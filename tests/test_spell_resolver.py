"""
Tests for the Spell Resolver enhancements.

Tests cover:
- Glamour usage tracking (per-turn, per-day, per-subject)
- Rune magnitude usage tracking
- Saving throw resolution
- Mechanical effect parsing and application
- Game state integration
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field

from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    SpellCastResult,
    MagicType,
    DurationType,
    SpellEffectType,
    RangeType,
    UsageFrequency,
    RuneMagnitude,
    GlamourUsageRecord,
    RuneUsageState,
    SaveResult,
    MechanicalEffect,
    MechanicalEffectCategory,
    ParsedMechanicalEffects,
)
from src.narrative.intent_parser import SaveType


# =============================================================================
# FIXTURES
# =============================================================================


@dataclass
class MockCharacterState:
    """Mock character for testing."""

    character_id: str = "test_char_1"
    name: str = "Test Character"
    level: int = 5
    kindred: str = "human"
    spells: list = field(default_factory=list)

    def has_spell_slot(self, level: int) -> bool:
        return True

    def use_spell_slot(self, level: int) -> bool:
        return True

    def get_glamours_known(self) -> list[str]:
        return ["awe", "beguilement", "breath_of_the_wind"]

    def get_runes_known(self) -> list[str]:
        return ["fog_cloud", "rune_of_vanishing"]


@dataclass
class MockSavingThrows:
    """Mock saving throws."""

    doom: int = 11
    ray: int = 12
    hold: int = 13
    blast: int = 14
    spell: int = 12


class MockDiceRoller:
    """Mock dice roller for testing."""

    def __init__(self, fixed_value: int = 10):
        self.fixed_value = fixed_value
        self.rolls = []

    def roll(self, dice_notation: str, reason: str = "") -> MagicMock:
        self.rolls.append((dice_notation, reason))
        result = MagicMock()
        result.total = self.fixed_value
        return result

    def roll_d20(self, count: int = 1, reason: str = "") -> MagicMock:
        return self.roll(f"{count}d20", reason)


@pytest.fixture
def resolver():
    """Create a spell resolver for testing."""
    return SpellResolver()


@pytest.fixture
def caster():
    """Create a mock caster."""
    return MockCharacterState()


@pytest.fixture
def dice():
    """Create a mock dice roller."""
    return MockDiceRoller()


@pytest.fixture
def glamour_awe():
    """Create the Awe glamour spell."""
    return SpellData(
        spell_id="awe",
        name="Awe",
        level=None,
        magic_type=MagicType.FAIRY_GLAMOUR,
        duration="1d4 Rounds",
        range="30'",
        description="Triggers a Morale Check. Usage frequency: Once per Turn.",
        duration_type=DurationType.ROUNDS,
        usage_frequency="Once per Turn",
    )


@pytest.fixture
def glamour_beguilement():
    """Create the Beguilement glamour spell."""
    return SpellData(
        spell_id="beguilement",
        name="Beguilement",
        level=None,
        magic_type=MagicType.FAIRY_GLAMOUR,
        duration="1d4 Rounds",
        range="30'",
        description="Target must Save Versus Spell or believe the caster. Usage frequency: Once per day per subject.",
        duration_type=DurationType.ROUNDS,
        usage_frequency="Once per day per subject",
        save_type=SaveType.SPELL,
        save_negates=True,
    )


@pytest.fixture
def lesser_rune():
    """Create a lesser rune spell."""
    return SpellData(
        spell_id="fog_cloud",
        name="Fog Cloud",
        level="lesser",
        magic_type=MagicType.RUNE,
        duration="1 Turn",
        range="20' around the caster",
        description="A cloud of roiling vapour surrounds the caster.",
        duration_type=DurationType.TURNS,
        rune_magnitude=RuneMagnitude.LESSER,
    )


@pytest.fixture
def greater_rune():
    """Create a greater rune spell."""
    return SpellData(
        spell_id="greater_ward",
        name="Greater Ward",
        level="greater",
        magic_type=MagicType.RUNE,
        duration="1 Turn",
        range="The caster",
        description="A protective ward surrounds the caster.",
        duration_type=DurationType.TURNS,
        rune_magnitude=RuneMagnitude.GREATER,
    )


@pytest.fixture
def damage_spell():
    """Create a spell that deals damage."""
    return SpellData(
        spell_id="magic_missile",
        name="Magic Missile",
        level=1,
        magic_type=MagicType.ARCANE,
        duration="Instant",
        range="60'",
        description="Fires magical darts that deal 2d6 damage to the target.",
        duration_type=DurationType.INSTANT,
        effect_type=SpellEffectType.MECHANICAL,
        mechanical_effects={
            "effects": [
                {
                    "category": "damage",
                    "damage_dice": "2d6",
                    "damage_type": "magic",
                }
            ]
        },
    )


@pytest.fixture
def charm_spell():
    """Create a spell that applies a condition."""
    return SpellData(
        spell_id="charm_person",
        name="Charm Person",
        level=1,
        magic_type=MagicType.ARCANE,
        duration="Special",
        range="30'",
        description="Target must Save Versus Spell or be charmed by the caster.",
        duration_type=DurationType.SPECIAL,
        effect_type=SpellEffectType.MECHANICAL,
        save_type=SaveType.SPELL,
        save_negates=True,
    )


# =============================================================================
# GLAMOUR USAGE TRACKING TESTS
# =============================================================================


class TestGlamourUsageTracking:
    """Tests for glamour usage frequency limits."""

    def test_parse_once_per_turn(self, resolver):
        """Test parsing 'once per turn' frequency."""
        freq = resolver._parse_usage_frequency("Once per Turn")
        assert freq == UsageFrequency.ONCE_PER_TURN

    def test_parse_once_per_day(self, resolver):
        """Test parsing 'once per day' frequency."""
        freq = resolver._parse_usage_frequency("Once per day")
        assert freq == UsageFrequency.ONCE_PER_DAY

    def test_parse_once_per_day_per_subject(self, resolver):
        """Test parsing 'once per day per subject' frequency."""
        freq = resolver._parse_usage_frequency("Once per day per subject")
        assert freq == UsageFrequency.ONCE_PER_DAY_PER_SUBJECT

    def test_parse_at_will(self, resolver):
        """Test parsing at-will frequency."""
        freq = resolver._parse_usage_frequency(None)
        assert freq == UsageFrequency.AT_WILL

        freq = resolver._parse_usage_frequency("")
        assert freq == UsageFrequency.AT_WILL

    def test_glamour_once_per_turn_allows_first_use(self, resolver, caster, glamour_awe, dice):
        """Test that once-per-turn glamour can be used."""
        resolver.register_spell(glamour_awe)
        resolver.set_turn(1)

        can_cast, reason = resolver._check_glamour_usage(
            caster.character_id, glamour_awe, None
        )
        assert can_cast is True

    def test_glamour_once_per_turn_blocks_second_use(self, resolver, caster, glamour_awe, dice):
        """Test that once-per-turn glamour blocks second use same turn."""
        resolver.register_spell(glamour_awe)
        resolver.set_turn(1)

        # First use
        resolver._record_glamour_usage(caster.character_id, glamour_awe, None)

        # Second use same turn
        can_cast, reason = resolver._check_glamour_usage(
            caster.character_id, glamour_awe, None
        )
        assert can_cast is False
        assert "Already used this turn" in reason

    def test_glamour_once_per_turn_allows_next_turn(self, resolver, caster, glamour_awe):
        """Test that once-per-turn glamour allows use on next turn."""
        resolver.register_spell(glamour_awe)
        resolver.set_turn(1)

        # First use
        resolver._record_glamour_usage(caster.character_id, glamour_awe, None)

        # Next turn
        resolver.set_turn(2)
        can_cast, reason = resolver._check_glamour_usage(
            caster.character_id, glamour_awe, None
        )
        assert can_cast is True

    def test_glamour_once_per_day_per_subject_different_targets(
        self, resolver, caster, glamour_beguilement
    ):
        """Test once-per-day-per-subject allows different targets."""
        resolver.register_spell(glamour_beguilement)
        resolver.set_turn(1)

        # Use on target 1
        resolver._record_glamour_usage(caster.character_id, glamour_beguilement, "npc_1")

        # Can still use on target 2
        can_cast, reason = resolver._check_glamour_usage(
            caster.character_id, glamour_beguilement, "npc_2"
        )
        assert can_cast is True

    def test_glamour_once_per_day_per_subject_same_target(
        self, resolver, caster, glamour_beguilement
    ):
        """Test once-per-day-per-subject blocks same target."""
        resolver.register_spell(glamour_beguilement)
        resolver.set_turn(1)

        # Use on target 1
        resolver._record_glamour_usage(caster.character_id, glamour_beguilement, "npc_1")

        # Can't use on target 1 again
        can_cast, reason = resolver._check_glamour_usage(
            caster.character_id, glamour_beguilement, "npc_1"
        )
        assert can_cast is False
        assert "subject" in reason.lower()

    def test_glamour_daily_reset(self, resolver, caster, glamour_beguilement):
        """Test daily reset clears usage."""
        resolver.register_spell(glamour_beguilement)
        resolver.set_turn(1)

        # Use on target 1
        resolver._record_glamour_usage(caster.character_id, glamour_beguilement, "npc_1")

        # Can't use on target 1
        can_cast, _ = resolver._check_glamour_usage(
            caster.character_id, glamour_beguilement, "npc_1"
        )
        assert can_cast is False

        # Reset daily
        resolver.reset_glamour_usage_daily()

        # Now can use again
        can_cast, _ = resolver._check_glamour_usage(
            caster.character_id, glamour_beguilement, "npc_1"
        )
        assert can_cast is True


# =============================================================================
# RUNE USAGE TRACKING TESTS
# =============================================================================


class TestRuneUsageTracking:
    """Tests for rune magnitude-based usage limits."""

    def test_rune_magnitude_from_spell(self, resolver, lesser_rune):
        """Test getting magnitude from spell data."""
        mag = resolver._get_rune_magnitude(lesser_rune)
        assert mag == RuneMagnitude.LESSER

    def test_rune_magnitude_from_level_string(self, resolver):
        """Test getting magnitude from level string."""
        spell = SpellData(
            spell_id="test",
            name="Test Rune",
            level="greater",
            magic_type=MagicType.RUNE,
            duration="1 Turn",
            range="Self",
            description="Test",
        )
        mag = resolver._get_rune_magnitude(spell)
        assert mag == RuneMagnitude.GREATER

    def test_lesser_rune_usage_tracking(self, resolver, caster, lesser_rune):
        """Test tracking lesser rune usage."""
        resolver.register_spell(lesser_rune)

        # First use allowed
        can_use, reason = resolver._check_rune_usage(caster.character_id, lesser_rune)
        assert can_use is True

        # Record use
        resolver._record_rune_usage(caster.character_id, lesser_rune)

        # Check remaining
        usage = resolver.get_rune_usage(caster.character_id)
        assert usage is not None
        assert usage.lesser_uses_today == 1

    def test_rune_daily_limit(self, resolver, caster, lesser_rune):
        """Test rune daily usage limit."""
        resolver.register_spell(lesser_rune)

        # Set limit to 2
        resolver.set_rune_limits(caster.character_id, level=3)
        usage = resolver.get_rune_usage(caster.character_id)

        # Use up all lesser rune slots
        for _ in range(usage.max_lesser_daily):
            resolver._record_rune_usage(caster.character_id, lesser_rune)

        # Next use blocked
        can_use, reason = resolver._check_rune_usage(caster.character_id, lesser_rune)
        assert can_use is False
        assert "No lesser rune uses remaining" in reason

    def test_rune_daily_reset(self, resolver, caster, lesser_rune):
        """Test daily reset restores rune usage."""
        resolver.register_spell(lesser_rune)
        resolver.set_rune_limits(caster.character_id, level=1)

        # Use all slots
        usage = resolver.get_rune_usage(caster.character_id)
        for _ in range(usage.max_lesser_daily):
            resolver._record_rune_usage(caster.character_id, lesser_rune)

        # Blocked
        can_use, _ = resolver._check_rune_usage(caster.character_id, lesser_rune)
        assert can_use is False

        # Reset
        resolver.reset_rune_usage_daily()

        # Now allowed
        can_use, _ = resolver._check_rune_usage(caster.character_id, lesser_rune)
        assert can_use is True

    def test_rune_remaining_counts(self, resolver, caster, lesser_rune, greater_rune):
        """Test getting remaining rune counts."""
        resolver.register_spell(lesser_rune)
        resolver.register_spell(greater_rune)
        resolver.set_rune_limits(caster.character_id, level=7)

        usage = resolver.get_rune_usage(caster.character_id)

        # Initial remaining
        lesser_remaining = usage.get_remaining(RuneMagnitude.LESSER)
        greater_remaining = usage.get_remaining(RuneMagnitude.GREATER)

        assert lesser_remaining > 0
        assert greater_remaining > 0

        # Use one lesser
        resolver._record_rune_usage(caster.character_id, lesser_rune)

        # Check remaining decreased
        new_lesser = usage.get_remaining(RuneMagnitude.LESSER)
        assert new_lesser == lesser_remaining - 1


# =============================================================================
# SAVING THROW RESOLUTION TESTS
# =============================================================================


class TestSavingThrowResolution:
    """Tests for saving throw mechanics."""

    def test_save_success(self, resolver, caster, dice):
        """Test successful saving throw."""
        dice.fixed_value = 18  # High roll - need >= 17 for default spell save

        result = resolver._resolve_saving_throw(
            target_id="npc_1",
            save_type=SaveType.SPELL,
            caster_level=caster.level,
            dice_roller=dice,
        )

        assert isinstance(result, SaveResult)
        assert result.success is True
        assert result.roll == 18
        assert result.save_type == "spell"

    def test_save_failure(self, resolver, caster, dice):
        """Test failed saving throw."""
        dice.fixed_value = 5  # Low roll

        result = resolver._resolve_saving_throw(
            target_id="npc_1",
            save_type=SaveType.SPELL,
            caster_level=caster.level,
            dice_roller=dice,
        )

        assert result.success is False
        assert result.roll == 5

    def test_natural_20_always_saves(self, resolver, caster, dice):
        """Test natural 20 always succeeds."""
        dice.fixed_value = 20

        result = resolver._resolve_saving_throw(
            target_id="npc_1",
            save_type=SaveType.DOOM,
            caster_level=caster.level,
            dice_roller=dice,
        )

        assert result.success is True
        assert result.natural_20 is True

    def test_natural_1_always_fails(self, resolver, caster, dice):
        """Test natural 1 always fails."""
        dice.fixed_value = 1

        result = resolver._resolve_saving_throw(
            target_id="npc_1",
            save_type=SaveType.DOOM,
            caster_level=caster.level,
            dice_roller=dice,
        )

        assert result.success is False
        assert result.natural_1 is True

    def test_save_modifier_applied(self, resolver, caster, dice):
        """Test save modifier is applied."""
        dice.fixed_value = 12

        result = resolver._resolve_saving_throw(
            target_id="npc_1",
            save_type=SaveType.SPELL,
            caster_level=caster.level,
            dice_roller=dice,
            modifier=3,
        )

        assert result.roll == 12
        assert result.modifier == 3
        assert result.total == 15


# =============================================================================
# MECHANICAL EFFECT PARSING TESTS
# =============================================================================


class TestMechanicalEffectParsing:
    """Tests for parsing spell descriptions into mechanical effects."""

    def test_parse_damage_dice(self, resolver):
        """Test parsing damage dice from description."""
        spell = SpellData(
            spell_id="test",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="60'",
            description="Deals 2d6 damage to the target.",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        assert parsed.deals_damage is True
        assert len(parsed.effects) >= 1

        damage_effect = parsed.effects[0]
        assert damage_effect.category == MechanicalEffectCategory.DAMAGE
        assert damage_effect.damage_dice == "2d6"

    def test_parse_damage_with_type(self, resolver):
        """Test parsing damage type from description."""
        spell = SpellData(
            spell_id="test",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="60'",
            description="Deals 3d6 damage from fire to all in range.",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        assert parsed.deals_damage is True

        damage_effect = parsed.primary_effect
        # Fire type is detected from description containing "fire"
        assert damage_effect.damage_type == "fire"

    def test_parse_healing(self, resolver):
        """Test parsing healing from description."""
        spell = SpellData(
            spell_id="test",
            name="Test",
            level=1,
            magic_type=MagicType.DIVINE,
            duration="Instant",
            range="Touch",
            description="The touched creature regains 2d8 health.",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        # Look for healing effect specifically
        healing_effects = [
            e for e in parsed.effects
            if e.category == MechanicalEffectCategory.HEALING
        ]
        assert len(healing_effects) >= 1

        heal_effect = healing_effects[0]
        assert heal_effect.category == MechanicalEffectCategory.HEALING
        assert heal_effect.healing_dice == "2d8"

    def test_parse_condition(self, resolver):
        """Test parsing condition from description."""
        spell = SpellData(
            spell_id="test",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="1d6 Turns",
            range="30'",
            description="Target is paralyzed for the duration.",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        assert parsed.applies_condition is True

        condition_effect = parsed.primary_effect
        assert condition_effect.category == MechanicalEffectCategory.CONDITION
        assert condition_effect.condition_applied == "paralyzed"

    def test_parse_charm_condition(self, resolver):
        """Test parsing charm condition from description."""
        spell = SpellData(
            spell_id="test",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Special",
            range="30'",
            description="Target must Save Versus Spell or be charmed.",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        assert parsed.applies_condition is True

        condition_effect = parsed.primary_effect
        assert condition_effect.condition_applied == "charmed"

    def test_parse_stat_modifier(self, resolver):
        """Test parsing stat modifiers from description."""
        spell = SpellData(
            spell_id="test",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="1 Turn",
            range="Touch",
            description="Grants +2 bonus to AC.",
        )

        parsed = resolver.parse_mechanical_effects(spell)
        assert len(parsed.effects) >= 1

        buff_effect = parsed.effects[0]
        assert buff_effect.category == MechanicalEffectCategory.BUFF
        assert buff_effect.modifier_value == 2


# =============================================================================
# SPELL RESOLUTION INTEGRATION TESTS
# =============================================================================


class TestSpellResolution:
    """Tests for complete spell resolution."""

    @patch("src.narrative.spell_resolver.SpellResolver.can_cast_spell")
    def test_resolve_glamour_records_usage(
        self, mock_can_cast, resolver, caster, glamour_awe, dice
    ):
        """Test that resolving a glamour records usage."""
        mock_can_cast.return_value = (True, "Can cast")
        resolver.register_spell(glamour_awe)
        resolver.set_turn(1)

        result = resolver.resolve_spell(
            caster=caster,
            spell=glamour_awe,
            dice_roller=dice,
        )

        assert result.success is True
        assert result.glamour_usage_recorded is True

    @patch("src.narrative.spell_resolver.SpellResolver.can_cast_spell")
    def test_resolve_rune_records_usage(
        self, mock_can_cast, resolver, caster, lesser_rune, dice
    ):
        """Test that resolving a rune records usage."""
        mock_can_cast.return_value = (True, "Can cast")
        resolver.register_spell(lesser_rune)
        resolver.set_rune_limits(caster.character_id, level=1)

        result = resolver.resolve_spell(
            caster=caster,
            spell=lesser_rune,
            dice_roller=dice,
        )

        assert result.success is True
        assert result.rune_usage_recorded is True

        usage = resolver.get_rune_usage(caster.character_id)
        assert usage.lesser_uses_today == 1

    @patch("src.narrative.spell_resolver.SpellResolver.can_cast_spell")
    def test_resolve_spell_with_save(
        self, mock_can_cast, resolver, caster, charm_spell, dice
    ):
        """Test resolving spell with saving throw."""
        mock_can_cast.return_value = (True, "Can cast")
        resolver.register_spell(charm_spell)
        dice.fixed_value = 5  # Low roll = fail save

        result = resolver.resolve_spell(
            caster=caster,
            spell=charm_spell,
            target_id="npc_1",
            dice_roller=dice,
        )

        assert result.success is True
        assert result.save_required is True
        assert result.save_result is not None
        assert result.save_result.success is False
        assert "npc_1" in result.targets_failed_save

    @patch("src.narrative.spell_resolver.SpellResolver.can_cast_spell")
    def test_resolve_spell_save_negates(
        self, mock_can_cast, resolver, caster, charm_spell, dice
    ):
        """Test spell save negates effect."""
        mock_can_cast.return_value = (True, "Can cast")
        resolver.register_spell(charm_spell)
        dice.fixed_value = 18  # High roll = make save

        result = resolver.resolve_spell(
            caster=caster,
            spell=charm_spell,
            target_id="npc_1",
            dice_roller=dice,
        )

        assert result.success is True
        assert result.save_result.success is True
        assert "npc_1" in result.targets_saved

    @patch("src.narrative.spell_resolver.SpellResolver.can_cast_spell")
    def test_resolve_damage_spell(
        self, mock_can_cast, resolver, caster, damage_spell, dice
    ):
        """Test resolving damage spell."""
        mock_can_cast.return_value = (True, "Can cast")
        resolver.register_spell(damage_spell)
        dice.fixed_value = 8  # 2d6 = 8 damage

        result = resolver.resolve_spell(
            caster=caster,
            spell=damage_spell,
            target_id="npc_1",
            dice_roller=dice,
        )

        assert result.success is True
        assert result.damage_dealt is not None
        assert "npc_1" in result.damage_dealt
        assert result.damage_dealt["npc_1"] == 8

    @patch("src.narrative.spell_resolver.SpellResolver.can_cast_spell")
    def test_resolve_multi_target(
        self, mock_can_cast, resolver, caster, damage_spell, dice
    ):
        """Test resolving spell on multiple targets."""
        mock_can_cast.return_value = (True, "Can cast")
        resolver.register_spell(damage_spell)
        dice.fixed_value = 6

        result = resolver.resolve_spell(
            caster=caster,
            spell=damage_spell,
            target_ids=["npc_1", "npc_2", "npc_3"],
            dice_roller=dice,
        )

        assert result.success is True
        assert len(result.targets_affected) == 3
        assert "npc_1" in result.targets_affected
        assert "npc_2" in result.targets_affected
        assert "npc_3" in result.targets_affected


# =============================================================================
# USAGE RECORD TESTS
# =============================================================================


class TestGlamourUsageRecord:
    """Tests for GlamourUsageRecord class."""

    def test_can_use_at_will(self):
        """Test at-will usage always allowed."""
        record = GlamourUsageRecord(spell_id="test", caster_id="char1")

        can_use, _ = record.can_use(UsageFrequency.AT_WILL, current_turn=1)
        assert can_use is True

        # Even after recording use
        record.record_use(UsageFrequency.AT_WILL, current_turn=1)
        can_use, _ = record.can_use(UsageFrequency.AT_WILL, current_turn=1)
        assert can_use is True

    def test_once_per_turn_blocks_same_turn(self):
        """Test once per turn blocking."""
        record = GlamourUsageRecord(spell_id="test", caster_id="char1")

        record.record_use(UsageFrequency.ONCE_PER_TURN, current_turn=5)

        can_use, _ = record.can_use(UsageFrequency.ONCE_PER_TURN, current_turn=5)
        assert can_use is False

        # Next turn allowed
        can_use, _ = record.can_use(UsageFrequency.ONCE_PER_TURN, current_turn=6)
        assert can_use is True

    def test_once_per_day_tracking(self):
        """Test once per day tracking."""
        record = GlamourUsageRecord(spell_id="test", caster_id="char1")

        record.record_use(UsageFrequency.ONCE_PER_DAY, current_turn=1)

        can_use, _ = record.can_use(UsageFrequency.ONCE_PER_DAY, current_turn=100)
        assert can_use is False

        # After reset
        record.reset_daily()
        can_use, _ = record.can_use(UsageFrequency.ONCE_PER_DAY, current_turn=1)
        assert can_use is True


class TestRuneUsageState:
    """Tests for RuneUsageState class."""

    def test_initial_state(self):
        """Test initial rune usage state."""
        state = RuneUsageState(caster_id="char1")

        assert state.lesser_uses_today == 0
        assert state.greater_uses_today == 0
        assert state.mighty_uses_today == 0

    def test_use_lesser_rune(self):
        """Test using lesser rune."""
        state = RuneUsageState(caster_id="char1")

        state.use_rune("fog_cloud", RuneMagnitude.LESSER)

        assert state.lesser_uses_today == 1
        assert state.greater_uses_today == 0
        assert state.rune_uses["fog_cloud"] == 1

    def test_daily_limit_enforcement(self):
        """Test daily limit enforcement."""
        state = RuneUsageState(caster_id="char1", max_lesser_daily=2)

        state.use_rune("rune1", RuneMagnitude.LESSER)
        state.use_rune("rune2", RuneMagnitude.LESSER)

        can_use, _ = state.can_use_rune("rune3", RuneMagnitude.LESSER)
        assert can_use is False

    def test_reset_daily(self):
        """Test daily reset."""
        state = RuneUsageState(caster_id="char1", max_lesser_daily=2)

        state.use_rune("rune1", RuneMagnitude.LESSER)
        state.use_rune("rune2", RuneMagnitude.LESSER)

        state.reset_daily()

        assert state.lesser_uses_today == 0
        assert state.rune_uses == {}

        can_use, _ = state.can_use_rune("rune1", RuneMagnitude.LESSER)
        assert can_use is True


# =============================================================================
# DAILY RESET TESTS
# =============================================================================


class TestDailyReset:
    """Tests for daily reset functionality."""

    def test_reset_daily_all(self, resolver, caster, glamour_awe, lesser_rune):
        """Test resetting all daily usage."""
        resolver.register_spell(glamour_awe)
        resolver.register_spell(lesser_rune)
        resolver.set_turn(1)
        resolver.set_rune_limits(caster.character_id, level=1)

        # Use glamour (per-turn) and rune
        resolver._record_glamour_usage(caster.character_id, glamour_awe, None)
        resolver._record_rune_usage(caster.character_id, lesser_rune)

        # Reset all
        result = resolver.reset_daily()

        assert result["glamour_records_reset"] >= 1
        assert result["rune_records_reset"] >= 1

        # Can use again (note: for per-turn glamour, we need to move to next turn
        # or test with a per-day glamour - reset_daily clears daily counters)
        # Rune should be usable again after reset
        can_use_rune, _ = resolver._check_rune_usage(caster.character_id, lesser_rune)
        assert can_use_rune is True

    def test_reset_daily_single_caster(self, resolver, caster):
        """Test resetting only specific caster."""
        other_caster = MockCharacterState(character_id="other_char")

        glamour = SpellData(
            spell_id="test_glamour",
            name="Test",
            level=None,
            magic_type=MagicType.FAIRY_GLAMOUR,
            duration="1 Round",
            range="30'",
            description="Test glamour. Once per day.",
            usage_frequency="Once per day",
        )
        resolver.register_spell(glamour)
        resolver.set_turn(1)

        # Both casters use glamour
        resolver._record_glamour_usage(caster.character_id, glamour, None)
        resolver._record_glamour_usage(other_caster.character_id, glamour, None)

        # Reset only first caster
        resolver.reset_daily(caster.character_id)

        # First caster can use again
        can_cast_1, _ = resolver._check_glamour_usage(caster.character_id, glamour, None)
        assert can_cast_1 is True

        # Other caster still blocked
        can_cast_2, _ = resolver._check_glamour_usage(
            other_caster.character_id, glamour, None
        )
        assert can_cast_2 is False
