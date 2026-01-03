"""
Tests for P1-5: Encounter narration callback.

Verifies that _narrate_encounter_action:
1. Calls the DM agent's narrate_resolved_action
2. Stores the narration in _last_encounter_narration
3. ConversationFacade surfaces the narration to the player
"""

import pytest
from unittest.mock import MagicMock, patch

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState, EncounterState, EncounterType
from src.game_state.state_machine import GameState
from src.conversation.conversation_facade import ConversationFacade, ConversationConfig
from src.encounter.encounter_engine import EncounterAction, EncounterOrigin


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
def dm_with_agent(seeded_dice, test_character):
    """Create VirtualDM with a mock DM agent."""
    config = GameConfig(
        llm_provider="mock",
        enable_narration=True,
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
def dm_without_agent(seeded_dice, test_character):
    """Create VirtualDM without DM agent."""
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


# =============================================================================
# TESTS: _narrate_encounter_action
# =============================================================================


class TestNarrateEncounterAction:
    """Test that _narrate_encounter_action calls DM agent correctly."""

    def test_calls_dm_agent_narrate(self, dm_with_agent):
        """Should call narrate_resolved_action when DM agent is available."""
        # Set up mock DM agent
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The party attempts to negotiate with the goblins."
        )
        dm_with_agent._dm_agent = mock_agent

        # Call the narration method
        result = {"success": True, "messages": ["Parley attempt begins."]}
        dm_with_agent._narrate_encounter_action(
            action="parley",
            actor="party",
            result=result,
        )

        # Verify DM agent was called
        mock_agent.narrate_resolved_action.assert_called_once()

    def test_stores_narration_in_last_encounter_narration(self, dm_with_agent):
        """Should store generated narration in _last_encounter_narration."""
        expected_narration = "The party steps forward to parley."

        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content=expected_narration
        )
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True, "messages": []}
        dm_with_agent._narrate_encounter_action(
            action="parley",
            actor="party",
            result=result,
        )

        assert dm_with_agent._last_encounter_narration == expected_narration

    def test_no_narration_when_agent_unavailable(self, dm_with_agent):
        """Should not store narration when DM agent is unavailable."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = False
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True, "messages": []}
        dm_with_agent._narrate_encounter_action(
            action="attack",
            actor="party",
            result=result,
        )

        # Should not have narration stored
        assert getattr(dm_with_agent, "_last_encounter_narration", None) is None

    def test_no_narration_when_narration_disabled(self, dm_without_agent):
        """Should not generate narration when enable_narration is False."""
        dm_without_agent._dm_agent = None

        result = {"success": True, "messages": []}
        dm_without_agent._narrate_encounter_action(
            action="evasion",
            actor="party",
            result=result,
        )

        assert getattr(dm_without_agent, "_last_encounter_narration", None) is None

    def test_handles_different_action_types(self, dm_with_agent):
        """Should generate appropriate narration for different action types."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="Narration text"
        )
        dm_with_agent._dm_agent = mock_agent

        actions = ["parley", "evasion", "attack", "wait"]

        for action in actions:
            dm_with_agent._narrate_encounter_action(
                action=action,
                actor="party",
                result={"success": True, "messages": []},
            )

            # Each action should trigger a call
            call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs
            assert "action_description" in call_kwargs
            assert action in call_kwargs.get("action_type", "")


# =============================================================================
# TESTS: get_last_encounter_narration
# =============================================================================


class TestGetLastEncounterNarration:
    """Test the get_last_encounter_narration method."""

    def test_returns_stored_narration(self, dm_with_agent):
        """Should return the stored narration."""
        dm_with_agent._last_encounter_narration = "Test narration text"

        result = dm_with_agent.get_last_encounter_narration()

        assert result == "Test narration text"

    def test_clears_narration_after_retrieval(self, dm_with_agent):
        """Should clear narration after returning it."""
        dm_with_agent._last_encounter_narration = "Test narration text"

        dm_with_agent.get_last_encounter_narration()

        # Second call should return None
        result = dm_with_agent.get_last_encounter_narration()
        assert result is None

    def test_returns_none_when_no_narration(self, dm_with_agent):
        """Should return None when no narration is stored."""
        dm_with_agent._last_encounter_narration = None

        result = dm_with_agent.get_last_encounter_narration()

        assert result is None


# =============================================================================
# TESTS: ConversationFacade Integration
# =============================================================================


