"""
Dolmenwood Weather Types and Tables.

Implements the 6 weather tables (Winter, Spring, Summer, Autumn, Hitching, Vague)
with their evocative descriptions and mechanical effects per the Campaign Book.
"""

from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Optional

from src.data_models import DiceRoller
from src.weather.calendar import DolmenwoodSeason, Unseason


class WeatherEffect(Flag):
    """
    Weather effect flags per the Campaign Book.

    I = Travel Impeded: Travel Points reduced by 2
    V = Poor Visibility: Encounter distance halved, +1-in-6 lost chance
    W = Wet Conditions: Building campfire is difficult
    """

    NONE = 0
    IMPEDED = auto()  # I - Travel impeded
    VISIBILITY = auto()  # V - Poor visibility
    WET = auto()  # W - Wet conditions

    @property
    def travel_point_penalty(self) -> int:
        """Get Travel Points penalty (0 or 2)."""
        return 2 if WeatherEffect.IMPEDED in self else 0

    @property
    def lost_chance_modifier(self) -> int:
        """Get modifier to lost chance (0 or 1)."""
        return 1 if WeatherEffect.VISIBILITY in self else 0

    @property
    def encounter_distance_halved(self) -> bool:
        """Check if encounter distance should be halved."""
        return WeatherEffect.VISIBILITY in self

    @property
    def campfire_difficult(self) -> bool:
        """Check if building campfire is difficult."""
        return WeatherEffect.WET in self

    def __str__(self) -> str:
        codes = []
        if WeatherEffect.IMPEDED in self:
            codes.append("I")
        if WeatherEffect.VISIBILITY in self:
            codes.append("V")
        if WeatherEffect.WET in self:
            codes.append("W")
        return "".join(codes) if codes else "-"


@dataclass(frozen=True)
class WeatherEntry:
    """A single weather table entry."""

    roll_min: int
    roll_max: int
    description: str
    effects: WeatherEffect = WeatherEffect.NONE

    def matches(self, roll: int) -> bool:
        """Check if this entry matches the given roll."""
        return self.roll_min <= roll <= self.roll_max


@dataclass
class WeatherResult:
    """
    The result of rolling on a weather table.

    Contains the evocative description and mechanical effects.
    """

    description: str
    effects: WeatherEffect
    roll: int
    table_used: str  # e.g., "winter", "hitching"

    @property
    def travel_point_penalty(self) -> int:
        """Get Travel Points penalty from effects."""
        return self.effects.travel_point_penalty

    @property
    def lost_chance_modifier(self) -> int:
        """Get lost chance modifier from effects."""
        return self.effects.lost_chance_modifier

    @property
    def encounter_distance_halved(self) -> bool:
        """Check if encounter distance halved."""
        return self.effects.encounter_distance_halved

    @property
    def campfire_difficult(self) -> bool:
        """Check if campfire building is difficult."""
        return self.effects.campfire_difficult

    def __str__(self) -> str:
        effect_str = str(self.effects)
        if effect_str == "-":
            return self.description
        return f"{self.description} [{effect_str}]"


# =============================================================================
# WEATHER TABLES - Per the Campaign Book (p112)
# =============================================================================

# Helper to create effect flags
I = WeatherEffect.IMPEDED
V = WeatherEffect.VISIBILITY
W = WeatherEffect.WET
IVW = I | V | W
VW = V | W
NONE = WeatherEffect.NONE

WINTER_TABLE: list[WeatherEntry] = [
    WeatherEntry(2, 2, "Deep freeze, hoarfrost", NONE),
    WeatherEntry(3, 3, "Snow storm", IVW),
    WeatherEntry(4, 4, "Relentless wind", NONE),
    WeatherEntry(5, 5, "Bitter, silent", NONE),
    WeatherEntry(6, 6, "Frigid, icy", NONE),
    WeatherEntry(7, 7, "Clear, cold", NONE),
    WeatherEntry(8, 8, "Freezing rain", VW),
    WeatherEntry(9, 9, "Cold wind, gloomy", NONE),
    WeatherEntry(10, 10, "Frigid mist", V),
    WeatherEntry(11, 11, "Icy, steady snow", VW),
    WeatherEntry(12, 12, "Relentless blizzard", IVW),
]

