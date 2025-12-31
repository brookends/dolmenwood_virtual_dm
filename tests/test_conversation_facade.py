"""
Tests for ConversationFacade - the chat-first orchestration layer.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.conversation.types import TurnResponse, ChatMessage, SuggestedAction
from src.game_state.state_machine import GameState
from src.data_models import GameDate, GameTime


class MockLocation:
    """Mock location for testing."""
    def __init__(self, location_id="0709", location_type="wilderness"):
        self.location_id = location_id
        self.location_type = location_type

    def __str__(self):
        return f"{self.location_id} ({self.location_type})"


class MockResources:
    """Mock party resources."""
    def __init__(self):
        self.food_days = 10
        self.water_days = 10
        self.torches = 6
        self.lantern_oil_flasks = 4


class MockWorldState:
    """Mock world state for testing."""
    def __init__(self):
        self.current_date = GameDate(year=1, month=6, day=15)
        self.current_time = GameTime(hour=10, minute=0)


class MockPartyState:
    """Mock party state for testing."""
    def __init__(self):
        self.location = MockLocation()
        self.active_light_source = "torch"
        self.light_remaining_turns = 6
        self.resources = MockResources()


class MockCharacter:
    """Mock character for testing."""
    def __init__(self, character_id="fighter_1", name="Test Fighter"):
        self.character_id = character_id
        self.name = name


class MockController:
    """Mock controller for testing."""
    def __init__(self):
        self.party_state = MockPartyState()
        self.world_state = MockWorldState()
        self._characters = [MockCharacter()]

    def get_active_characters(self):
        return self._characters

    def get_all_characters(self):
        return self._characters

    def transition(self, trigger, context=None):
        pass


class MockResolverResult:
    """Mock result from narrative resolver."""
    def __init__(self, narration="Action resolved."):
        self.narration = narration
        self.apply_damage = []
        self.apply_conditions = []


class MockDungeonTurnResult:
    """Mock result from dungeon execute_turn."""
    def __init__(self):
        self.messages = ["Searched the room."]
        self.warnings = []
        self.action_result = {"message": "Found nothing."}


class MockVirtualDM:
    """Mock VirtualDM for testing."""
    def __init__(self, state=GameState.WILDERNESS_TRAVEL):
        self.current_state = state
        self.controller = MockController()
        self.dm_agent = None  # No LLM agent in tests

        # Set up hex_crawl mock
        self.hex_crawl = MagicMock()
        self.hex_crawl.handle_player_action = MagicMock(return_value=MockResolverResult())

        # Set up dungeon mock
        self.dungeon = MagicMock()
        self.dungeon.search_room = MagicMock(return_value={"found": [], "time_spent": 1})
        self.dungeon.handle_player_action = MagicMock(return_value=MockResolverResult())
        self.dungeon.execute_turn = MagicMock(return_value=MockDungeonTurnResult())

        # Set up encounter mock
        self.encounter = MagicMock()
        self.encounter.handle_parley = MagicMock(return_value={"success": True})
        self.encounter.attempt_flee = MagicMock(return_value={"success": True})

        # Set up settlement mock
        self.settlement = MagicMock()
        self.settlement.handle_player_action = MagicMock(return_value=MockResolverResult())

        # Set up downtime mock
        self.downtime = MagicMock()
        self.downtime.handle_player_action = MagicMock(return_value=MockResolverResult())

        # Mock travel_to_hex as MagicMock
        self.travel_to_hex = MagicMock(return_value={"success": True, "new_hex": "0710"})

    def get_valid_actions(self):
        return []

    def get_full_state(self):
        return {"state": "test", "location": "0709"}


class TestConversationConfig:
    """Tests for ConversationConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConversationConfig()
        assert config.include_state_snapshot is True
        assert config.include_events is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ConversationConfig(
            include_state_snapshot=False,
            include_events=False
        )
        assert config.include_state_snapshot is False
        assert config.include_events is False


