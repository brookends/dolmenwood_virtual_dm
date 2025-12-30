"""
Tests for the observability and replay system.

Tests RunLog, ReplaySession, and integration with DiceRoller/StateMachine.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.data_models import DiceRoller
from src.game_state.state_machine import StateMachine, GameState
from src.observability.run_log import (
    RunLog,
    get_run_log,
    reset_run_log,
    EventType,
    RollEvent,
    TransitionEvent,
    TableLookupEvent,
    TimeStepEvent,
)
from src.observability.replay import ReplaySession, ReplayMode


class TestRunLog:
    """Tests for the RunLog class."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset RunLog and DiceRoller before each test."""
        reset_run_log()
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)
        yield
        reset_run_log()
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)

    def test_singleton_pattern(self):
        """RunLog should be a singleton."""
        log1 = get_run_log()
        log2 = get_run_log()
        assert log1 is log2

    def test_log_roll_event(self):
        """Test logging a roll event."""
        log = get_run_log()
        event = log.log_roll(
            notation="2d6",
            rolls=[3, 4],
            modifier=0,
            total=7,
            reason="test roll",
        )

        assert event.event_type == EventType.ROLL
        assert event.notation == "2d6"
        assert event.rolls == [3, 4]
        assert event.total == 7
        assert event.reason == "test roll"
        assert event.sequence_number == 1

    def test_log_transition_event(self):
        """Test logging a transition event."""
        log = get_run_log()
        event = log.log_transition(
            from_state="wilderness_travel",
            to_state="encounter",
            trigger="encounter_triggered",
        )

        assert event.event_type == EventType.TRANSITION
        assert event.from_state == "wilderness_travel"
        assert event.to_state == "encounter"
        assert event.trigger == "encounter_triggered"

    def test_log_table_lookup_event(self):
        """Test logging a table lookup event."""
        log = get_run_log()
        event = log.log_table_lookup(
            table_id="reaction_2d6",
            table_name="Reaction Roll",
            roll_total=9,
            result_text="Indifferent",
            modifier_applied=2,
        )

        assert event.event_type == EventType.TABLE_LOOKUP
        assert event.table_id == "reaction_2d6"
        assert event.roll_total == 9
        assert event.modifier_applied == 2

    def test_log_time_step_event(self):
        """Test logging a time step event."""
        log = get_run_log()
        event = log.log_time_step(
            old_time="14:00",
            new_time="14:10",
            turns_advanced=1,
            minutes_advanced=10,
            reason="exploration turn",
        )

        assert event.event_type == EventType.TIME_STEP
        assert event.old_time == "14:00"
        assert event.new_time == "14:10"
        assert event.turns_advanced == 1

    def test_sequence_numbers_increment(self):
        """Test that sequence numbers increment properly."""
        log = get_run_log()
        e1 = log.log_roll("1d6", [3], 0, 3, "test1")
        e2 = log.log_roll("1d6", [5], 0, 5, "test2")
        e3 = log.log_transition("a", "b", "trigger")

        assert e1.sequence_number == 1
        assert e2.sequence_number == 2
        assert e3.sequence_number == 3

    def test_get_events_by_type(self):
        """Test filtering events by type."""
        log = get_run_log()
        log.log_roll("1d6", [3], 0, 3, "roll1")
        log.log_transition("a", "b", "trigger1")
        log.log_roll("1d6", [5], 0, 5, "roll2")
        log.log_table_lookup("table1", "Table One", 5, "result")

        rolls = log.get_rolls()
        transitions = log.get_transitions()
        table_lookups = log.get_table_lookups()

        assert len(rolls) == 2
        assert len(transitions) == 1
        assert len(table_lookups) == 1

    def test_get_roll_stream(self):
        """Test extracting roll stream for replay."""
        log = get_run_log()
        log.log_roll("2d6", [3, 4], 0, 7, "roll1")
        log.log_roll("1d20", [15], 2, 17, "roll2")

        stream = log.get_roll_stream()

        assert len(stream) == 2
        assert stream[0]["notation"] == "2d6"
        assert stream[0]["rolls"] == [3, 4]
        assert stream[0]["total"] == 7
        assert stream[1]["notation"] == "1d20"

    def test_reset_clears_log(self):
        """Test that reset clears the log."""
        log = get_run_log()
        log.log_roll("1d6", [3], 0, 3, "test")
        assert log.get_event_count() == 1

        log.reset()
        assert log.get_event_count() == 0

    def test_pause_prevents_logging(self):
        """Test that pausing prevents new events from being logged."""
        log = get_run_log()
        log.log_roll("1d6", [3], 0, 3, "before pause")
        assert log.get_event_count() == 1

        log.pause()
        log.log_roll("1d6", [5], 0, 5, "during pause")
        assert log.get_event_count() == 1  # Still 1

        log.resume()
        log.log_roll("1d6", [2], 0, 2, "after resume")
        assert log.get_event_count() == 2

    def test_to_dict_serialization(self):
        """Test serializing the log to a dictionary."""
        log = get_run_log()
        log.set_seed(12345)
        log.log_roll("2d6", [3, 4], 0, 7, "test roll")
        log.log_transition("a", "b", "trigger")

        data = log.to_dict()

        assert data["seed"] == 12345
        assert len(data["events"]) == 2
        assert data["events"][0]["event_type"] == "roll"
        assert data["events"][1]["event_type"] == "transition"

    def test_save_and_load(self):
        """Test saving and loading the log."""
        log = get_run_log()
        log.set_seed(12345)
        log.log_roll("2d6", [3, 4], 0, 7, "test roll")
        log.log_transition("a", "b", "trigger")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            log.save(filepath)

            # Load into fresh log
            reset_run_log()
            loaded = RunLog.load(filepath)

            assert loaded.get_seed() == 12345
            assert loaded.get_event_count() == 2
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_format_log(self):
        """Test formatting the log as a string."""
        log = get_run_log()
        log.log_roll("2d6", [3, 4], 0, 7, "attack roll")
        log.log_transition("combat", "wilderness", "combat_end")

        formatted = log.format_log()

        assert "Run Log" in formatted
        assert "ROLL 2d6" in formatted
        assert "TRANSITION" in formatted

    def test_subscriber_receives_events(self):
        """Test that subscribers receive logged events."""
        log = get_run_log()
        received_events = []

        def subscriber(event):
            received_events.append(event)

        log.subscribe(subscriber)
        log.log_roll("1d6", [3], 0, 3, "test")
        log.log_transition("a", "b", "trigger")

        assert len(received_events) == 2
        assert received_events[0].event_type == EventType.ROLL
        assert received_events[1].event_type == EventType.TRANSITION

        log.unsubscribe(subscriber)
        log.log_roll("1d6", [5], 0, 5, "after unsubscribe")
        assert len(received_events) == 2  # No new events


