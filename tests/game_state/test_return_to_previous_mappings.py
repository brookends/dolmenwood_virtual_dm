"""
Tests for return_to_previous state machine mappings.

Phase 5.1: Verify that all nested state transitions have proper
return mappings, allowing combat/parley that starts from encounter
to return correctly.
"""

import pytest

from src.game_state.state_machine import (
    GameState,
    StateMachine,
    InvalidTransitionError,
)


@pytest.fixture
def state_machine():
    """Create a fresh state machine."""
    return StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)


class TestReturnFromCombatToEncounter:
    """Test returning from combat that was started by encounter_to_combat."""

    def test_combat_end_encounter_exists(self, state_machine):
        """The combat_end_encounter transition should exist."""
        # Start in wilderness, trigger encounter, then combat
        state_machine.transition("encounter_triggered")
        assert state_machine.current_state == GameState.ENCOUNTER

        state_machine.transition("encounter_to_combat")
        assert state_machine.current_state == GameState.COMBAT

        # Now return to encounter
        state_machine.transition("combat_end_encounter")
        assert state_machine.current_state == GameState.ENCOUNTER

    def test_return_to_previous_from_combat_to_encounter(self, state_machine):
        """return_to_previous should work when combat came from encounter."""
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")

        assert state_machine.current_state == GameState.COMBAT
        assert state_machine.previous_state == GameState.ENCOUNTER

        # Use return_to_previous
        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.ENCOUNTER


class TestReturnFromParleyToEncounter:
    """Test returning from parley that was started by encounter_to_parley."""

    def test_parley_end_encounter_exists(self, state_machine):
        """The parley_end_encounter transition should exist."""
        state_machine.transition("encounter_triggered")
        assert state_machine.current_state == GameState.ENCOUNTER

        state_machine.transition("encounter_to_parley")
        assert state_machine.current_state == GameState.SOCIAL_INTERACTION

        # Now return to encounter
        state_machine.transition("parley_end_encounter")
        assert state_machine.current_state == GameState.ENCOUNTER

    def test_return_to_previous_from_parley_to_encounter(self, state_machine):
        """return_to_previous should work when parley came from encounter."""
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_parley")

        assert state_machine.current_state == GameState.SOCIAL_INTERACTION
        assert state_machine.previous_state == GameState.ENCOUNTER

        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.ENCOUNTER


class TestReturnFromParleyToCombat:
    """Test returning from parley that was started by combat_to_parley."""

    def test_parley_return_combat_exists(self, state_machine):
        """The parley_return_combat transition should exist."""
        # Start combat from encounter, then parley
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")
        assert state_machine.current_state == GameState.COMBAT

        state_machine.transition("combat_to_parley")
        assert state_machine.current_state == GameState.SOCIAL_INTERACTION

        # Return to combat (negotiation failed)
        state_machine.transition("parley_return_combat")
        assert state_machine.current_state == GameState.COMBAT

    def test_return_to_previous_from_parley_to_combat(self, state_machine):
        """return_to_previous should work when parley came from combat."""
        # Start in dungeon for variety
        state_machine = StateMachine(initial_state=GameState.DUNGEON_EXPLORATION)
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")
        state_machine.transition("combat_to_parley")

        assert state_machine.current_state == GameState.SOCIAL_INTERACTION
        assert state_machine.previous_state == GameState.COMBAT

        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.COMBAT


class TestExistingReturnMappingsStillWork:
    """Verify existing return_to_previous mappings continue to work."""

    def test_combat_to_wilderness(self, state_machine):
        """Combat ending should return to wilderness correctly."""
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_combat")
        # Force previous to wilderness for this test
        state_machine._previous_state = GameState.WILDERNESS_TRAVEL

        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.WILDERNESS_TRAVEL

    def test_combat_to_dungeon(self):
        """Combat ending should return to dungeon correctly."""
        sm = StateMachine(initial_state=GameState.DUNGEON_EXPLORATION)
        sm.transition("encounter_triggered")
        sm.transition("encounter_to_combat")
        sm._previous_state = GameState.DUNGEON_EXPLORATION

        sm.return_to_previous()
        assert sm.current_state == GameState.DUNGEON_EXPLORATION

    def test_social_to_wilderness(self, state_machine):
        """Social interaction ending should return to wilderness."""
        state_machine.transition("initiate_conversation")
        assert state_machine.current_state == GameState.SOCIAL_INTERACTION

        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.WILDERNESS_TRAVEL

    def test_encounter_to_wilderness(self, state_machine):
        """Encounter ending should return to wilderness."""
        state_machine.transition("encounter_triggered")
        assert state_machine.current_state == GameState.ENCOUNTER

        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.WILDERNESS_TRAVEL


class TestNestedStateFlows:
    """Test complete nested state flows end-to-end."""

    def test_full_encounter_to_combat_to_parley_flow(self, state_machine):
        """Test full flow: wilderness → encounter → combat → parley → combat → encounter."""
        # Start encounter
        state_machine.transition("encounter_triggered")
        assert state_machine.current_state == GameState.ENCOUNTER

        # Encounter escalates to combat
        state_machine.transition("encounter_to_combat")
        assert state_machine.current_state == GameState.COMBAT

        # Combat leads to parley (surrender attempt)
        state_machine.transition("combat_to_parley")
        assert state_machine.current_state == GameState.SOCIAL_INTERACTION

        # Parley fails, return to combat
        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.COMBAT

        # Combat ends, return to encounter
        state_machine._previous_state = GameState.ENCOUNTER  # Set expected previous
        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.ENCOUNTER

    def test_encounter_parley_success_flow(self, state_machine):
        """Test flow: wilderness → encounter → parley → encounter → wilderness."""
        state_machine.transition("encounter_triggered")
        state_machine.transition("encounter_to_parley")

        assert state_machine.current_state == GameState.SOCIAL_INTERACTION
        assert state_machine.previous_state == GameState.ENCOUNTER

        # Parley ends, return to encounter
        state_machine.return_to_previous()
        assert state_machine.current_state == GameState.ENCOUNTER

        # Note: After returning from social to encounter, previous is now social_interaction.
        # To return to wilderness, we need to use the explicit trigger that knows the origin.
        # In practice, the encounter engine tracks the origin and uses the appropriate trigger.
        state_machine.transition("encounter_end_wilderness")
        assert state_machine.current_state == GameState.WILDERNESS_TRAVEL


class TestInvalidReturnAttempts:
    """Test that invalid return attempts are handled correctly."""

    def test_no_previous_state_raises(self, state_machine):
        """Attempting return without previous state should raise."""
        # Fresh machine has no previous state
        fresh = StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)
        with pytest.raises(InvalidTransitionError, match="No previous state"):
            fresh.return_to_previous()

    def test_unmapped_combination_raises(self, state_machine):
        """Unmapped state combinations should raise InvalidTransitionError."""
        # Force an unmapped combination
        state_machine._current_state = GameState.DOWNTIME
        state_machine._previous_state = GameState.COMBAT  # No mapping for this

        with pytest.raises(InvalidTransitionError, match="No valid return transition"):
            state_machine.return_to_previous()
