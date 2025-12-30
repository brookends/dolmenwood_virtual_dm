"""
Observability and replay system for the Dolmenwood Virtual DM.

Provides comprehensive logging of all game events (rolls, transitions,
table lookups, time changes) and supports deterministic replay mode.
"""

from src.observability.run_log import (
    RunLog,
    LogEvent,
    EventType,
    RollEvent,
    TransitionEvent,
    TableLookupEvent,
    TimeStepEvent,
    get_run_log,
    reset_run_log,
)
from src.observability.replay import ReplaySession, ReplayMode

__all__ = [
    "RunLog",
    "LogEvent",
    "EventType",
    "RollEvent",
    "TransitionEvent",
    "TableLookupEvent",
    "TimeStepEvent",
    "get_run_log",
    "reset_run_log",
    "ReplaySession",
    "ReplayMode",
]
