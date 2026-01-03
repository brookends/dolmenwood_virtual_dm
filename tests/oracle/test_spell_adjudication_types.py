"""
Tests for the four spell adjudication types implemented in P9.1:
- CHARM_RESISTANCE
- PROTECTION_BYPASS
- DURATION_EXTENSION
- REALITY_WARP

Each test:
- Seeds dice for determinism
- Runs adjudication
- Asserts outcome is in allowed set
- Asserts predetermined_effects are non-empty when outcome indicates success
- Asserts no exceptions
"""

import pytest

from src.data_models import DiceRoller
from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    AdjudicationContext,
    SpellAdjudicationType,
    SuccessLevel,
)
from src.oracle.effect_commands import EffectCommand, EffectType


@pytest.fixture(autouse=True)
def reset_dice():
    """Reset dice state before and after each test."""
    DiceRoller.clear_roll_log()
    yield
    DiceRoller.clear_roll_log()


@pytest.fixture
def adjudicator():
    """Create a fresh adjudicator for each test."""
    return MythicSpellAdjudicator()


def seed_dice(seed: int) -> None:
    """Helper to seed dice for deterministic tests."""
    DiceRoller.set_seed(seed)


# =============================================================================
# CHARM RESISTANCE TESTS
# =============================================================================


class TestCharmResistanceAdjudication:
    """Tests for adjudicate_charm_resistance."""

    def test_charm_resistance_returns_valid_result(self, adjudicator):
        """Basic test that charm resistance returns valid result structure."""
        seed_dice(42)

        context = AdjudicationContext(
            spell_name="Charm Person",
            caster_name="Evil Wizard",
            caster_level=5,
            target_description="Town Guard",
        )

        result = adjudicator.adjudicate_charm_resistance(
            context=context,
            target_hit_dice=2,
            charm_strength="standard",
        )

        assert result is not None
        assert result.adjudication_type == SpellAdjudicationType.CHARM_RESISTANCE
        assert result.success_level in list(SuccessLevel)
        assert result.primary_fate_check is not None
        assert result.summary != ""

    def test_charm_resistance_outcome_in_allowed_set(self, adjudicator):
        """Charm resistance outcome must be in allowed success levels."""
        allowed_outcomes = {
            SuccessLevel.EXCEPTIONAL_SUCCESS,
            SuccessLevel.SUCCESS,
            SuccessLevel.PARTIAL_SUCCESS,
            SuccessLevel.FAILURE,
            SuccessLevel.CATASTROPHIC_FAILURE,
        }

        for seed in range(10):
            seed_dice(seed * 100)
            context = AdjudicationContext(
                spell_name="Charm Person",
                caster_name="Caster",
                caster_level=7,
                target_description="Target",
            )
            result = adjudicator.adjudicate_charm_resistance(context, target_hit_dice=3)
            assert result.success_level in allowed_outcomes

    def test_charm_failure_produces_charmed_condition_effect(self, adjudicator):
        """When target fails to resist, charmed condition should be applied."""
        # Find a seed that produces failure (charm succeeds)
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Charm Person",
                caster_name="Enchantress",
                caster_level=10,
                target_description="Villager",
            )
            result = adjudicator.adjudicate_charm_resistance(
                context, target_hit_dice=1, charm_strength="strong"
            )
            if result.success_level in (SuccessLevel.FAILURE, SuccessLevel.CATASTROPHIC_FAILURE):
                # Should have charmed condition effect
                assert len(result.predetermined_effects) > 0
                charm_effects = [
                    e for e in result.predetermined_effects
                    if e.effect_type == EffectType.ADD_CONDITION
                    and e.parameters.get("condition") == "charmed"
                ]
                assert len(charm_effects) > 0, "Charmed condition should be applied on failure"
                return

        pytest.fail("Could not find a seed that produces charm failure")

    def test_charm_resistance_exceptional_produces_disposition_effect(self, adjudicator):
        """Exceptional resistance should produce suspicious disposition."""
        # Find a seed that produces exceptional success
        for seed in range(200):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Charm Person",
                caster_name="Enchantress",
                caster_level=3,
                target_description="Wise Elder",
                magical_resistance=True,  # Helps resistance
            )
            result = adjudicator.adjudicate_charm_resistance(
                context, target_hit_dice=8, charm_strength="weak"
            )
            if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
                # Should have disposition modification effect
                assert len(result.predetermined_effects) > 0
                disp_effects = [
                    e for e in result.predetermined_effects
                    if e.effect_type == EffectType.MODIFY_DISPOSITION
                ]
                assert len(disp_effects) > 0, "Disposition effect should be applied on exceptional resist"
                return

        pytest.fail("Could not find a seed that produces exceptional resistance")

    def test_charm_resistance_no_exceptions(self, adjudicator):
        """Charm resistance should not raise exceptions with various inputs."""
        contexts = [
            AdjudicationContext("Charm Person", "Caster", 1, "Target"),
            AdjudicationContext("Charm Monster", "Caster", 20, "Dragon"),
            AdjudicationContext("Suggestion", "Caster", 5, ""),
        ]

        for i, context in enumerate(contexts):
            seed_dice(i * 50)
            for hd in [1, 5, 10, 20]:
                for strength in ["weak", "standard", "strong"]:
                    result = adjudicator.adjudicate_charm_resistance(
                        context, target_hit_dice=hd, charm_strength=strength
                    )
                    assert result is not None


