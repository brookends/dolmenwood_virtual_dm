"""
Tests for Phase 2 Spell Handlers.

Tests the following condition-based spell handlers:
- Deathly Blossom (unconscious condition)
- En Croute (restrained condition)
- Awe (morale check + fleeing)
- Animal Growth (stat modification)
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    MagicType,
    DurationType,
    RangeType,
    SpellEffectType,
    ActiveSpellEffect,
)
from src.data_models import CharacterState, DiceRoller


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance with mocked controller."""
    resolver = SpellResolver()

    # Mock controller
    mock_controller = MagicMock()
    mock_controller.time_tracker.days = 10
    mock_controller.get_character.return_value = None
    mock_controller.apply_condition = MagicMock()
    resolver._controller = mock_controller

    return resolver


@pytest.fixture
def mock_caster():
    """Create a mock caster character."""
    caster = MagicMock(spec=CharacterState)
    caster.character_id = "fairy_1"
    caster.name = "Willow Glimmerleaf"
    caster.level = 5
    caster.inventory = []
    return caster


@pytest.fixture
def mock_dice_roller():
    """Create a mock dice roller with predictable results."""
    roller = MagicMock(spec=DiceRoller)
    roll_result = MagicMock()
    roll_result.total = 10
    roller.roll_d20 = MagicMock(return_value=roll_result)
    roller.roll = MagicMock(return_value=roll_result)
    return roller


# =============================================================================
# DEATHLY BLOSSOM TESTS
# =============================================================================


