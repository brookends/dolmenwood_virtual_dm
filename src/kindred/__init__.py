"""
Kindred (race) system for Dolmenwood.

This module provides:
- KindredDefinition: Complete data structure for a kindred
- KindredManager: Central registry for all kindreds
- KindredGenerator: Random character/NPC generation by kindred

Available Kindreds:
- Breggle: Goat-headed folk (mortal)
- Elf: Ageless fairies from the immortal realm (fairy)
- Grimalkin: Shape-shifting cat-fairies (fairy)
- Human: Common folk of Dolmenwood (mortal)
- Mossling: (coming soon)
- Woodgrue: (coming soon)
"""

from src.kindred.kindred_data import (
    AspectTable,
    AspectTableEntry,
    AspectType,
    DiceFormula,
    GeneratedKindredAspects,
    KindredAbility,
    KindredDefinition,
    KindredType,
    LevelProgression,
    NameColumn,
    NameTable,
    PhysicalRanges,
)
from src.kindred.kindred_manager import KindredManager, get_kindred_manager
from src.kindred.kindred_generator import (
    KindredGenerator,
    generate_character_kindred,
    generate_npc_kindred,
)

__all__ = [
    # Data structures
    "AspectTable",
    "AspectTableEntry",
    "AspectType",
    "DiceFormula",
    "GeneratedKindredAspects",
    "KindredAbility",
    "KindredDefinition",
    "KindredType",
    "LevelProgression",
    "NameColumn",
    "NameTable",
    "PhysicalRanges",
    # Manager
    "KindredManager",
    "get_kindred_manager",
    # Generator
    "KindredGenerator",
    "generate_character_kindred",
    "generate_npc_kindred",
]
