"""
Character generation tables for Dolmenwood.

Provides kindred-specific name tables and aspect tables for character creation.
Each kindred (Breggle, Elf, Grimalkin, Human, Mossling, Woodgrue) has its own
set of tables with appropriate entries.

NOTE: Table data is loaded from JSON files stored in SQLite/ChromaDB databases.
This module provides the structure for loading and rolling against those tables,
but does NOT contain hardcoded table entries.
"""

from typing import Any, Optional

from src.tables.table_types import (
    Kindred,
    NameColumn,
    CharacterAspectType,
    DieType,
    TableEntry,
    NameTableColumn,
    KindredNameTable,
    CharacterAspectTable,
    CharacterAspectResult,
    GeneratedCharacterAspects,
    RollTable,
    RollTableEntry,
    RollTableMetadata,
    RollTableType,
    RollResult,
)


class CharacterTableManager:
    """
    Manages character generation tables for all kindreds.

    This manager loads tables from the database rather than containing
    hardcoded entries. Table data is stored as JSON files and loaded
    into SQLite/ChromaDB databases.

    Provides access to name tables and aspect tables, and handles
    rolling complete character aspects.
    """

    def __init__(self, db_connection: Optional[Any] = None):
        """
        Initialize the character table manager.

        Args:
            db_connection: Optional database connection for loading tables.
                          If None, tables must be loaded manually.
        """
        self._db = db_connection

        # Name tables indexed by kindred
        self._name_tables: dict[Kindred, KindredNameTable] = {}

        # Aspect tables indexed by (kindred, aspect_type)
        self._aspect_tables: dict[tuple[Kindred, CharacterAspectType], CharacterAspectTable] = {}

    # =========================================================================
    # TABLE LOADING FROM DATABASE
    # =========================================================================

    def load_name_table(self, kindred: Kindred) -> Optional[KindredNameTable]:
        """
        Load a name table from the database by kindred.

        Args:
            kindred: The kindred to load the name table for.

        Returns:
            The loaded KindredNameTable, or None if not found.
        """
        # Check cache first
        if kindred in self._name_tables:
            return self._name_tables[kindred]

        # Load from database if available
        if self._db is not None:
            table = self._load_name_table_from_db(kindred)
            if table:
                self._name_tables[kindred] = table
                return table

        return None

    def load_aspect_table(
        self,
        kindred: Kindred,
        aspect_type: CharacterAspectType
    ) -> Optional[CharacterAspectTable]:
        """
        Load an aspect table from the database.

        Args:
            kindred: The kindred to load the table for.
            aspect_type: The aspect type to load.

        Returns:
            The loaded CharacterAspectTable, or None if not found.
        """
        key = (kindred, aspect_type)

        # Check cache first
        if key in self._aspect_tables:
            return self._aspect_tables[key]

        # Load from database if available
        if self._db is not None:
            table = self._load_aspect_table_from_db(kindred, aspect_type)
            if table:
                self._aspect_tables[key] = table
                return table

        return None

    def _load_name_table_from_db(self, kindred: Kindred) -> Optional[KindredNameTable]:
        """
        Load a name table from the SQLite database.

        This method should be overridden or extended when database
        integration is implemented.
        """
        # TODO: Implement database loading when SQLite integration is ready
        # Example query:
        # SELECT metadata, columns FROM name_tables WHERE kindred = ?
        return None

    def _load_aspect_table_from_db(
        self,
        kindred: Kindred,
        aspect_type: CharacterAspectType
    ) -> Optional[CharacterAspectTable]:
        """
        Load an aspect table from the SQLite database.

        This method should be overridden or extended when database
        integration is implemented.
        """
        # TODO: Implement database loading when SQLite integration is ready
        # Example query:
        # SELECT metadata, entries FROM aspect_tables WHERE kindred = ? AND aspect_type = ?
        return None

    def load_all_tables_for_kindred(self, kindred: Kindred) -> None:
        """
        Pre-load all tables for a kindred.

        This ensures all name and aspect tables are cached.
        """
        self.load_name_table(kindred)
        for aspect_type in CharacterAspectType:
            self.load_aspect_table(kindred, aspect_type)

    # =========================================================================
    # NAME TABLE REGISTRATION
    # =========================================================================

    def register_name_table(self, table: KindredNameTable) -> None:
        """
        Register a name table for a kindred.

        Used for testing or manual table loading.
        """
        self._name_tables[table.kindred] = table

    def get_name_table(self, kindred: Kindred) -> Optional[KindredNameTable]:
        """Get the name table for a kindred, loading from database if necessary."""
        return self.load_name_table(kindred)

    # =========================================================================
    # ASPECT TABLE REGISTRATION
    # =========================================================================

    def register_aspect_table(self, table: CharacterAspectTable) -> None:
        """
        Register an aspect table.

        Used for testing or manual table loading.
        """
        key = (table.kindred, table.aspect_type)
        self._aspect_tables[key] = table

    def get_aspect_table(
        self,
        kindred: Kindred,
        aspect_type: CharacterAspectType
    ) -> Optional[CharacterAspectTable]:
        """Get an aspect table for a kindred, loading from database if necessary."""
        return self.load_aspect_table(kindred, aspect_type)

    def get_all_aspect_tables(self, kindred: Kindred) -> list[CharacterAspectTable]:
        """Get all aspect tables for a kindred."""
        return [
            table for (k, _), table in self._aspect_tables.items()
            if k == kindred
        ]

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    def clear_cache(self) -> None:
        """Clear the table cache."""
        self._name_tables.clear()
        self._aspect_tables.clear()

    # =========================================================================
    # CHARACTER GENERATION
    # =========================================================================

    def roll_name(
        self,
        kindred: Kindred,
        gender: Optional[str] = None,
        style: Optional[str] = None
    ) -> str:
        """
        Roll a name for a character of the given kindred.

        Args:
            kindred: The character's kindred
            gender: "male", "female", or None for unisex
            style: For elves: "rustic" or "courtly"

        Returns:
            Generated name
        """
        table = self.get_name_table(kindred)
        if table:
            return table.roll_full_name(gender=gender, style=style)
        return ""

    def roll_aspect(
        self,
        kindred: Kindred,
        aspect_type: CharacterAspectType
    ) -> Optional[CharacterAspectResult]:
        """Roll on a specific aspect table."""
        table = self.get_aspect_table(kindred, aspect_type)
        if not table:
            return None

        roll, entry = table.roll()
        return CharacterAspectResult(
            kindred=kindred,
            aspect_type=aspect_type,
            roll=roll,
            result=entry.result,
            entry=entry
        )

    def generate_character(
        self,
        kindred: Kindred,
        gender: Optional[str] = None,
        style: Optional[str] = None,
        aspects_to_roll: Optional[list[CharacterAspectType]] = None
    ) -> GeneratedCharacterAspects:
        """
        Generate a complete set of character aspects.

        Args:
            kindred: The character's kindred
            gender: Gender for name generation
            style: Name style for elves
            aspects_to_roll: Specific aspects to roll, or None for all

        Returns:
            GeneratedCharacterAspects with all rolled results
        """
        character = GeneratedCharacterAspects(kindred=kindred, gender=gender)

        # Roll name
        character.name = self.roll_name(kindred, gender, style)

        # Determine which aspects to roll
        if aspects_to_roll is None:
            aspects_to_roll = [
                CharacterAspectType.BACKGROUND,
                CharacterAspectType.TRINKET,
                CharacterAspectType.HEAD,
                CharacterAspectType.DEMEANOUR,
                CharacterAspectType.DESIRES,
                CharacterAspectType.FACE,
                CharacterAspectType.DRESS,
                CharacterAspectType.BELIEFS,
                CharacterAspectType.FUR_BODY,
                CharacterAspectType.SPEECH,
            ]

        # Roll each aspect
        for aspect_type in aspects_to_roll:
            result = self.roll_aspect(kindred, aspect_type)
            if result:
                character.set_aspect(aspect_type, result)

        return character

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def list_kindreds_with_name_tables(self) -> list[Kindred]:
        """List all kindreds with registered name tables."""
        return list(self._name_tables.keys())

    def list_kindreds_with_aspect_tables(self) -> list[Kindred]:
        """List all kindreds with registered aspect tables."""
        return list(set(k for k, _ in self._aspect_tables.keys()))

    def list_aspect_types_for_kindred(self, kindred: Kindred) -> list[CharacterAspectType]:
        """List all aspect types available for a kindred."""
        return [
            aspect_type for (k, aspect_type) in self._aspect_tables.keys()
            if k == kindred
        ]

    def get_table_ids(self) -> list[str]:
        """Get all registered table IDs."""
        ids = []
        for table in self._name_tables.values():
            ids.append(f"name_{table.kindred.value}")
        for (kindred, aspect_type), _ in self._aspect_tables.items():
            ids.append(f"{kindred.value}_{aspect_type.value}")
        return ids


# Global instance
_character_manager: Optional[CharacterTableManager] = None


def get_character_table_manager() -> CharacterTableManager:
    """Get the global CharacterTableManager instance."""
    global _character_manager
    if _character_manager is None:
        _character_manager = CharacterTableManager()
    return _character_manager
