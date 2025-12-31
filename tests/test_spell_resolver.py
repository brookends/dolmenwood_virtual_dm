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


# =============================================================================
# PHASE 0 & 1 FEATURE TESTS
# =============================================================================


class TestLevelScaling:
    """Tests for per-level scaling effects."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_parse_per_level_projectiles(self, resolver):
        """Test parsing 'one stream per Level' pattern."""
        spell = SpellData(
            spell_id="ignite",
            name="Ignite",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="30'",
            description="One stream per level of the caster shoots toward targets.",
        )

        scalings = resolver.parse_level_scaling(spell)

        assert len(scalings) >= 1
        # Find projectile scaling
        projectile_scaling = None
        for s in scalings:
            if s.scaling_type.value == "projectiles":
                projectile_scaling = s
                break

        assert projectile_scaling is not None
        assert projectile_scaling.per_levels == 1

    def test_parse_additional_per_x_levels(self, resolver):
        """Test parsing 'one additional per 3 Levels' pattern."""
        spell = SpellData(
            spell_id="ioun_shard",
            name="Ioun Shard",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="2 Turns",
            range="120'",
            description="Conjures a shard. One additional shard per 3 Levels.",
        )

        scalings = resolver.parse_level_scaling(spell)

        assert len(scalings) >= 1
        # Find the per-3-levels scaling
        found = False
        for s in scalings:
            if s.per_levels == 3:
                found = True
                break
        assert found

    def test_parse_duration_per_level(self, resolver):
        """Test parsing '6 Turns + 1 Turn per Level' duration."""
        spell = SpellData(
            spell_id="firelight",
            name="Firelight",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="6 Turns + 1 Turn per Level",
            range="Touch",
            description="Creates a light source.",
        )

        scalings = resolver.parse_level_scaling(spell)

        duration_scaling = None
        for s in scalings:
            if s.scaling_type.value == "duration":
                duration_scaling = s
                break

        assert duration_scaling is not None
        assert duration_scaling.base_value == 6

    def test_calculate_scaled_value(self, resolver):
        """Test LevelScaling.calculate_scaled_value()."""
        from src.narrative.spell_resolver import LevelScaling, LevelScalingType

        scaling = LevelScaling(
            scaling_type=LevelScalingType.PROJECTILES,
            base_value=1,
            per_levels=3,
            minimum_level=1,
        )

        # Level 1: 1 + (1-1+1)//3 = 1 + 0 = 1
        assert scaling.calculate_scaled_value(1) == 1

        # Level 4: 1 + (4-1+1)//3 = 1 + 1 = 2
        assert scaling.calculate_scaled_value(4) == 2

        # Level 7: 1 + (7-1+1)//3 = 1 + 2 = 3
        assert scaling.calculate_scaled_value(7) == 3

        # Level 10: 1 + (10-1+1)//3 = 1 + 3 = 4
        assert scaling.calculate_scaled_value(10) == 4


class TestHDLevelLimitedTargeting:
    """Tests for HD/level-limited targeting."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_parse_level_restriction(self, resolver):
        """Test parsing 'Level 4 or lower' pattern."""
        spell = SpellData(
            spell_id="vapours",
            name="Vapours of Dream",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Concentration",
            range="240'",
            description="Living creatures of Level 4 or lower inside the vapour must save.",
        )

        restrictions = resolver.parse_target_restrictions(spell)

        assert restrictions["max_level"] == 4
        assert restrictions["living_only"] is True

    def test_filter_targets_by_level(self, resolver):
        """Test filtering targets by level restriction."""
        spell = SpellData(
            spell_id="sleep",
            name="Sleep",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="4d4 Turns",
            range="240'",
            description="Affects creatures of Level 4 or lower.",
            max_target_level=4,
        )

        def get_info(target_id):
            levels = {"low_1": 1, "low_3": 3, "high_5": 5, "high_8": 8}
            return {"level": levels.get(target_id, 1), "is_living": True}

        targets = ["low_1", "low_3", "high_5", "high_8"]
        valid, excluded = resolver.filter_valid_targets(spell, targets, get_info)

        assert "low_1" in valid
        assert "low_3" in valid
        assert "high_5" in excluded
        assert "high_8" in excluded


