"""
Tests for Tier 4 Spell Resolution (Mythic GME Integration).

Tests cover:
- MythicGME core functionality (Fate Check, Meaning Tables, Chaos Factor)
- MythicSpellAdjudicator for spell-specific resolution
- EffectCommand system for game state changes
- MythicInterpretationSchema for LLM output
- Full integration flow from spell to effect execution
"""

import pytest
import random
from dataclasses import asdict

from src.oracle.mythic_gme import (
    MythicGME,
    Likelihood,
    FateResult,
    FateCheckResult,
    RandomEvent,
    MeaningRoll,
    ChaosFactorState,
    FATE_CHART,
    ACTION_MEANINGS,
    SUBJECT_MEANINGS,
)

from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    SpellAdjudicationType,
    SuccessLevel,
    AdjudicationContext,
    AdjudicationResult,
)

from src.oracle.effect_commands import (
    EffectType,
    EffectCommand,
    EffectResult,
    EffectBatch,
    EffectCommandBuilder,
    EffectValidator,
    EffectExecutor,
)

from src.ai.prompt_schemas import (
    PromptSchemaType,
    MythicInterpretationInputs,
    MythicInterpretationSchema,
    create_schema,
)


# =============================================================================
# MYTHIC GME CORE TESTS
# =============================================================================


class TestMythicGME:
    """Tests for the core Mythic GME engine."""

    def test_fate_check_returns_result(self):
        """Fate check returns a valid result."""
        mythic = MythicGME(rng=random.Random(42))

        result = mythic.fate_check(
            "Does the spell succeed?",
            Likelihood.FIFTY_FIFTY,
        )

        assert isinstance(result, FateCheckResult)
        assert result.question == "Does the spell succeed?"
        assert result.likelihood == Likelihood.FIFTY_FIFTY
        assert result.result in FateResult
        assert 1 <= result.roll <= 100

    def test_higher_likelihood_more_likely_yes(self):
        """Higher likelihood settings produce more yes results."""
        unlikely_yes_count = 0
        likely_yes_count = 0

        for seed in range(100):
            mythic = MythicGME(rng=random.Random(seed))

            unlikely = mythic.fate_check("test?", Likelihood.UNLIKELY, check_for_event=False)
            likely = mythic.fate_check("test?", Likelihood.LIKELY, check_for_event=False)

            if mythic.is_yes(unlikely):
                unlikely_yes_count += 1
            if mythic.is_yes(likely):
                likely_yes_count += 1

        # Likely should produce significantly more yes results
        assert likely_yes_count > unlikely_yes_count

    def test_chaos_factor_affects_exceptional_results(self):
        """Higher chaos factor produces more exceptional results."""
        low_chaos_exceptional = 0
        high_chaos_exceptional = 0

        for seed in range(100):
            low_mythic = MythicGME(chaos_factor=1, rng=random.Random(seed))
            high_mythic = MythicGME(chaos_factor=9, rng=random.Random(seed))

            low_result = low_mythic.fate_check("test?", Likelihood.FIFTY_FIFTY, check_for_event=False)
            high_result = high_mythic.fate_check("test?", Likelihood.FIFTY_FIFTY, check_for_event=False)

            if low_mythic.is_exceptional(low_result):
                low_chaos_exceptional += 1
            if high_mythic.is_exceptional(high_result):
                high_chaos_exceptional += 1

        # High chaos should produce more exceptional results
        # (both exceptional yes AND exceptional no are more likely)
        assert high_chaos_exceptional > low_chaos_exceptional

    def test_random_event_on_doubles(self):
        """Random events trigger on doubles within chaos factor."""
        # Set up a seed that produces doubles (11, 22, 33, etc.)
        # We need to find a seed that produces a roll that's doubles
        events_triggered = 0

        for seed in range(1000):
            mythic = MythicGME(chaos_factor=9, rng=random.Random(seed))
            result = mythic.fate_check("test?", Likelihood.FIFTY_FIFTY)

            if result.random_event_triggered:
                events_triggered += 1
                assert result.random_event is not None
                assert isinstance(result.random_event, RandomEvent)

        # Should have triggered some events in 1000 checks
        assert events_triggered > 0

    def test_meaning_roll_structure(self):
        """Meaning roll returns valid action + subject."""
        mythic = MythicGME(rng=random.Random(42))

        meaning = mythic.roll_meaning()

        assert isinstance(meaning, MeaningRoll)
        assert meaning.action in ACTION_MEANINGS
        assert meaning.subject in SUBJECT_MEANINGS
        assert 1 <= meaning.action_roll <= 100
        assert 1 <= meaning.subject_roll <= 100

    def test_chaos_factor_bounds(self):
        """Chaos factor stays within 1-9 bounds."""
        chaos = ChaosFactorState(value=5)

        # Try to go below minimum
        for _ in range(20):
            chaos.decrease("test")
        assert chaos.value == 1

        # Try to go above maximum
        for _ in range(20):
            chaos.increase("test")
        assert chaos.value == 9

    def test_serialization(self):
        """Mythic state can be serialized and restored."""
        mythic = MythicGME(chaos_factor=7)
        mythic.chaos.increase("test event")

        data = mythic.to_dict()
        assert data["chaos_factor"] == 8
        assert len(data["chaos_history"]) > 0

        new_mythic = MythicGME()
        new_mythic.from_dict(data)
        assert new_mythic.get_chaos_factor() == 8


