"""
Tests for the Dolmenwood Weather System.

Tests the book-accurate weather tables, unseasons, and mechanical effects.
"""

import pytest

from src.data_models import DiceRoller
from src.weather.calendar import (
    DolmenwoodMonth,
    DolmenwoodSeason,
    Unseason,
    MONTHS,
    MONTH_BY_NAME,
    get_season_for_month,
    get_daylight_hours,
    is_dolmenday,
    get_year_length,
)
from src.weather.weather_types import (
    WeatherEffect,
    WeatherEntry,
    WeatherResult,
    WEATHER_TABLES,
    roll_weather,
    get_weather_table_for_month,
    get_effect_description,
)
from src.weather.unseason_tracker import (
    UnseasonState,
    check_unseason_trigger,
    get_active_unseason_effects,
)
from src.tables.encounter_roller import EncounterRoller, EncounterContext
from src.tables.wilderness_encounter_tables import get_unseason_table


class TestDolmenwoodCalendar:
    """Tests for the Dolmenwood calendar system."""

    def test_twelve_months_defined(self):
        """All 12 months should be defined."""
        assert len(MONTHS) == 12
        for i in range(1, 13):
            assert i in MONTHS

    def test_month_names(self):
        """Verify correct month names per the Campaign Book."""
        expected_names = [
            "Grimvold",
            "Lymewald",
            "Haggryme",
            "Symswald",
            "Harchment",
            "Iggwyld",
            "Chysting",
            "Lillipythe",
            "Haelhold",
            "Reedwryme",
            "Obthryme",
            "Braghold",
        ]
        for i, name in enumerate(expected_names, 1):
            assert MONTHS[i].name == name

    def test_month_seasons(self):
        """Verify months map to correct seasons."""
        # Winter: 1-3
        assert MONTHS[1].season == DolmenwoodSeason.WINTER
        assert MONTHS[2].season == DolmenwoodSeason.WINTER
        assert MONTHS[3].season == DolmenwoodSeason.WINTER
        # Spring: 4-6
        assert MONTHS[4].season == DolmenwoodSeason.SPRING
        assert MONTHS[5].season == DolmenwoodSeason.SPRING
        assert MONTHS[6].season == DolmenwoodSeason.SPRING
        # Summer: 7-9
        assert MONTHS[7].season == DolmenwoodSeason.SUMMER
        assert MONTHS[8].season == DolmenwoodSeason.SUMMER
        assert MONTHS[9].season == DolmenwoodSeason.SUMMER
        # Autumn: 10-12
        assert MONTHS[10].season == DolmenwoodSeason.AUTUMN
        assert MONTHS[11].season == DolmenwoodSeason.AUTUMN
        assert MONTHS[12].season == DolmenwoodSeason.AUTUMN

    def test_daylight_hours(self):
        """Test daylight hours per month."""
        # Winter has shortest days
        _, _, winter_hours = get_daylight_hours(1)
        assert winter_hours == 8.0

        # Summer has longest days
        _, _, summer_hours = get_daylight_hours(7)
        assert summer_hours == 17.0

    def test_sunrise_sunset(self):
        """Test sunrise/sunset times."""
        sunrise, sunset, _ = get_daylight_hours(1)  # Grimvold
        assert sunrise == "8:00 AM"
        assert sunset == "4:00 PM"

        sunrise, sunset, _ = get_daylight_hours(7)  # Chysting
        assert sunrise == "4:30 AM"
        assert sunset == "9:30 PM"

    def test_month_by_name_lookup(self):
        """Test looking up months by name."""
        month = MONTH_BY_NAME.get("grimvold")
        assert month is not None
        assert month.number == 1

    def test_get_season_for_month(self):
        """Test getting season from month number."""
        assert get_season_for_month(1) == DolmenwoodSeason.WINTER
        assert get_season_for_month(6) == DolmenwoodSeason.SPRING
        assert get_season_for_month(8) == DolmenwoodSeason.SUMMER
        assert get_season_for_month(12) == DolmenwoodSeason.AUTUMN

    def test_is_dolmenday(self):
        """Test Dolmenday detection (last day of year)."""
        assert is_dolmenday(12, 30) is True
        assert is_dolmenday(12, 29) is False
        assert is_dolmenday(1, 30) is False

    def test_year_length(self):
        """Test total days in year."""
        # 10 months of 30 days + 2 months of 28 days = 300 + 56 = 356
        assert get_year_length() == 356


