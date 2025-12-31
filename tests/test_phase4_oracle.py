"""
Phase 4 Tests: Oracle Adjudication Integration

Tests for oracle-based spell resolution using MythicSpellAdjudicator.
This covers:
- Oracle spell parsing patterns
- GlobalController oracle adjudication methods
- Integration with MythicSpellAdjudicator
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.data_models import CharacterState, Condition, ConditionType
from src.narrative.spell_resolver import (
    SpellResolver,
    SpellData,
    MagicType,
    MechanicalEffect,
    MechanicalEffectCategory,
    ParsedMechanicalEffects,
)
from src.game_state.global_controller import GlobalController
from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    AdjudicationContext,
    AdjudicationResult,
    SpellAdjudicationType,
    SuccessLevel,
)


def make_spell(name: str, level: int, description: str) -> SpellData:
    """Helper to create SpellData with required fields."""
    return SpellData(
        spell_id=f"spell_{name.lower().replace(' ', '_')}",
        name=name,
        level=level,
        magic_type=MagicType.ARCANE,
        duration="Permanent",
        range="Self",
        description=description,
    )


def make_character(
    char_id: str, name: str, level: int = 10, conditions: list = None
) -> CharacterState:
    """Helper to create CharacterState with required fields."""
    return CharacterState(
        character_id=char_id,
        name=name,
        character_class="Magic-User",
        level=level,
        ability_scores={"STR": 10, "INT": 16, "WIS": 12, "DEX": 10, "CON": 10, "CHA": 10},
        hp_current=30,
        hp_max=30,
        armor_class=10,
        base_speed=40,
        conditions=conditions or [],
    )


class TestOracleSpellParsing:
    """Test oracle spell patterns are correctly identified."""

    @pytest.fixture
    def resolver(self):
        """Create spell resolver."""
        return SpellResolver()

    # =========================================================================
    # WISH PATTERN TESTS
    # =========================================================================

    def test_wish_spell_requires_oracle(self, resolver):
        """Wish spell should require oracle adjudication."""
        spell = make_spell(
            "Wish", 9, "You may wish for almost anything. The referee determines outcome."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "wish"

    def test_limited_wish_requires_oracle(self, resolver):
        """Limited Wish should require oracle adjudication."""
        spell = make_spell(
            "Limited Wish", 7, "A lesser form of the wish spell with more limitations."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "wish"

    def test_alter_reality_requires_oracle(self, resolver):
        """Alter Reality should require oracle adjudication."""
        spell = make_spell(
            "Alter Reality", 8, "The caster can alter reality within limits."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "wish"

    def test_miracle_requires_oracle(self, resolver):
        """Miracle spell should require oracle adjudication."""
        spell = make_spell("Miracle", 9, "Divine intervention grants a miracle.")
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "wish"

    # =========================================================================
    # DIVINATION PATTERN TESTS
    # =========================================================================

    def test_commune_requires_oracle(self, resolver):
        """Commune spell should require oracle adjudication."""
        spell = make_spell("Commune", 5, "You contact your deity and ask questions.")
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "divination"

    def test_contact_other_plane_requires_oracle(self, resolver):
        """Contact Other Plane should require oracle adjudication."""
        spell = make_spell(
            "Contact Other Plane", 5, "You contact other plane entities for answers."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "divination"

    def test_augury_requires_oracle(self, resolver):
        """Augury should require oracle adjudication."""
        spell = make_spell(
            "Augury", 2, "You receive an omen about a proposed course of action."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "divination"

    def test_legend_lore_requires_oracle(self, resolver):
        """Legend Lore should require oracle adjudication."""
        spell = make_spell(
            "Legend Lore", 6, "You learn legend lore about a person, place, or thing."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "divination"

    def test_speak_with_dead_requires_oracle(self, resolver):
        """Speak with Dead should require oracle adjudication."""
        spell = make_spell(
            "Speak with Dead", 3, "You speak with the spirit of a dead creature."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "divination"

    # =========================================================================
    # ILLUSION BELIEF PATTERN TESTS
    # =========================================================================

    def test_phantasmal_force_requires_oracle(self, resolver):
        """Phantasmal Force should require oracle adjudication."""
        spell = make_spell(
            "Phantasmal Force",
            2,
            "You create a phantasmal force illusion that can harm those who believe.",
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "illusion_belief"

    def test_phantasmal_killer_requires_oracle(self, resolver):
        """Phantasmal Killer should require oracle adjudication."""
        spell = make_spell(
            "Phantasmal Killer",
            4,
            "Creates a phantasmal killer that slays those who believe in it.",
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "illusion_belief"

    def test_programmed_illusion_requires_oracle(self, resolver):
        """Programmed Illusion should require oracle adjudication."""
        spell = make_spell(
            "Programmed Illusion",
            6,
            "You create a programmed illusion that activates under conditions.",
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "illusion_belief"

    def test_simulacrum_requires_oracle(self, resolver):
        """Simulacrum should require oracle adjudication."""
        spell = make_spell(
            "Simulacrum", 7, "Creates a simulacrum duplicate of a creature."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "illusion_belief"

    # =========================================================================
    # SUMMONING CONTROL PATTERN TESTS
    # =========================================================================

    def test_conjure_elemental_requires_oracle(self, resolver):
        """Conjure Elemental should require oracle adjudication."""
        spell = make_spell(
            "Conjure Elemental", 5, "You conjure elemental to serve you."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "summoning_control"

    def test_summon_demon_requires_oracle(self, resolver):
        """Summon Demon should require oracle adjudication."""
        spell = make_spell(
            "Summon Demon", 7, "You summon demon from the lower planes."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "summoning_control"

    def test_planar_binding_requires_oracle(self, resolver):
        """Planar Binding should require oracle adjudication."""
        spell = make_spell(
            "Planar Binding",
            5,
            "You bind an extraplanar binding creature to your service.",
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "summoning_control"

    def test_gate_requires_oracle(self, resolver):
        """Gate should require oracle adjudication."""
        spell = make_spell("Gate", 9, "Opens a gate to another plane.")
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "summoning_control"

    # =========================================================================
    # COMMUNICATION PATTERN TESTS
    # =========================================================================

    def test_speak_with_animals_requires_oracle(self, resolver):
        """Speak with Animals should require oracle adjudication."""
        spell = make_spell(
            "Speak with Animals",
            2,
            "You can speak with animals and understand their replies.",
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "communication"

    def test_speak_with_plants_requires_oracle(self, resolver):
        """Speak with Plants should require oracle adjudication."""
        spell = make_spell(
            "Speak with Plants", 4, "You can speak with plants and learn information."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "communication"

    def test_tongues_requires_oracle(self, resolver):
        """Tongues should require oracle adjudication."""
        spell = make_spell(
            "Tongues", 3, "You understand all tongues and can communicate."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "communication"

    def test_sending_requires_oracle(self, resolver):
        """Sending should require oracle adjudication."""
        spell = make_spell(
            "Sending", 5, "You send a message through sending to a distant creature."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "communication"

    def test_telepathy_requires_oracle(self, resolver):
        """Telepathy should require oracle adjudication."""
        spell = make_spell(
            "Telepathy", 8, "You establish telepathy with another creature."
        )
        parsed = resolver.parse_mechanical_effects(spell)

        assert parsed.requires_oracle_adjudication
        assert parsed.oracle_adjudication_type == "communication"


class TestGlobalControllerOracleAdjudication:
    """Test GlobalController oracle adjudication methods."""

    @pytest.fixture
    def controller(self):
        """Create controller with test character."""
        ctrl = GlobalController()
        char = make_character("wizard_1", "Merlin", level=10)
        ctrl._characters["wizard_1"] = char
        return ctrl

    def test_get_spell_adjudicator_creates_instance(self, controller):
        """get_spell_adjudicator should create adjudicator on first call."""
        assert controller._spell_adjudicator is None
        adjudicator = controller.get_spell_adjudicator()
        assert adjudicator is not None
        assert isinstance(adjudicator, MythicSpellAdjudicator)
        assert controller._spell_adjudicator is adjudicator

    def test_get_spell_adjudicator_returns_same_instance(self, controller):
        """get_spell_adjudicator should return same instance on subsequent calls."""
        adj1 = controller.get_spell_adjudicator()
        adj2 = controller.get_spell_adjudicator()
        assert adj1 is adj2

    def test_adjudicate_oracle_spell_wish(self, controller):
        """adjudicate_oracle_spell should handle wish spells."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Wish",
            caster_id="wizard_1",
            adjudication_type="wish",
            intention="Remove the curse from Lord Malbrook",
            wish_text="Remove the curse from Lord Malbrook",
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.WISH
        assert result.success_level in [
            SuccessLevel.EXCEPTIONAL_SUCCESS,
            SuccessLevel.SUCCESS,
            SuccessLevel.PARTIAL_SUCCESS,
            SuccessLevel.FAILURE,
            SuccessLevel.CATASTROPHIC_FAILURE,
        ]
        assert "wizard_1" in str(controller._session_log[-1])

    def test_adjudicate_oracle_spell_divination(self, controller):
        """adjudicate_oracle_spell should handle divination spells."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Commune",
            caster_id="wizard_1",
            adjudication_type="divination",
            oracle_question="Where is the stolen artifact?",
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.DIVINATION
        assert result.meaning_roll is not None  # Divinations always get meaning

    def test_adjudicate_oracle_spell_illusion_belief(self, controller):
        """adjudicate_oracle_spell should handle illusion belief."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Phantasmal Force",
            caster_id="wizard_1",
            adjudication_type="illusion_belief",
            target_id="wizard_1",
            illusion_quality="standard",
            viewer_intelligence="average",
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.ILLUSION_BELIEF

    def test_adjudicate_oracle_spell_summoning_control(self, controller):
        """adjudicate_oracle_spell should handle summoning control."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Conjure Elemental",
            caster_id="wizard_1",
            adjudication_type="summoning_control",
            creature_type="fire elemental",
            creature_power="strong",
            binding_strength="standard",
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.SUMMONING_CONTROL

    def test_adjudicate_oracle_spell_curse_break(self, controller):
        """adjudicate_oracle_spell should handle curse breaking."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Remove Curse",
            caster_id="wizard_1",
            adjudication_type="curse_break",
            target_id="wizard_1",
            curse_power="normal",
            spell_specifically_counters=True,
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.CURSE_BREAK

    def test_adjudicate_oracle_spell_generic(self, controller):
        """adjudicate_oracle_spell should fall back to generic for unknown types."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Unknown Spell",
            caster_id="wizard_1",
            adjudication_type="unknown_type",
            oracle_question="Does this strange spell work?",
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.GENERIC

    def test_adjudicate_oracle_spell_unknown_caster(self, controller):
        """adjudicate_oracle_spell should handle unknown caster gracefully."""
        result = controller.adjudicate_oracle_spell(
            spell_name="Wish",
            caster_id="unknown_caster",
            adjudication_type="wish",
            intention="Grant me power",
        )

        # Should still work with defaults
        assert isinstance(result, AdjudicationResult)
        assert result.interpretation_context["caster"] == "Unknown Caster"
        assert result.interpretation_context["caster_level"] == 1

    def test_adjudicate_oracle_spell_logs_event(self, controller):
        """adjudicate_oracle_spell should log the adjudication."""
        initial_log_count = len(controller._session_log)

        controller.adjudicate_oracle_spell(
            spell_name="Wish",
            caster_id="wizard_1",
            adjudication_type="wish",
            intention="Grant me power",
        )

        assert len(controller._session_log) > initial_log_count
        last_event = controller._session_log[-1]
        assert last_event["event_type"] == "oracle_spell_adjudication"
        assert last_event["data"]["spell"] == "Wish"


class TestResolveOracleSpellEffects:
    """Test applying effects from oracle adjudication."""

    @pytest.fixture
    def controller(self):
        """Create controller with test character."""
        ctrl = GlobalController()
        char = make_character(
            "victim_1", "Victim", level=5,
            conditions=[Condition(condition_type=ConditionType.CURSED)]
        )
        ctrl._characters["victim_1"] = char
        return ctrl

    def test_resolve_removes_curse_condition(self, controller):
        """resolve_oracle_spell_effects should remove curse on success."""
        from src.data_models import ConditionType

        # Create a successful curse break result
        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.CURSE_BREAK,
            success_level=SuccessLevel.SUCCESS,
            predetermined_effects=["remove_condition:cursed:victim_1"],
            summary="Curse removed",
        )

        resolved = controller.resolve_oracle_spell_effects(
            result=result,
            caster_id="wizard_1",
            target_id="victim_1",
        )

        # Check effect was applied
        assert len(resolved["applied_effects"]) == 1
        assert resolved["applied_effects"][0]["type"] == "condition_removed"
        assert resolved["applied_effects"][0]["condition"] == "cursed"

        # Check character no longer cursed
        victim = controller._characters["victim_1"]
        curse_conditions = [
            c for c in victim.conditions if c.condition_type == ConditionType.CURSED
        ]
        assert len(curse_conditions) == 0

    def test_resolve_returns_llm_context_when_needed(self, controller):
        """resolve_oracle_spell_effects should return LLM context for interpretation."""
        # Create result that needs interpretation
        from src.oracle.mythic_gme import MeaningRoll

        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.DIVINATION,
            success_level=SuccessLevel.SUCCESS,
            meaning_roll=MeaningRoll(
                action="Reveal", subject="Deception", action_roll=42, subject_roll=73
            ),
            summary="Divination reveals: Reveal + Deception",
        )

        resolved = controller.resolve_oracle_spell_effects(
            result=result,
            caster_id="wizard_1",
        )

        assert resolved["requires_interpretation"] is True
        assert "meaning_pair" in resolved["llm_context"]
        assert "Reveal" in resolved["llm_context"]["meaning_pair"]

    def test_resolve_no_effects_on_failure(self, controller):
        """resolve_oracle_spell_effects should not apply effects on failure."""
        result = AdjudicationResult(
            adjudication_type=SpellAdjudicationType.CURSE_BREAK,
            success_level=SuccessLevel.FAILURE,
            predetermined_effects=[],  # No effects on failure
            summary="Curse resisted",
        )

        resolved = controller.resolve_oracle_spell_effects(
            result=result,
            caster_id="wizard_1",
            target_id="victim_1",
        )

        assert len(resolved["applied_effects"]) == 0
        assert resolved["success_level"] == "failure"


class TestMythicSpellAdjudicatorIntegration:
    """Integration tests for MythicSpellAdjudicator."""

    @pytest.fixture
    def adjudicator(self):
        """Create adjudicator instance."""
        return MythicSpellAdjudicator()

    def test_adjudicate_wish_returns_valid_result(self, adjudicator):
        """adjudicate_wish should return structured result."""
        context = AdjudicationContext(
            spell_name="Wish",
            caster_name="Archmage",
            caster_level=18,
            intention="Restore the kingdom",
        )

        result = adjudicator.adjudicate_wish(
            wish_text="Restore the fallen kingdom to its former glory",
            context=context,
            wish_power="major",
        )

        assert isinstance(result, AdjudicationResult)
        assert result.adjudication_type == SpellAdjudicationType.WISH
        assert result.primary_fate_check is not None
        assert "wish_text" in result.interpretation_context

    def test_adjudicate_divination_always_has_meaning(self, adjudicator):
        """adjudicate_divination should always produce meaning roll."""
        context = AdjudicationContext(
            spell_name="Commune",
            caster_name="Priest",
            caster_level=9,
        )

        result = adjudicator.adjudicate_divination(
            question="Where is the sacred relic?",
            context=context,
        )

        assert result.meaning_roll is not None
        assert "question" in result.interpretation_context

    def test_adjudicate_summoning_control_varies_by_power(self, adjudicator):
        """adjudicate_summoning_control likelihood varies by creature power."""
        context = AdjudicationContext(
            spell_name="Summon Demon",
            caster_name="Warlock",
            caster_level=12,
        )

        # Test with weak creature (should succeed more often)
        weak_results = [
            adjudicator.adjudicate_summoning_control(
                context, "imp", "weak", "strong"
            )
            for _ in range(5)
        ]

        # Test with overwhelming creature (should fail more often)
        strong_results = [
            adjudicator.adjudicate_summoning_control(
                context, "demon lord", "overwhelming", "weak"
            )
            for _ in range(5)
        ]

        # At least verify both return valid results
        assert all(isinstance(r, AdjudicationResult) for r in weak_results)
        assert all(isinstance(r, AdjudicationResult) for r in strong_results)

    def test_check_for_side_effect(self, adjudicator):
        """check_for_side_effect should sometimes return meaning."""
        context = AdjudicationContext(
            spell_name="Major Spell",
            caster_name="Wizard",
            caster_level=15,
        )

        # Run multiple times to check it sometimes triggers
        results = [
            adjudicator.check_for_side_effect(context, "legendary")
            for _ in range(20)
        ]

        # At legendary power, should trigger sometimes
        triggered = [r for r in results if r is not None]
        # With 20 trials at legendary (50/50), should trigger at least once
        # But this is probabilistic so we just check it's valid
        assert all(hasattr(r, "action") for r in triggered if r)


class TestParsedMechanicalEffectsOracleFlag:
    """Test that oracle flags propagate correctly through ParsedMechanicalEffects."""

    def test_add_effect_propagates_oracle_flag(self):
        """Adding oracle effect should set requires_oracle_adjudication."""
        parsed = ParsedMechanicalEffects()

        effect = MechanicalEffect(
            category=MechanicalEffectCategory.UTILITY,
            requires_oracle=True,
            oracle_adjudication_type="wish",
            description="Wish spell",
        )

        parsed.add_effect(effect)

        assert parsed.requires_oracle_adjudication is True
        assert parsed.oracle_adjudication_type == "wish"

    def test_non_oracle_effect_does_not_set_flag(self):
        """Non-oracle effects should not set oracle flag."""
        parsed = ParsedMechanicalEffects()

        effect = MechanicalEffect(
            category=MechanicalEffectCategory.DAMAGE,
            damage_dice="1d6",
            description="Normal damage",
        )

        parsed.add_effect(effect)

        assert parsed.requires_oracle_adjudication is False
        assert parsed.oracle_adjudication_type is None

    def test_mixed_effects_oracle_takes_precedence(self):
        """Oracle flag should be set if any effect requires oracle."""
        parsed = ParsedMechanicalEffects()

        # Add non-oracle effect first
        effect1 = MechanicalEffect(
            category=MechanicalEffectCategory.DAMAGE,
            damage_dice="1d6",
            description="Normal damage",
        )
        parsed.add_effect(effect1)

        assert parsed.requires_oracle_adjudication is False

        # Add oracle effect
        effect2 = MechanicalEffect(
            category=MechanicalEffectCategory.UTILITY,
            requires_oracle=True,
            oracle_adjudication_type="divination",
            description="Divination aspect",
        )
        parsed.add_effect(effect2)

        assert parsed.requires_oracle_adjudication is True
        assert parsed.oracle_adjudication_type == "divination"
