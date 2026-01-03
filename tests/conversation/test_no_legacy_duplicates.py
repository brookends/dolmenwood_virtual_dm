"""
P10.1: Tests to verify legacy duplicates are removed.

Ensures that:
1. For registered action IDs, only ActionRegistry executes (not legacy code)
2. Unknown action_ids return an error message
3. transition:* actions still work (only remaining legacy handler)
"""

import pytest
from unittest.mock import MagicMock, patch

from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.conversation.action_registry import get_default_registry, ActionSpec


class TestRegisteredActionsUseRegistry:
    """Verify registered actions are handled by ActionRegistry, not legacy."""

    @pytest.fixture
    def mock_dm(self):
        """Create a minimal mock VirtualDM."""
        dm = MagicMock()
        dm.controller = MagicMock()
        dm.controller.party_state = MagicMock()
        dm.controller.world_state = MagicMock()
        dm.controller.world_state.current_date = "Day 1"
        dm.controller.world_state.current_time = "08:00"
        dm.controller.party_state.location = MagicMock()
        dm.controller.party_state.location.location_id = "0101"
        dm.controller.party_state.location.location_type = "hex"
        dm.controller.party_state.active_light_source = None
        dm.controller.party_state.light_remaining_turns = 0
        dm.current_state = MagicMock()
        dm.current_state.value = "wilderness_travel"
        return dm

    @pytest.fixture
    def facade(self, mock_dm):
        """Create ConversationFacade with mocks."""
        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        return ConversationFacade(mock_dm, config=config)

    def test_meta_status_uses_registry(self, facade):
        """Verify meta:status goes through registry executor."""
        # The registry has an executor for meta:status
        registry = get_default_registry()
        spec = registry.get("meta:status")
        assert spec is not None
        assert spec.executor is not None

        # Execute via facade - should work and return status message
        response = facade.handle_action("meta:status")

        # Should succeed with mode info (from registry executor)
        assert len(response.messages) >= 1
        msg_text = response.messages[0].content
        assert "Mode:" in msg_text or "mode" in msg_text.lower()

    def test_wilderness_travel_uses_registry(self, facade, mock_dm):
        """Verify wilderness:travel goes through registry executor."""
        registry = get_default_registry()
        spec = registry.get("wilderness:travel")
        assert spec is not None
        assert spec.executor is not None

        # Set up mock return
        mock_dm.travel_to_hex = MagicMock(return_value={
            "success": True,
            "message": "Traveled to hex 0102",
        })

        response = facade.handle_action("wilderness:travel", {"hex_id": "0102"})

        # Verify travel_to_hex was called (via registry)
        mock_dm.travel_to_hex.assert_called_once_with("0102")

    def test_oracle_fate_check_uses_registry(self, facade):
        """Verify oracle:fate_check goes through registry executor."""
        registry = get_default_registry()
        spec = registry.get("oracle:fate_check")
        assert spec is not None
        assert spec.executor is not None

        response = facade.handle_action("oracle:fate_check", {
            "question": "Is the door trapped?",
            "likelihood": "fifty_fifty",
        })

        # Should get an oracle result
        assert len(response.messages) >= 1
        msg_text = response.messages[0].content
        assert "Oracle" in msg_text or "roll" in msg_text.lower()


class TestUnknownActionReturnsError:
    """Verify unknown action_ids return proper error."""

    @pytest.fixture
    def mock_dm(self):
        dm = MagicMock()
        dm.controller = MagicMock()
        dm.current_state = MagicMock()
        dm.current_state.value = "wilderness_travel"
        return dm

    @pytest.fixture
    def facade(self, mock_dm):
        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        return ConversationFacade(mock_dm, config=config)

    def test_unknown_action_returns_error(self, facade):
        """Verify unknown action_id returns error message."""
        response = facade.handle_action("nonexistent:action", {})

        assert len(response.messages) == 1
        assert "Unknown action_id" in response.messages[0].content
        assert "nonexistent:action" in response.messages[0].content

    def test_made_up_wilderness_action_returns_error(self, facade):
        """Verify made-up wilderness action returns error."""
        response = facade.handle_action("wilderness:teleport", {})

        assert len(response.messages) == 1
        assert "Unknown action_id" in response.messages[0].content


