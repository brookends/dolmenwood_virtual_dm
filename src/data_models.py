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
    """An item in inventory."""
    item_id: str
    name: str
    weight: float  # In coins (10 coins = 1 lb)
    quantity: int = 1
    equipped: bool = False
    charges: Optional[int] = None
    light_source: Optional[LightSourceType] = None
    light_remaining_turns: Optional[int] = None


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


@dataclass
class Feature:
    """A notable feature in a location."""
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
    """
    location: Location
    marching_order: list[str] = field(default_factory=list)  # character_ids
    resources: PartyResources = field(default_factory=PartyResources)
    encumbrance_total: int = 0
    active_conditions: list[Condition] = field(default_factory=list)
    active_light_source: Optional[LightSourceType] = None
    light_remaining_turns: int = 0

    def get_movement_rate(self, base_rate: int = 120) -> int:
        """Calculate movement rate based on encumbrance."""
        # Simplified encumbrance rules
        if self.encumbrance_total > 2400:  # Severely encumbered
            return base_rate // 4
        elif self.encumbrance_total > 1600:  # Heavily encumbered
            return base_rate // 2
        elif self.encumbrance_total > 800:  # Encumbered
            return (base_rate * 3) // 4
        return base_rate


# =============================================================================
# CHARACTER STATE (Section 6.3)
# =============================================================================


@dataclass
class CharacterState:
    """
    Individual character state.
    Covers both PCs and retainers/hirelings.
    """
    character_id: str
    name: str
    character_class: str
    level: int
    ability_scores: dict[str, int]  # STR, INT, WIS, DEX, CON, CHA
    hp_current: int
    hp_max: int
    armor_class: int
    movement_rate: int
    inventory: list[Item] = field(default_factory=list)
    spells: list[Spell] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    morale: Optional[int] = None  # For retainers (2-12 scale)
    is_retainer: bool = False
    employer_id: Optional[str] = None  # For retainers

    def get_ability_modifier(self, ability: str) -> int:
        """Get B/X-style ability modifier."""
        score = self.ability_scores.get(ability.upper(), 10)
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
        """Calculate total encumbrance from inventory."""
        return sum(item.weight * item.quantity for item in self.inventory)


# =============================================================================
# LOCATION STATE (Section 6.4)
# =============================================================================


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
    """A hex from the Campaign Book."""
    hex_id: str  # e.g., "0709"
    terrain: str
    name: Optional[str] = None
    description: str = ""
    features: list[Feature] = field(default_factory=list)
    lairs: list[Lair] = field(default_factory=list)
    landmarks: list[Landmark] = field(default_factory=list)
    fairy_influence: Optional[str] = None
    drune_presence: bool = False
    seasonal_variations: dict[Season, str] = field(default_factory=dict)
    encounter_table: Optional[str] = None  # Reference to encounter table
    source: Optional[SourceReference] = None

    # Navigation
    adjacent_hexes: dict[str, str] = field(default_factory=dict)  # direction -> hex_id
    roads: list[str] = field(default_factory=list)  # Connected hex_ids via road
    rivers: list[str] = field(default_factory=list)  # Connected hex_ids via river


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
