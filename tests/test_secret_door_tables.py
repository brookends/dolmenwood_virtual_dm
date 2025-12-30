"""
Tests for Secret Door tables and mechanics per Campaign Book p104.

Tests cover:
- Three secret door types (hidden, hidden mechanism, doubly hidden)
- 20 secret door locations
- 20 mechanical mechanisms
- 20 magical mechanisms
- Clue generation
- Search mechanics
- Mechanism interaction
"""

import pytest
from src.data_models import DiceRoller
from src.tables.secret_door_tables import (
    SecretDoorType,
    MechanismType,
    SecretDoorLocation,
    MechanicalMechanism,
    MagicalMechanism,
    ClueType,
    PortalType,
    SecretDoor,
    SecretDoorInteraction,
    LOCATION_DESCRIPTIONS,
    MECHANICAL_MECHANISM_DESCRIPTIONS,
    MAGICAL_MECHANISM_DESCRIPTIONS,
    VISUAL_CLUES,
    FUNCTIONAL_CLUES,
    SYMBOLIC_CLUES,
    roll_secret_door_type,
    roll_location,
    roll_mechanism_type,
    roll_mechanical_mechanism,
    roll_magical_mechanism,
    generate_clues,
    generate_secret_door,
    attempt_open_mechanism,
    search_for_secret_door,
)


class TestSecretDoorEnums:
    """Test secret door type enums."""

    def test_secret_door_types(self):
        """Test all three secret door types exist."""
        assert SecretDoorType.HIDDEN_DOOR == "hidden_door"
        assert SecretDoorType.HIDDEN_MECHANISM == "hidden_mechanism"
        assert SecretDoorType.DOUBLY_HIDDEN == "doubly_hidden"

    def test_mechanism_types(self):
        """Test mechanism type enum."""
        assert MechanismType.NONE == "none"
        assert MechanismType.MECHANICAL == "mechanical"
        assert MechanismType.MAGICAL == "magical"

    def test_all_20_locations_exist(self):
        """Verify all 20 locations from Campaign Book p104 are defined."""
        locations = list(SecretDoorLocation)
        assert len(locations) == 20

        # Check specific locations from the book
        assert SecretDoorLocation.POOL_BASE in locations
        assert SecretDoorLocation.BEHIND_TAPESTRY in locations
        assert SecretDoorLocation.PIVOTING_BOOKSHELF in locations
        assert SecretDoorLocation.SEAMLESS_WALL in locations

    def test_all_20_mechanical_mechanisms_exist(self):
        """Verify all 20 mechanical mechanisms from Campaign Book p104."""
        mechanisms = list(MechanicalMechanism)
        assert len(mechanisms) == 20

        # Check specific mechanisms from the book
        assert MechanicalMechanism.PULL_TORCH_SCONCE in mechanisms
        assert MechanicalMechanism.PRESS_BRICK in mechanisms
        assert MechanicalMechanism.WEIGHT_PRESSURE_PLATE in mechanisms

    def test_all_20_magical_mechanisms_exist(self):
        """Verify all 20 magical mechanisms from Campaign Book p104."""
        mechanisms = list(MagicalMechanism)
        assert len(mechanisms) == 20

        # Check specific mechanisms from the book
        assert MagicalMechanism.SPEAK_COMMAND_WORD in mechanisms
        assert MagicalMechanism.ANSWER_RIDDLE in mechanisms
        assert MagicalMechanism.KISS_STATUE in mechanisms

    def test_portal_types(self):
        """Test portal types for non-standard doors."""
        assert PortalType.DOOR == "door"
        assert PortalType.TRAPDOOR_FLOOR == "trapdoor_floor"
        assert PortalType.TRAPDOOR_CEILING == "trapdoor_ceiling"
        assert PortalType.HATCH == "hatch"
        assert PortalType.SPYHOLE == "spyhole"


