"""
Tests for hex 0101 (The Spectral Manse) loading and enrichment.

These tests verify that the enriched hex data loads correctly through the
runtime bootstrap system and that all enhanced POI features are accessible,
particularly dynamic_layout, availability, item_persistence, and quest_hooks.
"""

import json
from pathlib import Path

import pytest

from src.content_loader.runtime_bootstrap import (
    _parse_hex_json,
    _parse_point_of_interest,
    _parse_roll_table,
)
from src.data_models import HexLocation, PointOfInterest


@pytest.fixture
def hex_0101_data() -> dict:
    """Load hex 0101 JSON data."""
    hex_file = Path("data/content/hexes/hex_0101.json")
    with open(hex_file, "r") as f:
        return json.load(f)


@pytest.fixture
def hex_0101(hex_0101_data) -> HexLocation:
    """Parse hex 0101 into a HexLocation object."""
    return _parse_hex_json(hex_0101_data)


@pytest.fixture
def spectral_manse_poi(hex_0101) -> PointOfInterest:
    """Get The Spectral Manse POI from hex 0101."""
    poi = next(
        (p for p in hex_0101.points_of_interest if p.name == "The Spectral Manse"),
        None
    )
    assert poi is not None, "The Spectral Manse POI not found"
    return poi


class TestHex0101Loading:
    """Tests for basic hex 0101 loading."""

    def test_hex_loads_without_errors(self, hex_0101):
        """Verify hex 0101 loads without raising exceptions."""
        assert hex_0101 is not None
        assert hex_0101.hex_id == "0101"
        assert hex_0101.name == "The Spectral Manse"

    def test_hex_basic_properties(self, hex_0101):
        """Verify basic hex properties are set correctly."""
        assert hex_0101.terrain_type == "bog"
        assert hex_0101.terrain_difficulty == 3
        assert hex_0101.region == "Northern Scratch"
        assert hex_0101.coordinates == (1, 1)

    def test_hex_has_description(self, hex_0101):
        """Verify hex has enriched description."""
        assert "barren expanse" in hex_0101.description
        assert "stagnant pools" in hex_0101.description


class TestHex0101Procedural:
    """Tests for hex 0101 procedural section."""

    def test_procedural_section_populated(self, hex_0101):
        """Verify procedural section is present and populated."""
        assert hex_0101.procedural is not None
        assert hex_0101.procedural.lost_chance == "2-in-6"
        assert hex_0101.procedural.encounter_chance == "2-in-6"

    def test_encounter_modifiers_present(self, hex_0101):
        """Verify encounter modifiers contain bewildered banshee."""
        assert hex_0101.procedural.encounter_modifiers is not None
        assert len(hex_0101.procedural.encounter_modifiers) > 0

        banshee_mod = hex_0101.procedural.encounter_modifiers[0]
        assert banshee_mod["monster_id"] == "banshee"
        assert banshee_mod["chance"] == "2-in-6"
        assert banshee_mod["behavior"] == "non_hostile"

    def test_night_hazards_present(self, hex_0101):
        """Verify night hazards include dream transportation."""
        assert hex_0101.procedural.night_hazards is not None
        assert len(hex_0101.procedural.night_hazards) >= 1

        sleep_hazard = next(
            (h for h in hex_0101.procedural.night_hazards if h.get("trigger") == "sleep"),
            None
        )
        assert sleep_hazard is not None
        assert sleep_hazard["save_type"] == "spell"
        assert sleep_hazard["on_fail"]["destination"] == "The Spectral Manse"


class TestSpectralMansePOI:
    """Tests for The Spectral Manse POI core properties."""

    def test_poi_basic_properties(self, spectral_manse_poi):
        """Verify POI basic properties are set correctly."""
        assert spectral_manse_poi.name == "The Spectral Manse"
        assert spectral_manse_poi.poi_type == "manse"
        assert spectral_manse_poi.is_dungeon is True

    def test_poi_exploration_text(self, spectral_manse_poi):
        """Verify POI has exploration descriptions."""
        assert spectral_manse_poi.entering is not None
        assert "front door" in spectral_manse_poi.entering.lower()

        assert spectral_manse_poi.interior is not None
        assert "odd dimension" in spectral_manse_poi.interior.lower()

        assert spectral_manse_poi.exploring is not None
        assert "Rooms" in spectral_manse_poi.exploring


