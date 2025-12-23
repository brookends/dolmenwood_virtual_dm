"""
Downtime Engine for Dolmenwood Virtual DM.

Handles downtime activities including rest, healing, spell recovery,
training, crafting, research, and faction advancement.

Downtime can occur in settlements or safe wilderness locations.
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
    Engine for downtime activities.

    Manages:
    - Rest and healing
    - Spell recovery
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
        """Get summary of current downtime state."""
        return {
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
