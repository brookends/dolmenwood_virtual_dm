"""
Intent Parser for Dolmenwood Virtual DM.

Parses player natural language input into structured intents
that can be routed to appropriate mechanical resolvers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionCategory(str, Enum):
    """High-level categories of player actions."""
    SPELL = "spell"                 # Casting a spell or using magic
    HAZARD = "hazard"               # Physical challenges (climb, jump, swim, etc.)
    EXPLORATION = "exploration"     # Search, listen, probe
    SOCIAL = "social"               # Parley, intimidate, persuade
    COMBAT = "combat"               # Attack, defend, flee
    SURVIVAL = "survival"           # Forage, fish, hunt, camp
    MOVEMENT = "movement"           # Travel, enter location
    INVENTORY = "inventory"         # Use item, equip, drop
    CREATIVE = "creative"           # Non-standard problem solving
    NARRATIVE = "narrative"         # Pure roleplay, no mechanics
    UNKNOWN = "unknown"             # Could not classify


class ActionType(str, Enum):
    """Specific action types within categories."""
    # Spell actions
    CAST_SPELL = "cast_spell"
    USE_MAGIC_ITEM = "use_magic_item"
    DISMISS_SPELL = "dismiss_spell"

    # Hazard/Physical actions (p150-155)
    CLIMB = "climb"
    JUMP = "jump"
    SWIM = "swim"
    FORCE_DOOR = "force_door"
    PICK_LOCK = "pick_lock"

    # Exploration actions
    SEARCH = "search"
    LISTEN = "listen"
    PROBE = "probe"                 # Using pole, pouring water, etc.
    EXAMINE = "examine"

    # Social actions
    PARLEY = "parley"
    INTIMIDATE = "intimidate"
    PERSUADE = "persuade"
    DECEIVE = "deceive"

    # Survival actions
    FORAGE = "forage"
    FISH = "fish"
    HUNT = "hunt"
    CAMP = "camp"
    REST = "rest"

    # Combat actions
    ATTACK = "attack"
    DEFEND = "defend"
    FLEE = "flee"

    # Movement actions
    TRAVEL = "travel"
    ENTER = "enter"
    EXIT = "exit"
    SNEAK = "sneak"

    # Inventory actions
    USE_ITEM = "use_item"
    EQUIP = "equip"
    DROP = "drop"
    GIVE = "give"

    # Creative/Narrative
    CREATIVE_SOLUTION = "creative_solution"
    NARRATIVE_ACTION = "narrative_action"

    # Unknown
    UNKNOWN = "unknown"


class ResolutionType(str, Enum):
    """How an action should be mechanically resolved."""
    AUTO_SUCCESS = "auto_success"       # Adventurer competency, trivial task
    AUTO_FAIL = "auto_fail"             # Impossible action
    CHECK_REQUIRED = "check_required"   # Standard ability/skill check
    CHECK_ADVANTAGE = "check_advantage" # Check with bonus (creative solution)
    CHECK_DISADVANTAGE = "check_disadvantage"  # Check with penalty
    SAVE_REQUIRED = "save_required"     # Saving throw needed
    NARRATIVE_ONLY = "narrative_only"   # No mechanical effect
    COMBAT_TRIGGER = "combat_trigger"   # Transitions to combat
    TIME_ONLY = "time_only"             # Just consumes time, no roll
    RESOURCE_ONLY = "resource_only"     # Just consumes resources


class CheckType(str, Enum):
    """Types of ability checks per Dolmenwood rules."""
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"
    SEARCH = "search"               # Search check (secret doors, traps)
    LISTEN = "listen"               # Listen check
    SURVIVAL = "survival"           # Survival check (foraging, hunting)
    NONE = "none"


class SaveType(str, Enum):
    """Saving throw types per Dolmenwood rules."""
    DOOM = "doom"                   # Death/Poison
    RAY = "ray"                     # Wands/Rays
    HOLD = "hold"                   # Paralysis/Petrification
    BLAST = "blast"                 # Breath Weapons
    SPELL = "spell"                 # Spells/Magic


@dataclass
class ParsedIntent:
    """
    Structured output from LLM intent parsing.

    This is the JSON schema that the LLM will populate when
    parsing player input.
    """
    # Core classification
    action_category: ActionCategory
    action_type: ActionType
    confidence: float = 1.0         # 0.0-1.0 confidence in classification

    # Original input
    raw_input: str = ""

    # Target information
    target_type: Optional[str] = None       # "self", "creature", "object", "area", "door"
    target_id: Optional[str] = None         # Specific ID if known
    target_description: Optional[str] = None # "the goblin", "the locked door"

    # For spells specifically
    spell_id: Optional[str] = None          # Matched spell_id from DB
    spell_name: Optional[str] = None        # For fuzzy matching if id not found

    # For creative solutions
    proposed_approach: Optional[str] = None  # "pour water to reveal pit"
    narrative_description: Optional[str] = None  # Full description of action

    # Rule matching
    applicable_rule: Optional[str] = None    # "p152 - Hidden Features"
    suggested_resolution: ResolutionType = ResolutionType.CHECK_REQUIRED
    suggested_check: CheckType = CheckType.NONE
    suggested_save: Optional[SaveType] = None

    # Modifiers
    check_modifier: int = 0                  # Bonus/penalty to check

    # Context flags
    requires_check: bool = True
    is_combat_action: bool = False
    consumes_time: bool = True              # Does this take a Turn?
    time_cost_turns: int = 1                # How many turns it takes

    # For ambiguous cases
    alternative_interpretations: list[str] = field(default_factory=list)
    requires_clarification: bool = False
    clarification_prompt: Optional[str] = None


@dataclass
class IntentParserConfig:
    """Configuration for the intent parser."""
    # LLM settings
    use_semantic_spell_search: bool = True
    spell_match_threshold: float = 0.8

    # Known action patterns for quick matching
    # These bypass LLM for common actions
    quick_patterns: dict[str, ActionType] = field(default_factory=lambda: {
        "search": ActionType.SEARCH,
        "listen": ActionType.LISTEN,
        "attack": ActionType.ATTACK,
        "flee": ActionType.FLEE,
        "rest": ActionType.REST,
        "camp": ActionType.CAMP,
    })


# Adventurer competency rules (p150)
# These actions don't require rolls under normal conditions
ADVENTURER_COMPETENCIES = {
    "camping": "Finding campsites, setting up tents, gathering firewood, lighting fires",
    "horse_riding": "Basic riding and care of horses",
    "mapping": "Pacing out and estimating distances, basic mapping symbols",
    "rope_use": "Throwing, grappling, climbing, common knots",
    "swimming": "Treading water, swimming short distances",
    "travelling": "Packing gear, route planning, basic navigation",
    "valuing_treasure": "Identifying gems, valuing trade goods and art objects",
}


# Hazard rules mapping (p150-155)
HAZARD_RULES = {
    ActionType.CLIMB: {
        "rule_reference": "p150",
        "trivial_conditions": "non-pressured, lower branches of tree",
        "check_type": CheckType.DEXTERITY,
        "failure_effect": "fall at halfway point, 1d6 damage per 10'",
    },
    ActionType.JUMP: {
        "rule_reference": "p153",
        "trivial_long": "up to 5' with 20' run-up",
        "trivial_high": "up to 3' with 20' run-up",
        "check_long": "up to 10' with Strength Check",
        "check_high": "up to 5' with Strength Check",
        "check_type": CheckType.STRENGTH,
        "armor_modifiers": {"medium": -1, "heavy": -2},
    },
    ActionType.SWIM: {
        "rule_reference": "p154",
        "trivial_conditions": "calm water, no armor",
        "check_type": CheckType.STRENGTH,
        "armor_modifiers": {"light": 0, "medium": -2, "heavy": -4},
        "speed_modifier": 0.5,
    },
    ActionType.FORCE_DOOR: {
        "rule_reference": "p151",
        "check_type": CheckType.STRENGTH,
        "time_cost": 1,  # 1 Turn
        "noise": True,
        "tool_required": "axe or crowbar recommended",
    },
    ActionType.SEARCH: {
        "rule_reference": "p152",
        "check_type": CheckType.SEARCH,
        "time_cost": 1,  # 1 Turn per 10x10 area
        "referee_rolls": True,
    },
    ActionType.LISTEN: {
        "rule_reference": "p151",
        "check_type": CheckType.LISTEN,
        "time_cost": 1,  # 1 Turn
        "referee_rolls": True,
        "max_listeners": 2,  # Per typical door
    },
}


def get_hazard_rule(action_type: ActionType) -> Optional[dict]:
    """Get the hazard rule for an action type."""
    return HAZARD_RULES.get(action_type)


def is_adventurer_competency(action_description: str) -> bool:
    """
    Check if an action falls under adventurer competency (no roll needed).

    This is a simple keyword check; the LLM should do more nuanced evaluation.
    """
    description_lower = action_description.lower()
    competency_keywords = [
        "set up camp", "make camp", "light fire", "tie rope", "tie knot",
        "pack gear", "basic swimming", "tread water", "value gem", "appraise",
        "climb into tree", "lower branches",
    ]
    return any(kw in description_lower for kw in competency_keywords)
