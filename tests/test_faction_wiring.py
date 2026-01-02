"""
Tests for faction system wiring to VirtualDM.

Step 3 acceptance criteria:
- Faction engine initializes when content is loaded
- Faction state persists in save/load cycle
- meta:factions action returns formatted status
- Day advancement triggers faction cycles
"""

import pytest
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

from src.factions import (
    FactionEngine,
    FactionRules,
    FactionDefinition,
    FactionTurnState,
    PartyFactionState,
    get_factions_summary,
    get_party_faction_summary,
    save_faction_state,
    load_faction_state,
)
from src.factions.faction_wiring import init_faction_engine


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_rules() -> FactionRules:
    """Create sample faction rules."""
    return FactionRules(
        schema_version=1,
        turn_cadence_days=7,
    )


@pytest.fixture
def sample_engine(sample_rules: FactionRules) -> FactionEngine:
    """Create a sample faction engine."""
    definition = FactionDefinition(
        faction_id="test_faction",
        name="Test Faction",
        description="A test faction for wiring tests",
    )
    engine = FactionEngine(
        rules=sample_rules,
        definitions={"test_faction": definition},
    )
    engine.set_party_state(PartyFactionState())
    return engine


# =============================================================================
# PERSISTENCE TESTS
# =============================================================================


class TestFactionPersistence:
    """Tests for save/load of faction state."""

    def test_save_faction_state(self, sample_engine: FactionEngine):
        """Test saving faction state to custom_data."""
        custom_data: dict[str, Any] = {}

        save_faction_state(sample_engine, custom_data)

        assert "faction_state" in custom_data
        assert "faction_states" in custom_data["faction_state"]
        assert "test_faction" in custom_data["faction_state"]["faction_states"]

    def test_save_none_engine(self):
        """Test saving with None engine."""
        custom_data: dict[str, Any] = {}

        save_faction_state(None, custom_data)

        assert "faction_state" not in custom_data

    def test_load_faction_state(self, sample_engine: FactionEngine):
        """Test loading faction state from custom_data."""
        # Save state first
        custom_data: dict[str, Any] = {}
        sample_engine._cycles_completed = 5
        sample_engine._days_accumulated = 3
        save_faction_state(sample_engine, custom_data)

        # Create new engine and load state
        new_engine = FactionEngine(
            rules=sample_engine.rules,
            definitions=sample_engine.definitions,
        )

        result = load_faction_state(new_engine, custom_data)

        assert result is True
        assert new_engine.cycles_completed == 5
        assert new_engine.days_accumulated == 3

    def test_load_missing_state(self, sample_engine: FactionEngine):
        """Test loading when faction_state is not in custom_data."""
        result = load_faction_state(sample_engine, {})
        assert result is False

    def test_load_none_engine(self):
        """Test loading with None engine."""
        result = load_faction_state(None, {"faction_state": {}})
        assert result is False


# =============================================================================
# SUMMARY TESTS
# =============================================================================


class TestFactionsSummary:
    """Tests for faction status summaries."""

    def test_get_factions_summary(self, sample_engine: FactionEngine):
        """Test getting faction summary."""
        summary = get_factions_summary(sample_engine)

        assert "FACTION STATUS" in summary
        assert "Cycles completed:" in summary
        assert "Test Faction" in summary

    def test_get_factions_summary_none_engine(self):
        """Test getting summary with None engine."""
        summary = get_factions_summary(None)

        assert "not initialized" in summary

    def test_get_party_faction_summary(self, sample_engine: FactionEngine):
        """Test getting party faction summary."""
        sample_engine.party_state.adjust_standing("test_faction", 3)

        summary = get_party_faction_summary(sample_engine)

        assert "PARTY FACTION STANDING" in summary
        assert "test_faction" in summary
        assert "+3" in summary

    def test_get_party_faction_summary_no_standings(self, sample_engine: FactionEngine):
        """Test party summary with no standings."""
        summary = get_party_faction_summary(sample_engine)

        assert "No faction standings" in summary

    def test_get_party_faction_summary_none_engine(self):
        """Test party summary with None engine."""
        summary = get_party_faction_summary(None)

        assert "No party faction relationships" in summary


# =============================================================================
# WIRING INITIALIZATION TESTS
# =============================================================================


