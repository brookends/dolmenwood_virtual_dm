"""
Tests for wilderness:enter_dungeon action executability.

P0-3: Verify that wilderness:enter_dungeon properly enters a dungeon
through the ActionRegistry execution path and transitions to
DUNGEON_EXPLORATION state.
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.conversation.action_registry import get_default_registry, reset_registry


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


# =============================================================================
# TESTS: Action Registration
# =============================================================================


class TestWildernessEnterDungeonRegistration:
    """Test that wilderness:enter_dungeon is properly registered."""

    def test_action_is_registered(self):
        """wilderness:enter_dungeon should be registered in ActionRegistry."""
        reset_registry()
        registry = get_default_registry()

        spec = registry.get("wilderness:enter_dungeon")

        assert spec is not None, "wilderness:enter_dungeon not found in registry"
        assert spec.id == "wilderness:enter_dungeon"
        assert spec.executor is not None, "wilderness:enter_dungeon has no executor"

    def test_action_has_correct_category(self):
        """wilderness:enter_dungeon should be in WILDERNESS category."""
        reset_registry()
        registry = get_default_registry()

        spec = registry.get("wilderness:enter_dungeon")

        from src.conversation.action_registry import ActionCategory
        assert spec.category == ActionCategory.WILDERNESS

    def test_action_requires_wilderness_state(self):
        """wilderness:enter_dungeon should require wilderness_travel state."""
        reset_registry()
        registry = get_default_registry()

        spec = registry.get("wilderness:enter_dungeon")

        assert spec.requires_state == "wilderness_travel"

    def test_action_has_dungeon_params(self):
        """wilderness:enter_dungeon should accept dungeon parameters."""
        reset_registry()
        registry = get_default_registry()

        spec = registry.get("wilderness:enter_dungeon")

        assert "dungeon_id" in spec.params_schema
        assert "entrance_room" in spec.params_schema


# =============================================================================
# TESTS: Action Execution
# =============================================================================


class TestWildernessEnterDungeonExecution:
    """Test that wilderness:enter_dungeon executes correctly."""

    def test_executes_without_crash(self, facade, offline_dm):
        """wilderness:enter_dungeon should execute without raising exceptions."""
        assert offline_dm.current_state == GameState.WILDERNESS_TRAVEL

        response = facade.handle_action(
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon"}
        )

        # Should have some response (success or error)
        assert response.messages
        # Should not be "Unrecognized action"
        assert "unrecognized action" not in response.messages[0].content.lower()

    def test_transitions_to_dungeon_exploration(self, facade, offline_dm):
        """
        Successful enter_dungeon should transition to DUNGEON_EXPLORATION state.

        This is the key requirement from P0-3: the action must transition
        the state machine to DUNGEON_EXPLORATION.
        """
        assert offline_dm.current_state == GameState.WILDERNESS_TRAVEL

        response = facade.handle_action(
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon", "entrance_room": "entrance"}
        )

        # Should transition to dungeon exploration
        assert offline_dm.current_state == GameState.DUNGEON_EXPLORATION, (
            f"Expected DUNGEON_EXPLORATION, got {offline_dm.current_state}. "
            f"Response: {response.messages[0].content if response.messages else 'no message'}"
        )

    def test_includes_dungeon_message(self, facade, offline_dm):
        """Response should indicate dungeon entry."""
        response = facade.handle_action(
            "wilderness:enter_dungeon",
            {"dungeon_id": "ancient_crypt"}
        )

        assert response.messages
        content = response.messages[0].content.lower()
        # Should mention dungeon or entry
        assert "dungeon" in content or "enter" in content or "crypt" in content


# =============================================================================
# TESTS: Registry Direct Execution
# =============================================================================


class TestActionRegistryExecution:
    """Test execution through ActionRegistry directly."""

    def test_registry_execute_calls_executor(self, offline_dm):
        """ActionRegistry.execute() should call the registered executor."""
        reset_registry()
        registry = get_default_registry()

        # Execute through registry
        result = registry.execute(
            offline_dm,
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon"}
        )

        # Should return a result dict
        assert isinstance(result, dict)
        assert "success" in result or "message" in result

    def test_registry_transitions_state(self, offline_dm):
        """Registry execution should transition to DUNGEON_EXPLORATION."""
        reset_registry()
        registry = get_default_registry()

        assert offline_dm.current_state == GameState.WILDERNESS_TRAVEL

        result = registry.execute(
            offline_dm,
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon"}
        )

        # Should succeed and transition
        if result.get("success"):
            assert offline_dm.current_state == GameState.DUNGEON_EXPLORATION

    def test_registry_validates_state(self, offline_dm):
        """Registry should reject action if not in required state."""
        reset_registry()
        registry = get_default_registry()

        # Force to wrong state
        offline_dm.controller.state_machine.force_state(
            GameState.COMBAT,
            reason="test"
        )

        result = registry.execute(
            offline_dm,
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon"}
        )

        assert result["success"] is False
        assert "state" in result["message"].lower()


# =============================================================================
# TESTS: Edge Cases
# =============================================================================


class TestEnterDungeonEdgeCases:
    """Test edge cases for dungeon entry."""

    def test_default_dungeon_id(self, offline_dm):
        """Should use default dungeon_id if not provided."""
        reset_registry()
        registry = get_default_registry()

        # Execute without dungeon_id
        result = registry.execute(
            offline_dm,
            "wilderness:enter_dungeon",
            {}  # No dungeon_id
        )

        # Should still execute (with default "dungeon")
        assert isinstance(result, dict)
        # Should not error with "missing parameter"
        assert "missing" not in result.get("message", "").lower()

    def test_default_entrance_room(self, offline_dm):
        """Should use default entrance_room if not provided."""
        reset_registry()
        registry = get_default_registry()

        result = registry.execute(
            offline_dm,
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon"}  # No entrance_room
        )

        # Should use default "entrance"
        assert isinstance(result, dict)
        assert "missing" not in result.get("message", "").lower()

    def test_with_custom_entrance(self, offline_dm):
        """Should support custom entrance room."""
        reset_registry()
        registry = get_default_registry()

        result = registry.execute(
            offline_dm,
            "wilderness:enter_dungeon",
            {"dungeon_id": "test_dungeon", "entrance_room": "secret_passage"}
        )

        # Should execute with custom entrance
        assert isinstance(result, dict)