class TestReplaySession:
    """Tests for the ReplaySession class."""

    def test_create_from_run_log_data(self):
        """Test creating a replay session from run log data."""
        log_data = {
            "seed": 12345,
            "events": [
                {
                    "event_type": "roll",
                    "notation": "2d6",
                    "rolls": [3, 4],
                    "total": 7,
                    "reason": "r1",
                },
                {"event_type": "transition", "from_state": "a", "to_state": "b"},
                {
                    "event_type": "roll",
                    "notation": "1d20",
                    "rolls": [15],
                    "total": 15,
                    "reason": "r2",
                },
            ],
        }

        session = ReplaySession.from_run_log(log_data)

        assert session.seed == 12345
        assert len(session.roll_stream) == 2  # Only roll events
        assert session.roll_stream[0]["notation"] == "2d6"
        assert session.roll_stream[1]["notation"] == "1d20"

    def test_replay_mode_operations(self):
        """Test replay mode state operations."""
        session = ReplaySession(
            seed=12345,
            roll_stream=[
                {"notation": "2d6", "rolls": [3, 4], "total": 7, "reason": "r1"},
                {"notation": "1d20", "rolls": [15], "total": 15, "reason": "r2"},
            ],
        )

        assert not session.is_replaying()

        session.start_replay()
        assert session.is_replaying()
        assert session.get_position() == 0
        assert session.get_remaining_rolls() == 2

        roll1 = session.get_next_roll()
        assert roll1["notation"] == "2d6"
        assert session.get_position() == 1
        assert session.get_remaining_rolls() == 1

        roll2 = session.get_next_roll()
        assert roll2["notation"] == "1d20"
        assert session.get_position() == 2
        assert session.get_remaining_rolls() == 0

        # No more rolls
        assert not session.has_next_roll()
        roll3 = session.get_next_roll()
        assert roll3 is None
        assert session.get_overrun_count() == 1

        session.stop_replay()
        assert not session.is_replaying()

    def test_peek_next_roll(self):
        """Test peeking at next roll without advancing."""
        session = ReplaySession(
            seed=12345,
            roll_stream=[
                {"notation": "1d6", "rolls": [3], "total": 3, "reason": "test"},
            ],
        )
        session.start_replay()

        peeked = session.peek_next_roll()
        assert peeked["notation"] == "1d6"
        assert session.get_position() == 0  # Not advanced

        consumed = session.get_next_roll()
        assert consumed["notation"] == "1d6"
        assert session.get_position() == 1  # Advanced

    def test_reset_replay(self):
        """Test resetting replay to beginning."""
        session = ReplaySession(
            seed=12345,
            roll_stream=[
                {"notation": "1d6", "rolls": [3], "total": 3, "reason": "test"},
            ],
        )
        session.start_replay()
        session.get_next_roll()
        assert session.get_position() == 1

        session.reset()
        assert session.get_position() == 0
        assert session.has_next_roll()

    def test_save_and_load(self):
        """Test saving and loading a replay session."""
        session = ReplaySession(
            seed=12345,
            roll_stream=[
                {"notation": "2d6", "rolls": [3, 4], "total": 7, "reason": "r1"},
            ],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            session.save(filepath)
            loaded = ReplaySession.load(filepath)

            assert loaded.seed == 12345
            assert len(loaded.roll_stream) == 1
            assert loaded.roll_stream[0]["notation"] == "2d6"
        finally:
            Path(filepath).unlink(missing_ok=True)


class TestDiceRollerIntegration:
    """Test DiceRoller integration with observability."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset state before each test."""
        reset_run_log()
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)
        yield
        reset_run_log()
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)

    def test_dice_roller_logs_to_run_log(self):
        """Test that DiceRoller logs rolls to RunLog."""
        log = get_run_log()
        DiceRoller.set_seed(42)

        DiceRoller.roll("2d6", "attack roll")
        DiceRoller.roll("1d20", "to hit")

        rolls = log.get_rolls()
        assert len(rolls) == 2
        assert rolls[0].notation == "2d6"
        assert rolls[1].notation == "1d20"

    def test_dice_roller_seed_recorded(self):
        """Test that setting seed is recorded in RunLog."""
        log = get_run_log()
        DiceRoller.set_seed(12345)

        assert log.get_seed() == 12345

    def test_replay_mode_uses_recorded_rolls(self):
        """Test that replay mode uses recorded roll values."""
        # Create a replay session with predetermined rolls
        session = ReplaySession(
            seed=12345,
            roll_stream=[
                {"notation": "2d6", "rolls": [6, 6], "total": 12, "reason": "max roll"},
                {"notation": "1d20", "rolls": [20], "total": 20, "reason": "natural 20"},
            ],
        )
        session.start_replay()
        DiceRoller.set_replay_session(session)

        # These should return the predetermined values, not random ones
        result1 = DiceRoller.roll("2d6", "attack")
        assert result1.rolls == [6, 6]
        assert result1.total == 12

        result2 = DiceRoller.roll("1d20", "to hit")
        assert result2.rolls == [20]
        assert result2.total == 20

        # After exhausting the stream, should fall back to random
        # (but this would generate a new random roll)

    def test_randint_logs_to_run_log(self):
        """Test that randint logs to RunLog."""
        log = get_run_log()
        DiceRoller.set_seed(42)

        DiceRoller.randint(1, 10, "random pick")

        rolls = log.get_rolls()
        assert len(rolls) == 1
        assert "range(1-10)" in rolls[0].notation

    def test_choice_logs_to_run_log(self):
        """Test that choice logs to RunLog."""
        log = get_run_log()
        DiceRoller.set_seed(42)

        items = ["a", "b", "c"]
        DiceRoller.choice(items, "pick item")

        rolls = log.get_rolls()
        assert len(rolls) == 1
        assert "choice" in rolls[0].notation

    def test_replay_deterministic_sequence(self):
        """Test that replay produces identical sequence."""
        # First run: record
        reset_run_log()
        DiceRoller.set_seed(12345)
        DiceRoller.set_replay_session(None)

        r1 = DiceRoller.roll("2d6", "roll1")
        r2 = DiceRoller.roll("1d20", "roll2")
        r3 = DiceRoller.randint(1, 100, "randint1")

        original_totals = [r1.total, r2.total, r3]

        # Get the roll stream
        log = get_run_log()
        roll_stream = log.get_roll_stream()

        # Second run: replay
        reset_run_log()
        DiceRoller.clear_roll_log()

        session = ReplaySession(seed=12345, roll_stream=roll_stream)
        session.start_replay()
        DiceRoller.set_replay_session(session)

        r1_replay = DiceRoller.roll("2d6", "roll1")
        r2_replay = DiceRoller.roll("1d20", "roll2")
        r3_replay = DiceRoller.randint(1, 100, "randint1")

        replay_totals = [r1_replay.total, r2_replay.total, r3_replay]

        assert original_totals == replay_totals


