"""
Tests for dynamic dungeon room generation.

Tests the procedural room generation system used by dungeons like The Spectral Manse
where rooms are generated on-the-fly using roll tables.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.dungeon.dungeon_engine import (
    DungeonEngine,
    DungeonRoom,
    DungeonState,
    DoorState,
)
from src.data_models import RollTable, RollTableEntry


@pytest.fixture
def mock_dice():
    """Create a mock dice roller with predictable results."""
    dice = MagicMock()
    # Default roll results
    dice.roll.return_value = MagicMock(total=1)
    dice.roll_d6.return_value = MagicMock(total=1)
    return dice


@pytest.fixture
def room_table():
    """Create a test room table like The Spectral Manse Rooms table."""
    entries = [
        RollTableEntry(
            roll=1,
            title="Study",
            description="Books of frost elf poetry, stag heads, ice hearth.",
            items=["frost elf poetry books"],
        ),
        RollTableEntry(
            roll=2,
            title="Lounge",
            description="Velvet couches, ice candles, wolf-skin rugs.",
            items=[],
        ),
        RollTableEntry(
            roll=3,
            title="Dining room",
            description="Exquisite foods, frozen solid.",
            items=[],
        ),
        RollTableEntry(
            roll=4,
            title="Winter garden",
            description="Hoar-clad roses drip blood if touched.",
            items=[],
            mechanical_effect="Roses drip blood if touched",
        ),
        RollTableEntry(
            roll=5,
            title="Pantry",
            description="Bottled emotions, iced fruits, frozen game.",
            items=["bottled emotions", "iced fruits"],
        ),
        RollTableEntry(
            roll=6,
            title="Bedroom",
            description="Ice-block bed, furs, tundra tapestries.",
            items=[],
        ),
    ]
    return RollTable(
        name="Rooms",
        die_type="d6",
        description="Roll when entering a new room",
        entries=entries,
    )


@pytest.fixture
def encounter_table():
    """Create a test encounter table like The Spectral Manse Encounters table."""
    entries = [
        RollTableEntry(
            roll=1,
            description="Lord Hobbled-and-Blackened, manically playing a violin.",
            npcs=["Lord Hobbled-and-Blackened"],
            items=["magical violin"],
        ),
        RollTableEntry(
            roll=2,
            description="1d4 sleek, silver hounds growl and may attack.",
            monsters=["seelie dog"],
        ),
    ]
    return RollTable(
        name="Encounters",
        die_type="d8",
        description="Roll when entering a new room",
        entries=entries,
    )


@pytest.fixture
def dynamic_dungeon_state(room_table, encounter_table):
    """Create a dungeon state configured for dynamic generation."""
    state = DungeonState(
        dungeon_id="spectral_manse",
        name="The Spectral Manse",
        current_room="entry",
        dynamic_layout={
            "connections_per_room": "1d3",
            "room_table": "Rooms",
            "encounter_table": "Encounters",
        },
        room_table=room_table,
        encounter_table=encounter_table,
    )
    # Add an entry room
    entry_room = DungeonRoom(
        room_id="entry",
        name="Entry Hall",
        description="A grand entrance with spectral light.",
        exits={"north": "room_1"},
    )
    entry_room.doors["entry_north"] = DoorState.CLOSED
    state.rooms["entry"] = entry_room
    return state


@pytest.fixture
def dungeon_engine(mock_dice, dynamic_dungeon_state):
    """Create a dungeon engine with dynamic layout support."""
    engine = DungeonEngine.__new__(DungeonEngine)
    engine.dice = mock_dice
    engine._dungeon_state = dynamic_dungeon_state
    engine.controller = MagicMock()
    return engine


class TestDynamicRoomGeneration:
    """Tests for _generate_dynamic_room method."""

    def test_generate_dynamic_room_creates_room(self, dungeon_engine, mock_dice):
        """Verify _generate_dynamic_room creates a room with description."""
        # Roll 1 should give "Study" room
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=2),  # Connections roll
        ]

        room = dungeon_engine._generate_dynamic_room("room_1")

        assert room is not None
        assert room.room_id == "room_1"
        assert room.name == "Study"
        assert room.description == "Books of frost elf poetry, stag heads, ice hearth."
        assert room.visited is True

    def test_generate_dynamic_room_adds_exits(self, dungeon_engine, mock_dice):
        """Verify generated room has at least 1 exit."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=2),  # 2 connections
        ]

        room = dungeon_engine._generate_dynamic_room("room_1")

        assert len(room.exits) >= 1

    def test_generate_dynamic_room_with_bidirectional_exit(
        self, dungeon_engine, mock_dice
    ):
        """Verify generated room has exit back to source room."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=2),  # 2 connections
        ]

        room = dungeon_engine._generate_dynamic_room(
            "room_1", from_room_id="entry", from_direction="north"
        )

        # Should have south exit back to entry
        assert "south" in room.exits
        assert room.exits["south"] == "entry"
        # Door should be open (we just came through it)
        assert room.doors["room_1_south"] == DoorState.OPEN

    def test_generate_dynamic_room_adds_items(self, dungeon_engine, mock_dice):
        """Verify generated room includes items from table entry."""
        # Roll 1 = Study which has "frost elf poetry books"
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # 1 connection
        ]

        room = dungeon_engine._generate_dynamic_room("room_1")

        assert len(room.treasure) == 1
        assert room.treasure[0]["name"] == "frost elf poetry books"
        assert room.treasure[0]["found"] is False

    def test_generate_dynamic_room_pantry_has_multiple_items(
        self, dungeon_engine, mock_dice
    ):
        """Verify Pantry room (roll 5) has multiple items."""
        mock_dice.roll.side_effect = [
            MagicMock(total=5),  # Pantry
            MagicMock(total=1),  # 1 connection
        ]

        room = dungeon_engine._generate_dynamic_room("room_1")

        assert room.name == "Pantry"
        assert len(room.treasure) == 2
        item_names = [t["name"] for t in room.treasure]
        assert "bottled emotions" in item_names
        assert "iced fruits" in item_names

    def test_generate_dynamic_room_stored_in_state(self, dungeon_engine, mock_dice):
        """Verify generated room is stored in dungeon state."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1),
            MagicMock(total=1),
        ]

        room = dungeon_engine._generate_dynamic_room("room_1")

        assert "room_1" in dungeon_engine._dungeon_state.rooms
        assert dungeon_engine._dungeon_state.rooms["room_1"] is room