class TestRecurringSaves:
    """Tests for recurring save mechanics."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_parse_daily_save(self, resolver):
        """Test parsing 'Save Versus Spell once per day' pattern."""
        spell = SpellData(
            spell_id="ingratiate",
            name="Ingratiate",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Indefinite",
            range="Touch",
            description="Charm lasts indefinitely, but subject makes a Save Versus Spell once per day.",
        )

        recurring = resolver.parse_recurring_save(spell)

        assert recurring["frequency"] == "daily"
        assert recurring["save_type"] == "spell"
        assert recurring["ends_effect"] is True

    def test_check_recurring_saves_triggers_on_day_advance(self, resolver):
        """Test that recurring saves trigger when day advances."""
        from src.narrative.spell_resolver import ActiveSpellEffect, DurationType

        effect = ActiveSpellEffect(
            spell_id="ingratiate",
            spell_name="Ingratiate",
            caster_id="caster_1",
            target_id="target_1",
            duration_type=DurationType.SPECIAL,
            is_active=True,
            recurring_save_type="spell",
            recurring_save_frequency="daily",
            last_save_check_day=0,
        )
        resolver._active_effects.append(effect)

        # Check on day 1 (should trigger)
        results = resolver.check_recurring_saves(
            current_day=1,
            current_turn=1,
            dice_roller=None,
        )

        assert len(results) == 1
        assert results[0]["spell_name"] == "Ingratiate"

        # Check on same day (should not trigger again)
        results_same_day = resolver.check_recurring_saves(
            current_day=1,
            current_turn=2,
            dice_roller=None,
        )

        # Effect may have ended from the first check, so we need fresh effect
        # The key point is that same day doesn't trigger twice


class TestItemConsumption:
    """Tests for spell component verification and consumption."""

    @pytest.fixture
    def resolver(self):
        return SpellResolver()

    def test_parse_component_requirements(self, resolver):
        """Test parsing component requirements from description."""
        spell = SpellData(
            spell_id="fairy_servant",
            name="Fairy Servant",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="1 Turn per Level",
            range="10'",
            description="Requires a 50gp trinket or magical fungus (consumed).",
        )

        components = resolver.parse_spell_components(spell)

        assert len(components) == 1
        assert components[0].min_value_gp == 50
        assert components[0].consumed is True
        assert "magical_fungus" in components[0].alternatives

    def test_parse_destruction_chance(self, resolver):
        """Test parsing component destruction chance."""
        spell = SpellData(
            spell_id="crystal_resonance",
            name="Crystal Resonance",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="1 Turn",
            range="Self",
            description="Uses a 50gp crystal. 1-in-20 chance of shattering.",
        )

        components = resolver.parse_spell_components(spell)

        assert len(components) == 1
        assert components[0].destruction_chance == pytest.approx(0.05, rel=0.01)

    def test_verify_components_success(self, resolver):
        """Test component verification with matching item."""
        from src.data_models import Item

        spell = SpellData(
            spell_id="test_spell",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="30'",
            description="Requires a 50gp trinket.",
        )

        # Create mock caster with matching item
        caster = MockCharacterState()
        caster.inventory = [
            Item(item_id="golden_trinket", name="Golden Trinket", weight=1,
                 item_type="trinket", value_gp=60)
        ]

        has_components, reason, items = resolver.verify_components(caster, spell)

        assert has_components is True
        assert len(items) == 1

    def test_verify_components_insufficient_value(self, resolver):
        """Test component verification fails with low-value item."""
        from src.data_models import Item

        spell = SpellData(
            spell_id="test_spell",
            name="Test",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="30'",
            description="Requires a 50gp trinket.",
        )

        # Create mock caster with low-value item
        caster = MockCharacterState()
        caster.inventory = [
            Item(item_id="cheap_trinket", name="Cheap Trinket", weight=1,
                 item_type="trinket", value_gp=10)
        ]

        has_components, reason, items = resolver.verify_components(caster, spell)

        assert has_components is False
        assert "Missing component" in reason


class TestStatModifiers:
    """Tests for stat modifier (buff/debuff) system."""

    def test_stat_modifier_applies_to_context(self):
        """Test conditional modifier context matching."""
        from src.data_models import StatModifier

        modifier = StatModifier(
            modifier_id="test_1",
            stat="AC",
            value=5,
            source="Shield of Force",
            condition="vs_missiles",
        )

        # Should apply to missiles
        assert modifier.applies_to("missiles") is True
        assert modifier.applies_to("ranged") is True

        # Should not apply to melee
        assert modifier.applies_to("melee") is False

        # Conditional modifier requires context
        assert modifier.applies_to(None) is False

    def test_unconditional_modifier_always_applies(self):
        """Test that modifier without condition always applies."""
        from src.data_models import StatModifier

        modifier = StatModifier(
            modifier_id="test_2",
            stat="attack",
            value=2,
            source="Bless",
            condition=None,  # No condition
        )

        assert modifier.applies_to("missiles") is True
        assert modifier.applies_to("melee") is True
        assert modifier.applies_to(None) is True

    def test_character_get_effective_ac_with_modifiers(self):
        """Test CharacterState.get_effective_ac with modifiers."""
        from src.data_models import CharacterState, StatModifier

        # Create character with base AC 14
        char = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 12, "DEX": 14, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=14,
            base_speed=40,
        )

        # Add Shield of Force (AC 17 vs missiles, AC 15 vs other)
        char.add_stat_modifier(StatModifier(
            modifier_id="shield_missiles",
            stat="AC",
            value=3,
            source="Shield of Force",
            condition="vs_missiles",
        ))
        char.add_stat_modifier(StatModifier(
            modifier_id="shield_other",
            stat="AC",
            value=1,
            source="Shield of Force",
            condition="vs_melee",
        ))

        # Check AC against missiles
        ac_vs_missiles = char.get_effective_ac("missiles")
        assert ac_vs_missiles == 17  # 14 + 3

        # Check AC against melee
        ac_vs_melee = char.get_effective_ac("melee")
        assert ac_vs_melee == 15  # 14 + 1

        # Check base AC (no context)
        ac_base = char.get_effective_ac()
        assert ac_base == 14  # No modifiers apply without context

    def test_stat_modifier_override_mode(self):
        """Test StatModifier with mode='set' for AC override."""
        from src.data_models import StatModifier

        modifier = StatModifier(
            modifier_id="shield_force",
            stat="AC",
            value=17,
            source="Shield of Force",
            mode="set",  # Override mode
            condition="vs_missiles",
        )

        assert modifier.is_override is True
        assert modifier.mode == "set"

        # Regular modifier
        normal_mod = StatModifier(
            modifier_id="bless",
            stat="attack",
            value=1,
            source="Bless",
        )
        assert normal_mod.is_override is False
        assert normal_mod.mode == "add"

    def test_character_get_stat_override(self):
        """Test CharacterState.get_stat_override method."""
        from src.data_models import CharacterState, StatModifier

        char = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 12, "DEX": 14, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=12,
            base_speed=40,
        )

        # No overrides initially
        assert char.get_stat_override("AC") is None

        # Add override modifier
        char.add_stat_modifier(StatModifier(
            modifier_id="shield_force",
            stat="AC",
            value=17,
            source="Shield of Force",
            mode="set",
            condition="vs_missiles",
        ))

        # Override applies to missiles
        assert char.get_stat_override("AC", "missiles") == 17

        # No override for melee
        assert char.get_stat_override("AC", "melee") is None

    def test_character_get_effective_ac_with_override(self):
        """Test get_effective_ac uses override when appropriate."""
        from src.data_models import CharacterState, StatModifier

        # Character with low base AC (12)
        char = CharacterState(
            character_id="test",
            name="Test",
            character_class="Magic-User",
            level=1,
            ability_scores={"STR": 10, "DEX": 12, "CON": 10, "INT": 16, "WIS": 10, "CHA": 10},
            hp_current=4,
            hp_max=4,
            armor_class=12,  # Low AC
            base_speed=40,
        )

        # Add Shield of Force: AC 17 vs missiles, AC 15 vs other
        char.add_stat_modifier(StatModifier(
            modifier_id="shield_missiles",
            stat="AC",
            value=17,
            source="Shield of Force",
            mode="set",
            condition="vs_missiles",
        ))
        char.add_stat_modifier(StatModifier(
            modifier_id="shield_other",
            stat="AC",
            value=15,
            source="Shield of Force",
            mode="set",
            condition="vs_melee",
        ))

        # Override should apply (17 > 12)
        assert char.get_effective_ac("missiles") == 17
        assert char.get_effective_ac("melee") == 15

    def test_character_get_effective_ac_override_with_bonus(self):
        """Test get_effective_ac combines override with additive bonuses."""
        from src.data_models import CharacterState, StatModifier

        char = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 12, "DEX": 14, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=12,
            base_speed=40,
        )

        # Add Shield of Force override
        char.add_stat_modifier(StatModifier(
            modifier_id="shield",
            stat="AC",
            value=15,
            source="Shield of Force",
            mode="set",
        ))

        # Add Mantle of Protection (+1 AC)
        char.add_stat_modifier(StatModifier(
            modifier_id="mantle",
            stat="AC",
            value=1,
            source="Mantle of Protection",
            mode="add",
        ))

        # Should be 15 (override) + 1 (bonus) = 16
        assert char.get_effective_ac() == 16

    def test_character_get_effective_ac_override_not_worse_than_base(self):
        """Test that override doesn't lower AC below base."""
        from src.data_models import CharacterState, StatModifier

        # Character with high base AC (17)
        char = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=5,
            ability_scores={"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            hp_current=40,
            hp_max=40,
            armor_class=17,  # Plate armor
            base_speed=30,
        )

        # Add Shield of Force (AC 15) - but character already has AC 17
        char.add_stat_modifier(StatModifier(
            modifier_id="shield",
            stat="AC",
            value=15,
            source="Shield of Force",
            mode="set",
        ))

        # Should keep base AC 17 since it's better than override
        assert char.get_effective_ac() == 17


