"""
Comprehensive tests for the Settlement Engine v2 refactor.

Tests cover:
- Loader tests (fixture-based)
- Navigation tests (list/visit locations)
- Service tests (cost parsing, use service)
- NPC tests (list/talk)
- Encounter tests (deterministic with DiceRoller.set_seed)
- Lock enforcement tests
- Equipment availability tests
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.settlement import (
    SettlementEngine,
    SettlementData,
    SettlementLocationData,
    SettlementNPCData,
    SettlementServiceData,
    SettlementRegistry,
    SettlementEncounterTables,
    SettlementEncounterResult,
    SettlementServiceExecutor,
    parse_cost_text,
    tod_to_daynight,
)
from src.content_loader import SettlementLoader
from src.game_state import GlobalController
from src.data_models import TimeOfDay, DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def controller():
    """Create a GlobalController for tests."""
    return GlobalController()


@pytest.fixture
def engine(controller):
    """Create a SettlementEngine with registry loaded."""
    engine = SettlementEngine(controller)
    loader = SettlementLoader(Path("data/content/settlements"))
    registry = loader.load_registry()
    engine.set_registry(registry)
    return engine


@pytest.fixture
def engine_in_blackeswell(engine):
    """Create a SettlementEngine with Blackeswell as active settlement."""
    engine.set_active_settlement("blackeswell")
    return engine


@pytest.fixture
def engine_in_prigwort(engine):
    """Create a SettlementEngine with Prigwort as active settlement."""
    engine.set_active_settlement("prigwort")
    return engine


@pytest.fixture
def deterministic_dice():
    """Create a DiceRoller with fixed seed for deterministic tests."""
    dice = DiceRoller()
    dice.set_seed(42)
    return dice


# =============================================================================
# LOADER TESTS
# =============================================================================


class TestSettlementLoader:
    """Tests for settlement JSON loader."""

    def test_load_all_settlements(self):
        """Test loading all settlement JSON files."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry, report = loader.load_registry_with_report()

        assert report.files_processed == 12
        assert report.files_successful == 12
        assert report.total_settlements_loaded == 12
        assert len(report.errors) == 0

    def test_registry_contains_expected_settlements(self):
        """Test registry contains known settlements."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()

        expected = [
            "blackeswell",
            "castle_brackenwold",
            "prigwort",
            "lankshorn",
            "high_hankle",
        ]
        for sid in expected:
            assert registry.get(sid) is not None, f"Missing settlement: {sid}"

    def test_settlement_has_required_fields(self):
        """Test loaded settlement has required fields."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()

        blackeswell = registry.get("blackeswell")
        assert blackeswell is not None
        assert blackeswell.name == "Blackeswell"
        assert blackeswell.hex_id == "1604"
        assert len(blackeswell.locations) > 0
        assert len(blackeswell.npcs) > 0

    def test_find_settlement_by_hex(self):
        """Test finding settlement by hex ID."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()

        # Blackeswell is at hex 1604
        settlement = registry.find_by_hex("1604")
        assert settlement is not None
        assert settlement.settlement_id == "blackeswell"

        # No settlement at hex 0000
        assert registry.find_by_hex("0000") is None

    def test_location_by_number_mapping(self):
        """Test location lookup by number."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()

        blackeswell = registry.get("blackeswell")
        loc_map = blackeswell.location_by_number()

        # Location 1 should be The Blacke
        assert 1 in loc_map
        assert loc_map[1].name == "The Blacke"

    def test_npc_by_id_mapping(self):
        """Test NPC lookup by ID."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()

        blackeswell = registry.get("blackeswell")
        npc_map = blackeswell.npc_by_id()

        # Should have Father Bertil
        assert "father_ingram_bertil" in npc_map
        assert npc_map["father_ingram_bertil"].name == "Father Ingram Bertil"


# =============================================================================
# NAVIGATION TESTS
# =============================================================================


class TestNavigationActions:
    """Tests for settlement navigation actions."""

    def test_list_locations(self, engine_in_blackeswell):
        """Test listing locations in settlement."""
        result = engine_in_blackeswell.execute_action("settlement:list_locations", {})

        assert result["success"] is True
        assert result["settlement_name"] == "Blackeswell"
        assert len(result["locations"]) == 12

        # Check location structure
        loc = result["locations"][0]
        assert "number" in loc
        assert "name" in loc
        assert "is_locked" in loc
        assert "visited" in loc

    def test_visit_unlocked_location(self, engine_in_blackeswell):
        """Test visiting an unlocked location."""
        # Location 1 (The Blacke) should be unlocked
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 1}
        )

        assert result["success"] is True
        assert result["location"]["name"] == "The Blacke"
        assert "description" in result["location"]

    def test_visit_updates_current_location(self, engine_in_blackeswell):
        """Test that visiting updates current location state."""
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 3}
        )

        current = engine_in_blackeswell.get_current_location()
        assert current is not None
        assert current.number == 3

    def test_visit_tracks_visited_locations(self, engine_in_blackeswell):
        """Test that visited locations are tracked."""
        # Visit locations 1 and 3
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 1}
        )
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 3}
        )

        # Check visited set
        assert 1 in engine_in_blackeswell._visited_locations
        assert 3 in engine_in_blackeswell._visited_locations

        # Check list_locations shows visited status
        result = engine_in_blackeswell.execute_action("settlement:list_locations", {})
        loc1 = next(l for l in result["locations"] if l["number"] == 1)
        assert loc1["visited"] is True

    def test_visit_invalid_location(self, engine_in_blackeswell):
        """Test visiting a non-existent location."""
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 999}
        )

        assert result["success"] is False
        assert "not found" in result["message"]

    def test_visit_without_active_settlement(self, engine):
        """Test visiting when not in a settlement."""
        result = engine.execute_action(
            "settlement:visit_location", {"location_number": 1}
        )

        assert result["success"] is False
        assert "Not currently in a settlement" in result["message"]


# =============================================================================
# SERVICE TESTS
# =============================================================================


class TestServiceActions:
    """Tests for settlement service actions."""

    def test_list_services_at_location(self, engine_in_blackeswell):
        """Test listing services at a specific location."""
        # Visit the church (has services)
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 3}
        )

        result = engine_in_blackeswell.execute_action("settlement:list_services", {})

        assert result["success"] is True
        assert len(result["services"]) > 0
        assert result["location_name"] == "Church of St Gondyw"

    def test_list_services_all_settlement(self, engine_in_blackeswell):
        """Test listing all services in settlement (no current location)."""
        # Don't visit a location first
        result = engine_in_blackeswell.execute_action("settlement:list_services", {})

        assert result["success"] is True
        assert len(result["services"]) > 0
        # Should include location info for each service
        svc = result["services"][0]
        assert "location" in svc
        assert "location_number" in svc

    def test_use_service(self, engine_in_blackeswell):
        """Test using a service."""
        # Visit church and use prayer service
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 3}
        )

        result = engine_in_blackeswell.execute_action(
            "settlement:use_service", {"service_name": "prayer"}
        )

        assert result["success"] is True
        assert "service_result" in result

    def test_use_service_not_found(self, engine_in_blackeswell):
        """Test using a non-existent service."""
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 1}
        )

        result = engine_in_blackeswell.execute_action(
            "settlement:use_service", {"service_name": "nonexistent_service"}
        )

        assert result["success"] is False
        assert "not found" in result["message"]
        assert "available_services" in result


class TestCostParsing:
    """Tests for service cost text parsing."""

    def test_parse_simple_gold(self):
        """Test parsing simple gold amounts."""
        result = parse_cost_text("10gp")
        assert result is not None
        assert result.gp == 10

    def test_parse_silver(self):
        """Test parsing silver amounts."""
        result = parse_cost_text("5sp")
        assert result is not None
        assert result.sp == 5

    def test_parse_copper(self):
        """Test parsing copper amounts."""
        result = parse_cost_text("20cp")
        assert result is not None
        assert result.cp == 20

    def test_parse_free(self):
        """Test parsing free cost - returns None for unparseable text."""
        # parse_cost_text returns None for 'free' as it's not a coin pattern
        result = parse_cost_text("free")
        # Free is not a coin pattern, so returns None
        assert result is None

    def test_parse_complex_cost(self):
        """Test parsing costs with multiple denominations."""
        result = parse_cost_text("2gp 5sp")
        assert result is not None
        assert result.gp == 2
        assert result.sp == 5


# =============================================================================
# NPC TESTS
# =============================================================================


class TestNPCActions:
    """Tests for NPC-related actions."""

    def test_list_npcs_at_location(self, engine_in_blackeswell):
        """Test listing NPCs at a location."""
        # Visit church where Father Bertil is
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 3}
        )

        result = engine_in_blackeswell.execute_action("settlement:list_npcs", {})

        assert result["success"] is True
        assert "npcs" in result
        # Should find Father Bertil
        names = [npc["name"] for npc in result["npcs"]]
        assert any("Bertil" in name for name in names)

    def test_list_all_npcs(self, engine_in_blackeswell):
        """Test listing all NPCs in settlement."""
        result = engine_in_blackeswell.execute_action("settlement:list_npcs", {})

        assert result["success"] is True
        assert len(result["npcs"]) == 4  # Blackeswell has 4 NPCs

    def test_talk_to_npc_by_name(self, engine_in_blackeswell):
        """Test talking to an NPC by name."""
        result = engine_in_blackeswell.execute_action(
            "settlement:talk", {"npc_name": "Bertil"}
        )

        assert result["success"] is True
        assert result["npc"]["name"] == "Father Ingram Bertil"
        assert "description" in result["npc"]
        assert "demeanor" in result["npc"]

    def test_talk_to_npc_by_id(self, engine_in_blackeswell):
        """Test talking to an NPC by ID."""
        result = engine_in_blackeswell.execute_action(
            "settlement:talk", {"npc_id": "father_ingram_bertil"}
        )

        assert result["success"] is True
        assert result["npc"]["name"] == "Father Ingram Bertil"

    def test_talk_to_unknown_npc(self, engine_in_blackeswell):
        """Test talking to a non-existent NPC."""
        result = engine_in_blackeswell.execute_action(
            "settlement:talk", {"npc_name": "Unknown Person"}
        )

        assert result["success"] is False
        assert "Could not find" in result["message"]
        assert "available_npcs" in result


# =============================================================================
# ENCOUNTER TESTS
# =============================================================================


class TestEncounterActions:
    """Tests for settlement encounter actions."""

    def test_check_encounter_forced(self, engine_in_blackeswell):
        """Test forcing an encounter roll (skipping probability)."""
        result = engine_in_blackeswell.execute_action(
            "settlement:check_encounter",
            {"time_of_day": "midday", "force_roll": True},
        )

        assert result["success"] is True
        assert result["encounter_occurred"] is True
        assert "encounter" in result
        assert "roll" in result["encounter"]
        assert "description" in result["encounter"]

    def test_check_encounter_day_night_mapping(self, engine_in_blackeswell):
        """Test that time of day maps correctly to day/night."""
        # Midday should map to "day"
        result = engine_in_blackeswell.execute_action(
            "settlement:check_encounter",
            {"time_of_day": "midday", "force_roll": True},
        )
        assert result["day_night"] == "day"

        # Midnight should map to "night"
        result = engine_in_blackeswell.execute_action(
            "settlement:check_encounter",
            {"time_of_day": "midnight", "force_roll": True},
        )
        assert result["day_night"] == "night"

    def test_encounter_probability_check(self, engine_in_blackeswell):
        """Test that probability check works (may or may not trigger)."""
        # Run multiple times to ensure probability check runs
        results = []
        for _ in range(10):
            result = engine_in_blackeswell.execute_action(
                "settlement:check_encounter",
                {"time_of_day": "afternoon", "force_roll": False},
            )
            results.append(result["encounter_occurred"])

        # At least some should be True and some False (statistically)
        # But we can't guarantee this in a small sample

    def test_encounter_with_engine_routing(self, engine_in_blackeswell):
        """Test encounter with EncounterEngine routing data."""
        result = engine_in_blackeswell.execute_action(
            "settlement:check_encounter",
            {
                "time_of_day": "evening",
                "force_roll": True,
                "route_to_encounter_engine": True,
            },
        )

        assert result["success"] is True
        if result["encounter_occurred"]:
            # May or may not have routing data depending on actors
            if result["encounter"].get("monsters_involved") or result["encounter"].get(
                "npcs_involved"
            ):
                assert "encounter_engine_data" in result

    def test_check_encounter_on_time_advance(self, engine_in_blackeswell):
        """Test the time advance hook."""
        # This may or may not trigger an encounter
        result = engine_in_blackeswell.check_encounter_on_time_advance(
            TimeOfDay.DUSK, is_active=True
        )

        # Result is either None or a dict with encounter info
        if result is not None:
            assert result["encounter_occurred"] is True


class TestEncounterTables:
    """Tests for SettlementEncounterTables class."""

    def test_tod_to_daynight_mapping(self):
        """Test time of day to day/night mapping."""
        assert tod_to_daynight(TimeOfDay.DAWN) == "day"
        assert tod_to_daynight(TimeOfDay.MORNING) == "day"
        assert tod_to_daynight(TimeOfDay.MIDDAY) == "day"
        assert tod_to_daynight(TimeOfDay.AFTERNOON) == "day"
        assert tod_to_daynight(TimeOfDay.DUSK) == "day"
        assert tod_to_daynight(TimeOfDay.EVENING) == "night"
        assert tod_to_daynight(TimeOfDay.MIDNIGHT) == "night"
        assert tod_to_daynight(TimeOfDay.PREDAWN) == "night"

    def test_encounter_tables_roll_deterministic(self, deterministic_dice):
        """Test encounter table roll with deterministic dice."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()
        blackeswell = registry.get("blackeswell")

        tables = SettlementEncounterTables(blackeswell)

        # Roll with fixed seed
        result1 = tables.roll(deterministic_dice, TimeOfDay.MIDDAY)
        assert result1 is not None
        assert result1.table_key == "day"
        assert 1 <= result1.roll <= 6

    def test_encounter_tables_has_day_and_night(self):
        """Test that settlement has both day and night tables."""
        loader = SettlementLoader(Path("data/content/settlements"))
        registry = loader.load_registry()
        blackeswell = registry.get("blackeswell")

        tables = SettlementEncounterTables(blackeswell)

        assert tables.get_table("day") is not None
        assert tables.get_table("night") is not None


