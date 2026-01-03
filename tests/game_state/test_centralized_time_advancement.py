"""
Tests for P2-10: Centralized turn/time advancement.

Verifies that:
1. GlobalController.advance_time is the centralized API
2. Time advancement emits RunLog events
3. Resource consumption is tracked (food, light sources)
4. Conditions are ticked correctly
5. Reason strings are logged for observability
"""

import pytest

from src.game_state.global_controller import GlobalController
from src.data_models import (
    GameDate,
    GameTime,
    DiceRoller,
    LightSourceType,
    CharacterState,
    ConditionType,
    Condition,
)
from src.observability.run_log import get_run_log, reset_run_log, EventType


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
def controller():
    """Create a fresh GlobalController."""
    reset_run_log()
    return GlobalController()


@pytest.fixture
def controller_with_character():
    """Create a GlobalController with a character for condition tests."""
    reset_run_log()
    ctrl = GlobalController()

    char = CharacterState(
        character_id="test_fighter",
        name="Test Fighter",
        character_class="Fighter",
        level=3,
        hp_current=24,
        hp_max=24,
        armor_class=4,
        base_speed=30,
        ability_scores={
            "STR": 16, "INT": 10, "WIS": 12,
            "DEX": 14, "CON": 15, "CHA": 11
        },
    )
    ctrl.add_character(char)
    return ctrl


# =============================================================================
# TESTS: RunLog Integration
# =============================================================================


class TestRunLogIntegration:
    """Test that advance_time emits RunLog events."""

    def test_advance_time_emits_time_step_event(self, controller):
        """advance_time should emit a TIME_STEP event to RunLog."""
        run_log = get_run_log()

        controller.advance_time(1)

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        assert len(time_events) == 1

    def test_time_step_event_has_correct_times(self, controller):
        """TIME_STEP event should have old_time and new_time."""
        run_log = get_run_log()

        controller.advance_time(6)  # 1 hour

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        assert len(time_events) == 1

        event = time_events[0]
        assert event.old_time == "08:00"  # Default start time
        assert event.new_time == "09:00"  # 1 hour later

    def test_time_step_event_records_turns_and_minutes(self, controller):
        """TIME_STEP event should record turns and minutes advanced."""
        run_log = get_run_log()

        controller.advance_time(12)  # 2 hours = 12 turns

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        event = time_events[0]

        assert event.turns_advanced == 12
        assert event.minutes_advanced == 120

    def test_time_step_event_includes_reason(self, controller):
        """TIME_STEP event should include the reason string."""
        run_log = get_run_log()

        controller.advance_time(1, reason="dungeon exploration")

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        event = time_events[0]

        assert event.reason == "dungeon exploration"

    def test_multiple_advances_emit_multiple_events(self, controller):
        """Multiple calls should emit multiple TIME_STEP events."""
        run_log = get_run_log()

        controller.advance_time(1)
        controller.advance_time(3)
        controller.advance_time(6)

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        assert len(time_events) == 3


# =============================================================================
# TESTS: Light Source Depletion
# =============================================================================


class TestLightSourceDepletion:
    """Test that light sources are depleted during time advancement."""

    def test_torch_depletes_over_turns(self, controller):
        """Torch should deplete as turns pass."""
        # Light a torch (6 turns duration)
        controller.party_state.active_light_source = LightSourceType.TORCH
        controller.party_state.light_remaining_turns = 6

        controller.advance_time(3)

        assert controller.party_state.light_remaining_turns == 3

    def test_torch_extinguishes_when_depleted(self, controller):
        """Torch should extinguish when turns reach zero."""
        controller.party_state.active_light_source = LightSourceType.TORCH
        controller.party_state.light_remaining_turns = 3

        result = controller.advance_time(5)

        assert controller.party_state.active_light_source is None
        assert controller.party_state.light_remaining_turns == 0
        assert result.get("light_extinguished") is True
        assert result.get("light_source") == LightSourceType.TORCH.value

    def test_lantern_depletes_slowly(self, controller):
        """Lantern should deplete as turns pass."""
        controller.party_state.active_light_source = LightSourceType.LANTERN
        controller.party_state.light_remaining_turns = 144  # 4 hours

        controller.advance_time(24)  # 4 turns = 40 minutes

        assert controller.party_state.light_remaining_turns == 120


