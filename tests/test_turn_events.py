"""
Tests for turn-based event tracking system.

These tests verify that turn-based events (like delayed monster arrivals)
can be scheduled, tracked, and triggered correctly.
"""

import pytest
from unittest.mock import MagicMock


class TestPendingTurnEventDataclass:
    """Tests for the PendingTurnEvent dataclass."""

    def test_create_event(self):
        """Verify event can be created with required fields."""
        from src.data_models import PendingTurnEvent

        event = PendingTurnEvent(
            event_id="test1",
            event_type="monster_arrival",
            description="Frore gryphus arrives",
            trigger_in_turns=1,
            created_turn=5,
            target_turn=6,
            monster_id="frore_gryphus",
        )

        assert event.event_id == "test1"
        assert event.event_type == "monster_arrival"
        assert event.target_turn == 6
        assert event.monster_id == "frore_gryphus"
        assert not event.triggered
        assert not event.cancelled

    def test_should_trigger(self):
        """Verify trigger timing logic."""
        from src.data_models import PendingTurnEvent

        event = PendingTurnEvent(
            event_id="test1",
            event_type="monster_arrival",
            trigger_in_turns=1,
            created_turn=5,
            target_turn=6,
        )

        assert not event.should_trigger(5)  # Before target
        assert event.should_trigger(6)  # At target
        assert event.should_trigger(7)  # After target

    def test_should_not_trigger_if_already_triggered(self):
        """Verify triggered events don't trigger again."""
        from src.data_models import PendingTurnEvent

        event = PendingTurnEvent(
            event_id="test1",
            event_type="monster_arrival",
            trigger_in_turns=1,
            created_turn=5,
            target_turn=6,
            triggered=True,
        )

        assert not event.should_trigger(6)

    def test_should_not_trigger_if_cancelled(self):
        """Verify cancelled events don't trigger."""
        from src.data_models import PendingTurnEvent

        event = PendingTurnEvent(
            event_id="test1",
            event_type="monster_arrival",
            trigger_in_turns=1,
            created_turn=5,
            target_turn=6,
            cancelled=True,
        )

        assert not event.should_trigger(6)

    def test_serialization_roundtrip(self):
        """Verify event can serialize and deserialize."""
        from src.data_models import PendingTurnEvent

        event = PendingTurnEvent(
            event_id="test1",
            event_type="monster_arrival",
            description="Test event",
            trigger_in_turns=2,
            created_turn=10,
            target_turn=12,
            hex_id="0105",
            poi_name="The Nest",
            monster_id="frore_gryphus",
            monster_count=1,
            monster_context="It arrives!",
        )

        data = event.to_dict()
        restored = PendingTurnEvent.from_dict(data)

        assert restored.event_id == event.event_id
        assert restored.target_turn == event.target_turn
        assert restored.monster_id == event.monster_id
        assert restored.monster_context == event.monster_context

    def test_check_recurring_probability(self):
        """Verify recurring probability check logic."""
        from src.data_models import PendingTurnEvent

        event = PendingTurnEvent(
            event_id="test1",
            event_type="monster_arrival",
            check_each_turn=True,
            check_probability="1-3",
            check_die="d6",
        )

        # Should trigger on rolls 1, 2, 3
        assert event.check_recurring(1)
        assert event.check_recurring(2)
        assert event.check_recurring(3)

        # Should not trigger on rolls 4, 5, 6
        assert not event.check_recurring(4)
        assert not event.check_recurring(5)
        assert not event.check_recurring(6)