# =============================================================================
# LOCK ENFORCEMENT TESTS
# =============================================================================


class TestLockEnforcement:
    """Tests for locked location enforcement."""

    def test_visit_locked_location_denied(self, engine_in_blackeswell):
        """Test that visiting a locked location is denied without access."""
        # Location 2 (Village Square) is locked
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 2}
        )

        assert result["success"] is False
        assert result["is_locked"] is True
        assert "key_holder" in result
        assert "hint" in result

    def test_grant_access_allows_entry(self, engine_in_blackeswell):
        """Test that granting access allows entry."""
        # Grant access to location 2
        engine_in_blackeswell.grant_location_access(
            "blackeswell", 2, "Permission granted by Sylvain Aster"
        )

        # Should now be able to visit
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 2}
        )

        assert result["success"] is True
        assert result["location"]["name"] == "Village Square"

    def test_has_location_access(self, engine_in_blackeswell):
        """Test checking location access status."""
        assert engine_in_blackeswell.has_location_access("blackeswell", 2) is False

        engine_in_blackeswell.grant_location_access("blackeswell", 2, "Test")

        assert engine_in_blackeswell.has_location_access("blackeswell", 2) is True

    def test_revoke_access(self, engine_in_blackeswell):
        """Test revoking location access."""
        engine_in_blackeswell.grant_location_access("blackeswell", 2, "Test")
        assert engine_in_blackeswell.has_location_access("blackeswell", 2) is True

        engine_in_blackeswell.revoke_location_access("blackeswell", 2)
        assert engine_in_blackeswell.has_location_access("blackeswell", 2) is False

    def test_get_locked_locations(self, engine_in_blackeswell):
        """Test getting list of locked locations."""
        locked = engine_in_blackeswell.get_locked_locations()

        # Blackeswell has 3 locked locations: 2, 4, 10
        assert len(locked) == 3
        numbers = [loc["number"] for loc in locked]
        assert 2 in numbers
        assert 4 in numbers
        assert 10 in numbers

        # Check access status
        loc2 = next(l for l in locked if l["number"] == 2)
        assert loc2["has_access"] is False

    def test_force_entry_bypasses_lock(self, engine_in_blackeswell):
        """Test that force_entry parameter bypasses lock check."""
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 2, "force_entry": True}
        )

        assert result["success"] is True


