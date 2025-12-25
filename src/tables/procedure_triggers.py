"""
Procedure trigger system for automated game mechanics.

Implements an event-driven system where game procedures automatically
fire based on game state changes. This ensures consistent application
of rules like encounter checks, resource depletion, and time tracking.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, Union
from datetime import datetime
import random

from src.data_models import (
    GameTime,
    GameDate,
    Season,
    Weather,
    TimeOfDay,
    WatchPeriod,
    DiceRoller,
)
from src.tables.table_types import SkillCheck
from src.tables.table_manager import get_table_manager


class TriggerEvent(str, Enum):
    """Events that can trigger game procedures."""
    # Time-based
    TURN_PASSED = "turn_passed"           # 10 minutes of game time
    HOUR_PASSED = "hour_passed"           # 1 hour
    WATCH_PASSED = "watch_passed"         # 4 hours (watch change)
    DAY_PASSED = "day_passed"             # New day
    WEEK_PASSED = "week_passed"           # Week boundary

    # Movement-based
    HEX_ENTERED = "hex_entered"           # Entered a new hex
    ROOM_ENTERED = "room_entered"         # Entered dungeon room
    DUNGEON_LEVEL_ENTERED = "dungeon_level_entered"
    SETTLEMENT_ENTERED = "settlement_entered"

    # Activity-based
    REST_SHORT = "rest_short"             # Short rest (1 turn)
    REST_LONG = "rest_long"               # Long rest (8 hours)
    CAMP_MADE = "camp_made"               # Made camp in wilderness
    COMBAT_ENDED = "combat_ended"         # Combat concluded
    SEARCH_PERFORMED = "search_performed"
    FORAGE_ATTEMPTED = "forage_attempted"
    HUNT_ATTEMPTED = "hunt_attempted"

    # Resource-based
    TORCH_LIT = "torch_lit"               # Light source activated
    SPELL_CAST = "spell_cast"             # Spell was cast
    ITEM_USED = "item_used"               # Consumable used
    FOOD_CONSUMED = "food_consumed"
    WATER_CONSUMED = "water_consumed"

    # Combat-based
    COMBAT_ROUND = "combat_round"         # New combat round
    FIRST_BLOOD = "first_blood"           # First HP lost in combat
    HALF_CASUALTIES = "half_casualties"   # Half of side defeated
    LEADER_KILLED = "leader_killed"       # Leader eliminated

    # State-based
    HP_ZERO = "hp_zero"                   # Character dropped to 0 HP
    CONDITION_APPLIED = "condition_applied"
    LOUD_NOISE = "loud_noise"             # Noise made in dungeon


class TriggerPriority(int, Enum):
    """Priority levels for trigger execution order."""
    CRITICAL = 0    # Must execute first (save-or-die effects)
    HIGH = 10       # Important (morale checks)
    NORMAL = 50     # Standard (encounter checks)
    LOW = 90        # Deferred (bookkeeping)


@dataclass
class TriggerCondition:
    """
    Condition that must be met for a trigger to fire.

    Conditions can check game state, location, time, etc.
    """
    condition_type: str          # Type of condition check
    check_value: Any            # Value to compare against
    comparison: str = "equals"   # equals, greater, less, contains

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate if condition is met given context."""
        actual_value = context.get(self.condition_type)

        if actual_value is None:
            return False

        if self.comparison == "equals":
            return actual_value == self.check_value
        elif self.comparison == "greater":
            return actual_value > self.check_value
        elif self.comparison == "less":
            return actual_value < self.check_value
        elif self.comparison == "greater_equal":
            return actual_value >= self.check_value
        elif self.comparison == "less_equal":
            return actual_value <= self.check_value
        elif self.comparison == "contains":
            return self.check_value in actual_value
        elif self.comparison == "not_equals":
            return actual_value != self.check_value

        return False