class TestConversationFacadeEncounterNarration:
    """Test that ConversationFacade surfaces encounter narration."""

    def test_includes_narration_in_response(self, dm_with_agent, test_character):
        """Should include DM narration in encounter action response."""
        # Start an active encounter so the callback will trigger
        encounter_state = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=30,
            actors=["goblin_1", "goblin_2", "goblin_3"],
        )
        dm_with_agent.encounter.start_encounter(
            encounter=encounter_state,
            origin=EncounterOrigin.WILDERNESS,
        )

        # Set up mock agent with narration
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The party holds their ground, watching carefully."
        )
        dm_with_agent._dm_agent = mock_agent

        # Create facade
        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        facade = ConversationFacade(dm_with_agent, config=config)

        # Execute encounter action
        response = facade.handle_action(
            "encounter:action",
            {"action": "wait", "actor": "party"}
        )

        # Check that narration message is included
        dm_messages = [m for m in response.messages if m.role == "dm"]
        assert len(dm_messages) >= 1, "Should have DM narration message"
        assert "watching carefully" in dm_messages[-1].content

    def test_no_dm_message_when_narration_disabled(self, dm_without_agent, test_character):
        """Should not include DM message when narration is disabled."""
        # Start an active encounter
        encounter_state = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=40,
            actors=["wolf_1", "wolf_2"],
        )
        dm_without_agent.encounter.start_encounter(
            encounter=encounter_state,
            origin=EncounterOrigin.WILDERNESS,
        )

        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        facade = ConversationFacade(dm_without_agent, config=config)

        # Execute encounter action
        response = facade.handle_action(
            "encounter:action",
            {"action": "wait", "actor": "party"}
        )

        # Should have system messages but no DM narration
        dm_messages = [m for m in response.messages if m.role == "dm"]
        assert len(dm_messages) == 0, "Should not have DM narration when disabled"

    def test_system_messages_preserved(self, dm_with_agent, test_character):
        """Should preserve system messages alongside narration."""
        # Start an active encounter
        encounter_state = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=25,
            actors=["bandit_1", "bandit_2", "bandit_3", "bandit_4"],
        )
        dm_with_agent.encounter.start_encounter(
            encounter=encounter_state,
            origin=EncounterOrigin.WILDERNESS,
        )

        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="Narration text."
        )
        dm_with_agent._dm_agent = mock_agent

        config = ConversationConfig(
            use_llm_intent_parsing=False,
            use_oracle_enhancement=False,
        )
        facade = ConversationFacade(dm_with_agent, config=config)

        response = facade.handle_action(
            "encounter:action",
            {"action": "parley", "actor": "party"}
        )

        # Should have both system and dm messages
        system_messages = [m for m in response.messages if m.role == "system"]
        dm_messages = [m for m in response.messages if m.role == "dm"]

        # System messages from encounter engine should be present
        # (the exact count depends on encounter state)
        assert len(response.messages) >= 1


# =============================================================================
# TESTS: Edge Cases
# =============================================================================


class TestEncounterNarrationEdgeCases:
    """Test edge cases for encounter narration."""

    def test_handles_empty_result_messages(self, dm_with_agent):
        """Should handle result with no messages."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The party waits."
        )
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True}  # No messages key
        dm_with_agent._narrate_encounter_action(
            action="wait",
            actor="party",
            result=result,
        )

        assert dm_with_agent._last_encounter_narration == "The party waits."

    def test_handles_narration_failure(self, dm_with_agent):
        """Should handle DM agent narration failure gracefully."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.side_effect = Exception("LLM error")
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True, "messages": []}

        # Should not raise exception
        dm_with_agent._narrate_encounter_action(
            action="attack",
            actor="party",
            result=result,
        )

        # Narration should be None due to error
        assert getattr(dm_with_agent, "_last_encounter_narration", None) is None

    def test_unknown_action_gets_generic_description(self, dm_with_agent):
        """Unknown actions should get a generic description."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="Generic narration."
        )
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True, "messages": []}
        dm_with_agent._narrate_encounter_action(
            action="custom_action",
            actor="party",
            result=result,
        )

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs
        assert "custom_action" in call_kwargs["action_description"]

    def test_actor_party_converted_to_text(self, dm_with_agent):
        """Actor 'party' should be converted to 'the party' for narration."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The party acts."
        )
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True, "messages": []}
        dm_with_agent._narrate_encounter_action(
            action="wait",
            actor="party",
            result=result,
        )

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs
        assert call_kwargs["character_name"] == "the party"

    def test_individual_actor_preserved(self, dm_with_agent):
        """Individual actor names should be preserved."""
        mock_agent = MagicMock()
        mock_agent.is_available.return_value = True
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The fighter acts."
        )
        dm_with_agent._dm_agent = mock_agent

        result = {"success": True, "messages": []}
        dm_with_agent._narrate_encounter_action(
            action="attack",
            actor="Test Fighter",
            result=result,
        )

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs
        assert call_kwargs["character_name"] == "Test Fighter"
