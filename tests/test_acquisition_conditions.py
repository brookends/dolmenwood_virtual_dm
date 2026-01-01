"""
Tests for Acquisition Condition System.

Tests the condition parser, evaluation, and integration with item acquisition.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.game_state.condition_parser import (
    AcquisitionConditionParser,
    ConditionType,
    ParsedCondition,
    check_acquisition_condition,
    get_condition_parser,
)
from src.game_state.session_manager import SessionManager, NPCStateDelta


class TestConditionParser:
    """Tests for the AcquisitionConditionParser class."""

    def test_parse_killed_or_removed(self):
        """Test parsing 'must be killed or removed' condition."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Dredger must be killed or removed")

        assert result is not None
        assert result.condition_type == ConditionType.NPC_DEAD_OR_REMOVED
        assert result.target_name == "Dredger"
        assert result.original_text == "Dredger must be killed or removed"

    def test_parse_killed_or_removed_with_the(self):
        """Test parsing with 'The' prefix."""
        parser = AcquisitionConditionParser()
        result = parser.parse("The Dredger must be killed or removed")

        assert result is not None
        assert result.condition_type == ConditionType.NPC_DEAD_OR_REMOVED
        assert result.target_name == "The Dredger"

    def test_parse_defeated(self):
        """Test parsing 'must be defeated' condition."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Goblin King must be defeated")

        assert result is not None
        assert result.condition_type == ConditionType.NPC_DEAD
        assert result.target_name == "Goblin King"

    def test_parse_slain(self):
        """Test parsing 'must be slain' condition."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Dragon must be slain")

        assert result is not None
        assert result.condition_type == ConditionType.NPC_DEAD
        assert result.target_name == "Dragon"

    def test_parse_removed(self):
        """Test parsing 'must be removed' condition."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Ghost must be removed")

        assert result is not None
        assert result.condition_type == ConditionType.NPC_REMOVED
        assert result.target_name == "Ghost"

    def test_parse_banished(self):
        """Test parsing 'must be banished' condition."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Demon must be banished")

        assert result is not None
        assert result.condition_type == ConditionType.NPC_REMOVED
        assert result.target_name == "Demon"

    def test_parse_item_obtained(self):
        """Test parsing 'must be obtained' condition."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Key of Ages must be obtained")

        assert result is not None
        assert result.condition_type == ConditionType.ITEM_OBTAINED
        assert result.target_name == "Key of Ages"

    def test_parse_custom_condition(self):
        """Test parsing unknown condition falls back to custom."""
        parser = AcquisitionConditionParser()
        result = parser.parse("Some random condition text")

        assert result is not None
        assert result.condition_type == ConditionType.CUSTOM
        assert result.target_name == "Some random condition text"

    def test_parse_empty_returns_none(self):
        """Test empty string returns None."""
        parser = AcquisitionConditionParser()
        assert parser.parse("") is None
        assert parser.parse(None) is None

    def test_case_insensitive_parsing(self):
        """Test condition parsing is case insensitive."""
        parser = AcquisitionConditionParser()

        result1 = parser.parse("DREDGER MUST BE KILLED OR REMOVED")
        result2 = parser.parse("dredger must be killed or removed")

        assert result1.condition_type == ConditionType.NPC_DEAD_OR_REMOVED
        assert result2.condition_type == ConditionType.NPC_DEAD_OR_REMOVED


class TestConditionEvaluation:
    """Tests for condition evaluation."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create a session manager for testing."""
        sm = SessionManager(tmp_path / "sessions")
        sm.new_session("Test Session")
        return sm

    def test_evaluate_npc_dead_satisfied(self, session_manager):
        """Test condition satisfied when NPC is dead."""
        parser = AcquisitionConditionParser()
        condition = parser.parse("Dredger must be killed or removed")

        # Mark NPC as dead
        session_manager.mark_npc_dead("0104", "dredger")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is True
        assert "slain" in reason.lower()

    def test_evaluate_npc_removed_satisfied(self, session_manager):
        """Test condition satisfied when NPC is removed."""
        parser = AcquisitionConditionParser()
        condition = parser.parse("Dredger must be killed or removed")

        # Mark NPC as removed
        session_manager.mark_npc_removed("0104", "dredger")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is True
        assert "driven away" in reason.lower()

    def test_evaluate_npc_dead_or_removed_not_satisfied(self, session_manager):
        """Test condition not satisfied when NPC is still present."""
        parser = AcquisitionConditionParser()
        condition = parser.parse("Dredger must be killed or removed")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is False
        assert "still blocks" in reason.lower()

    def test_evaluate_npc_dead_only(self, session_manager):
        """Test 'must be defeated' requires death, not removal."""
        parser = AcquisitionConditionParser()
        condition = parser.parse("Goblin King must be defeated")

        # Only removed, not killed
        session_manager.mark_npc_removed("0104", "goblin_king")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is False

        # Now kill
        session_manager.mark_npc_dead("0104", "goblin_king")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is True

    def test_evaluate_npc_removed_only(self, session_manager):
        """Test 'must be removed' requires removal, not death."""
        parser = AcquisitionConditionParser()
        condition = parser.parse("Ghost must be removed")

        # Only killed, not removed
        session_manager.mark_npc_dead("0104", "ghost")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is False

        # Now remove
        session_manager.mark_npc_removed("0104", "ghost")

        is_satisfied, reason = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is True

    def test_npc_id_normalization(self, session_manager):
        """Test NPC name to ID normalization handles 'The' prefix."""
        parser = AcquisitionConditionParser()
        condition = parser.parse("The Dredger must be killed or removed")

        # Mark with normalized ID
        session_manager.mark_npc_dead("0104", "dredger")

        is_satisfied, _ = parser.evaluate(
            condition, "0104", session_manager
        )

        assert is_satisfied is True