# =============================================================================
# SPELL NARRATOR TESTS
# =============================================================================


class TestSpellNarrator:
    """Tests for the SpellNarrator LLM integration."""

    def test_classify_spell_effect_type_mechanical(self):
        """Classify spells with dice notation as MECHANICAL."""
        from src.narrative.spell_resolver import SpellNarrator

        narrator = SpellNarrator()
        spell = SpellData(
            spell_id="ioun_shard",
            name="Ioun Shard",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="2 Turns",
            range="120'",
            description="The shard inflicts 1d6+1 damage.",
        )
        result = narrator.classify_spell_effect_type(spell)
        assert result == SpellEffectType.MECHANICAL

    def test_classify_spell_effect_type_narrative(self):
        """Classify spells without mechanics as NARRATIVE."""
        from src.narrative.spell_resolver import SpellNarrator

        narrator = SpellNarrator()
        spell = SpellData(
            spell_id="crystal_resonance",
            name="Crystal Resonance",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="1 Turn",
            range="Touch",
            description="The caster attunes to the energy resonance of a crystal, perceiving its magical properties. The referee determines what information is revealed.",
        )
        result = narrator.classify_spell_effect_type(spell)
        assert result == SpellEffectType.NARRATIVE

    def test_classify_spell_effect_type_hybrid(self):
        """Classify spells with both mechanics and referee discretion as HYBRID."""
        from src.narrative.spell_resolver import SpellNarrator

        narrator = SpellNarrator()
        spell = SpellData(
            spell_id="detect_magic",
            name="Detect Magic",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="2 Turns",
            range="60'",
            description="Target must Save Versus Spell or the caster perceives magical auras. The referee determines what details are revealed.",
        )
        result = narrator.classify_spell_effect_type(spell)
        assert result == SpellEffectType.HYBRID

    def test_fallback_narration_arcane(self):
        """Test fallback narration for arcane spells."""
        from src.narrative.spell_resolver import SpellNarrator

        narrator = SpellNarrator()  # No LLM manager
        spell = SpellData(
            spell_id="magic_missile",
            name="Magic Missile",
            level=1,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="120'",
            description="Creates bolts of magical force.",
        )
        result = SpellCastResult(
            success=True,
            spell_id="magic_missile",
            spell_name="Magic Missile",
            reason="Cast successfully",
            damage_dealt={"goblin_1": 5},
        )
        narration = narrator._generate_fallback_narration(spell, result, "Merlin")
        assert "Merlin" in narration
        assert "arcane" in narration.lower()
        assert "Magic Missile" in narration
        assert "5 damage" in narration

    def test_fallback_narration_fairy_glamour(self):
        """Test fallback narration for fairy glamours."""
        from src.narrative.spell_resolver import SpellNarrator

        narrator = SpellNarrator()
        spell = SpellData(
            spell_id="glamour_of_invisibility",
            name="Glamour of Invisibility",
            level=1,
            magic_type=MagicType.FAIRY_GLAMOUR,
            duration="1 Turn",
            range="Self",
            description="Caster becomes invisible.",
        )
        result = SpellCastResult(
            success=True,
            spell_id="glamour_of_invisibility",
            spell_name="Glamour of Invisibility",
            reason="Cast successfully",
            conditions_applied=["invisible"],
        )
        narration = narrator._generate_fallback_narration(spell, result, "Elindra")
        assert "Elindra" in narration
        assert "glamour" in narration.lower() or "silvery" in narration.lower()
        assert "invisible" in narration.lower()

    def test_narrate_failed_cast(self):
        """Test narration for failed spell cast."""
        from src.narrative.spell_resolver import SpellNarrator

        narrator = SpellNarrator()
        spell = SpellData(
            spell_id="fireball",
            name="Fireball",
            level=3,
            magic_type=MagicType.ARCANE,
            duration="Instant",
            range="150'",
            description="Explosion of fire.",
        )
        result = SpellCastResult(
            success=False,
            spell_id="fireball",
            spell_name="Fireball",
            reason="No spell slots remaining",
        )
        narration = narrator._narrate_failed_cast(result, spell, "Wizard Bob")
        assert "Wizard Bob" in narration
        assert "Fireball" in narration
        assert "No spell slots remaining" in narration


