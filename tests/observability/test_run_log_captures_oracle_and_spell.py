"""
Tests for RunLog capturing oracle and spell adjudication events.

Phase 4.1: Verify that RunLog captures:
- Mythic GME fate checks
- Mythic GME meaning rolls
- Spell adjudication outcomes
- Encounter events
"""

import pytest

from src.data_models import DiceRoller
from src.observability.run_log import (
    get_run_log,
    reset_run_log,
    EventType,
    OracleEvent,
    SpellAdjudicationEvent,
)
from src.oracle.mythic_gme import MythicGME, Likelihood
from src.oracle.dice_rng_adapter import DiceRngAdapter


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def clean_run_log():
    """Ensure a clean RunLog for each test."""
    reset_run_log()
    log = get_run_log()
    yield log
    reset_run_log()


class TestRunLogCapturesFateCheck:
    """Test that RunLog captures Mythic GME fate checks."""

    def test_fate_check_logged_to_run_log(self, seeded_dice, clean_run_log):
        """Fate checks should be logged to RunLog."""
        adapter = DiceRngAdapter("test")
        mythic = MythicGME(rng=adapter)

        # Perform a fate check
        result = mythic.fate_check("Is the door locked?", Likelihood.LIKELY)

        # Check RunLog captured it
        oracle_events = clean_run_log.get_oracle_events()
        assert len(oracle_events) >= 1

        # Find the fate check event
        fate_events = [e for e in oracle_events if e.oracle_type == "fate_check"]
        assert len(fate_events) >= 1

        event = fate_events[0]
        assert event.question == "Is the door locked?"
        assert event.likelihood == "likely"
        assert event.result in ("yes", "no", "exceptional_yes", "exceptional_no")
        assert event.chaos_factor > 0

    def test_fate_check_event_has_roll_value(self, seeded_dice, clean_run_log):
        """Fate check event should include the dice roll."""
        adapter = DiceRngAdapter("test")
        mythic = MythicGME(rng=adapter)

        mythic.fate_check("Test question?", Likelihood.FIFTY_FIFTY)

        oracle_events = clean_run_log.get_oracle_events()
        fate_events = [e for e in oracle_events if e.oracle_type == "fate_check"]

        assert len(fate_events) >= 1
        assert fate_events[0].roll > 0
        assert fate_events[0].roll <= 100


class TestRunLogCapturesMeaningRoll:
    """Test that RunLog captures Mythic GME meaning rolls."""

    def test_meaning_roll_logged_to_run_log(self, seeded_dice, clean_run_log):
        """Meaning rolls should be logged to RunLog."""
        adapter = DiceRngAdapter("test")
        mythic = MythicGME(rng=adapter)

        # Perform a meaning roll
        result = mythic.roll_meaning()

        # Check RunLog captured it
        oracle_events = clean_run_log.get_oracle_events()
        meaning_events = [e for e in oracle_events if e.oracle_type == "meaning_roll"]

        assert len(meaning_events) >= 1
        event = meaning_events[0]
        assert event.meaning_action != ""
        assert event.meaning_subject != ""


class TestRunLogCapturesSpellAdjudication:
    """Test that RunLog captures spell adjudication events."""

    def test_spell_adjudication_logged_via_controller(self, seeded_dice, clean_run_log):
        """Spell adjudication via GlobalController should be logged."""
        from src.main import VirtualDM, GameConfig
        from src.data_models import GameDate, GameTime, CharacterState
        from src.game_state.state_machine import GameState

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

        # Add a character
        char = CharacterState(
            character_id="wizard_1",
            name="Test Wizard",
            character_class="Magic-User",
            level=5,
            ability_scores={"STR": 10, "INT": 16, "WIS": 12, "DEX": 13, "CON": 14, "CHA": 11},
            hp_current=15,
            hp_max=15,
            armor_class=9,
            base_speed=30,
        )
        dm.controller.add_character(char)

        # Perform spell adjudication
        result = dm.controller.adjudicate_oracle_spell(
            spell_name="Detect Magic",
            caster_id="wizard_1",
            adjudication_type="divination",
            oracle_question="What magical auras are present?",
        )

        # Check RunLog captured it
        spell_events = clean_run_log.get_spell_adjudications()
        assert len(spell_events) >= 1

        event = spell_events[0]
        assert event.spell_name == "Detect Magic"
        assert event.caster_id == "wizard_1"
        assert event.adjudication_type == "divination"
        assert event.success_level in (
            "exceptional_success", "success", "partial_success", "failure", "catastrophic_failure"
        )


