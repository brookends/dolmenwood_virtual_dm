"""
Tests for unknown action error handling.

Phase 4: Verify that unknown action IDs produce clear error messages
and don't crash or silently ignore the request.
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


class TestUnknownActionErrors:
    """Test that unknown actions produce clear error messages."""

    def test_nonexistent_action_returns_error_message(self, facade):
        """Calling a nonexistent action returns a clear error."""
        response = facade.handle_action("nonexistent:action", {})

        assert response.messages, "Should have messages"
        content = response.messages[0].content.lower()

        # Should contain error indication
        assert any(word in content for word in ["unknown", "unrecognized", "no executor"]), (
            f"Expected error message but got: {response.messages[0].content}"
        )

    def test_typo_in_action_id_returns_error(self, facade):
        """A typo in action ID returns an error, not silent ignore."""
        response = facade.handle_action("meta:statuss", {})  # Extra 's'

        assert response.messages
        content = response.messages[0].content.lower()
        assert any(word in content for word in ["unknown", "unrecognized"]), (
            f"Expected error for typo but got: {response.messages[0].content}"
        )

    def test_invalid_category_returns_error(self, facade):
        """Invalid action category returns an error."""
        response = facade.handle_action("invalid_category:do_something", {})

        assert response.messages
        content = response.messages[0].content.lower()
        assert any(word in content for word in ["unknown", "unrecognized"]), (
            f"Expected error for invalid category but got: {response.messages[0].content}"
        )

    def test_empty_action_id_returns_error(self, facade):
        """Empty action ID returns an error."""
        response = facade.handle_action("", {})

        assert response.messages
        # Should indicate something is wrong
        content = response.messages[0].content.lower()
        assert any(word in content for word in ["unknown", "unrecognized", "empty", "invalid"]), (
            f"Expected error for empty action but got: {response.messages[0].content}"
        )

    def test_unknown_action_does_not_crash(self, facade):
        """Unknown action IDs should not raise exceptions."""
        # These should all return gracefully, not crash
        test_ids = [
            "nonexistent:action",
            "meta:undefined",
            "combat:invalid_action_type",
            "totally_bogus",
            ":::",
        ]

        for action_id in test_ids:
            # Should not raise any exception
            response = facade.handle_action(action_id, {})
            assert response is not None, f"Response should not be None for {action_id}"
            assert hasattr(response, 'messages'), f"Response should have messages for {action_id}"

    def test_registry_returns_clear_unknown_action_message(self):
        """ActionRegistry.execute returns clear message for unknown action."""
        from src.main import VirtualDM, GameConfig

        reset_registry()
        registry = get_default_registry()

        # Create minimal DM
        config = GameConfig(llm_provider="mock", load_content=False)
        dm = VirtualDM(config=config, initial_state=GameState.WILDERNESS_TRAVEL)

        result = registry.execute(dm, "nonexistent:action", {})

        assert result["success"] is False
        assert "unknown" in result["message"].lower()


class TestRegistryValidation:
    """Test that the registry validates actions properly."""

    def test_is_registered_returns_true_for_known_actions(self):
        """is_registered returns True for registered actions."""
        reset_registry()
        registry = get_default_registry()

        known_actions = [
            "meta:status",
            "oracle:fate_check",
            "wilderness:travel",
            "dungeon:search",
        ]

        for action_id in known_actions:
            spec = registry.get(action_id)
            assert spec is not None, f"Action {action_id} should be registered"

    def test_registry_get_returns_none_for_unknown_actions(self):
        """registry.get returns None for unknown actions."""
        reset_registry()
        registry = get_default_registry()

        unknown_actions = [
            "nonexistent:action",
            "meta:undefined",
            "wilderness:fly_away",
        ]

        for action_id in unknown_actions:
            spec = registry.get(action_id)
            assert spec is None, f"Action {action_id} should NOT be registered"


class TestSuggestionRegistryAlignment:
    """Test that all suggested actions are registry-registered."""

    def test_all_suggestions_are_registered_or_legacy(self, facade, offline_dm):
        """Every suggested action should be in registry or legacy whitelist."""
        from src.conversation.suggestion_builder import LEGACY_SUPPORTED_ACTION_IDS

        reset_registry()
        registry = get_default_registry()

        # Test multiple states
        states = [
            GameState.WILDERNESS_TRAVEL,
            GameState.DUNGEON_EXPLORATION,
            GameState.ENCOUNTER,
            GameState.SETTLEMENT_EXPLORATION,
            GameState.DOWNTIME,
            GameState.COMBAT,
            GameState.SOCIAL_INTERACTION,
        ]

        not_registered = []

        for state in states:
            offline_dm.controller.state_machine.force_state(state, reason="test")
            response = facade.handle_chat("")

            for action in response.suggested_actions:
                action_id = action.id

                # Skip transition actions - always handled
                if action_id.startswith("transition:"):
                    continue

                # Check if registered
                spec = registry.get(action_id)
                if spec is not None:
                    continue

                # Check legacy whitelist
                if action_id in LEGACY_SUPPORTED_ACTION_IDS:
                    continue

                not_registered.append((state.value, action_id))

        # Strict mode: All suggestions must be registry-registered (Phase 4 goal)
        # For now, we accept legacy whitelist as fallback
        # After Phase 4.1, this should be empty
        if not_registered:
            pytest.fail(
                f"Actions suggested but not in registry or legacy: {not_registered}"
            )
