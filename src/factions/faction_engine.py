"""
Core Faction Engine for Dolmenwood Virtual DM.

Implements:
- Weekly faction turn cadence (7-day cycles)
- Per-faction dynamic state management
- Deterministic action selection and progress
- Effect application on action completion
- Integration with DiceRoller for reproducibility

Core philosophy:
- Python is the referee; the LLM is the narrator
- All RNG goes through DiceRoller for determinism
- State changes are centralized here
- System remains playable with LLM disabled
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from src.data_models import DiceRoller
from src.factions.faction_effects import EffectResult, FactionEffectsInterpreter
from src.factions.faction_models import (
    ActionInstance,
    ActionTemplate,
    FactionDefinition,
    FactionLogEntry,
    FactionRules,
    FactionTurnState,
    PartyFactionState,
    Territory,
)

if TYPE_CHECKING:
    from src.factions.faction_loader import FactionLoader
    from src.factions.faction_relations import FactionRelations
    from src.factions.faction_oracle import FactionOracle, OracleEvent

logger = logging.getLogger(__name__)


@dataclass
class ActionRollResult:
    """Result of a single action's progress roll."""
    action_id: str
    roll: int
    modifier: int
    total: int
    delta: int
    new_progress: int
    segments: int
    completed: bool
    complication: bool
    effects_applied: list[EffectResult] = field(default_factory=list)
    oracle_event: Optional[Any] = None  # OracleEvent if complication triggered


@dataclass
class FactionCycleResult:
    """Result of a single faction's turn within a cycle."""
    faction_id: str
    actions: list[ActionRollResult] = field(default_factory=list)
    actions_replaced: list[str] = field(default_factory=list)
    territory_points: int = 0
    level: int = 1


@dataclass
class CycleResult:
    """Result of a complete faction cycle."""
    cycle_number: int
    date: str
    faction_results: list[FactionCycleResult] = field(default_factory=list)
    rumors_generated: list[dict[str, Any]] = field(default_factory=list)
    oracle_events: list[Any] = field(default_factory=list)  # OracleEvent list


