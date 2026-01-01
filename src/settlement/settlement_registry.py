"""
In-memory settlement registry.

This is the primary lookup structure used by SettlementEngine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.settlement.settlement_content_models import SettlementData


@dataclass
class SettlementRecord:
    settlement: SettlementData
    source_path: str = ""


class SettlementRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, SettlementRecord] = {}
        self._by_hex: dict[str, str] = {}  # hex_id -> settlement_id

    def add(self, settlement: SettlementData, source_path: str = "") -> None:
        rec = SettlementRecord(settlement=settlement, source_path=source_path)
        self._by_id[settlement.settlement_id] = rec
        if settlement.hex_id:
            self._by_hex[settlement.hex_id] = settlement.settlement_id

    def get(self, settlement_id: str) -> Optional[SettlementData]:
        rec = self._by_id.get(settlement_id)
        return rec.settlement if rec else None

    def get_source_path(self, settlement_id: str) -> str:
        rec = self._by_id.get(settlement_id)
        return rec.source_path if rec else ""

    def find_by_hex(self, hex_id: str) -> Optional[SettlementData]:
        sid = self._by_hex.get(hex_id)
        return self.get(sid) if sid else None

    def list_ids(self) -> list[str]:
        return sorted(self._by_id.keys())
