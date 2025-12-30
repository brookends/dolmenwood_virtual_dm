"""
Game tables and resolution systems for the Dolmenwood Virtual DM.

This module provides:
- Table types and categories for random determination
- Table management and resolution with nested rolls
- Dolmenwood-specific game tables (encounters, treasure, NPCs, etc.)
- Action resolution with failure-first logic
- Skill check system (X-in-6)
"""

from src.tables.table_types import (
    # Enums
    TableCategory,
    DieType,
    SkillTarget,
    Kindred,
    NameColumn,
    CharacterAspectType,
    # Encounter enums
    EncounterLocationType,
    EncounterTimeOfDay,
    EncounterSeason,
    EncounterTableCategory,
    NestedTableConditionType,
    DolmenwoodRegion,
    DolmenwoodSettlement,
    EncounterResultType,
    # Treasure enums
    TreasureTableCategory,
    TreasureType,
    CoinType,
    MagicItemCategory,
    # Database-driven roll table enums
    RollTableType,
    # Data classes
    TableEntry,
    DolmenwoodTable,
    TableResult,
    TableContext,
    SkillCheck,
    NameTableColumn,
    KindredNameTable,
    CharacterAspectTable,
    CharacterAspectResult,
    GeneratedCharacterAspects,
    # Encounter data classes
    NestedTableCondition,
    NestedTableSelector,
    EncounterTableContext,
    EncounterEntry,
    EncounterTable,
    EncounterResult,
    # Treasure data classes
    TreasureEntry,
    TreasureTableContext,
    TreasureNestedTableSelector,
    TreasureTable,
    TreasureComponent,
    GeneratedTreasureItem,
    TreasureResult,
    # Database-driven roll table data classes
    RollTableEntry,
    RollTableMetadata,
    RollTable,
    RollTableReference,
    RollResult,
    # Hex-embedded roll table classes
    HexTableCategory,
    HexRollTableEntry,
    HexRollTable,
    # Functions
    parse_hex_roll_tables,
    convert_hex_tables_to_roll_tables,
)

from src.tables.character_tables import (
    CharacterTableManager,
    get_character_table_manager,
)

from src.tables.table_manager import (
    TableManager,
    get_table_manager,
)

from src.tables.dolmenwood_tables import (
    DolmenwoodTables,
    get_dolmenwood_tables,
)

from src.tables.action_resolver import (
    # Enums
    ResolutionType,
    FailureSeverity,
    # Data classes
    FailureConsequence,
    SuccessEffect,
    ActionContext,
    ActionResolution,
    # Main class
    ActionResolver,
    # Convenience functions
    prepare_skill_check,
    quick_skill_check,
)

from src.tables.encounter_tables import (
    EncounterTableManager,
    get_encounter_table_manager,
)

from src.tables.treasure_tables import (
    TreasureTableManager,
    get_treasure_table_manager,
)

__all__ = [
    # Table types
    "TableCategory",
    "DieType",
    "SkillTarget",
    "Kindred",
    "NameColumn",
    "CharacterAspectType",
    "TableEntry",
    "DolmenwoodTable",
    "TableResult",
    "TableContext",
    "SkillCheck",
    "NameTableColumn",
    "KindredNameTable",
    "CharacterAspectTable",
    "CharacterAspectResult",
    "GeneratedCharacterAspects",
    # Encounter types
    "EncounterLocationType",
    "EncounterTimeOfDay",
    "EncounterSeason",
    "EncounterTableCategory",
    "NestedTableConditionType",
    "DolmenwoodRegion",
    "DolmenwoodSettlement",
    "EncounterResultType",
    "NestedTableCondition",
    "NestedTableSelector",
    "EncounterTableContext",
    "EncounterEntry",
    "EncounterTable",
    "EncounterResult",
    # Treasure types
    "TreasureTableCategory",
    "TreasureType",
    "CoinType",
    "MagicItemCategory",
    "TreasureEntry",
    "TreasureTableContext",
    "TreasureNestedTableSelector",
    "TreasureTable",
    "TreasureComponent",
    "GeneratedTreasureItem",
    "TreasureResult",
    # Database-driven roll tables
    "RollTableType",
    "RollTableEntry",
    "RollTableMetadata",
    "RollTable",
    "RollTableReference",
    "RollResult",
    # Hex-embedded roll tables
    "HexTableCategory",
    "HexRollTableEntry",
    "HexRollTable",
    "parse_hex_roll_tables",
    "convert_hex_tables_to_roll_tables",
    # Character tables
    "CharacterTableManager",
    "get_character_table_manager",
    # Encounter tables
    "EncounterTableManager",
    "get_encounter_table_manager",
    # Treasure tables
    "TreasureTableManager",
    "get_treasure_table_manager",
    # Table manager
    "TableManager",
    "get_table_manager",
    # Dolmenwood tables
    "DolmenwoodTables",
    "get_dolmenwood_tables",
    # Action resolver
    "ResolutionType",
    "FailureSeverity",
    "FailureConsequence",
    "SuccessEffect",
    "ActionContext",
    "ActionResolution",
    "ActionResolver",
    "prepare_skill_check",
    "quick_skill_check",
]