@dataclass
class ProcedureResult:
    """Result of a triggered procedure."""
    procedure_name: str
    triggered: bool
    description: str
    effects: list[dict[str, Any]] = field(default_factory=list)

    # Roll details if applicable
    roll_made: bool = False
    roll_result: Optional[int] = None
    roll_success: Optional[bool] = None

    # State changes
    state_changes: dict[str, Any] = field(default_factory=dict)

    # Follow-up triggers
    follow_up_events: list[TriggerEvent] = field(default_factory=list)

    def describe(self) -> str:
        """Get narrative description of result."""
        lines = [f"[{self.procedure_name}]"]

        if self.roll_made:
            success_str = "success" if self.roll_success else "failure"
            lines.append(f"  Roll: {self.roll_result} ({success_str})")

        lines.append(f"  {self.description}")

        for effect in self.effects:
            lines.append(f"  → {effect.get('description', '')}")

        return "\n".join(lines)


@dataclass
class GameProcedure:
    """
    A game procedure that can be triggered automatically.

    Procedures encapsulate game rules that should be applied
    consistently, like encounter checks or resource depletion.
    """
    procedure_id: str
    name: str
    description: str

    # When this procedure triggers
    trigger_events: list[TriggerEvent]
    conditions: list[TriggerCondition] = field(default_factory=list)

    # Execution
    priority: TriggerPriority = TriggerPriority.NORMAL
    execution_func: Optional[Callable] = None

    # State
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0

    # Cooldown (in game turns)
    cooldown_turns: int = 0
    turns_since_trigger: int = 0

    def can_trigger(self, context: dict[str, Any]) -> bool:
        """Check if procedure can trigger given context."""
        if not self.enabled:
            return False

        # Check cooldown
        if self.cooldown_turns > 0 and self.turns_since_trigger < self.cooldown_turns:
            return False

        # Check all conditions
        for condition in self.conditions:
            if not condition.evaluate(context):
                return False

        return True

    def execute(self, context: dict[str, Any]) -> ProcedureResult:
        """Execute the procedure."""
        self.last_triggered = datetime.now()
        self.trigger_count += 1
        self.turns_since_trigger = 0

        if self.execution_func:
            return self.execution_func(self, context)

        return ProcedureResult(
            procedure_name=self.name,
            triggered=True,
            description="Procedure executed (no specific handler)",
        )


