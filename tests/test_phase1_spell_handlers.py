"""
Tests for Phase 1 Spell Handlers.

Tests the following spell special handlers:
- Ventriloquism
- Create Food
- Create Water
- Air Sphere
- Detect Disguise
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
from src.data_models import CharacterState, DiceRoller, Item


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
    resolver._controller = mock_controller

    return resolver


@pytest.fixture
def mock_caster():
    """Create a mock caster character."""
    caster = MagicMock(spec=CharacterState)
    caster.character_id = "cleric_1"
    caster.name = "Brother Aldric"
    caster.level = 5
    caster.inventory = []
    caster.add_item = MagicMock()
    caster.get_saving_throw = MagicMock(return_value=15)
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
# VENTRILOQUISM TESTS
# =============================================================================


class TestVentriloquismHandler:
    """Tests for _handle_ventriloquism."""

    def test_ventriloquism_returns_success(self, spell_resolver, mock_caster):
        """Should return successful result with duration and range."""
        result = spell_resolver._handle_ventriloquism(mock_caster, [], None)

        assert result["success"] is True
        assert result["effect_type"] == "utility"
        assert result["duration_turns"] == 1
        assert result["range_feet"] == 60

    def test_ventriloquism_has_narrative_context(self, spell_resolver, mock_caster):
        """Should include narrative hints for LLM."""
        result = spell_resolver._handle_ventriloquism(mock_caster, [], None)

        assert "narrative_context" in result
        assert result["narrative_context"]["effect"] == "voice_projection"
        assert len(result["narrative_context"]["hints"]) >= 1

    def test_ventriloquism_no_targets_required(self, spell_resolver, mock_caster):
        """Should work without any targets specified."""
        result = spell_resolver._handle_ventriloquism(mock_caster, [], None)
        assert result["success"] is True


# =============================================================================
# CREATE FOOD TESTS
# =============================================================================


class TestCreateFoodHandler:
    """Tests for _handle_create_food."""

    def test_create_food_base_portions(self, spell_resolver, mock_caster):
        """Should create base 12 people + 12 mount portions at level 5."""
        mock_caster.level = 5
        result = spell_resolver._handle_create_food(mock_caster, [], None)

        assert result["success"] is True
        assert result["people_fed"] == 12
        assert result["mounts_fed"] == 12

    def test_create_food_scales_at_level_10(self, spell_resolver, mock_caster):
        """Should create extra portions at level 10+."""
        mock_caster.level = 10
        result = spell_resolver._handle_create_food(mock_caster, [], None)

        # Level 10 = 1 bonus level above 9, so +12 each
        assert result["people_fed"] == 24
        assert result["mounts_fed"] == 24

    def test_create_food_scales_at_level_12(self, spell_resolver, mock_caster):
        """Should create more portions at higher levels."""
        mock_caster.level = 12
        result = spell_resolver._handle_create_food(mock_caster, [], None)

        # Level 12 = 3 bonus levels above 9, so +36 each
        assert result["people_fed"] == 48
        assert result["mounts_fed"] == 48

    def test_create_food_creates_items(self, spell_resolver, mock_caster):
        """Should create both rations and fodder items."""
        result = spell_resolver._handle_create_food(mock_caster, [], None)

        assert len(result["items_created"]) == 2
        types = [item["type"] for item in result["items_created"]]
        assert "rations" in types
        assert "fodder" in types

    def test_create_food_adds_to_inventory(self, spell_resolver, mock_caster):
        """Should add items to caster's inventory."""
        spell_resolver._handle_create_food(mock_caster, [], None)

        # Should have called add_item twice (rations + fodder)
        assert mock_caster.add_item.call_count == 2

    def test_create_food_items_magical(self, spell_resolver, mock_caster):
        """Created items should be marked as magical."""
        spell_resolver._handle_create_food(mock_caster, [], None)

        # Check the items passed to add_item
        calls = mock_caster.add_item.call_args_list
        for call in calls:
            item = call[0][0]  # First positional arg is the Item
            assert item.magical is True
            assert "Lasts 1 day" in item.description


# =============================================================================
# CREATE WATER TESTS
# =============================================================================


