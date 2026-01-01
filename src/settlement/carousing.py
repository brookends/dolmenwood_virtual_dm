"""
Carousing System for Dolmenwood Virtual DM.

Implements carousing rules based on Jeff Rients's original carousing rules,
adapted for Dolmenwood's setting and integrated with the XP award system.

Core Mechanics:
- Spend gold in a settlement to gain XP (1 XP per 1 GP spent)
- Maximum spending per session: character level × 100 GP
- Save vs. Poison (or Constitution check) to avoid mishaps
- On failed save, roll on mishap table for consequences
- High rolls may grant bonuses (contacts, rumors, winnings)

Settlement Integration:
- Requires a settlement with a tavern, inn, or similar establishment
- Different settlements may have different carousing modifiers
- Some locations may have unique mishap or bonus tables

Based on Jeff Rients's "Party like it's 999" carousing rules.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from src.data_models import DiceRoller, CharacterState

if TYPE_CHECKING:
    from src.game_state.global_controller import GlobalController


logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================


class CarousingOutcome(str, Enum):
    """Possible outcomes of a carousing session."""

    SUCCESS = "success"  # Successful carousing, full XP
    MINOR_MISHAP = "minor_mishap"  # Minor trouble, full XP
    MAJOR_MISHAP = "major_mishap"  # Major trouble, half XP
    BONUS = "bonus"  # Extra benefits, 150% XP
    BROKE = "broke"  # Can't pay the bill
    BANNED = "banned"  # Not welcome here


class MishapSeverity(str, Enum):
    """Severity of carousing mishaps."""

    MINOR = "minor"  # Embarrassing but manageable
    MAJOR = "major"  # Serious consequences
    CATASTROPHIC = "catastrophic"  # Life-changing disaster


# Maximum gold per level for carousing (Jeff Rients standard)
GOLD_PER_LEVEL = 100

# Minimum save target (Dolmenwood uses descending saves)
# Character must roll under their save vs. Poison
DEFAULT_SAVE_TARGET = 14  # Used if character has no save data


# =============================================================================
# MISHAP TABLES - JEFF RIENTS STYLE
# =============================================================================


# Major Mishaps (d20 table) - Serious consequences
MAJOR_MISHAPS: dict[int, dict[str, Any]] = {
    1: {
        "title": "Jailed",
        "description": "You wake up in jail with no memory of how you got there. The guards demand a fine.",
        "effect": "jail",
        "fine_dice": "2d6",
        "fine_multiplier": 10,  # 2d6 × 10 GP
        "days_jailed": "1d6",
    },
    2: {
        "title": "Powerful Enemy",
        "description": "You deeply insulted someone important - a noble, guild master, or other influential figure.",
        "effect": "enemy",
        "enemy_type": "noble",
        "reputation_penalty": -2,
    },
    3: {
        "title": "Gambling Debt",
        "description": "You owe a substantial sum to dangerous people. They expect payment within a week.",
        "effect": "debt",
        "debt_dice": "3d6",
        "debt_multiplier": 100,  # 3d6 × 100 GP
        "deadline_days": 7,
    },
    4: {
        "title": "Robbed",
        "description": "You were robbed while insensible. Lost all gold on your person and one random item.",
        "effect": "robbed",
        "lost_gold": True,
        "lost_item": True,
    },
    5: {
        "title": "Married",
        "description": "You woke up married to a stranger. The ceremony was apparently quite festive.",
        "effect": "married",
        "spouse_reaction": "2d6",  # Roll reaction to determine spouse's attitude
    },
    6: {
        "title": "Cursed",
        "description": "You offended a witch or fairy creature. Now you bear their curse.",
        "effect": "cursed",
        "curse_type": "bad_luck",
        "penalty": -1,
        "duration_days": 7,
    },
    7: {
        "title": "Tattoo",
        "description": "You now sport an embarrassing or controversial tattoo in a visible location.",
        "effect": "tattoo",
        "tattoo_type_roll": "1d6",  # 1-2: Embarrassing, 3-4: Controversial, 5-6: Arcane
    },
    8: {
        "title": "Banned",
        "description": "You are no longer welcome at this establishment. Or any of its sister locations.",
        "effect": "banned",
        "location_banned": True,
    },
    9: {
        "title": "Inducted into Secret Society",
        "description": "You apparently joined a secret society. You remember nothing, but they remember you.",
        "effect": "secret_society",
        "faction_involvement": True,
    },
    10: {
        "title": "Duel Scheduled",
        "description": "You challenged someone to a duel. They accepted. It's in three days at dawn.",
        "effect": "duel",
        "opponent_level": "1d4+1",
        "days_until_duel": 3,
    },
    11: {
        "title": "Religious Conversion",
        "description": "You made fervent vows to a deity or cause. The clergy expects you to honor them.",
        "effect": "religious_vow",
        "vow_type_roll": "1d6",
    },
    12: {
        "title": "Wanted Poster",
        "description": "Your face is now on wanted posters throughout the settlement.",
        "effect": "wanted",
        "bounty_dice": "1d6",
        "bounty_multiplier": 50,  # 1d6 × 50 GP
    },
    13: {
        "title": "Property Damage",
        "description": "You caused significant damage to property. Someone wants restitution.",
        "effect": "damage",
        "damage_cost_dice": "2d6",
        "damage_cost_multiplier": 50,  # 2d6 × 50 GP
    },
    14: {
        "title": "Romantic Entanglement",
        "description": "You're now involved in a complicated romantic situation with multiple parties.",
        "effect": "romance",
        "parties_involved": "1d4",
        "jealousy_level": "high",
    },
    15: {
        "title": "Brawl Injuries",
        "description": "You were in a serious brawl. You're beaten up and so are several others.",
        "effect": "injured",
        "hp_lost_dice": "1d6",
        "witnesses": True,
    },
    16: {
        "title": "Made a Vow",
        "description": "You swore a binding oath to accomplish some task. Many witnessed it.",
        "effect": "vow",
        "vow_witnessed": True,
    },
    17: {
        "title": "Insulted the Wrong Person",
        "description": "You insulted someone who doesn't forget. And has resources for revenge.",
        "effect": "insulted_powerful",
        "revenge_likelihood": "high",
    },
    18: {
        "title": "Lost Valuable Item",
        "description": "Your most valuable non-magical item is gone. Stolen, gambled away, or given away.",
        "effect": "lost_valuable",
        "item_type": "most_valuable",
    },
    19: {
        "title": "Fairy Bargain",
        "description": "You made a bargain with a fairy creature. The terms are... unclear.",
        "effect": "fairy_bargain",
        "bargain_type_roll": "1d6",
    },
    20: {
        "title": "Roll Twice",
        "description": "Your night was especially eventful.",
        "effect": "roll_twice",
        "reroll": True,
    },
}


# Minor Mishaps (d12 table) - Embarrassing but manageable
MINOR_MISHAPS: dict[int, dict[str, Any]] = {
    1: {
        "title": "Hangover",
        "description": "You have a terrible hangover. Everything is too loud and too bright.",
        "effect": "hangover",
        "penalty": -2,
        "duration_hours": 8,
    },
    2: {
        "title": "Lost Small Item",
        "description": "You misplaced something small - a trinket, some coins, or a personal item.",
        "effect": "lost_small_item",
        "value_dice": "1d6",
        "value_multiplier": 5,  # 1d6 × 5 GP
    },
    3: {
        "title": "Made a Scene",
        "description": "Everyone remembers your embarrassing behavior last night.",
        "effect": "embarrassed",
        "reputation_penalty": -1,
        "duration_days": 3,
    },
    4: {
        "title": "Minor Gambling Loss",
        "description": "You lost some extra money at games of chance.",
        "effect": "gambling_loss",
        "extra_loss_dice": "2d6",
    },
    5: {
        "title": "Minor Romantic Complication",
        "description": "Someone has developed feelings for you. Or thinks you have feelings for them.",
        "effect": "admirer",
        "admirer_persistence": "moderate",
    },
    6: {
        "title": "Minor Insult",
        "description": "You insulted someone who now dislikes you. Nothing serious, but awkward.",
        "effect": "minor_enemy",
        "enemy_type": "commoner",
    },
    7: {
        "title": "Questionable Promise",
        "description": "You promised to do something for someone. You don't remember what.",
        "effect": "promise",
        "promise_type_roll": "1d6",
    },
    8: {
        "title": "Embarrassing Story",
        "description": "An embarrassing story about you is now circulating through town.",
        "effect": "story",
        "spread_rate": "fast",
    },
    9: {
        "title": "Bar Tab",
        "description": "You ran up an additional bar tab you forgot about.",
        "effect": "extra_tab",
        "extra_cost_dice": "1d6",
        "extra_cost_multiplier": 10,
    },
    10: {
        "title": "Wrong Crowd",
        "description": "You were seen with disreputable company. Some people are making assumptions.",
        "effect": "bad_company",
        "reputation_effect": "minor_negative",
    },
    11: {
        "title": "Bruised",
        "description": "You got into a minor scuffle. Nothing serious, but you're a bit sore.",
        "effect": "bruised",
        "hp_lost": 1,
    },
    12: {
        "title": "Overshared",
        "description": "You told someone something you probably shouldn't have.",
        "effect": "overshared",
        "secret_revealed": True,
    },
}


# Carousing Bonuses (d8 table) - Good outcomes
CAROUSING_BONUSES: dict[int, dict[str, Any]] = {
    1: {
        "title": "Valuable Contact",
        "description": "You made a useful friend - a merchant, craftsman, or information broker.",
        "effect": "contact",
        "contact_type_roll": "1d6",
        "benefit": "discount",
    },
    2: {
        "title": "Treasure Rumor",
        "description": "You heard about hidden treasure or a lucrative opportunity.",
        "effect": "rumor",
        "rumor_type": "treasure",
        "accuracy_roll": "1d6",  # 1-2: False, 3-4: Partially true, 5-6: True
    },
    3: {
        "title": "Impressed a Patron",
        "description": "Someone wealthy or influential was impressed by you.",
        "effect": "patron",
        "patron_interest": "moderate",
    },
    4: {
        "title": "Potential Hireling",
        "description": "You met someone eager to work for you.",
        "effect": "hireling",
        "hireling_type_roll": "1d6",
        "loyalty_bonus": 1,
    },
    5: {
        "title": "Gambling Winnings",
        "description": "Lady luck smiled on you at the gaming tables.",
        "effect": "winnings",
        "winnings_dice": "3d6",
        "winnings_multiplier": 10,  # 3d6 × 10 GP
    },
    6: {
        "title": "Local Secret",
        "description": "You learned something interesting about this place or its inhabitants.",
        "effect": "secret",
        "secret_type_roll": "1d6",
    },
    7: {
        "title": "Good Reputation",
        "description": "Word of your generosity and good nature has spread.",
        "effect": "reputation",
        "reputation_bonus": 1,
        "duration": "persistent",
    },
    8: {
        "title": "Unexpected Gift",
        "description": "Someone gave you a small but useful gift as thanks for your company.",
        "effect": "gift",
        "gift_value_dice": "1d6",
        "gift_value_multiplier": 5,  # 1d6 × 5 GP worth
    },
}


# =============================================================================
# RESULT DATACLASSES
# =============================================================================


@dataclass
class CarousingMishap:
    """Details of a carousing mishap."""

    severity: MishapSeverity
    title: str
    description: str
    effect: str
    details: dict[str, Any] = field(default_factory=dict)
    mechanical_effects: list[str] = field(default_factory=list)


@dataclass
class CarousingBonus:
    """Details of a carousing bonus."""

    title: str
    description: str
    effect: str
    details: dict[str, Any] = field(default_factory=dict)
    mechanical_effects: list[str] = field(default_factory=list)


@dataclass
class CarousingResult:
    """Complete result of a carousing session."""

    # Basic info
    character_id: str
    character_name: str
    settlement_id: str
    settlement_name: str

    # Financial
    gold_spent: int
    gold_cap: int  # Maximum allowed based on level
    over_budget: bool = False

    # Outcome
    outcome: CarousingOutcome = CarousingOutcome.SUCCESS
    save_required: bool = True
    save_roll: int = 0
    save_target: int = 0
    save_passed: bool = True

    # XP
    base_xp: int = 0
    xp_modifier: float = 1.0
    final_xp: int = 0
    level_up_ready: bool = False

    # Mishap/Bonus
    mishap: Optional[CarousingMishap] = None
    bonus: Optional[CarousingBonus] = None

    # Narrative
    events: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)

    # Time
    days_spent: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "settlement_id": self.settlement_id,
            "settlement_name": self.settlement_name,
            "gold_spent": self.gold_spent,
            "gold_cap": self.gold_cap,
            "outcome": self.outcome.value,
            "save_required": self.save_required,
            "save_roll": self.save_roll,
            "save_target": self.save_target,
            "save_passed": self.save_passed,
            "base_xp": self.base_xp,
            "xp_modifier": self.xp_modifier,
            "final_xp": self.final_xp,
            "level_up_ready": self.level_up_ready,
            "events": self.events,
            "consequences": self.consequences,
            "days_spent": self.days_spent,
        }

        if self.mishap:
            result["mishap"] = {
                "severity": self.mishap.severity.value,
                "title": self.mishap.title,
                "description": self.mishap.description,
                "effect": self.mishap.effect,
                "details": self.mishap.details,
                "mechanical_effects": self.mishap.mechanical_effects,
            }

        if self.bonus:
            result["bonus"] = {
                "title": self.bonus.title,
                "description": self.bonus.description,
                "effect": self.bonus.effect,
                "details": self.bonus.details,
                "mechanical_effects": self.bonus.mechanical_effects,
            }

        return result


# =============================================================================
# CAROUSING ENGINE
# =============================================================================


class CarousingEngine:
    """
    Handles carousing in settlements based on Jeff Rients's rules.

    Usage:
        engine = CarousingEngine(controller)
        result = engine.carouse(
            character_id="char_001",
            gold_to_spend=150,
            settlement_id="lankshorn",
            settlement_name="Lankshorn"
        )
    """

    def __init__(self, controller: "GlobalController"):
        """
        Initialize the carousing engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

    def get_max_gold(self, character: CharacterState) -> int:
        """
        Get the maximum gold a character can spend carousing per session.

        Based on Jeff Rients's rule: level × 100 GP.

        Args:
            character: The character carousing

        Returns:
            Maximum gold allowed
        """
        return character.level * GOLD_PER_LEVEL

    def carouse(
        self,
        character_id: str,
        gold_to_spend: int,
        settlement_id: str,
        settlement_name: str,
        *,
        venue_modifier: int = 0,
        force_mishap: bool = False,
        force_bonus: bool = False,
    ) -> CarousingResult:
        """
        Execute a carousing session for a character.

        Args:
            character_id: ID of the character carousing
            gold_to_spend: Amount of gold to spend
            settlement_id: ID of the current settlement
            settlement_name: Name of the current settlement
            venue_modifier: Modifier to save based on venue quality
            force_mishap: Force a mishap (for testing)
            force_bonus: Force a bonus (for testing)

        Returns:
            CarousingResult with full details
        """
        character = self.controller.get_character(character_id)
        if not character:
            return CarousingResult(
                character_id=character_id,
                character_name="Unknown",
                settlement_id=settlement_id,
                settlement_name=settlement_name,
                gold_spent=0,
                gold_cap=0,
                outcome=CarousingOutcome.BROKE,
                events=["Character not found"],
            )

        # Calculate spending cap
        gold_cap = self.get_max_gold(character)
        actual_gold = min(gold_to_spend, gold_cap)
        over_budget = gold_to_spend > gold_cap

        result = CarousingResult(
            character_id=character_id,
            character_name=character.name,
            settlement_id=settlement_id,
            settlement_name=settlement_name,
            gold_spent=actual_gold,
            gold_cap=gold_cap,
            over_budget=over_budget,
            base_xp=actual_gold,
        )

        if over_budget:
            result.events.append(
                f"Spending capped at {gold_cap} GP (level {character.level} × 100)"
            )

        # Check if character can afford it
        if hasattr(character, "gold") and character.gold < actual_gold:
            result.outcome = CarousingOutcome.BROKE
            result.events.append("Cannot afford the carousing expenses")
            result.final_xp = 0
            return result

        # Make the save
        save_target = self._get_save_target(character)
        save_roll = self.dice.roll_d20("carousing save").total

        # Apply venue modifier
        effective_roll = save_roll + venue_modifier

        result.save_roll = save_roll
        result.save_target = save_target
        result.save_passed = effective_roll <= save_target  # B/X uses roll-under

        # Determine outcome
        if force_mishap or (not result.save_passed and not force_bonus):
            # Failed save - roll for mishap severity
            severity_roll = self.dice.roll_d20("mishap severity").total

            if severity_roll <= 5:
                result.outcome = CarousingOutcome.MAJOR_MISHAP
                result.mishap = self._roll_major_mishap()
                result.xp_modifier = 0.5
                result.events.append(f"Save failed! Major mishap: {result.mishap.title}")
            else:
                result.outcome = CarousingOutcome.MINOR_MISHAP
                result.mishap = self._roll_minor_mishap()
                result.xp_modifier = 1.0  # Full XP for minor mishaps
                result.events.append(f"Save failed! Minor mishap: {result.mishap.title}")

        elif force_bonus or (result.save_passed and save_roll >= 18):
            # Natural 18-20 and passed: bonus outcome
            result.outcome = CarousingOutcome.BONUS
            result.bonus = self._roll_bonus()
            result.xp_modifier = 1.5
            result.events.append(f"Excellent night! Bonus: {result.bonus.title}")

        else:
            # Normal success
            result.outcome = CarousingOutcome.SUCCESS
            result.xp_modifier = 1.0
            result.events.append("A fine night of revelry!")

        # Calculate final XP
        result.final_xp = int(result.base_xp * result.xp_modifier)

        # Apply XP if manager available
        if self.controller.xp_manager:
            xp_result = self.controller.xp_manager.award_carousing_xp(
                character_id=character_id,
                gold_spent=actual_gold,
                mishap_modifier=result.xp_modifier,
            )
            result.level_up_ready = bool(xp_result.level_ups)

            if result.level_up_ready:
                result.events.append(f"{character.name} has enough XP to level up!")

        # Process mishap consequences
        if result.mishap:
            result.consequences = self._process_mishap_consequences(
                character, result.mishap
            )

        # Process bonus effects
        if result.bonus:
            bonus_effects = self._process_bonus_effects(character, result.bonus)
            result.events.extend(bonus_effects)

        return result

    def _get_save_target(self, character: CharacterState) -> int:
        """
        Get the character's save target for carousing.

        Uses Save vs. Poison if available, otherwise Constitution check.

        Args:
            character: The character

        Returns:
            Save target (roll under to succeed)
        """
        # Try to get save vs. poison
        if character.saving_throws and "poison" in character.saving_throws:
            return character.saving_throws["poison"]

        # Fall back to Constitution-based save
        if hasattr(character, "constitution") and character.constitution:
            # Use 15 minus CON modifier as save target
            con_mod = (character.constitution - 10) // 2
            return max(1, 15 - con_mod)

        return DEFAULT_SAVE_TARGET

    def _roll_major_mishap(self) -> CarousingMishap:
        """Roll on the major mishap table."""
        roll = self.dice.roll_d20("major mishap table").total

        # Handle roll twice result
        if roll == 20:
            mishaps = []
            for _ in range(2):
                reroll = self.dice.roll("1d19", "reroll mishap").total
                mishaps.append(MAJOR_MISHAPS.get(reroll, MAJOR_MISHAPS[1]))
            # Combine the two mishaps
            combined = mishaps[0].copy()
            combined["title"] = f"{mishaps[0]['title']} AND {mishaps[1]['title']}"
            combined["description"] = (
                f"{mishaps[0]['description']} Also: {mishaps[1]['description']}"
            )
            mishap_data = combined
        else:
            mishap_data = MAJOR_MISHAPS.get(roll, MAJOR_MISHAPS[1])

        # Resolve any dice expressions in the mishap
        details = self._resolve_mishap_dice(mishap_data)

        return CarousingMishap(
            severity=MishapSeverity.MAJOR,
            title=mishap_data["title"],
            description=mishap_data["description"],
            effect=mishap_data["effect"],
            details=details,
        )

    def _roll_minor_mishap(self) -> CarousingMishap:
        """Roll on the minor mishap table."""
        roll = self.dice.roll("1d12", "minor mishap table").total
        mishap_data = MINOR_MISHAPS.get(roll, MINOR_MISHAPS[1])

        details = self._resolve_mishap_dice(mishap_data)

        return CarousingMishap(
            severity=MishapSeverity.MINOR,
            title=mishap_data["title"],
            description=mishap_data["description"],
            effect=mishap_data["effect"],
            details=details,
        )

    def _roll_bonus(self) -> CarousingBonus:
        """Roll on the carousing bonus table."""
        roll = self.dice.roll("1d8", "carousing bonus table").total
        bonus_data = CAROUSING_BONUSES.get(roll, CAROUSING_BONUSES[1])

        details = self._resolve_mishap_dice(bonus_data)

        return CarousingBonus(
            title=bonus_data["title"],
            description=bonus_data["description"],
            effect=bonus_data["effect"],
            details=details,
        )

    def _resolve_mishap_dice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Resolve any dice expressions in mishap/bonus data."""
        details = {}

        for key, value in data.items():
            if key in ("title", "description", "effect"):
                continue

            if isinstance(value, str) and "d" in value.lower():
                # It's a dice expression
                try:
                    roll_result = self.dice.roll(value, key)
                    details[key] = roll_result.total
                except Exception:
                    details[key] = value
            else:
                details[key] = value

        # Calculate derived values
        if "fine_dice" in details and "fine_multiplier" in data:
            fine_roll = details.get("fine_dice", 0)
            if isinstance(fine_roll, int):
                details["fine_amount"] = fine_roll * data["fine_multiplier"]

        if "debt_dice" in details and "debt_multiplier" in data:
            debt_roll = details.get("debt_dice", 0)
            if isinstance(debt_roll, int):
                details["debt_amount"] = debt_roll * data["debt_multiplier"]

        if "winnings_dice" in details and "winnings_multiplier" in data:
            win_roll = details.get("winnings_dice", 0)
            if isinstance(win_roll, int):
                details["winnings_amount"] = win_roll * data["winnings_multiplier"]

        return details

    def _process_mishap_consequences(
        self, character: CharacterState, mishap: CarousingMishap
    ) -> list[str]:
        """
        Process the mechanical consequences of a mishap.

        Args:
            character: The character who had the mishap
            mishap: The mishap details

        Returns:
            List of consequence descriptions
        """
        consequences = []
        effect = mishap.effect

        if effect == "jail":
            days = mishap.details.get("days_jailed", 1)
            fine = mishap.details.get("fine_amount", 20)
            consequences.append(f"Jailed for {days} days. Fine: {fine} GP")

        elif effect == "enemy":
            consequences.append("Made a powerful enemy")

        elif effect == "debt":
            amount = mishap.details.get("debt_amount", 300)
            consequences.append(f"Owe {amount} GP to dangerous people")

        elif effect == "robbed":
            consequences.append("Lost all carried gold and one random item")

        elif effect == "married":
            consequences.append("Woke up married to a stranger")

        elif effect == "cursed":
            penalty = mishap.details.get("penalty", -1)
            days = mishap.details.get("duration_days", 7)
            consequences.append(f"Cursed: {penalty} to all rolls for {days} days")

        elif effect == "hangover":
            penalty = mishap.details.get("penalty", -2)
            hours = mishap.details.get("duration_hours", 8)
            consequences.append(f"Hangover: {penalty} to all rolls for {hours} hours")

        elif effect == "injured":
            hp_lost = mishap.details.get("hp_lost_dice", 0)
            if isinstance(hp_lost, int) and hp_lost > 0:
                consequences.append(f"Lost {hp_lost} HP from brawl injuries")

        elif effect == "duel":
            days = mishap.details.get("days_until_duel", 3)
            consequences.append(f"Duel scheduled in {days} days")

        elif effect == "wanted":
            bounty = mishap.details.get("bounty_multiplier", 50)
            bounty_roll = mishap.details.get("bounty_dice", 1)
            if isinstance(bounty_roll, int):
                total_bounty = bounty_roll * bounty
                consequences.append(f"Wanted: {total_bounty} GP bounty")

        return consequences

    def _process_bonus_effects(
        self, character: CharacterState, bonus: CarousingBonus
    ) -> list[str]:
        """
        Process the effects of a carousing bonus.

        Args:
            character: The character who got the bonus
            bonus: The bonus details

        Returns:
            List of effect descriptions
        """
        effects = []
        effect = bonus.effect

        if effect == "winnings":
            amount = bonus.details.get("winnings_amount", 0)
            if amount > 0:
                effects.append(f"Won {amount} GP at gambling!")

        elif effect == "contact":
            effects.append("Made a valuable contact")

        elif effect == "rumor":
            effects.append("Learned a rumor about treasure")

        elif effect == "hireling":
            effects.append("Met a potential hireling")

        elif effect == "reputation":
            effects.append("Gained good reputation in this settlement")

        elif effect == "gift":
            value = bonus.details.get("gift_value_dice", 0)
            if isinstance(value, int):
                gift_worth = value * bonus.details.get("gift_value_multiplier", 5)
                effects.append(f"Received a gift worth ~{gift_worth} GP")

        return effects


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================


_engine: Optional[CarousingEngine] = None


def get_carousing_engine(controller: "GlobalController") -> CarousingEngine:
    """Get or create the shared CarousingEngine instance."""
    global _engine
    if _engine is None:
        _engine = CarousingEngine(controller)
    return _engine


def reset_carousing_engine() -> None:
    """Reset the shared CarousingEngine instance."""
    global _engine
    _engine = None
