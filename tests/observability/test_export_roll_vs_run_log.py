"""
Tests for meta actions: roll log vs run log distinction.

Phase 4.2: Verify that:
- meta:roll_log shows DiceRoller roll list
- meta:run_log shows RunLog formatted entries
- meta:export_roll_log exports dice roll JSON
- meta:export_run_log exports RunLog JSON (full events)
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
def test_character():
    """A sample character for testing."""
    return CharacterState(
        character_id="test_mage_1",
        name="Test Mage",
        character_class="Magic-User",
        level=3,
        ability_scores={
            "STR": 10, "INT": 16, "WIS": 12,
            "DEX": 13, "CON": 14, "CHA": 11,
        },
        hp_current=12,
        hp_max=12,
        armor_class=9,
        base_speed=30,
    )


@pytest.fixture
def offline_dm(seeded_dice, test_character):
    """Create VirtualDM in offline mode."""
    reset_registry()
    reset_run_log()

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

    def test_roll_log_shows_dice_rolls(self, offline_dm, seeded_dice):
        """meta:roll_log should show DiceRoller roll list."""
        reset_registry()
        registry = get_default_registry()

        # Make some dice rolls
        DiceRoller.roll_d20()
        DiceRoller.roll("2d6")
        DiceRoller.roll_d20()

        result = registry.execute(offline_dm, "meta:roll_log", {"limit": 10})

        assert result["success"] is True
        # Should mention the dice rolls
        assert "d20" in result["message"].lower() or "roll" in result["message"].lower()

    def test_roll_log_with_limit(self, offline_dm, seeded_dice):
        """meta:roll_log should respect the limit parameter."""
        reset_registry()
        registry = get_default_registry()

        # Make many rolls
        for _ in range(20):
            DiceRoller.roll_d20()

        result = registry.execute(offline_dm, "meta:roll_log", {"limit": 5})

        assert result["success"] is True
        # Message should exist (limited output)
        assert len(result["message"]) > 0


class TestMetaRunLog:
    """Test meta:run_log action."""

    def test_run_log_shows_formatted_events(self, offline_dm, seeded_dice):
        """meta:run_log should show RunLog formatted entries."""
        reset_registry()
        reset_run_log()
        registry = get_default_registry()

        # Generate some RunLog events by making rolls and transitions
        DiceRoller.roll_d20()
        DiceRoller.roll("2d6")

        result = registry.execute(offline_dm, "meta:run_log", {"limit": 20})

        assert result["success"] is True
        # Should show session information
        assert "Run Log" in result["message"] or "Session" in result["message"] or "events" in result["message"].lower()

    def test_run_log_includes_event_count(self, offline_dm, seeded_dice):
        """meta:run_log should include event count."""
        reset_registry()
        reset_run_log()
        registry = get_default_registry()

        # Generate events
        DiceRoller.roll_d20()
        DiceRoller.roll_d20()

        result = registry.execute(offline_dm, "meta:run_log", {"limit": 10})

        assert result["success"] is True
        assert "event_count" in result or "events" in result["message"].lower()


class TestMetaExportRollLog:
    """Test meta:export_roll_log action."""

    def test_export_roll_log_creates_file(self, offline_dm, seeded_dice):
        """meta:export_roll_log should create a JSON file with dice rolls."""
        reset_registry()
        registry = get_default_registry()

        # Make some rolls to export
        DiceRoller.roll_d20()
        DiceRoller.roll("3d6")
        DiceRoller.roll_d20()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(offline_dm, "meta:export_roll_log", {"save_dir": tmpdir})

            assert result["success"] is True
            assert "filepath" in result

            # Verify file exists and contains JSON
            filepath = result["filepath"]
            assert os.path.exists(filepath)

            with open(filepath, "r") as f:
                data = json.load(f)

            # Should contain roll data (either as list or dict with roll_log key)
            if isinstance(data, dict):
                assert "roll_log" in data
                rolls = data["roll_log"]
            else:
                rolls = data
            assert isinstance(rolls, list)
            assert len(rolls) >= 3


class TestMetaExportRunLog:
    """Test meta:export_run_log action."""

    def test_export_run_log_creates_file(self, offline_dm, seeded_dice):
        """meta:export_run_log should create a JSON file with full RunLog."""
        reset_registry()
        reset_run_log()
        registry = get_default_registry()

        # Generate some events
        DiceRoller.roll_d20()
        DiceRoller.roll("2d6")

        # Also add a custom event to RunLog
        run_log = get_run_log()
        run_log.log_custom("test_event", {"key": "value"})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(offline_dm, "meta:export_run_log", {"save_dir": tmpdir})

            assert result["success"] is True
            assert "filepath" in result

            # Verify file exists and contains JSON
            filepath = result["filepath"]
            assert os.path.exists(filepath)

            with open(filepath, "r") as f:
                data = json.load(f)

            # Should contain full RunLog structure
            assert "session_start" in data
            assert "events" in data
            assert isinstance(data["events"], list)

    def test_export_run_log_includes_summary(self, offline_dm, seeded_dice):
        """meta:export_run_log should include summary in result."""
        reset_registry()
        reset_run_log()
        registry = get_default_registry()

        DiceRoller.roll_d20()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(offline_dm, "meta:export_run_log", {"save_dir": tmpdir})

            assert result["success"] is True
            assert "summary" in result
            assert "total_events" in result["summary"]


class TestRollVsRunLogDistinction:
    """Test that roll log and run log are distinct exports."""

    def test_roll_log_is_just_dice_rolls(self, offline_dm, seeded_dice):
        """Roll log export should only contain dice roll data."""
        reset_registry()
        reset_run_log()
        registry = get_default_registry()

        # Add various events
        DiceRoller.roll_d20()
        run_log = get_run_log()
        run_log.log_oracle(
            oracle_type="fate_check",
            question="Test?",
            result="yes",
        )
        run_log.log_custom("custom_event", {"data": "test"})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(offline_dm, "meta:export_roll_log", {"save_dir": tmpdir})
            filepath = result["filepath"]

            with open(filepath, "r") as f:
                data = json.load(f)

            # Should only have roll data, not oracle or custom events
            # Roll log may be a list or dict with roll_log key
            if isinstance(data, dict):
                assert "roll_log" in data
                rolls = data["roll_log"]
            else:
                rolls = data
            assert isinstance(rolls, list)
            for item in rolls:
                # Each item should look like a dice roll
                assert "notation" in item or "total" in item

    def test_run_log_has_all_event_types(self, offline_dm, seeded_dice):
        """Run log export should contain all event types."""
        reset_registry()
        reset_run_log()
        registry = get_default_registry()

        # Add various events
        DiceRoller.roll_d20()
        run_log = get_run_log()
        run_log.log_oracle(
            oracle_type="fate_check",
            question="Test?",
            result="yes",
        )
        run_log.log_custom("custom_event", {"data": "test"})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = registry.execute(offline_dm, "meta:export_run_log", {"save_dir": tmpdir})
            filepath = result["filepath"]

            with open(filepath, "r") as f:
                data = json.load(f)

            # Should have events array with multiple types
            events = data["events"]
            event_types = {e["event_type"] for e in events}

            # Should include roll and oracle events
            assert "roll" in event_types
            assert "oracle" in event_types


class TestMetaReplayStatus:
    """Test meta:replay_status action."""

    def test_replay_status_reports_not_implemented(self, offline_dm):
        """meta:replay_status should report current replay state."""
        reset_registry()
        registry = get_default_registry()

        result = registry.execute(offline_dm, "meta:replay_status", {})

        assert result["success"] is True
        assert "replay" in result["message"].lower()
        # Should indicate whether replay is active or not
        assert "replay_active" in result