class TestStateMachineIntegration:
    """Test StateMachine integration with observability."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset state before each test."""
        reset_run_log()
        yield
        reset_run_log()

    def test_transitions_logged_to_run_log(self):
        """Test that state transitions are logged to RunLog."""
        log = get_run_log()
        sm = StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)

        # Initial state log
        transitions = log.get_transitions()
        assert len(transitions) == 1
        assert transitions[0].to_state == "wilderness_travel"

        # Trigger a transition
        sm.transition("encounter_triggered")

        transitions = log.get_transitions()
        assert len(transitions) == 2
        assert transitions[1].from_state == "wilderness_travel"
        assert transitions[1].to_state == "encounter"
        assert transitions[1].trigger == "encounter_triggered"

    def test_multiple_transitions_tracked(self):
        """Test tracking multiple state transitions."""
        log = get_run_log()
        sm = StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)

        sm.transition("encounter_triggered")
        sm.transition("encounter_to_combat")
        sm.transition("combat_end_wilderness")

        transitions = log.get_transitions()
        # Initial + 3 transitions
        assert len(transitions) == 4

        # Verify sequence
        assert transitions[1].from_state == "wilderness_travel"
        assert transitions[1].to_state == "encounter"
        assert transitions[2].from_state == "encounter"
        assert transitions[2].to_state == "combat"
        assert transitions[3].from_state == "combat"
        assert transitions[3].to_state == "wilderness_travel"


