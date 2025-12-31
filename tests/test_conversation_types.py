"""
Tests for conversation types: ChatMessage, SuggestedAction, TurnResponse.
"""

import pytest
from src.conversation.types import ChatMessage, SuggestedAction, TurnResponse


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_create_player_message(self):
        """Test creating a player message."""
        msg = ChatMessage(role="player", content="I look around the room")
        assert msg.role == "player"
        assert msg.content == "I look around the room"

    def test_create_dm_message(self):
        """Test creating a DM message."""
        msg = ChatMessage(role="dm", content="You see a dark corridor stretching ahead")
        assert msg.role == "dm"
        assert msg.content == "You see a dark corridor stretching ahead"

    def test_create_system_message(self):
        """Test creating a system message."""
        msg = ChatMessage(role="system", content="Combat has ended")
        assert msg.role == "system"
        assert msg.content == "Combat has ended"


class TestSuggestedAction:
    """Tests for SuggestedAction dataclass."""

    def test_create_basic_action(self):
        """Test creating a basic action with minimal params."""
        action = SuggestedAction(
            id="wilderness:travel",
            label="Travel to hex 0709"
        )
        assert action.id == "wilderness:travel"
        assert action.label == "Travel to hex 0709"
        assert action.params_schema == {}
        assert action.params == {}
        assert action.safe_to_execute is True
        assert action.help is None

    def test_create_action_with_params(self):
        """Test creating an action with params."""
        action = SuggestedAction(
            id="wilderness:travel",
            label="Travel to The Whispering Glade",
            params={"hex_id": "0709"},
            params_schema={"hex_id": {"type": "string"}}
        )
        assert action.params == {"hex_id": "0709"}
        assert action.params_schema == {"hex_id": {"type": "string"}}

    def test_unsafe_action(self):
        """Test creating an unsafe action."""
        action = SuggestedAction(
            id="combat:attack",
            label="Attack the dragon",
            safe_to_execute=False,
            help="This will start combat with a very dangerous foe"
        )
        assert action.safe_to_execute is False
        assert action.help == "This will start combat with a very dangerous foe"


class TestTurnResponse:
    """Tests for TurnResponse dataclass."""

    def test_empty_response(self):
        """Test creating an empty response."""
        turn = TurnResponse()
        assert turn.messages == []
        assert turn.suggested_actions == []
        assert turn.public_state == {}
        assert turn.events == []
        assert turn.requires_clarification is False
        assert turn.clarification_prompt is None

    def test_response_with_messages(self):
        """Test creating a response with messages."""
        messages = [
            ChatMessage(role="player", content="I attack the goblin"),
            ChatMessage(role="dm", content="Your sword strikes true!"),
        ]
        turn = TurnResponse(messages=messages)
        assert len(turn.messages) == 2
        assert turn.messages[0].role == "player"
        assert turn.messages[1].role == "dm"

    def test_response_with_suggestions(self):
        """Test creating a response with suggested actions."""
        actions = [
            SuggestedAction(id="combat:attack", label="Attack again"),
            SuggestedAction(id="combat:defend", label="Defend"),
        ]
        turn = TurnResponse(suggested_actions=actions)
        assert len(turn.suggested_actions) == 2
        assert turn.suggested_actions[0].id == "combat:attack"

    def test_response_requiring_clarification(self):
        """Test creating a response that requires clarification."""
        turn = TurnResponse(
            requires_clarification=True,
            clarification_prompt="Which direction do you want to travel?"
        )
        assert turn.requires_clarification is True
        assert turn.clarification_prompt == "Which direction do you want to travel?"

    def test_to_dict(self):
        """Test serializing a TurnResponse to dict."""
        turn = TurnResponse(
            messages=[ChatMessage(role="dm", content="Welcome, adventurer!")],
            suggested_actions=[
                SuggestedAction(id="meta:status", label="Check status")
            ],
            public_state={"location": "forest"},
            requires_clarification=True,
            clarification_prompt="What do you do?",
        )
        d = turn.to_dict()

        assert len(d["messages"]) == 1
        assert d["messages"][0]["role"] == "dm"
        assert d["messages"][0]["content"] == "Welcome, adventurer!"

        assert len(d["suggested_actions"]) == 1
        assert d["suggested_actions"][0]["id"] == "meta:status"
        assert d["suggested_actions"][0]["safe_to_execute"] is True

        assert d["public_state"] == {"location": "forest"}
        assert d["requires_clarification"] is True
        assert d["clarification_prompt"] == "What do you do?"
