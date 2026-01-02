"""
Dolmenwood Faction System.

This module provides a complete faction system for the Dolmenwood Virtual DM,
implementing:
- Territory-only faction turns on a weekly cadence
- Inter-faction relationship matrix with group matching
- Party-facing interaction layer (affiliation, jobs, standing)

Core philosophy (preserved):
- Python is the referee; the LLM is the narrator
- All dice/RNG goes through DiceRoller for determinism
- State changes are centralized through the faction engine
- The system remains playable with LLM disabled

Naming notes (collision avoidance):
- FactionTurnState (not FactionState) - avoids data_models.FactionState
- FactionRelations (not FactionRelationship) - avoids data_models.FactionRelationship
- PartyFactionState for party standing/affiliation
"""

# Data models
from src.factions.faction_models import (
    # Static content
    Resource,
    Goal,
    ActionTarget,
    EffectCommand,
    ActionTemplate,
    Enclave,
    HomeTerritory,
    FactionDefinition,
    FactionRules,
    # Dynamic state
    ActionInstance,
    Territory,
    FactionLogEntry,
    FactionTurnState,
    # Party state
    PartyAffiliation,
    ActiveJob,
    PartyFactionState,
    # Relationship models
    Relation,
    GroupRule,
    # Adventurer profile models
    PCJoinPolicy,
    QuestEffect,
    QuestTemplate,
    AdventurerProfile,
)

# Loaders
from src.factions.faction_loader import (
    FactionLoader,
    LoadResult,
)

from src.factions.faction_relations import (
    FactionRelations,
    FactionRelationsLoader,
    RelationsLoadResult,
)

from src.factions.faction_adventurers import (
    FactionAdventurerProfiles,
    FactionAdventurerProfilesLoader,
    ProfilesLoadResult,
)

__all__ = [
    # Static content models
    "Resource",
    "Goal",
    "ActionTarget",
    "EffectCommand",
    "ActionTemplate",
    "Enclave",
    "HomeTerritory",
    "FactionDefinition",
    "FactionRules",
    # Dynamic state models
    "ActionInstance",
    "Territory",
    "FactionLogEntry",
    "FactionTurnState",
    # Party state models
    "PartyAffiliation",
    "ActiveJob",
    "PartyFactionState",
    # Relationship models
    "Relation",
    "GroupRule",
    # Adventurer profile models
    "PCJoinPolicy",
    "QuestEffect",
    "QuestTemplate",
    "AdventurerProfile",
    # Loaders
    "FactionLoader",
    "LoadResult",
    "FactionRelations",
    "FactionRelationsLoader",
    "RelationsLoadResult",
    "FactionAdventurerProfiles",
    "FactionAdventurerProfilesLoader",
    "ProfilesLoadResult",
]
