"""
Settlement loader for JSON-authored Dolmenwood settlements.

Loads JSON files from a directory (e.g. data/content/settlements/) and returns
SettlementData records via a SettlementRegistry.

This loader is intentionally lightweight:
- parsing + minimal normalization happens here (via SettlementData.from_dict)
- gameplay logic stays in SettlementEngine

Format support:
- Single settlement per file (top-level settlement fields)
- Wrapper format: {"_metadata": {...}, "items": [ {settlement...}, ... ] }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from src.settlement.settlement_content_models import SettlementData
from src.settlement.settlement_registry import SettlementRegistry

logger = logging.getLogger(__name__)


@dataclass
class SettlementFileLoadResult:
    file_path: Path
    success: bool
    settlements_loaded: int = 0
    settlements_failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class SettlementDirectoryLoadResult:
    directory: Path
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_settlements_loaded: int = 0
    total_settlements_failed: int = 0
    file_results: list[SettlementFileLoadResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SettlementLoader:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def load_registry(self, pattern: str = "*.json") -> SettlementRegistry:
        """Convenience wrapper returning only the registry."""
        reg, _ = self.load_registry_with_report(pattern=pattern)
        return reg

    def load_registry_with_report(self, pattern: str = "*.json") -> tuple[SettlementRegistry, SettlementDirectoryLoadResult]:
        registry = SettlementRegistry()
        report = SettlementDirectoryLoadResult(directory=self.base_dir)

        if not self.base_dir.exists():
            msg = f"Settlement directory does not exist: {self.base_dir}"
            logger.warning(msg)
            report.errors.append(msg)
            return registry, report

        for path in sorted(self.base_dir.glob(pattern)):
            if not path.is_file():
                continue

            report.files_processed += 1
            fres = SettlementFileLoadResult(file_path=path, success=False)

            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                settlements = self._extract_settlement_records(raw)

                for rec in settlements:
                    try:
                        s = SettlementData.from_dict(rec if isinstance(rec, dict) else {})
                        if not s.settlement_id:
                            fres.settlements_failed += 1
                            fres.errors.append("Missing settlement_id")
                            continue
                        registry.add(s, source_path=str(path))
                        fres.settlements_loaded += 1
                    except Exception as e:
                        fres.settlements_failed += 1
                        fres.errors.append(str(e))

                fres.success = fres.settlements_failed == 0
            except Exception as e:
                logger.exception("Failed to load settlement JSON %s: %s", path, e)
                fres.errors.append(str(e))
                fres.settlements_failed += 1
                fres.success = False

            report.file_results.append(fres)
            if fres.success:
                report.files_successful += 1
            else:
                report.files_failed += 1

            report.total_settlements_loaded += fres.settlements_loaded
            report.total_settlements_failed += fres.settlements_failed

        return registry, report

    def _extract_settlement_records(self, raw: Any) -> list[dict[str, Any]]:
        """Return a list of dict records representing settlements."""
        if isinstance(raw, dict):
            # Wrapper format used by other loaders in this repo (e.g. spells)
            items = raw.get("items")
            if isinstance(items, list) and items:
                # Merge file-level metadata into each record (so downstream can access it if desired)
                md = raw.get("_metadata") if isinstance(raw.get("_metadata"), dict) else {}
                out = []
                for it in items:
                    if isinstance(it, dict):
                        rec = dict(it)
                        if md and "_metadata" not in rec:
                            rec["_metadata"] = md
                        out.append(rec)
                return out

            # Single settlement per file
            return [raw]

        # Unknown format
        return []
