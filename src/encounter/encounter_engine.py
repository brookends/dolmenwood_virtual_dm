"""
Encounter Engine for Dolmenwood Virtual DM.

Implements the unified Encounter Sequence from the Dolmenwood Player's Book.
This engine handles all encounters regardless of origin (wilderness, dungeon,
or settlement).

The Encounter Sequence:
1. Awareness - Check if either side is already aware of the other
2. Surprise - 2-in-6 base chance for unaware sides
3. Encounter Distance - 2d6×10' dungeon, 2d6×30' outdoors
4. Initiative - 1d6 per side, highest acts first
5. Actions - Attack, Parley, Evasion, or Waiting
6. Conclusion - One Turn passes after encounter resolves
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.data_models import (
    DiceRoller,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    ReactionResult,
    interpret_reaction,
    MovementCalculator,
)
from src.classes.ability_registry import get_ability_registry, AbilityEffectType


logger = logging.getLogger(__name__)


class EncounterPhase(str, Enum):
    """Phases of the encounter sequence."""

    AWARENESS = "awareness"
    SURPRISE = "surprise"
    DISTANCE = "distance"
    INITIATIVE = "initiative"
    ACTIONS = "actions"
    CONCLUSION = "conclusion"
    ENDED = "ended"


class EncounterOrigin(str, Enum):
    """Where the encounter originated from."""

    WILDERNESS = "wilderness"
    DUNGEON = "dungeon"
    SETTLEMENT = "settlement"
    FAIRY_ROAD = "fairy_road"


class EncounterAction(str, Enum):
    """Available actions during an encounter."""

    ATTACK = "attack"  # Initiates combat
    PARLEY = "parley"  # Attempt communication
    EVASION = "evasion"  # Attempt to flee/avoid
    WAIT = "wait"  # Hold position, observe
    ENCHANTMENT = "enchantment"  # Bard special action


@dataclass
class AwarenessResult:
    """Result of awareness check."""

    party_aware: bool
    enemies_aware: bool
    party_had_prior_knowledge: bool = False
    enemies_had_prior_knowledge: bool = False
    message: str = ""


@dataclass
class SurpriseResult:
    """Result of surprise determination."""

    surprise_status: SurpriseStatus
    party_roll: int = 0
    enemy_roll: int = 0
    party_modifier: int = 0
    enemy_modifier: int = 0
    surprise_rounds: int = 0
    message: str = ""


@dataclass
class DistanceResult:
    """Result of distance determination."""

    distance_feet: int
    base_roll: int
    multiplier: int
    is_outdoor: bool
    adjusted_for_surprise: bool = False
    message: str = ""


@dataclass
class InitiativeResult:
    """Result of initiative determination."""

    party_initiative: int
    enemy_initiative: int
    first_to_act: str  # "party", "enemy", or "simultaneous"
    message: str = ""


@dataclass
class ActionDeclaration:
    """A declared action by one side."""

    side: str  # "party" or "enemy"
    action: EncounterAction
    target: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class EncounterRoundResult:
    """Result of processing one encounter round."""

    phase: EncounterPhase
    success: bool
    actions_declared: list[ActionDeclaration] = field(default_factory=list)
    actions_resolved: list[dict[str, Any]] = field(default_factory=list)
    reaction_roll: Optional[int] = None
    reaction_result: Optional[ReactionResult] = None
    encounter_ended: bool = False
    end_reason: str = ""
    transition_to: Optional[str] = None  # State to transition to
    messages: list[str] = field(default_factory=list)


@dataclass
class EncounterEngineState:
    """Internal state of the encounter engine."""

    encounter: EncounterState
    origin: EncounterOrigin
    current_phase: EncounterPhase
    awareness: Optional[AwarenessResult] = None
    surprise: Optional[SurpriseResult] = None
    distance: Optional[DistanceResult] = None
    initiative: Optional[InitiativeResult] = None
    current_round: int = 0
    party_acted: bool = False
    enemy_acted: bool = False
    reaction_attempted: bool = False

    # POI context for dungeon/location encounters
    poi_name: Optional[str] = None
    hex_id: Optional[str] = None

    # Roll tables inherited from POI (for dungeon encounters)
    roll_tables: list = field(default_factory=list)

    # Pending time effects to apply when encounter concludes
    # Format: [{time_passes: "1d12 days", trigger: "on_exit", description: "..."}]
    pending_time_effects: list[dict[str, Any]] = field(default_factory=list)

    # Transportation effects that may trigger during encounter
    # Format: [{save_type: "Hold", destination: "Prince's Road", triggered: False}]
    pending_transportation: list[dict[str, Any]] = field(default_factory=list)


class EncounterEngine:
    """
    Unified engine for handling encounters.

    This engine implements the complete encounter sequence from the Dolmenwood
    Player's Book, handling:
    - Awareness and surprise determination
    - Encounter distance calculation
    - Initiative for action order
    - Action resolution (attack, parley, evasion, waiting)
    - Transitions to combat or social interaction

    The encounter sequence always follows this order:
    1. Awareness → 2. Surprise → 3. Distance → 4. Initiative → 5. Actions → 6. Conclusion
    """

    def __init__(self, controller: GlobalController):
        """
        Initialize the encounter engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Current encounter state
        self._state: Optional[EncounterEngineState] = None

        # Callbacks
        self._narration_callback: Optional[Callable] = None

    def register_narration_callback(self, callback: Callable) -> None:
        """Register callback for encounter narration."""
        self._narration_callback = callback

    # =========================================================================
    # ENCOUNTER INITIALIZATION
    # =========================================================================

    def start_encounter(
        self,
        encounter: EncounterState,
        origin: EncounterOrigin,
        party_aware: bool = False,
        enemies_aware: bool = False,
        roll_tables: Optional[list] = None,
        poi_name: Optional[str] = None,
        hex_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Start a new encounter.

        This initializes the encounter state and transitions the game to the
        ENCOUNTER state. The encounter will proceed through all phases in order.

        Args:
            encounter: The encounter state with actors and context
            origin: Where the encounter originated (wilderness/dungeon/settlement)
            party_aware: Whether the party was already aware of the encounter
            enemies_aware: Whether enemies were already aware of the party
            roll_tables: Optional list of RollTable objects from POI for dungeon encounters
            poi_name: Optional POI name for location context
            hex_id: Optional hex ID for location context

        Returns:
            Dictionary with encounter initialization results
        """
        # Store the encounter in the controller
        self.controller.set_encounter(encounter)

        # Initialize engine state
        self._state = EncounterEngineState(
            encounter=encounter,
            origin=origin,
            current_phase=EncounterPhase.AWARENESS,
            roll_tables=roll_tables or [],
            poi_name=poi_name,
            hex_id=hex_id,
        )

        # Transition to ENCOUNTER state
        self.controller.transition(
            "encounter_triggered",
            context={
                "origin": origin.value,
                "encounter_type": encounter.encounter_type.value,
                "poi_name": poi_name,
                "hex_id": hex_id,
            },
        )

        result: dict[str, Any] = {
            "encounter_started": True,
            "origin": origin.value,
            "encounter_type": encounter.encounter_type.value,
            "actors": encounter.actors,
            "context": encounter.context,
            "current_phase": EncounterPhase.AWARENESS.value,
            "poi_name": poi_name,
            "hex_id": hex_id,
        }

        # Log to RunLog for observability (Phase 4.1)
        try:
            from src.observability.run_log import get_run_log
            # Actors can be strings or dicts
            creature_names = [
                actor if isinstance(actor, str) else actor.get("name", actor.get("id", "unknown"))
                for actor in encounter.actors
            ]
            get_run_log().log_encounter(
                encounter_type="start",
                encounter_id=getattr(encounter, 'encounter_id', ''),
                creatures=creature_names,
                context={"origin": origin.value, "hex_id": hex_id, "poi_name": poi_name},
            )
        except ImportError:
            pass  # RunLog not available

        # Run awareness phase immediately
        awareness_result = self._resolve_awareness(party_aware, enemies_aware)
        result["awareness"] = awareness_result

        return result

    def activate_existing_encounter(
        self,
        encounter: EncounterState,
        origin: EncounterOrigin,
        context: Optional[dict[str, Any]] = None,
        party_aware: bool = False,
        enemies_aware: bool = False,
    ) -> dict[str, Any]:
        """
        Activate the encounter engine with an encounter that was already set in the controller.

        This method is called by the GlobalController's on-enter hook for ENCOUNTER state
        when the encounter was set via controller.set_encounter() but the engine wasn't
        started directly via start_encounter().

        Unlike start_encounter(), this method does NOT call controller.transition() again,
        avoiding infinite loops when the transition hook calls this method.

        Args:
            encounter: The encounter state (already stored in controller)
            origin: Where the encounter originated (wilderness/dungeon/settlement/fairy_road)
            context: Optional context from the transition
            party_aware: Whether the party was already aware of the encounter
            enemies_aware: Whether enemies were already aware of the party

        Returns:
            Dictionary with encounter activation results
        """
        context = context or {}

        # Extract optional context data
        poi_name = context.get("poi_name")
        hex_id = context.get("hex_id")
        roll_tables = context.get("roll_tables", [])

        # Initialize engine state (same as start_encounter but without the transition)
        self._state = EncounterEngineState(
            encounter=encounter,
            origin=origin,
            current_phase=EncounterPhase.AWARENESS,
            roll_tables=roll_tables,
            poi_name=poi_name,
            hex_id=hex_id,
        )

        result: dict[str, Any] = {
            "encounter_activated": True,
            "origin": origin.value,
            "encounter_type": encounter.encounter_type.value,
            "actors": encounter.actors,
            "context": encounter.context,
            "current_phase": EncounterPhase.AWARENESS.value,
            "poi_name": poi_name,
            "hex_id": hex_id,
        }

        # Run awareness phase immediately
        awareness_result = self._resolve_awareness(party_aware, enemies_aware)
        result["awareness"] = awareness_result

        logger.info(
            f"Encounter engine activated for {origin.value} encounter "
            f"with {len(encounter.actors)} actors"
        )

        return result

    # =========================================================================
    # PHASE 1: AWARENESS
    # =========================================================================

    def _resolve_awareness(
        self, party_already_aware: bool, enemies_already_aware: bool
    ) -> AwarenessResult:
        """
        Resolve the awareness phase.

        Awareness determines if either side knew about the other before the
        encounter began. This affects surprise chances.

        Args:
            party_already_aware: Whether party had prior knowledge
            enemies_already_aware: Whether enemies had prior knowledge

        Returns:
            AwarenessResult with awareness status
        """
        if not self._state:
            return AwarenessResult(
                party_aware=False, enemies_aware=False, message="No active encounter"
            )

        # If either side was already aware (scouting, tracking, etc.)
        # they cannot be surprised
        result = AwarenessResult(
            party_aware=party_already_aware,
            enemies_aware=enemies_already_aware,
            party_had_prior_knowledge=party_already_aware,
            enemies_had_prior_knowledge=enemies_already_aware,
        )

        if party_already_aware and enemies_already_aware:
            result.message = "Both sides were aware of each other"
        elif party_already_aware:
            result.message = "Party was aware of the encounter"
        elif enemies_already_aware:
            result.message = "Enemies were aware of the party"
        else:
            result.message = "Neither side was previously aware"

        self._state.awareness = result
        self._state.current_phase = EncounterPhase.SURPRISE

        return result

    # =========================================================================
    # PHASE 2: SURPRISE
    # =========================================================================

    def resolve_surprise(
        self,
        party_modifier: int = 0,
        enemy_modifier: int = 0,
    ) -> SurpriseResult:
        """
        Resolve the surprise phase.

        Each side that was not already aware rolls 1d6. On a 1-2, that side
        is surprised and cannot act for one round.

        Modifiers:
        - Cautious travel pace: +1 to surprise enemies
        - Fast travel pace: -1 to party's roll
        - Thief/Ranger abilities may modify

        Args:
            party_modifier: Modifier to party's surprise avoidance
            enemy_modifier: Modifier to enemy's surprise avoidance

        Returns:
            SurpriseResult with surprise determination
        """
        if not self._state:
            return SurpriseResult(
                surprise_status=SurpriseStatus.NO_SURPRISE, message="No active encounter"
            )

        result = SurpriseResult(
            surprise_status=SurpriseStatus.NO_SURPRISE,
            party_modifier=party_modifier,
            enemy_modifier=enemy_modifier,
        )

        # Check if either side was already aware (from awareness phase)
        party_aware = self._state.awareness.party_aware if self._state.awareness else False
        enemies_aware = self._state.awareness.enemies_aware if self._state.awareness else False

        # Roll surprise for unaware sides
        # 2-in-6 base chance to be surprised (roll 1-2)
        party_surprised = False
        enemy_surprised = False

        if not party_aware:
            party_roll = self.dice.roll_d6(1, "party surprise check")
            result.party_roll = party_roll.total + party_modifier
            party_surprised = result.party_roll <= 2
        else:
            result.party_roll = 0  # Cannot be surprised if aware

        if not enemies_aware:
            enemy_roll = self.dice.roll_d6(1, "enemy surprise check")
            result.enemy_roll = enemy_roll.total + enemy_modifier
            enemy_surprised = result.enemy_roll <= 2
        else:
            result.enemy_roll = 0  # Cannot be surprised if aware

        # Determine surprise status
        if party_surprised and enemy_surprised:
            result.surprise_status = SurpriseStatus.MUTUAL_SURPRISE
            result.surprise_rounds = 0  # Both surprised = no free actions
            result.message = "Both sides are surprised! No one acts."
        elif party_surprised:
            result.surprise_status = SurpriseStatus.PARTY_SURPRISED
            result.surprise_rounds = 1
            result.message = "Party is surprised! Enemies get a free round."
        elif enemy_surprised:
            result.surprise_status = SurpriseStatus.ENEMIES_SURPRISED
            result.surprise_rounds = 1
            result.message = "Enemies are surprised! Party gets a free round."
        else:
            result.surprise_status = SurpriseStatus.NO_SURPRISE
            result.surprise_rounds = 0
            result.message = "Neither side is surprised."

        # Update encounter state with surprise
        self._state.encounter.surprise_status = result.surprise_status
        self._state.surprise = result
        self._state.current_phase = EncounterPhase.DISTANCE

        return result

    # =========================================================================
    # PHASE 3: ENCOUNTER DISTANCE
    # =========================================================================

    def resolve_distance(self) -> DistanceResult:
        """
        Resolve the encounter distance.

        Distance is determined by:
        - Dungeon: 2d6 × 10 feet (20-120 feet)
        - Outdoors: 2d6 × 30 feet (60-360 feet, or 20-120 yards)

        If both sides are surprised (mutual surprise), multiply by 1d4
        to represent the closer encounter.

        Returns:
            DistanceResult with encounter distance
        """
        if not self._state:
            return DistanceResult(
                distance_feet=60,
                base_roll=6,
                multiplier=10,
                is_outdoor=True,
                message="No active encounter",
            )

        is_outdoor = self._state.origin == EncounterOrigin.WILDERNESS

        # Roll 2d6 for base distance
        base_roll = self.dice.roll("2d6", "encounter distance")

        # Determine multiplier based on location
        if is_outdoor:
            multiplier = 30  # 60-360 feet outdoors
        else:
            multiplier = 10  # 20-120 feet in dungeon

        distance = base_roll.total * multiplier

        result = DistanceResult(
            distance_feet=distance,
            base_roll=base_roll.total,
            multiplier=multiplier,
            is_outdoor=is_outdoor,
        )

        # If mutual surprise, roll 1d4 multiplier for closer encounter
        if (
            self._state.surprise
            and self._state.surprise.surprise_status == SurpriseStatus.MUTUAL_SURPRISE
        ):
            surprise_mult = self.dice.roll_d6(1, "surprise distance modifier")
            # Use 1-4 range (reroll 5-6)
            mult_value = min(surprise_mult.total, 4)
            result.distance_feet = distance // mult_value
            result.adjusted_for_surprise = True
            result.message = (
                f"Mutual surprise! Distance reduced to "
                f"{result.distance_feet} feet (÷{mult_value})"
            )
        else:
            result.message = f"Encounter at {distance} feet"

        # Update encounter state
        self._state.encounter.distance = result.distance_feet
        self._state.distance = result
        self._state.current_phase = EncounterPhase.INITIATIVE

        return result

    # =========================================================================
    # PHASE 4: INITIATIVE
    # =========================================================================

    def resolve_initiative(
        self,
        party_modifier: int = 0,
        enemy_modifier: int = 0,
    ) -> InitiativeResult:
        """
        Resolve initiative for the encounter.

        Each side rolls 1d6. Highest roll acts first. Ties mean simultaneous
        action declaration and resolution.

        Args:
            party_modifier: Bonus to party's initiative roll
            enemy_modifier: Bonus to enemy's initiative roll

        Returns:
            InitiativeResult with initiative order
        """
        if not self._state:
            return InitiativeResult(
                party_initiative=0,
                enemy_initiative=0,
                first_to_act="simultaneous",
                message="No active encounter",
            )

        # Roll initiative
        party_roll = self.dice.roll_d6(1, "party initiative")
        enemy_roll = self.dice.roll_d6(1, "enemy initiative")

        party_init = party_roll.total + party_modifier
        enemy_init = enemy_roll.total + enemy_modifier

        result = InitiativeResult(
            party_initiative=party_init,
            enemy_initiative=enemy_init,
            first_to_act="simultaneous",
        )

        if party_init > enemy_init:
            result.first_to_act = "party"
            result.message = f"Party wins initiative ({party_init} vs {enemy_init})"
        elif enemy_init > party_init:
            result.first_to_act = "enemy"
            result.message = f"Enemies win initiative ({enemy_init} vs {party_init})"
        else:
            result.first_to_act = "simultaneous"
            result.message = f"Tied initiative ({party_init}) - simultaneous actions"

        # Update encounter state
        self._state.encounter.party_initiative = party_init
        self._state.encounter.enemy_initiative = enemy_init
        self._state.initiative = result
        self._state.current_phase = EncounterPhase.ACTIONS

        return result

    # =========================================================================
    # PHASE 5: ACTIONS
    # =========================================================================

    def execute_action(
        self,
        action: EncounterAction,
        actor: str = "party",
        target: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> EncounterRoundResult:
        """
        Execute an encounter action.

        Available actions:
        - ATTACK: Initiates combat (transitions to COMBAT state)
        - PARLEY: Attempts communication (may transition to SOCIAL_INTERACTION)
        - EVASION: Attempts to flee/avoid the encounter
        - WAIT: Holds position, observes the situation

        Args:
            action: The action to take
            actor: "party" or "enemy"
            target: Optional target for the action
            parameters: Additional parameters

        Returns:
            EncounterRoundResult with action resolution
        """
        if not self._state:
            return EncounterRoundResult(
                phase=EncounterPhase.ACTIONS, success=False, messages=["No active encounter"]
            )

        parameters = parameters or {}
        result = EncounterRoundResult(
            phase=EncounterPhase.ACTIONS,
            success=True,
        )

        # Check if any party member can act (for party actions)
        if actor == "party":
            party_can_act = False
            party_blocked_reasons = []
            for char in self.controller.get_active_characters():
                can_act, reason = self.controller.can_character_act(char.character_id)
                if can_act:
                    party_can_act = True
                    break
                else:
                    party_blocked_reasons.append(f"{char.name}: {reason}")

            if not party_can_act and party_blocked_reasons:
                result.success = False
                result.messages.append("Party cannot act:")
                result.messages.extend(party_blocked_reasons[:3])  # Cap at 3
                return result

        declaration = ActionDeclaration(
            side=actor,
            action=action,
            target=target,
            parameters=parameters,
        )
        result.actions_declared.append(declaration)

        # Handle the action
        if action == EncounterAction.ATTACK:
            result = self._handle_attack(actor, result)
        elif action == EncounterAction.PARLEY:
            result = self._handle_parley(actor, result)
        elif action == EncounterAction.EVASION:
            result = self._handle_evasion(actor, result)
        elif action == EncounterAction.WAIT:
            result = self._handle_wait(actor, result)
        elif action == EncounterAction.ENCHANTMENT:
            result = self._handle_enchantment(actor, target, parameters, result)

        # Invoke narration callback if registered
        if self._narration_callback:
            try:
                self._narration_callback(
                    action=action.value,
                    actor=actor,
                    result={
                        "success": result.success,
                        "messages": result.messages,
                        "encounter_ended": result.encounter_ended,
                        "end_reason": result.end_reason,
                        "reaction_result": result.reaction_result.value if result.reaction_result else None,
                    },
                )
            except Exception as e:
                # Narration is advisory - don't block on failures
                pass

        return result

    def _handle_attack(self, actor: str, result: EncounterRoundResult) -> EncounterRoundResult:
        """Handle attack action - transitions to combat."""
        if not self._state:
            return result

        result.messages.append(f"{actor.capitalize()} attacks!")
        result.encounter_ended = True
        result.end_reason = "combat_initiated"
        result.transition_to = "encounter_to_combat"

        # Transition to combat
        self.controller.transition(
            "encounter_to_combat",
            context={
                "attacker": actor,
                "origin": self._state.origin.value,
            },
        )

        self._state.current_phase = EncounterPhase.ENDED

        return result

    def _handle_parley(self, actor: str, result: EncounterRoundResult) -> EncounterRoundResult:
        """Handle parley action - roll reaction and potentially transition to social."""
        if not self._state:
            return result

        result.messages.append(f"{actor.capitalize()} attempts to parley...")

        # Roll 2d6 reaction per Dolmenwood Player's Book
        reaction_roll = self.dice.roll_2d6("reaction roll")
        result.reaction_roll = reaction_roll.total

        # Interpret reaction using canonical function
        result.reaction_result = interpret_reaction(reaction_roll.total)

        # Handle reaction outcomes per official table
        if result.reaction_result == ReactionResult.ATTACKS:
            result.messages.append(f"Attacks! ({reaction_roll.total}) - They attack immediately!")
            result.encounter_ended = True
            result.end_reason = "hostile_reaction"
            result.transition_to = "encounter_to_combat"
            self.controller.transition(
                "encounter_to_combat", context={"reason": "hostile_reaction"}
            )
        elif result.reaction_result == ReactionResult.HOSTILE:
            result.messages.append(f"Hostile ({reaction_roll.total}) - They may attack")
            # May escalate or allow further parley
        elif result.reaction_result == ReactionResult.UNCERTAIN:
            result.messages.append(f"Uncertain ({reaction_roll.total}) - They are wary")
        elif result.reaction_result == ReactionResult.INDIFFERENT:
            result.messages.append(f"Indifferent ({reaction_roll.total}) - They may negotiate")
            result.encounter_ended = True
            result.end_reason = "parley_success"
            result.transition_to = "encounter_to_parley"
            self.controller.transition("encounter_to_parley", context={"reaction": "indifferent"})
        else:  # FRIENDLY (12+)
            result.messages.append(
                f"Friendly ({reaction_roll.total}) - They are eager and friendly!"
            )
            result.encounter_ended = True
            result.end_reason = "parley_success"
            result.transition_to = "encounter_to_parley"
            self.controller.transition("encounter_to_parley", context={"reaction": "friendly"})

        # Update encounter state
        self._state.encounter.reaction_result = result.reaction_result
        self._state.reaction_attempted = True

        if result.encounter_ended:
            self._state.current_phase = EncounterPhase.ENDED

        return result

    def _handle_evasion(self, actor: str, result: EncounterRoundResult) -> EncounterRoundResult:
        """
        Handle evasion action - attempt to flee the encounter.

        Per Dolmenwood rules (p146-147):
        - Evasion success depends on surprise, distance, and movement rates
        - Running speed = Speed × 3 per round
        - Faster party can evade slower enemies
        """
        if not self._state:
            return result

        result.messages.append(f"{actor.capitalize()} attempts to evade...")

        # Evasion success depends on:
        # - Surprise status (can't evade if surprised)
        # - Distance (easier at greater distance)
        # - Relative movement rates

        surprise = self._state.encounter.surprise_status

        # Can't evade if surprised
        if actor == "party" and surprise == SurpriseStatus.PARTY_SURPRISED:
            result.success = False
            result.messages.append("Cannot evade while surprised!")
            return result
        if actor == "enemy" and surprise == SurpriseStatus.ENEMIES_SURPRISED:
            result.success = False
            result.messages.append("Enemies cannot evade while surprised!")
            return result

        # Get movement rates (p146-147)
        party_speed = self.controller.get_party_movement_rate()
        party_running_speed = MovementCalculator.get_running_movement(party_speed)

        # Get enemy speed from encounter combatants (use fastest enemy)
        enemy_speed = 30  # Default fallback
        if self._state and self._state.encounter and self._state.encounter.combatants:
            enemy_speeds = [
                c.stat_block.movement
                for c in self._state.encounter.combatants
                if c.stat_block and c.stat_block.movement and c.stat_block.hp_current > 0
            ]
            if enemy_speeds:
                enemy_speed = max(enemy_speeds)
        enemy_running_speed = MovementCalculator.get_running_movement(enemy_speed)

        # Calculate evasion chance based on:
        # 1. Distance (easier at greater distance)
        # 2. Relative speed (faster party = easier evasion)
        distance = self._state.encounter.distance
        distance_mod = distance // 60  # +1 per 60 feet

        # Speed comparison modifier
        speed_diff = party_running_speed - enemy_running_speed
        speed_mod = speed_diff // 30  # +1/-1 per 30' speed difference

        # Roll d6: need 4+ to evade, modified by distance and speed
        evasion_roll = self.dice.roll_d6(1, "evasion attempt")
        base_target = 4
        target = max(1, min(6, base_target - distance_mod - speed_mod))

        result_detail = {
            "roll": evasion_roll.total,
            "target": target,
            "distance": distance,
            "distance_mod": distance_mod,
            "party_speed": party_running_speed,
            "enemy_speed": enemy_running_speed,
            "speed_mod": speed_mod,
        }

        if evasion_roll.total >= target:
            result.success = True
            result.messages.append(
                f"Evasion successful! (rolled {evasion_roll.total}, "
                f"needed {target}+, running at {party_running_speed}'/round)"
            )
            result.encounter_ended = True
            result.end_reason = "evaded"
            result.actions_resolved.append({"action": "evasion", "success": True, **result_detail})

            # Transition back to origin state
            if self._state.origin == EncounterOrigin.WILDERNESS:
                result.transition_to = "encounter_end_wilderness"
                self.controller.transition("encounter_end_wilderness")
            elif self._state.origin == EncounterOrigin.DUNGEON:
                result.transition_to = "encounter_end_dungeon"
                self.controller.transition("encounter_end_dungeon")
            elif self._state.origin == EncounterOrigin.FAIRY_ROAD:
                result.transition_to = "encounter_end_fairy_road"
                self.controller.transition("encounter_end_fairy_road")
            else:
                result.transition_to = "encounter_end_settlement"
                self.controller.transition("encounter_end_settlement")

            self._state.current_phase = EncounterPhase.ENDED
        else:
            result.success = False
            result.messages.append(
                f"Evasion failed! (rolled {evasion_roll.total}, " f"needed {target}+)"
            )
            result.actions_resolved.append({"action": "evasion", "success": False, **result_detail})
            # Other side may react

        return result

    def _handle_wait(self, actor: str, result: EncounterRoundResult) -> EncounterRoundResult:
        """Handle wait action - observe and hold position."""
        if not self._state:
            return result

        result.messages.append(f"{actor.capitalize()} waits and observes...")
        result.success = True

        # Waiting grants +1 to reaction if other side acts
        result.actions_resolved.append(
            {
                "action": "wait",
                "actor": actor,
                "effect": "reaction_bonus",
                "value": 1,
            }
        )

        return result

    def _handle_enchantment(
        self,
        actor: str,
        target: Optional[str],
        parameters: dict[str, Any],
        result: EncounterRoundResult,
    ) -> EncounterRoundResult:
        """
        Handle Bard enchantment action per Dolmenwood rules (p58-59).

        Enchantment:
        - Range: 60 feet (within hearing distance)
        - Targets: Mortals, fairies, demi-fey, and beasts
        - Effect: Charm-like (target views bard as trusted friend)
        - Duration: Until charm is broken (act against target's interests)
        - Save: Spell (target gets save to resist)
        - Uses per day: Scales with level (1 at level 1, +1 at 4, 8, 12)

        Args:
            actor: The actor (should be "party" with bard character)
            target: Target creature identifier
            parameters: Should include "bard_id" for the bard character
            result: The encounter result to update

        Returns:
            Updated EncounterRoundResult
        """
        if not self._state:
            return result

        bard_id = parameters.get("bard_id")
        if not bard_id:
            result.success = False
            result.messages.append("No bard specified for enchantment")
            return result

        # Get bard character state
        char_state = self.controller.get_character(bard_id)
        if not char_state:
            result.success = False
            result.messages.append("Bard character not found")
            return result

        if char_state.character_class.lower() != "bard":
            result.success = False
            result.messages.append("Only bards can use enchantment")
            return result

        # Get enchantment ability data from registry
        registry = get_ability_registry()
        ability = registry.get("bard_enchantment")
        if not ability:
            result.success = False
            result.messages.append("Enchantment ability not found")
            return result

        # Check uses per day
        uses_by_level = ability.extra_data.get("uses_per_day_by_level", {1: 1})
        max_uses = 1
        for level_threshold, uses in sorted(uses_by_level.items()):
            if char_state.level >= level_threshold:
                max_uses = uses

        # Check if character has uses remaining (would need state tracking)
        # For now, assume they have uses available

        # Perform the enchantment
        bard_name = char_state.name
        result.messages.append(f"{bard_name} weaves an enchanting melody...")

        # Target must save vs Spell or be charmed
        # Get target's save value (default to 15 if not specified)
        target_save = parameters.get("target_save_spell", 15)
        save_roll = self.dice.roll_d20("target saves vs Spell")

        enchantment_result = {
            "bard": bard_name,
            "bard_level": char_state.level,
            "target": target or "creatures",
            "save_roll": save_roll.total,
            "save_target": target_save,
        }

        if save_roll.total >= target_save:
            # Target resisted
            enchantment_result["resisted"] = True
            result.messages.append(
                f"Target resisted the enchantment! (Save: {save_roll.total} vs {target_save})"
            )
            result.success = False
        else:
            # Target enchanted
            enchantment_result["charmed"] = True
            enchantment_result["effect"] = "Target views bard as a trusted friend"
            result.messages.append(
                f"Target is enchanted! (Save: {save_roll.total} vs {target_save}) "
                f"They now view {bard_name} as a trusted friend."
            )
            result.success = True

            # This could transition to social interaction
            result.reaction_result = ReactionResult.FRIENDLY
            result.messages.append(
                "The enchantment has created a friendly disposition toward the bard."
            )

        result.actions_resolved.append(
            {
                "action": "enchantment",
                "actor": bard_id,
                "result": enchantment_result,
            }
        )

        return result

    # =========================================================================
    # PHASE 6: CONCLUSION
    # =========================================================================

    def conclude_encounter(self, reason: str = "resolved") -> dict[str, Any]:
        """
        Conclude the encounter.

        One turn (10 minutes) passes after encounter resolution.
        The game state returns to the origin state.

        Args:
            reason: Reason for conclusion

        Returns:
            Dictionary with conclusion details
        """
        if not self._state:
            return {"error": "No active encounter"}

        result = {
            "encounter_concluded": True,
            "reason": reason,
            "origin": self._state.origin.value,
            "turns_passed": 1,
        }

        # Log to RunLog for observability (Phase 4.1)
        try:
            from src.observability.run_log import get_run_log
            encounter = self._state.encounter
            # Actors can be strings or dicts
            creature_names = [
                actor if isinstance(actor, str) else actor.get("name", actor.get("id", "unknown"))
                for actor in encounter.actors
            ]
            get_run_log().log_encounter(
                encounter_type="resolution",
                encounter_id=getattr(encounter, 'encounter_id', ''),
                creatures=creature_names,
                outcome=reason,
                resolution_method=reason,
            )
        except ImportError:
            pass  # RunLog not available

        # Advance time by one turn
        time_result = self.controller.advance_time(1)
        result["time_result"] = time_result

        # Clear encounter
        self.controller.clear_encounter()

        # Determine return trigger
        if self._state.origin == EncounterOrigin.WILDERNESS:
            trigger = "encounter_end_wilderness"
        elif self._state.origin == EncounterOrigin.DUNGEON:
            trigger = "encounter_end_dungeon"
        elif self._state.origin == EncounterOrigin.FAIRY_ROAD:
            trigger = "encounter_end_fairy_road"
        else:
            trigger = "encounter_end_settlement"

        # Only transition if still in ENCOUNTER state
        if self.controller.current_state == GameState.ENCOUNTER:
            self.controller.transition(trigger, context=result)

        result["returned_to"] = self._state.origin.value

        # Clear engine state
        self._state = None

        return result

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_current_phase(self) -> Optional[EncounterPhase]:
        """Get the current encounter phase."""
        return self._state.current_phase if self._state else None

    def get_encounter_state(self) -> Optional[EncounterEngineState]:
        """Get the current encounter engine state."""
        return self._state

    def is_active(self) -> bool:
        """Check if an encounter is active."""
        return self._state is not None

    def get_origin(self) -> Optional[EncounterOrigin]:
        """Get the origin of the current encounter."""
        return self._state.origin if self._state else None

    def get_encounter_summary(self) -> dict[str, Any]:
        """Get summary of current encounter."""
        if not self._state:
            return {"active": False}

        return {
            "active": True,
            "origin": self._state.origin.value,
            "current_phase": self._state.current_phase.value,
            "encounter_type": self._state.encounter.encounter_type.value,
            "distance": self._state.encounter.distance,
            "surprise_status": self._state.encounter.surprise_status.value,
            "reaction": (
                self._state.encounter.reaction_result.value
                if self._state.encounter.reaction_result
                else None
            ),
            "actors": self._state.encounter.actors,
            "round": self._state.current_round,
        }

    def auto_run_phases(
        self,
        party_aware: bool = False,
        enemies_aware: bool = False,
        party_surprise_mod: int = 0,
        enemy_surprise_mod: int = 0,
        party_init_mod: int = 0,
        enemy_init_mod: int = 0,
    ) -> dict[str, Any]:
        """
        Automatically run through all pre-action phases.

        This is a convenience method that runs:
        1. Surprise resolution
        2. Distance determination
        3. Initiative resolution

        After this, the encounter is ready for action declarations.

        Args:
            party_aware: Whether party was aware beforehand
            enemies_aware: Whether enemies were aware beforehand
            party_surprise_mod: Modifier to party's surprise roll
            enemy_surprise_mod: Modifier to enemy's surprise roll
            party_init_mod: Modifier to party's initiative
            enemy_init_mod: Modifier to enemy's initiative

        Returns:
            Dictionary with all phase results
        """
        if not self._state:
            return {"error": "No active encounter"}

        result: dict[str, Any] = {}

        # Run surprise if in that phase
        if self._state.current_phase == EncounterPhase.SURPRISE:
            result["surprise"] = self.resolve_surprise(party_surprise_mod, enemy_surprise_mod)

        # Run distance if in that phase
        if self._state.current_phase == EncounterPhase.DISTANCE:
            result["distance"] = self.resolve_distance()

        # Run initiative if in that phase
        if self._state.current_phase == EncounterPhase.INITIATIVE:
            result["initiative"] = self.resolve_initiative(party_init_mod, enemy_init_mod)

        result["current_phase"] = self._state.current_phase.value
        result["ready_for_action"] = self._state.current_phase == EncounterPhase.ACTIONS

        return result

    # =========================================================================
    # ROLL TABLE OPERATIONS
    # =========================================================================

    def roll_on_table(
        self,
        table_name: str,
    ) -> Optional[dict[str, Any]]:
        """
        Roll on a roll table inherited from the POI.

        Used for dungeon encounters with room/encounter tables like
        The Spectral Manse's "Rooms" and "Encounters" tables.

        Args:
            table_name: Name of the table to roll on

        Returns:
            Dictionary with roll result or None if table not found
        """
        if not self._state or not self._state.roll_tables:
            return None

        # Find the table
        target_table = None
        for table in self._state.roll_tables:
            if table.name.lower() == table_name.lower():
                target_table = table
                break

        if not target_table:
            return None

        # Roll on the table
        die_type = target_table.die_type  # e.g., "d6", "d8"
        roll = self.dice.roll(f"1{die_type}", f"roll on {table_name}")

        # Find the entry
        entry = None
        for e in target_table.entries:
            if e.roll == roll.total:
                entry = e
                break

        if not entry:
            return {"roll": roll.total, "table": table_name, "entry": None}

        result = {
            "roll": roll.total,
            "table": table_name,
            "title": entry.title,
            "description": entry.description,
            "monsters": entry.monsters,
            "npcs": entry.npcs,
            "items": entry.items,
            "mechanical_effect": entry.mechanical_effect,
        }

        # Check for reaction conditions (alignment-based)
        if entry.reaction_conditions:
            result["reaction_conditions"] = entry.reaction_conditions

        # Check for transportation effects
        if entry.transportation_effect:
            self._state.pending_transportation.append(entry.transportation_effect)
            result["transportation_effect"] = entry.transportation_effect

        # Check for time effects
        if entry.time_effect:
            self._state.pending_time_effects.append(entry.time_effect)
            result["time_effect"] = entry.time_effect

        # Check for sub-table
        if entry.sub_table:
            result["sub_table"] = entry.sub_table
            result["sub_table_text"] = entry.sub_table

        return result

    def get_available_tables(self) -> list[str]:
        """Get names of available roll tables for this encounter."""
        if not self._state or not self._state.roll_tables:
            return []
        return [table.name for table in self._state.roll_tables]

    # =========================================================================
    # TRANSPORTATION EFFECTS
    # =========================================================================

    def resolve_transportation_save(
        self,
        character_id: str,
        save_modifier: int = 0,
    ) -> dict[str, Any]:
        """
        Resolve a transportation save for a pending transportation effect.

        Used for effects like "Save Versus Hold or be whisked away
        into the Prince's Road".

        Args:
            character_id: ID of the character making the save
            save_modifier: Modifier to the save roll

        Returns:
            Dictionary with save result and consequences
        """
        if not self._state or not self._state.pending_transportation:
            return {"error": "No pending transportation effect"}

        effect = self._state.pending_transportation[0]
        save_type = effect.get("save_type", "Hold")
        destination = effect.get("destination", "unknown location")
        failure_desc = effect.get("failure_desc", "transported away")

        # Roll save (assume base target of 14 for "vs Hold")
        roll = self.dice.roll("1d20", f"save vs {save_type}")
        target = 14 - save_modifier  # Lower target is better

        success = roll.total >= target

        result = {
            "character_id": character_id,
            "save_type": save_type,
            "roll": roll.total,
            "target": target,
            "success": success,
        }

        if success:
            result["message"] = f"Saved vs {save_type}!"
            # Remove the resolved effect
            self._state.pending_transportation.pop(0)
        else:
            result["message"] = failure_desc
            result["destination"] = destination
            result["transported"] = True
            # Character is transported - this would trigger state change
            self._state.pending_transportation.pop(0)

        return result

    # =========================================================================
    # TIME EFFECTS
    # =========================================================================

    def apply_pending_time_effects(self) -> dict[str, Any]:
        """
        Apply any pending time effects when leaving the encounter location.

        Used for effects like "Upon returning to the mortal world,
        1d12 days have passed".

        Returns:
            Dictionary with time passage results
        """
        if not self._state or not self._state.pending_time_effects:
            return {"time_passed": False, "days": 0}

        total_days = 0
        effects_applied = []

        for effect in self._state.pending_time_effects:
            time_str = effect.get("time_passes", "")
            trigger = effect.get("trigger_condition", "on_exit")

            # Only apply on_exit effects here
            if trigger == "on_exit" and time_str:
                # Parse time string (e.g., "1d12 days", "2d6 hours")
                if "day" in time_str.lower():
                    # Extract dice notation
                    import re

                    dice_match = re.match(r"(\d+d\d+)", time_str)
                    if dice_match:
                        roll = self.dice.roll(dice_match.group(1), "time dilation")
                        total_days += roll.total
                        effects_applied.append(
                            {
                                "effect": time_str,
                                "rolled": roll.total,
                                "description": effect.get("description", ""),
                            }
                        )

        # Apply time passage to the controller
        if total_days > 0:
            # Convert days to turns (6 turns per hour, 24 hours per day)
            turns = total_days * 24 * 6
            self.controller.advance_time(turns)

        # Clear applied effects
        self._state.pending_time_effects = []

        return {
            "time_passed": total_days > 0,
            "days": total_days,
            "effects": effects_applied,
        }

    def has_pending_effects(self) -> dict[str, bool]:
        """Check if there are pending effects to resolve."""
        if not self._state:
            return {"transportation": False, "time": False}

        return {
            "transportation": len(self._state.pending_transportation) > 0,
            "time": len(self._state.pending_time_effects) > 0,
        }
