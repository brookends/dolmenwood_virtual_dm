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