class TestRunLogEventSerialization:
    """Test that new event types serialize correctly."""

    def test_oracle_event_to_dict(self, clean_run_log):
        """OracleEvent should serialize to dict correctly."""
        clean_run_log.log_oracle(
            oracle_type="fate_check",
            question="Test?",
            likelihood="likely",
            roll=75,
            result="yes",
            chaos_factor=5,
        )

        events = clean_run_log.get_oracle_events()
        assert len(events) == 1

        as_dict = events[0].to_dict()
        assert as_dict["event_type"] == "oracle"
        assert as_dict["oracle_type"] == "fate_check"
        assert as_dict["question"] == "Test?"
        assert as_dict["roll"] == 75

    def test_spell_adjudication_event_to_dict(self, clean_run_log):
        """SpellAdjudicationEvent should serialize to dict correctly."""
        clean_run_log.log_spell_adjudication(
            spell_name="Fireball",
            caster_id="mage_1",
            adjudication_type="generic",
            success_level="success",
            summary="Fireball succeeds",
            effects_executed=["damage"],
            has_complication=False,
        )

        events = clean_run_log.get_spell_adjudications()
        assert len(events) == 1

        as_dict = events[0].to_dict()
        assert as_dict["event_type"] == "spell_adjudication"
        assert as_dict["spell_name"] == "Fireball"
        assert as_dict["success_level"] == "success"
        assert as_dict["effects_executed"] == ["damage"]

    def test_run_log_json_export_includes_new_events(self, clean_run_log):
        """RunLog JSON export should include new event types."""
        clean_run_log.log_oracle(
            oracle_type="fate_check",
            question="Test?",
            result="yes",
        )
        clean_run_log.log_spell_adjudication(
            spell_name="Magic Missile",
            caster_id="wizard_1",
            adjudication_type="generic",
            success_level="success",
        )
        clean_run_log.log_encounter(
            encounter_type="start",
            encounter_id="enc_001",
            creatures=["Goblin", "Hobgoblin"],
        )
        clean_run_log.log_llm_call(
            call_type="narration",
            schema_name="LocationSchema",
            success=True,
            latency_ms=150,
        )

        json_output = clean_run_log.to_json()

        assert '"oracle"' in json_output
        assert '"spell_adjudication"' in json_output
        assert '"encounter"' in json_output
        assert '"llm_call"' in json_output


class TestRunLogSummary:
    """Test that RunLog summary includes new event counts."""

    def test_summary_includes_new_event_counts(self, clean_run_log):
        """Summary should include counts for new event types."""
        clean_run_log.log_oracle(oracle_type="fate_check", question="Test?", result="yes")
        clean_run_log.log_oracle(oracle_type="meaning_roll", meaning_action="Reveal", meaning_subject="Secret")
        clean_run_log.log_spell_adjudication(
            spell_name="Charm",
            caster_id="w1",
            adjudication_type="generic",
            success_level="success",
        )
        clean_run_log.log_encounter(encounter_type="start", creatures=["Wolf"])
        clean_run_log.log_llm_call(call_type="narration", success=True)

        summary = clean_run_log.get_summary()

        assert summary["oracle_events"] == 2
        assert summary["spell_adjudications"] == 1
        assert summary["encounter_events"] == 1
        assert summary["llm_calls"] == 1
        assert summary["total_events"] == 5
