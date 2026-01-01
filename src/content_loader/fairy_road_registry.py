"""Fairy Road Registry for Dolmenwood Virtual DM.

Provides a centralized registry for fairy road lookup by:
- road id
- door hex id (which roads can be entered from a given hex)

This mirrors the patterns used by SpellRegistry and MonsterRegistry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.fairy_roads.models import FairyRoadCommon, FairyRoadDefinition, FairyRoadDoor

logger = logging.getLogger(__name__)

_fairy_road_registry: Optional["FairyRoadRegistry"] = None


@dataclass
class FairyRoadLookupResult:
    found: bool
    road: Optional[FairyRoadDefinition] = None
    error: str = ""


@dataclass
class FairyRoadListResult:
    roads: list[FairyRoadDefinition] = field(default_factory=list)
    count: int = 0


@dataclass(frozen=True)
class DoorRef:
    road_id: str
    road_name: str
    door: FairyRoadDoor


class FairyRoadRegistry:
    def __init__(self):
        self._roads_by_id: dict[str, FairyRoadDefinition] = {}
        self._doors_by_hex: dict[str, list[DoorRef]] = {}
        self._common: Optional[FairyRoadCommon] = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def road_count(self) -> int:
        return len(self._roads_by_id)

    @property
    def common(self) -> Optional[FairyRoadCommon]:
        return self._common

    def load_from_directory(self, fairy_road_directory: Optional[Path] = None) -> int:
        from src.content_loader.fairy_road_loader import load_all_fairy_roads

        result = load_all_fairy_roads(fairy_road_directory)
        if result.errors:
            for err in result.errors:
                logger.error(f"Fairy road loading error: {err}")

        self._common = result.common

        for road in result.all_roads:
            self.register(road)

        self._loaded = True
        logger.info(f"Loaded {self.road_count} fairy roads")
        return self.road_count

    def register(self, road: FairyRoadDefinition) -> None:
        self._roads_by_id[road.road_id] = road

        for door in road.doors:
            hex_id = door.hex_id
            refs = self._doors_by_hex.setdefault(hex_id, [])
            refs.append(DoorRef(road_id=road.road_id, road_name=road.name, door=door))

    def get_by_id(self, road_id: str) -> FairyRoadLookupResult:
        road = self._roads_by_id.get(road_id)
        if road:
            return FairyRoadLookupResult(found=True, road=road)
        return FairyRoadLookupResult(found=False, error=f"Fairy road not found: {road_id}")

    def list_roads(self) -> FairyRoadListResult:
        roads = list(self._roads_by_id.values())
        roads.sort(key=lambda r: r.name)
        return FairyRoadListResult(roads=roads, count=len(roads))

    def get_doors_at_hex(self, hex_id: str) -> list[DoorRef]:
        return list(self._doors_by_hex.get(hex_id, []))

    def get_door(self, hex_id: str, road_id: str) -> Optional[DoorRef]:
        """
        Get a specific door by hex ID and road ID.

        Args:
            hex_id: The hex containing the door
            road_id: The fairy road this door belongs to

        Returns:
            DoorRef if found, None otherwise
        """
        doors = self._doors_by_hex.get(hex_id, [])
        for door_ref in doors:
            if door_ref.road_id == road_id:
                return door_ref
        return None

    def get_door_by_name(self, door_name: str) -> Optional[DoorRef]:
        """
        Get a door by its name (searching all hexes).

        Args:
            door_name: The name of the door

        Returns:
            DoorRef if found, None otherwise
        """
        for hex_doors in self._doors_by_hex.values():
            for door_ref in hex_doors:
                if door_ref.door.name.lower() == door_name.lower():
                    return door_ref
        return None


def get_fairy_road_registry() -> FairyRoadRegistry:
    global _fairy_road_registry
    if _fairy_road_registry is None:
        _fairy_road_registry = FairyRoadRegistry()
    return _fairy_road_registry


def reset_fairy_road_registry() -> None:
    global _fairy_road_registry
    _fairy_road_registry = None
