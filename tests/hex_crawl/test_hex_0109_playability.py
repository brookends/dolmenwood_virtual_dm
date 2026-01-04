"""
Tests for hex 0109 advanced POI field parsing (playability features).

This test suite validates that the hex loader correctly parses all
advanced POI fields required for automation:
- alerts (alarm systems)
- concealed_items (hidden items requiring search)
- locks (barriers/secret doors)
- sub_locations (nested areas within POI)
- entry_conditions (requirements to enter)
- variable_inhabitants (roll-based population)
"""

import pytest
from pathlib import Path

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader


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
def lodge_poi(pipeline):
    """Get Lady Borrid's Hunting Lodge POI."""
    hex_data = pipeline.get_hex("0109")
    return next(p for p in hex_data.points_of_interest if p.name == "Lady Borrid's Hunting Lodge")


@pytest.fixture
def camp_poi(pipeline):
    """Get Murkin's Army camp POI."""
    hex_data = pipeline.get_hex("0109")
    return next(p for p in hex_data.points_of_interest if p.name == "Murkin's Army")


# =============================================================================
# ALERTS PARSING TESTS
# =============================================================================


class TestAlertsParsing:
    """Test that alerts are correctly parsed from POI data."""

    def test_lodge_has_alerts(self, lodge_poi):
        """Lodge should have moose head alarm alert."""
        assert len(lodge_poi.alerts) >= 1

    def test_lodge_alert_structure(self, lodge_poi):
        """Lodge alert should have proper structure."""
        alert = lodge_poi.alerts[0]
        assert alert.get("alert_id") == "moose_head_alarm"
        assert alert.get("trigger") == "on_enter_unauthorized"
        assert alert.get("effect") == "alert_inhabitants"
        assert "moose" in alert.get("description", "").lower()

    def test_lodge_alert_has_bypass(self, lodge_poi):
        """Lodge alert should have bypass method."""
        alert = lodge_poi.alerts[0]
        assert "bypass_method" in alert
        assert "acorn" in alert["bypass_method"].lower()

    def test_camp_has_alerts(self, camp_poi):
        """Camp should have sentry alarm alert."""
        assert len(camp_poi.alerts) >= 1

    def test_camp_alert_structure(self, camp_poi):
        """Camp alert should have proper structure."""
        alert = camp_poi.alerts[0]
        assert alert.get("alert_id") == "sentry_alarm"
        assert alert.get("trigger") == "on_enter_unauthorized"
        assert alert.get("effect") == "summon_guards"


# =============================================================================
# CONCEALED ITEMS PARSING TESTS
# =============================================================================


class TestConcealedItemsParsing:
    """Test that concealed_items are correctly parsed from POI data."""

    def test_lodge_has_concealed_items(self, lodge_poi):
        """Lodge should have Horn of Blasting as concealed item."""
        assert len(lodge_poi.concealed_items) >= 1

    def test_lodge_concealed_item_structure(self, lodge_poi):
        """Lodge concealed item should have proper structure."""
        item = lodge_poi.concealed_items[0]
        assert item.get("item_id") == "0109:item:horn_of_blasting"
        assert item.get("name") == "Horn of Blasting"
        assert item.get("hidden_in") == "trophy collection"
        assert item.get("search_dc") == "thorough"
        assert item.get("found") is False

    def test_camp_has_concealed_items(self, camp_poi):
        """Camp should have Snidebleat's onyxes as concealed item."""
        assert len(camp_poi.concealed_items) >= 1

    def test_camp_concealed_item_structure(self, camp_poi):
        """Camp concealed item should have proper structure (Buried Coffer containing onyxes)."""
        item = camp_poi.concealed_items[0]
        assert item.get("item_id") == "0109:concealed:buried_coffer"
        assert item.get("name") == "Buried Coffer"
        assert "buried" in item.get("hidden_in", "").lower() or "tent" in item.get("hidden_in", "").lower()
        # The coffer contains the onyxes
        contained_items = item.get("items", [])
        assert len(contained_items) >= 1
        onyx_item = contained_items[0]
        assert "onyx" in onyx_item.get("name", "").lower()