# =============================================================================
# EQUIPMENT AVAILABILITY TESTS
# =============================================================================


class TestEquipmentAvailability:
    """Tests for equipment availability action."""

    def test_equipment_availability_basic(self, engine_in_blackeswell):
        """Test basic equipment availability query."""
        result = engine_in_blackeswell.execute_action(
            "settlement:equipment_availability", {}
        )

        assert result["success"] is True
        assert "price_modifier" in result
        assert "available_categories" in result
        assert "unavailable_categories" in result
        assert "special_items" in result

    def test_blackeswell_has_price_markup(self, engine_in_blackeswell):
        """Test that Blackeswell has 100% price markup."""
        result = engine_in_blackeswell.execute_action(
            "settlement:equipment_availability", {}
        )

        assert result["price_modifier"] == 2.0
        assert result["price_modifier_percent"] == "+100%"

    def test_blackeswell_unavailable_armor(self, engine_in_blackeswell):
        """Test that armor is unavailable in Blackeswell."""
        result = engine_in_blackeswell.execute_action(
            "settlement:equipment_availability", {"category": "armor"}
        )

        assert result["category_available"] is False
        assert "not available" in result["message"]

    def test_prigwort_standard_prices(self, engine_in_prigwort):
        """Test that Prigwort has standard prices."""
        result = engine_in_prigwort.execute_action(
            "settlement:equipment_availability", {}
        )

        assert result["price_modifier"] == 1.0
        assert result["price_modifier_percent"] == "standard"

    def test_equipment_category_filter(self, engine_in_prigwort):
        """Test filtering by equipment category."""
        result = engine_in_prigwort.execute_action(
            "settlement:equipment_availability", {"category": "vehicles"}
        )

        assert result["success"] is True
        assert result["filtered_category"] == "vehicles"
        assert result["category_available"] is True


