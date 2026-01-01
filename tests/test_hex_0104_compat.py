"""
Compatibility tests for HEX 0104 - The Phantom Lighthouse.

Tests that hex data loads correctly and game engine can interact with:
- Terrain and procedural data
- POI (Lighthouse in the Bog)
- NPC (The Dredger) with combat stats
- Item (Crystal Of Sepulture)
- Special features (time-of-day dependent)
"""

import pytest
from pathlib import Path

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def hex_pipeline():
    """Create a content pipeline with hex 0104 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0104_the_phantom_lighthouse.json"))
    assert result.success, f"Failed to load hex: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0104(hex_pipeline):
    """Get the loaded HexLocation for hex 0104."""
    hex_data = hex_pipeline.get_hex("0104")
    assert hex_data is not None, "Hex 0104 not found in pipeline"
    return hex_data


@pytest.fixture
def hex_engine(hex_0104):
    """Create a HexCrawlEngine with hex 0104 loaded."""
    controller = GlobalController()
    engine = HexCrawlEngine(controller)
    engine._hex_data["0104"] = hex_0104
    return engine


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


# =============================================================================
# BASIC LOADING TESTS
# =============================================================================


class TestHex0104Loading:
    """Test that hex 0104 loads correctly."""

    def test_hex_loads_successfully(self, hex_0104):
        """Hex 0104 should load without errors."""
        assert hex_0104.hex_id == "0104"
        assert hex_0104.name == "The Phantom Lighthouse"

    def test_terrain_type(self, hex_0104):
        """Hex should have correct terrain type."""
        assert hex_0104.terrain_type == "bog"
        assert hex_0104.terrain_difficulty == 3

    def test_region(self, hex_0104):
        """Hex should be in correct region."""
        assert hex_0104.region == "Northern Scratch"

    def test_procedural_data(self, hex_0104):
        """Procedural data should be loaded."""
        proc = hex_0104.procedural
        assert proc is not None
        assert proc.lost_chance == "2-in-6"
        assert proc.encounter_chance == "2-in-6"


# =============================================================================
# POI TESTS
# =============================================================================


class TestHex0104POIs:
    """Test POI loading."""

    def test_poi_count(self, hex_0104):
        """Should have exactly 1 POI."""
        assert len(hex_0104.points_of_interest) == 1

    def test_lighthouse_poi(self, hex_0104):
        """Lighthouse in the Bog should be loaded correctly."""
        poi = hex_0104.points_of_interest[0]
        assert poi.name == "Lighthouse in the Bog"
        assert poi.poi_type == "lighthouse"
        assert poi.is_dungeon is False
        assert poi.hidden is False  # Visible POI

    def test_lighthouse_has_dredger_npc(self, hex_0104):
        """Lighthouse POI should reference the Dredger NPC."""
        poi = hex_0104.points_of_interest[0]
        assert "the_dredger" in poi.npcs

    def test_lighthouse_special_features(self, hex_0104):
        """Lighthouse should have 5 special features."""
        poi = hex_0104.points_of_interest[0]
        assert len(poi.special_features) == 5

    def test_lighthouse_time_dependent_interior(self, hex_0104):
        """Interior description mentions time-of-day variations."""
        poi = hex_0104.points_of_interest[0]
        assert "daytime" in poi.interior.lower() or "nighttime" in poi.interior.lower()

    def test_lighthouse_inhabitants(self, hex_0104):
        """Inhabitants field should mention the Dredger."""
        poi = hex_0104.points_of_interest[0]
        assert "Dredger" in poi.inhabitants


# =============================================================================
# NPC TESTS
# =============================================================================


class TestHex0104NPCs:
    """Test NPC loading."""

    def test_npc_count(self, hex_0104):
        """Should have 1 NPC (The Dredger)."""
        assert len(hex_0104.npcs) == 1

    def test_dredger_npc(self, hex_0104):
        """The Dredger should be loaded with correct data."""
        dredger = hex_0104.npcs[0]
        assert dredger.npc_id == "the_dredger"
        assert dredger.name == "The Dredger"
        assert dredger.kindred == "Monstrosity"
        assert dredger.is_combatant is True

    def test_dredger_stat_reference(self, hex_0104):
        """The Dredger should have stat reference."""
        dredger = hex_0104.npcs[0]
        assert dredger.stat_reference is not None
        assert "Level 7" in dredger.stat_reference
        assert "AC 14" in dredger.stat_reference
        assert "HP 45" in dredger.stat_reference

    def test_dredger_location(self, hex_0104):
        """The Dredger should have location specified."""
        dredger = hex_0104.npcs[0]
        assert "lantern room" in dredger.location.lower()
        assert "nighttime" in dredger.location.lower()


# =============================================================================
# ITEM TESTS
# =============================================================================


class TestHex0104Items:
    """Test item loading."""

    def test_item_count(self, hex_0104):
        """Should have 1 item (Crystal Of Sepulture)."""
        assert len(hex_0104.items) == 1

    def test_crystal_item(self, hex_0104):
        """Crystal Of Sepulture should be loaded correctly."""
        crystal = hex_0104.items[0]
        assert crystal["name"] == "Crystal Of Sepulture"
        assert crystal["magical"] is True
        assert crystal["item_id"] == "0104:item:crystal-of-sepulture"

    def test_crystal_acquisition_condition(self, hex_0104):
        """Crystal should have acquisition condition."""
        crystal = hex_0104.items[0]
        assert "acquisition_condition" in crystal
        assert "Dredger" in crystal["acquisition_condition"]


# =============================================================================
# ENGINE INTERACTION TESTS
# =============================================================================


class TestHex0104EngineInteraction:
    """Test HexCrawlEngine interactions with hex 0104."""

    def test_hex_loaded_in_engine(self, hex_engine):
        """Hex 0104 should be loaded in the engine."""
        assert "0104" in hex_engine._hex_data
        hex_data = hex_engine._hex_data["0104"]
        assert hex_data.name == "The Phantom Lighthouse"

    def test_poi_accessible_from_engine(self, hex_engine):
        """POI data should be accessible from engine."""
        hex_data = hex_engine._hex_data["0104"]
        poi = hex_data.points_of_interest[0]
        assert poi.name == "Lighthouse in the Bog"
        assert "the_dredger" in poi.npcs


# =============================================================================
# SMOKE TEST - PARSE ALL HEXES
# =============================================================================


class TestAllHexesParse:
    """Quick smoke test that hex files parse without error."""

    def test_hex_0104_parses_cleanly(self):
        """Hex 0104 should parse without errors."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0104_the_phantom_lighthouse.json"))
        assert result.success, f"Hex 0104 parsing errors: {result.errors}"

    def test_hex_0103_still_parses(self):
        """Hex 0103 should still parse (regression check)."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0103_the_golden_goose.json"))
        assert result.success, f"Hex 0103 parsing errors: {result.errors}"

    def test_hex_0102_still_parses(self):
        """Hex 0102 should still parse (regression check)."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0102_reedwall.json"))
        assert result.success, f"Hex 0102 parsing errors: {result.errors}"
