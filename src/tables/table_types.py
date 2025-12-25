"""
Table type definitions for the Dolmenwood Virtual DM.

Implements the table system from Phase 4, supporting various table categories
for character creation, encounters, treasure, weather, and more.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, Union
import random


class TableCategory(str, Enum):
    """
    Categories of game tables for organization and context-specific access.

    Tables are grouped by category to allow the system to load and use
    appropriate tables based on game context.
    """
    # Character creation
    CHARACTER_ASPECT = "character_aspect"  # Appearance, beliefs, background

    # Treasure and items
    TREASURE_TYPE = "treasure_type"        # What types/amounts of treasure
    TREASURE_ITEM = "treasure_item"        # Specific treasure items
    MAGIC_ITEM = "magic_item"              # Magic item generation

    # Weather
    WEATHER = "weather"                    # Weather conditions by season

    # Encounters (generic)
    ENCOUNTER_GENERIC = "encounter_generic"     # Generic wilderness encounters
    ENCOUNTER_TYPE = "encounter_type"           # Type of encounter (monster, NPC, etc.)
    REACTION = "reaction"                       # 2d6 reaction roll
    MORALE = "morale"                           # Morale check
    SURPRISE = "surprise"                       # Surprise determination

    # Encounters (hex-specific)
    ENCOUNTER_HEX = "encounter_hex"        # Hex-specific encounter tables

    # Dungeon (generic)
    DUNGEON_ROOM = "dungeon_room"          # Room contents
    DUNGEON_FEATURE = "dungeon_feature"    # Room features
    DUNGEON_TRAP = "dungeon_trap"          # Trap generation
    DUNGEON_GENERIC = "dungeon_generic"    # Generic dungeon tables

    # Dungeon (hex-specific)
    DUNGEON_HEX = "dungeon_hex"            # Hex-specific dungeon rooms

    # Rumors
    RUMOR_GENERIC = "rumor_generic"        # Generic rumors
    RUMOR_SETTLEMENT = "rumor_settlement"  # Settlement-specific rumors
    RUMOR_MONSTER = "rumor_monster"        # Monster-related rumors

    # Flavor
    FLAVOR = "flavor"                      # Context-specific flavor tables
    NPC_TRAIT = "npc_trait"               # NPC personality/traits

    # Procedural
    FORAGING = "foraging"                  # Foraging results
    LOST = "lost"                          # Getting lost results


class DieType(str, Enum):
    """Standard die types for table rolls."""
    D4 = "d4"
    D6 = "d6"
    D8 = "d8"
    D10 = "d10"
    D12 = "d12"
    D20 = "d20"
    D100 = "d100"
    D2 = "d2"  # Coin flip
    D3 = "d3"  # d6/2


@dataclass
class TableEntry:
    """
    A single entry in a game table.

    Entries can contain simple text results, nested table references,
    monster/NPC/item references, or mechanical effects.
    """
    # Roll range (inclusive)
    roll_min: int
    roll_max: int

    # Result content
    result: str                           # Text description of result
    title: Optional[str] = None           # Optional title

    # References to other content
    monster_refs: list[str] = field(default_factory=list)   # Monster IDs
    npc_refs: list[str] = field(default_factory=list)       # NPC IDs
    item_refs: list[str] = field(default_factory=list)      # Item IDs
    hex_refs: list[str] = field(default_factory=list)       # Hex IDs

    # Nested tables
    sub_table: Optional[str] = None       # Reference to another table to roll on
    sub_roll: Optional[str] = None        # Dice notation for sub-roll

    # Mechanical effects
    mechanical_effect: Optional[str] = None  # Game mechanical effect
    modifier: int = 0                        # Modifier to apply (e.g., reaction mod)

    # Quantity
    quantity: Optional[str] = None        # Dice notation for quantity, e.g., "2d6"

    def matches_roll(self, roll: int) -> bool:
        """Check if a roll value falls within this entry's range."""
        return self.roll_min <= roll <= self.roll_max