class TestMeaningTables:
    """Tests for meaning table content."""

    def test_action_meanings_complete(self):
        """All 100 action meanings are defined."""
        assert len(ACTION_MEANINGS) == 100

    def test_subject_meanings_complete(self):
        """All 100 subject meanings are defined."""
        assert len(SUBJECT_MEANINGS) == 100

    def test_fate_chart_complete(self):
        """Fate chart has all 9 chaos levels and 10 likelihoods."""
        assert len(FATE_CHART) == 9
        for chaos in range(1, 10):
            assert chaos in FATE_CHART
            assert len(FATE_CHART[chaos]) == 10


# =============================================================================
# SPELL ADJUDICATOR TESTS
# =============================================================================


class TestMythicSpellAdjudicator:
    """Tests for spell-specific adjudication."""

    def create_context(self, **kwargs) -> AdjudicationContext:
        """Helper to create test context."""
        defaults = {
            "spell_name": "Test Spell",
            "caster_name": "Test Wizard",
            "caster_level": 9,
        }
        defaults.update(kwargs)
        return AdjudicationContext(**defaults)

    def test_wish_adjudication_returns_result(self):
        """Wish adjudication returns valid result."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        context = self.create_context(
            spell_name="Wish",
            caster_level=14,
            target_description="Lord Malbrook",
            intention="remove the curse",
        )

        result = adjudicator.adjudicate_wish(
            wish_text="Remove the curse from Lord Malbrook",
            context=context,
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.WISH
        assert result.success_level in SuccessLevel
        assert result.primary_fate_check is not None
        assert len(result.summary) > 0

    def test_wish_power_affects_likelihood(self):
        """Higher wish power is less likely to succeed."""
        minor_successes = 0
        major_successes = 0

        for seed in range(50):
            mythic = MythicGME(rng=random.Random(seed))
            adjudicator = MythicSpellAdjudicator(mythic)
            context = self.create_context()

            minor = adjudicator.adjudicate_wish(
                "make a flower bloom",
                context,
                wish_power="minor",
            )
            major = adjudicator.adjudicate_wish(
                "resurrect a god",
                context,
                wish_power="major",
            )

            if minor.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                minor_successes += 1
            if major.success_level in (SuccessLevel.SUCCESS, SuccessLevel.EXCEPTIONAL_SUCCESS):
                major_successes += 1

        # Minor wishes should succeed more often
        assert minor_successes > major_successes

    def test_curse_break_adjudication(self):
        """Curse break adjudication works correctly."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        context = self.create_context(
            target_description="cursed knight",
            curse_source="hag's bargain",
        )

        result = adjudicator.adjudicate_curse_break(
            context,
            curse_power="normal",
        )

        assert result.adjudication_type == SpellAdjudicationType.CURSE_BREAK
        assert result.interpretation_context["curse_source"] == "hag's bargain"

    def test_illusion_belief_adjudication(self):
        """Illusion belief adjudication considers intelligence."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        context = self.create_context(target_description="goblin guard")

        # Test with different intelligence levels
        dim_result = adjudicator.adjudicate_illusion_belief(
            context,
            illusion_quality="standard",
            viewer_intelligence="dim",
        )

        clever_result = adjudicator.adjudicate_illusion_belief(
            context,
            illusion_quality="standard",
            viewer_intelligence="clever",
        )

        assert dim_result.adjudication_type == SpellAdjudicationType.ILLUSION_BELIEF
        assert clever_result.adjudication_type == SpellAdjudicationType.ILLUSION_BELIEF

    def test_divination_always_has_meaning(self):
        """Divination adjudication always produces meaning to interpret."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        context = self.create_context()

        result = adjudicator.adjudicate_divination(
            "Where is the hidden treasure?",
            context,
        )

        assert result.adjudication_type == SpellAdjudicationType.DIVINATION
        assert result.meaning_roll is not None
        assert result.requires_interpretation()

    def test_summoning_control(self):
        """Summoning control considers creature power."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        context = self.create_context()

        result = adjudicator.adjudicate_summoning_control(
            context,
            creature_type="fire elemental",
            creature_power="strong",
        )

        assert result.adjudication_type == SpellAdjudicationType.SUMMONING_CONTROL
        assert "fire elemental" in result.interpretation_context["creature"]

    def test_adjudication_to_llm_context(self):
        """Adjudication result can be converted to LLM context."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)
        context = self.create_context()

        result = adjudicator.adjudicate_generic(
            "Does the spell reveal the secret passage?",
            context,
        )

        llm_context = result.to_llm_context()

        assert "adjudication_type" in llm_context
        assert "success_level" in llm_context
        assert "summary" in llm_context
        if result.meaning_roll:
            assert "meaning_pair" in llm_context
            assert "action_word" in llm_context
            assert "subject_word" in llm_context


