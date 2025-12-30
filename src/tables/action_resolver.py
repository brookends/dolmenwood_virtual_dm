"""
Action resolution system with failure-first logic.

Implements the failure-first pattern where consequences of failure
are determined BEFORE any dice are rolled. This ensures the DM knows
what's at stake before asking for rolls.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, Union

from src.data_models import DiceResult, DiceRoller, ActionType
from src.tables.table_types import SkillCheck


class ResolutionType(str, Enum):
    """Types of resolution mechanics."""
    SKILL_CHECK = "skill_check"       # X-in-6 check
    ABILITY_CHECK = "ability_check"   # Roll under ability score
    ATTACK_ROLL = "attack_roll"       # d20 vs AC
    SAVING_THROW = "saving_throw"     # d20 vs save target
    REACTION = "reaction"             # 2d6 reaction roll
    MORALE = "morale"                 # 2d6 vs morale score
    OPPOSED = "opposed"               # Opposed roll
    AUTOMATIC = "automatic"           # No roll needed


class FailureSeverity(str, Enum):
    """Severity levels for failure consequences."""
    MINIMAL = "minimal"       # Minor setback
    MODERATE = "moderate"     # Significant consequence
    SEVERE = "severe"         # Major consequence
    CATASTROPHIC = "catastrophic"  # Potentially fatal


@dataclass
class FailureConsequence:
    """
    Pre-determined consequence of failure.

    This is established BEFORE any roll is made, following the
    failure-first pattern.
    """
    severity: FailureSeverity
    description: str
    mechanical_effect: Optional[str] = None

    # Specific consequences
    damage: Optional[str] = None           # Dice notation for damage
    condition: Optional[str] = None        # Condition applied
    resource_loss: Optional[str] = None    # Resource consumed
    time_loss: Optional[str] = None        # Time consumed (turns)
    noise_alert: bool = False              # Alerts nearby creatures
    item_damaged: bool = False             # Equipment is damaged
    position_compromised: bool = False     # Tactical disadvantage

    # For saves
    save_allowed: bool = False             # Can make a save to reduce
    save_type: Optional[str] = None        # Type of save
    save_reduction: str = ""               # What save reduces

    def describe(self) -> str:
        """Get a full description of the consequence."""
        parts = [f"[{self.severity.value.upper()}] {self.description}"]

        if self.damage:
            parts.append(f"  Damage: {self.damage}")
        if self.condition:
            parts.append(f"  Condition: {self.condition}")
        if self.resource_loss:
            parts.append(f"  Lost: {self.resource_loss}")
        if self.time_loss:
            parts.append(f"  Time: {self.time_loss} turns")
        if self.save_allowed:
            parts.append(f"  Save ({self.save_type}): {self.save_reduction}")

        return "\n".join(parts)


@dataclass
class SuccessEffect:
    """Effects of a successful action."""
    description: str
    mechanical_effect: Optional[str] = None

    # Positive outcomes
    damage_dealt: Optional[str] = None     # Damage to target
    resource_gained: Optional[str] = None  # Resource acquired
    information_gained: bool = False       # New information
    progress_made: str = ""                # Progress toward goal


@dataclass
class ActionContext:
    """
    Context for action resolution.

    Contains all information needed to determine appropriate
    failure consequences and success effects.
    """
    # Actor information
    actor_name: str
    actor_id: Optional[str] = None
    actor_level: int = 1
    actor_class: Optional[str] = None

    # Ability scores (for checks)
    strength: int = 10
    intelligence: int = 10
    wisdom: int = 10
    dexterity: int = 10
    constitution: int = 10
    charisma: int = 10

    # Situation
    action_type: ActionType = ActionType.SEARCH
    difficulty: str = "normal"            # easy, normal, hard, very_hard
    is_combat: bool = False
    is_time_sensitive: bool = False
    enemies_nearby: bool = False
    environment_hazardous: bool = False

    # Equipment
    has_proper_tools: bool = True
    armor_worn: str = "none"

    # Modifiers
    situational_modifiers: dict[str, int] = field(default_factory=dict)

    def get_ability_modifier(self, ability: str) -> int:
        """Get B/X-style modifier for an ability score."""
        score = getattr(self, ability.lower(), 10)
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


@dataclass
class ActionResolution:
    """
    Complete resolution of an action.

    Contains the pre-determined consequences, the roll results,
    and the final outcome.
    """
    # The action
    action_description: str
    resolution_type: ResolutionType
    context: ActionContext

    # Pre-determined consequences (failure-first)
    failure_consequence: FailureConsequence
    success_effect: SuccessEffect

    # Roll details
    target_number: int = 0
    modifier: int = 0
    roll_result: Optional[DiceResult] = None

    # Outcome
    success: bool = False
    final_description: str = ""

    # For partial success systems
    partial_success: bool = False
    partial_description: str = ""

    def get_narrative(self) -> str:
        """Get a narrative description of the resolution."""
        lines = [
            f"Action: {self.action_description}",
            f"Actor: {self.context.actor_name}",
            "",
        ]

        if self.roll_result:
            lines.append(f"Roll: {self.roll_result}")
            lines.append(f"Target: {self.target_number}")
            if self.modifier != 0:
                lines.append(f"Modifier: {self.modifier:+d}")
            lines.append("")

        if self.success:
            lines.append(f"SUCCESS: {self.success_effect.description}")
        elif self.partial_success:
            lines.append(f"PARTIAL SUCCESS: {self.partial_description}")
        else:
            lines.append(f"FAILURE: {self.failure_consequence.description}")

        return "\n".join(lines)


class ActionResolver:
    """
    Resolves actions using the failure-first pattern.

    Before any roll is made, the resolver determines:
    1. What happens on failure (and how bad it is)
    2. What happens on success
    3. The target number and modifiers

    This ensures the DM knows the stakes before asking for rolls.
    """

    def __init__(self):
        self._consequence_generators: dict[ActionType, Callable] = {}
        self._register_default_consequences()

    def _register_default_consequences(self) -> None:
        """Register default consequence generators for action types."""
        self._consequence_generators[ActionType.SEARCH] = self._search_consequences
        self._consequence_generators[ActionType.PICK_LOCK] = self._pick_lock_consequences
        self._consequence_generators[ActionType.DISARM_TRAP] = self._disarm_trap_consequences
        self._consequence_generators[ActionType.OPEN_DOOR] = self._open_door_consequences
        self._consequence_generators[ActionType.LISTEN] = self._listen_consequences
        self._consequence_generators[ActionType.HIDE] = self._hide_consequences
        self._consequence_generators[ActionType.ATTACK] = self._attack_consequences
        self._consequence_generators[ActionType.CAST_SPELL] = self._spell_consequences

    def prepare_resolution(
        self,
        action_description: str,
        resolution_type: ResolutionType,
        context: ActionContext,
        custom_failure: Optional[FailureConsequence] = None,
        custom_success: Optional[SuccessEffect] = None,
    ) -> ActionResolution:
        """
        Prepare an action for resolution (failure-first).

        This determines all consequences BEFORE any roll is made.

        Args:
            action_description: What the character is attempting
            resolution_type: Type of roll needed
            context: Full context for the action
            custom_failure: Override default failure consequence
            custom_success: Override default success effect

        Returns:
            ActionResolution ready for rolling
        """
        # Determine failure consequence
        if custom_failure:
            failure = custom_failure
        else:
            failure = self._generate_failure_consequence(context)

        # Determine success effect
        if custom_success:
            success = custom_success
        else:
            success = self._generate_success_effect(context)

        # Calculate target number and modifiers
        target, modifier = self._calculate_target(resolution_type, context)

        return ActionResolution(
            action_description=action_description,
            resolution_type=resolution_type,
            context=context,
            failure_consequence=failure,
            success_effect=success,
            target_number=target,
            modifier=modifier,
        )

    def resolve(
        self,
        resolution: ActionResolution,
        roll_result: Optional[DiceResult] = None,
    ) -> ActionResolution:
        """
        Resolve a prepared action.

        Args:
            resolution: The prepared ActionResolution
            roll_result: Optional pre-made roll (for testing)

        Returns:
            Updated ActionResolution with outcome
        """
        # Make the roll if not provided
        if roll_result is None:
            roll_result = self._make_roll(resolution.resolution_type)

        resolution.roll_result = roll_result

        # Determine success
        total = roll_result.total + resolution.modifier

        if resolution.resolution_type == ResolutionType.SKILL_CHECK:
            # X-in-6: roll must be <= target
            resolution.success = total <= resolution.target_number
        elif resolution.resolution_type in (
            ResolutionType.ATTACK_ROLL,
            ResolutionType.SAVING_THROW
        ):
            # d20: roll must be >= target
            resolution.success = total >= resolution.target_number
        elif resolution.resolution_type == ResolutionType.ABILITY_CHECK:
            # Roll under: roll must be <= ability score
            resolution.success = total <= resolution.target_number
        elif resolution.resolution_type == ResolutionType.AUTOMATIC:
            resolution.success = True

        # Set final description
        if resolution.success:
            resolution.final_description = resolution.success_effect.description
        else:
            resolution.final_description = resolution.failure_consequence.description

        return resolution

    def quick_resolve(
        self,
        action_description: str,
        resolution_type: ResolutionType,
        context: ActionContext,
    ) -> ActionResolution:
        """
        Prepare and resolve an action in one step.

        Useful for simple actions, but still follows failure-first pattern.
        """
        resolution = self.prepare_resolution(
            action_description=action_description,
            resolution_type=resolution_type,
            context=context,
        )
        return self.resolve(resolution)

    def _generate_failure_consequence(self, context: ActionContext) -> FailureConsequence:
        """Generate appropriate failure consequence based on context."""
        # Check for registered consequence generator
        if context.action_type in self._consequence_generators:
            return self._consequence_generators[context.action_type](context, success=False)

        # Default consequence based on severity factors
        severity = self._determine_severity(context)

        return FailureConsequence(
            severity=severity,
            description="The action fails.",
            time_loss="1" if context.is_time_sensitive else None,
            noise_alert=context.enemies_nearby,
        )

    def _generate_success_effect(self, context: ActionContext) -> SuccessEffect:
        """Generate appropriate success effect based on context."""
        if context.action_type in self._consequence_generators:
            return self._consequence_generators[context.action_type](context, success=True)

        return SuccessEffect(
            description="The action succeeds.",
        )

    def _determine_severity(self, context: ActionContext) -> FailureSeverity:
        """Determine failure severity based on context."""
        severity_score = 0

        if context.is_combat:
            severity_score += 2
        if context.environment_hazardous:
            severity_score += 1
        if context.enemies_nearby:
            severity_score += 1
        if context.difficulty == "hard":
            severity_score += 1
        if context.difficulty == "very_hard":
            severity_score += 2

        if severity_score >= 4:
            return FailureSeverity.SEVERE
        elif severity_score >= 2:
            return FailureSeverity.MODERATE
        else:
            return FailureSeverity.MINIMAL

    def _calculate_target(
        self,
        resolution_type: ResolutionType,
        context: ActionContext
    ) -> tuple[int, int]:
        """
        Calculate target number and modifier for a roll.

        Returns:
            Tuple of (target_number, modifier)
        """
        modifier = sum(context.situational_modifiers.values())

        if resolution_type == ResolutionType.SKILL_CHECK:
            # X-in-6 target
            base = {
                "easy": 3,
                "normal": 2,
                "hard": 1,
                "very_hard": 1,
            }.get(context.difficulty, 2)

            if not context.has_proper_tools:
                modifier -= 1

            return base, modifier

        elif resolution_type == ResolutionType.ABILITY_CHECK:
            # Roll under ability score
            ability = self._get_relevant_ability(context.action_type)
            target = getattr(context, ability.lower(), 10)
            return target, modifier

        elif resolution_type == ResolutionType.ATTACK_ROLL:
            # Target is enemy AC (placeholder)
            return 10, modifier + context.actor_level

        elif resolution_type == ResolutionType.SAVING_THROW:
            # Base save target
            return 15, modifier

        return 10, modifier

    def _get_relevant_ability(self, action_type: ActionType) -> str:
        """Get the ability score relevant to an action type."""
        ability_map = {
            ActionType.ATTACK: "strength",
            ActionType.OPEN_DOOR: "strength",
            ActionType.SEARCH: "intelligence",
            ActionType.PICK_LOCK: "dexterity",
            ActionType.DISARM_TRAP: "dexterity",
            ActionType.HIDE: "dexterity",
            ActionType.LISTEN: "wisdom",
            ActionType.PARLEY: "charisma",
        }
        return ability_map.get(action_type, "intelligence")

    def _make_roll(self, resolution_type: ResolutionType) -> DiceResult:
        """Make the appropriate roll for a resolution type."""
        if resolution_type == ResolutionType.SKILL_CHECK:
            return DiceRoller.roll_d6(1, "Skill check")
        elif resolution_type in (
            ResolutionType.ATTACK_ROLL,
            ResolutionType.SAVING_THROW,
            ResolutionType.ABILITY_CHECK
        ):
            return DiceRoller.roll_d20("Resolution roll")
        elif resolution_type in (ResolutionType.REACTION, ResolutionType.MORALE):
            return DiceRoller.roll_2d6("2d6 roll")
        else:
            return DiceRoller.roll_d20("Default roll")

    # =========================================================================
    # CONSEQUENCE GENERATORS FOR SPECIFIC ACTION TYPES
    # =========================================================================

    def _search_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for search actions."""
        if success:
            return SuccessEffect(
                description="You find what you're looking for.",
                information_gained=True,
            )
        else:
            return FailureConsequence(
                severity=FailureSeverity.MINIMAL,
                description="You find nothing of interest.",
                time_loss="1",
                noise_alert=context.enemies_nearby,
            )

    def _pick_lock_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for lock picking."""
        if success:
            return SuccessEffect(
                description="The lock clicks open.",
                progress_made="Lock opened",
            )
        else:
            severity = FailureSeverity.MODERATE if context.is_time_sensitive else FailureSeverity.MINIMAL
            return FailureConsequence(
                severity=severity,
                description="The lock resists your attempts. Your tools slip.",
                time_loss="1",
                noise_alert=True,
                mechanical_effect="lockpick_check" if not context.has_proper_tools else None,
            )

    def _disarm_trap_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for trap disarming."""
        if success:
            return SuccessEffect(
                description="The trap is safely disarmed.",
                progress_made="Trap disabled",
            )
        else:
            return FailureConsequence(
                severity=FailureSeverity.SEVERE,
                description="The trap is triggered!",
                mechanical_effect="trigger_trap",
                save_allowed=True,
                save_type="doom",
                save_reduction="half damage",
            )

    def _open_door_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for forcing doors."""
        if success:
            return SuccessEffect(
                description="The door bursts open!",
                progress_made="Door opened",
            )
        else:
            return FailureConsequence(
                severity=FailureSeverity.MINIMAL,
                description="The door holds firm. You make considerable noise.",
                time_loss="1",
                noise_alert=True,
            )

    def _listen_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for listening."""
        if success:
            return SuccessEffect(
                description="You hear sounds beyond.",
                information_gained=True,
            )
        else:
            return FailureConsequence(
                severity=FailureSeverity.MINIMAL,
                description="You hear nothing distinctive.",
            )

    def _hide_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for hiding."""
        if success:
            return SuccessEffect(
                description="You blend into the shadows, unseen.",
            )
        else:
            severity = FailureSeverity.MODERATE if context.enemies_nearby else FailureSeverity.MINIMAL
            return FailureConsequence(
                severity=severity,
                description="You fail to find adequate cover.",
                position_compromised=True,
            )

    def _attack_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for attack actions."""
        if success:
            return SuccessEffect(
                description="Your attack strikes true!",
                damage_dealt="weapon_damage",
            )
        else:
            return FailureConsequence(
                severity=FailureSeverity.MINIMAL,
                description="Your attack misses.",
            )

    def _spell_consequences(self, context: ActionContext, success: bool) -> Union[FailureConsequence, SuccessEffect]:
        """Generate consequences for spell casting."""
        if success:
            return SuccessEffect(
                description="The spell takes effect!",
            )
        else:
            return FailureConsequence(
                severity=FailureSeverity.MODERATE,
                description="The spell fizzles. The magic is wasted.",
                resource_loss="spell_slot",
            )