class FactionEngine:
    """
    Core faction simulation engine.

    Manages faction turns on a weekly cadence, processing all faction
    actions and applying effects. Designed to integrate with TimeTracker
    via day callbacks.
    """

    def __init__(
        self,
        rules: FactionRules,
        definitions: dict[str, FactionDefinition],
        relations: Optional["FactionRelations"] = None,
        oracle: Optional["FactionOracle"] = None,
    ):
        """
        Initialize the faction engine.

        Args:
            rules: Faction rules configuration
            definitions: Dict of faction_id -> FactionDefinition
            relations: Optional faction relations for modifiers
            oracle: Optional FactionOracle for complications and contested actions
        """
        self._rules = rules
        self._definitions = definitions
        self._relations = relations
        self._oracle = oracle
        self._effects = FactionEffectsInterpreter()

        # Dynamic state
        self._faction_states: dict[str, FactionTurnState] = {}
        self._party_state: Optional[PartyFactionState] = None
        self._days_accumulated: int = 0
        self._cycles_completed: int = 0
        self._current_date: str = ""

        # Callbacks for external notifications
        self._cycle_callbacks: list[Callable[[CycleResult], None]] = []

        # Initialize faction states from definitions
        self._initialize_faction_states()

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def _initialize_faction_states(self) -> None:
        """Initialize dynamic state for all defined factions."""
        for faction_id, definition in self._definitions.items():
            state = FactionTurnState(faction_id=faction_id)

            # Initialize territory from home_territory
            if definition.home_territory:
                state.territory = Territory.from_home_territory(definition.home_territory)

            # Initialize starting actions
            for action_id in definition.starting_actions[:3]:  # Max 3 actions
                template = definition.get_action_template(action_id)
                if template:
                    segments = template.segments
                    if segments is None:
                        segments = self._rules.get_default_segments(template.scope)

                    action = ActionInstance(
                        action_id=action_id,
                        goal_id=template.goal_id,
                        progress=0,
                        segments=segments,
                        started_on=self._current_date,
                    )
                    state.active_actions.append(action)

            self._faction_states[faction_id] = state

    def reset_state(self) -> None:
        """Reset all dynamic state (for new game)."""
        self._faction_states.clear()
        self._days_accumulated = 0
        self._cycles_completed = 0
        self._current_date = ""
        self._effects = FactionEffectsInterpreter()
        self._initialize_faction_states()

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def rules(self) -> FactionRules:
        """Get faction rules."""
        return self._rules

    @property
    def definitions(self) -> dict[str, FactionDefinition]:
        """Get faction definitions."""
        return self._definitions

    @property
    def faction_states(self) -> dict[str, FactionTurnState]:
        """Get all faction states."""
        return self._faction_states

    @property
    def party_state(self) -> Optional[PartyFactionState]:
        """Get party faction state."""
        return self._party_state

    @property
    def oracle(self) -> Optional["FactionOracle"]:
        """Get the faction oracle (if enabled)."""
        return self._oracle

    def set_oracle(self, oracle: Optional["FactionOracle"]) -> None:
        """Set or replace the faction oracle."""
        self._oracle = oracle

    @property
    def days_accumulated(self) -> int:
        """Get days accumulated toward next cycle."""
        return self._days_accumulated

    @property
    def cycles_completed(self) -> int:
        """Get total cycles completed."""
        return self._cycles_completed

    @property
    def effects_interpreter(self) -> FactionEffectsInterpreter:
        """Get the effects interpreter."""
        return self._effects

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    def set_party_state(self, party_state: PartyFactionState) -> None:
        """Set the party faction state."""
        self._party_state = party_state

    def set_current_date(self, date_str: str) -> None:
        """Set the current game date (for logging)."""
        self._current_date = date_str

    def get_faction_state(self, faction_id: str) -> Optional[FactionTurnState]:
        """Get state for a specific faction."""
        return self._faction_states.get(faction_id)

    def get_faction_level(self, faction_id: str) -> int:
        """Get the level of a faction based on territory points."""
        state = self._faction_states.get(faction_id)
        if not state:
            return 1
        points = state.territory.compute_points(self._rules.territory_point_values)
        return self._rules.get_level_for_points(points)

    def get_actions_per_turn(self, faction_id: str) -> int:
        """Get the number of actions a faction can take per turn."""
        level = self.get_faction_level(faction_id)
        return self._rules.actions_per_turn_by_level.get(level, 1)

    def register_cycle_callback(self, callback: Callable[[CycleResult], None]) -> None:
        """Register a callback for cycle completion."""
        self._cycle_callbacks.append(callback)

    # =========================================================================
    # TIME INTEGRATION
    # =========================================================================

    def on_days_advanced(self, days_passed: int) -> Optional[CycleResult]:
        """
        Callback for TimeTracker day advancement.

        Accumulates days and triggers faction cycle when cadence is reached.

        Args:
            days_passed: Number of days that passed

        Returns:
            CycleResult if a cycle was triggered, None otherwise
        """
        self._days_accumulated += days_passed

        if self._days_accumulated >= self._rules.turn_cadence_days:
            # Reset accumulator and run cycle
            self._days_accumulated = 0
            return self.run_cycle()

        return None

    # =========================================================================
    # FACTION CYCLE
    # =========================================================================

    def run_cycle(self) -> CycleResult:
        """
        Run a complete faction cycle.

        Processes all factions, rolling for each active action and
        applying effects for completed actions.

        Returns:
            CycleResult with all faction results
        """
        self._cycles_completed += 1

        # Reset oracle cycle counter if oracle is present
        if self._oracle:
            self._oracle.reset_cycle_counter()

        result = CycleResult(
            cycle_number=self._cycles_completed,
            date=self._current_date,
        )

        # Process each faction
        for faction_id in sorted(self._faction_states.keys()):
            faction_result = self._process_faction_turn(faction_id)
            result.faction_results.append(faction_result)

            # Collect oracle events from action results
            for action_result in faction_result.actions:
                if action_result.oracle_event is not None:
                    result.oracle_events.append(action_result.oracle_event)

        # Collect rumors generated during this cycle
        result.rumors_generated = self._effects.clear_pending_rumors()

        # Notify callbacks
        for callback in self._cycle_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Cycle callback error: {e}")

        return result

    def _process_faction_turn(self, faction_id: str) -> FactionCycleResult:
        """
        Process a single faction's turn.

        Args:
            faction_id: The faction to process

        Returns:
            FactionCycleResult with action results
        """
        state = self._faction_states.get(faction_id)
        definition = self._definitions.get(faction_id)

        if not state or not definition:
            return FactionCycleResult(faction_id=faction_id)

        result = FactionCycleResult(faction_id=faction_id)

        # Calculate territory points and level
        result.territory_points = state.territory.compute_points(
            self._rules.territory_point_values
        )
        result.level = self._rules.get_level_for_points(result.territory_points)

        # Determine how many actions this faction gets
        actions_this_turn = self._rules.actions_per_turn_by_level.get(result.level, 1)

        # Get modifiers for this cycle
        modifiers = self._get_cycle_modifiers(state)

        # Process each active action (up to actions_this_turn)
        actions_to_process = min(actions_this_turn, len(state.active_actions))
        completed_indices = []

        for i in range(actions_to_process):
            action = state.active_actions[i]
            template = definition.get_action_template(action.action_id)

            action_result = self._roll_action_progress(
                state=state,
                action=action,
                template=template,
                modifiers=modifiers,
            )
            result.actions.append(action_result)

            # Log this action
            log_entry = FactionLogEntry(
                date=self._current_date,
                action_id=action.action_id,
                roll=action_result.roll,
                modifier=action_result.modifier,
                delta=action_result.delta,
                completed=action_result.completed,
                effects_applied=[e.description for e in action_result.effects_applied],
            )
            state.log.append(log_entry)

            if action_result.completed:
                completed_indices.append(i)

        # Replace completed actions (process in reverse to maintain indices)
        for i in sorted(completed_indices, reverse=True):
            old_action = state.active_actions.pop(i)
            result.actions_replaced.append(old_action.action_id)

            # Select a replacement action
            new_action = self._select_replacement_action(definition, state)
            if new_action:
                state.active_actions.insert(i, new_action)

        # Clear cycle modifiers
        state.modifiers_next_cycle.clear()

        return result

    def _roll_action_progress(
        self,
        state: FactionTurnState,
        action: ActionInstance,
        template: Optional[ActionTemplate],
        modifiers: dict[str, int],
    ) -> ActionRollResult:
        """
        Roll for progress on a single action.

        Args:
            state: The faction's state
            action: The action instance
            template: The action template (may be None)
            modifiers: Dict of action_id -> modifier

        Returns:
            ActionRollResult with roll details
        """
        # Get modifier for this action
        modifier = modifiers.get(action.action_id, 0)
        modifier += modifiers.get("all", 0)

        # Cap modifier
        modifier = max(-self._rules.roll_mod_cap, min(self._rules.roll_mod_cap, modifier))

        # Roll the die
        dice = DiceRoller()
        roll_result = dice.roll_d6(
            reason=f"Faction {state.faction_id} action {action.action_id}"
        )
        raw_roll = roll_result.total
        total = raw_roll + modifier

        # Calculate progress delta
        delta = 0
        if total >= 6:
            delta = self._rules.advance_on_6_plus
        elif total >= 4:
            delta = self._rules.advance_on_4_5

        # Check for complication
        complication = raw_roll in self._rules.complication_on_rolls

        # Generate oracle event if complication occurred and oracle is enabled
        oracle_event = None
        if complication and self._oracle:
            oracle_config = self._oracle.config
            if oracle_config.enabled and oracle_config.auto_random_event_on_complication:
                oracle_event = self._oracle.random_event(
                    date=self._current_date,
                    faction_id=state.faction_id,
                    tag="action_complication",
                )

        # Apply progress
        action.progress += delta
        completed = action.is_complete

        # Apply effects if completed
        effects_applied: list[EffectResult] = []
        if completed and template and template.on_complete:
            context = {
                "date": self._current_date,
                "faction_id": state.faction_id,
                "oracle": self._oracle,
                "all_faction_states": self._faction_states,
                "faction_definitions": self._definitions,
                "relations": self._relations,
                "rules": self._rules,
            }
            effects_applied = self._effects.apply_effects(
                template.on_complete,
                state,
                self._party_state,
                context,
            )

        return ActionRollResult(
            action_id=action.action_id,
            roll=raw_roll,
            modifier=modifier,
            total=total,
            delta=delta,
            new_progress=action.progress,
            segments=action.segments,
            completed=completed,
            complication=complication,
            effects_applied=effects_applied,
            oracle_event=oracle_event,
        )

    def _get_cycle_modifiers(self, state: FactionTurnState) -> dict[str, int]:
        """
        Get modifiers for this cycle.

        Combines modifiers from previous effects and any standing modifiers.

        Args:
            state: The faction's state

        Returns:
            Dict of action_id -> modifier
        """
        modifiers: dict[str, int] = {}

        for mod in state.modifiers_next_cycle:
            action_id = mod.get("action_id", "all")
            modifier_value = mod.get("modifier", 0)
            modifiers[action_id] = modifiers.get(action_id, 0) + modifier_value

        return modifiers

    def _select_replacement_action(
        self,
        definition: FactionDefinition,
        state: FactionTurnState,
    ) -> Optional[ActionInstance]:
        """
        Select a replacement action for a completed one.

        Uses DiceRoller.choice for deterministic selection.

        Args:
            definition: The faction definition
            state: The faction's current state

        Returns:
            New ActionInstance or None
        """
        # Get IDs of currently active actions
        active_ids = {a.action_id for a in state.active_actions}

        # Find eligible actions (not currently active)
        eligible = [
            t for t in definition.action_library
            if t.action_id not in active_ids
        ]

        if not eligible:
            return None

        # Use DiceRoller.choice for deterministic selection
        dice = DiceRoller()
        template = dice.choice(
            eligible,
            reason=f"Faction {state.faction_id} replacement action"
        )

        # Create new action instance
        segments = template.segments
        if segments is None:
            segments = self._rules.get_default_segments(template.scope)

        return ActionInstance(
            action_id=template.action_id,
            goal_id=template.goal_id,
            progress=0,
            segments=segments,
            started_on=self._current_date,
        )

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize engine state for persistence.

        Returns:
            Dict suitable for JSON serialization
        """
        result = {
            "days_accumulated": self._days_accumulated,
            "cycles_completed": self._cycles_completed,
            "current_date": self._current_date,
            "faction_states": {
                fid: state.to_dict()
                for fid, state in self._faction_states.items()
            },
            "party_state": self._party_state.to_dict() if self._party_state else None,
            "global_flags": self._effects.global_flags,
        }

        # Include oracle state if oracle is present
        if self._oracle:
            result["oracle_state"] = self._oracle.to_dict()

        return result

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Restore engine state from persisted data.

        Args:
            data: Previously serialized state dict
        """
        self._days_accumulated = data.get("days_accumulated", 0)
        self._cycles_completed = data.get("cycles_completed", 0)
        self._current_date = data.get("current_date", "")

        # Restore faction states
        self._faction_states.clear()
        for fid, state_data in data.get("faction_states", {}).items():
            self._faction_states[fid] = FactionTurnState.from_dict(state_data)

        # Restore party state
        party_data = data.get("party_state")
        if party_data:
            self._party_state = PartyFactionState.from_dict(party_data)

        # Restore global flags
        global_flags = data.get("global_flags", {})
        self._effects.set_global_flags(global_flags)

        # Restore oracle state if present
        oracle_data = data.get("oracle_state")
        if oracle_data and self._oracle:
            self._oracle.from_dict(oracle_data)

    # =========================================================================
    # STATUS & REPORTING
    # =========================================================================

    def get_faction_status(self, faction_id: str) -> Optional[dict[str, Any]]:
        """
        Get a status summary for a faction.

        Args:
            faction_id: The faction ID

        Returns:
            Status dict or None if faction not found
        """
        state = self._faction_states.get(faction_id)
        definition = self._definitions.get(faction_id)

        if not state or not definition:
            return None

        points = state.territory.compute_points(self._rules.territory_point_values)
        level = self._rules.get_level_for_points(points)

        return {
            "faction_id": faction_id,
            "name": definition.name,
            "level": level,
            "territory_points": points,
            "actions": [
                {
                    "action_id": a.action_id,
                    "progress": a.progress,
                    "segments": a.segments,
                    "complete": a.is_complete,
                }
                for a in state.active_actions
            ],
            "territory": {
                "hexes": len(state.territory.hexes),
                "settlements": len(state.territory.settlements),
                "strongholds": len(state.territory.strongholds),
                "domains": len(state.territory.domains),
            },
            "recent_news": state.news[-5:] if state.news else [],
        }

    def get_all_factions_summary(self) -> list[dict[str, Any]]:
        """
        Get a summary of all factions.

        Returns:
            List of status dicts for all factions
        """
        summaries = []
        for faction_id in sorted(self._faction_states.keys()):
            status = self.get_faction_status(faction_id)
            if status:
                summaries.append(status)
        return summaries
