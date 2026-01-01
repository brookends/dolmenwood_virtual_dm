"""Fairy road package.

This package currently contains content-layer models used by the loader/registry.
The travel engine will live alongside these models (e.g., `fairy_road_engine.py`).
"""

from .models import (
    FairyRoadCommon,
    FairyRoadDefinition,
    FairyRoadDoor,
    FairyRoadEffect,
    FairyRoadLocationEntry,
    FairyRoadLocationTable,
    FairyRoadSideRoad,
)

__all__ = [
    "FairyRoadCommon",
    "FairyRoadDefinition",
    "FairyRoadDoor",
    "FairyRoadEffect",
    "FairyRoadLocationEntry",
    "FairyRoadLocationTable",
    "FairyRoadSideRoad",
]
