"""
Tests for POI alarm system including moose head alarm at Lady Borrid's Lodge.

This test suite validates:
- Unauthorized entry triggers alerts
- Alarms can be silenced with correct items
- Stealth entry bypasses entry conditions
- Alert tracking in POIVisit
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, GameDate
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine, POIVisit


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0109 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
    )
    assert result.success, f"Failed to load hex 0109: {result.errors}"
    return pipeline


@pytest.fixture
def controller():
    """Create a GlobalController."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=3, day=15)
    return controller


@pytest.fixture
def engine(controller, pipeline):
    """Create a HexCrawlEngine with hex 0109 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0109"] = pipeline.get_hex("0109")
    engine._current_hex = "0109"
    return engine


@pytest.fixture
def engine_at_lodge(engine):
    """Engine positioned at Lady Borrid's Hunting Lodge."""
    engine._current_poi = "Lady Borrid's Hunting Lodge"
    return engine


@pytest.fixture
def engine_at_camp(engine):
    """Engine positioned at Murkin's Army camp."""
    engine._current_poi = "Murkin's Army"
    return engine


# =============================================================================
# POI VISIT TRACKING TESTS
# =============================================================================


class TestPOIVisitAlarmTracking:
    """Test that POIVisit tracks alarm state."""

    def test_poi_visit_has_alarm_fields(self):
        """POIVisit should have alarm tracking fields."""
        visit = POIVisit(poi_name="Test POI")
        assert hasattr(visit, "alerts_triggered")
        assert hasattr(visit, "alarms_silenced")
        assert hasattr(visit, "entry_authorized")

    def test_poi_visit_defaults(self):
        """Alarm fields should default to False/empty."""
        visit = POIVisit(poi_name="Test POI")
        assert visit.alerts_triggered == []
        assert visit.alarms_silenced is False
        assert visit.entry_authorized is False


# =============================================================================
# UNAUTHORIZED ENTRY ALERT TESTS
# =============================================================================


class TestUnauthorizedEntryAlerts:
    """Test that unauthorized entry triggers alerts."""

    def test_lodge_has_moose_alarm(self, pipeline):
        """Lodge should have moose head alarm defined."""
        hex_data = pipeline.get_hex("0109")
        lodge = next(
            p for p in hex_data.points_of_interest
            if p.name == "Lady Borrid's Hunting Lodge"
        )
        assert len(lodge.alerts) >= 1
        moose_alarm = lodge.alerts[0]
        assert moose_alarm.get("alert_id") == "moose_head_alarm"
        assert moose_alarm.get("trigger") == "on_enter_unauthorized"

    def test_enter_without_permission_triggers_alert(self, engine_at_lodge):
        """Entering without permission should trigger unauthorized alert."""
        result = engine_at_lodge.enter_poi_with_conditions("0109", has_permission=False)

        assert result.get("allowed") is False
        assert result.get("triggers_alert") is True
        assert "alerts_triggered" in result or "alerts_suppressed" in result

    def test_alert_tracked_in_visit(self, engine_at_lodge):
        """Triggered alert should be recorded in POIVisit."""
        engine_at_lodge.enter_poi_with_conditions("0109", has_permission=False)

        visit_key = "0109:Lady Borrid's Hunting Lodge"
        visit = engine_at_lodge._poi_visits.get(visit_key)
        assert visit is not None
        assert "moose_head_alarm" in visit.alerts_triggered

    def test_enter_with_permission_no_alert(self, engine_at_lodge):
        """Entering with permission should not trigger alert."""
        result = engine_at_lodge.enter_poi_with_conditions("0109", has_permission=True)

        assert result.get("success") is True or result.get("allowed") is True
        assert "alerts_triggered" not in result

    def test_authorized_entry_tracked(self, engine_at_lodge):
        """Authorized entry should be marked in POIVisit."""
        engine_at_lodge.enter_poi_with_conditions("0109", has_permission=True)

        visit_key = "0109:Lady Borrid's Hunting Lodge"
        visit = engine_at_lodge._poi_visits.get(visit_key)
        assert visit is not None
        assert visit.entry_authorized is True


# =============================================================================
# SILENCE ALARM TESTS
# =============================================================================