# =============================================================================
# LOCKS PARSING TESTS
# =============================================================================


class TestLocksParsing:
    """Test that locks are correctly parsed from POI data."""

    def test_lodge_has_locks(self, lodge_poi):
        """Lodge should have vault door lock."""
        assert len(lodge_poi.locks) >= 1

    def test_lodge_lock_structure(self, lodge_poi):
        """Lodge lock should have proper structure."""
        lock = lodge_poi.locks[0]
        assert lock.get("lock_id") == "vault_door"
        assert lock.get("type") == "physical"
        assert lock.get("hidden") is True
        assert lock.get("detected") is False
        assert lock.get("bypassed") is False

    def test_camp_no_locks(self, camp_poi):
        """Camp should not have locks (open camp)."""
        assert len(camp_poi.locks) == 0


# =============================================================================
# SUB-LOCATIONS PARSING TESTS
# =============================================================================


class TestSubLocationsParsing:
    """Test that sub_locations are correctly parsed from POI data."""

    def test_lodge_has_sub_locations(self, lodge_poi):
        """Lodge should have Trophy Room, Cellars, Secret Vault."""
        assert len(lodge_poi.sub_locations) >= 3

    def test_lodge_sub_location_names(self, lodge_poi):
        """Lodge should have expected sub-location names."""
        names = [loc.get("name") for loc in lodge_poi.sub_locations]
        assert "Trophy Room" in names
        assert "Cellars" in names
        assert "Secret Vault" in names

    def test_lodge_vault_requires_secret_door(self, lodge_poi):
        """Secret Vault should require secret_door access."""
        vault = next(loc for loc in lodge_poi.sub_locations if loc.get("name") == "Secret Vault")
        assert vault.get("access_condition") == "secret_door"
        assert vault.get("visible_from") == "never"

    def test_lodge_vault_has_items(self, lodge_poi):
        """Secret Vault should list treasure items."""
        vault = next(loc for loc in lodge_poi.sub_locations if loc.get("name") == "Secret Vault")
        assert len(vault.get("items", [])) >= 2
        assert "0109:item:fairy_shortbow" in vault["items"]

    def test_camp_has_sub_locations(self, camp_poi):
        """Camp should have Command Tent, Prisoner Area, Supply Area, Training Ground."""
        assert len(camp_poi.sub_locations) >= 4

    def test_camp_sub_location_names(self, camp_poi):
        """Camp should have expected sub-location names."""
        names = [loc.get("name") for loc in camp_poi.sub_locations]
        assert "Command Tent" in names
        assert "Prisoner Holding Area" in names
        assert "Supply Area" in names
        assert "Training Ground" in names

    def test_camp_prisoner_area_structure(self, camp_poi):
        """Prisoner Holding Area should have proper structure."""
        prisoner_area = next(loc for loc in camp_poi.sub_locations if "Prisoner" in loc.get("name", ""))
        assert prisoner_area.get("visible_from") == "inside"
        assert "prisoners" in str(prisoner_area.get("features", [])).lower()


# =============================================================================
# ENTRY CONDITIONS PARSING TESTS
# =============================================================================


class TestEntryConditionsParsing:
    """Test that entry_conditions are correctly parsed from POI data."""

    def test_lodge_has_entry_conditions(self, lodge_poi):
        """Lodge should have entry conditions."""
        assert lodge_poi.entry_conditions is not None

    def test_lodge_entry_conditions_structure(self, lodge_poi):
        """Lodge entry conditions should have proper structure."""
        ec = lodge_poi.entry_conditions
        assert ec.get("type") == "permission_required"
        assert ec.get("check_type") == "social"
        assert ec.get("npc_id") == "lady_amonie_borrid"
        assert "outcomes" in ec
        assert "success" in ec["outcomes"]
        assert "failure" in ec["outcomes"]
        assert "hostile" in ec["outcomes"]

    def test_camp_has_entry_conditions(self, camp_poi):
        """Camp should have entry conditions."""
        assert camp_poi.entry_conditions is not None

    def test_camp_entry_conditions_structure(self, camp_poi):
        """Camp entry conditions should have proper structure."""
        ec = camp_poi.entry_conditions
        assert ec.get("type") == "interrogation"
        assert ec.get("check_type") == "social"
        assert ec.get("npc_id") == "sergeant_crewwin_snidebleat"


