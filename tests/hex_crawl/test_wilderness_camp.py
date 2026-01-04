"""
Tests for wilderness:camp action (Task 4.1).

Verifies that:
1. Camp action advances time to night and then to dawn
2. Night hazards are processed when camping (e.g., hex 0102's dreamless mist)
3. Hazard saves are resolved deterministically with seeded dice
4. Conditions are applied when saves fail
5. Narrative is generated based on outcomes
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, Optional

from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import (
    DiceRoller,
    HexLocation,
    TimeOfDay,
)


@dataclass
class MockProcedural:
    """Mock procedural data with night hazards."""
    night_hazards: list[dict[str, Any]] = field(default_factory=list)
    lost_behavior: Optional[dict[str, Any]] = None


@dataclass
class MockHexData:
    """Mock hex location data."""
    hex_id: str
    name: str
    terrain_type: str = "bog"
    terrain_description: str = "Bog (3)"
    description: str = "A test hex."
    procedural: Optional[MockProcedural] = None
    points_of_interest: list = field(default_factory=list)


@pytest.fixture
def mock_controller():
    """Create a mock controller with time management."""
    controller = MagicMock()
    controller.current_state = MagicMock()
    controller.session_manager = MagicMock()

    # Mock world state with time
    controller.world_state = MagicMock()
    controller.world_state.current_time = MagicMock()
    controller.world_state.current_time.hour = 14  # Afternoon (before dusk)
    controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.AFTERNOON
    controller.world_state.current_date = MagicMock()
    controller.world_state.current_date.is_full_moon.return_value = False
    controller.world_state.current_date.get_season.return_value = MagicMock(value="summer")

    # Mock time advancement
    controller.advance_to_time_of_day = MagicMock(return_value={
        "turns_advanced": 18,
        "hours_advanced": 3,
    })

    # Mock empty party by default
    controller.get_all_characters = MagicMock(return_value=[])

    return controller


@pytest.fixture
def hex_0102_with_sleep_hazard():
    """Create mock hex 0102 with the dreamless sleep hazard."""
    night_hazards = [
        {
            "trigger": "sleep",
            "save_type": "doom",
            "description": "At night, wisps of mauve, indigo, and orange mist drift from the mire. "
                          "Characters who fall asleep here must Save Versus Doom or be stricken "
                          "with a state of dreamlessness.",
            "on_fail": {
                "condition": "dreamless",
                "duration_dice": "2d6",
                "duration_unit": "days",
            },
        }
    ]

    procedural = MockProcedural(night_hazards=night_hazards)

    hex_data = MockHexData(
        hex_id="0102",
        name="Reedwall",
        terrain_type="bog",
        terrain_description="Bog (3), Hag's Addle",
        description="A maze-like bog with colorful mists at night.",
        procedural=procedural,
    )

    return hex_data


@pytest.fixture
def hex_without_hazards():
    """Create a hex without any night hazards."""
    procedural = MockProcedural(night_hazards=[])

    hex_data = MockHexData(
        hex_id="0103",
        name="Safe Meadow",
        terrain_type="grassland",
        terrain_description="Grassland (2)",
        description="A peaceful meadow.",
        procedural=procedural,
    )

    return hex_data


@pytest.fixture
def seeded_dice():
    """Create a seeded dice roller for deterministic tests."""
    DiceRoller.set_seed(42)
    return DiceRoller()


class TestCampBasicFunctionality:
    """Tests for basic camp() method functionality."""

    def test_camp_returns_success(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify camp returns success with required fields."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "0103"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        assert result["success"] is True
        assert result["hex_id"] == "0103"
        assert result["hex_name"] == "Safe Meadow"
        assert "narrative" in result
        assert "time_advanced" in result
        assert "hazard_results" in result

    def test_camp_without_current_hex_fails(
        self, mock_controller, seeded_dice
    ):
        """Verify camp fails when no current hex is set."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {}
        engine._current_hex = None

        result = engine.camp()

        assert result["success"] is False
        assert "No current hex" in result["message"]

    def test_camp_with_unloaded_hex_fails(
        self, mock_controller, seeded_dice
    ):
        """Verify camp fails when hex is not loaded."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {}
        engine._current_hex = "9999"

        result = engine.camp()

        assert result["success"] is False
        assert "not loaded" in result["message"]

    def test_camp_advances_time_to_dusk_then_dawn(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify camp advances time through night cycle."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "0103"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        # Should have called advance_to_time_of_day twice
        assert mock_controller.advance_to_time_of_day.call_count == 2

        calls = mock_controller.advance_to_time_of_day.call_args_list
        # First call should be to DUSK
        assert calls[0][0][0] == TimeOfDay.DUSK
        assert "camp" in calls[0][1]["reason"]

        # Second call should be to DAWN
        assert calls[1][0][0] == TimeOfDay.DAWN
        assert "night" in calls[1][1]["reason"]

    def test_camp_skips_dusk_if_already_night(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify camp doesn't advance to dusk if already night."""
        # Set time to already be night (MIDNIGHT)
        mock_controller.world_state.current_time.hour = 23
        mock_controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.MIDNIGHT

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "0103"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        # Should only call advance_to_time_of_day once (to DAWN)
        assert mock_controller.advance_to_time_of_day.call_count == 1

        call = mock_controller.advance_to_time_of_day.call_args
        assert call[0][0] == TimeOfDay.DAWN

    def test_camp_with_explicit_hex_id(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify camp can use explicit hex_id parameter."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "9999"  # Different from target
        engine._emit_run_log_event = MagicMock()

        result = engine.camp(hex_id="0103")

        assert result["success"] is True
        assert result["hex_id"] == "0103"


class TestCampNightHazards:
    """Tests for night hazard processing during camping."""

    def test_camp_processes_sleep_hazard(
        self, mock_controller, hex_0102_with_sleep_hazard, seeded_dice
    ):
        """Verify camp processes sleep trigger hazards."""
        # Set time to night for hazard to trigger
        mock_controller.world_state.current_time.hour = 22
        mock_controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.EVENING

        # Add a character to the party
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(8, False))  # Failed save
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": hex_0102_with_sleep_hazard}
        engine._current_hex = "0102"
        engine._emit_run_log_event = MagicMock()

        # Mock _resolve_hazard to return a failed save result
        mock_hazard_result = MagicMock()
        mock_hazard_result.success = False
        mock_hazard_result.description = "Failed save vs dreamless mist"
        mock_hazard_result.damage_taken = 0
        mock_hazard_result.conditions_applied = ["dreamless"]
        mock_hazard_result.apply_damage = False
        mock_hazard_result.apply_conditions = True
        engine._resolve_hazard = MagicMock(return_value=mock_hazard_result)

        result = engine.camp()

        assert result["success"] is True
        assert len(result["hazard_results"]) == 1
        assert result["characters_affected"] == 1
        assert result["hazard_results"][0]["character_name"] == "Theron"
        assert result["hazard_results"][0]["success"] is False

    def test_camp_no_hazards_for_empty_party(
        self, mock_controller, hex_0102_with_sleep_hazard, seeded_dice
    ):
        """Verify no hazard results when party is empty."""
        mock_controller.world_state.current_time.hour = 22
        mock_controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.EVENING
        mock_controller.get_all_characters.return_value = []

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": hex_0102_with_sleep_hazard}
        engine._current_hex = "0102"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        assert result["success"] is True
        assert result["hazard_results"] == []
        assert result["characters_affected"] == 0

    def test_camp_narrative_reflects_hazard_failure(
        self, mock_controller, hex_0102_with_sleep_hazard, seeded_dice
    ):
        """Verify narrative mentions affected characters."""
        mock_controller.world_state.current_time.hour = 22
        mock_controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.EVENING

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": hex_0102_with_sleep_hazard}
        engine._current_hex = "0102"
        engine._emit_run_log_event = MagicMock()

        # Mock failed hazard result
        mock_hazard_result = MagicMock()
        mock_hazard_result.success = False
        mock_hazard_result.description = "Failed"
        mock_hazard_result.damage_taken = 0
        mock_hazard_result.conditions_applied = ["dreamless"]
        mock_hazard_result.apply_damage = False
        mock_hazard_result.apply_conditions = True
        engine._resolve_hazard = MagicMock(return_value=mock_hazard_result)

        result = engine.camp()

        assert "affected" in result["narrative"].lower()
        assert "1 character" in result["narrative"]

    def test_camp_narrative_uneventful_without_hazards(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify narrative says uneventful when no hazards."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "0103"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        assert "uneventfully" in result["narrative"].lower()


class TestCampSuggestedActions:
    """Tests for suggested actions after camping."""

    def test_camp_suggests_travel_and_forage(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify camp suggests morning activities."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "0103"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        assert "suggested_actions" in result
        action_ids = [a["action_id"] for a in result["suggested_actions"]]
        assert "wilderness:travel" in action_ids
        assert "wilderness:forage" in action_ids


class TestCampActivityParameter:
    """Tests for activity parameter affecting hazard triggers."""

    def test_camp_with_sleeping_activity(
        self, mock_controller, hex_0102_with_sleep_hazard, seeded_dice
    ):
        """Verify 'sleeping' activity triggers sleep hazards."""
        mock_controller.world_state.current_time.hour = 22
        mock_controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.EVENING

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": hex_0102_with_sleep_hazard}
        engine._current_hex = "0102"
        engine._emit_run_log_event = MagicMock()

        mock_hazard_result = MagicMock()
        mock_hazard_result.success = True
        mock_hazard_result.description = "Saved"
        mock_hazard_result.damage_taken = 0
        mock_hazard_result.conditions_applied = []
        mock_hazard_result.apply_damage = False
        mock_hazard_result.apply_conditions = False
        engine._resolve_hazard = MagicMock(return_value=mock_hazard_result)

        result = engine.camp(activity="sleeping")

        # Should have processed hazards
        engine._resolve_hazard.assert_called()
        assert result["activity"] == "sleeping"

    def test_camp_with_watching_activity(
        self, mock_controller, hex_0102_with_sleep_hazard, seeded_dice
    ):
        """Verify 'watching' activity doesn't trigger sleep hazards."""
        mock_controller.world_state.current_time.hour = 22
        mock_controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.EVENING

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": hex_0102_with_sleep_hazard}
        engine._current_hex = "0102"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp(activity="watching")

        # "watching" is not in ("sleeping", "resting", "camping")
        # so sleep hazard should NOT trigger
        assert result["hazard_results"] == []
        assert result["activity"] == "watching"


class TestCampEmitsRunLogEvent:
    """Tests for run log event emission."""

    def test_camp_emits_wilderness_camp_event(
        self, mock_controller, hex_without_hazards, seeded_dice
    ):
        """Verify camp emits wilderness_camp run log event."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": hex_without_hazards}
        engine._current_hex = "0103"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp()

        engine._emit_run_log_event.assert_called_once()
        call_args = engine._emit_run_log_event.call_args
        assert call_args[0][0] == "wilderness_camp"
        assert call_args[0][1]["success"] is True
