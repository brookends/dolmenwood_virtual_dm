"""
Tests for hex 0108 (The Cabbage Plot) compatibility.

Verifies that the enriched hex data loads correctly and all
NPC interactions, roll tables, and faction data are accessible.
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


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()
    DiceRoller._seed = None


# =============================================================================
# HEX LOADING TESTS
# =============================================================================


class TestHex0108Loading:
    """Test that hex 0108 loads correctly."""

    def test_hex_0108_loads_successfully(self, pipeline):
        """Hex 0108 should load without errors."""
        hex_data = pipeline.get_hex("0108")
        assert hex_data is not None
        assert hex_data.hex_id == "0108"
        assert hex_data.name == "The Cabbage Plot"

    def test_hex_0108_has_correct_terrain(self, pipeline):
        """Hex 0108 should have farmland terrain."""
        hex_data = pipeline.get_hex("0108")
        assert hex_data.terrain_type == "farmland"
        assert hex_data.terrain_difficulty == 2
        assert hex_data.region == "High Wold"

    def test_hex_0108_has_procedural_data(self, pipeline):
        """Hex 0108 should have procedural encounter/foraging data."""
        hex_data = pipeline.get_hex("0108")
        assert hex_data.procedural is not None
        # Access as object attributes
        assert hex_data.procedural.lost_chance == "1-in-6"
        assert hex_data.procedural.encounter_chance == "1-in-6"


# =============================================================================
# POI TESTS
# =============================================================================


class TestCrimsonBathPOI:
    """Test The Crimson Bath POI loading."""

    def test_crimson_bath_exists(self, pipeline):
        """The Crimson Bath POI should exist."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        assert poi is not None
        assert poi.poi_type == "inn"

    def test_crimson_bath_has_entering(self, pipeline):
        """The Crimson Bath should have entering text."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        assert poi.entering is not None
        assert "Crimson Bath leans" in poi.entering

    def test_crimson_bath_has_interior(self, pipeline):
        """The Crimson Bath should have interior text."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        assert poi.interior is not None
        assert "smoke-filled" in poi.interior

    def test_crimson_bath_has_roll_tables(self, pipeline):
        """The Crimson Bath should have roll tables."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        assert len(poi.roll_tables) == 3

        table_names = [t.name for t in poi.roll_tables]
        assert "Current Patrons" in table_names
        assert "Crimson Bath Rumors" in table_names
        assert "Evening Events" in table_names

    def test_patrons_table_has_entries(self, pipeline):
        """Patrons table should have 6 entries."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        patrons_table = next(
            (t for t in poi.roll_tables if t.name == "Current Patrons"), None
        )
        assert patrons_table is not None
        assert len(patrons_table.entries) == 6

    def test_rumors_table_has_entries(self, pipeline):
        """Rumors table should have 6 entries with keywords."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        rumors_table = next(
            (t for t in poi.roll_tables if t.name == "Crimson Bath Rumors"), None
        )
        assert rumors_table is not None
        assert len(rumors_table.entries) == 6


# =============================================================================
# NPC TESTS
# =============================================================================


class TestTimildaBrumbleNPC:
    """Test Timilda Brumble NPC loading."""

    def test_timilda_exists(self, pipeline):
        """Timilda Brumble should exist in hex NPCs."""
        hex_data = pipeline.get_hex("0108")
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break
        assert timilda is not None
        assert timilda.name == "Timilda Brumble"

    def test_timilda_has_known_topics(self, pipeline):
        """Timilda should have known_topics for conversation."""
        hex_data = pipeline.get_hex("0108")
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break
        assert timilda is not None
        assert len(timilda.known_topics) >= 5

        topic_ids = [t.topic_id for t in timilda.known_topics]
        assert "welcome_to_inn" in topic_ids
        assert "poodden_pie" in topic_ids
        assert "crown_cabbages" in topic_ids

    def test_timilda_has_secret_info(self, pipeline):
        """Timilda should have secret_info about the rebellion."""
        hex_data = pipeline.get_hex("0108")
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break
        assert timilda is not None
        assert len(timilda.secret_info) >= 2

        secret_ids = [s.secret_id for s in timilda.secret_info]
        assert "cabbage_plot_leader" in secret_ids
        assert "borrid_alliance" in secret_ids

    def test_timilda_has_relationships(self, pipeline):
        """Timilda should have relationships defined."""
        hex_data = pipeline.get_hex("0108")
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break
        assert timilda is not None
        assert len(timilda.relationships) >= 2

        rel_npcs = [r.get("npc_id") for r in timilda.relationships]
        assert "grerg_brumble" in rel_npcs
        assert "lady_borrid" in rel_npcs

    def test_timilda_has_vulnerabilities(self, pipeline):
        """Timilda should have vulnerabilities for social mechanics."""
        hex_data = pipeline.get_hex("0108")
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break
        assert timilda is not None
        assert len(timilda.vulnerabilities) >= 2
        assert "protection_of_patrons" in timilda.vulnerabilities


class TestGrergBrumbleNPC:
    """Test Grerg Brumble NPC loading."""

    def test_grerg_exists(self, pipeline):
        """Grerg Brumble should exist in hex NPCs."""
        hex_data = pipeline.get_hex("0108")
        grerg = None
        for npc in hex_data.npcs:
            if npc.npc_id == "grerg_brumble":
                grerg = npc
                break
        assert grerg is not None
        assert grerg.name == "Grerg Brumble"
        assert grerg.kindred == "Human"

    def test_grerg_is_combatant(self, pipeline):
        """Grerg should be a combatant."""
        hex_data = pipeline.get_hex("0108")
        grerg = None
        for npc in hex_data.npcs:
            if npc.npc_id == "grerg_brumble":
                grerg = npc
                break
        assert grerg is not None
        assert grerg.is_combatant is True
        assert grerg.stat_reference == "Level 2 fighter (DMB)"

    def test_grerg_has_topics(self, pipeline):
        """Grerg should have known_topics."""
        hex_data = pipeline.get_hex("0108")
        grerg = None
        for npc in hex_data.npcs:
            if npc.npc_id == "grerg_brumble":
                grerg = npc
                break
        assert grerg is not None
        assert len(grerg.known_topics) >= 3


class TestMurkinsSoldiersNPC:
    """Test Murkin's Soldiers NPC group loading."""

    def test_soldiers_exist(self, pipeline):
        """Murkin's Soldiers should exist in hex NPCs."""
        hex_data = pipeline.get_hex("0108")
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert soldiers.name == "Murkin's Soldiers"

    def test_soldiers_are_combatant(self, pipeline):
        """Murkin's Soldiers should be combatants."""
        hex_data = pipeline.get_hex("0108")
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert soldiers.is_combatant is True
        assert "Level 1 fighter" in soldiers.stat_reference

    def test_soldiers_have_faction(self, pipeline):
        """Murkin's Soldiers should have faction: house_murkin."""
        hex_data = pipeline.get_hex("0108")
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert soldiers.faction == "house_murkin"

    def test_soldiers_have_topics_for_interaction(self, pipeline):
        """Murkin's Soldiers should have known_topics for roleplay."""
        hex_data = pipeline.get_hex("0108")
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        assert len(soldiers.known_topics) >= 3

        topic_ids = [t.topic_id for t in soldiers.known_topics]
        assert "demand_drinks" in topic_ids
        assert "cabbage_investigation" in topic_ids

    def test_soldiers_can_be_bribed(self, pipeline):
        """Murkin's Soldiers should have bribable secret_info."""
        hex_data = pipeline.get_hex("0108")
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        bribable = [s for s in soldiers.secret_info if s.can_be_bribed]
        assert len(bribable) >= 1


