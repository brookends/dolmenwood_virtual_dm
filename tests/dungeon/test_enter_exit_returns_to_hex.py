"""
Deterministic tests for dungeon enter/exit location preservation (P9.3).

Verifies that:
1. Party location is captured on dungeon entry
2. Dungeon state stores pre-dungeon location context
3. Exiting dungeon restores party to original hex/POI
4. State transitions are correct throughout
"""

import pytest
from unittest.mock import MagicMock, patch

from src.dungeon.dungeon_engine import (
    DungeonEngine,
    DungeonState,
    DungeonRoom,
)
from src.game_state.global_controller import GlobalController
from src.game_state.state_machine import GameState
from src.data_models import (
    Location,
    LocationType,
    PartyState,
    PartyResources,
    DiceRoller,
    CharacterState,
)


@pytest.fixture
def mock_controller():
    """Create a mock controller with party in wilderness hex."""
    controller = MagicMock(spec=GlobalController)

    # Set up initial party location in wilderness hex
    controller.party_state = PartyState(
        location=Location(
            location_type=LocationType.HEX,
            location_id="0703",
            sub_location="old_mill",
        ),
        resources=PartyResources(),
    )

    controller.current_state = GameState.WILDERNESS_TRAVEL
    controller.get_party_speed.return_value = 30

    return controller


@pytest.fixture
def dungeon_engine(mock_controller):
    """Create dungeon engine with mocked controller."""
    return DungeonEngine(controller=mock_controller)


class TestEnterDungeonCapturesLocation:
    """Test that enter_dungeon captures pre-dungeon location."""

    def test_captures_hex_location(self, dungeon_engine, mock_controller):
        """Verify hex location is captured before entering dungeon."""
        result = dungeon_engine.enter_dungeon(
            dungeon_id="old_mill_cellar",
            entry_room="entrance",
        )

        # Should succeed
        assert "error" not in result
        assert result["dungeon_id"] == "old_mill_cellar"

        # Should include entered_from context
        assert "entered_from" in result
        assert result["entered_from"]["location_type"] == "hex"
        assert result["entered_from"]["location_id"] == "0703"
        assert result["entered_from"]["sub_location"] == "old_mill"

    def test_stores_location_in_dungeon_state(self, dungeon_engine, mock_controller):
        """Verify pre-dungeon location is stored in DungeonState."""
        dungeon_engine.enter_dungeon(
            dungeon_id="old_mill_cellar",
            entry_room="entrance",
        )

        state = dungeon_engine._dungeon_state
        assert state is not None
        assert state.pre_dungeon_location_type == "hex"
        assert state.pre_dungeon_location_id == "0703"
        assert state.pre_dungeon_sub_location == "old_mill"

    def test_captures_settlement_location(self, dungeon_engine, mock_controller):
        """Verify settlement location is captured when entering from settlement."""
        # Change to settlement exploration
        mock_controller.current_state = GameState.SETTLEMENT_EXPLORATION
        mock_controller.party_state.location = Location(
            location_type=LocationType.SETTLEMENT,
            location_id="lankshorn",
            sub_location="tavern_cellar",
        )

        result = dungeon_engine.enter_dungeon(
            dungeon_id="tavern_basement",
            entry_room="cellar_stairs",
        )

        assert result["entered_from"]["location_type"] == "settlement"
        assert result["entered_from"]["location_id"] == "lankshorn"
        assert result["entered_from"]["sub_location"] == "tavern_cellar"

    def test_transition_includes_from_context(self, dungeon_engine, mock_controller):
        """Verify state transition includes pre-dungeon context."""
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        # Check transition was called with from_ context
        mock_controller.transition.assert_called_once()
        call_args = mock_controller.transition.call_args
        context = call_args[1]["context"]

        assert context["from_location_type"] == "hex"
        assert context["from_location_id"] == "0703"
        assert context["from_sub_location"] == "old_mill"


