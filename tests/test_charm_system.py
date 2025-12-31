"""
Tests for the Charm/Control Condition System.

Tests charm effects, recurring saves, hostility checks, and
the caster/spell tracking functionality.
"""

import pytest
from src.data_models import (
    ConditionType,
    Condition,
    CharacterState,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def npc():
    """Create an NPC that can be charmed."""
    return CharacterState(
        character_id="npc_guard",
        name="Guard Captain",
        character_class="Fighter",
        level=3,
        ability_scores={"STR": 14, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        hp_current=20,
        hp_max=20,
        armor_class=16,
        base_speed=40,
    )


@pytest.fixture
def magic_user():
    """Create a magic-user who can charm."""
    return CharacterState(
        character_id="mage_1",
        name="Elara",
        character_class="Magic-User",
        level=5,
        ability_scores={"STR": 8, "DEX": 14, "CON": 10, "INT": 17, "WIS": 12, "CHA": 12},
        hp_current=12,
        hp_max=12,
        armor_class=12,
        base_speed=40,
    )


# =============================================================================
# CONDITION CHARM TRACKING TESTS
# =============================================================================


class TestConditionCharmTracking:
    """Tests for Condition charm tracking fields."""

    def test_condition_with_caster_id(self):
        """Test creating a condition with caster tracking."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            source="Ingratiate spell",
            source_spell_id="ingratiate_123",
            caster_id="mage_1",
        )

        assert condition.caster_id == "mage_1"
        assert condition.source_spell_id == "ingratiate_123"
        assert condition.is_charm_effect is True

    def test_recurring_save_configuration(self):
        """Test configuring recurring saves for charm."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            source="Dominate",
            caster_id="mage_1",
            recurring_save={
                "save_type": "spell",
                "frequency": "daily",
                "modifier": 0,
                "ends_on_success": True,
            },
        )

        assert condition.has_recurring_save is True
        assert condition.recurring_save["frequency"] == "daily"
        assert condition.recurring_save["save_type"] == "spell"

    def test_non_charm_condition_is_not_charm_effect(self):
        """Test that non-charm conditions don't report as charm effects."""
        condition = Condition(
            condition_type=ConditionType.POISONED,
            source="Poison trap",
        )

        assert condition.is_charm_effect is False


class TestRecurringSaveChecks:
    """Tests for recurring save timing."""

    def test_needs_daily_save_on_new_day(self):
        """Test that daily save is needed on a new day."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            recurring_save={"frequency": "daily"},
            last_save_day=5,
        )

        assert condition.needs_recurring_save(current_day=6) is True
        assert condition.needs_recurring_save(current_day=5) is False

    def test_needs_per_turn_save(self):
        """Test per-turn recurring saves."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            recurring_save={"frequency": "per_turn"},
            last_save_day=1,
            last_save_turn=10,
        )

        # Same day, later turn
        assert condition.needs_recurring_save(current_day=1, current_turn=11) is True
        # Same turn - no save needed
        assert condition.needs_recurring_save(current_day=1, current_turn=10) is False
        # New day always needs save
        assert condition.needs_recurring_save(current_day=2, current_turn=1) is True

    def test_on_hostile_action_does_not_need_time_save(self):
        """Test that on_hostile_action doesn't trigger from time passage."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            recurring_save={"frequency": "on_hostile_action"},
        )

        # Should never return True for time-based checks
        assert condition.needs_recurring_save(current_day=100, current_turn=1000) is False

    def test_record_save_check_updates_tracking(self):
        """Test that recording a save check updates the tracking fields."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            recurring_save={"frequency": "daily"},
        )

        condition.record_save_check(current_day=5, current_turn=10)

        assert condition.last_save_day == 5
        assert condition.last_save_turn == 10

    def test_get_save_modifier(self):
        """Test getting save modifier from recurring save config."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            recurring_save={"frequency": "daily", "modifier": -4},
        )

        assert condition.get_save_modifier() == -4

    def test_get_save_modifier_default(self):
        """Test default save modifier is 0."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            recurring_save={"frequency": "daily"},
        )

        assert condition.get_save_modifier() == 0


