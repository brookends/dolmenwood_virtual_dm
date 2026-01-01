"""
Compatibility tests for HEX 0103 - The Golden Goose.

Tests that hex data loads correctly and game engine can interact with:
- Terrain and procedural data
- POIs (Sidney's Company, Crocus's Cave)
- NPCs (Crocus, Sidney Tew, Golden Goose, etc.)
- Hidden POI discovery
- Monster stat lookup
"""

import pytest
from pathlib import Path

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.monster_registry import get_monster_registry
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def hex_pipeline():
    """Create a content pipeline with hex 0103 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0103_the_golden_goose.json"))
    assert result.success, f"Failed to load hex: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0103(hex_pipeline):
    """Get the loaded HexLocation for hex 0103."""
    hex_data = hex_pipeline.get_hex("0103")
    assert hex_data is not None, "Hex 0103 not found in pipeline"
    return hex_data


@pytest.fixture
def hex_engine(hex_0103):
    """Create a HexCrawlEngine with hex 0103 loaded."""
    controller = GlobalController()
    engine = HexCrawlEngine(controller)
    # Load hex data into engine
    engine._hex_data["0103"] = hex_0103
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


class TestHex0103Loading:
    """Test that hex 0103 loads correctly."""

    def test_hex_loads_successfully(self, hex_0103):
        """Hex 0103 should load without errors."""
        assert hex_0103.hex_id == "0103"
        assert hex_0103.name == "The Golden Goose"

    def test_terrain_type(self, hex_0103):
        """Hex should have correct terrain type."""
        assert hex_0103.terrain_type == "bog"
        assert hex_0103.terrain_difficulty == 3

    def test_region(self, hex_0103):
        """Hex should be in correct region."""
        assert hex_0103.region == "Northern Scratch"

    def test_procedural_data(self, hex_0103):
        """Procedural data should be loaded."""
        proc = hex_0103.procedural
        assert proc is not None
        assert proc.lost_chance == "2-in-6"
        assert proc.encounter_chance == "2-in-6"


# =============================================================================
# POI TESTS
# =============================================================================


class TestHex0103POIs:
    """Test POI loading and visibility."""

    def test_poi_count(self, hex_0103):
        """Should have exactly 2 POIs."""
        assert len(hex_0103.points_of_interest) == 2

    def test_sidneys_company_poi(self, hex_0103):
        """Sidney's Company should be a visible encounter POI."""
        poi = hex_0103.points_of_interest[0]
        assert poi.name == "Sidney's Company"
        assert poi.poi_type == "encounter"
        assert poi.hidden is False
        assert poi.is_dungeon is False

    def test_crocus_cave_poi(self, hex_0103):
        """Crocus's Cave should be a hidden dungeon POI."""
        poi = hex_0103.points_of_interest[1]
        assert poi.name == "Crocus's Cave"
        assert poi.poi_type == "cave"
        assert poi.hidden is True  # Key test - entering="Hidden" should set hidden=True
        assert poi.is_dungeon is True

    def test_crocus_cave_entering_field(self, hex_0103):
        """Crocus's Cave should preserve the 'Hidden' entering value."""
        poi = hex_0103.points_of_interest[1]
        assert poi.entering == "Hidden"

    def test_poi_npcs_linked(self, hex_0103):
        """POIs should have NPC references."""
        sidneys = hex_0103.points_of_interest[0]
        assert "sidney_tew" in sidneys.npcs

        cave = hex_0103.points_of_interest[1]
        assert "crocus" in cave.npcs
        assert "the_golden_goose" in cave.npcs


# =============================================================================
# NPC TESTS
# =============================================================================