# =============================================================================
# ENGINE INTEGRATION TESTS
# =============================================================================


class TestHex0108EngineIntegration:
    """Test hex 0108 works with HexCrawlEngine."""

    def test_engine_can_get_pois(self, hex_0108_engine):
        """Engine should be able to get POIs for hex 0108."""
        hex_0108_engine._current_hex = "0108"
        hex_0108_engine._travel_points_remaining = 10
        hex_0108_engine._explored_hexes.add("0108")

        pois = hex_0108_engine.get_accessible_pois("0108")
        assert len(pois) >= 1

        poi_names = [p.get("name") for p in pois]
        assert "The Crimson Bath" in poi_names

    def test_engine_can_get_npcs_at_poi(self, hex_0108_engine):
        """Engine should be able to get NPCs at The Crimson Bath."""
        hex_0108_engine._current_hex = "0108"
        hex_0108_engine._travel_points_remaining = 10
        hex_0108_engine._explored_hexes.add("0108")
        hex_0108_engine._current_poi = "The Crimson Bath"

        npcs = hex_0108_engine.get_npcs_at_poi("0108")

        # Should find Timilda and/or Grerg
        assert len(npcs) >= 1


# =============================================================================
# FACTION TOPIC TESTS
# =============================================================================


class TestFactionTopics:
    """Test that faction-related topics are properly categorized."""

    def test_timilda_has_faction_topic(self, pipeline):
        """Timilda should have at least one faction-category topic."""
        hex_data = pipeline.get_hex("0108")
        timilda = None
        for npc in hex_data.npcs:
            if npc.npc_id == "timilda_brumble":
                timilda = npc
                break
        assert timilda is not None
        faction_topics = [t for t in timilda.known_topics if t.category == "faction"]
        assert len(faction_topics) >= 1

    def test_soldiers_have_faction_topic(self, pipeline):
        """Murkin's Soldiers should have faction-category topic."""
        hex_data = pipeline.get_hex("0108")
        soldiers = None
        for npc in hex_data.npcs:
            if npc.npc_id == "murkins_soldiers":
                soldiers = npc
                break
        assert soldiers is not None
        faction_topics = [t for t in soldiers.known_topics if t.category == "faction"]
        assert len(faction_topics) >= 1


# =============================================================================
# SECRETS TESTS
# =============================================================================


class TestHex0108Secrets:
    """Test hex-level secrets are loaded."""

    def test_hex_has_secrets(self, pipeline):
        """Hex 0108 should have hex-level secrets."""
        hex_data = pipeline.get_hex("0108")
        assert len(hex_data.secrets) >= 2

    def test_poi_has_secrets(self, pipeline):
        """The Crimson Bath should have POI-level secrets."""
        hex_data = pipeline.get_hex("0108")
        poi = next(
            (p for p in hex_data.points_of_interest if p.name == "The Crimson Bath"),
            None,
        )
        assert len(poi.secrets) >= 1
        assert any("cellar" in s.lower() for s in poi.secrets)


# =============================================================================
# ITEMS TESTS
# =============================================================================


class TestHex0108Items:
    """Test hex items are loaded."""

    def test_hex_has_vegetable_poison(self, pipeline):
        """Hex 0108 should have the vegetable poison item."""
        hex_data = pipeline.get_hex("0108")
        items = hex_data.items
        poison = next(
            (i for i in items if "poison" in i.get("name", "").lower()), None
        )
        assert poison is not None
        assert poison.get("item_id") == "0108:item:vegetable_poison"
