"""Fairy Road data models (content-layer).

These dataclasses are intended to represent *loaded content* from
`data/content/fairy_roads/*.json`.

Notes:
- This module is intentionally lightweight and does not depend on engine code.
- Effects are represented as typed dictionaries in `FairyRoadEffect` for flexibility.
  The engine can interpret these effect atoms and apply mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class FairyRoadDoor:
    """A magical door endpoint in the mortal world."""

    hex_id: str
    name: str
    # "endpoint" (normal), "entry" (one-way entry), "exit_only" (no physical door, forced exit)
    direction: str = "endpoint"
    notes: str = ""


@dataclass(frozen=True)
class FairyRoadSideRoad:
    """A side-road leading into a fairy domain."""

    name: str
    requires_invitation: bool = True
    domain_id: Optional[str] = None  # optional normalized id for internal use


@dataclass(frozen=True)
class FairyRoadEffect:
    """A single effect atom to be interpreted by the FairyRoadEngine.

    This is intentionally flexible: `type` is a short identifier and `data` holds payload.
    Example:
        FairyRoadEffect(type="heal", data={"amount": "1d4", "target": "single"})
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FairyRoadLocationEntry:
    """One entry in a road-specific location table."""

    roll: int
    summary: str
    effects: list[FairyRoadEffect] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FairyRoadLocationTable:
    """A location table (typically d8) for a fairy road."""

    die: str = "1d8"
    entries: list[FairyRoadLocationEntry] = field(default_factory=list)


@dataclass(frozen=True)
class FairyRoadDefinition:
    """Definition of a fairy road."""

    road_id: str
    name: str
    length_miles: float
    doors: list[FairyRoadDoor] = field(default_factory=list)
    side_roads: list[FairyRoadSideRoad] = field(default_factory=list)
    atmosphere: str = ""
    special_rules: list[dict[str, Any]] = field(default_factory=list)
    locations: FairyRoadLocationTable = field(default_factory=FairyRoadLocationTable)
    common_tables_ref: str = "fairy_roads_common.json"
    notes: str = ""


# ===== Common tables =====

@dataclass(frozen=True)
class FairyRoadEncounterEntry:
    roll: int
    name: str
    count: str = "1"
    notes: str = ""


@dataclass(frozen=True)
class FairyRoadEncounterTable:
    die: str = "1d20"
    entries: list[FairyRoadEncounterEntry] = field(default_factory=list)


@dataclass(frozen=True)
class TimePassedEntry:
    """A time-passed table entry.

    Either `roll` is set, or `roll_range` is set.
    `time` is a dice+unit string like "1d6 minutes", "2d6 days".
    """

    time: str
    roll: Optional[int] = None
    roll_range: Optional[tuple[int, int]] = None


@dataclass(frozen=True)
class TimePassedTable:
    die: str = "2d6"
    entries: list[TimePassedEntry] = field(default_factory=list)


@dataclass(frozen=True)
class FairyRoadCommon:
    """Shared tables and rules used by all fairy roads."""

    encounter_table: FairyRoadEncounterTable = field(default_factory=FairyRoadEncounterTable)
    time_passed_table: TimePassedTable = field(default_factory=TimePassedTable)
    rules: dict[str, Any] = field(default_factory=dict)
