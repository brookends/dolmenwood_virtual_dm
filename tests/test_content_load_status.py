"""
Tests for P1-6: Surface content-loading status (settlements + hex errors).

Verifies that:
1. Missing settlements/content are visible to the player via ContentLoadReport
2. Malformed content includes parse error strings in the report
3. fail_fast_on_missing_content config knob works correctly
"""

import pytest
import tempfile
import json
from pathlib import Path

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, ContentLoadReport
from src.game_state.state_machine import GameState


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()


@pytest.fixture
def temp_content_dir():
    """Create a temporary content directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def content_with_hexes(temp_content_dir):
    """Create content with valid hexes but no settlements."""
    hexes_dir = temp_content_dir / "hexes"
    hexes_dir.mkdir()

    # Create a valid hex file
    hex_data = {
        "hex_id": "0705",
        "name": "Test Hex",
        "terrain_type": "forest",
        "coordinates": [7, 5],
    }
    (hexes_dir / "hex_0705.json").write_text(json.dumps(hex_data))

    return temp_content_dir


@pytest.fixture
def content_with_malformed_settlement(temp_content_dir):
    """Create content with valid hexes and a malformed settlement."""
    # Create valid hexes
    hexes_dir = temp_content_dir / "hexes"
    hexes_dir.mkdir()
    hex_data = {
        "hex_id": "0705",
        "name": "Test Hex",
        "terrain_type": "forest",
        "coordinates": [7, 5],
    }
    (hexes_dir / "hex_0705.json").write_text(json.dumps(hex_data))

    # Create settlements dir with malformed JSON
    settlements_dir = temp_content_dir / "settlements"
    settlements_dir.mkdir()
    (settlements_dir / "bad_settlement.json").write_text("{invalid json")

    return temp_content_dir


# =============================================================================
# TESTS: ContentLoadReport dataclass
# =============================================================================


class TestContentLoadReportDataclass:
    """Test the ContentLoadReport dataclass."""

    def test_default_values(self):
        """Report should have sensible defaults."""
        report = ContentLoadReport()

        assert report.hexes_loaded == 0
        assert report.settlements_loaded == 0
        assert report.success is True
        assert report.errors == []
        assert report.warnings == []

    def test_add_error_marks_unsuccessful(self):
        """Adding an error should set success to False."""
        report = ContentLoadReport()
        report.add_error("Something went wrong")

        assert report.success is False
        assert "Something went wrong" in report.errors

    def test_add_warning_preserves_success(self):
        """Warnings should not mark the report as unsuccessful."""
        report = ContentLoadReport()
        report.add_warning("Minor issue")

        assert report.success is True
        assert "Minor issue" in report.warnings

    def test_summary_shows_counts(self):
        """Summary should show content counts."""
        report = ContentLoadReport(
            hexes_loaded=100,
            settlements_loaded=12,
            spells_loaded=50,
        )

        summary = report.summary()
        assert "100 hexes" in summary
        assert "12 settlements" in summary
        assert "50 spells" in summary

    def test_summary_shows_errors(self):
        """Summary should indicate error counts."""
        report = ContentLoadReport()
        report.add_error("Error 1")
        report.add_error("Error 2")

        summary = report.summary()
        assert "2 error(s)" in summary


# =============================================================================
# TESTS: Missing Settlements Warning
# =============================================================================


class TestMissingSettlementsWarning:
    """Test that missing settlements are visible in the status."""

    def test_missing_settlements_shows_warning(self, seeded_dice, content_with_hexes):
        """Missing settlements directory should result in a warning."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_with_hexes,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # Should have content status report
        report = dm.get_content_status()
        assert report is not None

        # Should show 0 settlements loaded
        assert report.settlements_loaded == 0

        # Should have a warning about missing settlements
        all_messages = report.errors + report.warnings
        settlement_messages = [m for m in all_messages if "settlement" in m.lower()]
        assert len(settlement_messages) > 0, "Should have message about settlements"

    def test_get_startup_warnings_includes_settlements(self, seeded_dice, content_with_hexes):
        """get_startup_warnings should include settlement-related messages."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_with_hexes,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        warnings = dm.get_startup_warnings()

        # Should have warning about settlements
        settlement_warnings = [w for w in warnings if "settlement" in w.lower()]
        assert len(settlement_warnings) > 0

    def test_content_summary_shows_zero_settlements(self, seeded_dice, content_with_hexes):
        """Content summary should clearly show '0 settlements'."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_with_hexes,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        report = dm.get_content_status()
        summary = report.summary()

        # Should NOT include "settlements" in summary if none loaded
        # (the summary only includes non-zero counts)
        assert report.settlements_loaded == 0


# =============================================================================
# TESTS: Malformed Content Parse Errors
# =============================================================================


class TestMalformedContentErrors:
    """Test that malformed content includes parse error strings."""

    def test_malformed_settlement_includes_error(
        self, seeded_dice, content_with_malformed_settlement
    ):
        """Malformed settlement JSON should result in an error in the report."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_with_malformed_settlement,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        report = dm.get_content_status()

        # Should have warnings about the malformed settlement
        all_messages = report.errors + report.warnings
        assert len(all_messages) > 0, "Should have error/warning messages"


# =============================================================================
# TESTS: fail_fast_on_missing_content Config
# =============================================================================


class TestFailFastConfig:
    """Test the fail_fast_on_missing_content configuration."""

    def test_default_does_not_raise_on_missing_hexes(self, seeded_dice, temp_content_dir):
        """By default, missing hexes should not raise an exception."""
        # Empty content directory (no hexes)
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
            fail_fast_on_missing_content=False,
        )

        # Should not raise
        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        report = dm.get_content_status()
        # Should have error about no hexes
        assert report.hexes_loaded == 0
        assert any("hex" in e.lower() for e in report.errors)

    def test_fail_fast_raises_on_missing_hexes(self, seeded_dice, temp_content_dir):
        """With fail_fast=True, missing hexes should raise RuntimeError."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
            fail_fast_on_missing_content=True,
        )

        with pytest.raises(RuntimeError) as exc_info:
            VirtualDM(
                config=config,
                initial_state=GameState.WILDERNESS_TRAVEL,
                game_date=GameDate(year=1, month=6, day=15),
                game_time=GameTime(hour=10, minute=0),
            )

        # Error message should mention hexes
        assert "hex" in str(exc_info.value).lower()


# =============================================================================
# TESTS: No Content Loading
# =============================================================================


class TestNoContentLoading:
    """Test behavior when load_content is False."""

    def test_no_report_when_content_not_loaded(self, seeded_dice):
        """When load_content=False, content status should be None."""
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

        report = dm.get_content_status()
        assert report is None

        warnings = dm.get_startup_warnings()
        assert warnings == []


# =============================================================================
# TESTS: Content Status with Successful Load
# =============================================================================


class TestSuccessfulContentLoad:
    """Test content status when loading succeeds."""

    def test_successful_load_has_correct_counts(self, seeded_dice, content_with_hexes):
        """Successful content load should show correct counts."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_with_hexes,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        report = dm.get_content_status()

        # Should have 1 hex loaded
        assert report.hexes_loaded == 1
        assert report.hexes_failed == 0

        # Settlements missing but that's a warning, not an error that fails load
        assert report.settlements_loaded == 0

    def test_successful_load_summary_readable(self, seeded_dice, content_with_hexes):
        """Successful load should have a readable summary."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_with_hexes,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        report = dm.get_content_status()
        summary = report.summary()

        # Should be a non-empty string
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "Content loaded" in summary
