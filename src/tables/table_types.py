"""
Table type definitions for the Dolmenwood Virtual DM.

Implements the table system from Phase 4, supporting various table categories
for character creation, encounters, treasure, weather, and more.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, Union

from src.data_models import DiceRoller


class Kindred(str, Enum):
    """Playable kindreds (races) in Dolmenwood."""
    BREGGLE = "breggle"
    ELF = "elf"
    GRIMALKIN = "grimalkin"
    HUMAN = "human"
    MOSSLING = "mossling"
    WOODGRUE = "woodgrue"


class NameColumn(str, Enum):
    """Name table column types."""
    MALE = "male"
    FEMALE = "female"
    UNISEX = "unisex"
    SURNAME = "surname"
    RUSTIC = "rustic"      # For elves
    COURTLY = "courtly"    # For elves


class CharacterAspectType(str, Enum):
    """Types of character aspect tables."""
    NAME = "name"
    BACKGROUND = "background"
    TRINKET = "trinket"
    HEAD = "head"
    DEMEANOUR = "demeanour"
    DESIRES = "desires"
    FACE = "face"
    DRESS = "dress"
    BELIEFS = "beliefs"
    FUR_BODY = "fur_body"      # Fur for some, body type for others
    SPEECH = "speech"


# =============================================================================
# ENCOUNTER TABLE ENUMS
# =============================================================================


class EncounterLocationType(str, Enum):
    """Types of locations for encounter tables."""
    WILDERNESS = "wilderness"          # General wilderness
    SETTLEMENT = "settlement"          # Town/village encounters
    FAIRY_ROAD = "fairy_road"          # Fairy road encounters
    HEX_SPECIFIC = "hex_specific"      # Specific hex encounters
    REGIONAL = "regional"              # Regional wilderness tables
    DUNGEON = "dungeon"                # Dungeon encounters


class EncounterTimeOfDay(str, Enum):
    """Time of day for encounter tables."""
    ANY = "any"                        # Applies any time
    DAY = "day"                        # Daytime only
    NIGHT = "night"                    # Nighttime only
    DAWN = "dawn"                      # Dawn specifically
    DUSK = "dusk"                      # Dusk specifically


class EncounterSeason(str, Enum):
    """Seasons for encounter tables, including Dolmenwood unseasons."""
    ANY = "any"                        # Applies any season
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    # Dolmenwood Unseasons
    CHAME = "chame"                    # Unseason of Chame
    VAGUE = "vague"                    # Unseason of Vague


class DolmenwoodRegion(str, Enum):
    """Regions of Dolmenwood for regional encounter tables."""
    ANY = "any"                        # Applies anywhere
    NORTHERN_SCRATCH = "northern_scratch"
    LAKE_LONGMERE = "lake_longmere"
    MULCHGROVE = "mulchgrove"
    HAGS_ADDLE = "hags_addle"
    ALDWEALD = "aldweald"
    TITHELANDS = "tithelands"
    HIGH_WOLD = "high_wold"
    FEVER_MARSH = "fever_marsh"
    DRUNE_TERRITORY = "drune_territory"


class DolmenwoodSettlement(str, Enum):
    """Named settlements in Dolmenwood with encounter tables."""
    BLACKESWELL = "blackeswell"
    CASTLE_BRACKENWOLD = "castle_brackenwold"
    COBTON = "cobton"
    DREG = "dreg"
    FORT_VULGAR = "fort_vulgar"
    HIGH_HANKLE = "high_hankle"
    LANKSHORN = "lankshorn"
    MEAGRES_REACH = "meagres_reach"
    ODD = "odd"
    ORBSWALLOW = "orbswallow"
    PRIGWORT = "prigwort"
    WOODCUTTERS_ENCAMPMENT = "woodcutters_encampment"


class EncounterResultType(str, Enum):
    """Types of encounter results."""
    MONSTER = "monster"                # Monster encounter
    NPC = "npc"                        # NPC encounter
    LAIR = "lair"                      # Monster lair discovery
    SPOOR = "spoor"                    # Signs of creature activity
    SPECIAL = "special"                # Special/unique encounter
    ENVIRONMENTAL = "environmental"    # Environmental hazard
    FAIRY = "fairy"                    # Fairy-related encounter
    PATROL = "patrol"                  # Guard/military patrol
    MERCHANT = "merchant"              # Traveling merchant
    PILGRIM = "pilgrim"                # Religious travelers
    EVENT = "event"                    # Local event/happening


class TableCategory(str, Enum):
    """
    Categories of game tables for organization and context-specific access.

    Tables are grouped by category to allow the system to load and use
    appropriate tables based on game context.
    """
    # Character creation
    CHARACTER_ASPECT = "character_aspect"  # Appearance, beliefs, background
    CHARACTER_NAME = "character_name"      # Name generation tables

    # Treasure and items
    TREASURE_TYPE = "treasure_type"        # What types/amounts of treasure
    TREASURE_ITEM = "treasure_item"        # Specific treasure items
    MAGIC_ITEM = "magic_item"              # Magic item generation

    # Weather
    WEATHER = "weather"                    # Weather conditions by season

    # Encounters (generic)
    ENCOUNTER_GENERIC = "encounter_generic"     # Generic wilderness encounters
    ENCOUNTER_TYPE = "encounter_type"           # Type of encounter (monster, NPC, etc.)
    ENCOUNTER_COMMON = "encounter_common"       # Common encounter table
    ENCOUNTER_REGIONAL = "encounter_regional"   # Regional encounter tables
    ENCOUNTER_SETTLEMENT = "encounter_settlement"  # Settlement encounters
    ENCOUNTER_FAIRY_ROAD = "encounter_fairy_road"  # Fairy road encounters
    ENCOUNTER_UNSEASON = "encounter_unseason"   # Unseason-specific encounters
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
        dice_result = DiceRoller.roll(f"{self.num_dice}d{die_size}", "table roll")
        total = dice_result.total + self.base_modifier + modifier

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
        roll = DiceRoller.roll("1d6", f"{skill_name} check").total
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


# =============================================================================
# CHARACTER GENERATION TABLES
# =============================================================================


@dataclass
class NameTableColumn:
    """
    A single column in a name table.

    Represents one category of names (male, female, unisex, surname, etc.)
    with a list of possible values to roll on.
    """
    column_type: NameColumn
    names: list[str] = field(default_factory=list)
    die_type: DieType = DieType.D20

    def roll(self) -> str:
        """Roll a random name from this column."""
        if not self.names:
            return ""
        die_size = int(self.die_type.value[1:])
        index = DiceRoller.randint(1, min(die_size, len(self.names)), "name roll") - 1
        return self.names[index]


@dataclass
class KindredNameTable:
    """
    Name table for a specific kindred.

    Different kindreds have different name table structures:
    - Breggles, Humans, Mosslings, Woodgrue: male, female, unisex, surname
    - Grimalkin: first names, surnames (no gender distinction)
    - Elves: rustic names, courtly names (no surnames)
    """
    kindred: Kindred
    columns: dict[NameColumn, NameTableColumn] = field(default_factory=dict)
    description: str = ""
    source_reference: str = ""

    def get_available_columns(self) -> list[NameColumn]:
        """Get list of available name columns for this kindred."""
        return list(self.columns.keys())

    def roll_name(self, column: NameColumn) -> str:
        """Roll a name from a specific column."""
        if column in self.columns:
            return self.columns[column].roll()
        return ""

    def roll_full_name(
        self,
        gender: Optional[str] = None,
        style: Optional[str] = None  # For elves: "rustic" or "courtly"
    ) -> str:
        """
        Roll a complete name appropriate for the kindred.

        Args:
            gender: "male", "female", or None for random/unisex
            style: For elves only - "rustic" or "courtly"

        Returns:
            Generated full name
        """
        if self.kindred == Kindred.ELF:
            # Elves use rustic or courtly names (no surnames)
            if style == "courtly" and NameColumn.COURTLY in self.columns:
                return self.roll_name(NameColumn.COURTLY)
            elif NameColumn.RUSTIC in self.columns:
                return self.roll_name(NameColumn.RUSTIC)
            return ""

        elif self.kindred == Kindred.GRIMALKIN:
            # Grimalkin have unisex first names and surnames
            first = self.roll_name(NameColumn.UNISEX)
            surname = self.roll_name(NameColumn.SURNAME)
            return f"{first} {surname}".strip()

        else:
            # Standard kindreds: male/female/unisex + surname
            if gender == "male" and NameColumn.MALE in self.columns:
                first = self.roll_name(NameColumn.MALE)
            elif gender == "female" and NameColumn.FEMALE in self.columns:
                first = self.roll_name(NameColumn.FEMALE)
            elif NameColumn.UNISEX in self.columns:
                first = self.roll_name(NameColumn.UNISEX)
            else:
                # Fallback to any available first name column
                for col in [NameColumn.MALE, NameColumn.FEMALE, NameColumn.UNISEX]:
                    if col in self.columns:
                        first = self.roll_name(col)
                        break
                else:
                    first = ""

            surname = self.roll_name(NameColumn.SURNAME)
            return f"{first} {surname}".strip()


@dataclass
class CharacterAspectTable:
    """
    An aspect table for character generation.

    Aspect tables provide random results for various character attributes
    like background, demeanour, dress, etc. Each kindred has its own
    set of aspect tables with kindred-appropriate results.
    """
    table_id: str
    kindred: Kindred
    aspect_type: CharacterAspectType
    name: str
    die_type: DieType = DieType.D10
    entries: list[TableEntry] = field(default_factory=list)
    description: str = ""
    source_reference: str = ""

    def roll(self) -> tuple[int, TableEntry]:
        """
        Roll on this aspect table.

        Returns:
            Tuple of (roll_total, matching_entry)
        """
        die_size = int(self.die_type.value[1:])
        roll = DiceRoller.roll(f"1d{die_size}", "aspect table roll").total

        for entry in self.entries:
            if entry.matches_roll(roll):
                return roll, entry

        # Fallback
        if self.entries:
            return roll, self.entries[-1]
        return roll, TableEntry(roll_min=roll, roll_max=roll, result="No result")


@dataclass
class CharacterAspectResult:
    """Result of rolling on a character aspect table."""
    kindred: Kindred
    aspect_type: CharacterAspectType
    roll: int
    result: str
    entry: Optional[TableEntry] = None

    def __str__(self) -> str:
        return f"{self.aspect_type.value}: {self.result}"


@dataclass
class GeneratedCharacterAspects:
    """
    Complete set of generated character aspects.

    Contains all rolled aspects for a character of a specific kindred.
    """
    kindred: Kindred
    name: str = ""
    gender: Optional[str] = None

    # Rolled aspects
    background: Optional[CharacterAspectResult] = None
    trinket: Optional[CharacterAspectResult] = None
    head: Optional[CharacterAspectResult] = None
    demeanour: Optional[CharacterAspectResult] = None
    desires: Optional[CharacterAspectResult] = None
    face: Optional[CharacterAspectResult] = None
    dress: Optional[CharacterAspectResult] = None
    beliefs: Optional[CharacterAspectResult] = None
    fur_body: Optional[CharacterAspectResult] = None
    speech: Optional[CharacterAspectResult] = None

    def get_aspect(self, aspect_type: CharacterAspectType) -> Optional[CharacterAspectResult]:
        """Get a specific aspect result."""
        aspect_map = {
            CharacterAspectType.BACKGROUND: self.background,
            CharacterAspectType.TRINKET: self.trinket,
            CharacterAspectType.HEAD: self.head,
            CharacterAspectType.DEMEANOUR: self.demeanour,
            CharacterAspectType.DESIRES: self.desires,
            CharacterAspectType.FACE: self.face,
            CharacterAspectType.DRESS: self.dress,
            CharacterAspectType.BELIEFS: self.beliefs,
            CharacterAspectType.FUR_BODY: self.fur_body,
            CharacterAspectType.SPEECH: self.speech,
        }
        return aspect_map.get(aspect_type)

    def set_aspect(self, aspect_type: CharacterAspectType, result: CharacterAspectResult) -> None:
        """Set a specific aspect result."""
        if aspect_type == CharacterAspectType.BACKGROUND:
            self.background = result
        elif aspect_type == CharacterAspectType.TRINKET:
            self.trinket = result
        elif aspect_type == CharacterAspectType.HEAD:
            self.head = result
        elif aspect_type == CharacterAspectType.DEMEANOUR:
            self.demeanour = result
        elif aspect_type == CharacterAspectType.DESIRES:
            self.desires = result
        elif aspect_type == CharacterAspectType.FACE:
            self.face = result
        elif aspect_type == CharacterAspectType.DRESS:
            self.dress = result
        elif aspect_type == CharacterAspectType.BELIEFS:
            self.beliefs = result
        elif aspect_type == CharacterAspectType.FUR_BODY:
            self.fur_body = result
        elif aspect_type == CharacterAspectType.SPEECH:
            self.speech = result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for display or serialization."""
        result = {
            "kindred": self.kindred.value,
            "name": self.name,
        }
        if self.gender:
            result["gender"] = self.gender

        for aspect_type in CharacterAspectType:
            if aspect_type == CharacterAspectType.NAME:
                continue  # Name handled separately
            aspect = self.get_aspect(aspect_type)
            if aspect:
                result[aspect_type.value] = aspect.result

        return result

    def describe(self) -> str:
        """Get a formatted description of the character."""
        lines = [
            f"Name: {self.name}",
            f"Kindred: {self.kindred.value.title()}",
        ]
        if self.gender:
            lines.append(f"Gender: {self.gender.title()}")
        lines.append("")

        aspect_order = [
            CharacterAspectType.BACKGROUND,
            CharacterAspectType.HEAD,
            CharacterAspectType.FACE,
            CharacterAspectType.FUR_BODY,
            CharacterAspectType.DRESS,
            CharacterAspectType.DEMEANOUR,
            CharacterAspectType.SPEECH,
            CharacterAspectType.BELIEFS,
            CharacterAspectType.DESIRES,
            CharacterAspectType.TRINKET,
        ]

        for aspect_type in aspect_order:
            aspect = self.get_aspect(aspect_type)
            if aspect:
                label = aspect_type.value.replace("_", " ").title()
                lines.append(f"{label}: {aspect.result}")

        return "\n".join(lines)


