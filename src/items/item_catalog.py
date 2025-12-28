"""
Item catalog loader for common items.

Loads item definitions from JSON files in data/content/items/.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from src.data_models import Item

logger = logging.getLogger(__name__)


class ItemCatalog:
    """
    Catalog of common items loaded from JSON files.

    The catalog is organized by category (weapons, armour, adventuring_gear, etc.)
    and provides methods to look up items by ID or search by properties.

    Directory structure:
        data/content/items/
            weapons/
                melee_weapons.json
                ranged_weapons.json
            armour/
                armour.json
                shields.json
            adventuring_gear/
                basic_equipment.json
                ...
    """

    def __init__(self, items_path: str = "data/content/items"):
        """
        Initialize the item catalog.

        Args:
            items_path: Path to the items directory
        """
        self.items_path = Path(items_path)
        self._items: dict[str, dict[str, Any]] = {}  # item_id -> item data
        self._categories: dict[str, list[str]] = {}  # category -> list of item_ids
        self._loaded = False

    def load(self) -> None:
        """Load all item JSON files from the catalog directory."""
        if not self.items_path.exists():
            logger.warning(f"Items directory not found: {self.items_path}")
            return

        # Recursively find all JSON files
        for json_file in self.items_path.rglob("*.json"):
            try:
                self._load_file(json_file)
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")

        self._loaded = True
        logger.info(
            f"Loaded {len(self._items)} items in {len(self._categories)} categories"
        )

    def _load_file(self, json_file: Path) -> None:
        """Load items from a single JSON file."""
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        category = data.get("category", "uncategorized")
        items = data.get("items", [])

        if category not in self._categories:
            self._categories[category] = []

        for item_data in items:
            item_id = item_data.get("item_id")
            if not item_id:
                logger.warning(f"Item without item_id in {json_file}")
                continue

            if item_id in self._items:
                logger.warning(f"Duplicate item_id '{item_id}' - overwriting")

            # Store the raw data
            self._items[item_id] = item_data
            self._categories[category].append(item_id)

    def get(self, item_id: str) -> Optional[dict[str, Any]]:
        """
        Get item data by ID.

        Args:
            item_id: The item identifier

        Returns:
            Item data dictionary or None if not found
        """
        if not self._loaded:
            self.load()
        return self._items.get(item_id)

    def get_item(
        self,
        item_id: str,
        quantity: int = 1,
        source_hex: Optional[str] = None,
        source_poi: Optional[str] = None,
    ) -> Optional[Item]:
        """
        Create an Item instance from the catalog.

        Args:
            item_id: The item identifier
            quantity: Number of items
            source_hex: Source hex ID
            source_poi: Source POI name

        Returns:
            Item instance or None if not found in catalog
        """
        item_data = self.get(item_id)
        if not item_data:
            return None

        # Normalize value (cost_sp -> value_gp)
        value_gp = item_data.get("value_gp")
        if value_gp is None and item_data.get("cost_sp"):
            value_gp = item_data.get("cost_sp") / 10.0

        # Normalize weight
        weight = item_data.get("weight") or item_data.get("weight_coins", 0)

        return Item(
            item_id=item_id,
            name=item_data.get("name", item_id),
            weight=weight,
            quantity=quantity,
            description=item_data.get("description"),
            value_gp=value_gp,
            item_type=item_data.get("item_type", ""),
            slot_size=item_data.get("slot_size", 1),
            is_container=item_data.get("is_container", False),
            source_hex=source_hex,
            source_poi=source_poi,
            magical=item_data.get("magical", False),
            # Handle light sources
            light_source=item_data.get("light_source"),
        )

    def get_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get all items in a category.

        Args:
            category: Category name (e.g., 'weapons', 'armour')

        Returns:
            List of item data dictionaries
        """
        if not self._loaded:
            self.load()

        item_ids = self._categories.get(category, [])
        return [self._items[item_id] for item_id in item_ids if item_id in self._items]

    def search(
        self,
        name_contains: Optional[str] = None,
        category: Optional[str] = None,
        max_cost_sp: Optional[float] = None,
        min_cost_sp: Optional[float] = None,
        item_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search for items matching criteria.

        Args:
            name_contains: Substring to match in item name (case-insensitive)
            category: Filter by category
            max_cost_sp: Maximum cost in silver pieces
            min_cost_sp: Minimum cost in silver pieces
            item_type: Filter by item type

        Returns:
            List of matching item data dictionaries
        """
        if not self._loaded:
            self.load()

        results = []
        for item_id, item_data in self._items.items():
            # Name filter
            if name_contains:
                name = item_data.get("name", "").lower()
                if name_contains.lower() not in name:
                    continue

            # Category filter
            if category:
                found_in_category = False
                for cat, ids in self._categories.items():
                    if cat == category and item_id in ids:
                        found_in_category = True
                        break
                if not found_in_category:
                    continue

            # Cost filters
            cost = item_data.get("cost_sp", 0)
            if max_cost_sp is not None and cost > max_cost_sp:
                continue
            if min_cost_sp is not None and cost < min_cost_sp:
                continue

            # Item type filter
            if item_type and item_data.get("item_type") != item_type:
                continue

            results.append(item_data)

        return results

    def list_categories(self) -> list[str]:
        """Get all available categories."""
        if not self._loaded:
            self.load()
        return list(self._categories.keys())

    def __contains__(self, item_id: str) -> bool:
        """Check if an item exists in the catalog."""
        if not self._loaded:
            self.load()
        return item_id in self._items

    def __len__(self) -> int:
        """Get total number of items in catalog."""
        if not self._loaded:
            self.load()
        return len(self._items)
