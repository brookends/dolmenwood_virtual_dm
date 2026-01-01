"""
Phase 6 Spell Handler Tests - Door/Lock and Trap Spells

Tests for:
- Through the Keyhole (fairy glamour) - instant door bypass
- Lock Singer (mossling knack) - charm locks with song
- Serpent Glyph (arcane level 3) - trap glyph with temporal stasis

These tests verify:
1. Handler mechanics match spell descriptions
2. Level-based ability scaling (Lock Singer)
3. Trap trigger mechanics (Serpent Glyph)
4. Integration with actual spell JSON data
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

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
# THROUGH THE KEYHOLE HANDLER TESTS
# =============================================================================


class TestThroughTheKeyholeHandler:
    """Tests for the Through the Keyhole glamour handler."""

    def test_basic_door_bypass(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test successful bypass of a normal door."""
        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["teleported"] is True
        assert result["door_id"] == "door_123"

    def test_instant_effect(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that Through the Keyhole is an instant effect."""
        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123"], mock_dice_roller
        )

        # Should succeed immediately without duration tracking
        assert result["success"] is True
        assert "duration" not in result or result.get("duration") is None

    def test_magically_sealed_door_requires_save(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that magically sealed doors require Save Versus Spell."""
        # Roll high enough to pass save
        mock_dice_roller.roll.return_value = 15

        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123", "magically_sealed"], mock_dice_roller
        )

        assert result["is_magically_sealed"] is True
        assert result["bypass_succeeded"] is True

    def test_magically_sealed_door_failed_save(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test failure to bypass magically sealed door on failed save."""
        # Roll too low to pass save
        mock_dice_roller.roll.return_value = 5

        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123", "magically_sealed"], mock_dice_roller
        )

        assert result["is_magically_sealed"] is True
        assert result["bypass_succeeded"] is False
        assert result["teleported"] is False

    def test_usage_limit_tracked(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that usage limit is tracked (once per day per door)."""
        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123"], mock_dice_roller
        )

        assert result["usage_limit"] == "once_per_day_per_door"

    def test_narrative_context_success(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test narrative hints for successful bypass."""
        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123"], mock_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("keyhole" in hint for hint in hints)
        assert result["narrative_context"]["glamour_used"] is True

    def test_narrative_context_failure(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test narrative hints for failed bypass."""
        mock_dice_roller.roll.return_value = 5  # Fail save

        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123", "magically_sealed"], mock_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("fail" in hint.lower() or "prevent" in hint.lower() for hint in hints)

    def test_caster_level_tracked(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that caster level is recorded."""
        mock_caster.level = 7
        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_123"], mock_dice_roller
        )

        assert result["caster_level"] == 7

    def test_unknown_door_default(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test handling when no door ID provided."""
        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, [], mock_dice_roller
        )

        assert result["door_id"] == "unknown_door"
        assert result["success"] is True


# =============================================================================
# LOCK SINGER HANDLER TESTS
# =============================================================================


class TestLockSingerHandler:
    """Tests for the Lock Singer knack handler."""

    def test_open_simple_lock_success(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test successful opening of simple lock (2-in-6 chance)."""
        mock_caster.level = 1
        mock_dice_roller.roll.return_value = 2  # Succeeds (<=2)

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_simple"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["ability_used"] == "open_simple"
        assert result["chance"] == "2-in-6"

    def test_open_simple_lock_failure(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test failed opening of simple lock (roll > 2)."""
        mock_caster.level = 1
        mock_dice_roller.roll.return_value = 5  # Fails (>2)

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_simple"], mock_dice_roller
        )

        assert result["success"] is False
        assert result["roll"] == 5

    def test_locate_key_level_3(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test locate key ability at level 3+."""
        mock_caster.level = 3

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "locate_key"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["key_location_revealed"] is True

    def test_locate_key_below_level_3(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test locate key fails below level 3."""
        mock_caster.level = 2

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "locate_key"], mock_dice_roller
        )

        assert result["success"] is False
        assert "requires higher level" in result.get("reason", "")

    def test_snap_shut_level_5(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test snap shut ability at level 5+."""
        mock_caster.level = 5

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "snap_shut"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["range_feet"] == 30

    def test_open_any_level_7(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test open any lock ability at level 7+."""
        mock_caster.level = 7
        mock_dice_roller.roll.return_value = 1  # Success

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_any"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["ability_used"] == "open_any"

    def test_magical_lock_backfire_risk(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test magical lock backfire on 1-in-6."""
        mock_caster.level = 7
        # First roll: 2 (success), second roll: 1 (backfire), third roll: 3 (seal duration)
        mock_dice_roller.roll.side_effect = [2, 1, 3]

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_any", "magical"], mock_dice_roller
        )

        assert result["success"] is True  # Lock still opens
        assert result["backfire"] is True
        assert result["mouth_sealed_days"] == 3

    def test_magical_lock_no_backfire(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test magical lock opened without backfire."""
        mock_caster.level = 7
        # First roll: 2 (success), second roll: 4 (no backfire)
        mock_dice_roller.roll.side_effect = [2, 4]

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_any", "magical"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["backfire"] is False

    def test_narrative_context_success(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test narrative hints for successful lock singing."""
        mock_caster.level = 1
        mock_dice_roller.roll.return_value = 1

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_simple"], mock_dice_roller
        )

        assert "narrative_context" in result
        assert result["narrative_context"]["knack_used"] is True

    def test_narrative_context_backfire(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test narrative mentions backfire consequence."""
        mock_caster.level = 7
        mock_dice_roller.roll.side_effect = [2, 1, 2]  # Success, backfire, 2 days

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_any", "magical"], mock_dice_roller
        )

        hints = result["narrative_context"]["hints"]
        assert any("backfire" in hint.lower() for hint in hints)


# =============================================================================
# SERPENT GLYPH HANDLER TESTS
# =============================================================================


class TestSerpentGlyphHandler:
    """Tests for the Serpent Glyph spell handler."""

    def test_place_glyph_on_surface(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test placing a visible glyph on a surface."""
        result = spell_resolver._handle_serpent_glyph(
            mock_caster, ["wall_section_1", "surface"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["glyph_type"] == "surface"
        assert result["is_visible"] is True
        assert result["duration"] == "permanent_until_triggered"

    def test_place_glyph_on_text(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test placing a hidden glyph on text."""
        result = spell_resolver._handle_serpent_glyph(
            mock_caster, ["book_page_1", "text"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["glyph_type"] == "text"
        assert result["is_visible"] is False

    def test_glyph_requires_material_component(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that material component is tracked."""
        result = spell_resolver._handle_serpent_glyph(
            mock_caster, ["surface_1", "surface"], mock_dice_roller
        )

        assert "powdered amber" in result["material_component"]
        assert "100gp" in result["material_component"]

    def test_trigger_glyph_attack_hits(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test triggered glyph with successful attack."""
        mock_caster.level = 5
        # First roll: attack (15), second roll: stasis duration (3)
        mock_dice_roller.roll.side_effect = [15, 3]

        result = spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )

        assert result["triggered"] is True
        assert result["attack_hits"] is True
        assert result["stasis_applied"] is True
        assert result["stasis_duration_days"] == 3

    def test_trigger_glyph_attack_misses(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test triggered glyph when attack misses."""
        mock_caster.level = 1
        mock_dice_roller.roll.return_value = 2  # Low roll + low level = miss

        result = spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )

        assert result["triggered"] is True
        assert result["attack_hits"] is False
        assert result["stasis_applied"] is False

    def test_attack_bonus_equals_caster_level(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that attack bonus equals caster level."""
        mock_caster.level = 8
        mock_dice_roller.roll.return_value = 5

        result = spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )

        assert result["attack_bonus"] == 8
        assert result["attack_total"] == 13  # 5 + 8

    def test_stasis_effect_created(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that temporal stasis effect is created on hit."""
        mock_caster.level = 5
        mock_dice_roller.roll.side_effect = [15, 4]  # Hit, 4 days stasis

        initial_effects = len(spell_resolver._active_effects)
        spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1

        effect = spell_resolver._active_effects[-1]
        assert "stasis" in effect.spell_name.lower()
        assert effect.duration_type == DurationType.DAYS
        assert effect.duration_remaining == 4

    def test_stasis_effect_properties(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test temporal stasis effect has correct properties."""
        mock_caster.level = 5
        mock_dice_roller.roll.side_effect = [15, 3]

        spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )

        effect = spell_resolver._active_effects[-1]
        mech = effect.mechanical_effects

        assert mech["condition"] == "temporal_stasis"
        assert mech["cannot_move"] is True
        assert mech["cannot_perceive"] is True
        assert mech["cannot_act"] is True
        assert mech["invulnerable"] is True
        assert mech["dispellable"] is True

    def test_glyph_placement_creates_effect(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that placing a glyph creates a tracked effect."""
        initial_effects = len(spell_resolver._active_effects)
        spell_resolver._handle_serpent_glyph(
            mock_caster, ["surface_1", "surface"], mock_dice_roller
        )

        assert len(spell_resolver._active_effects) == initial_effects + 1

        effect = spell_resolver._active_effects[-1]
        assert effect.spell_id == "serpent_glyph"
        assert effect.duration_type == DurationType.PERMANENT

    def test_glyph_trap_data_stored(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that glyph trap data is stored in effect."""
        mock_caster.level = 6
        spell_resolver._handle_serpent_glyph(
            mock_caster, ["surface_1", "surface"], mock_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        mech = effect.mechanical_effects

        assert mech["trap_type"] == "serpent_glyph"
        assert mech["attack_bonus"] == 6
        assert mech["trigger_action"] == "touch"

    def test_text_glyph_trigger_is_read(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that text glyphs trigger on reading."""
        spell_resolver._handle_serpent_glyph(
            mock_caster, ["book_1", "text"], mock_dice_roller
        )

        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["trigger_action"] == "read"
        assert effect.mechanical_effects["detect_magic_reveals"] is True

    def test_narrative_context_placement(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test narrative hints for glyph placement."""
        result = spell_resolver._handle_serpent_glyph(
            mock_caster, ["surface_1", "surface"], mock_dice_roller
        )

        assert "narrative_context" in result
        assert result["narrative_context"]["glyph_placed"] is True
        hints = result["narrative_context"]["hints"]
        assert any("amber" in hint for hint in hints)

    def test_narrative_context_trigger_hit(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test narrative hints for triggered glyph that hits."""
        mock_dice_roller.roll.side_effect = [18, 2]  # Hit, 2 days

        result = spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )

        hints = result["narrative_context"]["hints"]
        assert any("serpent" in hint.lower() for hint in hints)
        assert any("frozen" in hint or "stasis" in hint for hint in hints)


# =============================================================================
# INTEGRATION TESTS WITH ACTUAL SPELL DATA
# =============================================================================


class TestPhase6SpellDataIntegration:
    """Integration tests that verify handlers against actual spell JSON data."""

    def test_through_the_keyhole_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Through the Keyhole matches glamours.json."""
        spell = spell_data_loader("glamours.json", "through_the_keyhole")

        assert spell["magic_type"] == "fairy_glamour"
        assert "keyhole" in spell["description"].lower()
        assert "Magically sealed" in spell["description"]
        assert "Save Versus Spell" in spell["description"]

    def test_through_the_keyhole_instant_duration(self, spell_data_loader):
        """Verify Through the Keyhole has instant duration."""
        spell = spell_data_loader("glamours.json", "through_the_keyhole")

        assert spell["duration"] == "Instant"

    def test_through_the_keyhole_usage_limit_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify usage limit matches 'Once per day per door'."""
        spell = spell_data_loader("glamours.json", "through_the_keyhole")

        assert "Once per day per door" in spell["description"]

        result = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_1"], mock_dice_roller
        )
        assert result["usage_limit"] == "once_per_day_per_door"

    def test_lock_singer_matches_source(self, spell_data_loader):
        """Verify Lock Singer matches knacks.json."""
        spell = spell_data_loader("knacks.json", "lock_singer")

        assert spell["magic_type"] == "knack"
        assert spell["kindred"] == "Mossling"
        assert len(spell["abilities"]) == 4  # 4 level-based abilities

    def test_lock_singer_level_1_ability(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Level 1 ability: 2-in-6 per Turn."""
        spell = spell_data_loader("knacks.json", "lock_singer")
        level_1_ability = spell["abilities"][0]

        assert level_1_ability["level"] == 1
        assert "2-in-6" in level_1_ability["description"]

        mock_caster.level = 1
        mock_dice_roller.roll.return_value = 2

        result = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_simple"], mock_dice_roller
        )
        assert result["chance"] == "2-in-6"

    def test_lock_singer_level_7_backfire(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify Level 7 backfire risk: 1-in-6 for magical locks."""
        spell = spell_data_loader("knacks.json", "lock_singer")
        level_7_ability = spell["abilities"][3]

        assert level_7_ability["level"] == 7
        assert "1-in-6" in level_7_ability["description"]
        assert "backfiring" in level_7_ability["description"]
        assert "1d4 days" in level_7_ability["description"]

    def test_serpent_glyph_matches_source(self, spell_data_loader):
        """Verify Serpent Glyph matches arcane_level_3_2.json."""
        spell = spell_data_loader("arcane_level_3_2.json", "serpent_glyph")

        assert spell["level"] == 3
        assert spell["magic_type"] == "arcane"
        assert "permanent until triggered" in spell["duration"].lower()

    def test_serpent_glyph_attack_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify attack bonus equals caster level per source."""
        spell = spell_data_loader("arcane_level_3_2.json", "serpent_glyph")

        assert "Attack is equal to the caster's Level" in spell["description"]

        mock_caster.level = 7
        mock_dice_roller.roll.return_value = 10

        result = spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )
        assert result["attack_bonus"] == 7

    def test_serpent_glyph_stasis_duration_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Verify stasis duration is 1d4 days per source."""
        spell = spell_data_loader("arcane_level_3_2.json", "serpent_glyph")

        assert "1d4 days" in spell["description"]

        mock_dice_roller.roll.side_effect = [18, 3]  # Hit, 3 days

        result = spell_resolver._handle_serpent_glyph(
            mock_caster,
            ["surface_1", "surface", "triggered", "victim_1"],
            mock_dice_roller,
        )
        assert result["stasis_duration_days"] == 3

    def test_serpent_glyph_material_component_matches_source(self, spell_data_loader):
        """Verify material component: 100gp powdered amber."""
        spell = spell_data_loader("arcane_level_3_2.json", "serpent_glyph")

        assert "powdered amber" in spell["description"]
        assert "100gp" in spell["description"]


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestPhase6EdgeCases:
    """Edge case tests for Phase 6 spell handlers."""

    def test_through_keyhole_no_caster_level(self, spell_resolver, mock_dice_roller):
        """Test Through the Keyhole with caster missing level attribute."""
        caster = MagicMock(spec=[])
        caster.character_id = "levelless"

        result = spell_resolver._handle_through_the_keyhole(
            caster, ["door_1"], mock_dice_roller
        )

        assert result["caster_level"] == 1  # Default to 1

    def test_lock_singer_empty_targets(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test Lock Singer with no targets."""
        result = spell_resolver._handle_lock_singer(
            mock_caster, [], mock_dice_roller
        )

        assert result["lock_id"] == "unknown_lock"
        assert result["ability_used"] == "open_simple"

    def test_serpent_glyph_empty_targets(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test Serpent Glyph with no targets defaults to surface."""
        result = spell_resolver._handle_serpent_glyph(
            mock_caster, [], mock_dice_roller
        )

        assert result["surface_id"] == "unknown_surface"
        assert result["glyph_type"] == "surface"

    def test_unique_effect_ids_phase6(self, spell_resolver, mock_caster, mock_dice_roller):
        """Test that each spell generates unique effect IDs."""
        result1 = spell_resolver._handle_through_the_keyhole(
            mock_caster, ["door_1"], mock_dice_roller
        )
        result2 = spell_resolver._handle_lock_singer(
            mock_caster, ["lock_1", "open_simple"], mock_dice_roller
        )
        result3 = spell_resolver._handle_serpent_glyph(
            mock_caster, ["surface_1", "surface"], mock_dice_roller
        )

        assert result1["effect_id"] != result2["effect_id"]
        assert result2["effect_id"] != result3["effect_id"]
        assert result1["effect_id"] != result3["effect_id"]

    def test_lock_singer_high_level_all_abilities(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Test that high level Mossling can use all abilities."""
        mock_caster.level = 10
        mock_dice_roller.roll.return_value = 1

        # Should be able to use all abilities
        for ability in ["open_simple", "locate_key", "snap_shut", "open_any"]:
            result = spell_resolver._handle_lock_singer(
                mock_caster, ["lock_1", ability], mock_dice_roller
            )
            assert result["success"] is True, f"Failed for ability: {ability}"
