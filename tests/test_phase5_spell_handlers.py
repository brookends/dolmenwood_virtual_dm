"""
Phase 5 Spell Handler Tests - Utility and Transformation Spells

Tests for:
- Passwall (arcane level 5) - temporary passage through stone
- Fool's Gold (fairy glamour) - illusion on coins
- Ginger Snap (arcane level 3) - body part transformation

These tests verify:
1. Handler mechanics match spell descriptions
2. Duration tracking works correctly
3. Save mechanics are properly applied
4. Integration with actual spell JSON data
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.narrative.spell_resolver import (
    ActiveSpellEffect,
    DurationType,
    SpellResolver,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance for testing."""
    mock_controller = MagicMock()
    return SpellResolver(controller=mock_controller)


@pytest.fixture
def mock_caster():
    """Create a mock caster with standard attributes."""
    caster = MagicMock()
    caster.character_id = "test_caster_001"
    caster.level = 5
    caster.name = "Test Wizard"
    return caster


@pytest.fixture
def mock_dice_roller():
    """Create a mock dice roller with predictable results."""
    dice = MagicMock()
    dice.roll.return_value = 3  # Default roll result
    return dice


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
# PASSWALL HANDLER TESTS
# =============================================================================


class TestPasswallHandler:
    """Tests for the Passwall spell handler."""

    def test_passwall_creates_passage(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall creates a passage with correct dimensions."""
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert result["success"] is True
        assert result["passage_created"] is True
        assert result["diameter_feet"] == 5
        assert result["depth_feet"] == 10

    def test_passwall_duration_is_3_turns(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall has fixed 3 Turn duration."""
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert result["duration_turns"] == 3

    def test_passwall_affects_rock_and_stone(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall affects rock and stone materials."""
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert "rock" in result["material_affected"]
        assert "stone" in result["material_affected"]

    def test_passwall_creates_active_effect(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall creates a tracked active effect."""
        initial_effects = len(spell_resolver._active_effects)
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert len(spell_resolver._active_effects) == initial_effects + 1

        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "passwall"
        assert effect.duration_type == DurationType.TURNS
        assert effect.duration_remaining == 3

    def test_passwall_effect_has_passage_data(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that the active effect contains passage details."""
        spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["passage_type"] == "temporary_hole"
        assert effect.mechanical_effects["diameter_feet"] == 5
        assert effect.mechanical_effects["depth_feet"] == 10

    def test_passwall_blocks_when_ends(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passage closes when spell ends."""
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert result["blocks_when_ends"] is True

    def test_passwall_not_concentration(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall is not a concentration spell."""
        spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        effect = spell_resolver._active_effects[-1]
        assert effect.requires_concentration is False

    def test_passwall_narrative_context(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall provides narrative hints."""
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert "narrative_context" in result
        assert result["narrative_context"]["passage_open"] is True
        hints = result["narrative_context"]["hints"]
        assert any("5'" in hint for hint in hints)
        assert any("10'" in hint for hint in hints)

    def test_passwall_tracks_caster_level(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall records caster level."""
        mock_caster.level = 9
        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert result["caster_level"] == 9

    def test_passwall_no_creature_targets(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that passwall is a location effect with no creature targets."""
        spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        effect = spell_resolver._active_effects[-1]
        assert effect.target_type == "area"


# =============================================================================
# FOOL'S GOLD HANDLER TESTS
# =============================================================================


class TestFoolsGoldHandler:
    """Tests for the Fool's Gold glamour handler."""

    def test_fools_gold_calculates_max_coins(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that max coins is 20 per caster level."""
        mock_caster.level = 5
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["max_coins_per_day"] == 100  # 20 * 5

    def test_fools_gold_rolls_duration(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that duration is rolled with 1d6."""
        mock_dice_roller.roll.return_value = 4
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["duration_minutes"] == 4
        mock_dice_roller.roll.assert_any_call("1d6")

    def test_fools_gold_viewer_saves(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that viewers get saves to see through the illusion."""
        viewers = ["viewer_1", "viewer_2", "viewer_3"]
        # Alternate: fail, succeed, fail (rolls: 10, 15, 10)
        mock_dice_roller.roll.side_effect = [3, 10, 15, 10]  # First is duration

        result = spell_resolver._handle_fools_gold(mock_caster, viewers, mock_dice_roller)

        assert "viewer_1" in result["viewers_deceived"]
        assert "viewer_2" in result["viewers_saw_through"]
        assert "viewer_3" in result["viewers_deceived"]

    def test_fools_gold_all_viewers_deceived(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test when all viewers fail their saves."""
        viewers = ["victim_1", "victim_2"]
        mock_dice_roller.roll.return_value = 5  # All fail DC 14

        result = spell_resolver._handle_fools_gold(mock_caster, viewers, mock_dice_roller)

        assert len(result["viewers_deceived"]) == 2
        assert len(result["viewers_saw_through"]) == 0

    def test_fools_gold_all_viewers_see_through(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test when all viewers succeed on their saves."""
        viewers = ["skeptic_1", "skeptic_2"]
        mock_dice_roller.roll.return_value = 18  # All pass DC 14

        result = spell_resolver._handle_fools_gold(mock_caster, viewers, mock_dice_roller)

        assert len(result["viewers_deceived"]) == 0
        assert len(result["viewers_saw_through"]) == 2

    def test_fools_gold_creates_active_effect(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that fool's gold creates a tracked effect."""
        initial_effects = len(spell_resolver._active_effects)
        mock_dice_roller.roll.return_value = 3  # Duration
        spell_resolver._handle_fools_gold(mock_caster, ["viewer"], mock_dice_roller)

        assert len(spell_resolver._active_effects) == initial_effects + 1

        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "fools_gold"
        # Uses SPECIAL duration type since minutes isn't a standard duration type
        assert effect.duration_type == DurationType.SPECIAL
        assert effect.duration_unit == "minutes"

    def test_fools_gold_effect_tracks_glamour_details(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that effect data tracks glamour details."""
        mock_dice_roller.roll.return_value = 3  # Duration
        spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["glamour_type"] == "visual_illusion"
        assert effect.mechanical_effects["appears_as"] == "gold_coins"
        assert effect.mechanical_effects["actual_material"] == "copper_coins"

    def test_fools_gold_save_type_is_spell(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that fool's gold uses Save Versus Spell."""
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["save_type"] == "spell"

    def test_fools_gold_not_concentration(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that fool's gold is not a concentration glamour."""
        mock_dice_roller.roll.return_value = 3  # Duration
        spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        effect = spell_resolver._active_effects[-1]
        assert effect.requires_concentration is False

    def test_fools_gold_scales_with_level(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that coin limit scales with caster level."""
        mock_caster.level = 10
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["max_coins_per_day"] == 200  # 20 * 10

    def test_fools_gold_narrative_context(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that fool's gold provides narrative hints."""
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert "narrative_context" in result
        assert result["narrative_context"]["illusion_active"] is True


# =============================================================================
# GINGER SNAP HANDLER TESTS
# =============================================================================


class TestGingerSnapHandler:
    """Tests for the Ginger Snap spell handler."""

    def test_ginger_snap_limbs_scale_with_level(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that limbs affected = level // 3."""
        mock_caster.level = 9
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["limbs_affected_count"] == 3  # 9 // 3 = 3

    def test_ginger_snap_minimum_one_limb(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that at least 1 limb is affected even at low levels."""
        mock_caster.level = 1
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["limbs_affected_count"] == 1

    def test_ginger_snap_head_at_level_14(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that head is vulnerable at level 14+."""
        mock_caster.level = 14
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["head_vulnerable"] is True
        assert "head" in result["affected_parts"]

    def test_ginger_snap_no_head_below_14(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that head is not vulnerable below level 14."""
        mock_caster.level = 13
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["head_vulnerable"] is False
        assert "head" not in result["affected_parts"]

    def test_ginger_snap_rolls_duration(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that duration is rolled with 1d6."""
        mock_dice_roller.roll.return_value = 5
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["duration_rounds"] == 5

    def test_ginger_snap_target_saves(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that targets get Save Versus Hold."""
        targets = ["target_1", "target_2"]
        # First roll is duration (5), then saves (fail 10, pass 15)
        mock_dice_roller.roll.side_effect = [5, 10, 15]

        result = spell_resolver._handle_ginger_snap(mock_caster, targets, mock_dice_roller)

        assert "target_1" in result["targets_transformed"]
        assert "target_2" in result["targets_resisted"]

    def test_ginger_snap_save_type_is_hold(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that ginger snap uses Save Versus Hold."""
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["save_type"] == "hold"

    def test_ginger_snap_smashable_parts(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that transformed parts are marked as smashable."""
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["smashable"] is True

    def test_ginger_snap_permanent_loss(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that smashed parts are permanently destroyed."""
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["permanent_loss_on_smash"] is True

    def test_ginger_snap_creates_active_effect(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that ginger snap creates a tracked effect."""
        initial_effects = len(spell_resolver._active_effects)
        spell_resolver._handle_ginger_snap(mock_caster, ["target"], mock_dice_roller)

        assert len(spell_resolver._active_effects) == initial_effects + 1

        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "ginger_snap"
        assert effect.duration_type == DurationType.ROUNDS

    def test_ginger_snap_target_details_tracked(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that per-target transformation details are tracked."""
        mock_dice_roller.roll.return_value = 5  # Fail save
        mock_caster.level = 6
        result = spell_resolver._handle_ginger_snap(
            mock_caster, ["victim"], mock_dice_roller
        )

        assert "victim" in result["target_details"]
        details = result["target_details"]["victim"]
        assert "parts_transformed" in details
        assert "parts_smashed" in details
        assert details["parts_smashed"] == []

    def test_ginger_snap_body_parts_list(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that body parts are selected in order."""
        mock_caster.level = 12  # 4 limbs
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        expected_parts = ["left_arm", "right_arm", "left_leg", "right_leg"]
        assert result["affected_parts"] == expected_parts

    def test_ginger_snap_effect_data(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that effect data contains transformation details."""
        mock_caster.level = 6
        mock_dice_roller.roll.return_value = 5  # All rolls: duration and saves (fail)
        spell_resolver._handle_ginger_snap(mock_caster, ["target"], mock_dice_roller)

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["transformation_type"] == "gingerbread"
        assert effect.mechanical_effects["limbs_affected_count"] == 2
        assert effect.mechanical_effects["smashable"] is True

    def test_ginger_snap_narrative_mentions_head_danger(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that narrative warns about head vulnerability at high levels."""
        mock_caster.level = 14
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        hints = result["narrative_context"]["hints"]
        assert any("head" in hint.lower() for hint in hints)


# =============================================================================
# INTEGRATION TESTS WITH ACTUAL SPELL DATA
# =============================================================================


class TestPhase5SpellDataIntegration:
    """Integration tests that verify handlers against actual spell JSON data."""

    def test_passwall_dimensions_match_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Passwall handler produces dimensions matching source data."""
        spell = spell_data_loader("arcane_level_5_2.json", "passwall")

        # Source says: "5' diameter hole ... up to 10' deep" (uses ′ prime symbol)
        assert "5" in spell["description"] and "diameter" in spell["description"]
        assert "10" in spell["description"] and "deep" in spell["description"]

        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert result["diameter_feet"] == 5
        assert result["depth_feet"] == 10

    def test_passwall_duration_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Passwall duration matches '3 Turns' from source."""
        spell = spell_data_loader("arcane_level_5_2.json", "passwall")

        assert "3 Turns" in spell["duration"]

        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert result["duration_turns"] == 3

    def test_passwall_material_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Passwall affects solid rock or stone as per source."""
        spell = spell_data_loader("arcane_level_5_2.json", "passwall")

        assert "solid rock or stone" in spell["description"].lower()

        result = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)

        assert "rock" in result["material_affected"]
        assert "stone" in result["material_affected"]

    def test_fools_gold_coin_limit_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Fool's Gold coin limit matches '20 coins per Level' from source."""
        spell = spell_data_loader("glamours.json", "fools_gold")

        assert "20 coins per Level" in spell["description"]

        mock_caster.level = 3
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["max_coins_per_day"] == 60  # 20 * 3

    def test_fools_gold_duration_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Fool's Gold duration is 1d6 minutes per source."""
        spell = spell_data_loader("glamours.json", "fools_gold")

        assert "1d6 minutes" in spell["duration"]

        mock_dice_roller.roll.return_value = 4
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        mock_dice_roller.roll.assert_any_call("1d6")
        assert result["duration_minutes"] == 4

    def test_fools_gold_save_type_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Fool's Gold uses Save Versus Spell as per source."""
        spell = spell_data_loader("glamours.json", "fools_gold")

        assert "Save Versus Spell" in spell["description"]

        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["save_type"] == "spell"

    def test_ginger_snap_limbs_per_level_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Ginger Snap limbs affected matches '1 per 3 Levels' from source."""
        spell = spell_data_loader("hidden_spells.json", "ginger_snap")

        assert "every 3 Levels" in spell["description"]

        mock_caster.level = 9
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["limbs_affected_count"] == 3  # 9 // 3

    def test_ginger_snap_head_at_level_14_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Ginger Snap head vulnerability at Level 14 matches source."""
        spell = spell_data_loader("hidden_spells.json", "ginger_snap")

        assert "Level 14" in spell["description"]
        assert "head" in spell["description"].lower()

        mock_caster.level = 14
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["head_vulnerable"] is True

    def test_ginger_snap_duration_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Ginger Snap duration is 1d6 Rounds per source."""
        spell = spell_data_loader("hidden_spells.json", "ginger_snap")

        assert "1d6 Rounds" in spell["duration"]

        mock_dice_roller.roll.return_value = 4
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        # First roll should be 1d6 for duration
        mock_dice_roller.roll.assert_any_call("1d6")

    def test_ginger_snap_save_type_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Ginger Snap uses Save Versus Hold as per source."""
        spell = spell_data_loader("hidden_spells.json", "ginger_snap")

        assert "Save Versus Hold" in spell["description"]

        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["save_type"] == "hold"

    def test_ginger_snap_permanent_destruction_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify smashed parts are permanently destroyed per source."""
        spell = spell_data_loader("hidden_spells.json", "ginger_snap")

        assert "permanently destroyed" in spell["description"].lower()

        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["permanent_loss_on_smash"] is True


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestPhase5EdgeCases:
    """Edge case tests for Phase 5 spell handlers."""

    def test_passwall_with_no_caster_level(self, spell_resolver, mock_dice_roller):
        """Test passwall handles caster without level attribute."""
        caster = MagicMock(spec=[])  # No level attribute
        caster.character_id = "levelless"

        result = spell_resolver._handle_passwall(caster, [], mock_dice_roller)

        assert result["caster_level"] == 1  # Default to 1

    def test_fools_gold_no_viewers(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test fool's gold with no viewers."""
        result = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result["viewers_deceived"] == []
        assert result["viewers_saw_through"] == []
        assert result["success"] is True

    def test_ginger_snap_no_targets(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test ginger snap with no targets."""
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["targets_transformed"] == []
        assert result["targets_resisted"] == []
        assert result["success"] is True

    def test_ginger_snap_max_limbs_capped_at_4(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that limbs are capped at 4 before head is added."""
        mock_caster.level = 13  # 13 // 3 = 4 limbs, no head
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        # Should have exactly 4 limbs, no head
        assert result["limbs_affected_count"] == 4
        assert len([p for p in result["affected_parts"] if p != "head"]) == 4
        assert "head" not in result["affected_parts"]

    def test_ginger_snap_level_15_includes_head(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test level 15 includes both all limbs and head."""
        mock_caster.level = 15  # 15 // 3 = 5, but capped at 4 limbs + head
        result = spell_resolver._handle_ginger_snap(mock_caster, [], mock_dice_roller)

        assert result["head_vulnerable"] is True
        assert "head" in result["affected_parts"]
        # 4 limbs + head = 5 parts
        assert len(result["affected_parts"]) == 5

    def test_unique_effect_ids(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that each spell cast generates a unique effect ID."""
        result1 = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)
        result2 = spell_resolver._handle_passwall(mock_caster, [], mock_dice_roller)
        result3 = spell_resolver._handle_fools_gold(mock_caster, [], mock_dice_roller)

        assert result1["effect_id"] != result2["effect_id"]
        assert result2["effect_id"] != result3["effect_id"]
        assert result1["effect_id"] != result3["effect_id"]
