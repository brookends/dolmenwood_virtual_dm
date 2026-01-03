"""
Tests for HazardResult unified schema.

These tests verify that:
- HazardResult has damage_taken and effect_applied fields
- Fields are properly synchronized with damage_dealt and conditions_applied
- The narrative property alias works correctly
"""

import pytest
from unittest.mock import MagicMock, patch

from src.narrative.hazard_resolver import HazardResult, HazardType, HazardResolver
from src.narrative.intent_parser import ActionType


class TestHazardResultUnifiedSchema:
    """Tests for HazardResult unified schema fields."""

    def test_damage_taken_field_exists(self):
        """Verify HazardResult has damage_taken field."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.TRAP,
            action_type=ActionType.UNKNOWN,
            damage_dealt=10,
        )
        assert hasattr(result, "damage_taken")
        assert result.damage_taken == 10  # Synced from damage_dealt

    def test_effect_applied_field_exists(self):
        """Verify HazardResult has effect_applied field."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.ENCHANTMENT,
            action_type=ActionType.UNKNOWN,
            conditions_applied=["charmed", "confused"],
        )
        assert hasattr(result, "effect_applied")
        assert result.effect_applied == "charmed"  # First condition

    def test_damage_taken_syncs_from_damage_dealt(self):
        """Verify damage_taken is populated from damage_dealt."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.FALLING,
            action_type=ActionType.UNKNOWN,
            damage_dealt=15,
        )
        assert result.damage_taken == 15

    def test_damage_dealt_syncs_from_damage_taken(self):
        """Verify damage_dealt is populated from damage_taken."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.FALLING,
            action_type=ActionType.UNKNOWN,
            damage_taken=20,
        )
        assert result.damage_dealt == 20

    def test_effect_applied_syncs_from_conditions_applied(self):
        """Verify effect_applied is populated from conditions_applied."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.ENCHANTMENT,
            action_type=ActionType.UNKNOWN,
            conditions_applied=["poisoned"],
        )
        assert result.effect_applied == "poisoned"

    def test_conditions_applied_syncs_from_effect_applied(self):
        """Verify conditions_applied is populated from effect_applied."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.ENCHANTMENT,
            action_type=ActionType.UNKNOWN,
            effect_applied="stunned",
        )
        assert result.conditions_applied == ["stunned"]

    def test_narrative_property_exists(self):
        """Verify HazardResult has narrative property alias for description."""
        result = HazardResult(
            success=True,
            hazard_type=HazardType.DOOR_LOCKED,
            action_type=ActionType.PICK_LOCK,
            description="The lock clicks open.",
        )
        assert hasattr(result, "narrative")
        assert result.narrative == "The lock clicks open."

    def test_no_damage_defaults_to_zero(self):
        """Verify damage fields default to zero."""
        result = HazardResult(
            success=True,
            hazard_type=HazardType.DOOR_LOCKED,
            action_type=ActionType.PICK_LOCK,
        )
        assert result.damage_dealt == 0
        assert result.damage_taken == 0

    def test_no_effect_defaults_to_none(self):
        """Verify effect_applied defaults to None when no conditions."""
        result = HazardResult(
            success=True,
            hazard_type=HazardType.DOOR_LOCKED,
            action_type=ActionType.PICK_LOCK,
        )
        assert result.effect_applied is None
        assert result.conditions_applied == []


class TestResolveLockedDoorResult:
    """Tests for _resolve_door_locked returning proper HazardResult."""

    @pytest.fixture
    def mock_character(self):
        """Create a mock character."""
        char = MagicMock()
        char.name = "Test Thief"
        char.character_id = "thief_001"
        return char

    @pytest.fixture
    def resolver(self):
        """Create a hazard resolver."""
        return HazardResolver()

    def test_locked_door_with_key_has_damage_taken(self, resolver, mock_character):
        """Verify locked door with key result has damage_taken field."""
        result = resolver._resolve_door_locked(
            character=mock_character,
            has_key=True,
            can_pick=False,
        )
        assert hasattr(result, "damage_taken")
        assert result.damage_taken == 0

    def test_locked_door_pick_success_has_damage_taken(self, resolver, mock_character):
        """Verify locked door pick attempt result has damage_taken field."""
        # Mock the ability registry to return a pick lock target
        with patch("src.classes.ability_registry.get_ability_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_reg.get_skill_target.return_value = 3  # Thief with pick lock skill
            mock_registry.return_value = mock_reg

            # Mock dice to ensure success
            resolver.dice = MagicMock()
            resolver.dice.roll_d6.return_value = MagicMock(total=6)

            result = resolver._resolve_door_locked(
                character=mock_character,
                has_key=False,
                can_pick=True,
            )

            assert hasattr(result, "damage_taken")
            assert result.damage_taken == 0

    def test_locked_door_pick_failure_has_damage_taken(self, resolver, mock_character):
        """Verify locked door pick failure result has damage_taken field."""
        with patch("src.classes.ability_registry.get_ability_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_reg.get_skill_target.return_value = 5  # Hard target
            mock_registry.return_value = mock_reg

            # Mock dice to ensure failure
            resolver.dice = MagicMock()
            resolver.dice.roll_d6.return_value = MagicMock(total=1)

            result = resolver._resolve_door_locked(
                character=mock_character,
                has_key=False,
                can_pick=True,
            )

            assert hasattr(result, "damage_taken")
            assert result.damage_taken == 0

    def test_locked_door_no_skill_has_damage_taken(self, resolver, mock_character):
        """Verify locked door no skill result has damage_taken field."""
        with patch("src.classes.ability_registry.get_ability_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_reg.get_skill_target.return_value = None  # No pick lock skill
            mock_registry.return_value = mock_reg

            result = resolver._resolve_door_locked(
                character=mock_character,
                has_key=False,
                can_pick=True,
            )

            assert hasattr(result, "damage_taken")
            assert result.damage_taken == 0

    def test_locked_door_result_has_effect_applied(self, resolver, mock_character):
        """Verify locked door result has effect_applied field."""
        result = resolver._resolve_door_locked(
            character=mock_character,
            has_key=True,
            can_pick=False,
        )
        assert hasattr(result, "effect_applied")
        assert result.effect_applied is None  # No effect from opening door


class TestHazardResultWithDamageAndCondition:
    """Tests for HazardResult with both damage and condition."""

    def test_trap_with_poison(self):
        """Verify trap result with damage and poison condition."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.TRAP,
            action_type=ActionType.UNKNOWN,
            description="A poison dart strikes you!",
            damage_dealt=5,
            conditions_applied=["poisoned"],
        )

        # Both damage and effect should be synced
        assert result.damage_taken == 5
        assert result.effect_applied == "poisoned"

    def test_falling_with_injury(self):
        """Verify falling hazard with damage."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.FALLING,
            action_type=ActionType.UNKNOWN,
            description="You fall and hurt yourself.",
            damage_dealt=12,
            damage_type="falling",
        )

        assert result.damage_taken == 12
        assert result.effect_applied is None  # No condition

    def test_enchantment_with_multiple_conditions(self):
        """Verify enchantment with multiple conditions applies first."""
        result = HazardResult(
            success=False,
            hazard_type=HazardType.ENCHANTMENT,
            action_type=ActionType.UNKNOWN,
            description="You are enchanted!",
            conditions_applied=["charmed", "fascinated", "compelled"],
        )

        assert result.damage_taken == 0  # No damage
        assert result.effect_applied == "charmed"  # First condition
        assert len(result.conditions_applied) == 3  # All conditions preserved