class TestCheckAcquisitionCondition:
    """Tests for the convenience function."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create a session manager for testing."""
        sm = SessionManager(tmp_path / "sessions")
        sm.new_session("Test Session")
        return sm

    def test_check_no_condition(self, session_manager):
        """Test None/empty condition always passes."""
        is_satisfied, reason = check_acquisition_condition(
            None, "0104", session_manager
        )
        assert is_satisfied is True

        is_satisfied, reason = check_acquisition_condition(
            "", "0104", session_manager
        )
        assert is_satisfied is True

    def test_check_condition_satisfied(self, session_manager):
        """Test condition check when satisfied."""
        session_manager.mark_npc_dead("0104", "dredger")

        is_satisfied, reason = check_acquisition_condition(
            "Dredger must be killed or removed",
            "0104",
            session_manager,
        )

        assert is_satisfied is True

    def test_check_condition_not_satisfied(self, session_manager):
        """Test condition check when not satisfied."""
        is_satisfied, reason = check_acquisition_condition(
            "Dredger must be killed or removed",
            "0104",
            session_manager,
        )

        assert is_satisfied is False
        assert "Dredger" in reason


class TestSessionManagerNPCMethods:
    """Tests for NPCStateDelta marking methods."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create a session manager for testing."""
        sm = SessionManager(tmp_path / "sessions")
        sm.new_session("Test Session")
        return sm

    def test_mark_npc_dead(self, session_manager):
        """Test marking NPC as dead."""
        session_manager.mark_npc_dead("0104", "dredger")

        assert session_manager.is_npc_dead("0104", "dredger") is True
        assert session_manager.is_npc_removed("0104", "dredger") is False
        assert session_manager.is_npc_dead_or_removed("0104", "dredger") is True

    def test_mark_npc_removed(self, session_manager):
        """Test marking NPC as removed."""
        session_manager.mark_npc_removed("0104", "dredger")

        assert session_manager.is_npc_dead("0104", "dredger") is False
        assert session_manager.is_npc_removed("0104", "dredger") is True
        assert session_manager.is_npc_dead_or_removed("0104", "dredger") is True

    def test_mark_both_dead_and_removed(self, session_manager):
        """Test marking NPC as both dead and removed."""
        session_manager.mark_npc_dead("0104", "dredger")
        session_manager.mark_npc_removed("0104", "dredger")

        assert session_manager.is_npc_dead("0104", "dredger") is True
        assert session_manager.is_npc_removed("0104", "dredger") is True
        assert session_manager.is_npc_dead_or_removed("0104", "dredger") is True

    def test_different_npcs_independent(self, session_manager):
        """Test different NPCs are tracked independently."""
        session_manager.mark_npc_dead("0104", "dredger")
        session_manager.mark_npc_removed("0104", "ghost")

        assert session_manager.is_npc_dead("0104", "dredger") is True
        assert session_manager.is_npc_removed("0104", "dredger") is False

        assert session_manager.is_npc_dead("0104", "ghost") is False
        assert session_manager.is_npc_removed("0104", "ghost") is True

    def test_different_hexes_independent(self, session_manager):
        """Test NPCs in different hexes are tracked independently."""
        session_manager.mark_npc_dead("0104", "goblin")
        session_manager.mark_npc_dead("0105", "goblin")
        session_manager.mark_npc_removed("0105", "goblin")

        assert session_manager.is_npc_dead("0104", "goblin") is True
        assert session_manager.is_npc_removed("0104", "goblin") is False

        assert session_manager.is_npc_dead("0105", "goblin") is True
        assert session_manager.is_npc_removed("0105", "goblin") is True


