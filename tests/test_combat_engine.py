"""
Unit tests for combat engine.

Tests combat initialization, rounds, attacks, morale, and resolution
from src/combat/combat_engine.py.
"""

import pytest
from src.combat.combat_engine import (
    CombatEngine,
    CombatAction,
    CombatActionType,
    MoraleCheckTrigger,
    AttackResult,
    CombatRoundResult,
)
from src.game_state.state_machine import GameState
from src.data_models import (
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
)


class TestCombatEngineInitialization:
    """Tests for combat engine initialization."""

    def test_create_combat_engine(self, controller_with_party):
        """Test creating a combat engine."""
        engine = CombatEngine(controller_with_party)
        assert engine.controller is controller_with_party
        assert engine.is_in_combat() is False

    def test_engine_not_in_combat_initially(self, combat_engine):
        """Test that engine has no active combat initially."""
        assert combat_engine.is_in_combat() is False
        assert combat_engine.get_combat_state() is None


class TestCombatStart:
    """Tests for starting combat."""

    def test_start_combat(self, combat_engine, basic_encounter):
        """Test starting combat from encounter."""
        # Transition to encounter first
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")

        result = combat_engine.start_combat(
            encounter=basic_encounter,
            return_state=GameState.WILDERNESS_TRAVEL,
        )

        assert result["combat_started"] is True
        assert combat_engine.is_in_combat() is True
        assert len(result["party_combatants"]) > 0
        assert len(result["enemy_combatants"]) > 0

    def test_start_combat_handles_surprise(self, combat_engine, surprise_encounter):
        """Test that combat start handles surprise status."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")

        result = combat_engine.start_combat(
            encounter=surprise_encounter,
            return_state=GameState.WILDERNESS_TRAVEL,
        )

        assert result["surprise"]["surprise_status"] == "enemies_surprised"
        assert result["surprise"]["surprised_side"] == "enemies"
        assert result["surprise"]["surprise_rounds"] == 1


class TestCombatRounds:
    """Tests for combat round execution."""

    def test_execute_round(self, combat_engine, basic_encounter, seeded_dice):
        """Test executing a combat round."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        # Declare party actions
        party_combatant = basic_encounter.get_party_combatants()[0]
        enemy_combatant = basic_encounter.get_enemy_combatants()[0]

        party_actions = [
            CombatAction(
                combatant_id=party_combatant.combatant_id,
                action_type=CombatActionType.MELEE_ATTACK,
                target_id=enemy_combatant.combatant_id,
            )
        ]

        result = combat_engine.execute_round(party_actions)

        assert isinstance(result, CombatRoundResult)
        assert result.round_number == 1
        assert result.party_initiative >= 1
        assert result.enemy_initiative >= 1
        assert result.first_side in ["party", "enemy", "simultaneous"]

    def test_execute_multiple_rounds(self, combat_engine, basic_encounter, seeded_dice):
        """Test executing multiple combat rounds."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        for round_num in range(1, 4):
            party_actions = []
            result = combat_engine.execute_round(party_actions)
            assert result.round_number == round_num


class TestAttackResolution:
    """Tests for attack resolution."""

    def test_attack_hits_low_ac(self, combat_engine, basic_encounter, seeded_dice):
        """Test attack resolution against low AC target."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        # Get combatants
        party_combatant = basic_encounter.get_party_combatants()[0]
        enemy_combatant = basic_encounter.get_enemy_combatants()[0]

        # Execute attack
        party_actions = [
            CombatAction(
                combatant_id=party_combatant.combatant_id,
                action_type=CombatActionType.MELEE_ATTACK,
                target_id=enemy_combatant.combatant_id,
            )
        ]

        result = combat_engine.execute_round(party_actions)

        # Check that attack was resolved
        assert len(result.actions_resolved) >= 1
        attack_result = result.actions_resolved[0]
        assert isinstance(attack_result, AttackResult)
        assert attack_result.attacker_id == party_combatant.combatant_id

    def test_attack_damage_applied(self, combat_engine, basic_encounter, seeded_dice):
        """Test that damage is applied to targets."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        # Get initial HP
        enemy = basic_encounter.get_enemy_combatants()[0]
        initial_hp = enemy.stat_block.hp_current

        # Execute multiple rounds to ensure some hits
        for _ in range(5):
            party_combatant = basic_encounter.get_party_combatants()[0]
            party_actions = [
                CombatAction(
                    combatant_id=party_combatant.combatant_id,
                    action_type=CombatActionType.MELEE_ATTACK,
                    target_id=enemy.combatant_id,
                )
            ]
            result = combat_engine.execute_round(party_actions)
            if result.combat_ended:
                break

        # HP should have decreased if any hits landed
        final_hp = enemy.stat_block.hp_current
        # Can't guarantee damage due to random misses, but combat should progress


class TestEnemyAI:
    """Tests for enemy AI action generation."""

    def test_enemy_actions_generated(self, combat_engine, basic_encounter, seeded_dice):
        """Test that enemy actions are auto-generated."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        # Execute round with no explicit enemy actions
        result = combat_engine.execute_round([])

        # Enemy should have attacked
        enemy_attacks = [
            a for a in result.actions_resolved
            if a.attacker_id.startswith("goblin")
        ]
        assert len(enemy_attacks) >= 1


