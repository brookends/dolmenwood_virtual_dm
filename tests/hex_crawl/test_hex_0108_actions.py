"""
Tests for hex 0108 action resolution - the _resolve_hex_hazard_result helper.

This helper provides consistent narrative + encounter structure for hazard outcomes.
"""

import pytest
from pathlib import Path

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller, GameDate


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0108 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0108_the_cabbage_plot.json"))
    assert result.success, f"Failed to load hex 0108: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0108_engine(pipeline):
    """Create a HexCrawlEngine with hex 0108 loaded."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=1, day=1)
    engine = HexCrawlEngine(controller)
    engine._hex_data["0108"] = pipeline.get_hex("0108")
    return engine


# =============================================================================
# _resolve_hex_hazard_result TESTS
# =============================================================================


class TestResolveHexHazardResult:
    """Test the _resolve_hex_hazard_result helper method."""

    def test_returns_stable_structure_when_not_triggered(self, hex_0108_engine):
        """When hazard not triggered, should return stable structure with suggestions."""
        hazard_result = {
            "triggered": False,
            "description": "Nothing unusual happens.",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        assert result["resolved"] is True
        assert result["hazard_triggered"] is False
        assert result["encounter"] is None
        assert result["narrative"] == "Nothing unusual happens."
        assert isinstance(result["suggested_actions"], list)
        assert len(result["suggested_actions"]) > 0

    def test_returns_stable_structure_when_triggered(self, hex_0108_engine):
        """When hazard triggered, should return stable structure with encounter info."""
        hazard_result = {
            "triggered": True,
            "description": "Murkin's Soldiers arrive!",
            "result": "murkins_soldiers_arrive",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert result["resolved"] is True
        assert result["hazard_triggered"] is True
        assert result["encounter"] is not None
        assert isinstance(result["narrative"], str)
        assert isinstance(result["suggested_actions"], list)
        assert isinstance(result["rolls_made"], list)

    def test_matches_npc_by_partial_id(self, hex_0108_engine):
        """Should match NPC when result contains npc_id (e.g., 'murkins_soldiers_arrive')."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers approach.",
            "result": "murkins_soldiers_arrive",  # Contains "murkins_soldiers"
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert result["encounter"]["type"] == "npc_arrival"
        assert result["encounter"]["npc_id"] == "murkins_soldiers"
        assert result["encounter"]["is_combatant"] is True

    def test_rolls_group_size_for_group_npc(self, hex_0108_engine):
        """Should roll group size when NPC has group_count."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "3-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert result["npc_group"] is not None
        assert result["npc_group"]["is_group"] is True
        assert result["npc_group"]["total_count"] > 0

        # Should have group_size roll recorded
        group_rolls = [r for r in result["rolls_made"] if r["type"] == "group_size"]
        assert len(group_rolls) == 1
        assert group_rolls[0]["expression"] == "1d4+1d4"

    def test_records_hazard_trigger_roll(self, hex_0108_engine):
        """Should record the hazard trigger roll in rolls_made."""
        hazard_result = {
            "triggered": True,
            "description": "Event occurs.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        trigger_rolls = [r for r in result["rolls_made"] if r["type"] == "hazard_trigger"]
        assert len(trigger_rolls) == 1
        assert trigger_rolls[0]["chance"] == "2-in-6"
        assert trigger_rolls[0]["succeeded"] is True

    def test_provides_combat_suggestions_for_combatant_npc(self, hex_0108_engine):
        """Should provide combat-appropriate suggestions for combatant NPCs."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(42)
        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)
        DiceRoller._seed = None

        assert "Prepare for combat" in result["suggested_actions"]
        assert "Attempt to negotiate" in result["suggested_actions"]

    def test_handles_unknown_result_as_event(self, hex_0108_engine):
        """When result doesn't match an NPC, should treat as narrative event."""
        hazard_result = {
            "triggered": True,
            "description": "Strange sounds echo.",
            "result": "unknown_event_id",
            "chance": "1-in-6",
        }
        context = {"hex_id": "0108"}

        result = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        assert result["encounter"]["type"] == "event"
        assert result["encounter"]["event_id"] == "unknown_event_id"
        assert "Investigate further" in result["suggested_actions"]

    def test_deterministic_with_seeded_dice(self, hex_0108_engine):
        """Results should be deterministic with same seed."""
        hazard_result = {
            "triggered": True,
            "description": "Soldiers arrive.",
            "result": "murkins_soldiers",
            "chance": "2-in-6",
        }
        context = {"hex_id": "0108"}

        DiceRoller.set_seed(12345)
        result1 = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        DiceRoller.set_seed(12345)
        result2 = hex_0108_engine._resolve_hex_hazard_result(hazard_result, context)

        DiceRoller._seed = None

        assert result1["npc_group"]["total_count"] == result2["npc_group"]["total_count"]