class TestSpectralManseDynamicLayout:
    """Tests for The Spectral Manse dynamic_layout field."""

    def test_dynamic_layout_is_present(self, spectral_manse_poi):
        """Verify dynamic_layout field exists and is populated."""
        assert hasattr(spectral_manse_poi, "dynamic_layout")
        assert spectral_manse_poi.dynamic_layout is not None
        assert isinstance(spectral_manse_poi.dynamic_layout, dict)

    def test_dynamic_layout_connections_per_room(self, spectral_manse_poi):
        """Verify connections_per_room is correctly parsed."""
        layout = spectral_manse_poi.dynamic_layout
        assert "connections_per_room" in layout
        assert layout["connections_per_room"] == "1d3"

    def test_dynamic_layout_table_references(self, spectral_manse_poi):
        """Verify room and encounter table references are present."""
        layout = spectral_manse_poi.dynamic_layout
        assert layout["room_table"] == "Rooms"
        assert layout["encounter_table"] == "Encounters"

    def test_dynamic_layout_description(self, spectral_manse_poi):
        """Verify layout description is present."""
        layout = spectral_manse_poi.dynamic_layout
        assert "description" in layout
        assert "crooked doors" in layout["description"]


class TestSpectralManseAvailability:
    """Tests for The Spectral Manse availability field."""

    def test_availability_is_present(self, spectral_manse_poi):
        """Verify availability field exists and is populated."""
        assert hasattr(spectral_manse_poi, "availability")
        assert spectral_manse_poi.availability is not None
        assert isinstance(spectral_manse_poi.availability, dict)

    def test_availability_type(self, spectral_manse_poi):
        """Verify availability type is set."""
        avail = spectral_manse_poi.availability
        assert "type" in avail
        assert avail["type"] == "special"

    def test_availability_hidden_message(self, spectral_manse_poi):
        """Verify hidden_message for when manse is unavailable."""
        avail = spectral_manse_poi.availability
        assert "hidden_message" in avail
        assert "blackthorns" in avail["hidden_message"]


class TestSpectralManseItemPersistence:
    """Tests for The Spectral Manse item_persistence field."""

    def test_item_persistence_is_present(self, spectral_manse_poi):
        """Verify item_persistence field exists and is populated."""
        assert hasattr(spectral_manse_poi, "item_persistence")
        assert spectral_manse_poi.item_persistence is not None
        assert isinstance(spectral_manse_poi.item_persistence, dict)

    def test_item_persistence_default(self, spectral_manse_poi):
        """Verify default item behavior is evaporate."""
        persist = spectral_manse_poi.item_persistence
        assert "default" in persist
        assert persist["default"] == "evaporate"

    def test_item_persistence_exceptions(self, spectral_manse_poi):
        """Verify Lord Hobbled's items persist."""
        persist = spectral_manse_poi.item_persistence
        assert "exceptions" in persist
        assert len(persist["exceptions"]) >= 1

        lord_exception = persist["exceptions"][0]
        assert lord_exception["owner_npc"] == "lord_hobbled_and_blackened"
        assert lord_exception["persists"] is True


class TestSpectralManseQuestHooks:
    """Tests for The Spectral Manse quest_hooks field."""

    def test_quest_hooks_is_present(self, spectral_manse_poi):
        """Verify quest_hooks field exists and is populated."""
        assert hasattr(spectral_manse_poi, "quest_hooks")
        assert spectral_manse_poi.quest_hooks is not None
        assert isinstance(spectral_manse_poi.quest_hooks, list)
        assert len(spectral_manse_poi.quest_hooks) >= 1

    def test_quest_hook_deliver_letter(self, spectral_manse_poi):
        """Verify deliver letter quest hook is properly parsed."""
        quest = next(
            (q for q in spectral_manse_poi.quest_hooks
             if q.get("quest_id") == "deliver_letter_to_ygraine"),
            None
        )
        assert quest is not None
        assert quest["title"] == "A Letter for Ygraine"
        assert quest["quest_giver"] == "lord_hobbled_and_blackened"
        assert quest["destination_npc"] == "ygraine_mordlin"

    def test_quest_hook_rewards(self, spectral_manse_poi):
        """Verify quest hook rewards are parsed."""
        quest = next(
            (q for q in spectral_manse_poi.quest_hooks
             if q.get("quest_id") == "deliver_letter_to_ygraine"),
            None
        )
        assert "reward_items" in quest
        assert "violin_of_lord_hobbled" in quest["reward_items"]
        assert "letter_to_ygraine" in quest["reward_items"]


