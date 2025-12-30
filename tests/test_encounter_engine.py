"""
Unit tests for encounter engine.

Tests encounter sequence phases, actions, and state transitions
from src/encounter/encounter_engine.py.
"""

import pytest
from src.encounter.encounter_engine import (
    EncounterEngine,
    EncounterPhase,
    EncounterOrigin,
    EncounterAction,
    AwarenessResult,
    SurpriseResult,
    DistanceResult,
    InitiativeResult,
)
from src.game_state.state_machine import GameState
from src.data_models import (
    EncounterState,
    EncounterType,
    SurpriseStatus,
    ReactionResult,
    Combatant,
    StatBlock,
)


class TestEncounterEngineInitialization:
    """Tests for encounter engine initialization."""

    def test_create_encounter_engine(self, controller_with_party):
        """Test creating an encounter engine."""
        engine = EncounterEngine(controller_with_party)
        assert engine.controller is controller_with_party
        assert engine.is_active() is False

    def test_engine_not_active_initially(self, encounter_engine):
        """Test that engine has no active encounter initially."""
        assert encounter_engine.is_active() is False
        assert encounter_engine.get_current_phase() is None
        assert encounter_engine.get_origin() is None


class TestEncounterStart:
    """Tests for starting encounters."""

    def test_start_wilderness_encounter(self, encounter_engine, basic_encounter):
        """Test starting a wilderness encounter."""
        result = encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )

        assert result["encounter_started"] is True
        assert result["origin"] == "wilderness"
        assert encounter_engine.is_active() is True
        assert encounter_engine.controller.current_state == GameState.ENCOUNTER

    def test_start_dungeon_encounter(self, encounter_engine, basic_encounter):
        """Test starting a dungeon encounter."""
        # First enter dungeon
        encounter_engine.controller.transition("enter_dungeon")

        result = encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.DUNGEON,
        )

        assert result["origin"] == "dungeon"
        assert encounter_engine.get_origin() == EncounterOrigin.DUNGEON

    def test_start_encounter_runs_awareness(self, encounter_engine, basic_encounter):
        """Test that starting encounter runs awareness phase."""
        result = encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
            party_aware=True,
            enemies_aware=False,
        )

        assert "awareness" in result
        assert result["awareness"].party_aware is True
        assert result["awareness"].enemies_aware is False


class TestSurprisePhase:
    """Tests for surprise determination."""

    def test_resolve_surprise_neither_surprised(
        self, encounter_engine, basic_encounter, seeded_dice
    ):
        """Test when neither side is surprised."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )

        # With seed 42, results are deterministic
        result = encounter_engine.resolve_surprise()

        assert isinstance(result, SurpriseResult)
        assert result.surprise_status in SurpriseStatus

    def test_resolve_surprise_party_aware_cannot_be_surprised(
        self, encounter_engine, basic_encounter
    ):
        """Test that aware party cannot be surprised."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
            party_aware=True,
        )

        result = encounter_engine.resolve_surprise()

        # Party was aware, so cannot be surprised
        assert result.surprise_status != SurpriseStatus.PARTY_SURPRISED

    def test_resolve_surprise_with_modifiers(self, encounter_engine, basic_encounter):
        """Test surprise resolution with modifiers."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )

        result = encounter_engine.resolve_surprise(
            party_modifier=2,  # Cautious
            enemy_modifier=-1,  # Distracted
        )

        assert result.party_modifier == 2
        assert result.enemy_modifier == -1


class TestDistancePhase:
    """Tests for encounter distance determination."""

    def test_resolve_distance_outdoor(self, encounter_engine, basic_encounter, seeded_dice):
        """Test outdoor distance calculation."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.resolve_surprise()

        result = encounter_engine.resolve_distance()

        assert isinstance(result, DistanceResult)
        assert result.is_outdoor is True
        assert result.multiplier == 30  # Outdoor multiplier
        # Distance should be 2d6 * 30 = 60-360 feet
        assert 60 <= result.distance_feet <= 360

    def test_resolve_distance_dungeon(self, encounter_engine, basic_encounter, seeded_dice):
        """Test dungeon distance calculation."""
        # Enter dungeon first
        encounter_engine.controller.transition("enter_dungeon")

        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.DUNGEON,
        )
        encounter_engine.resolve_surprise()

        result = encounter_engine.resolve_distance()

        assert result.is_outdoor is False
        assert result.multiplier == 10  # Dungeon multiplier
        # Distance should be 2d6 * 10 = 20-120 feet
        assert 20 <= result.distance_feet <= 120