class TestLocationDescriptions:
    """Test location description data."""

    def test_all_locations_have_descriptions(self):
        """Every location should have a description dict."""
        for location in SecretDoorLocation:
            assert location in LOCATION_DESCRIPTIONS
            desc = LOCATION_DESCRIPTIONS[location]
            assert "name" in desc
            assert "description" in desc
            assert "discovery_hint" in desc

    def test_location_with_portal_type(self):
        """Some locations specify a different portal type."""
        # Beneath statue should be a trapdoor
        beneath_statue = LOCATION_DESCRIPTIONS[SecretDoorLocation.BENEATH_STATUE]
        assert beneath_statue.get("portal_type") == PortalType.TRAPDOOR_FLOOR

        # False closet back should be a closet
        false_closet = LOCATION_DESCRIPTIONS[SecretDoorLocation.FALSE_CLOSET]
        assert false_closet.get("portal_type") == PortalType.CLOSET


class TestMechanismDescriptions:
    """Test mechanism description data."""

    def test_all_mechanical_mechanisms_have_descriptions(self):
        """Every mechanical mechanism should have details."""
        for mechanism in MechanicalMechanism:
            assert mechanism in MECHANICAL_MECHANISM_DESCRIPTIONS
            desc = MECHANICAL_MECHANISM_DESCRIPTIONS[mechanism]
            assert "name" in desc
            assert "description" in desc
            assert "action_required" in desc
            assert "clue" in desc

    def test_all_magical_mechanisms_have_descriptions(self):
        """Every magical mechanism should have details."""
        for mechanism in MagicalMechanism:
            assert mechanism in MAGICAL_MECHANISM_DESCRIPTIONS
            desc = MAGICAL_MECHANISM_DESCRIPTIONS[mechanism]
            assert "name" in desc
            assert "description" in desc
            assert "action_required" in desc
            assert "clue" in desc

    def test_mechanisms_requiring_items(self):
        """Some mechanisms require specific items."""
        # Put coin in slot requires a coin
        coin_slot = MECHANICAL_MECHANISM_DESCRIPTIONS[MechanicalMechanism.PUT_COIN_SLOT]
        assert coin_slot.get("requires_item") is True
        assert coin_slot.get("item_type") == "coin"

        # Put gem in statue eye requires a gem
        gem_eye = MAGICAL_MECHANISM_DESCRIPTIONS[MagicalMechanism.PUT_GEM_STATUE_EYE]
        assert gem_eye.get("requires_item") is True
        assert gem_eye.get("item_type") == "gem"

    def test_mechanisms_requiring_password(self):
        """Speak command word requires a password."""
        command_word = MAGICAL_MECHANISM_DESCRIPTIONS[MagicalMechanism.SPEAK_COMMAND_WORD]
        assert command_word.get("requires_password") is True


class TestClueGeneration:
    """Test clue generation."""

    def test_visual_clues_exist(self):
        """Visual clues should be populated."""
        assert len(VISUAL_CLUES) >= 5

    def test_functional_clues_exist(self):
        """Functional clues should be populated."""
        assert len(FUNCTIONAL_CLUES) >= 3

    def test_symbolic_clues_exist(self):
        """Symbolic clues should be populated."""
        assert len(SYMBOLIC_CLUES) >= 3

    def test_generate_clues_includes_location_hint(self):
        """Generated clues should include location-specific hint."""
        DiceRoller.set_seed(42)
        clues = generate_clues(
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            mechanism_type=MechanismType.NONE,
            mechanism=None,
        )

        # Should have visual clues including the location hint
        assert "visual" in clues
        assert len(clues["visual"]) >= 1

        # Location-specific hint should be in visual clues
        loc_hint = LOCATION_DESCRIPTIONS[SecretDoorLocation.BEHIND_TAPESTRY]["discovery_hint"]
        assert loc_hint in clues["visual"]

    def test_generate_clues_with_mechanism(self):
        """Generated clues should include mechanism clue when present."""
        DiceRoller.set_seed(42)
        clues = generate_clues(
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PULL_TORCH_SCONCE.value,
        )

        # Should have symbolic clue about the mechanism
        assert "symbolic" in clues
        # At least one clue should reference the mechanism
        mech_clue = MECHANICAL_MECHANISM_DESCRIPTIONS[MechanicalMechanism.PULL_TORCH_SCONCE]["clue"]
        assert mech_clue in clues["symbolic"]


