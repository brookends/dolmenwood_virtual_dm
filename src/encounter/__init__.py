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

from src.encounter.encounter_factory import (
    EncounterFactory,
    EncounterFactoryResult,
    get_encounter_factory,
    reset_encounter_factory,
    create_encounter_from_roll,
    create_wilderness_encounter,
    # Integrated encounter functions (Factory + Engine + State Machine)
    start_wilderness_encounter,
    start_dungeon_encounter,
    start_settlement_encounter,
)

__all__ = [
    # Encounter Engine
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
    # Encounter Factory
    "EncounterFactory",
    "EncounterFactoryResult",
    "get_encounter_factory",
    "reset_encounter_factory",
    "create_encounter_from_roll",
    "create_wilderness_encounter",
    # Integrated Encounter Functions (preferred API)
    "start_wilderness_encounter",
    "start_dungeon_encounter",
    "start_settlement_encounter",
]