class TestDeathlyBlossomHandler:
    """Tests for _handle_deathly_blossom."""

    def test_deathly_blossom_creates_rose_no_targets(self, spell_resolver, mock_caster):
        """Should create rose item when no targets specified."""
        result = spell_resolver._handle_deathly_blossom(mock_caster, [], None)

        assert result["success"] is True
        assert "rose_created" in result
        assert result["rose_created"]["name"] == "Rose of Sublime Beauty"
        assert result["targets_affected"] == []

    def test_deathly_blossom_save_vs_doom(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should require Save vs Doom."""
        # Set up save to succeed (roll high)
        save_roll = MagicMock()
        save_roll.total = 20
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        result = spell_resolver._handle_deathly_blossom(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["success"] is True
        assert "target_npc" in result["targets_saved"]
        assert result["save_type"] == "doom"

    def test_deathly_blossom_failed_save_unconscious(self, spell_resolver, mock_caster, mock_dice_roller):
        """Failed save should apply unconscious condition."""
        # Set up save to fail
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        # Set up duration roll
        duration_roll = MagicMock()
        duration_roll.total = 4
        mock_dice_roller.roll = MagicMock(return_value=duration_roll)

        result = spell_resolver._handle_deathly_blossom(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["success"] is True
        assert "unconscious" in result["conditions_applied"]
        assert "target_npc" in result["targets_affected"]

    def test_deathly_blossom_duration_1d6_turns(self, spell_resolver, mock_caster, mock_dice_roller):
        """Unconscious duration should be 1d6 turns."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        duration_roll = MagicMock()
        duration_roll.total = 6
        mock_dice_roller.roll = MagicMock(return_value=duration_roll)

        result = spell_resolver._handle_deathly_blossom(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        # Check the individual result
        target_result = [r for r in result["results"] if r["target_id"] == "target_npc"][0]
        assert target_result["duration_turns"] == 6
        assert target_result["appears_dead"] is True

    def test_deathly_blossom_registers_active_effect(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should register unconscious as active spell effect."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        duration_roll = MagicMock()
        duration_roll.total = 3
        mock_dice_roller.roll = MagicMock(return_value=duration_roll)

        result = spell_resolver._handle_deathly_blossom(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        # Find the effect
        effect = next(
            (e for e in spell_resolver._active_effects if e.spell_id == "deathly_blossom"),
            None
        )
        assert effect is not None
        assert effect.duration_remaining == 3
        assert effect.mechanical_effects["condition"] == "unconscious"
        assert effect.mechanical_effects["appears_dead"] is True


# =============================================================================
# EN CROUTE TESTS
# =============================================================================


class TestEnCrouteHandler:
    """Tests for _handle_en_croute."""

    def test_en_croute_requires_target(self, spell_resolver, mock_caster):
        """Should fail if no target specified."""
        result = spell_resolver._handle_en_croute(mock_caster, [], None)

        assert result["success"] is False
        assert "no target" in result["message"].lower()

    def test_en_croute_save_vs_spell(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should allow Save vs Spell."""
        # Save succeeds
        save_roll = MagicMock()
        save_roll.total = 18
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        result = spell_resolver._handle_en_croute(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["save_succeeded"] is True

    def test_en_croute_failed_save_restrained(self, spell_resolver, mock_caster, mock_dice_roller):
        """Failed save should apply restrained condition."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        result = spell_resolver._handle_en_croute(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["save_succeeded"] is False
        assert "restrained" in result["conditions_applied"]

    def test_en_croute_strength_affects_escape_time(self, spell_resolver, mock_caster, mock_dice_roller):
        """Escape time should vary based on Strength."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        # Mock target with high strength
        mock_target = MagicMock()
        mock_target.strength = 18
        mock_target.get_saving_throw = MagicMock(return_value=0)
        spell_resolver._controller.get_character.return_value = mock_target

        result = spell_resolver._handle_en_croute(
            mock_caster, ["strong_target"], mock_dice_roller
        )

        # STR 18 should give 1 round escape time
        assert result["escape_rounds"] == 1
        assert result["target_strength"] == 18

    def test_en_croute_low_strength_longer_escape(self, spell_resolver, mock_caster, mock_dice_roller):
        """Low strength should result in longer escape time."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        # Mock target with low strength
        mock_target = MagicMock()
        mock_target.strength = 5
        mock_target.get_saving_throw = MagicMock(return_value=0)
        spell_resolver._controller.get_character.return_value = mock_target

        result = spell_resolver._handle_en_croute(
            mock_caster, ["weak_target"], mock_dice_roller
        )

        # STR 5 should give 6 rounds escape time
        assert result["escape_rounds"] == 6

    def test_en_croute_edible_property(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should indicate pastry is edible for ally escape."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        result = spell_resolver._handle_en_croute(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["narrative_context"]["edible"] is True


# =============================================================================
# AWE TESTS
# =============================================================================


class TestAweHandler:
    """Tests for _handle_awe."""

    def test_awe_requires_targets(self, spell_resolver, mock_caster):
        """Should fail if no targets specified."""
        result = spell_resolver._handle_awe(mock_caster, [], None)

        assert result["success"] is False
        assert "no targets" in result["message"].lower()

    def test_awe_hd_budget(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should respect HD budget based on caster level."""
        mock_caster.level = 3

        # Mock morale roll to fail
        morale_roll = MagicMock()
        morale_roll.total = 12  # High roll fails morale
        mock_dice_roller.roll = MagicMock(return_value=morale_roll)

        # Mock flee duration
        flee_roll = MagicMock()
        flee_roll.total = 2
        mock_dice_roller.roll.side_effect = [morale_roll, flee_roll]

        result = spell_resolver._handle_awe(
            mock_caster, ["target_1"], mock_dice_roller
        )

        assert result["hd_budget"] == 3

    def test_awe_morale_check(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should trigger morale check for affected targets."""
        mock_caster.level = 5

        # Mock morale roll - low roll passes
        morale_roll = MagicMock()
        morale_roll.total = 6
        mock_dice_roller.roll = MagicMock(return_value=morale_roll)

        result = spell_resolver._handle_awe(
            mock_caster, ["target_1"], mock_dice_roller
        )

        assert result["success"] is True
        assert "target_1" in result["targets_resisted"]

    def test_awe_failed_morale_flee(self, spell_resolver, mock_caster, mock_dice_roller):
        """Failed morale should cause fleeing."""
        mock_caster.level = 5

        # Mock morale roll - high roll fails
        morale_roll = MagicMock()
        morale_roll.total = 12
        flee_roll = MagicMock()
        flee_roll.total = 3
        mock_dice_roller.roll = MagicMock(side_effect=[morale_roll, flee_roll])

        result = spell_resolver._handle_awe(
            mock_caster, ["target_1"], mock_dice_roller
        )

        assert result["success"] is True
        assert "target_1" in result["targets_fled"]
        assert "frightened" in result["conditions_applied"]

    def test_awe_flee_duration_1d4_rounds(self, spell_resolver, mock_caster, mock_dice_roller):
        """Fleeing duration should be 1d4 rounds."""
        mock_caster.level = 5

        morale_roll = MagicMock()
        morale_roll.total = 12
        flee_roll = MagicMock()
        flee_roll.total = 4
        mock_dice_roller.roll = MagicMock(side_effect=[morale_roll, flee_roll])

        result = spell_resolver._handle_awe(
            mock_caster, ["target_1"], mock_dice_roller
        )

        target_result = [r for r in result["results"] if r["target_id"] == "target_1"][0]
        assert target_result["flee_rounds"] == 4

    def test_awe_registers_active_effect(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should register fleeing effect."""
        mock_caster.level = 5

        morale_roll = MagicMock()
        morale_roll.total = 12
        flee_roll = MagicMock()
        flee_roll.total = 2
        mock_dice_roller.roll = MagicMock(side_effect=[morale_roll, flee_roll])

        result = spell_resolver._handle_awe(
            mock_caster, ["target_1"], mock_dice_roller
        )

        effect = next(
            (e for e in spell_resolver._active_effects if e.spell_id == "awe"),
            None
        )
        assert effect is not None
        assert effect.mechanical_effects["condition"] == "frightened"
        assert effect.mechanical_effects["fleeing"] is True


# =============================================================================
# ANIMAL GROWTH TESTS
# =============================================================================


class TestAnimalGrowthHandler:
    """Tests for _handle_animal_growth."""

    def test_animal_growth_no_targets_rolls_count(self, spell_resolver, mock_caster, mock_dice_roller):
        """Without targets, should roll 1d4 for normal animal count."""
        count_roll = MagicMock()
        count_roll.total = 3
        mock_dice_roller.roll = MagicMock(return_value=count_roll)

        result = spell_resolver._handle_animal_growth(mock_caster, [], mock_dice_roller)

        assert result["success"] is True
        assert result["max_normal_animals"] == 3
        assert result["max_giant_animals"] == 1

    def test_animal_growth_doubles_stats(self, spell_resolver, mock_caster):
        """Should double size, damage, and carry capacity."""
        result = spell_resolver._handle_animal_growth(
            mock_caster, ["horse_1"], None
        )

        assert result["success"] is True
        target_result = result["results"][0]
        assert target_result["size_multiplier"] == 2
        assert target_result["damage_multiplier"] == 2
        assert target_result["carry_capacity_multiplier"] == 2

    def test_animal_growth_duration_12_turns(self, spell_resolver, mock_caster):
        """Duration should be 12 turns."""
        result = spell_resolver._handle_animal_growth(
            mock_caster, ["horse_1"], None
        )

        assert result["duration_turns"] == 12

    def test_animal_growth_registers_active_effect(self, spell_resolver, mock_caster):
        """Should register growth as active effect."""
        result = spell_resolver._handle_animal_growth(
            mock_caster, ["horse_1"], None
        )

        effect = next(
            (e for e in spell_resolver._active_effects if e.spell_id == "animal_growth"),
            None
        )
        assert effect is not None
        assert effect.duration_remaining == 12
        assert effect.mechanical_effects["size_multiplier"] == 2

    def test_animal_growth_multiple_animals(self, spell_resolver, mock_caster):
        """Should handle multiple animals."""
        result = spell_resolver._handle_animal_growth(
            mock_caster, ["horse_1", "dog_1", "cat_1"], None
        )

        assert len(result["targets_affected"]) == 3
        assert len(result["results"]) == 3

    def test_animal_growth_stat_modifiers_in_result(self, spell_resolver, mock_caster):
        """Should include stat modifiers in result."""
        result = spell_resolver._handle_animal_growth(
            mock_caster, ["horse_1"], None
        )

        modifiers = result["stat_modifiers_applied"]
        modifier_stats = [m["stat"] for m in modifiers]
        assert "size" in modifier_stats
        assert "damage" in modifier_stats
        assert "carry_capacity" in modifier_stats


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPhase2SpellIntegration:
    """Integration tests for Phase 2 spells with the dispatcher."""

    def test_deathly_blossom_registered_in_dispatcher(self, spell_resolver, mock_caster):
        """Deathly Blossom should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "deathly_blossom"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is not None
        assert result["success"] is True

    def test_en_croute_registered_in_dispatcher(self, spell_resolver, mock_caster, mock_dice_roller):
        """En Croute should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "en_croute"

        # Will fail due to no target
        result = spell_resolver._handle_special_spell(
            spell, mock_caster, [], mock_dice_roller
        )

        assert result is not None
        assert result["success"] is False  # No target

    def test_awe_registered_in_dispatcher(self, spell_resolver, mock_caster, mock_dice_roller):
        """Awe should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "awe"

        result = spell_resolver._handle_special_spell(
            spell, mock_caster, [], mock_dice_roller
        )

        assert result is not None
        assert result["success"] is False  # No targets

    def test_animal_growth_registered_in_dispatcher(self, spell_resolver, mock_caster):
        """Animal Growth should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "animal_growth"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is not None
        assert result["success"] is True


class TestPhase2ConditionApplication:
    """Tests for condition application via controller."""

    def test_deathly_blossom_calls_apply_condition(self, spell_resolver, mock_caster, mock_dice_roller):
        """Deathly Blossom should call controller.apply_condition."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        duration_roll = MagicMock()
        duration_roll.total = 3
        mock_dice_roller.roll = MagicMock(return_value=duration_roll)

        # Mock target character with proper get_saving_throw return
        mock_target = MagicMock()
        mock_target.get_saving_throw = MagicMock(return_value=0)
        spell_resolver._controller.get_character.return_value = mock_target

        spell_resolver._handle_deathly_blossom(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        spell_resolver._controller.apply_condition.assert_called_once()
        call_args = spell_resolver._controller.apply_condition.call_args
        assert call_args[0][0] == "target_npc"
        assert call_args[0][1] == "unconscious"

    def test_en_croute_calls_apply_condition(self, spell_resolver, mock_caster, mock_dice_roller):
        """En Croute should call controller.apply_condition."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        mock_target = MagicMock()
        mock_target.strength = 10
        mock_target.get_saving_throw = MagicMock(return_value=0)
        spell_resolver._controller.get_character.return_value = mock_target

        spell_resolver._handle_en_croute(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        spell_resolver._controller.apply_condition.assert_called_once()
        call_args = spell_resolver._controller.apply_condition.call_args
        assert call_args[0][0] == "target_npc"
        assert call_args[0][1] == "restrained"

    def test_awe_calls_apply_condition(self, spell_resolver, mock_caster, mock_dice_roller):
        """Awe should call controller.apply_condition for fleeing targets."""
        mock_caster.level = 5

        morale_roll = MagicMock()
        morale_roll.total = 12  # Fail
        flee_roll = MagicMock()
        flee_roll.total = 2
        mock_dice_roller.roll = MagicMock(side_effect=[morale_roll, flee_roll])

        spell_resolver._handle_awe(
            mock_caster, ["target_1"], mock_dice_roller
        )

        spell_resolver._controller.apply_condition.assert_called_once()
        call_args = spell_resolver._controller.apply_condition.call_args
        assert call_args[0][0] == "target_1"
        assert call_args[0][1] == "frightened"
