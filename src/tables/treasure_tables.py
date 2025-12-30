"""
Treasure tables for Dolmenwood.

Provides comprehensive treasure table management including:
- Main treasure tables (coins, riches, magic items)
- Gem, jewelry, and art object detail tables
- Magic item type and detail tables
- Full treasure generation with nested table rolls

NOTE: Table data is loaded from JSON files stored in SQLite/ChromaDB databases.
This module provides the structure for rolling against those tables,
but does NOT contain hardcoded table entries.

Treasure Generation Flow:
1. Roll chance (d100) to see if each component is present
2. Roll quantity dice to determine amount
3. Roll on detail tables for gems, art objects, and magic items
"""

from typing import Any, Optional

from src.data_models import DiceRoller
from src.tables.table_types import (
    TreasureType,
    CoinType,
    MagicItemCategory,
    TreasureTableContext,
    TreasureComponent,
    GeneratedTreasureItem,
    TreasureResult,
    RollTable,
    RollTableEntry,
    RollTableMetadata,
    RollTableType,
    RollResult,
)


class TreasureTableManager:
    """
    Manages treasure table lookups and generation for Dolmenwood.

    This manager loads tables from the database rather than containing
    hardcoded entries. Table data is stored as JSON files and loaded
    into SQLite/ChromaDB databases.

    Handles the treasure generation process:
    1. Roll chance (d100 percentage) for each component
    2. Roll quantity dice for present components
    3. Roll on detail tables for gems, art objects, magic items
    """

    def __init__(self, db_connection: Optional[Any] = None):
        """
        Initialize the treasure table manager.

        Args:
            db_connection: Optional database connection for loading tables.
                          If None, tables must be loaded manually.
        """
        self._db = db_connection

        # Cache of loaded tables (table_id -> RollTable)
        self._table_cache: dict[str, RollTable] = {}

        # Index of tables by category for quick lookup
        self._by_category: dict[str, list[str]] = {}

    # =========================================================================
    # TABLE LOADING FROM DATABASE
    # =========================================================================

    def load_table(self, table_id: str) -> Optional[RollTable]:
        """
        Load a table from the database by ID.

        Args:
            table_id: The unique identifier for the table.

        Returns:
            The loaded RollTable, or None if not found.
        """
        # Check cache first
        if table_id in self._table_cache:
            return self._table_cache[table_id]

        # Load from database if available
        if self._db is not None:
            table = self._load_table_from_db(table_id)
            if table:
                self._table_cache[table_id] = table
                return table

        return None

    def _load_table_from_db(self, table_id: str) -> Optional[RollTable]:
        """
        Load a table from the SQLite database.

        This method should be overridden or extended when database
        integration is implemented.
        """
        # TODO: Implement database loading when SQLite integration is ready
        # Example query:
        # SELECT metadata, entries FROM roll_tables WHERE table_id = ?
        return None

    def register_table(self, table: RollTable) -> None:
        """
        Register a table in the cache.

        Used for testing or manual table loading.
        """
        self._table_cache[table.table_id] = table
        category = table.metadata.category or "uncategorized"
        if category not in self._by_category:
            self._by_category[category] = []
        if table.table_id not in self._by_category[category]:
            self._by_category[category].append(table.table_id)

    def get_table(self, table_id: str) -> Optional[RollTable]:
        """
        Get a table by ID, loading from database if necessary.
        """
        return self.load_table(table_id)

    def clear_cache(self) -> None:
        """Clear the table cache."""
        self._table_cache.clear()
        self._by_category.clear()

    # =========================================================================
    # DICE ROLLING UTILITIES
    # =========================================================================

    def _roll_dice(self, notation: str) -> int:
        """
        Roll dice using standard notation (e.g., '2d6', '1d8+2').

        Args:
            notation: Dice notation string.

        Returns:
            The total rolled value.
        """
        if not notation:
            return 0

        if "d" not in notation.lower():
            return int(notation)

        modifier = 0
        if "+" in notation:
            dice_part, mod_part = notation.split("+")
            modifier = int(mod_part)
        elif "-" in notation:
            dice_part, mod_part = notation.split("-")
            modifier = -int(mod_part)
        else:
            dice_part = notation

        num_dice, die_size = dice_part.lower().split("d")
        num_dice = int(num_dice) if num_dice else 1
        die_size = int(die_size)

        return DiceRoller.roll(
            (
                f"{num_dice}d{die_size}+{modifier}"
                if modifier >= 0
                else f"{num_dice}d{die_size}{modifier}"
            ),
            "treasure quantity",
        ).total

    def _roll_d100(self) -> int:
        """Roll d100 (1-100)."""
        return DiceRoller.roll_percentile("treasure chance").total

    # =========================================================================
    # TABLE ROLLING
    # =========================================================================

    def roll_on_table(
        self, table_id: str, context: Optional[TreasureTableContext] = None
    ) -> Optional[RollResult]:
        """
        Roll on a table by ID.

        Args:
            table_id: The table to roll on.
            context: Optional context for the roll.

        Returns:
            RollResult with the outcome, or None if table not found.
        """
        table = self.get_table(table_id)
        if not table:
            return None

        roll_value, entry = table.roll()

        result = RollResult(
            table_id=table_id,
            table_name=table.name,
            roll=roll_value,
            entry=entry,
        )

        # Handle sub-table references
        if entry and entry.sub_tables:
            for sub_table_id in entry.sub_tables:
                sub_result = self.roll_on_table(sub_table_id, context)
                if sub_result:
                    result.sub_results.append(sub_result)

        return result

    # =========================================================================
    # TREASURE GENERATION
    # =========================================================================

    def generate_treasure(
        self, components: list[TreasureComponent], context: Optional[TreasureTableContext] = None
    ) -> TreasureResult:
        """
        Generate treasure from a list of components.

        Each component has a chance percentage and quantity dice.

        Args:
            components: List of treasure components to potentially generate.
            context: Optional context modifying generation.

        Returns:
            TreasureResult containing all generated items.
        """
        result = TreasureResult()
        if context:
            result.treasure_type_code = context.treasure_type_code

        for component in components:
            # Roll chance (d100 percentage)
            present = component.roll_present()
            key = f"{component.treasure_type.value}"
            if component.coin_type:
                key += f"_{component.coin_type.value}"
            result.component_rolls[key] = present

            if not present:
                continue

            # Roll quantity
            quantity = self._roll_dice(component.quantity_dice)
            if context:
                quantity += context.quantity_modifier
            quantity = max(1, quantity)

            # Generate based on type
            if component.treasure_type == TreasureType.COINS:
                item = self._generate_coins(component, quantity)
                result.coins.append(item)

            elif component.treasure_type == TreasureType.GEMS:
                items = self._generate_gems(quantity, context)
                result.gems.extend(items)

            elif component.treasure_type == TreasureType.JEWELRY:
                items = self._generate_jewelry(quantity, context)
                result.jewelry.extend(items)

            elif component.treasure_type == TreasureType.ART_OBJECT:
                items = self._generate_art_objects(quantity, context)
                result.art_objects.extend(items)

            elif component.treasure_type == TreasureType.MAGIC_ITEM:
                items = self._generate_magic_items(quantity, component.magic_item_category, context)
                result.magic_items.extend(items)

        return result

    def _generate_coins(self, component: TreasureComponent, quantity: int) -> GeneratedTreasureItem:
        """Generate a coin treasure item."""
        total = quantity * component.multiplier
        return GeneratedTreasureItem(
            treasure_type=TreasureType.COINS,
            coin_type=component.coin_type,
            coin_value=total,
            quantity=1,
        )

    def _generate_gems(
        self, quantity: int, context: Optional[TreasureTableContext] = None
    ) -> list[GeneratedTreasureItem]:
        """Generate gem treasure items."""
        items = []

        for _ in range(quantity):
            item = GeneratedTreasureItem(treasure_type=TreasureType.GEMS, quantity=1)

            # Roll gem value (from database table)
            gem_value_result = self.roll_on_table("gem_value", context)
            if gem_value_result and gem_value_result.entry:
                value = gem_value_result.entry.get_data("value_gp", 10)
                item.base_value_gp = value
                item.rolls["gem_value"] = gem_value_result.roll

            # Roll gem type (from database table)
            gem_type_result = self.roll_on_table("gem_type", context)
            if gem_type_result and gem_type_result.entry:
                item.item_name = gem_type_result.entry.result
                item.rolls["gem_type"] = gem_type_result.roll

            items.append(item)

        return items

    def _generate_jewelry(
        self, quantity: int, context: Optional[TreasureTableContext] = None
    ) -> list[GeneratedTreasureItem]:
        """Generate jewelry treasure items."""
        items = []

        for _ in range(quantity):
            item = GeneratedTreasureItem(treasure_type=TreasureType.JEWELRY, quantity=1)

            # Roll jewelry type
            jewelry_result = self.roll_on_table("jewelry", context)
            if jewelry_result and jewelry_result.entry:
                item.item_name = jewelry_result.entry.result
                item.base_value_gp = jewelry_result.entry.get_data("value_gp", 100)
                item.rolls["jewelry"] = jewelry_result.roll

            # Roll material
            material_result = self.roll_on_table("precious_material", context)
            if material_result and material_result.entry:
                item.material = material_result.entry.result
                item.rolls["material"] = material_result.roll

            # Roll embellishment (optional - 50% chance)
            if DiceRoller.percent_check(50, "embellishment chance"):
                embellishment_result = self.roll_on_table("embellishment", context)
                if embellishment_result and embellishment_result.entry:
                    item.embellishment = embellishment_result.entry.result
                    item.rolls["embellishment"] = embellishment_result.roll

            # Roll provenance (optional - 25% chance)
            if DiceRoller.percent_check(25, "special power chance"):
                provenance_result = self.roll_on_table("provenance", context)
                if provenance_result and provenance_result.entry:
                    item.provenance = provenance_result.entry.result
                    item.rolls["provenance"] = provenance_result.roll

            items.append(item)

        return items

    def _generate_art_objects(
        self, quantity: int, context: Optional[TreasureTableContext] = None
    ) -> list[GeneratedTreasureItem]:
        """Generate art object treasure items."""
        items = []

        for _ in range(quantity):
            item = GeneratedTreasureItem(treasure_type=TreasureType.ART_OBJECT, quantity=1)

            # Roll art object type
            art_result = self.roll_on_table("art_object", context)
            if art_result and art_result.entry:
                item.item_name = art_result.entry.result
                item.base_value_gp = art_result.entry.get_data("value_gp", 100)
                item.rolls["art_object"] = art_result.roll

            # Roll material
            material_result = self.roll_on_table("precious_material", context)
            if material_result and material_result.entry:
                item.material = material_result.entry.result
                item.rolls["material"] = material_result.roll

            # Roll embellishment (optional - 50% chance)
            if DiceRoller.percent_check(50, "embellishment chance"):
                embellishment_result = self.roll_on_table("embellishment", context)
                if embellishment_result and embellishment_result.entry:
                    item.embellishment = embellishment_result.entry.result
                    item.rolls["embellishment"] = embellishment_result.roll

            # Roll provenance (optional - 50% chance for art)
            if DiceRoller.percent_check(50, "embellishment chance"):
                provenance_result = self.roll_on_table("provenance", context)
                if provenance_result and provenance_result.entry:
                    item.provenance = provenance_result.entry.result
                    item.rolls["provenance"] = provenance_result.roll

            items.append(item)

        return items

    def _generate_magic_items(
        self,
        quantity: int,
        category: Optional[MagicItemCategory] = None,
        context: Optional[TreasureTableContext] = None,
    ) -> list[GeneratedTreasureItem]:
        """Generate magic item treasure items."""
        items = []

        for _ in range(quantity):
            item = GeneratedTreasureItem(treasure_type=TreasureType.MAGIC_ITEM, quantity=1)

            # Determine category if not specified
            if category:
                item.magic_item_category = category
            else:
                type_result = self.roll_on_table("magic_item_type", context)
                if type_result and type_result.entry:
                    cat_str = type_result.entry.get_data("category")
                    if cat_str:
                        try:
                            item.magic_item_category = MagicItemCategory(cat_str)
                        except ValueError:
                            pass
                    item.rolls["magic_item_type"] = type_result.roll

            # Generate details based on category
            if item.magic_item_category:
                self._generate_magic_item_details(item, context)

            items.append(item)

        return items

    def _generate_magic_item_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """
        Generate details for a magic item based on its category.

        Delegates to category-specific handlers that roll on the
        appropriate database tables.
        """
        category = item.magic_item_category
        if not category:
            return

        # Map categories to their generation methods
        category_handlers = {
            MagicItemCategory.ARMOUR: self._generate_armour_details,
            MagicItemCategory.WEAPON: self._generate_weapon_details,
            MagicItemCategory.POTION: self._generate_potion_details,
            MagicItemCategory.RING: self._generate_ring_details,
            MagicItemCategory.ROD: self._generate_rod_details,
            MagicItemCategory.STAFF: self._generate_staff_details,
            MagicItemCategory.WAND: self._generate_wand_details,
            MagicItemCategory.SPELL_BOOK: self._generate_spell_book_details,
            MagicItemCategory.SPELL_SCROLL: self._generate_spell_scroll_details,
            MagicItemCategory.MAGIC_GARMENT: self._generate_garment_details,
            MagicItemCategory.AMULET_TALISMAN: self._generate_amulet_details,
            MagicItemCategory.MAGIC_CRYSTAL: self._generate_crystal_details,
            MagicItemCategory.MAGIC_BALM_OIL: self._generate_balm_oil_details,
            MagicItemCategory.WONDROUS_ITEM: self._generate_wondrous_details,
        }

        handler = category_handlers.get(category)
        if handler:
            handler(item, context)

    def _generate_armour_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate armour magic item details from database tables."""
        # Roll armour type
        type_result = self.roll_on_table("armour_type", context)
        if type_result and type_result.entry:
            item.magic_item_name = type_result.entry.result
            item.rolls["armour_type"] = type_result.roll

        # Roll enchantment
        enchant_result = self.roll_on_table("armour_enchantment", context)
        if enchant_result and enchant_result.entry:
            item.enchantment = enchant_result.entry.result
            item.rolls["armour_enchantment"] = enchant_result.roll

        # 25% chance of special power
        if DiceRoller.percent_check(25, "special power chance"):
            power_result = self.roll_on_table("armour_special_power", context)
            if power_result and power_result.entry:
                item.special_powers.append(power_result.entry.result)
                item.rolls["armour_special_power"] = power_result.roll

        # 10% chance of oddity
        if DiceRoller.percent_check(10, "oddity chance"):
            oddity_result = self.roll_on_table("armour_oddity", context)
            if oddity_result and oddity_result.entry:
                item.oddities.append(oddity_result.entry.result)
                item.rolls["armour_oddity"] = oddity_result.roll

    def _generate_weapon_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate weapon magic item details from database tables."""
        # Roll weapon type
        type_result = self.roll_on_table("weapon_type", context)
        if type_result and type_result.entry:
            item.magic_item_name = type_result.entry.result
            item.rolls["weapon_type"] = type_result.roll

        # Roll enchantment
        enchant_result = self.roll_on_table("weapon_enchantment", context)
        if enchant_result and enchant_result.entry:
            item.enchantment = enchant_result.entry.result
            item.rolls["weapon_enchantment"] = enchant_result.roll

        # 25% chance of special power
        if DiceRoller.percent_check(25, "special power chance"):
            power_result = self.roll_on_table("weapon_special_power", context)
            if power_result and power_result.entry:
                item.special_powers.append(power_result.entry.result)
                item.rolls["weapon_special_power"] = power_result.roll

        # 10% chance of oddity
        if DiceRoller.percent_check(10, "oddity chance"):
            oddity_result = self.roll_on_table("weapon_oddity", context)
            if oddity_result and oddity_result.entry:
                item.oddities.append(oddity_result.entry.result)
                item.rolls["weapon_oddity"] = oddity_result.roll

    def _generate_potion_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate potion magic item details from database tables."""
        potion_result = self.roll_on_table("potion", context)
        if potion_result and potion_result.entry:
            item.magic_item_name = f"Potion of {potion_result.entry.result}"
            item.rolls["potion"] = potion_result.roll

    def _generate_ring_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate ring magic item details from database tables."""
        ring_result = self.roll_on_table("ring", context)
        if ring_result and ring_result.entry:
            item.magic_item_name = f"Ring of {ring_result.entry.result}"
            item.rolls["ring"] = ring_result.roll

        appearance_result = self.roll_on_table("ring_appearance", context)
        if appearance_result and appearance_result.entry:
            item.appearance = appearance_result.entry.result
            item.rolls["ring_appearance"] = appearance_result.roll

    def _generate_rod_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate rod magic item details from database tables."""
        rod_result = self.roll_on_table("rod", context)
        if rod_result and rod_result.entry:
            item.magic_item_name = f"Rod of {rod_result.entry.result}"
            item.rolls["rod"] = rod_result.roll

        appearance_result = self.roll_on_table("rod_appearance", context)
        if appearance_result and appearance_result.entry:
            item.appearance = appearance_result.entry.result
            item.rolls["rod_appearance"] = appearance_result.roll

        power_result = self.roll_on_table("rod_power", context)
        if power_result and power_result.entry:
            item.special_powers.append(power_result.entry.result)
            item.rolls["rod_power"] = power_result.roll

    def _generate_staff_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate staff magic item details from database tables."""
        staff_result = self.roll_on_table("staff", context)
        if staff_result and staff_result.entry:
            item.magic_item_name = f"Staff of {staff_result.entry.result}"
            item.rolls["staff"] = staff_result.roll

        appearance_result = self.roll_on_table("staff_appearance", context)
        if appearance_result and appearance_result.entry:
            item.appearance = appearance_result.entry.result
            item.rolls["staff_appearance"] = appearance_result.roll

        power_result = self.roll_on_table("staff_power", context)
        if power_result and power_result.entry:
            item.special_powers.append(power_result.entry.result)
            item.rolls["staff_power"] = power_result.roll

    def _generate_wand_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate wand magic item details from database tables."""
        wand_result = self.roll_on_table("wand", context)
        if wand_result and wand_result.entry:
            item.magic_item_name = f"Wand of {wand_result.entry.result}"
            item.rolls["wand"] = wand_result.roll

        appearance_result = self.roll_on_table("wand_appearance", context)
        if appearance_result and appearance_result.entry:
            item.appearance = appearance_result.entry.result
            item.rolls["wand_appearance"] = appearance_result.roll

        spell_result = self.roll_on_table("wand_spell", context)
        if spell_result and spell_result.entry:
            item.special_powers.append(spell_result.entry.result)
            item.rolls["wand_spell"] = spell_result.roll

    def _generate_spell_book_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate spell book magic item details from database tables."""
        book_result = self.roll_on_table("spell_book", context)
        if book_result and book_result.entry:
            item.magic_item_name = f"Spell Book ({book_result.entry.result})"
            item.rolls["spell_book"] = book_result.roll

        appearance_result = self.roll_on_table("spell_book_appearance", context)
        if appearance_result and appearance_result.entry:
            item.appearance = appearance_result.entry.result
            item.rolls["spell_book_appearance"] = appearance_result.roll

        language_result = self.roll_on_table("scroll_language", context)
        if language_result and language_result.entry:
            item.special_powers.append(f"Written in {language_result.entry.result}")
            item.rolls["language"] = language_result.roll

    def _generate_spell_scroll_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate spell scroll magic item details from database tables."""
        # Roll number of spells
        count_result = self.roll_on_table("spell_scroll_count", context)
        spell_count = 1
        if count_result and count_result.entry:
            count_dice = count_result.entry.dice_expressions.get("count", "1")
            spell_count = self._roll_dice(count_dice)
            item.rolls["spell_scroll_count"] = count_result.roll

        # Roll spell ranks for each spell
        spell_descriptions = []
        for i in range(spell_count):
            rank_result = self.roll_on_table("spell_scroll_rank", context)
            if rank_result and rank_result.entry:
                spell_descriptions.append(rank_result.entry.result)
                item.rolls[f"spell_rank_{i+1}"] = rank_result.roll

        item.magic_item_name = f"Spell Scroll ({', '.join(spell_descriptions)})"

        # Roll language
        language_result = self.roll_on_table("scroll_language", context)
        if language_result and language_result.entry:
            item.appearance = f"Written in {language_result.entry.result}"
            item.rolls["language"] = language_result.roll

    def _generate_garment_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate magic garment details from database tables."""
        garment_result = self.roll_on_table("magic_garment", context)
        if garment_result and garment_result.entry:
            item.magic_item_name = garment_result.entry.result
            item.rolls["magic_garment"] = garment_result.roll

    def _generate_amulet_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate amulet/talisman magic item details from database tables."""
        amulet_result = self.roll_on_table("amulet_talisman", context)
        if amulet_result and amulet_result.entry:
            item.magic_item_name = amulet_result.entry.result
            item.rolls["amulet_talisman"] = amulet_result.roll

        appearance_result = self.roll_on_table("amulet_appearance", context)
        if appearance_result and appearance_result.entry:
            item.appearance = appearance_result.entry.result
            item.rolls["amulet_appearance"] = appearance_result.roll

    def _generate_crystal_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate magic crystal details from database tables."""
        crystal_result = self.roll_on_table("magic_crystal", context)
        if crystal_result and crystal_result.entry:
            item.magic_item_name = crystal_result.entry.result
            item.rolls["magic_crystal"] = crystal_result.roll

    def _generate_balm_oil_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate magic balm/oil details from database tables."""
        balm_result = self.roll_on_table("magic_balm_oil", context)
        if balm_result and balm_result.entry:
            item.magic_item_name = balm_result.entry.result
            item.rolls["magic_balm_oil"] = balm_result.roll

    def _generate_wondrous_details(
        self, item: GeneratedTreasureItem, context: Optional[TreasureTableContext] = None
    ) -> None:
        """Generate wondrous item details from database tables."""
        wondrous_result = self.roll_on_table("wondrous_item", context)
        if wondrous_result and wondrous_result.entry:
            item.magic_item_name = wondrous_result.entry.result
            item.rolls["wondrous_item"] = wondrous_result.roll

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def list_tables_by_category(self, category: str) -> list[str]:
        """List all table IDs in a category."""
        return self._by_category.get(category, [])

    def list_all_categories(self) -> list[str]:
        """List all categories with registered tables."""
        return list(self._by_category.keys())

    def get_table_ids(self) -> list[str]:
        """Get all registered table IDs."""
        return list(self._table_cache.keys())


# Module-level singleton
_treasure_manager: Optional[TreasureTableManager] = None


def get_treasure_table_manager() -> TreasureTableManager:
    """Get the global TreasureTableManager instance."""
    global _treasure_manager
    if _treasure_manager is None:
        _treasure_manager = TreasureTableManager()
    return _treasure_manager
