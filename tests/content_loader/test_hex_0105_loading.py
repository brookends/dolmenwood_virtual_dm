"""
Tests for hex 0105 (The Demesne of the Frore Gryphus) loading and enrichment.

These tests verify that the enriched hex data loads correctly through the
runtime bootstrap system and that all enhanced features are accessible.
"""

import json
from pathlib import Path

import pytest

from src.content_loader.runtime_bootstrap import (
    _parse_hex_json,
    _parse_hex_npc,
    _parse_known_topic,
    _parse_secret_info,
    _parse_point_of_interest,
    _parse_roll_table,
)
from src.data_models import HexLocation, HexNPC, KnownTopic, SecretInfo


@pytest.fixture
def hex_0105_data() -> dict:
    """Load hex 0105 JSON data."""
    hex_file = Path("data/content/hexes/0105_the_demesne_of_the_frore_gryphus.json")
    with open(hex_file, "r") as f:
        return json.load(f)


@pytest.fixture
def hex_0105(hex_0105_data) -> HexLocation:
    """Parse hex 0105 into a HexLocation object."""
    return _parse_hex_json(hex_0105_data)


class TestHex0105Loading:
    """Tests for basic hex 0105 loading."""

    def test_hex_loads_without_errors(self, hex_0105):
        """Verify hex 0105 loads without raising exceptions."""
        assert hex_0105 is not None
        assert hex_0105.hex_id == "0105"
        assert hex_0105.name == "The Demesne of the Frore Gryphus"

    def test_hex_basic_properties(self, hex_0105):
        """Verify basic hex properties are set correctly."""
        assert hex_0105.terrain_type == "meadow"
        assert hex_0105.terrain_difficulty == 2
        assert hex_0105.region == "High Wold"
        assert hex_0105.coordinates == (1, 5)

    def test_hex_has_description(self, hex_0105):
        """Verify hex has enriched description."""
        assert "blue-green grass" in hex_0105.description
        assert "Frost-covered patches" in hex_0105.description


class TestHex0105Procedural:
    """Tests for hex 0105 procedural section."""

    def test_procedural_section_populated(self, hex_0105):
        """Verify procedural section is present and populated."""
        assert hex_0105.procedural is not None
        assert hex_0105.procedural.lost_chance == "1-in-6"
        assert hex_0105.procedural.encounter_chance == "1-in-6"

    def test_encounter_modifiers_present(self, hex_0105):
        """Verify encounter modifiers contain frore gryphus data."""
        assert hex_0105.procedural.encounter_modifiers is not None
        assert len(hex_0105.procedural.encounter_modifiers) > 0

        gryphus_mod = hex_0105.procedural.encounter_modifiers[0]
        assert gryphus_mod["monster_id"] == "frore_gryphus"
        assert gryphus_mod["chance"] == "3-in-6"

    def test_lost_behavior_present(self, hex_0105):
        """Verify lost behavior is defined."""
        assert hex_0105.procedural.lost_behavior is not None
        assert hex_0105.procedural.lost_behavior["type"] == "standard"

    def test_night_hazards_present(self, hex_0105):
        """Verify night hazards are defined."""
        assert hex_0105.procedural.night_hazards is not None
        assert len(hex_0105.procedural.night_hazards) >= 1

        # Check for sleep hazard
        sleep_hazard = None
        for hazard in hex_0105.procedural.night_hazards:
            if hazard.get("trigger") == "sleep":
                sleep_hazard = hazard
                break

        assert sleep_hazard is not None
        assert "save_type" in sleep_hazard

    def test_foraging_results_present(self, hex_0105):
        """Verify foraging results are defined."""
        assert hex_0105.procedural.foraging_results is not None
        assert "Meadow Herbs" in hex_0105.procedural.foraging_results


