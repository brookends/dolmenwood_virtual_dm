"""
P10.3: Tests for replay integration hygiene.

Verifies that:
1. Replay infrastructure is properly integrated and usable
2. meta:replay_status shows correct status
3. meta:replay_load can load a run log file
4. meta:replay_stop properly disables replay
5. meta:replay_peek shows upcoming rolls
6. DiceRoller actually uses replay rolls when in replay mode
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.observability.replay import ReplaySession, ReplayMode
from src.observability.run_log import RunLog, get_run_log, reset_run_log
from src.data_models import DiceRoller
from src.conversation.action_registry import get_default_registry


class TestReplaySessionBasics:
    """Test ReplaySession core functionality."""

    def test_create_empty_session(self):
        """Verify empty session can be created."""
        session = ReplaySession(seed=42)
        assert session.seed == 42
        assert session.mode == ReplayMode.DISABLED
        assert len(session.roll_stream) == 0

    def test_add_roll_to_session(self):
        """Verify rolls can be added to session."""
        session = ReplaySession(seed=42)
        session.add_roll("2d6", [3, 4], 0, 7, "test roll")

        assert len(session.roll_stream) == 1
        assert session.roll_stream[0]["notation"] == "2d6"
        assert session.roll_stream[0]["total"] == 7

    def test_start_replay(self):
        """Verify replay can be started."""
        session = ReplaySession(seed=42)
        session.add_roll("1d20", [15], 0, 15, "attack")
        session.start_replay()

        assert session.is_replaying()
        assert session.mode == ReplayMode.REPLAYING
        assert session.get_position() == 0

    def test_get_next_roll(self):
        """Verify rolls can be retrieved in sequence."""
        session = ReplaySession(seed=42)
        session.add_roll("1d20", [15], 0, 15, "first")
        session.add_roll("2d6", [3, 4], 0, 7, "second")
        session.start_replay()

        roll1 = session.get_next_roll()
        assert roll1["total"] == 15
        assert session.get_position() == 1

        roll2 = session.get_next_roll()
        assert roll2["total"] == 7
        assert session.get_position() == 2

    def test_overrun_tracking(self):
        """Verify overruns are tracked when rolls are exhausted."""
        session = ReplaySession(seed=42)
        session.add_roll("1d6", [4], 0, 4, "only roll")
        session.start_replay()

        session.get_next_roll()  # Consume the only roll
        session.get_next_roll()  # This should cause an overrun

        assert session.get_overrun_count() == 1

    def test_summary(self):
        """Verify summary provides correct info."""
        session = ReplaySession(seed=42)
        session.add_roll("1d6", [4], 0, 4, "roll")
        session.start_replay()
        session.get_next_roll()

        summary = session.get_summary()
        assert summary["seed"] == 42
        assert summary["total_rolls"] == 1
        assert summary["current_position"] == 1
        assert summary["remaining_rolls"] == 0


class TestReplaySessionFileIO:
    """Test ReplaySession file save/load."""

    def test_save_and_load_session(self, tmp_path):
        """Verify session can be saved and loaded."""
        filepath = tmp_path / "test_replay.json"

        # Create and save session
        session = ReplaySession(seed=42)
        session.add_roll("1d20", [18], 3, 21, "attack roll")
        session.add_roll("2d6", [4, 5], 0, 9, "damage")
        session.save(str(filepath))

        # Load session
        loaded = ReplaySession.load(str(filepath))
        assert loaded.seed == 42
        assert len(loaded.roll_stream) == 2
        assert loaded.roll_stream[0]["total"] == 21

    def test_load_from_run_log_format(self, tmp_path):
        """Verify session can be loaded from RunLog JSON format."""
        filepath = tmp_path / "run_log.json"

        # Create run log format data
        run_log_data = {
            "session_start": "2024-01-01T12:00:00",
            "seed": 123,
            "sequence": 3,
            "events": [
                {
                    "event_type": "roll",
                    "notation": "1d20",
                    "rolls": [17],
                    "modifier": 2,
                    "total": 19,
                    "reason": "initiative",
                },
                {
                    "event_type": "transition",  # Non-roll event, should be skipped
                    "from_state": "idle",
                    "to_state": "combat",
                },
                {
                    "event_type": "roll",
                    "notation": "1d8",
                    "rolls": [6],
                    "modifier": 0,
                    "total": 6,
                    "reason": "damage",
                },
            ],
        }

        with open(filepath, "w") as f:
            json.dump(run_log_data, f)

        # Load as replay session
        session = ReplaySession.load(str(filepath))
        assert session.seed == 123
        # Should only have 2 rolls (transitions are filtered)
        assert len(session.roll_stream) == 2
        assert session.roll_stream[0]["total"] == 19
        assert session.roll_stream[1]["total"] == 6


class TestDiceRollerReplayIntegration:
    """Test that DiceRoller uses replay rolls when in replay mode."""

    def setup_method(self):
        """Clean up replay session before each test."""
        DiceRoller.set_replay_session(None)

    def teardown_method(self):
        """Clean up replay session after each test."""
        DiceRoller.set_replay_session(None)

    def test_is_replaying_false_when_no_session(self):
        """Verify is_replaying returns False when no session."""
        assert DiceRoller.is_replaying() is False

    def test_is_replaying_true_when_session_active(self):
        """Verify is_replaying returns True with active session."""
        session = ReplaySession(seed=42)
        session.add_roll("1d6", [4], 0, 4, "test")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        assert DiceRoller.is_replaying() is True

    def test_roll_uses_replay_value(self):
        """Verify DiceRoller.roll uses replay values."""
        session = ReplaySession(seed=42)
        session.add_roll("2d6", [6, 6], 0, 12, "max damage")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        # This roll should return the recorded value, not random
        result = DiceRoller.roll("2d6")
        assert result.total == 12
        assert result.rolls == [6, 6]

    def test_roll_d20_uses_replay_value(self):
        """Verify DiceRoller.roll_d20 uses replay values."""
        session = ReplaySession(seed=42)
        session.add_roll("1d20", [20], 0, 20, "nat 20")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        result = DiceRoller.roll_d20()
        assert result.total == 20

    def test_multiple_rolls_consume_stream(self):
        """Verify multiple rolls consume stream in order."""
        session = ReplaySession(seed=42)
        session.add_roll("1d6", [1], 0, 1, "first")
        session.add_roll("1d6", [6], 0, 6, "second")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        result1 = DiceRoller.roll("1d6")
        result2 = DiceRoller.roll("1d6")

        assert result1.total == 1
        assert result2.total == 6


class TestReplayActionRegistry:
    """Test replay actions in ActionRegistry."""

    def setup_method(self):
        """Clean up replay session before each test."""
        DiceRoller.set_replay_session(None)

    def teardown_method(self):
        """Clean up replay session after each test."""
        DiceRoller.set_replay_session(None)

    def test_replay_status_inactive(self):
        """Verify meta:replay_status shows inactive when no session."""
        registry = get_default_registry()
        spec = registry.get("meta:replay_status")
        assert spec is not None
        assert spec.executor is not None

        # Execute with mock DM
        dm = MagicMock()
        result = spec.executor(dm, {})

        assert result["success"] is True
        assert "INACTIVE" in result["message"]
        assert result["replay_active"] is False

    def test_replay_status_active(self):
        """Verify meta:replay_status shows active with session."""
        session = ReplaySession(seed=42)
        session.add_roll("1d6", [4], 0, 4, "test")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        registry = get_default_registry()
        spec = registry.get("meta:replay_status")
        dm = MagicMock()
        result = spec.executor(dm, {})

        assert result["success"] is True
        assert "ACTIVE" in result["message"]
        assert result["replay_active"] is True
        assert result["total_rolls"] == 1

    def test_replay_load_file_not_found(self):
        """Verify meta:replay_load handles missing file."""
        registry = get_default_registry()
        spec = registry.get("meta:replay_load")
        dm = MagicMock()

        result = spec.executor(dm, {"filepath": "/nonexistent/path.json"})

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_replay_load_success(self, tmp_path):
        """Verify meta:replay_load loads file and activates replay."""
        # Create a test run log file
        filepath = tmp_path / "test_run_log.json"
        run_log_data = {
            "session_start": "2024-01-01T12:00:00",
            "seed": 42,
            "events": [
                {"event_type": "roll", "notation": "1d20", "rolls": [15], "modifier": 0, "total": 15, "reason": "test"},
            ],
        }
        with open(filepath, "w") as f:
            json.dump(run_log_data, f)

        registry = get_default_registry()
        spec = registry.get("meta:replay_load")
        dm = MagicMock()

        result = spec.executor(dm, {"filepath": str(filepath)})

        assert result["success"] is True
        assert "ACTIVE" in result["message"]
        assert DiceRoller.is_replaying() is True

    def test_replay_stop(self):
        """Verify meta:replay_stop disables replay."""
        # Set up active replay
        session = ReplaySession(seed=42)
        session.add_roll("1d6", [4], 0, 4, "test")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        registry = get_default_registry()
        spec = registry.get("meta:replay_stop")
        dm = MagicMock()

        result = spec.executor(dm, {})

        assert result["success"] is True
        assert "stopped" in result["message"].lower()
        assert DiceRoller.is_replaying() is False
        assert DiceRoller.get_replay_session() is None

    def test_replay_peek(self):
        """Verify meta:replay_peek shows upcoming rolls."""
        session = ReplaySession(seed=42)
        session.add_roll("1d20", [18], 0, 18, "attack")
        session.add_roll("2d6", [4, 5], 0, 9, "damage")
        session.start_replay()
        DiceRoller.set_replay_session(session)

        registry = get_default_registry()
        spec = registry.get("meta:replay_peek")
        dm = MagicMock()

        result = spec.executor(dm, {"count": 5})

        assert result["success"] is True
        assert "1d20" in result["message"]
        assert "18" in result["message"]
        assert result["remaining"] == 2

    def test_replay_peek_inactive(self):
        """Verify meta:replay_peek fails when replay inactive."""
        registry = get_default_registry()
        spec = registry.get("meta:replay_peek")
        dm = MagicMock()

        result = spec.executor(dm, {})

        assert result["success"] is False
        assert "not active" in result["message"].lower()


class TestReplayActionsRegistered:
    """Verify all replay actions are properly registered."""

    def test_all_replay_actions_have_executors(self):
        """Verify all replay actions have executors."""
        registry = get_default_registry()

        replay_actions = [
            "meta:replay_status",
            "meta:replay_load",
            "meta:replay_stop",
            "meta:replay_peek",
        ]

        for action_id in replay_actions:
            spec = registry.get(action_id)
            assert spec is not None, f"Action {action_id} not registered"
            assert spec.executor is not None, f"Action {action_id} has no executor"


class TestRunLogReplayIntegration:
    """Test integration between RunLog and replay."""

    def setup_method(self):
        """Reset run log before each test."""
        reset_run_log()
        DiceRoller.set_replay_session(None)

    def teardown_method(self):
        """Clean up after each test."""
        DiceRoller.set_replay_session(None)

    def test_run_log_can_be_saved_and_replayed(self, tmp_path):
        """Verify a run log can be saved and then used for replay."""
        run_log = get_run_log()

        # Log some rolls
        run_log.log_roll("1d20", [17], 3, 20, "attack")
        run_log.log_roll("1d8", [6], 2, 8, "damage")

        # Save to file
        filepath = tmp_path / "session.json"
        run_log.save(str(filepath))

        # Load as replay session
        session = ReplaySession.load(str(filepath))
        session.start_replay()

        # Verify rolls are available
        roll1 = session.get_next_roll()
        assert roll1["total"] == 20
        assert roll1["reason"] == "attack"

        roll2 = session.get_next_roll()
        assert roll2["total"] == 8
        assert roll2["reason"] == "damage"

    def test_full_replay_cycle(self, tmp_path):
        """Test complete cycle: log rolls, save, load, replay."""
        run_log = get_run_log()

        # 1. Log some dice rolls (simulating a game session)
        run_log.log_roll("1d20", [15], 0, 15, "initiative")
        run_log.log_roll("1d20", [12], 5, 17, "attack roll")
        run_log.log_roll("2d6", [4, 3], 2, 9, "damage")

        # 2. Save the run log
        filepath = tmp_path / "game_session.json"
        run_log.save(str(filepath))

        # 3. Load as replay session
        session = ReplaySession.load(str(filepath))
        session.start_replay()
        DiceRoller.set_replay_session(session)

        # 4. Verify DiceRoller returns the exact same values
        roll1 = DiceRoller.roll("1d20")
        assert roll1.total == 15

        roll2 = DiceRoller.roll("1d20+5")
        assert roll2.total == 17

        roll3 = DiceRoller.roll("2d6+2")
        assert roll3.total == 9