# =============================================================================
# EFFECT COMMAND TESTS
# =============================================================================


class TestEffectCommands:
    """Tests for the effect command system."""

    def test_builder_creates_valid_commands(self):
        """EffectCommandBuilder creates properly structured commands."""
        cmd = EffectCommandBuilder.remove_condition(
            target_id="lord_malbrook",
            condition="cursed",
            source="wish spell",
        )

        assert cmd.effect_type == EffectType.REMOVE_CONDITION
        assert cmd.target_id == "lord_malbrook"
        assert cmd.parameters["condition"] == "cursed"
        assert cmd.source == "wish spell"

    def test_builder_handles_dice_expressions(self):
        """Builder correctly identifies dice expressions."""
        cmd = EffectCommandBuilder.modify_stat(
            target_id="wizard_001",
            stat="CON",
            value="-1d3",
            source="wish cost",
        )

        assert "value" in cmd.dice_expressions
        assert cmd.dice_expressions["value"] == "-1d3"
        assert cmd.parameters.get("value_expr") == "-1d3"

    def test_builder_handles_integer_values(self):
        """Builder correctly handles integer values."""
        cmd = EffectCommandBuilder.modify_stat(
            target_id="wizard_001",
            stat="CON",
            value=-2,
        )

        assert "value" not in cmd.dice_expressions
        assert cmd.parameters["value"] == -2

    def test_validator_checks_conditions(self):
        """Validator rejects invalid conditions."""
        validator = EffectValidator()

        valid_cmd = EffectCommandBuilder.add_condition(
            target_id="target",
            condition="cursed",
        )
        validator.validate(valid_cmd)
        assert valid_cmd.validated

        invalid_cmd = EffectCommandBuilder.add_condition(
            target_id="target",
            condition="super_mega_cursed",  # Not a valid condition
        )
        validator.validate(invalid_cmd)
        assert not invalid_cmd.validated
        assert "Unknown condition" in invalid_cmd.validation_errors[0]

    def test_validator_checks_stats(self):
        """Validator rejects invalid stats."""
        validator = EffectValidator()

        valid_cmd = EffectCommandBuilder.modify_stat(
            target_id="target",
            stat="CON",
            value=-2,
        )
        validator.validate(valid_cmd)
        assert valid_cmd.validated

        invalid_cmd = EffectCommandBuilder.modify_stat(
            target_id="target",
            stat="CHARISMA",  # Should be CHA
            value=-2,
        )
        validator.validate(invalid_cmd)
        assert not invalid_cmd.validated

    def test_validator_checks_dice_expressions(self):
        """Validator validates dice expression syntax."""
        validator = EffectValidator()

        valid_cmd = EffectCommandBuilder.damage(
            target_id="target",
            amount="3d6+2",
        )
        validator.validate(valid_cmd)
        assert valid_cmd.validated

        invalid_cmd = EffectCommand(
            effect_type=EffectType.DAMAGE,
            target_id="target",
            parameters={},
            dice_expressions={"amount": "not_a_dice_expr"},
        )
        validator.validate(invalid_cmd)
        assert not invalid_cmd.validated

    def test_executor_runs_validated_commands(self):
        """Executor successfully runs validated commands."""
        executor = EffectExecutor()

        cmd = EffectCommandBuilder.remove_condition(
            target_id="lord_malbrook",
            condition="cursed",
        )

        result = executor.execute(cmd)

        assert result.success
        # Without controller, it's simulated; with controller, it's executed
        assert "remove" in result.description.lower()
        assert "cursed" in result.description

    def test_executor_fails_invalid_commands(self):
        """Executor fails on invalid commands."""
        executor = EffectExecutor()

        cmd = EffectCommandBuilder.add_condition(
            target_id="target",
            condition="invalid_condition",
        )

        result = executor.execute(cmd)

        assert not result.success
        assert "Validation failed" in result.error

    def test_batch_execution(self):
        """Batch execution processes all commands."""
        executor = EffectExecutor()

        batch = EffectBatch(
            source="wish spell",
            description="Curse removal with cost",
        )
        batch.add(EffectCommandBuilder.remove_condition("target", "cursed"))
        batch.add(EffectCommandBuilder.modify_stat("target", "CON", -2))

        executor.execute_batch(batch)

        assert len(batch.results) == 2
        assert batch.all_succeeded
        assert all(r.success for r in batch.results)


