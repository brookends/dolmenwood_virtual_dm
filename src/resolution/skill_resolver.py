"""
Skill Check Resolution System for Dolmenwood Virtual DM.

Implements the d6 skill check system used by Dolmenwood classes.
Integrates with the AbilityRegistry to get class-specific skill targets.

Skill Check Mechanics:
- Roll d6, compare to target number (lower is better)
- Success: roll >= target
- Natural 1: May trigger special failure effects
- Modifiers: Situational adjustments to target or roll
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from src.data_models import DiceRoller, DiceResult

if TYPE_CHECKING:
    from src.data_models import CharacterState


class SkillOutcome(str, Enum):
    """Possible outcomes of a skill check."""

    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"  # Natural 1 with save failure
    AUTOMATIC_SUCCESS = "automatic_success"  # No roll needed


@dataclass
class SkillCheckResult:
    """
    Result of a skill check.

    Contains the roll, target, modifiers, and outcome.
    """

    skill_name: str
    character_name: str
    character_level: int

    # Roll details
    roll: int
    target: int
    modifier: int = 0

    # Outcome
    outcome: SkillOutcome = SkillOutcome.FAILURE
    is_natural_1: bool = False

    # For natural 1 consequences
    save_required: bool = False
    save_type: Optional[str] = None
    save_roll: Optional[int] = None
    save_target: Optional[int] = None
    save_succeeded: bool = False

    # Consequence description
    description: str = ""
    consequence: Optional[str] = None

    # Time cost
    time_cost_turns: int = 0

    # Extra data for specific skills
    extra_data: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Whether the check succeeded."""
        return self.outcome in (SkillOutcome.SUCCESS, SkillOutcome.AUTOMATIC_SUCCESS)


@dataclass
class SkillDefinition:
    """
    Definition of a skill and its mechanics.

    Includes failure consequences, time costs, and special rules.
    """

    skill_id: str
    name: str
    description: str

    # Check mechanics
    base_target: int = 6  # Default target (roll >= target)
    uses_class_target: bool = True  # Use class-specific target from registry

    # Time cost
    time_per_attempt_turns: int = 0  # 0 = instant, 1 turn = 10 minutes
    time_on_failure_turns: int = 0

    # Retry rules
    can_retry: bool = True
    retry_delay_turns: int = 0
    retry_after_level_up: bool = False  # Can only retry after gaining level

    # Requirements
    requires_tools: Optional[str] = None  # e.g., "thieves_tools"
    requires_light: bool = False
    requires_quiet: bool = False

    # Natural 1 consequences
    natural_1_save: Optional[str] = None  # Save type on natural 1
    natural_1_consequence: Optional[str] = None  # What happens on failed save

    # Modifiers
    difficulty_modifiers: dict[str, int] = field(default_factory=dict)

    # Extra data
    extra_data: dict[str, Any] = field(default_factory=dict)


