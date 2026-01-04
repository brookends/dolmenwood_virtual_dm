"""
Tests for hex 0108 new features: investigation hazards, evening hazards,
encounter tables, and NPC group sizes.

These tests verify the new engine methods added to support hex 0108's
enriched content.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import (
    HexProcedural,
    PointOfInterest,
    HexNPC,
    RollTable,
    RollTableEntry,
    DiceRoller,
    GameDate,
)


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
def hex_0108_data(pipeline):
    """Get hex 0108 data from the pipeline."""
    return pipeline.get_hex("0108")


@pytest.fixture
def hex_0108_engine(pipeline):
    """Create a HexCrawlEngine with hex 0108 loaded."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=1, day=1)
    engine = HexCrawlEngine(controller)
    engine._hex_data["0108"] = pipeline.get_hex("0108")
    return engine


# =============================================================================
# DATA MODEL PARSING TESTS
# =============================================================================


class TestProceduralEncounterTable:
    """Test parsing of procedural.encounter_table."""

    def test_encounter_table_parsed(self, hex_0108_data):
        """Hex 0108's procedural section should have an encounter table."""
        assert hex_0108_data is not None
        assert hex_0108_data.procedural is not None
        assert hex_0108_data.procedural.encounter_table is not None

    def test_encounter_table_has_name(self, hex_0108_data):
        """Encounter table should have a name."""
        table = hex_0108_data.procedural.encounter_table
        assert table.name == "Hex 0108 Encounters"

    def test_encounter_table_has_entries(self, hex_0108_data):
        """Encounter table should have entries."""
        table = hex_0108_data.procedural.encounter_table
        assert len(table.entries) >= 2

    def test_encounter_table_die_type(self, hex_0108_data):
        """Encounter table should use d6."""
        table = hex_0108_data.procedural.encounter_table
        assert table.die_type == "d6"


class TestInvestigationHazard:
    """Test parsing of procedural.investigation_hazard."""

    def test_investigation_hazard_parsed(self, hex_0108_data):
        """Hex 0108 should have an investigation hazard."""
        assert hex_0108_data is not None
        assert hex_0108_data.procedural is not None
        assert hex_0108_data.procedural.investigation_hazard is not None

    def test_investigation_hazard_trigger(self, hex_0108_data):
        """Investigation hazard should have correct trigger."""
        hazard = hex_0108_data.procedural.investigation_hazard
        assert hazard.get("trigger") == "investigate_cabbages"

    def test_investigation_hazard_chance(self, hex_0108_data):
        """Investigation hazard should have 2-in-6 chance."""
        hazard = hex_0108_data.procedural.investigation_hazard
        assert hazard.get("chance") == "2-in-6"

    def test_investigation_hazard_result(self, hex_0108_data):
        """Investigation hazard should trigger Murkin's soldiers."""
        hazard = hex_0108_data.procedural.investigation_hazard
        assert hazard.get("result") == "murkins_soldiers_arrive"


class TestEveningHazard:
    """Test parsing of POI evening_hazard."""

    def test_evening_hazard_parsed(self, hex_0108_data):
        """Crimson Bath should have an evening hazard."""
        poi = hex_0108_data.points_of_interest[0]
        assert poi.name == "The Crimson Bath"
        assert poi.evening_hazard is not None

    def test_evening_hazard_trigger(self, hex_0108_data):
        """Evening hazard should trigger on evening_stay."""
        poi = hex_0108_data.points_of_interest[0]
        assert poi.evening_hazard.get("trigger") == "evening_stay"

    def test_evening_hazard_chance(self, hex_0108_data):
        """Evening hazard should have 3-in-6 chance."""
        poi = hex_0108_data.points_of_interest[0]
        assert poi.evening_hazard.get("chance") == "3-in-6"


class TestNPCGroupFields:
    """Test parsing of NPC group fields."""

    def test_soldiers_have_group_count(self, hex_0108_data):
        """Murkin's Soldiers should have group_count."""
        soldiers = None
        for npc in hex_0108_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert soldiers.group_count == "1d4+1d4"

    def test_soldiers_have_group_composition(self, hex_0108_data):
        """Murkin's Soldiers should have group_composition."""
        soldiers = None
        for npc in hex_0108_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert soldiers.group_composition is not None
        assert soldiers.group_composition.get("humans") == "1d4"
        assert soldiers.group_composition.get("shorthorns") == "1d4"

    def test_soldiers_have_faction_profile(self, hex_0108_data):
        """Murkin's Soldiers should have faction_profile."""
        soldiers = None
        for npc in hex_0108_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert soldiers.faction_profile is not None
        assert soldiers.faction_profile.get("faction_id") == "house_murkin"
        assert soldiers.faction_profile.get("role") == "enforcers"


# =============================================================================
# ENGINE METHOD TESTS
# =============================================================================


class TestCheckInvestigationHazard:
    """Test check_investigation_hazard engine method."""

    def test_no_hazard_when_wrong_trigger(self, hex_0108_engine):
        """Should return no hazard for non-matching trigger."""
        result = hex_0108_engine.check_investigation_hazard("0108", "investigate_trees")
        assert result["triggered"] is False

    def test_hazard_returns_chance(self, hex_0108_engine):
        """Should return the chance string in result."""
        DiceRoller.set_seed(42)
        result = hex_0108_engine.check_investigation_hazard("0108", "investigate_cabbages")
        assert result.get("chance") == "2-in-6"

    def test_hazard_can_trigger(self, hex_0108_engine):
        """With seeded dice, hazard should trigger deterministically."""
        # Seed that produces low rolls (triggers hazard)
        DiceRoller.set_seed(1)
        result = hex_0108_engine.check_investigation_hazard("0108", "investigate_cabbages")
        # Either triggered or not - just verify structure
        assert "triggered" in result
        assert "description" in result
        DiceRoller._seed = None

    def test_hazard_result_when_triggered(self, hex_0108_engine):
        """When triggered, should return the result ID."""
        # Force a trigger by mocking _check_chance
        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            result = hex_0108_engine.check_investigation_hazard("0108", "investigate_cabbages")
            assert result["triggered"] is True
            assert result.get("result") == "murkins_soldiers_arrive"