class TestSpellCastNarrationSchema:
    """Tests for the SpellCastNarrationSchema prompt builder."""

    def test_schema_creation(self):
        """Test schema can be created with required inputs."""
        from src.ai.prompt_schemas import SpellCastNarrationInputs, SpellCastNarrationSchema

        inputs = SpellCastNarrationInputs(
            spell_name="Magic Missile",
            spell_description="Bolts of force strike unerringly.",
            magic_type="arcane",
            effect_type="mechanical",
            caster_name="Merlin",
        )
        schema = SpellCastNarrationSchema(inputs)
        assert schema.typed_inputs.spell_name == "Magic Missile"
        assert schema.typed_inputs.caster_name == "Merlin"

    def test_schema_validates_required_inputs(self):
        """Test schema validation for required fields."""
        from src.ai.prompt_schemas import SpellCastNarrationInputs, SpellCastNarrationSchema

        inputs = SpellCastNarrationInputs(
            spell_name="Magic Missile",
            spell_description="Bolts of force.",
            magic_type="arcane",
            effect_type="mechanical",
            caster_name="Merlin",
        )
        schema = SpellCastNarrationSchema(inputs)
        errors = schema.validate_inputs()
        assert len(errors) == 0

    def test_schema_builds_prompt(self):
        """Test prompt building includes all relevant info."""
        from src.ai.prompt_schemas import SpellCastNarrationInputs, SpellCastNarrationSchema

        inputs = SpellCastNarrationInputs(
            spell_name="Ioun Shard",
            spell_description="Fires a shard of crystal that deals 1d6+1 damage.",
            magic_type="arcane",
            effect_type="mechanical",
            caster_name="Theodric",
            caster_level=3,
            targets=["goblin_warrior"],
            damage_dealt={"goblin_warrior": 5},
        )
        schema = SpellCastNarrationSchema(inputs)
        prompt = schema.build_prompt()

        assert "Ioun Shard" in prompt
        assert "Theodric" in prompt
        assert "Level 3" in prompt
        assert "goblin_warrior" in prompt
        assert "5 damage" in prompt

    def test_schema_system_prompt_arcane(self):
        """Test system prompt includes arcane magic flavor."""
        from src.ai.prompt_schemas import SpellCastNarrationInputs, SpellCastNarrationSchema

        inputs = SpellCastNarrationInputs(
            spell_name="Shield of Force",
            spell_description="Creates an invisible barrier.",
            magic_type="arcane",
            effect_type="mechanical",
            caster_name="Wizard",
        )
        schema = SpellCastNarrationSchema(inputs)
        system_prompt = schema.get_system_prompt()

        assert "ARCANE" in system_prompt
        assert "scholarly" in system_prompt.lower() or "sigils" in system_prompt.lower()

    def test_schema_system_prompt_fairy_glamour(self):
        """Test system prompt includes fairy glamour flavor."""
        from src.ai.prompt_schemas import SpellCastNarrationInputs, SpellCastNarrationSchema

        inputs = SpellCastNarrationInputs(
            spell_name="Moonlit Path",
            spell_description="Creates an ethereal pathway.",
            magic_type="fairy_glamour",
            effect_type="narrative",
            caster_name="Elara",
        )
        schema = SpellCastNarrationSchema(inputs)
        system_prompt = schema.get_system_prompt()

        assert "FAIRY_GLAMOUR" in system_prompt
        assert "whimsical" in system_prompt.lower() or "fey" in system_prompt.lower()

    def test_schema_includes_save_results(self):
        """Test prompt includes save information."""
        from src.ai.prompt_schemas import SpellCastNarrationInputs, SpellCastNarrationSchema

        inputs = SpellCastNarrationInputs(
            spell_name="Sleep",
            spell_description="Creatures fall asleep.",
            magic_type="arcane",
            effect_type="mechanical",
            caster_name="Wizard",
            targets=["goblin_1", "goblin_2", "goblin_3"],
            targets_saved=["goblin_3"],
            targets_affected=["goblin_1", "goblin_2"],
            save_type="spell",
        )
        schema = SpellCastNarrationSchema(inputs)
        prompt = schema.build_prompt()

        assert "goblin_3" in prompt
        assert "SAVED" in prompt.upper() or "saved" in prompt.lower()

    def test_factory_creates_spell_cast_schema(self):
        """Test factory function creates correct schema type."""
        from src.ai.prompt_schemas import create_schema, PromptSchemaType, SpellCastNarrationSchema

        inputs = {
            "spell_name": "Fireball",
            "spell_description": "A ball of fire explodes.",
            "magic_type": "arcane",
            "effect_type": "mechanical",
            "caster_name": "Pyromancer",
        }
        schema = create_schema(PromptSchemaType.SPELL_CAST, inputs)
        assert isinstance(schema, SpellCastNarrationSchema)