class TestNPCStateDeltaSerialization:
    """Tests for NPCStateDelta serialization with is_removed field."""

    def test_to_dict_includes_is_removed(self):
        """Test to_dict includes is_removed field."""
        delta = NPCStateDelta(
            npc_id="dredger",
            hex_id="0104",
            is_dead=True,
            is_removed=True,
        )

        data = delta.to_dict()

        assert data["is_dead"] is True
        assert data["is_removed"] is True

    def test_from_dict_loads_is_removed(self):
        """Test from_dict loads is_removed field."""
        data = {
            "npc_id": "dredger",
            "hex_id": "0104",
            "is_dead": False,
            "is_removed": True,
        }

        delta = NPCStateDelta.from_dict(data)

        assert delta.is_dead is False
        assert delta.is_removed is True

    def test_from_dict_defaults_is_removed_false(self):
        """Test from_dict defaults is_removed to False for old data."""
        data = {
            "npc_id": "dredger",
            "hex_id": "0104",
            # is_removed not present (old data format)
        }

        delta = NPCStateDelta.from_dict(data)

        assert delta.is_removed is False


class TestCustomConditions:
    """Tests for extensible custom conditions."""

    def test_register_custom_pattern(self):
        """Test registering a custom pattern."""
        import re
        parser = AcquisitionConditionParser()

        parser.register_pattern(
            re.compile(r"^Quest (.+?) must be completed$", re.IGNORECASE),
            ConditionType.CUSTOM,
            {"custom_type": "quest_completed"},
        )

        result = parser.parse("Quest The Dragon's Bane must be completed")

        assert result is not None
        assert result.condition_type == ConditionType.CUSTOM
        assert result.target_name == "The Dragon's Bane"
        assert result.metadata.get("custom_type") == "quest_completed"

    def test_register_custom_evaluator(self):
        """Test registering a custom evaluator."""
        parser = AcquisitionConditionParser()

        def quest_evaluator(condition, hex_id, session_manager):
            # Simple mock evaluator
            return (True, "Quest completed!")

        parser.register_evaluator("quest_check", quest_evaluator)

        condition = ParsedCondition(
            condition_type=ConditionType.CUSTOM,
            target_name="Some Quest",
            original_text="Some Quest must be completed",
        )

        is_satisfied, reason = parser.evaluate(
            condition, "0104", MagicMock()
        )

        assert is_satisfied is True
        assert reason == "Quest completed!"
