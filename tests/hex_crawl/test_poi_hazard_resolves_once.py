"""
Deterministic tests for POI hazard resolution (P9.4).

Verifies that:
1. Hazard resolution creates POI visit state
2. Resolved hazards are tracked in delta state
3. Second resolution attempt returns already_resolved
4. Effects are applied via controller APIs
5. RunLog event is emitted
"""

import pytest
from unittest.mock import MagicMock, patch

from src.hex_crawl.hex_crawl_engine import (
    HexCrawlEngine,
    POIVisit,
    POIExplorationState,
)
from src.data_models import (
    DiceRoller,
    HexLocation,
    PointOfInterest,
)
from src.game_state.global_controller import GlobalController


@pytest.fixture
def mock_controller():
    """Create a mock controller."""
    controller = MagicMock(spec=GlobalController)
    controller.current_state = MagicMock()
    return controller


@pytest.fixture
def test_character():
    """Create a test character (mock for hazard resolution)."""
    char = MagicMock()
    char.character_id = "test_char_1"
    char.name = "Thorfinn"
    char.hp_current = 10
    char.hp_max = 10
    char.armor_class = 14
    return char


@pytest.fixture
def hex_with_hazard_poi():
    """Create hex data with a POI that has approach hazards."""
    poi = PointOfInterest(
        name="Perilous Falls",
        poi_type="natural_feature",
        description="A dangerous waterfall approach",
        hazards=[
            {
                "trigger": "on_approach",
                "hazard_type": "climbing",
                "difficulty": "moderate",
                "description": "Slippery rocks require careful climbing",
                "damage": "1d6",
            },
            {
                "trigger": "on_approach",
                "hazard_type": "swimming",
                "difficulty": "hard",
                "description": "Strong currents threaten to sweep you away",
                "damage": "2d6",
            },
        ],
    )

    hex_data = HexLocation(
        hex_id="0703",
        name="Waterfall Gorge",
        terrain_type="craggy_forest",
        points_of_interest=[poi],
    )
    return hex_data


@pytest.fixture
def hex_crawl_engine(mock_controller, hex_with_hazard_poi, test_character):
    """Create hex crawl engine with test data."""
    DiceRoller.set_seed(42)

    engine = HexCrawlEngine(controller=mock_controller)
    engine._hex_data["0703"] = hex_with_hazard_poi
    engine._current_poi = "Perilous Falls"

    # Disable narrative resolver for basic dice-based testing
    engine.narrative_resolver = None

    # Mock _get_character to return test character
    engine._get_character = MagicMock(return_value=test_character)

    # Mock _log_event
    engine._log_event = MagicMock()

    return engine


class TestHazardResolutionCreatesVisitState:
    """Test that hazard resolution creates POI visit state."""

    def test_creates_poi_visit_on_first_resolution(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify POI visit is created when resolving hazard."""
        visit_key = "0703:Perilous Falls"
        assert visit_key not in hex_crawl_engine._poi_visits

        hex_crawl_engine.resolve_poi_hazard(
            hex_id="0703",
            hazard_index=0,
            character_id="test_char_1",
        )

        assert visit_key in hex_crawl_engine._poi_visits
        assert isinstance(hex_crawl_engine._poi_visits[visit_key], POIVisit)


class TestHazardTrackedInDeltaState:
    """Test that resolved hazards are tracked in delta state."""

    def test_success_marks_hazard_resolved(self, hex_crawl_engine, mock_controller):
        """Verify successful resolution marks hazard as resolved."""
        # Seed dice for success (need roll >= 3 for moderate difficulty)
        DiceRoller.set_seed(12345)  # Produces higher rolls

        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=5)  # Success

            result = hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        assert result["success"] is True
        visit = hex_crawl_engine._poi_visits["0703:Perilous Falls"]
        assert 0 in visit.hazards_resolved

    def test_failure_does_not_mark_hazard_resolved(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify failed resolution does not mark hazard as resolved."""
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=1)  # Failure

            result = hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        assert result["success"] is False
        visit = hex_crawl_engine._poi_visits["0703:Perilous Falls"]
        assert 0 not in visit.hazards_resolved