SPRING_TABLE: list[WeatherEntry] = [
    WeatherEntry(2, 2, "Cold, gentle snow", W),
    WeatherEntry(3, 3, "Chilly, damp", W),
    WeatherEntry(4, 4, "Windy, cloudy", NONE),
    WeatherEntry(5, 5, "Brisk, clear", NONE),
    WeatherEntry(6, 6, "Clement, cheery", NONE),
    WeatherEntry(7, 7, "Warm, sunny", NONE),
    WeatherEntry(8, 8, "Bright, fresh", NONE),
    WeatherEntry(9, 9, "Blustery, drizzle", W),
    WeatherEntry(10, 10, "Pouring rain", VW),
    WeatherEntry(11, 11, "Gloomy, cool", NONE),
    WeatherEntry(12, 12, "Chill mist", V),
]

SUMMER_TABLE: list[WeatherEntry] = [
    WeatherEntry(2, 2, "Cool winds", NONE),
    WeatherEntry(3, 3, "Low cloud, mist", V),
    WeatherEntry(4, 4, "Warm, gentle rain", W),
    WeatherEntry(5, 5, "Brooding thunder", NONE),
    WeatherEntry(6, 6, "Balmy, clear", NONE),
    WeatherEntry(7, 7, "Hot, humid", NONE),
    WeatherEntry(8, 8, "Overcast, muggy", NONE),
    WeatherEntry(9, 9, "Sweltering, still", NONE),
    WeatherEntry(10, 10, "Baking, dry", NONE),
    WeatherEntry(11, 11, "Warm wind", NONE),
    WeatherEntry(12, 12, "Thunder storm", VW),
]

AUTUMN_TABLE: list[WeatherEntry] = [
    WeatherEntry(2, 2, "Torrential rain", VW),
    WeatherEntry(3, 3, "Rolling fog", V),
    WeatherEntry(4, 4, "Driving rain", VW),
    WeatherEntry(5, 5, "Bracing wind", NONE),
    WeatherEntry(6, 6, "Balmy, clement", NONE),
    WeatherEntry(7, 7, "Clear, chilly", NONE),
    WeatherEntry(8, 8, "Drizzle, damp", W),
    WeatherEntry(9, 9, "Cloudy, misty", V),
    WeatherEntry(10, 10, "Brooding clouds", NONE),
    WeatherEntry(11, 11, "Frosty, chill", NONE),
    WeatherEntry(12, 12, "Icy, gentle snow", W),
]

# Unseason: Hitching (first 20 days of Grimvold)
HITCHING_TABLE: list[WeatherEntry] = [
    WeatherEntry(2, 2, "Torrential rain", VW),
    WeatherEntry(3, 3, "Clear, fresh dew", W),
    WeatherEntry(4, 4, "Sleepy, purple mist", V),
    WeatherEntry(5, 5, "Interminable drizzle", W),
    WeatherEntry(6, 6, "Balmy mist", V),
    WeatherEntry(7, 7, "Thick fog, hot", V),
    WeatherEntry(8, 8, "Misty, seeping damp", VW),
    WeatherEntry(9, 9, "Hazy fog, dripping", VW),
    WeatherEntry(10, 10, "Sticky dew drips", W),
    WeatherEntry(11, 11, "Gloomy, shadows drip", NONE),
    WeatherEntry(12, 12, "Befuddling green fog", V),
]

