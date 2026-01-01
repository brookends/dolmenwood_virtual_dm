"""
Phase 7 Spell Handler Tests

Tests for teleportation, condition, and healing spell handlers:
- Dimension Door (arcane level 4) - paired door-shaped rifts for teleportation
- Confusion (arcane level 4) - 3d6 creatures stricken with delusions
- Greater Healing (divine level 4) - restores 2d6+2 Hit Points
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.narrative.spell_resolver import SpellResolver, DurationType, SpellEffectType


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance for testing."""
    return SpellResolver()


@pytest.fixture
def mock_caster():
    """Create a mock caster character."""
    caster = MagicMock()
    caster.character_id = "test_caster"
    caster.level = 7
    return caster


@pytest.fixture
def mock_targets():
    """Create a list of mock target IDs."""
    return ["target_1", "target_2", "target_3", "target_4", "target_5"]


@pytest.fixture
def fixed_dice_roller():
    """Create a dice roller that returns predictable values."""
    roller = MagicMock()
    roller.roll = MagicMock(side_effect=lambda expr: {
        "1d20": 10,
        "2d6": 7,
        "3d6": 10,
        "1d10": 5,
        "1d4": 2,
    }.get(expr, 10))
    return roller


@pytest.fixture
def spell_data_loader():
    """Fixture to load actual spell data from JSON files."""

    def _load_spell(filename: str, spell_id: str) -> dict:
        spell_path = Path(__file__).parent.parent / "data" / "content" / "spells" / filename
        with open(spell_path) as f:
            data = json.load(f)
        for item in data["items"]:
            if item["spell_id"] == spell_id:
                return item
        raise ValueError(f"Spell {spell_id} not found in {filename}")

    return _load_spell


# =============================================================================
# DIMENSION DOOR TESTS
# =============================================================================


