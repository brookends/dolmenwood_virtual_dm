"""
Tests for micro-dungeon fallback behavior.

Verifies that POIs marked as is_dungeon but without dynamic layout
(like Crocus's Cave in hex 0103) create a single-room dungeon with
the POI's interior/exploring text.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.dungeon.dungeon_engine import DungeonEngine, DungeonRoom, LightLevel, DoorState
from src.game_state.state_machine import GameState


class MockLightSource:
    """Mock light source with value attribute."""
    def __init__(self, value="torch"):
        self.value = value


class MockPartyState:
    """Mock party state for testing."""

    def __init__(self):
        self.location = MagicMock()
        self.location.location_type = MagicMock()
        self.location.location_type.value = "hex"
        self.location.location_id = "0103"
        self.location.sub_location = None
        self.active_light_source = MockLightSource("torch")
        self.light_remaining_turns = 6


class MockController:
    """Mock controller for testing dungeon entry."""

    def __init__(self, state=GameState.WILDERNESS_TRAVEL):
        self.current_state = state
        self.party_state = MockPartyState()
        self._transitions = []

    def transition(self, action, context=None):
        self._transitions.append((action, context))
        self.current_state = GameState.DUNGEON_EXPLORATION

    def set_party_location(self, location_type, location_id, sub_location=None):
        self.party_state.location.location_type = location_type
        self.party_state.location.location_id = location_id
        self.party_state.location.sub_location = sub_location


class TestMicroDungeonFallback:
    """Tests for micro-dungeon creation without dynamic layout."""

    def test_micro_dungeon_created_without_dynamic_layout(self):
        """Verify single-room dungeon is created when no dynamic_layout."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Crocus's Cave",
            "hex_id": "0103",
            "interior": "A sodden, high-ceilinged stone cave.",
            "exploring": None,
            "dynamic_layout": None,
            "roll_tables": [],
        }

        result = engine.enter_dungeon(
            dungeon_id="crocuss_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        # Should have micro_dungeon flag
        assert result.get("micro_dungeon") is True

        # Should have room description from interior text
        assert "sodden, high-ceilinged stone cave" in result.get("room_description", "")

        # Should have message with POI name
        assert "Crocus's Cave" in result.get("message", "")

    def test_micro_dungeon_has_single_room(self):
        """Verify micro-dungeon has exactly one room."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Test Cave",
            "hex_id": "0103",
            "interior": "A small cave.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="test_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        # Should have exactly one room
        assert len(engine._dungeon_state.rooms) == 1
        assert "entrance" in engine._dungeon_state.rooms

    def test_micro_dungeon_room_has_exit(self):
        """Verify micro-dungeon room has an exit back outside."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Test Cave",
            "hex_id": "0103",
            "interior": "A small cave.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="test_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        room = engine._dungeon_state.rooms["entrance"]

        # Should have an exit
        assert "exit" in room.exits
        assert room.exits["exit"] == "outside"

    def test_micro_dungeon_room_is_dark(self):
        """Verify micro-dungeon room defaults to dark light level."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Test Cave",
            "hex_id": "0103",
            "interior": "A dark cave.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="test_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        room = engine._dungeon_state.rooms["entrance"]

        assert room.light_level == LightLevel.DARK

    def test_micro_dungeon_combines_interior_and_exploring(self):
        """Verify both interior and exploring text are included in description."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Rich Cave",
            "hex_id": "0103",
            "interior": "A glittering cave of crystals.",
            "exploring": "The crystals hum with ancient power.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="rich_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        room = engine._dungeon_state.rooms["entrance"]

        assert "glittering cave of crystals" in room.description
        assert "crystals hum with ancient power" in room.description

    def test_micro_dungeon_fallback_description_when_no_text(self):
        """Verify fallback description when no interior/exploring text."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Empty Cave",
            "hex_id": "0103",
            "interior": "",
            "exploring": "",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="empty_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        room = engine._dungeon_state.rooms["entrance"]

        assert "inside Empty Cave" in room.description

    def test_dynamic_layout_still_works(self):
        """Verify dynamic layout POIs don't use micro-dungeon fallback."""
        controller = MockController()
        engine = DungeonEngine(controller)

        # Mock the _generate_dynamic_room to avoid needing full table setup
        engine._generate_dynamic_room = MagicMock()

        poi_config = {
            "poi_name": "Spectral Manse",
            "hex_id": "0709",
            "interior": "A haunted mansion.",
            "dynamic_layout": {"connections_per_room": "1d3"},
        }

        result = engine.enter_dungeon(
            dungeon_id="spectral_manse",
            entry_room="entrance",
            poi_config=poi_config,
        )

        # Should have dynamic_layout flag, not micro_dungeon
        assert result.get("dynamic_layout") is True
        assert result.get("micro_dungeon") is None or result.get("micro_dungeon") is False

        # Should have called _generate_dynamic_room
        engine._generate_dynamic_room.assert_called_once_with("entrance")

    def test_micro_dungeon_room_marked_visited(self):
        """Verify micro-dungeon room is marked as visited."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Test Cave",
            "hex_id": "0103",
            "interior": "A small cave.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="test_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        room = engine._dungeon_state.rooms["entrance"]

        assert room.visited is True


class TestMicroDungeonTransition:
    """Tests for state transition when entering micro-dungeon."""

    def test_transitions_to_dungeon_exploration(self):
        """Verify entering micro-dungeon transitions to DUNGEON_EXPLORATION."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Test Cave",
            "hex_id": "0103",
            "interior": "A small cave.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="test_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        assert controller.current_state == GameState.DUNGEON_EXPLORATION

    def test_transition_includes_poi_name(self):
        """Verify transition context includes POI name."""
        controller = MockController()
        engine = DungeonEngine(controller)

        poi_config = {
            "poi_name": "Crocus's Cave",
            "hex_id": "0103",
            "interior": "A sodden cave.",
            "dynamic_layout": None,
        }

        engine.enter_dungeon(
            dungeon_id="crocuss_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        # Check transition was called with poi_name
        assert len(controller._transitions) == 1
        action, context = controller._transitions[0]
        assert action == "enter_dungeon"
        assert context.get("poi_name") == "Crocus's Cave"


class TestMicroDungeonWithHex0103:
    """Integration tests using hex 0103 Crocus's Cave configuration."""

    def test_crocuss_cave_config(self):
        """Test with config matching Crocus's Cave from hex 0103."""
        controller = MockController()
        engine = DungeonEngine(controller)

        # Config matching what get_poi_dungeon_config returns for Crocus's Cave
        poi_config = {
            "poi_name": "Crocus's Cave",
            "hex_id": "0103",
            "dungeon_levels": None,
            "dynamic_layout": None,
            "item_persistence": None,
            "roll_tables": [],
            "room_table": None,
            "encounter_table": None,
            "interior": "A sodden, high-ceilinged stone cave, filled with piles of reeds, bones, and shiny objects.",
            "exploring": None,
            "leaving": None,
        }

        result = engine.enter_dungeon(
            dungeon_id="crocuss_cave",
            entry_room="entrance",
            poi_config=poi_config,
        )

        # Should work as micro-dungeon
        assert result.get("micro_dungeon") is True
        assert "sodden, high-ceilinged stone cave" in result.get("room_description", "")
        assert controller.current_state == GameState.DUNGEON_EXPLORATION

        # Room should have proper structure
        room = engine._dungeon_state.rooms["entrance"]
        assert room.name == "Crocus's Cave"
        assert "exit" in room.exits
