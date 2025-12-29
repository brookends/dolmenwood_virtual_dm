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
    MovementCalculator,
    RunningState,
    MAX_RUNNING_ROUNDS,
    RUNNING_REST_TURNS,
    CharacterState,
)
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    SpellCastResult,
    ActiveSpellEffect,
    DurationType,
)
from src.classes.ability_registry import (
    AbilityRegistry,
    AbilityEffectType,
    get_ability_registry,
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
    BACKSTAB = "backstab"         # Thief special attack
    TURN_UNDEAD = "turn_undead"   # Cleric/Friar special action


class MoraleCheckTrigger(str, Enum):
    """Triggers for morale checks."""
    FIRST_DEATH = "first_death"
    HALF_CASUALTIES = "half_casualties"
    LEADER_KILLED = "leader_killed"
    OVERWHELMING_MAGIC = "overwhelming_magic"
    OUTNUMBERED = "outnumbered"
    # Dolmenwood solo creature triggers (p167)
    SOLO_FIRST_HARMED = "solo_first_harmed"
    SOLO_QUARTER_HP = "solo_quarter_hp"


class MissileRange(str, Enum):
    """Missile attack range bands (p167)."""
    SHORT = "short"   # +1 Attack
    MEDIUM = "medium"  # No modifier
    LONG = "long"     # -1 Attack


class CoverType(str, Enum):
    """Cover levels affecting missile attacks (p167)."""
    NONE = "none"         # No penalty
    QUARTER = "quarter"   # -1 Attack
    HALF = "half"         # -2 Attack
    THREE_QUARTER = "three_quarter"  # -3 Attack
    FULL = "full"         # -4 Attack (or cannot target)


@dataclass
class CombatAction:
    """A declared combat action."""
    combatant_id: str
    action_type: CombatActionType
    target_id: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class CombatantStatus:
    """
    Per-combatant status tracking for Dolmenwood combat rules.

    Tracks morale successes (two = fight to death), fleeing/parrying/charging
    flags, non-lethal damage, and running exhaustion (p147, p167).
    """
    combatant_id: str
    # Morale tracking (p167)
    successful_morale_checks: int = 0  # Two successes = fight to death
    is_fleeing: bool = False
    # Declaration tracking
    is_parrying: bool = False
    is_charging: bool = False
    declared_spell: bool = False
    # Damage tracking
    took_damage_this_round: bool = False
    first_harmed: bool = False  # For solo creature morale
    non_lethal_damage: int = 0  # Non-lethal damage tracked separately (p169)
    # Running exhaustion tracking (p147)
    running_state: RunningState = field(default_factory=RunningState)


@dataclass
class AttackModifierResult:
    """
    Calculated attack modifiers for a single attack (p167).

    Combines STR/DEX modifiers, range, cover, and situational bonuses.
    """
    attack_bonus: int = 0  # Total attack roll modifier
    damage_bonus: int = 0  # Total damage modifier (STR for melee only)
    details: list[str] = field(default_factory=list)  # Description of modifiers


@dataclass
class AttackResult:
    """Result of an action resolved during combat."""
    attacker_id: str
    defender_id: str
    action_type: CombatActionType
    attack_roll: int = 0
    needed_to_hit: int = 0
    hit: bool = False
    damage_roll: int = 0
    damage_dealt: int = 0
    critical: bool = False
    fumble: bool = False
    disrupted: bool = False  # For spells/runes disrupted before acting
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
    # Dolmenwood per-combatant status tracking
    combatant_status: dict[str, CombatantStatus] = field(default_factory=dict)
    # Solo creature tracking (p167) - only one enemy at start
    is_solo_creature: bool = False


class CombatEngine:
    """
    Engine for B/X-style combat resolution.

    Manages:
    - Side-based initiative
    - Attack and damage resolution
    - Morale checks
    - Combat state transitions
    """

    def __init__(
        self,
        controller: GlobalController,
        spell_resolver: Optional[SpellResolver] = None
    ):
        """
        Initialize the combat engine.

        Args:
            controller: The global game controller
            spell_resolver: Optional spell resolver for combat spell casting
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Spell resolution for combat casting
        self.spell_resolver = spell_resolver or SpellResolver()

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
        enemy_count = len(encounter.get_enemy_combatants())
        self._combat_state = CombatState(
            encounter=encounter,
            round_number=0,
            enemy_starting_count=enemy_count,
            is_solo_creature=(enemy_count == 1),  # Solo creature morale rules (p167)
        )

        # Initialize per-combatant status tracking
        for combatant in encounter.combatants:
            self._combat_state.combatant_status[combatant.combatant_id] = CombatantStatus(
                combatant_id=combatant.combatant_id
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

        # Build declaration map (spells/runes/charge/flee/parry) for rule enforcement
        declarations = self._collect_declarations(party_actions + enemy_actions)
        self._combat_state.actions_declared = party_actions + enemy_actions
        round_modifiers = self._init_round_modifiers()
        self._apply_declared_modifiers(
            party_actions + enemy_actions,
            round_modifiers,
        )

        # 3. Resolve actions in order
        damaged_so_far: set[str] = set()

        for side in action_order:
            if side == "simultaneous":
                # Resolve all actions, apply damage after
                party_results, party_damage = self._resolve_side_actions(
                    party_actions,
                    round_modifiers,
                    damaged_prior=damaged_so_far,
                    losing_side=False,
                    declarations=declarations,
                )
                enemy_results, enemy_damage = self._resolve_side_actions(
                    enemy_actions,
                    round_modifiers,
                    damaged_prior=damaged_so_far,
                    losing_side=False,
                    declarations=declarations,
                )
                result.actions_resolved.extend(party_results)
                result.actions_resolved.extend(enemy_results)
            elif side == "party":
                losing = result.first_side != "party"
                party_results, party_damage = self._resolve_side_actions(
                    party_actions,
                    round_modifiers,
                    damaged_prior=damaged_so_far,
                    losing_side=losing,
                    declarations=declarations,
                )
                result.actions_resolved.extend(party_results)
                damaged_so_far.update(party_damage)
            else:
                losing = result.first_side != "enemy"
                enemy_results, enemy_damage = self._resolve_side_actions(
                    enemy_actions,
                    round_modifiers,
                    damaged_prior=damaged_so_far,
                    losing_side=losing,
                    declarations=declarations,
                )
                result.actions_resolved.extend(enemy_results)
                damaged_so_far.update(enemy_damage)

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

    def _resolve_side_actions(
        self,
        actions: list[CombatAction],
        round_modifiers: dict[str, Any],
        damaged_prior: set[str],
        losing_side: bool,
        declarations: dict[str, set[str]],
    ) -> tuple[list[AttackResult], set[str]]:
        """
        Resolve actions for one side following Dolmenwood sequencing.

        Movement -> missile -> magic -> melee.
        """
        results: list[AttackResult] = []
        damaged_this_resolution: set[str] = set()

        movement_actions = [
            a for a in actions if a.action_type in {
                CombatActionType.MOVE, CombatActionType.CHARGE,
                CombatActionType.WITHDRAW, CombatActionType.FLEE
            }
        ]
        missile_actions = [
            a for a in actions if a.action_type == CombatActionType.MISSILE_ATTACK
        ]
        magic_actions = [
            a for a in actions if a.action_type == CombatActionType.CAST_SPELL
        ]
        melee_actions = [
            a for a in actions if a.action_type in {
                CombatActionType.MELEE_ATTACK, CombatActionType.DEFEND
            }
        ]

        # Movement phase (apply round modifiers like charge/flee/parry)
        for action in movement_actions:
            self._apply_movement_modifiers(action, round_modifiers)

        # Missile phase
        missile_results = [
            self._resolve_attack(action, round_modifiers)
            for action in missile_actions
        ]
        damaged_this_resolution.update(self._apply_attack_results(missile_results))
        results.extend(missile_results)

        # Magic phase (can be disrupted if harmed before acting and lost init)
        for action in magic_actions:
            disrupted = losing_side and action.combatant_id in damaged_prior
            spell_result = self._resolve_spell_action(action, disrupted)
            results.append(spell_result)
        # Magic does not deal damage directly in this simplified engine

        # Melee/defend phase
        melee_results = []
        for action in melee_actions:
            if action.action_type == CombatActionType.DEFEND:
                self._apply_parry_modifiers(action, round_modifiers)
                continue
            melee_results.append(self._resolve_attack(action, round_modifiers, declarations))

        damaged_this_resolution.update(self._apply_attack_results(melee_results))
        results.extend(melee_results)

        return results, damaged_this_resolution

    def _calculate_attack_modifiers(
        self,
        attacker: Combatant,
        defender: Combatant,
        action: CombatAction,
        round_modifiers: dict[str, Any],
    ) -> AttackModifierResult:
        """
        Calculate all attack modifiers per Dolmenwood rules (p167).

        - Melee: +STR to attack and damage
        - Missile: +DEX to attack only (NOT damage)
        - Range: +1 short, 0 medium, -1 long
        - Cover: -1 to -4 based on cover level
        - Charging: +2 attack (already in round_modifiers)
        - Fleeing target: +2 attack, ignore shield (p167)
        - Class abilities: Slayer, Weapon Specialist, Order bonuses, etc.
        """
        result = AttackModifierResult()

        if not attacker.stat_block:
            return result

        is_melee = action.action_type == CombatActionType.MELEE_ATTACK
        is_missile = action.action_type == CombatActionType.MISSILE_ATTACK

        # STR modifier for melee attacks (attack and damage)
        if is_melee:
            str_mod = attacker.stat_block.strength_mod
            if str_mod != 0:
                result.attack_bonus += str_mod
                result.damage_bonus += str_mod
                result.details.append(f"STR {'+' if str_mod > 0 else ''}{str_mod}")

        # DEX modifier for missile attacks (attack only, NOT damage)
        if is_missile:
            dex_mod = attacker.stat_block.dexterity_mod
            if dex_mod != 0:
                result.attack_bonus += dex_mod
                result.details.append(f"DEX {'+' if dex_mod > 0 else ''}{dex_mod}")

            # Range modifiers
            range_band = action.parameters.get("range", MissileRange.MEDIUM)
            if isinstance(range_band, str):
                range_band = MissileRange(range_band) if range_band in [r.value for r in MissileRange] else MissileRange.MEDIUM
            if range_band == MissileRange.SHORT:
                result.attack_bonus += 1
                result.details.append("Short range +1")
            elif range_band == MissileRange.LONG:
                result.attack_bonus -= 1
                result.details.append("Long range -1")

            # Cover modifiers
            cover = action.parameters.get("cover", CoverType.NONE)
            if isinstance(cover, str):
                cover = CoverType(cover) if cover in [c.value for c in CoverType] else CoverType.NONE
            cover_penalties = {
                CoverType.QUARTER: -1,
                CoverType.HALF: -2,
                CoverType.THREE_QUARTER: -3,
                CoverType.FULL: -4,
            }
            if cover in cover_penalties:
                penalty = cover_penalties[cover]
                result.attack_bonus += penalty
                result.details.append(f"Cover {penalty}")

        # Class ability modifiers
        class_mods = self._get_class_ability_combat_modifiers(
            attacker, defender, action
        )
        result.attack_bonus += class_mods.get("attack_bonus", 0)
        result.damage_bonus += class_mods.get("damage_bonus", 0)
        result.details.extend(class_mods.get("details", []))

        return result

    def _get_class_ability_combat_modifiers(
        self,
        attacker: Combatant,
        defender: Combatant,
        action: CombatAction,
    ) -> dict[str, Any]:
        """
        Get combat modifiers from class abilities.

        Handles:
        - Fighter combat talents (Slayer, Weapon Specialist, Battle Rage)
        - Knight combat prowess and mounted charge
        - Cleric Order of St Signis (+1 vs undead)
        - Hunter trophy bonuses
        """
        result = {
            "attack_bonus": 0,
            "damage_bonus": 0,
            "damage_dice": None,
            "details": [],
        }

        # Only party members have CharacterState with class abilities
        if attacker.side != "party":
            return result

        # Get CharacterState from controller
        char_state = self.controller.get_character(attacker.combatant_id)
        if not char_state:
            return result

        # Build context for ability registry lookup
        context = {
            "target_type": self._get_creature_type(defender),
            "position": action.parameters.get("position"),
            "target_aware": action.parameters.get("target_aware", True),
            "weapon": action.parameters.get("weapon", ""),
            "is_mounted": action.parameters.get("is_mounted", False),
            "talents": char_state.get_combat_talents() if hasattr(char_state, "get_combat_talents") else [],
        }

        # Query ability registry for combat modifiers
        registry = get_ability_registry()
        class_mods = registry.get_combat_modifiers(char_state, context)

        result["attack_bonus"] = class_mods.get("attack_bonus", 0)
        result["damage_bonus"] = class_mods.get("damage_bonus", 0)
        result["damage_dice"] = class_mods.get("damage_dice")

        # Add details for each applied ability
        for effect in class_mods.get("special_effects", []):
            if effect.get("attack_bonus") or effect.get("damage_bonus"):
                ability_id = effect.get("ability_id", "unknown")
                bonus_parts = []
                if effect.get("attack_bonus"):
                    bonus_parts.append(f"+{effect['attack_bonus']} Atk")
                if effect.get("damage_bonus"):
                    bonus_parts.append(f"+{effect['damage_bonus']} Dmg")
                result["details"].append(f"{ability_id}: {', '.join(bonus_parts)}")

        return result

    def _get_creature_type(self, combatant: Combatant) -> Optional[str]:
        """Get the creature type of a combatant for ability targeting."""
        if not combatant.stat_block:
            return None

        # Check for creature type in stat block
        creature_type = getattr(combatant.stat_block, "creature_type", None)
        if creature_type:
            return creature_type.lower()

        # Check for undead tag
        tags = getattr(combatant.stat_block, "tags", [])
        if "undead" in [t.lower() for t in tags]:
            return "undead"

        return None

    def _get_effective_ac(
        self,
        defender: Combatant,
        attacker: Combatant,
        round_modifiers: dict[str, Any],
    ) -> int:
        """
        Calculate effective AC considering shields, parrying, fleeing, and class abilities.

        - Fleeing targets: ignore shield bonus
        - Parrying: +parry bonus to AC
        - Rear attacks: ignore shield bonus
        - Friar Unarmoured Defence: AC 13 when not wearing armor
        - Main Gauche: +1 AC choice per round
        """
        if not defender.stat_block:
            return 10

        base_ac = defender.stat_block.armor_class
        defender_id = defender.combatant_id

        # Apply AC bonuses (parrying)
        base_ac += round_modifiers["ac_bonus"].get(defender_id, 0)

        # Apply AC penalties (charging)
        base_ac -= round_modifiers["ac_penalty"].get(defender_id, 0)

        # Fleeing targets lose shield bonus (p167)
        if defender_id in round_modifiers["fleeing"]:
            shield_bonus = defender.stat_block.shield_bonus
            base_ac -= shield_bonus  # Remove shield from AC

        # Rear attacks also ignore shield (p167) - check parameter
        # (This would be set in action.parameters if attacking from rear)

        # Class ability AC modifiers (for party members)
        if defender.side == "party":
            class_ac_mod = self._get_class_ability_ac_modifier(defender)
            base_ac += class_ac_mod

        return base_ac

    def _get_class_ability_ac_modifier(self, combatant: Combatant) -> int:
        """
        Get AC modifier from class abilities.

        Handles:
        - Friar Unarmoured Defence (base AC 13 when unarmored)
        - Main Gauche (if selected for AC)
        """
        char_state = self.controller.get_character(combatant.combatant_id)
        if not char_state:
            return 0

        registry = get_ability_registry()
        abilities = registry.get_by_class(char_state.character_class)

        total_modifier = 0

        for ability in abilities:
            if AbilityEffectType.COMBAT_AC not in ability.effect_types:
                continue

            # Friar Unarmoured Defence
            if ability.ability_id == "friar_unarmoured_defence":
                # Check if character is wearing armor
                armor_weight = getattr(char_state, "armor_weight", None)
                if armor_weight and str(armor_weight) == "ArmorWeight.UNARMOURED":
                    # The base AC should already be 13 from character creation,
                    # but we can add the modifier if stat_block AC is lower
                    stat_ac = combatant.stat_block.armor_class if combatant.stat_block else 10
                    if stat_ac < 13:
                        total_modifier += (13 - stat_ac)

        return total_modifier

    def _resolve_attack(
        self,
        action: CombatAction,
        round_modifiers: Optional[dict[str, Any]] = None,
        declarations: Optional[dict[str, set[str]]] = None,
    ) -> AttackResult:
        """
        Resolve a single attack using Dolmenwood rules (p167-169).

        Uses ascending AC: d20 + attack bonus vs AC.
        Includes STR/DEX modifiers, range, cover, and situational bonuses.
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
                action_type=action.action_type,
            )

        round_modifiers = round_modifiers or self._init_round_modifiers()
        declarations = declarations or {}

        # Calculate effective defender AC (handles shield, parrying, fleeing)
        defender_ac = self._get_effective_ac(defender, attacker, round_modifiers)

        # Calculate attack modifiers (STR/DEX, range, cover)
        modifiers = self._calculate_attack_modifiers(
            attacker, defender, action, round_modifiers
        )

        # Roll attack
        attack_roll = self.dice.roll_d20(f"{attacker.name} attacks {defender.name}")

        # Base attack bonus from stat block
        attack_bonus = 0
        if attacker.stat_block and attacker.stat_block.attacks:
            attack_bonus = attacker.stat_block.attacks[0].get("bonus", 0)

        # Add calculated modifiers
        attack_bonus += modifiers.attack_bonus

        # Add round modifiers (charging bonus)
        attack_bonus += round_modifiers["attack_bonus"].get(attacker_id, 0)

        # Fleeing targets grant +2 to attacks against them (p167)
        if defender_id in round_modifiers["fleeing"]:
            attack_bonus += 2
            modifiers.details.append("Fleeing target +2")

        # Check for hit
        total_attack = attack_roll.total + attack_bonus
        hit = total_attack >= defender_ac

        # Check for natural 20/1
        critical = attack_roll.total == 20
        fumble = attack_roll.total == 1

        result = AttackResult(
            attacker_id=attacker_id,
            defender_id=defender_id,
            action_type=action.action_type,
            attack_roll=total_attack,
            needed_to_hit=defender_ac,
            hit=hit or critical,
            critical=critical,
            fumble=fumble,
            special_effects=modifiers.details.copy(),
        )

        # Roll damage if hit
        if result.hit and attacker.stat_block:
            # Handle unarmed attacks (p169) - 1d2 + STR
            is_unarmed = action.parameters.get("unarmed", False)
            if is_unarmed:
                damage_roll = self.dice.roll("1d2", "unarmed damage")
                result.damage_roll = damage_roll.total
                result.damage_dealt = max(1, damage_roll.total + modifiers.damage_bonus)
                result.special_effects.append("Unarmed (1d2)")
            else:
                # Get attack damage from stat block
                attack_info = attacker.stat_block.attacks[0] if attacker.stat_block.attacks else {"damage": "1d6"}
                damage_dice = attack_info.get("damage", "1d6")
                damage_roll = self.dice.roll(damage_dice, "damage")
                result.damage_roll = damage_roll.total
                # Add STR modifier to melee damage (p167)
                result.damage_dealt = max(1, damage_roll.total + modifiers.damage_bonus)

            # Handle charging with braced weapon (p168)
            # If defender has braced weapon and attacker is charging, double damage to charger
            if attacker_id in round_modifiers.get("charging_combatants", set()):
                defender_braced = action.parameters.get("defender_braced", False)
                if defender_braced:
                    result.damage_dealt *= 2
                    result.special_effects.append("Braced weapon vs charge (2x damage)")

            # Track non-lethal damage separately if specified (p169)
            if action.parameters.get("non_lethal", False):
                result.special_effects.append("Non-lethal")

        return result

    def _resolve_spell_action(self, action: CombatAction, disrupted: bool) -> AttackResult:
        """
        Resolve spell or rune usage with disruption handling.

        Integrates with SpellResolver for actual spell mechanics:
        - Spell lookup and validation
        - Slot consumption
        - Effect application
        - Concentration management

        Per Dolmenwood rules (p167), spells are disrupted if the caster:
        - Takes damage before acting AND
        - Lost initiative
        """
        caster_id = action.combatant_id
        target_id = action.target_id or ""

        # Handle disruption first
        if disrupted:
            return AttackResult(
                attacker_id=caster_id,
                defender_id=target_id,
                action_type=CombatActionType.CAST_SPELL,
                hit=False,
                disrupted=True,
                special_effects=["spell_disrupted", "took damage before acting"],
            )

        # Get spell info from action parameters
        spell_id = action.parameters.get("spell_id")
        spell_name = action.parameters.get("spell_name")

        # Look up the spell
        spell: Optional[SpellData] = None
        if spell_id:
            spell = self.spell_resolver.lookup_spell(spell_id)
        elif spell_name:
            spell = self.spell_resolver.lookup_spell_by_name(spell_name)

        if not spell:
            return AttackResult(
                attacker_id=caster_id,
                defender_id=target_id,
                action_type=CombatActionType.CAST_SPELL,
                hit=False,
                special_effects=[f"unknown spell: {spell_name or spell_id}"],
            )

        # Get caster character state
        caster = self._get_combatant(caster_id)
        caster_state: Optional[CharacterState] = None

        # Try to get CharacterState from controller for party members
        if caster and caster.side == "party":
            caster_state = self.controller.get_character(caster_id)

        if not caster_state:
            # Create minimal CharacterState for spell casting validation
            # This handles NPC/monster spellcasters
            return AttackResult(
                attacker_id=caster_id,
                defender_id=target_id,
                action_type=CombatActionType.CAST_SPELL,
                hit=True,  # NPC/monster spells generally succeed
                special_effects=[f"cast {spell.name}", "NPC/monster spellcaster"],
            )

        # Resolve the spell through SpellResolver
        target_desc = action.parameters.get("target_description")
        result = self.spell_resolver.resolve_spell(
            caster=caster_state,
            spell=spell,
            target_id=target_id if target_id else None,
            target_description=target_desc,
            dice_roller=self.dice,
        )

        # Build attack result with spell outcomes
        special_effects = []

        if result.success:
            special_effects.append(f"cast {spell.name}")

            if result.slot_consumed:
                special_effects.append(f"used level {result.slot_level} slot")

            if result.effect_created:
                special_effects.append(f"effect: {result.effect_created.duration_type.value}")
                if result.effect_created.requires_concentration:
                    special_effects.append("concentration required")

            if result.save_required:
                special_effects.append(f"save required: {result.save_result}")

            # Handle damage spells
            if result.damage_dealt:
                damage_total = result.damage_dealt.get("total", 0)
                return AttackResult(
                    attacker_id=caster_id,
                    defender_id=target_id,
                    action_type=CombatActionType.CAST_SPELL,
                    hit=True,
                    damage_roll=damage_total,
                    damage_dealt=damage_total,
                    special_effects=special_effects,
                )
        else:
            special_effects.append(f"failed to cast {spell.name}")
            special_effects.append(result.reason or result.error or "unknown error")

        return AttackResult(
            attacker_id=caster_id,
            defender_id=target_id,
            action_type=CombatActionType.CAST_SPELL,
            hit=result.success,
            special_effects=special_effects,
        )

    def _apply_attack_results(self, results: list[AttackResult]) -> set[str]:
        """
        Apply damage from attack results.

        Handles:
        - Normal lethal damage
        - Non-lethal damage tracked separately (p169)
        - Damage tracking for morale triggers (solo creatures)
        """
        damaged: set[str] = set()

        for result in results:
            if result.hit and result.damage_dealt > 0:
                defender = self._get_combatant(result.defender_id)
                if not defender or not defender.stat_block:
                    continue

                # Check if non-lethal damage
                is_non_lethal = "Non-lethal" in result.special_effects

                if is_non_lethal and self._combat_state:
                    # Track non-lethal damage separately (p169)
                    status = self._combat_state.combatant_status.get(result.defender_id)
                    if status:
                        status.non_lethal_damage += result.damage_dealt
                        # If non-lethal exceeds current HP, target is unconscious (not dead)
                        if status.non_lethal_damage >= defender.stat_block.hp_current:
                            result.special_effects.append("Knocked unconscious")
                else:
                    # Apply lethal damage through controller
                    self.controller.apply_damage(
                        result.defender_id,
                        result.damage_dealt,
                        "physical"
                    )
                    # Also update combatant in encounter
                    defender.stat_block.hp_current -= result.damage_dealt

                damaged.add(result.defender_id)

                # Track damage for morale purposes (solo creature triggers)
                if self._combat_state:
                    status = self._combat_state.combatant_status.get(result.defender_id)
                    if status:
                        status.took_damage_this_round = True
                        if not status.first_harmed:
                            status.first_harmed = True

        return damaged

    def _get_combatant(self, combatant_id: str) -> Optional[Combatant]:
        """Get a combatant by ID."""
        if not self._combat_state:
            return None

        for combatant in self._combat_state.encounter.combatants:
            if combatant.combatant_id == combatant_id:
                return combatant

        return None

    def _init_round_modifiers(self) -> dict[str, Any]:
        """Initialize round modifier tracking."""
        return {
            "attack_bonus": {},
            "ac_bonus": {},
            "ac_penalty": {},
            "fleeing": set(),
        }

    def _collect_declarations(self, actions: list[CombatAction]) -> dict[str, set[str]]:
        """
        Track declarations that must be made before initiative:
        - CAST_SPELL / rune usage
        - FLEE from melee
        - CHARGE into melee
        - DEFEND (parry)
        """
        decl_map: dict[str, set[str]] = {}
        for action in actions:
            if action.action_type in {
                CombatActionType.CAST_SPELL,
                CombatActionType.FLEE,
                CombatActionType.CHARGE,
                CombatActionType.DEFEND,
            }:
                decl_map.setdefault(action.action_type.value, set()).add(action.combatant_id)
        return decl_map

    def _apply_movement_modifiers(
        self,
        action: CombatAction,
        round_modifiers: dict[str, Any],
    ) -> None:
        """Apply movement-phase modifiers such as charge or flee."""
        if action.action_type in {CombatActionType.CHARGE, CombatActionType.FLEE}:
            # Already applied at declaration; no further effect here
            return

    def _apply_parry_modifiers(
        self,
        action: CombatAction,
        round_modifiers: dict[str, Any],
    ) -> None:
        """Apply parry (defend) AC bonus for the round."""
        if action.combatant_id in round_modifiers["ac_bonus"]:
            return
        parry_bonus = max(action.parameters.get("parry_bonus", 1), 1)
        round_modifiers["ac_bonus"][action.combatant_id] = \
            round_modifiers["ac_bonus"].get(action.combatant_id, 0) + parry_bonus

    def _apply_declared_modifiers(
        self,
        actions: list[CombatAction],
        round_modifiers: dict[str, Any],
    ) -> None:
        """
        Apply modifiers that take effect as soon as declarations are made,
        regardless of initiative order.
        """
        for action in actions:
            if action.action_type == CombatActionType.CHARGE:
                round_modifiers["attack_bonus"][action.combatant_id] = \
                    round_modifiers["attack_bonus"].get(action.combatant_id, 0) + 2
                round_modifiers["ac_penalty"][action.combatant_id] = \
                    round_modifiers["ac_penalty"].get(action.combatant_id, 0) + 1
            elif action.action_type == CombatActionType.FLEE:
                round_modifiers["fleeing"].add(action.combatant_id)
            elif action.action_type == CombatActionType.DEFEND:
                parry_bonus = max(action.parameters.get("parry_bonus", 1), 1)
                round_modifiers["ac_bonus"][action.combatant_id] = \
                    round_modifiers["ac_bonus"].get(action.combatant_id, 0) + parry_bonus

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
        """
        Check for morale triggers this round (p167).

        Standard triggers:
        - First death on side
        - Half casualties

        Solo creature triggers (p167):
        - When first harmed
        - When reduced to 1/4 HP or less
        """
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

        # Solo creature morale triggers (p167)
        if self._combat_state.is_solo_creature:
            enemies = self._combat_state.encounter.get_active_enemies()
            if enemies:
                solo = enemies[0]
                status = self._combat_state.combatant_status.get(solo.combatant_id)

                if status and solo.stat_block:
                    # First harmed trigger - only once
                    if status.first_harmed and status.took_damage_this_round:
                        # Check if this is the first time being harmed
                        prev_rounds = self._combat_state.round_results[:-1] if self._combat_state.round_results else []
                        was_previously_harmed = any(
                            solo.combatant_id in [r.defender_id for r in round.actions_resolved if r.hit]
                            for round in prev_rounds
                        )
                        if not was_previously_harmed:
                            triggers.append(MoraleCheckTrigger.SOLO_FIRST_HARMED)

                    # Quarter HP trigger
                    hp_ratio = solo.stat_block.hp_current / solo.stat_block.hp_max
                    if hp_ratio <= 0.25 and status.took_damage_this_round:
                        triggers.append(MoraleCheckTrigger.SOLO_QUARTER_HP)

        return triggers

    def _roll_morale_check(self, trigger: MoraleCheckTrigger) -> dict[str, Any]:
        """
        Roll morale check for enemy side per Dolmenwood rules (p167).

        2d6 vs morale score. If roll > morale, enemies flee.

        Special rules:
        - Morale 12: Never checks morale, always fights to death
        - Two successful morale checks: Fights to death for rest of combat
        """
        result = {
            "trigger": trigger.value,
            "failed": False,
            "fleeing": [],
            "auto_pass": False,
        }

        if not self._combat_state:
            return result

        # Get remaining enemies
        enemies = self._combat_state.encounter.get_active_enemies()
        if not enemies:
            return result

        # Check each enemy's morale status
        enemies_to_check = []
        for enemy in enemies:
            status = self._combat_state.combatant_status.get(enemy.combatant_id)
            morale = enemy.stat_block.morale if enemy.stat_block else 7

            # Morale 12 never checks (p167)
            if morale >= 12:
                result["auto_pass"] = True
                continue

            # Two successful morale checks = fight to death (p167)
            if status and status.successful_morale_checks >= 2:
                continue

            enemies_to_check.append(enemy)

        if not enemies_to_check:
            # All enemies auto-pass or fight to death
            return result

        # Get average morale of enemies that need to check
        morale_scores = [
            e.stat_block.morale if e.stat_block else 7
            for e in enemies_to_check
        ]
        avg_morale = sum(morale_scores) // len(morale_scores)

        # Roll morale
        roll = self.dice.roll_2d6(f"morale check ({trigger.value})")
        result["roll"] = roll.total
        result["morale"] = avg_morale

        if roll.total > avg_morale:
            # Morale failed - enemies flee
            result["failed"] = True
            result["fleeing"] = [e.combatant_id for e in enemies_to_check]
            # Mark them as fleeing
            for enemy in enemies_to_check:
                status = self._combat_state.combatant_status.get(enemy.combatant_id)
                if status:
                    status.is_fleeing = True
        else:
            # Morale passed - track successful check
            for enemy in enemies_to_check:
                status = self._combat_state.combatant_status.get(enemy.combatant_id)
                if status:
                    status.successful_morale_checks += 1
                    if status.successful_morale_checks >= 2:
                        result.setdefault("fight_to_death", []).append(enemy.combatant_id)

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

    def attempt_flee(self, character_id: str, running: bool = True) -> dict[str, Any]:
        """
        Attempt to flee from melee combat per Dolmenwood rules (p147, p167).

        Fleeing must be declared before initiative.
        Enemies get +2 Attack and ignore shield AC bonus.
        Success based on movement rate comparison.

        Running (p147):
        - Running speed = Speed × 3 per round
        - Can only run for 30 rounds before exhaustion
        - Must rest 3 turns after running to exhaustion

        Args:
            character_id: ID of the fleeing character
            running: Whether to run (3× speed) vs normal movement

        Returns:
            Result of flee attempt with running/exhaustion info
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        fleeing_combatant = self._get_combatant(character_id)
        if not fleeing_combatant:
            return {"success": False, "error": "Combatant not found"}

        # Get combatant status for running tracking
        status = self._combat_state.combatant_status.get(character_id)

        # Check if can run (not exhausted)
        can_run = True
        if status and running:
            can_run = status.running_state.can_run()
            if not can_run:
                return {
                    "success": False,
                    "error": "Too exhausted to run! Must rest for 3 turns.",
                    "exhausted": True,
                    "rest_turns_remaining": status.running_state.rest_turns_remaining,
                }

        # Mark as fleeing in round modifiers
        round_modifiers = self._init_round_modifiers()
        round_modifiers["fleeing"].add(character_id)

        # Free attacks from engaged enemies with +2 bonus and ignore shield
        free_attacks = []
        for enemy in self._combat_state.encounter.get_active_enemies():
            attack = CombatAction(
                combatant_id=enemy.combatant_id,
                action_type=CombatActionType.MELEE_ATTACK,
                target_id=character_id,
            )
            result = self._resolve_attack(attack, round_modifiers)
            free_attacks.append(result)

        # Apply free attack damage
        self._apply_attack_results(free_attacks)

        # Calculate movement rates using MovementCalculator (p146-147)
        base_speed = fleeing_combatant.stat_block.movement if fleeing_combatant.stat_block else 30
        if running:
            fleeing_movement = MovementCalculator.get_running_movement(base_speed)
        else:
            fleeing_movement = MovementCalculator.get_encounter_movement(base_speed)

        # Compare with fastest enemy
        enemies = self._combat_state.encounter.get_active_enemies()
        if enemies:
            # Assume enemies also run if pursuing
            enemy_speeds = []
            for e in enemies:
                e_speed = e.stat_block.movement if e.stat_block else 30
                if running:
                    enemy_speeds.append(MovementCalculator.get_running_movement(e_speed))
                else:
                    enemy_speeds.append(MovementCalculator.get_encounter_movement(e_speed))
            fastest_enemy = max(enemy_speeds)
            escaped = fleeing_movement >= fastest_enemy
        else:
            fastest_enemy = 0
            escaped = True

        # Track running state (p147)
        if status:
            status.is_fleeing = True
            if running:
                # Record running round
                can_continue = status.running_state.run_round()
                if not can_continue:
                    # Became exhausted this round
                    pass  # Still escaped if faster, but now exhausted

        result = {
            "success": escaped,
            "free_attacks": len(free_attacks),
            "damage_taken": sum(a.damage_dealt for a in free_attacks if a.hit),
            "fleeing_speed": fleeing_movement,
            "enemy_speed": fastest_enemy,
            "running": running,
        }

        # Add running exhaustion info
        if status and running:
            result["rounds_run"] = status.running_state.rounds_run
            result["max_running_rounds"] = MAX_RUNNING_ROUNDS
            result["exhausted"] = status.running_state.is_exhausted
            if status.running_state.is_exhausted:
                result["rest_turns_needed"] = RUNNING_REST_TURNS

        return result

    def attempt_charge(self, character_id: str, target_id: str) -> dict[str, Any]:
        """
        Attempt a charging attack per Dolmenwood rules (p168).

        Charging must be declared before initiative.
        Grants +2 Attack but -1 AC.
        If target has braced weapon, charger takes double damage.
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        charger = self._get_combatant(character_id)
        target = self._get_combatant(target_id)
        if not charger or not target:
            return {"success": False, "error": "Combatant not found"}

        # Apply charge modifiers
        round_modifiers = self._init_round_modifiers()
        round_modifiers["attack_bonus"][character_id] = 2
        round_modifiers["ac_penalty"][character_id] = 1
        round_modifiers["charging_combatants"] = {character_id}

        # Mark charging status
        status = self._combat_state.combatant_status.get(character_id)
        if status:
            status.is_charging = True

        # Execute the charge attack
        attack = CombatAction(
            combatant_id=character_id,
            action_type=CombatActionType.MELEE_ATTACK,
            target_id=target_id,
        )
        result = self._resolve_attack(attack, round_modifiers)
        result.special_effects.append("Charge (+2 Attack, -1 AC)")

        # Apply damage
        self._apply_attack_results([result])

        return {
            "success": result.hit,
            "attack_result": result,
            "modifiers": "+2 Attack, -1 AC",
        }

    def attempt_push(self, character_id: str, target_id: str) -> dict[str, Any]:
        """
        Attempt a push attack per Dolmenwood rules (p169).

        Push attacks suffer -4 Attack penalty.
        If hit, target must Save vs Hold or be pushed back/knocked down.
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        pusher = self._get_combatant(character_id)
        target = self._get_combatant(target_id)
        if not pusher or not target:
            return {"success": False, "error": "Combatant not found"}

        # Apply push penalty
        round_modifiers = self._init_round_modifiers()
        round_modifiers["attack_bonus"][character_id] = -4

        # Execute push attack (no damage, just hit check)
        attack = CombatAction(
            combatant_id=character_id,
            action_type=CombatActionType.MELEE_ATTACK,
            target_id=target_id,
            parameters={"push_attack": True},
        )
        attack_roll = self.dice.roll_d20(f"{pusher.name} attempts to push {target.name}")
        attack_bonus = 0
        if pusher.stat_block and pusher.stat_block.attacks:
            attack_bonus = pusher.stat_block.attacks[0].get("bonus", 0)
        attack_bonus -= 4  # Push penalty

        target_ac = target.stat_block.armor_class if target.stat_block else 10
        hit = (attack_roll.total + attack_bonus) >= target_ac

        result = {
            "hit": hit,
            "attack_roll": attack_roll.total,
            "attack_bonus": attack_bonus,
            "target_ac": target_ac,
            "pushed": False,
        }

        if hit:
            # Target must Save vs Hold
            save_roll = self.dice.roll_d20(f"{target.name} saves vs Hold")
            # Default save target is 16 (can be adjusted based on creature)
            save_target = 16
            if target.stat_block and hasattr(target.stat_block, 'save_hold'):
                save_target = target.stat_block.save_hold

            if save_roll.total < save_target:
                result["pushed"] = True
                result["save_roll"] = save_roll.total
                result["save_needed"] = save_target
                result["effect"] = "Target pushed back and/or knocked down"
            else:
                result["save_roll"] = save_roll.total
                result["save_needed"] = save_target
                result["effect"] = "Target resisted push"

        return result

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
    # SPELL CASTING
    # =========================================================================

    def cast_spell(
        self,
        caster_id: str,
        spell_name: Optional[str] = None,
        spell_id: Optional[str] = None,
        target_id: Optional[str] = None,
        target_description: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Cast a spell during combat.

        This is the main entry point for combat spell casting. It handles:
        - Spell lookup and validation
        - Slot consumption
        - Effect application (damage, conditions, buffs)
        - Concentration management

        Args:
            caster_id: ID of the spellcaster
            spell_name: Name of the spell to cast
            spell_id: Alternative: ID of the spell to cast
            target_id: Optional target combatant ID
            target_description: Optional description of target for narration

        Returns:
            Dictionary with spell casting results
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        # Build combat action for spell
        action = CombatAction(
            combatant_id=caster_id,
            action_type=CombatActionType.CAST_SPELL,
            target_id=target_id,
            parameters={
                "spell_name": spell_name,
                "spell_id": spell_id,
                "target_description": target_description,
            },
        )

        # Check if caster was damaged before acting (for disruption)
        # In a full round, this would be tracked; for single action, assume not disrupted
        disrupted = False
        status = self._combat_state.combatant_status.get(caster_id)
        if status and status.took_damage_this_round:
            # Check if caster lost initiative
            caster = self._get_combatant(caster_id)
            if caster and caster.side == "party":
                if self._combat_state.party_initiative < self._combat_state.enemy_initiative:
                    disrupted = True
            elif caster and caster.side == "enemy":
                if self._combat_state.enemy_initiative < self._combat_state.party_initiative:
                    disrupted = True

        # Resolve the spell
        result = self._resolve_spell_action(action, disrupted)

        # Apply spell damage if any
        if result.hit and result.damage_dealt > 0:
            self._apply_attack_results([result])

        return {
            "success": result.hit,
            "disrupted": result.disrupted,
            "spell_name": spell_name or spell_id,
            "target_id": target_id,
            "damage_dealt": result.damage_dealt,
            "special_effects": result.special_effects,
        }

    def get_available_spells(self, caster_id: str) -> list[dict[str, Any]]:
        """
        Get list of spells available to a combatant.

        Args:
            caster_id: ID of the spellcaster

        Returns:
            List of available spell information
        """
        caster = self._get_combatant(caster_id)
        if not caster or caster.side != "party":
            return []

        # Get character state from controller
        char_state = self.controller.get_character(caster_id)
        if not char_state:
            return []

        available = []
        for spell_entry in char_state.spells:
            if not spell_entry.cast_today:
                spell_data = self.spell_resolver.lookup_spell(spell_entry.spell_id)
                if spell_data:
                    available.append({
                        "spell_id": spell_entry.spell_id,
                        "name": spell_data.name,
                        "level": spell_data.level,
                        "range": spell_data.range,
                        "duration": spell_data.duration,
                        "requires_concentration": spell_data.requires_concentration,
                    })
                else:
                    # Spell not in resolver cache, return basic info
                    available.append({
                        "spell_id": spell_entry.spell_id,
                        "name": spell_entry.spell_id,
                        "cast_today": False,
                    })

        return available

    def break_caster_concentration(self, caster_id: str) -> list[str]:
        """
        Break concentration for a spellcaster (called when they take damage).

        Args:
            caster_id: ID of the caster

        Returns:
            List of spell names whose concentration was broken
        """
        broken = self.spell_resolver.break_concentration(caster_id)
        return [effect.spell_name for effect in broken]

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_combat_state(self) -> Optional[CombatState]:
        """Get current combat state."""
        return self._combat_state

    def is_in_combat(self) -> bool:
        """Check if combat is active."""
        return self._combat_state is not None

    # =========================================================================
    # CLASS SPECIAL ACTIONS
    # =========================================================================

    def attempt_backstab(
        self,
        thief_id: str,
        target_id: str,
        stealth_success: bool = False,
    ) -> dict[str, Any]:
        """
        Attempt a backstab attack per Dolmenwood rules (p74-75).

        Backstab requirements:
        - Must be positioned behind the target
        - Target must be unaware (from successful Stealth or surprise)
        - Must use a dagger in melee

        Backstab bonuses:
        - +4 Attack bonus
        - 3d4 damage (plus STR and magic dagger bonuses)

        Natural 1: Save vs Doom or be noticed by target.

        Args:
            thief_id: ID of the thief attempting backstab
            target_id: ID of the target
            stealth_success: Whether thief successfully used Stealth to hide

        Returns:
            Dictionary with backstab result
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        thief = self._get_combatant(thief_id)
        target = self._get_combatant(target_id)

        if not thief or not target:
            return {"success": False, "error": "Combatant not found"}

        # Verify thief is a thief class
        char_state = self.controller.get_character(thief_id)
        if not char_state or char_state.character_class.lower() != "thief":
            return {"success": False, "error": "Only thieves can backstab"}

        # Get backstab data from registry
        registry = get_ability_registry()
        backstab_data = registry.get_backstab_data(char_state)
        if not backstab_data:
            return {"success": False, "error": "Backstab ability not found"}

        # Check target awareness
        surprise_status = self._combat_state.encounter.surprise_status
        target_unaware = (
            stealth_success or
            surprise_status == SurpriseStatus.ENEMIES_SURPRISED
        )
        if not target_unaware:
            return {
                "success": False,
                "error": "Target is aware of you - cannot backstab",
            }

        # Roll attack with +4 bonus
        attack_roll = self.dice.roll_d20(f"{thief.name} backstabs {target.name}")
        attack_bonus = backstab_data["attack_bonus"]  # +4

        # Add STR modifier
        str_mod = 0
        if thief.stat_block:
            str_mod = thief.stat_block.strength_mod
            attack_bonus += str_mod

        # Get target AC
        round_modifiers = self._init_round_modifiers()
        target_ac = self._get_effective_ac(target, thief, round_modifiers)

        # Check for natural 1
        is_natural_1 = attack_roll.total == 1
        total_attack = attack_roll.total + attack_bonus
        hit = total_attack >= target_ac and not is_natural_1

        result = {
            "attacker": thief.name,
            "target": target.name,
            "attack_roll": attack_roll.total,
            "attack_bonus": attack_bonus,
            "total_attack": total_attack,
            "target_ac": target_ac,
            "hit": hit,
            "is_natural_1": is_natural_1,
            "damage_dealt": 0,
            "special_effects": ["Backstab (+4 Attack, 3d4 damage)"],
        }

        # Handle natural 1 consequence
        if is_natural_1:
            # Save vs Doom or be noticed
            save_target = char_state.get_saving_throw("doom")
            save_roll = self.dice.roll_d20(f"{thief.name} saves vs Doom")

            result["save_roll"] = save_roll.total
            result["save_target"] = save_target
            result["save_type"] = "doom"

            if save_roll.total >= save_target:
                result["save_success"] = True
                result["special_effects"].append(
                    "Natural 1! Saved vs Doom - attack missed but not noticed"
                )
            else:
                result["save_success"] = False
                result["noticed"] = True
                result["special_effects"].append(
                    "Natural 1! Failed save - target noticed you!"
                )
            return result

        # Roll damage on hit
        if hit:
            # Backstab damage: 3d4 + STR + magic dagger bonus
            damage_roll = self.dice.roll("3d4", "backstab damage")
            damage = damage_roll.total + str_mod
            # Minimum damage of 1
            damage = max(1, damage)

            result["damage_roll"] = damage_roll.total
            result["str_modifier"] = str_mod
            result["damage_dealt"] = damage

            # Apply damage
            if target.stat_block:
                target.stat_block.hp_current -= damage
                self.controller.apply_damage(target_id, damage, "physical")

            # Check for kill
            if target.stat_block and target.stat_block.hp_current <= 0:
                result["target_killed"] = True
                result["special_effects"].append("Target slain!")

        return result

    def attempt_turn_undead(
        self,
        cleric_id: str,
        target_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Attempt to turn undead per Dolmenwood rules (p60-61).

        Turn Undead mechanics:
        - Range: 30 feet
        - Roll: 2d6
        - Results vary based on roll and level difference

        Level modifiers:
        - Lower level undead: +2 per level difference (max +6)
        - Higher level undead: -2 per level difference (max -6)

        Results:
        - 4 or lower: Undead unaffected
        - 5-6: 2d4 undead stunned for 1 Round
        - 7-12: 2d4 undead flee for 1 Turn
        - 13+: 2d4 undead permanently destroyed

        Args:
            cleric_id: ID of the cleric/friar
            target_ids: Optional specific undead targets

        Returns:
            Dictionary with turn undead result
        """
        if not self._combat_state:
            return {"success": False, "error": "No active combat"}

        cleric = self._get_combatant(cleric_id)
        if not cleric:
            return {"success": False, "error": "Combatant not found"}

        # Verify cleric/friar class
        char_state = self.controller.get_character(cleric_id)
        if not char_state:
            return {"success": False, "error": "Character not found"}

        class_lower = char_state.character_class.lower()
        if class_lower not in ("cleric", "friar"):
            return {"success": False, "error": "Only clerics and friars can turn undead"}

        # Get turn undead data from registry
        registry = get_ability_registry()
        turn_data = registry.get_turn_undead_data(char_state)
        if not turn_data:
            return {"success": False, "error": "Turn undead ability not found"}

        # Find undead targets within 30 feet
        undead_targets = []
        for enemy in self._combat_state.encounter.get_active_enemies():
            creature_type = self._get_creature_type(enemy)
            if creature_type == "undead":
                undead_targets.append(enemy)

        if not undead_targets:
            return {
                "success": False,
                "error": "No undead within range",
                "targets_checked": len(self._combat_state.encounter.get_active_enemies()),
            }

        # Calculate level modifier (based on lowest level undead present)
        cleric_level = char_state.level
        # Assume undead HD equals their level; use stat_block if available
        undead_levels = []
        for undead in undead_targets:
            if undead.stat_block:
                # Use HD as level approximation
                hd = getattr(undead.stat_block, "hit_dice", 1)
                if isinstance(hd, str):
                    # Parse "3d8" to get 3
                    hd = int(hd.split("d")[0]) if "d" in hd else 1
                undead_levels.append(hd)
            else:
                undead_levels.append(1)

        lowest_undead_level = min(undead_levels) if undead_levels else 1
        level_diff = cleric_level - lowest_undead_level
        level_modifier = max(-6, min(6, level_diff * 2))

        # Roll 2d6 + level modifier
        turn_roll = self.dice.roll_2d6("turn undead")
        total = turn_roll.total + level_modifier

        result = {
            "cleric": cleric.name,
            "cleric_level": cleric_level,
            "roll": turn_roll.total,
            "level_modifier": level_modifier,
            "total": total,
            "undead_present": len(undead_targets),
            "affected_count": 0,
            "effect": "",
        }

        # Determine effect based on total
        if total <= 4:
            result["effect"] = "unaffected"
            result["description"] = "The undead are unaffected by your holy power."
        elif total <= 6:
            # 2d4 stunned for 1 Round
            affected_roll = self.dice.roll("2d4", "undead affected")
            affected_count = min(affected_roll.total, len(undead_targets))
            result["affected_count"] = affected_count
            result["effect"] = "stunned"
            result["duration"] = "1 Round"
            result["description"] = (
                f"{affected_count} undead are stunned by holy power, unable to act!"
            )
            # Apply stunned condition to affected undead
            for i, undead in enumerate(undead_targets[:affected_count]):
                status = self._combat_state.combatant_status.get(undead.combatant_id)
                # Would add stunned condition here
        elif total <= 12:
            # 2d4 flee for 1 Turn
            affected_roll = self.dice.roll("2d4", "undead affected")
            affected_count = min(affected_roll.total, len(undead_targets))
            result["affected_count"] = affected_count
            result["effect"] = "fled"
            result["duration"] = "1 Turn"
            result["description"] = (
                f"{affected_count} undead flee in terror from your holy presence!"
            )
            # Mark them as fleeing
            for i, undead in enumerate(undead_targets[:affected_count]):
                status = self._combat_state.combatant_status.get(undead.combatant_id)
                if status:
                    status.is_fleeing = True
        else:
            # 2d4 destroyed
            affected_roll = self.dice.roll("2d4", "undead destroyed")
            affected_count = min(affected_roll.total, len(undead_targets))
            result["affected_count"] = affected_count
            result["effect"] = "destroyed"
            result["description"] = (
                f"{affected_count} undead are destroyed by divine power!"
            )
            # Kill the affected undead
            destroyed_names = []
            for i, undead in enumerate(undead_targets[:affected_count]):
                if undead.stat_block:
                    undead.stat_block.hp_current = 0
                    destroyed_names.append(undead.name)
            result["destroyed"] = destroyed_names

        result["success"] = result["effect"] != "unaffected"
        return result

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
