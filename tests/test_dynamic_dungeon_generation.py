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

    # Set up controller with properly mocked party_state
    controller = MagicMock()
    controller.party_state.active_light_source = True
    controller.party_state.light_remaining_turns = 10
    controller.party_state.party_inventory = []  # Real list for treasure tests
    engine.controller = controller

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
            MagicMock(total=1),  # Encounter roll -> NPC (Lord Hobbled)
            MagicMock(total=30),  # Distance roll (for encounter state)
        ]
        # Surprise rolls for encounter state creation
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise
            MagicMock(total=3),  # NPC surprise
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
            MagicMock(total=1),  # Encounter roll -> NPC
            MagicMock(total=30),  # Distance roll
        ]
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise
            MagicMock(total=3),  # NPC surprise
        ]

        result = dungeon_engine._handle_move({"direction": "north"})

        assert result["room_name"] == "Dining room"
        assert result["room_description"] == "Exquisite foods, frozen solid."

    def test_move_returns_exits(self, dungeon_engine, mock_dice):
        """Verify move result includes available exits."""
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Study
            MagicMock(total=2),  # 2 additional connections
            MagicMock(total=1),  # Encounter roll -> NPC
            MagicMock(total=30),  # Distance roll
        ]
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise
            MagicMock(total=3),  # NPC surprise
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
            MagicMock(total=1),  # Encounter: Lord Hobbled (NPC)
            MagicMock(total=30),  # Distance roll
        ]
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise
            MagicMock(total=3),  # NPC surprise
        ]

        result = dungeon_engine._handle_move({"direction": "north"})

        assert "encounter" in result
        assert result["encounter"]["roll"] == 1


class TestMultiRoomExploration:
    """Tests for exploring multiple rooms in sequence."""

    def test_explore_three_rooms(self, dungeon_engine, mock_dice):
        """Verify exploring 3+ rooms each has description and exits."""
        # Configure dice for 3 room generations, each with encounter and state transition
        mock_dice.roll.side_effect = [
            # Room 1: Study with 2 connections
            MagicMock(total=1),  # Room table
            MagicMock(total=2),  # Connections
            MagicMock(total=1),  # Encounter (NPC)
            MagicMock(total=30),  # Distance
            # Room 2: Lounge with 2 connections
            MagicMock(total=2),  # Room table
            MagicMock(total=2),  # Connections
            MagicMock(total=2),  # Encounter (monster)
            MagicMock(total=30),  # Distance
            # Room 3: Dining room with 1 connection
            MagicMock(total=3),  # Room table
            MagicMock(total=1),  # Connections
            MagicMock(total=1),  # Encounter (NPC)
            MagicMock(total=30),  # Distance
        ]
        # Surprise rolls for each encounter
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3), MagicMock(total=3),  # Room 1
            MagicMock(total=3), MagicMock(total=3),  # Room 2
            MagicMock(total=3), MagicMock(total=3),  # Room 3
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
            MagicMock(total=1),  # Encounter (NPC)
            MagicMock(total=30),  # Distance
            MagicMock(total=2), MagicMock(total=2),  # Room 2
            MagicMock(total=1),  # Encounter (NPC)
            MagicMock(total=30),  # Distance
        ]
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3), MagicMock(total=3),  # Room 1 surprise
            MagicMock(total=3), MagicMock(total=3),  # Room 2 surprise
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


