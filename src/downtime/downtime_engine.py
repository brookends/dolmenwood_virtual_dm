"""
Downtime Engine for Dolmenwood Virtual DM.

Implements camping and downtime per Dolmenwood rules (p158-159).
Handles rest, healing, spell recovery, training, crafting, research,
and faction advancement.

Camping Procedure (p158):
1. Setup activities: Prepare campsite, fetch firewood, fetch water
2. Camp activities: Build fire, optionally cook meal and entertain
3. Watches through the night
4. Wandering monsters: Check for nighttime random encounter
5. Sleep: Constitution check may be required based on conditions
6. Waking up: Characters who slept well heal 1 HP, spell-casters prepare spells

Sleep Difficulty (p159) - based on fire, bedding, and season:
- Easy: Good night's rest automatically
- Moderate: Constitution check required
- Difficult: Constitution check with -2 penalty
- Impossible: Fail to get good night's rest

Good Night's Rest Effects (p159):
- Heal 1 HP
- Spell-casters may prepare new spells

Failed Rest Effects (p159):
- Exhaustion until good rest (cumulative -1 per day)
- Spell preparation: 1-in-6 failure chance per spell
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.data_models import (
    DiceRoller,
    CharacterState,
    ConditionType,
    Condition,
    Season,
)


logger = logging.getLogger(__name__)


class DowntimeActivity(str, Enum):
    """Types of downtime activities."""
    REST = "rest"                       # Natural healing
    RECUPERATE = "recuperate"           # Extended recovery
    TRAIN = "train"                     # Skill/ability training
    RESEARCH = "research"               # Library/sage research
    CRAFT = "craft"                     # Create items
    CAROUSE = "carouse"                 # Carousing (spend gold, make contacts)
    WORK = "work"                       # Earn money
    PRAY = "pray"                       # Religious devotion
    FACTION_WORK = "faction_work"       # Work for a faction
    SPELL_RESEARCH = "spell_research"   # Research new spells
    ITEM_CREATION = "item_creation"     # Create magic items


class RestType(str, Enum):
    """Types of rest."""
    SHORT_REST = "short_rest"   # 1 turn (10 minutes)
    LONG_REST = "long_rest"     # 8 hours
    FULL_REST = "full_rest"     # 24 hours complete bed rest


class SleepDifficulty(str, Enum):
    """
    Sleep difficulty levels per Dolmenwood rules (p159).

    Based on fire, bedding, and season combination.
    """
    EASY = "easy"              # Good night's rest automatically
    MODERATE = "moderate"      # Constitution check required
    DIFFICULT = "difficult"    # Constitution check with -2 penalty
    IMPOSSIBLE = "impossible"  # Fail to get good night's rest


class BeddingType(str, Enum):
    """Types of camping bedding per Dolmenwood rules (p159)."""
    NONE = "none"                   # No bedding
    BEDROLL_ONLY = "bedroll_only"   # Bedroll or tent
    BEDROLL_AND_TENT = "bedroll_and_tent"  # Bedroll and tent


# Sleep Difficulty Table per Dolmenwood rules (p159)
# Key: (has_fire, bedding_type, season) -> SleepDifficulty
SLEEP_DIFFICULTY_TABLE: dict[tuple[bool, BeddingType, Season], SleepDifficulty] = {
    # No fire, No bedding
    (False, BeddingType.NONE, Season.WINTER): SleepDifficulty.IMPOSSIBLE,
    (False, BeddingType.NONE, Season.SPRING): SleepDifficulty.DIFFICULT,
    (False, BeddingType.NONE, Season.SUMMER): SleepDifficulty.MODERATE,
    (False, BeddingType.NONE, Season.AUTUMN): SleepDifficulty.DIFFICULT,
    # No fire, Bedroll or tent
    (False, BeddingType.BEDROLL_ONLY, Season.WINTER): SleepDifficulty.IMPOSSIBLE,
    (False, BeddingType.BEDROLL_ONLY, Season.SPRING): SleepDifficulty.MODERATE,
    (False, BeddingType.BEDROLL_ONLY, Season.SUMMER): SleepDifficulty.EASY,
    (False, BeddingType.BEDROLL_ONLY, Season.AUTUMN): SleepDifficulty.MODERATE,
    # No fire, Bedroll and tent
    (False, BeddingType.BEDROLL_AND_TENT, Season.WINTER): SleepDifficulty.DIFFICULT,
    (False, BeddingType.BEDROLL_AND_TENT, Season.SPRING): SleepDifficulty.MODERATE,
    (False, BeddingType.BEDROLL_AND_TENT, Season.SUMMER): SleepDifficulty.EASY,
    (False, BeddingType.BEDROLL_AND_TENT, Season.AUTUMN): SleepDifficulty.MODERATE,
    # Campfire, No bedding
    (True, BeddingType.NONE, Season.WINTER): SleepDifficulty.IMPOSSIBLE,
    (True, BeddingType.NONE, Season.SPRING): SleepDifficulty.DIFFICULT,
    (True, BeddingType.NONE, Season.SUMMER): SleepDifficulty.MODERATE,
    (True, BeddingType.NONE, Season.AUTUMN): SleepDifficulty.DIFFICULT,
    # Campfire, Bedroll or tent
    (True, BeddingType.BEDROLL_ONLY, Season.WINTER): SleepDifficulty.DIFFICULT,
    (True, BeddingType.BEDROLL_ONLY, Season.SPRING): SleepDifficulty.EASY,
    (True, BeddingType.BEDROLL_ONLY, Season.SUMMER): SleepDifficulty.EASY,
    (True, BeddingType.BEDROLL_ONLY, Season.AUTUMN): SleepDifficulty.EASY,
    # Campfire, Bedroll and tent
    (True, BeddingType.BEDROLL_AND_TENT, Season.WINTER): SleepDifficulty.MODERATE,
    (True, BeddingType.BEDROLL_AND_TENT, Season.SPRING): SleepDifficulty.EASY,
    (True, BeddingType.BEDROLL_AND_TENT, Season.SUMMER): SleepDifficulty.EASY,
    (True, BeddingType.BEDROLL_AND_TENT, Season.AUTUMN): SleepDifficulty.EASY,
}


@dataclass
class CampState:
    """
    State of a wilderness camp per Dolmenwood rules (p158-159).

    Tracks all camping conditions that affect rest quality.
    """
    has_fire: bool = False
    fire_hours_remaining: int = 0
    bedding: BeddingType = BeddingType.NONE
    campsite_prepared: bool = False
    water_available: bool = False
    # Camp activity bonuses
    meal_bonus: int = 0  # +1 from good cooking (p158)
    camaraderie_bonus: int = 0  # +1 from entertainment (p158)
    camaraderie_penalty: int = 0  # -1 from failed entertainment (p158)
    # Watch tracking
    watch_assignments: list[str] = field(default_factory=list)  # Character IDs per watch
    characters_on_watch: set[str] = field(default_factory=set)  # Who took a watch


class FactionStanding(str, Enum):
    """Standing with a faction."""
    HOSTILE = "hostile"
    UNFRIENDLY = "unfriendly"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    ALLIED = "allied"
    MEMBER = "member"


@dataclass
class FactionRelation:
    """Relationship with a faction."""
    faction_id: str
    faction_name: str
    standing: FactionStanding
    reputation_points: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0


@dataclass
class DowntimeResult:
    """Result of a downtime activity."""
    activity: DowntimeActivity
    days_spent: int
    success: bool
    results: dict[str, Any] = field(default_factory=dict)
    costs: dict[str, Any] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    state_changes: list[dict] = field(default_factory=list)


@dataclass
class TrainingProgress:
    """Progress on training activities."""
    skill_name: str
    target_level: int
    days_trained: int
    days_required: int
    gold_spent: int
    gold_required: int


class DowntimeEngine:
    """
    Engine for downtime and camping per Dolmenwood rules (p158-159).

    Manages:
    - Wilderness camping with full procedure (p158)
    - Sleep difficulty based on conditions (p159)
    - Rest and healing (1 HP per good night's rest)
    - Spell recovery with difficulty after bad rest
    - Training and advancement
    - Crafting and research
    - Faction advancement
    - Random downtime events
    """

    def __init__(self, controller: GlobalController):
        """
        Initialize the downtime engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Faction relations
        self._faction_relations: dict[str, FactionRelation] = {}

        # Training progress
        self._training_progress: dict[str, TrainingProgress] = {}

        # Location context
        self._in_safe_location: bool = False
        self._location_type: str = ""  # "settlement", "wilderness_camp", etc.

        # Camping state per Dolmenwood rules (p158-159)
        self._camp_state: Optional[CampState] = None

        # Callbacks
        self._event_callback: Optional[Callable] = None

    def register_event_callback(self, callback: Callable) -> None:
        """Register callback for downtime events."""
        self._event_callback = callback

    # =========================================================================
    # DOWNTIME INITIATION
    # =========================================================================

    def begin_downtime(
        self,
        location_type: str = "settlement",
        is_safe: bool = True
    ) -> dict[str, Any]:
        """
        Begin a downtime period.

        Args:
            location_type: Type of location for downtime
            is_safe: Whether location is safe from random encounters

        Returns:
            Dictionary with downtime initialization
        """
        current_state = self.controller.current_state

        if current_state == GameState.COMBAT:
            return {"error": "Cannot begin downtime during combat"}

        self._in_safe_location = is_safe
        self._location_type = location_type

        # Determine trigger based on current state
        if current_state == GameState.SETTLEMENT_EXPLORATION:
            trigger = "begin_downtime"
        elif current_state == GameState.WILDERNESS_TRAVEL:
            trigger = "begin_rest"
        elif current_state == GameState.DUNGEON_EXPLORATION:
            trigger = "begin_rest"
        else:
            trigger = "begin_rest"

        self.controller.transition(trigger, context={
            "location_type": location_type,
            "is_safe": is_safe,
        })

        return {
            "downtime_started": True,
            "location_type": location_type,
            "is_safe": is_safe,
            "available_activities": self._get_available_activities(),
        }

    def end_downtime(self) -> dict[str, Any]:
        """
        End the downtime period and return to exploration.

        Returns:
            Dictionary with downtime summary
        """
        if self.controller.current_state != GameState.DOWNTIME:
            return {"error": "Not in downtime state"}

        # Determine return state based on location
        if self._location_type == "settlement":
            trigger = "downtime_end_settlement"
        elif self._location_type == "dungeon":
            trigger = "downtime_end_dungeon"
        else:
            trigger = "downtime_end_wilderness"

        self.controller.transition(trigger)

        result = {
            "downtime_ended": True,
            "return_location": self._location_type,
        }

        self._in_safe_location = False
        self._location_type = ""

        return result

    def _get_available_activities(self) -> list[str]:
        """Get activities available at current location."""
        activities = [DowntimeActivity.REST.value]

        if self._in_safe_location:
            activities.extend([
                DowntimeActivity.RECUPERATE.value,
            ])

        if self._location_type == "settlement":
            activities.extend([
                DowntimeActivity.TRAIN.value,
                DowntimeActivity.RESEARCH.value,
                DowntimeActivity.CAROUSE.value,
                DowntimeActivity.WORK.value,
                DowntimeActivity.PRAY.value,
            ])

        return activities

    # =========================================================================
    # REST AND HEALING
    # =========================================================================

    def rest(
        self,
        rest_type: RestType,
        character_ids: Optional[list[str]] = None
    ) -> DowntimeResult:
        """
        Rest to recover HP and spells.

        Args:
            rest_type: Type of rest
            character_ids: Specific characters (default: all party)

        Returns:
            DowntimeResult with recovery details
        """
        # Validate state - must be in downtime to rest
        if self.controller.current_state != GameState.DOWNTIME:
            return DowntimeResult(
                activity=DowntimeActivity.REST,
                days_spent=0,
                success=False,
                results={"error": "Must be in downtime state to rest. Use begin_downtime() first."},
            )

        result = DowntimeResult(
            activity=DowntimeActivity.REST,
            days_spent=0,
            success=True,
        )

        # Get characters
        if character_ids:
            characters = [
                self.controller.get_character(cid)
                for cid in character_ids
                if self.controller.get_character(cid)
            ]
        else:
            characters = self.controller.get_all_characters()

        # Advance time based on rest type
        if rest_type == RestType.SHORT_REST:
            self.controller.advance_time(1)  # 10 minutes
            result.days_spent = 0
        elif rest_type == RestType.LONG_REST:
            self.controller.advance_time(48)  # 8 hours
            result.days_spent = 0
        else:  # FULL_REST
            self.controller.advance_time(144)  # 24 hours
            result.days_spent = 1

        # Apply healing
        healing_results = []
        for character in characters:
            if not character:
                continue

            healing = self._calculate_healing(character, rest_type)
            if healing > 0:
                heal_result = self.controller.heal_character(
                    character.character_id,
                    healing
                )
                healing_results.append({
                    "character_id": character.character_id,
                    "name": character.name,
                    "healing": heal_result.get("healing_received", 0),
                    "new_hp": heal_result.get("hp_current", 0),
                })

        result.results["healing"] = healing_results

        # Recover spells on long/full rest
        if rest_type in {RestType.LONG_REST, RestType.FULL_REST}:
            spell_recovery = self._recover_spells(characters)
            result.results["spells_recovered"] = spell_recovery

        # Check for random encounter if not safe
        if not self._in_safe_location and rest_type != RestType.SHORT_REST:
            encounter = self._check_rest_encounter()
            if encounter:
                result.events.append("Rest interrupted by encounter!")
                result.results["interrupted"] = True

        return result

    def _calculate_healing(
        self,
        character: CharacterState,
        rest_type: RestType
    ) -> int:
        """Calculate HP healed for a character."""
        if rest_type == RestType.SHORT_REST:
            return 0  # No natural healing on short rest

        if rest_type == RestType.LONG_REST:
            # 1 HP per level on long rest
            return character.level

        # Full rest: 1d3 HP
        roll = self.dice.roll("1d3", f"healing for {character.name}")
        return roll.total

    def _recover_spells(self, characters: list[CharacterState]) -> list[dict]:
        """Recover spells for spellcasters."""
        recovery = []

        for character in characters:
            if not character:
                continue

            # Reset cast spells
            spells_recovered = 0
            for spell in character.spells:
                if spell.cast_today:
                    spell.cast_today = False
                    spells_recovered += 1

            if spells_recovered > 0:
                recovery.append({
                    "character_id": character.character_id,
                    "name": character.name,
                    "spells_recovered": spells_recovered,
                })

        return recovery

    def _check_rest_encounter(self) -> bool:
        """Check for encounter during rest."""
        roll = self.dice.roll_d6(1, "rest encounter")
        return roll.total == 1  # 1-in-6 chance

    # =========================================================================
    # WILDERNESS CAMPING (p158-159)
    # =========================================================================

    def setup_camp(
        self,
        bedding: BeddingType = BeddingType.NONE,
        has_tent: bool = False,
        has_bedroll: bool = False
    ) -> dict[str, Any]:
        """
        Set up a wilderness camp per Dolmenwood rules (p158).

        At least one character must remain at campsite to prepare it.

        Args:
            bedding: Type of bedding available
            has_tent: Whether party has a tent
            has_bedroll: Whether party has bedrolls

        Returns:
            Dictionary with camp setup results
        """
        # Determine bedding type from equipment
        if has_tent and has_bedroll:
            actual_bedding = BeddingType.BEDROLL_AND_TENT
        elif has_tent or has_bedroll:
            actual_bedding = BeddingType.BEDROLL_ONLY
        else:
            actual_bedding = bedding

        # Initialize camp state
        self._camp_state = CampState(
            bedding=actual_bedding,
            campsite_prepared=True,
            water_available=True,  # Easy to find water in Dolmenwood (p158)
        )

        self._location_type = "wilderness_camp"

        return {
            "campsite_prepared": True,
            "bedding": actual_bedding.value,
            "water_available": True,
        }

    def fetch_firewood(
        self,
        character_id: str,
        weather_modifier: int = 0
    ) -> dict[str, Any]:
        """
        Fetch firewood for the campfire per Dolmenwood rules (p158).

        Each character fetching wood collects 1d6 hours worth.
        Weather modifiers: -1 damp, -2 snow, -4 heavy rain.

        Args:
            character_id: Character fetching wood
            weather_modifier: Modifier based on weather conditions

        Returns:
            Dictionary with firewood collection results
        """
        roll = self.dice.roll("1d6", f"firewood for {character_id}")
        hours = max(0, roll.total + weather_modifier)

        if self._camp_state:
            self._camp_state.fire_hours_remaining += hours

        return {
            "character_id": character_id,
            "hours_collected": hours,
            "roll": roll.total,
            "weather_modifier": weather_modifier,
            "total_fire_hours": self._camp_state.fire_hours_remaining if self._camp_state else hours,
        }

    def build_fire(self, bad_conditions: bool = False) -> dict[str, Any]:
        """
        Build a campfire per Dolmenwood rules (p158).

        Normally auto-succeeds. In bad conditions, 4-in-6 chance.

        Args:
            bad_conditions: Whether conditions are troublesome

        Returns:
            Dictionary with fire building results
        """
        if not self._camp_state:
            return {"success": False, "error": "No camp set up"}

        if self._camp_state.fire_hours_remaining <= 0:
            return {"success": False, "error": "No firewood available"}

        success = True
        roll_result = None

        if bad_conditions:
            roll = self.dice.roll_d6(1, "build fire (bad conditions)")
            roll_result = roll.total
            success = roll.total <= 4  # 4-in-6 chance

        if success:
            self._camp_state.has_fire = True

        return {
            "success": success,
            "bad_conditions": bad_conditions,
            "roll": roll_result,
            "fire_hours_available": self._camp_state.fire_hours_remaining,
        }

    def cook_meal(self, cook_character_id: str) -> dict[str, Any]:
        """
        Cook a meal at camp per Dolmenwood rules (p158).

        Requires fire, cooking pots, and ingredients.
        Cook makes Wisdom check:
        - Success: +1 bonus to Constitution checks for rest
        - Natural 1: Save vs Doom or meal is ruined

        Args:
            cook_character_id: Character doing the cooking

        Returns:
            Dictionary with cooking results
        """
        if not self._camp_state:
            return {"success": False, "error": "No camp set up"}

        if not self._camp_state.has_fire:
            return {"success": False, "error": "No fire to cook with"}

        # Wisdom check (assume DC 10)
        roll = self.dice.roll("1d20", f"cooking wisdom check for {cook_character_id}")

        if roll.total == 1:
            # Natural 1 - Save vs Doom or meal ruined
            save_roll = self.dice.roll("1d20", "save vs doom (ruined meal)")
            if save_roll.total < 14:  # Failed save
                return {
                    "success": False,
                    "roll": roll.total,
                    "natural_one": True,
                    "save_roll": save_roll.total,
                    "meal_ruined": True,
                    "message": "Meal ruined! Ingredients wasted.",
                }
            else:
                # Saved - meal is just bad
                return {
                    "success": False,
                    "roll": roll.total,
                    "natural_one": True,
                    "save_roll": save_roll.total,
                    "meal_ruined": False,
                    "message": "Palatable but not exemplary dish.",
                }

        # Add Wisdom modifier (assuming we can get character)
        character = self.controller.get_character(cook_character_id)
        wis_mod = character.get_ability_modifier("wisdom") if character else 0
        check_total = roll.total + wis_mod

        if check_total >= 10:  # Success
            if self._camp_state:
                self._camp_state.meal_bonus = 1
            return {
                "success": True,
                "roll": roll.total,
                "modifier": wis_mod,
                "total": check_total,
                "bonus": 1,
                "message": "Tasty dish provides +1 to Constitution checks for rest!",
            }
        else:
            return {
                "success": False,
                "roll": roll.total,
                "modifier": wis_mod,
                "total": check_total,
                "message": "Palatable but not exemplary dish.",
            }

    def entertain_camp(self, entertainer_id: str) -> dict[str, Any]:
        """
        Entertain the camp for camaraderie per Dolmenwood rules (p158).

        Character makes Charisma check:
        - Success: +1 bonus to Constitution checks for rest
        - Natural 1: Save vs Doom or -1 penalty to rest checks

        Args:
            entertainer_id: Character providing entertainment

        Returns:
            Dictionary with entertainment results
        """
        if not self._camp_state:
            return {"success": False, "error": "No camp set up"}

        # Charisma check
        roll = self.dice.roll("1d20", f"camaraderie check for {entertainer_id}")

        if roll.total == 1:
            # Natural 1 - Save vs Doom or ridicule
            save_roll = self.dice.roll("1d20", "save vs doom (ridicule)")
            if save_roll.total < 14:  # Failed save
                if self._camp_state:
                    self._camp_state.camaraderie_penalty = 1
                return {
                    "success": False,
                    "roll": roll.total,
                    "natural_one": True,
                    "save_roll": save_roll.total,
                    "penalty": -1,
                    "message": "Entertainment fell flat! Ridicule incurs -1 to Constitution checks.",
                }
            else:
                return {
                    "success": False,
                    "roll": roll.total,
                    "natural_one": True,
                    "save_roll": save_roll.total,
                    "message": "Entertainment attempt falls flat but avoided ridicule.",
                }

        # Add Charisma modifier
        character = self.controller.get_character(entertainer_id)
        cha_mod = character.get_ability_modifier("charisma") if character else 0
        check_total = roll.total + cha_mod

        if check_total >= 10:  # Success
            if self._camp_state:
                self._camp_state.camaraderie_bonus = 1
            return {
                "success": True,
                "roll": roll.total,
                "modifier": cha_mod,
                "total": check_total,
                "bonus": 1,
                "message": "Spirits lifted! +1 to Constitution checks for rest.",
            }
        else:
            return {
                "success": False,
                "roll": roll.total,
                "modifier": cha_mod,
                "total": check_total,
                "message": "Entertainment attempt falls flat.",
            }

    def set_watches(self, watch_assignments: list[str]) -> dict[str, Any]:
        """
        Set up watch rotation for the night per Dolmenwood rules (p159).

        Typically 4 watches of 2 hours each during 8-hour rest.
        Characters who sleep less than 6 hours fail to get good rest.
        Spell-casters interrupted by watch have difficulty preparing spells.

        Args:
            watch_assignments: List of character IDs for each watch

        Returns:
            Dictionary with watch setup results
        """
        if not self._camp_state:
            return {"success": False, "error": "No camp set up"}

        self._camp_state.watch_assignments = watch_assignments
        self._camp_state.characters_on_watch = set(watch_assignments)

        # Check for characters with multiple watches (less than 6 hours sleep)
        watch_counts: dict[str, int] = {}
        for char_id in watch_assignments:
            watch_counts[char_id] = watch_counts.get(char_id, 0) + 1

        insufficient_sleep = [
            char_id for char_id, count in watch_counts.items()
            if count >= 2  # 2+ watches = 4+ hours watching = less than 6 hours sleep
        ]

        return {
            "success": True,
            "watches_set": len(watch_assignments),
            "characters_on_watch": list(self._camp_state.characters_on_watch),
            "insufficient_sleep": insufficient_sleep,
        }

    def check_falling_asleep_on_watch(
        self,
        character_id: str,
        constitution: int
    ) -> dict[str, Any]:
        """
        Check if character falls asleep on watch per Dolmenwood optional rule (p159).

        Base 1-in-10 chance.
        Constitution 15+: 1-in-20 chance.
        Constitution 6-: 1-in-6 chance.

        Args:
            character_id: Character on watch
            constitution: Character's Constitution score

        Returns:
            Dictionary with watch vigilance results
        """
        if constitution >= 15:
            # 1-in-20 chance
            roll = self.dice.roll("1d20", f"falling asleep check for {character_id}")
            fell_asleep = roll.total == 1
            chance = "1-in-20"
        elif constitution <= 6:
            # 1-in-6 chance
            roll = self.dice.roll_d6(1, f"falling asleep check for {character_id}")
            fell_asleep = roll.total == 1
            chance = "1-in-6"
        else:
            # 1-in-10 chance
            roll = self.dice.roll("1d10", f"falling asleep check for {character_id}")
            fell_asleep = roll.total == 1
            chance = "1-in-10"

        return {
            "character_id": character_id,
            "fell_asleep": fell_asleep,
            "roll": roll.total,
            "chance": chance,
            "constitution": constitution,
        }

    def check_nighttime_encounter(
        self,
        terrain_encounter_chance: int = 1
    ) -> dict[str, Any]:
        """
        Check for nighttime wandering monster per Dolmenwood rules (p159).

        One check per night. Chance depends on terrain.
        Distance: 2d6 × 30' (or 1d4 × 30' if both sides surprised).

        Args:
            terrain_encounter_chance: Encounter chance based on terrain (X-in-6)

        Returns:
            Dictionary with encounter check results
        """
        roll = self.dice.roll_d6(1, "nighttime wandering monster")
        encounter = roll.total <= terrain_encounter_chance

        result = {
            "encounter": encounter,
            "roll": roll.total,
            "terrain_chance": terrain_encounter_chance,
        }

        if encounter:
            # Determine distance (2d6 × 30')
            distance_roll = self.dice.roll("2d6", "encounter distance")
            result["distance_feet"] = distance_roll.total * 30
            result["distance_roll"] = distance_roll.total

        return result

    def get_sleep_difficulty(self, season: Optional[Season] = None) -> SleepDifficulty:
        """
        Get sleep difficulty based on camp conditions per Dolmenwood rules (p159).

        Uses the Sleep Difficulty table considering fire, bedding, and season.

        Args:
            season: Current season (defaults to controller's world state)

        Returns:
            SleepDifficulty level
        """
        if not self._camp_state:
            return SleepDifficulty.IMPOSSIBLE

        if season is None:
            season = self.controller.world_state.season

        key = (
            self._camp_state.has_fire,
            self._camp_state.bedding,
            season
        )

        return SLEEP_DIFFICULTY_TABLE.get(key, SleepDifficulty.MODERATE)

    def resolve_sleep(
        self,
        character_id: str,
        constitution: int,
        season: Optional[Season] = None
    ) -> dict[str, Any]:
        """
        Resolve sleep for a character per Dolmenwood rules (p159).

        Checks sleep difficulty and applies Constitution check if needed.
        Applies bonuses from cooking and camaraderie.

        Args:
            character_id: Character sleeping
            constitution: Character's Constitution score
            season: Current season

        Returns:
            Dictionary with sleep results
        """
        difficulty = self.get_sleep_difficulty(season)

        # Calculate Constitution modifier
        con_mod = (constitution - 10) // 2

        # Add camp activity bonuses
        bonus = 0
        if self._camp_state:
            bonus += self._camp_state.meal_bonus
            bonus += self._camp_state.camaraderie_bonus
            bonus -= self._camp_state.camaraderie_penalty

        # Check if character was on watch (spell-caster concern)
        on_watch = False
        if self._camp_state and character_id in self._camp_state.characters_on_watch:
            on_watch = True

        result = {
            "character_id": character_id,
            "difficulty": difficulty.value,
            "constitution": constitution,
            "con_modifier": con_mod,
            "camp_bonus": bonus,
            "on_watch": on_watch,
        }

        if difficulty == SleepDifficulty.EASY:
            result["good_rest"] = True
            result["message"] = "Good night's rest achieved."

        elif difficulty == SleepDifficulty.IMPOSSIBLE:
            result["good_rest"] = False
            result["message"] = "Impossible to get good rest in these conditions."

        elif difficulty == SleepDifficulty.MODERATE:
            # Constitution check required
            roll = self.dice.roll("1d20", f"sleep constitution check for {character_id}")
            total = roll.total + con_mod + bonus
            result["roll"] = roll.total
            result["check_total"] = total
            result["good_rest"] = total >= 10
            if result["good_rest"]:
                result["message"] = "Passed Constitution check - good night's rest."
            else:
                result["message"] = "Failed Constitution check - poor rest."

        elif difficulty == SleepDifficulty.DIFFICULT:
            # Constitution check with -2 penalty
            roll = self.dice.roll("1d20", f"sleep constitution check for {character_id}")
            total = roll.total + con_mod + bonus - 2
            result["roll"] = roll.total
            result["penalty"] = -2
            result["check_total"] = total
            result["good_rest"] = total >= 10
            if result["good_rest"]:
                result["message"] = "Passed difficult Constitution check - good night's rest."
            else:
                result["message"] = "Failed Constitution check - poor rest."

        return result

    def apply_rest_effects(
        self,
        character_id: str,
        good_rest: bool,
        is_spellcaster: bool = False,
        on_watch: bool = False
    ) -> dict[str, Any]:
        """
        Apply effects of rest per Dolmenwood rules (p159).

        Good Rest:
        - Heal 1 HP
        - Spell-casters may prepare spells normally

        Poor Rest:
        - Exhaustion (cumulative -1 per day)
        - Spell preparation: 1-in-6 failure chance per spell

        Args:
            character_id: Character receiving effects
            good_rest: Whether character got good rest
            is_spellcaster: Whether character is a spell-caster
            on_watch: Whether character took a watch (affects spell prep)

        Returns:
            Dictionary with rest effects
        """
        result = {
            "character_id": character_id,
            "good_rest": good_rest,
        }

        if good_rest:
            # Heal 1 HP per Dolmenwood rules (p159)
            heal_result = self.controller.heal_character(character_id, 1)
            result["healing"] = 1
            result["new_hp"] = heal_result.get("hp_current", 0)

            # Spell-casters prepare spells normally (unless on watch)
            if is_spellcaster and on_watch:
                result["spell_prep_difficulty"] = True
                result["spell_prep_note"] = "Watch interrupted sleep - difficulty preparing spells"
        else:
            # Exhaustion penalty per Dolmenwood rules (p159)
            result["exhaustion"] = True
            result["exhaustion_note"] = "Exhausted until good night's rest (-1 cumulative per day)"

            # Add exhaustion condition
            character = self.controller.get_character(character_id)
            if character:
                from src.data_models import Condition
                exhaustion = Condition(
                    condition_type=ConditionType.EXHAUSTED,
                    description="Failed to get good night's rest (p159)",
                    source="camping",
                )
                character.conditions.append(exhaustion)

            # Spell preparation difficulty (p159)
            if is_spellcaster:
                result["spell_prep_difficulty"] = True
                result["spell_prep_failure_chance"] = "1-in-6 per spell"

        return result

    def check_spell_preparation(
        self,
        character_id: str,
        spells_to_prepare: int,
        poor_rest: bool = False
    ) -> dict[str, Any]:
        """
        Check spell preparation after rest per Dolmenwood rules (p159).

        After poor rest, each spell has 1-in-6 chance of failure.

        Args:
            character_id: Character preparing spells
            spells_to_prepare: Number of spells to prepare
            poor_rest: Whether character had poor rest

        Returns:
            Dictionary with spell preparation results
        """
        result = {
            "character_id": character_id,
            "spells_attempted": spells_to_prepare,
            "poor_rest": poor_rest,
        }

        if not poor_rest:
            result["spells_prepared"] = spells_to_prepare
            result["spells_failed"] = 0
            return result

        # Check each spell for failure (1-in-6)
        prepared = 0
        failed = 0
        failed_slots = []

        for slot in range(spells_to_prepare):
            roll = self.dice.roll_d6(1, f"spell preparation slot {slot + 1}")
            if roll.total == 1:
                failed += 1
                failed_slots.append(slot + 1)
            else:
                prepared += 1

        result["spells_prepared"] = prepared
        result["spells_failed"] = failed
        result["failed_slots"] = failed_slots

        return result

    def check_hex_night_hazards(
        self,
        character_id: str,
        hex_procedural: Optional[Any] = None,
    ) -> list[dict[str, Any]]:
        """
        Check for hex-specific night hazards affecting a sleeping character.

        Some hexes have environmental hazards that affect those who sleep there.
        For example, hex 0102 (Reedwall) has mist that causes dreamlessness.

        Args:
            character_id: Character sleeping
            hex_procedural: HexProcedural data for current hex (or None)

        Returns:
            List of triggered hazard effects
        """
        triggered_hazards = []

        if not hex_procedural or not hex_procedural.night_hazards:
            return triggered_hazards

        for hazard in hex_procedural.night_hazards:
            trigger = hazard.get("trigger", "sleep")

            # Currently only supporting sleep trigger
            if trigger != "sleep":
                continue

            # Make saving throw
            save_type = hazard.get("save_type", "doom")
            save_roll = self.dice.roll("1d20", f"save vs {save_type} ({hazard.get('description', 'night hazard')})")

            # For now, assume standard B/X save thresholds (could be enhanced)
            # Using a baseline of 12 as a moderate save DC
            save_dc = hazard.get("save_dc", 12)
            save_success = save_roll.total >= save_dc

            hazard_result = {
                "character_id": character_id,
                "hazard": hazard,
                "save_type": save_type,
                "save_roll": save_roll.total,
                "save_dc": save_dc,
                "save_success": save_success,
                "description": hazard.get("description", ""),
            }

            if not save_success:
                on_fail = hazard.get("on_fail", {})
                condition_type = on_fail.get("condition")
                duration_dice = on_fail.get("duration_dice", "1d6")
                duration_unit = on_fail.get("duration_unit", "days")

                # Roll duration
                duration_roll = self.dice.roll(duration_dice, f"{condition_type} duration")
                duration = duration_roll.total

                hazard_result["condition_applied"] = condition_type
                hazard_result["duration"] = duration
                hazard_result["duration_unit"] = duration_unit

                # Create the condition if it's dreamlessness
                if condition_type == "dreamless":
                    from src.data_models import Condition
                    dreamless = Condition.create_dreamlessness(
                        duration_days=duration,
                        source=hazard.get("description", "hex night hazard"),
                    )
                    hazard_result["condition_object"] = dreamless

            triggered_hazards.append(hazard_result)

        return triggered_hazards

    def process_wilderness_night(
        self,
        season: Optional[Season] = None,
        terrain_encounter_chance: int = 1,
        use_quick_camping: bool = False
    ) -> dict[str, Any]:
        """
        Process a full wilderness night per Dolmenwood camping procedure (p158).

        Full procedure:
        1. Setup activities (already done via setup_camp)
        2. Camp activities (fire, cooking, entertainment)
        3. Watches through the night
        4. Wandering monsters check
        5. Sleep resolution
        6. Waking up effects

        Quick Camping (optional rule): If party has suitable camping gear,
        automatically succeed at getting good rest.

        Args:
            season: Current season
            terrain_encounter_chance: Encounter chance for terrain
            use_quick_camping: Use optional quick camping rule

        Returns:
            Dictionary with night results
        """
        result = {
            "procedure": "full" if not use_quick_camping else "quick",
        }

        # Check for wandering monsters (one check per night)
        encounter_result = self.check_nighttime_encounter(terrain_encounter_chance)
        result["encounter_check"] = encounter_result

        if encounter_result["encounter"]:
            result["encounter_occurred"] = True
            result["encounter_distance"] = encounter_result["distance_feet"]
            # If sleeping characters, they are automatically surprised (p159)
            result["sleeping_characters_surprised"] = True
            return result

        # Resolve sleep for all characters
        if use_quick_camping and self._camp_state:
            # Quick camping - auto success if proper gear (p158)
            if self._camp_state.bedding != BeddingType.NONE:
                result["quick_camping_success"] = True
                result["all_rested_well"] = True
                return result

        # Get all characters and resolve sleep
        characters = self.controller.get_all_characters()
        sleep_results = []

        for character in characters:
            if not character:
                continue

            con = character.abilities.get("constitution", 10)
            sleep_result = self.resolve_sleep(character.character_id, con, season)
            sleep_results.append(sleep_result)

        result["sleep_results"] = sleep_results

        # Advance time (8 hours = 48 turns)
        self.controller.advance_time(48)

        return result

    def clear_camp(self) -> dict[str, Any]:
        """
        Clear the current camp state.

        Returns:
            Dictionary confirming camp cleared
        """
        self._camp_state = None
        if self._location_type == "wilderness_camp":
            self._location_type = ""

        return {"camp_cleared": True}

    # =========================================================================
    # RECUPERATION
    # =========================================================================

    def recuperate(
        self,
        days: int,
        character_ids: Optional[list[str]] = None
    ) -> DowntimeResult:
        """
        Extended rest for enhanced healing.

        Requires safe location with bed rest and care.
        Heals 1d3 HP per day with proper care.

        Args:
            days: Number of days to recuperate
            character_ids: Specific characters

        Returns:
            DowntimeResult with recuperation details
        """
        if not self._in_safe_location:
            return DowntimeResult(
                activity=DowntimeActivity.RECUPERATE,
                days_spent=0,
                success=False,
                results={"error": "Requires safe location for recuperation"},
            )

        result = DowntimeResult(
            activity=DowntimeActivity.RECUPERATE,
            days_spent=days,
            success=True,
        )

        # Calculate costs (food, lodging)
        party_size = len(self.controller.get_all_characters())
        lodging_cost = days * 5 * party_size  # 5gp per day per person for good care
        food_cost = days * party_size  # 1gp per day per person

        result.costs = {
            "lodging_gp": lodging_cost,
            "food_gp": food_cost,
            "total_gp": lodging_cost + food_cost,
        }

        # Advance time
        self.controller.advance_time(days * 144)  # 144 turns per day

        # Get characters
        if character_ids:
            characters = [
                self.controller.get_character(cid)
                for cid in character_ids
                if self.controller.get_character(cid)
            ]
        else:
            characters = self.controller.get_all_characters()

        # Apply healing for each day
        healing_results = []
        for character in characters:
            if not character:
                continue

            total_healing = 0
            for _ in range(days):
                roll = self.dice.roll("1d3", f"recuperation healing for {character.name}")
                total_healing += roll.total

            heal_result = self.controller.heal_character(
                character.character_id,
                total_healing
            )
            healing_results.append({
                "character_id": character.character_id,
                "name": character.name,
                "total_healing": total_healing,
                "new_hp": heal_result.get("hp_current", 0),
            })

        result.results["healing"] = healing_results

        # Recover from conditions
        condition_results = self._heal_conditions(characters, days)
        if condition_results:
            result.results["conditions_healed"] = condition_results

        return result

    def _heal_conditions(
        self,
        characters: list[CharacterState],
        days: int
    ) -> list[dict]:
        """Attempt to heal conditions during recuperation."""
        healed = []

        for character in characters:
            if not character:
                continue

            for condition in character.conditions[:]:  # Copy list for modification
                # Natural recovery from some conditions
                if condition.condition_type in {
                    ConditionType.EXHAUSTED,
                    ConditionType.STARVING,
                    ConditionType.DEHYDRATED,
                }:
                    # Recover after 1 day of rest
                    if days >= 1:
                        character.conditions.remove(condition)
                        healed.append({
                            "character_id": character.character_id,
                            "condition": condition.condition_type.value,
                        })

                elif condition.condition_type == ConditionType.DISEASED:
                    # Save vs disease each day
                    for _ in range(days):
                        roll = self.dice.roll_d20("disease recovery")
                        if roll.total >= 15:  # Base save
                            character.conditions.remove(condition)
                            healed.append({
                                "character_id": character.character_id,
                                "condition": condition.condition_type.value,
                            })
                            break

        return healed

    # =========================================================================
    # TRAINING
    # =========================================================================

    def train(
        self,
        character_id: str,
        skill_or_ability: str,
        days: int,
        gold_spent: int
    ) -> DowntimeResult:
        """
        Train a skill or ability.

        Training requires a trainer and takes significant time and money.

        Args:
            character_id: Character doing the training
            skill_or_ability: What to train
            days: Days spent training
            gold_spent: Gold invested

        Returns:
            DowntimeResult with training progress
        """
        if self._location_type != "settlement":
            return DowntimeResult(
                activity=DowntimeActivity.TRAIN,
                days_spent=0,
                success=False,
                results={"error": "Training requires a settlement with trainers"},
            )

        result = DowntimeResult(
            activity=DowntimeActivity.TRAIN,
            days_spent=days,
            success=True,
            costs={"gold_gp": gold_spent},
        )

        # Advance time
        self.controller.advance_time(days * 144)

        # Get or create training progress
        progress_key = f"{character_id}:{skill_or_ability}"
        if progress_key not in self._training_progress:
            self._training_progress[progress_key] = TrainingProgress(
                skill_name=skill_or_ability,
                target_level=1,
                days_trained=0,
                days_required=30,  # Base 30 days
                gold_spent=0,
                gold_required=100,  # Base 100gp
            )

        progress = self._training_progress[progress_key]
        progress.days_trained += days
        progress.gold_spent += gold_spent

        result.results["progress"] = {
            "skill": skill_or_ability,
            "days_trained": progress.days_trained,
            "days_required": progress.days_required,
            "gold_spent": progress.gold_spent,
            "gold_required": progress.gold_required,
            "complete": progress.days_trained >= progress.days_required and
                       progress.gold_spent >= progress.gold_required,
        }

        if result.results["progress"]["complete"]:
            result.results["training_complete"] = True
            result.events.append(f"Training in {skill_or_ability} complete!")
            # Clear progress
            del self._training_progress[progress_key]

        return result

    # =========================================================================
    # CAROUSING
    # =========================================================================

    def carouse(
        self,
        character_id: str,
        gold_spent: int
    ) -> DowntimeResult:
        """
        Carouse in a settlement - spend gold, potentially gain XP, contacts, or trouble.

        Based on classic carousing tables.

        Args:
            character_id: Character carousing
            gold_spent: Gold to spend

        Returns:
            DowntimeResult with carousing outcomes
        """
        if self._location_type != "settlement":
            return DowntimeResult(
                activity=DowntimeActivity.CAROUSE,
                days_spent=0,
                success=False,
                results={"error": "Carousing requires a settlement"},
            )

        result = DowntimeResult(
            activity=DowntimeActivity.CAROUSE,
            days_spent=1,
            success=True,
            costs={"gold_gp": gold_spent},
        )

        # Advance time (1 day of carousing)
        self.controller.advance_time(144)

        # Base XP gain equals gold spent
        xp_gained = gold_spent

        # Roll on carousing mishap table
        mishap_roll = self.dice.roll_d20("carousing mishap")

        if mishap_roll.total <= 3:
            # Major mishap
            mishap = self._roll_major_mishap()
            result.events.append(f"Major mishap: {mishap}")
            result.results["mishap"] = mishap
            xp_gained = xp_gained // 2  # Half XP on mishap

        elif mishap_roll.total <= 8:
            # Minor mishap
            mishap = self._roll_minor_mishap()
            result.events.append(f"Minor mishap: {mishap}")
            result.results["minor_mishap"] = mishap

        elif mishap_roll.total >= 18:
            # Bonus - made a valuable contact or heard useful information
            bonus = self._roll_carousing_bonus()
            result.events.append(f"Bonus: {bonus}")
            result.results["bonus"] = bonus
            xp_gained = int(xp_gained * 1.5)  # Bonus XP

        result.results["xp_gained"] = xp_gained

        # Apply XP using XPManager if available
        if self.controller.xp_manager:
            # Calculate mishap modifier for XP award
            if mishap_roll.total <= 3:
                mishap_modifier = 0.5
            elif mishap_roll.total >= 18:
                mishap_modifier = 1.5
            else:
                mishap_modifier = 1.0

            xp_result = self.controller.xp_manager.award_carousing_xp(
                character_id=character_id,
                gold_spent=gold_spent,
                mishap_modifier=mishap_modifier,
            )
            result.results["xp_applied"] = True
            result.results["xp_final"] = xp_result.final_xp

            # Check for level-up
            if xp_result.level_ups:
                result.events.append(f"Ready to level up!")
                result.results["ready_to_level"] = True

        return result

    def _roll_major_mishap(self) -> str:
        """Roll on major carousing mishap table."""
        roll = self.dice.roll_d6(1, "major mishap")
        mishaps = {
            1: "Make a powerful enemy - insulted a noble or guild master",
            2: "Gambling debt - owe 2d6 x 100gp to dangerous people",
            3: "Jailed - spend 1d6 days in jail, must pay 50gp fine",
            4: "Married - woke up married to a stranger",
            5: "Robbed - lost all gold and one random item",
            6: "Cursed - offended a witch, suffer -1 to all rolls for a week",
        }
        return mishaps.get(roll.total, mishaps[1])

    def _roll_minor_mishap(self) -> str:
        """Roll on minor carousing mishap table."""
        roll = self.dice.roll_d6(1, "minor mishap")
        mishaps = {
            1: "Hangover - -2 to all rolls tomorrow",
            2: "Lost item - misplaced something small",
            3: "Made a scene - minor reputation hit in town",
            4: "Gambling loss - lost an extra 2d6 gp",
            5: "Romantic entanglement - complicated situation",
            6: "Insulted someone - minor enemy made",
        }
        return mishaps.get(roll.total, mishaps[1])

    def _roll_carousing_bonus(self) -> str:
        """Roll on carousing bonus table."""
        roll = self.dice.roll_d6(1, "carousing bonus")
        bonuses = {
            1: "Made a useful contact - merchant willing to give discounts",
            2: "Heard a valuable rumor about treasure",
            3: "Impressed a potential patron",
            4: "Made a new friend - potential hireling",
            5: "Won at gambling - gained extra 2d6 gp",
            6: "Learned local secret - useful information",
        }
        return bonuses.get(roll.total, bonuses[1])

    # =========================================================================
    # FACTION WORK
    # =========================================================================

    def faction_work(
        self,
        faction_id: str,
        task_type: str,
        days: int
    ) -> DowntimeResult:
        """
        Perform work for a faction.

        Args:
            faction_id: Faction to work for
            task_type: Type of task (errand, mission, etc.)
            days: Days spent

        Returns:
            DowntimeResult with faction progress
        """
        result = DowntimeResult(
            activity=DowntimeActivity.FACTION_WORK,
            days_spent=days,
            success=True,
        )

        # Advance time
        self.controller.advance_time(days * 144)

        # Get or create faction relation
        if faction_id not in self._faction_relations:
            self._faction_relations[faction_id] = FactionRelation(
                faction_id=faction_id,
                faction_name=faction_id,  # Would look up proper name
                standing=FactionStanding.NEUTRAL,
                reputation_points=0,
            )

        relation = self._faction_relations[faction_id]

        # Roll for task success
        roll = self.dice.roll_2d6("faction task")
        success_threshold = 7  # Base difficulty

        if roll.total >= success_threshold:
            # Success
            reputation_gain = days  # 1 rep per day of successful work
            relation.reputation_points += reputation_gain
            relation.completed_tasks += 1

            result.results["task_success"] = True
            result.results["reputation_gained"] = reputation_gain
            result.events.append(f"Completed task for {faction_id}")

            # Check for standing improvement
            new_standing = self._check_standing_improvement(relation)
            if new_standing != relation.standing:
                old_standing = relation.standing
                relation.standing = new_standing
                result.events.append(
                    f"Standing improved from {old_standing.value} to {new_standing.value}!"
                )

        else:
            # Failure
            relation.failed_tasks += 1
            result.results["task_success"] = False
            result.events.append(f"Failed task for {faction_id}")

            # Possible reputation loss on bad roll
            if roll.total <= 4:
                relation.reputation_points = max(0, relation.reputation_points - 1)
                result.results["reputation_lost"] = 1

        result.results["current_standing"] = relation.standing.value
        result.results["total_reputation"] = relation.reputation_points

        return result

    def _check_standing_improvement(self, relation: FactionRelation) -> FactionStanding:
        """Check if faction standing should improve."""
        thresholds = {
            FactionStanding.HOSTILE: -10,
            FactionStanding.UNFRIENDLY: -5,
            FactionStanding.NEUTRAL: 0,
            FactionStanding.FRIENDLY: 10,
            FactionStanding.ALLIED: 25,
            FactionStanding.MEMBER: 50,
        }

        for standing, threshold in reversed(list(thresholds.items())):
            if relation.reputation_points >= threshold:
                return standing

        return FactionStanding.HOSTILE

    def get_faction_standing(self, faction_id: str) -> Optional[FactionRelation]:
        """Get current standing with a faction."""
        return self._faction_relations.get(faction_id)

    # =========================================================================
    # WORK FOR MONEY
    # =========================================================================

    def work(
        self,
        character_id: str,
        job_type: str,
        days: int
    ) -> DowntimeResult:
        """
        Work for money during downtime.

        Args:
            character_id: Character doing the work
            job_type: Type of work
            days: Days worked

        Returns:
            DowntimeResult with earnings
        """
        result = DowntimeResult(
            activity=DowntimeActivity.WORK,
            days_spent=days,
            success=True,
        )

        # Advance time
        self.controller.advance_time(days * 144)

        # Calculate earnings based on job type and character skills
        daily_wages = {
            "unskilled": 1,     # 1gp per day
            "skilled": 3,       # 3gp per day
            "specialist": 10,   # 10gp per day
        }

        wage = daily_wages.get(job_type, 1)
        total_earnings = wage * days

        result.results["earnings_gp"] = total_earnings
        result.results["job_type"] = job_type
        result.results["daily_wage"] = wage

        return result

    # =========================================================================
    # RESEARCH
    # =========================================================================

    def research(
        self,
        topic: str,
        days: int,
        gold_spent: int = 0
    ) -> DowntimeResult:
        """
        Research a topic at a library or with a sage.

        Args:
            topic: Topic to research
            days: Days spent researching
            gold_spent: Gold spent on resources/sage fees

        Returns:
            DowntimeResult with research findings
        """
        if self._location_type != "settlement":
            return DowntimeResult(
                activity=DowntimeActivity.RESEARCH,
                days_spent=0,
                success=False,
                results={"error": "Research requires access to library or sage"},
            )

        result = DowntimeResult(
            activity=DowntimeActivity.RESEARCH,
            days_spent=days,
            success=True,
            costs={"gold_gp": gold_spent},
        )

        # Advance time
        self.controller.advance_time(days * 144)

        # Roll for research success
        # Bonus for more days and gold spent
        bonus = min(days // 3, 3) + min(gold_spent // 50, 3)
        roll = self.dice.roll_2d6("research")
        total = roll.total + bonus

        if total >= 12:
            result.results["quality"] = "comprehensive"
            result.results["information_level"] = 3
            result.events.append(f"Comprehensive information found about {topic}")
        elif total >= 9:
            result.results["quality"] = "detailed"
            result.results["information_level"] = 2
            result.events.append(f"Detailed information found about {topic}")
        elif total >= 6:
            result.results["quality"] = "basic"
            result.results["information_level"] = 1
            result.events.append(f"Basic information found about {topic}")
        else:
            result.results["quality"] = "none"
            result.results["information_level"] = 0
            result.success = False
            result.events.append(f"No useful information found about {topic}")

        result.results["topic"] = topic

        return result

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_downtime_summary(self) -> dict[str, Any]:
        """
        Get summary of current downtime state per Dolmenwood rules (p158-159).

        Includes camping state and all downtime tracking.
        """
        summary = {
            "in_downtime": self.controller.current_state == GameState.DOWNTIME,
            "location_type": self._location_type,
            "is_safe": self._in_safe_location,
            "available_activities": self._get_available_activities(),
            "faction_relations": {
                fid: {
                    "standing": rel.standing.value,
                    "reputation": rel.reputation_points,
                }
                for fid, rel in self._faction_relations.items()
            },
            "training_in_progress": {
                key: {
                    "skill": prog.skill_name,
                    "progress": f"{prog.days_trained}/{prog.days_required} days",
                }
                for key, prog in self._training_progress.items()
            },
        }

        # Add camping state per Dolmenwood rules (p158-159)
        if self._camp_state:
            summary["camp"] = {
                "campsite_prepared": self._camp_state.campsite_prepared,
                "has_fire": self._camp_state.has_fire,
                "fire_hours_remaining": self._camp_state.fire_hours_remaining,
                "bedding": self._camp_state.bedding.value,
                "water_available": self._camp_state.water_available,
                "meal_bonus": self._camp_state.meal_bonus,
                "camaraderie_bonus": self._camp_state.camaraderie_bonus,
                "camaraderie_penalty": self._camp_state.camaraderie_penalty,
                "characters_on_watch": list(self._camp_state.characters_on_watch),
            }

        return summary
