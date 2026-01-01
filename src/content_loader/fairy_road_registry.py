"""
Fairy road registry for Dolmenwood.

Stores loaded fairy road data and provides lookup methods.
"""

from __future__ import annotations

from typing import Optional

from src.fairy_roads.fairy_road_models import FairyRoadData, FairyDoor


class FairyRoadRegistry:
    """
    Registry for fairy roads and their doors.

    Provides lookup by road ID, door ID, or hex ID (for doors).
    """

    def __init__(self) -> None:
        self._roads: dict[str, FairyRoadData] = {}
        self._doors: dict[str, FairyDoor] = {}
        self._doors_by_hex: dict[str, list[FairyDoor]] = {}
        self._source_paths: dict[str, str] = {}

    def add(self, road: FairyRoadData, source_path: str = "") -> None:
        """Add a fairy road to the registry."""
        self._roads[road.road_id] = road
        if source_path:
            self._source_paths[road.road_id] = source_path

        # Index all doors
        for door in road.doors:
            self._doors[door.door_id] = door
            if door.hex_id not in self._doors_by_hex:
                self._doors_by_hex[door.hex_id] = []
            self._doors_by_hex[door.hex_id].append(door)

    def get(self, road_id: str) -> Optional[FairyRoadData]:
        """Get a fairy road by ID."""
        return self._roads.get(road_id)

    def get_door(self, door_id: str) -> Optional[FairyDoor]:
        """Get a fairy door by ID."""
        return self._doors.get(door_id)

    def get_doors_in_hex(self, hex_id: str) -> list[FairyDoor]:
        """Get all fairy doors in a given hex."""
        return self._doors_by_hex.get(hex_id, [])

    def get_all_roads(self) -> list[FairyRoadData]:
        """Get all registered fairy roads."""
        return list(self._roads.values())

    def get_all_doors(self) -> list[FairyDoor]:
        """Get all registered fairy doors."""
        return list(self._doors.values())

    def has_road(self, road_id: str) -> bool:
        """Check if a road is registered."""
        return road_id in self._roads

    def has_door(self, door_id: str) -> bool:
        """Check if a door is registered."""
        return door_id in self._doors

    def hex_has_doors(self, hex_id: str) -> bool:
        """Check if a hex has any fairy doors."""
        return hex_id in self._doors_by_hex and len(self._doors_by_hex[hex_id]) > 0

    def get_source_path(self, road_id: str) -> Optional[str]:
        """Get the source file path for a road."""
        return self._source_paths.get(road_id)

    def count(self) -> int:
        """Get the number of registered roads."""
        return len(self._roads)

    def door_count(self) -> int:
        """Get the number of registered doors."""
        return len(self._doors)

    def clear(self) -> None:
        """Clear all registered roads and doors."""
        self._roads.clear()
        self._doors.clear()
        self._doors_by_hex.clear()
        self._source_paths.clear()

    def get_connected_doors(self, road_id: str) -> list[FairyDoor]:
        """Get all doors connected to a specific road."""
        road = self._roads.get(road_id)
        if not road:
            return []
        return road.doors


# Singleton instance
_registry: Optional[FairyRoadRegistry] = None


def get_fairy_road_registry() -> FairyRoadRegistry:
    """Get the global fairy road registry instance."""
    global _registry
    if _registry is None:
        _registry = FairyRoadRegistry()
    return _registry


def reset_fairy_road_registry() -> None:
    """Reset the global fairy road registry (for testing)."""
    global _registry
    _registry = None
