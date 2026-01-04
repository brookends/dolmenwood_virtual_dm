"""
Tests for NPC time-based presence (Task 5.2).

Verifies that:
1. NPCs with "(nighttime only)" in location only appear at night
2. NPCs with "(daytime only)" in location only appear during day
3. NPCs without time restrictions appear at all times
4. The Dredger in hex 0104 only appears at night
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import DiceRoller
from src.game_state.global_controller import GlobalController
from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline


@pytest.fixture
def hex_pipeline():
    """Create a content pipeline with hex 0104 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(Path("data/content/hexes/0104_the_phantom_lighthouse.json"))
    assert result.success, f"Failed to load hex: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0104(hex_pipeline):
    """Get the loaded HexLocation for hex 0104."""
    hex_data = hex_pipeline.get_hex("0104")
    assert hex_data is not None, "Hex 0104 not found in pipeline"
    return hex_data


@pytest.fixture
def controller():
    """Create a GlobalController."""
    return GlobalController()


@pytest.fixture
def hex_engine(hex_0104, controller):
    """Create a HexCrawlEngine with hex 0104 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0104"] = hex_0104
    engine._current_hex = "0104"
    engine._current_poi = "Lighthouse in the Bog"
    return engine


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


class TestDredgerTimePresence:
    """Tests for the Dredger's nighttime-only presence."""

    def test_dredger_not_present_during_day(self, hex_engine, controller, seeded_dice):
        """Dredger should NOT appear during daytime."""
        # Set time to noon (daytime)
        controller.world_state.current_time.hour = 12

        npcs = hex_engine.get_npcs_at_poi("0104")

        # Dredger should not be in the list
        npc_names = [n.get("name") for n in npcs]
        assert "The Dredger" not in npc_names

    def test_dredger_present_at_night(self, hex_engine, controller, seeded_dice):
        """Dredger should appear during nighttime."""
        # Set time to midnight (nighttime)
        controller.world_state.current_time.hour = 0

        npcs = hex_engine.get_npcs_at_poi("0104")

        # Dredger should be in the list
        npc_names = [n.get("name") for n in npcs]
        assert "The Dredger" in npc_names

    def test_dredger_present_at_evening(self, hex_engine, controller, seeded_dice):
        """Dredger should appear at evening (after dusk)."""
        # Set time to 22:00 (late evening)
        controller.world_state.current_time.hour = 22

        npcs = hex_engine.get_npcs_at_poi("0104")

        npc_names = [n.get("name") for n in npcs]
        assert "The Dredger" in npc_names

    def test_dredger_not_present_morning(self, hex_engine, controller, seeded_dice):
        """Dredger should NOT appear in the morning."""
        # Set time to 8:00 (morning)
        controller.world_state.current_time.hour = 8

        npcs = hex_engine.get_npcs_at_poi("0104")

        npc_names = [n.get("name") for n in npcs]
        assert "The Dredger" not in npc_names

    def test_dredger_has_combatant_flag_when_present(self, hex_engine, controller, seeded_dice):
        """Dredger should have is_combatant flag when present."""
        controller.world_state.current_time.hour = 22

        npcs = hex_engine.get_npcs_at_poi("0104")

        dredger = next((n for n in npcs if n.get("name") == "The Dredger"), None)
        assert dredger is not None
        assert dredger.get("is_combatant") is True


class TestIsNpcPresentAtTime:
    """Tests for the _is_npc_present_at_time helper method."""

    def test_nighttime_only_npc_at_night(self, hex_engine):
        """NPC with (nighttime only) should be present at night."""
        mock_npc = MagicMock()
        mock_npc.location = "Lighthouse lantern room (nighttime only)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=True)

        assert result is True

    def test_nighttime_only_npc_during_day(self, hex_engine):
        """NPC with (nighttime only) should NOT be present during day."""
        mock_npc = MagicMock()
        mock_npc.location = "Lighthouse lantern room (nighttime only)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=False)

        assert result is False

    def test_nighttime_npc_at_night(self, hex_engine):
        """NPC with (nighttime) should be present at night."""
        mock_npc = MagicMock()
        mock_npc.location = "Graveyard (nighttime)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=True)

        assert result is True

    def test_nighttime_npc_during_day(self, hex_engine):
        """NPC with (nighttime) should NOT be present during day."""
        mock_npc = MagicMock()
        mock_npc.location = "Graveyard (nighttime)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=False)

        assert result is False

    def test_daytime_only_npc_during_day(self, hex_engine):
        """NPC with (daytime only) should be present during day."""
        mock_npc = MagicMock()
        mock_npc.location = "Market square (daytime only)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=False)

        assert result is True

    def test_daytime_only_npc_at_night(self, hex_engine):
        """NPC with (daytime only) should NOT be present at night."""
        mock_npc = MagicMock()
        mock_npc.location = "Market square (daytime only)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=True)

        assert result is False

    def test_daytime_npc_during_day(self, hex_engine):
        """NPC with (daytime) should be present during day."""
        mock_npc = MagicMock()
        mock_npc.location = "Field (daytime)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=False)

        assert result is True

    def test_daytime_npc_at_night(self, hex_engine):
        """NPC with (daytime) should NOT be present at night."""
        mock_npc = MagicMock()
        mock_npc.location = "Field (daytime)"

        result = hex_engine._is_npc_present_at_time(mock_npc, is_night=True)

        assert result is False

    def test_npc_without_time_restriction_always_present(self, hex_engine):
        """NPC without time keywords should always be present."""
        mock_npc = MagicMock()
        mock_npc.location = "The inn common room"

        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=True) is True
        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=False) is True

    def test_npc_with_empty_location_always_present(self, hex_engine):
        """NPC with empty location should always be present."""
        mock_npc = MagicMock()
        mock_npc.location = ""

        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=True) is True
        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=False) is True

    def test_npc_with_none_location_always_present(self, hex_engine):
        """NPC with None location should always be present."""
        mock_npc = MagicMock()
        mock_npc.location = None

        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=True) is True
        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=False) is True

    def test_case_insensitive_matching(self, hex_engine):
        """Time keywords should match case-insensitively."""
        mock_npc = MagicMock()
        mock_npc.location = "Tower (NIGHTTIME ONLY)"

        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=True) is True
        assert hex_engine._is_npc_present_at_time(mock_npc, is_night=False) is False


