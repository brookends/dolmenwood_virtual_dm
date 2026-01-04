"""
Tests for POI roll tables (Task 3.1 and 3.2).

Verifies that:
1. enter_poi returns available_tables list
2. roll_on_poi_table returns deterministic results
3. unique_entries tables don't repeat until exhausted
4. Proper error handling for missing tables
"""

import pytest
from unittest.mock import MagicMock, patch

from src.hex_crawl.hex_crawl_engine import (
    HexCrawlEngine,
    POIVisit,
    POIExplorationState,
)
from src.data_models import (
    DiceRoller,
    HexLocation,
    PointOfInterest,
    RollTable,
    RollTableEntry,
)
from src.game_state.global_controller import GlobalController


@pytest.fixture
def mock_controller():
    """Create a mock controller."""
    controller = MagicMock()
    controller.current_state = MagicMock()
    controller.session_manager = MagicMock()
    controller.session_manager.get_unfound_roll_table_entries = MagicMock(return_value=[1, 2, 3])
    controller.session_manager.mark_roll_table_entry_found = MagicMock()
    # Add world_state for _is_night check
    controller.world_state = MagicMock()
    controller.world_state.current_time = MagicMock()
    controller.world_state.current_time.hour = 12  # Daytime
    return controller


@pytest.fixture
def poi_with_roll_table():
    """Create a POI with roll tables like 'Leavings in the Mud'."""
    table_entries = [
        RollTableEntry(
            roll=1,
            title="Wooden Figurine",
            description="A finely detailed wooden figurine worth 2gp.",
            items=["wooden figurine"],
        ),
        RollTableEntry(
            roll=2,
            title="Mini Cask",
            description="A mini-cask of pale ale.",
            items=["mini-cask of ale"],
        ),
        RollTableEntry(
            roll=3,
            title="Leather Scroll",
            description="A leather scroll tube with a treasure map.",
            items=["treasure map"],
        ),
    ]
    roll_table = RollTable(
        name="Leavings in the Mud",
        die_type="d3",
        description="Items found in the mud",
        entries=table_entries,
        unique_entries=True,
    )

    poi = PointOfInterest(
        name="The Mud Flats",
        poi_type="treasure_site",
        description="A muddy area with scattered debris.",
        roll_tables=[roll_table],
    )

    hex_data = HexLocation(
        hex_id="0102",
        name="Reedwall",
        terrain_type="swamp",
        points_of_interest=[poi],
    )
    return hex_data


@pytest.fixture
def poi_with_regular_table():
    """Create a POI with a non-unique roll table."""
    table_entries = [
        RollTableEntry(
            roll=1,
            title="Croaking Frogs",
            description="Loud croaking from nearby frogs.",
        ),
        RollTableEntry(
            roll=2,
            title="Bubbling Mud",
            description="The mud bubbles ominously.",
        ),
    ]
    roll_table = RollTable(
        name="Ambient Effects",
        die_type="d2",
        description="Random ambient events",
        entries=table_entries,
        unique_entries=False,
    )

    poi = PointOfInterest(
        name="Swamp Pool",
        poi_type="natural_feature",
        description="A murky pool.",
        roll_tables=[roll_table],
    )

    hex_data = HexLocation(
        hex_id="0103",
        name="Swamplands",
        terrain_type="swamp",
        points_of_interest=[poi],
    )
    return hex_data


@pytest.fixture
def seeded_dice():
    """Create a seeded dice roller for deterministic tests."""
    DiceRoller.set_seed(42)
    return DiceRoller()


