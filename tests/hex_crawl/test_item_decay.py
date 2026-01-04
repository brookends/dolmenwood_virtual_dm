"""
Tests for item decay functionality (Task 6.2).

Tests that items with decay properties (like Golden Eggs with 4d6 days decay)
properly schedule decay events and mutate on the correct day.
"""

import pytest
from pathlib import Path

from src.content_loader.hex_loader import HexDataLoader
from src.content_loader.content_pipeline import ContentPipeline
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import (
    DiceRoller,
    GameDate,
    EventType,
    EventScheduler,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def controller():
    """Create a GlobalController with a known date."""
    ctrl = GlobalController()
    # Set initial date
    ctrl.world_state.current_date = GameDate(year=1, month=1, day=1)
    return ctrl


@pytest.fixture
def hex_engine(controller):
    """Create a HexCrawlEngine."""
    engine = HexCrawlEngine(controller)
    return engine


@pytest.fixture
def seeded_dice():
    """Provide a seeded DiceRoller for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield DiceRoller()
    DiceRoller.clear_roll_log()
    DiceRoller._seed = None  # Reset seed


@pytest.fixture
def golden_egg_item():
    """A Golden Egg item with decay properties."""
    return {
        "item_id": "0103:item:golden_egg",
        "name": "Golden Egg",
        "quantity": 1,
        "value_gp": 40,
        "notes": "Induces a subtle, covetous feeling in those who see it.",
        "decay_dice": "4d6",
        "decay_unit": "days",
    }


# =============================================================================
# EVENT SCHEDULER TESTS
# =============================================================================


class TestScheduleItemDecay:
    """Test EventScheduler.schedule_item_decay method."""

    def test_schedule_item_decay_creates_event(self, seeded_dice):
        """schedule_item_decay should create a decay event."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        event = scheduler.schedule_item_decay(
            item_id="test_egg_1",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
            source_hex_id="0103",
            source_poi_name="Crocus's Cave",
        )

        assert event is not None
        assert event.event_type == EventType.ITEM_DECAY
        assert event.effect_details["item_id"] == "test_egg_1"
        assert event.effect_details["item_name"] == "Golden Egg"
        assert event.days_until_trigger is not None
        assert event.trigger_date is not None

    def test_schedule_item_decay_uses_seeded_dice(self, seeded_dice):
        """Decay timer should be deterministic with seeded dice."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        # With seed 42, 4d6 should give consistent result
        event = scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # Record the first roll
        first_days = event.days_until_trigger

        # Reset and try again with same seed
        DiceRoller.set_seed(42)
        scheduler2 = EventScheduler()

        event2 = scheduler2.schedule_item_decay(
            item_id="test_egg_2",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # Should get same number of days
        assert event2.days_until_trigger == first_days

    def test_schedule_item_decay_range_valid(self, seeded_dice):
        """4d6 days should be between 4 and 24."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        event = scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # 4d6 minimum is 4, maximum is 24
        assert 4 <= event.days_until_trigger <= 24

    def test_schedule_item_decay_trigger_date_correct(self, seeded_dice):
        """Trigger date should be current date + days rolled."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        event = scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        expected_date = current_date.advance_days(event.days_until_trigger)
        assert event.trigger_date.year == expected_date.year
        assert event.trigger_date.month == expected_date.month
        assert event.trigger_date.day == expected_date.day


class TestCheckItemDecays:
    """Test checking and triggering item decay events."""

    def test_check_item_decays_not_triggered_early(self, seeded_dice):
        """Decay should not trigger before the scheduled date."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        event = scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # Check decay one day before trigger
        days_until = event.days_until_trigger
        check_date = current_date.advance_days(days_until - 1)

        triggered = scheduler.check_item_decays(check_date)
        assert len(triggered) == 0

    def test_check_item_decays_triggers_on_date(self, seeded_dice):
        """Decay should trigger on the scheduled date."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        event = scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # Check decay on trigger date
        triggered = scheduler.check_item_decays(event.trigger_date)

        assert len(triggered) == 1
        assert triggered[0]["effect_details"]["item_id"] == "test_egg"
        assert triggered[0]["effect_type"] == "item_decay"

    def test_check_item_decays_triggers_after_date(self, seeded_dice):
        """Decay should also trigger if checked after the date."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        event = scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # Check decay one day after trigger
        check_date = event.trigger_date.advance_days(1)
        triggered = scheduler.check_item_decays(check_date)

        assert len(triggered) == 1

    def test_check_item_decays_only_triggers_once(self, seeded_dice):
        """Decay should only trigger once."""
        scheduler = EventScheduler()
        current_date = GameDate(year=1, month=1, day=1)

        scheduler.schedule_item_decay(
            item_id="test_egg",
            item_name="Golden Egg",
            decay_dice="4d6",
            current_date=current_date,
        )

        # Get the trigger date
        event = scheduler.events[0]
        trigger_date = event.trigger_date

        # First check triggers
        triggered1 = scheduler.check_item_decays(trigger_date)
        assert len(triggered1) == 1

        # Second check should not trigger (already triggered)
        triggered2 = scheduler.check_item_decays(trigger_date)
        assert len(triggered2) == 0


