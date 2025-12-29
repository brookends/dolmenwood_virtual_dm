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

from src.data_models import DiceRoller
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
    # Hex-embedded table parsing
    HexTableCategory,
    HexRollTable,
    HexRollTableEntry,
    parse_hex_roll_tables,
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

        # Cache of hex-embedded roll tables (table_id -> RollTable)
        # These are loaded from hex data in the database
        self._roll_tables: dict[str, RollTable] = {}

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
    # HEX TABLE LOADING FROM DATABASE
    # =========================================================================

    def load_hex_tables_from_hex_data(
        self,
        hex_data: dict[str, Any]
    ) -> tuple[list[RollTable], list[RollTable]]:
        """
        Load and register roll tables embedded in hex data.

        Hex data in SQLite/ChromaDB contains embedded roll tables at:
        - hex_data["roll_tables"] (hex-level tables)
        - hex_data["points_of_interest"][*]["roll_tables"] (POI-specific)

        IMPORTANT: Only ENCOUNTER tables are registered for wilderness encounter
        rolls. Dungeon room tables and other table types are cached separately
        and not included in encounter selection.

        Args:
            hex_data: The full hex JSON data from the database.

        Returns:
            Tuple of (encounter_tables, other_tables) as RollTable lists.
        """
        hex_tables = parse_hex_roll_tables(hex_data)
        hex_id = hex_data.get("hex_id")

        encounter_tables: list[RollTable] = []
        other_tables: list[RollTable] = []

        for hex_table in hex_tables:
            roll_table = hex_table.to_roll_table()

            # Register in cache
            self._roll_tables[roll_table.table_id] = roll_table

            # Only index ENCOUNTER tables for wilderness encounter rolls
            if hex_table.is_encounter_table():
                encounter_tables.append(roll_table)
                if hex_id:
                    if hex_id not in self._by_hex:
                        self._by_hex[hex_id] = []
                    if roll_table.table_id not in self._by_hex[hex_id]:
                        self._by_hex[hex_id].append(roll_table.table_id)
            else:
                other_tables.append(roll_table)

        return encounter_tables, other_tables

    def load_hex_from_db(self, hex_id: str) -> Optional[dict[str, Any]]:
        """
        Load hex data from the database.

        This method should be overridden when database integration is ready.

        Args:
            hex_id: The hex identifier (e.g., "0101").

        Returns:
            The hex data dictionary, or None if not found.
        """
        if self._db is None:
            return None

        # TODO: Implement database loading
        # Example query:
        # SELECT data FROM hexes WHERE hex_id = ?
        return None

    def load_hex_tables(self, hex_id: str) -> list[RollTable]:
        """
        Load ENCOUNTER roll tables for a hex from the database.

        Only returns tables categorized as encounters. Dungeon room tables
        and other types are cached but not returned here.

        Args:
            hex_id: The hex identifier (e.g., "0101").

        Returns:
            List of ENCOUNTER RollTable objects for this hex.
        """
        # Check if already loaded
        if hex_id in self._by_hex:
            return [
                self._roll_tables[tid]
                for tid in self._by_hex[hex_id]
                if tid in self._roll_tables
            ]

        # Load from database
        hex_data = self.load_hex_from_db(hex_id)
        if hex_data:
            encounter_tables, _ = self.load_hex_tables_from_hex_data(hex_data)
            return encounter_tables

        return []

    def get_hex_encounter_tables(self, hex_id: str) -> list[RollTable]:
        """
        Get ENCOUNTER tables for a hex, loading from database if necessary.

        Only returns tables categorized as encounters. Use get_hex_dungeon_tables()
        for dungeon room tables.

        Args:
            hex_id: The hex identifier.

        Returns:
            List of ENCOUNTER RollTable objects for this hex.
        """
        return self.load_hex_tables(hex_id)

    def get_hex_roll_tables(self, hex_id: str) -> list[RollTable]:
        """
        Get ALL roll tables for a hex (encounter + dungeon + other).

        Args:
            hex_id: The hex identifier.

        Returns:
            List of ALL RollTable objects for this hex.
        """
        # Ensure tables are loaded
        self.load_hex_tables(hex_id)

        # Return all tables for this hex from cache
        return [
            table for table in self._roll_tables.values()
            if table.metadata.conditions.get("hex_id") == hex_id
        ]

    def get_hex_dungeon_tables(self, hex_id: str) -> list[RollTable]:
        """
        Get DUNGEON room tables for a hex.

        Args:
            hex_id: The hex identifier.

        Returns:
            List of DUNGEON RollTable objects for this hex.
        """
        # Ensure tables are loaded
        self.load_hex_tables(hex_id)

        # Return dungeon tables from cache
        return [
            table for table in self._roll_tables.values()
            if (table.metadata.conditions.get("hex_id") == hex_id and
                table.metadata.category in ("dungeon_room", "dungeon_encounter"))
        ]

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
        self._roll_tables.clear()
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

        result = DiceRoller.roll(notation, "Encounter table dice roll")
        return result.total

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

        # Note: Encounter tables do not chain to other encounter tables.
        # The Python code handles table selection (common, regional, seasonal, hex)
        # via _select_table() which randomly picks from all eligible tables.

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
        selected_id = DiceRoller.choice(eligible_tables, "Select encounter table")
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