# =============================================================================
# CHARACTER CHARM STATE TESTS
# =============================================================================


class TestCharacterCharmState:
    """Tests for CharacterState charm management."""

    def test_has_condition(self, npc):
        """Test checking for a condition type."""
        assert npc.has_condition(ConditionType.CHARMED) is False

        npc.add_condition(Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        ))

        assert npc.has_condition(ConditionType.CHARMED) is True

    def test_get_condition(self, npc):
        """Test getting a specific condition."""
        assert npc.get_condition(ConditionType.CHARMED) is None

        charm = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
            source="Ingratiate",
        )
        npc.add_condition(charm)

        result = npc.get_condition(ConditionType.CHARMED)
        assert result is not None
        assert result.source == "Ingratiate"

    def test_remove_condition_type(self, npc):
        """Test removing a condition by type."""
        charm = Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        )
        npc.add_condition(charm)
        assert npc.is_charmed() is True

        removed = npc.remove_condition_type(ConditionType.CHARMED)

        assert removed is not None
        assert npc.is_charmed() is False

    def test_is_charmed(self, npc):
        """Test is_charmed helper."""
        assert npc.is_charmed() is False

        npc.add_condition(Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        ))

        assert npc.is_charmed() is True

    def test_is_charmed_by(self, npc):
        """Test checking if charmed by specific caster."""
        npc.add_condition(Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        ))

        assert npc.is_charmed_by("mage_1") is True
        assert npc.is_charmed_by("mage_2") is False

    def test_get_charm_caster(self, npc):
        """Test getting the charm caster ID."""
        assert npc.get_charm_caster() is None

        npc.add_condition(Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        ))

        assert npc.get_charm_caster() == "mage_1"


# =============================================================================
# HOSTILITY TESTS
# =============================================================================


class TestHostility:
    """Tests for charm hostility behavior."""

    def test_not_hostile_to_charmer(self, npc):
        """Charmed characters are not hostile to their charmer."""
        npc.add_condition(Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        ))

        assert npc.is_hostile_to("mage_1") is False

    def test_hostile_to_non_charmer(self, npc):
        """Charmed characters can be hostile to others."""
        npc.add_condition(Condition(
            condition_type=ConditionType.CHARMED,
            caster_id="mage_1",
        ))

        # Hostile to others (default behavior)
        assert npc.is_hostile_to("fighter_1") is True

    def test_not_charmed_is_hostile(self, npc):
        """Non-charmed characters default to potentially hostile."""
        assert npc.is_hostile_to("anyone") is True


# =============================================================================
# APPLY/BREAK CHARM TESTS
# =============================================================================


class TestApplyBreakCharm:
    """Tests for apply_charm and break_charm methods."""

    def test_apply_charm(self, npc):
        """Test applying a charm effect."""
        charm = npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="ingratiate_spell",
            source="Ingratiate",
            recurring_save={"save_type": "spell", "frequency": "daily"},
        )

        assert npc.is_charmed() is True
        assert npc.is_charmed_by("mage_1") is True
        assert charm.source_spell_id == "ingratiate_spell"
        assert charm.recurring_save is not None

    def test_apply_charm_with_duration(self, npc):
        """Test applying charm with day-based duration."""
        charm = npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="dominate_spell",
            source="Dominate",
            duration_days=7,
        )

        assert charm.duration_days == 7

    def test_break_charm(self, npc):
        """Test breaking a charm effect."""
        npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="ingratiate_spell",
            source="Ingratiate",
        )
        assert npc.is_charmed() is True

        broken = npc.break_charm()

        assert broken is not None
        assert npc.is_charmed() is False

    def test_break_charm_by_specific_caster(self, npc):
        """Test breaking charm from a specific caster."""
        npc.apply_charm(caster_id="mage_1", source_spell_id="spell_1", source="Spell 1")
        npc.apply_charm(caster_id="mage_2", source_spell_id="spell_2", source="Spell 2")

        broken = npc.break_charm(caster_id="mage_1")

        assert broken is not None
        assert broken.caster_id == "mage_1"
        # Still charmed by mage_2
        assert npc.is_charmed_by("mage_2") is True
        assert npc.is_charmed_by("mage_1") is False

    def test_break_charm_when_not_charmed(self, npc):
        """Test breaking charm when not charmed returns None."""
        result = npc.break_charm()
        assert result is None