# =============================================================================
# ENCOUNTER TABLES
# =============================================================================


class EncounterTableCategory(str, Enum):
    """Categories of encounter tables for eligibility determination."""
    COMMON = "common"              # Common wilderness encounters
    HEX_SPECIFIC = "hex_specific"  # Specific to a hex
    REGIONAL = "regional"          # Regional wilderness table
    SEASONAL = "seasonal"          # Season-specific encounters (including unseasons)
    SETTLEMENT = "settlement"      # Settlement encounters (day/night)
    FAIRY_ROAD = "fairy_road"      # Fairy road only


class NestedTableConditionType(str, Enum):
    """Types of conditions for selecting nested sub-tables."""
    TIME_OF_DAY = "time_of_day"      # Day vs night
    ON_ROAD = "on_road"              # Traveling on road vs wild
    HAS_FIRE = "has_fire"            # Fire present (for night encounters)
    TERRAIN = "terrain"              # Terrain type
    WEATHER = "weather"              # Weather conditions
    CUSTOM = "custom"                # Custom condition


@dataclass
class NestedTableCondition:
    """
    A condition for selecting a nested sub-table.

    Used when a parent table contains multiple sub-tables
    selected based on situational conditions.
    """
    condition_type: NestedTableConditionType
    condition_value: Any              # The value to match (e.g., "day", True)
    condition_label: str = ""         # Human-readable label for the condition

    def matches(self, context: "EncounterTableContext") -> bool:
        """Check if this condition matches the given context."""
        if self.condition_type == NestedTableConditionType.TIME_OF_DAY:
            if self.condition_value == "day":
                return context.time_of_day in [
                    EncounterTimeOfDay.DAY, EncounterTimeOfDay.DAWN
                ]
            elif self.condition_value == "night":
                return context.time_of_day in [
                    EncounterTimeOfDay.NIGHT, EncounterTimeOfDay.DUSK
                ]
            return str(context.time_of_day.value) == str(self.condition_value)

        elif self.condition_type == NestedTableConditionType.ON_ROAD:
            return context.on_road == self.condition_value

        elif self.condition_type == NestedTableConditionType.HAS_FIRE:
            return context.has_fire == self.condition_value

        elif self.condition_type == NestedTableConditionType.TERRAIN:
            return context.terrain_type == self.condition_value

        elif self.condition_type == NestedTableConditionType.WEATHER:
            return context.weather == self.condition_value

        # Custom conditions use extra_conditions dict
        elif self.condition_type == NestedTableConditionType.CUSTOM:
            return context.extra_conditions.get(
                self.condition_label, None
            ) == self.condition_value

        return False


