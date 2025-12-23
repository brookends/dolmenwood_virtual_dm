"""
Combat Engine for Dolmenwood Virtual DM.

Implements the Combat Loop from Section 5.4 of the specification.
Handles B/X-style side-based initiative, action resolution, damage, and morale.

The combat loop per round:
1. Roll side-based initiative
2. Acting side declares actions
3. Resolve actions in order
4. Apply damage & conditions
5. Check morale (if triggered)
6. If morale breaks or enemies defeated -> Exit combat -> Return to previous state
7. Request LLM narration (attacks already resolved)
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
    Combatant,
    StatBlock,
    CombatPhase,
    SurpriseStatus,
    ActionType,
    ConditionType,
    Condition,
)


logger = logging.getLogger(__name__)


class CombatActionType(str, Enum):
    """Types of combat actions."""
    MELEE_ATTACK = "melee_attack"
    MISSILE_ATTACK = "missile_attack"
    CAST_SPELL = "cast_spell"
    USE_ITEM = "use_item"
    MOVE = "move"
    CHARGE = "charge"
    WITHDRAW = "withdraw"
    DEFEND = "defend"
    FLEE = "flee"
    PARLEY = "parley"


class MoraleCheckTrigger(str, Enum):
    """Triggers for morale checks."""
    FIRST_DEATH = "first_death"
    HALF_CASUALTIES = "half_casualties"
    LEADER_KILLED = "leader_killed"
    OVERWHELMING_MAGIC = "overwhelming_magic"
    OUTNUMBERED = "outnumbered"


@dataclass
class CombatAction:
    """A declared combat action."""
    combatant_id: str
    action_type: CombatActionType
    target_id: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackResult:
    """Result of an attack roll."""
    attacker_id: str
    defender_id: str
    attack_roll: int
    needed_to_hit: int
    hit: bool
    damage_roll: int = 0
    damage_dealt: int = 0
    critical: bool = False
    fumble: bool = False
    special_effects: list[str] = field(default_factory=list)


@dataclass
class CombatRoundResult:
    """Result of processing one combat round."""
    round_number: int
    party_initiative: int
    enemy_initiative: int
    first_side: str
    actions_resolved: list[AttackResult] = field(default_factory=list)
    morale_checks: list[dict[str, Any]] = field(default_factory=list)
    combat_ended: bool = False
    end_reason: str = ""
    casualties: list[str] = field(default_factory=list)
    fleeing: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


@dataclass
class CombatState:
    """Overall state of the current combat."""
    encounter: EncounterState
    round_number: int = 0
    party_initiative: int = 0
    enemy_initiative: int = 0
    active_side: str = ""
    actions_declared: list[CombatAction] = field(default_factory=list)
    round_results: list[CombatRoundResult] = field(default_factory=list)
    enemy_starting_count: int = 0
    enemy_casualties: int = 0
    party_casualties: int = 0


class CombatEngine:
    """
    Engine for B/X-style combat resolution.

    Manages:
    - Side-based initiative
    - Attack and damage resolution
    - Morale checks
    - Combat state transitions
    """

    def __init__(self, controller: GlobalController):
        """
        Initialize the combat engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Combat state
        self._combat_state: Optional[CombatState] = None
        self._return_state: Optional[GameState] = None

        # Callbacks
        self._narration_callback: Optional[Callable] = None

    def register_narration_callback(self, callback: Callable) -> None:
        """Register callback for combat narration."""
        self._narration_callback = callback

    # =========================================================================
    # COMBAT INITIALIZATION
    # =========================================================================

    def start_combat(
        self,
        encounter: EncounterState,
        return_state: GameState
    ) -> dict[str, Any]:
        """
        Start a new combat from an encounter.

        Args:
            encounter: The encounter state
            return_state: State to return to after combat

        Returns:
            Dictionary with combat initialization results
        """
        # Store return state
        self._return_state = return_state

        # Initialize combat state
        self._combat_state = CombatState(
            encounter=encounter,
            round_number=0,
            enemy_starting_count=len(encounter.get_enemy_combatants()),
        )

        # Handle surprise
        surprise_result = self._handle_surprise(encounter.surprise_status)

        result = {
            "combat_started": True,
            "surprise": surprise_result,
            "party_combatants": [c.name for c in encounter.get_party_combatants()],
            "enemy_combatants": [c.name for c in encounter.get_enemy_combatants()],
            "distance": encounter.distance,
        }

        return result

    def _handle_surprise(self, surprise: SurpriseStatus) -> dict[str, Any]:
        """Handle surprise at combat start."""
        result = {"surprise_status": surprise.value, "surprise_rounds": 0}

        if surprise == SurpriseStatus.PARTY_SURPRISED:
            result["surprised_side"] = "party"
            result["surprise_rounds"] = 1
            result["message"] = "Party is surprised! Enemies get a free round."
        elif surprise == SurpriseStatus.ENEMIES_SURPRISED:
            result["surprised_side"] = "enemies"
            result["surprise_rounds"] = 1
            result["message"] = "Enemies are surprised! Party gets a free round."
        elif surprise == SurpriseStatus.MUTUAL_SURPRISE:
            result["surprised_side"] = "both"
            result["message"] = "Both sides are surprised - no free rounds."
        else:
            result["message"] = "No surprise - normal combat begins."

        return result

    # =========================================================================
    # MAIN COMBAT LOOP (Section 5.4)
    # =========================================================================

    def execute_round(
        self,
        party_actions: list[CombatAction],
        enemy_actions: Optional[list[CombatAction]] = None
    ) -> CombatRoundResult:
        """
        Execute one combat round.

        Implements the Combat Loop from Section 5.4.

        Args:
            party_actions: Declared actions for party members
            enemy_actions: Declared actions for enemies (auto-generated if None)

        Returns:
            CombatRoundResult with all outcomes
        """
        if not self._combat_state:
            return CombatRoundResult(
                round_number=0,
                party_initiative=0,
                enemy_initiative=0,
                first_side="",
                messages=["No active combat"]
            )

        self._combat_state.round_number += 1
        round_num = self._combat_state.round_number

        result = CombatRoundResult(
            round_number=round_num,
            party_initiative=0,
            enemy_initiative=0,
            first_side="",
        )

        # 1. Roll initiative
        party_init = self.dice.roll_d6(1, "party initiative")
        enemy_init = self.dice.roll_d6(1, "enemy initiative")

        result.party_initiative = party_init.total
        result.enemy_initiative = enemy_init.total
        self._combat_state.party_initiative = party_init.total
        self._combat_state.enemy_initiative = enemy_init.total

        # Determine acting order
        if party_init.total > enemy_init.total:
            result.first_side = "party"
            action_order = ["party", "enemy"]
        elif enemy_init.total > party_init.total:
            result.first_side = "enemy"
            action_order = ["enemy", "party"]
        else:
            # Tie - simultaneous actions
            result.first_side = "simultaneous"
            action_order = ["simultaneous"]

        result.messages.append(
            f"Initiative: Party {party_init.total} vs Enemy {enemy_init.total}"
        )

        # 2. Generate enemy actions if not provided
        if enemy_actions is None:
            enemy_actions = self._generate_enemy_actions()

        # Store actions
        self._combat_state.actions_declared = party_actions + enemy_actions

        # 3. Resolve actions in order
        for side in action_order:
            if side == "simultaneous":
                # Resolve all actions, apply damage after
                party_results = self._resolve_side_actions(party_actions)
                enemy_results = self._resolve_side_actions(enemy_actions)
                result.actions_resolved.extend(party_results)
                result.actions_resolved.extend(enemy_results)
            elif side == "party":
                party_results = self._resolve_side_actions(party_actions)
                result.actions_resolved.extend(party_results)
                self._apply_attack_results(party_results)
            else:
                enemy_results = self._resolve_side_actions(enemy_actions)
                result.actions_resolved.extend(enemy_results)
                self._apply_attack_results(enemy_results)

        # If simultaneous, apply all damage now
        if result.first_side == "simultaneous":
            self._apply_attack_results(result.actions_resolved)

        # 4. Check for casualties
        result.casualties = self._check_casualties()
        if result.casualties:
            result.messages.append(f"Casualties: {', '.join(result.casualties)}")

        # 5. Check morale
        morale_triggers = self._check_morale_triggers()
        for trigger in morale_triggers:
            morale_result = self._roll_morale_check(trigger)
            result.morale_checks.append(morale_result)
            if morale_result.get("failed"):
                result.fleeing.extend(morale_result.get("fleeing", []))

        # 6. Check for combat end
        end_check = self._check_combat_end()
        if end_check["ended"]:
            result.combat_ended = True
            result.end_reason = end_check["reason"]
            result.messages.append(f"Combat ended: {end_check['reason']}")

        # Store round result
        self._combat_state.round_results.append(result)

        # 7. Request narration (if callback registered)
        if self._narration_callback:
            self._narration_callback(
                round_number=round_num,
                actions=result.actions_resolved,
                casualties=result.casualties,
            )

        return result

    def _resolve_side_actions(self, actions: list[CombatAction]) -> list[AttackResult]:
        """Resolve actions for one side."""
        results = []

        for action in actions:
            if action.action_type in {CombatActionType.MELEE_ATTACK, CombatActionType.MISSILE_ATTACK}:
                attack_result = self._resolve_attack(action)
                results.append(attack_result)
            elif action.action_type == CombatActionType.CAST_SPELL:
                # Spell resolution would go here
                pass
            elif action.action_type == CombatActionType.FLEE:
                # Handle flee attempt
                pass

        return results

    def _resolve_attack(self, action: CombatAction) -> AttackResult:
        """
        Resolve a single attack.

        Uses B/X attack matrix: Roll d20, compare to target AC.
        """
        attacker_id = action.combatant_id
        defender_id = action.target_id

        # Get combatants
        attacker = self._get_combatant(attacker_id)
        defender = self._get_combatant(defender_id) if defender_id else None

        if not attacker or not defender:
            return AttackResult(
                attacker_id=attacker_id,
                defender_id=defender_id or "",
                attack_roll=0,
                needed_to_hit=0,
                hit=False,
            )

        # Calculate needed roll
        attacker_thac0 = self._get_thac0(attacker)
        defender_ac = defender.stat_block.armor_class if defender.stat_block else 9

        # THAC0 - AC = needed roll
        needed_to_hit = attacker_thac0 - defender_ac

        # Roll attack
        attack_roll = self.dice.roll_d20(f"{attacker.name} attacks {defender.name}")

        # Check for hit
        hit = attack_roll.total >= needed_to_hit

        # Check for natural 20/1
        critical = attack_roll.total == 20
        fumble = attack_roll.total == 1

        result = AttackResult(
            attacker_id=attacker_id,
            defender_id=defender_id,
            attack_roll=attack_roll.total,
            needed_to_hit=needed_to_hit,
            hit=hit or critical,
            critical=critical,
            fumble=fumble,
        )

        # Roll damage if hit
        if result.hit and attacker.stat_block:
            # Get attack damage
            attack_info = attacker.stat_block.attacks[0] if attacker.stat_block.attacks else {"damage": "1d6"}
            damage_dice = attack_info.get("damage", "1d6")
            damage_roll = self.dice.roll(damage_dice, "damage")
            result.damage_roll = damage_roll.total
            result.damage_dealt = damage_roll.total

        return result

    def _apply_attack_results(self, results: list[AttackResult]) -> None:
        """Apply damage from attack results."""
        for result in results:
            if result.hit and result.damage_dealt > 0:
                # Apply damage through controller
                damage_result = self.controller.apply_damage(
                    result.defender_id,
                    result.damage_dealt,
                    "physical"
                )

                # Also update combatant in encounter
                defender = self._get_combatant(result.defender_id)
                if defender and defender.stat_block:
                    defender.stat_block.hp_current -= result.damage_dealt

    def _get_combatant(self, combatant_id: str) -> Optional[Combatant]:
        """Get a combatant by ID."""
        if not self._combat_state:
            return None

        for combatant in self._combat_state.encounter.combatants:
            if combatant.combatant_id == combatant_id:
                return combatant

        return None

    def _get_thac0(self, combatant: Combatant) -> int:
        """
        Get THAC0 (To Hit Armor Class 0) for a combatant.

        B/X uses descending AC and attack matrices.
        Normal man THAC0 = 19
        Fighter 1 THAC0 = 19
        Improves by 2 per 3 levels typically
        """
        # Would look up from class/level
        # Default to normal man THAC0
        return 19

    # =========================================================================
    # ENEMY AI
    # =========================================================================

    def _generate_enemy_actions(self) -> list[CombatAction]:
        """Generate actions for enemy combatants."""
        actions = []

        if not self._combat_state:
            return actions

        party_targets = [
            c for c in self._combat_state.encounter.get_party_combatants()
            if c.stat_block and c.stat_block.hp_current > 0
        ]

        for enemy in self._combat_state.encounter.get_active_enemies():
            if not party_targets:
                break

            # Simple AI: attack random party member in melee range
            # More sophisticated AI would consider tactics
            target = party_targets[
                self.dice.roll_d6(1, "target selection").total % len(party_targets)
            ]

            actions.append(CombatAction(
                combatant_id=enemy.combatant_id,
                action_type=CombatActionType.MELEE_ATTACK,
                target_id=target.combatant_id,
            ))

        return actions

    # =========================================================================
    # MORALE
    # =========================================================================

    def _check_morale_triggers(self) -> list[MoraleCheckTrigger]:
        """Check for morale triggers this round."""
        triggers = []

        if not self._combat_state:
            return triggers

        # First death
        if self._combat_state.enemy_casualties == 1:
            triggers.append(MoraleCheckTrigger.FIRST_DEATH)

        # Half casualties
        starting = self._combat_state.enemy_starting_count
        if starting > 0:
            casualty_ratio = self._combat_state.enemy_casualties / starting
            if casualty_ratio >= 0.5 and self._combat_state.round_number > 1:
                triggers.append(MoraleCheckTrigger.HALF_CASUALTIES)

        return triggers

    def _roll_morale_check(self, trigger: MoraleCheckTrigger) -> dict[str, Any]:
        """
        Roll morale check for enemy side.

        2d6 vs morale score. If roll > morale, enemies flee.
        """
        result = {
            "trigger": trigger.value,
            "failed": False,
            "fleeing": [],
        }

        if not self._combat_state:
            return result

        # Get average morale of remaining enemies
        enemies = self._combat_state.encounter.get_active_enemies()
        if not enemies:
            return result

        morale_scores = [
            e.stat_block.morale if e.stat_block else 7
            for e in enemies
        ]
        avg_morale = sum(morale_scores) // len(morale_scores)

        # Roll morale
        roll = self.dice.roll_2d6(f"morale check ({trigger.value})")

        if roll.total > avg_morale:
            result["failed"] = True
            result["roll"] = roll.total
            result["morale"] = avg_morale
            result["fleeing"] = [e.combatant_id for e in enemies]

        return result

    def _check_casualties(self) -> list[str]:
        """Check for new casualties this round."""
        casualties = []

        if not self._combat_state:
            return casualties

        for combatant in self._combat_state.encounter.combatants:
            if combatant.stat_block and combatant.stat_block.hp_current <= 0:
                if combatant.combatant_id not in [c for r in self._combat_state.round_results for c in r.casualties]:
                    casualties.append(combatant.name)
                    if combatant.side == "enemy":
                        self._combat_state.enemy_casualties += 1
                    else:
                        self._combat_state.party_casualties += 1

        return casualties

    # =========================================================================
    # COMBAT END
    # =========================================================================

    def _check_combat_end(self) -> dict[str, Any]:
        """Check if combat should end."""
        result = {"ended": False, "reason": ""}

        if not self._combat_state:
            return result

        active_enemies = self._combat_state.encounter.get_active_enemies()
        active_party = [
            c for c in self._combat_state.encounter.get_party_combatants()
            if c.stat_block and c.stat_block.hp_current > 0
        ]

        # All enemies defeated
        if not active_enemies:
            result["ended"] = True
            result["reason"] = "all_enemies_defeated"
            result["victor"] = "party"
            return result

        # All party defeated
        if not active_party:
            result["ended"] = True
            result["reason"] = "party_defeated"
            result["victor"] = "enemies"
            return result

        # Check for morale break (enemies fleeing)
        last_round = self._combat_state.round_results[-1] if self._combat_state.round_results else None
        if last_round and last_round.fleeing:
            # If all remaining enemies are fleeing
            fleeing_ids = set(last_round.fleeing)
            enemy_ids = {e.combatant_id for e in active_enemies}
            if enemy_ids.issubset(fleeing_ids):
                result["ended"] = True
                result["reason"] = "enemies_fled"
                result["victor"] = "party"
                return result

        return result

    def end_combat(self) -> dict[str, Any]:
        """
        End combat and transition back to appropriate state.

        Returns:
            Dictionary with combat results
        """
        if not self._combat_state:
            return {"error": "No active combat"}

        end_check = self._check_combat_end()

        result = {
            "rounds_fought": self._combat_state.round_number,
            "party_casualties": self._combat_state.party_casualties,
            "enemy_casualties": self._combat_state.enemy_casualties,
            "victor": end_check.get("victor", "unknown"),
            "reason": end_check.get("reason", "ended_manually"),
        }

        # Determine return trigger based on previous state
        if self._return_state == GameState.WILDERNESS_TRAVEL:
            trigger = "combat_end_wilderness"
        elif self._return_state == GameState.DUNGEON_EXPLORATION:
            trigger = "combat_end_dungeon"
        elif self._return_state == GameState.SETTLEMENT_EXPLORATION:
            trigger = "combat_end_settlement"
        else:
            trigger = "combat_end_wilderness"  # Default

        # Transition back
        self.controller.transition(trigger, context=result)
        self.controller.clear_encounter()

        # Clear combat state
        self._combat_state = None
        self._return_state = None

        return result

    # =========================================================================
    # SPECIAL ACTIONS
    # =========================================================================

    def attempt_flee(self, character_id: str) -> dict[str, Any]:
        """
        Attempt to flee from combat.

        Fleeing allows free attacks from enemies.
        Success based on movement rate comparison.
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        # Free attacks from engaged enemies
        free_attacks = []
        for enemy in self._combat_state.encounter.get_active_enemies():
            attack = CombatAction(
                combatant_id=enemy.combatant_id,
                action_type=CombatActionType.MELEE_ATTACK,
                target_id=character_id,
            )
            result = self._resolve_attack(attack)
            free_attacks.append(result)

        # Apply free attack damage
        self._apply_attack_results(free_attacks)

        # Roll to escape (1d6, 4+ to escape)
        escape_roll = self.dice.roll_d6(1, "escape attempt")
        escaped = escape_roll.total >= 4

        return {
            "success": escaped,
            "free_attacks": len(free_attacks),
            "damage_taken": sum(a.damage_dealt for a in free_attacks if a.hit),
            "roll": escape_roll.total,
        }

    def attempt_parley(self) -> dict[str, Any]:
        """
        Attempt to parley during combat.

        Must have not attacked this round.
        Reaction roll determines if enemies accept.
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        # Roll reaction
        roll = self.dice.roll_2d6("parley reaction")

        # -2 penalty for mid-combat parley
        adjusted = roll.total - 2

        if adjusted >= 9:
            # Enemies willing to talk
            self.controller.transition("combat_to_parley")
            return {
                "success": True,
                "roll": roll.total,
                "adjusted": adjusted,
                "message": "Enemies agree to parley",
            }
        elif adjusted >= 6:
            # Uncertain - may continue fighting
            return {
                "success": False,
                "roll": roll.total,
                "adjusted": adjusted,
                "message": "Enemies uncertain, combat may continue",
            }
        else:
            # Refuse
            return {
                "success": False,
                "roll": roll.total,
                "adjusted": adjusted,
                "message": "Enemies refuse to parley",
            }

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_combat_state(self) -> Optional[CombatState]:
        """Get current combat state."""
        return self._combat_state

    def is_in_combat(self) -> bool:
        """Check if combat is active."""
        return self._combat_state is not None

    def get_combat_summary(self) -> dict[str, Any]:
        """Get summary of current combat."""
        if not self._combat_state:
            return {"active": False}

        return {
            "active": True,
            "round": self._combat_state.round_number,
            "party_combatants": [
                {
                    "id": c.combatant_id,
                    "name": c.name,
                    "hp": c.stat_block.hp_current if c.stat_block else 0,
                }
                for c in self._combat_state.encounter.get_party_combatants()
            ],
            "enemy_combatants": [
                {
                    "id": c.combatant_id,
                    "name": c.name,
                    "hp": c.stat_block.hp_current if c.stat_block else 0,
                }
                for c in self._combat_state.encounter.get_enemy_combatants()
            ],
            "party_casualties": self._combat_state.party_casualties,
            "enemy_casualties": self._combat_state.enemy_casualties,
        }
