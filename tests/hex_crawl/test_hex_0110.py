"""
Tests for hex 0110 - The Shadow of Lord Gnarlgruff.

Tests hex loading, NPC structures, roll tables, entry conditions,
and faction relationships.
"""

import pytest
from pathlib import Path

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0110 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0110_the_shadow_of_lord_gnarlgruff.json")
    )
    assert result.success, f"Failed to load hex 0110: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0110(pipeline):
    """Get the hex 0110 data."""
    return pipeline.get_hex("0110")


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


# =============================================================================
# HEX LOADING TESTS
# =============================================================================


class TestHex0110Loading:
    """Test that hex 0110 loads correctly."""

    def test_hex_loads_successfully(self, hex_0110):
        """Hex 0110 should load without errors."""
        assert hex_0110 is not None
        assert hex_0110.hex_id == "0110"

    def test_hex_has_correct_metadata(self, hex_0110):
        """Hex should have correct basic metadata."""
        assert hex_0110.name == "The Shadow of Lord Gnarlgruff"
        assert hex_0110.region == "High Wold"
        # Note: terrain_type is normalized to use underscores
        assert "tangled" in hex_0110.terrain_type
        assert hex_0110.terrain_difficulty == 3

    def test_hex_has_procedural_section(self, hex_0110):
        """Hex should have a populated procedural section."""
        assert hex_0110.procedural is not None
        assert hex_0110.procedural.lost_chance == "2-in-6"
        assert hex_0110.procedural.encounter_chance == "2-in-6"

    def test_hex_has_encounter_modifiers(self, hex_0110):
        """Hex should have encounter modifiers for devil goats."""
        assert hex_0110.procedural.encounter_modifiers is not None
        assert len(hex_0110.procedural.encounter_modifiers) >= 1
        devil_goat_mod = hex_0110.procedural.encounter_modifiers[0]
        assert devil_goat_mod["monster_id"] == "devil_goat"
        assert devil_goat_mod["behavior"] == "hostile"

    def test_hex_has_night_hazards(self, hex_0110):
        """Hex should have night hazards."""
        assert hex_0110.procedural.night_hazards is not None
        assert len(hex_0110.procedural.night_hazards) >= 2
        # Check for sleep hazard
        sleep_hazard = next(
            (h for h in hex_0110.procedural.night_hazards if h["trigger"] == "sleep"),
            None,
        )
        assert sleep_hazard is not None
        assert sleep_hazard["chance"] == "3-in-6"

    def test_hex_has_foraging_special(self, hex_0110):
        """Hex should have foraging special items."""
        assert hex_0110.procedural.foraging_special is not None
        assert len(hex_0110.procedural.foraging_special) >= 2


# =============================================================================
# POI TESTS
# =============================================================================


class TestDevilGoatsGlade:
    """Test the Devil Goats' Glade POI."""

    def test_poi_exists(self, hex_0110):
        """Devil Goats' Glade should exist."""
        assert len(hex_0110.points_of_interest) >= 1
        glade = hex_0110.points_of_interest[0]
        assert glade.name == "Devil Goats' Glade"

    def test_poi_has_entry_conditions(self, hex_0110):
        """POI should have entry conditions restricting access."""
        glade = hex_0110.points_of_interest[0]
        assert glade.entry_conditions is not None
        assert glade.entry_conditions["type"] == "kindred_restricted"
        assert "longhorn breggle" in glade.entry_conditions["allowed_kindred"]

    def test_poi_has_hazards(self, hex_0110):
        """POI should have hazards defined."""
        glade = hex_0110.points_of_interest[0]
        assert glade.hazards is not None
        assert len(glade.hazards) >= 2
        # Check for devil goat attack hazard
        attack_hazard = next(
            (h for h in glade.hazards if h["hazard_id"] == "devil_goat_attack"), None
        )
        assert attack_hazard is not None
        assert attack_hazard["effect"] == "combat"

    def test_poi_has_discovery_hints(self, hex_0110):
        """POI should have discovery hints."""
        glade = hex_0110.points_of_interest[0]
        assert glade.discovery_hints is not None
        assert "smell" in glade.discovery_hints
        assert "charnel" in glade.discovery_hints["smell"].lower()

    def test_poi_has_roll_tables(self, hex_0110):
        """POI should have roll tables."""
        glade = hex_0110.points_of_interest[0]
        assert glade.roll_tables is not None
        assert len(glade.roll_tables) >= 2

    def test_bone_pile_discoveries_table(self, hex_0110):
        """Bone Pile Discoveries table should have correct structure."""
        glade = hex_0110.points_of_interest[0]
        bone_table = next(
            (t for t in glade.roll_tables if t.name == "Bone Pile Discoveries"), None
        )
        assert bone_table is not None
        assert bone_table.die_type == "d6"
        # Note: unique_entries may not be parsed by default loader
        assert len(bone_table.entries) == 6

    def test_monolith_events_table(self, hex_0110):
        """Monolith Events table should have correct structure."""
        glade = hex_0110.points_of_interest[0]
        monolith_table = next(
            (t for t in glade.roll_tables if t.name == "Monolith Events"), None
        )
        assert monolith_table is not None
        assert monolith_table.die_type == "d4"
        assert len(monolith_table.entries) == 4

    def test_poi_has_evening_hazard(self, hex_0110):
        """POI should have evening hazard."""
        glade = hex_0110.points_of_interest[0]
        assert glade.evening_hazard is not None
        assert glade.evening_hazard["chance"] == "4-in-6"

    def test_poi_references_npcs(self, hex_0110):
        """POI should reference the devil_goats and lord_gnarlgruff_spirit NPCs."""
        glade = hex_0110.points_of_interest[0]
        assert "devil_goats" in glade.npcs
        assert "lord_gnarlgruff_spirit" in glade.npcs


