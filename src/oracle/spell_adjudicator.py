"""
Mythic Spell Adjudicator for Dolmenwood Virtual DM.

Uses the Mythic GME oracle to adjudicate open-ended spell effects
that require referee discretion. This is the core of Tier 4 spell
resolution - handling spells where the outcome is genuinely uncertain.

The adjudicator:
1. Analyzes the spell and situation
2. Formulates appropriate Mythic questions
3. Returns structured adjudication results
4. Provides context for LLM interpretation

Example flow:
    adjudicator = MythicSpellAdjudicator(mythic_gme)
    result = adjudicator.adjudicate_wish(
        wish_text="remove the curse from Lord Malbrook",
        caster_level=14,
        target="Lord Malbrook",
        target_condition="cursed by a powerful hag"
    )
    # result contains: success level, complications, meaning pair for LLM
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from src.oracle.mythic_gme import (
    MythicGME,
    Likelihood,
    FateResult,
    FateCheckResult,
    MeaningRoll,
)
from src.oracle.effect_commands import EffectCommand, EffectCommandBuilder

if TYPE_CHECKING:
    from src.oracle.effect_commands import EffectBatch


# =============================================================================
# ENUMS
# =============================================================================


class SpellAdjudicationType(str, Enum):
    """Types of spell adjudication scenarios."""

    WISH = "wish"  # Open-ended reality alteration
    DIVINATION = "divination"  # Seeking information
    ILLUSION_BELIEF = "illusion_belief"  # Do targets believe?
    CHARM_RESISTANCE = "charm_resistance"  # Mental resistance
    SUMMONING_CONTROL = "summoning_control"  # Creature loyalty
    CURSE_BREAK = "curse_break"  # Removing afflictions
    REALITY_WARP = "reality_warp"  # Polymorph, transmutation
    PROTECTION_BYPASS = "protection_bypass"  # Does magic pierce defenses?
    DURATION_EXTENSION = "duration_extension"  # Spell lasts longer?
    SIDE_EFFECT = "side_effect"  # Unintended consequences
    GENERIC = "generic"  # Catch-all for unusual spells


class SuccessLevel(str, Enum):
    """Degrees of spell success."""

    EXCEPTIONAL_SUCCESS = "exceptional_success"  # Better than expected
    SUCCESS = "success"  # Works as intended
    PARTIAL_SUCCESS = "partial_success"  # Works with complications
    FAILURE = "failure"  # Doesn't work
    CATASTROPHIC_FAILURE = "catastrophic_failure"  # Backfires badly


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class AdjudicationContext:
    """Context for spell adjudication."""

    spell_name: str
    caster_name: str
    caster_level: int
    target_description: str = ""
    intention: str = ""  # What the caster is trying to achieve

    # Situational factors
    target_power_level: str = "normal"  # weak, normal, strong, legendary
    environmental_factors: list[str] = field(default_factory=list)
    magical_resistance: bool = False
    curse_source: str = ""  # For curse-breaking

    # Previous attempts
    previous_attempts: int = 0


@dataclass
class AdjudicationResult:
    """Result of spell adjudication."""

    adjudication_type: SpellAdjudicationType
    success_level: SuccessLevel

    # Mythic results for record-keeping
    primary_fate_check: Optional[FateCheckResult] = None
    secondary_fate_checks: list[FateCheckResult] = field(default_factory=list)
    meaning_roll: Optional[MeaningRoll] = None

    # For LLM interpretation
    interpretation_context: dict[str, Any] = field(default_factory=dict)

    # Complications/side effects
    has_complication: bool = False
    complication_meaning: Optional[MeaningRoll] = None
    random_event_occurred: bool = False

    # Pre-determined effects (if any can be mechanically resolved)
    # These are EffectCommand objects that can be executed by EffectExecutor
    predetermined_effects: list[EffectCommand] = field(default_factory=list)

    # Human-readable summary
    summary: str = ""

    def requires_interpretation(self) -> bool:
        """Check if this result needs LLM interpretation."""
        return self.meaning_roll is not None or self.has_complication

    def to_llm_context(self) -> dict[str, Any]:
        """Convert to context for LLM interpretation schema."""
        context = {
            "adjudication_type": self.adjudication_type.value,
            "success_level": self.success_level.value,
            "summary": self.summary,
            **self.interpretation_context,
        }

        if self.meaning_roll:
            context["meaning_pair"] = f"{self.meaning_roll.action} + {self.meaning_roll.subject}"
            context["action_word"] = self.meaning_roll.action
            context["subject_word"] = self.meaning_roll.subject

        if self.has_complication and self.complication_meaning:
            context["complication_pair"] = (
                f"{self.complication_meaning.action} + {self.complication_meaning.subject}"
            )

        return context


# =============================================================================
# MYTHIC SPELL ADJUDICATOR
# =============================================================================


class MythicSpellAdjudicator:
    """
    Adjudicates spell outcomes using the Mythic GME oracle.

    This class handles the probabilistic resolution of spell effects
    that cannot be determined purely mechanically. It translates
    spell intentions into Mythic questions, interprets the oracle's
    response, and produces structured results for further processing.

    Key design principles:
    1. Each spell type has tailored likelihood assessments
    2. Results are structured for LLM interpretation
    3. Complications come from Random Events and meaning tables
    4. The adjudicator doesn't apply effects - it determines outcomes
    """

    def __init__(self, mythic: Optional[MythicGME] = None):
        """
        Initialize the adjudicator.

        Args:
            mythic: MythicGME instance (creates new one with DiceRngAdapter if not provided)
        """
        if mythic is None:
            from src.oracle.dice_rng_adapter import DiceRngAdapter
            mythic = MythicGME(rng=DiceRngAdapter("SpellAdjudicator"))
        self._mythic = mythic

    @property
    def chaos_factor(self) -> int:
        """Current Mythic Chaos Factor."""
        return self._mythic.get_chaos_factor()

    # =========================================================================
    # WISH ADJUDICATION
    # =========================================================================

    def adjudicate_wish(
        self,
        wish_text: str,
        context: AdjudicationContext,
        wish_power: str = "standard",  # minor, standard, major
    ) -> AdjudicationResult:
        """
        Adjudicate a Wish spell or similar reality-altering magic.

        Wishes are complex because they can attempt almost anything.
        We assess likelihood based on:
        - The magnitude of the wish
        - Caster level vs. effect difficulty
        - Whether it conflicts with powerful forces

        Args:
            wish_text: The exact wording of the wish
            context: Spell casting context
            wish_power: Power level of the wish spell

        Returns:
            AdjudicationResult with success level and interpretation context
        """
        # Determine base likelihood based on wish difficulty
        likelihood = self._assess_wish_likelihood(wish_text, context, wish_power)

        # Primary question: Does the wish succeed?
        primary_check = self._mythic.fate_check(
            f"Does the wish '{wish_text}' succeed?",
            likelihood,
        )

        # Map fate result to success level
        success_level = self._fate_to_success(primary_check.result)

        # For partial or complicated success, roll meaning
        meaning_roll = None
        if success_level in (SuccessLevel.PARTIAL_SUCCESS, SuccessLevel.SUCCESS):
            if primary_check.random_event_triggered or success_level == SuccessLevel.PARTIAL_SUCCESS:
                meaning_roll = self._mythic.roll_meaning()

        # Check for complications on exceptional no
        complication_meaning = None
        has_complication = (
            success_level == SuccessLevel.CATASTROPHIC_FAILURE or
            (success_level == SuccessLevel.FAILURE and primary_check.random_event_triggered)
        )
        if has_complication:
            complication_meaning = self._mythic.roll_meaning()

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.WISH,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            has_complication=has_complication,
            complication_meaning=complication_meaning,
            random_event_occurred=primary_check.random_event_triggered,
            interpretation_context={
                "wish_text": wish_text,
                "wish_power": wish_power,
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "target": context.target_description,
                "intention": context.intention or wish_text,
            },
        )

        result.summary = self._generate_wish_summary(result)
        return result

    def _assess_wish_likelihood(
        self,
        wish_text: str,
        context: AdjudicationContext,
        wish_power: str,
    ) -> Likelihood:
        """Assess the likelihood of a wish succeeding."""
        # Start with base likelihood based on wish power
        base_likelihoods = {
            "minor": Likelihood.VERY_LIKELY,
            "standard": Likelihood.LIKELY,
            "major": Likelihood.FIFTY_FIFTY,
        }
        base = base_likelihoods.get(wish_power, Likelihood.FIFTY_FIFTY)

        # Modify based on target power level
        power_mods = {
            "weak": 1,
            "normal": 0,
            "strong": -1,
            "legendary": -2,
        }
        modifier = power_mods.get(context.target_power_level, 0)

        # Higher level casters have better odds
        if context.caster_level >= 14:
            modifier += 1
        elif context.caster_level >= 9:
            modifier += 0
        elif context.caster_level >= 5:
            modifier -= 1
        else:
            modifier -= 2

        # Apply modifier (clamp to valid range)
        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    def _generate_wish_summary(self, result: AdjudicationResult) -> str:
        """Generate human-readable summary of wish result."""
        ctx = result.interpretation_context

        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            summary = f"The wish succeeds exceptionally - beyond {ctx['caster']}'s expectations."
        elif result.success_level == SuccessLevel.SUCCESS:
            summary = f"The wish succeeds as intended."
            if result.meaning_roll:
                summary += f" Theme: {result.meaning_roll}"
        elif result.success_level == SuccessLevel.PARTIAL_SUCCESS:
            summary = f"The wish succeeds but with a twist: {result.meaning_roll}"
        elif result.success_level == SuccessLevel.FAILURE:
            summary = "The wish fails to take effect."
        else:  # Catastrophic
            summary = f"The wish backfires catastrophically: {result.complication_meaning}"

        return summary

    # =========================================================================
    # CURSE BREAKING
    # =========================================================================

    def adjudicate_curse_break(
        self,
        context: AdjudicationContext,
        curse_power: str = "normal",  # minor, normal, powerful, legendary
        spell_specifically_counters: bool = False,
    ) -> AdjudicationResult:
        """
        Adjudicate an attempt to remove a curse.

        Success depends on:
        - Power of the curse vs. caster level
        - Whether the spell specifically targets this curse type
        - Previous failed attempts (makes it harder)

        Args:
            context: Includes curse details in target_description and curse_source
            curse_power: Strength of the curse
            spell_specifically_counters: True if using Remove Curse vs. general magic

        Returns:
            AdjudicationResult with success and potential costs
        """
        # Assess likelihood
        likelihood = self._assess_curse_break_likelihood(
            context, curse_power, spell_specifically_counters
        )

        # Primary check: Does the curse break?
        primary_check = self._mythic.fate_check(
            f"Does {context.caster_name}'s spell break the curse on {context.target_description}?",
            likelihood,
        )

        success_level = self._fate_to_success(primary_check.result)

        # On success or partial, determine if there's a cost
        meaning_roll = None
        predetermined_effects = []

        if success_level in (SuccessLevel.EXCEPTIONAL_SUCCESS, SuccessLevel.SUCCESS):
            # Create proper EffectCommand to remove the curse
            predetermined_effects.append(
                EffectCommandBuilder.remove_condition(
                    target_id=context.target_description,
                    condition="cursed",
                    source=f"{context.spell_name} by {context.caster_name}",
                )
            )

            # Check for cost even on success (powerful curses resist)
            if curse_power in ("powerful", "legendary"):
                cost_check = self._mythic.fate_check(
                    "Does breaking the curse exact a cost?",
                    Likelihood.LIKELY if curse_power == "legendary" else Likelihood.FIFTY_FIFTY,
                )
                if self._mythic.is_yes(cost_check):
                    meaning_roll = self._mythic.roll_meaning()

        elif success_level == SuccessLevel.PARTIAL_SUCCESS:
            # Curse weakened but not removed
            meaning_roll = self._mythic.roll_meaning()

        # Complications on failure
        has_complication = (
            success_level in (SuccessLevel.FAILURE, SuccessLevel.CATASTROPHIC_FAILURE) and
            (primary_check.random_event_triggered or curse_power in ("powerful", "legendary"))
        )
        complication_meaning = self._mythic.roll_meaning() if has_complication else None

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.CURSE_BREAK,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            has_complication=has_complication,
            complication_meaning=complication_meaning,
            random_event_occurred=primary_check.random_event_triggered,
            predetermined_effects=predetermined_effects,
            interpretation_context={
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "target": context.target_description,
                "curse_source": context.curse_source,
                "curse_power": curse_power,
            },
        )

        result.summary = self._generate_curse_break_summary(result)
        return result

    def _assess_curse_break_likelihood(
        self,
        context: AdjudicationContext,
        curse_power: str,
        specifically_counters: bool,
    ) -> Likelihood:
        """Assess likelihood of breaking a curse."""
        # Base likelihood from curse power
        base_likelihoods = {
            "minor": Likelihood.VERY_LIKELY,
            "normal": Likelihood.LIKELY,
            "powerful": Likelihood.FIFTY_FIFTY,
            "legendary": Likelihood.UNLIKELY,
        }
        base = base_likelihoods.get(curse_power, Likelihood.FIFTY_FIFTY)

        modifier = 0

        # Specific counterspell bonus
        if specifically_counters:
            modifier += 1

        # Caster level matters
        if context.caster_level >= 14:
            modifier += 1
        elif context.caster_level <= 5:
            modifier -= 1

        # Previous attempts make it harder
        modifier -= context.previous_attempts

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    def _generate_curse_break_summary(self, result: AdjudicationResult) -> str:
        """Generate summary for curse breaking."""
        ctx = result.interpretation_context

        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            return f"The curse shatters completely, with no lingering trace."
        elif result.success_level == SuccessLevel.SUCCESS:
            base = f"The curse is broken."
            if result.meaning_roll:
                return f"{base} Cost/theme: {result.meaning_roll}"
            return base
        elif result.success_level == SuccessLevel.PARTIAL_SUCCESS:
            return f"The curse weakens but clings to {ctx['target']}: {result.meaning_roll}"
        elif result.success_level == SuccessLevel.FAILURE:
            return f"The curse resists {ctx['caster']}'s magic."
        else:
            return f"The curse lashes back: {result.complication_meaning}"

    # =========================================================================
    # ILLUSION BELIEF
    # =========================================================================

    def adjudicate_illusion_belief(
        self,
        context: AdjudicationContext,
        illusion_quality: str = "standard",  # crude, standard, masterful
        viewer_intelligence: str = "average",  # dim, average, clever, brilliant
        viewer_has_reason_to_doubt: bool = False,
    ) -> AdjudicationResult:
        """
        Adjudicate whether a target believes an illusion.

        Used for illusion spells where belief determines effectiveness.

        Args:
            context: Casting context
            illusion_quality: How convincing is the illusion?
            viewer_intelligence: Target's mental acuity
            viewer_has_reason_to_doubt: Has something tipped them off?

        Returns:
            AdjudicationResult indicating belief level
        """
        likelihood = self._assess_illusion_likelihood(
            context, illusion_quality, viewer_intelligence, viewer_has_reason_to_doubt
        )

        primary_check = self._mythic.fate_check(
            f"Does {context.target_description} believe the illusion?",
            likelihood,
        )

        success_level = self._fate_to_success(primary_check.result)

        # On partial belief, roll for how they're affected
        meaning_roll = None
        if success_level == SuccessLevel.PARTIAL_SUCCESS:
            meaning_roll = self._mythic.roll_meaning()

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.ILLUSION_BELIEF,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            interpretation_context={
                "caster": context.caster_name,
                "target": context.target_description,
                "illusion_quality": illusion_quality,
                "viewer_intelligence": viewer_intelligence,
            },
        )

        if success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            result.summary = f"{context.target_description} is completely convinced."
        elif success_level == SuccessLevel.SUCCESS:
            result.summary = f"{context.target_description} believes the illusion."
        elif success_level == SuccessLevel.PARTIAL_SUCCESS:
            result.summary = f"{context.target_description} is uncertain: {meaning_roll}"
        else:
            result.summary = f"{context.target_description} sees through the illusion."

        return result

    def _assess_illusion_likelihood(
        self,
        context: AdjudicationContext,
        quality: str,
        intelligence: str,
        has_doubt: bool,
    ) -> Likelihood:
        """Assess likelihood of illusion being believed."""
        # Base from quality
        quality_bases = {
            "crude": Likelihood.UNLIKELY,
            "standard": Likelihood.FIFTY_FIFTY,
            "masterful": Likelihood.LIKELY,
        }
        base = quality_bases.get(quality, Likelihood.FIFTY_FIFTY)

        # Intelligence modifier
        int_mods = {
            "dim": 1,
            "average": 0,
            "clever": -1,
            "brilliant": -2,
        }
        modifier = int_mods.get(intelligence, 0)

        # Doubt is significant
        if has_doubt:
            modifier -= 2

        # Caster level helps
        if context.caster_level >= 9:
            modifier += 1

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    # =========================================================================
    # DIVINATION
    # =========================================================================

    def adjudicate_divination(
        self,
        question: str,
        context: AdjudicationContext,
        divination_type: str = "general",  # general, specific, scrying
        target_is_protected: bool = False,
    ) -> AdjudicationResult:
        """
        Adjudicate a divination spell seeking information.

        Divinations don't just succeed/fail - they provide information
        of varying clarity and completeness.

        Args:
            question: What the caster is trying to learn
            context: Casting context
            divination_type: Type of divination being attempted
            target_is_protected: Is the target warded against divination?

        Returns:
            AdjudicationResult with clarity of information received
        """
        # Assess likelihood of useful information
        likelihood = Likelihood.LIKELY
        if target_is_protected:
            likelihood = Likelihood.UNLIKELY
        elif divination_type == "scrying":
            likelihood = Likelihood.FIFTY_FIFTY

        primary_check = self._mythic.fate_check(
            f"Does the divination reveal useful information about: {question}?",
            likelihood,
        )

        success_level = self._fate_to_success(primary_check.result)

        # Divinations always produce some meaning to interpret
        meaning_roll = self._mythic.roll_meaning()

        # On failure, the meaning is misleading or fragmentary
        # On success, it's clear guidance

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.DIVINATION,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            interpretation_context={
                "question": question,
                "caster": context.caster_name,
                "divination_type": divination_type,
                "protected_target": target_is_protected,
                "information_quality": self._success_to_clarity(success_level),
            },
        )

        result.summary = self._generate_divination_summary(result)
        return result

    def _success_to_clarity(self, success_level: SuccessLevel) -> str:
        """Map success level to divination clarity."""
        return {
            SuccessLevel.EXCEPTIONAL_SUCCESS: "crystal clear vision",
            SuccessLevel.SUCCESS: "clear but symbolic",
            SuccessLevel.PARTIAL_SUCCESS: "fragmentary glimpses",
            SuccessLevel.FAILURE: "confusing, possibly false",
            SuccessLevel.CATASTROPHIC_FAILURE: "deliberately misleading",
        }.get(success_level, "unclear")

    def _generate_divination_summary(self, result: AdjudicationResult) -> str:
        """Generate summary for divination."""
        ctx = result.interpretation_context
        clarity = ctx["information_quality"]
        meaning = result.meaning_roll

        return f"Divination reveals ({clarity}): {meaning}"

    # =========================================================================
    # SUMMONING CONTROL
    # =========================================================================

    def adjudicate_summoning_control(
        self,
        context: AdjudicationContext,
        creature_type: str,
        creature_power: str = "normal",  # weak, normal, strong, overwhelming
        binding_strength: str = "standard",  # weak, standard, strong
    ) -> AdjudicationResult:
        """
        Adjudicate control over a summoned creature.

        Used for summoning spells where the creature might resist
        or break free from control.

        Args:
            context: Casting context
            creature_type: Type of creature summoned
            creature_power: Power level of the creature
            binding_strength: How strong is the binding magic?

        Returns:
            AdjudicationResult with control status
        """
        # Assess likelihood based on power balance
        likelihood = self._assess_summoning_likelihood(
            context, creature_power, binding_strength
        )

        primary_check = self._mythic.fate_check(
            f"Does {context.caster_name} maintain control over the {creature_type}?",
            likelihood,
        )

        success_level = self._fate_to_success(primary_check.result)

        # On failure, roll for creature's action
        meaning_roll = None
        if success_level in (SuccessLevel.FAILURE, SuccessLevel.CATASTROPHIC_FAILURE):
            meaning_roll = self._mythic.roll_meaning()

        # Partial success means tenuous control
        if success_level == SuccessLevel.PARTIAL_SUCCESS:
            meaning_roll = self._mythic.roll_meaning()

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.SUMMONING_CONTROL,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            interpretation_context={
                "caster": context.caster_name,
                "creature": creature_type,
                "creature_power": creature_power,
                "binding_strength": binding_strength,
            },
        )

        if success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            result.summary = f"The {creature_type} is utterly bound to {context.caster_name}'s will."
        elif success_level == SuccessLevel.SUCCESS:
            result.summary = f"The {creature_type} obeys {context.caster_name}."
        elif success_level == SuccessLevel.PARTIAL_SUCCESS:
            result.summary = f"The {creature_type} obeys reluctantly: {meaning_roll}"
        elif success_level == SuccessLevel.FAILURE:
            result.summary = f"The {creature_type} breaks free: {meaning_roll}"
        else:
            result.summary = f"The {creature_type} turns on its summoner: {meaning_roll}"

        return result

    def _assess_summoning_likelihood(
        self,
        context: AdjudicationContext,
        creature_power: str,
        binding_strength: str,
    ) -> Likelihood:
        """Assess likelihood of controlling a summoned creature."""
        # Base from binding strength
        binding_bases = {
            "weak": Likelihood.FIFTY_FIFTY,
            "standard": Likelihood.LIKELY,
            "strong": Likelihood.VERY_LIKELY,
        }
        base = binding_bases.get(binding_strength, Likelihood.LIKELY)

        # Creature power resists
        power_mods = {
            "weak": 1,
            "normal": 0,
            "strong": -1,
            "overwhelming": -3,
        }
        modifier = power_mods.get(creature_power, 0)

        # Caster level helps
        if context.caster_level >= 14:
            modifier += 1
        elif context.caster_level <= 5:
            modifier -= 1

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    # =========================================================================
    # CHARM RESISTANCE
    # =========================================================================

    def adjudicate_charm_resistance(
        self,
        context: AdjudicationContext,
        target_hit_dice: int = 1,
        charm_strength: str = "standard",  # weak, standard, strong
    ) -> AdjudicationResult:
        """
        Adjudicate whether a target resists a charm effect.

        Mechanic: target saves vs charm; on success, effect fails;
        on partial, duration reduced. If system lacks a charm save
        mechanic, use oracle fate check with odds derived from
        target HD/level vs caster level.

        Args:
            context: Casting context with caster and target info
            target_hit_dice: Target's hit dice or level
            charm_strength: Strength of the charm spell

        Returns:
            AdjudicationResult with resist/partial/fail and effects
        """
        # Assess likelihood of resistance based on HD vs caster level
        likelihood = self._assess_charm_resistance_likelihood(
            context, target_hit_dice, charm_strength
        )

        # Primary question: Does target resist?
        primary_check = self._mythic.fate_check(
            f"Does {context.target_description} resist the charm?",
            likelihood,
        )

        # Resistance outcomes:
        # Exceptional Yes = Complete resistance, target becomes suspicious
        # Yes = Resists charm
        # No = Charmed
        # Exceptional No = Deeply charmed (extended duration)

        predetermined_effects: list[EffectCommand] = []
        meaning_roll = None

        if primary_check.result == FateResult.EXCEPTIONAL_YES:
            success_level = SuccessLevel.EXCEPTIONAL_SUCCESS
            # Target resists and becomes suspicious
            predetermined_effects.append(
                EffectCommandBuilder.modify_disposition(
                    target_id=context.target_description,
                    delta=-1,
                    reason="Sensed charm attempt",
                    source=f"{context.spell_name} resisted",
                )
            )
        elif primary_check.result == FateResult.YES:
            success_level = SuccessLevel.SUCCESS
            # Clean resistance, no effects
        elif primary_check.result == FateResult.EXCEPTIONAL_NO:
            success_level = SuccessLevel.CATASTROPHIC_FAILURE
            # Deeply charmed - apply with extended duration
            predetermined_effects.append(
                EffectCommandBuilder.add_condition(
                    target_id=context.target_description,
                    condition="charmed",
                    duration="1 day",  # Extended
                    source=f"{context.spell_name} by {context.caster_name}",
                )
            )
        else:  # NO
            success_level = SuccessLevel.FAILURE
            # Standard charm
            predetermined_effects.append(
                EffectCommandBuilder.add_condition(
                    target_id=context.target_description,
                    condition="charmed",
                    duration="1 hour",
                    source=f"{context.spell_name} by {context.caster_name}",
                )
            )

        # Check for secondary partial result (between YES and clean NO)
        # If there's a random event on failure, it's a partial charm
        if success_level == SuccessLevel.FAILURE and primary_check.random_event_triggered:
            success_level = SuccessLevel.PARTIAL_SUCCESS
            # Partial charm - reduced duration
            predetermined_effects = [
                EffectCommandBuilder.add_condition(
                    target_id=context.target_description,
                    condition="charmed",
                    duration="10 minutes",  # Reduced
                    source=f"{context.spell_name} (weakened) by {context.caster_name}",
                )
            ]
            meaning_roll = self._mythic.roll_meaning()

        # Log to RunLog
        self._log_adjudication(
            context=context,
            adjudication_type=SpellAdjudicationType.CHARM_RESISTANCE,
            success_level=success_level,
            effects=predetermined_effects,
            primary_check=primary_check,
            meaning_roll=meaning_roll,
        )

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.CHARM_RESISTANCE,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            predetermined_effects=predetermined_effects,
            interpretation_context={
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "target": context.target_description,
                "target_hd": target_hit_dice,
                "charm_strength": charm_strength,
                "resistance_result": "resisted" if success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS) else "charmed",
            },
        )

        result.summary = self._generate_charm_resistance_summary(result)
        return result

    def _assess_charm_resistance_likelihood(
        self,
        context: AdjudicationContext,
        target_hit_dice: int,
        charm_strength: str,
    ) -> Likelihood:
        """Assess likelihood of target resisting charm."""
        # Higher HD targets are more likely to resist
        # HD difference: positive = target stronger, negative = caster stronger
        hd_diff = target_hit_dice - context.caster_level

        # Base likelihood from charm strength (inverted - stronger charm = less likely to resist)
        strength_bases = {
            "weak": Likelihood.LIKELY,
            "standard": Likelihood.FIFTY_FIFTY,
            "strong": Likelihood.UNLIKELY,
        }
        base = strength_bases.get(charm_strength, Likelihood.FIFTY_FIFTY)

        # Modify based on HD difference
        modifier = 0
        if hd_diff >= 4:
            modifier += 2  # Much stronger target
        elif hd_diff >= 2:
            modifier += 1  # Stronger target
        elif hd_diff <= -4:
            modifier -= 2  # Much weaker target
        elif hd_diff <= -2:
            modifier -= 1  # Weaker target

        # Magical resistance bonus
        if context.magical_resistance:
            modifier += 2

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    def _generate_charm_resistance_summary(self, result: AdjudicationResult) -> str:
        """Generate summary for charm resistance."""
        ctx = result.interpretation_context
        target = ctx.get("target", "target")

        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            return f"{target} completely resists and becomes suspicious of {ctx.get('caster')}."
        elif result.success_level == SuccessLevel.SUCCESS:
            return f"{target} resists the charm."
        elif result.success_level == SuccessLevel.PARTIAL_SUCCESS:
            return f"{target} is partially charmed (reduced duration): {result.meaning_roll}"
        elif result.success_level == SuccessLevel.FAILURE:
            return f"{target} is charmed by {ctx.get('caster')}."
        else:  # Catastrophic
            return f"{target} is deeply charmed by {ctx.get('caster')} (extended duration)."

    # =========================================================================
    # PROTECTION BYPASS
    # =========================================================================

    def adjudicate_protection_bypass(
        self,
        context: AdjudicationContext,
        protection_strength: str = "standard",  # minor, standard, powerful, legendary
        spell_level: int = 1,
    ) -> AdjudicationResult:
        """
        Adjudicate whether a spell bypasses a ward or protection.

        Mechanic: does spell bypass a ward/protection? Use deterministic
        check first if protections are mechanized; otherwise oracle fate
        check with odds derived from spell level vs protection strength.

        Args:
            context: Casting context
            protection_strength: How strong is the protection?
            spell_level: Level of the spell attempting to bypass

        Returns:
            AdjudicationResult with bypass/fail and context flags
        """
        # Assess likelihood based on spell level vs protection
        likelihood = self._assess_protection_bypass_likelihood(
            context, protection_strength, spell_level
        )

        # Primary question: Does spell bypass?
        primary_check = self._mythic.fate_check(
            f"Does {context.spell_name} bypass the protection on {context.target_description}?",
            likelihood,
        )

        success_level = self._fate_to_success(primary_check.result)
        predetermined_effects: list[EffectCommand] = []
        meaning_roll = None

        if success_level in (SuccessLevel.EXCEPTIONAL_SUCCESS, SuccessLevel.SUCCESS):
            # Spell bypasses - set context flag for downstream effects
            predetermined_effects.append(
                EffectCommandBuilder.set_flag(
                    target_id=context.target_description,
                    flag_name="protection_bypassed",
                    flag_value=True,
                    scope="interaction",
                    source=f"{context.spell_name} by {context.caster_name}",
                )
            )
            if success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
                # Protection is temporarily weakened
                predetermined_effects.append(
                    EffectCommandBuilder.set_flag(
                        target_id=context.target_description,
                        flag_name="protection_weakened",
                        flag_value=True,
                        scope="scene",
                        source=f"{context.spell_name} overwhelmed protection",
                    )
                )
        else:
            # Protection holds
            if success_level == SuccessLevel.CATASTROPHIC_FAILURE:
                # Spell is reflected or caster is affected
                meaning_roll = self._mythic.roll_meaning()

        # Log to RunLog
        self._log_adjudication(
            context=context,
            adjudication_type=SpellAdjudicationType.PROTECTION_BYPASS,
            success_level=success_level,
            effects=predetermined_effects,
            primary_check=primary_check,
            meaning_roll=meaning_roll,
        )

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.PROTECTION_BYPASS,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            predetermined_effects=predetermined_effects,
            interpretation_context={
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "spell": context.spell_name,
                "spell_level": spell_level,
                "target": context.target_description,
                "protection_strength": protection_strength,
                "bypassed": success_level in (SuccessLevel.EXCEPTIONAL_SUCCESS, SuccessLevel.SUCCESS),
            },
        )

        result.summary = self._generate_protection_bypass_summary(result)
        return result

    def _assess_protection_bypass_likelihood(
        self,
        context: AdjudicationContext,
        protection_strength: str,
        spell_level: int,
    ) -> Likelihood:
        """Assess likelihood of bypassing protection."""
        # Base likelihood from protection strength
        strength_bases = {
            "minor": Likelihood.VERY_LIKELY,
            "standard": Likelihood.LIKELY,
            "powerful": Likelihood.FIFTY_FIFTY,
            "legendary": Likelihood.UNLIKELY,
        }
        base = strength_bases.get(protection_strength, Likelihood.FIFTY_FIFTY)

        # Modify based on spell level
        modifier = 0
        if spell_level >= 7:
            modifier += 2  # Very high level spell
        elif spell_level >= 5:
            modifier += 1  # High level spell
        elif spell_level >= 3:
            modifier += 0  # Medium spell
        elif spell_level >= 1:
            modifier -= 1  # Low level spell
        else:
            modifier -= 2  # Cantrip

        # Caster level helps
        if context.caster_level >= 14:
            modifier += 1
        elif context.caster_level <= 5:
            modifier -= 1

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    def _generate_protection_bypass_summary(self, result: AdjudicationResult) -> str:
        """Generate summary for protection bypass."""
        ctx = result.interpretation_context

        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            return f"{ctx.get('spell')} overwhelms the protection - barrier temporarily weakened."
        elif result.success_level == SuccessLevel.SUCCESS:
            return f"{ctx.get('spell')} pierces the protection."
        elif result.success_level == SuccessLevel.PARTIAL_SUCCESS:
            return f"{ctx.get('spell')} partially penetrates: {result.meaning_roll}"
        elif result.success_level == SuccessLevel.FAILURE:
            return f"The protection holds against {ctx.get('spell')}."
        else:  # Catastrophic
            return f"The protection reflects {ctx.get('spell')}: {result.meaning_roll}"

    # =========================================================================
    # DURATION EXTENSION
    # =========================================================================

    def adjudicate_duration_extension(
        self,
        context: AdjudicationContext,
        condition_to_extend: str,
        original_duration_turns: int = 10,
        extension_power: str = "standard",  # minor, standard, major
    ) -> AdjudicationResult:
        """
        Adjudicate extending an existing effect's duration.

        Mechanic: extend an existing effect's duration. Needs stable
        representation of active effect durations. Produces effects
        to extend condition duration.

        Args:
            context: Casting context
            condition_to_extend: The condition/effect to extend
            original_duration_turns: Original duration in turns
            extension_power: How powerful is the extension attempt

        Returns:
            AdjudicationResult with extension amount and effects
        """
        # Assess likelihood of successful extension
        likelihood = self._assess_duration_extension_likelihood(
            context, extension_power
        )

        # Primary question: Does extension succeed?
        primary_check = self._mythic.fate_check(
            f"Does {context.caster_name}'s extension of {condition_to_extend} succeed?",
            likelihood,
        )

        success_level = self._fate_to_success(primary_check.result)
        predetermined_effects: list[EffectCommand] = []
        meaning_roll = None

        # Calculate extension amount based on success
        extension_turns = 0
        extension_hours = 0

        if success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            # Double original duration
            extension_turns = original_duration_turns
            extension_hours = 1 if original_duration_turns >= 60 else 0
        elif success_level == SuccessLevel.SUCCESS:
            # Standard extension (50% of original)
            extension_turns = original_duration_turns // 2
        elif success_level == SuccessLevel.PARTIAL_SUCCESS:
            # Minimal extension
            extension_turns = max(1, original_duration_turns // 4)
            meaning_roll = self._mythic.roll_meaning()

        if extension_turns > 0 or extension_hours > 0:
            predetermined_effects.append(
                EffectCommandBuilder.extend_condition_duration(
                    target_id=context.target_description,
                    condition=condition_to_extend,
                    turns=extension_turns,
                    hours=extension_hours,
                    source=f"{context.spell_name} by {context.caster_name}",
                )
            )

        # Log to RunLog
        self._log_adjudication(
            context=context,
            adjudication_type=SpellAdjudicationType.DURATION_EXTENSION,
            success_level=success_level,
            effects=predetermined_effects,
            primary_check=primary_check,
            meaning_roll=meaning_roll,
        )

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.DURATION_EXTENSION,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            predetermined_effects=predetermined_effects,
            interpretation_context={
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "target": context.target_description,
                "condition": condition_to_extend,
                "original_duration": original_duration_turns,
                "extension_turns": extension_turns,
                "extension_hours": extension_hours,
            },
        )

        result.summary = self._generate_duration_extension_summary(result)
        return result

    def _assess_duration_extension_likelihood(
        self,
        context: AdjudicationContext,
        extension_power: str,
    ) -> Likelihood:
        """Assess likelihood of duration extension."""
        # Base from extension power
        power_bases = {
            "minor": Likelihood.LIKELY,
            "standard": Likelihood.FIFTY_FIFTY,
            "major": Likelihood.UNLIKELY,  # Hard to extend major effects
        }
        base = power_bases.get(extension_power, Likelihood.FIFTY_FIFTY)

        # Caster level helps
        modifier = 0
        if context.caster_level >= 14:
            modifier += 2
        elif context.caster_level >= 9:
            modifier += 1
        elif context.caster_level <= 3:
            modifier -= 1

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    def _generate_duration_extension_summary(self, result: AdjudicationResult) -> str:
        """Generate summary for duration extension."""
        ctx = result.interpretation_context
        condition = ctx.get("condition", "effect")
        ext_turns = ctx.get("extension_turns", 0)
        ext_hours = ctx.get("extension_hours", 0)

        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            return f"{condition} duration doubled: +{ext_turns} turns, +{ext_hours} hours."
        elif result.success_level == SuccessLevel.SUCCESS:
            return f"{condition} duration extended by {ext_turns} turns."
        elif result.success_level == SuccessLevel.PARTIAL_SUCCESS:
            return f"{condition} barely extended ({ext_turns} turns): {result.meaning_roll}"
        else:
            return f"Failed to extend {condition} duration."

    # =========================================================================
    # REALITY WARP
    # =========================================================================

    # Reality warp outcome categories (deterministic table)
    REALITY_WARP_OUTCOMES = [
        "temporary_condition",  # 1-20
        "displacement",         # 21-40
        "resource_loss",        # 41-55
        "environmental_change", # 56-70
        "transformation",       # 71-85
        "temporal_effect",      # 86-95
        "planar_echo",          # 96-100
    ]

    def adjudicate_reality_warp(
        self,
        context: AdjudicationContext,
        warp_intensity: str = "standard",  # minor, standard, major, legendary
    ) -> AdjudicationResult:
        """
        Adjudicate a reality warp spell (polymorph, transmutation, etc.).

        High-uncertainty outcome that MUST be deterministic, not LLM-decided.
        Uses oracle tables: fate check for backlash, then deterministic
        table roll for warp category.

        Args:
            context: Casting context
            warp_intensity: How intense is the reality warp

        Returns:
            AdjudicationResult with structured outcome
        """
        from src.data_models import DiceRoller

        predetermined_effects: list[EffectCommand] = []
        secondary_checks: list[FateCheckResult] = []

        # First check: Does the spell succeed?
        success_likelihood = self._assess_reality_warp_likelihood(context, warp_intensity)
        primary_check = self._mythic.fate_check(
            f"Does {context.spell_name} successfully warp reality?",
            success_likelihood,
        )
        success_level = self._fate_to_success(primary_check.result)

        # Check for backlash (always a risk with reality warps)
        backlash_likelihood = self._assess_backlash_likelihood(warp_intensity)
        backlash_check = self._mythic.fate_check(
            "Does the reality warp cause a backlash?",
            backlash_likelihood,
        )
        secondary_checks.append(backlash_check)

        has_backlash = self._mythic.is_yes(backlash_check)
        warp_category = None
        meaning_roll = None

        # Roll on deterministic warp table for outcome category
        warp_roll = DiceRoller.roll("1d100", f"{context.spell_name} warp category")
        warp_category = self._lookup_warp_category(warp_roll.total)

        # Generate effects based on success and warp category
        if success_level in (SuccessLevel.EXCEPTIONAL_SUCCESS, SuccessLevel.SUCCESS):
            # Warp succeeded - apply primary effect
            predetermined_effects.extend(
                self._generate_warp_effects(context, warp_category, "success")
            )
        elif success_level == SuccessLevel.PARTIAL_SUCCESS:
            # Partial warp - reduced effect
            predetermined_effects.extend(
                self._generate_warp_effects(context, warp_category, "partial")
            )
            meaning_roll = self._mythic.roll_meaning()

        # Apply backlash if triggered
        if has_backlash:
            backlash_effects = self._generate_backlash_effects(context, warp_category)
            predetermined_effects.extend(backlash_effects)
            if meaning_roll is None:
                meaning_roll = self._mythic.roll_meaning()

        # Log to RunLog
        self._log_adjudication(
            context=context,
            adjudication_type=SpellAdjudicationType.REALITY_WARP,
            success_level=success_level,
            effects=predetermined_effects,
            primary_check=primary_check,
            meaning_roll=meaning_roll,
            has_complication=has_backlash,  # Backlash is the complication for reality warp
        )

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.REALITY_WARP,
            success_level=success_level,
            primary_fate_check=primary_check,
            secondary_fate_checks=secondary_checks,
            meaning_roll=meaning_roll,
            has_complication=has_backlash,
            complication_meaning=meaning_roll if has_backlash else None,
            random_event_occurred=primary_check.random_event_triggered or backlash_check.random_event_triggered,
            predetermined_effects=predetermined_effects,
            interpretation_context={
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "target": context.target_description,
                "spell": context.spell_name,
                "warp_intensity": warp_intensity,
                "warp_category": warp_category,
                "warp_roll": warp_roll.total,
                "has_backlash": has_backlash,
            },
        )

        result.summary = self._generate_reality_warp_summary(result)
        return result

    def _assess_reality_warp_likelihood(
        self,
        context: AdjudicationContext,
        warp_intensity: str,
    ) -> Likelihood:
        """Assess likelihood of reality warp succeeding."""
        # Base from intensity
        intensity_bases = {
            "minor": Likelihood.VERY_LIKELY,
            "standard": Likelihood.LIKELY,
            "major": Likelihood.FIFTY_FIFTY,
            "legendary": Likelihood.UNLIKELY,
        }
        base = intensity_bases.get(warp_intensity, Likelihood.FIFTY_FIFTY)

        # Caster level helps
        modifier = 0
        if context.caster_level >= 14:
            modifier += 2
        elif context.caster_level >= 9:
            modifier += 1
        elif context.caster_level <= 5:
            modifier -= 1

        result_value = max(0, min(9, base.value + modifier))
        return Likelihood(result_value)

    def _assess_backlash_likelihood(self, warp_intensity: str) -> Likelihood:
        """Assess likelihood of backlash from reality warp."""
        # Higher intensity = more likely backlash
        intensity_backlash = {
            "minor": Likelihood.VERY_UNLIKELY,
            "standard": Likelihood.UNLIKELY,
            "major": Likelihood.FIFTY_FIFTY,
            "legendary": Likelihood.LIKELY,
        }
        return intensity_backlash.get(warp_intensity, Likelihood.UNLIKELY)

    def _lookup_warp_category(self, roll: int) -> str:
        """Look up warp category from roll (1-100)."""
        if roll <= 20:
            return "temporary_condition"
        elif roll <= 40:
            return "displacement"
        elif roll <= 55:
            return "resource_loss"
        elif roll <= 70:
            return "environmental_change"
        elif roll <= 85:
            return "transformation"
        elif roll <= 95:
            return "temporal_effect"
        else:
            return "planar_echo"

    def _generate_warp_effects(
        self,
        context: AdjudicationContext,
        warp_category: str,
        outcome: str,  # "success" or "partial"
    ) -> list[EffectCommand]:
        """Generate effects based on warp category and outcome."""
        effects: list[EffectCommand] = []
        target = context.target_description

        duration = "1 hour" if outcome == "success" else "10 minutes"

        if warp_category == "temporary_condition":
            effects.append(
                EffectCommandBuilder.add_condition(
                    target_id=target,
                    condition="transformed",
                    duration=duration,
                    source=f"{context.spell_name} by {context.caster_name}",
                )
            )
        elif warp_category == "displacement":
            effects.append(
                EffectCommandBuilder.set_flag(
                    target_id=target,
                    flag_name="displaced",
                    flag_value=True,
                    scope="scene",
                    source=f"{context.spell_name}",
                )
            )
        elif warp_category == "resource_loss":
            # Minor exhaustion from reality strain
            effects.append(
                EffectCommandBuilder.apply_exhaustion(
                    target_id=target,
                    duration_days=1 if outcome == "success" else "1d4",
                    effect="reality strain",
                    source=f"{context.spell_name}",
                )
            )
        elif warp_category == "environmental_change":
            effects.append(
                EffectCommandBuilder.set_flag(
                    target_id="environment",
                    flag_name="reality_warped",
                    flag_value=True,
                    scope="scene",
                    source=f"{context.spell_name}",
                )
            )
        elif warp_category == "transformation":
            effects.append(
                EffectCommandBuilder.add_condition(
                    target_id=target,
                    condition="transformed",
                    duration=duration,
                    source=f"{context.spell_name}",
                )
            )
            effects.append(
                EffectCommandBuilder.set_flag(
                    target_id=target,
                    flag_name="form_changed",
                    flag_value=True,
                    scope="scene",
                    source=f"{context.spell_name}",
                )
            )
        elif warp_category == "temporal_effect":
            effects.append(
                EffectCommandBuilder.set_flag(
                    target_id=target,
                    flag_name="time_affected",
                    flag_value=True,
                    scope="scene",
                    source=f"{context.spell_name}",
                )
            )
        elif warp_category == "planar_echo":
            effects.append(
                EffectCommandBuilder.set_flag(
                    target_id=target,
                    flag_name="planar_touched",
                    flag_value=True,
                    scope="scene",
                    source=f"{context.spell_name}",
                )
            )

        return effects

    def _generate_backlash_effects(
        self,
        context: AdjudicationContext,
        warp_category: str,
    ) -> list[EffectCommand]:
        """Generate backlash effects from reality warp."""
        effects: list[EffectCommand] = []
        caster = context.caster_name

        # Backlash hits the caster
        if warp_category in ("temporary_condition", "transformation"):
            effects.append(
                EffectCommandBuilder.add_condition(
                    target_id=caster,
                    condition="stunned",
                    duration="1 round",
                    source="Reality warp backlash",
                )
            )
        elif warp_category == "resource_loss":
            effects.append(
                EffectCommandBuilder.apply_exhaustion(
                    target_id=caster,
                    duration_days=1,
                    effect="reality strain backlash",
                    source="Reality warp backlash",
                )
            )
        elif warp_category == "temporal_effect":
            effects.append(
                EffectCommandBuilder.age(
                    target_id=caster,
                    years="1d4",
                    source="Reality warp temporal backlash",
                )
            )
        else:
            # Generic minor backlash
            effects.append(
                EffectCommandBuilder.damage(
                    target_id=caster,
                    amount="1d6",
                    damage_type="psychic",
                    source="Reality warp backlash",
                )
            )

        return effects

    def _generate_reality_warp_summary(self, result: AdjudicationResult) -> str:
        """Generate summary for reality warp."""
        ctx = result.interpretation_context
        warp_cat = ctx.get("warp_category", "unknown")
        has_backlash = ctx.get("has_backlash", False)

        category_descriptions = {
            "temporary_condition": "temporary transformation",
            "displacement": "spatial displacement",
            "resource_loss": "draining reality strain",
            "environmental_change": "environmental warping",
            "transformation": "physical transformation",
            "temporal_effect": "time distortion",
            "planar_echo": "planar resonance",
        }
        cat_desc = category_descriptions.get(warp_cat, warp_cat)

        base = ""
        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            base = f"Reality warps perfectly: {cat_desc}."
        elif result.success_level == SuccessLevel.SUCCESS:
            base = f"Reality warps: {cat_desc}."
        elif result.success_level == SuccessLevel.PARTIAL_SUCCESS:
            base = f"Reality partially warps ({cat_desc}): {result.meaning_roll}"
        elif result.success_level == SuccessLevel.FAILURE:
            base = "The reality warp fails to take hold."
        else:
            base = f"The reality warp fails catastrophically: {result.meaning_roll}"

        if has_backlash:
            base += f" [BACKLASH: {result.complication_meaning}]"

        return base

    # =========================================================================
    # LOGGING HELPER
    # =========================================================================

    def _log_adjudication(
        self,
        context: AdjudicationContext,
        adjudication_type: SpellAdjudicationType,
        success_level: SuccessLevel,
        effects: list[EffectCommand],
        primary_check: FateCheckResult,
        meaning_roll: Optional[MeaningRoll] = None,
        has_complication: Optional[bool] = None,
    ) -> None:
        """Log adjudication to RunLog for observability."""
        # Default to primary check's random event if not specified
        complication = has_complication if has_complication is not None else primary_check.random_event_triggered
        try:
            from src.observability.run_log import get_run_log
            get_run_log().log_spell_adjudication(
                spell_name=context.spell_name,
                caster_id=context.caster_name,
                adjudication_type=adjudication_type.value,
                success_level=success_level.value,
                summary=f"Roll: {primary_check.roll}, Likelihood: {primary_check.likelihood.name}",
                effects_executed=[str(e) for e in effects],
                has_complication=complication,
                meaning_pair=str(meaning_roll) if meaning_roll else "",
            )
        except ImportError:
            pass  # RunLog not available

    # =========================================================================
    # GENERIC ADJUDICATION
    # =========================================================================

    def adjudicate_generic(
        self,
        question: str,
        context: AdjudicationContext,
        base_likelihood: Likelihood = Likelihood.FIFTY_FIFTY,
    ) -> AdjudicationResult:
        """
        Generic adjudication for unusual spell effects.

        Use this when none of the specific adjudicators apply.

        Args:
            question: The yes/no question to answer
            context: Casting context
            base_likelihood: Starting probability

        Returns:
            AdjudicationResult with outcome and meaning
        """
        # Apply caster level modifier
        modifier = 0
        if context.caster_level >= 14:
            modifier += 1
        elif context.caster_level >= 9:
            modifier += 0
        elif context.caster_level >= 5:
            modifier -= 1
        else:
            modifier -= 2

        adjusted_likelihood = Likelihood(
            max(0, min(9, base_likelihood.value + modifier))
        )

        primary_check = self._mythic.fate_check(question, adjusted_likelihood)
        success_level = self._fate_to_success(primary_check.result)

        # Always roll meaning for interpretation
        meaning_roll = self._mythic.roll_meaning()

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.GENERIC,
            success_level=success_level,
            primary_fate_check=primary_check,
            meaning_roll=meaning_roll,
            random_event_occurred=primary_check.random_event_triggered,
            interpretation_context={
                "question": question,
                "caster": context.caster_name,
                "caster_level": context.caster_level,
                "intention": context.intention,
            },
        )

        result.summary = f"{question} -> {success_level.value}: {meaning_roll}"
        return result

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _fate_to_success(self, fate_result: FateResult) -> SuccessLevel:
        """Convert Mythic Fate result to success level."""
        return {
            FateResult.EXCEPTIONAL_YES: SuccessLevel.EXCEPTIONAL_SUCCESS,
            FateResult.YES: SuccessLevel.SUCCESS,
            FateResult.NO: SuccessLevel.FAILURE,
            FateResult.EXCEPTIONAL_NO: SuccessLevel.CATASTROPHIC_FAILURE,
        }.get(fate_result, SuccessLevel.FAILURE)

    def check_for_side_effect(
        self,
        context: AdjudicationContext,
        spell_power: str = "standard",
    ) -> Optional[MeaningRoll]:
        """
        Check if a spell produces unintended side effects.

        This is a secondary check that can be applied to any spell
        resolution to add chaos and unpredictability.

        Args:
            context: Casting context
            spell_power: Power level of the spell

        Returns:
            MeaningRoll if side effect occurs, None otherwise
        """
        # Higher power = more likely side effects
        likelihood_map = {
            "minor": Likelihood.VERY_UNLIKELY,
            "standard": Likelihood.UNLIKELY,
            "major": Likelihood.FIFTY_FIFTY,
            "legendary": Likelihood.LIKELY,
        }
        likelihood = likelihood_map.get(spell_power, Likelihood.UNLIKELY)

        check = self._mythic.fate_check(
            "Does the spell produce an unexpected side effect?",
            likelihood,
        )

        if self._mythic.is_yes(check):
            return self._mythic.roll_meaning()

        return None

    def adjust_chaos_for_spell_outcome(self, result: AdjudicationResult) -> int:
        """
        Adjust Mythic Chaos Factor based on spell outcome.

        Exceptional successes give players control (lower chaos).
        Catastrophic failures cause chaos (raise chaos).

        Args:
            result: The adjudication result

        Returns:
            New chaos factor value
        """
        if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
            return self._mythic.chaos.decrease("Exceptional spell success")
        elif result.success_level == SuccessLevel.CATASTROPHIC_FAILURE:
            return self._mythic.chaos.increase("Catastrophic spell failure")
        elif result.has_complication:
            return self._mythic.chaos.increase("Spell complication")

        return self._mythic.get_chaos_factor()