class TestSpectralManseRollTables:
    """Tests for The Spectral Manse roll tables."""

    def test_has_roll_tables(self, spectral_manse_poi):
        """Verify roll tables are present."""
        assert len(spectral_manse_poi.roll_tables) == 2

    def test_rooms_table(self, spectral_manse_poi):
        """Verify Rooms table is correctly parsed."""
        rooms_table = next(
            (t for t in spectral_manse_poi.roll_tables if t.name == "Rooms"),
            None
        )
        assert rooms_table is not None
        assert rooms_table.die_type == "d6"
        assert len(rooms_table.entries) == 6

        # Check a specific room
        study = next(
            (e for e in rooms_table.entries if e.title == "Study"),
            None
        )
        assert study is not None
        assert "frost elf poetry" in study.description

    def test_encounters_table(self, spectral_manse_poi):
        """Verify Encounters table is correctly parsed."""
        encounters_table = next(
            (t for t in spectral_manse_poi.roll_tables if t.name == "Encounters"),
            None
        )
        assert encounters_table is not None
        assert encounters_table.die_type == "d8"
        assert len(encounters_table.entries) == 8

    def test_encounter_with_quest_hook(self, spectral_manse_poi):
        """Verify encounter entry has quest_hook reference."""
        encounters_table = next(
            (t for t in spectral_manse_poi.roll_tables if t.name == "Encounters"),
            None
        )
        # Roll 1 is Lord Hobbled with quest hook
        lord_encounter = next(
            (e for e in encounters_table.entries if e.roll == 1),
            None
        )
        assert lord_encounter is not None
        assert "Lord Hobbled-and-Blackened" in lord_encounter.description


class TestSpectralManseOtherFields:
    """Tests for other Spectral Manse POI fields."""

    def test_npcs_field(self, spectral_manse_poi):
        """Verify NPCs are referenced."""
        assert "lord_hobbled_and_blackened" in spectral_manse_poi.npcs

    def test_hazards_field_is_list(self, spectral_manse_poi):
        """Verify hazards field exists as list (even if empty)."""
        assert hasattr(spectral_manse_poi, "hazards")
        assert isinstance(spectral_manse_poi.hazards, list)

    def test_locks_field_is_list(self, spectral_manse_poi):
        """Verify locks field exists as list (even if empty)."""
        assert hasattr(spectral_manse_poi, "locks")
        assert isinstance(spectral_manse_poi.locks, list)

    def test_items_field_is_list(self, spectral_manse_poi):
        """Verify items field exists as list (even if empty)."""
        assert hasattr(spectral_manse_poi, "items")
        assert isinstance(spectral_manse_poi.items, list)


class TestHex0101NPCs:
    """Tests for hex 0101 NPCs."""

    def test_lord_hobbled_loaded(self, hex_0101):
        """Verify Lord Hobbled-and-Blackened is loaded."""
        lord = next(
            (n for n in hex_0101.npcs if n.npc_id == "lord_hobbled_and_blackened"),
            None
        )
        assert lord is not None
        assert lord.name == "Lord Hobbled-and-Blackened"
        assert lord.kindred == "Frost Elf"
        assert lord.alignment == "Neutral"

    def test_lord_hobbled_binding(self, hex_0101):
        """Verify Lord Hobbled has binding information."""
        lord = next(
            (n for n in hex_0101.npcs if n.npc_id == "lord_hobbled_and_blackened"),
            None
        )
        assert lord.binding is not None
        assert lord.binding["bound_to"] == "The Spectral Manse"
        assert lord.binding["can_leave"] is False

    def test_lord_hobbled_relationships(self, hex_0101):
        """Verify Lord Hobbled has relationships."""
        lord = next(
            (n for n in hex_0101.npcs if n.npc_id == "lord_hobbled_and_blackened"),
            None
        )
        assert len(lord.relationships) >= 2

        ygraine_rel = next(
            (r for r in lord.relationships if r.get("npc_id") == "ygraine_mordlin"),
            None
        )
        assert ygraine_rel is not None
        assert ygraine_rel["relationship_type"] == "love_interest"

    def test_lord_hobbled_known_topics(self, hex_0101):
        """Verify Lord Hobbled has topic intelligence."""
        lord = next(
            (n for n in hex_0101.npcs if n.npc_id == "lord_hobbled_and_blackened"),
            None
        )
        assert len(lord.known_topics) >= 5

        quest_topic = next(
            (t for t in lord.known_topics if t.topic_id == "quest_deliver_letter"),
            None
        )
        assert quest_topic is not None
        assert quest_topic.category == "quest"


