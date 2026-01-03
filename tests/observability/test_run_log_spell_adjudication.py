"""
Tests for RunLog observability of spell adjudication events.

Phase 9.1: Verify that all adjudication types produce RunLog events
with proper structure: type, inputs, rolls, outcome, effects applied.
"""

import pytest

from src.data_models import DiceRoller
from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    AdjudicationContext,
    SpellAdjudicationType,
)
from src.observability.run_log import (
    get_run_log,
    reset_run_log,
    EventType,
    SpellAdjudicationEvent,
)


@pytest.fixture(autouse=True)
def clean_run_log():
    """Reset RunLog before and after each test."""
    reset_run_log()
    DiceRoller.clear_roll_log()
    yield
    reset_run_log()
    DiceRoller.clear_roll_log()


@pytest.fixture
def adjudicator():
    """Create a fresh adjudicator for each test."""
    return MythicSpellAdjudicator()


def seed_dice(seed: int) -> None:
    """Helper to seed dice."""
    DiceRoller.set_seed(seed)


# =============================================================================
# CHARM RESISTANCE LOGGING TESTS
# =============================================================================


class TestCharmResistanceRunLog:
    """Test RunLog events for charm resistance adjudication."""

    def test_charm_resistance_logs_spell_adjudication_event(self, adjudicator):
        """Charm resistance should log a spell adjudication event."""
        seed_dice(42)
        run_log = get_run_log()
        initial_count = len(run_log.get_spell_adjudications())

        context = AdjudicationContext(
            spell_name="Charm Person",
            caster_name="Evil Wizard",
            caster_level=5,
            target_description="Town Guard",
        )

        adjudicator.adjudicate_charm_resistance(
            context, target_hit_dice=2, charm_strength="standard"
        )

        events = run_log.get_spell_adjudications()
        assert len(events) > initial_count

        # Check the logged event
        event = events[-1]
        assert event.adjudication_type == SpellAdjudicationType.CHARM_RESISTANCE.value
        assert event.spell_name == "Charm Person"
        assert event.caster_id == "Evil Wizard"
        assert event.success_level != ""

    def test_charm_resistance_logs_oracle_fate_check(self, adjudicator):
        """Charm resistance should also log the underlying oracle fate check."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Charm Person",
            caster_name="Wizard",
            caster_level=5,
            target_description="Guard",
        )

        adjudicator.adjudicate_charm_resistance(context, target_hit_dice=2)

        oracle_events = run_log.get_oracle_events()
        assert len(oracle_events) > 0

        # Should have a fate check for "does target resist"
        fate_checks = [e for e in oracle_events if e.oracle_type == "fate_check"]
        assert len(fate_checks) > 0
        assert "resist" in fate_checks[0].question.lower()


# =============================================================================
# PROTECTION BYPASS LOGGING TESTS
# =============================================================================


class TestProtectionBypassRunLog:
    """Test RunLog events for protection bypass adjudication."""

    def test_protection_bypass_logs_event(self, adjudicator):
        """Protection bypass should log a spell adjudication event."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Dispel Magic",
            caster_name="Archmage",
            caster_level=12,
            target_description="Warded Door",
        )

        adjudicator.adjudicate_protection_bypass(
            context, protection_strength="standard", spell_level=3
        )

        events = run_log.get_spell_adjudications()
        assert len(events) > 0

        event = events[-1]
        assert event.adjudication_type == SpellAdjudicationType.PROTECTION_BYPASS.value
        assert event.spell_name == "Dispel Magic"

    def test_protection_bypass_logs_effects_list(self, adjudicator):
        """Protection bypass should log effects when bypass succeeds."""
        run_log = get_run_log()

        # Find seed that produces success
        for seed in range(100):
            seed_dice(seed)
            reset_run_log()

            context = AdjudicationContext(
                spell_name="Dispel Magic",
                caster_name="Archmage",
                caster_level=15,
                target_description="Minor Ward",
            )

            result = adjudicator.adjudicate_protection_bypass(
                context, protection_strength="minor", spell_level=6
            )

            if len(result.predetermined_effects) > 0:
                events = run_log.get_spell_adjudications()
                assert len(events) > 0
                event = events[-1]
                # Effects should be logged
                assert len(event.effects_executed) > 0
                return

        pytest.fail("Could not find seed with effects")


