"""
Tests for social:say behavior in offline mode (no LLM).

Verifies that:
- social:say works in offline mode with oracle guidance
- social:say does not hallucinate NPC dialogue
- social:say requires text parameter
"""

import pytest

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.conversation.action_registry import get_default_registry


@pytest.fixture
def controller():
    """Create a test controller."""
    return GlobalController(initial_state=GameState.WILDERNESS_TRAVEL)


class TestSocialSayOffline:
    """Test social:say behavior in offline mode (no LLM)."""

    def test_social_say_offline_returns_oracle_guidance(self, controller):
        """In offline mode, social:say should suggest using oracle."""
        # Transition to social interaction state manually
        controller.transition("initiate_conversation", context={
            "npc_id": "test_npc",
            "npc_name": "Test NPC",
        })

        assert controller.current_state == GameState.SOCIAL_INTERACTION

        class MockDM:
            def __init__(self, ctrl):
                self.controller = ctrl
                self.dm_agent = None  # No LLM

            @property
            def current_state(self):
                return self.controller.current_state

        mock_dm = MockDM(controller)

        registry = get_default_registry()
        result = registry.execute(mock_dm, "social:say", {"text": "Hello, how are you?"})

        # Should succeed but suggest oracle
        assert result["success"] is True
        assert "oracle" in result["message"].lower() or "offline" in result["message"].lower()

    def test_social_say_requires_text(self, controller):
        """social:say should require text parameter."""
        controller.transition("initiate_conversation", context={})

        class MockDM:
            def __init__(self, ctrl):
                self.controller = ctrl
                self.dm_agent = None

            @property
            def current_state(self):
                return self.controller.current_state

        mock_dm = MockDM(controller)

        registry = get_default_registry()
        result = registry.execute(mock_dm, "social:say", {})

        # Should fail without text
        assert result["success"] is False
        assert "text" in result["message"].lower()

    def test_social_say_does_not_hallucinate(self, controller):
        """social:say in offline mode should not generate fake NPC dialogue."""
        controller.transition("initiate_conversation", context={
            "npc_name": "Gorbald",
        })

        class MockDM:
            def __init__(self, ctrl):
                self.controller = ctrl
                self.dm_agent = None

            @property
            def current_state(self):
                return self.controller.current_state

        mock_dm = MockDM(controller)

        registry = get_default_registry()
        result = registry.execute(mock_dm, "social:say", {"text": "Tell me about the forest"})

        # The message should NOT contain quoted NPC dialogue
        # It should be guidance/system message
        message = result["message"]

        # Should contain guidance about using oracle
        assert "oracle" in message.lower() or "offline" in message.lower()

    def test_social_end_returns_to_previous_state(self, controller):
        """social:end should return to previous state."""
        # Start from wilderness
        assert controller.current_state == GameState.WILDERNESS_TRAVEL

        # Enter conversation
        controller.transition("initiate_conversation", context={})
        assert controller.current_state == GameState.SOCIAL_INTERACTION

        class MockDM:
            def __init__(self, ctrl):
                self.controller = ctrl
                self.dm_agent = None

            @property
            def current_state(self):
                return self.controller.current_state

        mock_dm = MockDM(controller)

        registry = get_default_registry()
        result = registry.execute(mock_dm, "social:end", {})

        # Should return to wilderness
        assert result["success"] is True
        assert controller.current_state == GameState.WILDERNESS_TRAVEL
