"""
Kindred character generator for Dolmenwood.

Generates random physical characteristics, names, and aspects
for characters based on their kindred definition.
"""

import logging
import random
from typing import Optional

from src.kindred.kindred_data import (
    AspectType,
    DiceFormula,
    GeneratedKindredAspects,
    KindredDefinition,
    NameColumn,
)
from src.kindred.kindred_manager import get_kindred_manager

logger = logging.getLogger(__name__)


def roll_dice(formula: DiceFormula) -> int:
    """
    Roll dice according to a formula.

    Args:
        formula: DiceFormula specifying num_dice, die_size, and modifier

    Returns:
        Total roll result
    """
    total = sum(random.randint(1, formula.die_size) for _ in range(formula.num_dice))
    return total + formula.modifier


class KindredGenerator:
    """
    Generates random character aspects based on kindred definitions.

    Handles rolling for physical characteristics, names, and all
    aspect tables defined for a kindred.
    """

    def __init__(self, kindred_id: str):
        """
        Initialize generator for a specific kindred.

        Args:
            kindred_id: The kindred to generate for (e.g., "breggle")

        Raises:
            ValueError: If kindred_id is not registered
        """
        self.manager = get_kindred_manager()
        self.definition = self.manager.get(kindred_id)
        if not self.definition:
            raise ValueError(f"Unknown kindred: {kindred_id}")

    def generate_all(
        self,
        gender: Optional[str] = None,
        level: int = 1,
    ) -> GeneratedKindredAspects:
        """
        Generate all random aspects for a character.

        Args:
            gender: "male", "female", or None for random
            level: Starting level (default 1)

        Returns:
            GeneratedKindredAspects with all rolled values
        """
        aspects = GeneratedKindredAspects(kindred_id=self.definition.kindred_id)

        # Determine gender if not specified
        if gender is None:
            gender = random.choice(["male", "female"])
        aspects.gender = gender

        # Roll physical characteristics
        aspects.age = self.roll_age()
        aspects.height_inches = self.roll_height()
        aspects.weight_lbs = self.roll_weight()

        # Generate name
        aspects.name = self.generate_name(gender)

        # Roll all aspects
        aspect_results = self.roll_all_aspects()
        aspects.background = aspect_results.get("background", "")
        aspects.trinket = aspect_results.get("trinket", "")
        aspects.trinket_item_id = aspect_results.get("trinket_item_id")
        aspects.head = aspect_results.get("head", "")
        aspects.demeanour = aspect_results.get("demeanour", "")
        aspects.desires = aspect_results.get("desires", "")
        aspects.face = aspect_results.get("face", "")
        aspects.dress = aspect_results.get("dress", "")
        aspects.beliefs = aspect_results.get("beliefs", "")
        aspects.fur_body = aspect_results.get("fur_body", "")
        aspects.speech = aspect_results.get("speech", "")

        # Store roll history
        aspects.rolls = aspect_results.get("_rolls", {})

        return aspects

    def roll_age(self) -> int:
        """Roll starting age for level 1 character."""
        physical = self.definition.physical
        base = physical.age_base
        dice_roll = roll_dice(physical.age_dice)

        # Special handling for fairies (elf, grimalkin): age is 1d100 × 10 years
        if self.definition.kindred_id in ("elf", "grimalkin"):
            return dice_roll * 10

        return base + dice_roll

    def roll_height(self) -> int:
        """Roll height in inches."""
        physical = self.definition.physical
        base = physical.height_base
        dice_roll = roll_dice(physical.height_dice)
        return base + dice_roll

    def roll_weight(self) -> int:
        """Roll weight in pounds."""
        physical = self.definition.physical
        base = physical.weight_base
        dice_roll = roll_dice(physical.weight_dice)
        return base + dice_roll

    def generate_name(
        self,
        gender: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        """
        Generate a random name appropriate for the kindred.

        Args:
            gender: "male", "female", or None for random/unisex
            style: For elves: "rustic" or "courtly" (random if None)

        Returns:
            Generated full name
        """
        name_table = self.definition.name_table
        if not name_table:
            return "Unnamed"

        # Special handling for elves: use rustic or courtly names (no surnames)
        if self.definition.kindred_id == "elf":
            # Choose style randomly if not specified
            if style is None:
                style = random.choice(["rustic", "courtly"])

            if style == "courtly" and NameColumn.COURTLY in name_table.columns:
                names = name_table.get_names(NameColumn.COURTLY)
            elif NameColumn.RUSTIC in name_table.columns:
                names = name_table.get_names(NameColumn.RUSTIC)
            else:
                names = ["Unknown"]

            return random.choice(names) if names else "Unknown"

        # Standard naming for other kindreds
        # Determine first name column based on gender
        if gender == "male" and NameColumn.MALE in name_table.columns:
            first_names = name_table.get_names(NameColumn.MALE)
        elif gender == "female" and NameColumn.FEMALE in name_table.columns:
            first_names = name_table.get_names(NameColumn.FEMALE)
        elif NameColumn.UNISEX in name_table.columns:
            first_names = name_table.get_names(NameColumn.UNISEX)
        else:
            # Fallback: try any available column
            for col in [NameColumn.MALE, NameColumn.FEMALE, NameColumn.UNISEX]:
                if col in name_table.columns:
                    first_names = name_table.get_names(col)
                    break
            else:
                first_names = ["Unknown"]

        # Get surname if available
        surnames = name_table.get_names(NameColumn.SURNAME)

        first = random.choice(first_names) if first_names else "Unknown"
        surname = random.choice(surnames) if surnames else ""

        if surname:
            return f"{first} {surname}"
        return first

    def roll_aspect(self, aspect_type: AspectType) -> dict:
        """
        Roll on a specific aspect table.

        Args:
            aspect_type: The type of aspect to roll

        Returns:
            Dict with 'result', 'roll', and optionally 'item_id'
        """
        table = self.definition.get_aspect_table(aspect_type)
        if not table:
            return {"result": "", "roll": 0}

        roll = random.randint(1, table.die_size)
        entry = table.get_entry(roll)

        if entry:
            result = {
                "result": entry.result,
                "roll": roll,
            }
            if entry.item_id:
                result["item_id"] = entry.item_id
            if entry.description:
                result["description"] = entry.description
            return result

        return {"result": "", "roll": roll}

    def roll_all_aspects(self) -> dict:
        """
        Roll on all available aspect tables.

        Returns:
            Dict mapping aspect names to results, plus "_rolls" with roll history
        """
        results = {}
        rolls = {}

        # Map AspectType to output keys
        aspect_keys = {
            AspectType.BACKGROUND: "background",
            AspectType.TRINKET: "trinket",
            AspectType.HEAD: "head",
            AspectType.DEMEANOUR: "demeanour",
            AspectType.DESIRES: "desires",
            AspectType.FACE: "face",
            AspectType.DRESS: "dress",
            AspectType.BELIEFS: "beliefs",
            AspectType.FUR_BODY: "fur_body",
            AspectType.SPEECH: "speech",
        }

        for aspect_type, key in aspect_keys.items():
            if aspect_type in self.definition.aspect_tables:
                roll_result = self.roll_aspect(aspect_type)
                results[key] = roll_result.get("result", "")
                rolls[key] = roll_result.get("roll", 0)

                # Special handling for trinkets - store item_id
                if aspect_type == AspectType.TRINKET and "item_id" in roll_result:
                    results["trinket_item_id"] = roll_result["item_id"]

        results["_rolls"] = rolls
        return results

    def get_starting_abilities(self, level: int = 1) -> list[str]:
        """
        Get the ability IDs available at a given level.

        Args:
            level: Character level

        Returns:
            List of ability IDs the character can use
        """
        abilities = self.manager.get_abilities_for_level(
            self.definition.kindred_id, level
        )
        return [a.ability_id for a in abilities]

    def get_starting_languages(self) -> list[str]:
        """Get the native languages for this kindred."""
        return list(self.definition.native_languages)


def generate_character_kindred(
    kindred_id: str,
    gender: Optional[str] = None,
    level: int = 1,
) -> GeneratedKindredAspects:
    """
    Convenience function to generate kindred aspects for a character.

    Args:
        kindred_id: The kindred to generate (e.g., "breggle")
        gender: "male", "female", or None for random
        level: Starting level (default 1)

    Returns:
        GeneratedKindredAspects with all rolled values
    """
    generator = KindredGenerator(kindred_id)
    return generator.generate_all(gender=gender, level=level)


def generate_npc_kindred(
    kindred_id: str,
    gender: Optional[str] = None,
) -> GeneratedKindredAspects:
    """
    Generate kindred aspects for a randomly generated NPC.

    Args:
        kindred_id: The kindred to generate
        gender: "male", "female", or None for random

    Returns:
        GeneratedKindredAspects with all rolled values
    """
    # NPCs are typically level 0-1 equivalent
    return generate_character_kindred(kindred_id, gender=gender, level=1)