@dataclass
class EncounterTableContext:
    """
    Context for selecting and rolling on encounter tables.

    Used to determine which encounter table(s) apply and
    any modifiers to the roll.
    """
    # Location context
    location_type: EncounterLocationType = EncounterLocationType.WILDERNESS
    hex_id: Optional[str] = None
    settlement: Optional[DolmenwoodSettlement] = None
    region: Optional[DolmenwoodRegion] = None
    on_fairy_road: bool = False

    # Time context
    time_of_day: EncounterTimeOfDay = EncounterTimeOfDay.ANY
    season: EncounterSeason = EncounterSeason.ANY
    is_unseason: bool = False

    # Situational conditions (for nested table selection)
    on_road: bool = False              # Traveling on a road
    has_fire: bool = False             # Fire/light source present
    terrain_type: Optional[str] = None # Current terrain
    weather: Optional[str] = None      # Current weather

    # Extra conditions for custom nested table logic
    extra_conditions: dict[str, Any] = field(default_factory=dict)

    # Modifiers
    stealth_modifier: int = 0          # Party attempting stealth
    noise_modifier: int = 0            # Party making noise
    light_modifier: int = 0            # Light sources at night

    def matches_table(
        self,
        table_location: EncounterLocationType,
        table_time: EncounterTimeOfDay,
        table_season: EncounterSeason,
        table_settlement: Optional[DolmenwoodSettlement] = None,
        table_region: Optional[DolmenwoodRegion] = None
    ) -> bool:
        """Check if this context matches a table's requirements."""
        # Check location type
        if table_location != self.location_type:
            if table_location != EncounterLocationType.WILDERNESS:
                return False

        # Check settlement
        if table_settlement is not None:
            if self.settlement != table_settlement:
                return False

        # Check region
        if table_region is not None and table_region != DolmenwoodRegion.ANY:
            if self.region != table_region:
                return False

        # Check time of day
        if table_time != EncounterTimeOfDay.ANY:
            if self.time_of_day != table_time:
                # Day/night don't match
                if not (table_time == EncounterTimeOfDay.DAY and
                        self.time_of_day in [EncounterTimeOfDay.DAWN, EncounterTimeOfDay.DAY]):
                    if not (table_time == EncounterTimeOfDay.NIGHT and
                            self.time_of_day in [EncounterTimeOfDay.DUSK, EncounterTimeOfDay.NIGHT]):
                        return False

        # Check season
        if table_season != EncounterSeason.ANY:
            if self.season != table_season:
                return False

        return True


@dataclass
class EncounterEntry:
    """
    A single entry in an encounter table.

    Extends TableEntry with encounter-specific fields.
    """
    # Roll range
    roll_min: int
    roll_max: int

    # Result
    result: str
    result_type: EncounterResultType = EncounterResultType.MONSTER

    # References
    monster_refs: list[str] = field(default_factory=list)
    npc_refs: list[str] = field(default_factory=list)
    number_appearing: Optional[str] = None  # Dice notation

    # Sub-tables
    sub_table: Optional[str] = None         # Reference to another table
    regional_table: bool = False            # Roll on regional table instead

    # Behavioral hints
    activity: Optional[str] = None          # What the encounter is doing
    disposition: Optional[str] = None       # Starting attitude

    # Special flags
    is_lair: bool = False
    is_special: bool = False

    def matches_roll(self, roll: int) -> bool:
        """Check if a roll value falls within this entry's range."""
        return self.roll_min <= roll <= self.roll_max


@dataclass
class NestedTableSelector:
    """
    Defines a nested sub-table with its selection conditions.

    Used when a parent table contains multiple sub-tables that are
    selected based on situational conditions (time of day, on road, etc.).
    """
    conditions: list[NestedTableCondition]  # All must match for this table
    table: "EncounterTable"                  # The nested table to use

    def matches(self, context: EncounterTableContext) -> bool:
        """Check if all conditions match the given context."""
        return all(cond.matches(context) for cond in self.conditions)