# =============================================================================
# TESTS: Condition Ticking
# =============================================================================


class TestConditionTicking:
    """Test that character conditions are ticked during time advancement."""

    def test_condition_duration_decreases(self, controller_with_character):
        """Condition duration should decrease as turns pass."""
        char = controller_with_character.get_character("test_fighter")
        char.conditions.append(
            Condition(
                condition_type=ConditionType.BLINDED,
                duration_turns=10,
                source="test",
            )
        )

        controller_with_character.advance_time(3)

        assert char.conditions[0].duration_turns == 7

    def test_expired_conditions_returned(self, controller_with_character):
        """Expired conditions should be returned in result."""
        char = controller_with_character.get_character("test_fighter")
        char.conditions.append(
            Condition(
                condition_type=ConditionType.PARALYZED,
                duration_turns=2,
                source="spell",
            )
        )

        result = controller_with_character.advance_time(5)

        # Condition should have expired
        assert result.get("expired_conditions") is not None
        assert len(result["expired_conditions"]) > 0


# =============================================================================
# TESTS: Time Calculations
# =============================================================================


class TestTimeCalculations:
    """Test correct time calculations."""

    def test_advance_turns(self, controller):
        """Time should advance correctly by turns."""
        result = controller.advance_time(6)  # 1 hour

        assert result["turns_advanced"] == 6
        assert "09:00" in result["new_time"]

    def test_advance_day_boundary(self, controller):
        """Time should handle day boundary correctly."""
        # Start at 8:00, advance 100 turns (16h40m) to cross midnight
        result = controller.advance_time(100)

        assert result["days_passed"] == 1

    def test_advance_watch_tracking(self, controller):
        """Watch threshold should be tracked."""
        # Advance 24 turns = 1 watch
        result = controller.advance_time(24)

        assert result["watches_passed"] == 1


# =============================================================================
# TESTS: Context in RunLog
# =============================================================================


class TestRunLogContext:
    """Test that context data is included in RunLog events."""

    def test_context_includes_days_passed(self, controller):
        """Context should include days_passed."""
        run_log = get_run_log()

        controller.advance_time(150)  # More than 1 day

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        event = time_events[0]

        assert "days_passed" in event.context
        assert event.context["days_passed"] >= 1

    def test_context_includes_watches_passed(self, controller):
        """Context should include watches_passed."""
        run_log = get_run_log()

        controller.advance_time(24)  # 1 watch

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        event = time_events[0]

        assert "watches_passed" in event.context
        assert event.context["watches_passed"] == 1

    def test_context_includes_light_extinguished(self, controller):
        """Context should include light_extinguished flag."""
        run_log = get_run_log()

        controller.party_state.active_light_source = LightSourceType.TORCH
        controller.party_state.light_remaining_turns = 2
        controller.advance_time(5)

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        event = time_events[0]

        assert event.context["light_extinguished"] is True


# =============================================================================
# TESTS: Convenience Methods
# =============================================================================


class TestConvenienceMethods:
    """Test that convenience methods pass through reason strings."""

    def test_advance_travel_segment_logs_reason(self, controller):
        """advance_travel_segment should log with reason."""
        run_log = get_run_log()

        controller.advance_travel_segment()

        time_events = [e for e in run_log._events if e.event_type == EventType.TIME_STEP]
        assert len(time_events) == 1
        assert "travel segment" in time_events[0].reason


# =============================================================================
# TESTS: Determinism
# =============================================================================


class TestDeterministicTimeAdvancement:
    """Test that time advancement is deterministic."""

    def test_same_inputs_produce_same_outputs(self, seeded_dice):
        """Same inputs should produce identical outputs."""
        reset_run_log()
        controller1 = GlobalController()
        result1 = controller1.advance_time(10, reason="test")

        reset_run_log()
        controller2 = GlobalController()
        result2 = controller2.advance_time(10, reason="test")

        assert result1["turns_advanced"] == result2["turns_advanced"]
        assert result1["new_time"] == result2["new_time"]
        assert result1["days_passed"] == result2["days_passed"]
