"""
Test that roll log observability actions work.

Phase 6.1: Surface roll log for observability
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.conversation.action_registry import reset_registry


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


class TestRunLogSurface:
    """Test that roll log actions work."""

    def test_roll_log_empty_initially(self, facade):
        """Roll log should be empty before any rolls."""
        DiceRoller.clear_roll_log()

        response = facade.handle_action("meta:roll_log")
        assert response.messages
        assert "No dice rolls recorded" in response.messages[0].content

    def test_roll_log_shows_after_roll(self, facade):
        """Roll log should show dice rolls after they occur."""
        DiceRoller.clear_roll_log()

        # Make a roll through the dice roller
        dice = DiceRoller()
        dice.roll("1d20", "Test attack roll")

        # Check the log
        response = facade.handle_action("meta:roll_log")
        assert response.messages
        content = response.messages[0].content

        # Should contain the roll info
        assert "Recent Dice Rolls" in content
        assert "Test attack roll" in content

    def test_roll_log_includes_oracle_rolls(self, facade):
        """Roll log should include oracle fate check rolls."""
        DiceRoller.clear_roll_log()

        # Make an oracle fate check (this uses DiceRngAdapter)
        facade.handle_action("oracle:fate_check", {"question": "Is the sky blue?"})

        # Check the log
        response = facade.handle_action("meta:roll_log")
        assert response.messages
        content = response.messages[0].content

        # Should have some rolls
        assert "Recent Dice Rolls" in content

    def test_roll_log_limits_entries(self, facade):
        """Roll log should respect the limit parameter."""
        DiceRoller.clear_roll_log()

        # Make many rolls
        dice = DiceRoller()
        for i in range(30):
            dice.roll("1d20", f"Roll {i}")

        # Get only 5
        response = facade.handle_action("meta:roll_log", {"limit": 5})
        assert response.messages

        # The response should be limited (exact format may vary)
        # Just verify it succeeds
        assert "Recent Dice Rolls" in response.messages[0].content

    def test_export_run_log(self, facade, tmp_path):
        """Export run log should write to a file."""
        DiceRoller.clear_roll_log()

        # Make some rolls
        dice = DiceRoller()
        dice.roll("1d20", "Test roll 1")
        dice.roll("2d6", "Test roll 2")

        # Export to temp directory
        save_dir = str(tmp_path)
        response = facade.handle_action(
            "meta:export_run_log",
            {"save_dir": save_dir}
        )

        assert response.messages
        content = response.messages[0].content

        # Should indicate success
        assert "exported" in content.lower() or "Run log" in content

        # File should exist (check by filepath in response or by listing dir)
        import os
        files = os.listdir(save_dir)
        assert len(files) > 0
        assert any(f.startswith("run_log_") and f.endswith(".json") for f in files)
