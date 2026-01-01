"""
Fairy road content models (JSON-backed).

These dataclasses define the structure for fairy roads in Dolmenwood.
Fairy roads are ancient roads through the woods that connect locations
via fairy doors, allowing faster travel but with supernatural risks.

Key concepts:
- Fairy roads exist as a parallel realm to the mortal world
- Time may flow differently on fairy roads (subjective time vs mortal time)
- Travel on fairy roads has encounter checks (1d6: 1-2 monster, 3-4 location, 5-6 nothing)
- "Don't Stray From the Path" mechanic for when travelers go unconscious
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


def _as_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _as_list(x: Any) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _as_int(x: Any) -> int:
    if x is None:
        return 0
    if isinstance(x, int):
        return x
    try:
        return int(x)
    except (ValueError, TypeError):
        return 0


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


# -----------------------------------------------------------------------------
# Fairy Door (Entry/Exit Points)
# -----------------------------------------------------------------------------

@dataclass
class FairyDoor:
    """
    A fairy door - an entry/exit point to a fairy road.

    Fairy doors connect the mortal world (a specific hex) to a fairy road.
    They may have requirements to open (time of day, moonphase, offering, etc.)
    """

    door_id: str
    name: str
    hex_id: str  # Mortal world hex location
    fairy_road_id: str  # Which fairy road this connects to
    description: str = ""

    # Access requirements
    requires_moonphase: Optional[str] = None  # e.g., "full_moon", "new_moon"
    requires_time: Optional[str] = None  # e.g., "midnight", "twilight"
    requires_offering: Optional[str] = None  # e.g., "honey", "milk", "silver coin"
    requires_password: Optional[str] = None  # Spoken phrase to open

    # Visibility
    always_visible: bool = False  # Some doors are hidden until opened
    detection_dc: int = 0  # Difficulty to find if not visible

    # Position on road (0.0 = start, 1.0 = end)
    road_position: float = 0.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FairyDoor":
        return FairyDoor(
            door_id=_as_str(d.get("door_id")),
            name=_as_str(d.get("name")),
            hex_id=_as_str(d.get("hex_id")),
            fairy_road_id=_as_str(d.get("fairy_road_id")),
            description=_as_str(d.get("description")),
            requires_moonphase=d.get("requires_moonphase"),
            requires_time=d.get("requires_time"),
            requires_offering=d.get("requires_offering"),
            requires_password=d.get("requires_password"),
            always_visible=bool(d.get("always_visible", False)),
            detection_dc=_as_int(d.get("detection_dc", 0)),
            road_position=float(d.get("road_position", 0.0)),
        )


# -----------------------------------------------------------------------------
# Fairy Road Encounter Tables
# -----------------------------------------------------------------------------

@dataclass
class FairyRoadEncounterEntry:
    """A single entry in a fairy road encounter table."""

    roll: int  # The die roll that triggers this entry
    roll_max: int = 0  # For range entries (e.g., 1-2)
    creature_type: str = ""  # Monster/NPC type
    count_dice: str = ""  # e.g., "1d6", "2d4"
    count_fixed: int = 0  # Fixed count if no dice
    description: str = ""
    behavior: str = ""  # How they act toward travelers
    is_hostile: bool = False
    monster_ids: list[str] = field(default_factory=list)  # Lookup IDs

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FairyRoadEncounterEntry":
        roll = _as_int(d.get("roll", 0))
        roll_max = _as_int(d.get("roll_max", 0))
        if roll_max == 0:
            roll_max = roll
        return FairyRoadEncounterEntry(
            roll=roll,
            roll_max=roll_max,
            creature_type=_as_str(d.get("creature_type")),
            count_dice=_as_str(d.get("count_dice")),
            count_fixed=_as_int(d.get("count_fixed", 0)),
            description=_as_str(d.get("description")),
            behavior=_as_str(d.get("behavior")),
            is_hostile=bool(d.get("is_hostile", False)),
            monster_ids=_as_list(d.get("monster_ids")),
        )


@dataclass
class FairyRoadLocationEntry:
    """A location encountered on a fairy road (roll 3-4)."""

    roll: int
    roll_max: int = 0
    name: str = ""
    description: str = ""
    features: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    treasures: list[str] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FairyRoadLocationEntry":
        roll = _as_int(d.get("roll", 0))
        roll_max = _as_int(d.get("roll_max", 0))
        if roll_max == 0:
            roll_max = roll
        return FairyRoadLocationEntry(
            roll=roll,
            roll_max=roll_max,
            name=_as_str(d.get("name")),
            description=_as_str(d.get("description")),
            features=_as_list(d.get("features")),
            hazards=_as_list(d.get("hazards")),
            treasures=_as_list(d.get("treasures")),
            npcs=_as_list(d.get("npcs")),
        )


@dataclass
class FairyRoadEncounterTable:
    """Encounter table for a fairy road."""

    table_id: str
    name: str
    die_type: str = "d8"  # Die to roll
    monster_entries: list[FairyRoadEncounterEntry] = field(default_factory=list)
    location_entries: list[FairyRoadLocationEntry] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FairyRoadEncounterTable":
        monster_entries = [
            FairyRoadEncounterEntry.from_dict(e)
            for e in _as_list(d.get("monster_entries"))
            if isinstance(e, dict)
        ]
        location_entries = [
            FairyRoadLocationEntry.from_dict(e)
            for e in _as_list(d.get("location_entries"))
            if isinstance(e, dict)
        ]
        return FairyRoadEncounterTable(
            table_id=_as_str(d.get("table_id")),
            name=_as_str(d.get("name")),
            die_type=_as_str(d.get("die_type")) or "d8",
            monster_entries=monster_entries,
            location_entries=location_entries,
        )


# -----------------------------------------------------------------------------
# Fairy Road
# -----------------------------------------------------------------------------

@dataclass
class FairyRoadData:
    """
    A fairy road in Dolmenwood.

    Fairy roads are ancient, supernatural paths that allow travel between
    distant locations through fairy doors. Travel on fairy roads is faster
    than normal wilderness travel but carries supernatural risks.

    Key features:
    - Subjective time (time on the road may not match mortal world time)
    - Encounter checks (1d6: 1-2 monster, 3-4 location, 5-6 nothing)
    - "Don't Stray From the Path" mechanic for unconscious travelers
    """

    road_id: str
    name: str
    description: str = ""

    # Road characteristics
    length_segments: int = 3  # How many travel checks to traverse fully
    difficulty: str = "normal"  # easy, normal, dangerous

    # Time dilation
    time_dilation_enabled: bool = True  # Whether time flows differently
    time_dilation_dice: str = "1d12"  # Roll for mortal world time passage
    time_dilation_unit: str = "days"  # hours, days, weeks, months

    # Connected doors
    doors: list[FairyDoor] = field(default_factory=list)

    # Encounter table
    encounter_table: Optional[FairyRoadEncounterTable] = None

    # Stray from path consequences
    stray_exit_hexes: list[str] = field(default_factory=list)  # Random exit hexes
    stray_time_dice: str = "1d6"  # Additional time when straying
    stray_time_unit: str = "hours"

    # Atmosphere and description
    atmosphere: str = ""
    sights: list[str] = field(default_factory=list)
    sounds: list[str] = field(default_factory=list)
    smells: list[str] = field(default_factory=list)

    # Denizens - NPCs that frequent this road
    denizens: list[str] = field(default_factory=list)  # NPC IDs

    # Special rules
    no_magic: bool = False  # Magic doesn't work on this road
    no_iron: bool = False  # Iron items cause problems
    special_rules: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FairyRoadData":
        doors = [
            FairyDoor.from_dict(door)
            for door in _as_list(d.get("doors"))
            if isinstance(door, dict)
        ]

        encounter_table = None
        if d.get("encounter_table") and isinstance(d["encounter_table"], dict):
            encounter_table = FairyRoadEncounterTable.from_dict(d["encounter_table"])

        return FairyRoadData(
            road_id=_as_str(d.get("road_id")),
            name=_as_str(d.get("name")),
            description=_as_str(d.get("description")),
            length_segments=_as_int(d.get("length_segments", 3)),
            difficulty=_as_str(d.get("difficulty")) or "normal",
            time_dilation_enabled=bool(d.get("time_dilation_enabled", True)),
            time_dilation_dice=_as_str(d.get("time_dilation_dice")) or "1d12",
            time_dilation_unit=_as_str(d.get("time_dilation_unit")) or "days",
            doors=doors,
            encounter_table=encounter_table,
            stray_exit_hexes=_as_list(d.get("stray_exit_hexes")),
            stray_time_dice=_as_str(d.get("stray_time_dice")) or "1d6",
            stray_time_unit=_as_str(d.get("stray_time_unit")) or "hours",
            atmosphere=_as_str(d.get("atmosphere")),
            sights=_as_list(d.get("sights")),
            sounds=_as_list(d.get("sounds")),
            smells=_as_list(d.get("smells")),
            denizens=_as_list(d.get("denizens")),
            no_magic=bool(d.get("no_magic", False)),
            no_iron=bool(d.get("no_iron", False)),
            special_rules=_as_list(d.get("special_rules")),
        )


# -----------------------------------------------------------------------------
# Travel State (Runtime)
# -----------------------------------------------------------------------------

@dataclass
class FairyRoadTravelState:
    """
    Runtime state for a party traveling on a fairy road.

    This tracks:
    - Current position on the road
    - Subjective time elapsed (time experienced by travelers)
    - Entry door (for potential return)
    - Encounters triggered
    """

    road_id: str
    entry_door_id: str
    entry_hex_id: str  # Mortal world hex they entered from
    current_segment: int = 0
    total_segments: int = 3

    # Time tracking
    subjective_turns_elapsed: int = 0  # Time experienced on the road
    mortal_time_frozen: bool = True  # Whether mortal world time is frozen

    # Travel direction
    destination_door_id: Optional[str] = None  # Target exit door

    # Encounter tracking
    encounters_triggered: int = 0
    last_check_result: Optional[FairyRoadCheckResult] = None

    # Status flags
    strayed_from_path: bool = False
    is_complete: bool = False


@dataclass
class FairyRoadCheckOutcome:
    """Result of a fairy road travel check."""

    check_type: FairyRoadCheckResult
    roll: int

    # For monster encounters
    monster_entry: Optional[FairyRoadEncounterEntry] = None
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
    fairy_encounter_id: Optional[str] = None
