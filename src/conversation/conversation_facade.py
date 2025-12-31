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
        self.mythic = MythicGME(rng=random.Random())

        # Upgrade D: Oracle enhancement for ambiguity detection
        self.oracle_enhancement = None
        if self.config.use_oracle_enhancement:
            from src.conversation.oracle_enhancement import OracleEnhancement
            self.oracle_enhancement = OracleEnhancement(self.mythic)

        # Track recent context for LLM parsing
        self._recent_actions: list[str] = []
        self._max_recent: int = 5

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
        # Meta
        # ------------------------------------------------------------------
        if action_id == "meta:status":
            return self._response([ChatMessage("system", self._status_summary())])

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
            result = self.dm.hex_crawl.interact_with_npc(hex_id, npc_id)
            msgs = [ChatMessage("system", result.get("message", "You interact."))]
            if result.get("interaction"):
                msgs.append(ChatMessage("dm", result["interaction"]))
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
            msgs = [ChatMessage("dm", rr.narration)] if rr.narration else [ChatMessage("system", "Resolved.")]
            return self._response(msgs)

        if action_id == "downtime:action":
            text = params.get("text", "")
            character_id = params.get("character_id") or self._default_character_id()
            rr = self.dm.downtime.handle_player_action(text, character_id)
            msgs = [ChatMessage("dm", rr.narration)] if rr.narration else [ChatMessage("system", "Resolved.")]
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

        return self._response([ChatMessage("system", f"Unrecognized action id: {action_id}")])

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

        # Default: echo as DM narration
        return self._response([ChatMessage("dm", text)], character_id=character_id)

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
            tp = getattr(self.dm.hex_crawl, "_travel_points_remaining", None)
            tpt = getattr(self.dm.hex_crawl, "_travel_points_total", None)
            if tp is not None and tpt is not None:
                parts.append(f"Travel Points: {tp}/{tpt}")
        if self.dm.current_state == GameState.DUNGEON_EXPLORATION:
            try:
                summ = self.dm.dungeon.get_exploration_summary()
                parts.append(f"Dungeon Turns since rest: {summ.get('turns_since_rest')}/5")
            except Exception:
                pass
        return "\n".join(parts)
