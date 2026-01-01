"""Fairy Road Data Loader for Dolmenwood Virtual DM.

Loads fairy road definitions from JSON files in `data/content/fairy_roads`.

Supported formats:
1) Single-object road file (recommended):
    {
      "content_type": "fairy_road",
      "id": "buttercup_lane",
      "name": "Buttercup Lane",
      "length_miles": 12,
      "doors": [...],
      "tables": { "locations_d8": { "die": "1d8", "entries": [...] } },
      "common_tables_ref": "fairy_roads_common.json"
    }

2) Wrapper file (future-proof, consistent with spells/monsters):
    { "_metadata": {...}, "items": [ <road objects> ] }

3) Common tables file:
    { "content_type": "fairy_roads_common", "tables": {...}, "rules": {...} }

This module intentionally focuses on:
- file discovery
- minimal validation
- conversion into dataclasses in `src.fairy_roads.models`

Engine-specific interpretation of effects is out of scope here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.fairy_roads.models import (
    FairyRoadCommon,
    FairyRoadDefinition,
    FairyRoadDoor,
    FairyRoadEffect,
    FairyRoadEncounterEntry,
    FairyRoadEncounterTable,
    FairyRoadLocationEntry,
    FairyRoadLocationTable,
    FairyRoadSideRoad,
    TimePassedEntry,
    TimePassedTable,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class FairyRoadFileMetadata:
    """Metadata from a JSON file that optionally includes _metadata."""

    source_file: str = ""
    pages: list[int] = field(default_factory=list)
    content_type: str = ""
    item_count: int = 0
    errors: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class FairyRoadFileLoadResult:
    file_path: Path
    success: bool
    metadata: Optional[FairyRoadFileMetadata] = None
    roads_loaded: int = 0
    roads_failed: int = 0
    common_loaded: bool = False
    errors: list[str] = field(default_factory=list)
    loaded_roads: list[FairyRoadDefinition] = field(default_factory=list)
    loaded_common: Optional[FairyRoadCommon] = None


@dataclass
class FairyRoadDirectoryLoadResult:
    directory: Path
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_roads_loaded: int = 0
    total_roads_failed: int = 0
    common_loaded: bool = False
    file_results: list[FairyRoadFileLoadResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    all_roads: list[FairyRoadDefinition] = field(default_factory=list)
    common: Optional[FairyRoadCommon] = None


# =============================================================================
# LOADER
# =============================================================================

class FairyRoadDataLoader:
    """Loads fairy road definitions and common tables from JSON files."""

    def load_directory(
        self,
        directory: Path,
        recursive: bool = False,
        pattern: str = "*.json",
    ) -> FairyRoadDirectoryLoadResult:
        result = FairyRoadDirectoryLoadResult(directory=directory)

        if not directory.exists():
            result.errors.append(f"Directory not found: {directory}")
            return result

        files = list(directory.rglob(pattern) if recursive else directory.glob(pattern))
        result.files_processed = len(files)

        for f in sorted(files):
            fr = self.load_file(f)
            result.file_results.append(fr)
            if fr.success:
                result.files_successful += 1
            else:
                result.files_failed += 1

            result.total_roads_loaded += fr.roads_loaded
            result.total_roads_failed += fr.roads_failed
            result.all_roads.extend(fr.loaded_roads)

            # Keep the first common loaded (or prefer exact filename match)
            if fr.loaded_common and (not result.common or f.name == "fairy_roads_common.json"):
                result.common = fr.loaded_common
                result.common_loaded = True

        return result

    def load_file(self, file_path: Path) -> FairyRoadFileLoadResult:
        result = FairyRoadFileLoadResult(file_path=file_path, success=False)

        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            result.errors.append(f"Failed to read JSON: {e}")
            return result

        # Wrapper format: {"_metadata": {...}, "items": [...]}
        if isinstance(raw, dict) and "items" in raw and isinstance(raw["items"], list):
            result.metadata = self._parse_metadata(raw.get("_metadata"))
            items = raw["items"]
            for item in items:
                self._parse_item(item, result)
        else:
            self._parse_item(raw, result)

        # Determine success: common-only file is OK
        if result.common_loaded or result.roads_loaded > 0:
            result.success = True
        return result

    # ----- parsing helpers -----

    def _parse_metadata(self, meta: Any) -> Optional[FairyRoadFileMetadata]:
        if not isinstance(meta, dict):
            return None
        return FairyRoadFileMetadata(
            source_file=str(meta.get("source_file", "")),
            pages=list(meta.get("pages", []) or []),
            content_type=str(meta.get("content_type", "")),
            item_count=int(meta.get("item_count", 0) or 0),
            note=str(meta.get("note", "")),
        )

    def _parse_item(self, obj: Any, result: FairyRoadFileLoadResult) -> None:
        if not isinstance(obj, dict):
            result.roads_failed += 1
            result.errors.append("Top-level item is not an object")
            return

        ctype = str(obj.get("content_type", "")).strip().lower()
        if ctype == "fairy_roads_common":
            try:
                result.loaded_common = self._parse_common(obj)
                result.common_loaded = True
            except Exception as e:
                result.errors.append(f"Failed to parse common tables: {e}")
            return

        # Road definition
        if ctype and ctype != "fairy_road":
            # Not a fairy road file; ignore quietly (helps mixed-content directories)
            return

        try:
            road = self._parse_road(obj)
            result.loaded_roads.append(road)
            result.roads_loaded += 1
        except Exception as e:
            result.roads_failed += 1
            result.errors.append(f"Failed to parse fairy road: {e}")

    def _parse_road(self, obj: dict[str, Any]) -> FairyRoadDefinition:
        road_id = str(obj.get("id") or obj.get("road_id") or "").strip()
        name = str(obj.get("name") or "").strip()
        if not road_id or not name:
            raise ValueError("Missing required fields: id/name")

        length = obj.get("length_miles")
        if length is None:
            raise ValueError("Missing required field: length_miles")
        length_miles = float(length)

        doors_raw = obj.get("doors") or []
        doors: list[FairyRoadDoor] = []
        for d in doors_raw:
            if not isinstance(d, dict):
                continue
            hex_id = str(d.get("hex_id", "")).strip()
            dname = str(d.get("name", "")).strip()
            if not hex_id or not dname:
                raise ValueError(f"Door missing hex_id/name on road={road_id}")
            doors.append(
                FairyRoadDoor(
                    hex_id=hex_id,
                    name=dname,
                    direction=str(d.get("direction", "endpoint")),
                    notes=str(d.get("notes", "")),
                )
            )

        side_roads_raw = obj.get("side_roads") or []
        side_roads: list[FairyRoadSideRoad] = []
        for sr in side_roads_raw:
            if not isinstance(sr, dict):
                continue
            side_roads.append(
                FairyRoadSideRoad(
                    name=str(sr.get("name", "")).strip(),
                    requires_invitation=bool(sr.get("requires_invitation", True)),
                    domain_id=(str(sr.get("domain_id")).strip() if sr.get("domain_id") else None),
                )
            )

        # Location table
        tables = obj.get("tables") or {}
        locations_obj = None
        if isinstance(tables, dict):
            locations_obj = tables.get("locations_d8") or tables.get("locations") or tables.get("location_table")

        locations = self._parse_location_table(locations_obj)

        return FairyRoadDefinition(
            road_id=road_id,
            name=name,
            length_miles=length_miles,
            doors=doors,
            side_roads=side_roads,
            atmosphere=str(obj.get("atmosphere", "")),
            special_rules=list(obj.get("special_rules", []) or []),
            locations=locations,
            common_tables_ref=str(obj.get("common_tables_ref", "fairy_roads_common.json")),
            notes=str(obj.get("notes", "")),
        )

    def _parse_location_table(self, obj: Any) -> FairyRoadLocationTable:
        if not isinstance(obj, dict):
            # allow missing tables for MVP
            return FairyRoadLocationTable(die="1d8", entries=[])

        die = str(obj.get("die", "1d8"))
        entries_raw = obj.get("entries") or []
        entries: list[FairyRoadLocationEntry] = []

        for e in entries_raw:
            if not isinstance(e, dict):
                continue
            roll = int(e.get("roll"))
            summary = str(e.get("summary", "")).strip()
            if not summary:
                summary = str(e.get("title", "")).strip()
            effects: list[FairyRoadEffect] = []
            for eff in (e.get("effects") or []):
                if not isinstance(eff, dict):
                    continue
                etype = str(eff.get("type", "")).strip()
                if not etype:
                    continue
                data = {k: v for k, v in eff.items() if k != "type"}
                effects.append(FairyRoadEffect(type=etype, data=data))
            tags = list(e.get("tags", []) or [])
            entries.append(FairyRoadLocationEntry(roll=roll, summary=summary, effects=effects, tags=tags))

        return FairyRoadLocationTable(die=die, entries=entries)

    def _parse_common(self, obj: dict[str, Any]) -> FairyRoadCommon:
        tables = obj.get("tables") or {}
        rules = obj.get("rules") or {}

        # Encounter table
        enc_obj = tables.get("fairy_road_encounters_d20") or {}
        enc_die = str(enc_obj.get("die", "1d20"))
        enc_entries_raw = enc_obj.get("entries") or []
        enc_entries: list[FairyRoadEncounterEntry] = []
        for e in enc_entries_raw:
            if not isinstance(e, dict):
                continue
            enc_entries.append(
                FairyRoadEncounterEntry(
                    roll=int(e.get("roll")),
                    name=str(e.get("name", "")).strip(),
                    count=str(e.get("count", "1")),
                    notes=str(e.get("notes", "")),
                )
            )

        encounter_table = FairyRoadEncounterTable(die=enc_die, entries=enc_entries)

        # Time passed table
        tp_obj = tables.get("time_passed_in_mortal_world_2d6") or {}
        tp_die = str(tp_obj.get("die", "2d6"))
        tp_entries_raw = tp_obj.get("entries") or []
        tp_entries: list[TimePassedEntry] = []
        for e in tp_entries_raw:
            if not isinstance(e, dict):
                continue
            roll = e.get("roll")
            rr = e.get("roll_range")
            roll_range = None
            if isinstance(rr, list) and len(rr) == 2:
                roll_range = (int(rr[0]), int(rr[1]))
            tp_entries.append(
                TimePassedEntry(
                    time=str(e.get("time", "")).strip(),
                    roll=(int(roll) if roll is not None else None),
                    roll_range=roll_range,
                )
            )
        time_passed_table = TimePassedTable(die=tp_die, entries=tp_entries)

        return FairyRoadCommon(encounter_table=encounter_table, time_passed_table=time_passed_table, rules=dict(rules))


# =============================================================================
# CONVENIENCE FUNCTIONS (match spell_loader conventions)
# =============================================================================

def load_all_fairy_roads(
    fairy_road_directory: Optional[Path] = None,
) -> FairyRoadDirectoryLoadResult:
    """Load all fairy road JSON files from the default directory."""
    if fairy_road_directory is None:
        fairy_road_directory = Path(__file__).parent.parent.parent / "data" / "content" / "fairy_roads"

    loader = FairyRoadDataLoader()
    return loader.load_directory(fairy_road_directory)