class TestGetOppositeDirection:
    """Tests for _get_opposite_direction helper."""

    def test_opposite_north_south(self, dungeon_engine):
        """Verify north <-> south mapping."""
        assert dungeon_engine._get_opposite_direction("north") == "south"
        assert dungeon_engine._get_opposite_direction("south") == "north"

    def test_opposite_east_west(self, dungeon_engine):
        """Verify east <-> west mapping."""
        assert dungeon_engine._get_opposite_direction("east") == "west"
        assert dungeon_engine._get_opposite_direction("west") == "east"

    def test_opposite_up_down(self, dungeon_engine):
        """Verify up <-> down mapping."""
        assert dungeon_engine._get_opposite_direction("up") == "down"
        assert dungeon_engine._get_opposite_direction("down") == "up"

    def test_opposite_case_insensitive(self, dungeon_engine):
        """Verify case insensitivity."""
        assert dungeon_engine._get_opposite_direction("NORTH") == "south"
        assert dungeon_engine._get_opposite_direction("North") == "south"


class TestHandleMoveWithDynamicGeneration:
    """Tests for _handle_move triggering dynamic room generation."""

    def test_move_to_unexplored_generates_room(self, dungeon_engine, mock_dice):
        """Verify moving to unexplored room triggers generation."""
        mock_dice.roll.side_effect = [
            MagicMock(total=2),  # Lounge
            MagicMock(total=2),  # 2 connections
            MagicMock(total=1),  # Encounter roll (if triggered)
        ]

        # Move north from entry to room_1
        result = dungeon_engine._handle_move({"direction": "north"})

        assert result["success"] is True
        assert result["new_room"] == "room_1"
        assert "room_1" in dungeon_engine._dungeon_state.rooms

        generated_room = dungeon_engine._dungeon_state.rooms["room_1"]
        assert generated_room.name == "Lounge"
        assert generated_room.description != ""

    def test_move_returns_room_description(self, dungeon_engine, mock_dice):
        """Verify move result includes room description."""
        mock_dice.roll.side_effect = [
            MagicMock(total=3),  # Dining room
            MagicMock(total=1),  # 1 connection
            MagicMock(total=1),  # Encounter roll
        ]

        result = dungeon_engine._handle_move({"direction": "north"})

        assert result["room_name"] == "Dining room"
        assert result["room_description"] == "Exquisite foods, frozen solid."

    def test_move_returns_exits(self, dungeon_engine, mock_dice):
        """Verify move result includes available exits."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Study
            MagicMock(total=2),  # 2 additional connections
            MagicMock(total=1),  # Encounter roll
        ]

        result = dungeon_engine._handle_move({"direction": "north"})

        assert "exits" in result
        assert "south" in result["exits"]  # Back to entry
        assert len(result["exits"]) >= 1

    def test_move_generates_encounter(self, dungeon_engine, mock_dice):
        """Verify move generates encounter for new room."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Study room
            MagicMock(total=1),  # 1 connection
            MagicMock(total=1),  # Encounter: Lord Hobbled
        ]

        result = dungeon_engine._handle_move({"direction": "north"})

        assert "encounter" in result
        assert result["encounter"]["roll"] == 1


