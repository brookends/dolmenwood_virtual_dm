"""
Tests for P2-11: Combat triggers for settlement and fairy road.

Verifies that:
1. SettlementEngine.trigger_combat() transitions to COMBAT state
2. FairyRoadEngine.trigger_combat_transition() transitions to COMBAT state
3. Combat triggers set up encounter state correctly
4. Combat end returns to correct origin state
"""

import pytest
from unittest.mock import MagicMock, patch

from src.game_state.global_controller import GlobalController
from src.game_state.state_machine import GameState
from src.data_models import (
    DiceRoller,
    GameDate,
    GameTime,
    CharacterState,
    EncounterState,
    Combatant,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def controller():
    """Create a fresh GlobalController."""
    ctrl = GlobalController()
    # Add a character so party exists
    char = CharacterState(
        character_id="test_fighter",
        name="Test Fighter",
        character_class="Fighter",
        level=3,
        hp_current=24,
        hp_max=24,
        armor_class=4,
        base_speed=30,
        ability_scores={
            "STR": 16, "INT": 10, "WIS": 12,
            "DEX": 14, "CON": 15, "CHA": 11
        },
    )
    ctrl.add_character(char)
    return ctrl


# =============================================================================
# TESTS: Settlement Combat Trigger
# =============================================================================


class TestSettlementCombatTrigger:
    """Test SettlementEngine.trigger_combat() functionality."""

    def test_trigger_combat_returns_error_when_not_in_settlement(self, controller, seeded_dice):
        """trigger_combat should fail if not in a settlement."""
        from src.settlement.settlement_engine import SettlementEngine

        engine = SettlementEngine(controller)

        result = engine.trigger_combat(["guard"], reason="bar_fight")

        assert result["success"] is False
        assert "Not in a settlement" in result["message"]

    def test_trigger_combat_returns_error_for_empty_targets(self, controller, seeded_dice):
        """trigger_combat should fail if no targets specified."""
        from src.settlement.settlement_engine import SettlementEngine
        from src.settlement.settlement_content_models import SettlementData
        from src.settlement.settlement_registry import SettlementRegistry

        engine = SettlementEngine(controller)

        # Set up a minimal settlement using registry
        settlement = SettlementData(
            settlement_id="test_village",
            name="Test Village",
            hex_id="0705",
            size="village",
            population=100,
        )
        registry = SettlementRegistry()
        registry.add(settlement)
        engine.set_registry(registry)
        engine.set_active_settlement("test_village")

        result = engine.trigger_combat([], reason="bar_fight")

        assert result["success"] is False
        assert "No targets" in result["message"]

    def test_trigger_combat_transitions_to_combat_state(self, controller, seeded_dice):
        """trigger_combat should transition from SETTLEMENT to COMBAT."""
        from src.settlement.settlement_engine import SettlementEngine
        from src.settlement.settlement_content_models import SettlementData
        from src.settlement.settlement_registry import SettlementRegistry

        # Start in SETTLEMENT_EXPLORATION
        controller.transition("enter_settlement")
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

        engine = SettlementEngine(controller)

        # Set up a minimal settlement using registry
        settlement = SettlementData(
            settlement_id="test_village",
            name="Test Village",
            hex_id="0705",
            size="village",
            population=100,
        )
        registry = SettlementRegistry()
        registry.add(settlement)
        engine.set_registry(registry)
        engine.set_active_settlement("test_village")

        result = engine.trigger_combat(["bandit"], reason="theft_caught")

        assert result["success"] is True
        assert controller.current_state == GameState.COMBAT
        assert result["combatant_count"] >= 1

    def test_trigger_combat_sets_encounter_state(self, controller, seeded_dice):
        """trigger_combat should set the encounter on the controller."""
        from src.settlement.settlement_engine import SettlementEngine
        from src.settlement.settlement_content_models import SettlementData
        from src.settlement.settlement_registry import SettlementRegistry

        controller.transition("enter_settlement")
        engine = SettlementEngine(controller)

        # Set up a minimal settlement using registry
        settlement = SettlementData(
            settlement_id="test_village",
            name="Test Village",
            hex_id="0705",
            size="village",
            population=100,
        )
        registry = SettlementRegistry()
        registry.add(settlement)
        engine.set_registry(registry)
        engine.set_active_settlement("test_village")

        engine.trigger_combat(["guard", "guard"], reason="assault")

        # Verify encounter was set
        encounter = controller._current_encounter
        assert encounter is not None
        assert len(encounter.combatants) >= 1
        assert encounter.terrain == "settlement"


# =============================================================================
# TESTS: Fairy Road Combat Trigger
# =============================================================================


class TestFairyRoadCombatTrigger:
    """Test FairyRoadEngine.trigger_combat_transition() functionality."""

    def test_trigger_combat_returns_error_when_not_traveling(self, controller, seeded_dice):
        """trigger_combat_transition should fail if not on fairy road."""
        from src.fairy_roads.fairy_road_engine import FairyRoadEngine

        engine = FairyRoadEngine(controller)

        result = engine.trigger_combat_transition(["goblin"])

        assert result["success"] is False
        assert "No active fairy road" in result["message"]

    def test_trigger_combat_with_explicit_targets(self, controller, seeded_dice):
        """trigger_combat_transition should work with explicit target IDs."""
        from src.fairy_roads.fairy_road_engine import FairyRoadEngine, FairyRoadTravelState

        # Start in FAIRY_ROAD_TRAVEL
        controller.transition("enter_fairy_road")
        assert controller.current_state == GameState.FAIRY_ROAD_TRAVEL

        engine = FairyRoadEngine(controller)
        # Set up minimal travel state
        engine._state = FairyRoadTravelState(
            road_id="test_road",
            entry_door_hex="0705",
            entry_door_name="Test Door",
            current_segment=1,
            total_segments=5,
        )

        result = engine.trigger_combat_transition(
            target_ids=["sprite"],
            reason="party_attacked",
        )

        assert result["success"] is True
        assert controller.current_state == GameState.COMBAT
        assert result["combatant_count"] >= 1

    def test_trigger_combat_sets_encounter_state(self, controller, seeded_dice):
        """trigger_combat_transition should set encounter on controller."""
        from src.fairy_roads.fairy_road_engine import FairyRoadEngine, FairyRoadTravelState

        controller.transition("enter_fairy_road")
        engine = FairyRoadEngine(controller)
        engine._state = FairyRoadTravelState(
            road_id="test_road",
            entry_door_hex="0705",
            entry_door_name="Test Door",
            current_segment=2,
            total_segments=5,
        )

        engine.trigger_combat_transition(target_ids=["redcap"])

        encounter = controller._current_encounter
        assert encounter is not None
        assert len(encounter.combatants) >= 1
        assert encounter.terrain == "fairy_road"

    def test_trigger_combat_with_no_targets_fails(self, controller, seeded_dice):
        """trigger_combat_transition should fail if no targets available."""
        from src.fairy_roads.fairy_road_engine import FairyRoadEngine, FairyRoadTravelState

        controller.transition("enter_fairy_road")
        engine = FairyRoadEngine(controller)
        engine._state = FairyRoadTravelState(
            road_id="test_road",
            entry_door_hex="0705",
            entry_door_name="Test Door",
            current_segment=1,
            total_segments=5,
        )
        # No last_encounter_entry and no target_ids

        result = engine.trigger_combat_transition()

        assert result["success"] is False
        assert "No targets" in result["message"]


# =============================================================================
# TESTS: Combat End Returns to Correct State
# =============================================================================


class TestCombatEndReturns:
    """Test that combat end returns to the correct origin state."""

    def test_settlement_combat_returns_to_settlement(self, controller, seeded_dice):
        """Combat that started from settlement should return to settlement."""
        from src.settlement.settlement_engine import SettlementEngine
        from src.settlement.settlement_content_models import SettlementData
        from src.settlement.settlement_registry import SettlementRegistry

        # Enter settlement
        controller.transition("enter_settlement")
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

        engine = SettlementEngine(controller)
        settlement = SettlementData(
            settlement_id="test_village",
            name="Test Village",
            hex_id="0705",
            size="village",
            population=100,
        )
        registry = SettlementRegistry()
        registry.add(settlement)
        engine.set_registry(registry)
        engine.set_active_settlement("test_village")

        # Trigger combat
        engine.trigger_combat(["thief"], reason="caught_stealing")
        assert controller.current_state == GameState.COMBAT

        # End combat (return to previous)
        controller.state_machine.return_to_previous()
        assert controller.current_state == GameState.SETTLEMENT_EXPLORATION

    def test_fairy_road_combat_returns_to_fairy_road(self, controller, seeded_dice):
        """Combat that started from fairy road should return to fairy road."""
        from src.fairy_roads.fairy_road_engine import FairyRoadEngine, FairyRoadTravelState

        # Enter fairy road
        controller.transition("enter_fairy_road")
        assert controller.current_state == GameState.FAIRY_ROAD_TRAVEL

        engine = FairyRoadEngine(controller)
        engine._state = FairyRoadTravelState(
            road_id="test_road",
            entry_door_hex="0705",
            entry_door_name="Test Door",
            current_segment=3,
            total_segments=5,
        )

        # Trigger combat
        engine.trigger_combat_transition(target_ids=["pixie"])
        assert controller.current_state == GameState.COMBAT

        # End combat (return to previous)
        controller.state_machine.return_to_previous()
        assert controller.current_state == GameState.FAIRY_ROAD_TRAVEL


# =============================================================================
# TESTS: State Machine Trigger Validation
# =============================================================================


class TestStateMachineTriggers:
    """Test that the triggers are properly defined in state machine."""

    def test_settlement_combat_trigger_exists(self, controller):
        """settlement_combat trigger should be valid from SETTLEMENT_EXPLORATION."""
        controller.transition("enter_settlement")

        valid_triggers = controller.state_machine.get_valid_triggers()
        assert "settlement_combat" in valid_triggers

    def test_fairy_road_combat_trigger_exists(self, controller):
        """fairy_road_combat trigger should be valid from FAIRY_ROAD_TRAVEL."""
        controller.transition("enter_fairy_road")

        valid_triggers = controller.state_machine.get_valid_triggers()
        assert "fairy_road_combat" in valid_triggers

    def test_combat_end_settlement_trigger_exists(self, controller):
        """combat_end_settlement trigger should be valid from COMBAT."""
        # Get to combat from settlement
        controller.transition("enter_settlement")
        controller.transition("settlement_combat")
        assert controller.current_state == GameState.COMBAT

        valid_triggers = controller.state_machine.get_valid_triggers()
        assert "combat_end_settlement" in valid_triggers

    def test_combat_end_fairy_road_trigger_exists(self, controller):
        """combat_end_fairy_road trigger should be valid from COMBAT."""
        # Get to combat from fairy road
        controller.transition("enter_fairy_road")
        controller.transition("fairy_road_combat")
        assert controller.current_state == GameState.COMBAT

        valid_triggers = controller.state_machine.get_valid_triggers()
        assert "combat_end_fairy_road" in valid_triggers