class TestIntegrationWithHazardChecks:
    """Test _resolve_hex_hazard_result integrates with hazard check methods."""

    def test_resolves_investigation_hazard_result(self, hex_0108_engine):
        """Should properly resolve output from check_investigation_hazard."""
        # Force hazard to trigger
        DiceRoller.set_seed(0)  # Low roll triggers 2-in-6

        hazard_result = hex_0108_engine.check_investigation_hazard(
            "0108", "investigate_cabbages"
        )

        if hazard_result["triggered"]:
            resolution = hex_0108_engine._resolve_hex_hazard_result(
                hazard_result, {"hex_id": "0108", "trigger_type": "investigation"}
            )
            assert resolution["resolved"] is True
            assert resolution["encounter"] is not None

        DiceRoller._seed = None

    def test_resolves_evening_hazard_result(self, hex_0108_engine):
        """Should properly resolve output from check_evening_hazard."""
        # Force hazard to trigger
        DiceRoller.set_seed(0)  # Low roll triggers 3-in-6

        hazard_result = hex_0108_engine.check_evening_hazard(
            "0108", "The Crimson Bath"
        )

        if hazard_result["triggered"]:
            resolution = hex_0108_engine._resolve_hex_hazard_result(
                hazard_result, {"hex_id": "0108", "trigger_type": "evening_stay"}
            )
            assert resolution["resolved"] is True
            assert resolution["encounter"] is not None

        DiceRoller._seed = None


# =============================================================================
# WILDERNESS:INVESTIGATE ACTION TESTS
# =============================================================================


class TestWildernessInvestigateAction:
    """Test the wilderness:investigate action in the action registry."""

    def test_action_registered(self):
        """wilderness:investigate should be registered in the action registry."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")
        assert spec is not None
        assert spec.id == "wilderness:investigate"
        assert spec.label == "Investigate the area"

    def test_action_executor_returns_no_hazard_for_wrong_trigger(self, hex_0108_engine):
        """Executor should return no hazard for non-matching trigger."""
        from unittest.mock import MagicMock

        # Create mock VirtualDM with hex_crawl pointing to our engine
        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        params = {"hex_id": "0108", "trigger": "investigate_trees"}
        result = spec.executor(mock_dm, params)

        assert result["success"] is True
        assert result["hazard_triggered"] is False
        assert "message" in result

    def test_action_executor_returns_hazard_when_triggered(self, hex_0108_engine):
        """Executor should return encounter info when hazard triggers."""
        from unittest.mock import MagicMock, patch

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        # Force hazard to trigger
        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert result["success"] is True
        assert result["hazard_triggered"] is True
        assert result["encounter"] is not None
        assert "message" in result

    def test_action_executor_includes_group_info(self, hex_0108_engine):
        """Executor should include NPC group info when hazard triggers NPC arrival."""
        from unittest.mock import MagicMock, patch

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert result.get("npc_group") is not None
        assert result["npc_group"]["is_group"] is True
        assert result["npc_group"]["total_count"] > 0

    def test_action_executor_includes_suggested_actions(self, hex_0108_engine):
        """Executor should include suggested follow-up actions."""
        from unittest.mock import MagicMock, patch

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine

        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:investigate")

        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            DiceRoller.set_seed(42)
            params = {"hex_id": "0108", "trigger": "investigate_cabbages"}
            result = spec.executor(mock_dm, params)
            DiceRoller._seed = None

        assert "suggested_actions" in result
        assert isinstance(result["suggested_actions"], list)
        assert len(result["suggested_actions"]) > 0


class TestInvestigateSuggestion:
    """Test that wilderness:investigate appears in suggestions for hex 0108."""

    def test_suggestion_appears_for_hex_with_investigation_hazard(self, hex_0108_engine):
        """Suggestion should appear for hex with investigation_hazard."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []

        # get_valid_actions returns empty list
        mock_dm.get_valid_actions.return_value = []

        suggestions = build_suggestions(mock_dm, limit=15)
        action_ids = [s.id for s in suggestions]

        assert "wilderness:investigate" in action_ids

    def test_suggestion_has_correct_trigger(self, hex_0108_engine):
        """Suggestion should have the trigger from the hazard definition."""
        from unittest.mock import MagicMock
        from src.conversation.suggestion_builder import build_suggestions
        from src.game_state.state_machine import GameState

        mock_dm = MagicMock()
        mock_dm.hex_crawl = hex_0108_engine
        mock_dm.current_state = GameState.WILDERNESS_TRAVEL
        mock_dm.controller.party_state.location.location_id = "0108"
        mock_dm.controller.get_active_characters.return_value = []
        mock_dm.controller.get_all_characters.return_value = []
        mock_dm.get_valid_actions.return_value = []

        suggestions = build_suggestions(mock_dm, limit=15)
        investigate_suggestion = next(
            (s for s in suggestions if s.id == "wilderness:investigate"), None
        )

        assert investigate_suggestion is not None
        assert investigate_suggestion.params.get("trigger") == "investigate_cabbages"