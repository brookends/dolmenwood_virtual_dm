"""
Core data structures for Dolmenwood character classes.

Defines ClassDefinition, ClassAbility, and related structures for the 9 classes:
Bard, Cleric, Enchanter, Fighter, Friar, Hunter, Knight, Magician, Thief.

Source: Dolmenwood Player Book
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MagicType(str, Enum):
    """Types of magic available to spellcasting classes."""
    NONE = "none"
    ARCANE = "arcane"           # Magician
    HOLY = "holy"               # Cleric, Friar
    GLAMOUR = "glamour"         # Enchanter (fairy glamours)
    RUNE = "rune"               # Enchanter only (lesser, greater, mighty)


class HitDie(str, Enum):
    """Hit die types by class."""
    D4 = "d4"
    D6 = "d6"
    D8 = "d8"


class ArmorProficiency(str, Enum):
    """Armor proficiency levels."""
    NONE = "none"               # Magician, Enchanter
    LIGHT = "light"             # Leather, padded
    MEDIUM = "medium"           # Chain, scale
    HEAVY = "heavy"             # Plate
    ALL = "all"                 # Any armor
    SHIELDS = "shields"         # Can use shields


class WeaponProficiency(str, Enum):
    """Weapon proficiency categories."""
    SIMPLE = "simple"           # Daggers, staves, clubs
    MARTIAL = "martial"         # Swords, axes, polearms
    RANGED = "ranged"           # Bows, crossbows
    ALL = "all"                 # Any weapon


@dataclass
class SavingThrows:
    """
    Character saving throw values.

    Uses the 5 Dolmenwood save categories (p152-153).
    Lower is better - must roll >= target on d20.
    """
    doom: int = 14      # Death, poison, doom effects
    ray: int = 15       # Wands, rays, gaze attacks
    hold: int = 16      # Paralysis, petrification, hold
    blast: int = 17     # Breath weapons, area effects
    spell: int = 18     # Spells and spell-like effects

    def get_save(self, save_type: str) -> int:
        """Get save value by type name."""
        return getattr(self, save_type.lower(), 18)


@dataclass
class LevelProgression:
    """
    Class progression at a specific level.

    Defines what changes when a character reaches this level.
    """
    level: int
    experience_required: int        # XP needed to reach this level
    attack_bonus: int               # Base attack bonus at this level
    saving_throws: SavingThrows     # Save values at this level
    hit_dice: str                   # Total HD at this level (e.g., "3d8")

    # Spellcasting (for spellcasters only)
    spell_slots: dict[int, int] = field(default_factory=dict)  # Spell level -> slots

    # Rune access (for Enchanter only)
    rune_access: list[str] = field(default_factory=list)  # ["lesser", "greater", "mighty"]

    # Special abilities unlocked at this level
    abilities_gained: list[str] = field(default_factory=list)

    # Extra attacks (for martial classes)
    attacks_per_round: int = 1


@dataclass
class ClassAbility:
    """
    A special ability granted by a class.

    Similar to KindredAbility but for class features.
    """
    ability_id: str
    name: str
    description: str

    # When available
    min_level: int = 1

    # Usage
    is_passive: bool = True
    uses_per_day: Optional[int] = None
    uses_per_day_by_level: dict[int, int] = field(default_factory=dict)

    # Combat effects
    is_attack: bool = False
    damage_dice: Optional[str] = None
    damage_by_level: dict[int, str] = field(default_factory=dict)

    # Scaling
    scales_with_level: bool = False

    # Extra mechanical data
    extra_data: dict[str, Any] = field(default_factory=dict)

    def get_uses_at_level(self, level: int) -> Optional[int]:
        """Get uses per day at a specific level."""
        if self.uses_per_day is not None:
            return self.uses_per_day
        if self.uses_per_day_by_level:
            # Find highest level that doesn't exceed current level
            applicable_levels = [l for l in self.uses_per_day_by_level.keys() if l <= level]
            if applicable_levels:
                return self.uses_per_day_by_level[max(applicable_levels)]
        return None

    def get_damage_at_level(self, level: int) -> Optional[str]:
        """Get damage dice at a specific level."""
        if self.damage_dice:
            return self.damage_dice
        if self.damage_by_level:
            applicable_levels = [l for l in self.damage_by_level.keys() if l <= level]
            if applicable_levels:
                return self.damage_by_level[max(applicable_levels)]
        return None


@dataclass
class ClassDefinition:
    """
    Complete definition of a character class.

    Contains all mechanical and descriptive data for a class.
    """
    # Identification
    class_id: str                   # e.g., "fighter", "magician"
    name: str                       # Display name
    description: str                # Flavor text description

    # Core mechanics
    hit_die: HitDie                 # HP die type
    prime_ability: str              # Primary ability score (STR, INT, etc.)

    # Magic type
    magic_type: MagicType = MagicType.NONE

    # Proficiencies
    armor_proficiencies: list[ArmorProficiency] = field(default_factory=list)
    weapon_proficiencies: list[WeaponProficiency] = field(default_factory=list)

    # Level progression (levels 1-15)
    level_progression: list[LevelProgression] = field(default_factory=list)

    # Class abilities
    abilities: list[ClassAbility] = field(default_factory=list)

    # Kindred restrictions (which kindreds CANNOT be this class)
    restricted_kindreds: list[str] = field(default_factory=list)

    # Starting equipment options
    starting_equipment: list[str] = field(default_factory=list)

    # Source reference
    source_book: str = "Dolmenwood Player Book"
    source_page: int = 0

    def get_progression_at_level(self, level: int) -> Optional[LevelProgression]:
        """Get level progression data for a specific level."""
        for prog in self.level_progression:
            if prog.level == level:
                return prog
        return None

    def get_attack_bonus(self, level: int) -> int:
        """Get attack bonus at a specific level."""
        prog = self.get_progression_at_level(level)
        if prog:
            return prog.attack_bonus
        # Fallback: find highest level <= requested level
        applicable = [p for p in self.level_progression if p.level <= level]
        if applicable:
            return max(applicable, key=lambda p: p.level).attack_bonus
        return 0

    def get_saving_throws(self, level: int) -> SavingThrows:
        """Get saving throws at a specific level."""
        prog = self.get_progression_at_level(level)
        if prog:
            return prog.saving_throws
        # Fallback
        applicable = [p for p in self.level_progression if p.level <= level]
        if applicable:
            return max(applicable, key=lambda p: p.level).saving_throws
        return SavingThrows()

    def get_spell_slots(self, level: int) -> dict[int, int]:
        """Get spell slots at a specific level (for spellcasters)."""
        if self.magic_type == MagicType.NONE:
            return {}
        prog = self.get_progression_at_level(level)
        if prog:
            return prog.spell_slots
        return {}

    def get_ability(self, ability_id: str) -> Optional[ClassAbility]:
        """Get a specific ability by ID."""
        for ability in self.abilities:
            if ability.ability_id == ability_id:
                return ability
        return None

    def get_abilities_at_level(self, level: int) -> list[ClassAbility]:
        """Get all abilities available at a specific level."""
        return [a for a in self.abilities if a.min_level <= level]

    def can_cast_spell_type(self, spell_type: str) -> bool:
        """Check if this class can cast a specific spell type."""
        if self.magic_type == MagicType.NONE:
            return False

        spell_type_lower = spell_type.lower()

        if self.magic_type == MagicType.ARCANE:
            return spell_type_lower == "arcane"
        elif self.magic_type == MagicType.HOLY:
            return spell_type_lower in ("holy", "divine")
        elif self.magic_type == MagicType.GLAMOUR:
            # Enchanter can cast glamours and runes
            return spell_type_lower in ("glamour", "fairy_glamour", "rune")
        elif self.magic_type == MagicType.RUNE:
            return spell_type_lower == "rune"

        return False

    def can_be_kindred(self, kindred_id: str) -> bool:
        """Check if a kindred can be this class."""
        return kindred_id.lower() not in [k.lower() for k in self.restricted_kindreds]