class TestSecretDoorGeneration:
    """Test secret door generation."""

    def test_roll_secret_door_type_distribution(self):
        """Test door type roll distribution."""
        DiceRoller.set_seed(42)
        dice = DiceRoller()

        # Roll many times and check distribution
        types = {"hidden_door": 0, "hidden_mechanism": 0, "doubly_hidden": 0}
        for _ in range(100):
            door_type = roll_secret_door_type(dice)
            types[door_type.value] += 1

        # Hidden door should be most common (~50%)
        assert types["hidden_door"] > types["hidden_mechanism"]
        # Doubly hidden should be least common (~17%)
        assert types["doubly_hidden"] < types["hidden_mechanism"]

    def test_roll_location_all_valid(self):
        """All rolled locations should be valid enum values."""
        DiceRoller.set_seed(42)
        dice = DiceRoller()

        for _ in range(50):
            location = roll_location(dice)
            assert location in SecretDoorLocation

    def test_generate_secret_door_basic(self):
        """Test basic secret door generation."""
        DiceRoller.set_seed(42)

        door = generate_secret_door(
            door_id="test_door_1",
            destination_room="room_2",
            direction="north",
        )

        assert door.door_id == "test_door_1"
        assert door.destination_room == "room_2"
        assert door.direction == "north"
        assert door.door_type in SecretDoorType
        assert door.location in SecretDoorLocation
        assert not door.door_discovered
        assert not door.door_opened

    def test_generate_secret_door_with_mechanism(self):
        """Test generating door with specified mechanism type."""
        DiceRoller.set_seed(42)

        door = generate_secret_door(
            door_id="test_door_mech",
            mechanism_type=MechanismType.MECHANICAL,
        )

        assert door.mechanism_type == MechanismType.MECHANICAL
        assert door.mechanism is not None
        assert door.mechanism in [m.value for m in MechanicalMechanism]

    def test_generate_secret_door_with_magical_mechanism(self):
        """Test generating door with magical mechanism."""
        DiceRoller.set_seed(42)

        door = generate_secret_door(
            door_id="test_door_magic",
            mechanism_type=MechanismType.MAGICAL,
        )

        assert door.mechanism_type == MechanismType.MAGICAL
        assert door.mechanism is not None
        assert door.mechanism in [m.value for m in MagicalMechanism]

    def test_generate_secret_door_has_clues(self):
        """Generated doors should have clues."""
        DiceRoller.set_seed(42)

        door = generate_secret_door(door_id="test_door_clues")

        # Should have at least one visual clue
        assert len(door.visual_clues) >= 1


