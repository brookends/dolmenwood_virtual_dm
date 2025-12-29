"""
NPC generation system for Dolmenwood Virtual DM.

Provides tools for generating complete NPC characters with class abilities,
suitable for combat encounters and social interactions.
"""

from src.npc.npc_generator import (
    NPCGenerator,
    NPCGenerationResult,
    AbilityScoreMethod,
)

__all__ = [
    "NPCGenerator",
    "NPCGenerationResult",
    "AbilityScoreMethod",
]
