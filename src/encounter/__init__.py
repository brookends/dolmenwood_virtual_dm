"""
Encounter Engine for Dolmenwood Virtual DM.

This module provides the unified encounter system that handles all encounters
regardless of their origin (wilderness, dungeon, or settlement).
"""

from src.encounter.encounter_engine import (
    EncounterPhase,
    EncounterOrigin,
    EncounterAction,
    AwarenessResult,
    SurpriseResult,
    DistanceResult,
    InitiativeResult,
    ActionDeclaration,
    EncounterRoundResult,
    EncounterEngine,
)

__all__ = [
    "EncounterPhase",
    "EncounterOrigin",
    "EncounterAction",
    "AwarenessResult",
    "SurpriseResult",
    "DistanceResult",
    "InitiativeResult",
    "ActionDeclaration",
    "EncounterRoundResult",
    "EncounterEngine",
]