# Unseason: Vague (during Lymewald and Haggryme)
VAGUE_TABLE: list[WeatherEntry] = [
    WeatherEntry(2, 2, "Hoarfrost, freezing fog", V),
    WeatherEntry(3, 3, "Steady snow, icy mist", VW),
    WeatherEntry(4, 4, "Low mist, writhing soil", NONE),
    WeatherEntry(5, 5, "Sickly, yellow mist", V),
    WeatherEntry(6, 6, "Thick, rolling fog", V),
    WeatherEntry(7, 7, "Freezing fog", V),
    WeatherEntry(8, 8, "Chill mist, winds wail", V),
    WeatherEntry(9, 9, "Icy mist, eerie howling", V),
    WeatherEntry(10, 10, "Violet mist rises", V),
    WeatherEntry(11, 11, "Blizzard, earth tremors", IVW),
    WeatherEntry(12, 12, "Blizzard, dense fog", IVW),
]

# All tables indexed by identifier
WEATHER_TABLES: dict[str, list[WeatherEntry]] = {
    "winter": WINTER_TABLE,
    "spring": SPRING_TABLE,
    "summer": SUMMER_TABLE,
    "autumn": AUTUMN_TABLE,
    "hitching": HITCHING_TABLE,
    "vague": VAGUE_TABLE,
}


def get_weather_table_for_month(
    month_number: int,
    active_unseason: Unseason = Unseason.NONE,
) -> tuple[str, list[WeatherEntry]]:
    """
    Get the appropriate weather table for a month.

    Takes into account active unseasons:
    - Hitching uses the Hitching table
    - Vague uses the Vague table
    - Colliggwyld uses Spring table
    - Chame uses Summer table

    Args:
        month_number: 1-12
        active_unseason: Currently active unseason

    Returns:
        Tuple of (table_name, table_entries)
    """
    from src.weather.calendar import MONTHS

    # Handle unseasons first
    if active_unseason == Unseason.HITCHING:
        return "hitching", HITCHING_TABLE
    elif active_unseason == Unseason.VAGUE:
        return "vague", VAGUE_TABLE
    elif active_unseason == Unseason.COLLIGGWYLD:
        # Colliggwyld uses Spring table
        return "spring", SPRING_TABLE
    elif active_unseason == Unseason.CHAME:
        # Chame uses Summer table
        return "summer", SUMMER_TABLE

    # Normal seasonal weather
    if month_number not in MONTHS:
        raise ValueError(f"Invalid month number: {month_number}")

    season = MONTHS[month_number].season
    table_name = season.value
    return table_name, WEATHER_TABLES[table_name]


def roll_weather(
    month_number: int,
    active_unseason: Unseason = Unseason.NONE,
    modifier: int = 0,
) -> WeatherResult:
    """
    Roll on the weather table for the given month.

    Args:
        month_number: 1-12
        active_unseason: Currently active unseason
        modifier: Modifier to the 2d6 roll

    Returns:
        WeatherResult with description and effects
    """
    table_name, table = get_weather_table_for_month(month_number, active_unseason)

    # Roll 2d6
    dice_result = DiceRoller.roll("2d6", f"weather roll ({table_name})")
    roll = dice_result.total + modifier

    # Clamp to valid range (2-12)
    roll = max(2, min(12, roll))

    # Find matching entry
    for entry in table:
        if entry.matches(roll):
            return WeatherResult(
                description=entry.description,
                effects=entry.effects,
                roll=roll,
                table_used=table_name,
            )

    # Fallback (shouldn't happen with proper tables)
    return WeatherResult(
        description="Clear",
        effects=WeatherEffect.NONE,
        roll=roll,
        table_used=table_name,
    )


def get_effect_description(effects: WeatherEffect) -> list[str]:
    """
    Get human-readable descriptions of weather effects.

    Args:
        effects: WeatherEffect flags

    Returns:
        List of effect descriptions
    """
    descriptions = []

    if WeatherEffect.IMPEDED in effects:
        descriptions.append("Travel Points reduced by 2 (forced march if 0 or below)")

    if WeatherEffect.VISIBILITY in effects:
        descriptions.append("Encounter distance halved; +1-in-6 chance of getting lost")

    if WeatherEffect.WET in effects:
        descriptions.append("Building a campfire is difficult")

    return descriptions
