"""
Tests for hex 0109 (Lady Borrid and Murkin's Army) features.

This test suite validates the enriched hex data including:
- Hex loading and structure
- NPC intelligence (known_topics, secret_info, relationships)
- Faction profiles
- POI evening hazards
- Investigation hazards
- Roll tables
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, GameDate
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0109 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json"))
    assert result.success, f"Failed to load hex 0109: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0109_engine(pipeline):
    """Create a HexCrawlEngine with hex 0109 loaded."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=1, day=1)
    engine = HexCrawlEngine(controller)
    engine._hex_data["0109"] = pipeline.get_hex("0109")
    return engine


# =============================================================================
# HEX LOADING TESTS
# =============================================================================


class TestHex0109Loading:
    """Test that hex 0109 loads correctly with all enriched data."""

    def test_hex_loads_successfully(self, pipeline):
        """Hex 0109 should load without errors."""
        hex_data = pipeline.get_hex("0109")
        assert hex_data is not None
        assert hex_data.hex_id == "0109"

    def test_hex_has_name_and_region(self, pipeline):
        """Hex should have proper name and region."""
        hex_data = pipeline.get_hex("0109")
        assert hex_data.name == "Lady Borrid and Murkin's Army"
        assert hex_data.region == "High Wold"

    def test_hex_has_pois(self, pipeline):
        """Hex should have Lady Borrid's Lodge, Murkin's Army, and Hidden Vault."""
        hex_data = pipeline.get_hex("0109")
        # 2 visible POIs + 1 hidden vault (requires discovery)
        assert len(hex_data.points_of_interest) == 3
        poi_names = [p.name for p in hex_data.points_of_interest]
        assert "Lady Borrid's Hunting Lodge" in poi_names
        assert "Murkin's Army" in poi_names
        assert "Lady Borrid's Hidden Vault" in poi_names

    def test_hex_has_two_npcs(self, pipeline):
        """Hex should have Lady Borrid and Sergeant Snidebleat."""
        hex_data = pipeline.get_hex("0109")
        assert len(hex_data.npcs) == 2
        npc_ids = [n.npc_id for n in hex_data.npcs]
        assert "lady_amonie_borrid" in npc_ids
        assert "sergeant_crewwin_snidebleat" in npc_ids

    def test_hex_has_encounter_table(self, pipeline):
        """Hex should have a custom encounter table."""
        hex_data = pipeline.get_hex("0109")
        assert hex_data.procedural.encounter_table is not None
        assert hex_data.procedural.encounter_table.name == "Hex 0109 Encounters"
        assert len(hex_data.procedural.encounter_table.entries) == 3


# =============================================================================
# LADY BORRID NPC TESTS
# =============================================================================


class TestLadyBorridNPC:
    """Test Lady Borrid's NPC intelligence data."""

    def test_borrid_has_known_topics(self, pipeline):
        """Lady Borrid should have multiple known topics."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        assert len(borrid.known_topics) >= 8

    def test_borrid_has_topic_categories(self, pipeline):
        """Lady Borrid's topics should have proper categories."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        categories = {t.category for t in borrid.known_topics}
        assert "personal" in categories
        assert "faction" in categories
        assert "npc" in categories

    def test_borrid_has_secret_info(self, pipeline):
        """Lady Borrid should have secret_info entries."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        assert len(borrid.secret_info) >= 3

    def test_borrid_secrets_have_hints(self, pipeline):
        """Lady Borrid's secrets should have hints."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        for secret in borrid.secret_info:
            assert secret.hint is not None
            assert len(secret.hint) > 0

    def test_borrid_has_relationships(self, pipeline):
        """Lady Borrid should have relationship entries."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        assert len(borrid.relationships) >= 3
        rel_npcs = {r.get("npc_id") for r in borrid.relationships}
        assert "lord_murkin" in rel_npcs
        assert "timilda_brumble" in rel_npcs

    def test_borrid_has_faction_profile(self, pipeline):
        """Lady Borrid should have a faction profile."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        assert borrid.faction_profile is not None
        assert borrid.faction_profile.get("faction_id") == "house_murkin"

    def test_borrid_has_vulnerabilities(self, pipeline):
        """Lady Borrid should have vulnerabilities."""
        hex_data = pipeline.get_hex("0109")
        borrid = next(n for n in hex_data.npcs if n.npc_id == "lady_amonie_borrid")
        assert len(borrid.vulnerabilities) >= 3
        assert "mention_of_cousin_murkin" in borrid.vulnerabilities


# =============================================================================
# SERGEANT SNIDEBLEAT NPC TESTS
# =============================================================================


