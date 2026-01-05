"""
Tests for hex 0101's transported hazard effect (Task 1).

Verifies that:
1. Sleeping in hex 0101 can trigger the "transported" effect
2. The "transported" condition is handled as a special effect, not a ConditionType
3. Characters failing the save are transported to "The Spectral Manse"
4. The _current_poi is updated to the destination
5. The wilderness:camp action reports transportation correctly
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, Optional

from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import (
    DiceRoller,
    TimeOfDay,
)


@dataclass
class MockProcedural:
    """Mock procedural data with night hazards."""
    night_hazards: list[dict[str, Any]] = field(default_factory=list)
    lost_behavior: Optional[dict[str, Any]] = None


@dataclass
class MockPOI:
    """Mock point of interest."""
    name: str
    poi_type: str = "manse"
    is_dungeon: bool = True
    description: str = "A spectral manor."


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

    # Mock world state with time (night)
    controller.world_state = MagicMock()
    controller.world_state.current_time = MagicMock()
    controller.world_state.current_time.hour = 22  # Night time
    controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.EVENING
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
def hex_0101_with_transport_hazard():
    """Create mock hex 0101 with the Spectral Manse transport hazard."""
    night_hazards = [
        {
            "trigger": "sleep",
            "save_type": "spell",
            "description": "At night, the veil between worlds grows thin. Characters who sleep "
                          "in this hex may find themselves drawn toward the Spectral Manse in "
                          "their dreams, and must Save Versus Spell or awaken within the manse itself.",
            "on_fail": {
                "condition": "transported",
                "destination": "The Spectral Manse",
                "duration_unit": "until_escape",
            },
        }
    ]

    procedural = MockProcedural(night_hazards=night_hazards)

    pois = [MockPOI(name="The Spectral Manse", poi_type="manse", is_dungeon=True)]

    hex_data = MockHexData(
        hex_id="0101",
        name="The Spectral Manse",
        terrain_type="bog",
        terrain_description="Bog (3), Northern Scratch",
        description="A barren expanse of stagnant pools. The keening wind carries strains of distant violin music.",
        procedural=procedural,
        points_of_interest=pois,
    )

    return hex_data


@pytest.fixture
def seeded_dice():
    """Create a seeded dice roller for deterministic tests."""
    DiceRoller.set_seed(42)
    return DiceRoller()


class TestTransportedEffectHandling:
    """Tests for transported effect being handled as special effect, not condition."""

    def test_transported_is_not_condition(self, mock_controller, hex_0101_with_transport_hazard, seeded_dice):
        """Verify transported is handled as special effect, not added as condition."""
        # Add a character to the party
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed save
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp(activity="sleeping")

        # Verify hazard was processed
        assert len(result["hazard_results"]) == 1
        hazard_result = result["hazard_results"][0]

        # Verify transported was detected
        assert hazard_result.get("transported_to") == "The Spectral Manse"

        # Verify apply_condition was NOT called with "transported"
        # (transported should be handled as special effect)
        for call in mock_controller.apply_condition.call_args_list:
            # If apply_condition was called, the condition should not be "transported"
            if len(call[0]) >= 2:
                condition_arg = call[0][1]
                if hasattr(condition_arg, "condition_type"):
                    assert str(condition_arg.condition_type) != "transported"

    def test_transported_updates_current_poi(self, mock_controller, hex_0101_with_transport_hazard, seeded_dice):
        """Verify transported effect updates _current_poi to destination."""
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(3, False))  # Failed save
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._current_poi = None
        engine._emit_run_log_event = MagicMock()

        engine.camp(activity="sleeping")

        # Verify _current_poi was updated to destination
        assert engine._current_poi == "The Spectral Manse"

    def test_transported_in_hazard_results(self, mock_controller, hex_0101_with_transport_hazard, seeded_dice):
        """Verify transported destination is included in hazard results."""
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(4, False))  # Failed save
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._emit_run_log_event = MagicMock()

        result = engine.camp(activity="sleeping")

        hazard_result = result["hazard_results"][0]
        assert hazard_result["transported_to"] == "The Spectral Manse"
        assert "special_effects" in hazard_result
        assert any(e["type"] == "transported" for e in hazard_result["special_effects"])

    def test_successful_save_no_transport(self, mock_controller, hex_0101_with_transport_hazard, seeded_dice):
        """Verify successful save does not transport character."""
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(18, True))  # Successful save
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._current_poi = None
        engine._emit_run_log_event = MagicMock()

        result = engine.camp(activity="sleeping")

        hazard_result = result["hazard_results"][0]
        assert hazard_result["success"] is True
        assert "transported_to" not in hazard_result
        assert engine._current_poi is None  # Should not have been updated


class TestApplyHazardEffectsTransported:
    """Tests for _apply_hazard_effects handling of transported."""

    def test_apply_hazard_effects_handles_transported(self, mock_controller, seeded_dice):
        """Verify _apply_hazard_effects correctly processes transported condition."""
        from src.narrative.hazard_resolver import HazardResult, HazardType, ActionType

        engine = HexCrawlEngine(controller=mock_controller)
        engine._current_poi = None

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"

        hazard_data = {
            "on_fail": {
                "condition": "transported",
                "destination": "The Spectral Manse",
            }
        }

        # Create a HazardResult with transported condition
        result = HazardResult(
            success=False,
            hazard_type=HazardType.ENVIRONMENTAL,
            action_type=ActionType.UNKNOWN,
            description="Drawn into the manse in your dreams",
            conditions_applied=["transported"],
            apply_conditions=[("test_char_1", "transported")],
        )

        applied = engine._apply_hazard_effects(result, mock_char, hazard_data)

        # Verify special_effects contains transported
        assert "special_effects" in applied
        assert len(applied["special_effects"]) == 1
        assert applied["special_effects"][0]["type"] == "transported"
        assert applied["special_effects"][0]["destination"] == "The Spectral Manse"

        # Verify _current_poi was updated
        assert engine._current_poi == "The Spectral Manse"

        # Verify transported was NOT added to conditions_applied
        # (it should skip the condition creation for transported)
        for cond in applied["conditions_applied"]:
            if isinstance(cond, dict):
                assert cond.get("condition_type") != "transported"

    def test_apply_hazard_effects_no_destination_skips_transport(self, mock_controller, seeded_dice):
        """Verify transported without destination is skipped gracefully."""
        from src.narrative.hazard_resolver import HazardResult, HazardType, ActionType

        engine = HexCrawlEngine(controller=mock_controller)
        engine._current_poi = None

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"

        # No destination in on_fail
        hazard_data = {
            "on_fail": {
                "condition": "transported",
                # No destination!
            }
        }

        result = HazardResult(
            success=False,
            hazard_type=HazardType.ENVIRONMENTAL,
            action_type=ActionType.UNKNOWN,
            description="Something went wrong",
            conditions_applied=["transported"],
            apply_conditions=[("test_char_1", "transported")],
        )

        applied = engine._apply_hazard_effects(result, mock_char, hazard_data)

        # Verify special_effects is empty (no destination = no transport)
        assert applied["special_effects"] == []

        # Verify _current_poi was NOT updated
        assert engine._current_poi is None


class TestProcessNightHazardsTransported:
    """Tests for process_night_hazards returning transport info."""

    def test_process_night_hazards_includes_transported(
        self, mock_controller, hex_0101_with_transport_hazard, seeded_dice
    ):
        """Verify process_night_hazards includes transported_to in result."""
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"

        results = engine.process_night_hazards("0101", activity="sleeping")

        assert len(results) == 1
        assert results[0]["transported_to"] == "The Spectral Manse"
        assert results[0]["success"] is False

    def test_process_night_hazards_mixed_party(
        self, mock_controller, hex_0101_with_transport_hazard, seeded_dice
    ):
        """Verify mixed save results: some transported, some not."""
        mock_char1 = MagicMock()
        mock_char1.character_id = "char_1"
        mock_char1.name = "Theron"
        mock_char1.make_saving_throw = MagicMock(return_value=(3, False))  # Failed

        mock_char2 = MagicMock()
        mock_char2.character_id = "char_2"
        mock_char2.name = "Elara"
        mock_char2.make_saving_throw = MagicMock(return_value=(18, True))  # Passed

        mock_controller.get_all_characters.return_value = [mock_char1, mock_char2]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"

        results = engine.process_night_hazards("0101", activity="sleeping")

        assert len(results) == 2

        # First character failed - transported
        assert results[0]["character_name"] == "Theron"
        assert results[0]["success"] is False
        assert results[0]["transported_to"] == "The Spectral Manse"

        # Second character passed - not transported
        assert results[1]["character_name"] == "Elara"
        assert results[1]["success"] is True
        assert "transported_to" not in results[1]


class TestWildernessCampActionTransported:
    """Tests for wilderness:camp action handling transported effect."""

    def test_camp_action_reports_transported(
        self, mock_controller, hex_0101_with_transport_hazard, seeded_dice
    ):
        """Verify wilderness:camp action reports transported in response."""
        from src.conversation.action_registry import get_default_registry

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._emit_run_log_event = MagicMock()

        # Create mock VirtualDM
        mock_dm = MagicMock()
        mock_dm.hex_crawl = engine
        mock_dm.hex_crawl.current_hex_id = "0101"

        # Get the registry and execute the camp action
        registry = get_default_registry()
        camp_action = registry.get("wilderness:camp")

        result = camp_action.executor(mock_dm, {"activity": "sleeping"})

        assert result["success"] is True
        assert result.get("transported_to") == "The Spectral Manse"
        assert result.get("current_poi") == "The Spectral Manse"
        assert "Spectral Manse" in result["message"]

    def test_camp_action_message_includes_transported_characters(
        self, mock_controller, hex_0101_with_transport_hazard, seeded_dice
    ):
        """Verify message lists characters who were transported."""
        from src.conversation.action_registry import get_default_registry

        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(3, False))
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._emit_run_log_event = MagicMock()

        mock_dm = MagicMock()
        mock_dm.hex_crawl = engine
        mock_dm.hex_crawl.current_hex_id = "0101"

        registry = get_default_registry()
        camp_action = registry.get("wilderness:camp")

        result = camp_action.executor(mock_dm, {"activity": "sleeping"})

        # Message should mention the transported character
        assert "Theron" in result["message"]
        assert "Transported" in result["message"] or "transported" in result["message"].lower()


class TestCampNoCrashOnTransported:
    """Acceptance test: camping in hex 0101 doesn't crash."""

    def test_camp_0101_no_crash_deterministic(
        self, mock_controller, hex_0101_with_transport_hazard, seeded_dice
    ):
        """
        Acceptance test: Camping in hex 0101 completes without error.

        Seeds dice so save fails, verifies:
        - No exception is raised
        - Response indicates transported
        - current_poi is updated
        """
        mock_char = MagicMock()
        mock_char.character_id = "test_char_1"
        mock_char.name = "Theron"
        mock_char.make_saving_throw = MagicMock(return_value=(2, False))  # Always fails
        mock_controller.get_all_characters.return_value = [mock_char]

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0101": hex_0101_with_transport_hazard}
        engine._current_hex = "0101"
        engine._current_poi = None
        engine._emit_run_log_event = MagicMock()

        # This should NOT raise an exception
        result = engine.camp(activity="sleeping")

        # Verify successful completion
        assert result["success"] is True

        # Verify transported effect was applied
        assert len(result["hazard_results"]) == 1
        assert result["hazard_results"][0]["transported_to"] == "The Spectral Manse"

        # Verify POI was updated
        assert engine._current_poi == "The Spectral Manse"
