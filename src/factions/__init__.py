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

from src.factions.faction_effects import (
    EffectResult,
    FactionEffectsInterpreter,
)

from src.factions.faction_engine import (
    ActionRollResult,
    CycleResult,
    FactionCycleResult,
    FactionEngine,
)

from src.factions.faction_wiring import (
    init_faction_engine,
    save_faction_state,
    load_faction_state,
    get_factions_summary,
    get_party_faction_summary,
    get_party_manager,
)

from src.factions.faction_party import (
    FactionWorkResult,
    JobCompletionResult,
    FactionPartyManager,
)

from src.factions.faction_hooks import (
    FactionModifiers,
    HexFactionLookup,
    calculate_modifiers,
    get_service_cost_multiplier,
    get_encounter_modifier,
    apply_cost_modifier,
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
    # Effects
    "EffectResult",
    "FactionEffectsInterpreter",
    # Engine
    "ActionRollResult",
    "CycleResult",
    "FactionCycleResult",
    "FactionEngine",
    # Wiring
    "init_faction_engine",
    "save_faction_state",
    "load_faction_state",
    "get_factions_summary",
    "get_party_faction_summary",
    "get_party_manager",
    # Party interaction layer
    "FactionWorkResult",
    "JobCompletionResult",
    "FactionPartyManager",
    # Faction hooks for other systems
    "FactionModifiers",
    "HexFactionLookup",
    "calculate_modifiers",
    "get_service_cost_multiplier",
    "get_encounter_modifier",
    "apply_cost_modifier",
]
