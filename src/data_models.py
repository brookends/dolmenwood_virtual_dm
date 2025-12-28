"""
Shared data structures for the Dolmenwood Virtual DM.

These structures persist across all states and no state owns data exclusively.
Follows the specifications in Section 6 of the implementation spec.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional
import random
import uuid


# =============================================================================
# ENUMS
# =============================================================================


class Season(str, Enum):
    """Dolmenwood seasons affecting encounters and environment."""
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class Weather(str, Enum):
    """Weather conditions affecting travel and encounters."""
    CLEAR = "clear"
    OVERCAST = "overcast"
    FOG = "fog"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    BLIZZARD = "blizzard"


class LocationType(str, Enum):
    """Types of locations in the game world."""
    HEX = "hex"
    DUNGEON_ROOM = "dungeon_room"
    SETTLEMENT = "settlement"
    BUILDING = "building"
    WILDERNESS_FEATURE = "wilderness_feature"


class TerrainType(str, Enum):
    """Terrain types affecting travel speed and encounters."""
    FOREST = "forest"
    DEEP_FOREST = "deep_forest"
    MOOR = "moor"
    RIVER = "river"
    LAKE = "lake"
    HILLS = "hills"
    MOUNTAINS = "mountains"
    ROAD = "road"
    TRAIL = "trail"
    SWAMP = "swamp"
    FARMLAND = "farmland"
    SETTLEMENT = "settlement"


class EncounterType(str, Enum):
    """Types of encounters that can occur."""
    MONSTER = "monster"
    NPC = "npc"
    LAIR = "lair"
    ENVIRONMENTAL = "environmental"
    FAIRY = "fairy"
    DRUNE = "drune"


class SurpriseStatus(str, Enum):
    """Surprise status during encounter."""
    PARTY_SURPRISED = "party_surprised"
    ENEMIES_SURPRISED = "enemies_surprised"
    MUTUAL_SURPRISE = "mutual_surprise"
    NO_SURPRISE = "no_surprise"


class ReactionResult(str, Enum):
    """Results of 2d6 reaction roll."""
    HOSTILE = "hostile"
    UNFRIENDLY = "unfriendly"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    HELPFUL = "helpful"


class ConditionType(str, Enum):
    """Character conditions and status effects."""
    POISONED = "poisoned"
    DISEASED = "diseased"
    CURSED = "cursed"
    CHARMED = "charmed"
    FRIGHTENED = "frightened"
    PARALYZED = "paralyzed"
    PETRIFIED = "petrified"
    BLINDED = "blinded"
    DEAFENED = "deafened"
    EXHAUSTED = "exhausted"
    UNCONSCIOUS = "unconscious"
    DEAD = "dead"
    ENCUMBERED = "encumbered"
    LOST = "lost"
    STARVING = "starving"
    DEHYDRATED = "dehydrated"


class LightSourceType(str, Enum):
    """Types of light sources with different durations."""
    TORCH = "torch"  # 6 turns (1 hour)
    LANTERN = "lantern"  # 24 turns (4 hours) per flask
    CANDLE = "candle"  # 12 turns (2 hours)
    MAGICAL = "magical"  # Variable
    NONE = "none"


class TimeOfDay(str, Enum):
    """Time periods affecting encounters and activities."""
    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    EVENING = "evening"
    MIDNIGHT = "midnight"
    PREDAWN = "predawn"


class WatchPeriod(str, Enum):
    """4-hour watch periods for rest and travel."""
    FIRST_WATCH = "first_watch"     # Midnight to 4am
    SECOND_WATCH = "second_watch"   # 4am to 8am
    THIRD_WATCH = "third_watch"     # 8am to Noon
    FOURTH_WATCH = "fourth_watch"   # Noon to 4pm
    FIFTH_WATCH = "fifth_watch"     # 4pm to 8pm
    SIXTH_WATCH = "sixth_watch"     # 8pm to Midnight


class MovementMode(str, Enum):
    """Movement modes per Dolmenwood rules (p146-147)."""
    ENCOUNTER = "encounter"       # Combat/encounter: Speed per round
    EXPLORATION = "exploration"   # Dungeon exploration: Speed × 3 per turn
    FAMILIAR = "familiar"         # Known areas: Speed × 10 per turn
    RUNNING = "running"           # Running: Speed × 3 per round (max 30 rounds)
    OVERLAND = "overland"         # Wilderness travel: Speed ÷ 5 = TP/day


class SourceType(str, Enum):
    """Content source types with priority."""
    CORE_RULEBOOK = "core_rulebook"        # Priority 1 (Highest)
    CAMPAIGN_SETTING = "campaign_setting"  # Priority 2
    ADVENTURE_MODULE = "adventure_module"  # Priority 3
    HOMEBREW = "homebrew"                  # Priority 4 (Lowest)


class CombatPhase(str, Enum):
    """Phases within a combat round."""
    INITIATIVE = "initiative"
    DECLARATION = "declaration"
    MOVEMENT = "movement"
    MISSILE_ATTACKS = "missile_attacks"
    MELEE_ATTACKS = "melee_attacks"
    MAGIC = "magic"
    MORALE = "morale"
    END_ROUND = "end_round"


class ActionType(str, Enum):
    """Types of actions a character can take."""
    MOVE = "move"
    ATTACK = "attack"
    CAST_SPELL = "cast_spell"
    USE_ITEM = "use_item"
    SEARCH = "search"
    LISTEN = "listen"
    OPEN_DOOR = "open_door"
    PICK_LOCK = "pick_lock"
    DISARM_TRAP = "disarm_trap"
    HIDE = "hide"
    REST = "rest"
    PARLEY = "parley"
    FLEE = "flee"
    DEFEND = "defend"


# =============================================================================
# DICE AND RANDOMIZATION
# =============================================================================


class DiceRoller:
    """
    Centralized randomization interface.
    All dice rolls must go through this class for reproducibility and logging.
    """

    _instance = None
    _seed: Optional[int] = None
    _roll_log: list = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_seed(cls, seed: int) -> None:
        """Set random seed for reproducibility."""
        cls._seed = seed
        random.seed(seed)

    @classmethod
    def roll(cls, dice: str, reason: str = "") -> "DiceResult":
        """
        Roll dice using standard notation (e.g., '2d6', '1d20+5', '3d6-2').

        Args:
            dice: Dice notation string
            reason: Why this roll is being made (for logging)

        Returns:
            DiceResult with individual rolls and total
        """
        # Parse dice notation
        modifier = 0
        if '+' in dice:
            dice_part, mod_part = dice.split('+')
            modifier = int(mod_part)
        elif '-' in dice:
            dice_part, mod_part = dice.split('-')
            modifier = -int(mod_part)
        else:
            dice_part = dice

        num_dice, die_size = dice_part.lower().split('d')
        num_dice = int(num_dice) if num_dice else 1
        die_size = int(die_size)

        # Roll the dice
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier

        result = DiceResult(
            notation=dice,
            rolls=rolls,
            modifier=modifier,
            total=total,
            reason=reason
        )

        cls._roll_log.append(result)
        return result

    @classmethod
    def roll_d20(cls, reason: str = "") -> "DiceResult":
        """Convenience method for d20 rolls."""
        return cls.roll("1d20", reason)

    @classmethod
    def roll_2d6(cls, reason: str = "") -> "DiceResult":
        """Convenience method for 2d6 reaction/morale rolls."""
        return cls.roll("2d6", reason)

    @classmethod
    def roll_d6(cls, num_dice: int = 1, reason: str = "") -> "DiceResult":
        """Convenience method for d6 rolls."""
        return cls.roll(f"{num_dice}d6", reason)

    @classmethod
    def roll_percentile(cls, reason: str = "") -> "DiceResult":
        """Roll d100 for percentile checks."""
        return cls.roll("1d100", reason)

    @classmethod
    def get_roll_log(cls) -> list:
        """Get the complete roll log for the session."""
        return cls._roll_log.copy()

    @classmethod
    def clear_roll_log(cls) -> None:
        """Clear the roll log."""
        cls._roll_log = []


@dataclass
class DiceResult:
    """Result of a dice roll with full information."""
    notation: str
    rolls: list[int]
    modifier: int
    total: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        if self.modifier > 0:
            return f"{self.notation}: {self.rolls} + {self.modifier} = {self.total}"
        elif self.modifier < 0:
            return f"{self.notation}: {self.rolls} - {abs(self.modifier)} = {self.total}"
        return f"{self.notation}: {self.rolls} = {self.total}"


# =============================================================================
# DOLMENWOOD CALENDAR SYSTEM
# =============================================================================

# Moon phases in Dolmenwood - each month has its own named moon
class MoonPhase(str, Enum):
    """Moon phases in the Dolmenwood calendar."""
    GRINNING_MOON = "grinning_moon"  # Grimvold (month 1)
    DEAD_MOON = "dead_moon"          # Lymewald (month 2)
    BEAST_MOON = "beast_moon"        # Haggryme (month 3)
    WAXING_MOON = "waxing_moon"      # Brewmont (month 4)
    BLOSSOM_MOON = "blossom_moon"    # Plothmont (month 5)
    FIRST_MOON = "first_moon"        # Greenmont (month 6)
    RED_MOON = "red_moon"            # Moltmont (month 7)
    WYRM_MOON = "wyrm_moon"          # Midsummer (month 8)
    WANE_MOON = "wane_moon"          # Hautmont (month 9)
    FAT_MOON = "fat_moon"            # Harvestmont (month 10)
    WITHER_MOON = "wither_moon"      # Fogmont (month 11)
    BLACK_MOON = "black_moon"        # Braghold (month 12)


@dataclass
class DolmenwoodMonth:
    """A month in the Dolmenwood calendar."""
    number: int           # 1-12
    name: str            # Month name (e.g., "Grimvold")
    season_desc: str     # Season description (e.g., "The onset of winter")
    days: int            # Number of days (28 or 30)
    wysendays: list[str]  # Holy days/festivals in this month
    moon: MoonPhase      # Associated moon phase


# The Dolmenwood Calendar - 12 months with varying lengths and festivals
DOLMENWOOD_CALENDAR: dict[int, DolmenwoodMonth] = {
    1: DolmenwoodMonth(
        number=1, name="Grimvold", season_desc="The onset of winter",
        days=30, wysendays=["Hanglemas", "Dyboll's Day"], moon=MoonPhase.GRINNING_MOON
    ),
    2: DolmenwoodMonth(
        number=2, name="Lymewald", season_desc="Deep winter",
        days=28, wysendays=[], moon=MoonPhase.DEAD_MOON
    ),
    3: DolmenwoodMonth(
        number=3, name="Haggryme", season_desc="The fading of winter",
        days=30, wysendays=["Yarl's Day", "The Day of Virgins"], moon=MoonPhase.BEAST_MOON
    ),
    4: DolmenwoodMonth(
        number=4, name="Brewmont", season_desc="The onset of spring",
        days=30, wysendays=["Shunning Day", "Hob's Day", "The Day of Doors"], moon=MoonPhase.WAXING_MOON
    ),
    5: DolmenwoodMonth(
        number=5, name="Plothmont", season_desc="Springtide",
        days=30, wysendays=[], moon=MoonPhase.BLOSSOM_MOON
    ),
    6: DolmenwoodMonth(
        number=6, name="Greenmont", season_desc="The fading of spring",
        days=28, wysendays=[], moon=MoonPhase.FIRST_MOON
    ),
    7: DolmenwoodMonth(
        number=7, name="Moltmont", season_desc="The onset of summer",
        days=30, wysendays=[], moon=MoonPhase.RED_MOON
    ),
    8: DolmenwoodMonth(
        number=8, name="Midsummer", season_desc="High summer",
        days=30, wysendays=["The Day of the Falling Stars", "Frith's Day"], moon=MoonPhase.WYRM_MOON
    ),
    9: DolmenwoodMonth(
        number=9, name="Hautmont", season_desc="The fading of summer",
        days=30, wysendays=[], moon=MoonPhase.WANE_MOON
    ),
    10: DolmenwoodMonth(
        number=10, name="Harvestmont", season_desc="The onset of autumn",
        days=28, wysendays=[], moon=MoonPhase.FAT_MOON
    ),
    11: DolmenwoodMonth(
        number=11, name="Fogmont", season_desc="Deep autumn",
        days=30, wysendays=["All Souls' Eve", "All Souls' Day"], moon=MoonPhase.WITHER_MOON
    ),
    12: DolmenwoodMonth(
        number=12, name="Braghold", season_desc="The fading of autumn",
        days=30, wysendays=["The Day of Doors", "Dolmenday"], moon=MoonPhase.BLACK_MOON
    ),
}


def get_dolmenwood_year_length() -> int:
    """Get total days in a Dolmenwood year (352 days)."""
    return sum(m.days for m in DOLMENWOOD_CALENDAR.values())


# =============================================================================
# TIME TRACKING
# =============================================================================


@dataclass
class GameDate:
    """Dolmenwood calendar date with proper month lengths and moon phases."""
    year: int
    month: int  # 1-12
    day: int    # 1-28 or 1-30 depending on month

    def get_month_info(self) -> DolmenwoodMonth:
        """Get the DolmenwoodMonth info for the current month."""
        return DOLMENWOOD_CALENDAR[self.month]

    def get_days_in_month(self) -> int:
        """Get the number of days in the current month."""
        return self.get_month_info().days

    def advance_days(self, days: int) -> "GameDate":
        """Advance the date by a number of days, respecting proper month lengths."""
        new_day = self.day + days
        new_month = self.month
        new_year = self.year

        # Handle positive days
        while new_day > DOLMENWOOD_CALENDAR[new_month].days:
            new_day -= DOLMENWOOD_CALENDAR[new_month].days
            new_month += 1
            if new_month > 12:
                new_month = 1
                new_year += 1

        # Handle negative days (going backwards)
        while new_day < 1:
            new_month -= 1
            if new_month < 1:
                new_month = 12
                new_year -= 1
            new_day += DOLMENWOOD_CALENDAR[new_month].days

        return GameDate(year=new_year, month=new_month, day=new_day)

    def get_season(self) -> Season:
        """Determine season from month."""
        if self.month in [3, 4, 5]:
            return Season.SPRING
        elif self.month in [6, 7, 8]:
            return Season.SUMMER
        elif self.month in [9, 10, 11]:
            return Season.AUTUMN
        else:
            return Season.WINTER

    def get_moon_phase(self) -> MoonPhase:
        """
        Get the current moon phase based on the month.

        Each month in Dolmenwood has its own named moon that governs
        the entire month. The moon's influence waxes and wanes during
        the month but the name remains constant.
        """
        return self.get_month_info().moon

    def get_moon_phase_name(self) -> str:
        """Get human-readable moon phase name."""
        moon = self.get_moon_phase()
        # Convert enum value to title case
        return moon.value.replace("_", " ").title()

    def get_month_name(self) -> str:
        """Get the current month's name (e.g., 'Grimvold')."""
        return self.get_month_info().name

    def get_wysendays(self) -> list[str]:
        """Get the holy days/festivals in the current month."""
        return self.get_month_info().wysendays.copy()

    def is_wysenday(self, wysenday_name: Optional[str] = None) -> bool:
        """
        Check if the current date is a Wysenday (holy day).

        Args:
            wysenday_name: Specific wysenday to check for. If None, returns
                          True if any wysenday is today.

        Note: Specific dates for Wysendays would need to be defined.
        For now, this returns True if the month has any wysendays.
        """
        wysendays = self.get_wysendays()
        if not wysendays:
            return False
        if wysenday_name:
            return wysenday_name in wysendays
        # Without specific date mappings, return True on day 1 and 15
        # (symbolic - can be refined with actual Wysenday dates)
        return len(wysendays) > 0 and self.day in [1, 15]

    def get_moon_intensity(self) -> str:
        """
        Get the moon's intensity based on day of month.

        Returns: "new", "waxing", "full", "waning"
        """
        days_in_month = self.get_days_in_month()
        quarter = days_in_month // 4

        if self.day <= quarter:
            return "new"
        elif self.day <= quarter * 2:
            return "waxing"
        elif self.day <= quarter * 3:
            return "full"
        else:
            return "waning"

    def is_full_moon(self) -> bool:
        """Check if it's currently a full moon (mid-month)."""
        return self.get_moon_intensity() == "full"

    def is_new_moon(self) -> bool:
        """Check if it's currently a new moon (start of month)."""
        return self.get_moon_intensity() == "new"

    def __str__(self) -> str:
        month_name = self.get_month_name()
        return f"{self.day} {month_name}, Year {self.year}"

    def format_full(self) -> str:
        """Get a full formatted date with moon phase."""
        moon = self.get_moon_phase_name()
        intensity = self.get_moon_intensity()
        return f"{self} (The {moon}, {intensity})"