@dataclass
class DolmenwoodTable:
    """
    A game table for random determination.

    Tables support various die types, modifiers, and can reference
    other tables for nested rolls. They are categorized for
    context-appropriate access.
    """
    # Identification
    table_id: str
    name: str
    category: TableCategory

    # Die configuration
    die_type: DieType = DieType.D6
    num_dice: int = 1
    base_modifier: int = 0                # Permanent modifier to all rolls

    # Description
    description: str = ""                  # When/how to use this table
    source_reference: str = ""             # Book and page reference

    # Entries
    entries: list[TableEntry] = field(default_factory=list)

    # Context
    context_required: Optional[str] = None  # Required context (hex_id, season, etc.)
    hex_id: Optional[str] = None           # For hex-specific tables
    dungeon_id: Optional[str] = None       # For dungeon-specific tables
    settlement_id: Optional[str] = None    # For settlement-specific tables

    # Flags
    allows_reroll: bool = False            # Can results be rerolled
    cumulative: bool = False               # Results accumulate (treasure)

    def get_max_roll(self) -> int:
        """Get the maximum possible roll for this table."""
        die_size = int(self.die_type.value[1:])  # Extract number from "d6", "d20", etc.
        return self.num_dice * die_size + self.base_modifier

    def get_min_roll(self) -> int:
        """Get the minimum possible roll for this table."""
        return self.num_dice + self.base_modifier

    def roll(self, modifier: int = 0) -> tuple[int, TableEntry]:
        """
        Roll on this table and return the result.

        Args:
            modifier: Additional modifier to the roll

        Returns:
            Tuple of (roll_total, matching_entry)
        """
        die_size = int(self.die_type.value[1:])
        rolls = [random.randint(1, die_size) for _ in range(self.num_dice)]
        total = sum(rolls) + self.base_modifier + modifier

        # Clamp to valid range
        total = max(self.get_min_roll(), min(self.get_max_roll(), total))

        # Find matching entry
        for entry in self.entries:
            if entry.matches_roll(total):
                return total, entry

        # Fallback to last entry if no match (shouldn't happen with proper tables)
        if self.entries:
            return total, self.entries[-1]

        # Return empty entry if table has no entries
        return total, TableEntry(roll_min=total, roll_max=total, result="No result")


@dataclass
class TableResult:
    """
    Complete result of a table roll, including any sub-rolls.

    Captures the full chain of results for complex nested tables.
    """
    table_id: str
    table_name: str
    category: TableCategory

    # Roll details
    roll_total: int
    dice_rolled: list[int] = field(default_factory=list)
    modifier_applied: int = 0

    # Result
    entry: Optional[TableEntry] = None
    result_text: str = ""

    # Nested results
    sub_results: list["TableResult"] = field(default_factory=list)

    # Resolved references
    resolved_monsters: list[Any] = field(default_factory=list)
    resolved_npcs: list[Any] = field(default_factory=list)
    resolved_items: list[Any] = field(default_factory=list)

    # Quantity rolled (if applicable)
    quantity_rolled: Optional[int] = None

    def get_full_description(self) -> str:
        """Get complete description including all sub-results."""
        parts = [self.result_text]
        for sub in self.sub_results:
            parts.append(f"  → {sub.get_full_description()}")
        return "\n".join(parts)


# Type alias for table modifier functions
TableModifierFunc = Callable[[int, dict[str, Any]], int]


@dataclass
class TableContext:
    """
    Context for table resolution, providing modifiers and state.

    Passed to tables to allow context-sensitive modifiers (e.g.,
    CHA modifier for reaction rolls, terrain for encounter tables).
    """
    # Location context
    hex_id: Optional[str] = None
    dungeon_id: Optional[str] = None
    settlement_id: Optional[str] = None
    room_id: Optional[str] = None

    # Time context
    time_of_day: Optional[str] = None
    season: Optional[str] = None
    weather: Optional[str] = None

    # Character context
    party_level: int = 1
    cha_modifier: int = 0                 # For reaction rolls

    # Terrain context
    terrain_type: Optional[str] = None
    terrain_difficulty: int = 1

    # Modifiers
    explicit_modifier: int = 0            # User-specified modifier
    situational_modifiers: dict[str, int] = field(default_factory=dict)

    # State
    previous_results: list[TableResult] = field(default_factory=list)

    def get_total_modifier(self) -> int:
        """Calculate total modifier from all sources."""
        total = self.explicit_modifier
        total += sum(self.situational_modifiers.values())
        return total