# =============================================================================
# RECURRING SAVE CHECK TESTS
# =============================================================================


class TestCharmSaveChecks:
    """Tests for checking which charms need saves."""

    def test_check_charm_saves_finds_due_saves(self, npc):
        """Test finding charms that need save checks."""
        npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="spell_1",
            source="Ingratiate",
            recurring_save={"frequency": "daily"},
        )
        # Set last check to yesterday
        npc.conditions[0].last_save_day = 5

        needs_save = npc.check_charm_saves(current_day=6)

        assert len(needs_save) == 1
        assert needs_save[0].caster_id == "mage_1"

    def test_check_charm_saves_skips_recent(self, npc):
        """Test that recently checked charms are skipped."""
        npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="spell_1",
            source="Ingratiate",
            recurring_save={"frequency": "daily"},
        )
        # Set last check to today
        npc.conditions[0].last_save_day = 6

        needs_save = npc.check_charm_saves(current_day=6)

        assert len(needs_save) == 0

    def test_check_charm_saves_only_charmed(self, npc):
        """Test that only charmed conditions are checked."""
        # Add non-charm condition
        npc.add_condition(Condition(
            condition_type=ConditionType.POISONED,
            source="Poison",
        ))
        # Add charm condition
        npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="spell_1",
            source="Ingratiate",
            recurring_save={"frequency": "daily"},
        )
        npc.conditions[-1].last_save_day = 0

        needs_save = npc.check_charm_saves(current_day=1)

        assert len(needs_save) == 1
        assert needs_save[0].condition_type == ConditionType.CHARMED


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestCharmIntegration:
    """Integration tests for charm system with other game mechanics."""

    def test_charm_with_multiple_conditions(self, npc):
        """Test charm alongside other conditions."""
        # Add multiple conditions
        npc.add_condition(Condition(
            condition_type=ConditionType.POISONED,
            source="Poison trap",
        ))
        npc.apply_charm(
            caster_id="mage_1",
            source_spell_id="spell_1",
            source="Charm Person",
        )
        npc.add_condition(Condition(
            condition_type=ConditionType.EXHAUSTED,
            source="Long march",
            severity=2,
        ))

        assert len(npc.conditions) == 3
        assert npc.is_charmed() is True
        assert npc.has_condition(ConditionType.POISONED) is True
        assert npc.has_condition(ConditionType.EXHAUSTED) is True

        # Breaking charm doesn't affect other conditions
        npc.break_charm()

        assert len(npc.conditions) == 2
        assert npc.is_charmed() is False
        assert npc.has_condition(ConditionType.POISONED) is True

    def test_full_charm_lifecycle(self, npc, magic_user):
        """Test complete charm lifecycle: apply, check, break."""
        # Day 1: Cast charm
        charm = npc.apply_charm(
            caster_id=magic_user.character_id,
            source_spell_id="ingratiate_spell",
            source="Ingratiate",
            recurring_save={"save_type": "spell", "frequency": "daily", "modifier": 0},
        )
        charm.record_save_check(current_day=1)

        # NPC is charmed and friendly to mage
        assert npc.is_charmed() is True
        assert npc.is_hostile_to(magic_user.character_id) is False

        # Day 2: Check for saves
        needs_save = npc.check_charm_saves(current_day=2)
        assert len(needs_save) == 1

        # Record the save check (assume failed)
        needs_save[0].record_save_check(current_day=2)

        # Day 3: Another save check
        needs_save = npc.check_charm_saves(current_day=3)
        assert len(needs_save) == 1

        # Assume save succeeds - break charm
        npc.break_charm()

        # NPC is now free
        assert npc.is_charmed() is False
        assert npc.is_hostile_to(magic_user.character_id) is True
