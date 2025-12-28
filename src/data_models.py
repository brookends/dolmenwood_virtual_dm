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
# TIME TRACKING
# =============================================================================


@dataclass
class GameDate:
    """Dolmenwood calendar date."""
    year: int
    month: int  # 1-12
    day: int    # 1-30 (simplified)

    def advance_days(self, days: int) -> "GameDate":
        """Advance the date by a number of days."""
        new_day = self.day + days
        new_month = self.month
        new_year = self.year

        while new_day > 30:
            new_day -= 30
            new_month += 1
            if new_month > 12:
                new_month = 1
                new_year += 1

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

    def __str__(self) -> str:
        return f"Year {self.year}, Month {self.month}, Day {self.day}"


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

    # Time-of-day variant descriptions
    description_day: Optional[str] = None  # Description during daylight
    description_night: Optional[str] = None  # Description at night
    interior_day: Optional[str] = None  # Interior during day
    interior_night: Optional[str] = None  # Interior at night
    entering_day: Optional[str] = None  # Entering during day
    entering_night: Optional[str] = None  # Entering at night

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

    def mark_discovered(self) -> None:
        """Mark this POI as discovered."""
        self.discovered = True


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
