"""
Tests for hex NPC conversation context.

Verifies that:
- first_meeting is computed correctly (True for first interaction, False for subsequent)
- npc_name is correctly passed in transition context
- state transitions to SOCIAL_INTERACTION
"""

import pytest

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import HexLocation, HexNPC


@pytest.fixture
def controller():
    """Create a test controller."""
    return GlobalController(initial_state=GameState.WILDERNESS_TRAVEL)


@pytest.fixture
def hex_engine(controller):
    """Create a test hex engine."""
    return HexCrawlEngine(controller)


@pytest.fixture
def test_hex_with_npc():
    """Create a test hex with an NPC."""
    return HexLocation(
        hex_id="test_hex",
        name="Test Hex",
        coordinates=(1, 1),
        terrain_type="forest",
        npcs=[
            HexNPC(
                npc_id="test_npc_1",
                name="Gorbald the Hermit",
                description="A wizened hermit living in the woods.",
                kindred="Human",
                alignment="Neutral",
                demeanor=["grumpy", "wise"],
                speech="speaks slowly and deliberately",
            )
        ],
        points_of_interest=[],
    )


class TestNPCConversationContext:
    """Test NPC conversation context handling."""

    def test_first_meeting_is_true_on_first_interaction(
        self, controller, hex_engine, test_hex_with_npc
    ):
        """First interaction with NPC should have first_meeting=True."""
        hex_id = "test_hex"
        npc_id = "test_npc_1"

        # Load hex data
        hex_engine.load_hex_data(hex_id, test_hex_with_npc)

        # Enter the hex and go to a POI (simulate being at a location)
        hex_engine._current_poi = "forest clearing"
        hex_engine._poi_state = hex_engine.POIExplorationState.INSIDE if hasattr(hex_engine, 'POIExplorationState') else None

        # Override get_npcs_at_poi to return our test NPC
        def mock_get_npcs_at_poi(hex_id):
            return [
                {
                    "npc_id": "test_npc_1",
                    "name": "Gorbald the Hermit",
                    "description": "A wizened hermit",
                    "kindred": "Human",
                }
            ]

        hex_engine.get_npcs_at_poi = mock_get_npcs_at_poi

        # Interact with NPC
        result = hex_engine.interact_with_npc(hex_id, npc_id)

        assert result["success"] is True
        assert result["first_meeting"] is True, (
            "First interaction should have first_meeting=True"
        )
        assert result["npc_name"] == "Gorbald the Hermit"

    def test_first_meeting_is_false_on_subsequent_interaction(
        self, controller, hex_engine, test_hex_with_npc
    ):
        """Second interaction with same NPC should have first_meeting=False."""
        hex_id = "test_hex"
        npc_id = "test_npc_1"

        # Load hex data
        hex_engine.load_hex_data(hex_id, test_hex_with_npc)
        hex_engine._current_poi = "forest clearing"

        # Override get_npcs_at_poi
        def mock_get_npcs_at_poi(hex_id):
            return [
                {
                    "npc_id": "test_npc_1",
                    "name": "Gorbald the Hermit",
                }
            ]

        hex_engine.get_npcs_at_poi = mock_get_npcs_at_poi

        # First interaction
        result1 = hex_engine.interact_with_npc(hex_id, npc_id)
        assert result1["first_meeting"] is True

        # Reset state to allow another transition (simulate returning from conversation)
        controller.transition("conversation_end_wilderness", context={})

        # Second interaction
        result2 = hex_engine.interact_with_npc(hex_id, npc_id)
        assert result2["success"] is True
        assert result2["first_meeting"] is False, (
            "Second interaction should have first_meeting=False"
        )

    def test_npc_name_in_result(self, controller, hex_engine, test_hex_with_npc):
        """NPC name should be correctly returned in result."""
        hex_id = "test_hex"
        npc_id = "test_npc_1"

        hex_engine.load_hex_data(hex_id, test_hex_with_npc)
        hex_engine._current_poi = "clearing"

        def mock_get_npcs_at_poi(hex_id):
            return [{"npc_id": "test_npc_1", "name": "Gorbald the Hermit"}]

        hex_engine.get_npcs_at_poi = mock_get_npcs_at_poi

        result = hex_engine.interact_with_npc(hex_id, npc_id)

        assert result["npc_name"] == "Gorbald the Hermit"
        assert result["npc_name"] != ""  # Should not be empty

    def test_state_transitions_to_social_interaction(
        self, controller, hex_engine, test_hex_with_npc
    ):
        """Interacting with NPC should transition to SOCIAL_INTERACTION state."""
        hex_id = "test_hex"
        npc_id = "test_npc_1"

        hex_engine.load_hex_data(hex_id, test_hex_with_npc)
        hex_engine._current_poi = "clearing"

        def mock_get_npcs_at_poi(hex_id):
            return [{"npc_id": "test_npc_1", "name": "Gorbald the Hermit"}]

        hex_engine.get_npcs_at_poi = mock_get_npcs_at_poi

        # Verify starting state
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Interact
        result = hex_engine.interact_with_npc(hex_id, npc_id)

        # Verify transition
        assert controller.current_state == GameState.SOCIAL_INTERACTION, (
            f"Expected SOCIAL_INTERACTION, got {controller.current_state}"
        )

    def test_transition_context_includes_npc_info(
        self, controller, hex_engine, test_hex_with_npc
    ):
        """Transition context should include NPC information."""
        hex_id = "test_hex"
        npc_id = "test_npc_1"

        hex_engine.load_hex_data(hex_id, test_hex_with_npc)
        hex_engine._current_poi = "clearing"

        def mock_get_npcs_at_poi(hex_id):
            return [{"npc_id": "test_npc_1", "name": "Gorbald the Hermit"}]

        hex_engine.get_npcs_at_poi = mock_get_npcs_at_poi

        # Capture the transition context
        captured_context = {}

        def capture_transition(trigger, context=None):
            captured_context.update(context or {})
            # Still do the real transition
            original_transition(trigger, context)

        original_transition = controller.transition
        controller.transition = capture_transition

        result = hex_engine.interact_with_npc(hex_id, npc_id)

        # Verify context was captured
        assert captured_context.get("npc_id") == "test_npc_1"
        assert captured_context.get("npc_name") == "Gorbald the Hermit"
        assert captured_context.get("first_meeting") is True
        assert captured_context.get("return_to") == "wilderness"


class TestNPCNotFound:
    """Test handling of NPC not found cases."""

    def test_npc_not_at_poi(self, controller, hex_engine, test_hex_with_npc):
        """Should return error if NPC is not at current POI."""
        hex_id = "test_hex"

        hex_engine.load_hex_data(hex_id, test_hex_with_npc)
        hex_engine._current_poi = "clearing"

        def mock_get_npcs_at_poi(hex_id):
            return []  # No NPCs

        hex_engine.get_npcs_at_poi = mock_get_npcs_at_poi

        result = hex_engine.interact_with_npc(hex_id, "nonexistent_npc")

        assert result["success"] is False
        assert "error" in result