# =============================================================================
# HEX CRAWL ENGINE INTEGRATION TESTS
# =============================================================================


class TestAcquireItem:
    """Test HexCrawlEngine.acquire_item method."""

    def test_acquire_item_adds_to_inventory(self, hex_engine, golden_egg_item, seeded_dice):
        """Acquiring an item should add it to party inventory."""
        result = hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        assert result["success"] is True
        assert result["item"]["name"] == "Golden Egg"

        party_state = hex_engine.controller.party_state
        assert len(party_state.party_inventory) == 1
        assert party_state.party_inventory[0]["name"] == "Golden Egg"

    def test_acquire_item_schedules_decay(self, hex_engine, golden_egg_item, seeded_dice):
        """Acquiring a decaying item should schedule a decay event."""
        result = hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        assert result["scheduled_decay"] is not None
        assert result["scheduled_decay"]["days_until"] is not None
        assert 4 <= result["scheduled_decay"]["days_until"] <= 24

    def test_acquire_item_without_decay(self, hex_engine, seeded_dice):
        """Acquiring a non-decaying item should not schedule decay."""
        normal_item = {
            "item_id": "test:silver_sword",
            "name": "Silver Sword",
            "value_gp": 100,
        }

        result = hex_engine.acquire_item(
            hex_id="0103",
            item=normal_item,
            poi_name="Crocus's Cave",
        )

        assert result["success"] is True
        assert result["scheduled_decay"] is None


class TestProcessItemDecays:
    """Test processing item decay events."""

    def test_process_item_decays_marks_item(self, hex_engine, golden_egg_item, seeded_dice):
        """Processing decay should mark item as decayed in inventory."""
        # Acquire the item
        result = hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        instance_id = result["instance_id"]
        days_until = result["scheduled_decay"]["days_until"]

        # Advance time to decay date
        hex_engine.controller.world_state.current_date = GameDate(year=1, month=1, day=1).advance_days(
            days_until
        )

        # Process decays
        decayed = hex_engine.process_item_decays()

        assert len(decayed) == 1
        assert decayed[0]["item_name"] == "Golden Egg"
        assert decayed[0]["decay_result"] == "dust"

        # Check inventory was updated
        party_state = hex_engine.controller.party_state
        item = next(
            (i for i in party_state.party_inventory if i["instance_id"] == instance_id), None
        )
        assert item is not None
        assert item["decayed"] is True
        assert item["decay_result"] == "dust"

    def test_process_item_decays_provides_narrative(self, hex_engine, golden_egg_item, seeded_dice):
        """Decay processing should provide narrative hints."""
        result = hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        days_until = result["scheduled_decay"]["days_until"]
        hex_engine.controller.world_state.current_date = GameDate(year=1, month=1, day=1).advance_days(
            days_until
        )

        decayed = hex_engine.process_item_decays()

        assert len(decayed) == 1
        assert "message" in decayed[0]
        assert "narrative_hints" in decayed[0]
        assert len(decayed[0]["narrative_hints"]) > 0