@dataclass
class EncounterTable:
    """
    An encounter table for a specific location/time/season combination.

    Supports:
    - Variable length tables (any die type, any number of entries)
    - Nested conditional tables (sub-tables selected by conditions)
    - Equal probability selection among eligible wilderness tables
    - Exclusive table types (fairy road, settlement)
    """
    table_id: str
    name: str

    # Table classification
    location_type: EncounterLocationType
    category: EncounterTableCategory = EncounterTableCategory.COMMON
    time_of_day: EncounterTimeOfDay = EncounterTimeOfDay.ANY
    season: EncounterSeason = EncounterSeason.ANY

    # Specific location (if applicable)
    settlement: Optional[DolmenwoodSettlement] = None
    region: Optional[DolmenwoodRegion] = None
    hex_id: Optional[str] = None

    # Die configuration - supports any die type for variable length
    die_type: DieType = DieType.D12
    num_dice: int = 1

    # Entries (for leaf tables that have actual results)
    entries: list[EncounterEntry] = field(default_factory=list)

    # Nested tables (for container tables with conditional sub-tables)
    nested_tables: list[NestedTableSelector] = field(default_factory=list)
    is_container: bool = False  # True if this only contains nested tables

    # Metadata
    description: str = ""
    source_reference: str = ""
    page_number: Optional[int] = None

    def get_max_roll(self) -> int:
        """Get the maximum possible roll for this table."""
        die_size = int(self.die_type.value[1:])
        return self.num_dice * die_size

    def get_min_roll(self) -> int:
        """Get the minimum possible roll for this table."""
        return self.num_dice

    def get_nested_table(self, context: EncounterTableContext) -> Optional["EncounterTable"]:
        """
        Get the appropriate nested table for the given context.

        Returns None if no nested table matches or this isn't a container.
        """
        if not self.is_container or not self.nested_tables:
            return None

        for selector in self.nested_tables:
            if selector.matches(context):
                return selector.table

        return None

    def roll(self, context: Optional[EncounterTableContext] = None) -> tuple[int, EncounterEntry]:
        """
        Roll on this encounter table.

        If this is a container table, selects the appropriate nested table
        based on context and rolls on that instead.
        """
        # If container table, delegate to nested table
        if self.is_container and context:
            nested = self.get_nested_table(context)
            if nested:
                return nested.roll(context)

        die_size = int(self.die_type.value[1:])
        dice_result = DiceRoller.roll(f"{self.num_dice}d{die_size}", "encounter table roll")
        total = dice_result.total

        for entry in self.entries:
            if entry.matches_roll(total):
                return total, entry

        # Fallback
        if self.entries:
            return total, self.entries[-1]

        return total, EncounterEntry(
            roll_min=total, roll_max=total,
            result="No encounter", result_type=EncounterResultType.SPECIAL
        )

    def matches_context(self, context: EncounterTableContext) -> bool:
        """Check if this table applies to the given context."""
        return context.matches_table(
            table_location=self.location_type,
            table_time=self.time_of_day,
            table_season=self.season,
            table_settlement=self.settlement,
            table_region=self.region
        )

    def is_eligible_for_context(self, context: EncounterTableContext) -> bool:
        """
        Check if this table is eligible for random selection in the given context.

        This is different from matches_context - it checks category-specific
        eligibility rules for the equal-probability selection system.
        """
        # Fairy road tables only eligible on fairy roads
        if self.category == EncounterTableCategory.FAIRY_ROAD:
            return context.on_fairy_road

        # Settlement tables only eligible in that settlement
        if self.category == EncounterTableCategory.SETTLEMENT:
            if context.location_type != EncounterLocationType.SETTLEMENT:
                return False
            return self.settlement == context.settlement

        # For wilderness encounters, check various eligibility
        if context.location_type != EncounterLocationType.WILDERNESS:
            return False

        # Common tables are always eligible in wilderness
        if self.category == EncounterTableCategory.COMMON:
            return True

        # Hex-specific tables only eligible in their hex
        if self.category == EncounterTableCategory.HEX_SPECIFIC:
            return self.hex_id == context.hex_id

        # Regional tables eligible in their region
        if self.category == EncounterTableCategory.REGIONAL:
            return self.region == context.region

        # Seasonal tables eligible during their season
        if self.category == EncounterTableCategory.SEASONAL:
            return self.season == context.season

        return False


@dataclass
class EncounterResult:
    """Complete result of an encounter roll."""
    table_id: str
    table_name: str

    # Roll details
    roll: int
    entry: EncounterEntry

    # Context
    location_type: EncounterLocationType
    time_of_day: EncounterTimeOfDay
    season: EncounterSeason

    # Resolved details
    description: str = ""
    monsters: list[str] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)
    number_appearing_rolled: Optional[int] = None

    # Sub-results (if regional table was rolled)
    sub_result: Optional["EncounterResult"] = None

    def describe(self) -> str:
        """Get a formatted description of the encounter."""
        lines = [
            f"[{self.table_name}] Roll: {self.roll}",
            f"Result: {self.entry.result}",
        ]

        if self.entry.result_type != EncounterResultType.SPECIAL:
            lines.append(f"Type: {self.entry.result_type.value}")

        if self.number_appearing_rolled:
            lines.append(f"Number Appearing: {self.number_appearing_rolled}")

        if self.entry.activity:
            lines.append(f"Activity: {self.entry.activity}")

        if self.sub_result:
            lines.append("")
            lines.append("Sub-table result:")
            lines.append(self.sub_result.describe())

        return "\n".join(lines)


# =============================================================================
# TREASURE TABLES
# =============================================================================


class TreasureTableCategory(str, Enum):
    """Categories of treasure tables for organization."""
    # Main treasure tables (p.393)
    COINS = "coins"                        # Coin quantities
    RICHES = "riches"                      # Gems, jewelry, art
    MAGIC_ITEM = "magic_item"              # Magic item determination
    MAGIC_ITEM_TYPE = "magic_item_type"    # Type of magic item

    # Detail tables for gems/jewelry/art (p.394)
    GEM_VALUE = "gem_value"
    GEM_TYPE = "gem_type"
    JEWELRY = "jewelry"
    ART_OBJECT = "art_object"
    PRECIOUS_MATERIAL = "precious_material"
    EMBELLISHMENT = "embellishment"
    PROVENANCE = "provenance"

    # Magic item detail tables - Amulet/Talisman (p.398)
    AMULET_TALISMAN = "amulet_talisman"
    AMULET_APPEARANCE = "amulet_appearance"

    # Magic item detail tables - Armour (p.400)
    ARMOUR_TYPE = "armour_type"
    ARMOUR_ENCHANTMENT = "armour_enchantment"
    ARMOUR_SPECIAL_POWER = "armour_special_power"
    ARMOUR_ODDITY = "armour_oddity"

    # Magic item detail tables - Magic Garments
    MAGIC_GARMENT = "magic_garment"

    # Magic item detail tables - Instrument (p.408)
    INSTRUMENT_TYPE = "instrument_type"
    INSTRUMENT_ENCHANTMENT = "instrument_enchantment"

    # Magic item detail tables - Ring (p.410)
    RING = "ring"
    RING_APPEARANCE = "ring_appearance"

    # Magic item detail tables - Weapon (p.412)
    WEAPON_TYPE = "weapon_type"
    WEAPON_ENCHANTMENT = "weapon_enchantment"
    WEAPON_SPECIAL_POWER = "weapon_special_power"
    WEAPON_ODDITY = "weapon_oddity"

    # Magic item detail tables - Rod/Staff/Wand (p.416)
    ROD = "rod"
    STAFF = "staff"
    WAND = "wand"
    ROD_APPEARANCE = "rod_appearance"
    STAFF_APPEARANCE = "staff_appearance"
    WAND_APPEARANCE = "wand_appearance"
    ROD_POWER = "rod_power"
    STAFF_POWER = "staff_power"
    WAND_SPELL = "wand_spell"

    # Magic item detail tables - Scroll/Book (p.418-419)
    SPELL_BOOK = "spell_book"
    SPELL_BOOK_APPEARANCE = "spell_book_appearance"
    SPELL_SCROLL = "spell_scroll"
    SPELL_SCROLL_COUNT = "spell_scroll_count"
    SPELL_SCROLL_RANK = "spell_scroll_rank"
    SCROLL_LANGUAGE = "scroll_language"

    # Magic item detail tables - Potions
    POTION = "potion"

    # Magic item detail tables - Crystals, Balms/Oils
    MAGIC_CRYSTAL = "magic_crystal"
    MAGIC_BALM_OIL = "magic_balm_oil"

    # Magic item detail tables - Wondrous Items
    WONDROUS_ITEM = "wondrous_item"

    # Arcane trade goods (p.423)
    ARCANE_TRADE_GOODS = "arcane_trade_goods"