# =============================================================================
# NPC TESTS
# =============================================================================


class TestDevilGoatsNPC:
    """Test the Devil Goats NPC."""

    def test_devil_goats_exists(self, hex_0110):
        """Devil Goats NPC should exist."""
        devil_goats = next(
            (n for n in hex_0110.npcs if n.npc_id == "devil_goats"), None
        )
        assert devil_goats is not None

    def test_devil_goats_is_combatant(self, hex_0110):
        """Devil Goats should be combatants."""
        devil_goats = next(
            (n for n in hex_0110.npcs if n.npc_id == "devil_goats"), None
        )
        assert devil_goats.is_combatant is True
        assert devil_goats.stat_reference == "Devil Goat (DMB)"

    def test_devil_goats_has_group_count(self, hex_0110):
        """Devil Goats should have group_count for variable spawns."""
        devil_goats = next(
            (n for n in hex_0110.npcs if n.npc_id == "devil_goats"), None
        )
        assert devil_goats.group_count == "2d4"

    def test_devil_goats_has_vulnerabilities(self, hex_0110):
        """Devil Goats should have vulnerabilities."""
        devil_goats = next(
            (n for n in hex_0110.npcs if n.npc_id == "devil_goats"), None
        )
        assert devil_goats.vulnerabilities is not None
        assert "holy_symbols" in devil_goats.vulnerabilities

    def test_devil_goats_has_relationships(self, hex_0110):
        """Devil Goats should have relationship to Gnarlgruff."""
        devil_goats = next(
            (n for n in hex_0110.npcs if n.npc_id == "devil_goats"), None
        )
        assert devil_goats.relationships is not None
        assert len(devil_goats.relationships) >= 1
        gnarlgruff_rel = next(
            (r for r in devil_goats.relationships if r["npc_id"] == "lord_gnarlgruff_spirit"),
            None,
        )
        assert gnarlgruff_rel is not None
        assert gnarlgruff_rel["relationship_type"] == "worshipper"


