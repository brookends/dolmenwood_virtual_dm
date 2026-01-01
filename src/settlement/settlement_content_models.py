"""
Settlement content models (JSON-backed).

These dataclasses mirror the JSON structure in the Dolmenwood settlement pack.
They are intentionally **data-only**: no game logic here.

Robustness note:
The settlement JSON pack has evolved over time, and earlier extracts sometimes use
slightly different key names (e.g. `type` vs `location_type`, missing `roll` fields
in encounter entries). The `from_dict` helpers below accept these variations so
imports fail less often and produce actionable warnings upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


def _as_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _as_list(x: Any) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _normalize_hex_id(raw: Any) -> str:
    s = _as_str(raw)
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return s
    if len(digits) < 4:
        digits = digits.zfill(4)
    return digits[:4]


def _coerce_obj(x: Any) -> dict[str, Any]:
    """Coerce governance/religion fields that may be dicts OR strings into dicts."""
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        return {"summary": x.strip()}
    return {"summary": str(x)}


# -----------------------------------------------------------------------------
# Services
# -----------------------------------------------------------------------------

@dataclass
class SettlementServiceData:
    name: str
    description: str = ""
    cost: str = ""
    notes: str = ""

    @staticmethod
    def from_any(x: Any) -> "SettlementServiceData":
        # Some extracts encode services as strings (e.g. "Food") rather than objects.
        if isinstance(x, str):
            return SettlementServiceData(name=x.strip())
        if isinstance(x, dict):
            return SettlementServiceData.from_dict(x)
        return SettlementServiceData(name=str(x).strip())

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SettlementServiceData":
        return SettlementServiceData(
            name=_as_str(d.get("name")),
            description=_as_str(d.get("description")),
            cost=_as_str(d.get("cost")),
            notes=_as_str(d.get("notes")),
        )


# -----------------------------------------------------------------------------
# Locations
# -----------------------------------------------------------------------------

@dataclass
class SettlementLocationData:
    number: int
    name: str
    location_type: str
    description: str = ""
    interior: str = ""
    exterior: str = ""
    populace: str = ""
    atmosphere: str = ""
    services: list[SettlementServiceData] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)          # npc_ids
    special_features: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    monsters: list[str] = field(default_factory=list)      # monster_ids (or local ids)
    is_locked: bool = False
    key_holder: Optional[str] = None                       # npc_id or free text

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SettlementLocationData":
        num_raw = d.get("number", d.get("id", 0))
        try:
            num = int(num_raw)
        except Exception:
            num = 0

        ltype = _as_str(d.get("location_type", d.get("type", d.get("category", ""))))
        locked = bool(d.get("is_locked", d.get("locked", False)))
        key_holder = d.get("key_holder", d.get("keyholder"))
        key_holder_s = _as_str(key_holder) if key_holder else None

        # NPC refs may be list of ids or list of dicts
        npc_refs: list[str] = []
        for x in _as_list(d.get("npcs")):
            if isinstance(x, dict):
                npc_refs.append(_as_str(x.get("npc_id", x.get("id", x.get("name")))))
            else:
                npc_refs.append(_as_str(x))

        return SettlementLocationData(
            number=num,
            name=_as_str(d.get("name")),
            location_type=ltype,
            description=_as_str(d.get("description")),
            interior=_as_str(d.get("interior")),
            exterior=_as_str(d.get("exterior")),
            populace=_as_str(d.get("populace")),
            atmosphere=_as_str(d.get("atmosphere")),
            services=[SettlementServiceData.from_any(x) for x in _as_list(d.get("services"))],
            npcs=[x for x in npc_refs if x],
            special_features=[_as_str(x) for x in _as_list(d.get("special_features")) if _as_str(x)],
            secrets=[_as_str(x) for x in _as_list(d.get("secrets")) if _as_str(x)],
            monsters=[_as_str(x) for x in _as_list(d.get("monsters")) if _as_str(x)],
            is_locked=locked,
            key_holder=key_holder_s,
        )


# -----------------------------------------------------------------------------
# NPCs
# -----------------------------------------------------------------------------

@dataclass
class SettlementNPCData:
    npc_id: str
    name: str
    title: str = ""
    description: str = ""
    kindred: str = ""
    alignment: str = ""
    demeanor: list[str] = field(default_factory=list)
    mannerisms: str = ""
    speech: str = ""
    languages: list[str] = field(default_factory=list)
    desires: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    location_id: Optional[str] = None        # location number as string in source data
    occupation: str = ""

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SettlementNPCData":
        loc = d.get("location_id", d.get("location"))
        loc_s = _as_str(loc) if loc is not None else None

        return SettlementNPCData(
            npc_id=_as_str(d.get("npc_id", d.get("id"))),
            name=_as_str(d.get("name")),
            title=_as_str(d.get("title")),
            description=_as_str(d.get("description")),
            kindred=_as_str(d.get("kindred")),
            alignment=_as_str(d.get("alignment")),
            demeanor=[_as_str(x) for x in _as_list(d.get("demeanor")) if _as_str(x)],
            mannerisms=_as_str(d.get("mannerisms")),
            speech=_as_str(d.get("speech")),
            languages=[_as_str(x) for x in _as_list(d.get("languages")) if _as_str(x)],
            desires=[_as_str(x) for x in _as_list(d.get("desires")) if _as_str(x)],
            secrets=[_as_str(x) for x in _as_list(d.get("secrets")) if _as_str(x)],
            location_id=loc_s,
            occupation=_as_str(d.get("occupation")),
        )


# -----------------------------------------------------------------------------
# Encounters
# -----------------------------------------------------------------------------

@dataclass
class SettlementEncounterEntry:
    roll: int
    description: str
    npcs_involved: list[str] = field(default_factory=list)
    monsters_involved: list[str] = field(default_factory=list)
    notes: Optional[str] = None

    @staticmethod
    def from_dict(d: dict[str, Any], *, fallback_roll: int = 0) -> "SettlementEncounterEntry":
        roll_raw = d.get("roll", fallback_roll)
        try:
            roll = int(roll_raw)
        except Exception:
            roll = fallback_roll

        return SettlementEncounterEntry(
            roll=roll,
            description=_as_str(d.get("description", d.get("result", ""))),
            npcs_involved=[_as_str(x) for x in _as_list(d.get("npcs_involved", d.get("npcs"))) if _as_str(x)],
            monsters_involved=[_as_str(x) for x in _as_list(d.get("monsters_involved", d.get("monsters"))) if _as_str(x)],
            notes=_as_str(d.get("notes")) or None,
        )


@dataclass
class SettlementEncounterTable:
    time_of_day: str              # "day" or "night"
    die_type: str                 # "d6", "d8", etc.
    entries: list[SettlementEncounterEntry] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SettlementEncounterTable":
        tod = _as_str(d.get("time_of_day", d.get("key", ""))).lower()
        die = _as_str(d.get("die_type", d.get("die", "d6"))) or "d6"

        raw_entries = _as_list(d.get("entries", d.get("results")))
        entries: list[SettlementEncounterEntry] = []
        for idx, x in enumerate(raw_entries, start=1):
            if isinstance(x, str):
                entries.append(SettlementEncounterEntry(roll=idx, description=x.strip()))
            elif isinstance(x, dict):
                entries.append(SettlementEncounterEntry.from_dict(x, fallback_roll=idx))
            else:
                entries.append(SettlementEncounterEntry(roll=idx, description=str(x).strip()))

        # If author used explicit roll values, keep; otherwise ensure 1..N
        if any(e.roll == 0 for e in entries):
            for i, e in enumerate(entries, start=1):
                e.roll = i

        return SettlementEncounterTable(time_of_day=tod, die_type=die, entries=entries)


# -----------------------------------------------------------------------------
# Equipment availability
# -----------------------------------------------------------------------------

@dataclass
class SettlementEquipmentAvailability:
    price_modifier: float = 1.0
    available_categories: list[str] = field(default_factory=list)
    unavailable_categories: list[str] = field(default_factory=list)
    special_items: list[str] = field(default_factory=list)
    notes: str = ""

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SettlementEquipmentAvailability":
        try:
            pm = float(d.get("price_modifier", 1.0))
        except Exception:
            pm = 1.0
        return SettlementEquipmentAvailability(
            price_modifier=pm,
            available_categories=[_as_str(x) for x in _as_list(d.get("available_categories", d.get("available"))) if _as_str(x)],
            unavailable_categories=[_as_str(x) for x in _as_list(d.get("unavailable_categories", d.get("unavailable"))) if _as_str(x)],
            special_items=[_as_str(x) for x in _as_list(d.get("special_items", d.get("special"))) if _as_str(x)],
            notes=_as_str(d.get("notes")),
        )


# -----------------------------------------------------------------------------
# Settlement root
# -----------------------------------------------------------------------------

@dataclass
class SettlementData:
    settlement_id: str
    name: str
    hex_id: str
    size: str
    population: int
    tagline: str = ""
    description: str = ""
    atmosphere: str = ""
    inhabitants_description: str = ""
    governance: dict[str, Any] = field(default_factory=dict)
    religion: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    current_events: list[str] = field(default_factory=list)
    rumors_reference: str = ""
    special_features: list[str] = field(default_factory=list)

    equipment_availability: SettlementEquipmentAvailability = field(default_factory=SettlementEquipmentAvailability)
    locations: list[SettlementLocationData] = field(default_factory=list)
    npcs: list[SettlementNPCData] = field(default_factory=list)
    encounter_tables: list[SettlementEncounterTable] = field(default_factory=list)

    monsters: list[dict[str, Any]] = field(default_factory=list)     # local monster defs; optional
    roads: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SettlementData":
        # Support both single-record files and wrapper formats like {"items":[...]}
        base = d.get("settlement") if isinstance(d.get("settlement"), dict) else d

        sid = _as_str(base.get("settlement_id", base.get("id")))
        name = _as_str(base.get("name"))
        hex_id = _normalize_hex_id(base.get("hex_id", base.get("hex")))
        size = _as_str(base.get("size"))
        try:
            pop = int(base.get("population", 0))
        except Exception:
            pop = 0

        return SettlementData(
            settlement_id=sid,
            name=name,
            hex_id=hex_id,
            size=size,
            population=pop,
            tagline=_as_str(base.get("tagline")),
            description=_as_str(base.get("description")),
            atmosphere=_as_str(base.get("atmosphere")),
            inhabitants_description=_as_str(base.get("inhabitants_description")),
            governance=_coerce_obj(base.get("governance")),
            religion=_coerce_obj(base.get("religion")),
            history=[_as_str(x) for x in _as_list(base.get("history")) if _as_str(x)],
            current_events=[_as_str(x) for x in _as_list(base.get("current_events")) if _as_str(x)],
            rumors_reference=_as_str(base.get("rumors_reference")),
            special_features=[_as_str(x) for x in _as_list(base.get("special_features")) if _as_str(x)],
            equipment_availability=SettlementEquipmentAvailability.from_dict(base.get("equipment_availability") or {}),
            locations=[SettlementLocationData.from_dict(x) for x in _as_list(base.get("locations")) if isinstance(x, dict)],
            npcs=[SettlementNPCData.from_dict(x) for x in _as_list(base.get("npcs")) if isinstance(x, dict)],
            encounter_tables=[SettlementEncounterTable.from_dict(x) for x in _as_list(base.get("encounter_tables")) if isinstance(x, dict)],
            monsters=_as_list(base.get("monsters")),
            roads=[_as_str(x) for x in _as_list(base.get("roads")) if _as_str(x)],
            connections=[_as_str(x) for x in _as_list(base.get("connections")) if _as_str(x)],
            metadata=(d.get("_metadata") or {}),
        )

    def location_by_number(self) -> dict[int, SettlementLocationData]:
        return {loc.number: loc for loc in self.locations}

    def npc_by_id(self) -> dict[str, SettlementNPCData]:
        return {npc.npc_id: npc for npc in self.npcs}