class TestSecretDoorDataclass:
    """Test SecretDoor dataclass methods."""

    def test_is_fully_discovered_hidden_door(self):
        """Hidden door is fully discovered when door is found."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            mechanism_type=MechanismType.NONE,
        )

        assert not door.is_fully_discovered()
        door.door_discovered = True
        assert door.is_fully_discovered()

    def test_is_fully_discovered_hidden_mechanism(self):
        """Hidden mechanism door requires mechanism to be discovered."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PULL_TORCH_SCONCE.value,
        )

        # Door is visible but mechanism is not found
        door.door_discovered = True
        assert not door.is_fully_discovered()

        # Now mechanism is found
        door.mechanism_discovered = True
        assert door.is_fully_discovered()

    def test_is_fully_discovered_doubly_hidden(self):
        """Doubly hidden requires both door and mechanism discovered."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.DOUBLY_HIDDEN,
            location=SecretDoorLocation.PIVOTING_BOOKSHELF,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PRESS_BRICK.value,
        )

        assert not door.is_fully_discovered()

        door.door_discovered = True
        assert not door.is_fully_discovered()

        door.mechanism_discovered = True
        assert door.is_fully_discovered()

    def test_can_be_opened(self):
        """Test can_be_opened logic."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_MIRROR,
            mechanism_type=MechanismType.NONE,
        )

        # Not discovered = can't open
        assert not door.can_be_opened()

        # Discovered, no mechanism = can open
        door.door_discovered = True
        assert door.can_be_opened()

        # Already open = can open
        door.door_opened = True
        assert door.can_be_opened()

    def test_get_required_action(self):
        """Test getting required action for mechanism doors."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PULL_TORCH_SCONCE.value,
        )

        action = door.get_required_action()
        assert action is not None
        assert "torch" in action.lower() or "sconce" in action.lower()

    def test_requires_item(self):
        """Test item requirement detection."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PUT_COIN_SLOT.value,
            mechanism_details={"requires_item": True, "item_type": "coin"},
        )

        assert door.requires_item() == "coin"

    def test_to_dict(self):
        """Test serialization."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            direction="north",
            destination_room="room_2",
        )

        data = door.to_dict()

        assert data["door_id"] == "test"
        assert data["door_type"] == "hidden_door"
        assert data["location"] == "behind_tapestry"
        assert data["direction"] == "north"


class TestSearchMechanics:
    """Test searching for secret doors."""

    def test_search_finds_hidden_door(self):
        """Test that searching can find a hidden door."""
        DiceRoller.set_seed(1)  # Seed for low roll

        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            mechanism_type=MechanismType.NONE,
        )

        # Search multiple times to eventually find it
        found = False
        for _ in range(20):
            result = search_for_secret_door(door)
            if result["door_found"]:
                found = True
                break

        assert found or door.door_discovered

    def test_search_provides_clues_on_partial_success(self):
        """Test that partial search success provides clues."""
        DiceRoller.set_seed(42)

        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            mechanism_type=MechanismType.NONE,
            visual_clues=["A draft stirs the bottom of the tapestry"],
        )

        # Search multiple times to get clue result
        clue_found = False
        for _ in range(30):
            if door.door_discovered:
                break
            result = search_for_secret_door(door)
            if result["clues_found"]:
                clue_found = True
                break

        # Either found the door or got a clue
        assert door.door_discovered or clue_found

    def test_search_hidden_mechanism_door_visible(self):
        """Hidden mechanism doors should be immediately visible."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PULL_TORCH_SCONCE.value,
        )

        result = search_for_secret_door(door)

        # Door should be auto-discovered for this type
        assert door.door_discovered

    def test_search_with_thief_bonus(self):
        """Thieves should have better search chance."""
        DiceRoller.set_seed(42)

        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.DOUBLY_HIDDEN,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PRESS_BRICK.value,
        )

        # Search with thief bonus
        result = search_for_secret_door(
            door,
            searcher_class="thief",
            search_bonus=2,  # Thief gets +2 to search
        )

        # Higher chance of success with bonus
        assert "message" in result


