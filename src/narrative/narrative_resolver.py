"""
Narrative Resolver for Dolmenwood Virtual DM.

The central switchboard that translates player text input into calls for
appropriate Python modules given the narrative context and knowledge of
Dolmenwood's rules.

Architecture:
1. Intent Parser (LLM→JSON) classifies player input
2. Action Router directs to appropriate resolver
3. Mechanical Resolution (Python) determines outcomes
4. Narration Context packages results for LLM narration
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from src.data_models import CharacterState, DiceRoller
    from src.game_state.global_controller import GlobalController

from src.narrative.intent_parser import (
    ParsedIntent,
    ActionCategory,
    ActionType,
    ResolutionType,
    CheckType,
    SaveType,
    ADVENTURER_COMPETENCIES,
    is_adventurer_competency,
)
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    SpellCastResult,
    ActiveSpellEffect,
)
from src.narrative.hazard_resolver import (
    HazardResolver,
    HazardType,
    HazardResult,
    DarknessLevel,
    DivingState,
)
from src.narrative.creative_resolver import (
    CreativeSolutionResolver,
    CreativeSolution,
    CreativeResolutionResult,
    CreativeSolutionCategory,
)


logger = logging.getLogger(__name__)


@dataclass
class NarrationContext:
    """
    Context package for LLM to narrate the outcome.

    Contains all mechanical results in a format the LLM can use
    to generate appropriate narrative description.
    """

    # Action information
    action_category: ActionCategory
    action_type: ActionType
    player_input: str = ""

    # Mechanical outcome
    success: bool = True
    partial_success: bool = False
    resolution_type: ResolutionType = ResolutionType.NARRATIVE_ONLY

    # Dice results
    dice_results: list[dict[str, Any]] = field(default_factory=list)

    # State changes
    damage_dealt: dict[str, int] = field(default_factory=dict)  # target_id -> damage
    healing_done: dict[str, int] = field(default_factory=dict)
    conditions_applied: list[str] = field(default_factory=list)
    conditions_removed: list[str] = field(default_factory=list)
    effects_created: list[str] = field(default_factory=list)  # Effect descriptions
    effects_expired: list[str] = field(default_factory=list)

    # Time consumption
    turns_spent: int = 0
    rounds_spent: int = 0

    # Resource changes
    resources_consumed: dict[str, int] = field(default_factory=dict)
    resources_gained: dict[str, int] = field(default_factory=dict)

    # Narrative guidance
    narrative_hints: list[str] = field(default_factory=list)
    sensory_details: list[str] = field(default_factory=list)

    # For spell effects
    spell_info: Optional[dict[str, Any]] = None

    # Rule reference
    rule_reference: Optional[str] = None

    # Warnings/errors
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """Complete result of resolving a player action."""

    success: bool
    narration_context: NarrationContext
    parsed_intent: ParsedIntent

    # State changes to apply
    apply_damage: list[tuple[str, int]] = field(default_factory=list)  # (target_id, damage)
    apply_conditions: list[tuple[str, str]] = field(default_factory=list)  # (target_id, condition)
    create_effects: list[ActiveSpellEffect] = field(default_factory=list)
    consume_resources: dict[str, int] = field(default_factory=dict)

    # Follow-up actions
    triggers_combat: bool = False
    triggers_encounter: bool = False
    requires_follow_up: bool = False
    follow_up_prompt: Optional[str] = None

    # LLM-generated narration (if callback was set)
    narration: Optional[str] = None


class NarrativeResolver:
    """
    Central switchboard for translating player input into game mechanics.

    Coordinates between:
    - Intent parsing (LLM classification)
    - Spell resolution
    - Hazard/challenge resolution
    - Creative solution resolution
    - Effect tracking
    """

    def __init__(
        self,
        controller: Optional["GlobalController"] = None,
        spell_resolver: Optional[SpellResolver] = None,
        hazard_resolver: Optional[HazardResolver] = None,
        creative_resolver: Optional[CreativeSolutionResolver] = None,
    ):
        """
        Initialize the narrative resolver.

        Args:
            controller: Global game controller for state access
            spell_resolver: Spell resolution handler
            hazard_resolver: Hazard/challenge handler
            creative_resolver: Creative solution handler
        """
        self.controller = controller
        self.spell_resolver = spell_resolver or SpellResolver()
        self.hazard_resolver = hazard_resolver or HazardResolver()
        self.creative_resolver = creative_resolver or CreativeSolutionResolver()

        # LLM interface for intent parsing
        self._intent_parser: Optional[Callable[[str, dict], ParsedIntent]] = None

        # LLM narration callback - called after each resolution
        # Signature: (NarrationContext, character_name: str) -> Optional[str]
        self._narration_callback: Optional[Callable[[NarrationContext, str], Optional[str]]] = None

        # Active effects tracking
        self._active_effects: list[ActiveSpellEffect] = []

    def set_narration_callback(
        self, callback: Callable[[NarrationContext, str], Optional[str]]
    ) -> None:
        """
        Set the LLM narration callback for resolved actions.

        The callback receives the NarrationContext and character name,
        and should return narrative text or None.

        Args:
            callback: Function that takes (NarrationContext, character_name) and returns narrative
        """
        self._narration_callback = callback

    def set_intent_parser(self, parser: Callable[[str, dict], ParsedIntent]) -> None:
        """
        Set the LLM-based intent parser function.

        Args:
            parser: Function that takes (player_input, context) and returns ParsedIntent
        """
        self._intent_parser = parser

    def resolve_player_input(
        self,
        player_input: str,
        character: "CharacterState",
        context: Optional[dict[str, Any]] = None,
    ) -> ResolutionResult:
        """
        Resolve player text input into mechanical outcomes.

        This is the main entry point for the switchboard.

        Args:
            player_input: Raw text from player
            character: The character performing the action
            context: Additional context (location, conditions, etc.)

        Returns:
            ResolutionResult with outcomes and narration context
        """
        context = context or {}

        # Step 1: Parse intent
        parsed = self._parse_intent(player_input, context)

        # Step 2: Route to appropriate resolver
        result = self._route_action(parsed, character, context)

        # Step 3: Generate narration if callback is set
        if self._narration_callback:
            try:
                character_name = getattr(character, "name", str(character))
                narration = self._narration_callback(result.narration_context, character_name)
                result.narration = narration
            except Exception as e:
                logger.warning(f"Narration callback failed: {e}")

        return result

    def _parse_intent(self, player_input: str, context: dict[str, Any]) -> ParsedIntent:
        """
        Parse player input into structured intent.

        Uses LLM if available, otherwise falls back to pattern matching.
        """
        if self._intent_parser:
            try:
                return self._intent_parser(player_input, context)
            except Exception as e:
                logger.warning(f"Intent parser failed: {e}, falling back to pattern match")

        # Fallback: simple pattern matching
        return self._pattern_match_intent(player_input, context)

    def _pattern_match_intent(self, player_input: str, context: dict[str, Any]) -> ParsedIntent:
        """Simple pattern matching for common actions."""
        input_lower = player_input.lower()

        # Spell casting
        if any(kw in input_lower for kw in ["cast", "use spell", "invoke"]):
            return ParsedIntent(
                action_category=ActionCategory.SPELL,
                action_type=ActionType.CAST_SPELL,
                raw_input=player_input,
            )

        # Physical actions
        if "climb" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.HAZARD,
                action_type=ActionType.CLIMB,
                raw_input=player_input,
            )

        if "jump" in input_lower or "leap" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.HAZARD,
                action_type=ActionType.JUMP,
                raw_input=player_input,
            )

        if "swim" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.HAZARD,
                action_type=ActionType.SWIM,
                raw_input=player_input,
            )

        if "force" in input_lower and "door" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.HAZARD,
                action_type=ActionType.FORCE_DOOR,
                raw_input=player_input,
            )

        # Exploration
        if "search" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.EXPLORATION,
                action_type=ActionType.SEARCH,
                raw_input=player_input,
                consumes_time=True,
                time_cost_turns=1,
            )

        if "listen" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.EXPLORATION,
                action_type=ActionType.LISTEN,
                raw_input=player_input,
                consumes_time=True,
                time_cost_turns=1,
            )

        # Survival
        if "forage" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.SURVIVAL,
                action_type=ActionType.FORAGE,
                raw_input=player_input,
            )

        if "fish" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.SURVIVAL,
                action_type=ActionType.FISH,
                raw_input=player_input,
            )

        if "hunt" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.SURVIVAL,
                action_type=ActionType.HUNT,
                raw_input=player_input,
            )

        # Combat
        if "attack" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.COMBAT,
                action_type=ActionType.ATTACK,
                raw_input=player_input,
                is_combat_action=True,
            )

        if "flee" in input_lower or "run away" in input_lower:
            return ParsedIntent(
                action_category=ActionCategory.COMBAT,
                action_type=ActionType.FLEE,
                raw_input=player_input,
                is_combat_action=True,
            )

        # Default to creative/narrative
        return ParsedIntent(
            action_category=ActionCategory.CREATIVE,
            action_type=ActionType.CREATIVE_SOLUTION,
            raw_input=player_input,
            narrative_description=player_input,
        )

    def _route_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Route parsed intent to appropriate resolver."""
        # Check adventurer competency first
        if is_adventurer_competency(parsed.raw_input):
            return self._resolve_competency(parsed, character)

        # Route by category
        if parsed.action_category == ActionCategory.SPELL:
            return self._resolve_spell_action(parsed, character, context)

        if parsed.action_category == ActionCategory.HAZARD:
            return self._resolve_hazard_action(parsed, character, context)

        if parsed.action_category == ActionCategory.EXPLORATION:
            return self._resolve_exploration_action(parsed, character, context)

        if parsed.action_category == ActionCategory.SURVIVAL:
            return self._resolve_survival_action(parsed, character, context)

        if parsed.action_category == ActionCategory.COMBAT:
            return self._resolve_combat_action(parsed, character, context)

        if parsed.action_category == ActionCategory.CREATIVE:
            return self._resolve_creative_action(parsed, character, context)

        # Default to narrative
        return self._resolve_narrative_action(parsed, character, context)

    def _resolve_competency(
        self, parsed: ParsedIntent, character: "CharacterState"
    ) -> ResolutionResult:
        """Resolve an action covered by adventurer competency (no roll needed)."""
        narration = NarrationContext(
            action_category=parsed.action_category,
            action_type=parsed.action_type,
            player_input=parsed.raw_input,
            success=True,
            resolution_type=ResolutionType.AUTO_SUCCESS,
            rule_reference="p150 - Adventurer Competency",
            narrative_hints=["accomplished with practiced ease", "basic adventuring skill"],
        )

        return ResolutionResult(
            success=True,
            narration_context=narration,
            parsed_intent=parsed,
        )

    def _resolve_spell_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve spell casting."""
        # Look up spell
        spell = None
        if parsed.spell_id:
            spell = self.spell_resolver.lookup_spell(parsed.spell_id)
        elif parsed.spell_name:
            spell = self.spell_resolver.lookup_spell_by_name(parsed.spell_name)

        if not spell:
            narration = NarrationContext(
                action_category=ActionCategory.SPELL,
                action_type=ActionType.CAST_SPELL,
                player_input=parsed.raw_input,
                success=False,
                errors=[f"Unknown spell: {parsed.spell_name or parsed.spell_id}"],
            )
            return ResolutionResult(
                success=False,
                narration_context=narration,
                parsed_intent=parsed,
            )

        # Resolve the spell
        from src.data_models import DiceRoller

        result = self.spell_resolver.resolve_spell(
            caster=character,
            spell=spell,
            target_id=parsed.target_id,
            target_description=parsed.target_description,
            dice_roller=DiceRoller(),
        )

        # Build narration context
        narration = NarrationContext(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            player_input=parsed.raw_input,
            success=result.success,
            resolution_type=(
                ResolutionType.CHECK_REQUIRED
                if result.save_required
                else ResolutionType.AUTO_SUCCESS
            ),
            spell_info=result.narrative_context,
            effects_created=[result.spell_name] if result.effect_created else [],
            narrative_hints=[f"casting {result.spell_name}", result.reason],
        )

        if result.slot_consumed:
            narration.resources_consumed["spell_slot"] = result.slot_level or 0

        effects_to_create = []
        if result.effect_created:
            effects_to_create.append(result.effect_created)

        return ResolutionResult(
            success=result.success,
            narration_context=narration,
            parsed_intent=parsed,
            create_effects=effects_to_create,
        )

    def _resolve_hazard_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve physical hazard/challenge."""
        # Map action type to hazard type
        hazard_map = {
            ActionType.CLIMB: HazardType.CLIMBING,
            ActionType.JUMP: HazardType.JUMPING,
            ActionType.SWIM: HazardType.SWIMMING,
            ActionType.FORCE_DOOR: HazardType.DOOR_STUCK,
        }

        hazard_type = hazard_map.get(parsed.action_type)
        if not hazard_type:
            return self._resolve_narrative_action(parsed, character, context)

        # Resolve the hazard
        result = self.hazard_resolver.resolve_hazard(
            hazard_type=hazard_type, character=character, **context
        )

        # Build narration context
        narration = NarrationContext(
            action_category=ActionCategory.HAZARD,
            action_type=parsed.action_type,
            player_input=parsed.raw_input,
            success=result.success,
            resolution_type=(
                ResolutionType.CHECK_REQUIRED if result.check_made else ResolutionType.AUTO_SUCCESS
            ),
            turns_spent=result.turns_spent,
            narrative_hints=result.narrative_hints,
        )

        if result.check_made:
            narration.dice_results.append(
                {
                    "type": result.check_type.value if result.check_type else "unknown",
                    "result": result.check_result,
                    "target": result.check_target,
                    "modifier": result.check_modifier,
                }
            )

        apply_damage = []
        if result.damage_dealt > 0:
            narration.damage_dealt[character.character_id] = result.damage_dealt
            apply_damage.append((character.character_id, result.damage_dealt))

        apply_conditions = []
        for condition in result.conditions_applied:
            narration.conditions_applied.append(condition)
            apply_conditions.append((character.character_id, condition))

        return ResolutionResult(
            success=result.success,
            narration_context=narration,
            parsed_intent=parsed,
            apply_damage=apply_damage,
            apply_conditions=apply_conditions,
        )

    def _resolve_exploration_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve exploration action (search, listen, etc.)."""
        if parsed.action_type == ActionType.LISTEN:
            result = self.hazard_resolver.resolve_hazard(
                HazardType.DOOR_LISTEN, character, **context
            )
        elif parsed.action_type == ActionType.SEARCH:
            # Search check - would integrate with dungeon state
            from src.data_models import DiceRoller

            dice = DiceRoller()
            roll = dice.roll_d6(1, "Search check")
            success = roll.total <= context.get("search_target", 2)

            narration = NarrationContext(
                action_category=ActionCategory.EXPLORATION,
                action_type=ActionType.SEARCH,
                player_input=parsed.raw_input,
                success=success,
                resolution_type=ResolutionType.CHECK_REQUIRED,
                turns_spent=1,
                dice_results=[{"type": "search", "result": roll.total}],
                narrative_hints=[
                    "carefully examining the area",
                    "found something!" if success else "nothing discovered",
                ],
                rule_reference="p152 - Hidden Features",
            )

            return ResolutionResult(
                success=success,
                narration_context=narration,
                parsed_intent=parsed,
            )
        else:
            return self._resolve_narrative_action(parsed, character, context)

        # Build narration from hazard result
        narration = NarrationContext(
            action_category=ActionCategory.EXPLORATION,
            action_type=parsed.action_type,
            player_input=parsed.raw_input,
            success=result.success,
            turns_spent=result.turns_spent,
            narrative_hints=result.narrative_hints,
        )

        return ResolutionResult(
            success=result.success,
            narration_context=narration,
            parsed_intent=parsed,
        )

    def _resolve_survival_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve survival action (forage, fish, hunt)."""
        method_map = {
            ActionType.FORAGE: "foraging",
            ActionType.FISH: "fishing",
            ActionType.HUNT: "hunting",
        }

        method = method_map.get(parsed.action_type, "foraging")

        # Get active unseason from context (if available)
        active_unseason = context.get("active_unseason")

        # If controller is available, get unseason state from world state
        if self.controller and not active_unseason:
            world_state = getattr(self.controller, "world_state", None)
            if world_state:
                active_unseason = getattr(world_state, "active_unseason", None)

        result = self.hazard_resolver.resolve_foraging(
            character=character,
            method=method,
            season=context.get("season", "normal"),
            full_day=context.get("full_day", False),
            active_unseason=active_unseason,
            **context,
        )

        narration = NarrationContext(
            action_category=ActionCategory.SURVIVAL,
            action_type=parsed.action_type,
            player_input=parsed.raw_input,
            success=result.success,
            resolution_type=ResolutionType.CHECK_REQUIRED,
            narrative_hints=result.narrative_hints,
            rule_reference="p152 - Finding Food in the Wild",
        )

        # Add Colliggwyld narrative hints if active
        if active_unseason == "colliggwyld":
            narration.narrative_hints.append(
                "Giant fungi bloom throughout the wood during Colliggwyld"
            )

        if result.success and "rations" in result.description:
            # Extract ration count from description
            import re

            match = re.search(r"(\d+) rations", result.description)
            if match:
                narration.resources_gained["rations"] = int(match.group(1))

        return ResolutionResult(
            success=result.success,
            narration_context=narration,
            parsed_intent=parsed,
            triggers_combat=parsed.action_type == ActionType.HUNT and result.success,
        )

    def _resolve_combat_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve combat-related action (should mostly go to combat engine)."""
        narration = NarrationContext(
            action_category=ActionCategory.COMBAT,
            action_type=parsed.action_type,
            player_input=parsed.raw_input,
            success=True,
            narrative_hints=["combat action - defer to combat engine"],
        )

        return ResolutionResult(
            success=True,
            narration_context=narration,
            parsed_intent=parsed,
            triggers_combat=True,
        )

    def _resolve_creative_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve creative/narrative solution."""
        # Build creative solution from parsed intent
        solution = CreativeSolution(
            category=CreativeSolutionCategory.UNKNOWN,
            description=parsed.narrative_description or parsed.raw_input,
            proposed_resolution=parsed.suggested_resolution,
            check_type=parsed.suggested_check if parsed.suggested_check != CheckType.NONE else None,
            check_modifier=parsed.check_modifier,
            time_cost_turns=parsed.time_cost_turns,
            rule_reference=parsed.applicable_rule,
        )

        # Validate and resolve
        result = self.creative_resolver.validate_proposed_solution(
            solution=solution, character=character, context=context
        )

        narration = NarrationContext(
            action_category=ActionCategory.CREATIVE,
            action_type=ActionType.CREATIVE_SOLUTION,
            player_input=parsed.raw_input,
            success=result.success,
            resolution_type=result.resolution_type,
            turns_spent=result.turns_spent,
            narrative_hints=result.narrative_hints,
        )

        if result.check_made:
            narration.dice_results.append(
                {
                    "type": result.check_type.value if result.check_type else "creative",
                    "result": result.check_result,
                    "target": result.check_target,
                    "modifier": result.check_modifier,
                }
            )

        if not result.accepted:
            narration.warnings.append(result.rejection_reason or "Solution requires validation")
            narration.narrative_hints.append(
                f"Alternatives: {', '.join(r.value for r in result.alternatives_offered)}"
            )

        return ResolutionResult(
            success=result.success,
            narration_context=narration,
            parsed_intent=parsed,
            requires_follow_up=not result.accepted,
            follow_up_prompt=result.rejection_reason,
        )

    def _resolve_narrative_action(
        self, parsed: ParsedIntent, character: "CharacterState", context: dict[str, Any]
    ) -> ResolutionResult:
        """Resolve pure narrative action (no mechanics)."""
        narration = NarrationContext(
            action_category=parsed.action_category,
            action_type=parsed.action_type,
            player_input=parsed.raw_input,
            success=True,
            resolution_type=ResolutionType.NARRATIVE_ONLY,
            narrative_hints=["narrative action", "describe freely"],
        )

        return ResolutionResult(
            success=True,
            narration_context=narration,
            parsed_intent=parsed,
        )

    # Effect management methods

    def tick_effects(self, time_unit: str = "turns") -> list[ActiveSpellEffect]:
        """
        Advance time for all active effects.

        Args:
            time_unit: "rounds" or "turns"

        Returns:
            List of effects that expired
        """
        return self.spell_resolver.tick_effects(time_unit)

    def break_concentration(self, caster_id: str) -> list[ActiveSpellEffect]:
        """
        Break concentration for a caster (called when they take damage).

        Args:
            caster_id: The caster whose concentration breaks

        Returns:
            List of effects that were broken
        """
        return self.spell_resolver.break_concentration(caster_id)

    def get_active_effects(self, entity_id: str) -> list[ActiveSpellEffect]:
        """Get all active effects on an entity."""
        return self.spell_resolver.get_active_effects(entity_id)

    def dismiss_effect(self, effect_id: str) -> Optional[ActiveSpellEffect]:
        """Dismiss an active effect."""
        return self.spell_resolver.dismiss_effect(effect_id)
