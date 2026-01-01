"""
State Machine for Dolmenwood Virtual DM.

Implements the canonical state machine from Section 4 of the specification.
Only ONE state may be active at any time. Previous state is tracked for re-entry.

All transitions follow strict validation rules and are logged for debugging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.data_models import TransitionLog


class GameState(str, Enum):
    """
    Primary game states. Only ONE state may be active at any time.
    From Section 4.1 of the specification.

    Note: ENCOUNTER is a unified state for all encounters regardless of location
    (wilderness, dungeon, or settlement). The encounter engine tracks the origin
    context to know where to return after the encounter resolves.
    """

    WILDERNESS_TRAVEL = "wilderness_travel"
    DUNGEON_EXPLORATION = "dungeon_exploration"
    FAIRY_ROAD_TRAVEL = "fairy_road_travel"
    ENCOUNTER = "encounter"  # Unified encounter state for all locations
    COMBAT = "combat"
    SETTLEMENT_EXPLORATION = "settlement_exploration"
    SOCIAL_INTERACTION = "social_interaction"
    DOWNTIME = "downtime"


@dataclass
class StateTransition:
    """
    Defines a valid state transition.
    From Section 4.2 of the specification.
    """

    from_state: GameState
    to_state: GameState
    trigger: str
    description: str = ""

    def __hash__(self) -> int:
        return hash((self.from_state, self.to_state, self.trigger))


# Valid state transitions as defined in Section 4.2
# Updated to use unified ENCOUNTER state
VALID_TRANSITIONS: list[StateTransition] = [
    # Wilderness Travel transitions
    StateTransition(
        GameState.WILDERNESS_TRAVEL,
        GameState.ENCOUNTER,
        "encounter_triggered",
        "Encounter roll indicates encounter occurs",
    ),
    StateTransition(
        GameState.WILDERNESS_TRAVEL,
        GameState.DUNGEON_EXPLORATION,
        "enter_dungeon",
        "Party enters a dungeon or underground area",
    ),
    StateTransition(
        GameState.WILDERNESS_TRAVEL,
        GameState.SETTLEMENT_EXPLORATION,
        "enter_settlement",
        "Party enters a settlement",
    ),
    StateTransition(
        GameState.WILDERNESS_TRAVEL,
        GameState.DOWNTIME,
        "begin_rest",
        "Party begins extended rest or downtime",
    ),
    StateTransition(
        GameState.WILDERNESS_TRAVEL,
        GameState.FAIRY_ROAD_TRAVEL,
        "enter_fairy_road",
        "Party enters a fairy road through a fairy door",
    ),
    # Fairy Road Travel transitions
    StateTransition(
        GameState.FAIRY_ROAD_TRAVEL,
        GameState.ENCOUNTER,
        "encounter_triggered",
        "Encounter occurs on the fairy road",
    ),
    StateTransition(
        GameState.FAIRY_ROAD_TRAVEL,
        GameState.COMBAT,
        "fairy_road_combat",
        "Combat breaks out on fairy road",
    ),
    StateTransition(
        GameState.FAIRY_ROAD_TRAVEL,
        GameState.SOCIAL_INTERACTION,
        "initiate_conversation",
        "Party initiates conversation with fairy road denizen",
    ),
    StateTransition(
        GameState.FAIRY_ROAD_TRAVEL,
        GameState.WILDERNESS_TRAVEL,
        "exit_fairy_road",
        "Party exits fairy road at destination or strays from path",
    ),
    # Dungeon Exploration transitions
    StateTransition(
        GameState.DUNGEON_EXPLORATION,
        GameState.ENCOUNTER,
        "encounter_triggered",
        "Wandering monster check or room encounter triggers encounter",
    ),
    StateTransition(
        GameState.DUNGEON_EXPLORATION,
        GameState.WILDERNESS_TRAVEL,
        "exit_dungeon",
        "Party exits dungeon to wilderness",
    ),
    StateTransition(
        GameState.DUNGEON_EXPLORATION,
        GameState.DOWNTIME,
        "begin_rest",
        "Party begins rest in dungeon",
    ),
    # Settlement Exploration transitions
    StateTransition(
        GameState.SETTLEMENT_EXPLORATION,
        GameState.ENCOUNTER,
        "encounter_triggered",
        "Encounter triggered in settlement",
    ),
    StateTransition(
        GameState.SETTLEMENT_EXPLORATION,
        GameState.SOCIAL_INTERACTION,
        "initiate_conversation",
        "Party initiates conversation with NPC",
    ),
    StateTransition(
        GameState.SETTLEMENT_EXPLORATION,
        GameState.COMBAT,
        "settlement_combat",
        "Combat breaks out in settlement",
    ),
    StateTransition(
        GameState.SETTLEMENT_EXPLORATION,
        GameState.WILDERNESS_TRAVEL,
        "exit_settlement",
        "Party leaves settlement",
    ),
    StateTransition(
        GameState.SETTLEMENT_EXPLORATION,
        GameState.DOWNTIME,
        "begin_downtime",
        "Party begins downtime activities",
    ),
    StateTransition(
        GameState.SETTLEMENT_EXPLORATION,
        GameState.DUNGEON_EXPLORATION,
        "enter_dungeon",
        "Party enters dungeon from settlement",
    ),
    # Unified Encounter transitions
    StateTransition(
        GameState.ENCOUNTER,
        GameState.COMBAT,
        "encounter_to_combat",
        "Encounter escalates to combat (attack or hostile reaction)",
    ),
    StateTransition(
        GameState.ENCOUNTER,
        GameState.SOCIAL_INTERACTION,
        "encounter_to_parley",
        "Encounter leads to social interaction (parley, negotiation)",
    ),
    StateTransition(
        GameState.ENCOUNTER,
        GameState.WILDERNESS_TRAVEL,
        "encounter_end_wilderness",
        "Encounter resolved, return to wilderness travel",
    ),
    StateTransition(
        GameState.ENCOUNTER,
        GameState.DUNGEON_EXPLORATION,
        "encounter_end_dungeon",
        "Encounter resolved, return to dungeon exploration",
    ),
    StateTransition(
        GameState.ENCOUNTER,
        GameState.SETTLEMENT_EXPLORATION,
        "encounter_end_settlement",
        "Encounter resolved, return to settlement exploration",
    ),
    StateTransition(
        GameState.ENCOUNTER,
        GameState.FAIRY_ROAD_TRAVEL,
        "encounter_end_fairy_road",
        "Encounter resolved, return to fairy road travel",
    ),
    # Combat transitions
    StateTransition(
        GameState.COMBAT,
        GameState.WILDERNESS_TRAVEL,
        "combat_end_wilderness",
        "Combat ends, return to wilderness travel",
    ),
    StateTransition(
        GameState.COMBAT,
        GameState.DUNGEON_EXPLORATION,
        "combat_end_dungeon",
        "Combat ends, return to dungeon exploration",
    ),
    StateTransition(
        GameState.COMBAT,
        GameState.SETTLEMENT_EXPLORATION,
        "combat_end_settlement",
        "Combat ends in settlement",
    ),
    StateTransition(
        GameState.COMBAT,
        GameState.FAIRY_ROAD_TRAVEL,
        "combat_end_fairy_road",
        "Combat ends on fairy road",
    ),
    StateTransition(
        GameState.COMBAT,
        GameState.DOWNTIME,
        "combat_end_downtime",
        "Combat ends, return to rest/downtime (rest was interrupted)",
    ),
    StateTransition(
        GameState.COMBAT,
        GameState.SOCIAL_INTERACTION,
        "combat_to_parley",
        "Combat transitions to negotiation (surrender, etc.)",
    ),
    # Social Interaction transitions
    StateTransition(
        GameState.SOCIAL_INTERACTION,
        GameState.WILDERNESS_TRAVEL,
        "conversation_end_wilderness",
        "Conversation ends, return to wilderness",
    ),
    StateTransition(
        GameState.SOCIAL_INTERACTION,
        GameState.DUNGEON_EXPLORATION,
        "conversation_end_dungeon",
        "Conversation ends, return to dungeon",
    ),
    StateTransition(
        GameState.SOCIAL_INTERACTION,
        GameState.SETTLEMENT_EXPLORATION,
        "conversation_end_settlement",
        "Conversation ends, return to settlement",
    ),
    StateTransition(
        GameState.SOCIAL_INTERACTION,
        GameState.FAIRY_ROAD_TRAVEL,
        "conversation_end_fairy_road",
        "Conversation ends, return to fairy road",
    ),
    StateTransition(
        GameState.SOCIAL_INTERACTION,
        GameState.COMBAT,
        "conversation_escalates",
        "Conversation escalates to combat",
    ),
    # Downtime transitions
    StateTransition(
        GameState.DOWNTIME,
        GameState.WILDERNESS_TRAVEL,
        "downtime_end_wilderness",
        "Downtime ends, resume travel",
    ),
    StateTransition(
        GameState.DOWNTIME,
        GameState.DUNGEON_EXPLORATION,
        "downtime_end_dungeon",
        "Downtime ends, resume dungeon exploration",
    ),
    StateTransition(
        GameState.DOWNTIME,
        GameState.SETTLEMENT_EXPLORATION,
        "downtime_end_settlement",
        "Downtime ends, resume settlement exploration",
    ),
    StateTransition(
        GameState.DOWNTIME, GameState.COMBAT, "rest_interrupted", "Rest is interrupted by combat"
    ),
]


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


class StateMachine:
    """
    Manages game state transitions with validation and history tracking.

    The state machine is authoritative - all state changes must go through
    this class to maintain integrity.

    Attributes:
        current_state: The current active game state
        previous_state: The state before the current transition
        state_history: Complete history of all state transitions
        transition_callbacks: Functions called on specific transitions
    """

    def __init__(self, initial_state: GameState = GameState.WILDERNESS_TRAVEL):
        """
        Initialize the state machine.

        Args:
            initial_state: The starting state (default: WILDERNESS_TRAVEL)
        """
        self._current_state: GameState = initial_state
        self._previous_state: Optional[GameState] = None
        self._state_history: list[TransitionLog] = []
        self._transition_callbacks: dict[str, list[Callable]] = {}
        self._pre_transition_hooks: list[Callable] = []
        self._post_transition_hooks: list[Callable] = []

        # Build transition lookup for fast validation
        self._valid_transitions: dict[tuple[GameState, str], GameState] = {}
        for transition in VALID_TRANSITIONS:
            key = (transition.from_state, transition.trigger)
            self._valid_transitions[key] = transition.to_state

        # Log initial state
        self._log_transition(
            from_state="INIT", to_state=initial_state.value, trigger="initialization"
        )

    @property
    def current_state(self) -> GameState:
        """Get the current game state."""
        return self._current_state

    @property
    def previous_state(self) -> Optional[GameState]:
        """Get the previous game state (for return transitions)."""
        return self._previous_state

    @property
    def state_history(self) -> list[TransitionLog]:
        """Get the complete state transition history."""
        return self._state_history.copy()

    def can_transition(self, trigger: str) -> bool:
        """
        Check if a transition is valid from the current state.

        Args:
            trigger: The trigger event name

        Returns:
            True if the transition is valid, False otherwise
        """
        key = (self._current_state, trigger)
        return key in self._valid_transitions

    def get_valid_triggers(self) -> list[str]:
        """
        Get all valid triggers from the current state.

        Returns:
            List of trigger names that can be used from current state
        """
        triggers = []
        for (state, trigger), _ in self._valid_transitions.items():
            if state == self._current_state:
                triggers.append(trigger)
        return triggers

    def get_valid_transitions(self) -> list[StateTransition]:
        """
        Get all valid transitions from the current state.

        Returns:
            List of StateTransition objects available from current state
        """
        return [t for t in VALID_TRANSITIONS if t.from_state == self._current_state]

    def transition(self, trigger: str, context: Optional[dict[str, Any]] = None) -> GameState:
        """
        Attempt to transition to a new state.

        Args:
            trigger: The trigger event causing the transition
            context: Optional context data for the transition

        Returns:
            The new game state

        Raises:
            InvalidTransitionError: If the transition is not valid
        """
        context = context or {}

        # Validate transition
        key = (self._current_state, trigger)
        if key not in self._valid_transitions:
            valid_triggers = self.get_valid_triggers()
            raise InvalidTransitionError(
                f"Invalid transition: Cannot trigger '{trigger}' from state "
                f"'{self._current_state.value}'. Valid triggers: {valid_triggers}"
            )

        new_state = self._valid_transitions[key]
        old_state = self._current_state

        # Run pre-transition hooks
        for hook in self._pre_transition_hooks:
            hook(old_state, new_state, trigger, context)

        # Execute transition
        self._previous_state = old_state
        self._current_state = new_state

        # Log the transition
        self._log_transition(
            from_state=old_state.value, to_state=new_state.value, trigger=trigger, context=context
        )

        # Run post-transition hooks
        for hook in self._post_transition_hooks:
            hook(old_state, new_state, trigger, context)

        # Run specific transition callbacks
        callback_key = f"{old_state.value}:{trigger}"
        if callback_key in self._transition_callbacks:
            for callback in self._transition_callbacks[callback_key]:
                callback(old_state, new_state, context)

        return new_state

    def return_to_previous(self, context: Optional[dict[str, Any]] = None) -> GameState:
        """
        Return to the previous state (used after combat/social/encounter ends).

        This creates an appropriate trigger based on current and previous states.

        Args:
            context: Optional context data for the transition

        Returns:
            The previous game state

        Raises:
            InvalidTransitionError: If no valid return transition exists
        """
        if self._previous_state is None:
            raise InvalidTransitionError("No previous state to return to")

        # Determine the appropriate trigger based on states
        trigger_map = {
            # Combat endings
            (GameState.COMBAT, GameState.WILDERNESS_TRAVEL): "combat_end_wilderness",
            (GameState.COMBAT, GameState.DUNGEON_EXPLORATION): "combat_end_dungeon",
            (GameState.COMBAT, GameState.SETTLEMENT_EXPLORATION): "combat_end_settlement",
            (GameState.COMBAT, GameState.DOWNTIME): "combat_end_downtime",
            # Social interaction endings
            (
                GameState.SOCIAL_INTERACTION,
                GameState.WILDERNESS_TRAVEL,
            ): "conversation_end_wilderness",
            (
                GameState.SOCIAL_INTERACTION,
                GameState.DUNGEON_EXPLORATION,
            ): "conversation_end_dungeon",
            (
                GameState.SOCIAL_INTERACTION,
                GameState.SETTLEMENT_EXPLORATION,
            ): "conversation_end_settlement",
            # Encounter endings (unified state)
            (GameState.ENCOUNTER, GameState.WILDERNESS_TRAVEL): "encounter_end_wilderness",
            (GameState.ENCOUNTER, GameState.DUNGEON_EXPLORATION): "encounter_end_dungeon",
            (GameState.ENCOUNTER, GameState.SETTLEMENT_EXPLORATION): "encounter_end_settlement",
            (GameState.ENCOUNTER, GameState.FAIRY_ROAD_TRAVEL): "encounter_end_fairy_road",
            # Fairy road endings
            (GameState.COMBAT, GameState.FAIRY_ROAD_TRAVEL): "combat_end_fairy_road",
            (
                GameState.SOCIAL_INTERACTION,
                GameState.FAIRY_ROAD_TRAVEL,
            ): "conversation_end_fairy_road",
        }

        key = (self._current_state, self._previous_state)
        if key not in trigger_map:
            raise InvalidTransitionError(
                f"No valid return transition from {self._current_state.value} "
                f"to {self._previous_state.value}"
            )

        trigger = trigger_map[key]
        return self.transition(trigger, context)

    def force_state(
        self, new_state: GameState, reason: str, context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Force a state change without validation (for debugging/recovery only).

        WARNING: This bypasses all validation and should only be used for
        debugging or recovering from invalid states.

        Args:
            new_state: The state to force
            reason: Why this force is necessary
            context: Optional context data
        """
        context = context or {}
        context["forced"] = True
        context["force_reason"] = reason

        old_state = self._current_state
        self._previous_state = old_state
        self._current_state = new_state

        self._log_transition(
            from_state=old_state.value,
            to_state=new_state.value,
            trigger=f"FORCED: {reason}",
            context=context,
        )

    def register_callback(self, from_state: GameState, trigger: str, callback: Callable) -> None:
        """
        Register a callback for a specific transition.

        The callback will be called with (old_state, new_state, context)
        after the transition completes.

        Args:
            from_state: The starting state
            trigger: The trigger event
            callback: Function to call on this transition
        """
        key = f"{from_state.value}:{trigger}"
        if key not in self._transition_callbacks:
            self._transition_callbacks[key] = []
        self._transition_callbacks[key].append(callback)

    def register_pre_hook(self, hook: Callable) -> None:
        """
        Register a hook to run before any transition.

        The hook will be called with (old_state, new_state, trigger, context).

        Args:
            hook: Function to call before transitions
        """
        self._pre_transition_hooks.append(hook)

    def register_post_hook(self, hook: Callable) -> None:
        """
        Register a hook to run after any transition.

        The hook will be called with (old_state, new_state, trigger, context).

        Args:
            hook: Function to call after transitions
        """
        self._post_transition_hooks.append(hook)

    def _log_transition(
        self, from_state: str, to_state: str, trigger: str, context: Optional[dict[str, Any]] = None
    ) -> None:
        """Log a state transition."""
        log_entry = TransitionLog(
            timestamp=datetime.now(),
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            context=context or {},
        )
        self._state_history.append(log_entry)

        # Also log to RunLog for observability
        self._log_to_run_log(from_state, to_state, trigger, context)

    def _log_to_run_log(
        self,
        from_state: str,
        to_state: str,
        trigger: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log transition to the observability RunLog."""
        try:
            from src.observability.run_log import get_run_log

            get_run_log().log_transition(
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                context=context,
            )
        except ImportError:
            pass  # Observability module not available

    def get_state_info(self) -> dict[str, Any]:
        """
        Get information about the current state for display/debugging.

        Returns:
            Dictionary with state information
        """
        return {
            "current_state": self._current_state.value,
            "previous_state": self._previous_state.value if self._previous_state else None,
            "valid_triggers": self.get_valid_triggers(),
            "transition_count": len(self._state_history),
            "last_transition": self._state_history[-1] if self._state_history else None,
        }

    def is_exploration_state(self) -> bool:
        """Check if current state is an exploration state."""
        return self._current_state in {
            GameState.WILDERNESS_TRAVEL,
            GameState.DUNGEON_EXPLORATION,
            GameState.SETTLEMENT_EXPLORATION,
            GameState.FAIRY_ROAD_TRAVEL,
        }

    def is_encounter_state(self) -> bool:
        """Check if current state is the encounter state."""
        return self._current_state == GameState.ENCOUNTER

    def is_combat_state(self) -> bool:
        """Check if currently in combat."""
        return self._current_state == GameState.COMBAT

    def is_social_state(self) -> bool:
        """Check if currently in social interaction."""
        return self._current_state == GameState.SOCIAL_INTERACTION

    def get_return_state(self) -> Optional[GameState]:
        """
        Get the state to return to after current state ends.

        For combat/social/encounter, this is the previous state.
        For other states, returns None.
        """
        if self._current_state in {
            GameState.COMBAT,
            GameState.SOCIAL_INTERACTION,
            GameState.ENCOUNTER,
        }:
            return self._previous_state
        return None

    def __repr__(self) -> str:
        return f"StateMachine(current={self._current_state.value}, previous={self._previous_state})"