class TestFactionWiringInit:
    """Tests for faction engine initialization via wiring."""

    @pytest.fixture
    def content_root(self) -> Path:
        """Get the content root path."""
        return Path(__file__).parent.parent / "data" / "content"

    def test_init_returns_engine_when_content_exists(self, content_root: Path):
        """Test that init returns engine when factions directory exists."""
        if not (content_root / "factions").exists():
            pytest.skip("Factions directory not found")

        # Create mock VirtualDM
        mock_dm = MagicMock()
        mock_dm.controller.time_tracker.register_day_callback = MagicMock()
        mock_dm.controller.time_tracker.game_date.year = 1
        mock_dm.controller.time_tracker.game_date.month = 1
        mock_dm.controller.time_tracker.game_date.day = 1

        engine = init_faction_engine(
            mock_dm,
            content_root,
            register_time_callback=True,
        )

        assert engine is not None
        assert len(engine.faction_states) > 0

    def test_init_returns_none_when_no_factions_dir(self, tmp_path: Path):
        """Test that init returns None when factions directory is missing."""
        mock_dm = MagicMock()

        engine = init_faction_engine(mock_dm, tmp_path)

        assert engine is None

    def test_init_registers_time_callback(self, content_root: Path):
        """Test that init registers day callback with TimeTracker."""
        if not (content_root / "factions").exists():
            pytest.skip("Factions directory not found")

        mock_dm = MagicMock()
        callback_holder = []
        mock_dm.controller.time_tracker.register_day_callback = lambda cb: callback_holder.append(cb)
        mock_dm.controller.time_tracker.game_date.year = 1
        mock_dm.controller.time_tracker.game_date.month = 1
        mock_dm.controller.time_tracker.game_date.day = 1

        engine = init_faction_engine(
            mock_dm,
            content_root,
            register_time_callback=True,
        )

        assert len(callback_holder) == 1
        # Verify callback is callable
        assert callable(callback_holder[0])

    def test_init_without_time_callback(self, content_root: Path):
        """Test that init can skip time callback registration."""
        if not (content_root / "factions").exists():
            pytest.skip("Factions directory not found")

        mock_dm = MagicMock()

        engine = init_faction_engine(
            mock_dm,
            content_root,
            register_time_callback=False,
        )

        assert engine is not None
        # Verify callback was not registered
        mock_dm.controller.time_tracker.register_day_callback.assert_not_called()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestFactionIntegration:
    """Integration tests for faction wiring."""

    @pytest.fixture
    def content_root(self) -> Path:
        """Get the content root path."""
        return Path(__file__).parent.parent / "data" / "content"

    def test_day_callback_triggers_cycle(self, content_root: Path):
        """Test that day callback triggers faction cycle at cadence."""
        if not (content_root / "factions").exists():
            pytest.skip("Factions directory not found")

        from src.data_models import DiceRoller
        DiceRoller.set_seed(42)

        mock_dm = MagicMock()
        callback_holder = []
        mock_dm.controller.time_tracker.register_day_callback = lambda cb: callback_holder.append(cb)
        mock_dm.controller.time_tracker.game_date.year = 1
        mock_dm.controller.time_tracker.game_date.month = 1
        mock_dm.controller.time_tracker.game_date.day = 1

        engine = init_faction_engine(
            mock_dm,
            content_root,
            register_time_callback=True,
        )

        assert engine is not None
        assert engine.cycles_completed == 0

        # Advance 7 days via callback
        callback = callback_holder[0]
        callback(7)

        assert engine.cycles_completed == 1

    def test_full_save_load_cycle(self, content_root: Path):
        """Test full save/load cycle with faction state."""
        if not (content_root / "factions").exists():
            pytest.skip("Factions directory not found")

        from src.data_models import DiceRoller
        DiceRoller.set_seed(42)

        mock_dm = MagicMock()
        mock_dm.controller.time_tracker.register_day_callback = MagicMock()
        mock_dm.controller.time_tracker.game_date.year = 1
        mock_dm.controller.time_tracker.game_date.month = 1
        mock_dm.controller.time_tracker.game_date.day = 1

        engine = init_faction_engine(
            mock_dm,
            content_root,
            register_time_callback=False,
        )

        # Run some cycles
        engine.run_cycle()
        engine.run_cycle()

        # Adjust party standing
        engine.party_state.adjust_standing("drune", 5)

        # Save state
        custom_data: dict[str, Any] = {}
        save_faction_state(engine, custom_data)

        # Create new engine and load
        mock_dm2 = MagicMock()
        mock_dm2.controller.time_tracker.register_day_callback = MagicMock()
        mock_dm2.controller.time_tracker.game_date.year = 1
        mock_dm2.controller.time_tracker.game_date.month = 1
        mock_dm2.controller.time_tracker.game_date.day = 1

        new_engine = init_faction_engine(
            mock_dm2,
            content_root,
            register_time_callback=False,
        )

        load_faction_state(new_engine, custom_data)

        # Verify state restored
        assert new_engine.cycles_completed == 2
        assert new_engine.party_state.get_standing("drune") == 5