# =============================================================================
# PROTECTION BYPASS TESTS
# =============================================================================


class TestProtectionBypassAdjudication:
    """Tests for adjudicate_protection_bypass."""

    def test_protection_bypass_returns_valid_result(self, adjudicator):
        """Basic test that protection bypass returns valid result structure."""
        seed_dice(42)

        context = AdjudicationContext(
            spell_name="Dispel Magic",
            caster_name="Archmage",
            caster_level=12,
            target_description="Warded Door",
        )

        result = adjudicator.adjudicate_protection_bypass(
            context=context,
            protection_strength="standard",
            spell_level=3,
        )

        assert result is not None
        assert result.adjudication_type == SpellAdjudicationType.PROTECTION_BYPASS
        assert result.success_level in list(SuccessLevel)
        assert result.primary_fate_check is not None

    def test_protection_bypass_success_sets_flag(self, adjudicator):
        """Successful bypass should set protection_bypassed flag."""
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Dispel Magic",
                caster_name="Archmage",
                caster_level=14,
                target_description="Warded Door",
            )
            result = adjudicator.adjudicate_protection_bypass(
                context, protection_strength="minor", spell_level=5
            )
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                # Should have protection_bypassed flag
                flag_effects = [
                    e for e in result.predetermined_effects
                    if e.effect_type == EffectType.SET_FLAG
                    and e.parameters.get("flag_name") == "protection_bypassed"
                ]
                assert len(flag_effects) > 0, "protection_bypassed flag should be set on success"
                return

        pytest.fail("Could not find a seed that produces bypass success")

    def test_protection_bypass_exceptional_weakens_protection(self, adjudicator):
        """Exceptional success should also set protection_weakened flag."""
        for seed in range(200):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Greater Dispel",
                caster_name="Archmage",
                caster_level=18,
                target_description="Minor Ward",
            )
            result = adjudicator.adjudicate_protection_bypass(
                context, protection_strength="minor", spell_level=7
            )
            if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
                flag_names = [
                    e.parameters.get("flag_name")
                    for e in result.predetermined_effects
                    if e.effect_type == EffectType.SET_FLAG
                ]
                assert "protection_bypassed" in flag_names
                assert "protection_weakened" in flag_names
                return

        pytest.fail("Could not find a seed that produces exceptional bypass")

    def test_protection_bypass_failure_no_effects(self, adjudicator):
        """Failed bypass should not set any flags."""
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Knock",
                caster_name="Apprentice",
                caster_level=3,
                target_description="Legendary Ward",
            )
            result = adjudicator.adjudicate_protection_bypass(
                context, protection_strength="legendary", spell_level=2
            )
            if result.success_level == SuccessLevel.FAILURE:
                # Should have no flag effects
                flag_effects = [
                    e for e in result.predetermined_effects
                    if e.effect_type == EffectType.SET_FLAG
                ]
                assert len(flag_effects) == 0, "No flags should be set on failure"
                return

        pytest.fail("Could not find a seed that produces bypass failure")

    def test_protection_bypass_no_exceptions(self, adjudicator):
        """Protection bypass should not raise exceptions with various inputs."""
        for seed in range(10):
            seed_dice(seed * 100)
            context = AdjudicationContext(
                spell_name="Test Spell",
                caster_name="Caster",
                caster_level=seed + 1,
                target_description="Target",
            )
            for strength in ["minor", "standard", "powerful", "legendary"]:
                for spell_level in [0, 1, 3, 5, 7, 9]:
                    result = adjudicator.adjudicate_protection_bypass(
                        context, protection_strength=strength, spell_level=spell_level
                    )
                    assert result is not None


