"""
Fairy road loader for JSON-authored Dolmenwood fairy roads.

Loads JSON files from a directory (e.g. data/content/fairy_roads/) and returns
FairyRoadData records via a FairyRoadRegistry.

Format support:
- Single road per file (top-level road fields)
- Wrapper format: {"_metadata": {...}, "items": [ {road...}, ... ] }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.fairy_roads.fairy_road_models import FairyRoadData
from src.content_loader.fairy_road_registry import FairyRoadRegistry

logger = logging.getLogger(__name__)


@dataclass
class FairyRoadFileLoadResult:
    file_path: Path
    success: bool
    roads_loaded: int = 0
    roads_failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class FairyRoadDirectoryLoadResult:
    directory: Path
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_roads_loaded: int = 0
    total_roads_failed: int = 0
    file_results: list[FairyRoadFileLoadResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class FairyRoadLoader:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def load_registry(self, pattern: str = "*.json") -> FairyRoadRegistry:
        """Convenience wrapper returning only the registry."""
        reg, _ = self.load_registry_with_report(pattern=pattern)
        return reg

    def load_registry_with_report(
        self, pattern: str = "*.json"
    ) -> tuple[FairyRoadRegistry, FairyRoadDirectoryLoadResult]:
        registry = FairyRoadRegistry()
        report = FairyRoadDirectoryLoadResult(directory=self.base_dir)

        if not self.base_dir.exists():
            msg = f"Fairy road directory does not exist: {self.base_dir}"
            logger.warning(msg)
            report.errors.append(msg)
            return registry, report

        for path in sorted(self.base_dir.glob(pattern)):
            if not path.is_file():
                continue

            report.files_processed += 1
            fres = FairyRoadFileLoadResult(file_path=path, success=False)

            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                roads = self._extract_road_records(raw)

                for rec in roads:
                    try:
                        road = FairyRoadData.from_dict(rec if isinstance(rec, dict) else {})
                        if not road.road_id:
                            fres.roads_failed += 1
                            fres.errors.append("Missing road_id")
                            continue
                        registry.add(road, source_path=str(path))
                        fres.roads_loaded += 1
                    except Exception as e:
                        fres.roads_failed += 1
                        fres.errors.append(str(e))

                fres.success = fres.roads_failed == 0
            except Exception as e:
                logger.exception("Failed to load fairy road JSON %s: %s", path, e)
                fres.errors.append(str(e))
                fres.roads_failed += 1
                fres.success = False

            if fres.success:
                report.files_successful += 1
            else:
                report.files_failed += 1

            report.total_roads_loaded += fres.roads_loaded
            report.total_roads_failed += fres.roads_failed
            report.file_results.append(fres)

        return registry, report

    def _extract_road_records(self, raw: Any) -> list[dict[str, Any]]:
        """Extract road records from various JSON formats."""
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]

        if isinstance(raw, dict):
            # Wrapper format: {"_metadata": {...}, "items": [...]}
            if "items" in raw and isinstance(raw["items"], list):
                return [r for r in raw["items"] if isinstance(r, dict)]

            # Single road at top level
            if "road_id" in raw:
                return [raw]

            # Nested format: {"roads": [...]}
            if "roads" in raw and isinstance(raw["roads"], list):
                return [r for r in raw["roads"] if isinstance(r, dict)]

        return []