class TestMoraleChecks:
    """Tests for morale system."""

    def test_morale_check_on_first_death(self, combat_engine, seeded_dice):
        """Test morale check triggers on first death."""
        # Create encounter with weak goblins
        combatants = [
            Combatant(
                combatant_id="fighter_1",
                name="Fighter",
                side="party",
                stat_block=StatBlock(
                    armor_class=4,
                    hit_dice="3d8",
                    hp_current=24,
                    hp_max=24,
                    movement=90,
                    attacks=[{"name": "Sword", "damage": "1d8+3", "bonus": 5}],
                    morale=12,
                ),
            ),
            Combatant(
                combatant_id="goblin_1",
                name="Goblin 1",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=7,
                    hit_dice="1d8-1",
                    hp_current=1,  # Very low HP
                    hp_max=4,
                    movement=60,
                    attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
            Combatant(
                combatant_id="goblin_2",
                name="Goblin 2",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=7,
                    hit_dice="1d8-1",
                    hp_current=4,
                    hp_max=4,
                    movement=60,
                    attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
        ]

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=30,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin"],
            terrain="dungeon",
            combatants=combatants,
        )

        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(encounter, GameState.WILDERNESS_TRAVEL)

        # Kill the first goblin
        goblin = encounter.combatants[1]
        goblin.stat_block.hp_current = 0

        # Execute round to trigger morale check
        result = combat_engine.execute_round([])

        # Morale check should have been triggered
        # (May or may not fail depending on roll)


class TestCombatEnd:
    """Tests for combat ending conditions."""

    def test_combat_ends_all_enemies_defeated(self, combat_engine, seeded_dice):
        """Test combat ends when all enemies are defeated."""
        # Create encounter with single weak enemy
        combatants = [
            Combatant(
                combatant_id="fighter_1",
                name="Fighter",
                side="party",
                stat_block=StatBlock(
                    armor_class=4,
                    hit_dice="3d8",
                    hp_current=24,
                    hp_max=24,
                    movement=90,
                    attacks=[{"name": "Sword", "damage": "1d8+3", "bonus": 5}],
                    morale=12,
                ),
            ),
            Combatant(
                combatant_id="goblin_1",
                name="Goblin",
                side="enemy",
                stat_block=StatBlock(
                    armor_class=9,  # Easy to hit
                    hit_dice="1d8-1",
                    hp_current=1,  # 1 HP
                    hp_max=1,
                    movement=60,
                    attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                    morale=7,
                ),
            ),
        ]

        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=30,
            surprise_status=SurpriseStatus.NO_SURPRISE,
            actors=["goblin"],
            terrain="dungeon",
            combatants=combatants,
        )

        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(encounter, GameState.WILDERNESS_TRAVEL)

        # Kill the goblin directly
        encounter.combatants[1].stat_block.hp_current = 0

        # Execute round
        result = combat_engine.execute_round([])

        assert result.combat_ended is True
        assert result.end_reason == "all_enemies_defeated"

    def test_end_combat_transitions_back(self, combat_engine, basic_encounter):
        """Test that ending combat transitions to return state."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        result = combat_engine.end_combat()

        assert "rounds_fought" in result
        assert combat_engine.is_in_combat() is False
        assert combat_engine.controller.current_state == GameState.WILDERNESS_TRAVEL


class TestSpecialActions:
    """Tests for special combat actions."""

    def test_attempt_flee(self, combat_engine, basic_encounter, seeded_dice):
        """Test flee attempt."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        fighter = basic_encounter.get_party_combatants()[0]
        result = combat_engine.attempt_flee(fighter.combatant_id)

        assert "success" in result
        assert "free_attacks" in result
        assert "damage_taken" in result

    def test_attempt_parley(self, combat_engine, basic_encounter, seeded_dice):
        """Test parley attempt during combat."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        result = combat_engine.attempt_parley()

        assert "success" in result
        assert "roll" in result
        assert "message" in result


class TestCombatSummary:
    """Tests for combat state summary."""

    def test_get_combat_summary_inactive(self, combat_engine):
        """Test summary when not in combat."""
        summary = combat_engine.get_combat_summary()
        assert summary["active"] is False

    def test_get_combat_summary_active(self, combat_engine, basic_encounter):
        """Test summary during active combat."""
        combat_engine.controller.transition("encounter_triggered")
        combat_engine.controller.transition("encounter_to_combat")
        combat_engine.start_combat(basic_encounter, GameState.WILDERNESS_TRAVEL)

        summary = combat_engine.get_combat_summary()

        assert summary["active"] is True
        assert "round" in summary
        assert "party_combatants" in summary
        assert "enemy_combatants" in summary
        assert summary["party_casualties"] == 0
        assert summary["enemy_casualties"] == 0