class TestCreateWaterHandler:
    """Tests for _handle_create_water."""

    def test_create_water_base_gallons(self, spell_resolver, mock_caster):
        """Should create 50 gallons at base level."""
        mock_caster.level = 8
        result = spell_resolver._handle_create_water(mock_caster, [], None)

        assert result["success"] is True
        assert result["gallons_created"] == 50

    def test_create_water_scales_above_level_8(self, spell_resolver, mock_caster):
        """Should create extra water at level 9+."""
        mock_caster.level = 10
        result = spell_resolver._handle_create_water(mock_caster, [], None)

        # Level 10 = 2 bonus levels above 8, so +100 gallons
        assert result["gallons_created"] == 150

    def test_create_water_supplies_people_and_mounts(self, spell_resolver, mock_caster):
        """Should track people and mounts supplied."""
        mock_caster.level = 8
        result = spell_resolver._handle_create_water(mock_caster, [], None)

        assert result["people_supplied"] == 12
        assert result["mounts_supplied"] == 12

    def test_create_water_creates_item(self, spell_resolver, mock_caster):
        """Should create water container item."""
        result = spell_resolver._handle_create_water(mock_caster, [], None)

        assert len(result["items_created"]) == 1
        assert result["items_created"][0]["type"] == "water"

    def test_create_water_adds_to_inventory(self, spell_resolver, mock_caster):
        """Should add water to caster's inventory."""
        spell_resolver._handle_create_water(mock_caster, [], None)

        assert mock_caster.add_item.call_count == 1


# =============================================================================
# AIR SPHERE TESTS
# =============================================================================


