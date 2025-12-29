"""
Dolmenwood character class system.

Provides class definitions for the 9 Dolmenwood classes:
- Bard: Performer with special music abilities
- Cleric: Holy spellcaster (holy spells 1-5)
- Enchanter: Fairy magic user (glamours + runes)
- Fighter: Martial combatant
- Friar: Wandering holy spellcaster (holy spells 1-5)
- Hunter: Wilderness warrior and tracker
- Knight: Noble martial warrior
- Magician: Arcane spellcaster (arcane spells 1-6)
- Thief: Skilled infiltrator and rogue
"""

from src.classes.class_data import (
    ArmorProficiency,
    ClassAbility,
    ClassDefinition,
    HitDie,
    LevelProgression,
    MagicType,
    SavingThrows,
    WeaponProficiency,
)
from src.classes.class_manager import ClassManager, get_class_manager

__all__ = [
    # Data structures
    "ArmorProficiency",
    "ClassAbility",
    "ClassDefinition",
    "HitDie",
    "LevelProgression",
    "MagicType",
    "SavingThrows",
    "WeaponProficiency",
    # Manager
    "ClassManager",
    "get_class_manager",
]
