"""
Tests for Phase 3 Spell Handlers - Dispel Magic.

Per Dolmenwood source:
- All spell effects in a 20' cube within range are unravelled
- Effects created by lower Level casters are automatically dispelled
- 5% chance per Level difference that higher-Level caster's magic resists
- Magic items are unaffected
- Curses from spells (e.g. Hex Weaving) are affected
- Curses from magic items are unaffected
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.narrative.spell_resolver import (
    SpellResolver,
    ActiveSpellEffect,
    SpellEffectType,
    DurationType,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def spell_resolver():
    """Create a SpellResolver with a mock controller."""
    controller = MagicMock()
    resolver = SpellResolver(controller)
    return resolver


@pytest.fixture
def mock_caster():
    """Create a mock caster character."""
    caster = MagicMock()
    caster.character_id = "caster_1"
    caster.name = "Test Wizard"
    caster.level = 5
    return caster


@pytest.fixture
def low_level_caster():
    """Create a mock low-level caster."""
    caster = MagicMock()
    caster.character_id = "low_caster"
    caster.name = "Apprentice"
    caster.level = 2
    return caster


@pytest.fixture
def high_level_caster():
    """Create a mock high-level caster."""
    caster = MagicMock()
    caster.character_id = "high_caster"
    caster.name = "Archmage"
    caster.level = 10
    return caster


@pytest.fixture
def mock_dice_roller():
    """Create a mock dice roller."""
    roller = MagicMock()
    roller.roll.return_value = MagicMock(total=50)  # Mid-range roll
    return roller


@pytest.fixture
def create_active_effect():
    """Factory fixture to create active spell effects."""
    def _create(
        spell_id: str,
        spell_name: str,
        caster_id: str,
        caster_level: int,
        target_id: str,
        condition: str = None,
        from_magic_item: bool = False,
    ) -> ActiveSpellEffect:
        effect = ActiveSpellEffect(
            spell_id=spell_id,
            spell_name=spell_name,
            caster_id=caster_id,
            caster_level=caster_level,
            target_id=target_id,
            effect_type=SpellEffectType.MECHANICAL,
            duration_type=DurationType.TURNS,
            duration_remaining=10,
            is_active=True,
        )
        if condition:
            effect.mechanical_effects["condition"] = condition
        if from_magic_item:
            effect.mechanical_effects["from_magic_item"] = True
        return effect
    return _create


# =============================================================================
# DISPEL MAGIC HANDLER TESTS
# =============================================================================


class TestDispelMagicHandler:
    """Tests for the Dispel Magic spell handler."""

    def test_dispel_magic_no_effects_to_dispel(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Dispel Magic with no active effects returns empty results."""
        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["target_1", "target_2"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["total_dispelled"] == 0
        assert result["total_resisted"] == 0
        assert result["caster_level"] == 5
        assert result["area_size"] == "20' cube"

    def test_dispel_magic_auto_dispels_lower_level(
        self, spell_resolver, mock_caster, mock_dice_roller, create_active_effect
    ):
        """Effects from lower level casters are auto-dispelled."""
        # Create an effect from a level 3 caster (lower than our level 5 caster)
        effect = create_active_effect(
            spell_id="hold_person",
            spell_name="Hold Person",
            caster_id="enemy_1",
            caster_level=3,
            target_id="ally_1",
            condition="paralyzed",
        )
        spell_resolver._active_effects.append(effect)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["total_dispelled"] == 1
        assert result["total_resisted"] == 0
        assert result["effects_dispelled"][0]["spell_name"] == "Hold Person"
        assert result["effects_dispelled"][0]["level_difference"] == -2  # 3 - 5

    def test_dispel_magic_auto_dispels_equal_level(
        self, spell_resolver, mock_caster, mock_dice_roller, create_active_effect
    ):
        """Effects from equal level casters are auto-dispelled."""
        effect = create_active_effect(
            spell_id="sleep",
            spell_name="Sleep",
            caster_id="enemy_1",
            caster_level=5,  # Same as our caster
            target_id="ally_1",
        )
        spell_resolver._active_effects.append(effect)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_dice_roller
        )

        assert result["success"] is True
        assert result["total_dispelled"] == 1
        assert result["effects_dispelled"][0]["level_difference"] == 0

    def test_dispel_magic_higher_level_resist_chance(
        self, spell_resolver, mock_caster, create_active_effect
    ):
        """Higher level effects have 5% per level difference to resist."""
        # Create an effect from a level 10 caster (5 levels higher)
        effect = create_active_effect(
            spell_id="charm_person",
            spell_name="Charm Person",
            caster_id="archmage",
            caster_level=10,
            target_id="ally_1",
        )
        spell_resolver._active_effects.append(effect)

        # Mock dice roller to roll 20 (below 25% threshold)
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=20)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_roller
        )

        # Roll of 20 is <= 25 (5 levels × 5%), so it resists
        assert result["total_resisted"] == 1
        assert result["effects_resisted"][0]["resist_chance"] == 25
        assert result["effects_resisted"][0]["resist_roll"] == 20

    def test_dispel_magic_higher_level_can_still_be_dispelled(
        self, spell_resolver, mock_caster, create_active_effect
    ):
        """Higher level effects can still be dispelled with good roll."""
        # Create an effect from a level 7 caster (2 levels higher = 10% resist)
        effect = create_active_effect(
            spell_id="web",
            spell_name="Web",
            caster_id="enemy_wizard",
            caster_level=7,
            target_id="ally_1",
        )
        spell_resolver._active_effects.append(effect)

        # Mock dice roller to roll 50 (above 10% threshold)
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=50)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_roller
        )

        # Roll of 50 is > 10 (2 levels × 5%), so it's dispelled
        assert result["total_dispelled"] == 1
        assert result["effects_dispelled"][0]["spell_name"] == "Web"

    def test_dispel_magic_ignores_magic_item_effects(
        self, spell_resolver, mock_caster, mock_dice_roller, create_active_effect
    ):
        """Effects from magic items are not affected by Dispel Magic."""
        # Create an effect from a magic item
        effect = create_active_effect(
            spell_id="ring_of_protection",
            spell_name="Ring of Protection",
            caster_id="item_1",
            caster_level=1,
            target_id="ally_1",
            from_magic_item=True,  # This should be skipped
        )
        spell_resolver._active_effects.append(effect)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_dice_roller
        )

        assert result["total_dispelled"] == 0
        assert result["total_resisted"] == 0

    def test_dispel_magic_multiple_effects_mixed_results(
        self, spell_resolver, mock_caster, create_active_effect
    ):
        """Dispel Magic handles multiple effects with mixed success/failure."""
        # Low level effect (auto-dispel)
        effect1 = create_active_effect(
            spell_id="bless",
            spell_name="Bless",
            caster_id="cleric_1",
            caster_level=2,
            target_id="ally_1",
        )
        # High level effect (may resist)
        effect2 = create_active_effect(
            spell_id="haste",
            spell_name="Haste",
            caster_id="archmage",
            caster_level=15,  # 10 levels higher = 50% resist
            target_id="ally_1",
        )
        spell_resolver._active_effects.append(effect1)
        spell_resolver._active_effects.append(effect2)

        # Mock roller to return 30 (resists 50% threshold)
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=30)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_roller
        )

        assert result["total_dispelled"] == 1  # Low level effect
        assert result["total_resisted"] == 1  # High level effect resisted

    def test_dispel_magic_removes_condition_via_controller(
        self, mock_caster, mock_dice_roller, create_active_effect
    ):
        """Dispel Magic removes associated conditions via controller."""
        # Create resolver with a proper mock controller that has remove_condition
        mock_controller = MagicMock()
        mock_controller.remove_condition = MagicMock()
        resolver = SpellResolver(controller=mock_controller)

        effect = create_active_effect(
            spell_id="hold_monster",
            spell_name="Hold Monster",
            caster_id="enemy_1",
            caster_level=3,
            target_id="ally_1",
            condition="paralyzed",
        )
        resolver._active_effects.append(effect)

        result = resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_dice_roller
        )

        assert result["total_dispelled"] == 1
        # Verify controller was called to remove condition
        mock_controller.remove_condition.assert_called_once_with(
            "ally_1", "paralyzed"
        )

    def test_dispel_magic_narrative_context(
        self, spell_resolver, mock_caster, mock_dice_roller, create_active_effect
    ):
        """Dispel Magic returns appropriate narrative context."""
        effect = create_active_effect(
            spell_id="light",
            spell_name="Light",
            caster_id="cleric_1",
            caster_level=1,
            target_id="torch_1",
        )
        spell_resolver._active_effects.append(effect)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["torch_1"], mock_dice_roller
        )

        assert result["narrative_context"]["dispel_cast"] is True
        assert result["narrative_context"]["magic_unravelled"] is True
        assert len(result["narrative_context"]["hints"]) >= 1

    def test_dispel_magic_narrative_when_resisted(
        self, spell_resolver, mock_caster, create_active_effect
    ):
        """Narrative context indicates when some magic resisted."""
        effect = create_active_effect(
            spell_id="force_field",
            spell_name="Force Field",
            caster_id="archmage",
            caster_level=20,  # Very high level
            target_id="ally_1",
        )
        spell_resolver._active_effects.append(effect)

        # Roll low to resist
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=5)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_roller
        )

        assert result["narrative_context"]["some_resisted"] is True
        assert "some powerful magics resist the dispelling" in result["narrative_context"]["hints"]


