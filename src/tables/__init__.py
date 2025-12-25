"""
Game tables and resolution systems for the Dolmenwood Virtual DM.

This module provides:
- Table types and categories for random determination
- Table management and resolution with nested rolls
- Dolmenwood-specific game tables (encounters, treasure, NPCs, etc.)
- Action resolution with failure-first logic
- Procedure triggers for automated game mechanics
- Skill check system (X-in-6)
"""

from src.tables.table_types import (
    # Enums
    TableCategory,
    DieType,
    ReactionRoll,
    MoraleResult,
    SkillTarget,
    Kindred,
    NameColumn,
    CharacterAspectType,
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
    # Functions
    interpret_reaction_roll,
    check_morale,
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

from src.tables.procedure_triggers import (
    # Enums
    TriggerEvent,
    TriggerPriority,
    # Data classes
    TriggerCondition,
    ProcedureResult,
    GameProcedure,
    # Main class
    ProcedureManager,
    get_procedure_manager,
    # Convenience functions
    fire_turn_passed,
    fire_hex_entered,
    fire_combat_round,
)

__all__ = [
    # Table types
    "TableCategory",
    "DieType",
    "ReactionRoll",
    "MoraleResult",
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
    "interpret_reaction_roll",
    "check_morale",
    # Character tables
    "CharacterTableManager",
    "get_character_table_manager",
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
    # Procedure triggers
    "TriggerEvent",
    "TriggerPriority",
    "TriggerCondition",
    "ProcedureResult",
    "GameProcedure",
    "ProcedureManager",
    "get_procedure_manager",
    "fire_turn_passed",
    "fire_hex_entered",
    "fire_combat_round",
]