# =============================================================================
# DURATION EXTENSION TESTS
# =============================================================================


class TestDurationExtensionAdjudication:
    """Tests for adjudicate_duration_extension."""

    def test_duration_extension_returns_valid_result(self, adjudicator):
        """Basic test that duration extension returns valid result structure."""
        seed_dice(42)

        context = AdjudicationContext(
            spell_name="Extend Duration",
            caster_name="Chronomancer",
            caster_level=9,
            target_description="Ally",
        )

        result = adjudicator.adjudicate_duration_extension(
            context=context,
            condition_to_extend="invisible",
            original_duration_turns=10,
            extension_power="standard",
        )

        assert result is not None
        assert result.adjudication_type == SpellAdjudicationType.DURATION_EXTENSION
        assert result.success_level in list(SuccessLevel)

    def test_duration_extension_success_produces_effect(self, adjudicator):
        """Successful extension should produce extend_condition_duration effect."""
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Extend Duration",
                caster_name="Chronomancer",
                caster_level=14,
                target_description="Ally",
            )
            result = adjudicator.adjudicate_duration_extension(
                context, condition_to_extend="haste", original_duration_turns=10
            )
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                extend_effects = [
                    e for e in result.predetermined_effects
                    if e.effect_type == EffectType.EXTEND_CONDITION_DURATION
                ]
                assert len(extend_effects) > 0, "Extension effect should be created on success"
                # Check condition matches
                assert extend_effects[0].parameters.get("condition") == "haste"
                return

        pytest.fail("Could not find a seed that produces extension success")

    def test_duration_extension_exceptional_doubles_duration(self, adjudicator):
        """Exceptional success should extend by full original duration."""
        for seed in range(200):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Greater Extend",
                caster_name="Chronomancer",
                caster_level=18,
                target_description="Ally",
            )
            result = adjudicator.adjudicate_duration_extension(
                context,
                condition_to_extend="fly",
                original_duration_turns=20,
                extension_power="minor",
            )
            if result.success_level == SuccessLevel.EXCEPTIONAL_SUCCESS:
                extend_effects = [
                    e for e in result.predetermined_effects
                    if e.effect_type == EffectType.EXTEND_CONDITION_DURATION
                ]
                assert len(extend_effects) > 0
                # Exceptional should double (extend by original amount)
                assert extend_effects[0].parameters.get("extend_turns") == 20
                return

        pytest.fail("Could not find a seed that produces exceptional extension")

    def test_duration_extension_failure_no_effects(self, adjudicator):
        """Failed extension should not produce any effects."""
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Weak Extend",
                caster_name="Apprentice",
                caster_level=2,
                target_description="Ally",
            )
            result = adjudicator.adjudicate_duration_extension(
                context,
                condition_to_extend="stoneskin",
                original_duration_turns=5,
                extension_power="major",
            )
            if result.success_level == SuccessLevel.FAILURE:
                assert len(result.predetermined_effects) == 0
                return

        pytest.fail("Could not find a seed that produces extension failure")

    def test_duration_extension_no_exceptions(self, adjudicator):
        """Duration extension should not raise exceptions with various inputs."""
        for seed in range(10):
            seed_dice(seed * 100)
            context = AdjudicationContext(
                spell_name="Extend",
                caster_name="Caster",
                caster_level=seed + 1,
                target_description="Target",
            )
            for power in ["minor", "standard", "major"]:
                for duration in [1, 10, 60, 100]:
                    result = adjudicator.adjudicate_duration_extension(
                        context,
                        condition_to_extend="test_condition",
                        original_duration_turns=duration,
                        extension_power=power,
                    )
                    assert result is not None