class ProcedureManager:
    """
    Manages and executes game procedures based on triggers.

    The manager maintains a registry of procedures and automatically
    fires appropriate ones when trigger events occur.
    """

    def __init__(self):
        self._procedures: dict[str, GameProcedure] = {}
        self._by_event: dict[TriggerEvent, list[str]] = {
            event: [] for event in TriggerEvent
        }

        # Register default procedures
        self._register_default_procedures()

    def _register_default_procedures(self) -> None:
        """Register the standard game procedures."""
        # Encounter checks
        self.register_procedure(GameProcedure(
            procedure_id="wilderness_encounter_check",
            name="Wilderness Encounter Check",
            description="Check for random wilderness encounters when entering a hex",
            trigger_events=[TriggerEvent.HEX_ENTERED],
            priority=TriggerPriority.NORMAL,
            execution_func=self._execute_encounter_check,
        ))

        self.register_procedure(GameProcedure(
            procedure_id="dungeon_encounter_check",
            name="Dungeon Encounter Check",
            description="Check for wandering monsters every 2 turns in dungeon",
            trigger_events=[TriggerEvent.TURN_PASSED],
            conditions=[TriggerCondition("in_dungeon", True)],
            priority=TriggerPriority.NORMAL,
            cooldown_turns=2,
            execution_func=self._execute_dungeon_encounter,
        ))

        # Lost check
        self.register_procedure(GameProcedure(
            procedure_id="lost_check",
            name="Lost Check",
            description="Check if party becomes lost when entering wilderness hex",
            trigger_events=[TriggerEvent.HEX_ENTERED],
            conditions=[TriggerCondition("on_road", False)],
            priority=TriggerPriority.HIGH,
            execution_func=self._execute_lost_check,
        ))

        # Resource depletion
        self.register_procedure(GameProcedure(
            procedure_id="torch_burndown",
            name="Torch Duration",
            description="Track torch burndown (6 turns per torch)",
            trigger_events=[TriggerEvent.TURN_PASSED],
            conditions=[TriggerCondition("light_source", "torch")],
            priority=TriggerPriority.LOW,
            execution_func=self._execute_torch_burndown,
        ))

        self.register_procedure(GameProcedure(
            procedure_id="lantern_fuel",
            name="Lantern Fuel",
            description="Track lantern oil consumption (24 turns per flask)",
            trigger_events=[TriggerEvent.TURN_PASSED],
            conditions=[TriggerCondition("light_source", "lantern")],
            priority=TriggerPriority.LOW,
            execution_func=self._execute_lantern_fuel,
        ))

        # Food and water
        self.register_procedure(GameProcedure(
            procedure_id="daily_rations",
            name="Daily Rations",
            description="Consume food and water each day",
            trigger_events=[TriggerEvent.DAY_PASSED],
            priority=TriggerPriority.NORMAL,
            execution_func=self._execute_daily_rations,
        ))

        # Rest procedures
        self.register_procedure(GameProcedure(
            procedure_id="rest_healing",
            name="Rest Healing",
            description="Recover HP during long rest",
            trigger_events=[TriggerEvent.REST_LONG],
            priority=TriggerPriority.NORMAL,
            execution_func=self._execute_rest_healing,
        ))

        # Combat triggers
        self.register_procedure(GameProcedure(
            procedure_id="morale_check_casualties",
            name="Morale Check (Casualties)",
            description="Check morale when half the group is killed",
            trigger_events=[TriggerEvent.HALF_CASUALTIES],
            priority=TriggerPriority.HIGH,
            execution_func=self._execute_morale_check,
        ))

        self.register_procedure(GameProcedure(
            procedure_id="morale_check_leader",
            name="Morale Check (Leader)",
            description="Check morale when leader is killed",
            trigger_events=[TriggerEvent.LEADER_KILLED],
            priority=TriggerPriority.HIGH,
            execution_func=self._execute_morale_check,
        ))

        # Noise alerts
        self.register_procedure(GameProcedure(
            procedure_id="noise_alert",
            name="Noise Alert",
            description="Alert nearby creatures to noise",
            trigger_events=[TriggerEvent.LOUD_NOISE],
            conditions=[TriggerCondition("in_dungeon", True)],
            priority=TriggerPriority.HIGH,
            execution_func=self._execute_noise_alert,
        ))

        # Weather check
        self.register_procedure(GameProcedure(
            procedure_id="daily_weather",
            name="Daily Weather",
            description="Determine weather for the day",
            trigger_events=[TriggerEvent.DAY_PASSED],
            priority=TriggerPriority.LOW,
            execution_func=self._execute_weather_check,
        ))

    def register_procedure(self, procedure: GameProcedure) -> None:
        """Register a procedure with the manager."""
        self._procedures[procedure.procedure_id] = procedure

        for event in procedure.trigger_events:
            if procedure.procedure_id not in self._by_event[event]:
                self._by_event[event].append(procedure.procedure_id)

    def unregister_procedure(self, procedure_id: str) -> bool:
        """Remove a procedure from the manager."""
        if procedure_id not in self._procedures:
            return False

        procedure = self._procedures.pop(procedure_id)
        for event in procedure.trigger_events:
            if procedure_id in self._by_event[event]:
                self._by_event[event].remove(procedure_id)

        return True

    def fire_event(
        self,
        event: TriggerEvent,
        context: dict[str, Any]
    ) -> list[ProcedureResult]:
        """
        Fire a trigger event and execute all applicable procedures.

        Args:
            event: The event that occurred
            context: Current game state context

        Returns:
            List of results from triggered procedures
        """
        results = []

        # Get all procedures for this event
        procedure_ids = self._by_event.get(event, [])

        # Sort by priority
        procedures = [
            self._procedures[pid] for pid in procedure_ids
            if pid in self._procedures
        ]
        procedures.sort(key=lambda p: p.priority)

        # Execute each applicable procedure
        for procedure in procedures:
            if procedure.can_trigger(context):
                result = procedure.execute(context)
                results.append(result)

                # Handle follow-up events
                for follow_up in result.follow_up_events:
                    sub_results = self.fire_event(follow_up, context)
                    results.extend(sub_results)

        return results

    def advance_turn(self, context: dict[str, Any]) -> list[ProcedureResult]:
        """Convenience method to advance time by one turn."""
        # Update cooldowns
        for procedure in self._procedures.values():
            if procedure.cooldown_turns > 0:
                procedure.turns_since_trigger += 1

        return self.fire_event(TriggerEvent.TURN_PASSED, context)

    def get_procedure(self, procedure_id: str) -> Optional[GameProcedure]:
        """Get a procedure by ID."""
        return self._procedures.get(procedure_id)

    def enable_procedure(self, procedure_id: str) -> bool:
        """Enable a procedure."""
        if procedure_id in self._procedures:
            self._procedures[procedure_id].enabled = True
            return True
        return False

    def disable_procedure(self, procedure_id: str) -> bool:
        """Disable a procedure."""
        if procedure_id in self._procedures:
            self._procedures[procedure_id].enabled = False
            return True
        return False

    # =========================================================================
    # PROCEDURE EXECUTION FUNCTIONS
    # =========================================================================

    def _execute_encounter_check(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Execute wilderness encounter check."""
        encounter_chance = context.get("encounter_chance", 2)  # X-in-6

        roll = random.randint(1, 6)
        encounter = roll <= encounter_chance

        if encounter:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Random encounter! (rolled {roll} vs {encounter_chance}-in-6)",
                roll_made=True,
                roll_result=roll,
                roll_success=True,
                effects=[{"type": "encounter", "description": "Roll on encounter table"}],
                follow_up_events=[],
            )
        else:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"No encounter (rolled {roll} vs {encounter_chance}-in-6)",
                roll_made=True,
                roll_result=roll,
                roll_success=False,
            )

    def _execute_dungeon_encounter(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Execute dungeon wandering monster check."""
        roll = random.randint(1, 6)
        encounter = roll == 1  # 1-in-6 for dungeon

        if encounter:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Wandering monster! (rolled {roll})",
                roll_made=True,
                roll_result=roll,
                roll_success=True,
                effects=[{"type": "encounter", "description": "Roll for wandering monster"}],
            )
        else:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"No wandering monster (rolled {roll})",
                roll_made=True,
                roll_result=roll,
                roll_success=False,
            )

    def _execute_lost_check(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Execute getting lost check."""
        lost_chance = context.get("lost_chance", 2)  # X-in-6

        roll = random.randint(1, 6)
        lost = roll <= lost_chance

        if lost:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"The party becomes lost! (rolled {roll} vs {lost_chance}-in-6)",
                roll_made=True,
                roll_result=roll,
                roll_success=True,
                state_changes={"party_lost": True},
            )
        else:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Party maintains bearing (rolled {roll} vs {lost_chance}-in-6)",
                roll_made=True,
                roll_result=roll,
                roll_success=False,
            )

    def _execute_torch_burndown(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Track torch duration."""
        remaining = context.get("light_remaining_turns", 6)
        remaining -= 1

        if remaining <= 0:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description="The torch sputters and dies!",
                state_changes={"light_source": "none", "light_remaining_turns": 0},
                effects=[{"type": "darkness", "description": "Party is in darkness"}],
            )
        elif remaining == 1:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description="The torch is nearly spent. It will go out next turn.",
                state_changes={"light_remaining_turns": remaining},
            )
        else:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Torch burns steadily. {remaining} turns remaining.",
                state_changes={"light_remaining_turns": remaining},
            )

    def _execute_lantern_fuel(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Track lantern oil consumption."""
        remaining = context.get("light_remaining_turns", 24)
        remaining -= 1

        if remaining <= 0:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description="The lantern flickers and goes dark. It needs more oil.",
                state_changes={"light_source": "none", "light_remaining_turns": 0},
                effects=[{"type": "darkness", "description": "Party is in darkness"}],
            )
        elif remaining <= 4:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Lantern oil running low. {remaining} turns remaining.",
                state_changes={"light_remaining_turns": remaining},
            )
        else:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Lantern burns steadily. {remaining} turns remaining.",
                state_changes={"light_remaining_turns": remaining},
            )

    def _execute_daily_rations(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Consume daily food and water."""
        party_size = context.get("party_size", 4)
        food = context.get("food_days", 0)
        water = context.get("water_days", 0)

        food_consumed = party_size
        water_consumed = party_size

        new_food = max(0, food - food_consumed)
        new_water = max(0, water - water_consumed)

        effects = []
        if new_food <= 0:
            effects.append({"type": "starvation", "description": "No food! Party members must save vs starvation."})
        elif new_food < party_size:
            effects.append({"type": "low_food", "description": f"Running low on food! {new_food} days remaining."})

        if new_water <= 0:
            effects.append({"type": "dehydration", "description": "No water! Party members must save vs dehydration."})
        elif new_water < party_size:
            effects.append({"type": "low_water", "description": f"Running low on water! {new_water} days remaining."})

        return ProcedureResult(
            procedure_name=procedure.name,
            triggered=True,
            description=f"Consumed daily rations. Food: {new_food} days, Water: {new_water} days.",
            state_changes={"food_days": new_food, "water_days": new_water},
            effects=effects,
        )

    def _execute_rest_healing(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Handle healing during long rest."""
        # In B/X, characters heal 1d3 HP per day of complete rest
        # or 1 HP for light activity
        rest_type = context.get("rest_type", "light")

        if rest_type == "complete":
            healing = random.randint(1, 3)
        else:
            healing = 1

        return ProcedureResult(
            procedure_name=procedure.name,
            triggered=True,
            description=f"Rest completed. Each character recovers {healing} HP.",
            state_changes={"healing_amount": healing},
        )

    def _execute_morale_check(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Execute morale check for enemies."""
        morale_score = context.get("enemy_morale", 7)
        modifier = context.get("morale_modifier", 0)

        dice = [random.randint(1, 6), random.randint(1, 6)]
        roll = sum(dice)
        adjusted = roll + modifier

        if adjusted > morale_score:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Morale breaks! (rolled {roll}{modifier:+d} = {adjusted} vs morale {morale_score})",
                roll_made=True,
                roll_result=roll,
                roll_success=False,
                effects=[{"type": "flee", "description": "Enemies attempt to flee or surrender"}],
            )
        else:
            return ProcedureResult(
                procedure_name=procedure.name,
                triggered=True,
                description=f"Morale holds (rolled {roll}{modifier:+d} = {adjusted} vs morale {morale_score})",
                roll_made=True,
                roll_result=roll,
                roll_success=True,
            )

    def _execute_noise_alert(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Handle noise alerting nearby creatures."""
        return ProcedureResult(
            procedure_name=procedure.name,
            triggered=True,
            description="The noise echoes through the corridors. Something may have heard...",
            effects=[{"type": "alert", "description": "Increase encounter chance for nearby rooms"}],
        )

    def _execute_weather_check(
        self,
        procedure: GameProcedure,
        context: dict[str, Any]
    ) -> ProcedureResult:
        """Determine daily weather."""
        season = context.get("season", "summer")
        manager = get_table_manager()

        result = manager.roll_table(f"weather_{season}")

        return ProcedureResult(
            procedure_name=procedure.name,
            triggered=True,
            description=f"Today's weather: {result.result_text}",
            roll_made=True,
            roll_result=result.roll_total,
            state_changes={"weather": result.result_text},
        )


# Global instance
_procedure_manager: Optional[ProcedureManager] = None


def get_procedure_manager() -> ProcedureManager:
    """Get the global ProcedureManager instance."""
    global _procedure_manager
    if _procedure_manager is None:
        _procedure_manager = ProcedureManager()
    return _procedure_manager


# Convenience functions

def fire_turn_passed(context: dict[str, Any]) -> list[ProcedureResult]:
    """Fire all turn-based procedures."""
    return get_procedure_manager().fire_event(TriggerEvent.TURN_PASSED, context)


def fire_hex_entered(context: dict[str, Any]) -> list[ProcedureResult]:
    """Fire all procedures for entering a hex."""
    return get_procedure_manager().fire_event(TriggerEvent.HEX_ENTERED, context)


def fire_combat_round(context: dict[str, Any]) -> list[ProcedureResult]:
    """Fire all procedures for a combat round."""
    return get_procedure_manager().fire_event(TriggerEvent.COMBAT_ROUND, context)
