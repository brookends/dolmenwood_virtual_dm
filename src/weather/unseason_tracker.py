"""
Unseason Tracking and Trigger Logic.

Implements the rules for when unseasons begin and end per the Campaign Book (p111).
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from src.data_models import DiceRoller
from src.weather.calendar import (
    Unseason,
    MONTHS,
    is_dolmenday,
)


@dataclass
class UnseasonState:
    """
    Tracks the current unseason state.

    Attributes:
        active: The currently active unseason (NONE if normal weather)
        days_remaining: Days remaining in the unseason
        special_encounters: Whether special encounter rules apply
    """

    active: Unseason = Unseason.NONE
    days_remaining: int = 0

    def is_active(self) -> bool:
        """Check if any unseason is currently active."""
        return self.active != Unseason.NONE and self.days_remaining > 0

    def advance_day(self) -> bool:
        """
        Advance one day. Returns True if unseason ended.
        """
        if self.days_remaining > 0:
            self.days_remaining -= 1
            if self.days_remaining == 0:
                self.active = Unseason.NONE
                return True
        return False

    def start_unseason(self, unseason: Unseason, duration: int) -> None:
        """Start a new unseason with the given duration."""
        self.active = unseason
        self.days_remaining = duration

    def end_unseason(self) -> None:
        """Force end the current unseason."""
        self.active = Unseason.NONE
        self.days_remaining = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "active": self.active.value,
            "days_remaining": self.days_remaining,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnseasonState":
        """Deserialize from dictionary."""
        return cls(
            active=Unseason(data.get("active", "none")),
            days_remaining=data.get("days_remaining", 0),
        )


def check_unseason_trigger(
    month: int,
    day: int,
    current_state: UnseasonState,
) -> Optional[tuple[Unseason, int]]:
    """
    Check if an unseason should trigger on this date.

    Per the Campaign Book (p111):
    - Hitching: 1-in-4 on Dolmenday, lasts 20 days into Grimvold
    - Colliggwyld: 1-in-4 on 1st of Iggwyld, lasts 30 days (full month)
    - Chame: 1-in-20 on days 1-5 of Haelhold, lasts 2d10 days
    - Vague: 1-in-10 on 1st of each week in Lymewald/Haggryme, lasts 1d6 days

    Args:
        month: Current month (1-12)
        day: Current day of the month
        current_state: Current unseason state

    Returns:
        Tuple of (Unseason, duration) if triggered, None otherwise
    """
    # Don't trigger if unseason already active
    if current_state.is_active():
        return None

    # Hitching: 1-in-4 on Dolmenday (last day of year = day 30 of month 12)
    if is_dolmenday(month, day):
        if DiceRoller.randint(1, 4, "Hitching check (1-in-4 on Dolmenday)") == 1:
            return (Unseason.HITCHING, 20)

    # Colliggwyld: 1-in-4 on first day of Iggwyld (month 6)
    if month == 6 and day == 1:
        if DiceRoller.randint(1, 4, "Colliggwyld check (1-in-4 on 1st of Iggwyld)") == 1:
            # Lasts the entire month
            return (Unseason.COLLIGGWYLD, MONTHS[6].days)

    # Chame: 1-in-20 on days 1-5 of Haelhold (month 9)
    if month == 9 and 1 <= day <= 5:
        if DiceRoller.randint(1, 20, f"Chame check (1-in-20 on day {day} of Haelhold)") == 1:
            duration = DiceRoller.roll("2d10", "Chame duration").total
            return (Unseason.CHAME, duration)

    # Vague: 1-in-10 on first day of each week in Lymewald (2) or Haggryme (3)
    # Assuming 7-day weeks, first day of week is day 1, 8, 15, 22, 29
    if month in (2, 3) and day in (1, 8, 15, 22, 29):
        month_name = MONTHS[month].name
        if DiceRoller.randint(1, 10, f"Vague check (1-in-10 on week start in {month_name})") == 1:
            duration = DiceRoller.roll("1d6", "Vague duration").total
            return (Unseason.VAGUE, duration)

    return None


def get_active_unseason_effects(state: UnseasonState) -> dict[str, Any]:
    """
    Get the special effects for the currently active unseason.

    Returns a dictionary with:
    - special_encounters: Whether special encounter table applies
    - special_encounter_chance: X-in-6 chance of special encounter
    - foraging_bonus: Multiplier for foraging (Colliggwyld doubles fungi)
    - description: Narrative description of the unseason
    """
    if not state.is_active():
        return {
            "special_encounters": False,
            "special_encounter_chance": 0,
            "foraging_bonus": 1.0,
            "description": None,
        }

    if state.active == Unseason.HITCHING:
        return {
            "special_encounters": False,
            "special_encounter_chance": 0,
            "foraging_bonus": 1.0,
            "description": (
                "The trees drip with dew, the woods are filled with balmy mists, "
                "and the eternal night of the fairy realm of Everborne encroaches upon "
                "the mortal world. The fey moon shines at night alongside the true moon."
            ),
        }

    elif state.active == Unseason.COLLIGGWYLD:
        return {
            "special_encounters": False,
            "special_encounter_chance": 0,
            "foraging_bonus": 2.0,  # Double fungi
            "description": (
                "Particularly beautiful and fecund fungus blooms throughout the Wood. "
                "These blossoms grow to fantastic proportions, dwarfing humans. "
                "All fungi found by foraging are in twice the normal quantity."
            ),
        }

    elif state.active == Unseason.CHAME:
        return {
            "special_encounters": True,
            "special_encounter_chance": 2,  # 2-in-6
            "encounter_table": "chame",  # Serpents and wyrms
            "foraging_bonus": 1.0,
            "description": (
                "Chame is a period of snakes and unease. Serpents of all sizes "
                "fill the wood, creeping from underneath rocks and slithering "
                "out of holes in trees. Travel is perilous."
            ),
        }

    elif state.active == Unseason.VAGUE:
        return {
            "special_encounters": True,
            "special_encounter_chance": 2,  # 2-in-6
            "encounter_table": "vague",  # Undead
            "foraging_bonus": 1.0,
            "description": (
                "A thick, sinister fog emerges from the earth and rolls in great "
                "clouds through the forest. Ghosts, phantoms, and ghouls roam with "
                "the fogs, ensuring that only the desperate venture out of doors."
            ),
        }

    return {
        "special_encounters": False,
        "special_encounter_chance": 0,
        "foraging_bonus": 1.0,
        "description": None,
    }


# Note: Unseason encounter tables (Chame and Vague) are defined in
# src/tables/wilderness_encounter_tables.py and used by the EncounterRoller.
# The encounter system already handles unseason encounters with a 2-in-6 chance
# when active_unseason is set in the EncounterContext.
#
# To roll unseason encounters, use:
#   from src.tables.encounter_roller import roll_wilderness_encounter
#   result = roll_wilderness_encounter(region, active_unseason="chame")
#
# The EncounterRoller._check_unseason_encounter() method handles the 2-in-6
# trigger chance and rolls on the appropriate CHAME_TABLE or VAGUE_TABLE.
