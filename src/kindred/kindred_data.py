"""
Kindred data structures for Dolmenwood.

Defines the core data classes for kindred (race) definitions,
abilities, name tables, and aspect tables.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class KindredType(str, Enum):
    """Classification of kindred types."""
    MORTAL = "mortal"
    DEMI_FEY = "demi_fey"
    FAIRY = "fairy"


class AspectType(str, Enum):
    """Types of character aspects for generation."""
    BACKGROUND = "background"
    TRINKET = "trinket"
    HEAD = "head"
    DEMEANOUR = "demeanour"
    DESIRES = "desires"
    FACE = "face"
    DRESS = "dress"
    BELIEFS = "beliefs"
    FUR_BODY = "fur_body"  # Fur for breggles/grimalkin, body for others
    SPEECH = "speech"


class NameColumn(str, Enum):
    """Name table column types."""
    MALE = "male"
    FEMALE = "female"
    UNISEX = "unisex"
    SURNAME = "surname"
    RUSTIC = "rustic"      # For elves
    COURTLY = "courtly"    # For elves


@dataclass
class DiceFormula:
    """
    Represents a dice formula like 2d6+10.

    Used for rolling age, height, weight, etc.
    """
    num_dice: int
    die_size: int
    modifier: int = 0

    def __str__(self) -> str:
        if self.modifier > 0:
            return f"{self.num_dice}d{self.die_size}+{self.modifier}"
        elif self.modifier < 0:
            return f"{self.num_dice}d{self.die_size}{self.modifier}"
        return f"{self.num_dice}d{self.die_size}"

    @classmethod
    def parse(cls, formula: str) -> "DiceFormula":
        """Parse a string like '2d6+10' into a DiceFormula."""
        import re
        match = re.match(r"(\d+)d(\d+)([+-]\d+)?", formula.replace(" ", ""))
        if not match:
            raise ValueError(f"Invalid dice formula: {formula}")
        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        return cls(num_dice, die_size, modifier)


@dataclass
class PhysicalRanges:
    """Physical characteristic ranges for a kindred."""
    # Age at level 1 (base + dice)
    age_base: int
    age_dice: DiceFormula

    # Lifespan (base + dice)
    lifespan_base: int
    lifespan_dice: DiceFormula

    # Height in inches (base + dice)
    height_base: int
    height_dice: DiceFormula

    # Weight in pounds (base + dice)
    weight_base: int
    weight_dice: DiceFormula

    # Size category
    size: str = "Medium"


@dataclass
class KindredAbility:
    """
    A special ability granted by a kindred.

    Abilities can be passive (always active) or active (require activation).
    Some abilities scale with level.
    """
    ability_id: str
    name: str
    description: str

    # Mechanical effects
    is_passive: bool = True  # False = requires activation
    ac_bonus: int = 0  # Passive AC bonus
    ac_conditions: list[str] = field(default_factory=list)  # When AC bonus applies

    # For attack abilities (like horns)
    is_attack: bool = False
    damage_by_level: dict[int, str] = field(default_factory=dict)  # Level -> damage dice

    # For abilities with limited uses
    uses_per_day_by_level: dict[int, int] = field(default_factory=dict)  # Level -> uses

    # Save to resist (for abilities that target others)
    save_type: Optional[str] = None  # "spell", "doom", etc.

    # Duration
    duration: Optional[str] = None  # "until sunrise", "1 turn", etc.

    # Minimum level required
    min_level: int = 1

    # Additional mechanical data
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AspectTableEntry:
    """A single entry in an aspect table."""
    roll_min: int
    roll_max: int
    result: str
    description: Optional[str] = None  # Extended description if any
    item_id: Optional[str] = None  # For trinkets, reference to item catalog


@dataclass
class AspectTable:
    """
    A table for rolling character aspects.

    Contains entries that map die rolls to results.
    """
    aspect_type: AspectType
    die_size: int  # d12, d20, d100, etc.
    entries: list[AspectTableEntry] = field(default_factory=list)

    def get_entry(self, roll: int) -> Optional[AspectTableEntry]:
        """Get the entry matching a specific roll."""
        for entry in self.entries:
            if entry.roll_min <= roll <= entry.roll_max:
                return entry
        return None


@dataclass
class NameTable:
    """
    Name table for a kindred.

    Contains lists of names organized by column type.
    """
    columns: dict[NameColumn, list[str]] = field(default_factory=dict)

    def get_names(self, column: NameColumn) -> list[str]:
        """Get all names in a column."""
        return self.columns.get(column, [])


@dataclass
class LevelProgression:
    """
    Level-based progression for kindred abilities.

    Tracks things like horn length, damage, ability uses, etc.
    """
    level: int
    horn_length: Optional[str] = None  # For breggles
    horn_damage: Optional[str] = None  # Damage dice
    gaze_uses: Optional[int] = None    # Uses per day
    # Add more progression fields as needed for other kindreds


@dataclass
class KindredDefinition:
    """
    Complete definition of a kindred (race).

    Contains all data needed to generate and play a character
    of this kindred.
    """
    # Identity
    kindred_id: str
    name: str
    description: str
    kindred_type: KindredType

    # Physical characteristics
    physical: PhysicalRanges

    # Languages
    native_languages: list[str]

    # Special abilities
    abilities: list[KindredAbility]

    # Level progression (for scaling abilities)
    level_progression: list[LevelProgression] = field(default_factory=list)

    # Class preferences/restrictions
    preferred_classes: list[str] = field(default_factory=list)
    restricted_classes: list[str] = field(default_factory=list)  # Rare/forbidden
    level_limits: dict[str, int] = field(default_factory=dict)  # Class -> max level

    # Name tables
    name_table: Optional[NameTable] = None

    # Aspect tables
    aspect_tables: dict[AspectType, AspectTable] = field(default_factory=dict)

    # Trinket item IDs (references to item catalog)
    trinket_item_ids: list[str] = field(default_factory=list)

    # Lore and relations
    kindred_relations: str = ""
    religion_notes: str = ""

    # Source reference
    source_book: str = ""
    source_page: int = 0

    def get_ability(self, ability_id: str) -> Optional[KindredAbility]:
        """Get a specific ability by ID."""
        for ability in self.abilities:
            if ability.ability_id == ability_id:
                return ability
        return None

    def get_progression(self, level: int) -> Optional[LevelProgression]:
        """Get progression data for a specific level."""
        for prog in self.level_progression:
            if prog.level == level:
                return prog
        # Return highest available if level exceeds defined progression
        if self.level_progression:
            return max(self.level_progression, key=lambda p: p.level)
        return None

    def get_aspect_table(self, aspect_type: AspectType) -> Optional[AspectTable]:
        """Get an aspect table by type."""
        return self.aspect_tables.get(aspect_type)


@dataclass
class GeneratedKindredAspects:
    """
    Container for all randomly generated kindred aspects.

    Stores the results of rolling on all aspect tables
    during character generation.
    """
    kindred_id: str

    # Physical stats (rolled)
    age: int = 0
    height_inches: int = 0
    weight_lbs: int = 0

    # Generated name
    name: str = ""
    gender: Optional[str] = None

    # Rolled aspects
    background: str = ""
    trinket: str = ""
    trinket_item_id: Optional[str] = None
    head: str = ""
    demeanour: str = ""
    desires: str = ""
    face: str = ""
    dress: str = ""
    beliefs: str = ""
    fur_body: str = ""
    speech: str = ""

    # Roll history (for reference)
    rolls: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "kindred_id": self.kindred_id,
            "age": self.age,
            "height_inches": self.height_inches,
            "weight_lbs": self.weight_lbs,
            "name": self.name,
            "gender": self.gender,
            "background": self.background,
            "trinket": self.trinket,
            "trinket_item_id": self.trinket_item_id,
            "head": self.head,
            "demeanour": self.demeanour,
            "desires": self.desires,
            "face": self.face,
            "dress": self.dress,
            "beliefs": self.beliefs,
            "fur_body": self.fur_body,
            "speech": self.speech,
            "rolls": self.rolls,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeneratedKindredAspects":
        """Deserialize from dictionary."""
        return cls(
            kindred_id=data.get("kindred_id", ""),
            age=data.get("age", 0),
            height_inches=data.get("height_inches", 0),
            weight_lbs=data.get("weight_lbs", 0),
            name=data.get("name", ""),
            gender=data.get("gender"),
            background=data.get("background", ""),
            trinket=data.get("trinket", ""),
            trinket_item_id=data.get("trinket_item_id"),
            head=data.get("head", ""),
            demeanour=data.get("demeanour", ""),
            desires=data.get("desires", ""),
            face=data.get("face", ""),
            dress=data.get("dress", ""),
            beliefs=data.get("beliefs", ""),
            fur_body=data.get("fur_body", ""),
            speech=data.get("speech", ""),
            rolls=data.get("rolls", {}),
        )
