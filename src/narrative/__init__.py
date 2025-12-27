"""
Narrative Resolution System for Dolmenwood Virtual DM.

This module provides the central switchboard for translating player text input
into game mechanics, coordinating between LLM intent parsing and Python mechanical
resolution per Dolmenwood rules.

Main Components:
- NarrativeResolver: Central switchboard connecting all resolvers
- IntentParser: Structures for LLM classification of player input
- SpellResolver: Handles spell casting and effect tracking
- HazardResolver: Resolves physical challenges per p150-155 rules
- CreativeSolutionResolver: Handles non-standard narrative solutions
"""

# Intent Parser - classification structures
from src.narrative.intent_parser import (
    ActionCategory,
    ActionType,
    ResolutionType,
    CheckType,
    SaveType,
    ParsedIntent,
    IntentParserConfig,
    ADVENTURER_COMPETENCIES,
    HAZARD_RULES,
    get_hazard_rule,
    is_adventurer_competency,
)

# Spell Resolver - spell casting and effects
from src.narrative.spell_resolver import (
    DurationType,
    RangeType,
    SpellEffectType,
    MagicType,
    SpellData,
    ActiveSpellEffect,
    SpellCastResult,
    SpellResolver,
)

# Hazard Resolver - physical challenges
from src.narrative.hazard_resolver import (
    HazardType,
    DarknessLevel,
    HazardResult,
    HazardResolver,
)

# Creative Solution Resolver - narrative solutions
from src.narrative.creative_resolver import (
    CreativeSolutionCategory,
    CreativeSolution,
    CreativeResolutionResult,
    CreativeSolutionResolver,
    KNOWN_CREATIVE_PATTERNS,
)

# Main Narrative Resolver - central switchboard
from src.narrative.narrative_resolver import (
    NarrationContext,
    ResolutionResult,
    NarrativeResolver,
)


__all__ = [
    # Intent Parser
    "ActionCategory",
    "ActionType",
    "ResolutionType",
    "CheckType",
    "SaveType",
    "ParsedIntent",
    "IntentParserConfig",
    "ADVENTURER_COMPETENCIES",
    "HAZARD_RULES",
    "get_hazard_rule",
    "is_adventurer_competency",
    # Spell Resolver
    "DurationType",
    "RangeType",
    "SpellEffectType",
    "MagicType",
    "SpellData",
    "ActiveSpellEffect",
    "SpellCastResult",
    "SpellResolver",
    # Hazard Resolver
    "HazardType",
    "DarknessLevel",
    "HazardResult",
    "HazardResolver",
    # Creative Solution Resolver
    "CreativeSolutionCategory",
    "CreativeSolution",
    "CreativeResolutionResult",
    "CreativeSolutionResolver",
    "KNOWN_CREATIVE_PATTERNS",
    # Main Narrative Resolver
    "NarrationContext",
    "ResolutionResult",
    "NarrativeResolver",
]
