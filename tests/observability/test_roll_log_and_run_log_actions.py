"""
Tests for roll_log and run_log meta actions.

Phase 5: Verify that:
- meta:roll_log returns content containing recent dice rolls
- meta:export_roll_log returns valid JSON with dice rolls
- meta:run_log returns formatted RunLog events
- meta:export_run_log exports the actual RunLog
"""

import pytest
import json
import os
import tempfile

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState
from src.conversation.action_registry import get_default_registry, reset_registry
from src.observability.run_log import get_run_log, reset_run_log


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def reset_logs():
    """Reset all logs before and after tests."""
    DiceRoller.clear_roll_log()
    reset_run_log()
    yield
    DiceRoller.clear_roll_log()
    reset_run_log()


@pytest.fixture
def test_character():
    """A sample character for testing."""
    return CharacterState(
        character_id="test_fighter_1",
        name="Test Fighter",
        character_class="Fighter",
        level=3,
        ability_scores={
            "STR": 16, "INT": 10, "WIS": 12,
            "DEX": 14, "CON": 15, "CHA": 11,
        },
        hp_current=24,
        hp_max=24,
        armor_class=4,
        base_speed=30,
    )


@pytest.fixture
def offline_dm(seeded_dice, test_character, reset_logs):
    """Create VirtualDM in offline mode."""
    reset_registry()
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


class TestMetaRollLog:
    """Test meta:roll_log action."""

    def test_roll_log_shows_recent_rolls(self, offline_dm, seeded_dice):
        """meta:roll_log should return content with recent dice rolls."""
        reset_registry()
        registry = get_default_registry()

        # Perform some dice rolls
        DiceRoller.roll("1d20", reason="Attack roll")
        DiceRoller.roll("2d6", reason="Damage roll")
        DiceRoller.roll("1d6", reason="Random check")

        # Execute meta:roll_log
        result = registry.execute(offline_dm, "meta:roll_log", {"limit": 20})

        assert result["success"] is True
        assert "Recent Dice Rolls" in result["message"]
        assert "Attack roll" in result["message"]
        assert "Damage roll" in result["message"]

    def test_roll_log_empty_when_no_rolls(self, offline_dm):
        """meta:roll_log with no rolls should indicate empty."""
        reset_registry()
        registry = get_default_registry()

        # Clear any existing rolls
        DiceRoller.clear_roll_log()

        result = registry.execute(offline_dm, "meta:roll_log", {})

        assert result["success"] is True
        assert "No dice rolls recorded" in result["message"]

    def test_roll_log_respects_limit(self, offline_dm, seeded_dice):
        """meta:roll_log should respect the limit parameter."""
        reset_registry()
        registry = get_default_registry()

        # Make many rolls
        for i in range(10):
            DiceRoller.roll("1d6", reason=f"Roll {i+1}")

        # Request only 3
        result = registry.execute(offline_dm, "meta:roll_log", {"limit": 3})

        assert result["success"] is True
        # The roll_log data should have only 3 entries
        if "roll_log" in result:
            assert len(result["roll_log"]) <= 3


class TestMetaExportRollLog:
    """Test meta:export_roll_log action."""

    def test_export_roll_log_creates_valid_json(self, offline_dm, seeded_dice):
        """meta:export_roll_log should create a valid JSON file."""
        reset_registry()
        registry = get_default_registry()

        # Perform some rolls
        DiceRoller.roll("1d20", reason="Test export roll 1")
        DiceRoller.roll("2d6+3", reason="Test export roll 2")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(
                offline_dm,
                "meta:export_roll_log",
                {"save_dir": tmpdir}
            )

            assert result["success"] is True
            assert "exported" in result["message"].lower()
            assert "filepath" in result

            # Verify the file exists and is valid JSON
            filepath = result["filepath"]
            assert os.path.exists(filepath)

            with open(filepath, "r") as f:
                data = json.load(f)

            assert "roll_log" in data
            assert isinstance(data["roll_log"], list)
            assert len(data["roll_log"]) >= 2


class TestMetaRunLog:
    """Test meta:run_log action."""

    def test_run_log_shows_events(self, offline_dm):
        """meta:run_log should show RunLog events."""
        reset_registry()
        registry = get_default_registry()

        # Get the RunLog and add some events
        run_log = get_run_log()
        run_log.log_transition(
            from_state="wilderness_travel",
            to_state="encounter",
            trigger="encounter_triggered",
        )
        run_log.log_roll(
            notation="1d6",
            rolls=[4],
            modifier=0,
            total=4,
            reason="Encounter check",
        )

        # Execute meta:run_log
        result = registry.execute(offline_dm, "meta:run_log", {"limit": 50})

        assert result["success"] is True
        # Should contain the log header
        assert "Run Log" in result["message"]

    def test_run_log_returns_formatted_output(self, offline_dm, reset_logs):
        """meta:run_log should return formatted RunLog output."""
        reset_registry()
        registry = get_default_registry()

        result = registry.execute(offline_dm, "meta:run_log", {})

        assert result["success"] is True
        # The VirtualDM initialization adds an INIT transition event,
        # so we should see the Run Log header
        assert "Run Log" in result["message"]


