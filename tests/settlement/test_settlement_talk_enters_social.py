"""
Tests for settlement NPC talk entering SOCIAL_INTERACTION state.

Phase 2.1: Verify that settlement:talk_npc uses the same canonical
SOCIAL_INTERACTION pathway as hex NPC conversations.
"""

import pytest

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


@pytest.fixture
def dm_in_settlement(seeded_dice, test_character):
    """Create VirtualDM in settlement state."""
    reset_registry()

    config = GameConfig(
        llm_provider="mock",
        enable_narration=False,
        load_content=False,
    )

    dm = VirtualDM(
        config=config,
        initial_state=GameState.SETTLEMENT_EXPLORATION,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=10, minute=0),
    )

    dm.controller.add_character(test_character)
    return dm


class TestSettlementTalkEntersSocial:
    """Test that settlement:talk_npc transitions to SOCIAL_INTERACTION."""

    def test_talk_npc_transitions_to_social_interaction(self, dm_in_settlement):
        """settlement:talk_npc should transition to SOCIAL_INTERACTION state."""
        reset_registry()
        registry = get_default_registry()

        assert dm_in_settlement.current_state == GameState.SETTLEMENT_EXPLORATION

        # Mock the settlement engine to return NPC data
        class MockSettlement:
            def execute_action(self, action_id, params):
                if action_id == "settlement:talk":
                    return {
                        "success": True,
                        "npc": {
                            "npc_id": "innkeeper_01",
                            "name": "Goodwife Margery",
                        },
                    }
                return {"success": True}

            def get_active_settlement(self):
                class Settlement:
                    settlement_id = "prigwort"
                    name = "Prigwort"
                return Settlement()

        dm_in_settlement.settlement = MockSettlement()

        # Execute settlement:talk_npc
        result = registry.execute(
            dm_in_settlement,
            "settlement:talk_npc",
            {"npc_id": "innkeeper_01"}
        )

        assert result["success"] is True
        # State should be SOCIAL_INTERACTION
        assert dm_in_settlement.current_state == GameState.SOCIAL_INTERACTION

    def test_social_end_returns_to_settlement(self, dm_in_settlement):
        """social:end should return to SETTLEMENT_EXPLORATION state."""
        reset_registry()
        registry = get_default_registry()

        # Set up mock settlement
        class MockSettlement:
            def execute_action(self, action_id, params):
                if action_id == "settlement:talk":
                    return {
                        "success": True,
                        "npc": {
                            "npc_id": "innkeeper_01",
                            "name": "Goodwife Margery",
                        },
                    }
                return {"success": True}

            def get_active_settlement(self):
                class Settlement:
                    settlement_id = "prigwort"
                    name = "Prigwort"
                return Settlement()

        dm_in_settlement.settlement = MockSettlement()

        # Start conversation
        registry.execute(
            dm_in_settlement,
            "settlement:talk_npc",
            {"npc_id": "innkeeper_01"}
        )

        assert dm_in_settlement.current_state == GameState.SOCIAL_INTERACTION

        # End conversation
        result = registry.execute(
            dm_in_settlement,
            "social:end",
            {}
        )

        assert result["success"] is True
        # Should return to settlement
        assert dm_in_settlement.current_state == GameState.SETTLEMENT_EXPLORATION

    def test_social_context_populated_after_talk(self, dm_in_settlement):
        """After settlement:talk_npc, social_context should be populated."""
        reset_registry()
        registry = get_default_registry()

        class MockSettlement:
            def execute_action(self, action_id, params):
                if action_id == "settlement:talk":
                    return {
                        "success": True,
                        "npc": {
                            "npc_id": "innkeeper_01",
                            "name": "Goodwife Margery",
                        },
                    }
                return {"success": True}

            def get_active_settlement(self):
                class Settlement:
                    settlement_id = "prigwort"
                    name = "Prigwort"
                return Settlement()

        dm_in_settlement.settlement = MockSettlement()

        registry.execute(
            dm_in_settlement,
            "settlement:talk_npc",
            {"npc_id": "innkeeper_01"}
        )

        # Social context should exist
        social_ctx = dm_in_settlement.controller.social_context
        assert social_ctx is not None


class TestSettlementSocialActionsWork:
    """Test that social:* actions work after settlement:talk_npc."""

    def test_social_say_works_in_settlement_conversation(self, dm_in_settlement):
        """social:say should work after entering conversation from settlement."""
        reset_registry()
        registry = get_default_registry()

        class MockSettlement:
            def execute_action(self, action_id, params):
                if action_id == "settlement:talk":
                    return {
                        "success": True,
                        "npc": {
                            "npc_id": "innkeeper_01",
                            "name": "Goodwife Margery",
                        },
                    }
                return {"success": True}

            def get_active_settlement(self):
                class Settlement:
                    settlement_id = "prigwort"
                    name = "Prigwort"
                return Settlement()

        dm_in_settlement.settlement = MockSettlement()

        # Start conversation
        registry.execute(
            dm_in_settlement,
            "settlement:talk_npc",
            {"npc_id": "innkeeper_01"}
        )

        # social:say should work
        result = registry.execute(
            dm_in_settlement,
            "social:say",
            {"text": "Good day to you!"}
        )

        assert result["success"] is True
        assert "Good day" in result["message"]

    def test_social_oracle_question_works_in_settlement_conversation(self, dm_in_settlement):
        """social:oracle_question should work after entering conversation from settlement."""
        reset_registry()
        registry = get_default_registry()

        class MockSettlement:
            def execute_action(self, action_id, params):
                if action_id == "settlement:talk":
                    return {
                        "success": True,
                        "npc": {
                            "npc_id": "innkeeper_01",
                            "name": "Goodwife Margery",
                        },
                    }
                return {"success": True}

            def get_active_settlement(self):
                class Settlement:
                    settlement_id = "prigwort"
                    name = "Prigwort"
                return Settlement()

        dm_in_settlement.settlement = MockSettlement()

        # Start conversation
        registry.execute(
            dm_in_settlement,
            "settlement:talk_npc",
            {"npc_id": "innkeeper_01"}
        )

        # social:oracle_question should work
        result = registry.execute(
            dm_in_settlement,
            "social:oracle_question",
            {"question": "Is she friendly?"}
        )

        assert result["success"] is True
        assert "Oracle" in result["message"]
