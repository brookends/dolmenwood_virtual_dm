"""
Oracle Module for Dolmenwood Virtual DM.

Provides the Mythic GME 2e integration for adjudicating uncertain outcomes
in spell resolution and other referee-discretion situations.

Key components:
- MythicGME: Core oracle engine (Fate Check, Meaning Tables, Chaos Factor)
- MythicSpellAdjudicator: Spell-specific question formulation
- EffectCommand: Structured game state changes
- EffectExecutor: Applies validated effects to game state

Usage:
    from src.oracle import MythicGME, MythicSpellAdjudicator, AdjudicationContext

    # Default uses DiceRngAdapter for deterministic, logged rolls
    mythic = MythicGME(chaos_factor=5)
    adjudicator = MythicSpellAdjudicator(mythic)

    context = AdjudicationContext(
        spell_name="Wish",
        caster_name="Merlin",
        caster_level=14,
        target_description="Lord Malbrook",
        intention="remove the hag's curse",
    )

    result = adjudicator.adjudicate_wish(
        wish_text="Remove the curse from Lord Malbrook",
        context=context,
    )

    # Result contains success level, meaning pairs for interpretation
    if result.requires_interpretation():
        llm_context = result.to_llm_context()
        # Send to LLM with MythicInterpretationSchema
"""

from src.oracle.mythic_gme import (
    MythicGME,
    Likelihood,
    FateResult,
    FateCheckResult,
    RandomEvent,
    RandomEventFocus,
    MeaningRoll,
    ChaosFactorState,
    FATE_CHART,
    ACTION_MEANINGS,
    SUBJECT_MEANINGS,
)

from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    SpellAdjudicationType,
    SuccessLevel,
    AdjudicationContext,
    AdjudicationResult,
)

from src.oracle.effect_commands import (
    EffectType,
    EffectCommand,
    EffectResult,
    EffectBatch,
    EffectCommandBuilder,
    EffectValidator,
    EffectExecutor,
)

__all__ = [
    # Mythic GME core
    "MythicGME",
    "Likelihood",
    "FateResult",
    "FateCheckResult",
    "RandomEvent",
    "RandomEventFocus",
    "MeaningRoll",
    "ChaosFactorState",
    "FATE_CHART",
    "ACTION_MEANINGS",
    "SUBJECT_MEANINGS",
    # Spell adjudicator
    "MythicSpellAdjudicator",
    "SpellAdjudicationType",
    "SuccessLevel",
    "AdjudicationContext",
    "AdjudicationResult",
    # Effect commands
    "EffectType",
    "EffectCommand",
    "EffectResult",
    "EffectBatch",
    "EffectCommandBuilder",
    "EffectValidator",
    "EffectExecutor",
]