class TestHex0101Items:
    """Tests for hex 0101 items."""

    def test_hex_items_loaded(self, hex_0101):
        """Verify hex-level items are loaded."""
        assert len(hex_0101.items) >= 2

    def test_violin_item(self, hex_0101):
        """Verify magical violin item is loaded."""
        violin = next(
            (i for i in hex_0101.items if i.get("item_id") == "violin_of_lord_hobbled"),
            None
        )
        assert violin is not None
        assert violin["value"] == 10000
        assert violin["magical"] is True

    def test_letter_item(self, hex_0101):
        """Verify letter to Ygraine is loaded."""
        letter = next(
            (i for i in hex_0101.items if i.get("item_id") == "letter_to_ygraine"),
            None
        )
        assert letter is not None
        assert letter["quest_item"] is True
        assert letter["quest_id"] == "deliver_letter_to_ygraine"


class TestPOIFieldsDirectParsing:
    """Tests for direct POI parsing to verify all fields are preserved."""

    def test_parse_poi_preserves_dynamic_layout(self, hex_0101_data):
        """Verify _parse_point_of_interest preserves dynamic_layout."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert poi.dynamic_layout is not None
        assert poi.dynamic_layout["connections_per_room"] == "1d3"

    def test_parse_poi_preserves_availability(self, hex_0101_data):
        """Verify _parse_point_of_interest preserves availability."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert poi.availability is not None
        assert poi.availability["type"] == "special"

    def test_parse_poi_preserves_item_persistence(self, hex_0101_data):
        """Verify _parse_point_of_interest preserves item_persistence."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert poi.item_persistence is not None
        assert poi.item_persistence["default"] == "evaporate"

    def test_parse_poi_preserves_quest_hooks(self, hex_0101_data):
        """Verify _parse_point_of_interest preserves quest_hooks."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert len(poi.quest_hooks) >= 1
        assert poi.quest_hooks[0]["quest_id"] == "deliver_letter_to_ygraine"

    def test_parse_poi_preserves_all_dungeon_fields(self, hex_0101_data):
        """Verify all dungeon-related POI fields are preserved."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert poi.is_dungeon is True
        assert poi.dungeon_levels is None  # Spectral Manse uses dynamic layout instead
        assert poi.dynamic_layout is not None
        assert poi.item_persistence is not None


class TestPOIRawDataEscapeHatch:
    """Tests for POI raw_data field that preserves original JSON for future schema expansion."""

    def test_raw_data_contains_original_json(self, hex_0101_data):
        """Verify raw_data contains the original POI JSON data."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert hasattr(poi, "raw_data")
        assert isinstance(poi.raw_data, dict)
        assert poi.raw_data is poi_data  # Should be the same dict reference

    def test_raw_data_name_matches_parsed_name(self, hex_0101_data):
        """Verify poi.raw_data.get('name') == poi.name as per acceptance criteria."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        assert poi.raw_data.get("name") == poi.name

    def test_raw_data_preserves_all_original_fields(self, hex_0101_data):
        """Verify raw_data contains all original fields from JSON."""
        poi_data = hex_0101_data["points_of_interest"][0]
        poi = _parse_point_of_interest(poi_data)

        # Check several fields exist in raw_data
        assert poi.raw_data.get("poi_type") == "manse"
        assert poi.raw_data.get("is_dungeon") is True
        assert "dynamic_layout" in poi.raw_data
        assert "roll_tables" in poi.raw_data

    def test_raw_data_allows_access_to_unparsed_fields(self, spectral_manse_poi):
        """Verify raw_data allows access to fields not yet formally parsed."""
        # raw_data allows engines to access new fields before formal support
        assert spectral_manse_poi.raw_data is not None

        # Can access existing fields via raw_data
        assert spectral_manse_poi.raw_data.get("poi_type") == spectral_manse_poi.poi_type

    def test_raw_data_available_on_loaded_hex_poi(self, hex_0101):
        """Verify raw_data is available on POIs loaded through full hex parsing."""
        poi = next(
            (p for p in hex_0101.points_of_interest if p.name == "The Spectral Manse"),
            None
        )
        assert poi is not None
        assert hasattr(poi, "raw_data")
        assert poi.raw_data.get("name") == "The Spectral Manse"
