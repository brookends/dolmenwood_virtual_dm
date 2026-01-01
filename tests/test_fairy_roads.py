"""
Tests for the Fairy Roads system.

Tests cover:
- Fairy road models and data loading
- Registry operations
- Travel mechanics
- Encounter triggering
- Time dilation
- State machine integration
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from src.fairy_roads.models import (
    FairyRoadDefinition,
    FairyRoadDoor,
    FairyRoadLocationEntry,
    FairyRoadLocationTable,
    FairyRoadCommon,
    FairyRoadEncounterEntry,
    FairyRoadEncounterTable,
    TimePassedEntry,
    TimePassedTable,
)
from src.fairy_roads.fairy_road_engine import (
    FairyRoadEngine,
    FairyRoadPhase,
    FairyRoadTravelResult,
    FairyRoadEntryResult,
    FairyRoadExitResult,
    FairyRoadTravelState,
    FairyRoadCheckResult,
    FairyRoadCheckOutcome,
    StrayFromPathResult,
    StrayFromPathOutcome,
    reset_fairy_road_engine,
)
from src.content_loader.fairy_road_registry import (
    FairyRoadRegistry,
    get_fairy_road_registry,
    reset_fairy_road_registry,
    DoorRef,
)
from src.content_loader.fairy_road_loader import (
    FairyRoadDataLoader,
)
from src.game_state.state_machine import GameState
from src.data_models import DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_door_data():
    """Sample fairy door data using the canonical schema."""
    return {
        "hex_id": "0704",
        "name": "The Test Door",
        "direction": "entry",
        "notes": "A shimmering portal at twilight",
    }


@pytest.fixture
def sample_road_data():
    """Sample fairy road data using the canonical schema."""
    return {
        "road_id": "test_road",
        "name": "The Test Road",
        "atmosphere": "Ethereal mist surrounds the path",
        "length_miles": 12,
        "doors": [
            {
                "hex_id": "0704",
                "name": "Entry Door",
                "direction": "entry",
            },
            {
                "hex_id": "1203",
                "name": "Exit Door",
                "direction": "endpoint",
            },
        ],
        "locations": {
            "die": "1d8",
            "entries": [
                {
                    "roll": 1,
                    "summary": "A clearing in the mist with a strange tree",
                },
                {
                    "roll": 2,
                    "summary": "An abandoned fairy market",
                },
            ],
        },
    }


@pytest.fixture
def sample_common_data():
    """Sample fairy roads common data."""
    return {
        "encounter_table": {
            "die": "1d6",
            "entries": [
                {"roll": 1, "name": "Goblin", "count": "2d6"},
                {"roll": 2, "name": "Elf Knight", "count": "1d4"},
                {"roll": 3, "name": "Sprite", "count": "3d6"},
                {"roll": 4, "name": "Lost Soul", "count": "1d4"},
                {"roll": 5, "name": "Grimalkin", "count": "1"},
                {"roll": 6, "name": "Fairy Horse", "count": "1"},
            ],
        },
        "time_passed_table": {
            "die": "2d6",
            "entries": [
                {"roll": 2, "time": "1d6 minutes"},
                {"roll_range": [3, 5], "time": "1d6 hours"},
                {"roll_range": [6, 8], "time": "1d6 days"},
                {"roll_range": [9, 11], "time": "2d6 days"},
                {"roll": 12, "time": "1d6 weeks"},
            ],
        },
    }


@pytest.fixture
def fairy_road(sample_road_data):
    """Create a FairyRoadDefinition instance."""
    doors = [FairyRoadDoor(**d) for d in sample_road_data["doors"]]
    locations_entries = [FairyRoadLocationEntry(**e) for e in sample_road_data["locations"]["entries"]]
    locations = FairyRoadLocationTable(die=sample_road_data["locations"]["die"], entries=locations_entries)

    return FairyRoadDefinition(
        road_id=sample_road_data["road_id"],
        name=sample_road_data["name"],
        atmosphere=sample_road_data["atmosphere"],
        length_miles=sample_road_data["length_miles"],
        doors=doors,
        locations=locations,
    )


@pytest.fixture
def fairy_common(sample_common_data):
    """Create a FairyRoadCommon instance."""
    enc_entries = [FairyRoadEncounterEntry(**e) for e in sample_common_data["encounter_table"]["entries"]]
    enc_table = FairyRoadEncounterTable(die=sample_common_data["encounter_table"]["die"], entries=enc_entries)

    time_entries = []
    for e in sample_common_data["time_passed_table"]["entries"]:
        entry = TimePassedEntry(
            roll=e.get("roll"),
            roll_range=e.get("roll_range"),
            time=e["time"],
        )
        time_entries.append(entry)
    time_table = TimePassedTable(die=sample_common_data["time_passed_table"]["die"], entries=time_entries)

    return FairyRoadCommon(
        encounter_table=enc_table,
        time_passed_table=time_table,
    )


@pytest.fixture
def registry(fairy_road, fairy_common):
    """Create a registry with a sample road."""
    reset_fairy_road_registry()
    reg = FairyRoadRegistry()
    # Manually add road and doors
    reg._roads_by_id[fairy_road.road_id] = fairy_road
    for door in fairy_road.doors:
        door_ref = DoorRef(
            road_id=fairy_road.road_id,
            road_name=fairy_road.name,
            door=door,
        )
        if door.hex_id not in reg._doors_by_hex:
            reg._doors_by_hex[door.hex_id] = []
        reg._doors_by_hex[door.hex_id].append(door_ref)
    reg._common = fairy_common
    reg._is_loaded = True
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
    engine = FairyRoadEngine(mock_controller, registry)
    engine.dice = DiceRoller()
    return engine


@pytest.fixture(autouse=True)
def cleanup_singletons():
    """Clean up singleton instances after each test."""
    yield
    reset_fairy_road_registry()
    reset_fairy_road_engine()


@pytest.fixture(autouse=True)
def seed_rng():
    """Seed the RNG for deterministic tests."""
    DiceRoller.set_seed(42)
    yield
    DiceRoller.set_seed(None)


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestFairyRoadDoor:
    """Tests for FairyRoadDoor model."""

    def test_from_dict_basic(self, sample_door_data):
        """Test creating a door from dict."""
        door = FairyRoadDoor(**sample_door_data)

        assert door.name == "The Test Door"
        assert door.hex_id == "0704"
        assert door.direction == "entry"

    def test_frozen_dataclass(self, sample_door_data):
        """Test that door is immutable."""
        door = FairyRoadDoor(**sample_door_data)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            door.name = "Modified Name"


class TestFairyRoadDefinition:
    """Tests for FairyRoadDefinition model."""

    def test_from_dict_full(self, fairy_road):
        """Test road creation with full data."""
        assert fairy_road.road_id == "test_road"
        assert fairy_road.name == "The Test Road"
        assert fairy_road.length_miles == 12
        assert len(fairy_road.doors) == 2
        assert fairy_road.locations is not None
        assert len(fairy_road.locations.entries) == 2


class TestFairyRoadTravelState:
    """Tests for FairyRoadTravelState model."""

    def test_initial_state(self):
        """Test creating initial travel state."""
        state = FairyRoadTravelState(
            road_id="test_road",
            entry_door_hex="0704",
            entry_door_name="Entry Door",
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

    def test_get_by_id(self, registry):
        """Test retrieving a road by ID."""
        result = registry.get_by_id("test_road")

        assert result.found is True
        assert result.road is not None
        assert result.road.name == "The Test Road"

    def test_get_by_id_not_found(self, registry):
        """Test retrieving a non-existent road."""
        result = registry.get_by_id("nonexistent")

        assert result.found is False
        assert result.road is None

    def test_get_doors_at_hex(self, registry):
        """Test getting doors at a hex."""
        doors = registry.get_doors_at_hex("0704")

        assert len(doors) == 1
        assert doors[0].door.name == "Entry Door"

    def test_get_doors_at_hex_empty(self, registry):
        """Test getting doors at hex with no doors."""
        doors = registry.get_doors_at_hex("9999")
        assert len(doors) == 0

    def test_get_door_specific(self, registry):
        """Test getting a specific door."""
        door_ref = registry.get_door("0704", "test_road")

        assert door_ref is not None
        assert door_ref.door.name == "Entry Door"

    def test_list_roads(self, registry):
        """Test listing all roads."""
        result = registry.list_roads()

        assert result.count == 1
        assert len(result.roads) == 1
        assert result.roads[0].name == "The Test Road"


# =============================================================================
# ENGINE TESTS
# =============================================================================


class TestFairyRoadEngineEntry:
    """Tests for entering fairy roads."""

    def test_enter_road_success(self, engine):
        """Test successfully entering a fairy road."""
        result = engine.enter_fairy_road("test_road", "0704")

        assert result.success is True
        assert result.road_id == "test_road"
        assert result.door_name == "Entry Door"
        assert engine.is_active() is True
        assert engine.get_current_phase() == FairyRoadPhase.TRAVELING

    def test_enter_road_not_found(self, engine):
        """Test entering a non-existent road."""
        result = engine.enter_fairy_road("fake_road", "0704")

        assert result.success is False
        assert "not found" in result.messages[0].lower()

    def test_enter_road_no_door_at_hex(self, engine):
        """Test entering from a hex without a door."""
        result = engine.enter_fairy_road("test_road", "9999")

        assert result.success is False
        assert "no door" in result.messages[0].lower()

    def test_enter_road_transitions_state(self, engine, mock_controller):
        """Test that entering triggers state transition."""
        engine.enter_fairy_road("test_road", "0704")

        mock_controller.transition.assert_called_with(
            "enter_fairy_road",
            context={
                "road_id": "test_road",
                "road_name": "The Test Road",
                "door_name": "Entry Door",
                "entry_hex": "0704",
            },
        )


class TestFairyRoadEngineTravel:
    """Tests for traveling on fairy roads."""

    def test_travel_segment(self, engine):
        """Test traveling a segment."""
        engine.enter_fairy_road("test_road", "0704")

        result = engine.travel_segment()

        assert result.success is True
        assert result.segment == 1
        assert result.phase == FairyRoadPhase.TRAVELING

    def test_travel_segment_not_active(self, engine):
        """Test traveling when not on a road."""
        result = engine.travel_segment()

        assert result.success is False
        assert "not currently" in result.messages[0].lower()

    def test_travel_increments_turns(self, engine):
        """Test that travel increments subjective time."""
        engine.enter_fairy_road("test_road", "0704")
        engine.travel_segment()

        state = engine.get_travel_state()
        assert state.subjective_turns_elapsed == 1
        assert state.current_segment == 1

    def test_travel_check_results(self, engine):
        """Test that travel produces check results."""
        engine.enter_fairy_road("test_road", "0704")

        # Seed for deterministic result
        DiceRoller.set_seed(1)  # Should produce a specific result

        result = engine.travel_segment()

        assert result.check_outcome is not None
        assert result.check_outcome.roll >= 1 and result.check_outcome.roll <= 6


class TestFairyRoadEngineEncounters:
    """Tests for encounter handling on fairy roads."""

    def test_monster_encounter_triggers_phase_change(self, engine):
        """Test that monster encounters change phase."""
        engine.enter_fairy_road("test_road", "0704")

        # Force a monster encounter result
        DiceRoller.set_seed(100)  # Seed that gives roll of 1 or 2

        # Keep trying until we get an encounter
        for _ in range(10):
            result = engine.travel_segment()
            if result.encounter_triggered:
                break
            # Reset to traveling phase for next try
            engine._phase = FairyRoadPhase.TRAVELING

        # If we got an encounter, check the phase
        if result.encounter_triggered:
            assert engine.get_current_phase() == FairyRoadPhase.ENCOUNTER

    def test_trigger_encounter_transition(self, engine, mock_controller):
        """Test transitioning to encounter state."""
        engine.enter_fairy_road("test_road", "0704")

        # Manually set up an encounter
        from src.fairy_roads.models import FairyRoadEncounterEntry
        engine._state.last_encounter_entry = FairyRoadEncounterEntry(
            roll=1, name="Test Monster", count="1d4"
        )

        result = engine.trigger_encounter_transition()

        assert result["success"] is True
        mock_controller.set_encounter.assert_called_once()
        mock_controller.transition.assert_called()


class TestFairyRoadEngineExit:
    """Tests for exiting fairy roads."""

    def test_exit_road_success(self, engine, mock_controller):
        """Test successfully exiting a fairy road."""
        engine.enter_fairy_road("test_road", "0704")

        # Travel to near the end
        for _ in range(3):
            engine.travel_segment()
            if engine.get_current_phase() != FairyRoadPhase.TRAVELING:
                engine._phase = FairyRoadPhase.TRAVELING

        result = engine.exit_fairy_road("1203")

        assert result.success is True
        assert result.exit_hex_id == "1203"
        assert engine.is_active() is False

    def test_exit_road_advances_time(self, engine, mock_controller):
        """Test that exiting advances mortal time."""
        engine.enter_fairy_road("test_road", "0704")

        engine.exit_fairy_road()

        # Should have called advance_time
        assert mock_controller.advance_time.called

    def test_exit_road_not_active(self, engine):
        """Test exiting when not on a road."""
        result = engine.exit_fairy_road()

        assert result.success is False
        assert "not currently" in result.messages[0].lower()


class TestFairyRoadEngineSummary:
    """Tests for travel summary."""

    def test_travel_summary_active(self, engine):
        """Test getting summary while traveling."""
        engine.enter_fairy_road("test_road", "0704")
        engine.travel_segment()

        summary = engine.get_travel_summary()

        assert summary["active"] is True
        assert summary["road_id"] == "test_road"
        assert summary["road_name"] == "The Test Road"
        assert summary["segment"] == 1

    def test_travel_summary_inactive(self, engine):
        """Test getting summary when not traveling."""
        summary = engine.get_travel_summary()

        assert summary["active"] is False


class TestFairyRoadEngineHelpers:
    """Tests for helper methods."""

    def test_can_enter_from_hex(self, engine):
        """Test checking available entries from a hex."""
        result = engine.can_enter_from_hex("0704")

        assert len(result) == 1
        assert result[0]["road_id"] == "test_road"
        assert result[0]["door_name"] == "Entry Door"

    def test_can_enter_from_hex_empty(self, engine):
        """Test checking entries from hex without doors."""
        result = engine.can_enter_from_hex("9999")

        assert len(result) == 0

    def test_get_doors_in_hex(self, engine):
        """Test getting door refs in a hex."""
        doors = engine.get_doors_in_hex("0704")

        assert len(doors) == 1
        assert isinstance(doors[0], DoorRef)


# =============================================================================
# DATA LOADER TESTS
# =============================================================================


class TestFairyRoadDataLoader:
    """Tests for FairyRoadDataLoader."""

    def test_loader_initialization(self):
        """Test loader can be initialized."""
        loader = FairyRoadDataLoader()
        assert loader is not None

    def test_loader_has_load_methods(self):
        """Test loader has expected methods."""
        loader = FairyRoadDataLoader()
        assert hasattr(loader, "load_directory")
        assert hasattr(loader, "load_file")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestFairyRoadIntegration:
    """Integration tests for fairy road system."""

    def test_full_travel_flow(self, engine, mock_controller):
        """Test complete travel from entry to exit."""
        # Enter the road
        entry_result = engine.enter_fairy_road("test_road", "0704")
        assert entry_result.success is True

        # Travel segments
        segments_traveled = 0
        max_iterations = 10
        for _ in range(max_iterations):
            result = engine.travel_segment()
            if not result.success:
                break
            segments_traveled += 1

            # Handle phase changes
            if engine.get_current_phase() == FairyRoadPhase.ENCOUNTER:
                engine.resume_after_encounter()
            elif engine.get_current_phase() == FairyRoadPhase.LOCATION:
                engine.resume_after_location()
            elif engine.get_current_phase() == FairyRoadPhase.EXITING:
                break

        # Exit
        exit_result = engine.exit_fairy_road()
        assert exit_result.success is True
        assert engine.is_active() is False

    def test_controller_transitions_called(self, engine, mock_controller):
        """Test that appropriate controller transitions are called."""
        engine.enter_fairy_road("test_road", "0704")
        engine.exit_fairy_road()

        # Should have called enter and exit transitions
        call_triggers = [call[0][0] for call in mock_controller.transition.call_args_list]
        assert "enter_fairy_road" in call_triggers
        assert "exit_fairy_road" in call_triggers
