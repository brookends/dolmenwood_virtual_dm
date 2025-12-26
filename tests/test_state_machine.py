"""
Unit tests for game state machine.

Tests state transitions, validation, and callbacks from
src/game_state/state_machine.py.
"""

import pytest
from src.game_state.state_machine import (
    GameState,
    StateMachine,
    StateTransition,
    InvalidTransitionError,
    VALID_TRANSITIONS,
)


class TestStateMachineInitialization:
    """Tests for state machine initialization."""

    def test_default_initial_state(self):
        """Test default initial state is WILDERNESS_TRAVEL."""
        sm = StateMachine()
        assert sm.current_state == GameState.WILDERNESS_TRAVEL

    def test_custom_initial_state(self):
        """Test custom initial state."""
        sm = StateMachine(GameState.DUNGEON_EXPLORATION)
        assert sm.current_state == GameState.DUNGEON_EXPLORATION

    def test_previous_state_initially_none(self):
        """Test previous state is None initially."""
        sm = StateMachine()
        assert sm.previous_state is None

    def test_initial_state_history(self):
        """Test that initial state is logged in history."""
        sm = StateMachine()
        history = sm.state_history
        assert len(history) == 1
        assert history[0].to_state == GameState.WILDERNESS_TRAVEL.value


class TestStateTransitions:
    """Tests for state transitions."""

    def test_valid_wilderness_to_encounter(self, state_machine):
        """Test valid transition from wilderness to encounter."""
        new_state = state_machine.transition("encounter_triggered")
        assert new_state == GameState.ENCOUNTER
        assert state_machine.current_state == GameState.ENCOUNTER
        assert state_machine.previous_state == GameState.WILDERNESS_TRAVEL

    def test_valid_encounter_to_combat(self, state_machine):
        """Test valid transition from encounter to combat."""
        state_machine.transition("encounter_triggered")
        new_state = state_machine.transition("encounter_to_combat")
        assert new_state == GameState.COMBAT
        assert state_machine.previous_state == GameState.ENCOUNTER

    def test_valid_combat_end_wilderness(self, state_machine):
        """Test returning to wilderness after combat."""
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")
        new_state = state_machine.transition("combat_end_wilderness")
        assert new_state == GameState.WILDERNESS_TRAVEL

    def test_invalid_transition_raises(self, state_machine):
        """Test that invalid transitions raise InvalidTransitionError."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            state_machine.transition("combat_end_wilderness")  # Not in combat

        assert "Invalid transition" in str(exc_info.value)
        assert "wilderness_travel" in str(exc_info.value)

    def test_transition_with_context(self, state_machine):
        """Test that context is passed through transition."""
        context = {"encounter_type": "monster", "actors": ["goblin"]}
        state_machine.transition("encounter_triggered", context=context)

        history = state_machine.state_history
        last_entry = history[-1]
        assert last_entry.context == context


class TestDungeonTransitions:
    """Tests for dungeon-specific transitions."""

    def test_wilderness_to_dungeon(self, state_machine):
        """Test entering dungeon from wilderness."""
        new_state = state_machine.transition("enter_dungeon")
        assert new_state == GameState.DUNGEON_EXPLORATION

    def test_dungeon_to_encounter(self, state_machine_dungeon):
        """Test encounter in dungeon."""
        new_state = state_machine_dungeon.transition("encounter_triggered")
        assert new_state == GameState.ENCOUNTER

    def test_encounter_end_dungeon(self, state_machine_dungeon):
        """Test returning to dungeon after encounter."""
        state_machine_dungeon.transition("encounter_triggered")
        new_state = state_machine_dungeon.transition("encounter_end_dungeon")
        assert new_state == GameState.DUNGEON_EXPLORATION

    def test_dungeon_to_wilderness(self, state_machine_dungeon):
        """Test exiting dungeon to wilderness."""
        new_state = state_machine_dungeon.transition("exit_dungeon")
        assert new_state == GameState.WILDERNESS_TRAVEL


class TestSettlementTransitions:
    """Tests for settlement-specific transitions."""

    def test_wilderness_to_settlement(self, state_machine):
        """Test entering settlement from wilderness."""
        new_state = state_machine.transition("enter_settlement")
        assert new_state == GameState.SETTLEMENT_EXPLORATION

    def test_settlement_to_social(self):
        """Test initiating conversation in settlement."""
        sm = StateMachine(GameState.SETTLEMENT_EXPLORATION)
        new_state = sm.transition("initiate_conversation")
        assert new_state == GameState.SOCIAL_INTERACTION

    def test_social_to_settlement(self):
        """Test ending conversation in settlement."""
        sm = StateMachine(GameState.SETTLEMENT_EXPLORATION)
        sm.transition("initiate_conversation")
        new_state = sm.transition("conversation_end_settlement")
        assert new_state == GameState.SETTLEMENT_EXPLORATION

    def test_settlement_to_dungeon(self):
        """Test entering dungeon from settlement."""
        sm = StateMachine(GameState.SETTLEMENT_EXPLORATION)
        new_state = sm.transition("enter_dungeon")
        assert new_state == GameState.DUNGEON_EXPLORATION


class TestDowntimeTransitions:
    """Tests for downtime transitions."""

    def test_wilderness_to_downtime(self, state_machine):
        """Test beginning rest in wilderness."""
        new_state = state_machine.transition("begin_rest")
        assert new_state == GameState.DOWNTIME

    def test_downtime_to_wilderness(self, state_machine):
        """Test ending rest, returning to wilderness."""
        state_machine.transition("begin_rest")
        new_state = state_machine.transition("downtime_end_wilderness")
        assert new_state == GameState.WILDERNESS_TRAVEL

    def test_downtime_interrupted(self, state_machine):
        """Test rest interrupted by combat."""
        state_machine.transition("begin_rest")
        new_state = state_machine.transition("rest_interrupted")
        assert new_state == GameState.COMBAT


class TestCanTransition:
    """Tests for can_transition method."""

    def test_can_transition_valid(self, state_machine):
        """Test can_transition returns True for valid trigger."""
        assert state_machine.can_transition("encounter_triggered") is True
        assert state_machine.can_transition("enter_dungeon") is True
        assert state_machine.can_transition("enter_settlement") is True

    def test_can_transition_invalid(self, state_machine):
        """Test can_transition returns False for invalid trigger."""
        assert state_machine.can_transition("combat_end_wilderness") is False
        assert state_machine.can_transition("exit_dungeon") is False


class TestGetValidTriggers:
    """Tests for get_valid_triggers method."""

    def test_wilderness_triggers(self, state_machine):
        """Test valid triggers from wilderness state."""
        triggers = state_machine.get_valid_triggers()
        assert "encounter_triggered" in triggers
        assert "enter_dungeon" in triggers
        assert "enter_settlement" in triggers
        assert "begin_rest" in triggers
        # Should not include invalid triggers
        assert "combat_end_wilderness" not in triggers

    def test_encounter_triggers(self, state_machine):
        """Test valid triggers from encounter state."""
        state_machine.transition("encounter_triggered")
        triggers = state_machine.get_valid_triggers()
        assert "encounter_to_combat" in triggers
        assert "encounter_to_parley" in triggers
        assert "encounter_end_wilderness" in triggers


class TestReturnToPrevious:
    """Tests for return_to_previous method."""

    def test_return_from_combat_to_wilderness(self, state_machine):
        """Test returning to wilderness from combat via proper transition."""
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")
        # Use the proper combat_end transition instead of return_to_previous
        state_machine.transition("combat_end_wilderness")
        assert state_machine.current_state == GameState.WILDERNESS_TRAVEL

    def test_return_from_encounter(self, state_machine):
        """Test returning from encounter."""
        state_machine.transition("encounter_triggered")
        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.WILDERNESS_TRAVEL

    def test_return_no_previous_raises(self, state_machine):
        """Test that return with no previous state raises error."""
        with pytest.raises(InvalidTransitionError):
            state_machine.return_to_previous()


class TestForceState:
    """Tests for force_state method."""

    def test_force_state_bypasses_validation(self, state_machine):
        """Test that force_state bypasses normal validation."""
        # This would normally be invalid
        state_machine.force_state(GameState.COMBAT, "debug override")
        assert state_machine.current_state == GameState.COMBAT

    def test_force_state_logs_reason(self, state_machine):
        """Test that force_state logs the reason."""
        state_machine.force_state(GameState.COMBAT, "testing")
        history = state_machine.state_history
        last_entry = history[-1]
        assert "FORCED" in last_entry.trigger
        assert "testing" in last_entry.trigger


class TestCallbacks:
    """Tests for state transition callbacks."""

    def test_register_callback(self, state_machine):
        """Test registering a transition callback."""
        callback_data = {"called": False}

        def callback(old, new, context):
            callback_data["called"] = True
            callback_data["old"] = old
            callback_data["new"] = new

        state_machine.register_callback(
            GameState.WILDERNESS_TRAVEL,
            "encounter_triggered",
            callback
        )

        state_machine.transition("encounter_triggered")
        assert callback_data["called"] is True
        assert callback_data["old"] == GameState.WILDERNESS_TRAVEL
        assert callback_data["new"] == GameState.ENCOUNTER

    def test_pre_hook(self, state_machine):
        """Test pre-transition hook."""
        hook_data = {"called": False}

        def hook(old, new, trigger, context):
            hook_data["called"] = True
            hook_data["trigger"] = trigger

        state_machine.register_pre_hook(hook)
        state_machine.transition("encounter_triggered")

        assert hook_data["called"] is True
        assert hook_data["trigger"] == "encounter_triggered"

    def test_post_hook(self, state_machine):
        """Test post-transition hook."""
        hook_data = {"called": False}

        def hook(old, new, trigger, context):
            hook_data["called"] = True
            hook_data["new_state"] = new

        state_machine.register_post_hook(hook)
        state_machine.transition("encounter_triggered")

        assert hook_data["called"] is True
        assert hook_data["new_state"] == GameState.ENCOUNTER


class TestStateInfo:
    """Tests for state information methods."""

    def test_get_state_info(self, state_machine):
        """Test get_state_info method."""
        info = state_machine.get_state_info()
        assert info["current_state"] == "wilderness_travel"
        assert info["previous_state"] is None
        assert isinstance(info["valid_triggers"], list)
        assert info["transition_count"] >= 1

    def test_is_exploration_state(self, state_machine):
        """Test is_exploration_state method."""
        assert state_machine.is_exploration_state() is True

        state_machine.transition("encounter_triggered")
        assert state_machine.is_exploration_state() is False

    def test_is_encounter_state(self, state_machine):
        """Test is_encounter_state method."""
        assert state_machine.is_encounter_state() is False

        state_machine.transition("encounter_triggered")
        assert state_machine.is_encounter_state() is True

    def test_is_combat_state(self, state_machine):
        """Test is_combat_state method."""
        assert state_machine.is_combat_state() is False

        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")
        assert state_machine.is_combat_state() is True


class TestValidTransitions:
    """Tests for VALID_TRANSITIONS constant."""

    def test_all_states_have_outgoing_transitions(self):
        """Test that all non-terminal states have outgoing transitions."""
        states_with_transitions = {t.from_state for t in VALID_TRANSITIONS}
        for state in GameState:
            # All states should have at least one outgoing transition
            assert state in states_with_transitions, f"{state} has no outgoing transitions"

    def test_transitions_are_consistent(self):
        """Test that transitions form valid state graph."""
        # Build set of all mentioned states
        all_states = set()
        for t in VALID_TRANSITIONS:
            all_states.add(t.from_state)
            all_states.add(t.to_state)

        # All should be valid GameState values
        for state in all_states:
            assert isinstance(state, GameState)