class TestSessionManagerTurnEvents:
    """Tests for SessionManager turn event methods."""

    def test_schedule_turn_event(self):
        """Verify turn event can be scheduled."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        event = manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=1,
            current_turn=5,
            hex_id="0105",
            poi_name="The Nest",
            monster_id="frore_gryphus",
            monster_count=1,
            monster_context="It arrives!",
        )

        assert event is not None
        assert event["event_type"] == "monster_arrival"
        assert event["target_turn"] == 6
        assert event["monster_id"] == "frore_gryphus"
        assert len(manager._current_session.pending_turn_events) == 1

    def test_process_turn_events_triggers_at_correct_time(self):
        """Verify events trigger at the correct turn."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=2,
            current_turn=5,
            monster_id="frore_gryphus",
        )

        # Turn 5 - too early
        triggered = manager.process_turn_events(5)
        assert len(triggered) == 0

        # Turn 6 - still too early
        triggered = manager.process_turn_events(6)
        assert len(triggered) == 0

        # Turn 7 - should trigger
        triggered = manager.process_turn_events(7)
        assert len(triggered) == 1
        assert triggered[0]["monster_id"] == "frore_gryphus"

    def test_process_turn_events_with_recurring_check(self):
        """Verify recurring events check each turn."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=0,  # Check immediately
            current_turn=5,
            monster_id="frore_gryphus",
            check_each_turn=True,
            check_probability="1-3",
            check_die="d6",
        )

        # Mock dice roller that returns 4 (no trigger)
        dice = MagicMock()
        dice.roll.return_value = MagicMock(total=4)

        triggered = manager.process_turn_events(5, dice_roller=dice)
        assert len(triggered) == 0

        # Try again with roll of 2 (triggers)
        dice.roll.return_value = MagicMock(total=2)
        triggered = manager.process_turn_events(6, dice_roller=dice)
        assert len(triggered) == 1

    def test_cancel_turn_event(self):
        """Verify events can be cancelled."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        event = manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=1,
            current_turn=5,
        )

        result = manager.cancel_turn_event(event["event_id"])
        assert result is True

        # Cancelled event should not trigger
        triggered = manager.process_turn_events(6)
        assert len(triggered) == 0

    def test_cancel_poi_events(self):
        """Verify all events at a POI can be cancelled."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        # Schedule two events at same POI
        manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=1,
            current_turn=5,
            hex_id="0105",
            poi_name="The Nest",
        )
        manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=2,
            current_turn=5,
            hex_id="0105",
            poi_name="The Nest",
        )
        # One event at different POI
        manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=1,
            current_turn=5,
            hex_id="0105",
            poi_name="Other POI",
        )

        count = manager.cancel_poi_events("0105", "The Nest")
        assert count == 2

        # Only the "Other POI" event should remain active
        pending = manager.get_pending_turn_events()
        assert len(pending) == 1
        assert pending[0]["poi_name"] == "Other POI"

    def test_cleanup_old_turn_events(self):
        """Verify triggered and cancelled events are removed."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        # Schedule and trigger an event
        manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=0,
            current_turn=5,
        )
        manager.process_turn_events(5)

        # Schedule and cancel an event
        event = manager.schedule_turn_event(
            event_type="monster_arrival",
            trigger_in_turns=1,
            current_turn=5,
        )
        manager.cancel_turn_event(event["event_id"])

        assert len(manager._current_session.pending_turn_events) == 2

        removed = manager.cleanup_old_turn_events()
        assert removed == 2
        assert len(manager._current_session.pending_turn_events) == 0


class TestSessionSerialization:
    """Tests for turn event persistence in session."""

    def test_pending_turn_events_serialized(self):
        """Verify pending turn events are included in session serialization."""
        from src.game_state.session_manager import GameSession

        session = GameSession(
            session_id="test",
            session_name="Test Session",
            pending_turn_events=[
                {
                    "event_id": "test1",
                    "event_type": "monster_arrival",
                    "target_turn": 10,
                }
            ],
        )

        data = session.to_dict()

        assert "pending_turn_events" in data
        assert len(data["pending_turn_events"]) == 1

    def test_pending_turn_events_deserialized(self):
        """Verify pending turn events are restored from session data."""
        from src.game_state.session_manager import GameSession

        data = {
            "session_id": "test",
            "session_name": "Test Session",
            "pending_turn_events": [
                {
                    "event_id": "test1",
                    "event_type": "monster_arrival",
                    "target_turn": 10,
                    "monster_id": "frore_gryphus",
                }
            ],
        }

        session = GameSession.from_dict(data)

        assert len(session.pending_turn_events) == 1
        assert session.pending_turn_events[0]["monster_id"] == "frore_gryphus"