class TreasureType(str, Enum):
    """Types of treasure items."""
    COINS = "coins"
    GEMS = "gems"
    JEWELRY = "jewelry"
    ART_OBJECT = "art_object"
    MAGIC_ITEM = "magic_item"


class CoinType(str, Enum):
    """Types of coins in Dolmenwood."""
    COPPER = "cp"
    SILVER = "sp"
    GOLD = "gp"
    PELLUCIDIUM = "pp"  # Dolmenwood-specific precious coin


class MagicItemCategory(str, Enum):
    """Categories of magic items in Dolmenwood."""
    ARMOUR = "armour"
    AMULET_TALISMAN = "amulet_talisman"
    WEAPON = "weapon"
    RING = "ring"
    ROD = "rod"
    STAFF = "staff"
    WAND = "wand"
    SPELL_BOOK = "spell_book"
    SPELL_SCROLL = "spell_scroll"
    MAGIC_GARMENT = "magic_garment"
    POTION = "potion"
    MAGIC_CRYSTAL = "magic_crystal"
    MAGIC_BALM_OIL = "magic_balm_oil"
    WONDROUS_ITEM = "wondrous_item"


@dataclass
class TreasureEntry:
    """
    A single entry in a treasure table.

    Supports variable roll ranges and references to sub-tables.
    """
    # Roll range (inclusive)
    roll_min: int
    roll_max: int

    # Result
    result: str
    result_type: TreasureType = TreasureType.COINS

    # Value (for gems, jewelry, art)
    value_gp: Optional[int] = None           # Base value in gold pieces
    value_dice: Optional[str] = None         # Dice notation for value

    # Magic item specifics
    magic_item_category: Optional[MagicItemCategory] = None
    magic_item_ref: Optional[str] = None     # Specific magic item ID

    # Sub-tables for further detail
    sub_table: Optional[str] = None          # Reference to another table
    sub_tables: list[str] = field(default_factory=list)  # Multiple sub-tables

    # Quantity (if this entry can appear multiple times)
    quantity_dice: Optional[str] = None      # e.g., "1d6" gems

    # Coin type (for coin entries)
    coin_type: Optional[CoinType] = None
    coin_multiplier: int = 1                 # e.g., x1000 for "1d6 x 1000cp"

    # Descriptive details
    description: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)

    def matches_roll(self, roll: int) -> bool:
        """Check if a roll value falls within this entry's range."""
        return self.roll_min <= roll <= self.roll_max


@dataclass
class TreasureTableContext:
    """
    Context for treasure generation.

    Provides information about the source of treasure
    and any modifiers to treasure rolls.
    """
    # Source context
    treasure_type_code: Optional[str] = None  # e.g., "A", "B", "H" etc.
    source_monster: Optional[str] = None      # Monster that dropped it
    source_location: Optional[str] = None     # Where treasure was found

    # Modifiers
    value_multiplier: float = 1.0             # Multiply all values
    quantity_modifier: int = 0                # Add to quantity rolls
    magic_item_bonus: int = 0                 # Bonus to magic item chance

    # Extra conditions for nested table selection
    extra_conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class TreasureNestedTableSelector:
    """
    Defines a nested sub-table with its selection conditions.

    Used when a treasure table has conditional sub-tables
    (e.g., different tables based on item type).
    """
    conditions: dict[str, Any]               # Conditions to match
    table_id: str                            # The table to use when matched

    def matches(self, context: TreasureTableContext) -> bool:
        """Check if all conditions match the given context."""
        for key, value in self.conditions.items():
            if context.extra_conditions.get(key) != value:
                return False
        return True


@dataclass
class TreasureTable:
    """
    A treasure table for random treasure determination.

    Supports:
    - Variable length tables (any die type, any number of entries)
    - Nested conditional tables (sub-tables for detail)
    - Percentage chance rolls
    - Quantity dice rolls
    """
    table_id: str
    name: str
    category: TreasureTableCategory

    # Die configuration - supports any die type for variable length
    die_type: DieType = DieType.D100
    num_dice: int = 1

    # Entries (for tables with actual results)
    entries: list[TreasureEntry] = field(default_factory=list)

    # Nested tables (for container tables with conditional sub-tables)
    nested_tables: list[TreasureNestedTableSelector] = field(default_factory=list)
    is_container: bool = False

    # Metadata
    description: str = ""
    source_reference: str = "Campaign Book"
    page_number: Optional[int] = None

    def get_max_roll(self) -> int:
        """Get the maximum possible roll for this table."""
        die_size = int(self.die_type.value[1:])
        return self.num_dice * die_size

    def get_min_roll(self) -> int:
        """Get the minimum possible roll for this table."""
        return self.num_dice

    def roll(self, context: Optional[TreasureTableContext] = None) -> tuple[int, TreasureEntry]:
        """
        Roll on this treasure table.

        If this is a container table, selects the appropriate nested table
        based on context and rolls on that instead.
        """
        die_size = int(self.die_type.value[1:])
        dice_result = DiceRoller.roll(f"{self.num_dice}d{die_size}", "treasure table roll")
        total = dice_result.total

        for entry in self.entries:
            if entry.matches_roll(total):
                return total, entry

        # Fallback
        if self.entries:
            return total, self.entries[-1]

        return total, TreasureEntry(
            roll_min=total, roll_max=total,
            result="No treasure"
        )


@dataclass
class TreasureComponent:
    """
    A component of a treasure type with chance and quantity.

    Represents one line in a treasure type definition, e.g.:
    "25% chance of 1d6 x 1000 cp"
    """
    treasure_type: TreasureType
    chance_percent: int                      # Percentage chance (roll d100)
    quantity_dice: str                       # Dice for quantity, e.g., "1d6"
    multiplier: int = 1                      # e.g., x1000 for coins

    # For coins
    coin_type: Optional[CoinType] = None

    # For gems, jewelry, art - reference detail table
    detail_table: Optional[str] = None

    # For magic items
    magic_item_category: Optional[MagicItemCategory] = None
    specific_table: Optional[str] = None     # Specific magic item table

    def roll_present(self) -> bool:
        """Roll to see if this component is present."""
        return DiceRoller.percent_check(self.chance_percent, "treasure component check")