# =============================================================================
# REALITY WARP TESTS
# =============================================================================


class TestRealityWarpAdjudication:
    """Tests for adjudicate_reality_warp."""

    def test_reality_warp_returns_valid_result(self, adjudicator):
        """Basic test that reality warp returns valid result structure."""
        seed_dice(42)

        context = AdjudicationContext(
            spell_name="Polymorph",
            caster_name="Transmuter",
            caster_level=9,
            target_description="Goblin",
        )

        result = adjudicator.adjudicate_reality_warp(
            context=context,
            warp_intensity="standard",
        )

        assert result is not None
        assert result.adjudication_type == SpellAdjudicationType.REALITY_WARP
        assert result.success_level in list(SuccessLevel)
        # Should have warp_category in context
        assert "warp_category" in result.interpretation_context
        assert "warp_roll" in result.interpretation_context

    def test_reality_warp_produces_effects_on_success(self, adjudicator):
        """Successful reality warp should produce effects."""
        for seed in range(100):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Polymorph",
                caster_name="Transmuter",
                caster_level=14,
                target_description="Enemy",
            )
            result = adjudicator.adjudicate_reality_warp(context, warp_intensity="minor")
            if result.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                assert len(result.predetermined_effects) > 0, "Effects should be produced on success"
                return

        pytest.fail("Could not find a seed that produces warp success")

    def test_reality_warp_category_is_deterministic(self, adjudicator):
        """Warp category should be deterministic with same seed."""
        seed_dice(12345)
        context = AdjudicationContext(
            spell_name="Warp Reality",
            caster_name="Wizard",
            caster_level=10,
            target_description="Target",
        )
        result1 = adjudicator.adjudicate_reality_warp(context)

        seed_dice(12345)
        result2 = adjudicator.adjudicate_reality_warp(context)

        assert result1.interpretation_context["warp_category"] == result2.interpretation_context["warp_category"]
        assert result1.interpretation_context["warp_roll"] == result2.interpretation_context["warp_roll"]

    def test_reality_warp_backlash_produces_effects_on_caster(self, adjudicator):
        """Backlash should produce effects targeting the caster."""
        # Find a seed with backlash
        for seed in range(200):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Dangerous Polymorph",
                caster_name="TestCaster",
                caster_level=5,
                target_description="Target",
            )
            result = adjudicator.adjudicate_reality_warp(context, warp_intensity="legendary")
            if result.has_complication:  # Backlash occurred
                # Find effects on caster
                caster_effects = [
                    e for e in result.predetermined_effects
                    if e.target_id == "TestCaster"
                ]
                assert len(caster_effects) > 0, "Backlash should produce effects on caster"
                return

        pytest.fail("Could not find a seed that produces backlash")

    def test_reality_warp_all_categories_valid(self, adjudicator):
        """All warp categories should be valid strings."""
        valid_categories = {
            "temporary_condition",
            "displacement",
            "resource_loss",
            "environmental_change",
            "transformation",
            "temporal_effect",
            "planar_echo",
        }

        for seed in range(50):
            seed_dice(seed)
            context = AdjudicationContext(
                spell_name="Warp",
                caster_name="Caster",
                caster_level=10,
                target_description="Target",
            )
            result = adjudicator.adjudicate_reality_warp(context)
            category = result.interpretation_context.get("warp_category")
            assert category in valid_categories, f"Invalid category: {category}"

    def test_reality_warp_no_exceptions(self, adjudicator):
        """Reality warp should not raise exceptions with various inputs."""
        for seed in range(10):
            seed_dice(seed * 100)
            context = AdjudicationContext(
                spell_name="Warp",
                caster_name="Caster",
                caster_level=seed + 1,
                target_description="Target",
            )
            for intensity in ["minor", "standard", "major", "legendary"]:
                result = adjudicator.adjudicate_reality_warp(context, warp_intensity=intensity)
                assert result is not None