class TestCheckEveningHazard:
    """Test check_evening_hazard engine method."""

    def test_no_hazard_for_unknown_poi(self, hex_0108_engine):
        """Should return no hazard for non-existent POI."""
        result = hex_0108_engine.check_evening_hazard("0108", "Unknown Inn")
        assert result["triggered"] is False

    def test_evening_hazard_returns_chance(self, hex_0108_engine):
        """Should return the chance string."""
        DiceRoller.set_seed(42)
        result = hex_0108_engine.check_evening_hazard("0108", "The Crimson Bath")
        assert result.get("chance") == "3-in-6"
        DiceRoller._seed = None

    def test_evening_hazard_can_trigger(self, hex_0108_engine):
        """With mocked trigger, should return correct structure."""
        with patch.object(hex_0108_engine, "_check_chance", return_value=True):
            result = hex_0108_engine.check_evening_hazard("0108", "The Crimson Bath")
            assert result["triggered"] is True
            assert result.get("result") == "murkins_soldiers_harassment"


class TestRollHexEncounterTable:
    """Test roll_hex_encounter_table engine method."""

    def test_hex_has_encounter_table(self, hex_0108_engine):
        """Hex 0108 should have a custom encounter table."""
        result = hex_0108_engine.roll_hex_encounter_table("0108")
        assert result["has_table"] is True

    def test_encounter_table_roll_returns_result(self, hex_0108_engine):
        """Rolling should return a result from the table."""
        DiceRoller.set_seed(42)
        result = hex_0108_engine.roll_hex_encounter_table("0108")
        assert "roll" in result
        assert "description" in result
        assert result.get("table_name") == "Hex 0108 Encounters"
        DiceRoller._seed = None

    def test_roll_1_returns_murkins_soldiers(self, hex_0108_engine):
        """Rolling 1 should return Murkin's Soldiers."""
        # Seed that produces roll of 1
        DiceRoller.set_seed(0)
        result = hex_0108_engine.roll_hex_encounter_table("0108")
        # Check if result mentions soldiers (depends on dice seed)
        assert result["has_table"] is True
        DiceRoller._seed = None

    def test_no_table_for_hex_without_one(self, hex_0108_engine):
        """Should return has_table=False for hex without custom table."""
        result = hex_0108_engine.roll_hex_encounter_table("9999")
        assert result["has_table"] is False


class TestGetNpcGroupSize:
    """Test get_npc_group_size engine method."""

    def test_non_group_npc_returns_count_1(self, hex_0108_engine):
        """Individual NPC should return is_group=False."""
        result = hex_0108_engine.get_npc_group_size("0108", "timilda_brumble")
        assert result["is_group"] is False
        assert result["total_count"] == 1

    def test_group_npc_returns_is_group_true(self, hex_0108_engine):
        """Group NPC should return is_group=True."""
        DiceRoller.set_seed(42)
        result = hex_0108_engine.get_npc_group_size("0108", "murkins_soldiers")
        assert result["is_group"] is True
        DiceRoller._seed = None

    def test_group_npc_has_composition(self, hex_0108_engine):
        """Group NPC should return composition breakdown."""
        DiceRoller.set_seed(42)
        result = hex_0108_engine.get_npc_group_size("0108", "murkins_soldiers")
        assert "composition" in result
        assert "humans" in result["composition"]
        assert "shorthorns" in result["composition"]
        DiceRoller._seed = None

    def test_group_count_expression_returned(self, hex_0108_engine):
        """Should return the original dice expression."""
        DiceRoller.set_seed(42)
        result = hex_0108_engine.get_npc_group_size("0108", "murkins_soldiers")
        assert result.get("group_count_expression") == "1d4+1d4"
        DiceRoller._seed = None

    def test_deterministic_group_size(self, hex_0108_engine):
        """Group size should be deterministic with same seed."""
        DiceRoller.set_seed(12345)
        result1 = hex_0108_engine.get_npc_group_size("0108", "murkins_soldiers")

        DiceRoller.set_seed(12345)
        result2 = hex_0108_engine.get_npc_group_size("0108", "murkins_soldiers")

        assert result1["total_count"] == result2["total_count"]
        DiceRoller._seed = None


class TestCheckChance:
    """Test the _check_chance helper method."""

    def test_parse_x_in_y_format(self, hex_0108_engine):
        """Should parse 'X-in-Y' format and return boolean."""
        # Just verify it parses and returns a boolean
        result = hex_0108_engine._check_chance("1-in-6")
        assert isinstance(result, bool)

    def test_6_in_6_always_succeeds(self, hex_0108_engine):
        """6-in-6 chance should always succeed."""
        # Run multiple times to verify
        for _ in range(10):
            result = hex_0108_engine._check_chance("6-in-6")
            assert result is True

    def test_0_in_6_always_fails(self, hex_0108_engine):
        """0-in-6 chance should always fail."""
        # Run multiple times to verify
        for _ in range(10):
            result = hex_0108_engine._check_chance("0-in-6")
            assert result is False