# =============================================================================
# VARIABLE INHABITANTS PARSING TESTS
# =============================================================================


class TestVariableInhabitantsParsing:
    """Test that variable_inhabitants are correctly parsed from POI data."""

    def test_lodge_has_variable_inhabitants(self, lodge_poi):
        """Lodge should have variable inhabitants."""
        assert lodge_poi.variable_inhabitants is not None

    def test_lodge_variable_inhabitants_structure(self, lodge_poi):
        """Lodge variable inhabitants should have proper structure."""
        vi = lodge_poi.variable_inhabitants
        assert "base_inhabitants" in vi
        assert "lady_amonie_borrid" in vi["base_inhabitants"]
        assert "variable" in vi
        assert len(vi["variable"]) >= 1
        assert vi["variable"][0].get("roll") == "1d6"

    def test_camp_has_variable_inhabitants(self, camp_poi):
        """Camp should have variable inhabitants."""
        assert camp_poi.variable_inhabitants is not None

    def test_camp_variable_inhabitants_structure(self, camp_poi):
        """Camp variable inhabitants should have proper structure."""
        vi = camp_poi.variable_inhabitants
        assert "base_inhabitants" in vi
        assert "sergeant_crewwin_snidebleat" in vi["base_inhabitants"]
        assert "variable" in vi
        assert len(vi["variable"]) >= 2  # sentries + prisoners


# =============================================================================
# FULL POI FIELD VERIFICATION
# =============================================================================


class TestFullPOIFieldCoverage:
    """Test that all expected POI fields are present and parsed."""

    def test_lodge_has_all_advanced_fields(self, lodge_poi):
        """Lodge should have all advanced POI fields populated."""
        assert lodge_poi.alerts is not None and len(lodge_poi.alerts) > 0
        assert lodge_poi.concealed_items is not None and len(lodge_poi.concealed_items) > 0
        assert lodge_poi.locks is not None and len(lodge_poi.locks) > 0
        assert lodge_poi.sub_locations is not None and len(lodge_poi.sub_locations) > 0
        assert lodge_poi.entry_conditions is not None
        assert lodge_poi.variable_inhabitants is not None

    def test_camp_has_all_advanced_fields(self, camp_poi):
        """Camp should have all advanced POI fields populated."""
        assert camp_poi.alerts is not None and len(camp_poi.alerts) > 0
        assert camp_poi.concealed_items is not None and len(camp_poi.concealed_items) > 0
        assert camp_poi.sub_locations is not None and len(camp_poi.sub_locations) > 0
        assert camp_poi.entry_conditions is not None
        assert camp_poi.variable_inhabitants is not None

    def test_core_fields_still_work(self, lodge_poi, camp_poi):
        """Core POI fields should still be parsed correctly."""
        # Lodge
        assert lodge_poi.name == "Lady Borrid's Hunting Lodge"
        assert lodge_poi.poi_type == "lodge"
        assert lodge_poi.evening_hazard is not None
        assert len(lodge_poi.roll_tables) >= 2
        assert len(lodge_poi.secrets) >= 1

        # Camp
        assert camp_poi.name == "Murkin's Army"
        assert camp_poi.poi_type == "military camp"
        assert camp_poi.evening_hazard is not None
        assert len(camp_poi.roll_tables) >= 2
        assert len(camp_poi.secrets) >= 1
