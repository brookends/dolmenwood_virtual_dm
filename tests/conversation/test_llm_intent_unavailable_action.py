"""
Tests for P1-8: Don't silently ignore unknown LLM-proposed action IDs.

Verifies that when the LLM suggests an action with high confidence that
isn't in the available_actions list, the user gets explicit feedback
instead of silent failure.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.ai.prompt_schemas import IntentParseOutput


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def test_character():
    """A sample character for testing."""
    return CharacterState(
        character_id="test_fighter_1",
        name="Test Fighter",
        character_class="Fighter",
        level=3,
        ability_scores={
            "STR": 16,
            "INT": 10,
            "WIS": 12,
            "DEX": 14,
            "CON": 15,
            "CHA": 11,
        },
        hp_current=24,
        hp_max=24,
        armor_class=4,
        base_speed=30,
    )


@pytest.fixture
def dm_with_mock_agent(seeded_dice, test_character):
    """Create VirtualDM with a mock DM agent that returns controlled intents."""
    config = GameConfig(
        llm_provider="mock",
        enable_narration=True,
        load_content=False,
    )

    dm = VirtualDM(
        config=config,
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=10, minute=0),
    )

    dm.controller.add_character(test_character)
    return dm


@pytest.fixture
def facade_with_llm(dm_with_mock_agent):
    """Create ConversationFacade with LLM intent parsing enabled."""
    config = ConversationConfig(
        use_llm_intent_parsing=True,
        use_oracle_enhancement=False,
        llm_confidence_threshold=0.7,
    )
    return ConversationFacade(dm_with_mock_agent, config=config)


# =============================================================================
# TESTS: Unavailable Action Feedback
# =============================================================================


class TestUnavailableActionFeedback:
    """Test that unavailable LLM-suggested actions get explicit feedback."""

    def test_returns_error_for_unavailable_high_confidence_action(
        self, dm_with_mock_agent, facade_with_llm
    ):
        """
        When LLM returns high-confidence action not in available_actions,
        user should get explicit error message.
        """
        # Create a mock intent result with an unavailable action
        mock_intent = IntentParseOutput(
            action_id="combat:cast_fireball",  # Action not available in WILDERNESS_TRAVEL
            params={"target": "enemy"},
            confidence=0.95,  # High confidence
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Player seems to want to cast fireball",
        )

        # Mock the dm_agent.parse_intent
        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        # Make a request that would trigger LLM intent parsing
        response = facade_with_llm.handle_chat("I cast fireball at the enemies")

        # Should return a response with explicit error message
        assert response.messages, "Should have response messages"
        content = response.messages[0].content.lower()

        # Should mention the action
        assert "combat:cast_fireball" in content or "cast_fireball" in content
        # Should indicate it's not available
        assert "available" in content or "right now" in content

    def test_unavailable_action_sets_requires_clarification(
        self, dm_with_mock_agent, facade_with_llm
    ):
        """Response should have requires_clarification set."""
        mock_intent = IntentParseOutput(
            action_id="dungeon:disarm_trap",  # Not available in wilderness
            params={},
            confidence=0.9,
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Player wants to disarm trap",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        response = facade_with_llm.handle_chat("I disarm the trap")

        # Should set requires_clarification to True
        assert response.requires_clarification is True

    def test_unavailable_action_has_clarification_prompt(
        self, dm_with_mock_agent, facade_with_llm
    ):
        """Response should have a helpful clarification prompt."""
        mock_intent = IntentParseOutput(
            action_id="settlement:buy_item",  # Not available in wilderness
            params={"item": "sword"},
            confidence=0.85,
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Player wants to buy a sword",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        response = facade_with_llm.handle_chat("I want to buy a sword")

        # Should have clarification_prompt
        assert response.clarification_prompt is not None
        assert len(response.clarification_prompt) > 0
        # Prompt should mention the action or availability
        assert "settlement:buy_item" in response.clarification_prompt or "available" in response.clarification_prompt.lower()


class TestAvailableActionsStillWork:
    """Test that available actions still execute normally."""

    def test_available_action_executes(self, dm_with_mock_agent, facade_with_llm):
        """Available action should execute, not return error."""
        # Get an action that's actually available
        from src.conversation.suggestion_builder import build_suggestions
        suggestions = build_suggestions(dm_with_mock_agent, limit=5)
        if not suggestions:
            pytest.skip("No suggestions available in current state")

        available_action = suggestions[0].id

        mock_intent = IntentParseOutput(
            action_id=available_action,
            params={},
            confidence=0.9,
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Player wants to execute action",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        response = facade_with_llm.handle_chat("do the action")

        # Should NOT have unavailable action error
        content = response.messages[0].content.lower() if response.messages else ""
        assert "isn't available right now" not in content


class TestUnknownActionId:
    """Test handling of 'unknown' action ID."""

    def test_unknown_action_falls_through(self, dm_with_mock_agent, facade_with_llm):
        """When action_id is 'unknown', should fall through to pattern matching."""
        mock_intent = IntentParseOutput(
            action_id="unknown",
            params={},
            confidence=0.95,  # High confidence but unknown
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Couldn't determine action",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        response = facade_with_llm.handle_chat("random gibberish")

        # Should NOT show the unavailable action error
        content = response.messages[0].content.lower() if response.messages else ""
        assert "isn't available right now" not in content


class TestLowConfidenceActions:
    """Test that low confidence actions don't trigger the unavailable message."""

    def test_low_confidence_unavailable_falls_through(
        self, dm_with_mock_agent, facade_with_llm
    ):
        """Low confidence unavailable action should fall through, not error."""
        mock_intent = IntentParseOutput(
            action_id="combat:cast_fireball",  # Not available
            params={},
            confidence=0.3,  # Low confidence - below threshold
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Uncertain parse",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        response = facade_with_llm.handle_chat("maybe cast something?")

        # Should NOT show the unavailable action error (low confidence)
        content = response.messages[0].content.lower() if response.messages else ""
        assert "combat:cast_fireball" not in content or "isn't available" not in content


class TestEdgeCases:
    """Test edge cases for unavailable action handling."""

    def test_handles_empty_action_id(self, dm_with_mock_agent, facade_with_llm):
        """Empty action_id should not crash."""
        mock_intent = IntentParseOutput(
            action_id="",  # Empty
            params={},
            confidence=0.9,
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Empty action",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        # Should not raise
        response = facade_with_llm.handle_chat("do something")
        assert response is not None

    def test_handles_whitespace_action_id(self, dm_with_mock_agent, facade_with_llm):
        """Whitespace-only action_id should not crash."""
        mock_intent = IntentParseOutput(
            action_id="   ",  # Whitespace
            params={},
            confidence=0.9,
            requires_clarification=False,
            clarification_prompt="",
            reasoning="Whitespace action",
        )

        dm_with_mock_agent._dm_agent.parse_intent = MagicMock(return_value=mock_intent)

        # Should not raise
        response = facade_with_llm.handle_chat("do something")
        assert response is not None
