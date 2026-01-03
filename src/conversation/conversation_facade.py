"""src.conversation.conversation_facade

Chat-first orchestration wrapper around the existing engines.

Key idea for the UI:
- The player mostly types natural language.
- The system *also* emits a small set of ranked, OSR/Dolmenwood-native suggested actions.
- Clicking a suggestion calls `handle_action(action_id, params)`.

This file wires those action ids to concrete engine calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING
import re
import random

if TYPE_CHECKING:
    from src.main import VirtualDM

from src.data_models import LightSourceType
from src.game_state.state_machine import GameState
from src.dungeon.dungeon_engine import DungeonActionType
from src.encounter.encounter_engine import EncounterAction

from src.conversation.types import TurnResponse, ChatMessage
from src.conversation.suggestion_builder import build_suggestions
from src.conversation.state_export import export_public_state, EventStream
from src.conversation.action_registry import get_default_registry, ActionRegistry

# Mythic oracle (present in this repo)
from src.oracle.mythic_gme import MythicGME, Likelihood


HEX_ID_RE = re.compile(r"\b\d{4}\b")


@dataclass
class ConversationConfig:
    """Toggles for the conversation layer."""

    include_state_snapshot: bool = True
    include_events: bool = True

    # Upgrade A: LLM intent parsing
    use_llm_intent_parsing: bool = True  # Try LLM parsing first
    llm_confidence_threshold: float = 0.7  # Minimum confidence to use LLM result

    # Upgrade D: Enhanced oracle integration
    use_oracle_enhancement: bool = True  # Detect ambiguity and offer oracle
    oracle_auto_suggest: bool = True  # Automatically suggest oracle for questions


class ConversationFacade:
    def __init__(self, dm: VirtualDM, *, config: Optional[ConversationConfig] = None):
        self.dm = dm
        self.config = config or ConversationConfig()
        self.events = EventStream() if self.config.include_events else None

        # Mythic oracle for uncertain questions
        from src.oracle.dice_rng_adapter import DiceRngAdapter
        self.mythic = MythicGME(rng=DiceRngAdapter("ConversationOracle"))

        # Upgrade D: Oracle enhancement for ambiguity detection
        self.oracle_enhancement = None
        if self.config.use_oracle_enhancement:
            from src.conversation.oracle_enhancement import OracleEnhancement
            self.oracle_enhancement = OracleEnhancement(self.mythic)

        # Track recent context for LLM parsing
        self._recent_actions: list[str] = []
        self._max_recent: int = 5

        # Action registry for unified action routing
        self._registry: ActionRegistry = get_default_registry()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def handle_chat(self, text: str, *, character_id: Optional[str] = None) -> TurnResponse:
        """Handle freeform player chat.

        Routing priority:
        1. Try LLM intent parsing if enabled and DM agent available
        2. Use pattern matching (hex IDs, keywords) as fallback
        3. Delegate to engine's handle_player_action()
        """

        text = (text or "").strip()
        if not text:
            return self._response([])

        character_id = character_id or self._default_character_id()

        # Try LLM intent parsing first (Upgrade A)
        if self.config.use_llm_intent_parsing and self.dm.dm_agent:
            intent_result = self._try_llm_intent_parse(text, character_id)
            if intent_result:
                return intent_result

        # Fall back to pattern matching
        if self.dm.current_state == GameState.WILDERNESS_TRAVEL:
            m = HEX_ID_RE.search(text)
            if m:
                return self.handle_action("wilderness:travel", {"hex_id": m.group(0)})

        # Minimal dungeon keyword shortcuts
        if self.dm.current_state == GameState.DUNGEON_EXPLORATION:
            lowered = text.lower().strip()
            if lowered in ("search", "rest", "map"):
                return self.handle_action(f"dungeon:{lowered}")

        return self._handle_freeform(text, character_id=character_id)

    def _try_llm_intent_parse(self, text: str, character_id: str) -> Optional[TurnResponse]:
        """
        Try to parse player intent using LLM.

        Returns TurnResponse if successful with high confidence, None otherwise.
        """
        try:
            # Get available actions for current state
            suggestions = build_suggestions(self.dm, character_id=character_id, limit=20)
            available_actions = [s.id for s in suggestions]

            # Get location context
            location_context = str(self.dm.controller.party_state.location)

            # Get recent context
            recent_context = "; ".join(self._recent_actions[-self._max_recent:])

            # Parse intent
            intent = self.dm.dm_agent.parse_intent(
                player_input=text,
                current_state=self.dm.current_state.value,
                available_actions=available_actions,
                location_context=location_context,
                recent_context=recent_context,
            )

            # Check confidence threshold
            if intent.confidence >= self.config.llm_confidence_threshold:
                # High confidence - execute the action
                if intent.action_id != "unknown" and intent.action_id in available_actions:
                    # Track the action for context
                    self._add_recent_action(f"{intent.action_id}: {text[:50]}")
                    return self.handle_action(intent.action_id, intent.params)

            # Clarification needed
            if intent.requires_clarification:
                return self._response(
                    [ChatMessage("system", intent.clarification_prompt)],
                    requires_clarification=True,
                    clarification_prompt=intent.clarification_prompt,
                )

            # Low confidence but no clarification - fall through to pattern matching
            return None

        except Exception as e:
            # LLM parsing failed - fall back to pattern matching
            import logging
            logging.getLogger(__name__).debug(f"LLM intent parse failed: {e}")
            return None

    def _add_recent_action(self, action_desc: str) -> None:
        """Track a recent action for context."""
        self._recent_actions.append(action_desc)
        if len(self._recent_actions) > self._max_recent:
            self._recent_actions.pop(0)

    def handle_action(self, action_id: str, params: Optional[dict[str, Any]] = None) -> TurnResponse:
        """Execute a clicked suggestion (action_id + params)."""

        params = params or {}

        # ------------------------------------------------------------------
        # Try ActionRegistry first (Upgrade B: Unified action routing)
        # ------------------------------------------------------------------
        spec = self._registry.get(action_id)
        if spec and spec.executor:
            result = self._registry.execute(self.dm, action_id, params)
            if result.get("success", False):
                msg = result.get("message", "Action completed.")
                narration = result.get("narration")
                messages = [ChatMessage("system", msg)]
                if narration:
                    messages.append(ChatMessage("dm", narration))
                return self._response(messages)
            else:
                # Executor returned failure - return error message
                return self._response([ChatMessage("system", result.get("message", "Action failed."))])

        # ------------------------------------------------------------------
        # Fallback: Legacy if-chain for actions without executors
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # Meta
        # ------------------------------------------------------------------
        if action_id == "meta:status":
            return self._response([ChatMessage("system", self._status_summary())])

        if action_id == "meta:factions":
            return self._response([ChatMessage("system", self._factions_summary())])

        # State-machine trigger passthrough (debug/tooling)
        if action_id.startswith("transition:"):
            trigger = action_id.split(":", 1)[1]
            try:
                self.dm.controller.transition(trigger, context=params or {})
                return self._response([ChatMessage("system", f"Transitioned via trigger: {trigger}")])
            except Exception as e:
                return self._response([ChatMessage("system", f"Transition failed: {e}")])

        # ------------------------------------------------------------------
        # Party utilities
        # ------------------------------------------------------------------
        if action_id == "party:light":
            raw = (params.get("light_source") or "torch").lower()
            ls = {"torch": LightSourceType.TORCH, "lantern": LightSourceType.LANTERN}.get(raw, LightSourceType.TORCH)
            try:
                self.dm.controller.activate_light_source(ls)
                ps = self.dm.controller.party_state
                return self._response(
                    [
                        ChatMessage(
                            "system",
                            f"Light source set to {ls.value} (remaining turns: {ps.light_remaining_turns}).",
                        )
                    ]
                )
            except Exception as e:
                return self._response([ChatMessage("system", f"Couldn't set light source: {e}")])

        # ------------------------------------------------------------------
        # Wilderness
        # ------------------------------------------------------------------
        if action_id == "wilderness:travel":
            hex_id = params.get("hex_id", "")
            result = self.dm.travel_to_hex(hex_id)
            msg = result.get("message") or f"Traveled to {hex_id}"
            narration = result.get("narration")
            messages = [ChatMessage("system", msg)]
            if narration:
                messages.append(ChatMessage("dm", narration))
            return self._response(messages)

        if action_id == "wilderness:look_around":
            hex_id = params.get("hex_id") or self._current_hex_id()
            try:
                hints = self.dm.hex_crawl.get_sensory_hints(hex_id)
            except Exception:
                hints = []
            try:
                overview = self.dm.hex_crawl.get_hex_overview(hex_id)
                visible = getattr(overview, "visible_locations", []) or []
            except Exception:
                visible = self.dm.hex_crawl.get_visible_pois(hex_id)

            lines = [f"Location: {hex_id}"]
            if hints:
                lines.append("Sensory hints:")
                lines.extend([f"- {h}" for h in hints[:6]])
            if visible:
                lines.append("Visible locations:")
                for v in visible[:6]:
                    if isinstance(v, dict):
                        t = v.get("type", "location")
                        b = v.get("brief")
                        lines.append(f"- {t}" + (f": {b}" if b else ""))
                    else:
                        lines.append(f"- {v}")
            return self._response([ChatMessage("system", "\n".join(lines))])

        if action_id == "wilderness:search_hex":
            hex_id = params.get("hex_id") or self._current_hex_id()
            result = self.dm.hex_crawl.search_hex(hex_id)
            return self._response([ChatMessage("system", result.get("message", "Searched the hex."))])

        if action_id == "wilderness:end_day":
            result = self.dm.hex_crawl.end_travel_day()
            return self._response([ChatMessage("system", result.get("message", "Ended the travel day."))])

        if action_id == "wilderness:approach_poi":
            hex_id = params.get("hex_id") or self._current_hex_id()
            poi_index = int(params.get("poi_index", 0))
            result = self.dm.hex_crawl.approach_poi(hex_id, poi_index)

            # Pull updated POI identity after approach
            poi_state = self.dm.hex_crawl.get_current_poi_state()
            poi_name = poi_state.get("poi_name") or "the location"

            messages = [ChatMessage("system", result.get("message", f"You approach {poi_name}."))]

            # Optional narrative flair
            try:
                summary = self.dm.hex_crawl.get_poi_visit_summary(hex_id)
                poi_type = summary.get("poi_type", "location")
                desc = summary.get("description", "")
                narration = self.dm.narrate_poi_approach(poi_name=poi_name, poi_type=poi_type, description=desc)
                if narration:
                    messages.append(ChatMessage("dm", narration))
            except Exception:
                pass

            return self._response(messages)

        if action_id == "wilderness:resolve_poi_hazard":
            hex_id = params.get("hex_id") or self._current_hex_id()
            hazard_index = int(params.get("hazard_index", 0))
            character_id = params.get("character_id") or self._default_character_id()
            approach_method = params.get("approach_method", "careful")

            result = self.dm.hex_crawl.resolve_poi_hazard(hex_id, hazard_index, character_id, approach_method)
            msgs = [ChatMessage("system", result.get("message", "Resolved hazard."))]
            if result.get("success") and result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:enter_poi":
            hex_id = params.get("hex_id") or self._current_hex_id()
            result = self.dm.hex_crawl.enter_poi(hex_id)

            if result.get("requires_entry_check"):
                return self._response(
                    [ChatMessage("system", result.get("message", "Entry requires conditions."))],
                    requires_clarification=True,
                    clarification_prompt="Provide payment/password/approach and try 'Enter (provide entry conditions)'.",
                )

            msgs = [ChatMessage("system", result.get("message", "You enter."))]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:enter_poi_with_conditions":
            hex_id = params.get("hex_id") or self._current_hex_id()
            payment = (params.get("payment") or "").strip()
            password = (params.get("password") or "").strip()
            approach = (params.get("approach") or "").strip() or "respectful"
            result = self.dm.hex_crawl.enter_poi_with_conditions(hex_id, payment=payment, password=password, approach=approach)
            msgs = [ChatMessage("system", result.get("message", "You attempt entry."))]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:leave_poi":
            hex_id = params.get("hex_id") or self._current_hex_id()
            result = self.dm.hex_crawl.leave_poi(hex_id)
            msgs = [ChatMessage("system", result.get("message", "You depart."))]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:talk_npc":
            hex_id = params.get("hex_id") or self._current_hex_id()
            npc_id = params.get("npc_id", "")
            npc_index = params.get("npc_index")

            # Support both npc_id and npc_index
            if npc_index is not None and not npc_id:
                result = self.dm.hex_crawl.talk_to_npc_by_index(hex_id, int(npc_index))
            elif npc_id:
                result = self.dm.hex_crawl.interact_with_npc(hex_id, npc_id)
            else:
                # No NPC specified - list available NPCs
                npcs = self.dm.hex_crawl.get_npcs_at_poi(hex_id)
                if not npcs:
                    return self._response([ChatMessage("system", "No NPCs present here.")])
                npc_list = ", ".join(n.get("name", "unknown") for n in npcs)
                return self._response([
                    ChatMessage("system", f"Available NPCs: {npc_list}. Specify npc_id or npc_index.")
                ])

            if not result.get("success"):
                return self._response([ChatMessage("system", result.get("error", "Could not talk to NPC."))])

            # Build response message
            npc_name = result.get("npc_name", "the NPC")
            msgs = [ChatMessage("system", f"You begin a conversation with {npc_name}.")]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:take_item":
            hex_id = params.get("hex_id") or self._current_hex_id()
            item_name = params.get("item_name", "")
            character_id = params.get("character_id") or self._default_character_id()
            result = self.dm.hex_crawl.take_item(hex_id, item_name, character_id)
            msgs = [ChatMessage("system", result.get("message", "Taken."))]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:search_location":
            hex_id = params.get("hex_id") or self._current_hex_id()
            loc = params.get("search_location", "")
            thorough = bool(params.get("thorough", False))
            result = self.dm.hex_crawl.search_poi_location(hex_id, loc, thorough)
            msgs = [ChatMessage("system", result.get("message", "Searched."))]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id == "wilderness:explore_feature":
            hex_id = params.get("hex_id") or self._current_hex_id()
            desc = params.get("feature_description", "")
            result = self.dm.hex_crawl.explore_poi_feature(hex_id, desc)
            msgs = [ChatMessage("system", result.get("message", "Explored."))]
            if result.get("description"):
                msgs.append(ChatMessage("dm", result["description"]))
            return self._response(msgs)

        if action_id in ("wilderness:forage", "wilderness:hunt"):
            character_id = params.get("character_id") or self._default_character_id()
            verb = "forage" if action_id.endswith("forage") else "hunt"
            rr = self.dm.hex_crawl.handle_player_action(verb, character_id)
            msgs = [ChatMessage("dm", rr.narration)] if rr.narration else [ChatMessage("system", "Resolved.")]
            return self._response(msgs)

        if action_id == "wilderness:enter_dungeon":
            hex_id = params.get("hex_id") or self._current_hex_id()
            dungeon_id = params.get("dungeon_id") or "dungeon"
            entrance_room = params.get("entrance_room") or "entrance"
            try:
                poi_config = self.dm.hex_crawl.get_poi_dungeon_config(hex_id)
                poi_config["hex_id"] = hex_id
            except Exception:
                poi_config = {"hex_id": hex_id}

            result = self.dm.dungeon.enter_dungeon(dungeon_id=dungeon_id, entry_room=entrance_room, poi_config=poi_config)
            msgs = [ChatMessage("system", result.get("message", f"Entered {dungeon_id}."))]
            if result.get("room_description"):
                msgs.append(ChatMessage("dm", result["room_description"]))
            return self._response(msgs)

        # ------------------------------------------------------------------
        # Dungeon
        # ------------------------------------------------------------------
        if action_id.startswith("dungeon:"):
            mapping: dict[str, DungeonActionType] = {
                "dungeon:move": DungeonActionType.MOVE,
                "dungeon:search": DungeonActionType.SEARCH,
                "dungeon:listen": DungeonActionType.LISTEN,
                "dungeon:open_door": DungeonActionType.OPEN_DOOR,
                "dungeon:pick_lock": DungeonActionType.PICK_LOCK,
                "dungeon:disarm_trap": DungeonActionType.DISARM_TRAP,
                "dungeon:rest": DungeonActionType.REST,
                "dungeon:map": DungeonActionType.MAP,
                "dungeon:fast_travel": DungeonActionType.FAST_TRAVEL,
            }

            if action_id == "dungeon:exit":
                result = self.dm.dungeon.exit_dungeon()
                return self._response([ChatMessage("system", result.get("message", "Exited dungeon."))])

            if action_id in ("dungeon:search", "dungeon:rest", "dungeon:map") and not params:
                params = {}

            if action_id not in mapping:
                return self._response([ChatMessage("system", f"Unknown dungeon action id: {action_id}")])

            action = mapping[action_id]
            turn = self.dm.dungeon.execute_turn(action, params or None)

            messages: list[ChatMessage] = []
            for m in (turn.messages or []):
                messages.append(ChatMessage("system", m))
            for w in (turn.warnings or []):
                messages.append(ChatMessage("system", f"Warning: {w}"))

            # Optional narration hook
            if self.dm.dm_agent and turn.action_result.get("message"):
                narration = self.dm.narrate_dungeon_event(
                    event_type=action.value,
                    event_description=turn.action_result.get("message", ""),
                    location_name=self._current_location_name(),
                )
                if narration:
                    messages.append(ChatMessage("dm", narration))

            return self._response(messages)

        # ------------------------------------------------------------------
        # Encounter
        # ------------------------------------------------------------------
        if action_id == "encounter:action":
            action_str = params.get("action", "")
            actor = params.get("actor", "party")
            try:
                action = EncounterAction(action_str)
            except Exception:
                return self._response([ChatMessage("system", f"Unknown encounter action: {action_str}")])

            result = self.dm.encounter.execute_action(action, actor=actor)
            messages = [ChatMessage("system", m) for m in (result.messages or [])]
            return self._response(messages)

        # ------------------------------------------------------------------
        # Settlement / Downtime (freeform for now)
        # ------------------------------------------------------------------
        if action_id == "settlement:action":
            text = params.get("text", "")
            character_id = params.get("character_id") or self._default_character_id()
            rr = self.dm.settlement.handle_player_action(text, character_id)
            # SettlementEngine.handle_player_action returns a dict
            if isinstance(rr, dict):
                msg = rr.get("message", "Resolved.")
                msgs = [ChatMessage("system", msg)]
            elif hasattr(rr, 'narration') and rr.narration:
                msgs = [ChatMessage("dm", rr.narration)]
            else:
                msgs = [ChatMessage("system", "Resolved.")]
            return self._response(msgs)

        if action_id == "downtime:action":
            text = params.get("text", "")
            character_id = params.get("character_id") or self._default_character_id()
            rr = self.dm.downtime.handle_player_action(text, character_id)
            # DowntimeResult uses .events list, not .narration
            if hasattr(rr, 'events') and rr.events:
                msgs = [ChatMessage("system", event) for event in rr.events]
            else:
                msgs = [ChatMessage("system", "Resolved.")]
            return self._response(msgs)

        # ------------------------------------------------------------------
        # Mythic oracle
        # ------------------------------------------------------------------
        if action_id == "oracle:fate_check":
            q = (params.get("question") or "").strip()
            like = (params.get("likelihood") or "fifty_fifty").strip().lower()

            if not q:
                return self._response(
                    [ChatMessage("system", "Oracle requires a yes/no question.")],
                    requires_clarification=True,
                    clarification_prompt="Ask a yes/no question, e.g. 'Is the door trapped?'",
                )

            likelihood = {
                "impossible": Likelihood.IMPOSSIBLE,
                "very_unlikely": Likelihood.VERY_UNLIKELY,
                "unlikely": Likelihood.UNLIKELY,
                "fifty_fifty": Likelihood.FIFTY_FIFTY,
                "likely": Likelihood.LIKELY,
                "very_likely": Likelihood.VERY_LIKELY,
                "near_sure_thing": Likelihood.NEAR_SURE_THING,
                "a_sure_thing": Likelihood.A_SURE_THING,
                "has_to_be": Likelihood.HAS_TO_BE,
            }.get(like, Likelihood.FIFTY_FIFTY)

            r = self.mythic.fate_check(q, likelihood)
            result_str = r.result.value.replace("_", " ").title()
            msg = f"Oracle: {result_str} (roll={r.roll}, chaos={r.chaos_factor})"
            if r.random_event_triggered and r.random_event:
                msg += f" [Random Event: {r.random_event}]"
            return self._response([ChatMessage("system", msg)])

        if action_id == "oracle:random_event":
            ev = self.mythic.generate_random_event()
            msg = f"Random Event — Focus: {ev.focus.value}; Meaning: {ev.action} / {ev.subject}"
            return self._response([ChatMessage("system", msg)])

        if action_id == "oracle:detail_check":
            m = self.mythic.detail_check()
            msg = f"Detail Check — {m.action} / {m.subject}"
            return self._response([ChatMessage("system", msg)])

        # ------------------------------------------------------------------
        # Combat actions
        # ------------------------------------------------------------------
        if action_id.startswith("combat:"):
            return self._handle_combat_action(action_id, params)

        # ------------------------------------------------------------------
        # Fairy Road actions
        # ------------------------------------------------------------------
        if action_id.startswith("fairy_road:"):
            return self._handle_fairy_road_action(action_id, params)

        return self._response([ChatMessage("system", f"Unrecognized action id: {action_id}")])

    # ---------------------------------------------------------------------
    # Combat handlers
    # ---------------------------------------------------------------------
    def _handle_combat_action(self, action_id: str, params: dict[str, Any]) -> TurnResponse:
        """Handle combat action IDs."""
        combat_engine = self.dm.controller.combat_engine

        if action_id == "combat:resolve_round":
            if not combat_engine or not combat_engine.is_in_combat():
                return self._response([ChatMessage("system", "No active combat.")])

            # Build default party actions (attack nearest enemy)
            party_actions = self._build_default_party_attacks(combat_engine)

            # Execute round - enemies are auto-generated
            result = combat_engine.execute_round(party_actions)

            messages = []
            if result.get("success"):
                for event in result.get("round_events", []):
                    messages.append(ChatMessage("system", event))
                if result.get("combat_ended"):
                    messages.append(ChatMessage("system", f"Combat ended: {result.get('end_reason', 'unknown')}"))
            else:
                messages.append(ChatMessage("system", result.get("message", "Combat round failed.")))

            return self._response(messages)

        if action_id == "combat:flee":
            if not combat_engine or not combat_engine.is_in_combat():
                return self._response([ChatMessage("system", "No active combat.")])

            result = combat_engine.attempt_flee()
            messages = [ChatMessage("system", result.get("message", "Flee attempt resolved."))]
            if result.get("success"):
                messages.append(ChatMessage("system", "The party escapes!"))
            else:
                messages.append(ChatMessage("system", "The party cannot escape!"))
            return self._response(messages)

        if action_id == "combat:parley":
            if not combat_engine or not combat_engine.is_in_combat():
                return self._response([ChatMessage("system", "No active combat.")])

            # Attempt to pause combat for negotiation
            messages = [ChatMessage("system", "You attempt to parley mid-combat...")]
            # This would transition to social interaction if successful
            # For now, just acknowledge the attempt
            messages.append(ChatMessage("system", "Parley during combat is not yet fully implemented."))
            return self._response(messages)

        if action_id == "combat:status":
            if not combat_engine or not combat_engine.is_in_combat():
                return self._response([ChatMessage("system", "No active combat.")])

            summary = combat_engine.get_combat_summary()
            lines = ["Combat Status:"]
            lines.append(f"Round: {summary.get('round', 1)}")
            for c in summary.get("combatants", []):
                status = f"{c.get('name')}: HP {c.get('hp_current')}/{c.get('hp_max')}"
                if c.get("is_defeated"):
                    status += " [DEFEATED]"
                lines.append(f"  {status}")
            return self._response([ChatMessage("system", "\n".join(lines))])

        if action_id == "combat:end":
            if combat_engine and combat_engine.is_in_combat():
                combat_engine.end_combat("player_request")
            # Transition back to previous state
            try:
                self.dm.controller.transition("combat_resolved")
            except Exception:
                pass
            return self._response([ChatMessage("system", "Combat ended.")])

        return self._response([ChatMessage("system", f"Unknown combat action: {action_id}")])

    def _build_default_party_attacks(self, combat_engine) -> list[dict[str, Any]]:
        """Build default melee attack actions for all party members."""
        from src.combat.combat_engine import CombatActionType

        party_actions = []
        combat_state = combat_engine._combat_state
        if not combat_state:
            return party_actions

        # Get alive party combatants and enemies
        party = [c for c in combat_state.combatants if c.side == "party" and not c.is_defeated]
        enemies = [c for c in combat_state.combatants if c.side == "enemy" and not c.is_defeated]

        if not enemies:
            return party_actions

        # Each party member attacks the first available enemy
        for pc in party:
            party_actions.append({
                "combatant_id": pc.combatant_id,
                "action_type": CombatActionType.MELEE_ATTACK.value,
                "target_id": enemies[0].combatant_id,
            })

        return party_actions

    # ---------------------------------------------------------------------
    # Fairy Road handlers
    # ---------------------------------------------------------------------
    def _handle_fairy_road_action(self, action_id: str, params: dict[str, Any]) -> TurnResponse:
        """Handle fairy road action IDs."""
        from src.fairy_roads.fairy_road_engine import (
            get_fairy_road_engine,
            FairyRoadPhase,
            reset_fairy_road_engine,
        )

        engine = get_fairy_road_engine(self.dm.controller)

        if action_id == "fairy_road:enter":
            road_id = params.get("road_id", "")
            hex_id = params.get("hex_id") or self._current_hex_id()
            destination = params.get("destination_hex_id")

            result = engine.enter_fairy_road(road_id, hex_id, destination)

            messages = [ChatMessage("system", msg) for msg in result.messages]
            if not result.success:
                return self._response(messages)

            # Add atmospheric narration if LLM is available
            if self.dm.dm_agent and result.success:
                narration = self.dm.dm_agent.generate(
                    prompt=f"Narrate stepping through a fairy door onto {result.door_name}.",
                    context={"road_name": result.road_id, "door_name": result.door_name},
                    max_tokens=150,
                )
                if narration:
                    messages.append(ChatMessage("dm", narration))

            return self._response(messages)

        if action_id == "fairy_road:travel_segment":
            if not engine.is_active():
                return self._response([ChatMessage("system", "Not on a fairy road.")])

            result = engine.travel_segment()
            messages = [ChatMessage("system", msg) for msg in result.messages]

            # If encounter triggered, prompt for encounter resolution
            if result.encounter_triggered:
                messages.append(ChatMessage("system", "An encounter awaits! Choose to face it or try to evade."))

            return self._response(messages)

        if action_id == "fairy_road:resolve_encounter":
            if not engine.is_active():
                return self._response([ChatMessage("system", "Not on a fairy road.")])

            # Trigger the encounter transition
            result = engine.trigger_encounter_transition()
            if result.get("success"):
                return self._response([ChatMessage("system", result.get("message", "Encounter begins!"))])
            else:
                return self._response([ChatMessage("system", result.get("message", "No encounter to resolve."))])

        if action_id == "fairy_road:flee_encounter":
            if not engine.is_active():
                return self._response([ChatMessage("system", "Not on a fairy road.")])

            # Skip the encounter and continue
            result = engine.resume_after_encounter()
            messages = [ChatMessage("system", "You evade the encounter and continue on the road...")]
            messages.extend([ChatMessage("system", msg) for msg in result.messages])
            return self._response(messages)

        if action_id == "fairy_road:explore_location":
            if not engine.is_active():
                return self._response([ChatMessage("system", "Not on a fairy road.")])

            summary = engine.get_travel_summary()
            state = engine.get_travel_state()

            if state and state.last_location_entry:
                location = state.last_location_entry
                messages = [
                    ChatMessage("system", f"Location: {location.summary}"),
                ]
                # Could expand with more location interaction later
                return self._response(messages)

            return self._response([ChatMessage("system", "No location to explore.")])

        if action_id == "fairy_road:continue_past":
            if not engine.is_active():
                return self._response([ChatMessage("system", "Not on a fairy road.")])

            result = engine.resume_after_location()
            messages = [ChatMessage("system", msg) for msg in result.messages]
            return self._response(messages)

        if action_id == "fairy_road:exit":
            if not engine.is_active():
                return self._response([ChatMessage("system", "Not on a fairy road.")])

            exit_hex = params.get("exit_hex_id")
            result = engine.exit_fairy_road(exit_hex)

            messages = [ChatMessage("system", msg) for msg in result.messages]
            if result.success and result.mortal_time_passed:
                messages.append(ChatMessage("system", f"Time passed in mortal world: {result.mortal_time_passed}"))

            return self._response(messages)

        if action_id == "fairy_road:stray":
            return self._response([
                ChatMessage("system", "You intentionally leave the path..."),
                ChatMessage("system", "This is dangerous and not yet fully implemented."),
            ])

        if action_id == "fairy_road:status":
            summary = engine.get_travel_summary()
            if not summary.get("active"):
                return self._response([ChatMessage("system", "Not currently on a fairy road.")])

            lines = [
                f"Road: {summary.get('road_name', 'Unknown')}",
                f"Phase: {summary.get('phase', 'unknown')}",
                f"Segment: {summary.get('segment', 0)}/{summary.get('total_segments', 0)}",
                f"Entry: {summary.get('entry_door', 'Unknown')}",
            ]
            if summary.get("destination_door"):
                lines.append(f"Destination: {summary.get('destination_door')}")
            lines.append(f"Subjective time: {summary.get('subjective_turns', 0)} turns")
            lines.append(f"Encounters: {summary.get('encounters_triggered', 0)}")

            return self._response([ChatMessage("system", "\n".join(lines))])

        if action_id == "fairy_road:find_door":
            hex_id = self._current_hex_id()
            doors = engine.can_enter_from_hex(hex_id)

            if not doors:
                return self._response([ChatMessage("system", f"No fairy doors found in hex {hex_id}.")])

            lines = [f"Fairy doors in hex {hex_id}:"]
            for door in doors:
                lines.append(f"  - {door.get('door_name')} → {door.get('road_name')}")

            return self._response([ChatMessage("system", "\n".join(lines))])

        return self._response([ChatMessage("system", f"Unknown fairy road action: {action_id}")])

    # ---------------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------------
    def _handle_freeform(self, text: str, *, character_id: str) -> TurnResponse:
        """Delegate to the appropriate engine's handle_player_action() for the current mode."""

        state = self.dm.current_state

        # Upgrade D: Check for ambiguity and offer oracle
        if self.oracle_enhancement and self.config.oracle_auto_suggest:
            detection = self.oracle_enhancement.detect_ambiguity(
                text, state.value
            )
            if detection.is_ambiguous and detection.oracle_suggestions:
                # Offer oracle options alongside the action
                oracle_msg = ChatMessage("system", detection.clarification_prompt)
                oracle_actions = self.oracle_enhancement.format_oracle_options(detection)

                # Still try to process the action, but with oracle suggestions
                response = self._process_freeform_action(text, state, character_id)

                # Add oracle suggestion to messages
                if oracle_actions:
                    response.messages.insert(0, oracle_msg)
                    # Add oracle actions to suggestions
                    from src.conversation.types import SuggestedAction
                    for oa in oracle_actions:
                        response.suggested_actions.insert(0, SuggestedAction(
                            id=oa["id"],
                            label=oa["label"],
                            params=oa.get("params", {}),
                            safe_to_execute=True,
                            help="Use the Oracle to resolve uncertainty"
                        ))

                return response

        return self._process_freeform_action(text, state, character_id)

    def _process_freeform_action(
        self, text: str, state: GameState, character_id: str
    ) -> TurnResponse:
        """Process a freeform action for the current game state."""
        if state == GameState.WILDERNESS_TRAVEL:
            rr = self.dm.hex_crawl.handle_player_action(text, character_id)
            msgs: list[ChatMessage] = []
            if rr.narration:
                msgs.append(ChatMessage("dm", rr.narration))
            else:
                msgs.append(ChatMessage("system", "Resolved action (no narration)."))
            if rr.narration_context.rule_reference:
                msgs.append(ChatMessage("system", f"Rule: {rr.narration_context.rule_reference}"))
            for w in (rr.narration_context.warnings or []):
                msgs.append(ChatMessage("system", f"Warning: {w}"))
            for e in (rr.narration_context.errors or []):
                msgs.append(ChatMessage("system", f"Error: {e}"))
            return self._response(msgs, character_id=character_id)

        if state == GameState.DUNGEON_EXPLORATION:
            rr = self.dm.dungeon.handle_player_action(text, character_id)
            msgs = [ChatMessage("dm", rr.narration)] if rr.narration else [ChatMessage("system", "Resolved.")]
            if rr.narration_context.rule_reference:
                msgs.append(ChatMessage("system", f"Rule: {rr.narration_context.rule_reference}"))
            return self._response(msgs, character_id=character_id)

        if state == GameState.SETTLEMENT_EXPLORATION:
            rr = self.dm.settlement.handle_player_action(text, character_id)
            msgs = [ChatMessage("dm", rr.narration)] if rr.narration else [ChatMessage("system", "Resolved.")]
            return self._response(msgs, character_id=character_id)

        if state == GameState.DOWNTIME:
            rr = self.dm.downtime.handle_player_action(text, character_id)
            msgs = [ChatMessage("dm", rr.narration)] if rr.narration else [ChatMessage("system", "Resolved.")]
            return self._response(msgs, character_id=character_id)

        # Social interaction: route freeform text to social:say
        if state == GameState.SOCIAL_INTERACTION:
            return self.handle_action("social:say", {"text": text})

        # Combat requires mechanical resolution
        if state == GameState.COMBAT:
            return self._response(
                [ChatMessage("system", "Combat requires selecting an action. Use the numbered options above.")],
                character_id=character_id,
            )

        # Fairy road travel requires choosing travel actions
        if state == GameState.FAIRY_ROAD_TRAVEL:
            return self._response(
                [ChatMessage("system", "While traveling on the fairy road, select an action from the options above.")],
                character_id=character_id,
            )

        # Default: return safe instruction for unsupported states
        return self._response(
            [ChatMessage("system", f"Freeform input not supported in {state.value} state. Use the numbered options.")],
            character_id=character_id,
        )

    def _response(
        self,
        messages: list[ChatMessage],
        *,
        character_id: Optional[str] = None,
        requires_clarification: bool = False,
        clarification_prompt: Optional[str] = None,
    ) -> TurnResponse:
        resp = TurnResponse(messages=messages)
        resp.suggested_actions = build_suggestions(self.dm, character_id=character_id)

        if self.config.include_state_snapshot:
            resp.public_state = export_public_state(self.dm)

        if self.config.include_events and self.events:
            resp.events = self.events.drain()

        resp.requires_clarification = requires_clarification
        resp.clarification_prompt = clarification_prompt
        return resp

    def _default_character_id(self) -> str:
        chars = self.dm.controller.get_active_characters()
        if chars:
            return chars[0].character_id
        all_chars = self.dm.controller.get_all_characters()
        return all_chars[0].character_id if all_chars else "party"

    def _current_hex_id(self) -> str:
        return self.dm.controller.party_state.location.location_id

    def _current_location_name(self) -> str:
        return str(self.dm.controller.party_state.location)

    def _status_summary(self) -> str:
        ps = self.dm.controller.party_state
        ws = self.dm.controller.world_state
        parts = [f"Mode: {self.dm.current_state.value}"]
        parts.append(f"Location: {ps.location.location_id} ({ps.location.location_type})")
        parts.append(f"Time: {ws.current_date} {ws.current_time}")
        if ps.active_light_source and ps.light_remaining_turns > 0:
            parts.append(f"Light: {ps.active_light_source} ({ps.light_remaining_turns} turn(s) left)")
        else:
            parts.append("Light: none")
        if self.dm.current_state == GameState.WILDERNESS_TRAVEL:
            # Use public accessors (Phase 6: no private field access)
            try:
                tp = self.dm.hex_crawl.get_travel_points_remaining()
                tpt = self.dm.hex_crawl.get_travel_points_total()
                parts.append(f"Travel Points: {tp}/{tpt}")
            except Exception:
                pass  # Travel points not available
        if self.dm.current_state == GameState.DUNGEON_EXPLORATION:
            try:
                summ = self.dm.dungeon.get_exploration_summary()
                parts.append(f"Dungeon Turns since rest: {summ.get('turns_since_rest')}/5")
            except Exception:
                pass
        return "\n".join(parts)

    def _factions_summary(self) -> str:
        """Generate a summary of faction status."""
        from src.factions import get_factions_summary
        if not hasattr(self.dm, "factions") or not self.dm.factions:
            return "Faction system not initialized."
        return get_factions_summary(self.dm.factions)
