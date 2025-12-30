"""
Dolmenwood Weather and Calendar System.

Implements the book-accurate weather tables, seasons, unseasons,
and mechanical effects from the Dolmenwood Campaign Book.
"""

from src.weather.calendar import (
    DolmenwoodMonth,
    DolmenwoodSeason,
    Unseason,
    MONTHS,
    MONTH_BY_NAME,
    get_season_for_month,
    get_daylight_hours,
)
from src.weather.weather_types import (
    WeatherEffect,
    WeatherResult,
    WEATHER_TABLES,
    roll_weather,
    get_weather_table_for_month,
)
from src.weather.unseason_tracker import (
    UnseasonState,
    check_unseason_trigger,
    get_active_unseason_effects,
)

__all__ = [
    # Calendar
    "DolmenwoodMonth",
    "DolmenwoodSeason",
    "Unseason",
    "MONTHS",
    "MONTH_BY_NAME",
    "get_season_for_month",
    "get_daylight_hours",
    # Weather
    "WeatherEffect",
    "WeatherResult",
    "WEATHER_TABLES",
    "roll_weather",
    "get_weather_table_for_month",
    # Unseasons
    "UnseasonState",
    "check_unseason_trigger",
    "get_active_unseason_effects",
]