class TestTransitionStillWorks:
    """Verify transition:* actions still work via legacy handler."""

    @pytest.fixture
    def mock_dm(self):
        dm = MagicMock()
        dm.controller = MagicMock()
        dm.controller.transition = MagicMock()
        dm.current_state = MagicMock()
        dm.current_state.value = "wilderness_travel"
        return dm

    @pytest.fixture
    def facade(self, mock_dm):
        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        return ConversationFacade(mock_dm, config=config)

    def test_transition_action_calls_controller(self, facade, mock_dm):
        """Verify transition:enter_dungeon calls controller.transition."""
        response = facade.handle_action("transition:enter_dungeon", {})

        # Should call controller.transition with the trigger
        mock_dm.controller.transition.assert_called_once_with(
            "enter_dungeon", context={}
        )

        # Should return success message
        assert len(response.messages) == 1
        assert "Transitioned" in response.messages[0].content
        assert "enter_dungeon" in response.messages[0].content

    def test_transition_with_context(self, facade, mock_dm):
        """Verify transition passes context parameters."""
        response = facade.handle_action("transition:combat_started", {
            "enemy_count": 3,
            "surprise": True,
        })

        mock_dm.controller.transition.assert_called_once_with(
            "combat_started", context={"enemy_count": 3, "surprise": True}
        )

    def test_transition_failure_returns_error(self, facade, mock_dm):
        """Verify failed transition returns error message."""
        mock_dm.controller.transition.side_effect = ValueError("Invalid trigger")

        response = facade.handle_action("transition:invalid_trigger", {})

        assert len(response.messages) == 1
        assert "failed" in response.messages[0].content.lower()
        assert "Invalid trigger" in response.messages[0].content


class TestLegacyCodeNotReached:
    """Verify that legacy code paths are not reached for registered actions."""

    @pytest.fixture
    def mock_dm(self):
        dm = MagicMock()
        dm.controller = MagicMock()
        dm.controller.party_state = MagicMock()
        dm.controller.world_state = MagicMock()
        dm.controller.world_state.current_date = "Day 1"
        dm.controller.world_state.current_time = "08:00"
        dm.controller.party_state.location = MagicMock()
        dm.controller.party_state.location.location_id = "0101"
        dm.controller.party_state.location.location_type = "hex"
        dm.controller.party_state.active_light_source = None
        dm.controller.party_state.light_remaining_turns = 0
        dm.current_state = MagicMock()
        dm.current_state.value = "wilderness_travel"
        return dm

    def test_all_registered_actions_have_executors(self):
        """Verify all registered action specs have executors."""
        registry = get_default_registry()

        # Key action IDs that must have executors
        required_actions = [
            "meta:status",
            "meta:factions",
            "wilderness:travel",
            "wilderness:look_around",
            "wilderness:search_hex",
            "wilderness:approach_poi",
            "wilderness:enter_poi",
            "wilderness:leave_poi",
            "wilderness:forage",
            "wilderness:hunt",
            "dungeon:move",
            "dungeon:search",
            "dungeon:exit",
            "encounter:action",
            "settlement:action",
            "downtime:action",
            "oracle:fate_check",
            "oracle:random_event",
            "oracle:detail_check",
            "combat:resolve_round",
            "combat:flee",
            "combat:status",
            "combat:end",
            "fairy_road:enter",
            "fairy_road:exit",
            "fairy_road:status",
            "party:light",
        ]

        for action_id in required_actions:
            spec = registry.get(action_id)
            assert spec is not None, f"Action {action_id} not registered"
            assert spec.executor is not None, f"Action {action_id} has no executor"

    def test_registry_intercepts_before_legacy(self, mock_dm):
        """Verify registry execution happens before any legacy would."""
        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        facade = ConversationFacade(mock_dm, config=config)

        # Patch the registry's execute method to track calls
        with patch.object(facade._registry, 'execute') as mock_execute:
            mock_execute.return_value = {"success": True, "message": "Done"}

            # Call a registered action
            facade.handle_action("meta:status", {})

            # Registry execute should have been called
            mock_execute.assert_called_once()
            args, kwargs = mock_execute.call_args
            assert args[1] == "meta:status"  # action_id is second arg


class TestCombatAndFairyRoadUseRegistry:
    """Verify combat and fairy road actions use registry (no legacy handlers)."""

    def test_combat_actions_registered(self):
        """Verify all combat actions have registry executors."""
        registry = get_default_registry()

        combat_actions = [
            "combat:resolve_round",
            "combat:flee",
            "combat:parley",
            "combat:status",
            "combat:end",
        ]

        for action_id in combat_actions:
            spec = registry.get(action_id)
            assert spec is not None, f"Combat action {action_id} not registered"
            assert spec.executor is not None, f"Combat action {action_id} has no executor"

    def test_fairy_road_actions_registered(self):
        """Verify all fairy road actions have registry executors."""
        registry = get_default_registry()

        fairy_actions = [
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
        ]

        for action_id in fairy_actions:
            spec = registry.get(action_id)
            assert spec is not None, f"Fairy road action {action_id} not registered"
            assert spec.executor is not None, f"Fairy road action {action_id} has no executor"
