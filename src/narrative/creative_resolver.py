"""
Creative Solution Resolver for Dolmenwood Virtual DM.

Handles non-standard, creative approaches to problems that don't map
directly to standard game mechanics. Implements the "Narrative Interaction"
principle from p150:

"The environment is described and clarified with questions from the group,
then the characters act and the Referee judges what happens. Sometimes a
die roll is required—putting a character's fate in the hands of chance—
but it is often possible to bypass hazards using ingenuity, without any
kind of random roll."
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_models import CharacterState

from src.narrative.intent_parser import ParsedIntent, ActionType, ResolutionType, CheckType


class CreativeSolutionCategory(str, Enum):
    """Categories of creative solutions."""

    TRAP_BYPASS = "trap_bypass"  # Creative ways to avoid/disarm traps
    OBSTACLE_BYPASS = "obstacle_bypass"  # Creative ways around physical obstacles
    INFORMATION_GATHERING = "information_gathering"  # Clever ways to learn things
    SOCIAL_MANIPULATION = "social_manipulation"  # Non-standard social approaches
    ENVIRONMENTAL_USE = "environmental_use"  # Using environment cleverly
    ITEM_IMPROVISATION = "item_improvisation"  # Using items in unusual ways
    UNKNOWN = "unknown"


@dataclass
class CreativeSolution:
    """A proposed creative solution from the LLM."""

    category: CreativeSolutionCategory
    description: str  # What the player is trying to do
    proposed_resolution: ResolutionType  # LLM's suggested resolution

    # Context
    target_hazard: Optional[str] = None  # What hazard/obstacle this addresses
    required_items: list[str] = field(default_factory=list)
    required_conditions: list[str] = field(default_factory=list)

    # Resolution details
    check_type: Optional[CheckType] = None
    check_modifier: int = 0  # Bonus/penalty to check
    time_cost_turns: int = 0

    # Rule justification
    rule_reference: Optional[str] = None
    similar_precedent: Optional[str] = None

    # For LLM explanation
    reasoning: str = ""


@dataclass
class CreativeResolutionResult:
    """Result of resolving a creative solution."""

    accepted: bool  # Was the solution accepted?
    resolution_type: ResolutionType
    description: str

    # If check was made
    check_made: bool = False
    check_type: Optional[CheckType] = None
    check_result: Optional[int] = None
    check_target: Optional[int] = None
    check_modifier: int = 0

    # Outcomes
    success: bool = False
    partial_success: bool = False
    consequences: list[str] = field(default_factory=list)

    # Time cost
    turns_spent: int = 0

    # For narration
    narrative_hints: list[str] = field(default_factory=list)

    # If solution was rejected
    rejection_reason: Optional[str] = None
    alternatives_offered: list[ResolutionType] = field(default_factory=list)


# Known creative solution patterns from Dolmenwood rules
# These are examples from the book that can be matched
KNOWN_CREATIVE_PATTERNS = {
    # From p155 - Tips for Handling Traps
    "smash_lock_destroy_trap": {
        "category": CreativeSolutionCategory.TRAP_BYPASS,
        "description": "Smashing the lock of a chest to destroy a delicate trap",
        "resolution": ResolutionType.AUTO_SUCCESS,
        "rule_reference": "p155 - Force",
        "conditions": ["target is chest with trapped lock", "has hammer or similar"],
    },
    "jam_trap_mechanism": {
        "category": CreativeSolutionCategory.TRAP_BYPASS,
        "description": "Jamming a trap mechanism with a rock or flagstone",
        "resolution": ResolutionType.CHECK_ADVANTAGE,
        "rule_reference": "p155 - Jamming",
        "check_type": CheckType.DEXTERITY,
    },
    "pour_water_reveal_pit": {
        "category": CreativeSolutionCategory.INFORMATION_GATHERING,
        "description": "Pouring water on floor to reveal hidden pit or trapdoor",
        "resolution": ResolutionType.AUTO_SUCCESS,
        "rule_reference": "p155 - Liquids",
    },
    "probe_with_pole": {
        "category": CreativeSolutionCategory.TRAP_BYPASS,
        "description": "Tapping ahead with a pole to trigger tripwires",
        "resolution": ResolutionType.AUTO_SUCCESS,
        "rule_reference": "p155 - Probing",
        "conditions": ["has 10' pole or similar"],
    },
    "tap_walls_hollow": {
        "category": CreativeSolutionCategory.INFORMATION_GATHERING,
        "description": "Tapping walls to find hollow sections/hidden compartments",
        "resolution": ResolutionType.CHECK_ADVANTAGE,
        "rule_reference": "p155 - Tapping",
        "check_type": CheckType.SEARCH,
    },
    "weight_trigger_trap": {
        "category": CreativeSolutionCategory.TRAP_BYPASS,
        "description": "Throwing heavy object to trigger pressure plate from safety",
        "resolution": ResolutionType.AUTO_SUCCESS,
        "rule_reference": "p155 - Weight",
        "conditions": ["has heavy object to throw"],
    },
    # From p150 example - statue as bridge
    "improvise_bridge": {
        "category": CreativeSolutionCategory.OBSTACLE_BYPASS,
        "description": "Using large object (statue, log) as bridge across chasm",
        "resolution": ResolutionType.CHECK_REQUIRED,
        "check_type": CheckType.STRENGTH,
        "time_cost": 1,  # 1 Turn to set up
    },
    "rope_and_grapple": {
        "category": CreativeSolutionCategory.OBSTACLE_BYPASS,
        "description": "Using rope and grappling hook to swing across gap",
        "resolution": ResolutionType.CHECK_REQUIRED,
        "check_type": CheckType.DEXTERITY,
        "conditions": ["has rope", "has grappling hook"],
    },
}


class CreativeSolutionResolver:
    """
    Resolves creative, non-standard solutions to problems.

    Works in two modes:
    1. LLM proposes resolution → Python validates
    2. If no match, Python offers alternatives → LLM chooses
    """

    def __init__(self):
        """Initialize the creative solution resolver."""
        self._pattern_cache = KNOWN_CREATIVE_PATTERNS.copy()

    def validate_proposed_solution(
        self, solution: CreativeSolution, character: "CharacterState", context: dict[str, Any]
    ) -> CreativeResolutionResult:
        """
        Validate a solution proposed by the LLM.

        Args:
            solution: The proposed creative solution
            character: The character attempting the solution
            context: Current game context (location, items available, etc.)

        Returns:
            CreativeResolutionResult indicating if solution is valid
        """
        # Check if solution matches a known pattern
        matched_pattern = self._match_known_pattern(solution)

        if matched_pattern:
            return self._resolve_known_pattern(matched_pattern, solution, character, context)

        # Check if proposed resolution is reasonable
        if self._is_reasonable_resolution(solution, context):
            return self._accept_proposed_resolution(solution, character, context)

        # Propose alternatives
        alternatives = self._generate_alternatives(solution, context)

        return CreativeResolutionResult(
            accepted=False,
            resolution_type=ResolutionType.UNKNOWN,
            description="Proposed resolution not validated",
            rejection_reason=self._get_rejection_reason(solution, context),
            alternatives_offered=alternatives,
            narrative_hints=["creative approach noted", "alternative methods available"],
        )

    def _match_known_pattern(self, solution: CreativeSolution) -> Optional[dict[str, Any]]:
        """Check if solution matches a known creative pattern."""
        description_lower = solution.description.lower()

        for pattern_key, pattern in self._pattern_cache.items():
            pattern_desc = pattern["description"].lower()

            # Simple keyword matching - could be enhanced with semantic search
            keywords = pattern_desc.split()
            matches = sum(1 for kw in keywords if kw in description_lower)

            if matches >= len(keywords) * 0.6:  # 60% keyword match
                return pattern

        return None

    def _resolve_known_pattern(
        self,
        pattern: dict[str, Any],
        solution: CreativeSolution,
        character: "CharacterState",
        context: dict[str, Any],
    ) -> CreativeResolutionResult:
        """Resolve using a known pattern."""
        from src.data_models import DiceRoller

        resolution = pattern.get("resolution", ResolutionType.CHECK_REQUIRED)

        # Check required conditions
        required_conditions = pattern.get("conditions", [])
        for condition in required_conditions:
            if not self._check_condition(condition, character, context):
                return CreativeResolutionResult(
                    accepted=False,
                    resolution_type=resolution,
                    description=f"Missing requirement: {condition}",
                    rejection_reason=f"Requires: {condition}",
                    alternatives_offered=[ResolutionType.CHECK_REQUIRED],
                )

        # Handle auto-success
        if resolution == ResolutionType.AUTO_SUCCESS:
            return CreativeResolutionResult(
                accepted=True,
                resolution_type=ResolutionType.AUTO_SUCCESS,
                description=f"Creative solution succeeds: {solution.description}",
                success=True,
                turns_spent=pattern.get("time_cost", 0),
                narrative_hints=[
                    "ingenuity pays off",
                    pattern.get("rule_reference", "creative approach"),
                ],
            )

        # Handle check with advantage
        if resolution == ResolutionType.CHECK_ADVANTAGE:
            check_type = pattern.get("check_type", CheckType.INTELLIGENCE)
            modifier = 2  # Advantage gives +2

            dice = DiceRoller()
            roll = dice.roll_d20(f"Creative solution: {solution.description}")
            ability_mod = self._get_ability_modifier(character, check_type)
            total = roll.total + ability_mod + modifier
            target = context.get("difficulty", 10)

            success = total >= target

            return CreativeResolutionResult(
                accepted=True,
                resolution_type=ResolutionType.CHECK_ADVANTAGE,
                description=f"Creative approach with advantage: {solution.description}",
                check_made=True,
                check_type=check_type,
                check_result=total,
                check_target=target,
                check_modifier=ability_mod + modifier,
                success=success,
                turns_spent=pattern.get("time_cost", 0),
                narrative_hints=[
                    "clever thinking" if success else "good idea, poor execution",
                    f"rolled {roll.total} + {ability_mod + modifier} = {total} vs {target}",
                ],
            )

        # Standard check required
        if resolution == ResolutionType.CHECK_REQUIRED:
            check_type = pattern.get("check_type", CheckType.INTELLIGENCE)

            dice = DiceRoller()
            roll = dice.roll_d20(f"Creative solution: {solution.description}")
            ability_mod = self._get_ability_modifier(character, check_type)
            total = roll.total + ability_mod
            target = context.get("difficulty", 10)

            success = total >= target

            return CreativeResolutionResult(
                accepted=True,
                resolution_type=ResolutionType.CHECK_REQUIRED,
                description=f"Creative approach requires check: {solution.description}",
                check_made=True,
                check_type=check_type,
                check_result=total,
                check_target=target,
                check_modifier=ability_mod,
                success=success,
                turns_spent=pattern.get("time_cost", 0),
                narrative_hints=[
                    "attempt made" if success else "didn't quite work",
                ],
            )

        # Narrative only
        return CreativeResolutionResult(
            accepted=True,
            resolution_type=ResolutionType.NARRATIVE_ONLY,
            description=solution.description,
            success=True,
            narrative_hints=["purely narrative action"],
        )

    def _is_reasonable_resolution(
        self, solution: CreativeSolution, context: dict[str, Any]
    ) -> bool:
        """Check if a proposed resolution is reasonable given context."""
        # Auto-success should be reserved for truly trivial or well-established tricks
        if solution.proposed_resolution == ResolutionType.AUTO_SUCCESS:
            # Only allow if it's clearly within adventurer competency
            # or matches a known safe pattern
            return False

        # Auto-fail should only be for truly impossible actions
        if solution.proposed_resolution == ResolutionType.AUTO_FAIL:
            return True  # Trust LLM judgment on impossibility

        # Other resolutions are generally reasonable
        return True

    def _accept_proposed_resolution(
        self, solution: CreativeSolution, character: "CharacterState", context: dict[str, Any]
    ) -> CreativeResolutionResult:
        """Accept the LLM's proposed resolution and resolve it."""
        from src.data_models import DiceRoller

        if solution.proposed_resolution in (
            ResolutionType.NARRATIVE_ONLY,
            ResolutionType.TIME_ONLY,
        ):
            return CreativeResolutionResult(
                accepted=True,
                resolution_type=solution.proposed_resolution,
                description=solution.description,
                success=True,
                turns_spent=solution.time_cost_turns,
                narrative_hints=["creative approach accepted"],
            )

        if solution.proposed_resolution == ResolutionType.AUTO_FAIL:
            return CreativeResolutionResult(
                accepted=True,
                resolution_type=ResolutionType.AUTO_FAIL,
                description=solution.description,
                success=False,
                narrative_hints=["impossible action", solution.reasoning],
            )

        # Check required
        check_type = solution.check_type or CheckType.INTELLIGENCE
        modifier = solution.check_modifier

        dice = DiceRoller()
        roll = dice.roll_d20(f"Creative: {solution.description}")
        ability_mod = self._get_ability_modifier(character, check_type)
        total = roll.total + ability_mod + modifier
        target = context.get("difficulty", 10)

        success = total >= target

        return CreativeResolutionResult(
            accepted=True,
            resolution_type=solution.proposed_resolution,
            description=solution.description,
            check_made=True,
            check_type=check_type,
            check_result=total,
            check_target=target,
            check_modifier=ability_mod + modifier,
            success=success,
            turns_spent=solution.time_cost_turns,
            narrative_hints=["creative solution attempted", "success!" if success else "not quite"],
        )

    def _generate_alternatives(
        self, solution: CreativeSolution, context: dict[str, Any]
    ) -> list[ResolutionType]:
        """Generate alternative resolution types for a rejected solution."""
        alternatives = []

        # Most creative solutions can be attempted with a check
        alternatives.append(ResolutionType.CHECK_REQUIRED)

        # If it seems clever, offer advantage
        if "clever" in solution.description.lower() or solution.category in (
            CreativeSolutionCategory.TRAP_BYPASS,
            CreativeSolutionCategory.ENVIRONMENTAL_USE,
        ):
            alternatives.append(ResolutionType.CHECK_ADVANTAGE)

        # Narrative-only is always an option
        alternatives.append(ResolutionType.NARRATIVE_ONLY)

        return alternatives

    def _get_rejection_reason(self, solution: CreativeSolution, context: dict[str, Any]) -> str:
        """Explain why a solution was not auto-validated."""
        if solution.proposed_resolution == ResolutionType.AUTO_SUCCESS:
            return (
                "Auto-success requires matching a known safe pattern or "
                "adventurer competency. A check may still be attempted."
            )

        return "Resolution type requires validation for this context."

    def _check_condition(
        self, condition: str, character: "CharacterState", context: dict[str, Any]
    ) -> bool:
        """Check if a required condition is met."""
        condition_lower = condition.lower()

        # Check for item requirements
        if "has " in condition_lower:
            item_name = condition_lower.replace("has ", "").strip()
            # Check character inventory
            for item in character.inventory:
                if item_name in item.name.lower():
                    return True
            # Check context for available items
            available_items = context.get("available_items", [])
            return any(item_name in item.lower() for item in available_items)

        # Check context flags
        if condition in context:
            return bool(context[condition])

        # Default to requiring LLM judgment
        return context.get(f"condition_{condition}", False)

    def _get_ability_modifier(self, character: "CharacterState", check_type: CheckType) -> int:
        """Get the ability modifier for a check type."""
        ability_map = {
            CheckType.STRENGTH: "STR",
            CheckType.DEXTERITY: "DEX",
            CheckType.CONSTITUTION: "CON",
            CheckType.INTELLIGENCE: "INT",
            CheckType.WISDOM: "WIS",
            CheckType.CHARISMA: "CHA",
        }

        ability = ability_map.get(check_type)
        if ability:
            return character.get_ability_modifier(ability)

        return 0

    def register_pattern(self, pattern_key: str, pattern: dict[str, Any]) -> None:
        """Register a new creative solution pattern."""
        self._pattern_cache[pattern_key] = pattern

    def get_pattern_suggestions(
        self, hazard_type: str, context: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Get suggested creative patterns for a hazard type."""
        suggestions = []

        for pattern_key, pattern in self._pattern_cache.items():
            if hazard_type.lower() in pattern.get("description", "").lower():
                suggestions.append({"key": pattern_key, **pattern})

        return suggestions
