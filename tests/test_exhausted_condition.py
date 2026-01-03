"""
Tests for the exhausted condition.

The exhausted condition is applied when characters fail a Save vs Spell
during night in hex 0105, causing -1 to all rolls until rest elsewhere.
"""

import pytest


class TestExhaustedConditionType:
    """Tests for exhausted condition in ConditionType enum."""

    def test_exhausted_exists(self):
        """Verify exhausted condition exists."""
        from src.data_models import ConditionType

        assert ConditionType.EXHAUSTED.value == "exhausted"

    def test_exhausted_in_blocked_actions(self):
        """Verify exhausted has entry in CONDITION_BLOCKED_ACTIONS."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS

        assert "exhausted" in CONDITION_BLOCKED_ACTIONS
        # Exhaustion doesn't block actions
        assert CONDITION_BLOCKED_ACTIONS["exhausted"]["blocked"] == []


class TestConditionRollModifiers:
    """Tests for condition-based roll modifiers."""

    def test_exhausted_modifier_exists(self):
        """Verify exhausted condition has modifiers defined."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert "exhausted" in CONDITION_ROLL_MODIFIERS
        assert CONDITION_ROLL_MODIFIERS["exhausted"]["all_rolls"] == -1

    def test_get_condition_roll_modifier_exhausted(self):
        """Verify get_condition_roll_modifier returns -1 for exhausted."""
        from src.data_models import get_condition_roll_modifier

        # All roll types should return -1 for exhausted
        assert get_condition_roll_modifier("exhausted", "all_rolls") == -1
        assert get_condition_roll_modifier("exhausted", "attack_rolls") == -1
        assert get_condition_roll_modifier("exhausted", "saving_throws") == -1
        assert get_condition_roll_modifier("exhausted", "ability_checks") == -1

    def test_get_condition_roll_modifier_unknown(self):
        """Verify unknown condition returns 0."""
        from src.data_models import get_condition_roll_modifier

        assert get_condition_roll_modifier("unknown_condition", "all_rolls") == 0

    def test_get_condition_roll_modifier_specific_type(self):
        """Verify specific roll types are returned correctly."""
        from src.data_models import get_condition_roll_modifier

        # Frightened only affects attack rolls
        assert get_condition_roll_modifier("frightened", "attack_rolls") == -2
        assert get_condition_roll_modifier("frightened", "all_rolls") == 0

    def test_exhausted_removal_method(self):
        """Verify exhausted has correct removal method."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert CONDITION_ROLL_MODIFIERS["exhausted"]["removal"] == "rest_elsewhere"


class TestHex0105NightHazardIntegration:
    """Integration tests for hex 0105 exhausted condition application."""

    def test_night_hazard_applies_exhausted(self):
        """Verify hex 0105 sleep hazard can apply exhausted condition."""
        from src.data_models import ConditionType

        # The hazard definition from hex 0105
        hazard = {
            "trigger": "sleep",
            "save_type": "spell",
            "description": "Characters sleeping here must Save Versus Spell or awaken exhausted",
            "on_fail": {
                "condition": "exhausted",
                "duration_dice": "1",
                "duration_unit": "days",
                "effect": "-1 to all rolls until rest elsewhere",
            },
        }

        # Verify the condition is a valid ConditionType
        condition = hazard["on_fail"]["condition"]
        assert condition == ConditionType.EXHAUSTED.value

    def test_exhausted_has_correct_message(self):
        """Verify exhausted condition has informative message."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS

        message = CONDITION_BLOCKED_ACTIONS["exhausted"]["message"]
        assert "-1 to all rolls" in message
        assert "rest" in message.lower()


class TestOtherConditionModifiers:
    """Tests for other conditions with roll modifiers."""

    def test_poisoned_modifier(self):
        """Verify poisoned condition has correct modifiers."""
        from src.data_models import get_condition_roll_modifier

        assert get_condition_roll_modifier("poisoned", "attack_rolls") == -2
        assert get_condition_roll_modifier("poisoned", "saving_throws") == -2

    def test_hasted_bonuses(self):
        """Verify hasted condition gives bonuses."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert CONDITION_ROLL_MODIFIERS["hasted"]["initiative"] == 2
        assert CONDITION_ROLL_MODIFIERS["hasted"]["armor_class"] == 2

    def test_starving_penalty(self):
        """Verify starving has severe penalty."""
        from src.data_models import get_condition_roll_modifier

        assert get_condition_roll_modifier("starving", "all_rolls") == -2