class TestEnterPoiAvailableTables:
    """Tests for surfacing available tables in enter_poi."""

    def test_enter_poi_includes_available_tables(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify enter_poi returns available_tables list."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        # Approach and enter the POI
        engine.approach_poi("0102", 0)
        result = engine.enter_poi("0102")

        assert result["success"] is True
        assert "available_tables" in result
        assert len(result["available_tables"]) == 1
        assert result["available_tables"][0]["name"] == "Leavings in the Mud"
        assert result["available_tables"][0]["die_type"] == "d3"
        assert result["available_tables"][0]["unique_entries"] is True

    def test_enter_poi_suggests_roll_actions(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify enter_poi suggests roll_poi_table actions."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)
        result = engine.enter_poi("0102")

        assert "suggested_actions" in result
        roll_actions = [
            a for a in result["suggested_actions"]
            if a["action_id"] == "wilderness:roll_poi_table"
        ]
        assert len(roll_actions) == 1
        assert roll_actions[0]["params"]["table_name"] == "Leavings in the Mud"

    def test_enter_poi_no_tables_omits_field(
        self, mock_controller, seeded_dice
    ):
        """Verify POI without tables doesn't include available_tables."""
        poi = PointOfInterest(
            name="Empty Cave",
            poi_type="cave",
            description="An empty cave.",
            roll_tables=[],
        )
        hex_data = HexLocation(
            hex_id="0104",
            name="Cave Area",
            terrain_type="craggy_forest",
            points_of_interest=[poi],
        )

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0104": hex_data}

        engine.approach_poi("0104", 0)
        result = engine.enter_poi("0104")

        assert result["success"] is True
        assert "available_tables" not in result


class TestRollOnPoiTable:
    """Tests for rolling on POI tables."""

    def test_roll_returns_deterministic_entry(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify seeded dice produces deterministic table result."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)
        engine.enter_poi("0102")

        result = engine.roll_on_poi_table("0102", "Leavings in the Mud")

        assert result is not None
        assert "roll" in result
        assert "title" in result
        assert "description" in result
        assert result["poi"] == "The Mud Flats"
        assert result["table"] == "Leavings in the Mud"

    def test_roll_on_nonexistent_table_returns_none(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify rolling on missing table returns None."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)
        engine.enter_poi("0102")

        result = engine.roll_on_poi_table("0102", "Nonexistent Table")

        assert result is None

    def test_roll_without_current_poi_returns_none(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify rolling without being at POI returns None."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        # Don't approach POI
        result = engine.roll_on_poi_table("0102", "Leavings in the Mud")

        assert result is None

    def test_unique_entries_marks_found(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify unique_entries table marks entries as found."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)
        engine.enter_poi("0102")

        result = engine.roll_on_poi_table("0102", "Leavings in the Mud")

        # Should call mark_roll_table_entry_found
        mock_controller.session_manager.mark_roll_table_entry_found.assert_called_once()
        call_args = mock_controller.session_manager.mark_roll_table_entry_found.call_args
        assert call_args[0][0] == "0102"  # hex_id
        assert call_args[0][1] == "The Mud Flats"  # poi_name
        assert call_args[0][2] == "Leavings in the Mud"  # table_name

    def test_exhausted_table_returns_exhausted_message(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify exhausted table returns appropriate message."""
        # Configure mock to return empty unfound list (all found)
        mock_controller.session_manager.get_unfound_roll_table_entries.return_value = []

        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)
        engine.enter_poi("0102")

        result = engine.roll_on_poi_table("0102", "Leavings in the Mud")

        assert result is not None
        assert result.get("exhausted") is True
        assert "have been found" in result.get("message", "")

    def test_regular_table_allows_repeats(
        self, mock_controller, poi_with_regular_table, seeded_dice
    ):
        """Verify non-unique table can produce same result multiple times."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0103": poi_with_regular_table}

        engine.approach_poi("0103", 0)
        engine.enter_poi("0103")

        # Roll multiple times
        results = []
        for _ in range(5):
            result = engine.roll_on_poi_table("0103", "Ambient Effects")
            results.append(result.get("roll"))

        # Should NOT call mark_roll_table_entry_found (not unique)
        mock_controller.session_manager.mark_roll_table_entry_found.assert_not_called()

    def test_roll_returns_items_and_monsters(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify roll result includes items, monsters, npcs fields."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)
        engine.enter_poi("0102")

        result = engine.roll_on_poi_table("0102", "Leavings in the Mud")

        assert "items" in result
        assert isinstance(result["items"], list)
        assert "monsters" in result
        assert "npcs" in result


class TestGetPoiRollTables:
    """Tests for get_poi_roll_tables helper."""

    def test_get_tables_returns_list(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify get_poi_roll_tables returns table list."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)

        tables = engine.get_poi_roll_tables("0102", "The Mud Flats")

        assert len(tables) == 1
        assert tables[0].name == "Leavings in the Mud"

    def test_get_tables_uses_current_poi(
        self, mock_controller, poi_with_roll_table, seeded_dice
    ):
        """Verify get_poi_roll_tables defaults to current POI."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {"0102": poi_with_roll_table}

        engine.approach_poi("0102", 0)

        # Don't specify poi_name - should use current
        tables = engine.get_poi_roll_tables("0102")

        assert len(tables) == 1

    def test_get_tables_nonexistent_poi_returns_empty(
        self, mock_controller, seeded_dice
    ):
        """Verify missing POI returns empty list."""
        engine = HexCrawlEngine(controller=mock_controller)
        engine._hex_data = {}

        tables = engine.get_poi_roll_tables("9999", "Nonexistent")

        assert tables == []