class TestSeededDiceRoomGeneration:
    """Tests for seeded dice producing specific room content from tables."""

    def test_each_room_roll_produces_correct_room(self, dungeon_engine, mock_dice):
        """Verify each dice roll produces the corresponding room from table."""
        # Test all 6 room types
        expected_rooms = [
            (1, "Study", "Books of frost elf poetry, stag heads, ice hearth."),
            (2, "Lounge", "Velvet couches, ice candles, wolf-skin rugs."),
            (3, "Dining room", "Exquisite foods, frozen solid."),
            (4, "Winter garden", "Hoar-clad roses drip blood if touched."),
            (5, "Pantry", "Bottled emotions, iced fruits, frozen game."),
            (6, "Bedroom", "Ice-block bed, furs, tundra tapestries."),
        ]

        for roll_value, expected_name, expected_description in expected_rooms:
            # Reset state for each test
            dungeon_engine._dungeon_state.rooms = {"entry": dungeon_engine._dungeon_state.rooms["entry"]}

            mock_dice.roll.side_effect = [
                MagicMock(total=roll_value),  # Room table roll
                MagicMock(total=1),  # Connections roll
            ]

            room = dungeon_engine._generate_dynamic_room(f"room_{roll_value}")

            assert room is not None, f"Failed for roll {roll_value}"
            assert room.name == expected_name, f"Expected {expected_name}, got {room.name}"
            assert room.description == expected_description, (
                f"Expected {expected_description}, got {room.description}"
            )

    def test_room_features_from_mechanical_effect(self, mock_dice):
        """Verify rooms with mechanical_effect get a Feature added."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice

        # Create room table with mechanical_effect
        entries = [
            RollTableEntry(
                roll=1,
                title="Danger Room",
                description="A room with hazards.",
                mechanical_effect="Roses drip blood if touched, causing 1 damage",
            ),
        ]
        room_table = RollTable(
            name="Rooms",
            die_type="d6",
            description="Test rooms",
            entries=entries,
        )

        state = DungeonState(
            dungeon_id="test",
            dynamic_layout={"connections_per_room": "1d3"},
            room_table=room_table,
        )
        state.rooms = {}
        engine._dungeon_state = state

        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # Connections roll
        ]

        room = engine._generate_dynamic_room("room_1")

        assert room is not None
        assert len(room.features) == 1
        feature = room.features[0]
        assert feature.feature_id == "room_1_effect"
        assert feature.name == "Danger Room"
        assert "Roses drip blood" in feature.description
        assert feature.discovered is True


class TestEncounterStateTransition:
    """Tests for encounter table rolling and state transitions."""

    def test_monster_encounter_creates_encounter_state(self, dungeon_engine, mock_dice):
        """Verify monster encounter creates EncounterState and triggers transition."""
        # Roll 2 = silver hounds (monster encounter)
        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # Connections roll
            MagicMock(total=2),  # Encounter: silver hounds
            MagicMock(total=30),  # Distance roll
        ]
        # Rolls for surprise
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise roll (not surprised)
            MagicMock(total=3),  # Monster surprise roll (not surprised)
        ]

        result = dungeon_engine._handle_move({"direction": "north"})

        assert result["success"] is True
        assert "encounter" in result
        assert result["encounter"]["encounter_type"] == "monster"
        assert result["encounter"]["requires_transition"] is True

        # Verify encounter state was created and transition was called
        assert "encounter_state" in result
        dungeon_engine.controller.set_encounter.assert_called_once()
        dungeon_engine.controller.transition.assert_called_once()

        # Check transition was called with correct event
        call_args = dungeon_engine.controller.transition.call_args
        assert call_args[0][0] == "encounter_triggered"
        assert call_args[1]["context"]["source"] == "room_entry"

    def test_npc_encounter_creates_encounter_state(self, mock_dice):
        """Verify NPC encounter creates EncounterState with social option."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice

        # Set up controller with properly mocked party_state
        controller = MagicMock()
        controller.party_state.active_light_source = True
        controller.party_state.light_remaining_turns = 10
        engine.controller = controller

        # Create room and encounter tables
        room_entries = [
            RollTableEntry(roll=1, title="Hall", description="A grand hall."),
        ]
        room_table = RollTable(
            name="Rooms",
            die_type="d6",
            entries=room_entries,
        )

        encounter_entries = [
            RollTableEntry(
                roll=1,
                description="A spectral lord appears.",
                npcs=["spectral_lord"],
            ),
        ]
        encounter_table = RollTable(
            name="Encounters",
            die_type="d6",
            entries=encounter_entries,
        )

        state = DungeonState(
            dungeon_id="test",
            current_room="entry",
            dynamic_layout={"connections_per_room": "1d3"},
            room_table=room_table,
            encounter_table=encounter_table,
        )
        entry_room = DungeonRoom(room_id="entry", exits={"north": "room_1"})
        entry_room.doors["entry_north"] = DoorState.CLOSED
        state.rooms = {"entry": entry_room}
        engine._dungeon_state = state

        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # Connections roll
            MagicMock(total=1),  # Encounter: spectral lord
            MagicMock(total=30),  # Distance roll
        ]
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise
            MagicMock(total=3),  # NPC surprise
        ]

        result = engine._handle_move({"direction": "north"})

        assert "encounter" in result
        assert result["encounter"]["encounter_type"] == "npc"
        assert result["encounter"]["allows_social"] is True
        assert result["encounter"]["requires_transition"] is True

        # Verify transition was triggered
        engine.controller.transition.assert_called_once()

    def test_ambient_encounter_no_state_transition(self, mock_dice):
        """Verify ambient encounters do not trigger state transitions."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice
        engine.controller = MagicMock()

        # Create encounter table with ambient entry (no monsters/npcs)
        room_entries = [
            RollTableEntry(roll=1, title="Hall", description="A grand hall."),
        ]
        room_table = RollTable(
            name="Rooms",
            die_type="d6",
            entries=room_entries,
        )

        encounter_entries = [
            RollTableEntry(
                roll=1,
                description="A cold wind blows through the corridor.",
            ),
        ]
        encounter_table = RollTable(
            name="Encounters",
            die_type="d6",
            entries=encounter_entries,
        )

        state = DungeonState(
            dungeon_id="test",
            current_room="entry",
            dynamic_layout={"connections_per_room": "1d3"},
            room_table=room_table,
            encounter_table=encounter_table,
        )
        entry_room = DungeonRoom(room_id="entry", exits={"north": "room_1"})
        entry_room.doors["entry_north"] = DoorState.CLOSED
        state.rooms = {"entry": entry_room}
        engine._dungeon_state = state

        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # Connections roll
            MagicMock(total=1),  # Encounter: ambient
        ]

        result = engine._handle_move({"direction": "north"})

        assert "encounter" in result
        assert result["encounter"]["encounter_type"] == "ambient"
        assert result["encounter"]["requires_transition"] is False

        # Verify NO transition was triggered
        engine.controller.transition.assert_not_called()
        engine.controller.set_encounter.assert_not_called()

    def test_item_encounter_no_state_transition(self, mock_dice):
        """Verify item discovery encounters do not trigger state transitions."""
        engine = DungeonEngine.__new__(DungeonEngine)
        engine.dice = mock_dice
        engine.controller = MagicMock()

        room_entries = [
            RollTableEntry(roll=1, title="Hall", description="A hall."),
        ]
        room_table = RollTable(name="Rooms", die_type="d6", entries=room_entries)

        encounter_entries = [
            RollTableEntry(
                roll=1,
                description="A glittering gem rests on a pedestal.",
                items=["glittering gem"],
            ),
        ]
        encounter_table = RollTable(
            name="Encounters",
            die_type="d6",
            entries=encounter_entries,
        )

        state = DungeonState(
            dungeon_id="test",
            current_room="entry",
            dynamic_layout={"connections_per_room": "1d3"},
            room_table=room_table,
            encounter_table=encounter_table,
        )
        entry_room = DungeonRoom(room_id="entry", exits={"north": "room_1"})
        entry_room.doors["entry_north"] = DoorState.CLOSED
        state.rooms = {"entry": entry_room}
        engine._dungeon_state = state

        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # Connections roll
            MagicMock(total=1),  # Encounter: item
        ]

        result = engine._handle_move({"direction": "north"})

        assert "encounter" in result
        assert result["encounter"]["encounter_type"] == "item"
        assert result["encounter"]["requires_transition"] is False

        # Verify NO transition was triggered
        engine.controller.transition.assert_not_called()

    def test_encounter_transition_includes_context(self, dungeon_engine, mock_dice):
        """Verify encounter transition includes required context for EncounterEngine."""
        # Set up dungeon state with POI info
        dungeon_engine._dungeon_state.poi_name = "The Spectral Manse"
        dungeon_engine._dungeon_state.hex_id = "0101"

        mock_dice.roll.side_effect = [
            MagicMock(total=1),  # Room table roll
            MagicMock(total=1),  # Connections roll
            MagicMock(total=2),  # Encounter: monster
            MagicMock(total=30),  # Distance roll
        ]
        mock_dice.roll_d6.side_effect = [
            MagicMock(total=3),  # Party surprise
            MagicMock(total=3),  # Monster surprise
        ]

        dungeon_engine._handle_move({"direction": "north"})

        # Verify transition context
        call_args = dungeon_engine.controller.transition.call_args
        context = call_args[1]["context"]

        assert context["dungeon_id"] == "spectral_manse"
        assert context["room_id"] == "room_1"
        assert context["source"] == "room_entry"
        assert context["poi_name"] == "The Spectral Manse"
        assert context["hex_id"] == "0101"
        assert "encounter_data" in context


class TestTreasureDiscovery:
    """Tests for treasure discovery during search."""

    def test_search_reveals_treasure(self, dungeon_engine, mock_dice):
        """Verify searching a room reveals unfound treasure."""
        # Set up room with treasure
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Gold coins", "value": 50, "found": False},
            {"name": "Silver dagger", "value": 25, "found": False},
        ]

        # Mock any dice rolls for hidden features/traps (roll 6 = fail to find hidden stuff)
        mock_dice.roll_d6.return_value = MagicMock(total=6)

        result = dungeon_engine._handle_search({})

        assert result["success"] is True
        assert len(result["found_treasure"]) == 2
        assert result["found_treasure"][0]["name"] == "Gold coins"
        assert result["found_treasure"][0]["value"] == 50
        assert result["found_treasure"][1]["name"] == "Silver dagger"

    def test_search_marks_treasure_as_found(self, dungeon_engine, mock_dice):
        """Verify found treasure is marked to prevent duplicates."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Ruby", "value": 100, "found": False},
        ]

        mock_dice.roll_d6.return_value = MagicMock(total=6)

        dungeon_engine._handle_search({})

        # Treasure should be marked as found
        assert current_room.treasure[0]["found"] is True

    def test_repeated_search_no_duplicate_treasure(self, dungeon_engine, mock_dice):
        """Verify repeated searches don't report already-found treasure."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Ancient tome", "value": 200, "found": False},
        ]

        mock_dice.roll_d6.return_value = MagicMock(total=6)

        # First search finds treasure
        result1 = dungeon_engine._handle_search({})
        assert len(result1["found_treasure"]) == 1

        # Second search finds nothing new
        result2 = dungeon_engine._handle_search({})
        assert len(result2["found_treasure"]) == 0

    def test_search_empty_room_no_treasure(self, dungeon_engine, mock_dice):
        """Verify searching a room with no treasure reports empty list."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = []

        mock_dice.roll_d6.return_value = MagicMock(total=6)

        result = dungeon_engine._handle_search({})

        assert result["success"] is True
        assert result["found_treasure"] == []

    def test_treasure_quantity_included(self, dungeon_engine, mock_dice):
        """Verify treasure quantity is included in results."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Copper pieces", "value": 10, "quantity": 50, "found": False},
        ]

        mock_dice.roll_d6.return_value = MagicMock(total=6)

        result = dungeon_engine._handle_search({})

        assert len(result["found_treasure"]) == 1
        assert result["found_treasure"][0]["quantity"] == 50

    def test_treasure_default_quantity_is_one(self, dungeon_engine, mock_dice):
        """Verify treasure without quantity defaults to 1."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Magic wand", "found": False},  # No quantity specified
        ]

        mock_dice.roll_d6.return_value = MagicMock(total=6)

        result = dungeon_engine._handle_search({})

        assert result["found_treasure"][0]["quantity"] == 1