class TestWeatherEffects:
    """Tests for WeatherEffect flags."""

    def test_none_effect(self):
        """Test NONE effect has no penalties."""
        effect = WeatherEffect.NONE
        assert effect.travel_point_penalty == 0
        assert effect.lost_chance_modifier == 0
        assert effect.encounter_distance_halved is False
        assert effect.campfire_difficult is False

    def test_impeded_effect(self):
        """Test IMPEDED (I) effect."""
        effect = WeatherEffect.IMPEDED
        assert effect.travel_point_penalty == 2
        assert effect.lost_chance_modifier == 0

    def test_visibility_effect(self):
        """Test VISIBILITY (V) effect."""
        effect = WeatherEffect.VISIBILITY
        assert effect.lost_chance_modifier == 1
        assert effect.encounter_distance_halved is True

    def test_wet_effect(self):
        """Test WET (W) effect."""
        effect = WeatherEffect.WET
        assert effect.campfire_difficult is True

    def test_combined_effects(self):
        """Test combined effects (IVW)."""
        effect = WeatherEffect.IMPEDED | WeatherEffect.VISIBILITY | WeatherEffect.WET
        assert effect.travel_point_penalty == 2
        assert effect.lost_chance_modifier == 1
        assert effect.encounter_distance_halved is True
        assert effect.campfire_difficult is True

    def test_effect_string_representation(self):
        """Test string representation of effects."""
        assert str(WeatherEffect.NONE) == "-"
        assert str(WeatherEffect.IMPEDED) == "I"
        assert str(WeatherEffect.VISIBILITY) == "V"
        assert str(WeatherEffect.WET) == "W"
        assert "I" in str(WeatherEffect.IMPEDED | WeatherEffect.VISIBILITY | WeatherEffect.WET)
        assert "V" in str(WeatherEffect.IMPEDED | WeatherEffect.VISIBILITY | WeatherEffect.WET)
        assert "W" in str(WeatherEffect.IMPEDED | WeatherEffect.VISIBILITY | WeatherEffect.WET)


class TestWeatherTables:
    """Tests for the weather tables."""

    def test_all_tables_exist(self):
        """All 6 weather tables should exist."""
        expected_tables = ["winter", "spring", "summer", "autumn", "hitching", "vague"]
        for table_name in expected_tables:
            assert table_name in WEATHER_TABLES

    def test_table_coverage(self):
        """Each table should cover rolls 2-12."""
        for table_name, entries in WEATHER_TABLES.items():
            covered = set()
            for entry in entries:
                for roll in range(entry.roll_min, entry.roll_max + 1):
                    covered.add(roll)
            assert covered == set(range(2, 13)), f"{table_name} table doesn't cover 2-12"

    def test_winter_table_entries(self):
        """Verify specific winter table entries."""
        winter = WEATHER_TABLES["winter"]
        # Find blizzard entry (roll 12)
        blizzard = [e for e in winter if e.roll_max == 12][0]
        assert "blizzard" in blizzard.description.lower()
        assert WeatherEffect.IMPEDED in blizzard.effects
        assert WeatherEffect.VISIBILITY in blizzard.effects
        assert WeatherEffect.WET in blizzard.effects

    def test_hitching_table_entries(self):
        """Verify Hitching unseason table has mystical weather."""
        hitching = WEATHER_TABLES["hitching"]
        # Find befuddling green fog entry (roll 12)
        fog = [e for e in hitching if e.roll_max == 12][0]
        assert "befuddling" in fog.description.lower() or "fog" in fog.description.lower()

    def test_vague_table_entries(self):
        """Verify Vague unseason table has sinister weather."""
        vague = WEATHER_TABLES["vague"]
        # Should have lots of mist/fog and some blizzards
        descriptions = [e.description.lower() for e in vague]
        fog_count = sum(1 for d in descriptions if "fog" in d or "mist" in d)
        assert fog_count >= 5  # Vague is very foggy