class TestAirSphereHandler:
    """Tests for _handle_air_sphere."""

    def test_air_sphere_creates_buff(self, spell_resolver, mock_caster):
        """Should create underwater breathing buff."""
        result = spell_resolver._handle_air_sphere(mock_caster, [], None)

        assert result["success"] is True
        assert result["effect_type"] == "buff"
        assert "underwater_breathing" in result["conditions_applied"]

    def test_air_sphere_duration_one_day(self, spell_resolver, mock_caster):
        """Should last 1 day."""
        result = spell_resolver._handle_air_sphere(mock_caster, [], None)

        assert result["duration_days"] == 1

    def test_air_sphere_radius_10_feet(self, spell_resolver, mock_caster):
        """Should have 10 foot radius."""
        result = spell_resolver._handle_air_sphere(mock_caster, [], None)

        assert result["radius_feet"] == 10

    def test_air_sphere_centered_on_caster(self, spell_resolver, mock_caster):
        """Should be centered on caster."""
        result = spell_resolver._handle_air_sphere(mock_caster, [], None)

        assert result["centered_on"] == mock_caster.character_id

    def test_air_sphere_registers_active_effect(self, spell_resolver, mock_caster):
        """Should register as active spell effect when controller available."""
        result = spell_resolver._handle_air_sphere(mock_caster, [], None)

        effect_id = result["effect_id"]
        # Find the effect in the list
        effect = next(
            (e for e in spell_resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect is not None
        assert effect.spell_id == "air_sphere"
        assert effect.duration_remaining == 1


# =============================================================================
# DETECT DISGUISE TESTS
# =============================================================================


class TestDetectDisguiseHandler:
    """Tests for _handle_detect_disguise."""

    def test_detect_disguise_requires_target(self, spell_resolver, mock_caster, mock_dice_roller):
        """Should fail if no target specified."""
        result = spell_resolver._handle_detect_disguise(mock_caster, [], mock_dice_roller)

        assert result["success"] is False
        assert "no target" in result["message"].lower()

    def test_detect_disguise_allows_save(self, spell_resolver, mock_caster, mock_dice_roller):
        """Target should get saving throw."""
        # Set up save to succeed (roll high)
        save_roll = MagicMock()
        save_roll.total = 20
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        result = spell_resolver._handle_detect_disguise(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["success"] is True
        assert "target_npc" in result.get("targets_saved", [])

    def test_detect_disguise_save_blocks_reveal(self, spell_resolver, mock_caster, mock_dice_roller):
        """Successful save should prevent disguise revelation."""
        save_roll = MagicMock()
        save_roll.total = 20
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        result = spell_resolver._handle_detect_disguise(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        # Should indicate St Dougan is silent
        assert result["narrative_context"]["st_dougan_silent"] is True

    @patch("src.oracle.mythic_gme.MythicGME")
    def test_detect_disguise_uses_oracle(self, mock_mythic_class, spell_resolver, mock_caster, mock_dice_roller):
        """Should query oracle for disguise status when save fails."""
        # Set up save to fail
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        # Mock oracle response
        mock_oracle = MagicMock()
        mock_result = MagicMock()
        mock_result.result.value = "yes"
        mock_result.roll = 65
        mock_oracle.fate_check.return_value = mock_result
        mock_mythic_class.return_value = mock_oracle

        result = spell_resolver._handle_detect_disguise(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        # Oracle should have been called
        mock_oracle.fate_check.assert_called_once()
        assert result["is_disguised"] is True
        assert result["saint_response"] == "be wary"

    @patch("src.oracle.mythic_gme.MythicGME")
    def test_detect_disguise_reveals_non_disguised(self, mock_mythic_class, spell_resolver, mock_caster, mock_dice_roller):
        """Should reveal when target is not disguised."""
        save_roll = MagicMock()
        save_roll.total = 5
        mock_dice_roller.roll_d20 = MagicMock(return_value=save_roll)

        mock_oracle = MagicMock()
        mock_result = MagicMock()
        mock_result.result.value = "no"
        mock_result.roll = 35
        mock_oracle.fate_check.return_value = mock_result
        mock_mythic_class.return_value = mock_oracle

        result = spell_resolver._handle_detect_disguise(
            mock_caster, ["target_npc"], mock_dice_roller
        )

        assert result["is_disguised"] is False
        assert result["saint_response"] == "be sure"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPhase1SpellIntegration:
    """Integration tests for Phase 1 spells with the dispatcher."""

    def test_ventriloquism_registered_in_dispatcher(self, spell_resolver, mock_caster):
        """Ventriloquism should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "ventriloquism"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is not None
        assert result["success"] is True

    def test_create_food_registered_in_dispatcher(self, spell_resolver, mock_caster):
        """Create Food should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "create_food"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is not None
        assert result["success"] is True

    def test_create_water_registered_in_dispatcher(self, spell_resolver, mock_caster):
        """Create Water should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "create_water"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is not None
        assert result["success"] is True

    def test_air_sphere_registered_in_dispatcher(self, spell_resolver, mock_caster):
        """Air Sphere should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "air_sphere"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is not None
        assert result["success"] is True

    def test_detect_disguise_registered_in_dispatcher(self, spell_resolver, mock_caster, mock_dice_roller):
        """Detect Disguise should be accessible via _handle_special_spell."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "detect_disguise"

        # Will fail due to no target, but should be dispatched
        result = spell_resolver._handle_special_spell(
            spell, mock_caster, [], mock_dice_roller
        )

        assert result is not None
        # Returns success=False due to no target, but handler was called
        assert "success" in result

    def test_unregistered_spell_returns_none(self, spell_resolver, mock_caster):
        """Unregistered spells should return None from dispatcher."""
        spell = MagicMock(spec=SpellData)
        spell.spell_id = "not_a_real_spell"

        result = spell_resolver._handle_special_spell(spell, mock_caster, [], None)

        assert result is None


class TestSpellHandlerWithRealController:
    """Integration tests with a more realistic controller setup."""

    def test_create_food_uses_controller_time(self, mock_caster):
        """Create Food should use controller's time tracker for item descriptions."""
        resolver = SpellResolver()
        mock_controller = MagicMock()
        mock_controller.time_tracker.days = 42
        resolver._controller = mock_controller

        resolver._handle_create_food(mock_caster, [], None)

        # Check items were created with correct day in description
        calls = mock_caster.add_item.call_args_list
        for call in calls:
            item = call[0][0]
            assert "created day 42" in item.description

    def test_air_sphere_effect_stored_with_controller(self, mock_caster):
        """Air Sphere should store active effect when controller present."""
        resolver = SpellResolver()
        mock_controller = MagicMock()
        mock_controller.time_tracker.days = 10
        resolver._controller = mock_controller

        result = resolver._handle_air_sphere(mock_caster, [], None)

        effect_id = result["effect_id"]
        # Find the effect in the list
        effect = next(
            (e for e in resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect is not None
        assert effect.caster_id == mock_caster.character_id
        assert effect.target_id == mock_caster.character_id
        assert effect.mechanical_effects["underwater_breathing"] is True
