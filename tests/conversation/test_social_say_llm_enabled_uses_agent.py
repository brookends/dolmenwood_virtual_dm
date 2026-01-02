"""
Tests for social:say LLM-enabled mode using the DM agent.

Phase 3 (P1): Verify that social:say uses the real narrator pathway
when LLM is enabled, while still respecting Python-referee separation.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
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


class MockDescriptionResult:
    """Mock result from DmAgent."""
    def __init__(self, description: str):
        self.description = description
        self.warnings = []


@pytest.fixture
def mock_dm_agent():
    """Create a mock DM agent that records calls."""
    agent = MagicMock()
    agent.generate_simple_npc_dialogue = MagicMock(
        return_value=MockDescriptionResult("The old merchant strokes his beard thoughtfully.")
    )
    return agent


@pytest.fixture
def offline_dm(seeded_dice, test_character):
    """Create VirtualDM in offline mode (no LLM)."""
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


class TestSocialSayOfflineMode:
    """Test social:say behavior when LLM is disabled."""

    def test_offline_mode_gives_oracle_guidance(self, offline_dm):
        """In offline mode, social:say should direct user to oracle."""
        reset_registry()
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "What do you know about the ruins?"}
        )

        assert result["success"] is True
        assert "Offline mode" in result["message"]
        assert "oracle" in result["message"].lower()

    def test_offline_mode_echoes_player_text(self, offline_dm):
        """In offline mode, the player's text should be echoed."""
        reset_registry()
        registry = get_default_registry()

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "Greetings, friend!"}
        )

        assert result["success"] is True
        assert "Greetings, friend!" in result["message"]


class TestSocialSayLLMEnabled:
    """Test social:say when LLM/DM agent is available."""

    def test_llm_enabled_calls_dm_agent(self, offline_dm, mock_dm_agent):
        """When DM agent is available, social:say should call it."""
        reset_registry()
        registry = get_default_registry()

        # Inject mock agent
        offline_dm._dm_agent = mock_dm_agent

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "What do you know about the ruins?"}
        )

        # Agent should have been called exactly once
        assert mock_dm_agent.generate_simple_npc_dialogue.call_count == 1

        # Check the call arguments
        call_args = mock_dm_agent.generate_simple_npc_dialogue.call_args
        assert call_args.kwargs["topic"] == "What do you know about the ruins?"

    def test_llm_enabled_returns_narration(self, offline_dm, mock_dm_agent):
        """When DM agent is available, response should contain narration."""
        reset_registry()
        registry = get_default_registry()

        offline_dm._dm_agent = mock_dm_agent

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "Tell me about the forest."}
        )

        assert result["success"] is True
        # Should include the mock narration
        assert "beard" in result["message"] or "merchant" in result["message"]
        # Should also include what player said
        assert "Tell me about the forest" in result["message"]

    def test_llm_enabled_uses_social_context(self, offline_dm, mock_dm_agent):
        """DM agent should receive NPC context from social_context."""
        reset_registry()
        registry = get_default_registry()

        offline_dm._dm_agent = mock_dm_agent

        # Set up social context
        offline_dm.controller._social_context = {
            "npc_id": "bramble_01",
            "npc_name": "Old Bramble",
            "personality": "grumpy but wise forest hermit",
            "disposition": "wary",
        }

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "Can you help me?"}
        )

        # Check agent was called with context
        call_args = mock_dm_agent.generate_simple_npc_dialogue.call_args
        assert call_args.kwargs["npc_name"] == "Old Bramble"
        assert call_args.kwargs["personality"] == "grumpy but wise forest hermit"
        assert call_args.kwargs["disposition"] == "wary"

    def test_llm_error_falls_back_gracefully(self, offline_dm):
        """If DM agent raises error, should fall back to oracle guidance."""
        reset_registry()
        registry = get_default_registry()

        # Create agent that raises error
        failing_agent = MagicMock()
        failing_agent.generate_simple_npc_dialogue = MagicMock(
            side_effect=Exception("LLM connection failed")
        )
        offline_dm._dm_agent = failing_agent

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "Hello there!"}
        )

        # Should still succeed (graceful fallback)
        assert result["success"] is True
        # Should mention the error or oracle
        assert "oracle" in result["message"].lower() or "error" in result["message"].lower()

    def test_llm_empty_response_falls_back(self, offline_dm):
        """If DM agent returns empty, should fall back to oracle guidance."""
        reset_registry()
        registry = get_default_registry()

        # Create agent that returns empty result
        empty_agent = MagicMock()
        empty_agent.generate_simple_npc_dialogue = MagicMock(
            return_value=MockDescriptionResult("")
        )
        offline_dm._dm_agent = empty_agent

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "Any news?"}
        )

        assert result["success"] is True
        # Should mention oracle since narration is empty
        assert "oracle" in result["message"].lower()


class TestPythonRefereeSeparation:
    """Verify that LLM cannot introduce mechanical changes."""

    def test_controller_state_not_mutated_by_llm(self, offline_dm, mock_dm_agent):
        """Calling social:say should not mutate controller state unexpectedly."""
        reset_registry()
        registry = get_default_registry()

        offline_dm._dm_agent = mock_dm_agent

        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        # Capture state before
        party_state_before = offline_dm.controller.party_state
        resources_before = (
            party_state_before.resources.food_days,
            party_state_before.resources.torches,
        )

        result = registry.execute(
            offline_dm,
            "social:say",
            {"text": "I'll trade you some food for that information!"}
        )

        # State should not have changed
        party_state_after = offline_dm.controller.party_state
        resources_after = (
            party_state_after.resources.food_days,
            party_state_after.resources.torches,
        )

        assert resources_before == resources_after
        # Game state should still be social interaction
        assert offline_dm.current_state == GameState.SOCIAL_INTERACTION