class TestWeatherRolling:
    """Tests for rolling weather."""

    @pytest.fixture(autouse=True)
    def reset_roller(self):
        """Reset dice roller before each test."""
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)
        yield

    def test_get_weather_table_for_month_normal(self):
        """Test getting correct table for normal months."""
        # Winter month
        name, table = get_weather_table_for_month(1)
        assert name == "winter"

        # Spring month
        name, table = get_weather_table_for_month(5)
        assert name == "spring"

        # Summer month
        name, table = get_weather_table_for_month(8)
        assert name == "summer"

        # Autumn month
        name, table = get_weather_table_for_month(11)
        assert name == "autumn"

    def test_get_weather_table_for_hitching(self):
        """Test Hitching uses its own table."""
        name, table = get_weather_table_for_month(1, Unseason.HITCHING)
        assert name == "hitching"

    def test_get_weather_table_for_vague(self):
        """Test Vague uses its own table."""
        name, table = get_weather_table_for_month(2, Unseason.VAGUE)
        assert name == "vague"

    def test_get_weather_table_for_colliggwyld(self):
        """Test Colliggwyld uses Spring table."""
        name, table = get_weather_table_for_month(6, Unseason.COLLIGGWYLD)
        assert name == "spring"

    def test_get_weather_table_for_chame(self):
        """Test Chame uses Summer table."""
        name, table = get_weather_table_for_month(9, Unseason.CHAME)
        assert name == "summer"

    def test_roll_weather_returns_valid_result(self):
        """Test rolling weather returns a valid result."""
        DiceRoller.set_seed(42)
        result = roll_weather(6)  # Iggwyld (spring)

        assert isinstance(result, WeatherResult)
        assert result.description != ""
        assert result.table_used == "spring"
        assert 2 <= result.roll <= 12

    def test_roll_weather_with_modifier(self):
        """Test rolling weather with modifier."""
        DiceRoller.set_seed(42)
        result = roll_weather(1, modifier=5)

        # Roll should be clamped to 2-12
        assert 2 <= result.roll <= 12

    def test_weather_result_string(self):
        """Test WeatherResult string representation."""
        result = WeatherResult(
            description="Relentless blizzard",
            effects=WeatherEffect.IMPEDED | WeatherEffect.VISIBILITY | WeatherEffect.WET,
            roll=12,
            table_used="winter",
        )
        result_str = str(result)
        assert "Relentless blizzard" in result_str
        assert "[" in result_str  # Should include effect codes


class TestUnseasonState:
    """Tests for UnseasonState tracking."""

    def test_initial_state(self):
        """Test initial state is inactive."""
        state = UnseasonState()
        assert not state.is_active()
        assert state.active == Unseason.NONE

    def test_start_unseason(self):
        """Test starting an unseason."""
        state = UnseasonState()
        state.start_unseason(Unseason.HITCHING, 20)

        assert state.is_active()
        assert state.active == Unseason.HITCHING
        assert state.days_remaining == 20

    def test_advance_day(self):
        """Test advancing days."""
        state = UnseasonState()
        state.start_unseason(Unseason.VAGUE, 3)

        assert state.advance_day() is False
        assert state.days_remaining == 2

        assert state.advance_day() is False
        assert state.days_remaining == 1

        assert state.advance_day() is True  # Unseason ended
        assert state.days_remaining == 0
        assert not state.is_active()

    def test_serialization(self):
        """Test to_dict and from_dict."""
        state = UnseasonState()
        state.start_unseason(Unseason.CHAME, 15)

        data = state.to_dict()
        restored = UnseasonState.from_dict(data)

        assert restored.active == Unseason.CHAME
        assert restored.days_remaining == 15