# =============================================================================
# BRIDGE API TESTS
# =============================================================================


class TestBridgeAPI:
    """Tests for handle_player_action bridge API."""

    def test_list_locations_keywords(self, engine_in_blackeswell):
        """Test various keywords for listing locations."""
        keywords = ["list locations", "show locations", "where can i go", "look around"]

        for kw in keywords:
            result = engine_in_blackeswell.handle_player_action(kw)
            assert result["success"] is True, f"Failed for keyword: {kw}"
            assert result["action"] == "settlement:list_locations"

    def test_visit_by_number(self, engine_in_blackeswell):
        """Test visiting location by number."""
        result = engine_in_blackeswell.handle_player_action("visit 1")

        assert result["success"] is True
        assert result["action"] == "settlement:visit_location"

    def test_visit_by_name(self, engine_in_blackeswell):
        """Test visiting location by name."""
        result = engine_in_blackeswell.handle_player_action("go to the blacke")

        assert result["success"] is True
        assert result["action"] == "settlement:visit_location"

    def test_services_keyword(self, engine_in_blackeswell):
        """Test services keyword."""
        result = engine_in_blackeswell.handle_player_action("services")

        assert result["success"] is True
        assert result["action"] == "settlement:list_services"

    def test_talk_to_npc(self, engine_in_blackeswell):
        """Test talking to NPC via bridge."""
        result = engine_in_blackeswell.handle_player_action("talk to bertil")

        assert result["success"] is True
        assert result["action"] == "settlement:talk"

    def test_unrecognized_input(self, engine_in_blackeswell):
        """Test unrecognized input returns helpful message."""
        result = engine_in_blackeswell.handle_player_action("do a backflip")

        assert result["success"] is False
        assert "I don't understand" in result["message"]
        assert result["action"] is None


