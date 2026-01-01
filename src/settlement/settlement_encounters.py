"""
Settlement encounter table support.

The authored settlement JSON pack provides two encounter tables per settlement:
- day (usually d6)
- night (usually d6)

The core codebase's TimeOfDay enum is granular (dawn/morning/.../midnight),
so we map it to a day/night key:
- DAY: DAWN, MORNING, MIDDAY, AFTERNOON, DUSK
- NIGHT: EVENING, MIDNIGHT, PREDAWN

This module intentionally does *not* trigger state transitions. It returns a
structured encounter result which SettlementEngine can:
- narrate directly, or
- treat as an EncounterEngine/CombatEngine trigger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.data_models import DiceRoller, TimeOfDay
from src.settlement.settlement_content_models import (
    SettlementData,
    SettlementEncounterEntry,
    SettlementEncounterTable,
)

try:
    # Existing repo has RunLog; keep optional to make this module copy-paste friendly.
    from src.observability.run_log import get_run_log
except Exception:  # pragma: no cover
    get_run_log = None  # type: ignore


# --- Day/Night mapping -------------------------------------------------------

_NIGHT_TODS = {TimeOfDay.EVENING, TimeOfDay.MIDNIGHT, TimeOfDay.PREDAWN}


def tod_to_daynight(tod: TimeOfDay) -> str:
    """Map granular TimeOfDay into 'day' or 'night' keys used by settlement tables."""
    return "night" if tod in _NIGHT_TODS else "day"


# --- Results -----------------------------------------------------------------

@dataclass
class SettlementEncounterResult:
    table_key: str               # 'day' or 'night'
    roll: int                    # die total (e.g. 1..6)
    description: str
    npcs_involved: list[str]
    monsters_involved: list[str]
    notes: Optional[str] = None


# --- Table wrapper -----------------------------------------------------------

class SettlementEncounterTables:
    def __init__(self, settlement: SettlementData) -> None:
        self.settlement = settlement
        self._tables_by_key: dict[str, SettlementEncounterTable] = {}
        for t in (settlement.encounter_tables or []):
            key = (t.time_of_day or "").strip().lower()
            if key:
                self._tables_by_key[key] = t

    def get_table(self, key: str) -> Optional[SettlementEncounterTable]:
        return self._tables_by_key.get((key or "").lower())

    def roll(self, dice: DiceRoller, tod: TimeOfDay) -> Optional[SettlementEncounterResult]:
        key = tod_to_daynight(tod)
        table = self.get_table(key)
        if not table:
            return None

        # die_type like "d6" -> sides (default 6)
        sides = 6
        dt = (table.die_type or "d6").strip().lower()
        if dt.startswith("d"):
            try:
                sides = int(dt[1:])
            except Exception:
                sides = 6

        r = dice.roll(f"1d{sides}", reason=f"Settlement {self.settlement.settlement_id}:{key} encounter table")
        roll_total = int(r.total)

        entry: Optional[SettlementEncounterEntry] = None
        for e in (table.entries or []):
            if e.roll == roll_total:
                entry = e
                break
        if not entry and (table.entries or []):
            # Fallback: clamp into range (e.g. if author omitted roll fields)
            idx = max(0, min(len(table.entries) - 1, roll_total - 1))
            entry = table.entries[idx]

        if not entry:
            return None

        # Optional: log a table lookup event (nice for Foundry-ready UI).
        if get_run_log is not None:
            try:
                get_run_log().log_table_lookup(
                    table_id=f"settlement:{self.settlement.settlement_id}:encounter:{key}",
                    table_name=f"Settlement Encounter ({self.settlement.name} / {key})",
                    roll_total=roll_total,
                    result_text=entry.description,
                    context={
                        "settlement_id": self.settlement.settlement_id,
                        "table_key": key,
                        "npcs_involved": entry.npcs_involved,
                        "monsters_involved": entry.monsters_involved,
                    },
                )
            except Exception:
                pass

        return SettlementEncounterResult(
            table_key=key,
            roll=roll_total,
            description=entry.description,
            npcs_involved=entry.npcs_involved or [],
            monsters_involved=entry.monsters_involved or [],
            notes=entry.notes,
        )