class TestUnseasonTriggers:
    """Tests for unseason trigger logic."""

    @pytest.fixture(autouse=True)
    def reset_roller(self):
        """Reset dice roller before each test."""
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)
        yield

    def test_no_trigger_when_active(self):
        """No trigger should occur when unseason already active."""
        state = UnseasonState()
        state.start_unseason(Unseason.HITCHING, 10)

        # Even on Dolmenday, shouldn't trigger
        result = check_unseason_trigger(12, 30, state)
        assert result is None

    def test_hitching_trigger_on_dolmenday(self):
        """Hitching can trigger on Dolmenday."""
        state = UnseasonState()
        DiceRoller.set_seed(1)  # Seed that gives 1 on d4

        # May or may not trigger depending on roll
        # Just verify no error occurs
        result = check_unseason_trigger(12, 30, state)
        # Result is either (Unseason.HITCHING, 20) or None

    def test_colliggwyld_trigger_on_iggwyld_first(self):
        """Colliggwyld can trigger on 1st of Iggwyld."""
        state = UnseasonState()
        DiceRoller.set_seed(1)

        result = check_unseason_trigger(6, 1, state)
        # Result is either (Unseason.COLLIGGWYLD, 30) or None

    def test_vague_trigger_in_lymewald(self):
        """Vague can trigger at week starts in Lymewald."""
        state = UnseasonState()
        DiceRoller.set_seed(1)

        # First day of month is first day of week
        result = check_unseason_trigger(2, 1, state)
        # Result is either (Unseason.VAGUE, 1-6) or None


class TestUnseasonEffects:
    """Tests for unseason special effects."""

    def test_no_effects_when_inactive(self):
        """No special effects when no unseason active."""
        state = UnseasonState()
        effects = get_active_unseason_effects(state)

        assert effects["special_encounters"] is False
        assert effects["foraging_bonus"] == 1.0

    def test_hitching_effects(self):
        """Test Hitching effects."""
        state = UnseasonState()
        state.start_unseason(Unseason.HITCHING, 20)
        effects = get_active_unseason_effects(state)

        assert effects["special_encounters"] is False
        assert "fey moon" in effects["description"].lower()

    def test_colliggwyld_effects(self):
        """Test Colliggwyld effects (double fungi)."""
        state = UnseasonState()
        state.start_unseason(Unseason.COLLIGGWYLD, 30)
        effects = get_active_unseason_effects(state)

        assert effects["foraging_bonus"] == 2.0
        assert "fungus" in effects["description"].lower()

    def test_chame_effects(self):
        """Test Chame effects (serpent encounters)."""
        state = UnseasonState()
        state.start_unseason(Unseason.CHAME, 10)
        effects = get_active_unseason_effects(state)

        assert effects["special_encounters"] is True
        assert effects["special_encounter_chance"] == 2  # 2-in-6
        assert (
            "serpent" in effects["description"].lower() or "snake" in effects["description"].lower()
        )

    def test_vague_effects(self):
        """Test Vague effects (undead encounters)."""
        state = UnseasonState()
        state.start_unseason(Unseason.VAGUE, 5)
        effects = get_active_unseason_effects(state)

        assert effects["special_encounters"] is True
        assert effects["special_encounter_chance"] == 2  # 2-in-6
        assert "fog" in effects["description"].lower() or "undead" in effects["description"].lower()