class TestDimensionDoorHandler:
    """Tests for the Dimension Door spell handler."""

    def test_basic_teleportation_succeeds(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test basic willing teleportation."""
        result = spell_resolver._handle_dimension_door(
            mock_caster, ["self"], fixed_dice_roller
        )

        assert result["spell_id"] == "dimension_door"
        assert result["spell_name"] == "Dimension Door"
        assert result["success"] is True
        assert result["teleported"] is True
        assert result["max_range"] == 360
        assert result["entrance_range"] == 10

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_dimension_door(
            mock_caster, ["target_1"], fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7
        assert result["target_id"] == "target_1"

    def test_destination_blocked_fails(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that blocked destination causes spell to fail."""
        spell_resolver._current_context = {"destination_blocked": True}

        result = spell_resolver._handle_dimension_door(
            mock_caster, ["self"], fixed_dice_roller
        )

        assert result["success"] is False
        assert result["destination_blocked"] is True
        assert "narrative_context" in result
        assert result["narrative_context"]["spell_fizzled"] is True

    def test_unwilling_target_save_succeeds(self, spell_resolver, mock_caster, mock_targets):
        """Test that unwilling target can resist with successful save."""
        # Make save succeed (roll 15 vs target 14)
        roller = MagicMock()
        roller.roll = MagicMock(return_value=15)
        spell_resolver._current_context = {"is_unwilling": True}

        result = spell_resolver._handle_dimension_door(
            mock_caster, mock_targets, roller
        )

        assert result["is_unwilling"] is True
        assert result["save_roll"] == 15
        assert result["save_success"] is True
        assert result["teleported"] is False

    def test_unwilling_target_save_fails(self, spell_resolver, mock_caster, mock_targets):
        """Test that unwilling target is teleported when save fails."""
        # Make save fail (roll 5 vs target 14)
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)
        spell_resolver._current_context = {"is_unwilling": True}

        result = spell_resolver._handle_dimension_door(
            mock_caster, mock_targets, roller
        )

        assert result["is_unwilling"] is True
        assert result["save_roll"] == 5
        assert result["save_success"] is False
        assert result["teleported"] is True

    def test_known_location_destination(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test teleporting to a known location."""
        spell_resolver._current_context = {"destination_type": "known_location"}

        result = spell_resolver._handle_dimension_door(
            mock_caster, ["self"], fixed_dice_roller
        )

        assert result["destination_type"] == "known_location"
        assert "a known destination" in str(result["narrative_context"]["hints"])

    def test_offset_coordinates_destination(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test teleporting using coordinate offsets."""
        spell_resolver._current_context = {
            "destination_type": "offset_coordinates",
            "destination_offset": {"north": 120, "east": 160, "up": 80}
        }

        result = spell_resolver._handle_dimension_door(
            mock_caster, ["self"], fixed_dice_roller
        )

        assert result["destination_type"] == "offset_coordinates"
        assert result["destination_offset"]["north"] == 120
        assert result["destination_offset"]["east"] == 160
        assert result["destination_offset"]["up"] == 80

    def test_creates_active_effect(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that an active effect is created."""
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_dimension_door(
            mock_caster, ["target_1"], fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1
        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "dimension_door"
        assert effect.duration_type == DurationType.ROUNDS
        assert effect.duration_remaining == 1

    def test_effect_has_correct_mechanics(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that effect contains correct mechanical data."""
        spell_resolver._handle_dimension_door(
            mock_caster, ["target_1"], fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["teleportation"] is True
        assert effect.mechanical_effects["max_range"] == 360
        assert effect.mechanical_effects["one_way"] is True

    def test_narrative_context_for_willing_transport(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test narrative context for willing teleportation."""
        result = spell_resolver._handle_dimension_door(
            mock_caster, ["self"], fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("door-shaped rifts" in hint for hint in hints)
        assert any("instant arrival" in hint for hint in hints)

    def test_empty_targets_uses_caster(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that empty targets list uses caster as target."""
        result = spell_resolver._handle_dimension_door(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] is None
        assert result["teleported"] is True


# =============================================================================
# CONFUSION TESTS
# =============================================================================


class TestConfusionHandler:
    """Tests for the Confusion spell handler."""

    def test_basic_confusion_succeeds(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test basic confusion spell casting."""
        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["spell_id"] == "confusion"
        assert result["spell_name"] == "Confusion"
        assert result["success"] is True
        assert result["duration_rounds"] == 12
        assert result["area_radius"] == 30

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7

    def test_rolls_3d6_for_creatures_affected(self, spell_resolver, mock_caster, mock_targets):
        """Test that 3d6 is rolled for number of creatures affected."""
        roller = MagicMock()
        roller.roll = MagicMock(side_effect=lambda expr: 12 if expr == "3d6" else 5)

        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, roller
        )

        assert result["max_creatures_affected"] == 12
        roller.roll.assert_any_call("3d6")

    def test_limits_affected_to_available_targets(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that creatures affected is limited to available targets."""
        # Only 2 targets provided but 3d6 might roll higher
        result = spell_resolver._handle_confusion(
            mock_caster, ["target_1", "target_2"], fixed_dice_roller
        )

        assert len(result["affected_creatures"]) <= 2

    def test_behavior_table_included(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that behavior table is included in result."""
        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert "behavior_table" in result
        assert "wander_away" in result["behavior_table"]
        assert "stand_confused" in result["behavior_table"]
        assert "attack_nearest" in result["behavior_table"]
        assert "act_normally" in result["behavior_table"]

    def test_low_level_creatures_cannot_save(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that creatures Level 2 or lower cannot save."""
        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # All creatures default to level 1
        for creature in result["affected_creatures"]:
            assert creature["can_save"] is False

    def test_high_level_creatures_can_save(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that creatures Level 3+ can save each round."""
        # Set up controller to return level 5 character
        controller = MagicMock()
        target_char = MagicMock()
        target_char.level = 5
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        for creature in result["affected_creatures"]:
            assert creature["can_save"] is True
            assert creature["level"] == 5

    def test_initial_behavior_rolled(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that initial behavior is rolled for each creature."""
        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        for creature in result["affected_creatures"]:
            assert "initial_behavior" in creature
            assert creature["initial_behavior"] in [
                "wander_away", "stand_confused", "attack_nearest", "act_normally"
            ]

    def test_creates_active_effect_per_target(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that an active effect is created for each affected creature."""
        initial_effects = len(spell_resolver._active_effects)

        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        num_affected = len(result["affected_creatures"])
        assert len(spell_resolver._active_effects) == initial_effects + num_affected

    def test_effect_has_correct_duration(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that effects have correct duration."""
        spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        for effect in spell_resolver._active_effects:
            if effect.spell_id == "confusion":
                assert effect.duration_type == DurationType.ROUNDS
                assert effect.duration_remaining == 12
                assert effect.effect_type == SpellEffectType.HYBRID

    def test_effect_contains_behavior_table(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that effect contains behavior table for per-round rolls."""
        spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert "behavior_table" in effect.mechanical_effects
        assert "current_behavior" in effect.mechanical_effects

    def test_narrative_context_includes_hints(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative context includes appropriate hints."""
        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("30' radius" in hint for hint in hints)
        assert any("delusions" in hint for hint in hints)

    def test_empty_targets_creates_no_effects(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that empty targets creates no creature effects."""
        initial_effects = len(spell_resolver._active_effects)

        result = spell_resolver._handle_confusion(
            mock_caster, [], fixed_dice_roller
        )

        assert len(result["affected_creatures"]) == 0
        assert len(spell_resolver._active_effects) == initial_effects


# =============================================================================
# GREATER HEALING TESTS
# =============================================================================


class TestGreaterHealingHandler:
    """Tests for the Greater Healing spell handler."""

    def test_basic_healing_succeeds(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test basic healing spell casting."""
        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["spell_id"] == "greater_healing"
        assert result["spell_name"] == "Greater Healing"
        assert result["success"] is True
        assert result["duration_type"] == "instant"

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7
        assert result["target_id"] == "target_1"

    def test_heals_2d6_plus_2(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that healing is 2d6+2."""
        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["healing_roll"] == 7  # From fixed dice roller
        assert result["healing_bonus"] == 2
        assert result["total_healing"] == 9

    def test_minimum_healing(self, spell_resolver, mock_caster, mock_targets):
        """Test minimum healing roll (2d6=2, +2 = 4)."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=2)

        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, roller
        )

        assert result["healing_roll"] == 2
        assert result["total_healing"] == 4

    def test_maximum_healing(self, spell_resolver, mock_caster, mock_targets):
        """Test maximum healing roll (2d6=12, +2 = 14)."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=12)

        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, roller
        )

        assert result["healing_roll"] == 12
        assert result["total_healing"] == 14

    def test_healing_capped_at_max_hp(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that healing cannot exceed max HP."""
        # Set up controller with character at near-max HP
        controller = MagicMock()
        target_char = MagicMock()
        target_char.current_hp = 18
        target_char.max_hp = 20
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Roll was 7+2=9, but only 2 HP needed
        assert result["actual_healing"] == 2
        assert result["healing_capped"] is True
        assert result["current_hp_before"] == 18
        assert result["current_hp_after"] == 20

    def test_full_healing_when_below_max(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test full healing when HP deficit is larger than roll."""
        controller = MagicMock()
        target_char = MagicMock()
        target_char.current_hp = 5
        target_char.max_hp = 20
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Roll was 7+2=9, deficit is 15, so all 9 HP healed
        assert result["actual_healing"] == 9
        assert result["healing_capped"] is False
        assert result["current_hp_after"] == 14

    def test_empty_targets_heals_caster(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that empty targets heals the caster."""
        result = spell_resolver._handle_greater_healing(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] == "test_caster"

    def test_no_active_effect_created(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that no active effect is created (instant spell)."""
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Greater Healing is instant - no ongoing effect
        assert len(spell_resolver._active_effects) == initial_effects

    def test_narrative_context_mentions_st_wick(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative context mentions St Wick."""
        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("St Wick" in hint for hint in hints)
        assert any("parable" in hint for hint in hints)

    def test_narrative_context_shows_healing_amount(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative context shows healing amount."""
        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("Hit Points" in hint for hint in hints)


# =============================================================================
# INTEGRATION TESTS WITH SPELL DATA
# =============================================================================


class TestPhase7SpellDataIntegration:
    """Integration tests that verify handlers against actual spell JSON data."""

    def test_dimension_door_matches_source(self, spell_data_loader):
        """Verify Dimension Door matches arcane_level_4_1.json."""
        spell = spell_data_loader("arcane_level_4_1.json", "dimension_door")

        assert spell["level"] == 4
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "1 Round"
        assert "10'" in spell["range"] and "360'" in spell["range"]

    def test_dimension_door_description_validation(self, spell_data_loader):
        """Verify Dimension Door description contains key mechanics."""
        spell = spell_data_loader("arcane_level_4_1.json", "dimension_door")

        # Verify description contains key mechanics from source
        assert "door-shaped rifts" in spell["description"]
        assert "360′" in spell["description"]  # Unicode prime character
        assert "Save Versus Hold" in spell["description"]
        assert "Unwilling subjects" in spell["description"]
        assert "Occupied destination" in spell["description"]

    def test_dimension_door_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_4_1.json", "dimension_door")

        result = spell_resolver._handle_dimension_door(
            mock_caster, ["target_1"], fixed_dice_roller
        )

        # Verify range matches (10' / 360' from source)
        assert result["entrance_range"] == 10
        assert result["max_range"] == 360
        # Verify duration is 1 Round per source
        effect = spell_resolver._active_effects[-1]
        assert effect.duration_remaining == 1
        assert effect.duration_unit == "rounds"

    def test_dimension_door_unwilling_save_type(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets
    ):
        """Verify unwilling target uses Save Versus Hold per source."""
        spell = spell_data_loader("arcane_level_4_1.json", "dimension_door")

        assert "Save Versus Hold" in spell["description"]

        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)
        spell_resolver._current_context = {"is_unwilling": True}

        result = spell_resolver._handle_dimension_door(
            mock_caster, mock_targets, roller
        )

        assert result["is_unwilling"] is True
        assert "save_roll" in result

    def test_confusion_matches_source(self, spell_data_loader):
        """Verify Confusion matches arcane_level_4_1.json."""
        spell = spell_data_loader("arcane_level_4_1.json", "confusion")

        assert spell["level"] == 4
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "12 Rounds"
        assert spell["range"] == "120'"

    def test_confusion_description_validation(self, spell_data_loader):
        """Verify Confusion description contains key mechanics."""
        spell = spell_data_loader("arcane_level_4_1.json", "confusion")

        # Verify key mechanics from source
        assert "3d6" in spell["description"]
        assert "30′ radius" in spell["description"]  # Unicode prime character
        assert "delusions" in spell["description"]
        assert "Level 3 or greater" in spell["description"]
        assert "Save Versus Spell" in spell["description"]
        assert "Level 2 or lower" in spell["description"]
        assert "May not make a Saving Throw" in spell["description"]

    def test_confusion_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_4_1.json", "confusion")

        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Verify 12 Rounds duration from source
        assert result["duration_rounds"] == 12
        # Verify 30' radius from source
        assert result["area_radius"] == 30

    def test_confusion_3d6_creatures_from_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets
    ):
        """Verify 3d6 creatures affected per source."""
        spell = spell_data_loader("arcane_level_4_1.json", "confusion")

        assert "3d6" in spell["description"]

        roller = MagicMock()
        roller.roll = MagicMock(side_effect=lambda expr: 12 if expr == "3d6" else 5)

        result = spell_resolver._handle_confusion(
            mock_caster, mock_targets, roller
        )

        assert result["max_creatures_affected"] == 12

    def test_greater_healing_matches_source(self, spell_data_loader):
        """Verify Greater Healing matches holy_level_4.json."""
        spell = spell_data_loader("holy_level_4.json", "greater_healing")

        assert spell["level"] == 4
        assert spell["magic_type"] == "divine"
        assert spell["duration"] == "Instant"

    def test_greater_healing_description_validation(self, spell_data_loader):
        """Verify Greater Healing description contains key mechanics."""
        spell = spell_data_loader("holy_level_4.json", "greater_healing")

        # Verify key mechanics from source
        assert "St Wick" in spell["description"]
        assert "parable" in spell["description"]
        assert "2d6+2" in spell["description"]
        assert "Hit Points" in spell["description"]
        assert "cannot raise" in spell["description"] or "normal maximum" in spell["description"]

    def test_greater_healing_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("holy_level_4.json", "greater_healing")

        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Verify instant duration from source
        assert result["duration_type"] == "instant"
        # Verify 2d6+2 healing from source
        assert result["healing_bonus"] == 2


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestPhase7EdgeCases:
    """Edge case tests for Phase 7 handlers."""

    def test_dimension_door_negative_offset(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test Dimension Door with negative coordinate offsets."""
        spell_resolver._current_context = {
            "destination_type": "offset_coordinates",
            "destination_offset": {"north": -100, "east": -50, "up": -30}
        }

        result = spell_resolver._handle_dimension_door(
            mock_caster, ["self"], fixed_dice_roller
        )

        assert result["destination_offset"]["north"] == -100
        # Narrative should show south/west/down
        hints = str(result["narrative_context"]["hints"])
        assert "south" in hints or "west" in hints or "down" in hints

    def test_confusion_with_single_target(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test Confusion with only one target available."""
        result = spell_resolver._handle_confusion(
            mock_caster, ["lone_target"], fixed_dice_roller
        )

        assert len(result["affected_creatures"]) == 1
        assert result["affected_creatures"][0]["target_id"] == "lone_target"

    def test_greater_healing_at_full_hp(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test Greater Healing when target is at full HP."""
        controller = MagicMock()
        target_char = MagicMock()
        target_char.current_hp = 20
        target_char.max_hp = 20
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        result = spell_resolver._handle_greater_healing(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["actual_healing"] == 0
        assert result["healing_capped"] is True

    def test_dimension_door_without_context(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test Dimension Door without context defaults."""
        # Ensure no context is set
        spell_resolver._current_context = None

        result = spell_resolver._handle_dimension_door(
            mock_caster, ["target_1"], fixed_dice_roller
        )

        # Should use defaults
        assert result["destination_type"] == "known_location"
        assert result["is_unwilling"] is False
        assert result["teleported"] is True

    def test_confusion_behavior_distribution(self, spell_resolver, mock_caster):
        """Test that confusion behavior rolls are distributed across table."""
        behaviors_seen = set()

        for _ in range(100):
            roller = MagicMock()
            # Random value between 1-10
            import random
            roller.roll = MagicMock(side_effect=lambda expr: random.randint(3, 18) if expr == "3d6" else random.randint(1, 10))

            result = spell_resolver._handle_confusion(
                mock_caster, ["target_1"], roller
            )

            if result["affected_creatures"]:
                behaviors_seen.add(result["affected_creatures"][0]["initial_behavior"])

        # Should see multiple behavior types
        assert len(behaviors_seen) >= 2

    def test_level_1_caster_handlers(self, spell_resolver, fixed_dice_roller):
        """Test all handlers work with level 1 caster."""
        caster = MagicMock()
        caster.character_id = "level_1_mage"
        caster.level = 1

        # Dimension Door
        result1 = spell_resolver._handle_dimension_door(caster, ["target"], fixed_dice_roller)
        assert result1["caster_level"] == 1

        # Confusion
        result2 = spell_resolver._handle_confusion(caster, ["target"], fixed_dice_roller)
        assert result2["caster_level"] == 1

        # Greater Healing
        result3 = spell_resolver._handle_greater_healing(caster, ["target"], fixed_dice_roller)
        assert result3["caster_level"] == 1

    def test_high_level_caster_handlers(self, spell_resolver, fixed_dice_roller):
        """Test all handlers work with high level caster."""
        caster = MagicMock()
        caster.character_id = "archmage"
        caster.level = 14

        # Dimension Door
        result1 = spell_resolver._handle_dimension_door(caster, ["target"], fixed_dice_roller)
        assert result1["caster_level"] == 14

        # Confusion
        result2 = spell_resolver._handle_confusion(caster, ["target"], fixed_dice_roller)
        assert result2["caster_level"] == 14

        # Greater Healing
        result3 = spell_resolver._handle_greater_healing(caster, ["target"], fixed_dice_roller)
        assert result3["caster_level"] == 14