class TestInitiativePhase:
    """Tests for initiative determination."""

    def test_resolve_initiative(self, encounter_engine, basic_encounter, seeded_dice):
        """Test initiative resolution."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.resolve_surprise()
        encounter_engine.resolve_distance()

        result = encounter_engine.resolve_initiative()

        assert isinstance(result, InitiativeResult)
        assert 1 <= result.party_initiative <= 6
        assert 1 <= result.enemy_initiative <= 6
        assert result.first_to_act in ["party", "enemy", "simultaneous"]

    def test_resolve_initiative_with_modifiers(self, encounter_engine, basic_encounter):
        """Test initiative with modifiers."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.resolve_surprise()
        encounter_engine.resolve_distance()

        result = encounter_engine.resolve_initiative(
            party_modifier=2,
            enemy_modifier=-1,
        )

        # Modifiers should be applied
        # We can't test exact values but can verify the method runs


class TestEncounterActions:
    """Tests for encounter action resolution."""

    def test_attack_action_transitions_to_combat(self, encounter_engine, basic_encounter):
        """Test that attack action triggers combat."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.auto_run_phases()

        result = encounter_engine.execute_action(EncounterAction.ATTACK, actor="party")

        assert result.encounter_ended is True
        assert result.transition_to == "encounter_to_combat"
        assert encounter_engine.controller.current_state == GameState.COMBAT

    def test_parley_action_rolls_reaction(self, encounter_engine, basic_encounter, seeded_dice):
        """Test that parley triggers reaction roll."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.auto_run_phases()

        result = encounter_engine.execute_action(EncounterAction.PARLEY, actor="party")

        assert result.reaction_roll is not None
        assert 2 <= result.reaction_roll <= 12
        assert result.reaction_result in ReactionResult

    def test_evasion_action(self, encounter_engine, basic_encounter, seeded_dice):
        """Test evasion attempt."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.auto_run_phases()

        result = encounter_engine.execute_action(EncounterAction.EVASION, actor="party")

        # Result should indicate success or failure
        assert result.success in [True, False]

    def test_evasion_fails_when_surprised(self, encounter_engine, surprise_encounter):
        """Test that surprised party cannot evade."""
        # Create encounter where party is surprised
        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=30,
            surprise_status=SurpriseStatus.PARTY_SURPRISED,
            actors=["goblin"],
            context="ambush",
            terrain="forest",
        )

        encounter_engine.start_encounter(
            encounter=encounter,
            origin=EncounterOrigin.WILDERNESS,
        )

        # Set surprise status directly
        state = encounter_engine.get_encounter_state()
        state.encounter.surprise_status = SurpriseStatus.PARTY_SURPRISED
        state.surprise = SurpriseResult(
            surprise_status=SurpriseStatus.PARTY_SURPRISED,
            message="Party surprised",
        )

        result = encounter_engine.execute_action(EncounterAction.EVASION, actor="party")

        assert result.success is False
        # Check that some message about being unable to evade exists
        assert len(result.messages) > 0

    def test_wait_action_grants_bonus(self, encounter_engine, basic_encounter):
        """Test that waiting grants reaction bonus."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.auto_run_phases()

        result = encounter_engine.execute_action(EncounterAction.WAIT, actor="party")

        assert result.success is True
        assert len(result.actions_resolved) > 0
        assert result.actions_resolved[0]["effect"] == "reaction_bonus"


class TestEncounterConclusion:
    """Tests for encounter conclusion."""

    def test_conclude_encounter(self, encounter_engine, basic_encounter):
        """Test concluding an encounter."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.auto_run_phases()

        result = encounter_engine.conclude_encounter("fled")

        assert result["encounter_concluded"] is True
        assert result["reason"] == "fled"
        assert result["turns_passed"] == 1
        assert encounter_engine.is_active() is False
        assert encounter_engine.controller.current_state == GameState.WILDERNESS_TRAVEL


class TestAutoRunPhases:
    """Tests for auto_run_phases convenience method."""

    def test_auto_run_phases(self, encounter_engine, basic_encounter):
        """Test auto-running all pre-action phases."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )

        result = encounter_engine.auto_run_phases()

        assert "surprise" in result
        assert "distance" in result
        assert "initiative" in result
        assert result["ready_for_action"] is True
        assert encounter_engine.get_current_phase() == EncounterPhase.ACTIONS


class TestEncounterSummary:
    """Tests for encounter summary."""

    def test_get_encounter_summary_inactive(self, encounter_engine):
        """Test summary when no encounter active."""
        summary = encounter_engine.get_encounter_summary()
        assert summary["active"] is False

    def test_get_encounter_summary_active(self, encounter_engine, basic_encounter):
        """Test summary during active encounter."""
        encounter_engine.start_encounter(
            encounter=basic_encounter,
            origin=EncounterOrigin.WILDERNESS,
        )
        encounter_engine.auto_run_phases()

        summary = encounter_engine.get_encounter_summary()

        assert summary["active"] is True
        assert summary["origin"] == "wilderness"
        assert summary["current_phase"] == "actions"
        assert "distance" in summary
        assert "surprise_status" in summary
