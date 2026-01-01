"""
Phase 9 Spell Handler Tests

Tests for transformation and utility spell handlers:
- Petrification (arcane level 6) - flesh to stone/stone to flesh
- Invisibility (arcane level 2) - makes targets invisible
- Knock (arcane level 2) - opens locked doors
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
    return ["target_1", "target_2", "target_3"]


@pytest.fixture
def fixed_dice_roller():
    """Create a dice roller that returns predictable values."""
    roller = MagicMock()
    roller.roll = MagicMock(side_effect=lambda expr: {
        "1d20": 10,
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
# PETRIFICATION TESTS
# =============================================================================


class TestPetrificationHandler:
    """Tests for the Petrification spell handler."""

    def test_basic_petrification_succeeds(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test basic flesh to stone casting."""
        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["spell_id"] == "petrification"
        assert result["spell_name"] == "Petrification"
        assert result["success"] is True
        assert result["mode"] == "flesh_to_stone"

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7
        assert result["target_id"] == "target_1"

    def test_flesh_to_stone_save_succeeds(self, spell_resolver, mock_caster, mock_targets):
        """Test that target can resist with successful save."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=18)  # High roll succeeds

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        assert result["save_roll"] == 18
        assert result["save_success"] is True
        assert result["petrified"] is False

    def test_flesh_to_stone_save_fails(self, spell_resolver, mock_caster, mock_targets):
        """Test that target is petrified when save fails."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Low roll fails

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        assert result["save_roll"] == 5
        assert result["save_success"] is False
        assert result["petrified"] is True

    def test_flesh_to_stone_creates_permanent_effect(self, spell_resolver, mock_caster, mock_targets):
        """Test that petrification creates permanent effect."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1
        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "petrification"
        assert effect.duration_type == DurationType.PERMANENT

    def test_flesh_to_stone_effect_includes_equipment(self, spell_resolver, mock_caster, mock_targets):
        """Test that petrification includes equipment."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save

        spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["includes_equipment"] is True
        assert effect.mechanical_effects["condition"] == "petrified"

    def test_stone_to_flesh_mode(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test stone to flesh restoration mode."""
        spell_resolver._current_context = {"mode": "stone_to_flesh"}

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["mode"] == "stone_to_flesh"
        assert result["restored"] is True

    def test_stone_to_flesh_removes_petrification_effect(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that stone to flesh removes existing petrification effect."""
        # First petrify the target
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save
        spell_resolver._handle_petrification(mock_caster, mock_targets, roller)
        initial_effects = len(spell_resolver._active_effects)

        # Now restore them
        spell_resolver._current_context = {"mode": "stone_to_flesh"}
        spell_resolver._handle_petrification(mock_caster, mock_targets, fixed_dice_roller)

        # Effect should be removed
        petri_effects = [e for e in spell_resolver._active_effects
                         if e.spell_id == "petrification" and e.target_id == "target_1"]
        assert len(petri_effects) == 0

    def test_save_success_no_effect_created(self, spell_resolver, mock_caster, mock_targets):
        """Test that successful save doesn't create effect."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=18)  # High roll succeeds
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        assert len(spell_resolver._active_effects) == initial_effects

    def test_narrative_context_for_petrification(self, spell_resolver, mock_caster, mock_targets):
        """Test narrative context when target is petrified."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("stone" in hint for hint in hints)
        assert any("permanent" in hint for hint in hints)

    def test_narrative_context_for_restoration(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test narrative context for stone to flesh."""
        spell_resolver._current_context = {"mode": "stone_to_flesh"}

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("restored" in hint for hint in hints)
        assert result["narrative_context"]["restoration"] is True


# =============================================================================
# INVISIBILITY TESTS
# =============================================================================


class TestInvisibilityHandler:
    """Tests for the Invisibility spell handler."""

    def test_basic_invisibility_succeeds(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test basic invisibility casting."""
        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["spell_id"] == "invisibility"
        assert result["spell_name"] == "Invisibility"
        assert result["success"] is True

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7
        assert result["target_id"] == "target_1"

    def test_duration_scales_with_level(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that duration is 1 hour per level."""
        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["duration_hours"] == 7

    def test_high_level_caster_long_duration(self, spell_resolver, mock_targets, fixed_dice_roller):
        """Test that high level caster has long duration."""
        caster = MagicMock()
        caster.character_id = "archmage"
        caster.level = 12

        result = spell_resolver._handle_invisibility(
            caster, mock_targets, fixed_dice_roller
        )

        assert result["duration_hours"] == 12

    def test_creates_hours_duration_effect(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that effect uses hours duration type."""
        initial_effects = len(spell_resolver._active_effects)

        spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1
        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "invisibility"
        assert effect.duration_type == DurationType.HOURS
        assert effect.duration_remaining == 7

    def test_effect_breaks_on_attack(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that effect has break on attack flag."""
        spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["breaks_on_attack"] is True
        assert effect.mechanical_effects["breaks_on_spell_cast"] is True

    def test_includes_gear_for_creatures(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that creature invisibility includes gear."""
        spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["includes_gear"] is True

    def test_object_target_type(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test invisibility on object target."""
        spell_resolver._current_context = {"target_type": "object"}

        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["target_type"] == "object"
        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["includes_gear"] is False

    def test_light_sources_still_shine(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that light sources remain visible."""
        spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["light_sources_still_shine"] is True

    def test_empty_targets_uses_caster(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that empty targets makes caster invisible."""
        result = spell_resolver._handle_invisibility(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] == "test_caster"

    def test_narrative_mentions_duration(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative mentions duration."""
        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("7 hours" in hint for hint in hints)

    def test_narrative_mentions_breaking_conditions(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative warns about breaking conditions."""
        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("attack" in hint.lower() for hint in hints)


# =============================================================================
# KNOCK TESTS
# =============================================================================


class TestKnockHandler:
    """Tests for the Knock spell handler."""

    def test_basic_knock_succeeds(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test basic knock casting."""
        result = spell_resolver._handle_knock(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["spell_id"] == "knock"
        assert result["spell_name"] == "Knock"
        assert result["success"] is True
        assert result["duration_type"] == "instant"

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that spell metadata is correct."""
        result = spell_resolver._handle_knock(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["caster_id"] == "test_caster"
        assert result["caster_level"] == 7
        assert result["target_id"] == "target_1"

    def test_opens_mundane_lock(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that knock opens mundane locks."""
        spell_resolver._current_context = {"has_mundane_lock": True}

        result = spell_resolver._handle_knock(
            mock_caster, ["door_1"], fixed_dice_roller
        )

        assert "mundane_lock_opened" in result["effects_applied"]

    def test_removes_bar(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that knock removes bars."""
        spell_resolver._current_context = {"has_mundane_lock": False, "has_bar": True}

        result = spell_resolver._handle_knock(
            mock_caster, ["door_1"], fixed_dice_roller
        )

        assert "bar_removed" in result["effects_applied"]

    def test_dispels_glyph_of_sealing(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that knock dispels Glyph of Sealing."""
        spell_resolver._current_context = {
            "has_mundane_lock": False,
            "has_glyph_of_sealing": True
        }

        result = spell_resolver._handle_knock(
            mock_caster, ["door_1"], fixed_dice_roller
        )

        assert "glyph_of_sealing_dispelled" in result["effects_applied"]

    def test_disables_glyph_of_locking_for_1_turn(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that knock disables Glyph of Locking for 1 Turn."""
        spell_resolver._current_context = {
            "has_mundane_lock": False,
            "has_glyph_of_locking": True
        }

        result = spell_resolver._handle_knock(
            mock_caster, ["door_1"], fixed_dice_roller
        )

        assert "glyph_of_locking_disabled" in result["effects_applied"]
        assert result["glyph_disabled_duration"] == 1

    def test_opens_secret_door(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that knock opens known secret doors."""
        spell_resolver._current_context = {
            "has_mundane_lock": False,
            "is_secret_door": True
        }

        result = spell_resolver._handle_knock(
            mock_caster, ["secret_door"], fixed_dice_roller
        )

        assert "secret_door_opened" in result["effects_applied"]

    def test_multiple_effects(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test knock with multiple barriers."""
        spell_resolver._current_context = {
            "has_mundane_lock": True,
            "has_bar": True,
            "has_glyph_of_locking": True
        }

        result = spell_resolver._handle_knock(
            mock_caster, ["fortified_door"], fixed_dice_roller
        )

        assert "mundane_lock_opened" in result["effects_applied"]
        assert "bar_removed" in result["effects_applied"]
        assert "glyph_of_locking_disabled" in result["effects_applied"]

    def test_already_unlocked_door(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test knock on already unlocked door."""
        spell_resolver._current_context = {
            "has_mundane_lock": False,
            "has_bar": False,
            "has_glyph_of_sealing": False,
            "has_glyph_of_locking": False,
            "is_secret_door": False
        }

        result = spell_resolver._handle_knock(
            mock_caster, ["open_door"], fixed_dice_roller
        )

        assert len(result["effects_applied"]) == 0
        hints = result["narrative_context"]["hints"]
        assert any("already unlocked" in hint for hint in hints)

    def test_narrative_includes_knock_action(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative describes knocking."""
        result = spell_resolver._handle_knock(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("knocks" in hint for hint in hints)

    def test_narrative_includes_opening(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test that narrative describes door opening."""
        result = spell_resolver._handle_knock(
            mock_caster, mock_targets, fixed_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("opens" in hint for hint in hints)

    def test_empty_targets_uses_door_default(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that empty targets defaults to 'door'."""
        result = spell_resolver._handle_knock(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] == "door"


# =============================================================================
# INTEGRATION TESTS WITH SPELL DATA
# =============================================================================


class TestPhase9SpellDataIntegration:
    """Integration tests that verify handlers against actual spell JSON data."""

    def test_petrification_matches_source(self, spell_data_loader):
        """Verify Petrification matches arcane_level_6_2.json."""
        spell = spell_data_loader("arcane_level_6_2.json", "petrification")

        assert spell["level"] == 6
        assert spell["magic_type"] == "arcane"
        assert "Permanent" in spell["duration"] or "instant" in spell["duration"].lower()
        assert spell["range"] == "120'"

    def test_petrification_description_validation(self, spell_data_loader):
        """Verify Petrification description contains key mechanics."""
        spell = spell_data_loader("arcane_level_6_2.json", "petrification")

        # Verify description contains key mechanics from source
        assert "Flesh to stone" in spell["description"]
        assert "Stone to flesh" in spell["description"]
        assert "Save Versus Hold" in spell["description"]
        assert "equipment" in spell["description"].lower()
        assert "permanently" in spell["description"].lower() or "Permanent" in spell["description"]

    def test_petrification_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_6_2.json", "petrification")

        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save
        spell_resolver._handle_petrification(mock_caster, mock_targets, roller)

        # Verify permanent duration from source
        effect = spell_resolver._active_effects[-1]
        assert effect.duration_type == DurationType.PERMANENT
        assert effect.mechanical_effects["includes_equipment"] is True

    def test_petrification_save_type_from_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets
    ):
        """Verify Save Versus Hold per source - handler uses hold save."""
        spell = spell_data_loader("arcane_level_6_2.json", "petrification")

        # Verify source description requires Save Versus Hold
        assert "Save Versus Hold" in spell["description"]

        # Handler should process save and return result
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        # Handler returns save result data
        assert "save_roll" in result
        assert "save_target" in result

    def test_invisibility_matches_source(self, spell_data_loader):
        """Verify Invisibility matches arcane_level_2_1.json."""
        spell = spell_data_loader("arcane_level_2_1.json", "invisibility")

        assert spell["level"] == 2
        assert spell["magic_type"] == "arcane"
        assert "1 hour per Level" in spell["duration"]
        assert spell["range"] == "240'"

    def test_invisibility_description_validation(self, spell_data_loader):
        """Verify Invisibility description contains key mechanics."""
        spell = spell_data_loader("arcane_level_2_1.json", "invisibility")

        # Verify description contains key mechanics from source
        assert "disappears from sight" in spell["description"]
        assert "attacks or casts a spell" in spell["description"]
        assert "invisibility is broken" in spell["description"]
        assert "gear" in spell["description"].lower() or "equipment" in spell["description"].lower()
        assert "light source" in spell["description"].lower()

    def test_invisibility_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_2_1.json", "invisibility")

        result = spell_resolver._handle_invisibility(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Verify 1 hour per level from source
        assert result["duration_hours"] == mock_caster.level
        # Verify effect breaks on attack from source
        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["breaks_on_attack"] is True
        assert effect.mechanical_effects["breaks_on_spell_cast"] is True
        assert effect.mechanical_effects["light_sources_still_shine"] is True

    def test_knock_matches_source(self, spell_data_loader):
        """Verify Knock matches arcane_level_2_1.json."""
        spell = spell_data_loader("arcane_level_2_1.json", "knock")

        assert spell["level"] == 2
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "Instant"

    def test_knock_description_validation(self, spell_data_loader):
        """Verify Knock description contains key mechanics."""
        spell = spell_data_loader("arcane_level_2_1.json", "knock")

        # Verify description contains key mechanics from source
        assert "door" in spell["description"].lower() or "portal" in spell["description"].lower()
        assert "Locks and bars" in spell["description"]
        assert "Glyphs of Sealing" in spell["description"]
        assert "Glyphs of Locking" in spell["description"]
        assert "1 Turn" in spell["description"]
        assert "Secret doors" in spell["description"]

    def test_knock_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_2_1.json", "knock")

        result = spell_resolver._handle_knock(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Verify instant duration from source
        assert result["duration_type"] == "instant"

    def test_knock_glyph_of_locking_1_turn(
        self, spell_data_loader, spell_resolver, mock_caster, fixed_dice_roller
    ):
        """Verify Glyph of Locking disabled for 1 Turn per source."""
        spell = spell_data_loader("arcane_level_2_1.json", "knock")

        assert "1 Turn" in spell["description"]

        spell_resolver._current_context = {"has_glyph_of_locking": True}
        result = spell_resolver._handle_knock(
            mock_caster, ["door"], fixed_dice_roller
        )

        assert result["glyph_disabled_duration"] == 1


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestPhase9EdgeCases:
    """Edge case tests for Phase 9 handlers."""

    def test_petrification_no_target(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test petrification with no target."""
        result = spell_resolver._handle_petrification(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] is None

    def test_invisibility_level_1_caster(self, spell_resolver, fixed_dice_roller):
        """Test invisibility with level 1 caster (1 hour duration)."""
        caster = MagicMock()
        caster.character_id = "apprentice"
        caster.level = 1

        result = spell_resolver._handle_invisibility(
            caster, ["target"], fixed_dice_roller
        )

        assert result["duration_hours"] == 1
        hints = result["narrative_context"]["hints"]
        assert any("1 hour" in hint for hint in hints)

    def test_knock_all_barriers(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test knock with every type of barrier."""
        spell_resolver._current_context = {
            "has_mundane_lock": True,
            "has_bar": True,
            "has_glyph_of_sealing": True,
            "has_glyph_of_locking": True,
            "is_secret_door": True
        }

        result = spell_resolver._handle_knock(
            mock_caster, ["super_locked_door"], fixed_dice_roller
        )

        assert len(result["effects_applied"]) == 5
        assert "mundane_lock_opened" in result["effects_applied"]
        assert "bar_removed" in result["effects_applied"]
        assert "glyph_of_sealing_dispelled" in result["effects_applied"]
        assert "glyph_of_locking_disabled" in result["effects_applied"]
        assert "secret_door_opened" in result["effects_applied"]

    def test_stone_to_flesh_without_existing_effect(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test stone to flesh when no petrification effect exists."""
        spell_resolver._current_context = {"mode": "stone_to_flesh"}

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, fixed_dice_roller
        )

        # Should still succeed - restoration narrative
        assert result["restored"] is True

    def test_all_handlers_work_without_context(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test all Phase 9 handlers work without context."""
        spell_resolver._current_context = None

        # Petrification defaults to flesh_to_stone
        result1 = spell_resolver._handle_petrification(
            mock_caster, ["target"], fixed_dice_roller
        )
        assert result1["mode"] == "flesh_to_stone"

        # Invisibility defaults to creature
        result2 = spell_resolver._handle_invisibility(
            mock_caster, ["target"], fixed_dice_roller
        )
        assert result2["target_type"] == "creature"

        # Knock defaults to locked door
        result3 = spell_resolver._handle_knock(
            mock_caster, ["door"], fixed_dice_roller
        )
        assert "mundane_lock_opened" in result3["effects_applied"]

    def test_petrification_with_controller_save_target(self, spell_resolver, mock_caster, mock_targets):
        """Test petrification uses controller's save target."""
        controller = MagicMock()
        target_char = MagicMock(spec=["level", "saving_throws"])
        target_char.level = 5
        target_char.saving_throws = MagicMock()
        target_char.saving_throws.hold = 10  # Easy save
        controller.get_character = MagicMock(return_value=target_char)
        spell_resolver._controller = controller

        roller = MagicMock()
        roller.roll = MagicMock(return_value=12)  # Would fail vs 14, succeeds vs 10

        result = spell_resolver._handle_petrification(
            mock_caster, mock_targets, roller
        )

        assert result["save_target"] == 10
        assert result["save_success"] is True
        assert result["petrified"] is False