# =============================================================================
# DURATION EXTENSION LOGGING TESTS
# =============================================================================


class TestDurationExtensionRunLog:
    """Test RunLog events for duration extension adjudication."""

    def test_duration_extension_logs_event(self, adjudicator):
        """Duration extension should log a spell adjudication event."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Extend Duration",
            caster_name="Chronomancer",
            caster_level=9,
            target_description="Ally",
        )

        adjudicator.adjudicate_duration_extension(
            context, condition_to_extend="haste", original_duration_turns=10
        )

        events = run_log.get_spell_adjudications()
        assert len(events) > 0

        event = events[-1]
        assert event.adjudication_type == SpellAdjudicationType.DURATION_EXTENSION.value
        assert event.spell_name == "Extend Duration"

    def test_duration_extension_logs_summary_with_roll(self, adjudicator):
        """Duration extension log should include roll information in summary."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Extend",
            caster_name="Wizard",
            caster_level=10,
            target_description="Target",
        )

        adjudicator.adjudicate_duration_extension(
            context, condition_to_extend="invisible"
        )

        events = run_log.get_spell_adjudications()
        event = events[-1]

        # Summary should contain roll info
        assert "Roll:" in event.summary
        assert "Likelihood:" in event.summary


# =============================================================================
# REALITY WARP LOGGING TESTS
# =============================================================================


class TestRealityWarpRunLog:
    """Test RunLog events for reality warp adjudication."""

    def test_reality_warp_logs_event(self, adjudicator):
        """Reality warp should log a spell adjudication event."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Polymorph",
            caster_name="Transmuter",
            caster_level=9,
            target_description="Goblin",
        )

        adjudicator.adjudicate_reality_warp(context, warp_intensity="standard")

        events = run_log.get_spell_adjudications()
        assert len(events) > 0

        event = events[-1]
        assert event.adjudication_type == SpellAdjudicationType.REALITY_WARP.value
        assert event.spell_name == "Polymorph"

    def test_reality_warp_logs_multiple_oracle_events(self, adjudicator):
        """Reality warp uses multiple fate checks which should all be logged."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Warp Reality",
            caster_name="Wizard",
            caster_level=10,
            target_description="Target",
        )

        adjudicator.adjudicate_reality_warp(context, warp_intensity="major")

        oracle_events = run_log.get_oracle_events()

        # Should have at least 2 fate checks (success + backlash)
        fate_checks = [e for e in oracle_events if e.oracle_type == "fate_check"]
        assert len(fate_checks) >= 2

    def test_reality_warp_logs_complication_when_backlash(self, adjudicator):
        """Reality warp with backlash should log has_complication."""
        run_log = get_run_log()

        # Find seed with backlash
        for seed in range(200):
            seed_dice(seed)
            reset_run_log()

            context = AdjudicationContext(
                spell_name="Dangerous Warp",
                caster_name="Wizard",
                caster_level=5,
                target_description="Target",
            )

            result = adjudicator.adjudicate_reality_warp(context, warp_intensity="legendary")

            if result.has_complication:
                events = run_log.get_spell_adjudications()
                assert len(events) > 0
                event = events[-1]
                assert event.has_complication is True
                return

        pytest.fail("Could not find seed with backlash")


# =============================================================================
# CROSS-TYPE LOGGING TESTS
# =============================================================================


