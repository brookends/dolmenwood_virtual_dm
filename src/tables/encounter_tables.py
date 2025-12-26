"""
Encounter tables for Dolmenwood.

Provides comprehensive encounter table management including:
- Common encounter type and encounter tables
- Regional encounter tables
- Settlement encounter tables (day/night variants)
- Fairy Road encounter tables
- Unseason encounter tables (Chame, Vague)
- Integration with hex-specific encounter tables

NOTE: Table data is loaded from JSON files stored in SQLite/ChromaDB databases.
This module provides the structure for loading and rolling against those tables,
but does NOT contain hardcoded table entries.

Table Selection Logic:
- Fairy Road: EXCLUSIVE - only fairy road table is used
- Settlement: EXCLUSIVE - only settlement day/night tables are used
- Wilderness: EQUAL PROBABILITY - randomly selects from all eligible tables
  (common, hex-specific, regional, seasonal) with equal probability
"""

from typing import Any, Optional
import random

from src.tables.table_types import (
    DieType,
    EncounterLocationType,
    EncounterTimeOfDay,
    EncounterSeason,
    EncounterResultType,
    EncounterTableCategory,
    NestedTableCondition,
    NestedTableConditionType,
    NestedTableSelector,
    DolmenwoodRegion,
    DolmenwoodSettlement,
    EncounterTableContext,
    EncounterEntry,
    EncounterTable,
    EncounterResult,
    RollTable,
    RollTableEntry,
    RollTableMetadata,
    RollTableType,
    RollResult,
)


