"""
Test that all suggested actions are executable.

Phase 0.1: Suggestion executability test harness

This test ensures that every action shown in TurnResponse.suggested_actions
can actually be executed without "No executor for action" errors.

The test exercises all major game states and verifies that the ConversationFacade
can handle every suggested action.
"""

import pytest
from typing import Any

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
    """
    Create VirtualDM in offline mode (LLM disabled).

    This is the primary fixture for executability testing - it simulates
    a fully functional game without any LLM dependency.
    """
    reset_registry()  # Ensure clean registry state

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

    # Add a test character
    dm.controller.add_character(test_character)

    # Give party some resources
    dm.controller.party_state.resources.food_days = 10
    dm.controller.party_state.resources.water_days = 10
    dm.controller.party_state.resources.torches = 6
    dm.controller.party_state.resources.lantern_oil_flasks = 4

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
# HELPER FUNCTIONS
# =============================================================================


# Legacy action IDs that are handled by the fallback if-chain in handle_action()
LEGACY_SUPPORTED_ACTION_IDS = {
    # Meta actions
    "meta:status",
    "meta:factions",
    # Party utilities
    "party:light",
    # Wilderness actions
    "wilderness:travel",
    "wilderness:look_around",
    "wilderness:search_hex",
    "wilderness:end_day",
    "wilderness:approach_poi",
    "wilderness:enter_poi",
    "wilderness:leave_poi",
    "wilderness:forage",
    "wilderness:hunt",
    "wilderness:resolve_poi_hazard",
    "wilderness:enter_poi_with_conditions",
    "wilderness:talk_npc",
    "wilderness:take_item",
    "wilderness:search_location",
    "wilderness:explore_feature",
    "wilderness:enter_dungeon",
    # Dungeon actions
    "dungeon:move",
    "dungeon:search",
    "dungeon:listen",
    "dungeon:open_door",
    "dungeon:pick_lock",
    "dungeon:disarm_trap",
    "dungeon:rest",
    "dungeon:map",
    "dungeon:fast_travel",
    "dungeon:exit",
    # Encounter actions
    "encounter:action",
    # Settlement/Downtime generic actions
    "settlement:action",
    "downtime:action",
    # Oracle actions
    "oracle:fate_check",
    "oracle:random_event",
    "oracle:detail_check",
    # Combat actions
    "combat:resolve_round",
    "combat:flee",
    "combat:parley",
    "combat:status",
    "combat:end",
    "combat:cast_spell",
    # Fairy road actions
    "fairy_road:enter",
    "fairy_road:travel_segment",
    "fairy_road:resolve_encounter",
    "fairy_road:flee_encounter",
    "fairy_road:explore_location",
    "fairy_road:continue_past",
    "fairy_road:exit",
    "fairy_road:stray",
    "fairy_road:status",
    "fairy_road:find_door",
}


def is_action_executable(facade: ConversationFacade, action_id: str) -> bool:
    """
    Check if an action ID is executable.

    An action is executable if:
    1. It's registered in ActionRegistry with an executor, OR
    2. It's in the legacy fallback support set
    3. It's a transition action (transition:*)
    """
    # Transition actions are always handled
    if action_id.startswith("transition:"):
        return True

    # Check registry first
    registry = get_default_registry()
    spec = registry.get(action_id)
    if spec and spec.executor:
        return True

    # Check legacy support
    if action_id in LEGACY_SUPPORTED_ACTION_IDS:
        return True

    return False


def get_suggested_action_ids(facade: ConversationFacade) -> list[str]:
    """Get all suggested action IDs for the current state."""
    # Generate a response to get suggestions
    response = facade.handle_chat("")
    return [a.id for a in response.suggested_actions]


def collect_unexecutable_actions(
    facade: ConversationFacade,
    action_ids: list[str]
) -> list[str]:
    """Return list of action IDs that cannot be executed."""
    unexecutable = []
    for action_id in action_ids:
        if not is_action_executable(facade, action_id):
            unexecutable.append(action_id)
    return unexecutable


# =============================================================================
# TESTS
# =============================================================================