class TestMultiRoomExploration:
    """Tests for exploring multiple rooms in sequence."""

    def test_explore_three_rooms(self, dungeon_engine, mock_dice):
        """Verify exploring 3+ rooms each has description and exits."""
        # Configure dice for 3 room generations
        mock_dice.roll.side_effect = [
            # Room 1: Study with 2 connections
            MagicMock(total=1),
            MagicMock(total=2),
            MagicMock(total=1),  # Encounter
            # Room 2: Lounge with 2 connections
            MagicMock(total=2),
            MagicMock(total=2),
            MagicMock(total=2),  # Encounter
            # Room 3: Dining room with 1 connection
            MagicMock(total=3),
            MagicMock(total=1),
            MagicMock(total=1),  # Encounter
        ]

        # Move to room 1
        result1 = dungeon_engine._handle_move({"direction": "north"})
        assert result1["success"] is True
        assert result1["room_description"] != ""
        room1_id = result1["new_room"]

        # Get an exit to move to (not back to entry)
        room1 = dungeon_engine._dungeon_state.rooms[room1_id]
        next_direction = None
        for direction, target in room1.exits.items():
            if target != "entry":
                next_direction = direction
                break

        if next_direction:
            # Move to room 2
            result2 = dungeon_engine._handle_move({"direction": next_direction})
            assert result2["success"] is True
            assert result2["room_description"] != ""
            room2_id = result2["new_room"]

            # Get an exit to move to
            room2 = dungeon_engine._dungeon_state.rooms[room2_id]
            next_direction2 = None
            for direction, target in room2.exits.items():
                if target not in ["entry", room1_id]:
                    next_direction2 = direction
                    break

            if next_direction2:
                # Move to room 3
                result3 = dungeon_engine._handle_move({"direction": next_direction2})
                assert result3["success"] is True
                assert result3["room_description"] != ""
                assert len(result3["exits"]) >= 1

    def test_rooms_have_unique_ids(self, dungeon_engine, mock_dice):
        """Verify each generated room has a unique ID."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1), MagicMock(total=3),  # Room 1 with 3 exits
            MagicMock(total=1),  # Encounter
            MagicMock(total=2), MagicMock(total=2),  # Room 2
            MagicMock(total=1),  # Encounter
        ]

        dungeon_engine._handle_move({"direction": "north"})
        room1 = dungeon_engine._dungeon_state.rooms["room_1"]

        # Move to next room
        for direction, target in room1.exits.items():
            if target != "entry" and target not in dungeon_engine._dungeon_state.rooms:
                dungeon_engine._handle_move({"direction": direction})
                break

        # All rooms should have unique IDs
        room_ids = list(dungeon_engine._dungeon_state.rooms.keys())
        assert len(room_ids) == len(set(room_ids))


class TestNonDynamicDungeonFallback:
    """Tests for non-dynamic dungeons (fallback behavior)."""

    def test_move_without_dynamic_layout_creates_empty_room(self, mock_dice):
        """Verify non-dynamic dungeon creates placeholder room."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice
        engine.controller = MagicMock()

        # Create state WITHOUT dynamic_layout
        state = DungeonState(
            dungeon_id="static_dungeon",
            name="Static Dungeon",
            current_room="entry",
            dynamic_layout=None,  # No dynamic layout
        )
        entry_room = DungeonRoom(
            room_id="entry",
            exits={"north": "room_1"},
        )
        entry_room.doors["entry_north"] = DoorState.CLOSED
        state.rooms["entry"] = entry_room
        engine._dungeon_state = state

        result = engine._handle_move({"direction": "north"})

        assert result["success"] is True
        assert "room_1" in engine._dungeon_state.rooms
        # Room should be empty placeholder (no name/description)
        room = engine._dungeon_state.rooms["room_1"]
        assert room.name == ""
        assert room.description == ""


class TestRoomTableMissing:
    """Tests for handling missing room table."""

    def test_generate_room_without_table_returns_none(self, mock_dice):
        """Verify generation returns None without room table."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice
        engine._dungeon_state = DungeonState(
            dungeon_id="test",
            dynamic_layout={"connections_per_room": "1d3"},
            room_table=None,  # No room table
        )

        result = engine._generate_dynamic_room("room_1")

        assert result is None

    def test_move_falls_back_to_empty_room_without_table(self, mock_dice):
        """Verify move creates empty room if generation fails."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice
        engine.controller = MagicMock()

        state = DungeonState(
            dungeon_id="test",
            current_room="entry",
            dynamic_layout={"connections_per_room": "1d3"},
            room_table=None,  # No room table - generation will fail
        )
        entry_room = DungeonRoom(
            room_id="entry",
            exits={"north": "room_1"},
        )
        entry_room.doors["entry_north"] = DoorState.CLOSED
        state.rooms["entry"] = entry_room
        engine._dungeon_state = state

        result = engine._handle_move({"direction": "north"})

        assert result["success"] is True
        # Should have created empty fallback room
        assert "room_1" in engine._dungeon_state.rooms