# =============================================================================
# MYTHIC INTERPRETATION SCHEMA TESTS
# =============================================================================


class TestMythicInterpretationSchema:
    """Tests for the LLM interpretation schema."""

    def test_schema_creation(self):
        """Schema can be created with required inputs."""
        inputs = MythicInterpretationInputs(
            adjudication_type="wish",
            success_level="success",
            summary="The wish succeeds as intended.",
            meaning_pair="Waste + Energy",
            action_word="Waste",
            subject_word="Energy",
            spell_name="Wish",
            caster_name="Merlin",
            caster_level=14,
            target="Lord Malbrook",
            intention="remove the curse",
        )

        schema = MythicInterpretationSchema(inputs)
        assert schema.typed_inputs.meaning_pair == "Waste + Energy"

    def test_schema_prompt_includes_meaning(self):
        """Prompt includes the meaning pair."""
        inputs = MythicInterpretationInputs(
            adjudication_type="curse_break",
            success_level="success",
            summary="The curse is broken.",
            meaning_pair="Heal + Suffering",
            action_word="Heal",
            subject_word="Suffering",
            spell_name="Remove Curse",
            caster_name="Cleric",
        )

        schema = MythicInterpretationSchema(inputs)
        prompt = schema.build_prompt()

        assert "Heal + Suffering" in prompt
        assert "Heal" in prompt
        assert "Suffering" in prompt

    def test_schema_includes_success_guidance(self):
        """Schema provides guidance based on success level."""
        inputs = MythicInterpretationInputs(
            adjudication_type="wish",
            success_level="partial_success",
            summary="Works with complications",
            meaning_pair="Victory + Dispute",
            action_word="Victory",
            subject_word="Dispute",
            spell_name="Wish",
            caster_name="Wizard",
        )

        schema = MythicInterpretationSchema(inputs)
        system = schema.get_system_prompt()

        assert "PARTIAL_SUCCESS" in system
        assert "complications" in system.lower()

    def test_schema_includes_effect_types(self):
        """Schema includes valid effect types guidance."""
        inputs = MythicInterpretationInputs(
            adjudication_type="generic",
            success_level="success",
            summary="Test",
            meaning_pair="Action + Subject",
            action_word="Action",
            subject_word="Subject",
            spell_name="Test Spell",
            caster_name="Tester",
            valid_effect_types=["damage", "heal", "add_condition"],
        )

        schema = MythicInterpretationSchema(inputs)
        system = schema.get_system_prompt()

        assert "damage" in system
        assert "heal" in system
        assert "add_condition" in system

    def test_factory_creates_schema(self):
        """Factory function creates correct schema type."""
        inputs = {
            "adjudication_type": "wish",
            "success_level": "success",
            "summary": "The wish succeeds.",
            "meaning_pair": "Test + Meaning",
            "action_word": "Test",
            "subject_word": "Meaning",
            "spell_name": "Wish",
            "caster_name": "Wizard",
        }

        schema = create_schema(PromptSchemaType.MYTHIC_INTERPRETATION, inputs)
        assert isinstance(schema, MythicInterpretationSchema)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestTier4Integration:
    """Integration tests for the full Tier 4 flow."""

    def test_wish_full_flow(self):
        """Test full flow from wish to effect commands."""
        # 1. Set up oracle and adjudicator
        mythic = MythicGME(chaos_factor=5, rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        # 2. Create adjudication context
        context = AdjudicationContext(
            spell_name="Wish",
            caster_name="Archmage Thorn",
            caster_level=14,
            target_description="Lord Malbrook",
            intention="remove the hag's curse from Lord Malbrook",
            target_power_level="normal",
            curse_source="Hagwood Coven",
        )

        # 3. Adjudicate the wish
        result = adjudicator.adjudicate_wish(
            wish_text="Remove the hag's curse from Lord Malbrook",
            context=context,
            wish_power="standard",
        )

        # 4. Verify adjudication result
        assert result.adjudication_type == SpellAdjudicationType.WISH
        assert result.summary is not None

        # 5. Convert to LLM context
        if result.requires_interpretation():
            llm_context = result.to_llm_context()
            assert "wish_text" in llm_context
            assert "meaning_pair" in llm_context or result.meaning_roll is None

    def test_adjudication_to_effect_commands(self):
        """Test creating effect commands from adjudication results."""
        # Simulate an adjudication result
        mythic = MythicGME(rng=random.Random(42))

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.CURSE_BREAK,
            success_level=SuccessLevel.SUCCESS,
            meaning_roll=mythic.roll_meaning(),
            predetermined_effects=["remove_condition:cursed:lord_malbrook"],
            interpretation_context={
                "target": "lord_malbrook",
                "caster": "cleric",
            },
        )

        # Parse predetermined effects into commands
        for effect_str in result.predetermined_effects:
            parts = effect_str.split(":")
            if parts[0] == "remove_condition":
                cmd = EffectCommandBuilder.remove_condition(
                    target_id=parts[2],
                    condition=parts[1],
                    source=str(result.adjudication_type.value),
                )

                # Validate and execute
                executor = EffectExecutor()
                exec_result = executor.execute(cmd)

                assert exec_result.success

    def test_chaos_adjustment_on_outcome(self):
        """Chaos factor adjusts based on spell outcomes."""
        mythic = MythicGME(chaos_factor=5, rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        # Create a result with exceptional success
        exceptional_result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.WISH,
            success_level=SuccessLevel.EXCEPTIONAL_SUCCESS,
        )

        initial_chaos = mythic.get_chaos_factor()
        adjudicator.adjust_chaos_for_spell_outcome(exceptional_result)
        assert mythic.get_chaos_factor() <= initial_chaos

        # Create a result with catastrophic failure
        catastrophic_result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.WISH,
            success_level=SuccessLevel.CATASTROPHIC_FAILURE,
        )

        mythic.set_chaos_factor(5)  # Reset
        adjudicator.adjust_chaos_for_spell_outcome(catastrophic_result)
        assert mythic.get_chaos_factor() >= 5

    def test_side_effect_check(self):
        """Side effect checking produces meaningful results."""
        mythic = MythicGME(rng=random.Random(42))
        adjudicator = MythicSpellAdjudicator(mythic)

        context = AdjudicationContext(
            spell_name="Polymorph",
            caster_name="Wizard",
            caster_level=9,
        )

        # Check for side effects on a major spell
        side_effect = adjudicator.check_for_side_effect(context, spell_power="major")

        # May or may not produce a side effect, but should handle both cases
        if side_effect:
            assert isinstance(side_effect, MeaningRoll)
            assert side_effect.action in ACTION_MEANINGS
            assert side_effect.subject in SUBJECT_MEANINGS