class TestUnseasonEncounters:
    """Tests for special unseason encounter tables integration."""

    @pytest.fixture(autouse=True)
    def reset_roller(self):
        """Reset dice roller before each test."""
        DiceRoller.clear_roll_log()
        DiceRoller.set_replay_session(None)
        yield

    def test_chame_table_exists(self):
        """Test that Chame encounter table exists in encounter system."""
        table = get_unseason_table("chame")
        assert table is not None
        assert table["die"] == "d10"
        assert len(table["entries"]) == 10

        # Verify expected creatures are in the table
        creature_names = {entry.name for entry in table["entries"].values()}
        assert "Galosher" in creature_names
        assert "Snake—Adder" in creature_names
        assert "Snake—Giant Python" in creature_names
        assert "Wyrm—Black Bile" in creature_names

    def test_vague_table_exists(self):
        """Test that Vague encounter table exists in encounter system."""
        table = get_unseason_table("vague")
        assert table is not None
        assert table["die"] == "d10"
        assert len(table["entries"]) == 10

        # Verify expected creatures are in the table
        creature_names = {entry.name for entry in table["entries"].values()}
        assert "Banshee" in creature_names
        assert "Bog Corpse" in creature_names
        assert "Ghoul" in creature_names
        assert "Skeleton" in creature_names

    def test_encounter_roller_handles_chame(self):
        """Test EncounterRoller correctly uses Chame unseason."""
        DiceRoller.set_seed(1)  # Seed that triggers unseason encounter
        roller = EncounterRoller()
        context = EncounterContext(
            region="tithelands",
            active_unseason="chame",
        )

        # Roll multiple times - some should be unseason encounters (2-in-6 chance)
        unseason_count = 0
        for _ in range(30):
            DiceRoller.set_seed(_)  # Different seed each time
            result = roller.roll_encounter(context, check_lair=False)
            if result.unseason == "chame":
                unseason_count += 1
                # Verify it's a valid Chame creature
                assert result.entry.name in [
                    "Galosher",
                    "Snake—Adder",
                    "Snake—Giant Python",
                    "Wyrm—Black Bile",
                    "Wyrm—Blood",
                    "Wyrm—Phlegm",
                    "Wyrm—Yellow Bile",
                ]

        # With 2-in-6 chance over 30 rolls, we should get some unseason encounters
        # (statistically ~10, but we just check > 0)
        assert unseason_count > 0

    def test_encounter_roller_handles_vague(self):
        """Test EncounterRoller correctly uses Vague unseason."""
        DiceRoller.set_seed(1)
        roller = EncounterRoller()
        context = EncounterContext(
            region="tithelands",
            active_unseason="vague",
        )

        # Roll multiple times - some should be unseason encounters
        unseason_count = 0
        for _ in range(30):
            DiceRoller.set_seed(_)
            result = roller.roll_encounter(context, check_lair=False)
            if result.unseason == "vague":
                unseason_count += 1
                # Verify it's a valid Vague creature
                assert result.entry.name in [
                    "Banshee",
                    "Bog Corpse",
                    "Ghoul",
                    "Gloam",
                    "Headless Rider",
                    "Skeleton",
                    "Spectre",
                    "Wight",
                ]

        assert unseason_count > 0

    def test_no_unseason_table_for_hitching(self):
        """Hitching doesn't have a special encounter table."""
        table = get_unseason_table("hitching")
        assert table is None

    def test_no_unseason_table_for_colliggwyld(self):
        """Colliggwyld doesn't have a special encounter table."""
        table = get_unseason_table("colliggwyld")
        assert table is None


class TestEffectDescriptions:
    """Tests for effect description generation."""

    def test_get_effect_description_none(self):
        """Test description for no effects."""
        descriptions = get_effect_description(WeatherEffect.NONE)
        assert descriptions == []

    def test_get_effect_description_all(self):
        """Test description for all effects."""
        effects = WeatherEffect.IMPEDED | WeatherEffect.VISIBILITY | WeatherEffect.WET
        descriptions = get_effect_description(effects)

        assert len(descriptions) == 3
        assert any("Travel Points" in d for d in descriptions)
        assert any("lost" in d.lower() for d in descriptions)
        assert any("campfire" in d.lower() for d in descriptions)
