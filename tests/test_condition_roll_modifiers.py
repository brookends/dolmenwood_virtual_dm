"""
Tests for CONDITION_ROLL_MODIFIERS application to checks, saves, and hazards.

These tests verify that:
- Condition modifiers are correctly applied to saving throws
- Condition modifiers are correctly applied to ability checks
- Restless sleep prevents HP recovery and spell memorization
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import (
    CharacterState,
    Condition,
    ConditionType,
    CONDITION_ROLL_MODIFIERS,
    get_condition_roll_modifier,
)


class TestConditionRollModifiers:
    """Tests for condition roll modifier values."""

    def test_exhausted_has_saving_throw_penalty(self):
        """Verify exhausted condition has -1 to saving throws."""
        assert get_condition_roll_modifier("exhausted", "saving_throws") == -1

    def test_exhausted_has_all_rolls_penalty(self):
        """Verify exhausted condition has -1 to all rolls."""
        assert get_condition_roll_modifier("exhausted", "all_rolls") == -1

    def test_exhausted_has_ability_check_penalty(self):
        """Verify exhausted condition has -1 to ability checks."""
        assert get_condition_roll_modifier("exhausted", "ability_checks") == -1

    def test_poisoned_has_saving_throw_penalty(self):
        """Verify poisoned condition has -2 to saving throws."""
        assert get_condition_roll_modifier("poisoned", "saving_throws") == -2

    def test_restless_sleep_has_no_hp_recovery(self):
        """Verify restless_sleep blocks HP recovery."""
        assert CONDITION_ROLL_MODIFIERS["restless_sleep"]["hp_recovery"] == 0

    def test_restless_sleep_blocks_spell_memorization(self):
        """Verify restless_sleep blocks spell memorization."""
        assert CONDITION_ROLL_MODIFIERS["restless_sleep"]["spell_memorization"] is False

    def test_nauseated_has_saving_throw_penalty(self):
        """Verify nauseated condition has -1 to saving throws."""
        assert get_condition_roll_modifier("nauseated", "saving_throws") == -1

    def test_nauseated_has_attack_roll_penalty(self):
        """Verify nauseated condition has -1 to attack rolls."""
        assert get_condition_roll_modifier("nauseated", "attack_rolls") == -1

    def test_nauseated_removal_method(self):
        """Verify nauseated condition is removed by leaving the area."""
        assert CONDITION_ROLL_MODIFIERS["nauseated"]["removal"] == "leave_area"


class TestCharacterConditionModifierIntegration:
    """Tests for get_total_condition_modifier on CharacterState."""

    @pytest.fixture
    def character(self):
        """Create a test character."""
        return CharacterState(
            character_id="test_char",
            name="Test Fighter",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )

    def test_no_conditions_no_modifier(self, character):
        """Verify no modifier when character has no conditions."""
        assert character.get_total_condition_modifier("saving_throws") == 0
        assert character.get_total_condition_modifier("ability_checks") == 0

    def test_exhausted_applies_saving_throw_penalty(self, character):
        """Verify exhausted condition applies -1 to saving throws."""
        character.conditions.append(
            Condition(condition_type=ConditionType.EXHAUSTED, source="test")
        )
        assert character.get_total_condition_modifier("saving_throws") == -1

    def test_exhausted_applies_ability_check_penalty(self, character):
        """Verify exhausted condition applies -1 to ability checks."""
        character.conditions.append(
            Condition(condition_type=ConditionType.EXHAUSTED, source="test")
        )
        assert character.get_total_condition_modifier("ability_checks") == -1

    def test_multiple_conditions_stack(self, character):
        """Verify multiple conditions stack their modifiers."""
        # Add exhausted (-1 saving_throws)
        character.conditions.append(
            Condition(condition_type=ConditionType.EXHAUSTED, source="test")
        )
        # Add poisoned (-2 saving_throws)
        character.conditions.append(
            Condition(condition_type=ConditionType.POISONED, source="test")
        )
        # Total should be -3
        assert character.get_total_condition_modifier("saving_throws") == -3

    def test_nauseated_applies_saving_throw_penalty(self, character):
        """Verify nauseated condition applies -1 to saving throws."""
        character.conditions.append(
            Condition(condition_type=ConditionType.NAUSEATED, source="charnel_stench")
        )
        assert character.get_total_condition_modifier("saving_throws") == -1

    def test_nauseated_applies_attack_roll_penalty(self, character):
        """Verify nauseated condition applies -1 to attack rolls."""
        character.conditions.append(
            Condition(condition_type=ConditionType.NAUSEATED, source="charnel_stench")
        )
        assert character.get_total_condition_modifier("attack_rolls") == -1

    def test_nauseated_stacks_with_other_conditions(self, character):
        """Verify nauseated stacks with other conditions."""
        # Add nauseated (-1 saving_throws)
        character.conditions.append(
            Condition(condition_type=ConditionType.NAUSEATED, source="charnel_stench")
        )
        # Add exhausted (-1 saving_throws)
        character.conditions.append(
            Condition(condition_type=ConditionType.EXHAUSTED, source="nightmares")
        )
        # Total should be -2
        assert character.get_total_condition_modifier("saving_throws") == -2


class TestSavingThrowConditionModifier:
    """Tests for saving throw condition modifier application."""

    @pytest.fixture
    def character_with_save(self):
        """Create a character with saving throws."""
        char = CharacterState(
            character_id="test_char",
            name="Test Fighter",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )
        # Set saving throws (target 14 for doom)
        char.saving_throws = {"doom": 14, "spell": 15, "ray": 14, "hold": 13, "blast": 16}
        return char

    def test_exhausted_reduces_save_result(self, character_with_save):
        """
        Deterministic test: character with exhausted makes saving throw with reduced modifier.

        Given:
        - Character has exhausted condition (-1 to saving throws)
        - Character makes a doom save (target 14)
        - Dice roll is mocked to return 14

        Expected:
        - Total = 14 (roll) + 0 (modifier) + -1 (condition) = 13
        - Result should be FAIL (13 < 14)
        """
        character_with_save.conditions.append(
            Condition(condition_type=ConditionType.EXHAUSTED, source="magic")
        )

        # Mock dice roll to return exactly 14
        with patch("src.data_models.DiceRoller.roll_d20") as mock_roll:
            mock_roll.return_value = MagicMock(total=14)

            roll_total, success = character_with_save.make_saving_throw("doom", modifier=0)

            # Roll was 14, condition penalty is -1, so total is 13
            # Target is 14, so 13 < 14 = fail
            assert roll_total == 13
            assert success is False

    def test_save_without_condition_succeeds(self, character_with_save):
        """Verify save succeeds without condition penalty."""
        # Mock dice roll to return exactly 14
        with patch("src.data_models.DiceRoller.roll_d20") as mock_roll:
            mock_roll.return_value = MagicMock(total=14)

            roll_total, success = character_with_save.make_saving_throw("doom", modifier=0)

            # Roll was 14, no condition penalty, target is 14
            # 14 >= 14 = success
            assert roll_total == 14
            assert success is True

    def test_poisoned_gives_larger_penalty(self, character_with_save):
        """Verify poisoned condition gives -2 penalty to saves."""
        character_with_save.conditions.append(
            Condition(condition_type=ConditionType.POISONED, source="venom")
        )

        with patch("src.data_models.DiceRoller.roll_d20") as mock_roll:
            mock_roll.return_value = MagicMock(total=16)

            roll_total, success = character_with_save.make_saving_throw("doom", modifier=0)

            # Roll was 16, condition penalty is -2, so total is 14
            # Target is 14, so 14 >= 14 = success
            assert roll_total == 14
            assert success is True

    def test_nauseated_reduces_save_result(self, character_with_save):
        """
        Deterministic test: character with nauseated makes saving throw with reduced modifier.

        Given:
        - Character has nauseated condition (-1 to saving throws)
        - Character makes a doom save (target 14)
        - Dice roll is mocked to return 14

        Expected:
        - Total = 14 (roll) + 0 (modifier) + -1 (condition) = 13
        - Result should be FAIL (13 < 14)
        """
        character_with_save.conditions.append(
            Condition(condition_type=ConditionType.NAUSEATED, source="charnel_stench")
        )

        # Mock dice roll to return exactly 14
        with patch("src.data_models.DiceRoller.roll_d20") as mock_roll:
            mock_roll.return_value = MagicMock(total=14)

            roll_total, success = character_with_save.make_saving_throw("doom", modifier=0)

            # Roll was 14, condition penalty is -1, so total is 13
            # Target is 14, so 13 < 14 = fail
            assert roll_total == 13
            assert success is False


class TestRestlessSleepEffects:
    """Tests for restless_sleep condition effects."""

    @pytest.fixture
    def character(self):
        """Create a test character."""
        return CharacterState(
            character_id="test_char",
            name="Test Wizard",
            character_class="Magic-User",
            level=3,
            ability_scores={"STR": 8, "INT": 16, "WIS": 14, "DEX": 10, "CON": 10, "CHA": 12},
            hp_current=8,
            hp_max=8,
            armor_class=10,
            base_speed=40,
        )

    def test_can_recover_hp_without_condition(self, character):
        """Verify character can recover HP without restless_sleep."""
        assert character.can_recover_hp() is True

    def test_cannot_recover_hp_with_restless_sleep(self, character):
        """Verify restless_sleep prevents HP recovery."""
        character.conditions.append(
            Condition(condition_type=ConditionType.RESTLESS_SLEEP, source="monolith")
        )
        assert character.can_recover_hp() is False

    def test_can_memorize_spells_without_condition(self, character):
        """Verify character can memorize spells without restless_sleep."""
        assert character.can_memorize_spells() is True

    def test_cannot_memorize_spells_with_restless_sleep(self, character):
        """Verify restless_sleep prevents spell memorization."""
        character.conditions.append(
            Condition(condition_type=ConditionType.RESTLESS_SLEEP, source="monolith")
        )
        assert character.can_memorize_spells() is False

    def test_hp_recovery_modifier_normal(self, character):
        """Verify HP recovery modifier is 1.0 without conditions."""
        assert character.get_hp_recovery_modifier() == 1.0

    def test_hp_recovery_modifier_with_restless_sleep(self, character):
        """Verify HP recovery modifier is 0.0 with restless_sleep."""
        character.conditions.append(
            Condition(condition_type=ConditionType.RESTLESS_SLEEP, source="monolith")
        )
        assert character.get_hp_recovery_modifier() == 0.0


class TestHazardResolverConditionModifiers:
    """Tests for condition modifier application in hazard resolution."""

    def test_ability_check_with_exhausted_condition(self):
        """Verify ability check applies exhausted condition penalty."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=12)
        engine.narrative_resolver = MagicMock()

        # Create character with dexterity 14 and exhausted condition
        char = CharacterState(
            character_id="test_char",
            name="Test Thief",
            character_class="Thief",
            level=3,
            ability_scores={"STR": 10, "INT": 12, "WIS": 10, "DEX": 14, "CON": 12, "CHA": 10},
            hp_current=12,
            hp_max=12,
            armor_class=12,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.EXHAUSTED, source="nightmare")
        )

        # Hazard with dexterity check
        hazard = {
            "hazard_type": "environmental",
            "check_type": "dexterity",
            "description": "Climbing the wall",
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        # Roll was 12, exhausted penalty is -1, so effective roll is 13
        # (For ability checks, penalties INCREASE the roll since success is <= ability)
        # So roll_total = 12 - 0 (modifier) - (-1) (condition) = 13
        # Success if 13 <= 14 (dexterity) = True
        assert result.success is True


class TestCombatAttackConditionModifiers:
    """Tests for condition modifier application in combat attack rolls."""

    @pytest.fixture
    def controller(self):
        """Create a GlobalController with test character."""
        from src.game_state.global_controller import GlobalController

        controller = GlobalController()
        char = CharacterState(
            character_id="fighter_1",
            name="Test Fighter",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )
        controller.add_character(char)
        return controller

    def test_no_condition_no_attack_modifier(self, controller):
        """Verify no attack modifier when character has no conditions."""
        modifier = controller.get_condition_attack_modifier("fighter_1")
        assert modifier == 0

    def test_nauseated_applies_attack_penalty(self, controller):
        """Verify nauseated condition applies -1 to attack rolls."""
        controller.apply_condition("fighter_1", "nauseated", source="charnel_stench")
        modifier = controller.get_condition_attack_modifier("fighter_1")
        assert modifier == -1

    def test_poisoned_applies_attack_penalty(self, controller):
        """Verify poisoned condition applies -2 to attack rolls."""
        controller.apply_condition("fighter_1", "poisoned", source="venom")
        modifier = controller.get_condition_attack_modifier("fighter_1")
        assert modifier == -2

    def test_exhausted_applies_attack_penalty(self, controller):
        """Verify exhausted condition applies -1 to attack rolls."""
        controller.apply_condition("fighter_1", "exhausted", source="nightmares")
        modifier = controller.get_condition_attack_modifier("fighter_1")
        assert modifier == -1

    def test_blinded_applies_attack_penalty(self, controller):
        """Verify blinded condition applies -4 to attack rolls (special case)."""
        controller.apply_condition("fighter_1", "blinded", source="spell")
        modifier = controller.get_condition_attack_modifier("fighter_1")
        assert modifier == -4

    def test_multiple_conditions_stack(self, controller):
        """Verify multiple conditions stack their attack penalties."""
        controller.apply_condition("fighter_1", "nauseated", source="charnel_stench")
        controller.apply_condition("fighter_1", "exhausted", source="nightmares")
        modifier = controller.get_condition_attack_modifier("fighter_1")
        # nauseated (-1) + exhausted (-1) = -2
        assert modifier == -2

    def test_nauseated_plus_blinded_stack(self, controller):
        """Verify nauseated and blinded conditions stack."""
        controller.apply_condition("fighter_1", "nauseated", source="charnel_stench")
        controller.apply_condition("fighter_1", "blinded", source="spell")
        modifier = controller.get_condition_attack_modifier("fighter_1")
        # nauseated (-1) + blinded (-4) = -5
        assert modifier == -5
