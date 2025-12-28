"""
Item materialization system for generating random properties on template magic items.

When a hex contains a magic item with template properties (e.g., "roll for enchantment"),
this system generates and locks those random properties on first encounter.
"""

import logging
import random
from typing import Any, Optional

from src.data_models import Item

logger = logging.getLogger(__name__)


class ItemMaterializer:
    """
    Generates random properties for template magic items.

    Template items have is_materialized=False and specify a materialization_template
    that determines what properties need to be randomly generated.

    Materialization templates:
    - "magic_weapon": Roll for weapon enchantment, special power (25%), oddity (10%)
    - "magic_armour": Roll for armour enchantment, special power (25%), oddity (10%)
    - "magic_potion": Roll for potion type
    - "magic_scroll": Roll for spell scroll contents
    - "magic_ring": Roll for ring type and properties
    - "enchantment_only": Roll only for enchantment type (arcane/fairy/holy)
    - "full_random": Roll for category, then full details
    """

    # Enchantment types and their probabilities (d100)
    ENCHANTMENT_TYPES = [
        (1, 65, "arcane"),   # 65%
        (66, 90, "fairy"),   # 25%
        (91, 100, "holy"),   # 10%
    ]

    # Special power chance by category
    SPECIAL_POWER_CHANCES = {
        "weapon": 25,
        "armour": 25,
        "ring": 50,
        "wondrous": 75,
    }

    # Oddity chance by category
    ODDITY_CHANCES = {
        "weapon": 10,
        "armour": 10,
        "ring": 25,
        "wondrous": 50,
    }

    def __init__(self, treasure_manager: Optional[Any] = None):
        """
        Initialize the materializer.

        Args:
            treasure_manager: Optional TreasureTableManager for complex rolls
        """
        self.treasure_manager = treasure_manager

    def materialize(
        self,
        item: Item,
        materialized_cache: Optional[dict[str, dict]] = None,
    ) -> Item:
        """
        Materialize a template item by generating its random properties.

        If the item has already been materialized (cached), returns the cached
        version to ensure consistency across sessions.

        Args:
            item: The template item to materialize
            materialized_cache: Optional cache of previously materialized items
                               (keyed by unique_item_id)

        Returns:
            The materialized item with generated properties
        """
        if item.is_materialized:
            return item

        # Check cache first
        cache_key = item.unique_item_id or item.item_id
        if materialized_cache and cache_key in materialized_cache:
            cached = materialized_cache[cache_key]
            return self._apply_cached_properties(item, cached)

        # Generate new properties based on template
        template = item.materialization_template or "enchantment_only"
        properties = self._generate_properties(template, item.magic_item_category)

        # Apply properties to item
        materialized = self._apply_properties(item, properties)

        # Store in cache if available
        if materialized_cache is not None and cache_key:
            materialized_cache[cache_key] = properties

        return materialized

    def _generate_properties(
        self,
        template: str,
        category: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate random properties based on template.

        Args:
            template: The materialization template name
            category: Optional item category for category-specific rolls

        Returns:
            Dictionary of generated properties
        """
        properties: dict[str, Any] = {
            "is_materialized": True,
        }

        if template == "enchantment_only":
            properties["enchantment_type"] = self._roll_enchantment_type()

        elif template == "magic_weapon":
            properties["enchantment_type"] = self._roll_enchantment_type()
            if self._check_chance(self.SPECIAL_POWER_CHANCES.get("weapon", 25)):
                properties["special_powers"] = [self._generate_weapon_power()]
            if self._check_chance(self.ODDITY_CHANCES.get("weapon", 10)):
                properties["oddities"] = [self._generate_oddity()]

        elif template == "magic_armour":
            properties["enchantment_type"] = self._roll_enchantment_type()
            if self._check_chance(self.SPECIAL_POWER_CHANCES.get("armour", 25)):
                properties["special_powers"] = [self._generate_armour_power()]
            if self._check_chance(self.ODDITY_CHANCES.get("armour", 10)):
                properties["oddities"] = [self._generate_oddity()]

        elif template == "magic_ring":
            properties["enchantment_type"] = self._roll_enchantment_type()
            if self._check_chance(self.SPECIAL_POWER_CHANCES.get("ring", 50)):
                properties["special_powers"] = [self._generate_ring_power()]
            if self._check_chance(self.ODDITY_CHANCES.get("ring", 25)):
                properties["oddities"] = [self._generate_oddity()]

        elif template == "full_random":
            # Use treasure manager if available for full generation
            if self.treasure_manager:
                return self._generate_from_treasure_tables()
            else:
                properties["enchantment_type"] = self._roll_enchantment_type()

        return properties

    def _roll_enchantment_type(self) -> str:
        """Roll for enchantment type (arcane/fairy/holy)."""
        roll = random.randint(1, 100)
        for low, high, enchant_type in self.ENCHANTMENT_TYPES:
            if low <= roll <= high:
                return enchant_type
        return "arcane"

    def _check_chance(self, percent: int) -> bool:
        """Check if a percentage chance succeeds."""
        return random.randint(1, 100) <= percent

    def _generate_weapon_power(self) -> str:
        """Generate a random weapon special power."""
        # Simplified list - full implementation would use treasure tables
        powers = [
            "Glows faintly when enemies are near",
            "Bonus damage vs. undead",
            "Returns when thrown",
            "Grants +1 to initiative",
            "Inflicts bleeding wounds",
            "Ignores armour on critical hits",
            "Drains life from enemies",
            "Bursts into flame on command",
        ]
        return random.choice(powers)

    def _generate_armour_power(self) -> str:
        """Generate a random armour special power."""
        powers = [
            "Grants resistance to fire",
            "Muffles sound of movement",
            "Repairs itself over time",
            "Grants darkvision",
            "Reduces falling damage",
            "Grants immunity to poison",
            "Reflects minor spells",
            "Weighs nothing to the wearer",
        ]
        return random.choice(powers)

    def _generate_ring_power(self) -> str:
        """Generate a random ring special power."""
        powers = [
            "Grants invisibility for 1 turn per day",
            "Allows water breathing",
            "Provides feather fall",
            "Grants telepathy within 30 feet",
            "Stores one spell level",
            "Grants +1 to saving throws",
            "Allows spider climbing",
            "Provides warmth in cold environments",
        ]
        return random.choice(powers)

    def _generate_oddity(self) -> str:
        """Generate a random oddity/quirk."""
        oddities = [
            "Hums softly in moonlight",
            "Feels slightly warm to the touch",
            "Occasionally whispers in an unknown language",
            "Attracts small insects",
            "Leaves a faint trail of sparkles",
            "Smells of roses",
            "Casts no shadow",
            "Weighs more at night",
            "Changes color with the wearer's mood",
            "Tastes of copper if licked",
        ]
        return random.choice(oddities)

    def _generate_from_treasure_tables(self) -> dict[str, Any]:
        """Generate properties using the full treasure table system."""
        if not self.treasure_manager:
            return {"is_materialized": True}

        # Use the treasure manager's magic item generation
        from src.tables.table_types import MagicItemCategory

        items = self.treasure_manager._generate_magic_items(1)
        if items:
            generated = items[0]
            return {
                "is_materialized": True,
                "enchantment_type": generated.enchantment,
                "special_powers": generated.special_powers,
                "oddities": generated.oddities,
                "appearance": generated.appearance,
                "magic_item_category": (
                    generated.magic_item_category.value
                    if generated.magic_item_category
                    else None
                ),
            }

        return {"is_materialized": True}

    def _apply_properties(self, item: Item, properties: dict[str, Any]) -> Item:
        """Apply generated properties to an item."""
        # Create a copy with new properties
        return Item(
            item_id=item.item_id,
            name=item.name,
            weight=item.weight,
            quantity=item.quantity,
            equipped=item.equipped,
            charges=item.charges,
            light_source=item.light_source,
            light_remaining_turns=item.light_remaining_turns,
            item_type=item.item_type,
            slot_size=item.slot_size,
            is_container=item.is_container,
            is_unique=item.is_unique,
            unique_item_id=item.unique_item_id,
            source_hex=item.source_hex,
            source_poi=item.source_poi,
            description=item.description,
            value_gp=item.value_gp,
            magical=item.magical,
            cursed=item.cursed,
            identified=item.identified,
            # Apply generated properties
            enchantment_type=properties.get("enchantment_type", item.enchantment_type),
            special_powers=properties.get("special_powers", item.special_powers),
            oddities=properties.get("oddities", item.oddities),
            appearance=properties.get("appearance", item.appearance),
            magic_item_category=properties.get(
                "magic_item_category", item.magic_item_category
            ),
            is_materialized=True,
            materialization_template=None,  # Clear template after materialization
        )

    def _apply_cached_properties(
        self, item: Item, cached: dict[str, Any]
    ) -> Item:
        """Apply cached properties to restore a previously materialized item."""
        return self._apply_properties(item, cached)