@dataclass
class GeneratedTreasureItem:
    """A single generated treasure item with all details."""
    treasure_type: TreasureType
    quantity: int = 1

    # For coins
    coin_type: Optional[CoinType] = None
    coin_value: int = 0                      # Total coin value

    # For gems/jewelry/art
    item_name: Optional[str] = None
    base_value_gp: int = 0
    material: Optional[str] = None
    embellishment: Optional[str] = None
    provenance: Optional[str] = None

    # For magic items
    magic_item_category: Optional[MagicItemCategory] = None
    magic_item_name: Optional[str] = None
    enchantment: Optional[str] = None
    special_powers: list[str] = field(default_factory=list)
    oddities: list[str] = field(default_factory=list)
    appearance: Optional[str] = None

    # Roll history for reference
    rolls: dict[str, int] = field(default_factory=dict)
    sub_results: list["GeneratedTreasureItem"] = field(default_factory=list)

    def total_value_gp(self) -> int:
        """Calculate total value in gold pieces."""
        if self.treasure_type == TreasureType.COINS:
            # Convert coins to GP (Dolmenwood rates: 10cp=1sp, 10sp=1gp, 5gp=1pp)
            conversion = {
                CoinType.COPPER: 0.01,      # 100 cp = 1 gp
                CoinType.SILVER: 0.1,       # 10 sp = 1 gp
                CoinType.GOLD: 1.0,         # 1 gp = 1 gp
                CoinType.PELLUCIDIUM: 5.0,  # 1 pp = 5 gp
            }
            if self.coin_type:
                return int(self.coin_value * conversion.get(self.coin_type, 1.0))
            return self.coin_value
        return self.base_value_gp * self.quantity

    def describe(self) -> str:
        """Get a formatted description of this treasure item."""
        if self.treasure_type == TreasureType.COINS:
            return f"{self.coin_value:,} {self.coin_type.value if self.coin_type else 'coins'}"

        elif self.treasure_type == TreasureType.GEMS:
            desc = f"{self.quantity}x Gem"
            if self.item_name:
                desc = f"{self.quantity}x {self.item_name}"
            desc += f" ({self.base_value_gp} gp each)"
            return desc

        elif self.treasure_type in [TreasureType.JEWELRY, TreasureType.ART_OBJECT]:
            desc = self.item_name or self.treasure_type.value
            if self.material:
                desc = f"{self.material} {desc}"
            if self.embellishment:
                desc += f" with {self.embellishment}"
            if self.provenance:
                desc += f" ({self.provenance})"
            desc += f" - {self.base_value_gp} gp"
            return desc

        elif self.treasure_type == TreasureType.MAGIC_ITEM:
            desc = self.magic_item_name or "Magic Item"
            if self.enchantment:
                desc += f" ({self.enchantment})"
            if self.special_powers:
                desc += f" [Powers: {', '.join(self.special_powers)}]"
            return desc

        return f"{self.quantity}x {self.item_name or self.treasure_type.value}"


@dataclass
class TreasureResult:
    """Complete result of treasure generation."""
    treasure_type_code: Optional[str] = None  # The treasure type rolled

    # Generated items by type
    coins: list[GeneratedTreasureItem] = field(default_factory=list)
    gems: list[GeneratedTreasureItem] = field(default_factory=list)
    jewelry: list[GeneratedTreasureItem] = field(default_factory=list)
    art_objects: list[GeneratedTreasureItem] = field(default_factory=list)
    magic_items: list[GeneratedTreasureItem] = field(default_factory=list)

    # Roll history
    component_rolls: dict[str, bool] = field(default_factory=dict)  # Which components were present

    def total_value_gp(self) -> int:
        """Calculate total treasure value in gold pieces."""
        total = 0
        for items in [self.coins, self.gems, self.jewelry, self.art_objects]:
            for item in items:
                total += item.total_value_gp()
        # Magic items don't have standard GP value
        return total

    def describe(self) -> str:
        """Get a formatted description of all treasure."""
        lines = []

        if self.treasure_type_code:
            lines.append(f"Treasure Type {self.treasure_type_code}")
            lines.append("")

        if self.coins:
            lines.append("Coins:")
            for item in self.coins:
                lines.append(f"  {item.describe()}")

        if self.gems:
            lines.append("Gems:")
            for item in self.gems:
                lines.append(f"  {item.describe()}")

        if self.jewelry:
            lines.append("Jewelry:")
            for item in self.jewelry:
                lines.append(f"  {item.describe()}")

        if self.art_objects:
            lines.append("Art Objects:")
            for item in self.art_objects:
                lines.append(f"  {item.describe()}")

        if self.magic_items:
            lines.append("Magic Items:")
            for item in self.magic_items:
                lines.append(f"  {item.describe()}")

        if not any([self.coins, self.gems, self.jewelry, self.art_objects, self.magic_items]):
            lines.append("No treasure found.")

        lines.append("")
        lines.append(f"Total Value: {self.total_value_gp():,} gp (excluding magic items)")

        return "\n".join(lines)


# =============================================================================
# DATABASE-DRIVEN ROLL TABLE SYSTEM
# =============================================================================
# All game tables (character, encounter, treasure, rumor, dungeon, flavor, etc.)
# are stored as JSON files and loaded into SQLite/ChromaDB databases.
# These structures support loading and rolling against tables from the database.


class RollTableType(str, Enum):
    """Types of roll tables in the game system."""
    # Character tables
    CHARACTER_NAME = "character_name"
    CHARACTER_ASPECT = "character_aspect"
    CHARACTER_BACKGROUND = "character_background"

    # Encounter tables
    ENCOUNTER_COMMON = "encounter_common"
    ENCOUNTER_REGIONAL = "encounter_regional"
    ENCOUNTER_SETTLEMENT = "encounter_settlement"
    ENCOUNTER_FAIRY_ROAD = "encounter_fairy_road"
    ENCOUNTER_SEASONAL = "encounter_seasonal"
    ENCOUNTER_HEX = "encounter_hex"

    # Treasure tables
    TREASURE_COINS = "treasure_coins"
    TREASURE_RICHES = "treasure_riches"
    TREASURE_MAGIC_ITEM = "treasure_magic_item"
    TREASURE_GEM = "treasure_gem"
    TREASURE_JEWELRY = "treasure_jewelry"
    TREASURE_ART = "treasure_art"

    # Magic item detail tables
    MAGIC_ITEM_DETAIL = "magic_item_detail"

    # Rumor tables
    RUMOR = "rumor"

    # Dungeon tables
    DUNGEON_ROOM = "dungeon_room"
    DUNGEON_FEATURE = "dungeon_feature"
    DUNGEON_HAZARD = "dungeon_hazard"

    # Flavor/Atmosphere tables
    FLAVOR = "flavor"
    WEATHER = "weather"
    NPC_REACTION = "npc_reaction"

    # Generic
    CUSTOM = "custom"