class TestSilenceAlarm:
    """Test silencing alarms with correct items."""

    def test_silence_with_acorns(self, engine_at_lodge):
        """Moose head alarm can be silenced with acorns."""
        result = engine_at_lodge.silence_poi_alarm("0109", item_used="acorns")

        assert result.get("success") is True
        assert "moose_head_alarm" in result.get("silenced_alerts", [])

    def test_silence_marks_visit(self, engine_at_lodge):
        """Silencing alarm should mark POIVisit.alarms_silenced."""
        engine_at_lodge.silence_poi_alarm("0109", item_used="acorns")

        visit_key = "0109:Lady Borrid's Hunting Lodge"
        visit = engine_at_lodge._poi_visits.get(visit_key)
        assert visit is not None
        assert visit.alarms_silenced is True

    def test_wrong_item_fails(self, engine_at_lodge):
        """Using wrong item should fail."""
        result = engine_at_lodge.silence_poi_alarm("0109", item_used="rocks")

        assert result.get("success") is False
        assert "hint" in result or "error" in result

    def test_no_item_returns_requirements(self, engine_at_lodge):
        """No item should return bypass method hints."""
        result = engine_at_lodge.silence_poi_alarm("0109", item_used=None)

        assert result.get("success") is False
        assert result.get("requires_item") is True
        assert "bypass_methods" in result

    def test_silenced_alarm_suppresses_alerts(self, engine_at_lodge):
        """After silencing, unauthorized entry should not trigger alerts."""
        # First silence the alarm
        engine_at_lodge.silence_poi_alarm("0109", item_used="acorns")

        # Then try unauthorized entry
        result = engine_at_lodge.enter_poi_with_conditions("0109", has_permission=False)

        # Alerts should be suppressed
        assert result.get("alerts_suppressed") is True
        assert "alerts_triggered" not in result


# =============================================================================
# STEALTH ENTRY TESTS
# =============================================================================


class TestStealthEntry:
    """Test stealthy POI entry."""

    def test_stealth_entry_returns_roll_info(self, engine_at_lodge):
        """Stealth entry should return roll information."""
        result = engine_at_lodge.enter_poi_stealth("0109")

        # Should have roll info regardless of success
        assert "stealth_roll" in result or "success" in result

    def test_successful_stealth_enters_poi(self, engine_at_lodge):
        """Successful stealth should enter the POI."""
        # Mock dice to ensure success
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 20  # High roll ensures success
            mock_roll.return_value = mock_result

            result = engine_at_lodge.enter_poi_stealth("0109")

            assert result.get("stealth_success") is True
            assert "description" in result or "poi_type" in result

    def test_failed_stealth_triggers_alerts(self, engine_at_lodge):
        """Failed stealth should trigger unauthorized alerts."""
        # Mock dice to ensure failure
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 1  # Low roll ensures failure
            mock_roll.return_value = mock_result

            result = engine_at_lodge.enter_poi_stealth("0109")

            assert result.get("stealth_failed") is True
            assert "alerts_triggered" in result

    def test_stealth_at_camp_uses_sentry_count(self, engine_at_camp):
        """Stealth at camp should factor in sentry count."""
        result = engine_at_camp.enter_poi_stealth("0109")

        # Should have sentry info
        assert "stealth_dc" in result


# =============================================================================
# GET POI INFO TESTS
# =============================================================================


class TestGetPOIInfo:
    """Test get_poi_info method."""

    def test_returns_alert_info(self, engine_at_lodge):
        """Should return alert information."""
        info = engine_at_lodge.get_poi_info("0109")

        assert info is not None
        assert "alerts" in info
        assert len(info["alerts"]) >= 1

    def test_returns_silenceable_flag(self, engine_at_lodge):
        """Should indicate if alarms are silenceable."""
        info = engine_at_lodge.get_poi_info("0109")

        assert "has_silenceable_alarms" in info
        assert info["has_silenceable_alarms"] is True

    def test_returns_alarm_state(self, engine_at_lodge):
        """Should return current alarm state."""
        info = engine_at_lodge.get_poi_info("0109")

        assert "alarms_silenced" in info
        assert "alerts_triggered" in info

    def test_not_at_poi_returns_none(self, engine):
        """Should return None if not at a POI."""
        engine._current_poi = None
        info = engine.get_poi_info("0109")

        assert info is None


# =============================================================================
# CAMP SENTRY ALARM TESTS
# =============================================================================


class TestCampSentryAlarm:
    """Test sentry alarm at Murkin's Army camp."""

    def test_camp_has_sentry_alarm(self, pipeline):
        """Camp should have sentry alarm defined."""
        hex_data = pipeline.get_hex("0109")
        camp = next(
            p for p in hex_data.points_of_interest
            if p.name == "Murkin's Army"
        )
        assert len(camp.alerts) >= 1
        sentry_alarm = camp.alerts[0]
        assert sentry_alarm.get("alert_id") == "sentry_alarm"

    def test_camp_interrogation_failure_no_alert(self, engine_at_camp):
        """Camp interrogation failure should not trigger sentry alarm."""
        # Interrogation type uses social_result, not permission
        result = engine_at_camp.enter_poi_with_conditions(
            "0109", social_result="failure"
        )

        # Failure means "move along" not alarm
        assert result.get("allowed") is False
        assert result.get("triggers_alert") is not True

    def test_camp_hostile_triggers_combat(self, engine_at_camp):
        """Camp hostile result should trigger combat."""
        result = engine_at_camp.enter_poi_with_conditions(
            "0109", social_result="hostile"
        )

        assert result.get("allowed") is False
        assert result.get("triggers_combat") is True
