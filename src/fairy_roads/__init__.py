"""Fairy roads travel engine module for Dolmenwood."""

from src.fairy_roads.fairy_road_models import (
    FairyRoadCheckResult,
    StrayFromPathResult,
    FairyDoor,
    FairyRoadEncounterEntry,
    FairyRoadLocationEntry,
    FairyRoadEncounterTable,
    FairyRoadData,
    FairyRoadTravelState,
    FairyRoadCheckOutcome,
    StrayFromPathOutcome,
)
from src.fairy_roads.fairy_road_engine import (
    FairyRoadEngine,
    FairyRoadPhase,
    FairyRoadTravelResult,
    FairyRoadEntryResult,
    FairyRoadExitResult,
    get_fairy_road_engine,
    reset_fairy_road_engine,
)

__all__ = [
    # Enums
    "FairyRoadCheckResult",
    "StrayFromPathResult",
    "FairyRoadPhase",
    # Content models
    "FairyDoor",
    "FairyRoadEncounterEntry",
    "FairyRoadLocationEntry",
    "FairyRoadEncounterTable",
    "FairyRoadData",
    # Runtime state
    "FairyRoadTravelState",
    "FairyRoadCheckOutcome",
    "StrayFromPathOutcome",
    # Engine
    "FairyRoadEngine",
    "FairyRoadTravelResult",
    "FairyRoadEntryResult",
    "FairyRoadExitResult",
    "get_fairy_road_engine",
    "reset_fairy_road_engine",
]