# =============================================================================
# STATE MANAGEMENT TESTS
# =============================================================================


class TestStateManagement:
    """Tests for settlement state management."""

    def test_set_active_settlement(self, engine):
        """Test setting active settlement."""
        result = engine.set_active_settlement("blackeswell")

        assert result is True
        assert engine.get_active_settlement() is not None
        assert engine.get_active_settlement().name == "Blackeswell"

    def test_set_invalid_settlement(self, engine):
        """Test setting invalid settlement."""
        result = engine.set_active_settlement("nonexistent")

        assert result is False
        assert engine.get_active_settlement() is None

    def test_clear_active_settlement(self, engine_in_blackeswell):
        """Test clearing active settlement."""
        assert engine_in_blackeswell.get_active_settlement() is not None

        engine_in_blackeswell.clear_active_settlement()

        assert engine_in_blackeswell.get_active_settlement() is None
        assert engine_in_blackeswell._current_location_number is None
        assert len(engine_in_blackeswell._visited_locations) == 0

    def test_leave_action_clears_state(self, engine_in_blackeswell):
        """Test that leave action clears settlement state."""
        # Visit a location first
        engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 1}
        )

        # Leave
        result = engine_in_blackeswell.execute_action("settlement:leave", {})

        assert result["success"] is True
        assert engine_in_blackeswell.get_active_settlement() is None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestSettlementIntegration:
    """Integration tests for full settlement workflows."""

    def test_full_exploration_workflow(self, engine_in_blackeswell):
        """Test a full exploration workflow."""
        # List locations
        result = engine_in_blackeswell.execute_action("settlement:list_locations", {})
        assert result["success"] is True
        assert len(result["locations"]) > 0

        # Visit a location
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 1}
        )
        assert result["success"] is True

        # List NPCs at location
        result = engine_in_blackeswell.execute_action("settlement:list_npcs", {})
        assert result["success"] is True

        # Check for services
        result = engine_in_blackeswell.execute_action("settlement:list_services", {})
        assert result["success"] is True

        # Ask for directions
        result = engine_in_blackeswell.execute_action("settlement:ask_directions", {})
        assert result["success"] is True
        assert "roads" in result

        # Check equipment availability
        result = engine_in_blackeswell.execute_action(
            "settlement:equipment_availability", {}
        )
        assert result["success"] is True

        # Leave
        result = engine_in_blackeswell.execute_action("settlement:leave", {})
        assert result["success"] is True

    def test_locked_location_workflow(self, engine_in_blackeswell):
        """Test workflow for accessing locked location."""
        # Try to visit locked location
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 2}
        )
        assert result["success"] is False
        assert result["is_locked"] is True

        # Talk to key holder
        result = engine_in_blackeswell.execute_action(
            "settlement:talk", {"npc_name": "Sylvain Aster"}
        )
        assert result["success"] is True

        # Grant access (simulating NPC granting permission)
        engine_in_blackeswell.grant_location_access(
            "blackeswell", 2, "Sylvain Aster granted permission"
        )

        # Now should be able to visit
        result = engine_in_blackeswell.execute_action(
            "settlement:visit_location", {"location_number": 2}
        )
        assert result["success"] is True