class TestLordGnarlgruffSpirit:
    """Test the Lord Gnarlgruff Spirit NPC."""

    def test_spirit_exists(self, hex_0110):
        """Lord Gnarlgruff Spirit should exist."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert spirit is not None
        assert spirit.name == "Lord Gnarlgruff"

    def test_spirit_is_not_combatant(self, hex_0110):
        """Spirit should not be a combatant."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert spirit.is_combatant is False

    def test_spirit_has_known_topics(self, hex_0110):
        """Spirit should have known_topics for conversation."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert spirit.known_topics is not None
        assert len(spirit.known_topics) >= 4

    def test_spirit_has_faction_topics(self, hex_0110):
        """Spirit should have faction-related topics."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        faction_topics = [t for t in spirit.known_topics if t.category == "faction"]
        assert len(faction_topics) >= 2  # Malbleat and Ramius connections

    def test_spirit_has_secret_info(self, hex_0110):
        """Spirit should have secret_info with hints."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert spirit.secret_info is not None
        assert len(spirit.secret_info) >= 2

    def test_spirit_secret_has_required_trust(self, hex_0110):
        """Spirit secrets should require trust to reveal."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        remains_secret = next(
            (s for s in spirit.secret_info if s.secret_id == "remains_location"), None
        )
        assert remains_secret is not None
        assert remains_secret.required_trust >= 1

    def test_spirit_has_relationships(self, hex_0110):
        """Spirit should have relationships to descendants."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert spirit.relationships is not None
        assert len(spirit.relationships) >= 3
        # Check for Malbleat relationship with hex_id
        malbleat_rel = next(
            (r for r in spirit.relationships if r["npc_id"] == "lord_malbleat"), None
        )
        assert malbleat_rel is not None
        assert malbleat_rel["hex_id"] == "0709"

    def test_spirit_location_indicates_binding(self, hex_0110):
        """Spirit location should indicate binding to monolith."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        # Spirit's location indicates binding to monolith
        assert "monolith" in spirit.location.lower()
        assert "full moon" in spirit.location.lower()

    def test_spirit_has_vulnerabilities(self, hex_0110):
        """Spirit should have cold_iron vulnerability."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert "cold_iron" in spirit.vulnerabilities

    def test_spirit_has_time_presence(self, hex_0110):
        """Spirit should have time_presence for moon phase availability."""
        spirit = next(
            (n for n in hex_0110.npcs if n.npc_id == "lord_gnarlgruff_spirit"), None
        )
        assert spirit.time_presence is not None
        assert spirit.time_presence["type"] == "moon_phase"
        assert spirit.time_presence["phase"] == "full"

    def test_devil_goats_no_time_presence(self, hex_0110):
        """Devil Goats should not have time_presence (always present)."""
        devil_goats = next(
            (n for n in hex_0110.npcs if n.npc_id == "devil_goats"), None
        )
        assert devil_goats.time_presence is None


# =============================================================================
# ITEMS AND SECRETS TESTS
# =============================================================================


class TestHex0110Items:
    """Test hex 0110 items."""

    def test_items_have_proper_ids(self, hex_0110):
        """Items should have proper item_id format."""
        for item in hex_0110.items:
            assert item["item_id"].startswith("0110:item:")

    def test_silver_dagger_exists(self, hex_0110):
        """Silver dagger item should exist."""
        dagger = next(
            (i for i in hex_0110.items if "silver_dagger" in i["item_id"]), None
        )
        assert dagger is not None
        assert dagger["magical"] is False

    def test_magical_items_marked(self, hex_0110):
        """Magical items should be marked as magical."""
        ioun = next(
            (i for i in hex_0110.items if "ioun" in i["item_id"]), None
        )
        assert ioun is not None
        assert ioun["magical"] is True


class TestHex0110Secrets:
    """Test hex 0110 secrets."""

    def test_secrets_have_proper_structure(self, hex_0110):
        """Secrets should have secret_id, content, and keywords."""
        for secret in hex_0110.secrets:
            assert "secret_id" in secret
            assert "content" in secret
            assert "keywords" in secret

    def test_gnarlgruff_laboratory_secret(self, hex_0110):
        """Laboratory secret should exist."""
        lab_secret = next(
            (s for s in hex_0110.secrets if s["secret_id"] == "gnarlgruff_laboratory"),
            None,
        )
        assert lab_secret is not None
        assert "laboratory" in lab_secret["keywords"]


# =============================================================================
# ROLL TABLE RESOLUTION TESTS
# =============================================================================


class TestRollTableResolution:
    """Test roll table resolution for hex 0110."""

    def test_bone_pile_table_resolution(self, hex_0110, seeded_dice):
        """Bone pile table should resolve correctly."""
        glade = hex_0110.points_of_interest[0]
        bone_table = next(
            (t for t in glade.roll_tables if t.name == "Bone Pile Discoveries"), None
        )
        assert bone_table is not None

        # Roll a d6
        roll = seeded_dice.roll("1d6", "bone_pile_test")
        assert 1 <= roll.total <= 6

        # Find matching entry
        entry = next((e for e in bone_table.entries if e.roll == roll.total), None)
        assert entry is not None

    def test_monolith_events_table_resolution(self, hex_0110, seeded_dice):
        """Monolith events table should resolve correctly."""
        glade = hex_0110.points_of_interest[0]
        monolith_table = next(
            (t for t in glade.roll_tables if t.name == "Monolith Events"), None
        )
        assert monolith_table is not None

        # Roll a d4
        roll = seeded_dice.roll("1d4", "monolith_test")
        assert 1 <= roll.total <= 4

        # Find matching entry
        entry = next((e for e in monolith_table.entries if e.roll == roll.total), None)
        assert entry is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestHex0110Integration:
    """Integration tests for hex 0110 with HexCrawlEngine."""

    def test_hex_can_be_used_in_engine(self, hex_0110):
        """Hex 0110 should work with HexCrawlEngine."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()
        engine = HexCrawlEngine(controller)
        engine._hex_data["0110"] = hex_0110
        engine._current_hex = "0110"

        # Should be able to get hex data
        hex_data = engine.get_hex_data("0110")
        assert hex_data is not None
        assert hex_data.name == "The Shadow of Lord Gnarlgruff"

    def test_poi_can_be_listed(self, hex_0110):
        """POIs should be listable from the hex."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()
        engine = HexCrawlEngine(controller)
        engine._hex_data["0110"] = hex_0110
        engine._current_hex = "0110"

        pois = engine.get_visible_pois("0110")
        assert pois is not None
        assert len(pois) >= 1
        # Check that the glade POI is found (type='glade')
        assert any(poi.get("type") == "glade" for poi in pois)
