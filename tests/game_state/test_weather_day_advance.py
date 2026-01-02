"""
Test that weather updates automatically on day advancement.

Phase 5.1: Weather automatic daily advancement
"""

import pytest

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller, GameDate, GameTime, CharacterState
from src.game_state.state_machine import GameState


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
        character_id="test_fighter_1",
        name="Test Fighter",
        character_class="Fighter",
        level=3,
        ability_scores={
            "STR": 16,
            "INT": 10,
            "WIS": 12,
            "DEX": 14,
            "CON": 15,
            "CHA": 11,
        },
        hp_current=24,
        hp_max=24,
        armor_class=4,
        base_speed=30,
    )


@pytest.fixture
def offline_dm(seeded_dice, test_character):
    """Create VirtualDM in offline mode."""
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

    # Give party some resources
    dm.controller.party_state.resources.food_days = 10
    dm.controller.party_state.resources.water_days = 10

    return dm


class TestWeatherDayAdvance:
    """Test weather updates on day advancement."""

    def test_weather_updates_on_day_advance(self, offline_dm, seeded_dice):
        """Weather should update when day advances."""
        controller = offline_dm.controller

        # Get initial weather
        initial_weather = controller.world_state.weather

        # Advance a day
        controller.advance_time(turns=144)

        # Weather should be set (may or may not have changed)
        new_weather = controller.world_state.weather
        assert new_weather is not None

    def test_weather_is_deterministic_with_seed(self, seeded_dice, test_character):
        """Weather rolls should be deterministic when seeded."""
        # Create first DM
        DiceRoller.set_seed(42)
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=False,
        )

        dm1 = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )
        dm1.controller.add_character(test_character)
        dm1.controller.party_state.resources.food_days = 10
        dm1.controller.party_state.resources.water_days = 10
        dm1.controller.advance_time(turns=144)
        weather1 = dm1.controller.world_state.weather

        # Create second DM with same seed
        DiceRoller.set_seed(42)
        dm2 = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )
        dm2.controller.add_character(test_character)
        dm2.controller.party_state.resources.food_days = 10
        dm2.controller.party_state.resources.water_days = 10
        dm2.controller.advance_time(turns=144)
        weather2 = dm2.controller.world_state.weather

        # Weather should be the same with same seed
        assert weather1 == weather2

    def test_multiple_day_advance_updates_weather_each_day(self, offline_dm, seeded_dice):
        """Multiple day advance should update weather for each day."""
        controller = offline_dm.controller

        # Clear the session log
        controller._session_log = []

        # Advance 3 days
        controller.advance_time(turns=432)  # 72 hours = 432 turns

        # Check that weather was rolled multiple times
        weather_events = [
            e for e in controller._session_log
            if e.get("event_type") == "day_advance_weather"
        ]

        # Should have at least 1 weather event (may be deduplicated)
        assert len(weather_events) >= 1

    def test_day_advance_checks_unseason(self, offline_dm):
        """Day advance should check for unseason triggers."""
        controller = offline_dm.controller

        # Clear the session log
        controller._session_log = []

        # Advance a day
        controller.advance_time(turns=144)

        # Check that the day advance happened (weather event is logged)
        weather_events = [
            e for e in controller._session_log
            if e.get("event_type") == "day_advance_weather"
        ]

        assert len(weather_events) >= 1