# =============================================================================
# CROSS-TYPE TESTS
# =============================================================================


class TestAdjudicationTypeConsistency:
    """Tests that all adjudication types follow consistent patterns."""

    @pytest.mark.parametrize("seed", [0, 42, 100, 999])
    def test_all_types_produce_summaries(self, adjudicator, seed):
        """All adjudication types should produce non-empty summaries."""
        seed_dice(seed)
        context = AdjudicationContext(
            spell_name="Test Spell",
            caster_name="Test Caster",
            caster_level=7,
            target_description="Test Target",
        )

        charm_result = adjudicator.adjudicate_charm_resistance(context, target_hit_dice=3)
        assert charm_result.summary != ""

        seed_dice(seed)
        bypass_result = adjudicator.adjudicate_protection_bypass(context, spell_level=3)
        assert bypass_result.summary != ""

        seed_dice(seed)
        extend_result = adjudicator.adjudicate_duration_extension(
            context, condition_to_extend="test"
        )
        assert extend_result.summary != ""

        seed_dice(seed)
        warp_result = adjudicator.adjudicate_reality_warp(context)
        assert warp_result.summary != ""

    @pytest.mark.parametrize("seed", [0, 42, 100, 999])
    def test_all_types_have_primary_fate_check(self, adjudicator, seed):
        """All adjudication types should have a primary fate check."""
        seed_dice(seed)
        context = AdjudicationContext(
            spell_name="Test Spell",
            caster_name="Test Caster",
            caster_level=7,
            target_description="Test Target",
        )

        results = [
            adjudicator.adjudicate_charm_resistance(context, target_hit_dice=3),
        ]
        seed_dice(seed)
        results.append(adjudicator.adjudicate_protection_bypass(context, spell_level=3))
        seed_dice(seed)
        results.append(adjudicator.adjudicate_duration_extension(context, condition_to_extend="x"))
        seed_dice(seed)
        results.append(adjudicator.adjudicate_reality_warp(context))

        for result in results:
            assert result.primary_fate_check is not None
            assert result.primary_fate_check.roll > 0

    def test_all_types_have_correct_adjudication_type(self, adjudicator):
        """Each result should have correct adjudication_type."""
        seed_dice(42)
        context = AdjudicationContext(
            spell_name="Test", caster_name="C", caster_level=5, target_description="T"
        )

        assert adjudicator.adjudicate_charm_resistance(
            context, target_hit_dice=2
        ).adjudication_type == SpellAdjudicationType.CHARM_RESISTANCE

        seed_dice(42)
        assert adjudicator.adjudicate_protection_bypass(
            context, spell_level=3
        ).adjudication_type == SpellAdjudicationType.PROTECTION_BYPASS

        seed_dice(42)
        assert adjudicator.adjudicate_duration_extension(
            context, condition_to_extend="x"
        ).adjudication_type == SpellAdjudicationType.DURATION_EXTENSION

        seed_dice(42)
        assert adjudicator.adjudicate_reality_warp(
            context
        ).adjudication_type == SpellAdjudicationType.REALITY_WARP