class TestDeterministicDecay:
    """Test that decay timing is deterministic with seeded dice."""

    def test_deterministic_decay_timing(self, controller, seeded_dice):
        """Same seed should give same decay timing."""
        # First run
        DiceRoller.set_seed(42)
        engine1 = HexCrawlEngine(controller)
        controller.world_state.current_date = GameDate(year=1, month=1, day=1)

        result1 = engine1.acquire_item(
            hex_id="0103",
            item={
                "item_id": "golden_egg",
                "name": "Golden Egg",
                "decay_dice": "4d6",
            },
        )
        days1 = result1["scheduled_decay"]["days_until"]

        # Reset state
        controller.party_state.party_inventory.clear()
        engine1._event_scheduler.events.clear()

        # Second run with same seed
        DiceRoller.set_seed(42)
        engine2 = HexCrawlEngine(controller)

        result2 = engine2.acquire_item(
            hex_id="0103",
            item={
                "item_id": "golden_egg",
                "name": "Golden Egg",
                "decay_dice": "4d6",
            },
        )
        days2 = result2["scheduled_decay"]["days_until"]

        assert days1 == days2

    def test_decay_triggers_exactly_once(self, hex_engine, golden_egg_item, seeded_dice):
        """Decay should trigger exactly once on the correct day."""
        result = hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        days_until = result["scheduled_decay"]["days_until"]

        # Day before - no decay
        hex_engine.controller.world_state.current_date = GameDate(year=1, month=1, day=1).advance_days(
            days_until - 1
        )
        decayed_before = hex_engine.process_item_decays()
        assert len(decayed_before) == 0

        # Day of - decay triggers
        hex_engine.controller.world_state.current_date = GameDate(year=1, month=1, day=1).advance_days(
            days_until
        )
        decayed_on = hex_engine.process_item_decays()
        assert len(decayed_on) == 1

        # Day after - already decayed, shouldn't trigger again
        hex_engine.controller.world_state.current_date = GameDate(year=1, month=1, day=1).advance_days(
            days_until + 1
        )
        decayed_after = hex_engine.process_item_decays()
        assert len(decayed_after) == 0


class TestGetActiveDecayTimers:
    """Test getting active decay timers for display."""

    def test_get_active_decay_timers(self, hex_engine, golden_egg_item, seeded_dice):
        """Should return list of pending decay timers."""
        hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        timers = hex_engine.get_active_decay_timers()

        assert len(timers) == 1
        assert timers[0]["item_name"] == "Golden Egg"
        assert timers[0]["days_remaining"] >= 0

    def test_decay_timer_decreases(self, hex_engine, golden_egg_item, seeded_dice):
        """Timer should decrease as days pass."""
        result = hex_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        initial_days = result["scheduled_decay"]["days_until"]

        # Check initial timer
        timers = hex_engine.get_active_decay_timers()
        assert timers[0]["days_remaining"] == initial_days

        # Advance 5 days
        hex_engine.controller.world_state.current_date = GameDate(year=1, month=1, day=1).advance_days(5)

        timers_after = hex_engine.get_active_decay_timers()
        assert timers_after[0]["days_remaining"] == initial_days - 5


# =============================================================================
# GOLDEN EGG SPECIFIC TESTS
# =============================================================================


class TestGoldenEggFromHex0103:
    """Test Golden Egg behavior matching hex 0103 data."""

    @pytest.fixture
    def hex_0103_engine(self):
        """Create engine with hex 0103 loaded."""
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)
        result = loader.load_file(Path("data/content/hexes/0103_the_golden_goose.json"))
        assert result.success

        controller = GlobalController()
        controller.world_state.current_date = GameDate(year=1, month=1, day=1)
        engine = HexCrawlEngine(controller)
        engine._hex_data["0103"] = pipeline.get_hex("0103")
        return engine

    def test_golden_egg_from_treasure_hoard(self, hex_0103_engine, seeded_dice):
        """Golden Egg from Crocus's Cave treasure hoard should have decay properties."""
        hex_data = hex_0103_engine._hex_data["0103"]
        crocus_cave = next(
            (poi for poi in hex_data.points_of_interest if poi.name == "Crocus's Cave"),
            None,
        )

        assert crocus_cave is not None
        assert crocus_cave.treasure_hoard is not None

        # Get the golden egg from treasure hoard
        golden_eggs = next(
            (item for item in crocus_cave.treasure_hoard["items"] if item["name"] == "Golden Egg"),
            None,
        )

        assert golden_eggs is not None
        assert golden_eggs["quantity"] == 4
        assert golden_eggs["value_gp"] == 40

    def test_acquire_golden_egg_with_decay(self, hex_0103_engine, seeded_dice):
        """Acquiring a Golden Egg should schedule 4d6 day decay."""
        golden_egg_item = {
            "item_id": "0103:item:golden_egg",
            "name": "Golden Egg",
            "quantity": 1,
            "value_gp": 40,
            "decay_dice": "4d6",
            "decay_unit": "days",
            "notes": "Induces a subtle, covetous feeling in those who see it.",
        }

        result = hex_0103_engine.acquire_item(
            hex_id="0103",
            item=golden_egg_item,
            poi_name="Crocus's Cave",
        )

        assert result["scheduled_decay"] is not None
        # 4d6 should be between 4 and 24
        assert 4 <= result["scheduled_decay"]["days_until"] <= 24