class TestExitDungeonRestoresLocation:
    """Test that exit_dungeon restores pre-dungeon location."""

    def test_restores_hex_location(self, dungeon_engine, mock_controller):
        """Verify exiting dungeon restores party to original hex."""
        # Enter dungeon
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        # Change state to dungeon exploration for exit
        mock_controller.current_state = GameState.DUNGEON_EXPLORATION

        # Exit dungeon
        result = dungeon_engine.exit_dungeon()

        assert "error" not in result
        assert result["returned_to"]["location_type"] == "hex"
        assert result["returned_to"]["location_id"] == "0703"
        assert result["returned_to"]["sub_location"] == "old_mill"

    def test_restores_location_via_controller(self, dungeon_engine, mock_controller):
        """Verify set_party_location is called with correct values."""
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        mock_controller.current_state = GameState.DUNGEON_EXPLORATION
        mock_controller.set_party_location.reset_mock()

        dungeon_engine.exit_dungeon()

        # Should restore to hex location
        mock_controller.set_party_location.assert_called_once_with(
            LocationType.HEX,
            "0703",
            sub_location="old_mill",
        )

    def test_fallback_to_hex_id_from_poi_config(self, dungeon_engine, mock_controller):
        """Verify fallback to hex_id when pre_dungeon fields not set."""
        # Create dungeon state without pre_dungeon fields (simulating legacy data)
        dungeon_engine._dungeon_state = DungeonState(
            dungeon_id="legacy_dungeon",
            current_room="entrance",
            hex_id="0805",
            poi_name="ancient_ruins",
        )

        mock_controller.current_state = GameState.DUNGEON_EXPLORATION

        result = dungeon_engine.exit_dungeon()

        assert result["returned_to"]["location_type"] == "hex"
        assert result["returned_to"]["location_id"] == "0805"
        assert result["returned_to"]["sub_location"] == "ancient_ruins"

    def test_transition_includes_return_context(self, dungeon_engine, mock_controller):
        """Verify exit transition includes return location context."""
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        mock_controller.current_state = GameState.DUNGEON_EXPLORATION
        mock_controller.transition.reset_mock()

        dungeon_engine.exit_dungeon()

        call_args = mock_controller.transition.call_args
        context = call_args[1]["context"]

        assert context["return_location_type"] == "hex"
        assert context["return_location_id"] == "0703"
        assert context["return_sub_location"] == "old_mill"

    def test_includes_leaving_description(self, dungeon_engine, mock_controller):
        """Verify leaving_description is included in exit result if configured."""
        dungeon_engine.enter_dungeon(
            dungeon_id="spectral_manse",
            entry_room="entrance",
            poi_config={
                "leaving": "The mists part as you step back into the mortal world.",
                "hex_id": "0703",
            },
        )

        mock_controller.current_state = GameState.DUNGEON_EXPLORATION

        result = dungeon_engine.exit_dungeon()

        assert result.get("leaving_description") == (
            "The mists part as you step back into the mortal world."
        )


class TestEnterExitRoundTrip:
    """Test complete enter-dungeon-exit cycle."""

    def test_full_cycle_preserves_location(self, dungeon_engine, mock_controller):
        """Verify location is correctly preserved through full cycle."""
        # Record original location
        original_location = Location(
            location_type=LocationType.HEX,
            location_id="1205",
            sub_location="barrow_mound",
        )
        mock_controller.party_state.location = original_location

        # Enter dungeon
        enter_result = dungeon_engine.enter_dungeon(
            dungeon_id="barrow_crypt",
            entry_room="tomb_entrance",
        )

        assert enter_result["entered_from"]["location_id"] == "1205"

        # Simulate exploring dungeon (state would change)
        mock_controller.current_state = GameState.DUNGEON_EXPLORATION

        # Exit dungeon
        exit_result = dungeon_engine.exit_dungeon()

        # Should return to original location
        assert exit_result["returned_to"]["location_type"] == "hex"
        assert exit_result["returned_to"]["location_id"] == "1205"
        assert exit_result["returned_to"]["sub_location"] == "barrow_mound"

    def test_dungeon_state_preserved_for_reentry(self, dungeon_engine, mock_controller):
        """Verify dungeon state is preserved after exit for potential re-entry."""
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        # Explore some rooms
        dungeon_engine._dungeon_state.explored_rooms.add("entrance")
        dungeon_engine._dungeon_state.explored_rooms.add("hallway")
        dungeon_engine._dungeon_state.turns_in_dungeon = 5

        mock_controller.current_state = GameState.DUNGEON_EXPLORATION
        dungeon_engine.exit_dungeon()

        # State should still exist
        assert dungeon_engine._dungeon_state is not None
        assert "entrance" in dungeon_engine._dungeon_state.explored_rooms
        assert dungeon_engine._dungeon_state.turns_in_dungeon == 5


class TestStateTransitions:
    """Test proper state transitions during enter/exit."""

    def test_enter_triggers_transition(self, dungeon_engine, mock_controller):
        """Verify enter_dungeon triggers correct state transition."""
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        mock_controller.transition.assert_called()
        first_call = mock_controller.transition.call_args_list[0]
        assert first_call[0][0] == "enter_dungeon"

    def test_exit_triggers_transition(self, dungeon_engine, mock_controller):
        """Verify exit_dungeon triggers correct state transition."""
        dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        mock_controller.current_state = GameState.DUNGEON_EXPLORATION
        mock_controller.transition.reset_mock()

        dungeon_engine.exit_dungeon()

        mock_controller.transition.assert_called_once()
        assert mock_controller.transition.call_args[0][0] == "exit_dungeon"

    def test_cannot_enter_from_wrong_state(self, dungeon_engine, mock_controller):
        """Verify cannot enter dungeon from invalid state."""
        mock_controller.current_state = GameState.COMBAT

        result = dungeon_engine.enter_dungeon(
            dungeon_id="test_dungeon",
            entry_room="entrance",
        )

        assert "error" in result
        mock_controller.transition.assert_not_called()

    def test_cannot_exit_from_wrong_state(self, dungeon_engine, mock_controller):
        """Verify cannot exit dungeon from invalid state."""
        # Don't enter dungeon first
        mock_controller.current_state = GameState.WILDERNESS_TRAVEL

        result = dungeon_engine.exit_dungeon()

        assert "error" in result