class TestConversationFacade:
    """Tests for ConversationFacade."""

    def test_initialization(self):
        """Test facade initializes correctly."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        assert facade.dm is dm
        assert facade.config is not None
        assert facade.mythic is not None

    def test_initialization_with_custom_config(self):
        """Test facade initializes with custom config."""
        dm = MockVirtualDM()
        config = ConversationConfig(include_events=False)
        facade = ConversationFacade(dm, config=config)

        assert facade.config.include_events is False
        assert facade.events is None

    def test_handle_chat_empty_text(self):
        """Test handle_chat with empty text."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_chat("")
        assert isinstance(turn, TurnResponse)
        # Should return a response with suggestions
        assert isinstance(turn.suggested_actions, list)

    def test_handle_chat_whitespace_only(self):
        """Test handle_chat with whitespace-only text."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_chat("   \n\t  ")
        assert isinstance(turn, TurnResponse)

    def test_handle_chat_wilderness_with_hex_id(self):
        """Test that chat with hex ID in wilderness triggers travel."""
        dm = MockVirtualDM(state=GameState.WILDERNESS_TRAVEL)

        facade = ConversationFacade(dm)
        turn = facade.handle_chat("I want to travel to 0710")

        # Should have attempted to handle the travel action
        assert isinstance(turn, TurnResponse)
        dm.travel_to_hex.assert_called()

    def test_handle_chat_dungeon_search_keyword(self):
        """Test that 'search' keyword in dungeon triggers search action."""
        dm = MockVirtualDM(state=GameState.DUNGEON_EXPLORATION)

        facade = ConversationFacade(dm)
        turn = facade.handle_chat("search")

        assert isinstance(turn, TurnResponse)

    def test_handle_chat_dungeon_rest_keyword(self):
        """Test that 'rest' keyword in dungeon triggers rest action."""
        dm = MockVirtualDM(state=GameState.DUNGEON_EXPLORATION)

        facade = ConversationFacade(dm)
        turn = facade.handle_chat("rest")

        assert isinstance(turn, TurnResponse)

    def test_handle_chat_dungeon_map_keyword(self):
        """Test that 'map' keyword in dungeon triggers map action."""
        dm = MockVirtualDM(state=GameState.DUNGEON_EXPLORATION)

        facade = ConversationFacade(dm)
        turn = facade.handle_chat("map")

        assert isinstance(turn, TurnResponse)

    def test_handle_action_meta_status(self):
        """Test handling meta:status action."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("meta:status")

        assert isinstance(turn, TurnResponse)
        assert len(turn.messages) > 0
        # Should contain status information
        assert turn.messages[0].role == "system"

    def test_handle_action_transition(self):
        """Test handling transition actions."""
        dm = MockVirtualDM()

        facade = ConversationFacade(dm)
        turn = facade.handle_action("transition:enter_dungeon")

        assert isinstance(turn, TurnResponse)

    def test_handle_action_oracle_fate_check(self):
        """Test handling oracle:fate_check action."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:fate_check", {"question": "Is the door locked?"})

        assert isinstance(turn, TurnResponse)
        # Should have a message with the oracle result
        assert len(turn.messages) > 0

    def test_handle_action_oracle_random_event(self):
        """Test handling oracle:random_event action."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:random_event")

        assert isinstance(turn, TurnResponse)
        assert len(turn.messages) > 0

    def test_handle_action_oracle_detail_check(self):
        """Test handling oracle:detail_check action."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:detail_check")

        assert isinstance(turn, TurnResponse)
        assert len(turn.messages) > 0

    def test_handle_action_unknown_action(self):
        """Test handling unknown action ID."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("unknown:action")

        assert isinstance(turn, TurnResponse)
        # Should return with suggestions

    def test_response_includes_suggestions(self):
        """Test that responses include suggested actions."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("meta:status")

        assert isinstance(turn.suggested_actions, list)
        assert len(turn.suggested_actions) > 0

    def test_response_includes_state_snapshot(self):
        """Test that responses include state snapshot when configured."""
        dm = MockVirtualDM()
        config = ConversationConfig(include_state_snapshot=True)
        facade = ConversationFacade(dm, config=config)

        turn = facade.handle_action("meta:status")

        assert isinstance(turn.public_state, dict)


class TestWildernessActions:
    """Tests for wilderness-specific actions."""

    def test_wilderness_travel_action(self):
        """Test wilderness:travel action."""
        dm = MockVirtualDM(state=GameState.WILDERNESS_TRAVEL)

        facade = ConversationFacade(dm)
        turn = facade.handle_action("wilderness:travel", {"hex_id": "0710"})

        assert isinstance(turn, TurnResponse)
        dm.travel_to_hex.assert_called_once_with("0710")

    def test_wilderness_look_around_action(self):
        """Test wilderness:look_around action."""
        dm = MockVirtualDM(state=GameState.WILDERNESS_TRAVEL)

        facade = ConversationFacade(dm)
        turn = facade.handle_action("wilderness:look_around")

        assert isinstance(turn, TurnResponse)


class TestDungeonActions:
    """Tests for dungeon-specific actions."""

    def test_dungeon_search_action(self):
        """Test dungeon:search action."""
        dm = MockVirtualDM(state=GameState.DUNGEON_EXPLORATION)

        facade = ConversationFacade(dm)
        turn = facade.handle_action("dungeon:search")

        assert isinstance(turn, TurnResponse)


class TestEncounterActions:
    """Tests for encounter-specific actions."""

    def test_encounter_parley_action(self):
        """Test encounter:parley action."""
        dm = MockVirtualDM(state=GameState.ENCOUNTER)

        facade = ConversationFacade(dm)
        turn = facade.handle_action("encounter:parley")

        assert isinstance(turn, TurnResponse)

    def test_encounter_flee_action(self):
        """Test encounter:flee action."""
        dm = MockVirtualDM(state=GameState.ENCOUNTER)

        facade = ConversationFacade(dm)
        turn = facade.handle_action("encounter:flee")

        assert isinstance(turn, TurnResponse)


class TestOracleActions:
    """Tests for Mythic GME oracle actions."""

    def test_fate_check_with_likelihood(self):
        """Test fate check with explicit likelihood."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:fate_check", {
            "question": "Is the guard asleep?",
            "likelihood": "likely"
        })

        assert isinstance(turn, TurnResponse)
        # Should have an oracle result message
        assert len(turn.messages) > 0
        assert turn.messages[0].role == "system"

    def test_fate_check_default_likelihood(self):
        """Test fate check with default (50/50) likelihood."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:fate_check", {
            "question": "Does the door open?"
        })

        assert isinstance(turn, TurnResponse)
        assert len(turn.messages) > 0

    def test_random_event_generation(self):
        """Test random event generation."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:random_event")

        assert isinstance(turn, TurnResponse)
        # Should generate some event description
        assert len(turn.messages) > 0
        assert "Random Event" in turn.messages[0].content

    def test_detail_check(self):
        """Test detail check (action/subject word pair)."""
        dm = MockVirtualDM()
        facade = ConversationFacade(dm)

        turn = facade.handle_action("oracle:detail_check")

        assert isinstance(turn, TurnResponse)
        # Should contain action/subject words
        assert len(turn.messages) > 0
        assert "Detail Check" in turn.messages[0].content