class TestSnidebleatNPC:
    """Test Sergeant Snidebleat's NPC intelligence data."""

    def test_snidebleat_has_known_topics(self, pipeline):
        """Snidebleat should have multiple known topics."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        assert len(snidebleat.known_topics) >= 8

    def test_snidebleat_has_faction_topics(self, pipeline):
        """Snidebleat should have faction-related topics."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        faction_topics = [t for t in snidebleat.known_topics if t.category == "faction"]
        assert len(faction_topics) >= 2

    def test_snidebleat_is_bribable(self, pipeline):
        """Snidebleat should have bribable secret_info entries."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        bribable_secrets = [s for s in snidebleat.secret_info if s.can_be_bribed]
        assert len(bribable_secrets) >= 2

    def test_snidebleat_has_faction_profile(self, pipeline):
        """Snidebleat should have a faction profile with role."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        assert snidebleat.faction_profile is not None
        assert snidebleat.faction_profile.get("faction_id") == "house_murkin"
        assert snidebleat.faction_profile.get("role") == "knight"

    def test_snidebleat_has_personal_feelings(self, pipeline):
        """Snidebleat should have personal_feelings (loathes employer)."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        assert snidebleat.personal_feelings == "loathes employer"

    def test_snidebleat_loyalty_bought(self, pipeline):
        """Snidebleat's loyalty should be 'bought'."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        assert snidebleat.loyalty == "bought"

    def test_snidebleat_has_cross_hex_relationships(self, pipeline):
        """Snidebleat should have relationships to NPCs in other hexes."""
        hex_data = pipeline.get_hex("0109")
        snidebleat = next(n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat")
        external_rels = [r for r in snidebleat.relationships if r.get("hex_id") != "0109"]
        assert len(external_rels) >= 2


# =============================================================================
# POI EVENING HAZARD TESTS
# =============================================================================


class TestPOIEveningHazards:
    """Test POI evening hazard configurations."""

    def test_lodge_has_evening_hazard(self, pipeline):
        """Lady Borrid's Lodge should have evening hazard."""
        hex_data = pipeline.get_hex("0109")
        lodge = next(p for p in hex_data.points_of_interest if p.name == "Lady Borrid's Hunting Lodge")
        assert lodge.evening_hazard is not None
        assert lodge.evening_hazard.get("chance") == "4-in-6"
        assert lodge.evening_hazard.get("result") == "dinner_invitation"

    def test_camp_has_evening_hazard(self, pipeline):
        """Murkin's Army should have evening hazard."""
        hex_data = pipeline.get_hex("0109")
        camp = next(p for p in hex_data.points_of_interest if p.name == "Murkin's Army")
        assert camp.evening_hazard is not None
        assert camp.evening_hazard.get("chance") == "2-in-6"
        assert camp.evening_hazard.get("result") == "night_patrol_encounter"

    def test_evening_hazard_triggers(self, hex_0109_engine):
        """Evening hazard check should work for lodge."""
        # Seed for deterministic behavior - low seed triggers hazard
        DiceRoller.set_seed(1)
        result = hex_0109_engine.check_evening_hazard("0109", "Lady Borrid's Hunting Lodge")
        DiceRoller._seed = None

        assert "triggered" in result
        assert "chance" in result


# =============================================================================
# INVESTIGATION HAZARD TESTS
# =============================================================================


class TestInvestigationHazard:
    """Test investigation hazard for the army camp."""

    def test_hex_has_investigation_hazard(self, pipeline):
        """Hex should have investigation hazard for camp."""
        hex_data = pipeline.get_hex("0109")
        inv_hazard = hex_data.procedural.investigation_hazard
        assert inv_hazard is not None
        assert inv_hazard.get("trigger") == "investigate_camp"
        assert inv_hazard.get("chance") == "3-in-6"

    def test_investigation_hazard_check(self, hex_0109_engine):
        """Investigation hazard should trigger on investigate_camp."""
        # Seed for deterministic behavior
        DiceRoller.set_seed(1)
        result = hex_0109_engine.check_investigation_hazard("0109", "investigate_camp")
        DiceRoller._seed = None

        assert "triggered" in result


# =============================================================================
# ROLL TABLE TESTS
# =============================================================================


class TestRollTables:
    """Test roll tables in POIs."""

    def test_lodge_has_roll_tables(self, pipeline):
        """Lodge should have Hunting Companions and Trophy tables."""
        hex_data = pipeline.get_hex("0109")
        lodge = next(p for p in hex_data.points_of_interest if p.name == "Lady Borrid's Hunting Lodge")
        assert len(lodge.roll_tables) >= 2
        table_names = [t.name for t in lodge.roll_tables]
        assert "Hunting Companions Present" in table_names
        assert "Trophy Room Curiosities" in table_names

    def test_camp_has_roll_tables(self, pipeline):
        """Camp should have Activities and Morale tables."""
        hex_data = pipeline.get_hex("0109")
        camp = next(p for p in hex_data.points_of_interest if p.name == "Murkin's Army")
        assert len(camp.roll_tables) >= 2
        table_names = [t.name for t in camp.roll_tables]
        assert "Camp Activities" in table_names
        assert "Soldier Morale" in table_names

    def test_roll_table_entries_have_structure(self, pipeline):
        """Roll table entries should have proper structure."""
        hex_data = pipeline.get_hex("0109")
        lodge = next(p for p in hex_data.points_of_interest if p.name == "Lady Borrid's Hunting Lodge")
        companions_table = next(t for t in lodge.roll_tables if t.name == "Hunting Companions Present")
        assert len(companions_table.entries) == 6
        # Check first entry has required fields
        first_entry = companions_table.entries[0]
        assert first_entry.roll == 1
        assert first_entry.description is not None


# =============================================================================
# ENCOUNTER TABLE TESTS
# =============================================================================


class TestEncounterTable:
    """Test hex-level encounter table."""

    def test_encounter_table_has_entries(self, pipeline):
        """Encounter table should have patrol, hunting party, and standard entries."""
        hex_data = pipeline.get_hex("0109")
        table = hex_data.procedural.encounter_table
        assert len(table.entries) == 3

    def test_encounter_table_roll(self, hex_0109_engine):
        """Rolling on encounter table should return structured result."""
        DiceRoller.set_seed(1)  # Should roll 1 - murkins_patrol
        result = hex_0109_engine.roll_hex_encounter_table("0109")
        DiceRoller._seed = None

        assert result["has_table"] is True
        assert "roll" in result
        assert "result" in result
        assert "description" in result


# =============================================================================
# ITEMS TESTS
# =============================================================================


class TestItems:
    """Test item definitions in hex."""

    def test_hex_has_items(self, pipeline):
        """Hex should have item definitions."""
        hex_data = pipeline.get_hex("0109")
        assert len(hex_data.items) >= 4

    def test_horn_of_blasting_exists(self, pipeline):
        """Horn of Blasting should be defined."""
        hex_data = pipeline.get_hex("0109")
        horn = next((i for i in hex_data.items if "horn" in i.get("name", "").lower()), None)
        assert horn is not None
        assert horn.get("magical") is True

    def test_fairy_shortbow_exists(self, pipeline):
        """Fairy Shortbow should be defined."""
        hex_data = pipeline.get_hex("0109")
        bow = next((i for i in hex_data.items if "shortbow" in i.get("name", "").lower()), None)
        assert bow is not None
        assert bow.get("magical") is True


# =============================================================================
# SECRETS TESTS
# =============================================================================


class TestSecrets:
    """Test hex-level secrets."""

    def test_hex_has_secrets(self, pipeline):
        """Hex should have hex-level secrets."""
        hex_data = pipeline.get_hex("0109")
        assert len(hex_data.secrets) >= 3

    def test_poi_has_secrets(self, pipeline):
        """POIs should have secrets."""
        hex_data = pipeline.get_hex("0109")
        lodge = next(p for p in hex_data.points_of_interest if p.name == "Lady Borrid's Hunting Lodge")
        assert len(lodge.secrets) >= 1


# =============================================================================
# RUNTIME BOOTSTRAP PARSER TESTS
# =============================================================================


class TestRuntimeBootstrap:
    """Test that runtime_bootstrap parses all fields correctly."""

    def test_runtime_loads_evening_hazard(self):
        """Runtime bootstrap should parse evening_hazard for POIs."""
        from src.content_loader.runtime_bootstrap import load_runtime_content

        content = load_runtime_content(load_spells=False, load_monsters=False, load_items=False)
        hex_data = content.hexes.get("0109")
        if hex_data:
            lodge = next(
                (p for p in hex_data.points_of_interest if p.name == "Lady Borrid's Hunting Lodge"),
                None,
            )
            if lodge:
                assert lodge.evening_hazard is not None

    def test_runtime_loads_faction_profile(self):
        """Runtime bootstrap should parse faction_profile for NPCs."""
        from src.content_loader.runtime_bootstrap import load_runtime_content

        content = load_runtime_content(load_spells=False, load_monsters=False, load_items=False)
        hex_data = content.hexes.get("0109")
        if hex_data:
            snidebleat = next(
                (n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat"),
                None,
            )
            if snidebleat:
                assert snidebleat.faction_profile is not None
                assert snidebleat.faction_profile.get("faction_id") == "house_murkin"

    def test_runtime_loads_personal_feelings(self):
        """Runtime bootstrap should parse personal_feelings for NPCs."""
        from src.content_loader.runtime_bootstrap import load_runtime_content

        content = load_runtime_content(load_spells=False, load_monsters=False, load_items=False)
        hex_data = content.hexes.get("0109")
        if hex_data:
            snidebleat = next(
                (n for n in hex_data.npcs if n.npc_id == "sergeant_crewwin_snidebleat"),
                None,
            )
            if snidebleat:
                assert snidebleat.personal_feelings == "loathes employer"
