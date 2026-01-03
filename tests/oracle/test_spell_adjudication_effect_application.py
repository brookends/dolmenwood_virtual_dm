"""
Tests for applying spell adjudication predetermined_effects via EffectExecutor.

Phase 9.1: Verify that all effects produced by the new adjudication types
can be parsed and executed by the EffectExecutor.
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    AdjudicationContext,
    SuccessLevel,
)
from src.oracle.effect_commands import (
    EffectExecutor,
    EffectType,
    EffectCommandBuilder,
)


@pytest.fixture(autouse=True)
def reset_dice():
    """Reset dice state before and after each test."""
    DiceRoller.clear_roll_log()
    yield
    DiceRoller.clear_roll_log()


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.set_seed(42)
    return DiceRoller()


@pytest.fixture
def test_character():
    """A sample character for testing effects."""
    return CharacterState(
        character_id="test_target",
        name="Test Target",
        character_class="Fighter",
        level=5,
        ability_scores={
            "STR": 14, "INT": 10, "WIS": 12,
            "DEX": 13, "CON": 15, "CHA": 11,
        },
        hp_current=30,
        hp_max=30,
        armor_class=5,
        base_speed=30,
    )


@pytest.fixture
def dm_with_character(seeded_dice, test_character):
    """Create VirtualDM with a character for testing effects."""
    config = GameConfig(
        llm_provider="mock",
        enable_narration=False,
        load_content=False,
    )

    dm = VirtualDM(
        config=config,
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=10, minute=0),
    )

    dm.controller.add_character(test_character)
    return dm


@pytest.fixture
def adjudicator():
    """Create a fresh adjudicator for each test."""
    return MythicSpellAdjudicator()


def seed_dice(seed: int) -> None:
    """Helper to seed dice."""
    DiceRoller.set_seed(seed)


# =============================================================================
# NEW EFFECT TYPE EXECUTION TESTS
# =============================================================================


class TestExtendConditionDurationEffect:
    """Test that extend_condition_duration effect executes correctly."""

    def test_extend_condition_duration_simulated(self, seeded_dice):
        """Without controller, extension should be simulated."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.extend_condition_duration(
            target_id="test_char",
            condition="haste",
            turns=5,
            source="Extension Spell",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("simulated") is True
        assert result.changes.get("condition") == "haste"
        assert result.changes.get("extended_turns") == 5

    def test_extend_condition_requires_condition_name(self, seeded_dice):
        """Extension without condition should fail."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.extend_condition_duration(
            target_id="test_char",
            condition="",  # Empty
            turns=5,
            source="Test",
        )

        result = executor.execute(cmd)

        assert result.success is False
        assert "condition" in result.error.lower()


class TestSetFlagEffect:
    """Test that set_flag effect executes correctly."""

    def test_set_flag_basic(self, seeded_dice):
        """Set flag should succeed and report changes."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.set_flag(
            target_id="test_target",
            flag_name="protection_bypassed",
            flag_value=True,
            scope="interaction",
            source="Dispel Magic",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("flag_name") == "protection_bypassed"
        assert result.changes.get("flag_value") is True
        assert result.changes.get("scope") == "interaction"

    def test_set_flag_requires_name(self, seeded_dice):
        """Set flag without name should fail."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.set_flag(
            target_id="test_target",
            flag_name="",  # Empty
            flag_value=True,
        )

        result = executor.execute(cmd)

        assert result.success is False
        assert "flag_name" in result.error.lower()


class TestModifyDispositionEffect:
    """Test that modify_disposition effect executes correctly."""

    def test_modify_disposition_simulated(self, seeded_dice):
        """Without controller, disposition change should be simulated."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)
        cmd = EffectCommandBuilder.modify_disposition(
            target_id="town_guard",
            delta=-1,
            reason="Sensed charm attempt",
            source="Charm Person resisted",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("simulated") is True
        assert result.changes.get("delta") == -1
        assert result.changes.get("npc_id") == "town_guard"


# =============================================================================
# ADJUDICATION EFFECT APPLICATION TESTS
# =============================================================================


class TestCharmResistanceEffectApplication:
    """Test applying charm resistance adjudication effects."""

    def test_charm_failure_effects_are_executable(self, adjudicator, seeded_dice):
        """Effects from charm failure should be executable."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        # Find a seed that produces failure
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Charm Person",
                caster_name="Enchantress",
                caster_level=10,
                target_description="test_target",
            )
            result = adjudicator.adjudicate_charm_resistance(
                context, target_hit_dice=1, charm_strength="strong"
            )
            if result.success_level in (SuccessLevel.FAILURE, SuccessLevel.CATASTROPHIC_FAILURE):
                # Execute all effects
                for effect in result.predetermined_effects:
                    exec_result = executor.execute(effect)
                    assert exec_result.success is True, f"Effect {effect} failed: {exec_result.error}"
                return

        pytest.fail("Could not find seed producing charm failure")

    def test_charm_exceptional_effects_are_executable(self, adjudicator, seeded_dice):
        """Effects from exceptional resistance should be executable."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        for seed in range(200):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Charm Person",
                caster_name="Enchantress",
                caster_level=3,
                target_description="test_target",
                magical_resistance=True,
            )
            result = adjudicator.adjudicate_charm_resistance(
                context, target_hit_dice=8, charm_strength="weak"
            )
            if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
                for effect in result.predetermined_effects:
                    exec_result = executor.execute(effect)
                    assert exec_result.success is True
                return

        pytest.fail("Could not find seed producing exceptional resistance")


