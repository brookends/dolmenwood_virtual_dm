"""
Fairy Road Engine for Dolmenwood Virtual DM.

Implements fairy road travel mechanics:
1. Entering fairy roads through fairy doors
2. Travel checks (1d6: 1-2 monster, 3-4 location, 5-6 nothing)
3. "Don't Stray From the Path" mechanic for unconscious travelers
4. Time dilation (subjective time vs mortal world time)
5. Exiting at destination doors

Key design:
- Subjective time: time advances on the road but mortal world time is frozen
- On exit: roll for mortal world time passage (e.g., 1d12 days)
- Party travels as a unit; if anyone goes unconscious, ALL stray from path
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging
import random

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.data_models import (
    DiceRoller,
    EncounterState,
    EncounterType,
    Combatant,
)
from src.encounter.encounter_engine import EncounterOrigin
from src.fairy_roads.fairy_road_models import (
    FairyRoadData,
    FairyDoor,
    FairyRoadTravelState,
    FairyRoadCheckResult,
    FairyRoadCheckOutcome,
    StrayFromPathResult,
    StrayFromPathOutcome,
    FairyRoadEncounterEntry,
    FairyRoadLocationEntry,
)
from src.content_loader.fairy_road_registry import (
    FairyRoadRegistry,
    get_fairy_road_registry,
)

logger = logging.getLogger(__name__)


class FairyRoadPhase(str, Enum):
    """Current phase of fairy road travel."""

    ENTERING = "entering"  # At the door, about to enter
    TRAVELING = "traveling"  # On the road
    ENCOUNTER = "encounter"  # Handling an encounter
    LOCATION = "location"  # At a location on the road
    EXITING = "exiting"  # About to exit
    STRAYED = "strayed"  # Party strayed from the path
    COMPLETE = "complete"  # Travel finished


@dataclass
class FairyRoadTravelResult:
    """Result of a fairy road travel action."""

    success: bool
    phase: FairyRoadPhase
    segment: int = 0
    total_segments: int = 0
    check_outcome: Optional[FairyRoadCheckOutcome] = None
    stray_outcome: Optional[StrayFromPathOutcome] = None
    messages: list[str] = field(default_factory=list)
    encounter_triggered: bool = False
    location_found: bool = False
    travel_complete: bool = False
    time_dilation_applied: bool = False
    mortal_days_passed: int = 0


@dataclass
class FairyRoadEntryResult:
    """Result of attempting to enter a fairy road."""

    success: bool
    road_id: str = ""
    door_id: str = ""
    messages: list[str] = field(default_factory=list)
    requirements_met: bool = True
    missing_requirements: list[str] = field(default_factory=list)


@dataclass
class FairyRoadExitResult:
    """Result of exiting a fairy road."""

    success: bool
    exit_hex_id: str = ""
    door_id: str = ""
    time_dilation_dice: str = ""
    time_dilation_roll: int = 0
    mortal_days_passed: int = 0
    messages: list[str] = field(default_factory=list)


class FairyRoadEngine:
    """
    Engine for handling fairy road travel in Dolmenwood.

    Fairy roads are supernatural paths through the woods that allow
    faster travel between distant locations, but with risks:
    - Encounters with fairy creatures
    - Time dilation (mortal world time may pass differently)
    - "Don't Stray From the Path" - unconscious travelers wake in random hexes
    """

    def __init__(
        self,
        controller: GlobalController,
        registry: Optional[FairyRoadRegistry] = None,
    ):
        """
        Initialize the fairy road engine.

        Args:
            controller: The global game controller
            registry: Optional fairy road registry (uses global if not provided)
        """
        self.controller = controller
        self.registry = registry or get_fairy_road_registry()
        self.dice = DiceRoller()

        # Current travel state
        self._state: Optional[FairyRoadTravelState] = None
        self._current_road: Optional[FairyRoadData] = None
        self._phase: FairyRoadPhase = FairyRoadPhase.COMPLETE

        # Callbacks
        self._narration_callback: Optional[Callable] = None

        # Track mortal world time that was frozen
        self._frozen_mortal_turns: int = 0

    def register_narration_callback(self, callback: Callable) -> None:
        """Register callback for fairy road narration."""
        self._narration_callback = callback

    # =========================================================================
    # ENTRY
    # =========================================================================

    def can_enter_door(
        self,
        door_id: str,
        current_hex_id: str,
        time_of_day: Optional[str] = None,
        moonphase: Optional[str] = None,
        offerings: Optional[list[str]] = None,
        password: Optional[str] = None,
    ) -> FairyRoadEntryResult:
        """
        Check if the party can enter through a fairy door.

        Args:
            door_id: ID of the door to enter
            current_hex_id: Party's current hex location
            time_of_day: Current time (e.g., "twilight", "midnight")
            moonphase: Current moon phase (e.g., "full_moon")
            offerings: Items offered at the door
            password: Spoken password/phrase

        Returns:
            FairyRoadEntryResult with success status and missing requirements
        """
        door = self.registry.get_door(door_id)
        if not door:
            return FairyRoadEntryResult(
                success=False,
                messages=[f"Fairy door '{door_id}' not found"],
            )

        # Check if party is at the right hex
        if door.hex_id != current_hex_id:
            return FairyRoadEntryResult(
                success=False,
                messages=[f"Party must be in hex {door.hex_id} to use this door"],
            )

        # Check requirements
        missing = []
        offerings = offerings or []

        if door.requires_time and time_of_day != door.requires_time:
            missing.append(f"Must be {door.requires_time}")

        if door.requires_moonphase and moonphase != door.requires_moonphase:
            missing.append(f"Must be during {door.requires_moonphase}")

        if door.requires_offering and door.requires_offering not in offerings:
            missing.append(f"Requires offering of {door.requires_offering}")

        if door.requires_password and password != door.requires_password:
            missing.append("Correct password required")

        if missing:
            return FairyRoadEntryResult(
                success=False,
                door_id=door_id,
                road_id=door.fairy_road_id,
                requirements_met=False,
                missing_requirements=missing,
                messages=[f"Cannot enter: {', '.join(missing)}"],
            )

        return FairyRoadEntryResult(
            success=True,
            door_id=door_id,
            road_id=door.fairy_road_id,
            requirements_met=True,
            messages=[f"The way to {door.name} is open"],
        )

    def enter_fairy_road(
        self,
        door_id: str,
        destination_door_id: Optional[str] = None,
    ) -> FairyRoadEntryResult:
        """
        Enter a fairy road through a door.

        Args:
            door_id: ID of the entry door
            destination_door_id: Optional target exit door

        Returns:
            FairyRoadEntryResult with entry status
        """
        door = self.registry.get_door(door_id)
        if not door:
            return FairyRoadEntryResult(
                success=False,
                messages=[f"Door '{door_id}' not found"],
            )

        road = self.registry.get(door.fairy_road_id)
        if not road:
            return FairyRoadEntryResult(
                success=False,
                messages=[f"Fairy road '{door.fairy_road_id}' not found"],
            )

        # Initialize travel state
        self._current_road = road
        self._state = FairyRoadTravelState(
            road_id=road.road_id,
            entry_door_id=door_id,
            entry_hex_id=door.hex_id,
            current_segment=0,
            total_segments=road.length_segments,
            destination_door_id=destination_door_id,
            mortal_time_frozen=road.time_dilation_enabled,
        )
        self._phase = FairyRoadPhase.ENTERING
        self._frozen_mortal_turns = 0

        # Transition game state
        self.controller.transition(
            "enter_fairy_road",
            context={
                "road_id": road.road_id,
                "road_name": road.name,
                "door_id": door_id,
                "door_name": door.name,
                "entry_hex": door.hex_id,
            },
        )

        self._phase = FairyRoadPhase.TRAVELING

        messages = [
            f"The party enters {door.name}...",
            f"You step onto {road.name}.",
            road.atmosphere,
        ]

        # Add atmospheric details
        if road.sights:
            messages.append(f"You see: {random.choice(road.sights)}")
        if road.sounds:
            messages.append(f"You hear: {random.choice(road.sounds)}")

        # Warn about special rules
        if road.no_iron:
            messages.append("WARNING: Iron is dangerous here!")
        if road.special_rules:
            messages.append(f"Note: {road.special_rules[0]}")

        return FairyRoadEntryResult(
            success=True,
            road_id=road.road_id,
            door_id=door_id,
            messages=messages,
        )

    # =========================================================================
    # TRAVEL
    # =========================================================================

    def travel_segment(self) -> FairyRoadTravelResult:
        """
        Travel one segment of the fairy road.

        Each segment involves:
        1. Advance subjective time (1 turn)
        2. Roll 1d6 for encounters (1-2 monster, 3-4 location, 5-6 nothing)
        3. Handle any encounters/locations

        Returns:
            FairyRoadTravelResult with segment outcome
        """
        if not self._state or not self._current_road:
            return FairyRoadTravelResult(
                success=False,
                phase=FairyRoadPhase.COMPLETE,
                messages=["Not currently on a fairy road"],
            )

        if self._phase != FairyRoadPhase.TRAVELING:
            return FairyRoadTravelResult(
                success=False,
                phase=self._phase,
                messages=[f"Cannot travel: current phase is {self._phase.value}"],
            )

        # Advance segment
        self._state.current_segment += 1
        self._state.subjective_turns_elapsed += 1

        # Track frozen mortal time if time dilation is active
        if self._state.mortal_time_frozen:
            self._frozen_mortal_turns += 1

        result = FairyRoadTravelResult(
            success=True,
            phase=FairyRoadPhase.TRAVELING,
            segment=self._state.current_segment,
            total_segments=self._state.total_segments,
        )

        result.messages.append(
            f"Traveling segment {self._state.current_segment} of {self._state.total_segments}..."
        )

        # Roll 1d6 for encounter check
        check_roll = self.dice.roll_d6(1, "fairy road travel check")
        check_value = check_roll.total

        if check_value <= 2:
            # Monster encounter
            check_result = FairyRoadCheckResult.MONSTER_ENCOUNTER
            result.encounter_triggered = True
            self._phase = FairyRoadPhase.ENCOUNTER
        elif check_value <= 4:
            # Location encounter
            check_result = FairyRoadCheckResult.LOCATION_ENCOUNTER
            result.location_found = True
            self._phase = FairyRoadPhase.LOCATION
        else:
            # Nothing happens
            check_result = FairyRoadCheckResult.NOTHING

        self._state.last_check_result = check_result

        # Create check outcome
        outcome = FairyRoadCheckOutcome(
            check_type=check_result,
            roll=check_value,
        )

        # Handle encounter/location
        if check_result == FairyRoadCheckResult.MONSTER_ENCOUNTER:
            self._state.encounters_triggered += 1
            outcome = self._roll_monster_encounter(outcome)
            result.messages.append("An encounter occurs!")
            result.messages.append(outcome.description)

        elif check_result == FairyRoadCheckResult.LOCATION_ENCOUNTER:
            outcome = self._roll_location_encounter(outcome)
            result.messages.append("You discover a location!")
            result.messages.append(outcome.description)

        else:
            result.messages.append("The journey continues uneventfully...")
            # Add atmospheric description
            if self._current_road.sights:
                result.messages.append(random.choice(self._current_road.sights))

        result.check_outcome = outcome

        # Check if travel is complete
        if (
            self._state.current_segment >= self._state.total_segments
            and self._phase == FairyRoadPhase.TRAVELING
        ):
            self._phase = FairyRoadPhase.EXITING
            result.messages.append("You approach the end of the road...")

        return result

    def _roll_monster_encounter(
        self, outcome: FairyRoadCheckOutcome
    ) -> FairyRoadCheckOutcome:
        """Roll on the monster encounter table."""
        if not self._current_road or not self._current_road.encounter_table:
            outcome.description = "A shadowy figure appears on the road..."
            return outcome

        table = self._current_road.encounter_table
        die_type = table.die_type or "d8"
        roll = self.dice.roll(f"1{die_type}", "monster table roll")

        # Find matching entry
        for entry in table.monster_entries:
            if entry.roll <= roll.total <= entry.roll_max:
                outcome.monster_entry = entry
                outcome.description = entry.description

                # Roll for count
                if entry.count_dice:
                    count_roll = self.dice.roll(entry.count_dice, "monster count")
                    outcome.monster_count = count_roll.total
                else:
                    outcome.monster_count = entry.count_fixed or 1

                return outcome

        outcome.description = "Strange shapes move in the mist..."
        return outcome

    def _roll_location_encounter(
        self, outcome: FairyRoadCheckOutcome
    ) -> FairyRoadCheckOutcome:
        """Roll on the location encounter table."""
        if not self._current_road or not self._current_road.encounter_table:
            outcome.description = "A clearing appears in the ethereal mist..."
            return outcome

        table = self._current_road.encounter_table
        die_type = table.die_type or "d6"

        # Location table typically uses d6
        roll = self.dice.roll("1d6", "location table roll")

        # Find matching entry
        for entry in table.location_entries:
            if entry.roll <= roll.total <= (entry.roll_max or entry.roll):
                outcome.location_entry = entry
                outcome.description = f"{entry.name}: {entry.description}"
                return outcome

        outcome.description = "A strange location materializes before you..."
        return outcome

    # =========================================================================
    # ENCOUNTER INTEGRATION
    # =========================================================================

    def create_monster_encounter(self) -> Optional[EncounterState]:
        """
        Create an encounter state from the current monster encounter.

        Returns:
            EncounterState for the encounter engine, or None if no encounter
        """
        if not self._state or not self._state.last_check_result:
            return None

        if self._state.last_check_result != FairyRoadCheckResult.MONSTER_ENCOUNTER:
            return None

        # Get the monster entry from the last check
        # This would need to be stored somewhere - for now return basic encounter
        encounter = EncounterState(
            encounter_type=EncounterType.HOSTILE,
            actors=["Fairy road denizen"],
            context={"origin": "fairy_road", "road_id": self._state.road_id},
        )

        return encounter

    def resume_after_encounter(self) -> FairyRoadTravelResult:
        """
        Resume fairy road travel after an encounter concludes.

        Returns:
            FairyRoadTravelResult with resumed travel status
        """
        if not self._state:
            return FairyRoadTravelResult(
                success=False,
                phase=FairyRoadPhase.COMPLETE,
                messages=["No active fairy road travel"],
            )

        self._phase = FairyRoadPhase.TRAVELING

        result = FairyRoadTravelResult(
            success=True,
            phase=FairyRoadPhase.TRAVELING,
            segment=self._state.current_segment,
            total_segments=self._state.total_segments,
            messages=["The encounter concludes. The road stretches on..."],
        )

        # Check if any party member is unconscious
        if self._check_party_unconscious():
            return self._handle_stray_from_path()

        return result

    def resume_after_location(self) -> FairyRoadTravelResult:
        """
        Resume travel after exploring a location.

        Returns:
            FairyRoadTravelResult with resumed status
        """
        if not self._state:
            return FairyRoadTravelResult(
                success=False,
                phase=FairyRoadPhase.COMPLETE,
                messages=["No active fairy road travel"],
            )

        self._phase = FairyRoadPhase.TRAVELING

        return FairyRoadTravelResult(
            success=True,
            phase=FairyRoadPhase.TRAVELING,
            segment=self._state.current_segment,
            total_segments=self._state.total_segments,
            messages=["You leave the location behind and continue on the road..."],
        )

    # =========================================================================
    # STRAY FROM PATH
    # =========================================================================

    def _check_party_unconscious(self) -> bool:
        """Check if any party member is unconscious."""
        for char in self.controller.get_active_characters():
            # Check HP <= 0 or unconscious condition
            if char.current_hp <= 0:
                return True
            if hasattr(char, "conditions") and "unconscious" in char.conditions:
                return True
        return False

    def _handle_stray_from_path(self) -> FairyRoadTravelResult:
        """
        Handle the "Don't Stray From the Path" mechanic.

        When a party member goes unconscious, the entire party
        strays from the path and ends up in a random mortal hex.

        Returns:
            FairyRoadTravelResult with stray outcome
        """
        if not self._state or not self._current_road:
            return FairyRoadTravelResult(
                success=False,
                phase=FairyRoadPhase.COMPLETE,
                messages=["No active travel"],
            )

        self._phase = FairyRoadPhase.STRAYED
        self._state.strayed_from_path = True

        # Roll for exit hex
        exit_hexes = self._current_road.stray_exit_hexes
        if exit_hexes:
            exit_hex = random.choice(exit_hexes)
        else:
            exit_hex = self._state.entry_hex_id  # Fall back to entry hex

        # Roll for additional time
        time_dice = self._current_road.stray_time_dice or "1d6"
        time_roll = self.dice.roll(time_dice, "stray time")
        time_unit = self._current_road.stray_time_unit or "hours"

        outcome = StrayFromPathOutcome(
            result_type=StrayFromPathResult.LOST_IN_WOODS,
            exit_hex_id=exit_hex,
            time_passed_mortal=time_roll.total,
            time_unit=time_unit,
            description=(
                f"The unconscious traveler causes the party to stray from the path. "
                f"They awaken in hex {exit_hex}, having lost {time_roll.total} {time_unit}."
            ),
        )

        # Apply time passage
        if time_unit == "hours":
            turns = time_roll.total * 6  # 6 turns per hour
        elif time_unit == "days":
            turns = time_roll.total * 144  # 144 turns per day
        else:
            turns = time_roll.total

        self.controller.advance_time(turns)

        # Transition back to wilderness
        self.controller.transition(
            "exit_fairy_road",
            context={
                "reason": "strayed_from_path",
                "exit_hex": exit_hex,
                "time_passed": time_roll.total,
                "time_unit": time_unit,
            },
        )

        # Clear travel state
        self._clear_travel_state()

        return FairyRoadTravelResult(
            success=True,
            phase=FairyRoadPhase.STRAYED,
            stray_outcome=outcome,
            travel_complete=True,
            messages=[
                "A party member loses consciousness!",
                "Without their awareness anchoring the path, you stray...",
                outcome.description,
            ],
        )

    # =========================================================================
    # EXIT
    # =========================================================================

    def exit_fairy_road(
        self, door_id: Optional[str] = None
    ) -> FairyRoadExitResult:
        """
        Exit the fairy road through a door.

        Args:
            door_id: Door to exit through (uses destination if not specified)

        Returns:
            FairyRoadExitResult with exit details and time dilation
        """
        if not self._state or not self._current_road:
            return FairyRoadExitResult(
                success=False,
                messages=["Not currently on a fairy road"],
            )

        # Determine exit door
        target_door_id = door_id or self._state.destination_door_id
        if not target_door_id:
            # Find the furthest door on the road
            doors = self._current_road.doors
            if doors:
                target_door_id = max(doors, key=lambda d: d.road_position).door_id
            else:
                return FairyRoadExitResult(
                    success=False,
                    messages=["No exit door available"],
                )

        door = self.registry.get_door(target_door_id)
        if not door:
            return FairyRoadExitResult(
                success=False,
                messages=[f"Exit door '{target_door_id}' not found"],
            )

        result = FairyRoadExitResult(
            success=True,
            door_id=target_door_id,
            exit_hex_id=door.hex_id,
        )

        messages = [
            f"You approach {door.name}...",
            f"Stepping through, you emerge in the mortal world at hex {door.hex_id}.",
        ]

        # Apply time dilation if enabled
        if self._current_road.time_dilation_enabled:
            time_dice = self._current_road.time_dilation_dice or "1d12"
            time_roll = self.dice.roll(time_dice, "time dilation")
            time_unit = self._current_road.time_dilation_unit or "days"

            result.time_dilation_dice = time_dice
            result.time_dilation_roll = time_roll.total
            result.mortal_days_passed = time_roll.total

            messages.append(
                f"As you exit, you realize {time_roll.total} {time_unit} "
                f"have passed in the mortal world!"
            )

            # Apply time passage
            if time_unit == "hours":
                turns = time_roll.total * 6
            elif time_unit == "days":
                turns = time_roll.total * 144
            elif time_unit == "weeks":
                turns = time_roll.total * 144 * 7
            else:
                turns = time_roll.total

            self.controller.advance_time(turns)

        result.messages = messages

        # Transition back to wilderness
        self.controller.transition(
            "exit_fairy_road",
            context={
                "exit_door": target_door_id,
                "exit_hex": door.hex_id,
                "time_passed": result.mortal_days_passed,
                "road_id": self._state.road_id,
            },
        )

        # Clear travel state
        self._clear_travel_state()

        return result

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _clear_travel_state(self) -> None:
        """Clear the current travel state."""
        self._state = None
        self._current_road = None
        self._phase = FairyRoadPhase.COMPLETE
        self._frozen_mortal_turns = 0

    def is_active(self) -> bool:
        """Check if fairy road travel is active."""
        return self._state is not None and self._phase != FairyRoadPhase.COMPLETE

    def get_current_phase(self) -> FairyRoadPhase:
        """Get the current travel phase."""
        return self._phase

    def get_travel_state(self) -> Optional[FairyRoadTravelState]:
        """Get the current travel state."""
        return self._state

    def get_current_road(self) -> Optional[FairyRoadData]:
        """Get the current fairy road data."""
        return self._current_road

    def get_travel_summary(self) -> dict[str, Any]:
        """Get a summary of current travel for display."""
        if not self._state or not self._current_road:
            return {"active": False}

        return {
            "active": True,
            "road_id": self._state.road_id,
            "road_name": self._current_road.name,
            "phase": self._phase.value,
            "segment": self._state.current_segment,
            "total_segments": self._state.total_segments,
            "entry_door": self._state.entry_door_id,
            "destination_door": self._state.destination_door_id,
            "subjective_turns": self._state.subjective_turns_elapsed,
            "encounters_triggered": self._state.encounters_triggered,
            "strayed": self._state.strayed_from_path,
        }

    def get_available_exits(self) -> list[FairyDoor]:
        """Get available exit doors from the current road."""
        if not self._current_road:
            return []
        return self._current_road.doors

    def get_doors_in_hex(self, hex_id: str) -> list[FairyDoor]:
        """Get fairy doors available in a given hex."""
        return self.registry.get_doors_in_hex(hex_id)


# Singleton instance
_engine: Optional[FairyRoadEngine] = None


def get_fairy_road_engine(controller: GlobalController) -> FairyRoadEngine:
    """Get or create the fairy road engine instance."""
    global _engine
    if _engine is None:
        _engine = FairyRoadEngine(controller)
    return _engine


def reset_fairy_road_engine() -> None:
    """Reset the fairy road engine (for testing)."""
    global _engine
    _engine = None
