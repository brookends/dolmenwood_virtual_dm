"""
Dolmenwood Calendar System.

Defines the 12 months, 4 seasons, and daylight hours per the Campaign Book.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DolmenwoodSeason(str, Enum):
    """The four seasons of the Dolmenwood year."""

    WINTER = "winter"  # Grimvold, Lymewald, Haggryme
    SPRING = "spring"  # Symswald, Harchment, Iggwyld
    SUMMER = "summer"  # Chysting, Lillipythe, Haelhold
    AUTUMN = "autumn"  # Reedwryme, Obthryme, Braghold


class Unseason(str, Enum):
    """
    Magical unseasons that occasionally take hold in Dolmenwood.

    Each has specific triggers, durations, and effects.
    """

    NONE = "none"  # Normal seasonal weather
    HITCHING = "hitching"  # Fairy realm encroaches, fey moon visible
    COLLIGGWYLD = "colliggwyld"  # Giant fungus blooms
    CHAME = "chame"  # Snakes and serpents fill the wood
    VAGUE = "vague"  # Sinister fog, undead rise


@dataclass(frozen=True)
class DolmenwoodMonth:
    """
    A month in the Dolmenwood calendar.

    Attributes:
        number: 1-12
        name: Month name (e.g., "Grimvold")
        season: The season this month belongs to
        days: Number of days (28 or 30)
        sunrise: Time of sunrise (e.g., "8:00 AM")
        sunset: Time of sunset (e.g., "4:00 PM")
        daylight_hours: Total daylight hours
    """

    number: int
    name: str
    season: DolmenwoodSeason
    days: int
    sunrise: str
    sunset: str
    daylight_hours: float  # Can be fractional (e.g., 8.5)


# The 12 months of the Dolmenwood calendar per the Campaign Book
MONTHS: dict[int, DolmenwoodMonth] = {
    # WINTER
    1: DolmenwoodMonth(
        number=1,
        name="Grimvold",
        season=DolmenwoodSeason.WINTER,
        days=30,
        sunrise="8:00 AM",
        sunset="4:00 PM",
        daylight_hours=8.0,
    ),
    2: DolmenwoodMonth(
        number=2,
        name="Lymewald",
        season=DolmenwoodSeason.WINTER,
        days=28,
        sunrise="8:00 AM",
        sunset="4:30 PM",
        daylight_hours=8.5,
    ),
    3: DolmenwoodMonth(
        number=3,
        name="Haggryme",
        season=DolmenwoodSeason.WINTER,
        days=30,
        sunrise="7:30 AM",
        sunset="5:00 PM",
        daylight_hours=9.5,
    ),
    # SPRING
    4: DolmenwoodMonth(
        number=4,
        name="Symswald",
        season=DolmenwoodSeason.SPRING,
        days=30,
        sunrise="6:30 AM",
        sunset="6:00 PM",
        daylight_hours=11.5,
    ),
    5: DolmenwoodMonth(
        number=5,
        name="Harchment",
        season=DolmenwoodSeason.SPRING,
        days=30,
        sunrise="6:00 AM",
        sunset="8:00 PM",
        daylight_hours=14.0,
    ),
    6: DolmenwoodMonth(
        number=6,
        name="Iggwyld",
        season=DolmenwoodSeason.SPRING,
        days=30,
        sunrise="5:00 AM",
        sunset="9:00 PM",
        daylight_hours=16.0,
    ),
    # SUMMER
    7: DolmenwoodMonth(
        number=7,
        name="Chysting",
        season=DolmenwoodSeason.SUMMER,
        days=30,
        sunrise="4:30 AM",
        sunset="9:30 PM",
        daylight_hours=17.0,
    ),
    8: DolmenwoodMonth(
        number=8,
        name="Lillipythe",
        season=DolmenwoodSeason.SUMMER,
        days=30,
        sunrise="5:00 AM",
        sunset="9:00 PM",
        daylight_hours=16.0,
    ),
    9: DolmenwoodMonth(
        number=9,
        name="Haelhold",
        season=DolmenwoodSeason.SUMMER,
        days=30,
        sunrise="6:00 AM",
        sunset="8:30 PM",
        daylight_hours=15.5,
    ),
    # AUTUMN
    10: DolmenwoodMonth(
        number=10,
        name="Reedwryme",
        season=DolmenwoodSeason.AUTUMN,
        days=30,
        sunrise="6:30 AM",
        sunset="7:30 PM",
        daylight_hours=13.0,
    ),
    11: DolmenwoodMonth(
        number=11,
        name="Obthryme",
        season=DolmenwoodSeason.AUTUMN,
        days=28,
        sunrise="7:30 AM",
        sunset="6:00 PM",
        daylight_hours=10.5,
    ),
    12: DolmenwoodMonth(
        number=12,
        name="Braghold",
        season=DolmenwoodSeason.AUTUMN,
        days=30,
        sunrise="7:30 AM",
        sunset="4:30 PM",
        daylight_hours=9.0,
    ),
}

# Lookup by name for convenience
MONTH_BY_NAME: dict[str, DolmenwoodMonth] = {m.name.lower(): m for m in MONTHS.values()}


def get_season_for_month(month_number: int) -> DolmenwoodSeason:
    """Get the season for a given month number (1-12)."""
    if month_number not in MONTHS:
        raise ValueError(f"Invalid month number: {month_number}")
    return MONTHS[month_number].season


def get_daylight_hours(month_number: int) -> tuple[str, str, float]:
    """
    Get daylight information for a month.

    Returns:
        Tuple of (sunrise, sunset, total_hours)
    """
    if month_number not in MONTHS:
        raise ValueError(f"Invalid month number: {month_number}")
    month = MONTHS[month_number]
    return month.sunrise, month.sunset, month.daylight_hours


def get_month_by_name(name: str) -> Optional[DolmenwoodMonth]:
    """Get a month by its name (case-insensitive)."""
    return MONTH_BY_NAME.get(name.lower())


def get_year_length() -> int:
    """Get the total number of days in the Dolmenwood year."""
    return sum(m.days for m in MONTHS.values())


def is_dolmenday(month: int, day: int) -> bool:
    """Check if the given date is Dolmenday (last day of the year)."""
    return month == 12 and day == MONTHS[12].days
