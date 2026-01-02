"""
Tests for freeform text routing to social:say in SOCIAL_INTERACTION state.

Phase 2 (P1): Ensure typing freeform text during social interaction
behaves like speaking (routes to social:say), not "unsupported".
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.conversation_facade import ConversationFacade, ConversationConfig


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
            "STR": 16, "INT": 10, "WIS": 12,
            "DEX": 14, "CON": 15, "CHA": 11,
        },
        hp_current=24,
        hp_max=24,
        armor_class=4,
        base_speed=30,
    )


@pytest.fixture
def offline_dm(seeded_dice, test_character):
    """Create VirtualDM in offline mode."""
    from src.conversation.action_registry import reset_registry
    reset_registry()

    config = GameConfig(
        llm_provider="mock",
        enable_narration=False,
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
def facade(offline_dm):
    """Create ConversationFacade with LLM features disabled."""
    config = ConversationConfig(
        use_llm_intent_parsing=False,
        use_oracle_enhancement=False,
    )
    return ConversationFacade(offline_dm, config=config)


class TestSocialFreeformRouting:
    """Test that freeform text in SOCIAL_INTERACTION routes to social:say."""

    def test_freeform_does_not_return_unsupported_error(self, facade, offline_dm):
        """Freeform text should not return 'unsupported' in SOCIAL_INTERACTION."""
        # Enter social interaction state
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_chat("Hello, stranger.")

        assert response.messages
        content = response.messages[0].content.lower()

        # Should NOT contain the unsupported message
        assert "unsupported" not in content
        assert "not supported" not in content

    def test_freeform_routes_to_social_say(self, facade, offline_dm):
        """Freeform text should behave like social:say."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        # Call via freeform chat
        freeform_response = facade.handle_chat("What do you know about the ruins?")

        assert freeform_response.messages
        # The response should look like social:say output
        # In offline mode, it tells user to use oracle
        content = freeform_response.messages[0].content
        assert "oracle" in content.lower() or "say" in content.lower() or "ruins" in content.lower()

    def test_freeform_includes_player_text(self, facade, offline_dm):
        """The response should echo/reference the player's text."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_chat("Tell me about the fairy roads")

        assert response.messages
        content = response.messages[0].content

        # Should reference what was said
        assert "fairy" in content.lower() or "say" in content.lower()

    def test_freeform_is_successful(self, facade, offline_dm):
        """Freeform input should succeed, not error."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_chat("Greetings, friend!")

        assert response.messages
        # Should not be an error message
        content = response.messages[0].content.lower()
        assert "error" not in content
        assert "failed" not in content

    def test_freeform_returns_suggestions(self, facade, offline_dm):
        """Freeform in social should still return suggested actions."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_chat("How's the weather?")

        assert response.suggested_actions is not None
        # Should have social-relevant suggestions
        action_ids = [a.id for a in response.suggested_actions]
        assert any(a.startswith("social:") or a.startswith("oracle:") for a in action_ids)


class TestOtherStatesFreeformBehavior:
    """Verify other states still work correctly after adding social routing."""

    def test_wilderness_freeform_still_works(self, facade, offline_dm):
        """Wilderness freeform should still work via hex_crawl."""
        assert offline_dm.current_state == GameState.WILDERNESS_TRAVEL

        response = facade.handle_chat("Look around")

        assert response.messages
        # Should not be unsupported
        content = response.messages[0].content.lower()
        assert "unsupported" not in content

    def test_combat_freeform_still_requires_action(self, facade, offline_dm):
        """Combat should still require selecting an action."""
        offline_dm.controller.state_machine.force_state(
            GameState.COMBAT,
            reason="test setup"
        )

        response = facade.handle_chat("I attack the goblin!")

        assert response.messages
        content = response.messages[0].content.lower()
        # Combat should indicate action selection is needed
        assert "action" in content or "option" in content
