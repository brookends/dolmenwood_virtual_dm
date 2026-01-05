"""
Tests for hex 0103 treasure hoard claiming.

Verifies that players can claim the treasure hoard at Crocus's Cave
via the wilderness:claim_treasure_hoard action.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, Optional

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine, POIVisit
from src.game_state.global_controller import GlobalController
from src.data_models import (
    CharacterState,
    GameDate,
    GameTime,
    PointOfInterest,
    PartyState,
    PartyResources,
    Location,
    LocationType,
)


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0103 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0103_the_golden_goose.json")
    )
    assert result.success, f"Failed to load hex 0103: {result.errors}"
    return pipeline


@pytest.fixture
def hex_0103(pipeline):
    """Get the hex 0103 data."""
    return pipeline.get_hex("0103")


@pytest.fixture
def controller():
    """Create a GlobalController with a test character."""
    controller = GlobalController()

    char = CharacterState(
        character_id="test_fighter",
        name="Sir Galahad",
        character_class="Fighter",
        level=5,
        ability_scores={"STR": 16, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
        hp_current=30,
        hp_max=30,
        armor_class=16,
        base_speed=40,
    )
    controller.add_character(char)

    controller.world_state.current_date = GameDate(year=1, month=3, day=15)
    controller.world_state.current_time = GameTime(hour=12, minute=0)

    return controller


class TestClaimTreasureHoard:
    """Tests for claiming treasure hoards at POIs."""

    def test_claim_treasure_at_crocuss_cave(self, hex_0103, controller):
        """Verify treasure can be claimed at Crocus's Cave."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Claim the treasure
        result = engine.claim_treasure_hoard("0103")

        assert result["success"] is True
        assert "treasure" in result
        assert result["treasure"]["coins"]["cp"] == 673
        assert result["treasure"]["coins"]["sp"] == 432
        assert result["treasure"]["coins"]["gp"] == 925

        # Check items
        items = result["treasure"]["items"]
        assert len(items) == 2

        # Golden eggs
        golden_eggs = next((i for i in items if i["name"] == "Golden Egg"), None)
        assert golden_eggs is not None
        assert golden_eggs["quantity"] == 4
        assert golden_eggs["value_gp"] == 40

        # Talisman
        talisman = next((i for i in items if "Talisman" in i["name"]), None)
        assert talisman is not None
        assert talisman["magical"] is True

    def test_treasure_claimed_once_only(self, hex_0103, controller):
        """Verify treasure cannot be claimed twice."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # First claim succeeds
        result1 = engine.claim_treasure_hoard("0103")
        assert result1["success"] is True

        # Second claim fails
        result2 = engine.claim_treasure_hoard("0103")
        assert result2["success"] is False
        assert "already claimed" in result2["error"].lower()

    def test_claim_adds_coins_to_party_gold(self, hex_0103, controller):
        """Verify coins are added to party gold."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state with 0 gold
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
            gold_gp=0,
            party_inventory=[],
        )

        result = engine.claim_treasure_hoard("0103")
        assert result["success"] is True

        # Coins: 673 cp + 432 sp + 925 gp
        # = 6.73 gp + 43.2 gp + 925 gp = 974.93 gp
        # Rounded down to 974 gp
        expected_gp = 925 + int(432 / 10) + int(673 / 100)  # = 925 + 43 + 6 = 974
        assert controller.party_state.gold_gp == expected_gp

    def test_claim_adds_items_to_party_inventory(self, hex_0103, controller):
        """Verify items are added to party inventory."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
            gold_gp=0,
            party_inventory=[],
        )

        result = engine.claim_treasure_hoard("0103")
        assert result["success"] is True

        # Check party inventory
        inventory = controller.party_state.party_inventory
        assert len(inventory) == 2

        # Find golden eggs in inventory
        eggs = next((i for i in inventory if i["name"] == "Golden Egg"), None)
        assert eggs is not None
        assert eggs["quantity"] == 4
        assert eggs["source_hex"] == "0103"
        assert eggs["source_poi"] == "Crocus's Cave"

    def test_no_treasure_hoard_at_poi(self, hex_0103, controller):
        """Verify error when POI has no treasure hoard."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Sidney's Company"  # No treasure hoard

        result = engine.claim_treasure_hoard("0103")
        assert result["success"] is False
        assert "no treasure" in result["error"].lower()

    def test_not_at_poi_error(self, hex_0103, controller):
        """Verify error when not at a POI."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = None  # Not at any POI

        result = engine.claim_treasure_hoard("0103")
        assert result["success"] is False
        assert "not at" in result["error"].lower()


class TestHasUnclaimedTreasureHoard:
    """Tests for checking if treasure hoard is available."""

    def test_has_unclaimed_treasure_at_crocuss_cave(self, hex_0103, controller):
        """Verify unclaimed treasure is detected."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        assert engine.has_unclaimed_treasure_hoard("0103") is True

    def test_no_unclaimed_treasure_after_claim(self, hex_0103, controller):
        """Verify treasure is no longer unclaimed after claiming."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
        )

        # Claim the treasure
        engine.claim_treasure_hoard("0103")

        # Should no longer have unclaimed treasure
        assert engine.has_unclaimed_treasure_hoard("0103") is False

    def test_no_unclaimed_treasure_at_poi_without_hoard(self, hex_0103, controller):
        """Verify no unclaimed treasure at POI without a hoard."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Sidney's Company"  # No treasure hoard

        assert engine.has_unclaimed_treasure_hoard("0103") is False

    def test_no_unclaimed_treasure_when_not_at_poi(self, hex_0103, controller):
        """Verify no unclaimed treasure when not at any POI."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = None

        assert engine.has_unclaimed_treasure_hoard("0103") is False


class TestPOIVisitFlags:
    """Tests for POIVisit flags functionality."""

    def test_poi_visit_flags_initialized_empty(self):
        """Verify POIVisit flags start empty."""
        visit = POIVisit(poi_name="Test POI")
        assert visit.flags == {}

    def test_poi_visit_flags_can_be_set(self):
        """Verify flags can be set on POIVisit."""
        visit = POIVisit(poi_name="Test POI")
        visit.flags["treasure_claimed"] = True
        assert visit.flags["treasure_claimed"] is True

    def test_poi_visit_flags_get_default(self):
        """Verify get returns None for missing flags."""
        visit = POIVisit(poi_name="Test POI")
        assert visit.flags.get("nonexistent") is None
        assert visit.flags.get("nonexistent", False) is False


class TestTreasureValueCalculation:
    """Tests for treasure value calculation."""

    def test_coin_conversion_to_gp(self, hex_0103, controller):
        """Verify coin conversion to gp equivalent is correct."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
        )

        result = engine.claim_treasure_hoard("0103")

        # Expected: 673 cp = 6.73 gp, 432 sp = 43.2 gp, 925 gp
        # Total coins in gp = 6.73 + 43.2 + 925 = 974.93, int() = 974
        coins = result["treasure"]["coins"]
        assert coins["total_gp_equivalent"] == 974

    def test_total_value_includes_items(self, hex_0103, controller):
        """Verify total value includes item values."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
        )

        result = engine.claim_treasure_hoard("0103")

        # Coins: 974 gp equivalent
        # Golden Eggs: 4 x 40 gp = 160 gp
        # Talisman: no value_gp set
        # Total: 974 + 160 = 1134 gp
        assert result["total_value_gp"] == 1134

    def test_coin_description_format(self, hex_0103, controller):
        """Verify coin description is formatted correctly."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
        )

        result = engine.claim_treasure_hoard("0103")

        coin_desc = result["coin_description"]
        assert "673 cp" in coin_desc
        assert "432 sp" in coin_desc
        assert "925 gp" in coin_desc


class TestWorthlessItems:
    """Tests for worthless items description."""

    def test_worthless_items_included(self, hex_0103, controller):
        """Verify worthless items description is included."""
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = hex_0103
        engine._current_hex = "0103"
        engine._current_poi = "Crocus's Cave"

        # Initialize party state
        controller.party_state = PartyState(
            location=Location(LocationType.HEX, "0103"),
        )

        result = engine.claim_treasure_hoard("0103")

        worthless = result["treasure"]["worthless"]
        assert "broken glass" in worthless.lower()
        assert "polished metal" in worthless.lower()