class TestEngageNpcTimeGating:
    """Tests for time-gating affecting combat engagement."""

    def test_cannot_engage_dredger_during_day(self, hex_engine, controller, seeded_dice):
        """Cannot engage Dredger during daytime (not present)."""
        controller.world_state.current_time.hour = 12

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is False
        assert "not present during daytime" in result["error"]

    def test_can_engage_dredger_at_night(self, hex_engine, controller, seeded_dice):
        """Can engage Dredger at nighttime."""
        controller.world_state.current_time.hour = 22

        result = hex_engine.engage_poi_npc("0104", "the_dredger")

        assert result["success"] is True
        assert result["combatant_count"] == 1
        assert result["combatants"][0]["name"] == "The Dredger"


class TestMixedNpcPresence:
    """Tests for POIs with multiple NPCs having different time restrictions."""

    def test_mixed_presence_at_night(self, hex_engine, controller):
        """At night, only nighttime NPCs should appear (plus unrestricted ones)."""
        # Create a mock hex with mixed NPCs
        mock_hex = MagicMock()
        mock_poi = MagicMock()
        mock_poi.name = "Test POI"
        mock_poi.npcs = ["night_guard", "day_merchant", "innkeeper"]
        mock_poi.inhabitants = None
        mock_hex.points_of_interest = [mock_poi]

        # Create mock NPCs with different time restrictions
        night_guard = MagicMock()
        night_guard.npc_id = "night_guard"
        night_guard.name = "Night Guard"
        night_guard.description = "A vigilant guard"
        night_guard.kindred = "human"
        night_guard.title = None
        night_guard.demeanor = None
        night_guard.location = "Gatehouse (nighttime only)"
        night_guard.is_combatant = True

        day_merchant = MagicMock()
        day_merchant.npc_id = "day_merchant"
        day_merchant.name = "Day Merchant"
        day_merchant.description = "A busy trader"
        day_merchant.kindred = "human"
        day_merchant.title = None
        day_merchant.demeanor = None
        day_merchant.location = "Market stall (daytime only)"
        day_merchant.is_combatant = False

        innkeeper = MagicMock()
        innkeeper.npc_id = "innkeeper"
        innkeeper.name = "Innkeeper"
        innkeeper.description = "The friendly innkeeper"
        innkeeper.kindred = "human"
        innkeeper.title = None
        innkeeper.demeanor = None
        innkeeper.location = "Behind the bar"
        innkeeper.is_combatant = False

        mock_hex.npcs = [night_guard, day_merchant, innkeeper]

        hex_engine._hex_data["test_hex"] = mock_hex
        hex_engine._current_poi = "Test POI"
        controller.world_state.current_time.hour = 22  # Night

        npcs = hex_engine.get_npcs_at_poi("test_hex")
        npc_names = [n.get("name") for n in npcs]

        # Night guard and innkeeper should be present
        assert "Night Guard" in npc_names
        assert "Innkeeper" in npc_names
        # Day merchant should not be present
        assert "Day Merchant" not in npc_names

    def test_mixed_presence_during_day(self, hex_engine, controller):
        """During day, only daytime NPCs should appear (plus unrestricted ones)."""
        # Create a mock hex with mixed NPCs
        mock_hex = MagicMock()
        mock_poi = MagicMock()
        mock_poi.name = "Test POI"
        mock_poi.npcs = ["night_guard", "day_merchant", "innkeeper"]
        mock_poi.inhabitants = None
        mock_hex.points_of_interest = [mock_poi]

        # Create mock NPCs with different time restrictions
        night_guard = MagicMock()
        night_guard.npc_id = "night_guard"
        night_guard.name = "Night Guard"
        night_guard.description = "A vigilant guard"
        night_guard.kindred = "human"
        night_guard.title = None
        night_guard.demeanor = None
        night_guard.location = "Gatehouse (nighttime only)"
        night_guard.is_combatant = True

        day_merchant = MagicMock()
        day_merchant.npc_id = "day_merchant"
        day_merchant.name = "Day Merchant"
        day_merchant.description = "A busy trader"
        day_merchant.kindred = "human"
        day_merchant.title = None
        day_merchant.demeanor = None
        day_merchant.location = "Market stall (daytime only)"
        day_merchant.is_combatant = False

        innkeeper = MagicMock()
        innkeeper.npc_id = "innkeeper"
        innkeeper.name = "Innkeeper"
        innkeeper.description = "The friendly innkeeper"
        innkeeper.kindred = "human"
        innkeeper.title = None
        innkeeper.demeanor = None
        innkeeper.location = "Behind the bar"
        innkeeper.is_combatant = False

        mock_hex.npcs = [night_guard, day_merchant, innkeeper]

        hex_engine._hex_data["test_hex"] = mock_hex
        hex_engine._current_poi = "Test POI"
        controller.world_state.current_time.hour = 12  # Day

        npcs = hex_engine.get_npcs_at_poi("test_hex")
        npc_names = [n.get("name") for n in npcs]

        # Day merchant and innkeeper should be present
        assert "Day Merchant" in npc_names
        assert "Innkeeper" in npc_names
        # Night guard should not be present
        assert "Night Guard" not in npc_names