class TestProtectionBypassEffectApplication:
    """Test applying protection bypass adjudication effects."""

    def test_bypass_success_effects_are_executable(self, adjudicator, seeded_dice):
        """Effects from bypass success should be executable."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Dispel Magic",
                caster_name="Archmage",
                caster_level=14,
                target_description="warded_door",
            )
            result = adjudicator.adjudicate_protection_bypass(
                context, protection_strength="minor", spell_level=5
            )
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                for effect in result.predetermined_effects:
                    exec_result = executor.execute(effect)
                    assert exec_result.success is True, f"Effect {effect} failed: {exec_result.error}"
                return

        pytest.fail("Could not find seed producing bypass success")


class TestDurationExtensionEffectApplication:
    """Test applying duration extension adjudication effects."""

    def test_extension_success_effects_are_executable(self, adjudicator, seeded_dice):
        """Effects from extension success should be executable."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Extend Duration",
                caster_name="Chronomancer",
                caster_level=14,
                target_description="test_target",
            )
            result = adjudicator.adjudicate_duration_extension(
                context, condition_to_extend="haste", original_duration_turns=10
            )
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                for effect in result.predetermined_effects:
                    exec_result = executor.execute(effect)
                    assert exec_result.success is True, f"Effect {effect} failed: {exec_result.error}"
                # Verify it's the right effect type
                assert any(
                    e.effect_type == EffectType.EXTEND_CONDITION_DURATION
                    for e in result.predetermined_effects
                )
                return

        pytest.fail("Could not find seed producing extension success")


class TestRealityWarpEffectApplication:
    """Test applying reality warp adjudication effects."""

    def test_warp_success_effects_are_executable(self, adjudicator, seeded_dice):
        """Effects from warp success should be executable."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Polymorph",
                caster_name="Transmuter",
                caster_level=14,
                target_description="test_target",
            )
            result = adjudicator.adjudicate_reality_warp(context, warp_intensity="minor")
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                for effect in result.predetermined_effects:
                    exec_result = executor.execute(effect)
                    assert exec_result.success is True, f"Effect {effect} failed: {exec_result.error}"
                return

        pytest.fail("Could not find seed producing warp success")

    def test_warp_backlash_effects_are_executable(self, adjudicator, seeded_dice):
        """Backlash effects should be executable."""
        executor = EffectExecutor(controller=None, dice_roller=seeded_dice)

        for seed in range(200):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Dangerous Polymorph",
                caster_name="TestCaster",
                caster_level=5,
                target_description="test_target",
            )
            result = adjudicator.adjudicate_reality_warp(context, warp_intensity="legendary")
            if result.has_complication:  # Backlash
                for effect in result.predetermined_effects:
                    exec_result = executor.execute(effect)
                    assert exec_result.success is True, f"Effect {effect} failed: {exec_result.error}"
                return

        pytest.fail("Could not find seed producing backlash")


# =============================================================================
# INTEGRATION WITH CONTROLLER
# =============================================================================


class TestEffectApplicationWithController:
    """Test effect application with actual game controller."""

    def test_add_condition_with_controller(self, dm_with_character, seeded_dice):
        """Add condition effect should work with controller."""
        controller = dm_with_character.controller
        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)

        cmd = EffectCommandBuilder.add_condition(
            target_id="test_target",
            condition="charmed",
            duration="1 hour",
            source="Charm Person",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert result.changes.get("simulated") is not True

    def test_damage_backlash_with_controller(self, dm_with_character, seeded_dice):
        """Damage from backlash should work with controller."""
        controller = dm_with_character.controller
        char = controller.get_character("test_target")
        initial_hp = char.hp_current

        executor = EffectExecutor(controller=controller, dice_roller=seeded_dice)

        cmd = EffectCommandBuilder.damage(
            target_id="test_target",
            amount=5,
            damage_type="psychic",
            source="Reality warp backlash",
        )

        result = executor.execute(cmd)

        assert result.success is True
        assert char.hp_current == initial_hp - 5


class TestEffectStringRepresentation:
    """Test that effect commands have useful string representations."""

    def test_effect_commands_stringify(self, adjudicator):
        """All effects should have string representation for logging."""
        seed_dice(42)
        context = AdjudicationContext(
            spell_name="Test",
            caster_name="Caster",
            caster_level=5,
            target_description="Target",
        )

        # Get effects from various adjudications
        all_effects = []

        result = adjudicator.adjudicate_charm_resistance(context, target_hit_dice=1)
        all_effects.extend(result.predetermined_effects)

        seed_dice(43)
        result = adjudicator.adjudicate_protection_bypass(context, spell_level=3)
        all_effects.extend(result.predetermined_effects)

        seed_dice(44)
        result = adjudicator.adjudicate_duration_extension(context, condition_to_extend="x")
        all_effects.extend(result.predetermined_effects)

        seed_dice(45)
        result = adjudicator.adjudicate_reality_warp(context)
        all_effects.extend(result.predetermined_effects)

        # All effects should stringify without error
        for effect in all_effects:
            str_repr = str(effect)
            assert isinstance(str_repr, str)
            assert len(str_repr) > 0