class TestDispelMagicEdgeCases:
    """Edge case tests for Dispel Magic."""

    def test_dispel_magic_no_targets(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Dispel Magic handles empty target list."""
        result = spell_resolver._handle_dispel_magic(
            mock_caster, [], mock_dice_roller
        )

        assert result["success"] is True
        assert result["total_dispelled"] == 0
        assert result["targets_checked"] == []

    def test_dispel_magic_same_effect_not_processed_twice(
        self, spell_resolver, mock_caster, mock_dice_roller, create_active_effect
    ):
        """Same effect ID should only be processed once."""
        effect = create_active_effect(
            spell_id="bless",
            spell_name="Bless",
            caster_id="cleric_1",
            caster_level=3,
            target_id="ally_1",
        )
        spell_resolver._active_effects.append(effect)

        # Pass same target multiple times
        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1", "ally_1", "ally_1"], mock_dice_roller
        )

        assert result["total_dispelled"] == 1  # Only processed once

    def test_dispel_magic_caster_without_level_attribute(
        self, spell_resolver, mock_dice_roller
    ):
        """Caster without level attribute defaults to level 1."""
        caster = MagicMock(spec=["character_id", "name"])  # No level attribute
        caster.character_id = "basic_caster"
        caster.name = "Basic"

        result = spell_resolver._handle_dispel_magic(
            caster, ["target_1"], mock_dice_roller
        )

        assert result["caster_level"] == 1

    def test_dispel_magic_effect_without_caster_level(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Effect with caster_level=0 defaults to level 1 for calculations."""
        effect = ActiveSpellEffect(
            spell_id="old_spell",
            spell_name="Old Spell",
            caster_id="old_caster",
            caster_level=0,  # Not set
            target_id="ally_1",
            duration_type=DurationType.TURNS,
            duration_remaining=5,
            is_active=True,
        )
        spell_resolver._active_effects.append(effect)

        result = spell_resolver._handle_dispel_magic(
            mock_caster, ["ally_1"], mock_dice_roller
        )

        # With caster_level=0 treated as 1, level 5 caster auto-dispels
        assert result["total_dispelled"] == 1
        assert result["effects_dispelled"][0]["effect_caster_level"] == 1


class TestDispelMagicIntegration:
    """Integration tests for Dispel Magic with dispatcher."""

    def test_dispel_magic_registered_in_dispatcher(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Dispel Magic is registered in the spell handler dispatcher."""
        # Create a mock spell with dispel_magic id
        mock_spell = MagicMock()
        mock_spell.spell_id = "dispel_magic"

        result = spell_resolver._handle_special_spell(
            mock_spell, mock_caster, ["target_1"], mock_dice_roller
        )

        assert result is not None
        assert result["success"] is True


class TestDispelMagicSpellDataIntegration:
    """Integration tests verifying handler matches actual spell JSON data."""

    @pytest.fixture
    def spell_data_loader(self):
        """Load spell data from actual JSON files."""
        data_dir = Path(__file__).parent.parent / "data" / "content" / "spells"

        def load_spell(filename: str, spell_id: str) -> dict:
            spell_file = data_dir / filename
            if not spell_file.exists():
                pytest.skip(f"Spell file {filename} not found")

            with open(spell_file) as f:
                data = json.load(f)

            for item in data.get("items", []):
                if item.get("spell_id") == spell_id:
                    return item
            pytest.skip(f"Spell {spell_id} not found in {filename}")

        return load_spell

    def test_dispel_magic_matches_source_data(self, spell_data_loader):
        """Dispel Magic handler behavior matches spell source data."""
        spell = spell_data_loader("arcane_level_3_1.json", "dispel_magic")

        assert spell["name"] == "Dispel Magic"
        assert spell["level"] == 3
        assert spell["magic_type"] == "arcane"
        assert spell["duration"] == "Instant"
        assert spell["range"] == "120'"

        # Verify key mechanics from description
        desc = spell["description"]
        assert "20" in desc and "cube" in desc.lower()  # 20' cube
        assert "5%" in desc  # 5% per level
        assert "Magic items" in desc  # Magic items unaffected
        assert "Curses" in desc  # Curses from spells affected

    def test_dispel_magic_area_matches_source(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Handler returns correct area size from source."""
        result = spell_resolver._handle_dispel_magic(
            mock_caster, [], mock_dice_roller
        )

        assert result["area_size"] == "20' cube"


class TestActiveSpellEffectCasterLevel:
    """Tests for the new caster_level field on ActiveSpellEffect."""

    def test_active_spell_effect_has_caster_level(self):
        """ActiveSpellEffect should have caster_level field."""
        effect = ActiveSpellEffect(
            spell_id="test",
            spell_name="Test",
            caster_id="caster_1",
            caster_level=7,
            target_id="target_1",
        )

        assert effect.caster_level == 7

    def test_active_spell_effect_caster_level_defaults_zero(self):
        """ActiveSpellEffect caster_level defaults to 0."""
        effect = ActiveSpellEffect(
            spell_id="test",
            spell_name="Test",
            caster_id="caster_1",
            target_id="target_1",
        )

        assert effect.caster_level == 0
