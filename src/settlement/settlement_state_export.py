"""
Settlement snapshot + event export.

Foundry-ready seam:
- snapshot: what exists right now (locations, known NPCs, rumors, etc.)
- events: what changed since last tick (for incremental UI updates)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SettlementEvent:
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "payload": self.payload}


@dataclass
class SettlementEventBuffer:
    _events: list[SettlementEvent] = field(default_factory=list)

    def emit(self, type: str, payload: dict[str, Any]) -> None:
        self._events.append(SettlementEvent(type=type, payload=payload))

    def flush(self) -> list[dict[str, Any]]:
        out = [e.to_dict() for e in self._events]
        self._events.clear()
        return out


def build_settlement_snapshot(active_settlement: dict[str, Any]) -> dict[str, Any]:
    """
    Return a pure-JSON snapshot suitable for CLI display now and Foundry visualization later.

    `active_settlement` should be a stable dict produced by SettlementEngine (no live objects).
    """
    return {
        "version": 1,
        "active_settlement": active_settlement,
    }