class SkillResolver:
    """
    Resolves skill checks for Dolmenwood characters.

    Integrates with AbilityRegistry to get class-specific skill targets
    and implements the d6 skill check system.
    """

    def __init__(self):
        self._dice = DiceRoller()
        self._skills: dict[str, SkillDefinition] = {}
        self._register_standard_skills()

    def _register_standard_skills(self) -> None:
        """Register all standard skill definitions."""
        # =================================================================
        # THIEF SKILLS
        # =================================================================
        self._skills["climb_wall"] = SkillDefinition(
            skill_id="climb_wall",
            name="Climb Wall",
            description=(
                "Climb vertical or very steep surfaces with only minimal "
                "handholds, without special climbing equipment."
            ),
            can_retry=True,
            retry_delay_turns=1,
            natural_1_save="doom",
            natural_1_consequence=(
                "Fall from halfway point, suffering 1d6 damage per 10' of fall."
            ),
            extra_data={
                "check_per_100ft": True,
                "easier_climbs_auto_success": True,
            },
        )

        self._skills["decipher_document"] = SkillDefinition(
            skill_id="decipher_document",
            name="Decipher Document",
            description=(
                "Understand the gist of a non-magical text in an unknown "
                "language, unravel a cypher, or identify cryptic map landmarks."
            ),
            can_retry=False,
            retry_after_level_up=True,
        )

        self._skills["disarm_mechanism"] = SkillDefinition(
            skill_id="disarm_mechanism",
            name="Disarm Mechanism",
            description=(
                "Disarm complex, clockwork-like trap mechanisms hidden in "
                "a lock, lid, door handle, or similar."
            ),
            time_per_attempt_turns=1,
            can_retry=True,
            retry_delay_turns=1,
            requires_tools="thieves_tools",
            natural_1_save="doom",
            natural_1_consequence="Accidentally spring the trap.",
        )

        self._skills["legerdemain"] = SkillDefinition(
            skill_id="legerdemain",
            name="Legerdemain",
            description=(
                "Pilfer a small item in possession of another creature or "
                "perform sleight of hand tricks."
            ),
            natural_1_save="doom",
            natural_1_consequence="Noticed by victim. Referee determines reaction.",
            extra_data={
                "difficulty_per_3_levels": -1,
            },
        )

        self._skills["pick_lock"] = SkillDefinition(
            skill_id="pick_lock",
            name="Pick Lock",
            description="Open a lock without the key.",
            time_per_attempt_turns=1,
            can_retry=True,
            retry_delay_turns=1,
            requires_tools="thieves_tools",
            extra_data={
                "advanced_locks": "May incur penalty or limited attempts",
            },
        )

        self._skills["stealth"] = SkillDefinition(
            skill_id="stealth",
            name="Stealth",
            description=(
                "Hide in shadows as only cover, or remain undetected when "
                "party has been spotted."
            ),
        )

        # =================================================================
        # STANDARD SKILLS (all characters)
        # =================================================================
        self._skills["listen"] = SkillDefinition(
            skill_id="listen",
            name="Listen",
            description="Listen for sounds beyond a door or around a corner.",
            base_target=6,  # Default 1-in-6 for non-specialists
            requires_quiet=True,
        )

        self._skills["search"] = SkillDefinition(
            skill_id="search",
            name="Search",
            description="Search an area for hidden objects, secret doors, or traps.",
            base_target=6,  # Default 1-in-6 for non-specialists
            time_per_attempt_turns=1,
        )

        # =================================================================
        # HUNTER SKILLS
        # =================================================================
        self._skills["track"] = SkillDefinition(
            skill_id="track",
            name="Track",
            description="Follow tracks left by creatures through wilderness terrain.",
            time_on_failure_turns=1,
            can_retry=True,
            extra_data={
                "modifiers": {
                    "rain": -2,
                    "snow": +1,
                    "hard_ground": -1,
                    "old_trail": -1,
                },
            },
        )

        # =================================================================
        # BARD SKILLS
        # =================================================================
        self._skills["lore"] = SkillDefinition(
            skill_id="lore",
            name="Lore",
            description="Recall knowledge about legends, history, or folklore.",
            base_target=5,  # 2-in-6 base
            extra_data={
                "scaling": "+1 per 3 levels",
            },
        )

        # =================================================================
        # MAGICIAN SKILLS
        # =================================================================
        self._skills["detect_magic"] = SkillDefinition(
            skill_id="detect_magic",
            name="Detect Magic",
            description="Sense the presence of magical enchantments on objects or areas.",
            time_per_attempt_turns=1,
        )

    def get_skill_definition(self, skill_name: str) -> Optional[SkillDefinition]:
        """Get a skill definition by name."""
        return self._skills.get(skill_name.lower().replace(" ", "_"))

    def get_skill_target(
        self,
        character: "CharacterState",
        skill_name: str,
    ) -> int:
        """
        Get the skill check target for a character.

        Uses the AbilityRegistry to look up class-specific targets,
        falling back to base target if not a class skill.

        Args:
            character: The character making the check
            skill_name: Name of the skill

        Returns:
            Target number (roll d6 >= target to succeed)
        """
        from src.classes.ability_registry import get_ability_registry

        registry = get_ability_registry()
        skill_key = skill_name.lower().replace(" ", "_")

        # Try class-specific target first
        class_target = registry.get_skill_target(character, skill_key)
        if class_target is not None:
            return class_target

        # Fall back to skill definition base target
        skill_def = self.get_skill_definition(skill_key)
        if skill_def:
            return skill_def.base_target

        # Default: 6 (1-in-6 chance)
        return 6

    def check_can_use_skill(
        self,
        character: "CharacterState",
        skill_name: str,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check if a character can use a skill.

        Args:
            character: The character
            skill_name: Name of the skill
            context: Context with keys like:
                - has_tools: Whether character has required tools
                - is_quiet: Whether environment is quiet
                - has_light: Whether there is light

        Returns:
            Tuple of (can_use, reason)
        """
        skill_key = skill_name.lower().replace(" ", "_")
        skill_def = self.get_skill_definition(skill_key)

        if not skill_def:
            return True, ""  # Unknown skill, allow attempt

        # Check tool requirements
        if skill_def.requires_tools:
            if not context.get("has_tools", False):
                return False, f"Requires {skill_def.requires_tools}"

        # Check quiet requirement
        if skill_def.requires_quiet:
            if not context.get("is_quiet", True):
                return False, "Environment too noisy"

        # Check light requirement
        if skill_def.requires_light:
            if not context.get("has_light", True):
                return False, "Not enough light"

        return True, ""

    def resolve_skill_check(
        self,
        character: "CharacterState",
        skill_name: str,
        modifier: int = 0,
        context: Optional[dict[str, Any]] = None,
        auto_roll: bool = True,
        roll_value: Optional[int] = None,
    ) -> SkillCheckResult:
        """
        Resolve a skill check for a character.

        Args:
            character: The character making the check
            skill_name: Name of the skill
            modifier: Situational modifier to the roll
            context: Additional context for the check
            auto_roll: Whether to automatically roll dice
            roll_value: Pre-set roll value (for testing)

        Returns:
            SkillCheckResult with full outcome
        """
        context = context or {}
        skill_key = skill_name.lower().replace(" ", "_")
        skill_def = self.get_skill_definition(skill_key)

        # Get target number
        target = self.get_skill_target(character, skill_key)

        # Create base result
        result = SkillCheckResult(
            skill_name=skill_name,
            character_name=character.name,
            character_level=character.level,
            roll=0,
            target=target,
            modifier=modifier,
        )

        # Check requirements
        can_use, reason = self.check_can_use_skill(character, skill_name, context)
        if not can_use:
            result.outcome = SkillOutcome.FAILURE
            result.description = f"Cannot attempt: {reason}"
            return result

        # Roll the dice
        if roll_value is not None:
            result.roll = roll_value
        elif auto_roll:
            roll = self._dice.roll_d6(1, f"{character.name} {skill_name} check")
            result.roll = roll.total
        else:
            result.roll = 0
            result.description = f"Roll d6, need {target}+ to succeed"
            return result

        # Apply modifier and determine outcome
        effective_roll = result.roll + modifier
        is_natural_1 = result.roll == 1
        result.is_natural_1 = is_natural_1

        if effective_roll >= target:
            result.outcome = SkillOutcome.SUCCESS
            result.description = f"Success! Rolled {result.roll}"
            if modifier != 0:
                result.description += f" ({effective_roll} with modifier)"
        else:
            result.outcome = SkillOutcome.FAILURE
            result.description = f"Failed. Rolled {result.roll}, needed {target}+"

            # Handle natural 1 consequences
            if is_natural_1 and skill_def and skill_def.natural_1_save:
                result.save_required = True
                result.save_type = skill_def.natural_1_save
                result.consequence = skill_def.natural_1_consequence

                # Roll the save
                save_roll = self._dice.roll_d20(
                    f"{character.name} saves vs {skill_def.natural_1_save}"
                )
                result.save_roll = save_roll.total

                # Get save target from character
                save_target = character.get_saving_throw(skill_def.natural_1_save)
                result.save_target = save_target

                if save_roll.total >= save_target:
                    result.save_succeeded = True
                    result.description += (
                        f" Natural 1! Saved vs {skill_def.natural_1_save} "
                        f"(rolled {save_roll.total} vs {save_target})"
                    )
                else:
                    result.outcome = SkillOutcome.CRITICAL_FAILURE
                    result.save_succeeded = False
                    result.description += (
                        f" Natural 1! Failed save vs {skill_def.natural_1_save} "
                        f"(rolled {save_roll.total} vs {save_target}). "
                        f"{skill_def.natural_1_consequence}"
                    )

        # Track time cost
        if skill_def:
            if result.success:
                result.time_cost_turns = skill_def.time_per_attempt_turns
            else:
                result.time_cost_turns = max(
                    skill_def.time_per_attempt_turns, skill_def.time_on_failure_turns
                )

        return result

    def get_character_skills(
        self,
        character: "CharacterState",
    ) -> list[dict[str, Any]]:
        """
        Get all skills available to a character with their targets.

        Returns:
            List of skill info dicts with name, target, description
        """
        from src.classes.ability_registry import get_ability_registry

        registry = get_ability_registry()
        class_skills = registry.get_class_skills(character.character_class)

        skills = []
        for skill_name in class_skills:
            target = self.get_skill_target(character, skill_name)
            skill_def = self.get_skill_definition(skill_name)

            skills.append(
                {
                    "name": skill_name,
                    "target": target,
                    "description": skill_def.description if skill_def else "",
                    "chance": f"{7 - target}-in-6",
                }
            )

        # Add standard skills if character has bonuses
        for standard_skill in ["listen", "search"]:
            if standard_skill not in class_skills:
                target = self.get_skill_target(character, standard_skill)
                if target < 6:  # Character has bonus to this skill
                    skill_def = self.get_skill_definition(standard_skill)
                    skills.append(
                        {
                            "name": standard_skill,
                            "target": target,
                            "description": skill_def.description if skill_def else "",
                            "chance": f"{7 - target}-in-6",
                        }
                    )

        return skills


# Module-level singleton accessor
_resolver: Optional[SkillResolver] = None


def get_skill_resolver() -> SkillResolver:
    """Get the global skill resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = SkillResolver()
    return _resolver


# Convenience functions
def resolve_skill_check(
    character: "CharacterState",
    skill_name: str,
    modifier: int = 0,
    context: Optional[dict[str, Any]] = None,
) -> SkillCheckResult:
    """
    Resolve a skill check for a character.

    Convenience function that uses the global resolver.
    """
    resolver = get_skill_resolver()
    return resolver.resolve_skill_check(character, skill_name, modifier, context)
