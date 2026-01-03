"""
Tests for hex 0107 (The Weeping Woman) loading and enrichment.

These tests verify that the enriched hex data loads correctly through the
runtime bootstrap system and that all enhanced features are accessible.
"""

import json
from pathlib import Path

import pytest

from src.content_loader.runtime_bootstrap import (
    _parse_hex_json,
    _parse_point_of_interest,
    _parse_roll_table,
)
from src.data_models import HexLocation


@pytest.fixture
def hex_0107_data() -> dict:
    """Load hex 0107 JSON data."""
    hex_file = Path("data/content/hexes/0107_the_weeping_woman.json")
    with open(hex_file, "r") as f:
        return json.load(f)


@pytest.fixture
def hex_0107(hex_0107_data) -> HexLocation:
    """Parse hex 0107 into a HexLocation object."""
    return _parse_hex_json(hex_0107_data)


class TestHex0107Loading:
    """Tests for basic hex 0107 loading."""

    def test_hex_loads_without_errors(self, hex_0107):
        """Verify hex 0107 loads without raising exceptions."""
        assert hex_0107 is not None
        assert hex_0107.hex_id == "0107"
        assert hex_0107.name == "The Weeping Woman"

    def test_hex_basic_properties(self, hex_0107):
        """Verify basic hex properties are set correctly."""
        assert hex_0107.terrain_type == "meadow"
        assert hex_0107.terrain_difficulty == 2
        assert hex_0107.region == "High Wold"
        assert hex_0107.coordinates == (1, 7)

    def test_hex_has_description(self, hex_0107):
        """Verify hex has enriched description."""
        assert "Weeping Woman" in hex_0107.description
        assert "pipe music" in hex_0107.description


class TestHex0107Procedural:
    """Tests for hex 0107 procedural section."""

    def test_procedural_section_populated(self, hex_0107):
        """Verify procedural section is present and populated."""
        assert hex_0107.procedural is not None
        assert hex_0107.procedural.lost_chance == "1-in-6"
        assert hex_0107.procedural.encounter_chance == "1-in-6"

    def test_lost_behavior_present(self, hex_0107):
        """Verify lost behavior is defined."""
        assert hex_0107.procedural.lost_behavior is not None
        assert hex_0107.procedural.lost_behavior["type"] == "drawn"
        assert "water" in hex_0107.procedural.lost_behavior["description"].lower()

    def test_night_hazards_present(self, hex_0107):
        """Verify night hazards are defined."""
        assert hex_0107.procedural.night_hazards is not None
        assert len(hex_0107.procedural.night_hazards) >= 2

        # Check for night enchantment hazard
        night_hazard = next(
            (h for h in hex_0107.procedural.night_hazards
             if "night" in h.get("trigger", "")),
            None
        )
        assert night_hazard is not None

        # Check for full moon hazard
        moon_hazard = next(
            (h for h in hex_0107.procedural.night_hazards
             if "moon" in h.get("trigger", "")),
            None
        )
        assert moon_hazard is not None
        assert moon_hazard["save_modifier"] == -4

    def test_foraging_results_present(self, hex_0107):
        """Verify foraging results are defined."""
        assert hex_0107.procedural.foraging_results is not None
        assert "Wolfsbane" in hex_0107.procedural.foraging_results


class TestHex0107PointsOfInterest:
    """Tests for hex 0107 points of interest."""

    def test_single_poi_loaded(self, hex_0107):
        """Verify the single POI is loaded."""
        assert len(hex_0107.points_of_interest) == 1

    def test_weeping_woman_poi(self, hex_0107):
        """Verify The Weeping Woman POI is enriched."""
        poi = hex_0107.points_of_interest[0]
        assert poi.name == "The Weeping Woman"
        assert poi.poi_type == "natural_formation"

        # Check enriched fields
        assert poi.entering is not None
        assert "cooler" in poi.entering.lower()
        assert poi.interior is not None
        assert poi.exploring is not None
        assert poi.leaving is not None

    def test_poi_has_roll_table(self, hex_0107):
        """Verify POI has roll table."""
        poi = hex_0107.points_of_interest[0]
        assert len(poi.roll_tables) > 0

        table = poi.roll_tables[0]
        assert table.name == "Fairy Dance Visions"
        assert len(table.entries) == 6

    def test_poi_special_features(self, hex_0107):
        """Verify POI has special features."""
        poi = hex_0107.points_of_interest[0]
        assert len(poi.special_features) >= 4