@dataclass
class GameTime:
    """Time within a day, tracked in 10-minute turns."""
    hour: int = 8      # 0-23
    minute: int = 0    # 0-59

    def advance_turns(self, turns: int) -> tuple["GameTime", int]:
        """
        Advance time by exploration turns (10 minutes each).

        Returns:
            Tuple of (new_time, days_passed)
        """
        total_minutes = self.hour * 60 + self.minute + (turns * 10)
        days_passed = total_minutes // (24 * 60)
        remaining_minutes = total_minutes % (24 * 60)

        new_hour = remaining_minutes // 60
        new_minute = remaining_minutes % 60

        return GameTime(hour=new_hour, minute=new_minute), days_passed

    def advance_hours(self, hours: int) -> tuple["GameTime", int]:
        """Advance time by hours."""
        return self.advance_turns(hours * 6)

    def advance_watch(self) -> tuple["GameTime", int]:
        """Advance time by one watch (4 hours)."""
        return self.advance_hours(4)

    def get_time_of_day(self) -> TimeOfDay:
        """Determine time of day from hour."""
        if 5 <= self.hour < 7:
            return TimeOfDay.DAWN
        elif 7 <= self.hour < 11:
            return TimeOfDay.MORNING
        elif 11 <= self.hour < 14:
            return TimeOfDay.MIDDAY
        elif 14 <= self.hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= self.hour < 19:
            return TimeOfDay.DUSK
        elif 19 <= self.hour < 23:
            return TimeOfDay.EVENING
        elif 23 <= self.hour or self.hour < 2:
            return TimeOfDay.MIDNIGHT
        else:
            return TimeOfDay.PREDAWN

    def get_current_watch(self) -> WatchPeriod:
        """Determine current watch period."""
        if 0 <= self.hour < 4:
            return WatchPeriod.FIRST_WATCH
        elif 4 <= self.hour < 8:
            return WatchPeriod.SECOND_WATCH
        elif 8 <= self.hour < 12:
            return WatchPeriod.THIRD_WATCH
        elif 12 <= self.hour < 16:
            return WatchPeriod.FOURTH_WATCH
        elif 16 <= self.hour < 20:
            return WatchPeriod.FIFTH_WATCH
        else:
            return WatchPeriod.SIXTH_WATCH

    def is_daylight(self) -> bool:
        """Check if it's daylight hours."""
        return 6 <= self.hour < 20

    def __str__(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


# =============================================================================
# TIME AND MOVEMENT CONSTANTS (p146-147)
# =============================================================================

# Time unit conversions per Dolmenwood rules (p146)
MINUTES_PER_TURN = 10       # 1 Turn = 10 minutes
SECONDS_PER_ROUND = 10      # 1 Round = 10 seconds
TURNS_PER_HOUR = 6          # 6 Turns per hour (60 min ÷ 10 min)
ROUNDS_PER_TURN = 60        # 60 Rounds per Turn (600 sec ÷ 10 sec)
ROUNDS_PER_MINUTE = 6       # 6 Rounds per minute (60 sec ÷ 10 sec)

# Running exhaustion rules (p147)
MAX_RUNNING_ROUNDS = 30     # Can run for 30 rounds before exhaustion
RUNNING_REST_TURNS = 3      # Must rest 3 turns after running to exhaustion

# Weight system (p147)
COINS_PER_POUND = 10        # 10 coins = 1 pound


# =============================================================================
# ENCUMBRANCE SYSTEM (p148-149)
# =============================================================================


class EncumbranceSystem(str, Enum):
    """Encumbrance tracking system per Dolmenwood rules (p148-149)."""
    WEIGHT = "weight"           # Detailed weight tracking in coins
    BASIC_WEIGHT = "basic_weight"  # Simplified weight tracking (treasure only)
    SLOT = "slot"               # Abstract slot-based system


class ArmorWeight(str, Enum):
    """Armor weight categories for encumbrance (p148)."""
    UNARMOURED = "unarmoured"   # No armor
    LIGHT = "light"             # Light armor (leather, etc.)
    MEDIUM = "medium"           # Medium armor (chain, etc.)
    HEAVY = "heavy"             # Heavy armor (plate, etc.)


class GearSlotType(str, Enum):
    """Gear slot types for slot encumbrance system (p149)."""
    EQUIPPED = "equipped"       # Worn/held items (max 10 slots)
    STOWED = "stowed"           # Items in containers (max 16 slots)


# Encumbrance constants (p148)
MAX_WEIGHT_CAPACITY = 1600      # Maximum weight in coins a character can carry
MAX_EQUIPPED_SLOTS = 10         # Maximum equipped gear slots
MAX_STOWED_SLOTS = 16           # Maximum stowed gear slots total
STOWED_SLOTS_PER_CONTAINER = 10 # Each container holds 10 stowed items


# Weight thresholds for speed calculation (p148)
# Format: (max_weight, speed)
WEIGHT_ENCUMBRANCE_THRESHOLDS = [
    (400, 40),   # ≤400 coins: Speed 40
    (600, 30),   # ≤600 coins: Speed 30
    (800, 20),   # ≤800 coins: Speed 20
    (1600, 10),  # ≤1600 coins: Speed 10
]


# Slot encumbrance thresholds for speed calculation (p149)
# Format: (max_equipped, max_stowed, speed)
SLOT_ENCUMBRANCE_THRESHOLDS = [
    (3, 10, 40),   # 0-3 equipped / 0-10 stowed: Speed 40
    (5, 12, 30),   # 4-5 equipped / 11-12 stowed: Speed 30
    (7, 14, 20),   # 6-7 equipped / 13-14 stowed: Speed 20
    (10, 16, 10),  # 8-10 equipped / 15-16 stowed: Speed 10
]


# Treasure weights in coins (p148)
TREASURE_WEIGHTS: dict[str, int] = {
    "coin": 1,
    "gem": 1,
    "jewellery": 10,
    "jewelry": 10,  # Alternate spelling
    "potion": 10,
    "rod": 20,
    "scroll": 1,
    "staff": 40,
    "wand": 10,
}


# Armor weights by category (p148)
# Format: armor_weight -> coins
ARMOR_WEIGHTS: dict[str, int] = {
    ArmorWeight.UNARMOURED.value: 0,
    ArmorWeight.LIGHT.value: 200,   # ~20 lbs
    ArmorWeight.MEDIUM.value: 400,  # ~40 lbs
    ArmorWeight.HEAVY.value: 600,   # ~60 lbs
}


# Gear slots by item type (p149)
# Format: item_type -> slots
GEAR_SLOTS: dict[str, int] = {
    # Weapons
    "dagger": 1,
    "sword": 1,
    "longsword": 1,
    "short_sword": 1,
    "axe": 1,
    "hand_axe": 1,
    "battle_axe": 2,
    "mace": 1,
    "hammer": 1,
    "war_hammer": 2,
    "spear": 1,
    "polearm": 2,
    "halberd": 2,
    "staff": 1,
    "bow": 1,
    "shortbow": 1,
    "longbow": 2,
    "crossbow": 2,
    "sling": 1,
    # Armor
    "leather_armor": 1,
    "chain_mail": 2,
    "plate_mail": 3,
    "shield": 1,
    "helmet": 1,
    # Containers
    "backpack": 1,
    "sack": 1,
    "pouch": 0,
    "belt_pouch": 0,
    # Misc equipment
    "rope": 1,
    "lantern": 1,
    "torch": 1,
    "quiver": 1,
    # Bundled items (10 = 1 slot)
    "arrows_20": 1,
    "bolts_20": 1,
    "rations_7": 1,
    "torches_6": 1,
    # Tiny items (no slot)
    "coin": 0,
    "gem": 0,
    "scroll": 0,
    "key": 0,
    "ring": 0,
    # Default for unknown items
    "default": 1,
}


@dataclass
class RunningState:
    """Tracks running exhaustion per Dolmenwood rules (p147)."""
    rounds_run: int = 0
    is_exhausted: bool = False
    rest_turns_remaining: int = 0

    def run_round(self) -> bool:
        """
        Record one round of running.

        Returns:
            True if can continue running, False if exhausted
        """
        if self.is_exhausted:
            return False

        self.rounds_run += 1
        if self.rounds_run >= MAX_RUNNING_ROUNDS:
            self.is_exhausted = True
            self.rest_turns_remaining = RUNNING_REST_TURNS
            return False
        return True

    def rest_turn(self) -> None:
        """Record one turn of rest to recover from running."""
        if self.rest_turns_remaining > 0:
            self.rest_turns_remaining -= 1
            if self.rest_turns_remaining == 0:
                self.is_exhausted = False
                self.rounds_run = 0

    def can_run(self) -> bool:
        """Check if character can run."""
        return not self.is_exhausted and self.rounds_run < MAX_RUNNING_ROUNDS


class MovementCalculator:
    """
    Calculate movement rates per Dolmenwood rules (p146-147).

    Movement rates are derived from base Speed:
    - Encounter (per round): Speed feet
    - Exploration (per turn): Speed × 3 feet
    - Familiar areas (per turn): Speed × 10 feet
    - Running (per round): Speed × 3 feet (max 30 rounds)
    - Overland (Travel Points/day): Speed ÷ 5
    """

    # Movement multipliers per mode (p146-147)
    ENCOUNTER_MULTIPLIER = 1        # Speed per round
    EXPLORATION_MULTIPLIER = 3      # Speed × 3 per turn
    FAMILIAR_MULTIPLIER = 10        # Speed × 10 per turn
    RUNNING_MULTIPLIER = 3          # Speed × 3 per round

    @classmethod
    def get_encounter_movement(cls, speed: int) -> int:
        """
        Get encounter/combat movement rate (feet per round).

        Per Dolmenwood rules (p146): Speed per round.
        Example: Speed 30 = 30'/round
        """
        return speed * cls.ENCOUNTER_MULTIPLIER

    @classmethod
    def get_exploration_movement(cls, speed: int) -> int:
        """
        Get dungeon exploration movement rate (feet per turn).

        Per Dolmenwood rules (p146): Speed × 3 per turn.
        Example: Speed 30 = 90'/turn
        """
        return speed * cls.EXPLORATION_MULTIPLIER

    @classmethod
    def get_familiar_movement(cls, speed: int) -> int:
        """
        Get movement rate in familiar/explored areas (feet per turn).

        Per Dolmenwood rules (p146): Speed × 10 per turn.
        Example: Speed 30 = 300'/turn
        """
        return speed * cls.FAMILIAR_MULTIPLIER

    @classmethod
    def get_running_movement(cls, speed: int) -> int:
        """
        Get running movement rate (feet per round).

        Per Dolmenwood rules (p147): Speed × 3 per round.
        Can only run for 30 rounds before needing 3 turns rest.
        Example: Speed 30 = 90'/round
        """
        return speed * cls.RUNNING_MULTIPLIER

    @classmethod
    def get_travel_points(cls, speed: int) -> int:
        """
        Get Travel Points per day for overland travel.

        Per Dolmenwood rules (p147): Speed ÷ 5 = TP/day.
        Example: Speed 30 = 6 TP/day
        """
        return speed // 5

    @classmethod
    def get_forced_march_travel_points(cls, speed: int) -> int:
        """
        Get Travel Points per day for forced march.

        Per Dolmenwood rules (p156): Forced march grants 50% more TP.
        """
        base_tp = cls.get_travel_points(speed)
        return base_tp + (base_tp // 2)  # 1.5x base, rounded down

    @classmethod
    def get_movement_rate(cls, speed: int, mode: "MovementMode") -> int:
        """
        Get movement rate for a specific mode.

        Args:
            speed: Base movement speed in feet
            mode: Movement mode (encounter, exploration, etc.)

        Returns:
            Movement rate in feet (per round or per turn depending on mode)
        """
        handlers = {
            MovementMode.ENCOUNTER: cls.get_encounter_movement,
            MovementMode.EXPLORATION: cls.get_exploration_movement,
            MovementMode.FAMILIAR: cls.get_familiar_movement,
            MovementMode.RUNNING: cls.get_running_movement,
        }
        handler = handlers.get(mode)
        if handler:
            return handler(speed)
        # For OVERLAND, return travel points (different unit)
        if mode == MovementMode.OVERLAND:
            return cls.get_travel_points(speed)
        return speed

    @classmethod
    def get_party_speed(cls, member_speeds: list[int]) -> int:
        """
        Get party movement speed (slowest member).

        Per Dolmenwood rules (p146): Party speed = slowest member's speed.

        Args:
            member_speeds: List of movement speeds for all party members

        Returns:
            Party speed (minimum of all member speeds)
        """
        if not member_speeds:
            return 30  # Default speed
        return min(member_speeds)

    @classmethod
    def calculate_turns_for_distance(
        cls,
        distance_feet: int,
        speed: int,
        mode: MovementMode
    ) -> int:
        """
        Calculate turns needed to travel a distance.

        Args:
            distance_feet: Distance to travel in feet
            speed: Base movement speed
            mode: Movement mode

        Returns:
            Number of turns needed (rounded up)
        """
        movement_per_turn = cls.get_movement_rate(speed, mode)
        if movement_per_turn <= 0:
            return 0
        return (distance_feet + movement_per_turn - 1) // movement_per_turn

    @classmethod
    def calculate_rounds_for_distance(
        cls,
        distance_feet: int,
        speed: int,
        running: bool = False
    ) -> int:
        """
        Calculate rounds needed to travel a distance (combat/encounter).

        Args:
            distance_feet: Distance to travel in feet
            speed: Base movement speed
            running: Whether running (3× speed)

        Returns:
            Number of rounds needed (rounded up)
        """
        if running:
            movement_per_round = cls.get_running_movement(speed)
        else:
            movement_per_round = cls.get_encounter_movement(speed)

        if movement_per_round <= 0:
            return 0
        return (distance_feet + movement_per_round - 1) // movement_per_round


class EncumbranceCalculator:
    """
    Calculate encumbrance and speed per Dolmenwood rules (p148-149).

    Supports three encumbrance systems:
    - Weight: Detailed tracking of weight in coins (10 coins = 1 lb)
    - Basic Weight: Simplified tracking (only treasure weight matters)
    - Slot: Abstract slot-based system (equipped + stowed slots)
    """

    @classmethod
    def get_speed_from_weight(cls, total_weight: int) -> int:
        """
        Calculate movement speed based on weight encumbrance (p148).

        Args:
            total_weight: Total carried weight in coins

        Returns:
            Movement speed (40, 30, 20, or 10)
        """
        for max_weight, speed in WEIGHT_ENCUMBRANCE_THRESHOLDS:
            if total_weight <= max_weight:
                return speed
        # Over maximum capacity
        return 0

    @classmethod
    def get_speed_from_slots(cls, equipped_slots: int, stowed_slots: int) -> int:
        """
        Calculate movement speed based on slot encumbrance (p149).

        Uses the WORSE of equipped or stowed encumbrance.

        Args:
            equipped_slots: Number of equipped gear slots used
            stowed_slots: Number of stowed gear slots used

        Returns:
            Movement speed (40, 30, 20, or 10)
        """
        equipped_speed = 40
        stowed_speed = 40

        # Find speed based on equipped slots
        for max_equipped, _, speed in SLOT_ENCUMBRANCE_THRESHOLDS:
            if equipped_slots <= max_equipped:
                equipped_speed = speed
                break
        else:
            equipped_speed = 0  # Over maximum

        # Find speed based on stowed slots
        for _, max_stowed, speed in SLOT_ENCUMBRANCE_THRESHOLDS:
            if stowed_slots <= max_stowed:
                stowed_speed = speed
                break
        else:
            stowed_speed = 0  # Over maximum

        # Use the worse (slower) of the two
        return min(equipped_speed, stowed_speed)

    @classmethod
    def get_treasure_weight(cls, treasure_type: str, quantity: int = 1) -> int:
        """
        Get weight of treasure items in coins (p148).

        Args:
            treasure_type: Type of treasure (coin, gem, jewellery, etc.)
            quantity: Number of items

        Returns:
            Total weight in coins
        """
        weight_per_item = TREASURE_WEIGHTS.get(treasure_type.lower(), 1)
        return weight_per_item * quantity

    @classmethod
    def get_armor_weight(cls, armor_weight: ArmorWeight) -> int:
        """
        Get weight of armor in coins (p148).

        Args:
            armor_weight: Armor weight category

        Returns:
            Weight in coins
        """
        return ARMOR_WEIGHTS.get(armor_weight.value, 0)

    @classmethod
    def get_item_slots(cls, item_type: str) -> int:
        """
        Get gear slots required for an item type (p149).

        Args:
            item_type: Type of item

        Returns:
            Number of gear slots required
        """
        return GEAR_SLOTS.get(item_type.lower(), GEAR_SLOTS["default"])

    @classmethod
    def is_over_weight_capacity(cls, total_weight: int) -> bool:
        """
        Check if weight exceeds maximum capacity (p148).

        Args:
            total_weight: Total carried weight in coins

        Returns:
            True if over capacity (1600 coins)
        """
        return total_weight > MAX_WEIGHT_CAPACITY

    @classmethod
    def is_over_slot_capacity(
        cls,
        equipped_slots: int,
        stowed_slots: int
    ) -> bool:
        """
        Check if slot usage exceeds maximum capacity (p149).

        Args:
            equipped_slots: Number of equipped gear slots used
            stowed_slots: Number of stowed gear slots used

        Returns:
            True if over capacity
        """
        return (equipped_slots > MAX_EQUIPPED_SLOTS or
                stowed_slots > MAX_STOWED_SLOTS)

    @classmethod
    def calculate_encumbrance_level(
        cls,
        total_weight: int = 0,
        equipped_slots: int = 0,
        stowed_slots: int = 0,
        system: EncumbranceSystem = EncumbranceSystem.WEIGHT
    ) -> tuple[int, bool]:
        """
        Calculate encumbrance level and over-capacity status.

        Args:
            total_weight: Total weight in coins (for WEIGHT system)
            equipped_slots: Equipped slots used (for SLOT system)
            stowed_slots: Stowed slots used (for SLOT system)
            system: Which encumbrance system to use

        Returns:
            Tuple of (movement_speed, is_over_capacity)
        """
        if system == EncumbranceSystem.WEIGHT:
            speed = cls.get_speed_from_weight(total_weight)
            over_capacity = cls.is_over_weight_capacity(total_weight)
        elif system == EncumbranceSystem.BASIC_WEIGHT:
            # Basic weight only tracks treasure weight
            speed = cls.get_speed_from_weight(total_weight)
            over_capacity = cls.is_over_weight_capacity(total_weight)
        else:  # SLOT system
            speed = cls.get_speed_from_slots(equipped_slots, stowed_slots)
            over_capacity = cls.is_over_slot_capacity(equipped_slots, stowed_slots)

        return speed, over_capacity

    @classmethod
    def get_remaining_capacity(
        cls,
        total_weight: int = 0,
        equipped_slots: int = 0,
        stowed_slots: int = 0,
        system: EncumbranceSystem = EncumbranceSystem.WEIGHT
    ) -> dict[str, int]:
        """
        Get remaining capacity before reaching limits.

        Args:
            total_weight: Current weight in coins
            equipped_slots: Current equipped slots used
            stowed_slots: Current stowed slots used
            system: Which encumbrance system to use

        Returns:
            Dict with remaining capacity values
        """
        if system in (EncumbranceSystem.WEIGHT, EncumbranceSystem.BASIC_WEIGHT):
            return {
                "weight_remaining": max(0, MAX_WEIGHT_CAPACITY - total_weight),
            }
        else:  # SLOT system
            return {
                "equipped_remaining": max(0, MAX_EQUIPPED_SLOTS - equipped_slots),
                "stowed_remaining": max(0, MAX_STOWED_SLOTS - stowed_slots),
            }


@dataclass
class EncumbranceState:
    """
    Tracks encumbrance for a character per Dolmenwood rules (p148-149).

    Supports both weight-based and slot-based encumbrance systems.
    """
    # Weight-based tracking
    total_weight: int = 0  # In coins

    # Slot-based tracking
    equipped_slots: int = 0
    stowed_slots: int = 0

    # Current system in use
    system: EncumbranceSystem = EncumbranceSystem.WEIGHT

    def get_speed(self) -> int:
        """Get movement speed based on current encumbrance."""
        if self.system in (EncumbranceSystem.WEIGHT, EncumbranceSystem.BASIC_WEIGHT):
            return EncumbranceCalculator.get_speed_from_weight(self.total_weight)
        else:
            return EncumbranceCalculator.get_speed_from_slots(
                self.equipped_slots, self.stowed_slots
            )

    def is_over_capacity(self) -> bool:
        """Check if over maximum capacity."""
        if self.system in (EncumbranceSystem.WEIGHT, EncumbranceSystem.BASIC_WEIGHT):
            return EncumbranceCalculator.is_over_weight_capacity(self.total_weight)
        else:
            return EncumbranceCalculator.is_over_slot_capacity(
                self.equipped_slots, self.stowed_slots
            )

    def add_weight(self, weight: int) -> None:
        """Add weight to encumbrance."""
        self.total_weight += weight

    def remove_weight(self, weight: int) -> None:
        """Remove weight from encumbrance."""
        self.total_weight = max(0, self.total_weight - weight)

    def add_item_slots(self, slots: int, equipped: bool = True) -> None:
        """Add item slots to encumbrance."""
        if equipped:
            self.equipped_slots += slots
        else:
            self.stowed_slots += slots

    def remove_item_slots(self, slots: int, equipped: bool = True) -> None:
        """Remove item slots from encumbrance."""
        if equipped:
            self.equipped_slots = max(0, self.equipped_slots - slots)
        else:
            self.stowed_slots = max(0, self.stowed_slots - slots)


# =============================================================================
# GAME ENTITIES
# =============================================================================


@dataclass
class Condition:
    """A condition affecting a character or creature."""
    condition_type: ConditionType
    duration_turns: Optional[int] = None  # None = permanent until cured
    source: str = ""
    severity: int = 1  # For conditions like exhaustion

    def tick(self) -> bool:
        """
        Reduce duration by 1 turn.

        Returns:
            True if condition has expired, False otherwise
        """
        if self.duration_turns is not None:
            self.duration_turns -= 1
            return self.duration_turns <= 0
        return False


@dataclass
class Item:
    """
    An item in inventory.

    Supports both weight-based and slot-based encumbrance systems (p148-149).
    """
    item_id: str
    name: str
    weight: float  # In coins (10 coins = 1 lb)
    quantity: int = 1
    equipped: bool = False
    charges: Optional[int] = None
    light_source: Optional[LightSourceType] = None
    light_remaining_turns: Optional[int] = None
    # Encumbrance system fields (p148-149)
    item_type: str = ""  # Used to look up slot size in GEAR_SLOTS
    slot_size: int = 1   # Number of gear slots required (for slot encumbrance)
    is_container: bool = False  # True for backpacks, sacks, etc.

    def get_total_weight(self) -> float:
        """Get total weight of this item stack (weight × quantity)."""
        return self.weight * self.quantity

    def get_total_slots(self) -> int:
        """Get total gear slots required for this item."""
        # Tiny items (slot_size 0) don't consume slots even with quantity
        if self.slot_size == 0:
            return 0
        return self.slot_size * self.quantity


@dataclass
class Spell:
    """A memorized spell."""
    spell_id: str
    name: str
    level: int
    prepared: bool = True
    cast_today: bool = False


@dataclass
class StatBlock:
    """Combat statistics for a creature or character."""
    armor_class: int
    hit_dice: str  # e.g., "2d8" or "4d8+4"
    hp_current: int
    hp_max: int
    movement: int  # In feet per round
    attacks: list[dict]  # [{"name": "Claw", "damage": "1d6", "bonus": 2}]
    morale: int = 7  # 2-12 scale
    save_as: str = ""  # e.g., "Fighter 4"
    special_abilities: list[str] = field(default_factory=list)
    # Dolmenwood combat modifiers (p166-169)
    shield_bonus: int = 0  # Shield AC bonus, negated by rear/fleeing attacks (p167)
    strength_mod: int = 0  # STR modifier for melee attack/damage and parrying (p167, p169)
    dexterity_mod: int = 0  # DEX modifier for missile attacks only (p167)


@dataclass
class MonsterSaves:
    """Saving throw values for a monster."""
    doom: int = 14  # Save vs Death/Doom
    ray: int = 15   # Save vs Wands/Rays
    hold: int = 16  # Save vs Paralysis/Hold
    blast: int = 17 # Save vs Breath/Blast
    spell: int = 18 # Save vs Spells


@dataclass
class Monster:
    """
    A monster entry from the Dolmenwood Monster Book.

    Contains all information needed to run encounters with this creature,
    including stats, abilities, behavior, and encounter seeds.
    """
    # Core identification
    name: str
    monster_id: str

    # Combat statistics
    armor_class: int = 10
    hit_dice: str = "1d8"
    hp: int = 4
    level: int = 1
    morale: int = 7

    # Movement (in feet)
    movement: str = "40'"  # Display string
    speed: int = 40        # Base speed in feet
    burrow_speed: Optional[int] = None
    fly_speed: Optional[int] = None
    swim_speed: Optional[int] = None

    # Combat
    attacks: list[str] = field(default_factory=list)  # ["Claw (+2, 1d6)", "Bite (+2, 1d8)"]
    damage: list[str] = field(default_factory=list)   # ["1d6", "1d8"]

    # Saving throws
    save_doom: int = 14
    save_ray: int = 15
    save_hold: int = 16
    save_blast: int = 17
    save_spell: int = 18
    saves_as: Optional[str] = None  # Alternative: "Fighter 3"

    # Treasure
    treasure_type: Optional[str] = None
    hoard: Optional[str] = None
    possessions: Optional[str] = None

    # Classification
    size: str = "Medium"  # Tiny, Small, Medium, Large, Huge, Gargantuan
    monster_type: str = "Mortal"  # Mortal, Fairy, Undead, Demon, Monstrosity, etc.
    sentience: str = "Sentient"  # Non-Sentient, Semi-Intelligent, Sentient
    alignment: str = "Neutral"
    intelligence: Optional[str] = None

    # Abilities
    special_abilities: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)

    # Description and behavior
    description: Optional[str] = None
    behavior: Optional[str] = None
    speech: Optional[str] = None
    traits: list[str] = field(default_factory=list)  # Random traits table

    # Encounter information
    number_appearing: Optional[str] = None  # Dice notation, e.g., "2d6"
    lair_percentage: Optional[int] = None   # Percentage chance to find in lair
    encounter_scenarios: list[str] = field(default_factory=list)
    lair_descriptions: list[str] = field(default_factory=list)

    # Experience and habitat
    xp_value: int = 0
    habitat: list[str] = field(default_factory=list)

    # Source tracking
    page_reference: str = ""
    source: Optional["SourceReference"] = None  # Forward reference

    def get_saves(self) -> MonsterSaves:
        """Get saving throws as a MonsterSaves object."""
        return MonsterSaves(
            doom=self.save_doom,
            ray=self.save_ray,
            hold=self.save_hold,
            blast=self.save_blast,
            spell=self.save_spell,
        )

    def get_attack_bonus(self) -> int:
        """Calculate attack bonus based on hit dice/level."""
        return self.level

    def to_stat_block(self) -> StatBlock:
        """Convert to legacy StatBlock format for combat engine."""
        # Parse attacks into the dict format expected by StatBlock
        attack_list = []
        for i, atk in enumerate(self.attacks):
            dmg = self.damage[i] if i < len(self.damage) else "1d6"
            attack_list.append({
                'name': atk,
                'damage': dmg,
                'bonus': self.level,
            })

        return StatBlock(
            armor_class=self.armor_class,
            hit_dice=self.hit_dice,
            hp_current=self.hp,
            hp_max=self.hp,
            movement=self.speed,
            attacks=attack_list,
            morale=self.morale,
            save_as=self.saves_as or f"Monster {self.level}",
            special_abilities=self.special_abilities,
        )


@dataclass
class HexFeature:
    """
    A notable feature within a hex location (legacy format).

    Features can be locations, structures, or points of interest
    that characters can explore or interact with.
    """
    name: str
    description: str
    feature_type: str = "general"  # manor, ruin, grove, cave, etc.
    is_hidden: bool = False
    discovered: bool = False

    # Associated entities
    npcs: list[str] = field(default_factory=list)  # NPC names/IDs present
    monsters: list[str] = field(default_factory=list)  # Monster encounters
    treasure: Optional[str] = None  # Treasure description

    # Adventure hooks
    hooks: list[str] = field(default_factory=list)  # Plot hooks and connections

    # Legacy compatibility
    searchable: bool = False


# =============================================================================
# NEW HEX DATA STRUCTURES (Updated Format)
# =============================================================================


@dataclass
class HexProcedural:
    """
    Procedural generation rules for a hex.

    Contains chances for getting lost, encounters, and foraging results.
    """
    lost_chance: str = "1-in-6"  # e.g., "2-in-6"
    encounter_chance: str = "1-in-6"  # e.g., "2-in-6"
    encounter_notes: str = ""  # Special notes about encounters
    foraging_results: str = ""  # Description of foraging results
    foraging_special: list[str] = field(default_factory=list)  # Special foraging yields
    # Contextual encounter modifiers that apply to all wilderness encounters in this hex
    # Each modifier has: chance (e.g., "2-in-6"), result (creature/event), context (flavor)
    encounter_modifiers: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RollTableEntry:
    """
    A single entry in a roll table.

    Contains the roll value, optional title, description, and associated content.
    """
    roll: int  # The die roll value for this entry
    description: str  # What happens on this roll
    title: Optional[str] = None  # Optional title for the entry
    monsters: list[str] = field(default_factory=list)  # Monster references
    npcs: list[str] = field(default_factory=list)  # NPC references
    items: list[str] = field(default_factory=list)  # Item references
    mechanical_effect: Optional[str] = None  # Game mechanical effects
    sub_table: Optional[str] = None  # Reference to a sub-table to roll on

    # Alignment-based reaction conditions
    # Format: {hostile_if: {alignment_not: ["Neutral"]}, friendly_if: {alignment: ["Lawful"]}}
    # Creatures may attack or react differently based on party alignment
    reaction_conditions: Optional[dict[str, Any]] = None

    # Transportation effect triggered by this entry (for ENCOUNTERS state)
    # Format: {save_type: "Hold", destination: "Prince's Road", failure_desc: "whisked away"}
    # Used for magical effects that may transport characters to other locations
    transportation_effect: Optional[dict[str, Any]] = None

    # Time dilation effect when this entry is triggered (for ENCOUNTERS state)
    # Format: {time_passes: "1d12 days", trigger_condition: "on_exit", description: "..."}
    # Used for locations where time flows differently
    time_effect: Optional[dict[str, Any]] = None


@dataclass
class RollTable:
    """
    A roll table used for random generation.

    Contains a die type and list of entries to roll on.
    """
    name: str
    die_type: str  # e.g., "d6", "d8", "d20"
    description: str = ""  # When to use this table
    entries: list[RollTableEntry] = field(default_factory=list)


@dataclass
class PointOfInterest:
    """
    A point of interest within a hex.

    More detailed than HexFeature, supports dungeon-like locations
    with rooms, roll tables, and NPCs.
    """
    name: str
    poi_type: str  # manse, ruin, grove, cave, settlement, etc.
    description: str
    tagline: Optional[str] = None  # Short evocative description

    # Exploration details
    entering: Optional[str] = None  # How to enter the location
    interior: Optional[str] = None  # Description of the interior
    exploring: Optional[str] = None  # How exploration works
    leaving: Optional[str] = None  # Rules/effects when leaving
    inhabitants: Optional[str] = None  # Who lives here

    # Roll tables for this POI
    roll_tables: list[RollTable] = field(default_factory=list)

    # Associated content
    npcs: list[str] = field(default_factory=list)  # NPC IDs present here
    special_features: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)

    # Dungeon properties
    is_dungeon: bool = False
    dungeon_levels: Optional[int] = None

    # Visibility and discovery
    hidden: bool = False  # Must be searched for to find
    discovered: bool = False  # Has been found (for hidden POIs)
    visible_from_distance: bool = True  # Can be seen from elsewhere in hex
    approach_required: bool = True  # Must approach before entering

    # POI relationships and gated discovery
    parent_poi: Optional[str] = None  # Name of parent POI (for nested locations)
    requires_discovery: Optional[str] = None  # Secret name that must be found first
    child_pois: list[str] = field(default_factory=list)  # Names of child POIs within this one

    # Hex-level magical effects that apply at this POI
    magical_effects: list[str] = field(default_factory=list)  # e.g., ["no_teleportation", "no_scrying"]

    # Items and treasures at this location
    items: list[dict[str, Any]] = field(default_factory=list)  # [{name, description, value, taken}]

    # Automatic hazards triggered on approach/entry
    # Format: [{trigger, hazard_type, difficulty, description, save_type, damage}]
    # trigger: "on_approach", "on_enter", "on_exit", "always"
    # hazard_type: "swimming", "climbing", "jumping", "trap", "environmental"
    hazards: list[dict[str, Any]] = field(default_factory=list)

    # Locks/barriers preventing access
    # Format: [{type, requirement, description, bypassed, hidden, detected, magic_school}]
    # type: "magical", "physical", "puzzle", "key"
    # requirement: spell name, item name, key ID, or puzzle solution
    # hidden: if True, lock is not obvious - requires magic detection to find
    # detected: if True, hidden lock has been revealed by detection
    # magic_school: optional school of magic for magical locks (e.g., "abjuration", "illusion")
    locks: list[dict[str, Any]] = field(default_factory=list)

    # Dungeon linkage (for POIs that lead to dungeons)
    dungeon_id: Optional[str] = None  # ID of dungeon to transition to
    dungeon_entrance_room: Optional[str] = None  # Starting room in dungeon

    # Sub-locations within this POI (for non-dungeon exploration)
    # Format: [{name, description, access_condition, visible_from, features, items}]
    # access_condition: e.g., "diving", "climbing", "secret_door", None (always accessible)
    # visible_from: "surface", "underwater", "inside", "always"
    sub_locations: list[dict[str, Any]] = field(default_factory=list)

    # Sensory discovery hints - clues that draw players toward this POI
    # Format: {sense_type: {description, range, conditions}}
    # sense_type: "sound", "smell", "visual"
    # range: "nearby" (same hex), "adjacent" (1 hex away), "distant" (2+ hexes)
    # conditions: optional list of conditions, e.g., ["night_only", "wind_direction"]
    discovery_hints: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Ability grants - spells, skills, or effects that can be granted to characters
    # Format: [{name, ability_type, description, requirements, duration, once_per_character}]
    # ability_type: "spell", "skill", "blessing", "curse", "transformation"
    # requirements: optional dict with requirements (e.g., {"alignment": "Lawful"})
    # duration: "permanent", "until_rest", "1_day", "1_week", "until_used"
    # once_per_character: if True, can only be granted once to each character
    ability_grants: list[dict[str, Any]] = field(default_factory=list)

    # Alert/alarm systems - triggered by specific actions
    # Format: [{trigger, condition, effect, description, triggered}]
    # trigger: "on_enter", "on_enter_unauthorized", "on_item_taken", "on_combat"
    # condition: optional condition that must be met (e.g., "without_permission")
    # effect: "alert_inhabitants", "summon_guards", "lock_exits", "sound_alarm"
    # triggered: whether this alert has already fired (for one-time alerts)
    alerts: list[dict[str, Any]] = field(default_factory=list)

    # Concealed items hidden within fixtures/decorations
    # Format: [{name, hidden_in, search_dc, description, found}]
    # hidden_in: what the item is concealed in (e.g., "trophies", "bookshelf")
    # search_dc: difficulty to find (1-6 for d6, or "thorough" for careful search)
    # found: whether the item has been discovered
    concealed_items: list[dict[str, Any]] = field(default_factory=list)

    # Variable inhabitant counts (roll-based population)
    # Format: {base_inhabitants: [...], variable: [{roll, description}]}
    # base_inhabitants: always-present NPCs
    # variable: additional NPCs determined by roll (e.g., "1d6 hunters")
    variable_inhabitants: Optional[dict[str, Any]] = None

    # Entry conditions - requirements or encounters when entering
    # Format: {type, description, check_type, npc_id, outcomes}
    # type: "permission_required", "interrogation", "toll", "challenge"
    # check_type: "social", "payment", "password", "none"
    # npc_id: NPC who handles the entry check
    # outcomes: {success: ..., failure: ..., hostile: ...}
    entry_conditions: Optional[dict[str, Any]] = None

    # Quest hooks available at this POI
    # Format: [{quest_id, title, description, conditions, destination_hex, reward}]
    # conditions: requirements to receive the quest (e.g., {"disposition": "friendly"})
    # destination_hex: target hex for the quest (for cross-hex quests)
    quest_hooks: list[dict[str, Any]] = field(default_factory=list)

    # Time-of-day variant descriptions
    description_day: Optional[str] = None  # Description during daylight
    description_night: Optional[str] = None  # Description at night
    interior_day: Optional[str] = None  # Interior during day
    interior_night: Optional[str] = None  # Interior at night
    entering_day: Optional[str] = None  # Entering during day
    entering_night: Optional[str] = None  # Entering at night

    # POI availability conditions (for ENCOUNTERS/DUNGEON states)
    # Format: {type: "moon_phase", required: "full_moon", hidden_message: "The manor has vanished..."}
    # Types: "moon_phase", "time_of_day", "seasonal", "condition"
    # When not available, POI cannot be entered and hidden_message is shown
    availability: Optional[dict[str, Any]] = None

    # Contextual encounter modifiers - affects hex-level random encounters
    # Format: [{chance: "2-in-6", result: "bewildered banshee", context: "heading to a ball"}]
    # When rolling hex encounters, these modifiers may replace or supplement standard results
    encounter_modifiers: list[dict[str, Any]] = field(default_factory=list)

    # Item persistence rules for this POI (for DUNGEON state)
    # Format: {default: "evaporate", exceptions: [{owner_npc: "lord_hobbled...", persists: True}]}
    # Controls what happens to items taken from this location
    item_persistence: Optional[dict[str, Any]] = None

    # Dynamic room generation for procedural dungeons (for DUNGEON state)
    # Format: {connections_per_room: "1d3", room_table: "Rooms", encounter_table: "Encounters"}
    # Enables randomly generated room connections instead of fixed maps
    dynamic_layout: Optional[dict[str, Any]] = None

    def is_visible(self, discovered_secrets: Optional[set[str]] = None) -> bool:
        """
        Check if POI is currently visible to players.

        Args:
            discovered_secrets: Set of secret names that have been discovered

        Returns:
            True if visible (not hidden or has been discovered, and requirements met)
        """
        # Basic visibility check
        if self.hidden and not self.discovered:
            return False

        # Check if a secret must be discovered first
        if self.requires_discovery:
            if discovered_secrets is None or self.requires_discovery not in discovered_secrets:
                return False

        return True

    def is_accessible_from(self, current_poi: Optional[str]) -> bool:
        """
        Check if this POI can be accessed from the current location.

        Args:
            current_poi: Name of the current POI (None if in general hex)

        Returns:
            True if accessible from current location
        """
        # If no parent, accessible from hex-level
        if not self.parent_poi:
            return current_poi is None

        # If has parent, must be at or inside that parent
        return current_poi == self.parent_poi

    def get_hazards_for_trigger(self, trigger: str) -> list[dict[str, Any]]:
        """
        Get hazards that trigger at a specific point.

        Args:
            trigger: "on_approach", "on_enter", "on_exit", "always"

        Returns:
            List of hazard definitions that trigger at this point
        """
        return [h for h in self.hazards if h.get("trigger") == trigger or h.get("trigger") == "always"]

    def get_active_locks(self, include_hidden: bool = False) -> list[dict[str, Any]]:
        """
        Get locks that haven't been bypassed.

        Args:
            include_hidden: If True, include hidden locks that haven't been detected

        Returns:
            List of active lock definitions
        """
        result = []
        for lock in self.locks:
            if lock.get("bypassed", False):
                continue
            # Hidden locks only show if detected or include_hidden is True
            if lock.get("hidden", False) and not lock.get("detected", False):
                if include_hidden:
                    result.append(lock)
                continue
            result.append(lock)
        return result

    def get_visible_locks(self) -> list[dict[str, Any]]:
        """Get locks that are visible (not hidden, or hidden but detected)."""
        return self.get_active_locks(include_hidden=False)

    def get_hidden_locks(self) -> list[dict[str, Any]]:
        """Get hidden locks that haven't been detected yet."""
        return [
            lock for lock in self.locks
            if not lock.get("bypassed", False)
            and lock.get("hidden", False)
            and not lock.get("detected", False)
        ]

    def get_magical_properties(self) -> list[dict[str, Any]]:
        """
        Get all magical properties at this POI for magic detection.

        Returns list of magical elements including:
        - Magical locks/barriers
        - Magical effects
        - Magic items
        """
        magical = []

        # Magical locks
        for i, lock in enumerate(self.locks):
            if lock.get("type") == "magical" and not lock.get("bypassed", False):
                magical.append({
                    "category": "lock",
                    "index": i,
                    "hidden": lock.get("hidden", False),
                    "detected": lock.get("detected", False),
                    "school": lock.get("magic_school"),
                    "description": lock.get("description", "A magical barrier"),
                })

        # Magical effects at the POI
        for effect in self.magical_effects:
            magical.append({
                "category": "effect",
                "description": effect,
            })

        # Magic items (if any are present and not taken)
        for item in self.items:
            if item.get("magical", False) and not item.get("taken", False):
                magical.append({
                    "category": "item",
                    "name": item.get("name"),
                    "hidden": item.get("hidden", False),
                })

        return magical

    def reveal_magical_lock(self, lock_index: int) -> bool:
        """
        Mark a hidden magical lock as detected.

        Args:
            lock_index: Index of the lock in the locks list

        Returns:
            True if successfully revealed
        """
        if 0 <= lock_index < len(self.locks):
            self.locks[lock_index]["detected"] = True
            return True
        return False

    def has_active_locks(self) -> bool:
        """Check if there are any active locks preventing access."""
        return len(self.get_active_locks()) > 0

    def check_lock_requirement(
        self,
        lock: dict[str, Any],
        available_spells: list[str],
        available_items: list[str],
        available_keys: list[str],
    ) -> bool:
        """
        Check if a lock's requirement is satisfied.

        Args:
            lock: Lock definition dict
            available_spells: List of spell names the party can cast
            available_items: List of magic item names the party has
            available_keys: List of key IDs the party possesses

        Returns:
            True if the lock can be bypassed
        """
        lock_type = lock.get("type", "physical")
        requirement = lock.get("requirement", "")

        if lock_type == "magical":
            # Check if party has the required spell or magic item
            req_lower = requirement.lower()
            for spell in available_spells:
                if spell.lower() == req_lower or req_lower in spell.lower():
                    return True
            for item in available_items:
                if item.lower() == req_lower or req_lower in item.lower():
                    return True
            return False

        elif lock_type == "key":
            # Check if party has the required key
            return requirement in available_keys

        elif lock_type == "physical":
            # Physical locks might require strength check or lockpicking
            # Return False here - actual check happens in engine
            return False

        elif lock_type == "puzzle":
            # Puzzles are resolved through gameplay
            return False

        return False

    def bypass_lock(self, lock_index: int) -> bool:
        """
        Mark a lock as bypassed.

        Args:
            lock_index: Index of the lock in the locks list

        Returns:
            True if successfully bypassed
        """
        if 0 <= lock_index < len(self.locks):
            self.locks[lock_index]["bypassed"] = True
            return True
        return False

    def leads_to_dungeon(self) -> bool:
        """Check if this POI leads to a dungeon."""
        return self.is_dungeon or self.dungeon_id is not None

    # =========================================================================
    # SUB-LOCATION METHODS
    # =========================================================================

    def get_sub_locations(
        self,
        access_context: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get sub-locations accessible from the current context.

        Args:
            access_context: Current access condition (e.g., "surface", "underwater", "inside")
                           If None, returns all sub-locations.

        Returns:
            List of accessible sub-location definitions
        """
        if access_context is None:
            return self.sub_locations

        accessible = []
        for sub_loc in self.sub_locations:
            visible_from = sub_loc.get("visible_from", "always")

            # Check if visible from current context
            if visible_from == "always":
                accessible.append(sub_loc)
            elif visible_from == access_context:
                accessible.append(sub_loc)
            elif visible_from == "underwater" and access_context == "diving":
                accessible.append(sub_loc)
            elif visible_from == "surface" and access_context in ("surface", None):
                accessible.append(sub_loc)
            elif visible_from == "inside" and access_context == "inside":
                accessible.append(sub_loc)

        return accessible

    def get_sub_location_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """
        Get a specific sub-location by name.

        Args:
            name: Name of the sub-location

        Returns:
            Sub-location definition or None if not found
        """
        for sub_loc in self.sub_locations:
            if sub_loc.get("name", "").lower() == name.lower():
                return sub_loc
        return None

    def can_access_sub_location(
        self,
        sub_location_name: str,
        current_context: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a sub-location can be accessed from the current context.

        Args:
            sub_location_name: Name of the sub-location to access
            current_context: Current access context (surface, diving, inside, etc.)

        Returns:
            Tuple of (can_access, required_condition_if_not)
        """
        sub_loc = self.get_sub_location_by_name(sub_location_name)
        if not sub_loc:
            return False, None

        access_condition = sub_loc.get("access_condition")

        # No special access required
        if access_condition is None:
            return True, None

        # Check if current context satisfies the condition
        if access_condition == "diving" and current_context not in ("underwater", "diving"):
            return False, "diving"
        if access_condition == "climbing" and current_context != "climbing":
            return False, "climbing"
        if access_condition == "secret_door" and current_context != "discovered":
            return False, "discovering the secret entrance"

        return True, None

    def get_visible_features_from_context(
        self,
        context: str = "surface",
    ) -> list[str]:
        """
        Get features visible from a specific context.

        Some features may only be visible when diving, at night,
        or from specific vantage points.

        Args:
            context: Current viewing context (surface, underwater, inside, etc.)

        Returns:
            List of visible feature descriptions
        """
        visible = []

        for feature in self.special_features:
            feature_lower = feature.lower()

            # Check visibility conditions
            if "(underwater only)" in feature_lower or "(diving)" in feature_lower:
                if context in ("underwater", "diving"):
                    visible.append(feature)
            elif "(surface)" in feature_lower or "(from surface)" in feature_lower:
                if context == "surface":
                    visible.append(feature)
            elif "(inside)" in feature_lower:
                if context == "inside":
                    visible.append(feature)
            else:
                # No context restriction - always visible
                visible.append(feature)

        return visible

    def get_description(self, is_night: bool = False) -> str:
        """Get appropriate description based on time of day."""
        if is_night and self.description_night:
            return self.description_night
        if not is_night and self.description_day:
            return self.description_day
        return self.description

    def get_entering_description(self, is_night: bool = False) -> Optional[str]:
        """Get appropriate entering description based on time of day."""
        if is_night and self.entering_night:
            return self.entering_night
        if not is_night and self.entering_day:
            return self.entering_day
        return self.entering

    def get_interior_description(self, is_night: bool = False) -> Optional[str]:
        """Get appropriate interior description based on time of day."""
        if is_night and self.interior_night:
            return self.interior_night
        if not is_night and self.interior_day:
            return self.interior_day
        return self.interior

    # =========================================================================
    # SENSORY DISCOVERY HINTS
    # =========================================================================

    def get_active_discovery_hints(
        self,
        is_night: bool = False,
        wind_from: Optional[str] = None,
        current_range: str = "nearby",
    ) -> list[dict[str, Any]]:
        """
        Get discovery hints that are currently perceivable.

        Args:
            is_night: Whether it's nighttime
            wind_from: Direction the wind is blowing from (for smell propagation)
            current_range: How far the observer is ("nearby", "adjacent", "distant")

        Returns:
            List of active hint definitions with sense_type, description, and range
        """
        active_hints = []
        range_priority = {"nearby": 0, "adjacent": 1, "distant": 2}
        current_priority = range_priority.get(current_range, 0)

        for sense_type, hint_data in self.discovery_hints.items():
            hint_range = hint_data.get("range", "nearby")
            hint_priority = range_priority.get(hint_range, 0)

            # Skip if hint doesn't carry this far
            if hint_priority < current_priority:
                continue

            # Check conditions
            conditions = hint_data.get("conditions", [])
            if conditions:
                condition_met = True
                for condition in conditions:
                    if condition == "night_only" and not is_night:
                        condition_met = False
                        break
                    elif condition == "day_only" and is_night:
                        condition_met = False
                        break
                    elif condition == "wind_direction" and wind_from:
                        # Smell only carries if wind is favorable
                        # This could be expanded with actual wind logic
                        pass
                if not condition_met:
                    continue

            active_hints.append({
                "sense_type": sense_type,
                "description": hint_data.get("description", ""),
                "range": hint_range,
                "poi_name": self.name,
                "hidden": self.hidden,
            })

        return active_hints

    def has_discovery_hints(self) -> bool:
        """Check if this POI has any sensory discovery hints."""
        return len(self.discovery_hints) > 0

    def mark_discovered(self) -> None:
        """Mark this POI as discovered."""
        self.discovered = True

    # =========================================================================
    # ALERT/ALARM METHODS
    # =========================================================================

    def get_alerts_for_trigger(self, trigger: str) -> list[dict[str, Any]]:
        """
        Get alerts that should fire for a specific trigger.

        Args:
            trigger: The trigger event (on_enter, on_enter_unauthorized, etc.)

        Returns:
            List of alert definitions that match this trigger
        """
        return [
            alert for alert in self.alerts
            if alert.get("trigger") == trigger and not alert.get("triggered", False)
        ]

    def trigger_alert(self, alert_index: int) -> dict[str, Any]:
        """
        Mark an alert as triggered and return its effect.

        Args:
            alert_index: Index of the alert in the alerts list

        Returns:
            The alert definition with effect details
        """
        if 0 <= alert_index < len(self.alerts):
            alert = self.alerts[alert_index]
            # Mark one-time alerts as triggered
            if alert.get("one_time", True):
                self.alerts[alert_index]["triggered"] = True
            return alert
        return {}

    def has_active_alerts(self, trigger: str) -> bool:
        """Check if there are any untriggered alerts for a given trigger."""
        return len(self.get_alerts_for_trigger(trigger)) > 0

    # =========================================================================
    # CONCEALED ITEM METHODS
    # =========================================================================

    def get_concealed_items(self, include_found: bool = False) -> list[dict[str, Any]]:
        """
        Get concealed items at this POI.

        Args:
            include_found: If True, include already-found items

        Returns:
            List of concealed item definitions
        """
        if include_found:
            return self.concealed_items
        return [item for item in self.concealed_items if not item.get("found", False)]

    def search_for_concealed(
        self,
        location: str,
        search_roll: int,
        thorough: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search a specific location for concealed items.

        Args:
            location: Where to search (e.g., "trophies", "bookshelf")
            search_roll: The d6 search roll result
            thorough: If True, this is a thorough/careful search

        Returns:
            List of found items
        """
        found = []
        for i, item in enumerate(self.concealed_items):
            if item.get("found", False):
                continue

            hidden_in = item.get("hidden_in", "").lower()
            if location.lower() not in hidden_in and hidden_in not in location.lower():
                continue

            search_dc = item.get("search_dc", 3)
            if search_dc == "thorough":
                if thorough:
                    self.concealed_items[i]["found"] = True
                    found.append(item)
            elif isinstance(search_dc, int):
                if search_roll >= search_dc:
                    self.concealed_items[i]["found"] = True
                    found.append(item)

        return found

    def reveal_concealed_item(self, item_name: str) -> bool:
        """
        Mark a concealed item as found.

        Args:
            item_name: Name of the item to reveal

        Returns:
            True if item was found and marked
        """
        for i, item in enumerate(self.concealed_items):
            if item.get("name", "").lower() == item_name.lower():
                self.concealed_items[i]["found"] = True
                return True
        return False

    # =========================================================================
    # VARIABLE INHABITANTS METHODS
    # =========================================================================

    def get_current_inhabitants(
        self,
        dice_roller: Optional[Any] = None,
        cached_roll: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Get the current inhabitants, resolving variable counts.

        Args:
            dice_roller: DiceRoller instance for rolling variable counts
            cached_roll: Previously rolled value (to maintain consistency)

        Returns:
            Dict with base_inhabitants and variable_inhabitants lists
        """
        result = {
            "base_inhabitants": self.npcs.copy(),
            "variable_inhabitants": [],
            "variable_count": 0,
        }

        if not self.variable_inhabitants:
            return result

        result["base_inhabitants"] = self.variable_inhabitants.get(
            "base_inhabitants", self.npcs
        ).copy()

        variable = self.variable_inhabitants.get("variable", [])
        for var in variable:
            roll_expr = var.get("roll", "0")
            description = var.get("description", "")

            if cached_roll is not None:
                count = cached_roll
            elif dice_roller:
                count = dice_roller.roll(roll_expr).total
            else:
                # Default to parsing the dice expression for average
                # e.g., "1d6" -> 3
                count = 3

            result["variable_inhabitants"].append({
                "count": count,
                "description": description,
                "roll_expression": roll_expr,
            })
            result["variable_count"] += count

        return result

    # =========================================================================
    # ENTRY CONDITIONS METHODS
    # =========================================================================

    def has_entry_conditions(self) -> bool:
        """Check if this POI has entry conditions."""
        return self.entry_conditions is not None

    def get_entry_condition_type(self) -> Optional[str]:
        """Get the type of entry condition (permission, interrogation, etc.)."""
        if self.entry_conditions:
            return self.entry_conditions.get("type")
        return None

    def check_entry_allowed(
        self,
        has_permission: bool = False,
        payment_offered: int = 0,
        password_given: Optional[str] = None,
        social_result: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Check if entry is allowed based on conditions.

        Args:
            has_permission: Whether the party has permission to enter
            payment_offered: Amount of payment offered (for toll)
            password_given: Password provided (for password check)
            social_result: Result of social check (success, failure, hostile)

        Returns:
            Dict with allowed, outcome, and description
        """
        if not self.entry_conditions:
            return {"allowed": True, "outcome": "none", "description": ""}

        cond_type = self.entry_conditions.get("type", "none")
        outcomes = self.entry_conditions.get("outcomes", {})

        if cond_type == "permission_required":
            if has_permission:
                return {
                    "allowed": True,
                    "outcome": "success",
                    "description": outcomes.get("success", "Entry granted"),
                }
            else:
                return {
                    "allowed": False,
                    "outcome": "failure",
                    "description": outcomes.get("failure", "Entry denied"),
                    "triggers_alert": True,
                }

        elif cond_type == "interrogation":
            if social_result == "success":
                return {
                    "allowed": True,
                    "outcome": "success",
                    "description": outcomes.get("success", "You may pass"),
                }
            elif social_result == "hostile":
                return {
                    "allowed": False,
                    "outcome": "hostile",
                    "description": outcomes.get("hostile", "Combat ensues"),
                    "triggers_combat": True,
                }
            else:
                return {
                    "allowed": False,
                    "outcome": "failure",
                    "description": outcomes.get("failure", "Move along"),
                }

        elif cond_type == "toll":
            toll_amount = self.entry_conditions.get("toll_amount", 0)
            if payment_offered >= toll_amount:
                return {
                    "allowed": True,
                    "outcome": "success",
                    "description": outcomes.get("success", "Toll accepted"),
                    "payment_taken": toll_amount,
                }
            else:
                return {
                    "allowed": False,
                    "outcome": "failure",
                    "description": outcomes.get("failure", "Insufficient payment"),
                }

        elif cond_type == "password":
            correct_password = self.entry_conditions.get("password", "")
            if password_given and password_given.lower() == correct_password.lower():
                return {
                    "allowed": True,
                    "outcome": "success",
                    "description": outcomes.get("success", "Password accepted"),
                }
            else:
                return {
                    "allowed": False,
                    "outcome": "failure",
                    "description": outcomes.get("failure", "Incorrect password"),
                }

        return {"allowed": True, "outcome": "none", "description": ""}

    # =========================================================================
    # QUEST HOOK METHODS
    # =========================================================================

    def get_available_quests(
        self,
        party_disposition: str = "neutral",
        party_level: int = 1,
        completed_quests: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Get quest hooks available to the party.

        Args:
            party_disposition: Party's disposition with POI (friendly, neutral, hostile)
            party_level: Average party level (for level requirements)
            completed_quests: Set of quest IDs already completed

        Returns:
            List of available quest definitions
        """
        completed = completed_quests or set()
        available = []

        for quest in self.quest_hooks:
            quest_id = quest.get("quest_id", "")

            # Skip completed quests
            if quest_id in completed:
                continue

            # Check conditions
            conditions = quest.get("conditions", {})

            # Check disposition requirement
            required_disposition = conditions.get("disposition")
            if required_disposition:
                disposition_order = ["hostile", "neutral", "friendly"]
                if disposition_order.index(party_disposition) < disposition_order.index(required_disposition):
                    continue

            # Check level requirement
            min_level = conditions.get("min_level", 0)
            if party_level < min_level:
                continue

            available.append(quest)

        return available

    def has_quest_hooks(self) -> bool:
        """Check if this POI has any quest hooks."""
        return len(self.quest_hooks) > 0


@dataclass
class HexStateChange:
    """
    Tracks a world-state change that occurred in a hex.

    Used to record permanent changes to hex/POI state caused by player actions.
    Examples:
    - Removing the Hand of St Howarth lifts the curse on Lankston Pool
    - Killing the lord of a manor changes its description
    - Solving a puzzle opens a secret passage permanently
    """
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hex_id: str = ""
    poi_name: Optional[str] = None  # If change is to a specific POI

    # What triggered this change
    trigger_action: str = ""  # e.g., "item_removed", "npc_killed", "puzzle_solved", "spell_cast"
    trigger_details: dict[str, Any] = field(default_factory=dict)  # e.g., {"item": "Hand of St Howarth"}

    # What changed
    change_type: str = ""  # e.g., "curse_lifted", "description_changed", "npc_removed", "access_granted"
    before_state: dict[str, Any] = field(default_factory=dict)  # State before change
    after_state: dict[str, Any] = field(default_factory=dict)  # State after change

    # Narrative consequence
    narrative_description: str = ""  # Player-facing description of what happened

    # When this occurred
    occurred_at: Optional["GameDate"] = None

    # Whether this change is reversible
    reversible: bool = False
    reverse_condition: Optional[str] = None  # How to reverse the change


@dataclass
class WorldStateChanges:
    """
    Container for all world-state changes in a campaign.

    Tracks permanent mutations to hexes, POIs, NPCs, etc. caused by player actions.
    """
    changes: list[HexStateChange] = field(default_factory=list)

    # Index for quick lookup
    _by_hex: dict[str, list[HexStateChange]] = field(default_factory=dict)
    _by_poi: dict[str, list[HexStateChange]] = field(default_factory=dict)

    def add_change(self, change: HexStateChange) -> None:
        """Add a new state change."""
        self.changes.append(change)

        # Update indices
        if change.hex_id not in self._by_hex:
            self._by_hex[change.hex_id] = []
        self._by_hex[change.hex_id].append(change)

        if change.poi_name:
            key = f"{change.hex_id}:{change.poi_name}"
            if key not in self._by_poi:
                self._by_poi[key] = []
            self._by_poi[key].append(change)

    def get_changes_for_hex(self, hex_id: str) -> list[HexStateChange]:
        """Get all changes that have occurred in a hex."""
        return self._by_hex.get(hex_id, [])

    def get_changes_for_poi(self, hex_id: str, poi_name: str) -> list[HexStateChange]:
        """Get all changes that have occurred at a specific POI."""
        key = f"{hex_id}:{poi_name}"
        return self._by_poi.get(key, [])

    def has_change_type(
        self,
        hex_id: str,
        change_type: str,
        poi_name: Optional[str] = None,
    ) -> bool:
        """Check if a specific type of change has occurred."""
        changes = self.get_changes_for_poi(hex_id, poi_name) if poi_name else self.get_changes_for_hex(hex_id)
        return any(c.change_type == change_type for c in changes)

    def get_current_state(
        self,
        hex_id: str,
        state_key: str,
        poi_name: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Get the current value of a state key after all changes.

        Returns the 'after_state' value of the most recent change
        that affects this state key, or None if no changes.
        """
        changes = self.get_changes_for_poi(hex_id, poi_name) if poi_name else self.get_changes_for_hex(hex_id)

        # Find the most recent change affecting this key
        for change in reversed(changes):
            if state_key in change.after_state:
                return change.after_state[state_key]

        return None

    def is_condition_active(
        self,
        hex_id: str,
        condition: str,
        poi_name: Optional[str] = None,
    ) -> bool:
        """
        Check if a condition (like a curse) is still active.

        Conditions start as active and become inactive when a change
        of type "{condition}_lifted" or "{condition}_removed" is recorded.
        """
        changes = self.get_changes_for_poi(hex_id, poi_name) if poi_name else self.get_changes_for_hex(hex_id)

        # Check for lifting/removal of condition
        lifted_types = [f"{condition}_lifted", f"{condition}_removed", f"remove_{condition}"]
        return not any(c.change_type in lifted_types for c in changes)


# =============================================================================
# SCHEDULED EVENTS AND INVITATIONS
# =============================================================================


class EventType(str, Enum):
    """Types of scheduled events."""
    INVITATION = "invitation"        # Invitation to return to a location
    BLESSING = "blessing"            # Temporary blessing expires
    CURSE = "curse"                  # Curse takes effect or expires
    MEETING = "meeting"              # Scheduled meeting with NPC
    FESTIVAL = "festival"            # Seasonal or Wysenday festival
    TRANSFORMATION = "transformation"  # Time-triggered transformation
    QUEST_DEADLINE = "quest_deadline"  # Quest timer expires


@dataclass
class ScheduledEvent:
    """
    An event scheduled to occur at a specific time or condition.

    Used for invitations, delayed rewards, timed curses, and other
    future-triggered game events.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.INVITATION

    # When issued
    created_at: Optional["GameDate"] = None

    # Who/what is affected
    character_ids: list[str] = field(default_factory=list)  # Empty = entire party

    # Source of the event
    source_hex_id: Optional[str] = None
    source_poi_name: Optional[str] = None
    source_npc_id: Optional[str] = None

    # Event trigger conditions (at least one must be set)
    trigger_date: Optional["GameDate"] = None  # Specific date
    trigger_moon_phase: Optional[MoonPhase] = None  # Specific moon phase
    trigger_condition: Optional[str] = None  # Narrative condition (e.g., "return to grove")
    days_until_trigger: Optional[int] = None  # Days from creation

    # Event details
    title: str = ""
    description: str = ""  # Full description for DM
    player_message: str = ""  # What players were told

    # Reward/effect when triggered
    effect_type: str = ""  # e.g., "healing", "spell_grant", "item_grant", "curse_removal"
    effect_details: dict[str, Any] = field(default_factory=dict)

    # State tracking
    triggered: bool = False
    triggered_at: Optional["GameDate"] = None
    expired: bool = False
    expiry_date: Optional["GameDate"] = None

    def is_active(self, current_date: "GameDate") -> bool:
        """Check if the event is still active (not triggered or expired)."""
        if self.triggered or self.expired:
            return False
        if self.expiry_date and self._date_compare(current_date, self.expiry_date) > 0:
            return False
        return True

    def check_trigger(
        self,
        current_date: "GameDate",
        current_hex: Optional[str] = None,
        current_poi: Optional[str] = None,
        condition_met: bool = False,
    ) -> bool:
        """
        Check if the event should trigger.

        Args:
            current_date: Current game date
            current_hex: Hex the party is currently in
            current_poi: POI the party is currently at
            condition_met: Whether narrative condition is met

        Returns:
            True if the event should trigger now
        """
        if not self.is_active(current_date):
            return False

        # Check date trigger
        if self.trigger_date and self._date_compare(current_date, self.trigger_date) >= 0:
            return True

        # Check days elapsed trigger
        if self.days_until_trigger is not None and self.created_at:
            target_date = self.created_at.advance_days(self.days_until_trigger)
            if self._date_compare(current_date, target_date) >= 0:
                return True

        # Check moon phase trigger
        if self.trigger_moon_phase:
            if current_date.get_moon_phase() == self.trigger_moon_phase:
                return True

        # Check location-based trigger (return to place)
        if self.trigger_condition == "return to grove" or self.trigger_condition == "return":
            if current_hex == self.source_hex_id:
                if current_poi == self.source_poi_name or self.source_poi_name is None:
                    return True

        # Check custom condition
        if self.trigger_condition and condition_met:
            return True

        return False

    def trigger(self, current_date: "GameDate") -> dict[str, Any]:
        """
        Mark the event as triggered and return the effect.

        Returns:
            Dict with effect_type and effect_details for processing
        """
        self.triggered = True
        self.triggered_at = current_date

        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "title": self.title,
            "description": self.description,
            "player_message": self.player_message,
            "effect_type": self.effect_type,
            "effect_details": self.effect_details,
            "character_ids": self.character_ids,
        }

    def _date_compare(self, d1: "GameDate", d2: "GameDate") -> int:
        """Compare two dates. Returns -1, 0, or 1."""
        if d1.year != d2.year:
            return -1 if d1.year < d2.year else 1
        if d1.month != d2.month:
            return -1 if d1.month < d2.month else 1
        if d1.day != d2.day:
            return -1 if d1.day < d2.day else 1
        return 0


@dataclass
class EventScheduler:
    """
    Manages all scheduled events for the campaign.

    Tracks invitations, delayed rewards, and timed effects.
    """
    events: list[ScheduledEvent] = field(default_factory=list)

    # Indices for quick lookup
    _by_character: dict[str, list[ScheduledEvent]] = field(default_factory=dict)
    _by_source: dict[str, list[ScheduledEvent]] = field(default_factory=dict)

    def add_event(self, event: ScheduledEvent) -> None:
        """Add a scheduled event."""
        self.events.append(event)

        # Index by character
        for char_id in event.character_ids:
            if char_id not in self._by_character:
                self._by_character[char_id] = []
            self._by_character[char_id].append(event)

        # Index by source
        source_key = f"{event.source_hex_id}:{event.source_poi_name}"
        if source_key not in self._by_source:
            self._by_source[source_key] = []
        self._by_source[source_key].append(event)

    def create_invitation(
        self,
        source_hex: str,
        source_poi: str,
        character_ids: list[str],
        title: str,
        player_message: str,
        effect_type: str,
        effect_details: dict[str, Any],
        current_date: "GameDate",
        trigger_condition: str = "return",
        expiry_days: Optional[int] = None,
    ) -> ScheduledEvent:
        """
        Create an invitation for characters to return for a reward.

        Args:
            source_hex: Hex issuing the invitation
            source_poi: POI issuing the invitation
            character_ids: Characters who received the invitation
            title: Event title
            player_message: What the players were told
            effect_type: Type of reward (healing, spell_grant, etc.)
            effect_details: Details of the reward
            current_date: When the invitation was issued
            trigger_condition: What triggers the reward (default: "return")
            expiry_days: Days until invitation expires (None = never)

        Returns:
            The created ScheduledEvent
        """
        expiry = current_date.advance_days(expiry_days) if expiry_days else None

        event = ScheduledEvent(
            event_type=EventType.INVITATION,
            created_at=current_date,
            character_ids=character_ids,
            source_hex_id=source_hex,
            source_poi_name=source_poi,
            trigger_condition=trigger_condition,
            title=title,
            player_message=player_message,
            effect_type=effect_type,
            effect_details=effect_details,
            expiry_date=expiry,
        )

        self.add_event(event)
        return event

    def get_events_for_character(self, character_id: str) -> list[ScheduledEvent]:
        """Get all events affecting a character."""
        return self._by_character.get(character_id, [])

    def get_active_events_for_character(
        self,
        character_id: str,
        current_date: "GameDate",
    ) -> list[ScheduledEvent]:
        """Get active (non-triggered, non-expired) events for a character."""
        return [
            e for e in self.get_events_for_character(character_id)
            if e.is_active(current_date)
        ]

    def get_events_at_location(
        self,
        hex_id: str,
        poi_name: Optional[str] = None,
    ) -> list[ScheduledEvent]:
        """Get events tied to a specific location."""
        source_key = f"{hex_id}:{poi_name}"
        return self._by_source.get(source_key, [])

    def check_triggers(
        self,
        current_date: "GameDate",
        current_hex: Optional[str] = None,
        current_poi: Optional[str] = None,
        conditions_met: Optional[dict[str, bool]] = None,
    ) -> list[dict[str, Any]]:
        """
        Check all events for triggers and return triggered effects.

        Args:
            current_date: Current game date
            current_hex: Current hex location
            current_poi: Current POI (if any)
            conditions_met: Dict mapping event IDs to condition status

        Returns:
            List of triggered event effects
        """
        triggered = []
        conditions = conditions_met or {}

        for event in self.events:
            if not event.is_active(current_date):
                continue

            condition_met = conditions.get(event.event_id, False)

            if event.check_trigger(current_date, current_hex, current_poi, condition_met):
                effect = event.trigger(current_date)
                triggered.append(effect)

        return triggered

    def get_pending_invitations(self, current_date: "GameDate") -> list[ScheduledEvent]:
        """Get all pending (active) invitations."""
        return [
            e for e in self.events
            if e.event_type == EventType.INVITATION and e.is_active(current_date)
        ]


# =============================================================================
# GRANTED ABILITIES TRACKING
# =============================================================================


class AbilityType(str, Enum):
    """Types of grantable abilities."""
    SPELL = "spell"              # Magic spell added to character's repertoire
    SKILL = "skill"              # Skill or proficiency
    BLESSING = "blessing"        # Divine or nature blessing (temporary bonus)
    CURSE = "curse"              # Curse or negative effect
    TRANSFORMATION = "transformation"  # Physical or magical transformation
    SPECIAL = "special"          # Unique ability specific to the source


@dataclass
class GrantedAbility:
    """
    An ability granted to a character by a hex feature, POI, or NPC.

    Tracks spells, blessings, curses, and other abilities that can
    be granted to characters through exploration and interaction.
    """
    grant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    character_id: str = ""

    # Source of the grant
    source_hex_id: str = ""
    source_poi_name: Optional[str] = None
    source_description: str = ""  # Human-readable source

    # The ability
    ability_name: str = ""
    ability_type: AbilityType = AbilityType.SPELL
    description: str = ""

    # For spells, the spell details
    spell_level: Optional[int] = None
    spell_school: Optional[str] = None
    spell_data: Optional[dict[str, Any]] = None  # Full spell definition

    # Duration and tracking
    duration: str = "permanent"  # permanent, until_rest, 1_day, 1_week, until_used
    uses_remaining: Optional[int] = None  # For limited-use abilities
    granted_at: Optional["GameDate"] = None
    expires_at: Optional["GameDate"] = None

    # State
    is_active: bool = True
    used: bool = False  # For "until_used" abilities

    def is_expired(self, current_date: "GameDate") -> bool:
        """Check if this granted ability has expired."""
        if not self.is_active:
            return True
        if self.duration == "until_used" and self.used:
            return True
        if self.expires_at:
            return self._date_compare(current_date, self.expires_at) > 0
        return False

    def use(self) -> bool:
        """
        Mark the ability as used (for limited-use abilities).

        Returns True if successfully used, False if already exhausted.
        """
        if self.uses_remaining is not None:
            if self.uses_remaining <= 0:
                return False
            self.uses_remaining -= 1
            if self.uses_remaining <= 0:
                self.is_active = False
            return True
        elif self.duration == "until_used":
            if self.used:
                return False
            self.used = True
            self.is_active = False
            return True
        return True  # Permanent abilities can always be used

    def _date_compare(self, d1: "GameDate", d2: "GameDate") -> int:
        """Compare two dates. Returns -1, 0, or 1."""
        if d1.year != d2.year:
            return -1 if d1.year < d2.year else 1
        if d1.month != d2.month:
            return -1 if d1.month < d2.month else 1
        if d1.day != d2.day:
            return -1 if d1.day < d2.day else 1
        return 0


@dataclass
class AbilityGrantTracker:
    """
    Tracks all granted abilities across the campaign.

    Manages spell grants, blessings, curses, and other abilities
    given to characters by hex features, POIs, and NPCs.
    """
    granted_abilities: list[GrantedAbility] = field(default_factory=list)

    # Track which abilities have been granted to prevent double-grants
    # Format: {(character_id, source_key, ability_name)}
    _grants_issued: set[tuple[str, str, str]] = field(default_factory=set)

    def grant_ability(
        self,
        character_id: str,
        ability_name: str,
        ability_type: AbilityType,
        source_hex_id: str,
        source_poi_name: Optional[str],
        description: str,
        current_date: "GameDate",
        duration: str = "permanent",
        spell_level: Optional[int] = None,
        spell_school: Optional[str] = None,
        spell_data: Optional[dict[str, Any]] = None,
        uses: Optional[int] = None,
        once_per_character: bool = True,
    ) -> Optional[GrantedAbility]:
        """
        Grant an ability to a character.

        Args:
            character_id: Character receiving the ability
            ability_name: Name of the ability/spell
            ability_type: Type of ability
            source_hex_id: Hex where ability was granted
            source_poi_name: POI that granted the ability
            description: Description of the ability
            current_date: Current game date
            duration: How long the ability lasts
            spell_level: For spells, the spell level
            spell_school: For spells, the school of magic
            spell_data: Full spell definition if applicable
            uses: Number of uses (None = unlimited)
            once_per_character: If True, cannot grant same ability twice

        Returns:
            The GrantedAbility if granted, None if already granted
        """
        source_key = f"{source_hex_id}:{source_poi_name}"

        # Check for duplicate grants
        if once_per_character:
            grant_key = (character_id, source_key, ability_name)
            if grant_key in self._grants_issued:
                return None
            self._grants_issued.add(grant_key)

        # Calculate expiry date
        expires_at = None
        if duration == "1_day":
            expires_at = current_date.advance_days(1)
        elif duration == "1_week":
            expires_at = current_date.advance_days(7)

        # Create the granted ability
        granted = GrantedAbility(
            character_id=character_id,
            source_hex_id=source_hex_id,
            source_poi_name=source_poi_name,
            source_description=f"{source_poi_name or 'Unknown'} in hex {source_hex_id}",
            ability_name=ability_name,
            ability_type=ability_type,
            description=description,
            spell_level=spell_level,
            spell_school=spell_school,
            spell_data=spell_data,
            duration=duration,
            uses_remaining=uses,
            granted_at=current_date,
            expires_at=expires_at,
        )

        self.granted_abilities.append(granted)
        return granted

    def get_character_abilities(
        self,
        character_id: str,
        current_date: Optional["GameDate"] = None,
        include_expired: bool = False,
    ) -> list[GrantedAbility]:
        """Get all granted abilities for a character."""
        abilities = [
            a for a in self.granted_abilities
            if a.character_id == character_id
        ]

        if not include_expired and current_date:
            abilities = [a for a in abilities if not a.is_expired(current_date)]

        return abilities

    def get_character_spells(
        self,
        character_id: str,
        current_date: Optional["GameDate"] = None,
    ) -> list[GrantedAbility]:
        """Get granted spells for a character."""
        return [
            a for a in self.get_character_abilities(character_id, current_date)
            if a.ability_type == AbilityType.SPELL
        ]

    def has_ability(
        self,
        character_id: str,
        ability_name: str,
        current_date: Optional["GameDate"] = None,
    ) -> bool:
        """Check if a character has a specific granted ability."""
        return any(
            a.ability_name == ability_name
            for a in self.get_character_abilities(character_id, current_date)
        )

    def was_ability_granted(
        self,
        character_id: str,
        source_hex: str,
        source_poi: Optional[str],
        ability_name: str,
    ) -> bool:
        """Check if a specific ability was ever granted from a source."""
        source_key = f"{source_hex}:{source_poi}"
        grant_key = (character_id, source_key, ability_name)
        return grant_key in self._grants_issued

    def expire_rest_based(self, character_id: str) -> int:
        """
        Expire abilities that expire on rest.

        Returns number of abilities expired.
        """
        count = 0
        for ability in self.granted_abilities:
            if ability.character_id == character_id and ability.duration == "until_rest":
                if ability.is_active:
                    ability.is_active = False
                    count += 1
        return count


@dataclass
class HexNPC:
    """
    An NPC found within a hex location.

    Contains full NPC details for roleplay and encounters.
    """
    npc_id: str
    name: str
    description: str
    kindred: str = "Human"  # Race/species
    alignment: str = "Neutral"

    # Roleplay details
    title: Optional[str] = None
    demeanor: list[str] = field(default_factory=list)  # Personality traits
    speech: str = ""  # How they speak

    # Knowledge and goals
    languages: list[str] = field(default_factory=list)
    desires: list[str] = field(default_factory=list)  # What they want
    secrets: list[str] = field(default_factory=list)  # Hidden information

    # Equipment and location
    possessions: list[str] = field(default_factory=list)
    location: str = ""  # Where in the hex they can be found

    # Combat
    stat_reference: Optional[str] = None  # Reference to stat block
    is_combatant: bool = False

    # Relationship network
    # Format: [{npc_id, relationship_type, description, hex_id}]
    # relationship_type: "family", "employer", "ally", "rival", "enemy", "subordinate"
    # hex_id: hex where the related NPC can be found (for cross-hex relationships)
    relationships: list[dict[str, Any]] = field(default_factory=list)

    # Faction loyalty vs personal feelings
    # faction: official faction/employer they serve
    # loyalty: "loyal", "bought", "coerced", "secret_traitor"
    # personal_feelings: how they actually feel (may differ from loyalty)
    faction: Optional[str] = None
    loyalty: str = "loyal"
    personal_feelings: Optional[str] = None  # e.g., "loathes employer"

    # Magical binding or imprisonment
    # Format: {bound_to: "The Spectral Manse", release_condition: "Ygraine's intervention",
    #          captor: "Prince Mallowheart", can_leave: False}
    # NPCs with binding cannot leave their bound location until condition is met
    binding: Optional[dict[str, Any]] = None

    def get_relationship(self, npc_id: str) -> Optional[dict[str, Any]]:
        """Get relationship to a specific NPC."""
        for rel in self.relationships:
            if rel.get("npc_id") == npc_id:
                return rel
        return None

    def get_relationships_by_type(self, rel_type: str) -> list[dict[str, Any]]:
        """Get all relationships of a specific type."""
        return [r for r in self.relationships if r.get("relationship_type") == rel_type]

    def is_secretly_disloyal(self) -> bool:
        """Check if NPC is secretly disloyal to their faction."""
        return self.loyalty in ["bought", "coerced", "secret_traitor"]

    def get_cross_hex_connections(self) -> list[dict[str, Any]]:
        """Get relationships to NPCs in other hexes."""
        return [r for r in self.relationships if r.get("hex_id")]

    def is_bound(self) -> bool:
        """Check if NPC is magically bound to a location."""
        return self.binding is not None

    def can_leave_location(self) -> bool:
        """Check if NPC can leave their current location."""
        if not self.binding:
            return True
        return self.binding.get("can_leave", False)

    def get_bound_location(self) -> Optional[str]:
        """Get the location this NPC is bound to."""
        if self.binding:
            return self.binding.get("bound_to")
        return None

    def get_release_condition(self) -> Optional[str]:
        """Get the condition required to release this NPC from binding."""
        if self.binding:
            return self.binding.get("release_condition")
        return None


@dataclass
class Feature:
    """A notable feature in a location (legacy format)."""
    feature_id: str
    name: str
    description: str
    searchable: bool = False
    hidden: bool = False
    discovered: bool = False


@dataclass
class Hazard:
    """A hazard or trap in a location."""
    hazard_id: str
    name: str
    trigger: str
    effect: str
    damage: Optional[str] = None
    save_type: Optional[str] = None
    detected: bool = False
    disarmed: bool = False


@dataclass
class Lair:
    """A monster lair within a hex."""
    lair_id: str
    monster_type: str
    monster_count: str  # Dice notation, e.g., "2d6"
    treasure_type: Optional[str] = None
    discovered: bool = False
    cleared: bool = False


@dataclass
class Landmark:
    """A visible landmark in a hex."""
    landmark_id: str
    name: str
    description: str
    visible_from_adjacent: bool = True


@dataclass
class Threat:
    """An active threat in the world."""
    threat_id: str
    name: str
    threat_type: str
    location: str  # hex_id or area name
    severity: int  # 1-5
    active: bool = True
    expires_date: Optional[GameDate] = None


# =============================================================================
# WORLD STATE (Section 6.1)
# =============================================================================


@dataclass
class WorldState:
    """
    Global world state that persists across all game states.
    This is the authoritative source for world-level information.
    """
    current_date: GameDate
    current_time: GameTime
    season: Season
    weather: Weather
    global_flags: dict[str, Any] = field(default_factory=dict)
    cleared_locations: set[str] = field(default_factory=set)
    active_threats: list[Threat] = field(default_factory=list)
    active_adventure: Optional[str] = None

    def __post_init__(self):
        # Ensure season matches date
        self.season = self.current_date.get_season()


# =============================================================================
# PARTY STATE (Section 6.2)
# =============================================================================


@dataclass
class PartyResources:
    """Tracked party resources."""
    food_days: float = 0.0
    water_days: float = 0.0
    torches: int = 0
    lantern_oil_flasks: int = 0
    ammunition: dict[str, int] = field(default_factory=dict)  # ammo_type -> count

    def consume_food(self, days: float, party_size: int) -> bool:
        """
        Consume food for the party.

        Returns:
            True if sufficient food, False if running low
        """
        required = days * party_size
        self.food_days -= required
        return self.food_days >= 0

    def consume_water(self, days: float, party_size: int) -> bool:
        """Consume water for the party."""
        required = days * party_size
        self.water_days -= required
        return self.water_days >= 0


@dataclass
class Location:
    """Current party location."""
    location_type: LocationType
    location_id: str  # hex_id, room_id, or settlement_id
    sub_location: Optional[str] = None  # Building within settlement, etc.

    def __str__(self) -> str:
        if self.sub_location:
            return f"{self.location_type.value}:{self.location_id}:{self.sub_location}"
        return f"{self.location_type.value}:{self.location_id}"


@dataclass
class PartyState:
    """
    Current party state including position and shared resources.

    Per Dolmenwood rules (p146): Party speed = slowest member's speed.
    """
    location: Location
    marching_order: list[str] = field(default_factory=list)  # character_ids
    resources: PartyResources = field(default_factory=PartyResources)
    encumbrance_total: int = 0  # Legacy: total weight in coins
    active_conditions: list[Condition] = field(default_factory=list)
    active_light_source: Optional[LightSourceType] = None
    light_remaining_turns: int = 0
    # Member encumbrance tracking (p148-149)
    member_speeds: list[int] = field(default_factory=list)  # Encumbered speeds

    def get_movement_rate(self, base_rate: int = 40) -> int:
        """
        Calculate party movement rate per Dolmenwood rules (p146, p148-149).

        Party speed is determined by the slowest member's encumbered speed.
        Default base_rate of 40 represents unencumbered human speed.

        Args:
            base_rate: Fallback rate if no member speeds tracked

        Returns:
            Party movement speed (slowest member)
        """
        if self.member_speeds:
            # Party speed = slowest member (p146)
            return min(self.member_speeds)

        # Legacy fallback using encumbrance_total
        return EncumbranceCalculator.get_speed_from_weight(self.encumbrance_total)

    def update_member_speeds(self, characters: list["CharacterState"]) -> None:
        """
        Update member speeds from character states.

        Call this after any inventory changes to recalculate party speed.

        Args:
            characters: List of party member CharacterStates
        """
        self.member_speeds = [char.get_encumbered_speed() for char in characters]
        # Also update legacy encumbrance_total
        self.encumbrance_total = sum(char.calculate_encumbrance() for char in characters)

    def get_slowest_member_speed(self) -> int:
        """Get the speed of the slowest party member."""
        if self.member_speeds:
            return min(self.member_speeds)
        return EncumbranceCalculator.get_speed_from_weight(self.encumbrance_total)

    def any_over_capacity(self, characters: list["CharacterState"]) -> bool:
        """
        Check if any party member is over carrying capacity.

        Over capacity means the party cannot move.

        Args:
            characters: List of party member CharacterStates

        Returns:
            True if any member is over capacity
        """
        return any(char.is_over_capacity() for char in characters)


# =============================================================================
# CHARACTER STATE (Section 6.3)
# =============================================================================


@dataclass
class CharacterState:
    """
    Individual character state.
    Covers both PCs and retainers/hirelings.

    Supports Dolmenwood encumbrance rules (p148-149).
    """
    character_id: str
    name: str
    character_class: str
    level: int
    ability_scores: dict[str, int]  # STR, INT, WIS, DEX, CON, CHA
    hp_current: int
    hp_max: int
    armor_class: int
    movement_rate: int  # Base movement rate (unencumbered)
    inventory: list[Item] = field(default_factory=list)
    spells: list[Spell] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    morale: Optional[int] = None  # For retainers (2-12 scale)
    is_retainer: bool = False
    employer_id: Optional[str] = None  # For retainers
    # Encumbrance tracking (p148-149)
    encumbrance_system: EncumbranceSystem = EncumbranceSystem.WEIGHT
    armor_weight: ArmorWeight = ArmorWeight.UNARMOURED
    # Polymorph overlay for transformations
    polymorph_overlay: Optional["PolymorphOverlay"] = None

    def get_ability_score(self, ability: str) -> int:
        """
        Get effective ability score, applying polymorph overlay if active.

        Args:
            ability: Ability name (STR, DEX, CON, INT, WIS, CHA)

        Returns:
            Effective ability score
        """
        base_score = self.ability_scores.get(ability.upper(), 10)
        if self.polymorph_overlay and self.polymorph_overlay.is_active:
            return self.polymorph_overlay.get_effective_ability(ability, base_score)
        return base_score

    def get_ability_modifier(self, ability: str) -> int:
        """Get B/X-style ability modifier."""
        score = self.get_ability_score(ability)
        if score <= 3:
            return -3
        elif score <= 5:
            return -2
        elif score <= 8:
            return -1
        elif score <= 12:
            return 0
        elif score <= 15:
            return 1
        elif score <= 17:
            return 2
        else:
            return 3

    def get_effective_ac(self) -> int:
        """Get effective armor class, applying polymorph overlay if active."""
        if self.polymorph_overlay and self.polymorph_overlay.is_active:
            if self.polymorph_overlay.armor_class is not None:
                return self.polymorph_overlay.armor_class
        return self.armor_class

    def get_effective_movement(self) -> int:
        """Get effective movement rate, applying polymorph overlay if active."""
        if self.polymorph_overlay and self.polymorph_overlay.is_active:
            if self.polymorph_overlay.movement_rate is not None:
                return self.polymorph_overlay.movement_rate
        return self.get_encumbered_speed()

    def get_effective_attacks(self) -> list[dict]:
        """Get available attacks, using polymorph form attacks if active."""
        if self.polymorph_overlay and self.polymorph_overlay.is_active:
            if self.polymorph_overlay.attacks:
                return self.polymorph_overlay.attacks
        # Default attacks would come from class/equipment
        return []

    def apply_polymorph(self, overlay: "PolymorphOverlay") -> None:
        """Apply a polymorph transformation overlay."""
        overlay.character_id = self.character_id
        self.polymorph_overlay = overlay

    def remove_polymorph(self) -> Optional["PolymorphOverlay"]:
        """Remove and return the current polymorph overlay."""
        overlay = self.polymorph_overlay
        self.polymorph_overlay = None
        return overlay

    def is_polymorphed(self) -> bool:
        """Check if character currently has an active polymorph effect."""
        return (self.polymorph_overlay is not None and
                self.polymorph_overlay.is_active)

    def is_alive(self) -> bool:
        """Check if character is alive."""
        return self.hp_current > 0 and not any(
            c.condition_type == ConditionType.DEAD for c in self.conditions
        )

    def is_conscious(self) -> bool:
        """Check if character is conscious."""
        return self.is_alive() and not any(
            c.condition_type == ConditionType.UNCONSCIOUS for c in self.conditions
        )

    def calculate_encumbrance(self) -> int:
        """
        Calculate total weight encumbrance from inventory (p148).

        Returns total weight in coins.
        """
        return int(sum(item.get_total_weight() for item in self.inventory))

    def calculate_slot_encumbrance(self) -> tuple[int, int]:
        """
        Calculate slot encumbrance from inventory (p149).

        Returns:
            Tuple of (equipped_slots, stowed_slots)
        """
        equipped_slots = 0
        stowed_slots = 0

        for item in self.inventory:
            slots = item.get_total_slots()
            if item.equipped:
                equipped_slots += slots
            else:
                stowed_slots += slots

        return equipped_slots, stowed_slots

    def get_encumbrance_state(self) -> "EncumbranceState":
        """
        Get current encumbrance state for this character.

        Returns:
            EncumbranceState with current weight and slot usage
        """
        total_weight = self.calculate_encumbrance()
        equipped_slots, stowed_slots = self.calculate_slot_encumbrance()

        return EncumbranceState(
            total_weight=total_weight,
            equipped_slots=equipped_slots,
            stowed_slots=stowed_slots,
            system=self.encumbrance_system
        )

    def get_encumbered_speed(self) -> int:
        """
        Get movement speed accounting for encumbrance (p148-149).

        Returns:
            Movement speed based on current encumbrance level
        """
        if self.encumbrance_system in (
            EncumbranceSystem.WEIGHT,
            EncumbranceSystem.BASIC_WEIGHT
        ):
            total_weight = self.calculate_encumbrance()
            return EncumbranceCalculator.get_speed_from_weight(total_weight)
        else:  # SLOT system
            equipped, stowed = self.calculate_slot_encumbrance()
            return EncumbranceCalculator.get_speed_from_slots(equipped, stowed)

    def is_over_capacity(self) -> bool:
        """
        Check if character is over maximum carrying capacity (p148-149).

        Over capacity means the character cannot move.
        """
        if self.encumbrance_system in (
            EncumbranceSystem.WEIGHT,
            EncumbranceSystem.BASIC_WEIGHT
        ):
            total_weight = self.calculate_encumbrance()
            return EncumbranceCalculator.is_over_weight_capacity(total_weight)
        else:  # SLOT system
            equipped, stowed = self.calculate_slot_encumbrance()
            return EncumbranceCalculator.is_over_slot_capacity(equipped, stowed)


# =============================================================================
# LOCATION STATE (Section 6.4)
# =============================================================================


class AreaEffectType(str, Enum):
    """Types of area effects that can exist in locations."""
    WEB = "web"                     # Restricts movement
    FOG = "fog"                     # Obscures vision
    DARKNESS = "darkness"           # Magical darkness
    LIGHT = "light"                 # Magical light
    SILENCE = "silence"             # Blocks sound/spells with verbal components
    STINKING_CLOUD = "stinking_cloud"  # Nauseating gas
    GREASE = "grease"               # Slippery surface
    ENTANGLE = "entangle"           # Plants restrain creatures
    ILLUSION = "illusion"           # Illusory terrain/objects
    CUSTOM = "custom"               # Custom effect


@dataclass
class AreaEffect:
    """
    An effect that applies to an area (location).

    Used for spells like Web, Fog Cloud, Silence, etc. that create
    persistent effects in a specific location.
    """
    effect_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    effect_type: AreaEffectType = AreaEffectType.CUSTOM
    name: str = ""
    description: str = ""

    # Source tracking
    source_spell_id: Optional[str] = None
    caster_id: Optional[str] = None

    # Location
    location_id: str = ""
    location_type: LocationType = LocationType.DUNGEON_ROOM
    area_radius_feet: int = 0  # 0 = entire location

    # Duration (tied to turn/time system)
    duration_turns: Optional[int] = None  # None = permanent until dispelled
    is_permanent: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    # Mechanical effects
    blocks_movement: bool = False
    blocks_vision: bool = False
    blocks_sound: bool = False
    blocks_magic: bool = False
    damage_per_turn: Optional[str] = None  # Dice notation, e.g., "1d6"
    damage_type: Optional[str] = None
    save_type: Optional[str] = None  # "doom", "ray", "hold", "blast", "spell"
    save_negates: bool = False
    save_halves_damage: bool = False

    # For entering/exiting the area
    enter_effect: Optional[str] = None  # Description of effect on entry
    exit_effect: Optional[str] = None   # Description of effect on exit

    # State
    is_active: bool = True
    dismissed: bool = False

    def tick(self) -> bool:
        """
        Advance time by one turn.

        Returns:
            True if effect has expired
        """
        if not self.is_active:
            return True

        if self.is_permanent:
            return False

        if self.duration_turns is not None:
            self.duration_turns -= 1
            if self.duration_turns <= 0:
                self.is_active = False
                return True

        return False

    def dismiss(self) -> bool:
        """
        Dismiss the area effect.

        Returns:
            True if successfully dismissed
        """
        if self.is_active:
            self.dismissed = True
            self.is_active = False
            return True
        return False


@dataclass
class PolymorphOverlay:
    """
    Temporary stat overlay for polymorph-style transformations.

    When a character is polymorphed, this overlay temporarily replaces
    their physical stats (STR, DEX, CON, AC, attacks) while preserving
    their mental stats (INT, WIS, CHA) and identity.

    The overlay is applied on top of the character's base stats and
    is removed when the polymorph effect ends.
    """
    overlay_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # What triggered this transformation
    source_effect_id: Optional[str] = None
    source_spell_id: Optional[str] = None
    caster_id: Optional[str] = None

    # Target character
    character_id: str = ""

    # New form description
    form_name: str = ""
    form_description: str = ""

    # Overridden physical stats
    # None means use original stat
    strength: Optional[int] = None
    dexterity: Optional[int] = None
    constitution: Optional[int] = None
    armor_class: Optional[int] = None
    movement_rate: Optional[int] = None
    hp_max: Optional[int] = None  # Some polymorphs change HP

    # New attack options (replaces character's normal attacks)
    attacks: list[dict] = field(default_factory=list)  # [{"name": "Claw", "damage": "1d6", "bonus": 2}]

    # Special abilities gained in this form
    special_abilities: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)

    # Movement modes
    can_fly: bool = False
    fly_speed: Optional[int] = None
    can_swim: bool = False
    swim_speed: Optional[int] = None
    can_burrow: bool = False
    burrow_speed: Optional[int] = None

    # Restrictions in this form
    can_speak: bool = True
    can_cast_spells: bool = True
    can_use_items: bool = True

    # Duration tracking
    duration_turns: Optional[int] = None
    is_permanent: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    # State
    is_active: bool = True

    def tick(self) -> bool:
        """
        Advance time by one turn.

        Returns:
            True if transformation has ended
        """
        if not self.is_active:
            return True

        if self.is_permanent:
            return False

        if self.duration_turns is not None:
            self.duration_turns -= 1
            if self.duration_turns <= 0:
                self.is_active = False
                return True

        return False

    def end_transformation(self) -> bool:
        """
        End the transformation early (dispel, caster's choice, etc.).

        Returns:
            True if successfully ended
        """
        if self.is_active:
            self.is_active = False
            return True
        return False

    def get_effective_ability(self, ability: str, base_value: int) -> int:
        """
        Get the effective ability score, applying overlay if applicable.

        Args:
            ability: Ability name (STR, DEX, CON, INT, WIS, CHA)
            base_value: Character's base ability score

        Returns:
            Effective ability score (overlaid or base)
        """
        ability_upper = ability.upper()
        if ability_upper == "STR" and self.strength is not None:
            return self.strength
        elif ability_upper == "DEX" and self.dexterity is not None:
            return self.dexterity
        elif ability_upper == "CON" and self.constitution is not None:
            return self.constitution
        # Mental stats are never overridden
        return base_value


@dataclass
class LocationState:
    """
    State of a specific location (hex, dungeon room, settlement).
    """
    location_type: LocationType
    location_id: str
    terrain: str
    name: Optional[str] = None
    known_features: list[Feature] = field(default_factory=list)
    hazards: list[Hazard] = field(default_factory=list)
    occupants: list[str] = field(default_factory=list)  # character/monster IDs
    discovery_flags: dict[str, bool] = field(default_factory=dict)
    visited: bool = False
    last_visited_date: Optional[GameDate] = None

    # Hex-specific
    fairy_influence: Optional[str] = None
    drune_presence: bool = False
    lairs: list[Lair] = field(default_factory=list)
    landmarks: list[Landmark] = field(default_factory=list)

    # Dungeon-specific
    doors: list[dict] = field(default_factory=list)  # [{"direction": "N", "locked": True, "secret": False}]
    light_level: str = "dark"  # "bright", "dim", "dark"

    # Settlement-specific
    buildings: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    population: Optional[int] = None

    # Area effects (spells, environmental hazards affecting the location)
    area_effects: list[AreaEffect] = field(default_factory=list)

    def add_area_effect(self, effect: AreaEffect) -> None:
        """Add an area effect to this location."""
        effect.location_id = self.location_id
        effect.location_type = self.location_type
        self.area_effects.append(effect)

    def remove_area_effect(self, effect_id: str) -> Optional[AreaEffect]:
        """Remove an area effect by ID."""
        for i, effect in enumerate(self.area_effects):
            if effect.effect_id == effect_id:
                return self.area_effects.pop(i)
        return None

    def get_active_effects(self) -> list[AreaEffect]:
        """Get all active area effects."""
        return [e for e in self.area_effects if e.is_active]

    def tick_effects(self) -> list[AreaEffect]:
        """
        Advance time for all area effects.

        Returns:
            List of effects that expired
        """
        expired = []
        for effect in self.area_effects:
            if effect.tick():
                expired.append(effect)

        # Clean up expired effects
        self.area_effects = [e for e in self.area_effects if e.is_active]
        return expired

    def has_blocking_effect(self, block_type: str) -> bool:
        """
        Check if location has an effect blocking something.

        Args:
            block_type: "movement", "vision", "sound", "magic"

        Returns:
            True if such a blocking effect exists
        """
        for effect in self.get_active_effects():
            if block_type == "movement" and effect.blocks_movement:
                return True
            elif block_type == "vision" and effect.blocks_vision:
                return True
            elif block_type == "sound" and effect.blocks_sound:
                return True
            elif block_type == "magic" and effect.blocks_magic:
                return True
        return False


# =============================================================================
# ENCOUNTER STATE (Section 6.5)
# =============================================================================


@dataclass
class Combatant:
    """A participant in combat or encounter."""
    combatant_id: str
    name: str
    side: str  # "party" or "enemy"
    initiative: int = 0
    has_acted: bool = False
    stat_block: Optional[StatBlock] = None
    character_ref: Optional[str] = None  # Reference to CharacterState if applicable


@dataclass
class EncounterState:
    """
    State of an active encounter.
    """
    encounter_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    encounter_type: EncounterType = EncounterType.MONSTER
    distance: int = 60  # feet
    surprise_status: SurpriseStatus = SurpriseStatus.NO_SURPRISE
    actors: list[str] = field(default_factory=list)  # monster/NPC IDs
    context: str = ""  # traveling, guarding, hunting, etc.
    reaction_result: Optional[ReactionResult] = None
    terrain: str = ""

    # Combat-specific
    combatants: list[Combatant] = field(default_factory=list)
    current_round: int = 0
    current_phase: CombatPhase = CombatPhase.INITIATIVE
    party_initiative: int = 0
    enemy_initiative: int = 0
    active_side: str = ""  # "party" or "enemy"

    def get_party_combatants(self) -> list[Combatant]:
        """Get all party-side combatants."""
        return [c for c in self.combatants if c.side == "party"]

    def get_enemy_combatants(self) -> list[Combatant]:
        """Get all enemy-side combatants."""
        return [c for c in self.combatants if c.side == "enemy"]

    def get_active_enemies(self) -> list[Combatant]:
        """Get enemies still in the fight."""
        return [c for c in self.get_enemy_combatants()
                if c.stat_block and c.stat_block.hp_current > 0]


# =============================================================================
# CONTENT SOURCE REFERENCES (Section 7.2)
# =============================================================================


@dataclass
class SourceReference:
    """Reference to source material."""
    source_id: str
    book_code: str
    page_reference: Optional[str] = None
    section: Optional[str] = None


@dataclass
class ContentSource:
    """A content source (book, module, etc.)."""
    source_id: str
    source_type: SourceType
    book_name: str
    book_code: str
    version: str
    file_path: str
    file_hash: Optional[str] = None
    page_count: Optional[int] = None
    imported_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# NPC DATA (Section 7.4)
# =============================================================================


@dataclass
class NPC:
    """Non-player character with full profile."""
    npc_id: str
    name: str
    title: Optional[str] = None
    location: str = ""  # Settlement or hex
    faction: Optional[str] = None
    personality: str = ""
    goals: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)  # Hidden info for DM
    stat_block: Optional[StatBlock] = None
    dialogue_hooks: list[str] = field(default_factory=list)
    relationships: dict[str, str] = field(default_factory=dict)
    source: Optional[SourceReference] = None

    # Relationship tracking
    disposition: int = 0  # -5 to +5 scale with party
    met_before: bool = False
    interactions: list[dict] = field(default_factory=list)


# =============================================================================
# HEX DATA (Section 7.3)
# =============================================================================


@dataclass
class HexLocation:
    """
    A hex location from the Dolmenwood Campaign Book.

    Contains all information needed to run exploration, encounters,
    and activities within a single hex on the campaign map.
    """
    # Core identification
    hex_id: str  # e.g., "0101"
    coordinates: tuple[int, int] = (0, 0)  # Grid coordinates
    name: Optional[str] = None  # Named location, if any
    tagline: str = ""  # Short evocative description

    # Terrain and region
    terrain_type: str = "forest"  # bog, forest, river, etc.
    terrain_description: str = ""  # Full terrain description, e.g., "Bog (3), Northern Scratch"
    terrain_difficulty: int = 1  # Terrain difficulty rating (1-4)
    region: str = ""  # Region name, e.g., "Northern Scratch"

    # Descriptions
    description: str = ""  # Full description
    dm_notes: str = ""  # Notes for the DM

    # Procedural rules (new format)
    procedural: Optional["HexProcedural"] = None  # Lost/encounter/foraging rules

    # Points of interest (new format)
    points_of_interest: list["PointOfInterest"] = field(default_factory=list)

    # Roll tables for the hex
    roll_tables: list["RollTable"] = field(default_factory=list)

    # NPCs (new format - full NPC data)
    npcs: list["HexNPC"] = field(default_factory=list)

    # Associated content
    items: list[Any] = field(default_factory=list)  # Notable items in this hex
    secrets: list[str] = field(default_factory=list)  # Hidden information

    # Item location mapping: maps hex-level items to their POI/sub-location paths
    # Format: {"item_name": {"poi": "POI Name", "sub_location": "Sub-Location Name"}}
    # If sub_location is None, item is at the POI level
    item_locations: dict[str, dict[str, Optional[str]]] = field(default_factory=dict)

    # Navigation
    adjacent_hexes: list[str] = field(default_factory=list)  # Adjacent hex IDs
    roads: list[str] = field(default_factory=list)  # Roads through hex

    # Source tracking
    page_reference: str = ""  # Page in source book
    source: Optional["SourceReference"] = None

    # Metadata
    _metadata: Optional[dict] = None  # Source metadata from JSON

    # Legacy fields (for backward compatibility)
    terrain: str = ""  # Deprecated: use terrain_type
    flavour_text: str = ""  # Deprecated: use tagline
    travel_point_cost: int = 1  # Points to traverse this hex (legacy)
    lost_chance: int = 1  # X-in-6 chance of getting lost (legacy)
    encounter_chance: int = 1  # X-in-6 chance of encounter (legacy)
    special_encounter_chance: int = 0  # X-in-6 chance of special encounter (legacy)
    encounter_table: Optional[str] = None  # Reference to encounter table (legacy)
    special_encounters: list[str] = field(default_factory=list)  # Legacy
    features: list["HexFeature"] = field(default_factory=list)  # Legacy format
    ley_lines: Optional[str] = None  # Ley line information
    foraging_yields: list[str] = field(default_factory=list)  # Legacy
    lairs: list["Lair"] = field(default_factory=list)
    landmarks: list["Landmark"] = field(default_factory=list)
    fairy_influence: Optional[str] = None
    drune_presence: bool = False
    seasonal_variations: dict[Season, str] = field(default_factory=dict)
    rivers: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Sync terrain fields
        if self.terrain and not self.terrain_type:
            self.terrain_type = self.terrain
        elif self.terrain_type and not self.terrain:
            self.terrain = self.terrain_type

        # Parse coordinates from hex_id if not provided
        if self.coordinates == (0, 0) and self.hex_id:
            try:
                self.coordinates = (int(self.hex_id[:2]), int(self.hex_id[2:4]))
            except (ValueError, IndexError):
                pass

        # Sync legacy flavour_text with tagline
        if self.flavour_text and not self.tagline:
            self.tagline = self.flavour_text
        elif self.tagline and not self.flavour_text:
            self.flavour_text = self.tagline

    # =========================================================================
    # ITEM LOCATION MANAGEMENT
    # =========================================================================

    def set_item_location(
        self,
        item_name: str,
        poi_name: str,
        sub_location_name: Optional[str] = None,
    ) -> None:
        """
        Set the POI/sub-location where a hex-level item is found.

        Args:
            item_name: Name of the item from the hex's items list
            poi_name: Name of the POI containing the item
            sub_location_name: Optional sub-location within the POI
        """
        self.item_locations[item_name] = {
            "poi": poi_name,
            "sub_location": sub_location_name,
        }

    def get_item_location(self, item_name: str) -> Optional[dict[str, Optional[str]]]:
        """
        Get the location of a hex-level item.

        Args:
            item_name: Name of the item

        Returns:
            Dict with 'poi' and 'sub_location' keys, or None if not mapped
        """
        return self.item_locations.get(item_name)

    def migrate_item_to_poi(
        self,
        item_name: str,
        poi_name: str,
        sub_location_name: Optional[str] = None,
    ) -> bool:
        """
        Migrate a hex-level item to a POI or sub-location.

        Moves the item from the hex's items list to the specified POI/sub-location.

        Args:
            item_name: Name of the item to migrate
            poi_name: Target POI name
            sub_location_name: Optional sub-location within the POI

        Returns:
            True if item was migrated, False if not found
        """
        # Find the item in hex-level items
        item_to_migrate = None
        for item in self.items:
            if isinstance(item, dict):
                if item.get("name", "").lower() == item_name.lower():
                    item_to_migrate = item
                    break
            elif isinstance(item, str):
                if item.lower() == item_name.lower():
                    item_to_migrate = {"name": item, "description": ""}
                    break

        if not item_to_migrate:
            return False

        # Find the target POI
        target_poi = None
        for poi in self.points_of_interest:
            if poi.name.lower() == poi_name.lower():
                target_poi = poi
                break

        if not target_poi:
            return False

        # Migrate to sub-location or POI
        if sub_location_name:
            sub_loc = target_poi.get_sub_location_by_name(sub_location_name)
            if sub_loc:
                if "items" not in sub_loc:
                    sub_loc["items"] = []
                sub_loc["items"].append(item_to_migrate)
            else:
                # Sub-location not found, add to POI items
                target_poi.items.append(item_to_migrate)
        else:
            target_poi.items.append(item_to_migrate)

        # Remove from hex-level items
        self.items = [i for i in self.items if i != item_to_migrate and
                      (not isinstance(i, str) or i.lower() != item_name.lower())]

        # Track the migration
        self.set_item_location(item_name, poi_name, sub_location_name)

        return True

    def get_items_at_poi(self, poi_name: str) -> list[dict[str, Any]]:
        """
        Get all items at a specific POI (including migrated hex-level items).

        Args:
            poi_name: Name of the POI

        Returns:
            List of items at the POI
        """
        for poi in self.points_of_interest:
            if poi.name.lower() == poi_name.lower():
                return poi.items.copy()
        return []

    def get_items_at_sub_location(
        self,
        poi_name: str,
        sub_location_name: str,
    ) -> list[dict[str, Any]]:
        """
        Get all items at a specific sub-location.

        Args:
            poi_name: Name of the POI
            sub_location_name: Name of the sub-location

        Returns:
            List of items at the sub-location
        """
        for poi in self.points_of_interest:
            if poi.name.lower() == poi_name.lower():
                sub_loc = poi.get_sub_location_by_name(sub_location_name)
                if sub_loc:
                    return sub_loc.get("items", []).copy()
        return []

    def get_unmapped_hex_items(self) -> list[Any]:
        """
        Get hex-level items that haven't been mapped to POI locations.

        Returns:
            List of items without location mappings
        """
        unmapped = []
        for item in self.items:
            if isinstance(item, dict):
                item_name = item.get("name", "")
            else:
                item_name = str(item)

            if item_name and item_name not in self.item_locations:
                unmapped.append(item)
        return unmapped


# =============================================================================
# ACTION RESULTS
# =============================================================================


@dataclass
class ActionResult:
    """Result of attempting an action."""
    success: bool
    reason: str = ""
    cost: dict[str, Any] = field(default_factory=dict)  # time, resources consumed
    warnings: list[str] = field(default_factory=list)
    state_changes: list[dict] = field(default_factory=list)  # Changes to apply
    dice_results: list[DiceResult] = field(default_factory=list)

    def add_dice_result(self, result: DiceResult) -> None:
        """Add a dice result to this action."""
        self.dice_results.append(result)


@dataclass
class TransitionLog:
    """Log entry for a state transition."""
    timestamp: datetime
    from_state: str
    to_state: str
    trigger: str
    context: dict[str, Any] = field(default_factory=dict)
