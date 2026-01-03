"""
Tests for VirtualDM._narrate_from_context damage computation.

P0-4: Verify that damage_taken is computed correctly from damage_dealt,
not from healing_done.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.narrative.narrative_resolver import NarrationContext, ActionCategory, ActionType


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


# =============================================================================
# TESTS: Damage Computation
# =============================================================================


class TestDamageComputation:
    """Test that damage_taken and damage_dealt are computed correctly."""

    def test_damage_taken_not_from_healing(self, dm_with_agent):
        """
        P0-4 BUG FIX: damage_taken should NOT come from healing_done.

        Previously, the code was:
            damage_taken = sum(context.healing_done.values())

        This is wrong - healing should not be treated as damage taken.
        """
        # Create context where actor receives healing but no damage
        context = NarrationContext(
            action_category=ActionCategory.SURVIVAL,
            action_type=ActionType.REST,
            player_input="Rest and heal",
            success=True,
            damage_dealt={},  # No damage dealt
            healing_done={"test_fighter_1": 10},  # Actor received healing
        )

        # Mock the DM agent
        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The fighter rests peacefully."
        )
        dm_with_agent._dm_agent = mock_agent

        # Call the narration
        dm_with_agent._narrate_from_context(context, "Test Fighter")

        # Verify narrate_resolved_action was called with damage_taken=0
        # (NOT damage_taken=10 from healing)
        mock_agent.narrate_resolved_action.assert_called_once()
        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        assert call_kwargs["damage_taken"] == 0, (
            f"damage_taken should be 0, not from healing_done. "
            f"Got: {call_kwargs['damage_taken']}"
        )
        assert call_kwargs["damage_dealt"] == 0

    def test_damage_taken_from_damage_dealt_to_self(self, dm_with_agent):
        """
        damage_taken should be the damage dealt TO the actor (self).
        """
        # Context where actor takes damage from a hazard
        context = NarrationContext(
            action_category=ActionCategory.HAZARD,
            action_type=ActionType.NARRATIVE_ACTION,  # Generic action for hazard
            player_input="Fell into a pit",
            success=False,
            damage_dealt={"test_fighter_1": 8},  # Actor took 8 damage
            healing_done={},
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The fighter crashes to the ground."
        )
        dm_with_agent._dm_agent = mock_agent

        dm_with_agent._narrate_from_context(context, "Test Fighter")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        # Actor took 8 damage
        assert call_kwargs["damage_taken"] == 8
        # No damage dealt to others
        assert call_kwargs["damage_dealt"] == 0

    def test_damage_dealt_to_others(self, dm_with_agent):
        """
        damage_dealt should be damage dealt to targets OTHER than actor.
        """
        # Context where actor deals damage to an enemy
        context = NarrationContext(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            player_input="Attack the goblin",
            success=True,
            damage_dealt={"goblin_1": 12},  # Enemy took 12 damage
            healing_done={},
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="The fighter strikes the goblin!"
        )
        dm_with_agent._dm_agent = mock_agent

        dm_with_agent._narrate_from_context(context, "Test Fighter")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        # Actor took no damage
        assert call_kwargs["damage_taken"] == 0
        # Actor dealt 12 damage to the goblin
        assert call_kwargs["damage_dealt"] == 12

    def test_mixed_damage_dealt_and_taken(self, dm_with_agent):
        """
        Test scenario where actor deals damage AND takes damage.
        """
        # Context where actor deals damage but also takes damage (e.g., trap)
        context = NarrationContext(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            player_input="Attack with risky maneuver",
            success=True,
            damage_dealt={
                "goblin_1": 15,  # Enemy took 15 damage
                "test_fighter_1": 5,  # Actor took 5 damage (recoil/trap)
            },
            healing_done={},
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="A fierce exchange!"
        )
        dm_with_agent._dm_agent = mock_agent

        dm_with_agent._narrate_from_context(context, "Test Fighter")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        # Actor took 5 damage
        assert call_kwargs["damage_taken"] == 5
        # Actor dealt 15 damage to others (total 20 - self 5 = 15)
        assert call_kwargs["damage_dealt"] == 15

    def test_healing_does_not_affect_damage(self, dm_with_agent):
        """
        Healing should be completely separate from damage computation.
        """
        # Actor takes damage AND receives healing in same context
        context = NarrationContext(
            action_category=ActionCategory.HAZARD,
            action_type=ActionType.NARRATIVE_ACTION,  # Generic action for hazard
            player_input="Fall but cushioned by magic",
            success=True,
            damage_dealt={"test_fighter_1": 6},  # Took 6 damage
            healing_done={"test_fighter_1": 4},  # Also healed 4
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="Cushioned landing."
        )
        dm_with_agent._dm_agent = mock_agent

        dm_with_agent._narrate_from_context(context, "Test Fighter")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        # damage_taken should be 6 (from damage_dealt to self)
        # NOT 4 (from healing_done) or 10 (combined)
        assert call_kwargs["damage_taken"] == 6
        assert call_kwargs["damage_dealt"] == 0


class TestUnknownActorFallback:
    """Test behavior when actor cannot be identified."""

    def test_unknown_character_name(self, dm_with_agent):
        """
        When character_name doesn't match any known character,
        assume all damage was dealt to others.
        """
        context = NarrationContext(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            player_input="Attack",
            success=True,
            damage_dealt={"some_target": 10},
            healing_done={},
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="Attack lands."
        )
        dm_with_agent._dm_agent = mock_agent

        # Use a character name that doesn't exist
        dm_with_agent._narrate_from_context(context, "Unknown Character")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        # Since we can't identify the actor, assume no damage taken
        assert call_kwargs["damage_taken"] == 0
        # All damage assumed dealt to others
        assert call_kwargs["damage_dealt"] == 10


class TestEdgeCases:
    """Test edge cases for damage computation."""

    def test_empty_damage_dicts(self, dm_with_agent):
        """Empty damage dicts should result in zeros."""
        context = NarrationContext(
            action_category=ActionCategory.EXPLORATION,
            action_type=ActionType.SEARCH,
            player_input="Search the room",
            success=True,
            damage_dealt={},
            healing_done={},
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="You find nothing."
        )
        dm_with_agent._dm_agent = mock_agent

        dm_with_agent._narrate_from_context(context, "Test Fighter")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        assert call_kwargs["damage_taken"] == 0
        assert call_kwargs["damage_dealt"] == 0

    def test_multiple_targets_damage(self, dm_with_agent):
        """Damage to multiple targets should sum correctly."""
        context = NarrationContext(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            player_input="Sweeping attack",
            success=True,
            damage_dealt={
                "goblin_1": 8,
                "goblin_2": 6,
                "goblin_3": 4,
            },
            healing_done={},
        )

        mock_agent = MagicMock()
        mock_agent.narrate_resolved_action.return_value = MagicMock(
            success=True,
            content="Sweeping strike!"
        )
        dm_with_agent._dm_agent = mock_agent

        dm_with_agent._narrate_from_context(context, "Test Fighter")

        call_kwargs = mock_agent.narrate_resolved_action.call_args.kwargs

        assert call_kwargs["damage_taken"] == 0
        # Total damage dealt: 8 + 6 + 4 = 18
        assert call_kwargs["damage_dealt"] == 18

    def test_no_dm_agent_returns_none(self, dm_with_agent):
        """When dm_agent is None, should return None."""
        dm_with_agent._dm_agent = None

        context = NarrationContext(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            player_input="Attack",
            success=True,
            damage_dealt={"goblin": 10},
            healing_done={},
        )

        result = dm_with_agent._narrate_from_context(context, "Test Fighter")

        assert result is None