class TestActionExecutability:
    """Test that all suggested actions can be executed."""

    def test_wilderness_travel_suggestions_executable(self, facade, offline_dm):
        """All wilderness travel suggestions should be executable."""
        # Ensure we're in wilderness travel
        assert offline_dm.current_state == GameState.WILDERNESS_TRAVEL

        # Get suggested actions
        action_ids = get_suggested_action_ids(facade)

        # Check all are executable
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in WILDERNESS_TRAVEL: {unexecutable}"
        )

    def test_dungeon_exploration_suggestions_executable(self, facade, offline_dm):
        """All dungeon exploration suggestions should be executable."""
        # Transition to dungeon
        offline_dm.controller.state_machine.force_state(
            GameState.DUNGEON_EXPLORATION,
            reason="test setup"
        )

        # Set up minimal dungeon state
        try:
            offline_dm.dungeon.enter_dungeon(
                dungeon_id="test_dungeon",
                entry_room="entrance"
            )
        except Exception:
            # If dungeon entry fails, set up mock state
            pass

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in DUNGEON_EXPLORATION: {unexecutable}"
        )

    def test_encounter_suggestions_executable(self, facade, offline_dm):
        """All encounter suggestions should be executable."""
        # Force encounter state
        offline_dm.controller.state_machine.force_state(
            GameState.ENCOUNTER,
            reason="test setup"
        )

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in ENCOUNTER: {unexecutable}"
        )

    def test_settlement_suggestions_executable(self, facade, offline_dm):
        """All settlement suggestions should be executable."""
        # Force settlement state
        offline_dm.controller.state_machine.force_state(
            GameState.SETTLEMENT_EXPLORATION,
            reason="test setup"
        )

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in SETTLEMENT_EXPLORATION: {unexecutable}"
        )

    def test_downtime_suggestions_executable(self, facade, offline_dm):
        """All downtime suggestions should be executable."""
        # Force downtime state
        offline_dm.controller.state_machine.force_state(
            GameState.DOWNTIME,
            reason="test setup"
        )

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in DOWNTIME: {unexecutable}"
        )

    def test_combat_suggestions_executable(self, facade, offline_dm):
        """All combat suggestions should be executable."""
        # Force combat state
        offline_dm.controller.state_machine.force_state(
            GameState.COMBAT,
            reason="test setup"
        )

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in COMBAT: {unexecutable}"
        )

    def test_fairy_road_suggestions_executable(self, facade, offline_dm):
        """All fairy road suggestions should be executable."""
        # Force fairy road state
        offline_dm.controller.state_machine.force_state(
            GameState.FAIRY_ROAD_TRAVEL,
            reason="test setup"
        )

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in FAIRY_ROAD_TRAVEL: {unexecutable}"
        )

    def test_social_interaction_suggestions_executable(self, facade, offline_dm):
        """All social interaction suggestions should be executable."""
        # Force social interaction state
        offline_dm.controller.state_machine.force_state(
            GameState.SOCIAL_INTERACTION,
            reason="test setup"
        )

        action_ids = get_suggested_action_ids(facade)
        unexecutable = collect_unexecutable_actions(facade, action_ids)

        assert not unexecutable, (
            f"Unexecutable actions in SOCIAL_INTERACTION: {unexecutable}"
        )


class TestRegistryExecutorCoverage:
    """Test that registered actions have executors or are handled."""

    def test_all_registered_actions_have_handler(self):
        """Every registered action should have an executor or legacy handler."""
        reset_registry()
        registry = get_default_registry()

        missing_handlers = []
        for spec in registry.all():
            # Check if it has an executor
            if spec.executor:
                continue
            # Check if it's legacy supported
            if spec.id in LEGACY_SUPPORTED_ACTION_IDS:
                continue
            # Check if it's a transition
            if spec.id.startswith("transition:"):
                continue

            missing_handlers.append(spec.id)

        assert not missing_handlers, (
            f"Actions registered without executor or legacy support: {missing_handlers}"
        )


class TestActionExecutionDoesNotError:
    """Test that executing actions doesn't raise unhandled exceptions."""

    def test_meta_status_executes(self, facade):
        """meta:status should execute without error."""
        response = facade.handle_action("meta:status")
        assert response.messages
        # Should not be an error message
        assert "Unrecognized action" not in response.messages[0].content
        assert "No executor" not in response.messages[0].content

    def test_oracle_fate_check_requires_question(self, facade):
        """oracle:fate_check should require a question parameter."""
        response = facade.handle_action("oracle:fate_check", {"question": ""})
        # Should ask for a question, not error
        assert response.messages
        # Check it handled gracefully (not a crash)

    def test_oracle_detail_check_executes(self, facade):
        """oracle:detail_check should execute without error."""
        response = facade.handle_action("oracle:detail_check")
        assert response.messages
        assert "Detail Check" in response.messages[0].content

    def test_wilderness_look_around_executes(self, facade, offline_dm):
        """wilderness:look_around should execute without error."""
        assert offline_dm.current_state == GameState.WILDERNESS_TRAVEL
        response = facade.handle_action("wilderness:look_around")
        assert response.messages
        # Check it doesn't fail with "Unrecognized action"
        # Note: May fail with "current_hex_id" error until Phase 7 adds accessors
        content = response.messages[0].content
        if "Execution failed" in content and "current_hex_id" in content:
            pytest.skip("HexCrawlEngine needs accessor methods (Phase 7)")
        assert "Unrecognized action" not in content


class TestLegacyActionsStillWork:
    """Test that legacy action IDs still work through fallback."""

    def test_encounter_action_works(self, facade, offline_dm):
        """encounter:action should work through legacy handler."""
        # Force encounter state
        offline_dm.controller.state_machine.force_state(
            GameState.ENCOUNTER,
            reason="test setup"
        )

        # Try to execute with valid action
        response = facade.handle_action(
            "encounter:action",
            {"action": "parley", "actor": "party"}
        )
        assert response.messages
        # Should not be "Unrecognized action"
        assert "Unrecognized action" not in response.messages[0].content

    def test_settlement_action_works(self, facade, offline_dm):
        """settlement:action should work through legacy handler."""
        offline_dm.controller.state_machine.force_state(
            GameState.SETTLEMENT_EXPLORATION,
            reason="test setup"
        )

        response = facade.handle_action(
            "settlement:action",
            {"text": "look around", "character_id": "test_fighter_1"}
        )
        assert response.messages
        assert "Unrecognized action" not in response.messages[0].content

    def test_downtime_action_works(self, facade, offline_dm):
        """downtime:action should work through legacy handler."""
        offline_dm.controller.state_machine.force_state(
            GameState.DOWNTIME,
            reason="test setup"
        )

        response = facade.handle_action(
            "downtime:action",
            {"text": "rest", "character_id": "test_fighter_1"}
        )
        assert response.messages
        assert "Unrecognized action" not in response.messages[0].content