class EncounterTableManager:
    """
    Manages all encounter tables for Dolmenwood.

    This manager loads tables from the database rather than containing
    hardcoded entries. Table data is stored as JSON files and loaded
    into SQLite/ChromaDB databases.

    Table Selection:
    - Fairy Road encounters: EXCLUSIVE - only uses fairy road table
    - Settlement encounters: EXCLUSIVE - only uses settlement day/night tables
    - Wilderness encounters: EQUAL PROBABILITY selection from eligible tables:
      - Common encounter tables (always eligible)
      - Hex-specific tables (if in that hex)
      - Regional tables (if in that region)
      - Seasonal tables (if during that season, including unseasons)

    All registered tables of eligible categories have equal chance of being
    selected for wilderness encounters.
    """

    def __init__(self, db_connection: Optional[Any] = None):
        """
        Initialize the encounter table manager.

        Args:
            db_connection: Optional database connection for loading tables.
                          If None, tables must be loaded manually.
        """
        self._db = db_connection

        # Cache of loaded tables (table_id -> EncounterTable)
        self._tables: dict[str, EncounterTable] = {}

        # Indexes by category for quick lookup
        self._by_category: dict[EncounterTableCategory, list[str]] = {
            cat: [] for cat in EncounterTableCategory
        }
        self._by_settlement: dict[DolmenwoodSettlement, dict[EncounterTimeOfDay, str]] = {}
        self._by_region: dict[DolmenwoodRegion, str] = {}
        self._by_season: dict[EncounterSeason, str] = {}
        self._by_hex: dict[str, list[str]] = {}  # hex_id -> list of table_ids

    # =========================================================================
    # TABLE LOADING FROM DATABASE
    # =========================================================================

    def load_table(self, table_id: str) -> Optional[EncounterTable]:
        """
        Load a table from the database by ID.

        Args:
            table_id: The unique identifier for the table.

        Returns:
            The loaded EncounterTable, or None if not found.
        """
        # Check cache first
        if table_id in self._tables:
            return self._tables[table_id]

        # Load from database if available
        if self._db is not None:
            table = self._load_table_from_db(table_id)
            if table:
                self.register_table(table)
                return table

        return None

    def _load_table_from_db(self, table_id: str) -> Optional[EncounterTable]:
        """
        Load a table from the SQLite database.

        This method should be overridden or extended when database
        integration is implemented.
        """
        # TODO: Implement database loading when SQLite integration is ready
        # Example query:
        # SELECT metadata, entries FROM roll_tables WHERE table_id = ?
        return None

    def load_tables_for_context(self, context: EncounterTableContext) -> None:
        """
        Pre-load all tables that might be needed for a given context.

        This ensures all relevant tables are cached before rolling.
        """
        if self._db is None:
            return

        # Load tables based on context
        # TODO: Implement batch loading from database
        pass

    # =========================================================================
    # TABLE REGISTRATION
    # =========================================================================

    def register_table(self, table: EncounterTable) -> None:
        """
        Register an encounter table in the cache.

        Used for testing or manual table loading.
        """
        self._tables[table.table_id] = table

        # Index by category
        if table.table_id not in self._by_category[table.category]:
            self._by_category[table.category].append(table.table_id)

        # Index by settlement
        if table.settlement is not None:
            if table.settlement not in self._by_settlement:
                self._by_settlement[table.settlement] = {}
            self._by_settlement[table.settlement][table.time_of_day] = table.table_id

        # Index by region
        if table.region is not None:
            self._by_region[table.region] = table.table_id

        # Index by season (for seasonal tables including unseasons)
        if table.category == EncounterTableCategory.SEASONAL:
            self._by_season[table.season] = table.table_id

        # Index by hex
        if table.hex_id is not None:
            if table.hex_id not in self._by_hex:
                self._by_hex[table.hex_id] = []
            if table.table_id not in self._by_hex[table.hex_id]:
                self._by_hex[table.hex_id].append(table.table_id)

    def register_hex_table(self, table: EncounterTable) -> None:
        """Register a hex-specific encounter table."""
        table.category = EncounterTableCategory.HEX_SPECIFIC
        self.register_table(table)

    def get_table(self, table_id: str) -> Optional[EncounterTable]:
        """Get a table by ID, loading from database if necessary."""
        return self.load_table(table_id)

    def clear_cache(self) -> None:
        """Clear the table cache and indexes."""
        self._tables.clear()
        self._by_category = {cat: [] for cat in EncounterTableCategory}
        self._by_settlement.clear()
        self._by_region.clear()
        self._by_season.clear()
        self._by_hex.clear()

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

        # Handle plain numbers (e.g., "1" or "5")
        if 'd' not in notation.lower():
            return int(notation)

        modifier = 0
        if '+' in notation:
            dice_part, mod_part = notation.split('+')
            modifier = int(mod_part)
        elif '-' in notation:
            dice_part, mod_part = notation.split('-')
            modifier = -int(mod_part)
        else:
            dice_part = notation

        num_dice, die_size = dice_part.lower().split('d')
        num_dice = int(num_dice) if num_dice else 1
        die_size = int(die_size)

        return sum(random.randint(1, die_size) for _ in range(num_dice)) + modifier

    # =========================================================================
    # ENCOUNTER RESOLUTION
    # =========================================================================

    def roll_encounter(
        self,
        context: EncounterTableContext,
        hex_tables: Optional[dict[str, EncounterTable]] = None
    ) -> Optional[EncounterResult]:
        """
        Roll for an encounter based on context.

        Selection logic:
        - Fairy Road: EXCLUSIVE - only uses fairy road table
        - Settlement: EXCLUSIVE - only uses settlement day/night tables
        - Wilderness: Random equal-probability selection from eligible tables

        Args:
            context: Current encounter context
            hex_tables: Optional hex-specific tables (from hex data)

        Returns:
            EncounterResult or None if no table matches
        """
        table = self._select_table(context, hex_tables)
        if table is None:
            return None

        roll, entry = table.roll(context)

        # Roll number appearing if specified
        num_appearing = None
        if entry.number_appearing:
            num_appearing = self._roll_dice(entry.number_appearing)

        result = EncounterResult(
            table_id=table.table_id,
            table_name=table.name,
            roll=roll,
            entry=entry,
            location_type=context.location_type,
            time_of_day=context.time_of_day,
            season=context.season,
            description=entry.result,
            monsters=entry.monster_refs[:] if entry.monster_refs else [],
            npcs=entry.npc_refs[:] if entry.npc_refs else [],
            number_appearing_rolled=num_appearing,
        )

        # Handle sub-table references
        if entry.regional_table and context.region:
            regional_result = self._roll_regional(context)
            if regional_result:
                result.sub_result = regional_result

        elif entry.sub_table:
            sub_table = self._tables.get(entry.sub_table)
            if sub_table:
                sub_roll, sub_entry = sub_table.roll(context)
                result.sub_result = EncounterResult(
                    table_id=sub_table.table_id,
                    table_name=sub_table.name,
                    roll=sub_roll,
                    entry=sub_entry,
                    location_type=context.location_type,
                    time_of_day=context.time_of_day,
                    season=context.season,
                    description=sub_entry.result,
                )

        return result

    def _select_table(
        self,
        context: EncounterTableContext,
        hex_tables: Optional[dict[str, EncounterTable]] = None
    ) -> Optional[EncounterTable]:
        """
        Select the appropriate encounter table based on context.

        - Fairy Road: EXCLUSIVE - only fairy road table
        - Settlement: EXCLUSIVE - only settlement tables
        - Wilderness: Random equal-probability from all eligible tables
        """
        # EXCLUSIVE: Fairy Road - only use fairy road table
        if context.on_fairy_road:
            fairy_tables = self._by_category[EncounterTableCategory.FAIRY_ROAD]
            if fairy_tables:
                return self._tables.get(fairy_tables[0])
            return None

        # EXCLUSIVE: Settlement - only use settlement tables
        if context.location_type == EncounterLocationType.SETTLEMENT and context.settlement:
            settlement_tables = self._by_settlement.get(context.settlement, {})
            # Try specific time first
            if context.time_of_day in settlement_tables:
                return self._tables.get(settlement_tables[context.time_of_day])
            # Try day/night based on current time
            if context.time_of_day in [EncounterTimeOfDay.DAY, EncounterTimeOfDay.DAWN]:
                if EncounterTimeOfDay.DAY in settlement_tables:
                    return self._tables.get(settlement_tables[EncounterTimeOfDay.DAY])
            elif context.time_of_day in [EncounterTimeOfDay.NIGHT, EncounterTimeOfDay.DUSK]:
                if EncounterTimeOfDay.NIGHT in settlement_tables:
                    return self._tables.get(settlement_tables[EncounterTimeOfDay.NIGHT])
            return None

        # WILDERNESS: Equal probability selection from eligible tables
        eligible_tables = self._get_eligible_wilderness_tables(context, hex_tables)

        if not eligible_tables:
            return None

        # Random selection with equal probability
        selected_id = random.choice(eligible_tables)
        return self._tables.get(selected_id)

    def _get_eligible_wilderness_tables(
        self,
        context: EncounterTableContext,
        hex_tables: Optional[dict[str, EncounterTable]] = None
    ) -> list[str]:
        """
        Get all wilderness tables eligible for the given context.

        Eligible tables include:
        - Common encounter tables (always eligible)
        - Hex-specific tables (if in that hex)
        - Regional tables (if in that region)
        - Seasonal tables (if during that season)
        """
        eligible: list[str] = []

        # Common tables are always eligible
        eligible.extend(self._by_category[EncounterTableCategory.COMMON])

        # Hex-specific tables from registered tables
        if context.hex_id and context.hex_id in self._by_hex:
            eligible.extend(self._by_hex[context.hex_id])

        # Hex-specific tables from provided hex_tables
        if hex_tables and context.hex_id:
            for table in hex_tables.values():
                if table.is_eligible_for_context(context):
                    # Add to tables dict if not already there
                    if table.table_id not in self._tables:
                        self._tables[table.table_id] = table
                    eligible.append(table.table_id)

        # Regional tables for current region
        if context.region and context.region in self._by_region:
            eligible.append(self._by_region[context.region])

        # Seasonal tables for current season
        if context.season and context.season in self._by_season:
            eligible.append(self._by_season[context.season])

        return eligible

    def _roll_regional(self, context: EncounterTableContext) -> Optional[EncounterResult]:
        """Roll on the regional table for the current context."""
        if context.region and context.region in self._by_region:
            table = self._tables.get(self._by_region[context.region])
            if table:
                roll, entry = table.roll(context)
                return EncounterResult(
                    table_id=table.table_id,
                    table_name=table.name,
                    roll=roll,
                    entry=entry,
                    location_type=context.location_type,
                    time_of_day=context.time_of_day,
                    season=context.season,
                    description=entry.result,
                )
        return None

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def list_tables_by_category(
        self,
        category: EncounterTableCategory
    ) -> list[str]:
        """List all table IDs in a category."""
        return self._by_category.get(category, [])

    def list_all_categories(self) -> list[EncounterTableCategory]:
        """List all categories with registered tables."""
        return [cat for cat in EncounterTableCategory if self._by_category.get(cat)]

    def get_settlement_tables(
        self,
        settlement: DolmenwoodSettlement
    ) -> dict[EncounterTimeOfDay, str]:
        """Get all table IDs for a settlement."""
        return self._by_settlement.get(settlement, {})

    def get_regional_table(
        self,
        region: DolmenwoodRegion
    ) -> Optional[str]:
        """Get the table ID for a region."""
        return self._by_region.get(region)

    def get_seasonal_table(
        self,
        season: EncounterSeason
    ) -> Optional[str]:
        """Get the table ID for a season."""
        return self._by_season.get(season)

    def get_hex_tables(self, hex_id: str) -> list[str]:
        """Get all table IDs for a hex."""
        return self._by_hex.get(hex_id, [])

    def get_table_ids(self) -> list[str]:
        """Get all registered table IDs."""
        return list(self._tables.keys())


# Module-level singleton
_encounter_manager: Optional[EncounterTableManager] = None


def get_encounter_table_manager() -> EncounterTableManager:
    """Get the global EncounterTableManager instance."""
    global _encounter_manager
    if _encounter_manager is None:
        _encounter_manager = EncounterTableManager()
    return _encounter_manager