class TestHex0107Hazards:
    """Tests for hex 0107 hazards in POI data."""

    def test_poi_has_hazards(self, hex_0107_data):
        """Verify POI has hazards defined."""
        poi = hex_0107_data["points_of_interest"][0]
        assert "hazards" in poi
        assert len(poi["hazards"]) >= 4

    def test_drinking_hazard(self, hex_0107_data):
        """Verify drinking tears hazard is defined."""
        poi = hex_0107_data["points_of_interest"][0]
        drinking = next(
            (h for h in poi["hazards"] if h["hazard_id"] == "drinking_tears"),
            None
        )
        assert drinking is not None
        assert drinking["save_type"] == "spell"

    def test_reverie_hazard(self, hex_0107_data):
        """Verify enchanted reverie hazard is defined."""
        poi = hex_0107_data["points_of_interest"][0]
        reverie = next(
            (h for h in poi["hazards"] if h["hazard_id"] == "enchanted_reverie"),
            None
        )
        assert reverie is not None
        assert reverie["automatic"] is True

    def test_dawn_slumber_hazard(self, hex_0107_data):
        """Verify dawn slumber hazard is defined."""
        poi = hex_0107_data["points_of_interest"][0]
        slumber = next(
            (h for h in poi["hazards"] if h["hazard_id"] == "dawn_slumber"),
            None
        )
        assert slumber is not None
        assert slumber["effect"]["healing"] == "1d6 HP if undisturbed"

    def test_neveryon_dreams_hazard(self, hex_0107_data):
        """Verify Neveryon dreams hazard is defined."""
        poi = hex_0107_data["points_of_interest"][0]
        dreams = next(
            (h for h in poi["hazards"] if h["hazard_id"] == "neveryon_dreams"),
            None
        )
        assert dreams is not None
        assert dreams["long_term"] is True
        assert "6 months" in dreams["effect"]["duration"]


class TestHex0107NoNPCs:
    """Tests confirming hex 0107 has no NPCs."""

    def test_no_npcs(self, hex_0107):
        """Verify hex has no NPCs (as expected)."""
        assert len(hex_0107.npcs) == 0


class TestHex0107Items:
    """Tests for hex 0107 items."""

    def test_items_present(self, hex_0107_data):
        """Verify items are defined in JSON."""
        assert "items" in hex_0107_data
        assert len(hex_0107_data["items"]) >= 1

    def test_tear_vial(self, hex_0107_data):
        """Verify tear vial item is defined."""
        vial = next(
            (i for i in hex_0107_data["items"] if "tear" in i["name"].lower()),
            None
        )
        assert vial is not None
        assert vial["magical"] is True
        assert vial["mechanical_effect"]["save_modifier"] == 2


class TestHex0107Secrets:
    """Tests for hex 0107 secrets."""

    def test_hex_secrets_present(self, hex_0107_data):
        """Verify hex-level secrets are defined."""
        assert "secrets" in hex_0107_data
        assert len(hex_0107_data["secrets"]) >= 4

    def test_neveryon_mentioned(self, hex_0107_data):
        """Verify Neveryon is mentioned in secrets."""
        secrets_text = " ".join(hex_0107_data["secrets"])
        assert "Neveryon" in secrets_text

    def test_poi_secrets_present(self, hex_0107_data):
        """Verify POI-level secrets are defined."""
        poi = hex_0107_data["points_of_interest"][0]
        assert "secrets" in poi
        assert len(poi["secrets"]) >= 4


class TestHex0107ParsedPOIFields:
    """Tests for parsed POI objects containing all fields (not just raw JSON)."""

    def test_parsed_poi_has_hazards(self, hex_0107):
        """Verify parsed POI has hazards as list attribute."""
        poi = hex_0107.points_of_interest[0]
        assert hasattr(poi, "hazards")
        assert isinstance(poi.hazards, list)
        assert len(poi.hazards) >= 4

        # Check drinking_tears hazard is accessible
        drinking = next(
            (h for h in poi.hazards if h.get("hazard_id") == "drinking_tears"),
            None
        )
        assert drinking is not None
        assert drinking["save_type"] == "spell"

    def test_parsed_poi_has_visibility_fields(self, hex_0107):
        """Verify parsed POI has visibility-related fields."""
        poi = hex_0107.points_of_interest[0]
        assert hasattr(poi, "visible_from_distance")
        assert hasattr(poi, "approach_required")
        assert isinstance(poi.visible_from_distance, bool)
        assert isinstance(poi.approach_required, bool)

    def test_parsed_poi_has_roll_tables(self, hex_0107):
        """Verify parsed POI has roll_tables as list of RollTable objects."""
        poi = hex_0107.points_of_interest[0]
        assert len(poi.roll_tables) > 0
        # Roll tables should be RollTable objects, not dicts
        table = poi.roll_tables[0]
        assert hasattr(table, "name")
        assert hasattr(table, "entries")
        assert table.name == "Fairy Dance Visions"

    def test_parsed_poi_has_special_features(self, hex_0107):
        """Verify parsed POI has special_features list."""
        poi = hex_0107.points_of_interest[0]
        assert hasattr(poi, "special_features")
        assert isinstance(poi.special_features, list)
        assert len(poi.special_features) >= 4

    def test_parsed_poi_has_secrets(self, hex_0107):
        """Verify parsed POI has secrets list."""
        poi = hex_0107.points_of_interest[0]
        assert hasattr(poi, "secrets")
        assert isinstance(poi.secrets, list)
        assert len(poi.secrets) >= 4

    def test_parsed_poi_defaults_for_missing_fields(self, hex_0107):
        """Verify parsed POI has default values for optional fields."""
        poi = hex_0107.points_of_interest[0]
        # These fields should have default values even if not in JSON
        assert hasattr(poi, "seasonal_behavior")
        assert hasattr(poi, "quest_hooks")
        assert hasattr(poi, "locks")
        assert hasattr(poi, "alerts")
        # They should be None or empty list
        assert poi.seasonal_behavior is None or isinstance(poi.seasonal_behavior, dict)
        assert isinstance(poi.quest_hooks, list)
        assert isinstance(poi.locks, list)
        assert isinstance(poi.alerts, list)
