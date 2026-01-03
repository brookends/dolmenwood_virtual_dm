"""
Tests for hex 0106 (The Outlook and the Red Monolith) loading and enrichment.

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
def hex_0106_data() -> dict:
    """Load hex 0106 JSON data."""
    hex_file = Path("data/content/hexes/0106_the_outlook_and_the_red_monolith.json")
    with open(hex_file, "r") as f:
        return json.load(f)


@pytest.fixture
def hex_0106(hex_0106_data) -> HexLocation:
    """Parse hex 0106 into a HexLocation object."""
    return _parse_hex_json(hex_0106_data)


class TestHex0106Loading:
    """Tests for basic hex 0106 loading."""

    def test_hex_loads_without_errors(self, hex_0106):
        """Verify hex 0106 loads without raising exceptions."""
        assert hex_0106 is not None
        assert hex_0106.hex_id == "0106"
        assert hex_0106.name == "The Outlook and the Red Monolith"

    def test_hex_basic_properties(self, hex_0106):
        """Verify basic hex properties are set correctly."""
        assert hex_0106.terrain_type == "tangled forest"
        assert hex_0106.terrain_difficulty == 3
        assert hex_0106.region == "High Wold"
        assert hex_0106.coordinates == (1, 6)

    def test_hex_has_description(self, hex_0106):
        """Verify hex has enriched description."""
        assert "pale, wind-carved rock" in hex_0106.description
        assert "crimson glow" in hex_0106.description


class TestHex0106Procedural:
    """Tests for hex 0106 procedural section."""

    def test_procedural_section_populated(self, hex_0106):
        """Verify procedural section is present and populated."""
        assert hex_0106.procedural is not None
        assert hex_0106.procedural.lost_chance == "2-in-6"
        assert hex_0106.procedural.encounter_chance == "2-in-6"

    def test_lost_behavior_present(self, hex_0106):
        """Verify lost behavior is defined."""
        assert hex_0106.procedural.lost_behavior is not None
        assert hex_0106.procedural.lost_behavior["type"] == "disorienting"
        assert "crag" in hex_0106.procedural.lost_behavior["description"].lower()

    def test_night_hazards_present(self, hex_0106):
        """Verify night hazards are defined."""
        assert hex_0106.procedural.night_hazards is not None
        assert len(hex_0106.procedural.night_hazards) >= 2

        # Check for sleep hazard
        sleep_hazard = next(
            (h for h in hex_0106.procedural.night_hazards
             if "sleep" in h.get("trigger", "")),
            None
        )
        assert sleep_hazard is not None

        # Check for winter night hazard
        winter_hazard = next(
            (h for h in hex_0106.procedural.night_hazards
             if "winter" in h.get("trigger", "")),
            None
        )
        assert winter_hazard is not None

    def test_foraging_results_present(self, hex_0106):
        """Verify foraging results are defined."""
        assert hex_0106.procedural.foraging_results is not None
        assert "Wayfarrow" in hex_0106.procedural.foraging_results


class TestHex0106PointsOfInterest:
    """Tests for hex 0106 points of interest."""

    def test_all_pois_loaded(self, hex_0106):
        """Verify both POIs are loaded."""
        assert len(hex_0106.points_of_interest) == 2

    def test_granite_crag_poi(self, hex_0106):
        """Verify Granite Crag POI is enriched."""
        poi = next(
            (p for p in hex_0106.points_of_interest if p.name == "Granite Crag"),
            None
        )
        assert poi is not None
        assert poi.poi_type == "crag"

        # Check enriched fields
        assert poi.entering is not None
        assert "Climb Walls" in poi.entering
        assert poi.exploring is not None
        assert poi.leaving is not None

    def test_granite_crag_roll_table(self, hex_0106):
        """Verify Granite Crag has roll table."""
        poi = next(
            (p for p in hex_0106.points_of_interest if p.name == "Granite Crag"),
            None
        )
        assert len(poi.roll_tables) > 0

        table = poi.roll_tables[0]
        assert table.name == "Crag Base Discoveries"
        assert len(table.entries) == 6
        assert table.unique_entries is True

    def test_monolith_poi(self, hex_0106):
        """Verify The Red Vorpal Monolith POI is enriched."""
        poi = next(
            (p for p in hex_0106.points_of_interest if "Monolith" in p.name),
            None
        )
        assert poi is not None
        assert poi.poi_type == "monolith"

        # Check enriched fields
        assert poi.entering is not None
        assert poi.exploring is not None
        assert "winter" in poi.exploring.lower()

    def test_monolith_special_features(self, hex_0106):
        """Verify monolith has detailed special features."""
        poi = next(
            (p for p in hex_0106.points_of_interest if "Monolith" in p.name),
            None
        )
        assert len(poi.special_features) >= 4

        # Check for seasonal feature
        seasonal_feature = next(
            (f for f in poi.special_features if "seasonal" in f.lower()),
            None
        )
        assert seasonal_feature is not None

        # Check for terror feature
        terror_feature = next(
            (f for f in poi.special_features if "terror" in f.lower()),
            None
        )
        assert terror_feature is not None


class TestHex0106NoNPCs:
    """Tests confirming hex 0106 has no NPCs."""

    def test_no_npcs(self, hex_0106):
        """Verify hex has no NPCs (as expected)."""
        assert len(hex_0106.npcs) == 0


class TestHex0106Items:
    """Tests for hex 0106 items."""

    def test_items_present(self, hex_0106_data):
        """Verify items are defined in JSON."""
        assert "items" in hex_0106_data
        assert len(hex_0106_data["items"]) >= 2

    def test_bone_talisman(self, hex_0106_data):
        """Verify bone talisman is defined."""
        talisman = next(
            (i for i in hex_0106_data["items"] if "talisman" in i["name"].lower()),
            None
        )
        assert talisman is not None
        assert talisman["magical"] is True

    def test_obsidian_shard(self, hex_0106_data):
        """Verify obsidian shard is defined."""
        shard = next(
            (i for i in hex_0106_data["items"] if "obsidian" in i["name"].lower()),
            None
        )
        assert shard is not None
        assert shard["magical"] is True


class TestHex0106Hazards:
    """Tests for hex 0106 hazards in POI data."""

    def test_crag_has_hazards(self, hex_0106_data):
        """Verify Granite Crag has hazards defined."""
        crag = next(
            (p for p in hex_0106_data["points_of_interest"] if p["name"] == "Granite Crag"),
            None
        )
        assert "hazards" in crag
        assert len(crag["hazards"]) >= 2

        # Check for climbing hazard
        climbing_hazard = next(
            (h for h in crag["hazards"] if h["hazard_id"] == "climbing_check"),
            None
        )
        assert climbing_hazard is not None
        assert climbing_hazard["check_type"] == "dexterity"

    def test_monolith_has_hazards(self, hex_0106_data):
        """Verify Monolith has hazards defined."""
        monolith = next(
            (p for p in hex_0106_data["points_of_interest"] if "Monolith" in p["name"]),
            None
        )
        assert "hazards" in monolith
        assert len(monolith["hazards"]) >= 3

        # Check for terror hazard
        terror_hazard = next(
            (h for h in monolith["hazards"] if h["hazard_id"] == "monolith_viewing"),
            None
        )
        assert terror_hazard is not None
        assert terror_hazard["save_type"] == "spell"

        # Check for spell permanence hazard
        spell_hazard = next(
            (h for h in monolith["hazards"] if h["hazard_id"] == "monolith_touching"),
            None
        )
        assert spell_hazard is not None
        assert spell_hazard["effect"] == "spell_permanence"


class TestHex0106SeasonalBehavior:
    """Tests for seasonal behavior of the monolith."""

    def test_seasonal_behavior_defined(self, hex_0106_data):
        """Verify seasonal behavior is defined for the monolith."""
        monolith = next(
            (p for p in hex_0106_data["points_of_interest"] if "Monolith" in p["name"]),
            None
        )
        assert "seasonal_behavior" in monolith
        assert "winter" in monolith["seasonal_behavior"]
        assert "non_winter" in monolith["seasonal_behavior"]

    def test_winter_months_defined(self, hex_0106_data):
        """Verify winter months are listed."""
        monolith = next(
            (p for p in hex_0106_data["points_of_interest"] if "Monolith" in p["name"]),
            None
        )
        winter = monolith["seasonal_behavior"]["winter"]
        assert "months" in winter
        assert len(winter["months"]) == 3
        assert "Haggryme" in winter["months"]

    def test_winter_effects_active(self, hex_0106_data):
        """Verify winter effects are listed."""
        monolith = next(
            (p for p in hex_0106_data["points_of_interest"] if "Monolith" in p["name"]),
            None
        )
        winter = monolith["seasonal_behavior"]["winter"]
        assert "effects_active" in winter
        assert "terror_aura" in winter["effects_active"]
        assert "spell_permanence" in winter["effects_active"]


class TestHex0106ParsedPOIFields:
    """Tests for parsed POI objects containing all fields (not just raw JSON)."""

    def test_parsed_crag_has_hazards(self, hex_0106):
        """Verify parsed Granite Crag POI has hazards as list attribute."""
        crag = next(
            (p for p in hex_0106.points_of_interest if p.name == "Granite Crag"),
            None
        )
        assert crag is not None
        # Hazards should be a list on the parsed POI object
        assert hasattr(crag, "hazards")
        assert isinstance(crag.hazards, list)
        assert len(crag.hazards) >= 2

        # Check climbing hazard content
        climbing_hazard = next(
            (h for h in crag.hazards if h.get("hazard_id") == "climbing_check"),
            None
        )
        assert climbing_hazard is not None
        assert climbing_hazard["check_type"] == "dexterity"

    def test_parsed_monolith_has_hazards(self, hex_0106):
        """Verify parsed Monolith POI has hazards as list attribute."""
        monolith = next(
            (p for p in hex_0106.points_of_interest if "Monolith" in p.name),
            None
        )
        assert monolith is not None
        assert hasattr(monolith, "hazards")
        assert isinstance(monolith.hazards, list)
        assert len(monolith.hazards) >= 3

    def test_parsed_monolith_has_seasonal_behavior(self, hex_0106):
        """Verify parsed Monolith POI has seasonal_behavior as dict attribute."""
        monolith = next(
            (p for p in hex_0106.points_of_interest if "Monolith" in p.name),
            None
        )
        assert monolith is not None
        assert hasattr(monolith, "seasonal_behavior")
        assert monolith.seasonal_behavior is not None
        assert isinstance(monolith.seasonal_behavior, dict)
        assert "winter" in monolith.seasonal_behavior
        assert "non_winter" in monolith.seasonal_behavior

    def test_parsed_seasonal_behavior_winter_content(self, hex_0106):
        """Verify winter seasonal behavior content is correct."""
        monolith = next(
            (p for p in hex_0106.points_of_interest if "Monolith" in p.name),
            None
        )
        winter = monolith.seasonal_behavior["winter"]
        assert winter["state"] == "semi-corporeal"
        assert "terror_aura" in winter["effects_active"]
        assert "spell_permanence" in winter["effects_active"]

    def test_parsed_crag_has_roll_tables(self, hex_0106):
        """Verify parsed Crag POI has roll_tables as list of RollTable objects."""
        crag = next(
            (p for p in hex_0106.points_of_interest if p.name == "Granite Crag"),
            None
        )
        assert crag is not None
        assert len(crag.roll_tables) > 0
        # Roll tables should be RollTable objects, not dicts
        table = crag.roll_tables[0]
        assert hasattr(table, "name")
        assert hasattr(table, "unique_entries")
        assert table.name == "Crag Base Discoveries"
        assert table.unique_entries is True