class TestEndToEndObservability:
    """End-to-end tests for the observability system."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset state before each test."""
        reset_run_log()
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)
        yield
        reset_run_log()
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)

    def test_full_session_recording_and_replay(self):
        """Test recording a full session and replaying it."""
        # Record a session
        log = get_run_log()
        DiceRoller.set_seed(42)

        sm = StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)

        # Simulate some gameplay
        attack_roll = DiceRoller.roll("1d20", "attack roll")
        damage_roll = DiceRoller.roll("2d6", "damage roll")
        reaction = DiceRoller.roll("2d6", "reaction roll")

        sm.transition("encounter_triggered")
        sm.transition("encounter_to_combat")

        # Record original results
        original_attack = attack_roll.total
        original_damage = damage_roll.total
        original_reaction = reaction.total

        # Save the session
        roll_stream = log.get_roll_stream()
        session_data = log.to_dict()

        # Reset everything
        reset_run_log()
        DiceRoller.clear_roll_log()

        # Replay
        session = ReplaySession.from_run_log(session_data)
        session.start_replay()
        DiceRoller.set_replay_session(session)

        sm2 = StateMachine(initial_state=GameState.WILDERNESS_TRAVEL)

        attack_replay = DiceRoller.roll("1d20", "attack roll")
        damage_replay = DiceRoller.roll("2d6", "damage roll")
        reaction_replay = DiceRoller.roll("2d6", "reaction roll")

        # Verify deterministic replay
        assert attack_replay.total == original_attack
        assert damage_replay.total == original_damage
        assert reaction_replay.total == original_reaction

    def test_log_summary(self):
        """Test getting a summary of the log."""
        log = get_run_log()
        DiceRoller.set_seed(42)

        DiceRoller.roll("2d6", "roll1")
        DiceRoller.roll("1d20", "roll2")

        sm = StateMachine()
        sm.transition("encounter_triggered")

        log.log_table_lookup("reaction_2d6", "Reaction", 9, "Indifferent")
        log.log_time_step("14:00", "14:10", 1, 10, "exploration")

        summary = log.get_summary()

        assert summary["seed"] == 42
        assert summary["rolls"] == 2
        assert summary["transitions"] >= 1
        assert summary["table_lookups"] == 1
        assert summary["time_steps"] == 1