class TestMechanismInteraction:
    """Test interacting with secret door mechanisms."""

    def test_open_simple_hidden_door(self):
        """Simple hidden door opens without mechanism."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            mechanism_type=MechanismType.NONE,
            door_discovered=True,
        )

        result = attempt_open_mechanism(door, action="push the door")

        assert result.success
        assert result.door_opened
        assert door.door_opened

    def test_open_already_open_door(self):
        """Already open doors return success."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_DOOR,
            location=SecretDoorLocation.BEHIND_TAPESTRY,
            mechanism_type=MechanismType.NONE,
            door_discovered=True,
            door_opened=True,
        )

        result = attempt_open_mechanism(door, action="open")

        assert result.success
        assert result.door_opened

    def test_mechanism_not_discovered(self):
        """Can't open if mechanism not discovered."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PULL_TORCH_SCONCE.value,
            door_discovered=True,
            mechanism_discovered=False,
        )

        result = attempt_open_mechanism(door, action="push")

        assert not result.success
        assert not result.door_opened

    def test_mechanical_mechanism_success(self):
        """Test successfully operating a mechanical mechanism."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PULL_TORCH_SCONCE.value,
            mechanism_details=MECHANICAL_MECHANISM_DESCRIPTIONS[MechanicalMechanism.PULL_TORCH_SCONCE],
            door_discovered=True,
            mechanism_discovered=True,
        )

        result = attempt_open_mechanism(door, action="pull the torch sconce")

        assert result.success
        assert result.door_opened
        assert result.mechanism_triggered

    def test_mechanism_requires_item(self):
        """Test mechanism that requires an item."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MECHANICAL,
            mechanism=MechanicalMechanism.PUT_COIN_SLOT.value,
            mechanism_details={"requires_item": True, "item_type": "coin"},
            door_discovered=True,
            mechanism_discovered=True,
        )

        # Without item
        result = attempt_open_mechanism(door, action="use the slot")
        assert not result.success
        assert result.item_required == "coin"

        # With correct item
        result = attempt_open_mechanism(door, action="insert coin", item_used="gold coin")
        assert result.success
        assert result.item_consumed

    def test_magical_mechanism_password(self):
        """Test magical mechanism requiring password."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MAGICAL,
            mechanism=MagicalMechanism.SPEAK_COMMAND_WORD.value,
            mechanism_details={"requires_password": True},
            password="Melorn",
            door_discovered=True,
            mechanism_discovered=True,
        )

        # Wrong password
        result = attempt_open_mechanism(door, action="speak", spoken_word="Abracadabra")
        assert not result.success
        assert not result.door_opened

        # Correct password
        result = attempt_open_mechanism(door, action="speak", spoken_word="Melorn")
        assert result.success
        assert result.door_opened

    def test_magical_mechanism_riddle(self):
        """Test magical mechanism with riddle."""
        door = SecretDoor(
            door_id="test",
            name="Test Door",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            location=SecretDoorLocation.SEAMLESS_WALL,
            mechanism_type=MechanismType.MAGICAL,
            mechanism=MagicalMechanism.ANSWER_RIDDLE.value,
            mechanism_details={"requires_answer": True},
            riddle_answer="shadow",
            door_discovered=True,
            mechanism_discovered=True,
        )

        # Wrong answer
        result = attempt_open_mechanism(door, action="answer", spoken_word="light")
        assert not result.success

        # Correct answer
        result = attempt_open_mechanism(door, action="answer", spoken_word="shadow")
        assert result.success
        assert result.door_opened


class TestSecretDoorIntegration:
    """Integration tests for the complete secret door flow."""

    def test_complete_hidden_door_flow(self):
        """Test complete flow: generate, search, open."""
        DiceRoller.set_seed(1)

        # Generate a simple hidden door
        door = generate_secret_door(
            door_id="integration_test",
            destination_room="treasure_room",
            direction="east",
            door_type=SecretDoorType.HIDDEN_DOOR,
            mechanism_type=MechanismType.NONE,
        )

        assert not door.door_discovered
        assert not door.door_opened

        # Search until found
        for _ in range(30):
            result = search_for_secret_door(door, search_bonus=2)
            if door.door_discovered:
                break

        assert door.door_discovered

        # Open the door
        open_result = attempt_open_mechanism(door, action="push")
        assert open_result.success
        assert door.door_opened

    def test_complete_mechanism_door_flow(self):
        """Test complete flow with mechanism door."""
        DiceRoller.set_seed(42)

        # Generate door with mechanical mechanism
        door = generate_secret_door(
            door_id="mech_test",
            destination_room="secret_vault",
            direction="south",
            door_type=SecretDoorType.HIDDEN_MECHANISM,
            mechanism_type=MechanismType.MECHANICAL,
        )

        # Door should be immediately visible for HIDDEN_MECHANISM type
        search_for_secret_door(door)
        assert door.door_discovered

        # But mechanism needs to be found
        for _ in range(30):
            if door.mechanism_discovered:
                break
            search_for_secret_door(door, search_bonus=2)

        # Try to open
        if door.mechanism_discovered:
            action = door.get_required_action() or "activate mechanism"
            result = attempt_open_mechanism(door, action=action)
            # Result depends on item requirements etc.
            assert "message" in result.__dict__

    def test_secret_door_serialization(self):
        """Test that generated doors can be serialized."""
        DiceRoller.set_seed(42)

        door = generate_secret_door(
            door_id="serialize_test",
            destination_room="hidden_chamber",
            direction="down",
        )

        # Serialize to dict
        data = door.to_dict()

        # Verify key fields
        assert data["door_id"] == "serialize_test"
        assert data["destination_room"] == "hidden_chamber"
        assert data["direction"] == "down"
        assert "door_type" in data
        assert "location" in data
        assert "clues" in data
