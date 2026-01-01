"""
Tests for Phase 10 spell handlers (remaining moderate/significant spells).

This module tests the following spells:
- Arcane Cypher (arcane level 2) - Transforms text into arcane sigils
- Trap the Soul (arcane level 6) - Traps/releases life force in gem
- Holy Quest (divine level 5) - Compels target to perform quest
- Polymorph (arcane level 4) - Transforms into another creature
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.narrative.spell_resolver import (
    ActiveSpellEffect,
    DurationType,
    SpellEffectType,
    SpellResolver,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver instance for testing."""
    resolver = SpellResolver()
    resolver._active_effects = []
    resolver._current_context = {}
    return resolver


@pytest.fixture
def mock_caster():
    """Create a mock caster with spec to prevent auto-attribute creation."""
    caster = MagicMock(spec=["character_id", "level"])
    caster.character_id = "caster_1"
    caster.level = 5
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
        "1d6": 3,
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
# ARCANE CYPHER TESTS
# =============================================================================


class TestArcaneCypherHandler:
    """Tests for the Arcane Cypher spell handler."""

    def test_basic_encryption_succeeds(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test basic text encryption."""
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["spellbook_page"], fixed_dice_roller
        )

        assert result["success"] is True
        assert result["spell_id"] == "arcane_cypher"
        assert result["max_pages"] == mock_caster.level

    def test_returns_correct_spell_metadata(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that handler returns correct metadata."""
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )

        assert result["spell_name"] == "Arcane Cypher"
        assert result["caster_id"] == mock_caster.character_id
        assert result["caster_level"] == mock_caster.level

    def test_max_pages_scales_with_level(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that max pages equals caster level."""
        mock_caster.level = 7
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )

        assert result["max_pages"] == 7

    def test_creates_permanent_effect(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that a permanent effect is created."""
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == 1
        effect = spell_resolver._active_effects[0]
        assert effect.duration_type == DurationType.PERMANENT

    def test_effect_tracks_encryption(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that effect tracks encryption details."""
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )

        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["encrypted"] is True
        assert mock_caster.character_id in effect.mechanical_effects["readable_by"]
        assert effect.mechanical_effects["decryption_method"] == "decipher_spell"

    def test_narrative_context_included(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that narrative context is included."""
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )

        assert "narrative_context" in result
        assert result["narrative_context"]["spell_cast"] is True
        assert len(result["narrative_context"]["hints"]) > 0


# =============================================================================
# TRAP THE SOUL TESTS
# =============================================================================


class TestTrapTheSoulHandler:
    """Tests for the Trap the Soul spell handler."""

    def test_trap_mode_succeeds_on_failed_save(self, spell_resolver, mock_caster, mock_targets):
        """Test soul trapping when target fails save."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Fails default save of 12

        result = spell_resolver._handle_trap_the_soul(
            mock_caster, mock_targets, roller
        )

        assert result["success"] is True
        assert result["soul_trapped"] is True
        assert result["save_success"] is False

    def test_trap_mode_fails_on_successful_save(self, spell_resolver, mock_caster, mock_targets):
        """Test target resists when save succeeds."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=15)  # Succeeds vs 12

        result = spell_resolver._handle_trap_the_soul(
            mock_caster, mock_targets, roller
        )

        assert result["soul_trapped"] is False
        assert result["save_success"] is True

    def test_creates_effect_on_trap(self, spell_resolver, mock_caster, mock_targets):
        """Test that effect is created when soul is trapped."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Fails save

        spell_resolver._handle_trap_the_soul(mock_caster, mock_targets, roller)

        assert len(spell_resolver._active_effects) == 1
        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["soul_trapped"] is True
        assert effect.mechanical_effects["days_until_death"] == 30

    def test_effect_tracks_30_day_timer(self, spell_resolver, mock_caster, mock_targets):
        """Test that 30-day death timer is tracked."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)

        spell_resolver._handle_trap_the_soul(mock_caster, mock_targets, roller)

        effect = spell_resolver._active_effects[0]
        assert effect.duration_remaining == 30
        assert effect.duration_unit == "days"

    def test_release_mode_works(self, spell_resolver, mock_caster, mock_targets):
        """Test soul release mode."""
        spell_resolver._current_context = {"mode": "release"}

        result = spell_resolver._handle_trap_the_soul(
            mock_caster, mock_targets, MagicMock()
        )

        assert result["mode"] == "release"
        assert result["soul_released"] is True

    def test_receptacle_tracked(self, spell_resolver, mock_caster, mock_targets):
        """Test that receptacle ID is tracked."""
        spell_resolver._current_context = {"receptacle_id": "ruby_gem"}
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)

        result = spell_resolver._handle_trap_the_soul(
            mock_caster, mock_targets, roller
        )

        assert result["receptacle_id"] == "ruby_gem"