@dataclass
class RollTableEntry:
    """
    A single entry in a database-loaded roll table.

    This is a generic structure that can represent any table entry
    loaded from JSON and stored in the database.
    """
    # Roll range (inclusive)
    roll_min: int
    roll_max: int

    # Primary result
    result: str

    # Optional structured data (loaded from JSON)
    data: dict[str, Any] = field(default_factory=dict)

    # Sub-table references (table_id strings)
    sub_tables: list[str] = field(default_factory=list)

    # Dice expressions for quantities, values, etc.
    dice_expressions: dict[str, str] = field(default_factory=dict)

    def matches_roll(self, roll: int) -> bool:
        """Check if a roll value falls within this entry's range."""
        return self.roll_min <= roll <= self.roll_max

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get a value from the data dictionary."""
        return self.data.get(key, default)

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> "RollTableEntry":
        """Create a RollTableEntry from JSON data."""
        return cls(
            roll_min=json_data.get("roll_min", 1),
            roll_max=json_data.get("roll_max", 1),
            result=json_data.get("result", ""),
            data=json_data.get("data", {}),
            sub_tables=json_data.get("sub_tables", []),
            dice_expressions=json_data.get("dice", {}),
        )

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "roll_min": self.roll_min,
            "roll_max": self.roll_max,
            "result": self.result,
            "data": self.data,
            "sub_tables": self.sub_tables,
            "dice": self.dice_expressions,
        }


@dataclass
class RollTableMetadata:
    """
    Metadata for a roll table stored in the database.

    Contains information about the table but not the entries themselves.
    """
    table_id: str                          # Unique identifier
    name: str                              # Human-readable name
    table_type: RollTableType              # Type classification

    # Die configuration
    die_type: str = "d20"                  # e.g., "d6", "d8", "d12", "d100"
    num_dice: int = 1

    # Source reference
    source_book: str = "Campaign Book"
    page_number: Optional[int] = None

    # Category for filtering/organization
    category: Optional[str] = None         # e.g., "regional", "settlement"
    subcategory: Optional[str] = None      # e.g., "aldweald", "prigwort"

    # Conditions for table applicability
    conditions: dict[str, Any] = field(default_factory=dict)

    # Nested table configuration
    is_container: bool = False             # True if contains conditional sub-tables
    nested_conditions: list[dict[str, Any]] = field(default_factory=list)

    # Description
    description: str = ""

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> "RollTableMetadata":
        """Create RollTableMetadata from JSON data."""
        return cls(
            table_id=json_data.get("table_id", ""),
            name=json_data.get("name", ""),
            table_type=RollTableType(json_data.get("table_type", "custom")),
            die_type=json_data.get("die_type", "d20"),
            num_dice=json_data.get("num_dice", 1),
            source_book=json_data.get("source_book", "Campaign Book"),
            page_number=json_data.get("page_number"),
            category=json_data.get("category"),
            subcategory=json_data.get("subcategory"),
            conditions=json_data.get("conditions", {}),
            is_container=json_data.get("is_container", False),
            nested_conditions=json_data.get("nested_conditions", []),
            description=json_data.get("description", ""),
        )

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "table_id": self.table_id,
            "name": self.name,
            "table_type": self.table_type.value,
            "die_type": self.die_type,
            "num_dice": self.num_dice,
            "source_book": self.source_book,
            "page_number": self.page_number,
            "category": self.category,
            "subcategory": self.subcategory,
            "conditions": self.conditions,
            "is_container": self.is_container,
            "nested_conditions": self.nested_conditions,
            "description": self.description,
        }


@dataclass
class RollTable:
    """
    A complete roll table with metadata and entries.

    This is the primary structure for database-loaded tables.
    Entries can be loaded lazily from the database as needed.
    """
    metadata: RollTableMetadata
    entries: list[RollTableEntry] = field(default_factory=list)

    # Database reference (for lazy loading)
    _entries_loaded: bool = field(default=False, repr=False)

    @property
    def table_id(self) -> str:
        return self.metadata.table_id

    @property
    def name(self) -> str:
        return self.metadata.name

    def get_die_size(self) -> int:
        """Get the die size from the die_type string."""
        die_type = self.metadata.die_type.lower()
        if die_type.startswith('d'):
            return int(die_type[1:])
        return 20  # Default

    def get_max_roll(self) -> int:
        """Get the maximum possible roll for this table."""
        return self.metadata.num_dice * self.get_die_size()

    def get_min_roll(self) -> int:
        """Get the minimum possible roll for this table."""
        return self.metadata.num_dice

    def roll(self) -> tuple[int, Optional[RollTableEntry]]:
        """
        Roll on this table and return the result.

        Returns (roll_value, entry) or (roll_value, None) if no match.
        """
        die_size = self.get_die_size()
        dice_result = DiceRoller.roll(f"{self.metadata.num_dice}d{die_size}", "roll table")
        total = dice_result.total

        for entry in self.entries:
            if entry.matches_roll(total):
                return total, entry

        # Fallback to last entry if no match
        if self.entries:
            return total, self.entries[-1]

        return total, None

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> "RollTable":
        """Create a RollTable from JSON data."""
        metadata = RollTableMetadata.from_json(json_data.get("metadata", json_data))
        entries = [
            RollTableEntry.from_json(e)
            for e in json_data.get("entries", [])
        ]
        return cls(metadata=metadata, entries=entries, _entries_loaded=True)

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "metadata": self.metadata.to_json(),
            "entries": [e.to_json() for e in self.entries],
        }


@dataclass
class RollTableReference:
    """
    A lightweight reference to a table in the database.

    Used when you need to reference a table without loading all entries.
    """
    table_id: str
    table_type: RollTableType
    name: str = ""

    # Optional filter conditions for the reference
    conditions: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"TableRef({self.table_id})"


@dataclass
class RollResult:
    """
    The result of rolling on one or more tables.

    Captures the full roll history including any sub-table rolls.
    """
    table_id: str
    table_name: str
    roll: int
    entry: Optional[RollTableEntry]

    # Sub-results from referenced sub-tables
    sub_results: list["RollResult"] = field(default_factory=list)

    # Additional resolved data
    resolved_data: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        """Get a formatted description of this roll result."""
        lines = [f"[{self.table_name}] Roll: {self.roll}"]

        if self.entry:
            lines.append(f"Result: {self.entry.result}")

            # Add any extra data
            for key, value in self.entry.data.items():
                lines.append(f"  {key}: {value}")

        for sub in self.sub_results:
            lines.append("")
            lines.append("Sub-table:")
            lines.append(sub.describe())

        return "\n".join(lines)


# =============================================================================
# HEX-EMBEDDED ROLL TABLES
# =============================================================================
# Hex data stored in SQLite/ChromaDB contains embedded roll tables with a
# different format than standalone JSON tables. These classes parse that format.


class HexTableCategory(str, Enum):
    """
    Categories for hex-embedded roll tables.

    Used to distinguish between different types of tables found in hex data,
    so the system knows which tables to use for encounters vs dungeon exploration.
    """
    ENCOUNTER = "encounter"      # Wilderness/hex encounter tables
    DUNGEON_ROOM = "dungeon_room"  # Dungeon room/location tables
    DUNGEON_ENCOUNTER = "dungeon_encounter"  # Dungeon-specific encounters
    TREASURE = "treasure"        # Treasure tables
    EVENT = "event"              # Random event tables
    NPC = "npc"                  # NPC tables
    OTHER = "other"              # Miscellaneous tables


# Keywords used to infer table category from name
_ENCOUNTER_KEYWORDS = {"encounter", "encounters", "wandering", "random encounter"}
_DUNGEON_ROOM_KEYWORDS = {"room", "rooms", "location", "locations", "area", "areas", "chamber", "chambers"}
_TREASURE_KEYWORDS = {"treasure", "loot", "hoard"}
_EVENT_KEYWORDS = {"event", "events", "happening", "occurrence"}
_NPC_KEYWORDS = {"npc", "npcs", "character", "characters", "inhabitant", "inhabitants"}


@dataclass
class HexRollTableEntry:
    """
    An entry from a hex-embedded roll table.

    Hex tables use a different JSON format:
    - "roll" instead of "roll_min"/"roll_max"
    - "title" and "description" instead of "result"
    - Direct arrays for "monsters", "npcs", "items"
    - "mechanical_effect" for game rules
    - "sub_table" for inline text sub-tables
    """
    roll: int
    title: Optional[str] = None
    description: str = ""
    monsters: list[str] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    mechanical_effect: Optional[str] = None
    sub_table: Optional[str] = None  # Inline sub-table text

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> "HexRollTableEntry":
        """Parse a hex table entry from JSON."""
        return cls(
            roll=json_data.get("roll", 1),
            title=json_data.get("title"),
            description=json_data.get("description", ""),
            monsters=json_data.get("monsters", []),
            npcs=json_data.get("npcs", []),
            items=json_data.get("items", []),
            mechanical_effect=json_data.get("mechanical_effect"),
            sub_table=json_data.get("sub_table"),
        )

    def to_roll_table_entry(self) -> RollTableEntry:
        """Convert to standard RollTableEntry format."""
        # Build result string from title and description
        if self.title:
            result = f"{self.title}: {self.description}" if self.description else self.title
        else:
            result = self.description

        return RollTableEntry(
            roll_min=self.roll,
            roll_max=self.roll,
            result=result,
            data={
                "title": self.title,
                "description": self.description,
                "monsters": self.monsters,
                "npcs": self.npcs,
                "items": self.items,
                "mechanical_effect": self.mechanical_effect,
                "sub_table_text": self.sub_table,
            },
            sub_tables=[],
            dice_expressions={},
        )


def _infer_hex_table_category(name: str) -> HexTableCategory:
    """
    Infer the table category from the table name.

    Uses keyword matching to determine what type of table this is.
    """
    name_lower = name.lower().strip()

    # Check for encounter keywords first (most specific)
    for keyword in _ENCOUNTER_KEYWORDS:
        if keyword in name_lower:
            return HexTableCategory.ENCOUNTER

    # Check for dungeon room keywords
    for keyword in _DUNGEON_ROOM_KEYWORDS:
        if keyword in name_lower:
            return HexTableCategory.DUNGEON_ROOM

    # Check for treasure keywords
    for keyword in _TREASURE_KEYWORDS:
        if keyword in name_lower:
            return HexTableCategory.TREASURE

    # Check for event keywords
    for keyword in _EVENT_KEYWORDS:
        if keyword in name_lower:
            return HexTableCategory.EVENT

    # Check for NPC keywords
    for keyword in _NPC_KEYWORDS:
        if keyword in name_lower:
            return HexTableCategory.NPC

    # Default to OTHER
    return HexTableCategory.OTHER


@dataclass
class HexRollTable:
    """
    A roll table embedded in hex data.

    Found in hex JSON under:
    - hex.roll_tables[] (hex-level tables)
    - hex.points_of_interest[].roll_tables[] (POI-specific tables)

    The table_category field distinguishes between different types:
    - ENCOUNTER: Used for wilderness/hex encounter rolls
    - DUNGEON_ROOM: Used when exploring dungeons/POIs
    - DUNGEON_ENCOUNTER: Encounters specific to a dungeon
    - TREASURE, EVENT, NPC, OTHER: Other specialized tables
    """
    name: str
    die_type: str
    description: str = ""
    entries: list[HexRollTableEntry] = field(default_factory=list)

    # Context for where this table came from
    hex_id: Optional[str] = None
    poi_name: Optional[str] = None

    # Table category (inferred from name if not specified)
    table_category: HexTableCategory = HexTableCategory.OTHER

    @classmethod
    def from_json(
        cls,
        json_data: dict[str, Any],
        hex_id: Optional[str] = None,
        poi_name: Optional[str] = None
    ) -> "HexRollTable":
        """Parse a hex table from JSON."""
        entries = [
            HexRollTableEntry.from_json(e)
            for e in json_data.get("entries", [])
        ]

        name = json_data.get("name", "")

        # Get category from JSON or infer from name
        category_str = json_data.get("table_category", json_data.get("category"))
        if category_str:
            try:
                category = HexTableCategory(category_str)
            except ValueError:
                category = _infer_hex_table_category(name)
        else:
            category = _infer_hex_table_category(name)

        return cls(
            name=name,
            die_type=json_data.get("die_type", "d6"),
            description=json_data.get("description", ""),
            entries=entries,
            hex_id=hex_id,
            poi_name=poi_name,
            table_category=category,
        )

    def is_encounter_table(self) -> bool:
        """Check if this is an encounter table (for wilderness encounter rolls)."""
        return self.table_category == HexTableCategory.ENCOUNTER

    def is_dungeon_table(self) -> bool:
        """Check if this is a dungeon-related table."""
        return self.table_category in (
            HexTableCategory.DUNGEON_ROOM,
            HexTableCategory.DUNGEON_ENCOUNTER
        )

    def to_roll_table(self) -> RollTable:
        """Convert to standard RollTable format."""
        # Generate a unique table_id
        if self.poi_name:
            table_id = f"hex_{self.hex_id}_{self.poi_name}_{self.name}".lower().replace(" ", "_")
        elif self.hex_id:
            table_id = f"hex_{self.hex_id}_{self.name}".lower().replace(" ", "_")
        else:
            table_id = f"hex_{self.name}".lower().replace(" ", "_")

        # Map category to RollTableType
        if self.table_category == HexTableCategory.ENCOUNTER:
            table_type = RollTableType.ENCOUNTER_HEX
        elif self.table_category == HexTableCategory.DUNGEON_ROOM:
            table_type = RollTableType.CUSTOM  # Could add DUNGEON_ROOM type
        elif self.table_category == HexTableCategory.DUNGEON_ENCOUNTER:
            table_type = RollTableType.ENCOUNTER_HEX
        else:
            table_type = RollTableType.CUSTOM

        metadata = RollTableMetadata(
            table_id=table_id,
            name=self.name,
            table_type=table_type,
            die_type=self.die_type,
            num_dice=1,
            category=self.table_category.value,
            subcategory=self.hex_id,
            description=self.description,
            conditions={
                "hex_id": self.hex_id,
                "poi_name": self.poi_name,
                "table_category": self.table_category.value,
            },
        )

        entries = [e.to_roll_table_entry() for e in self.entries]

        return RollTable(metadata=metadata, entries=entries, _entries_loaded=True)

    def roll(self) -> tuple[int, Optional[HexRollTableEntry]]:
        """Roll on this table and return the result."""
        die_size = int(self.die_type.lower().replace('d', ''))
        roll_value = DiceRoller.roll(f"1d{die_size}", "hex table roll").total

        for entry in self.entries:
            if entry.roll == roll_value:
                return roll_value, entry

        # Fallback
        if self.entries:
            return roll_value, self.entries[-1]

        return roll_value, None


def parse_hex_roll_tables(hex_data: dict[str, Any]) -> list[HexRollTable]:
    """
    Extract all roll tables from hex data.

    Parses tables from:
    - hex_data["roll_tables"] (hex-level)
    - hex_data["points_of_interest"][*]["roll_tables"] (POI-level)

    Returns list of HexRollTable objects.
    """
    tables: list[HexRollTable] = []
    hex_id = hex_data.get("hex_id")

    # Hex-level tables
    for table_data in hex_data.get("roll_tables", []):
        tables.append(HexRollTable.from_json(table_data, hex_id=hex_id))

    # POI-level tables
    for poi in hex_data.get("points_of_interest", []):
        poi_name = poi.get("name", "unknown")
        for table_data in poi.get("roll_tables", []):
            tables.append(HexRollTable.from_json(
                table_data,
                hex_id=hex_id,
                poi_name=poi_name
            ))

    return tables


def convert_hex_tables_to_roll_tables(hex_data: dict[str, Any]) -> list[RollTable]:
    """
    Extract and convert all roll tables from hex data to standard RollTable format.

    This is the primary function for loading hex tables into the database-driven
    table system.
    """
    hex_tables = parse_hex_roll_tables(hex_data)
    return [ht.to_roll_table() for ht in hex_tables]
