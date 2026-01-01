"""
Tests for the Fairy Roads system.

Tests cover:
- Fairy road models and data loading
- Registry operations
- Fairy door mechanics
- Travel checks and encounters
- Time dilation
- Stray from path mechanics
- State machine integration
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from src.fairy_roads.fairy_road_models import (
    FairyRoadData,
    FairyDoor,
    FairyRoadEncounterTable,
    FairyRoadEncounterEntry,
    FairyRoadLocationEntry,
    FairyRoadTravelState,
    FairyRoadCheckResult,
    FairyRoadCheckOutcome,
    StrayFromPathResult,
    StrayFromPathOutcome,
)
from src.fairy_roads.fairy_road_engine import (
    FairyRoadEngine,
    FairyRoadPhase,
    FairyRoadTravelResult,
    FairyRoadEntryResult,
    FairyRoadExitResult,
    reset_fairy_road_engine,
)
from src.content_loader.fairy_road_registry import (
    FairyRoadRegistry,
    get_fairy_road_registry,
    reset_fairy_road_registry,
)
from src.content_loader.fairy_road_loader import (
    FairyRoadLoader,
)
from src.game_state.state_machine import GameState


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_door_data():
    """Sample fairy door data."""
    return {
        "door_id": "test_door_1",
        "name": "The Test Door",
        "hex_id": "0704",
        "fairy_road_id": "test_road",
        "description": "A shimmering portal",
        "requires_time": "twilight",
        "always_visible": False,
        "detection_dc": 15,
        "road_position": 0.0,
    }


@pytest.fixture
def sample_road_data():
    """Sample fairy road data."""
    return {
        "road_id": "test_road",
        "name": "The Test Road",
        "description": "A mysterious fairy road for testing",
        "length_segments": 3,
        "difficulty": "normal",
        "time_dilation_enabled": True,
        "time_dilation_dice": "1d6",
        "time_dilation_unit": "days",
        "atmosphere": "Ethereal mist surrounds the path",
        "sights": ["Glowing mushrooms", "Dancing shadows"],
        "sounds": ["Distant music"],
        "smells": ["Wild roses"],
        "doors": [
            {
                "door_id": "test_door_1",
                "name": "Entry Door",
                "hex_id": "0704",
                "fairy_road_id": "test_road",
                "description": "The entrance",
                "road_position": 0.0,
            },
            {
                "door_id": "test_door_2",
                "name": "Exit Door",
                "hex_id": "1203",
                "fairy_road_id": "test_road",
                "description": "The exit",
                "requires_moonphase": "full_moon",
                "road_position": 1.0,
            },
        ],
        "encounter_table": {
            "table_id": "test_encounters",
            "name": "Test Encounters",
            "die_type": "d6",
            "monster_entries": [
                {
                    "roll": 1,
                    "roll_max": 2,
                    "creature_type": "Test Monster",
                    "count_dice": "1d4",
                    "description": "A test monster appears",
                    "is_hostile": True,
                    "monster_ids": ["test_monster"],
                }
            ],
            "location_entries": [
                {
                    "roll": 1,
                    "name": "Test Location",
                    "description": "A clearing in the mist",
                    "features": ["Strange tree"],
                }
            ],
        },
        "stray_exit_hexes": ["0705", "0803"],
        "stray_time_dice": "1d4",
        "stray_time_unit": "hours",
        "no_iron": True,
        "special_rules": ["Iron damages carriers"],
    }


@pytest.fixture
def fairy_road(sample_road_data):
    """Create a FairyRoadData instance."""
    return FairyRoadData.from_dict(sample_road_data)


@pytest.fixture
def fairy_door(sample_door_data):
    """Create a FairyDoor instance."""
    return FairyDoor.from_dict(sample_door_data)


@pytest.fixture
def registry(fairy_road):
    """Create a registry with a sample road."""
    reg = FairyRoadRegistry()
    reg.add(fairy_road)
    return reg


@pytest.fixture
def mock_controller():
    """Create a mock GlobalController."""
    controller = Mock()
    controller.current_state = GameState.WILDERNESS_TRAVEL
    controller.get_active_characters.return_value = []
    controller.transition = Mock()
    controller.advance_time = Mock()
    return controller


@pytest.fixture
def engine(mock_controller, registry):
    """Create a FairyRoadEngine with mocked dependencies."""
    reset_fairy_road_engine()
    return FairyRoadEngine(mock_controller, registry)


@pytest.fixture(autouse=True)
def cleanup_singletons():
    """Clean up singleton instances after each test."""
    yield
    reset_fairy_road_registry()
    reset_fairy_road_engine()


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestFairyDoor:
    """Tests for FairyDoor model."""

    def test_from_dict_basic(self, sample_door_data):
        """Test creating a door from dict."""
        door = FairyDoor.from_dict(sample_door_data)

        assert door.door_id == "test_door_1"
        assert door.name == "The Test Door"
        assert door.hex_id == "0704"
        assert door.fairy_road_id == "test_road"
        assert door.requires_time == "twilight"
        assert door.detection_dc == 15
        assert door.road_position == 0.0

    def test_from_dict_optional_fields(self):
        """Test creating a door with minimal data."""
        door = FairyDoor.from_dict(
            {
                "door_id": "minimal_door",
                "name": "Minimal",
                "hex_id": "0101",
                "fairy_road_id": "road",
            }
        )

        assert door.door_id == "minimal_door"
        assert door.requires_time is None
        assert door.requires_moonphase is None
        assert door.always_visible is False


class TestFairyRoadData:
    """Tests for FairyRoadData model."""

    def test_from_dict_full(self, sample_road_data):
        """Test creating a road from complete dict."""
        road = FairyRoadData.from_dict(sample_road_data)

        assert road.road_id == "test_road"
        assert road.name == "The Test Road"
        assert road.length_segments == 3
        assert road.time_dilation_enabled is True
        assert road.time_dilation_dice == "1d6"
        assert len(road.doors) == 2
        assert road.encounter_table is not None
        assert road.no_iron is True

    def test_from_dict_minimal(self):
        """Test creating a road with minimal data."""
        road = FairyRoadData.from_dict(
            {
                "road_id": "minimal_road",
                "name": "Minimal Road",
            }
        )

        assert road.road_id == "minimal_road"
        assert road.length_segments == 3  # Default
        assert road.time_dilation_enabled is True  # Default
        assert len(road.doors) == 0

    def test_encounter_table_parsing(self, sample_road_data):
        """Test encounter table is properly parsed."""
        road = FairyRoadData.from_dict(sample_road_data)

        assert road.encounter_table is not None
        assert road.encounter_table.table_id == "test_encounters"
        assert len(road.encounter_table.monster_entries) == 1
        assert len(road.encounter_table.location_entries) == 1

        monster = road.encounter_table.monster_entries[0]
        assert monster.roll == 1
        assert monster.roll_max == 2
        assert monster.count_dice == "1d4"
        assert monster.is_hostile is True


class TestFairyRoadTravelState:
    """Tests for FairyRoadTravelState model."""

    def test_initial_state(self):
        """Test creating initial travel state."""
        state = FairyRoadTravelState(
            road_id="test_road",
            entry_door_id="door_1",
            entry_hex_id="0704",
            total_segments=4,
        )

        assert state.current_segment == 0
        assert state.subjective_turns_elapsed == 0
        assert state.mortal_time_frozen is True
        assert state.strayed_from_path is False
        assert state.is_complete is False


# =============================================================================
# REGISTRY TESTS
# =============================================================================


class TestFairyRoadRegistry:
    """Tests for FairyRoadRegistry."""

    def test_add_and_get(self, fairy_road):
        """Test adding and retrieving a road."""
        registry = FairyRoadRegistry()
        registry.add(fairy_road, source_path="/test/path.json")

        result = registry.get("test_road")
        assert result is not None
        assert result.road_id == "test_road"

    def test_get_nonexistent(self):
        """Test getting a non-existent road."""
        registry = FairyRoadRegistry()
        assert registry.get("nonexistent") is None

    def test_door_indexing(self, fairy_road):
        """Test that doors are properly indexed."""
        registry = FairyRoadRegistry()
        registry.add(fairy_road)

        # Get door by ID
        door = registry.get_door("test_door_1")
        assert door is not None
        assert door.name == "Entry Door"

        # Get doors by hex
        doors_in_hex = registry.get_doors_in_hex("0704")
        assert len(doors_in_hex) == 1
        assert doors_in_hex[0].door_id == "test_door_1"

    def test_hex_has_doors(self, fairy_road):
        """Test checking if hex has doors."""
        registry = FairyRoadRegistry()
        registry.add(fairy_road)

        assert registry.hex_has_doors("0704") is True
        assert registry.hex_has_doors("9999") is False

    def test_get_all_roads(self, fairy_road):
        """Test getting all roads."""
        registry = FairyRoadRegistry()
        registry.add(fairy_road)

        roads = registry.get_all_roads()
        assert len(roads) == 1
        assert roads[0].road_id == "test_road"

    def test_count(self, fairy_road):
        """Test counting roads and doors."""
        registry = FairyRoadRegistry()
        registry.add(fairy_road)

        assert registry.count() == 1
        assert registry.door_count() == 2

    def test_clear(self, fairy_road):
        """Test clearing the registry."""
        registry = FairyRoadRegistry()
        registry.add(fairy_road)
        registry.clear()

        assert registry.count() == 0
        assert registry.door_count() == 0


# =============================================================================
# LOADER TESTS
# =============================================================================


class TestFairyRoadLoader:
    """Tests for FairyRoadLoader."""

    def test_load_from_json(self, tmp_path, sample_road_data):
        """Test loading roads from JSON files."""
        # Create test JSON file
        json_file = tmp_path / "test_road.json"
        json_file.write_text(json.dumps(sample_road_data))

        # Load
        loader = FairyRoadLoader(tmp_path)
        registry = loader.load_registry()

        assert registry.count() == 1
        road = registry.get("test_road")
        assert road is not None
        assert road.name == "The Test Road"

    def test_load_wrapper_format(self, tmp_path, sample_road_data):
        """Test loading from wrapper format with items array."""
        wrapped = {"_metadata": {"version": "1.0"}, "items": [sample_road_data]}
        json_file = tmp_path / "roads.json"
        json_file.write_text(json.dumps(wrapped))

        loader = FairyRoadLoader(tmp_path)
        registry = loader.load_registry()

        assert registry.count() == 1

    def test_load_nonexistent_directory(self, tmp_path):
        """Test loading from non-existent directory."""
        loader = FairyRoadLoader(tmp_path / "nonexistent")
        registry, report = loader.load_registry_with_report()

        assert registry.count() == 0
        assert len(report.errors) > 0


# =============================================================================
# ENGINE TESTS
# =============================================================================


class TestFairyRoadEngineEntry:
    """Tests for fairy road entry mechanics."""

    def test_can_enter_door_success(self, engine, registry):
        """Test checking door entry with requirements met."""
        result = engine.can_enter_door(
            door_id="test_door_1",
            current_hex_id="0704",
        )

        # Door has no requirements (optional fields)
        assert result.success is True
        assert result.requirements_met is True

    def test_can_enter_door_wrong_hex(self, engine):
        """Test entry fails when not at correct hex."""
        result = engine.can_enter_door(
            door_id="test_door_1",
            current_hex_id="9999",
        )

        assert result.success is False

    def test_can_enter_door_missing_requirement(self, engine, registry):
        """Test entry fails when requirements not met."""
        # test_door_2 requires full_moon
        result = engine.can_enter_door(
            door_id="test_door_2",
            current_hex_id="1203",
            moonphase="new_moon",
        )

        assert result.success is False
        assert result.requirements_met is False
        assert "full_moon" in str(result.missing_requirements)

    def test_enter_fairy_road(self, engine, mock_controller):
        """Test entering a fairy road."""
        result = engine.enter_fairy_road("test_door_1")

        assert result.success is True
        assert result.road_id == "test_road"
        assert engine.is_active() is True
        assert engine.get_current_phase() == FairyRoadPhase.TRAVELING

        # Verify state transition was called
        mock_controller.transition.assert_called_once()
        call_args = mock_controller.transition.call_args
        assert call_args[0][0] == "enter_fairy_road"

    def test_enter_nonexistent_door(self, engine):
        """Test entering through non-existent door."""
        result = engine.enter_fairy_road("nonexistent_door")

        assert result.success is False
        assert engine.is_active() is False


class TestFairyRoadEngineTravel:
    """Tests for fairy road travel mechanics."""

    def test_travel_segment_nothing(self, engine, mock_controller):
        """Test traveling a segment with no encounter."""
        engine.enter_fairy_road("test_door_1")

        # Mock dice to return 5 (nothing happens)
        with patch.object(engine.dice, "roll_d6") as mock_roll:
            mock_roll.return_value = Mock(total=5)
            result = engine.travel_segment()

        assert result.success is True
        assert result.segment == 1
        assert result.encounter_triggered is False
        assert result.location_found is False

    def test_travel_segment_monster(self, engine, mock_controller):
        """Test traveling a segment with monster encounter."""
        engine.enter_fairy_road("test_door_1")

        # Mock dice to return 1 (monster encounter)
        with patch.object(engine.dice, "roll_d6") as mock_d6:
            mock_d6.return_value = Mock(total=1)
            with patch.object(engine.dice, "roll") as mock_roll:
                mock_roll.return_value = Mock(total=1)
                result = engine.travel_segment()

        assert result.success is True
        assert result.encounter_triggered is True
        assert result.check_outcome is not None
        assert result.check_outcome.check_type == FairyRoadCheckResult.MONSTER_ENCOUNTER
        assert engine.get_current_phase() == FairyRoadPhase.ENCOUNTER

    def test_travel_segment_location(self, engine, mock_controller):
        """Test traveling a segment with location encounter."""
        engine.enter_fairy_road("test_door_1")

        # Mock dice to return 3 (location encounter)
        with patch.object(engine.dice, "roll_d6") as mock_d6:
            mock_d6.return_value = Mock(total=3)
            with patch.object(engine.dice, "roll") as mock_roll:
                mock_roll.return_value = Mock(total=1)
                result = engine.travel_segment()

        assert result.success is True
        assert result.location_found is True
        assert result.check_outcome is not None
        assert result.check_outcome.check_type == FairyRoadCheckResult.LOCATION_ENCOUNTER
        assert engine.get_current_phase() == FairyRoadPhase.LOCATION

    def test_travel_complete_segments(self, engine, mock_controller):
        """Test traveling all segments."""
        engine.enter_fairy_road("test_door_1")

        # Travel all 3 segments with no encounters
        with patch.object(engine.dice, "roll_d6") as mock_roll:
            mock_roll.return_value = Mock(total=6)  # Nothing

            for i in range(3):
                result = engine.travel_segment()
                assert result.segment == i + 1

        # After 3 segments, should be ready to exit
        assert engine.get_current_phase() == FairyRoadPhase.EXITING


class TestFairyRoadEngineExit:
    """Tests for fairy road exit mechanics."""

    def test_exit_fairy_road_with_time_dilation(self, engine, mock_controller):
        """Test exiting with time dilation."""
        engine.enter_fairy_road("test_door_1")

        # Mock time dilation roll
        with patch.object(engine.dice, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=4)  # 4 days pass
            result = engine.exit_fairy_road("test_door_2")

        assert result.success is True
        assert result.exit_hex_id == "1203"
        assert result.mortal_days_passed == 4

        # Verify time was advanced
        mock_controller.advance_time.assert_called()

        # Verify state transition
        mock_controller.transition.assert_called()
        last_call = mock_controller.transition.call_args_list[-1]
        assert last_call[0][0] == "exit_fairy_road"

        # Engine should be inactive
        assert engine.is_active() is False

    def test_exit_uses_destination_door(self, engine, mock_controller):
        """Test exit uses destination door if specified on entry."""
        engine.enter_fairy_road("test_door_1", destination_door_id="test_door_2")

        with patch.object(engine.dice, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=1)
            result = engine.exit_fairy_road()  # No door specified

        assert result.success is True
        assert result.door_id == "test_door_2"


class TestFairyRoadEngineStray:
    """Tests for 'Don't Stray From the Path' mechanic."""

    def test_stray_when_unconscious(self, engine, mock_controller):
        """Test straying from path when party member is unconscious."""
        # Set up a character with 0 HP
        unconscious_char = Mock()
        unconscious_char.current_hp = 0
        mock_controller.get_active_characters.return_value = [unconscious_char]

        engine.enter_fairy_road("test_door_1")

        # Complete an encounter and resume - should trigger stray check
        engine._phase = FairyRoadPhase.ENCOUNTER

        with patch.object(engine.dice, "roll") as mock_roll:
            mock_roll.return_value = Mock(total=3)  # 3 hours pass
            result = engine.resume_after_encounter()

        assert result.phase == FairyRoadPhase.STRAYED
        assert result.stray_outcome is not None
        assert result.stray_outcome.exit_hex_id in ["0705", "0803"]
        assert engine.is_active() is False


