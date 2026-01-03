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

from src.game_state.state_machine import GameState

from src.conversation.types import TurnResponse, ChatMessage
from src.conversation.suggestion_builder import build_suggestions
from src.conversation.state_export import export_public_state, EventStream
from src.conversation.action_registry import get_default_registry, ActionRegistry

# Mythic oracle (for oracle enhancement feature)
from src.oracle.mythic_gme import MythicGME


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

                # P1-8: LLM suggested an action that's not currently available
                if intent.action_id != "unknown" and intent.action_id not in available_actions:
                    msg = (
                        f"I understood you want to '{intent.action_id}', but that action "
                        f"isn't available right now. Try asking for available options."
                    )
                    return self._response(
                        [ChatMessage("system", msg)],
                        requires_clarification=True,
                        clarification_prompt=msg,
                    )

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
        # Fallback: Legacy handlers for actions without registry executors
        # ------------------------------------------------------------------
        # NOTE (10.1): Most actions now have executors in ActionRegistry.
        # Only transition:* remains here as it handles dynamic state machine triggers.

        # State-machine trigger passthrough (debug/tooling)
        if action_id.startswith("transition:"):
            trigger = action_id.split(":", 1)[1]
            try:
                self.dm.controller.transition(trigger, context=params or {})
                return self._response([ChatMessage("system", f"Transitioned via trigger: {trigger}")])
            except Exception as e:
                return self._response([ChatMessage("system", f"Transition failed: {e}")])

        # ------------------------------------------------------------------
        # Unknown action_id - return error
        # ------------------------------------------------------------------
        return self._response([ChatMessage("system", f"Unknown action_id: {action_id}")])

    # ---------------------------------------------------------------------
    # NOTE (10.1): Combat and Fairy Road handlers removed.
    # All combat:* and fairy_road:* actions are now handled by ActionRegistry.
    # ---------------------------------------------------------------------

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
