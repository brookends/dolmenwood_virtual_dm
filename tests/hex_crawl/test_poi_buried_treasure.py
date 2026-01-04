"""
Tests for POI buried treasure discovery and taking items.

This test suite validates:
- Searching locations can find concealed items with contained items
- Found items become takeable via take_item
- Items are properly tracked in POI state
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    result = loader.load_file(
        Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
    )
    assert result.success, f"Failed to load hex 0109: {result.errors}"
    return pipeline


@pytest.fixture
def controller():
    """Create a GlobalController."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=3, day=15)
    return controller


@pytest.fixture
def engine(controller, pipeline):
    """Create a HexCrawlEngine with hex 0109 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0109"] = pipeline.get_hex("0109")
    engine._current_hex = "0109"
    return engine


@pytest.fixture
def engine_at_camp(engine):
    """Engine positioned at Murkin's Army camp."""
    engine._current_poi = "Murkin's Army"
    return engine


# =============================================================================
# CONCEALED ITEM DATA TESTS
# =============================================================================


class TestBuriedCofferData:
    """Test that the buried coffer is properly defined in concealed items."""

    def test_buried_coffer_exists(self, pipeline):
        """Camp should have buried coffer in concealed items."""
        hex_data = pipeline.get_hex("0109")
        camp = next(
            p for p in hex_data.points_of_interest
            if p.name == "Murkin's Army"
        )

        coffer = None
        for item in camp.concealed_items:
            if item.get("name") == "Buried Coffer":
                coffer = item
                break

        assert coffer is not None, "Buried Coffer should exist in concealed items"
        assert coffer.get("hidden_in") == "beneath command tent"
        assert coffer.get("search_dc") == 5

    def test_buried_coffer_has_items(self, pipeline):
        """Buried coffer should contain takeable items."""
        hex_data = pipeline.get_hex("0109")
        camp = next(
            p for p in hex_data.points_of_interest
            if p.name == "Murkin's Army"
        )

        coffer = next(
            (item for item in camp.concealed_items if item.get("name") == "Buried Coffer"),
            None
        )
        assert coffer is not None

        contained_items = coffer.get("items", [])
        assert len(contained_items) >= 1

        onyxes = next(
            (i for i in contained_items if "Onyxes" in i.get("name", "")),
            None
        )
        assert onyxes is not None
        assert onyxes.get("value") == 1000


# =============================================================================
# SEARCH AND ITEM DISCOVERY TESTS
# =============================================================================


class TestSearchRevealsItems:
    """Test that searching can reveal takeable items."""

    def test_search_command_tent_finds_coffer(self, engine_at_camp):
        """Searching command tent with high roll should find buried coffer."""
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6  # High roll ensures success (DC is 5)
            mock_roll.return_value = mock_result

            result = engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

            assert result.get("success") is True
            assert result.get("found_count", 0) > 0

            # Check that coffer was found
            found_names = [item.get("name") for item in result.get("items_found", [])]
            assert "Buried Coffer" in found_names

    def test_finding_coffer_makes_items_takeable(self, engine_at_camp):
        """Finding buried coffer should make contained items takeable."""
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6  # High roll ensures success
            mock_roll.return_value = mock_result

            result = engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

            # Check that items are now takeable
            assert "items_now_takeable" in result
            assert "Sergeant Snidebleat's Onyxes" in result["items_now_takeable"]

    def test_message_mentions_takeable_items(self, engine_at_camp):
        """Message should mention items that can be taken."""
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

            if "items_now_takeable" in result:
                assert "can now take" in result.get("message", "").lower()

    def test_low_roll_does_not_find_coffer(self, engine_at_camp):
        """Low search roll should not find buried coffer (DC 5)."""
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 3  # Below DC of 5
            mock_roll.return_value = mock_result

            result = engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

            found_names = [item.get("name") for item in result.get("items_found", [])]
            assert "Buried Coffer" not in found_names


# =============================================================================
# TAKE ITEM TESTS
# =============================================================================


class TestTakeItemAfterDiscovery:
    """Test that take_item works for items found in concealed items."""

    def test_cannot_take_onyxes_before_discovery(self, engine_at_camp):
        """Should not be able to take onyxes before finding the coffer."""
        result = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )

        # Item not yet available
        assert result.get("success") is False

    def test_can_take_onyxes_after_discovery(self, engine_at_camp):
        """Should be able to take onyxes after finding the buried coffer."""
        # First, find the coffer
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

        # Now try to take the onyxes
        result = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )

        assert result.get("success") is True
        assert "Onyxes" in result.get("item_name", result.get("item", {}).get("name", ""))

    def test_taken_items_tracked_in_visit(self, engine_at_camp):
        """Taken items should be tracked in POI visit state."""
        # Find the coffer
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

        # Take the onyxes
        engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )

        # Check visit tracking
        visit_key = "0109:Murkin's Army"
        visit = engine_at_camp._poi_visits.get(visit_key)
        if visit:
            assert "Sergeant Snidebleat's Onyxes" in visit.items_taken

    def test_cannot_take_same_item_twice(self, engine_at_camp):
        """Should not be able to take the same item twice."""
        # Find the coffer
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

        # Take the onyxes first time
        result1 = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )
        assert result1.get("success") is True

        # Try to take again
        result2 = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )
        assert result2.get("success") is False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestBuriedTreasureIntegration:
    """Integration tests for the full buried treasure discovery flow."""

    def test_full_treasure_discovery_flow(self, engine_at_camp):
        """Test complete flow: search -> find coffer -> take onyxes."""
        # Step 1: Items not yet available
        pre_result = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )
        assert pre_result.get("success") is False

        # Step 2: Search command tent with high roll
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            search_result = engine_at_camp.search_poi_location(
                "0109",
                "command tent",
            )

        # Step 3: Verify coffer found and items available
        assert search_result.get("success") is True
        assert "items_now_takeable" in search_result
        assert "Sergeant Snidebleat's Onyxes" in search_result["items_now_takeable"]

        # Step 4: Take the onyxes
        take_result = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )
        assert take_result.get("success") is True

        # Step 5: Cannot take again
        retry_result = engine_at_camp.take_item(
            "0109",
            "Sergeant Snidebleat's Onyxes",
            "test_character",
        )
        assert retry_result.get("success") is False


# =============================================================================
# ITEM PERSISTENCE TESTS
# =============================================================================


class TestItemPersistence:
    """Test that found items persist correctly."""

    def test_items_added_to_poi_items_list(self, engine_at_camp):
        """Found items should be added to POI's items list."""
        hex_data = engine_at_camp._hex_data["0109"]
        camp = next(
            p for p in hex_data.points_of_interest
            if p.name == "Murkin's Army"
        )

        # Check items before search
        initial_item_count = len(camp.items)

        # Search and find
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

        # Items should be added
        assert len(camp.items) > initial_item_count

        # Onyxes should be in the list
        item_names = [i.get("name", "") for i in camp.items]
        assert "Sergeant Snidebleat's Onyxes" in item_names

    def test_found_items_tracked_in_visit(self, engine_at_camp):
        """Found items should be tracked in POI visit state."""
        # Search and find
        with patch.object(engine_at_camp.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            engine_at_camp.search_poi_location(
                "0109",
                search_location="command tent",
            )

        # Check visit tracking
        visit_key = "0109:Murkin's Army"
        visit = engine_at_camp._poi_visits.get(visit_key)
        if visit:
            assert "Sergeant Snidebleat's Onyxes" in visit.items_found
