"""
Tests for Phase 4 Spell Handlers - Movement Spells.

Covers:
- Levitate: Vertical movement only, 20'/round, 6 turns + 1/level
- Fly: Full flight, Speed 120, 1d6 turns + 1/level
- Telekinesis: Concentration, 200 coins/level, Save vs Hold for creatures
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
    controller.get_character = MagicMock(return_value=None)
    resolver = SpellResolver(controller=controller)
    return resolver


@pytest.fixture
def mock_caster():
    """Create a mock caster character with flight methods."""
    caster = MagicMock()
    caster.character_id = "caster_1"
    caster.name = "Test Wizard"
    caster.level = 5
    caster.grant_flight = MagicMock()
    return caster


@pytest.fixture
def mock_dice_roller():
    """Create a mock dice roller."""
    roller = MagicMock()
    # Default to mid-range rolls
    roller.roll.return_value = MagicMock(total=3)
    roller.roll_d20.return_value = MagicMock(total=10)
    return roller


# =============================================================================
# LEVITATE TESTS
# =============================================================================


class TestLevitateHandler:
    """Tests for the Levitate spell handler."""

    def test_levitate_grants_hovering_state(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Levitate should grant HOVERING flight state, not FLYING."""
        from src.data_models import FlightState

        result = spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        assert result["success"] is True
        mock_caster.grant_flight.assert_called_once()
        call_kwargs = mock_caster.grant_flight.call_args
        assert call_kwargs[1]["flight_state"] == FlightState.HOVERING

    def test_levitate_vertical_speed_20(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Levitate should grant 20' per round vertical speed."""
        result = spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        assert result["vertical_speed"] == 20
        assert result["movement_mode"] == "levitating"

    def test_levitate_duration_6_plus_level(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Duration should be 6 turns + caster level."""
        # Caster is level 5
        result = spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        assert result["duration_turns"] == 11  # 6 + 5

    def test_levitate_registers_active_effect(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Should register as active spell effect."""
        result = spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        effect_id = result["effect_id"]
        effect = next(
            (e for e in spell_resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect is not None
        assert effect.spell_id == "levitate"
        assert effect.duration_remaining == 11
        assert effect.mechanical_effects["horizontal_requires_solid"] is True

    def test_levitate_narrative_context(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Should include narrative hints."""
        result = spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        assert result["narrative_context"]["levitation_granted"] is True
        assert result["narrative_context"]["vertical_only"] is True
        assert len(result["narrative_context"]["hints"]) >= 1


# =============================================================================
# FLY TESTS
# =============================================================================


class TestFlyHandler:
    """Tests for the Fly spell handler."""

    def test_fly_grants_flying_state(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Fly should grant FLYING flight state."""
        from src.data_models import FlightState

        result = spell_resolver._handle_fly(
            mock_caster, [], mock_dice_roller
        )

        assert result["success"] is True
        mock_caster.grant_flight.assert_called_once()
        call_kwargs = mock_caster.grant_flight.call_args
        assert call_kwargs[1]["flight_state"] == FlightState.FLYING

    def test_fly_speed_120(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Fly should grant Speed 120."""
        result = spell_resolver._handle_fly(
            mock_caster, [], mock_dice_roller
        )

        assert result["flight_speed"] == 120
        assert result["movement_mode"] == "flying"

    def test_fly_duration_1d6_plus_level(
        self, spell_resolver, mock_caster
    ):
        """Duration should be 1d6 turns + caster level."""
        mock_roller = MagicMock()
        mock_roller.roll.return_value = MagicMock(total=4)

        result = spell_resolver._handle_fly(
            mock_caster, [], mock_roller
        )

        # 4 (from 1d6) + 5 (level) = 9
        assert result["duration_turns"] == 9
        assert result["duration_roll"] == 4

    def test_fly_can_target_other(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Fly can target touched creature."""
        mock_target = MagicMock()
        mock_target.grant_flight = MagicMock()
        spell_resolver._controller.get_character.return_value = mock_target

        result = spell_resolver._handle_fly(
            mock_caster, ["ally_1"], mock_dice_roller
        )

        assert result["target_id"] == "ally_1"
        mock_target.grant_flight.assert_called_once()

    def test_fly_defaults_to_caster(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Without targets, fly affects caster."""
        result = spell_resolver._handle_fly(
            mock_caster, [], mock_dice_roller
        )

        assert result["target_id"] == mock_caster.character_id

    def test_fly_registers_active_effect(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Should register as active spell effect."""
        result = spell_resolver._handle_fly(
            mock_caster, [], mock_dice_roller
        )

        effect_id = result["effect_id"]
        effect = next(
            (e for e in spell_resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect is not None
        assert effect.spell_id == "fly"
        assert effect.mechanical_effects["flight_speed"] == 120
        assert effect.mechanical_effects["free_movement"] is True


# =============================================================================
# TELEKINESIS TESTS
# =============================================================================


class TestTelekinesisHandler:
    """Tests for the Telekinesis spell handler."""

    def test_telekinesis_weight_limit(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Weight limit should be 200 coins per level."""
        result = spell_resolver._handle_telekinesis(
            mock_caster, [], mock_dice_roller
        )

        # Level 5 caster = 1000 coins
        assert result["weight_limit_coins"] == 1000
        assert result["weight_limit_lbs"] == 50  # 1000/20

    def test_telekinesis_movement_speed(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Movement should be 20' per round."""
        result = spell_resolver._handle_telekinesis(
            mock_caster, [], mock_dice_roller
        )

        assert result["movement_speed"] == 20

    def test_telekinesis_requires_concentration(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Should require concentration."""
        result = spell_resolver._handle_telekinesis(
            mock_caster, [], mock_dice_roller
        )

        assert result["requires_concentration"] is True
        assert result["duration_rounds"] == 6

    def test_telekinesis_object_no_save(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Objects should not get saves."""
        # Controller returns None for target = it's an object
        spell_resolver._controller.get_character.return_value = None

        result = spell_resolver._handle_telekinesis(
            mock_caster, ["chest_1"], mock_dice_roller
        )

        assert len(result["targets_held"]) == 1
        assert result["targets_held"][0]["target_id"] == "chest_1"
        assert result["targets_held"][0].get("is_object") is True

    def test_telekinesis_creature_gets_save(
        self, spell_resolver, mock_caster
    ):
        """Creatures should get Save vs Hold."""
        mock_target = MagicMock()
        mock_target.get_saving_throw = MagicMock(return_value=5)
        spell_resolver._controller.get_character.return_value = mock_target

        # Roll 8, +5 save = 13, fails vs 15
        mock_roller = MagicMock()
        mock_roller.roll_d20.return_value = MagicMock(total=8)

        result = spell_resolver._handle_telekinesis(
            mock_caster, ["goblin_1"], mock_roller
        )

        assert len(result["targets_held"]) == 1
        assert result["targets_held"][0]["target_id"] == "goblin_1"

    def test_telekinesis_creature_resists_save(
        self, spell_resolver, mock_caster
    ):
        """Creatures that make save should resist."""
        mock_target = MagicMock()
        mock_target.get_saving_throw = MagicMock(return_value=5)
        spell_resolver._controller.get_character.return_value = mock_target

        # Roll 12, +5 save = 17, succeeds vs 15
        mock_roller = MagicMock()
        mock_roller.roll_d20.return_value = MagicMock(total=12)

        result = spell_resolver._handle_telekinesis(
            mock_caster, ["goblin_1"], mock_roller
        )

        assert len(result["targets_resisted"]) == 1
        assert result["targets_resisted"][0]["target_id"] == "goblin_1"
        assert len(result["targets_held"]) == 0

    def test_telekinesis_registers_concentration_effect(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Should register as concentration effect."""
        result = spell_resolver._handle_telekinesis(
            mock_caster, [], mock_dice_roller
        )

        effect_id = result["effect_id"]
        effect = next(
            (e for e in spell_resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect is not None
        assert effect.spell_id == "telekinesis"
        assert effect.requires_concentration is True
        assert effect.duration_type == DurationType.ROUNDS
        assert effect.duration_remaining == 6


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPhase4SpellIntegration:
    """Integration tests for Phase 4 spells with dispatcher."""

    def test_levitate_registered_in_dispatcher(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Levitate should be registered in the dispatcher."""
        mock_spell = MagicMock()
        mock_spell.spell_id = "levitate"

        result = spell_resolver._handle_special_spell(
            mock_spell, mock_caster, [], mock_dice_roller
        )

        assert result is not None
        assert result["success"] is True

    def test_fly_registered_in_dispatcher(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Fly should be registered in the dispatcher."""
        mock_spell = MagicMock()
        mock_spell.spell_id = "fly"

        result = spell_resolver._handle_special_spell(
            mock_spell, mock_caster, [], mock_dice_roller
        )

        assert result is not None
        assert result["success"] is True

    def test_telekinesis_registered_in_dispatcher(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Telekinesis should be registered in the dispatcher."""
        mock_spell = MagicMock()
        mock_spell.spell_id = "telekinesis"

        result = spell_resolver._handle_special_spell(
            mock_spell, mock_caster, [], mock_dice_roller
        )

        assert result is not None
        assert result["success"] is True


class TestPhase4SpellDataIntegration:
    """Integration tests verifying handlers match actual spell JSON data."""

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

    def test_levitate_matches_source_data(self, spell_data_loader):
        """Levitate handler behavior matches spell source data."""
        spell = spell_data_loader("arcane_level_2_2.json", "levitate")

        assert spell["name"] == "Levitate"
        assert spell["level"] == 2
        assert spell["magic_type"] == "arcane"
        assert "6 Turns" in spell["duration"]
        assert "+1 per Level" in spell["duration"]
        assert "20" in spell["description"]  # 20' per Round
        assert "Vertical" in spell["description"]

    def test_fly_matches_source_data(self, spell_data_loader):
        """Fly handler behavior matches spell source data."""
        spell = spell_data_loader("arcane_level_3_1.json", "fly")

        assert spell["name"] == "Fly"
        assert spell["level"] == 3
        assert spell["magic_type"] == "arcane"
        assert "1d6 Turns" in spell["duration"]
        assert "+1 per Level" in spell["duration"]
        assert "120" in spell["description"]  # Speed 120

    def test_telekinesis_matches_source_data(self, spell_data_loader):
        """Telekinesis handler behavior matches spell source data."""
        spell = spell_data_loader("arcane_level_5_2.json", "telekinesis")

        assert spell["name"] == "Telekinesis"
        assert spell["level"] == 5
        assert spell["magic_type"] == "arcane"
        assert "Concentration" in spell["duration"]
        assert "6 Rounds" in spell["duration"]
        assert "200 coins" in spell["description"]
        assert "20" in spell["description"]  # 20' per Round
        assert "Save Versus Hold" in spell["description"]

    def test_all_phase4_spells_have_valid_spell_ids(self, spell_data_loader):
        """Verify all Phase 4 spell_ids match the dispatcher registration."""
        phase4_spells = [
            ("arcane_level_2_2.json", "levitate"),
            ("arcane_level_3_1.json", "fly"),
            ("arcane_level_5_2.json", "telekinesis"),
        ]

        for filename, spell_id in phase4_spells:
            spell = spell_data_loader(filename, spell_id)
            assert spell["spell_id"] == spell_id, f"Mismatch for {spell_id}"


class TestPhase4FlightStateIntegration:
    """Tests for proper flight state integration."""

    def test_levitate_sets_correct_source(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Levitate should set source='levitate' for tracking."""
        spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        call_kwargs = mock_caster.grant_flight.call_args
        assert call_kwargs[1]["source"] == "levitate"

    def test_fly_sets_correct_source(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Fly should set source='fly' for tracking."""
        spell_resolver._handle_fly(
            mock_caster, [], mock_dice_roller
        )

        call_kwargs = mock_caster.grant_flight.call_args
        assert call_kwargs[1]["source"] == "fly"

    def test_levitate_effect_stores_caster_level(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Levitate effect should store caster level for dispel."""
        result = spell_resolver._handle_levitate(
            mock_caster, [], mock_dice_roller
        )

        effect_id = result["effect_id"]
        effect = next(
            (e for e in spell_resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect.caster_level == 5

    def test_fly_effect_stores_caster_level(
        self, spell_resolver, mock_caster, mock_dice_roller
    ):
        """Fly effect should store caster level for dispel."""
        result = spell_resolver._handle_fly(
            mock_caster, [], mock_dice_roller
        )

        effect_id = result["effect_id"]
        effect = next(
            (e for e in spell_resolver._active_effects if e.effect_id == effect_id),
            None
        )
        assert effect.caster_level == 5
