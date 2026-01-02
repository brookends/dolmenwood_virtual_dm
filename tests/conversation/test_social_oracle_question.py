"""
Tests for social:oracle_question action.

Phase 1 (P0): Ensure social:oracle_question doesn't crash and produces
deterministic oracle results in offline mode.
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.conversation.action_registry import get_default_registry, reset_registry


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


class TestSocialOracleQuestion:
    """Test social:oracle_question action."""

    def test_oracle_question_does_not_crash(self, facade, offline_dm):
        """Calling social:oracle_question should not raise exceptions."""
        # Enter SOCIAL_INTERACTION state
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        # Should not crash
        response = facade.handle_action(
            "social:oracle_question",
            {"question": "Does the NPC trust me?"}
        )

        assert response is not None
        assert hasattr(response, 'messages')
        assert len(response.messages) > 0

    def test_oracle_question_returns_structured_result(self, facade, offline_dm):
        """social:oracle_question should return a structured oracle answer."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_action(
            "social:oracle_question",
            {"question": "Does the NPC trust me?"}
        )

        assert response.messages
        content = response.messages[0].content

        # Should contain oracle result indicators
        assert "Oracle" in content
        # Should contain the question or reference to it
        assert "trust" in content.lower() or "npc" in content.lower()
        # Should have a roll result
        assert "Roll:" in content or "roll" in content.lower()

    def test_oracle_question_deterministic_with_seed(self, offline_dm):
        """Oracle results should be deterministic with seeded RNG."""
        reset_registry()
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        # First call with seed 42
        DiceRoller.set_seed(42)
        result1 = registry.execute(
            offline_dm,
            "social:oracle_question",
            {"question": "Does the NPC like me?"}
        )

        # Reset and call again with same seed
        DiceRoller.set_seed(42)
        result2 = registry.execute(
            offline_dm,
            "social:oracle_question",
            {"question": "Does the NPC like me?"}
        )

        # Results should be identical
        assert result1["result"]["roll"] == result2["result"]["roll"]
        assert result1["result"]["answer"] == result2["result"]["answer"]

    def test_oracle_question_with_likelihood(self, facade, offline_dm):
        """Oracle question should accept likelihood/odds parameter."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_action(
            "social:oracle_question",
            {"question": "Is the NPC hostile?", "likelihood": "unlikely"}
        )

        assert response.messages
        content = response.messages[0].content
        assert "Oracle" in content

    def test_oracle_question_with_empty_question_uses_default(self, facade, offline_dm):
        """Empty question should use default question."""
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        response = facade.handle_action(
            "social:oracle_question",
            {"question": ""}
        )

        assert response.messages
        content = response.messages[0].content
        assert "Oracle" in content
        # Should use default question about NPC reaction
        assert "react" in content.lower() or "npc" in content.lower()

    def test_oracle_question_with_npc_context(self, offline_dm):
        """Oracle question should include NPC context when available."""
        from src.data_models import SocialContext, SocialParticipant, SocialParticipantType

        reset_registry()
        registry = get_default_registry()

        # Set up social context with proper dataclass structure
        participant = SocialParticipant(
            participant_id="test_npc",
            name="Old Bramble",
            participant_type=SocialParticipantType.NPC,
        )
        social_ctx = SocialContext(participants=[participant])
        offline_dm.controller.set_social_context(social_ctx)

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:oracle_question",
            {"question": "Does the NPC help me?"}
        )

        assert result["success"] is True
        # NPC name should be mentioned in the question context
        assert "Bramble" in result["message"]

    def test_oracle_question_logs_to_roll_log(self, offline_dm):
        """Oracle question should log the roll."""
        reset_registry()
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        # Clear any previous rolls
        DiceRoller.clear_roll_log()

        result = registry.execute(
            offline_dm,
            "social:oracle_question",
            {"question": "Does the NPC trust me?"}
        )

        assert result["success"] is True

        # Check that a roll was logged
        roll_log = DiceRoller.get_roll_log()
        # The oracle uses dice internally
        assert len(roll_log) > 0


class TestSocialOracleQuestionViaRegistry:
    """Test social:oracle_question directly via registry."""

    def test_registry_execute_oracle_question(self, offline_dm):
        """Direct registry execution should work."""
        reset_registry()
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:oracle_question",
            {"question": "Is the merchant friendly?"}
        )

        assert result["success"] is True
        assert "message" in result
        assert "result" in result
        assert "answer" in result["result"]
        assert "roll" in result["result"]

    def test_registry_oracle_question_has_valid_spec(self):
        """social:oracle_question should be properly registered."""
        reset_registry()
        registry = get_default_registry()

        spec = registry.get("social:oracle_question")
        assert spec is not None
        assert spec.executor is not None
        assert spec.category.value == "social"