class TestSecondResolutionReturnsAlreadyResolved:
    """Test that second resolution attempt returns already_resolved."""

    def test_already_resolved_returns_immediately(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify second call returns already_resolved without re-rolling."""
        # First resolution - success
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=5)

            first_result = hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        assert first_result["success"] is True

        # Reset dice mock to track second call
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            second_result = hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

            # Should not have rolled dice
            mock_roll.assert_not_called()

        assert second_result["already_resolved"] is True
        assert second_result["success"] is True
        assert second_result["can_proceed"] is True

    def test_different_hazard_indexes_tracked_separately(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify different hazard indexes are tracked independently."""
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=5)

            # Resolve hazard 0
            hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        # Hazard 1 should still require resolution
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=4)

            result = hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=1,
                character_id="test_char_1",
            )

            # Should have rolled dice for new hazard
            mock_roll.assert_called()

        # Both should be resolved now
        visit = hex_crawl_engine._poi_visits["0703:Perilous Falls"]
        assert 0 in visit.hazards_resolved
        assert 1 in visit.hazards_resolved


class TestEffectsAppliedViaControllerAPIs:
    """Test that damage/conditions are applied via controller APIs."""

    def test_damage_applied_on_failure(self, hex_crawl_engine, mock_controller):
        """Verify damage is applied via controller.apply_damage on failure."""
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            # First roll for hazard check (fail), second for damage
            mock_roll.side_effect = [
                MagicMock(total=1),  # Fail hazard check
                MagicMock(total=4),  # Damage roll
            ]

            hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        # Should have called apply_damage
        mock_controller.apply_damage.assert_called_once_with(
            "test_char_1", 4, "hazard:climbing"
        )

    def test_no_damage_on_success(self, hex_crawl_engine, mock_controller):
        """Verify no damage is applied on successful resolution."""
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=5)

            hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        mock_controller.apply_damage.assert_not_called()


class TestRunLogEventEmitted:
    """Test that RunLog event is emitted on resolution."""

    def test_log_event_called_on_resolution(self, hex_crawl_engine, mock_controller):
        """Verify _log_event is called with correct data."""
        with patch.object(hex_crawl_engine.dice, 'roll') as mock_roll:
            mock_roll.return_value = MagicMock(total=5)

            hex_crawl_engine.resolve_poi_hazard(
                hex_id="0703",
                hazard_index=0,
                character_id="test_char_1",
            )

        hex_crawl_engine._log_event.assert_called_once()
        call_args = hex_crawl_engine._log_event.call_args

        assert call_args[0][0] == "poi_hazard_resolved"
        event_data = call_args[0][1]

        assert event_data["hex_id"] == "0703"
        assert event_data["poi_name"] == "Perilous Falls"
        assert event_data["hazard_index"] == 0
        assert event_data["hazard_type"] == "climbing"
        assert event_data["character_id"] == "test_char_1"
        assert event_data["success"] is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_error_when_not_at_poi(self, hex_crawl_engine, mock_controller):
        """Verify error when not at a POI."""
        hex_crawl_engine._current_poi = None

        result = hex_crawl_engine.resolve_poi_hazard(
            hex_id="0703",
            hazard_index=0,
            character_id="test_char_1",
        )

        assert result["success"] is False
        assert "error" in result

    def test_error_for_invalid_hazard_index(self, hex_crawl_engine, mock_controller):
        """Verify error for out-of-bounds hazard index."""
        result = hex_crawl_engine.resolve_poi_hazard(
            hex_id="0703",
            hazard_index=99,
            character_id="test_char_1",
        )

        assert result["success"] is False
        assert "Invalid hazard index" in result["error"]

    def test_error_for_unknown_hex(self, hex_crawl_engine, mock_controller):
        """Verify error for unknown hex ID."""
        result = hex_crawl_engine.resolve_poi_hazard(
            hex_id="9999",
            hazard_index=0,
            character_id="test_char_1",
        )

        assert result["success"] is False
        assert "Hex not found" in result["error"]