class TestMetaExportRunLog:
    """Test meta:export_run_log action (the actual RunLog, not dice log)."""

    def test_export_run_log_creates_valid_json(self, offline_dm, reset_logs):
        """meta:export_run_log should export the actual RunLog."""
        reset_registry()
        registry = get_default_registry()

        # Add events to RunLog
        run_log = get_run_log()
        run_log.log_transition(
            from_state="wilderness_travel",
            to_state="settlement_exploration",
            trigger="enter_settlement",
        )
        run_log.log_time_step(
            old_time="10:00",
            new_time="11:00",
            turns_advanced=6,
            minutes_advanced=60,
            reason="Travel time",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(
                offline_dm,
                "meta:export_run_log",
                {"save_dir": tmpdir}
            )

            assert result["success"] is True
            assert "exported" in result["message"].lower()
            assert "filepath" in result

            # Verify the file exists and is valid JSON
            filepath = result["filepath"]
            assert os.path.exists(filepath)

            with open(filepath, "r") as f:
                data = json.load(f)

            # This should be a RunLog export, not a dice log export
            # RunLog exports have "events" key, not just "roll_log"
            assert "events" in data
            assert isinstance(data["events"], list)
            assert len(data["events"]) >= 2

            # Check that our transition event is there
            event_types = [e["event_type"] for e in data["events"]]
            assert "transition" in event_types
            assert "time_step" in event_types

    def test_export_run_log_includes_summary(self, offline_dm, reset_logs):
        """meta:export_run_log result should include summary."""
        reset_registry()
        registry = get_default_registry()

        # Add an event
        run_log = get_run_log()
        run_log.log_roll(
            notation="2d6",
            rolls=[3, 4],
            modifier=0,
            total=7,
            reason="Test roll",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(
                offline_dm,
                "meta:export_run_log",
                {"save_dir": tmpdir}
            )

            assert result["success"] is True
            assert "summary" in result
            assert result["summary"]["total_events"] >= 1


class TestMetaReplayStatus:
    """Test meta:replay_status action."""

    def test_replay_status_reports_inactive(self, offline_dm):
        """meta:replay_status should indicate replay is not active when no session."""
        reset_registry()
        registry = get_default_registry()

        result = registry.execute(offline_dm, "meta:replay_status", {})

        assert result["success"] is True
        assert "replay_active" in result
        # P10.3: Replay is now implemented but should show inactive when no session
        assert result["replay_active"] is False
        assert "inactive" in result["message"].lower()


class TestLogNamingConsistency:
    """Test that log action naming is consistent with behavior."""

    def test_export_roll_log_exports_dice_rolls(self, offline_dm, seeded_dice):
        """meta:export_roll_log should export dice rolls specifically."""
        reset_registry()
        registry = get_default_registry()

        # Make some dice rolls
        DiceRoller.roll("1d20", reason="Naming test")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(
                offline_dm,
                "meta:export_roll_log",
                {"save_dir": tmpdir}
            )

            assert result["success"] is True
            filepath = result["filepath"]

            with open(filepath, "r") as f:
                data = json.load(f)

            # Should contain roll_log with dice data
            assert "roll_log" in data
            if data["roll_log"]:
                roll = data["roll_log"][-1]
                # Each roll should have notation, rolls, total
                assert "notation" in roll or "dice" in str(roll).lower()

    def test_export_run_log_exports_events_not_just_dice(self, offline_dm, reset_logs):
        """meta:export_run_log should export all event types, not just dice."""
        reset_registry()
        registry = get_default_registry()

        # Add different types of events
        run_log = get_run_log()
        run_log.log_transition("a", "b", "test")
        run_log.log_table_lookup("t1", "Test Table", 5, "Result text")
        run_log.log_custom("custom_event", {"key": "value"})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(
                offline_dm,
                "meta:export_run_log",
                {"save_dir": tmpdir}
            )

            filepath = result["filepath"]
            with open(filepath, "r") as f:
                data = json.load(f)

            # Should have events of different types
            event_types = set(e["event_type"] for e in data["events"])
            assert "transition" in event_types
            assert "table_lookup" in event_types
            assert "custom" in event_types