class TestAdjudicationLoggingConsistency:
    """Test consistent logging across all adjudication types."""

    def test_all_types_log_to_runlog(self, adjudicator):
        """All adjudication types should produce RunLog events."""
        seed_dice(42)
        run_log = get_run_log()
        reset_run_log()

        context = AdjudicationContext(
            spell_name="Test Spell",
            caster_name="Test Caster",
            caster_level=7,
            target_description="Test Target",
        )

        # Run all adjudication types
        adjudicator.adjudicate_charm_resistance(context, target_hit_dice=3)

        seed_dice(43)
        adjudicator.adjudicate_protection_bypass(context, spell_level=3)

        seed_dice(44)
        adjudicator.adjudicate_duration_extension(context, condition_to_extend="x")

        seed_dice(45)
        adjudicator.adjudicate_reality_warp(context)

        events = run_log.get_spell_adjudications()

        # Should have events for all 4 types
        assert len(events) >= 4

        types_found = {e.adjudication_type for e in events}
        assert SpellAdjudicationType.CHARM_RESISTANCE.value in types_found
        assert SpellAdjudicationType.PROTECTION_BYPASS.value in types_found
        assert SpellAdjudicationType.DURATION_EXTENSION.value in types_found
        assert SpellAdjudicationType.REALITY_WARP.value in types_found

    def test_event_sequence_numbers_increase(self, adjudicator):
        """RunLog sequence numbers should monotonically increase."""
        seed_dice(42)
        run_log = get_run_log()
        reset_run_log()

        context = AdjudicationContext(
            spell_name="Test",
            caster_name="Caster",
            caster_level=5,
            target_description="Target",
        )

        for i in range(5):
            seed_dice(i * 100)
            adjudicator.adjudicate_charm_resistance(context, target_hit_dice=2)

        events = run_log.get_events()
        sequence_numbers = [e.sequence_number for e in events]

        # Should be monotonically increasing
        for i in range(1, len(sequence_numbers)):
            assert sequence_numbers[i] > sequence_numbers[i-1]

    def test_all_events_have_event_type(self, adjudicator):
        """All logged events should have proper event_type."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Test",
            caster_name="Caster",
            caster_level=5,
            target_description="Target",
        )

        adjudicator.adjudicate_reality_warp(context)

        all_events = run_log.get_events()

        for event in all_events:
            assert event.event_type in list(EventType)


# =============================================================================
# LOG FORMAT AND SERIALIZATION TESTS
# =============================================================================


class TestRunLogSerialization:
    """Test that RunLog can be serialized with spell adjudication events."""

    def test_spell_adjudication_event_to_dict(self, adjudicator):
        """Spell adjudication events should serialize to dict."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Charm Person",
            caster_name="Wizard",
            caster_level=5,
            target_description="Guard",
        )

        adjudicator.adjudicate_charm_resistance(context, target_hit_dice=2)

        events = run_log.get_spell_adjudications()
        event = events[-1]

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == EventType.SPELL_ADJUDICATION.value
        assert event_dict["spell_name"] == "Charm Person"
        assert event_dict["adjudication_type"] == SpellAdjudicationType.CHARM_RESISTANCE.value

    def test_full_runlog_to_json(self, adjudicator):
        """Full RunLog should serialize to JSON."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Test",
            caster_name="Caster",
            caster_level=5,
            target_description="Target",
        )

        adjudicator.adjudicate_charm_resistance(context, target_hit_dice=2)
        adjudicator.adjudicate_reality_warp(context)

        json_str = run_log.to_json()

        assert isinstance(json_str, str)
        assert len(json_str) > 0
        assert "spell_adjudication" in json_str.lower()

    def test_spell_adjudication_event_str(self, adjudicator):
        """Spell adjudication event should have readable string representation."""
        seed_dice(42)
        run_log = get_run_log()

        context = AdjudicationContext(
            spell_name="Polymorph",
            caster_name="Wizard",
            caster_level=10,
            target_description="Dragon",
        )

        adjudicator.adjudicate_reality_warp(context)

        events = run_log.get_spell_adjudications()
        event = events[-1]

        str_repr = str(event)

        assert isinstance(str_repr, str)
        assert "Polymorph" in str_repr
        assert "reality_warp" in str_repr


# =============================================================================
# RUN LOG SUMMARY TESTS
# =============================================================================


class TestRunLogSummary:
    """Test RunLog summary includes spell adjudication counts."""

    def test_summary_includes_spell_adjudications(self, adjudicator):
        """RunLog summary should count spell adjudications."""
        seed_dice(42)
        run_log = get_run_log()
        reset_run_log()

        context = AdjudicationContext(
            spell_name="Test",
            caster_name="Caster",
            caster_level=5,
            target_description="Target",
        )

        # Run several adjudications
        for i in range(3):
            seed_dice(i * 100)
            adjudicator.adjudicate_charm_resistance(context, target_hit_dice=2)

        summary = run_log.get_summary()

        assert "spell_adjudications" in summary
        assert summary["spell_adjudications"] == 3