class TestFairyRoadEngineSummary:
    """Tests for engine state summary."""

    def test_get_travel_summary_inactive(self, engine):
        """Test summary when not traveling."""
        summary = engine.get_travel_summary()
        assert summary["active"] is False

    def test_get_travel_summary_active(self, engine):
        """Test summary when traveling."""
        engine.enter_fairy_road("test_door_1")

        summary = engine.get_travel_summary()

        assert summary["active"] is True
        assert summary["road_id"] == "test_road"
        assert summary["road_name"] == "The Test Road"
        assert summary["phase"] == "traveling"
        assert summary["segment"] == 0
        assert summary["total_segments"] == 3


# =============================================================================
# STATE MACHINE INTEGRATION TESTS
# =============================================================================


class TestFairyRoadStateMachine:
    """Tests for state machine integration."""

    def test_fairy_road_travel_state_exists(self):
        """Test that FAIRY_ROAD_TRAVEL state exists."""
        assert hasattr(GameState, "FAIRY_ROAD_TRAVEL")
        assert GameState.FAIRY_ROAD_TRAVEL.value == "fairy_road_travel"

    def test_valid_transitions_from_wilderness(self):
        """Test transition from wilderness to fairy road is valid."""
        from src.game_state.state_machine import StateMachine

        sm = StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)
        assert sm.can_transition("enter_fairy_road")

    def test_valid_transitions_from_fairy_road(self):
        """Test transitions from fairy road are valid."""
        from src.game_state.state_machine import StateMachine

        sm = StateMachine(initial_state=GameState.FAIRY_ROAD_TRAVEL)

        assert sm.can_transition("encounter_triggered")
        assert sm.can_transition("fairy_road_combat")
        assert sm.can_transition("initiate_conversation")
        assert sm.can_transition("exit_fairy_road")

    def test_return_transition_from_encounter(self):
        """Test returning to fairy road from encounter."""
        from src.game_state.state_machine import StateMachine

        sm = StateMachine(initial_state=GameState.FAIRY_ROAD_TRAVEL)
        sm.transition("encounter_triggered")

        assert sm.current_state == GameState.ENCOUNTER
        assert sm.previous_state == GameState.FAIRY_ROAD_TRAVEL

        # Return to fairy road
        sm.transition("encounter_end_fairy_road")
        assert sm.current_state == GameState.FAIRY_ROAD_TRAVEL


# =============================================================================
# ENCOUNTER ENGINE INTEGRATION TESTS
# =============================================================================


class TestFairyRoadEncounterIntegration:
    """Tests for encounter engine integration."""

    def test_encounter_origin_fairy_road_exists(self):
        """Test that FAIRY_ROAD origin exists."""
        from src.encounter.encounter_engine import EncounterOrigin

        assert hasattr(EncounterOrigin, "FAIRY_ROAD")
        assert EncounterOrigin.FAIRY_ROAD.value == "fairy_road"
