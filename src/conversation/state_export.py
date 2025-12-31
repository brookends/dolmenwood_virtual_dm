"""
State + event export for UI/Foundry.

- public_state: safe snapshot suitable for UI
- events: event stream derived from RunLog (or other bus)

Keeping this separate prevents UI from reaching into internal state.
"""
from __future__ import annotations

from typing import Any, Optional

from src.main import VirtualDM
from src.observability.run_log import RunLog, LogEvent


def export_public_state(dm: VirtualDM) -> dict[str, Any]:
    """
    Return a versioned, UI-safe snapshot of the game.

    For now we return VirtualDM.get_full_state() directly.
    Later, filter out secrets, GM-only notes, and huge blobs.
    """
    state = dm.get_full_state()
    return {
        "schema_version": 1,
        "state": state,
    }


class EventStream:
    """
    Small wrapper around RunLog subscriptions so UIs can poll or subscribe.
    """
    def __init__(self) -> None:
        self._log = RunLog()
        self._buffer: list[dict[str, Any]] = []
        self._log.subscribe(self._on_event)

    def _on_event(self, event: LogEvent) -> None:
        self._buffer.append(event.to_dict())

    def drain(self) -> list[dict[str, Any]]:
        events = self._buffer[:]
        self._buffer.clear()
        return events

    def close(self) -> None:
        self._log.unsubscribe(self._on_event)