class TestHex0105PointsOfInterest:
    """Tests for hex 0105 points of interest."""

    def test_all_pois_loaded(self, hex_0105):
        """Verify all 3 POIs are loaded."""
        assert len(hex_0105.points_of_interest) == 3

    def test_frozen_battleground_poi(self, hex_0105):
        """Verify Frozen Battleground POI is enriched."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Frozen Battleground"),
            None
        )
        assert poi is not None
        assert poi.poi_type == "battleground"

        # Check enriched fields
        assert poi.entering is not None
        assert "temperature drops" in poi.entering.lower()
        assert poi.exploring is not None
        assert poi.leaving is not None

    def test_frozen_battleground_roll_table(self, hex_0105):
        """Verify Frozen Battleground has roll table."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Frozen Battleground"),
            None
        )
        assert len(poi.roll_tables) > 0

        table = poi.roll_tables[0]
        assert table.name == "Battlefield Discoveries"
        assert len(table.entries) == 6

    def test_shepherd_encampment_poi(self, hex_0105):
        """Verify Shepherd Encampment POI is enriched."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Shepherd Encampment"),
            None
        )
        assert poi is not None
        assert poi.poi_type == "encampment"

        # Check NPC reference
        assert "aegnyth_cormick" in poi.npcs

    def test_nest_poi_is_dungeon(self, hex_0105):
        """Verify The Nest is marked as dungeon."""
        poi = next(
            (p for p in hex_0105.points_of_interest if "Nest" in p.name),
            None
        )
        assert poi is not None
        assert poi.is_dungeon is True
        assert poi.hidden is True

    def test_nest_has_encounter_table(self, hex_0105):
        """Verify The Nest has encounter table."""
        poi = next(
            (p for p in hex_0105.points_of_interest if "Nest" in p.name),
            None
        )
        assert len(poi.roll_tables) > 0

        table = poi.roll_tables[0]
        assert table.name == "Nest Encounters"


class TestHex0105NPCs:
    """Tests for hex 0105 NPCs with topic intelligence."""

    def test_all_npcs_loaded(self, hex_0105):
        """Verify both NPCs are loaded."""
        assert len(hex_0105.npcs) == 2

    def test_aegnyth_cormick_basic(self, hex_0105):
        """Verify Aegnyth Cormick basic properties."""
        aegnyth = next(
            (n for n in hex_0105.npcs if n.npc_id == "aegnyth_cormick"),
            None
        )
        assert aegnyth is not None
        assert aegnyth.name == "Aegnyth Cormick"
        assert aegnyth.kindred == "Human"
        assert aegnyth.alignment == "Lawful"

    def test_aegnyth_vulnerabilities(self, hex_0105):
        """Verify Aegnyth has vulnerabilities."""
        aegnyth = next(
            (n for n in hex_0105.npcs if n.npc_id == "aegnyth_cormick"),
            None
        )
        assert len(aegnyth.vulnerabilities) > 0
        assert "concern_for_flock" in aegnyth.vulnerabilities

    def test_aegnyth_known_topics(self, hex_0105):
        """Verify Aegnyth has known_topics parsed as KnownTopic objects."""
        aegnyth = next(
            (n for n in hex_0105.npcs if n.npc_id == "aegnyth_cormick"),
            None
        )
        assert len(aegnyth.known_topics) >= 5

        # Verify they are KnownTopic objects
        quest_topic = next(
            (t for t in aegnyth.known_topics if t.topic_id == "frore_gryphus_quest"),
            None
        )
        assert quest_topic is not None
        assert isinstance(quest_topic, KnownTopic)
        assert quest_topic.category == "quest"
        assert quest_topic.priority == 10
        assert "gryphus" in quest_topic.keywords

    def test_aegnyth_secret_info(self, hex_0105):
        """Verify Aegnyth has secret_info parsed as SecretInfo objects."""
        aegnyth = next(
            (n for n in hex_0105.npcs if n.npc_id == "aegnyth_cormick"),
            None
        )
        assert len(aegnyth.secret_info) >= 2

        # Verify they are SecretInfo objects
        cold_prince_secret = next(
            (s for s in aegnyth.secret_info if s.secret_id == "cold_prince_connection"),
            None
        )
        assert cold_prince_secret is not None
        assert isinstance(cold_prince_secret, SecretInfo)
        assert cold_prince_secret.required_disposition == 2
        assert cold_prince_secret.required_trust == 1

    def test_aegnyth_relationships(self, hex_0105):
        """Verify Aegnyth has relationships."""
        aegnyth = next(
            (n for n in hex_0105.npcs if n.npc_id == "aegnyth_cormick"),
            None
        )
        assert len(aegnyth.relationships) >= 2

        # Check for sister relationship
        sister_rel = next(
            (r for r in aegnyth.relationships if r.get("npc_id") == "marged_cormick"),
            None
        )
        assert sister_rel is not None
        assert sister_rel["relationship_type"] == "family"
        assert sister_rel["hex_id"] == "0108"

    def test_frore_gryphus_npc(self, hex_0105):
        """Verify frore gryphus is loaded as NPC."""
        gryphus = next(
            (n for n in hex_0105.npcs if n.npc_id == "frore_gryphus"),
            None
        )
        assert gryphus is not None
        assert gryphus.kindred == "Fairy"
        assert gryphus.is_combatant is True

    def test_frore_gryphus_vulnerabilities(self, hex_0105):
        """Verify frore gryphus has cold_iron vulnerability (fairy requirement)."""
        gryphus = next(
            (n for n in hex_0105.npcs if n.npc_id == "frore_gryphus"),
            None
        )
        assert "cold_iron" in gryphus.vulnerabilities

    def test_frore_gryphus_faction(self, hex_0105):
        """Verify frore gryphus has faction connection."""
        gryphus = next(
            (n for n in hex_0105.npcs if n.npc_id == "frore_gryphus"),
            None
        )
        assert gryphus.faction == "cold_prince"
        assert gryphus.loyalty == "independent"


class TestNPCTopicParsing:
    """Tests for NPC topic intelligence parsing."""

    def test_parse_known_topic_minimal(self):
        """Test parsing a minimal known topic."""
        data = {
            "topic_id": "test_topic",
            "content": "Test content"
        }
        topic = _parse_known_topic(data)

        assert topic.topic_id == "test_topic"
        assert topic.content == "Test content"
        assert topic.required_disposition == -5  # default
        assert topic.category == "general"  # default
        assert topic.priority == 0  # default

    def test_parse_known_topic_full(self):
        """Test parsing a fully specified known topic."""
        data = {
            "topic_id": "full_topic",
            "content": "Full content",
            "keywords": ["test", "example"],
            "required_disposition": 2,
            "category": "quest",
            "shared": True,
            "priority": 10
        }
        topic = _parse_known_topic(data)

        assert topic.topic_id == "full_topic"
        assert topic.keywords == ["test", "example"]
        assert topic.required_disposition == 2
        assert topic.category == "quest"
        assert topic.shared is True
        assert topic.priority == 10

    def test_parse_secret_info_minimal(self):
        """Test parsing a minimal secret info."""
        data = {
            "secret_id": "test_secret",
            "content": "Secret content"
        }
        secret = _parse_secret_info(data)

        assert secret.secret_id == "test_secret"
        assert secret.content == "Secret content"
        assert secret.required_disposition == 3  # default
        assert secret.required_trust == 2  # default

    def test_parse_secret_info_full(self):
        """Test parsing a fully specified secret info."""
        data = {
            "secret_id": "full_secret",
            "content": "Full secret",
            "hint": "A subtle hint",
            "keywords": ["secret", "hidden"],
            "required_disposition": 4,
            "required_trust": 3,
            "can_be_bribed": True,
            "bribe_amount": 100,
            "status": "hinted",
            "hint_count": 2
        }
        secret = _parse_secret_info(data)

        assert secret.secret_id == "full_secret"
        assert secret.hint == "A subtle hint"
        assert secret.required_disposition == 4
        assert secret.required_trust == 3
        assert secret.can_be_bribed is True
        assert secret.bribe_amount == 100

    def test_parse_hex_npc_with_topics(self):
        """Test parsing an NPC with topic intelligence."""
        data = {
            "npc_id": "test_npc",
            "name": "Test NPC",
            "description": "A test NPC",
            "known_topics": [
                {"topic_id": "t1", "content": "Topic 1", "category": "quest"},
                {"topic_id": "t2", "content": "Topic 2", "category": "lore"}
            ],
            "secret_info": [
                {"secret_id": "s1", "content": "Secret 1", "required_trust": 1}
            ],
            "relationships": [
                {"npc_id": "other", "relationship_type": "ally"}
            ],
            "binding": {"bound_to": "A location", "can_leave": False}
        }
        npc = _parse_hex_npc(data)

        assert npc.npc_id == "test_npc"
        assert len(npc.known_topics) == 2
        assert isinstance(npc.known_topics[0], KnownTopic)
        assert len(npc.secret_info) == 1
        assert isinstance(npc.secret_info[0], SecretInfo)
        assert len(npc.relationships) == 1
        assert npc.binding is not None
        assert npc.binding["bound_to"] == "A location"


class TestHex0105ParsedPOIFields:
    """Tests for parsed POI objects containing all fields (not just raw JSON)."""

    def test_parsed_battleground_has_hazards(self, hex_0105):
        """Verify parsed Frozen Battleground POI has hazards as list attribute."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Frozen Battleground"),
            None
        )
        assert poi is not None
        # Hazards should be a list on the parsed POI object
        assert hasattr(poi, "hazards")
        assert isinstance(poi.hazards, list)

    def test_parsed_nest_has_hazards(self, hex_0105):
        """Verify parsed Nest POI has hazards as list attribute."""
        poi = next(
            (p for p in hex_0105.points_of_interest if "Nest" in p.name),
            None
        )
        assert poi is not None
        assert hasattr(poi, "hazards")
        assert isinstance(poi.hazards, list)

    def test_parsed_encampment_has_quest_hooks(self, hex_0105):
        """Verify parsed Shepherd Encampment POI has quest_hooks as list attribute."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Shepherd Encampment"),
            None
        )
        assert poi is not None
        assert hasattr(poi, "quest_hooks")
        assert isinstance(poi.quest_hooks, list)
        # The encampment has a quest hook for the gryphus hunt
        assert len(poi.quest_hooks) >= 1

    def test_parsed_poi_has_visibility_fields(self, hex_0105):
        """Verify parsed POIs have visibility-related fields."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Frozen Battleground"),
            None
        )
        assert poi is not None
        assert hasattr(poi, "visible_from_distance")
        assert hasattr(poi, "approach_required")
        assert isinstance(poi.visible_from_distance, bool)
        assert isinstance(poi.approach_required, bool)

    def test_parsed_nest_is_hidden(self, hex_0105):
        """Verify parsed Nest POI has hidden flag set correctly."""
        poi = next(
            (p for p in hex_0105.points_of_interest if "Nest" in p.name),
            None
        )
        assert poi is not None
        assert poi.hidden is True

    def test_parsed_poi_has_roll_tables(self, hex_0105):
        """Verify parsed POI has roll_tables as list of RollTable objects."""
        poi = next(
            (p for p in hex_0105.points_of_interest if p.name == "Frozen Battleground"),
            None
        )
        assert poi is not None
        assert len(poi.roll_tables) > 0
        # Roll tables should be RollTable objects, not dicts
        table = poi.roll_tables[0]
        assert hasattr(table, "name")
        assert hasattr(table, "entries")
        assert table.name == "Battlefield Discoveries"