# Standard reaction table results
class ReactionRoll(str, Enum):
    """Standard 2d6 reaction roll results."""
    HOSTILE_ATTACK = "hostile_attack"      # 2
    HOSTILE = "hostile"                    # 3-5
    UNCERTAIN = "uncertain"                # 6-8
    INDIFFERENT = "indifferent"            # 9-11
    FRIENDLY = "friendly"                  # 12+


def interpret_reaction_roll(roll: int) -> ReactionRoll:
    """
    Interpret a 2d6 reaction roll result.

    Standard B/X reaction table:
    2: Hostile, attacks
    3-5: Hostile, may attack
    6-8: Uncertain, monster confused
    9-11: No attack, monster leaves or considers offers
    12: Friendly
    """
    if roll <= 2:
        return ReactionRoll.HOSTILE_ATTACK
    elif roll <= 5:
        return ReactionRoll.HOSTILE
    elif roll <= 8:
        return ReactionRoll.UNCERTAIN
    elif roll <= 11:
        return ReactionRoll.INDIFFERENT
    else:
        return ReactionRoll.FRIENDLY


# Morale check results
class MoraleResult(str, Enum):
    """Morale check outcomes."""
    PASS = "pass"        # Morale holds, continue fighting
    FAIL = "fail"        # Morale breaks, flee or surrender
    RALLY = "rally"      # Exceptional pass, bonus effect


def check_morale(roll: int, morale_score: int, modifier: int = 0) -> MoraleResult:
    """
    Check morale against a 2d6 roll.

    Args:
        roll: The 2d6 roll result
        morale_score: Target morale score (2-12)
        modifier: Situational modifiers

    Returns:
        MoraleResult indicating pass, fail, or rally
    """
    adjusted_roll = roll + modifier

    if adjusted_roll <= morale_score:
        # Check for rally (natural 2 on unmodified roll)
        if roll == 2:
            return MoraleResult.RALLY
        return MoraleResult.PASS
    else:
        return MoraleResult.FAIL


# Skill check (X-in-6) system
@dataclass
class SkillCheck:
    """
    X-in-6 skill check result.

    Used for OSR-style skills like Hear Noise, Find Secret Doors,
    Forage, Hunt, etc.
    """
    skill_name: str
    target: int           # X in X-in-6 (1-5 typically)
    roll: int             # d6 result
    success: bool         # roll <= target

    @classmethod
    def check(cls, skill_name: str, target: int, modifier: int = 0) -> "SkillCheck":
        """
        Perform an X-in-6 skill check.

        Args:
            skill_name: Name of the skill being checked
            target: Base X in X-in-6 chance
            modifier: Situational modifier to target

        Returns:
            SkillCheck result
        """
        effective_target = max(0, min(6, target + modifier))  # Clamp to 0-6
        roll = random.randint(1, 6)
        success = roll <= effective_target

        return cls(
            skill_name=skill_name,
            target=effective_target,
            roll=roll,
            success=success
        )


# Common skill targets
class SkillTarget(Enum):
    """Standard X-in-6 skill targets for common abilities."""
    HEAR_NOISE = 1         # 1-in-6 base
    FIND_TRAPS = 1         # 1-in-6 base (Thieves get better)
    FIND_SECRET_DOORS = 1  # 1-in-6 base (Elves get 2-in-6)
    FORAGE = 1             # 1-in-6 base
    HUNT = 1               # 1-in-6 base
    FORCE_DOOR = 2         # 2-in-6 base
    GET_LOST = 2           # 2-in-6 base in wilderness
    ENCOUNTER = 2          # 2-in-6 base encounter check