# Convenience functions

def prepare_skill_check(
    actor_name: str,
    skill_name: str,
    base_chance: int,
    difficulty: str = "normal",
    **context_kwargs
) -> ActionResolution:
    """
    Prepare a skill check with failure-first logic.

    Args:
        actor_name: Name of character attempting the check
        skill_name: Name of the skill being used
        base_chance: Base X-in-6 chance
        difficulty: Difficulty modifier
        **context_kwargs: Additional context parameters

    Returns:
        Prepared ActionResolution
    """
    resolver = ActionResolver()
    context = ActionContext(
        actor_name=actor_name,
        difficulty=difficulty,
        **context_kwargs
    )

    return resolver.prepare_resolution(
        action_description=f"{actor_name} attempts {skill_name}",
        resolution_type=ResolutionType.SKILL_CHECK,
        context=context,
    )


def quick_skill_check(
    actor_name: str,
    skill_name: str,
    base_chance: int = 2,
    modifier: int = 0
) -> tuple[bool, str]:
    """
    Quick skill check for simple situations.

    Returns:
        Tuple of (success, description)
    """
    roll = DiceRoller.randint(1, 6, f"Quick skill check: {skill_name}")
    success = roll <= (base_chance + modifier)

    if success:
        return True, f"{actor_name} succeeds at {skill_name} (rolled {roll})"
    else:
        return False, f"{actor_name} fails at {skill_name} (rolled {roll})"