# =============================================================================
# HOLY QUEST TESTS
# =============================================================================


class TestHolyQuestHandler:
    """Tests for the Holy Quest spell handler."""

    def test_compulsion_on_failed_save(self, spell_resolver, mock_caster, mock_targets):
        """Test target is compelled when save fails."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)  # Fails default save of 14

        result = spell_resolver._handle_holy_quest(
            mock_caster, mock_targets, roller
        )

        assert result["success"] is True
        assert result["compelled"] is True
        assert result["save_success"] is False

    def test_resistance_on_successful_save(self, spell_resolver, mock_caster, mock_targets):
        """Test target resists when save succeeds."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=18)  # Succeeds vs 14

        result = spell_resolver._handle_holy_quest(
            mock_caster, mock_targets, roller
        )

        assert result["compelled"] is False
        assert result["save_success"] is True

    def test_creates_compulsion_effect(self, spell_resolver, mock_caster, mock_targets):
        """Test that compulsion effect is created."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)  # Fails save

        spell_resolver._handle_holy_quest(mock_caster, mock_targets, roller)

        assert len(spell_resolver._active_effects) == 1
        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["compelled"] is True

    def test_tracks_penalty(self, spell_resolver, mock_caster, mock_targets):
        """Test that -2 penalty is tracked."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)

        spell_resolver._handle_holy_quest(mock_caster, mock_targets, roller)

        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["refusal_penalty"]["attack_rolls"] == -2
        assert effect.mechanical_effects["refusal_penalty"]["saving_throws"] == -2

    def test_quest_description_from_context(self, spell_resolver, mock_caster, mock_targets):
        """Test quest description is taken from context."""
        spell_resolver._current_context = {"quest": "rescue the princess"}
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)

        result = spell_resolver._handle_holy_quest(
            mock_caster, mock_targets, roller
        )

        assert result["quest_description"] == "rescue the princess"

    def test_special_duration_type(self, spell_resolver, mock_caster, mock_targets):
        """Test that duration is until quest complete."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)

        spell_resolver._handle_holy_quest(mock_caster, mock_targets, roller)

        effect = spell_resolver._active_effects[0]
        assert effect.duration_type == DurationType.SPECIAL
        assert effect.duration_unit == "until_quest_complete"


# =============================================================================
# POLYMORPH TESTS
# =============================================================================


class TestPolymorphHandler:
    """Tests for the Polymorph spell handler."""

    def test_self_cast_succeeds(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test self-cast polymorph succeeds."""
        result = spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        assert result["success"] is True
        assert result["is_self_cast"] is True

    def test_self_cast_duration(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test self-cast has limited duration."""
        result = spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        # Duration = 1d6 (3) + level (5) = 8 turns
        assert result["duration"] == 8
        assert result["duration_unit"] == "turns"

    def test_other_cast_permanent(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test casting on others is permanent."""
        result = spell_resolver._handle_polymorph(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["is_self_cast"] is False
        assert result["duration"] is None
        assert result["duration_unit"] == "permanent"

    def test_level_restriction_self(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test self-cast fails if form level > caster level."""
        spell_resolver._current_context = {"new_form": "dragon", "new_form_level": 10}

        result = spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        assert result["success"] is False
        assert result["failure_reason"] == "new_form_level_too_high"

    def test_level_restriction_other(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test other-cast fails if form level > 2x caster level."""
        spell_resolver._current_context = {"new_form": "dragon", "new_form_level": 12}

        result = spell_resolver._handle_polymorph(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["success"] is False
        assert result["failure_reason"] == "new_form_level_too_high"

    def test_unwilling_target_save(self, spell_resolver, mock_caster, mock_targets):
        """Test unwilling target can save."""
        spell_resolver._current_context = {"is_unwilling": True}
        roller = MagicMock()
        roller.roll = MagicMock(return_value=18)  # Succeeds vs 14

        result = spell_resolver._handle_polymorph(
            mock_caster, mock_targets, roller
        )

        assert result["success"] is False
        assert result["failure_reason"] == "target_resisted"

    def test_creates_polymorph_effect(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that polymorph effect is created."""
        spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        assert len(spell_resolver._active_effects) == 1
        effect = spell_resolver._active_effects[0]
        assert effect.spell_id == "polymorph"

    def test_self_cast_preserves_stats(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test self-cast preserves HP/saves/attack/intelligence."""
        spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["preserves_hp"] is True
        assert effect.mechanical_effects["preserves_saves"] is True
        assert effect.mechanical_effects["preserves_attack"] is True
        assert effect.mechanical_effects["preserves_intelligence"] is True

    def test_other_cast_fully_transforms(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test other-cast acquires all powers."""
        spell_resolver._handle_polymorph(
            mock_caster, mock_targets, fixed_dice_roller
        )

        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["acquires_special_powers"] is True
        assert effect.mechanical_effects["preserves_saves"] is False

    def test_reverts_on_death(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that polymorphed creature reverts on death."""
        spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["reverts_on_death"] is True

    def test_cannot_cast_spells(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test that polymorphed caster cannot cast spells."""
        spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        effect = spell_resolver._active_effects[0]
        assert effect.mechanical_effects["can_cast_spells"] is False


# =============================================================================
# INTEGRATION TESTS WITH SPELL DATA
# =============================================================================


class TestPhase10SpellDataIntegration:
    """Integration tests that verify handlers against actual spell JSON data."""

    def test_arcane_cypher_matches_source(self, spell_data_loader):
        """Verify Arcane Cypher matches arcane_level_2_1.json."""
        spell = spell_data_loader("arcane_level_2_1.json", "arcane_cypher")

        assert spell["level"] == 2
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "Permanent"
        assert spell["range"] == "5'"

    def test_arcane_cypher_description_validation(self, spell_data_loader):
        """Verify Arcane Cypher description contains key mechanics."""
        spell = spell_data_loader("arcane_level_2_1.json", "arcane_cypher")

        assert "arcane sigils" in spell["description"]
        assert "1 page" in spell["description"]
        assert "per Level" in spell["description"]
        assert "Decipher" in spell["description"]

    def test_arcane_cypher_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_2_1.json", "arcane_cypher")

        result = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )

        # Verify permanent duration from source
        effect = spell_resolver._active_effects[-1]
        assert effect.duration_type == DurationType.PERMANENT
        # Verify 1 page per level from source
        assert result["max_pages"] == mock_caster.level

    def test_trap_the_soul_matches_source(self, spell_data_loader):
        """Verify Trap the Soul matches hidden_spells.json."""
        spell = spell_data_loader("hidden_spells.json", "trap_the_soul")

        assert spell["level"] == 6
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "Instant"
        assert spell["range"] == "20′"

    def test_trap_the_soul_description_validation(self, spell_data_loader):
        """Verify Trap the Soul description contains key mechanics."""
        spell = spell_data_loader("hidden_spells.json", "trap_the_soul")

        assert "Save Versus Doom" in spell["description"]
        assert "30 days" in spell["description"]
        assert "comatose" in spell["description"]
        assert "receptacle" in spell["description"]
        assert "1,000gp per Level" in spell["description"]

    def test_trap_the_soul_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("hidden_spells.json", "trap_the_soul")

        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)  # Failed save

        result = spell_resolver._handle_trap_the_soul(
            mock_caster, mock_targets, roller
        )

        # Verify 30 days until death from source
        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["days_until_death"] == 30
        assert effect.mechanical_effects["body_comatose"] is True

    def test_holy_quest_matches_source(self, spell_data_loader):
        """Verify Holy Quest matches holy_level_5.json."""
        spell = spell_data_loader("holy_level_5.json", "holy_quest")

        assert spell["level"] == 5
        assert spell["magic_type"] == "divine"
        assert "Until quest is completed" in spell["duration"]
        assert spell["range"] == "30′"

    def test_holy_quest_description_validation(self, spell_data_loader):
        """Verify Holy Quest description contains key mechanics."""
        spell = spell_data_loader("holy_level_5.json", "holy_quest")

        assert "clap of thunder" in spell["description"]
        assert "ray of holy light" in spell["description"]
        assert "–2 penalty" in spell["description"] or "-2 penalty" in spell["description"]
        assert "Attack Rolls" in spell["description"]
        assert "Saving Throws" in spell["description"]
        assert "Save Versus Spell" in spell["description"]

    def test_holy_quest_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, mock_targets
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("holy_level_5.json", "holy_quest")

        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)  # Failed save

        result = spell_resolver._handle_holy_quest(
            mock_caster, mock_targets, roller
        )

        # Verify -2 penalty from source
        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["refusal_penalty"]["attack_rolls"] == -2
        assert effect.mechanical_effects["refusal_penalty"]["saving_throws"] == -2

    def test_polymorph_matches_source(self, spell_data_loader):
        """Verify Polymorph matches arcane_level_4_2.json."""
        spell = spell_data_loader("arcane_level_4_2.json", "polymorph")

        assert spell["level"] == 4
        assert spell["magic_type"] == "arcane"
        assert "1d6 Turns" in spell["duration"]
        assert spell["range"] == "60′"

    def test_polymorph_description_validation(self, spell_data_loader):
        """Verify Polymorph description contains key mechanics."""
        spell = spell_data_loader("arcane_level_4_2.json", "polymorph")

        assert "Cast on self" in spell["description"]
        assert "Cast on another" in spell["description"]
        assert "Hit Points" in spell["description"]
        assert "unable to cast spells" in spell["description"]
        assert "Save Versus Spell" in spell["description"]
        assert "reversion" in spell["description"].lower() or "return" in spell["description"].lower()

    def test_polymorph_handler_matches_source(
        self, spell_data_loader, spell_resolver, mock_caster, fixed_dice_roller
    ):
        """Verify handler behavior matches source description."""
        spell = spell_data_loader("arcane_level_4_2.json", "polymorph")

        result = spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )

        # Verify self-cast preserves stats from source
        effect = spell_resolver._active_effects[-1]
        assert effect.mechanical_effects["preserves_hp"] is True
        assert effect.mechanical_effects["can_cast_spells"] is False


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestPhase10EdgeCases:
    """Edge case tests for Phase 10 handlers."""

    def test_arcane_cypher_empty_targets(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test Arcane Cypher with empty targets defaults to 'text'."""
        result = spell_resolver._handle_arcane_cypher(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] == "text"
        assert result["success"] is True

    def test_trap_the_soul_empty_targets(self, spell_resolver, mock_caster):
        """Test Trap the Soul with empty targets."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)

        result = spell_resolver._handle_trap_the_soul(
            mock_caster, [], roller
        )

        assert result["target_id"] is None

    def test_holy_quest_empty_targets(self, spell_resolver, mock_caster):
        """Test Holy Quest with empty targets."""
        roller = MagicMock()
        roller.roll = MagicMock(return_value=10)

        result = spell_resolver._handle_holy_quest(
            mock_caster, [], roller
        )

        assert result["target_id"] is None

    def test_polymorph_empty_targets_defaults_to_caster(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test Polymorph with empty targets defaults to self-cast."""
        result = spell_resolver._handle_polymorph(
            mock_caster, [], fixed_dice_roller
        )

        assert result["target_id"] == mock_caster.character_id
        assert result["is_self_cast"] is True

    def test_polymorph_level_1_caster(self, spell_resolver, fixed_dice_roller):
        """Test Polymorph with level 1 caster."""
        caster = MagicMock(spec=["character_id", "level"])
        caster.character_id = "novice"
        caster.level = 1

        # Set form level to 1 so it's within caster's limits
        spell_resolver._current_context = {"new_form": "cat", "new_form_level": 1}

        result = spell_resolver._handle_polymorph(
            caster, [caster.character_id], fixed_dice_roller
        )

        # Duration = 1d6 (3) + level (1) = 4 turns
        assert result["success"] is True
        assert result["duration"] == 4

    def test_polymorph_high_level_form_on_other(self, spell_resolver, mock_caster, mock_targets, fixed_dice_roller):
        """Test high level form succeeds on other target when within limits."""
        # Level 5 caster can polymorph others into up to level 10 form
        spell_resolver._current_context = {"new_form": "giant", "new_form_level": 10}

        result = spell_resolver._handle_polymorph(
            mock_caster, mock_targets, fixed_dice_roller
        )

        assert result["success"] is True
        assert result["new_form_level"] == 10

    def test_all_handlers_work_without_context(self, spell_resolver, mock_caster, fixed_dice_roller):
        """Test all handlers work when _current_context is not set."""
        # Remove context entirely
        if hasattr(spell_resolver, "_current_context"):
            delattr(spell_resolver, "_current_context")

        result1 = spell_resolver._handle_arcane_cypher(
            mock_caster, ["text"], fixed_dice_roller
        )
        assert result1["success"] is True

        roller = MagicMock()
        roller.roll = MagicMock(return_value=5)
        result2 = spell_resolver._handle_trap_the_soul(
            mock_caster, ["target"], roller
        )
        assert result2["success"] is True

        roller2 = MagicMock()
        roller2.roll = MagicMock(return_value=10)
        result3 = spell_resolver._handle_holy_quest(
            mock_caster, ["target"], roller2
        )
        assert result3["success"] is True

        result4 = spell_resolver._handle_polymorph(
            mock_caster, [mock_caster.character_id], fixed_dice_roller
        )
        assert result4["success"] is True