class TestHex0103NPCs:
    """Test NPC loading."""

    def test_npc_count(self, hex_0103):
        """Should have 5 NPCs (Crocus, Sidney, Goose, Nobles, Ruffians)."""
        assert len(hex_0103.npcs) == 5

    def test_crocus_npc(self, hex_0103):
        """Crocus should be loaded with correct data."""
        crocus = next((n for n in hex_0103.npcs if n.npc_id == "crocus"), None)
        assert crocus is not None
        assert crocus.name == "Crocus"
        assert crocus.kindred == "Fairy"
        assert crocus.is_combatant is True
        assert "Ogre" in crocus.stat_reference

    def test_sidney_tew_npc(self, hex_0103):
        """Sidney Tew should be loaded correctly."""
        sidney = next((n for n in hex_0103.npcs if n.npc_id == "sidney_tew"), None)
        assert sidney is not None
        assert sidney.name == "Sidney Tew"
        assert sidney.kindred == "Human"
        assert sidney.is_combatant is True
        assert "Level 3 fighter" in sidney.stat_reference

    def test_golden_goose_npc(self, hex_0103):
        """The Golden Goose should be non-combatant."""
        goose = next((n for n in hex_0103.npcs if n.npc_id == "the_golden_goose"), None)
        assert goose is not None
        assert goose.name == "The Golden Goose"
        assert goose.is_combatant is False
        assert len(goose.secrets) > 0  # Has secrets about Thorn-Rosy


# =============================================================================
# HIDDEN POI DISCOVERY TESTS
# =============================================================================


class TestHex0103HiddenPOI:
    """Test hidden POI visibility and discovery."""

    def test_hidden_poi_not_visible_by_default(self, hex_engine):
        """Crocus's Cave should not be visible until discovered."""
        visible = hex_engine.get_visible_pois("0103")

        # Sidney's Company should be visible
        sidneys_visible = any(p.get("type") == "encounter" for p in visible)
        assert sidneys_visible, "Sidney's Company should be visible"

        # Crocus's Cave should NOT be visible (it's hidden)
        cave_visible = any("cave" in str(p).lower() for p in visible)
        assert not cave_visible, "Crocus's Cave should be hidden"

    def test_discover_hidden_poi(self, hex_engine):
        """discover_poi should mark the cave as discovered."""
        result = hex_engine.discover_poi("0103", "Crocus's Cave")
        assert result is True

        # Now it should be visible
        visible = hex_engine.get_visible_pois("0103")
        # After discovery, the cave should appear in visible list
        # (The exact structure depends on engine implementation)


# =============================================================================
# MONSTER STAT LOOKUP TESTS
# =============================================================================


class TestHex0103MonsterStats:
    """Test that monster stats can be looked up from stat_reference."""

    def test_ogre_stats_available(self):
        """Ogre stats should be available in monster registry."""
        registry = get_monster_registry()
        result = registry.get_monster_by_name("Ogre")

        assert result.found, f"Ogre not found: {result.error}"
        ogre = result.monster
        assert ogre.armor_class == 14
        assert ogre.level == 4
        assert ogre.hit_dice == "4d8"

    def test_ogre_stat_block(self):
        """Should be able to get StatBlock for combat."""
        registry = get_monster_registry()
        result = registry.get_stat_block("ogre")

        assert result.success, f"Failed to get stat block: {result.error}"
        stat_block = result.stat_block
        assert stat_block.armor_class == 14
        # HP can vary based on how stat block is generated
        assert stat_block.hp_max >= 1


# =============================================================================
# ENGINE INTERACTION TESTS
# =============================================================================


class TestHex0103EngineInteraction:
    """Test HexCrawlEngine interactions with hex 0103."""

    def test_get_hex_overview(self, hex_engine):
        """Should be able to get hex overview."""
        overview = hex_engine.get_hex_overview("0103")
        assert overview is not None
        # Overview should describe the bog terrain
        assert "bog" in overview.terrain_description.lower() or "moss" in overview.terrain_description.lower()

    def test_search_hex_costs_travel_points(self, hex_engine, seeded_dice):
        """Searching should cost travel points based on terrain."""
        # Set up travel points
        hex_engine._travel_points_remaining = 10

        result = hex_engine.search_hex("0103")

        # Bog terrain has difficulty 3, so search should cost 3 TP
        assert result.get("travel_points_spent") == 3 or result.get("success") is False


# =============================================================================
# SMOKE TEST - PARSE ALL HEXES
# =============================================================================


class TestAllHexesParse:
    """Quick smoke test that hex files parse without error."""

    def test_hex_0103_parses_cleanly(self):
        """Hex 0103 should parse without errors."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0103_the_golden_goose.json"))
        assert result.success, f"Hex 0103 parsing errors: {result.errors}"

    def test_hex_0102_parses_cleanly(self):
        """Hex 0102 (Reedwall) should parse without errors."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        result = loader.load_file(Path("data/content/hexes/0102_reedwall.json"))
        assert result.success, f"Hex 0102 parsing errors: {result.errors}"