class TestTakeTreasure:
    """Tests for taking treasure from rooms."""

    def test_take_treasure_removes_from_room(self, dungeon_engine, mock_dice):
        """Verify taking treasure removes it from the room."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Gold coins", "value": 50, "found": True},
        ]

        result = dungeon_engine._handle_take_treasure({})

        assert result["success"] is True
        assert len(current_room.treasure) == 0
        assert "Gold coins" in result["message"]

    def test_take_treasure_adds_to_party_inventory(self, dungeon_engine, mock_dice):
        """Verify taking treasure adds it to party inventory."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Ruby", "value": 100, "found": True},
        ]

        result = dungeon_engine._handle_take_treasure({})

        assert result["success"] is True
        assert len(dungeon_engine.controller.party_state.party_inventory) == 1
        assert dungeon_engine.controller.party_state.party_inventory[0]["name"] == "Ruby"
        assert dungeon_engine.controller.party_state.party_inventory[0]["value"] == 100

    def test_take_treasure_requires_discovered(self, dungeon_engine, mock_dice):
        """Verify cannot take treasure that hasn't been discovered."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Hidden gold", "value": 50, "found": False},
        ]

        result = dungeon_engine._handle_take_treasure({})

        assert result["success"] is False
        assert "Search the room first" in result["message"]
        assert len(current_room.treasure) == 1

    def test_take_all_treasure(self, dungeon_engine, mock_dice):
        """Verify take_all takes all discovered treasure."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Gold coins", "value": 50, "found": True},
            {"name": "Silver dagger", "value": 25, "found": True},
            {"name": "Hidden gem", "value": 200, "found": False},
        ]

        result = dungeon_engine._handle_take_treasure({"take_all": True})

        assert result["success"] is True
        assert len(result["items_taken"]) == 2
        # Hidden gem should remain
        assert len(current_room.treasure) == 1
        assert current_room.treasure[0]["name"] == "Hidden gem"

    def test_take_treasure_by_name(self, dungeon_engine, mock_dice):
        """Verify taking treasure by name."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Gold coins", "value": 50, "found": True},
            {"name": "Silver dagger", "value": 25, "found": True},
        ]

        result = dungeon_engine._handle_take_treasure({"item_name": "Silver dagger"})

        assert result["success"] is True
        assert len(result["items_taken"]) == 1
        assert result["items_taken"][0]["name"] == "Silver dagger"
        # Gold coins should remain
        assert len(current_room.treasure) == 1
        assert current_room.treasure[0]["name"] == "Gold coins"

    def test_take_treasure_by_index(self, dungeon_engine, mock_dice):
        """Verify taking treasure by index."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Gold coins", "value": 50, "found": True},
            {"name": "Silver dagger", "value": 25, "found": True},
        ]

        result = dungeon_engine._handle_take_treasure({"item_index": 1})

        assert result["success"] is True
        assert result["items_taken"][0]["name"] == "Silver dagger"
        assert len(current_room.treasure) == 1

    def test_take_treasure_logs_event(self, dungeon_engine, mock_dice):
        """Verify taking treasure logs an event."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Ancient artifact", "value": 500, "found": True},
        ]

        dungeon_engine._handle_take_treasure({})

        dungeon_engine.controller.log_event.assert_called_once()
        call_args = dungeon_engine.controller.log_event.call_args
        assert call_args[0][0] == "treasure_taken"
        assert "items" in call_args[0][1]

    def test_take_treasure_includes_source(self, dungeon_engine, mock_dice):
        """Verify taken treasure includes source location."""
        current_room = dungeon_engine._dungeon_state.rooms["entry"]
        current_room.treasure = [
            {"name": "Gem", "value": 75, "found": True},
        ]

        dungeon_engine._handle_take_treasure({})

        inventory = dungeon_engine.controller.party_state.party_inventory
        assert len(inventory) == 1
        assert "source" in inventory[0]
        assert "entry" in inventory[0]["source"]
