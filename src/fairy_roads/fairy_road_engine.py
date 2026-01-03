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
- On exit: roll for mortal world time passage from common tables
- Party travels as a unit; if anyone goes unconscious, ALL stray from path
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging
import re

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.data_models import (
    DiceRoller,
    EncounterState,
    EncounterType,
    Combatant,
    StatBlock,
)
from src.encounter.encounter_engine import EncounterOrigin
from src.fairy_roads.models import (
    FairyRoadDefinition,
    FairyRoadDoor,
    FairyRoadCommon,
    FairyRoadLocationEntry,
    FairyRoadEncounterEntry,
    TimePassedEntry,
)
from src.content_loader.fairy_road_registry import (
    FairyRoadRegistry,
    get_fairy_road_registry,
    DoorRef,
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


class FairyRoadCheckResult(str, Enum):
    """Result of a fairy road travel check (1d6)."""

    MONSTER_ENCOUNTER = "monster_encounter"  # 1-2
    LOCATION_ENCOUNTER = "location_encounter"  # 3-4
    NOTHING = "nothing"  # 5-6


class StrayFromPathResult(str, Enum):
    """What happens when a character strays from the path."""

    LOST_IN_WOODS = "lost_in_woods"  # Wakes in random hex
    TIME_DILATION = "time_dilation"  # Time passes differently
    FAIRY_ENCOUNTER = "fairy_encounter"  # Meets a fairy denizen


@dataclass
class FairyRoadTravelState:
    """
    Runtime state for a party traveling on a fairy road.
    """

    road_id: str
    entry_door_hex: str
    entry_door_name: str
    current_segment: int = 0
    total_segments: int = 3

    # Time tracking
    subjective_turns_elapsed: int = 0
    mortal_time_frozen: bool = True

    # Travel direction
    destination_door_hex: Optional[str] = None
    destination_door_name: Optional[str] = None

    # Encounter tracking
    encounters_triggered: int = 0
    last_check_result: Optional[FairyRoadCheckResult] = None

    # Last encounter/location data for reference
    last_encounter_entry: Optional[FairyRoadEncounterEntry] = None
    last_location_entry: Optional[FairyRoadLocationEntry] = None

    # Status flags
    strayed_from_path: bool = False
    is_complete: bool = False


@dataclass
class FairyRoadCheckOutcome:
    """Result of a fairy road travel check."""

    check_type: FairyRoadCheckResult
    roll: int

    # For monster encounters
    encounter_entry: Optional[FairyRoadEncounterEntry] = None
    monster_count: int = 0

    # For location encounters
    location_entry: Optional[FairyRoadLocationEntry] = None

    # Description for narration
    description: str = ""


@dataclass
class StrayFromPathOutcome:
    """Result of straying from the fairy road path."""

    result_type: StrayFromPathResult
    exit_hex_id: str = ""
    time_passed_mortal: int = 0
    time_unit: str = "hours"
    description: str = ""


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
    door_hex: str = ""
    door_name: str = ""
    messages: list[str] = field(default_factory=list)


@dataclass
class FairyRoadExitResult:
    """Result of exiting a fairy road."""

    success: bool
    exit_hex_id: str = ""
    door_name: str = ""
    time_dilation_dice: str = ""
    time_dilation_roll: int = 0
    mortal_time_passed: str = ""
    mortal_turns_passed: int = 0
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
        self._current_road: Optional[FairyRoadDefinition] = None
        self._common: Optional[FairyRoadCommon] = None
        self._phase: FairyRoadPhase = FairyRoadPhase.COMPLETE

        # Callbacks
        self._narration_callback: Optional[Callable] = None

        # Track mortal world time that was frozen
        self._frozen_mortal_turns: int = 0

    def register_narration_callback(self, callback: Callable) -> None:
        """Register callback for fairy road narration."""
        self._narration_callback = callback

    def _ensure_registry_loaded(self) -> None:
        """Ensure the registry is loaded."""
        if not self.registry.is_loaded:
            self.registry.load_from_directory()
        if self._common is None:
            self._common = self.registry.common

    # =========================================================================
    # ENTRY
    # =========================================================================

    def get_doors_in_hex(self, hex_id: str) -> list[DoorRef]:
        """Get fairy doors available in a given hex."""
        self._ensure_registry_loaded()
        return self.registry.get_doors_at_hex(hex_id)

    def can_enter_from_hex(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Check what fairy roads can be entered from a hex.

        Returns a list of available roads with door info.
        """
        self._ensure_registry_loaded()
        doors = self.registry.get_doors_at_hex(hex_id)
        result = []
        for door_ref in doors:
            # Only entry or endpoint doors can be entered
            if door_ref.door.direction in ("entry", "endpoint"):
                result.append({
                    "road_id": door_ref.road_id,
                    "road_name": door_ref.road_name,
                    "door_name": door_ref.door.name,
                    "door_hex": door_ref.door.hex_id,
                    "direction": door_ref.door.direction,
                })
        return result

    def enter_fairy_road(
        self,
        road_id: str,
        entry_hex_id: str,
        destination_hex_id: Optional[str] = None,
    ) -> FairyRoadEntryResult:
        """
        Enter a fairy road through a door.

        Args:
            road_id: ID of the fairy road to enter
            entry_hex_id: The hex with the entry door
            destination_hex_id: Optional target exit hex

        Returns:
            FairyRoadEntryResult with entry status
        """
        self._ensure_registry_loaded()

        # Get the road
        lookup = self.registry.get_by_id(road_id)
        if not lookup.found or not lookup.road:
            return FairyRoadEntryResult(
                success=False,
                messages=[f"Fairy road '{road_id}' not found"],
            )

        road = lookup.road

        # Find the door at entry hex
        door_ref = self.registry.get_door(entry_hex_id, road_id)
        if not door_ref:
            return FairyRoadEntryResult(
                success=False,
                messages=[f"No door to '{road.name}' in hex {entry_hex_id}"],
            )

        # Check door direction allows entry
        if door_ref.door.direction == "exit_only":
            return FairyRoadEntryResult(
                success=False,
                messages=[f"'{door_ref.door.name}' is exit-only"],
            )

        # Calculate segments based on road length (1 segment per 4 miles, minimum 2)
        segments = max(2, int(road.length_miles / 4))

        # Find destination door if specified
        dest_door_name = None
        dest_door_hex = None
        if destination_hex_id:
            dest_ref = self.registry.get_door(destination_hex_id, road_id)
            if dest_ref:
                dest_door_name = dest_ref.door.name
                dest_door_hex = dest_ref.door.hex_id

        # Initialize travel state
        self._current_road = road
        self._state = FairyRoadTravelState(
            road_id=road.road_id,
            entry_door_hex=entry_hex_id,
            entry_door_name=door_ref.door.name,
            current_segment=0,
            total_segments=segments,
            destination_door_hex=dest_door_hex,
            destination_door_name=dest_door_name,
            mortal_time_frozen=True,
        )
        self._phase = FairyRoadPhase.ENTERING
        self._frozen_mortal_turns = 0

        # Transition game state
        self.controller.transition(
            "enter_fairy_road",
            context={
                "road_id": road.road_id,
                "road_name": road.name,
                "door_name": door_ref.door.name,
                "entry_hex": entry_hex_id,
            },
        )

        self._phase = FairyRoadPhase.TRAVELING

        messages = [
            f"You pass through {door_ref.door.name}...",
            f"You step onto {road.name}.",
        ]
        if road.atmosphere:
            messages.append(road.atmosphere)

        return FairyRoadEntryResult(
            success=True,
            road_id=road.road_id,
            door_hex=entry_hex_id,
            door_name=door_ref.door.name,
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

        # Track frozen mortal time
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
        """Roll on the common monster encounter table."""
        if not self._common or not self._common.encounter_table.entries:
            outcome.description = "A shadowy figure appears on the road..."
            return outcome

        table = self._common.encounter_table
        die_type = table.die
        roll = self.dice.roll(die_type, "monster table roll")

        # Find matching entry
        for entry in table.entries:
            if entry.roll == roll.total:
                outcome.encounter_entry = entry
                self._state.last_encounter_entry = entry
                outcome.description = f"{entry.name} appears!"

                # Roll for count
                if entry.count and entry.count != "1":
                    # Parse dice notation like "2d6"
                    if re.match(r"\d+d\d+", entry.count):
                        count_roll = self.dice.roll(entry.count, "monster count")
                        outcome.monster_count = count_roll.total
                    else:
                        outcome.monster_count = int(entry.count)
                else:
                    outcome.monster_count = 1

                if entry.notes:
                    outcome.description += f" ({entry.notes})"

                return outcome

        outcome.description = "Strange shapes move in the mist..."
        return outcome

    def _roll_location_encounter(
        self, outcome: FairyRoadCheckOutcome
    ) -> FairyRoadCheckOutcome:
        """Roll on the road-specific location table."""
        if not self._current_road or not self._current_road.locations.entries:
            outcome.description = "A clearing appears in the ethereal mist..."
            return outcome

        table = self._current_road.locations
        die_type = table.die
        roll = self.dice.roll(die_type, "location table roll")

        # Find matching entry
        for entry in table.entries:
            if entry.roll == roll.total:
                outcome.location_entry = entry
                self._state.last_location_entry = entry
                outcome.description = entry.summary
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
        if not self._state or not self._state.last_encounter_entry:
            return None

        entry = self._state.last_encounter_entry

        # Build actor list from encounter entry
        actors = [entry.name]

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            actors=actors,
            context={
                "origin": "fairy_road",
                "road_id": self._state.road_id,
                "monster_name": entry.name,
                "monster_count": self._state.last_check_result,
            },
        )

        return encounter

    def trigger_encounter_transition(self) -> dict[str, Any]:
        """
        Trigger a transition to ENCOUNTER state for a fairy road monster.

        This should be called after travel_segment() returns encounter_triggered=True.

        Returns:
            Dictionary with transition result
        """
        if not self._state or not self._state.last_encounter_entry:
            return {"success": False, "message": "No encounter to trigger"}

        encounter = self.create_monster_encounter()
        if not encounter:
            return {"success": False, "message": "Could not create encounter"}

        # Set encounter in controller
        self.controller.set_encounter(encounter)

        # Transition to encounter state
        self.controller.transition(
            "encounter_triggered",
            context={
                "origin": "fairy_road",
                "road_id": self._state.road_id,
            },
        )

        return {
            "success": True,
            "message": f"Encounter triggered: {self._state.last_encounter_entry.name}",
        }

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

        # Roll for exit hex - use entry hex as fallback if no stray hexes defined
        # For now, use entry hex (could be expanded with stray hex tables)
        exit_hex = self._state.entry_door_hex

        # Roll time passed using common table
        time_str, time_turns = self._roll_time_dilation()

        outcome = StrayFromPathOutcome(
            result_type=StrayFromPathResult.LOST_IN_WOODS,
            exit_hex_id=exit_hex,
            time_passed_mortal=time_turns,
            time_unit="turns",
            description=(
                f"The unconscious traveler causes the party to stray from the path. "
                f"They awaken in hex {exit_hex}. {time_str} has passed in the mortal world."
            ),
        )

        # Apply time passage
        if time_turns > 0:
            self.controller.advance_time(time_turns)

        # Transition back to wilderness
        self.controller.transition(
            "exit_fairy_road",
            context={
                "reason": "strayed_from_path",
                "exit_hex": exit_hex,
                "time_passed": time_str,
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
        self, exit_hex_id: Optional[str] = None
    ) -> FairyRoadExitResult:
        """
        Exit the fairy road through a door.

        Args:
            exit_hex_id: Hex to exit at (uses destination or finds nearest if not specified)

        Returns:
            FairyRoadExitResult with exit details and time dilation
        """
        if not self._state or not self._current_road:
            return FairyRoadExitResult(
                success=False,
                messages=["Not currently on a fairy road"],
            )

        # Determine exit door
        target_hex = exit_hex_id or self._state.destination_door_hex
        if not target_hex:
            # Find any exit door on this road
            for door in self._current_road.doors:
                if door.direction in ("exit_only", "endpoint"):
                    target_hex = door.hex_id
                    break

        if not target_hex:
            return FairyRoadExitResult(
                success=False,
                messages=["No exit door available"],
            )

        # Get door info
        door_ref = self.registry.get_door(target_hex, self._state.road_id)
        door_name = door_ref.door.name if door_ref else "the exit"

        result = FairyRoadExitResult(
            success=True,
            door_name=door_name,
            exit_hex_id=target_hex,
        )

        messages = [
            f"You approach {door_name}...",
            f"Stepping through, you emerge in the mortal world at hex {target_hex}.",
        ]

        # Roll time dilation
        time_str, time_turns = self._roll_time_dilation()
        result.mortal_time_passed = time_str
        result.mortal_turns_passed = time_turns

        if time_turns > 0:
            messages.append(
                f"As you exit, you realize {time_str} has passed in the mortal world!"
            )
            self.controller.advance_time(time_turns)

        result.messages = messages

        # Transition back to wilderness
        self.controller.transition(
            "exit_fairy_road",
            context={
                "exit_hex": target_hex,
                "time_passed": time_str,
                "road_id": self._state.road_id,
            },
        )

        # Clear travel state
        self._clear_travel_state()

        return result

    def _roll_time_dilation(self) -> tuple[str, int]:
        """
        Roll on the time passed table from common tables.

        Returns:
            Tuple of (time description string, time in turns)
        """
        if not self._common or not self._common.time_passed_table.entries:
            return ("1d6 days", 144 * 3)  # Default fallback: ~3 days

        table = self._common.time_passed_table
        roll = self.dice.roll(table.die, "time dilation")
        roll_total = roll.total

        # Find matching entry
        for entry in table.entries:
            matched = False
            if entry.roll is not None and entry.roll == roll_total:
                matched = True
            elif entry.roll_range is not None:
                low, high = entry.roll_range
                if low <= roll_total <= high:
                    matched = True

            if matched:
                time_str = entry.time
                turns = self._parse_time_to_turns(time_str)
                return (time_str, turns)

        return ("1d6 days", 144 * 3)

    def _parse_time_to_turns(self, time_str: str) -> int:
        """
        Parse a time string like "1d6 days" or "2d6 hours" into turns.

        1 turn = 10 minutes
        1 hour = 6 turns
        1 day = 144 turns
        1 week = 1008 turns
        """
        time_str = time_str.lower().strip()

        # Extract dice notation
        dice_match = re.match(r"(\d+d\d+|\d+)", time_str)
        if not dice_match:
            return 144  # Default 1 day

        dice_part = dice_match.group(1)
        if "d" in dice_part:
            roll = self.dice.roll(dice_part, "time amount")
            amount = roll.total
        else:
            amount = int(dice_part)

        # Determine unit
        if "minute" in time_str:
            turns = amount // 10  # 10 min per turn
        elif "hour" in time_str:
            turns = amount * 6  # 6 turns per hour
        elif "week" in time_str:
            turns = amount * 144 * 7  # 144 turns/day * 7 days
        elif "day" in time_str:
            turns = amount * 144  # 144 turns per day
        else:
            turns = amount * 144  # Default to days

        return max(1, turns)

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

    def get_current_road(self) -> Optional[FairyRoadDefinition]:
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
            "entry_door": self._state.entry_door_name,
            "destination_door": self._state.destination_door_name,
            "subjective_turns": self._state.subjective_turns_elapsed,
            "encounters_triggered": self._state.encounters_triggered,
            "strayed": self._state.strayed_from_path,
        }

    def get_available_exits(self) -> list[dict[str, str]]:
        """Get available exit doors from the current road."""
        if not self._current_road:
            return []
        exits = []
        for door in self._current_road.doors:
            if door.direction in ("exit_only", "endpoint"):
                exits.append({
                    "hex_id": door.hex_id,
                    "name": door.name,
                    "direction": door.direction,
                })
        return exits

    # =========================================================================
    # COMBAT TRIGGER (P2-11)
    # =========================================================================

    def trigger_combat_transition(
        self,
        target_ids: Optional[list[str]] = None,
        reason: str = "hostile_encounter",
    ) -> dict[str, Any]:
        """
        Trigger a direct transition to COMBAT state for fairy road combat.

        This is used when:
        - Party attacks fairy road denizens
        - Hostile fairy creatures attack the party
        - A reaction roll results in immediate attack

        Per state_machine.py:
        - FAIRY_ROAD_TRAVEL -> COMBAT via "fairy_road_combat"
        - Combat ends return to FAIRY_ROAD_TRAVEL via "combat_end_fairy_road"

        Args:
            target_ids: Optional list of monster IDs to fight.
                If not provided, uses the last encounter entry.
            reason: Reason for combat (for logging)

        Returns:
            Dictionary with transition result
        """
        if not self._state:
            return {"success": False, "message": "No active fairy road travel"}

        # Get combatant info from last encounter or explicit targets
        combatants: list[Combatant] = []
        actors: list[str] = []
        encounter_name = "unknown creatures"

        if target_ids:
            actors = target_ids
            encounter_name = ", ".join(target_ids)
        elif self._state.last_encounter_entry:
            entry = self._state.last_encounter_entry
            actors = [entry.name]
            encounter_name = entry.name

            # Check is_hostile flag from fairy road models
            if hasattr(entry, "is_hostile") and entry.is_hostile:
                reason = "hostile_fairy_creature"

        if not actors:
            return {"success": False, "message": "No targets for combat"}

        # Create combatants from monster registry
        from src.content_loader.monster_registry import get_monster_registry
        from uuid import uuid4

        registry = get_monster_registry()
        num_appearing = self._state.last_check_result or 1

        for actor_id in actors:
            for i in range(num_appearing):
                combatant = registry.create_combatant(
                    monster_id=actor_id,
                    combatant_id=f"{actor_id}_{uuid4().hex[:8]}",
                )
                if combatant:
                    combatant.side = "enemy"
                    combatants.append(combatant)
                else:
                    # Fallback: create generic combatant with stat block
                    fallback_stat_block = StatBlock(
                        armor_class=12,  # Fairy creatures tend to be agile
                        hit_dice="1d8",
                        hp_current=8,
                        hp_max=8,
                        movement=40,  # Fey are quick
                        attacks=[{"name": "Attack", "damage": "1d6", "bonus": 1}],
                        morale=8,
                    )
                    combatants.append(
                        Combatant(
                            combatant_id=f"fairy_{uuid4().hex[:8]}",
                            name=actor_id if num_appearing == 1 else f"{actor_id} #{i + 1}",
                            side="enemy",
                            stat_block=fallback_stat_block,
                        )
                    )

        if not combatants:
            return {"success": False, "message": "Could not create combatants"}

        # Create encounter state with combatants
        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            actors=actors,
            context=reason,
            terrain="fairy_road",
            combatants=combatants,
        )

        # Set encounter in controller
        self.controller.set_encounter(encounter)

        # Transition to combat state
        self.controller.transition(
            "fairy_road_combat",
            context={
                "origin": "fairy_road",
                "road_id": self._state.road_id,
                "reason": reason,
            },
        )

        logger.info(
            f"Fairy road combat triggered: {encounter_name} "
            f"({len(combatants)} combatants)"
        )

        return {
            "success": True,
            "message": f"Combat begins on the fairy road! Fighting {encounter_name}.",
            "combatant_count": len(combatants),
            "reason": reason,
        }


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
