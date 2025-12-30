"""
Encounter Roller for Dolmenwood.

Orchestrates the encounter generation process:
1. Determines which encounter table to use based on conditions
2. Rolls on the appropriate tables
3. Returns a structured encounter result

This is the main entry point for generating wilderness encounters.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from src.data_models import DiceRoller

if TYPE_CHECKING:
    from src.content_loader.monster_registry import MonsterRegistry

from src.tables.wilderness_encounter_tables import (
    TimeOfDay,
    LocationType,
    EncounterCategory,
    EncounterEntry,
    ENCOUNTER_TYPE_TABLE,
    COMMON_TABLES,
    REGIONAL_TABLES,
    UNSEASON_TABLES,
    get_encounter_type_table,
    get_common_table,
    get_regional_table,
    get_unseason_table,
)


logger = logging.getLogger(__name__)


def _roll_number_appearing(dice_expr: str, entry_name: str) -> int:
    """
    Roll number appearing, handling both dice notation and plain numbers.

    Args:
        dice_expr: Dice expression (e.g., "2d6") or plain number (e.g., "1")
        entry_name: Name of the entry (for logging)

    Returns:
        The rolled or fixed number
    """
    # Check if it's a plain number
    if 'd' not in dice_expr.lower():
        try:
            return int(dice_expr)
        except ValueError:
            return 1

    # Roll dice
    return DiceRoller.roll(dice_expr, f"Number appearing: {entry_name}").total


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

class EncounterEntryType(str, Enum):
    """Type of encounter entry."""
    MONSTER = "monster"
    ANIMAL = "animal"
    ADVENTURER = "adventurer"
    EVERYDAY_MORTAL = "everyday_mortal"
    ADVENTURING_PARTY = "adventuring_party"


@dataclass
class RolledEncounter:
    """
    Result of rolling on encounter tables.

    Contains the raw roll results before resolution to actual creatures.
    """
    # The rolled entry
    entry: EncounterEntry
    entry_type: EncounterEntryType

    # Roll context
    category: EncounterCategory
    region: Optional[str] = None
    unseason: Optional[str] = None

    # Number appearing
    number_appearing_dice: str = "1"
    number_appearing: int = 1

    # Conditions that led to this roll
    time_of_day: Optional[TimeOfDay] = None
    location_type: Optional[LocationType] = None
    terrain_type: Optional[str] = None

    # Roll details (for logging/debugging)
    encounter_type_roll: int = 0
    creature_roll: int = 0

    # Optional activity
    activity: Optional[str] = None

    # Lair information (from monster data)
    in_lair: bool = False
    lair_chance: Optional[int] = None  # Monster's lair percentage (None = no lair possible)
    lair_description: Optional[str] = None  # Randomly selected lair description
    hoard: Optional[str] = None  # Treasure type code for lair (e.g., "C4 + R3")


@dataclass
class EncounterContext:
    """
    Context for encounter generation.

    Provides all the information needed to determine which tables to use.
    """
    time_of_day: TimeOfDay = TimeOfDay.DAYTIME
    location_type: LocationType = LocationType.WILD
    region: str = "tithelands"  # Default region
    terrain_type: str = "forest"

    # Unseason status
    active_unseason: Optional[str] = None  # "chame", "vague", "hitching", "colliggwyld"

    # Aquatic override
    is_aquatic: bool = False  # True for rivers/lakes


# =============================================================================
# ENCOUNTER ROLLER
# =============================================================================

@dataclass
class LairCheckResult:
    """Result of checking for a lair encounter."""
    in_lair: bool = False
    lair_chance: Optional[int] = None
    lair_description: Optional[str] = None
    hoard: Optional[str] = None


class EncounterRoller:
    """
    Rolls on encounter tables based on context.

    Usage:
        roller = EncounterRoller()

        # Create context
        context = EncounterContext(
            time_of_day=TimeOfDay.DAYTIME,
            location_type=LocationType.WILD,
            region="aldweald",
        )

        # Roll encounter
        result = roller.roll_encounter(context)

        # Result contains the entry and all roll details
        print(f"Encountered: {result.entry.name} x{result.number_appearing}")
    """

    def __init__(self, monster_registry: Optional["MonsterRegistry"] = None):
        """
        Initialize the encounter roller.

        Args:
            monster_registry: Optional MonsterRegistry for lair data lookup.
                              If not provided, uses the default singleton.
        """
        self._monster_registry = monster_registry

    @property
    def monster_registry(self) -> "MonsterRegistry":
        """Get the monster registry, loading default if needed."""
        if self._monster_registry is None:
            from src.content_loader.monster_registry import get_monster_registry
            self._monster_registry = get_monster_registry()
        return self._monster_registry

    def _check_lair(self, monster_id: Optional[str]) -> LairCheckResult:
        """
        Check if encounter is in a lair based on monster data.

        Args:
            monster_id: The monster's ID to look up

        Returns:
            LairCheckResult with lair information
        """
        if monster_id is None:
            return LairCheckResult()

        # Look up the monster
        result = self.monster_registry.get_monster(monster_id)
        if not result.found or result.monster is None:
            logger.debug(f"Monster '{monster_id}' not found in registry, skipping lair check")
            return LairCheckResult()

        monster = result.monster

        # Check if monster has a lair
        if monster.lair_percentage is None:
            # This monster has no lair
            return LairCheckResult(lair_chance=None)

        lair_chance = monster.lair_percentage

        # Roll against the lair percentage
        in_lair = DiceRoller.percent_check(lair_chance, f"Lair check ({monster.name})")

        if not in_lair:
            return LairCheckResult(in_lair=False, lair_chance=lair_chance)

        # Monster is in lair - select a random lair description
        lair_description = None
        if monster.lair_descriptions:
            lair_description = DiceRoller.choice(monster.lair_descriptions, "lair description")

        return LairCheckResult(
            in_lair=True,
            lair_chance=lair_chance,
            lair_description=lair_description,
            hoard=monster.hoard,
        )

    def roll_encounter(
        self,
        context: EncounterContext,
        roll_activity: bool = False,
        check_lair: bool = True,
    ) -> RolledEncounter:
        """
        Roll a complete encounter based on context.

        Args:
            context: The encounter context (time, location, region, etc.)
            roll_activity: Whether to roll on the activity table
            check_lair: Whether to check for lair encounter

        Returns:
            RolledEncounter with all details
        """
        # Check for unseason override first
        if context.active_unseason in ["chame", "vague"]:
            unseason_result = self._check_unseason_encounter(
                context.active_unseason,
                check_lair=check_lair,
            )
            if unseason_result is not None:
                return unseason_result

        # Check for aquatic encounters
        if context.is_aquatic:
            return self._roll_aquatic_encounter(context, roll_activity, check_lair)

        # Step 1: Roll encounter type (d8)
        type_table = get_encounter_type_table(context.time_of_day, context.location_type)
        type_roll = DiceRoller.roll("1d8", "Encounter type").total
        category = type_table.get(type_roll, EncounterCategory.REGIONAL)

        # Step 2: Roll on the appropriate table (d20)
        if category == EncounterCategory.REGIONAL:
            entry, creature_roll = self._roll_regional(context.region)
        else:
            entry, creature_roll = self._roll_common(category)

        # Step 3: Determine number appearing
        num_appearing_dice = entry.number_appearing
        num_appearing = _roll_number_appearing(num_appearing_dice, entry.name)

        # Step 4: Determine entry type
        entry_type = self._determine_entry_type(entry)

        # Step 5: Check for lair (using monster-specific data)
        lair_result = LairCheckResult()
        if check_lair and entry_type in (EncounterEntryType.MONSTER, EncounterEntryType.ANIMAL):
            lair_result = self._check_lair(entry.monster_id)

        # Step 6: Roll activity if requested
        activity = None
        if roll_activity:
            activity = self._roll_activity()

        return RolledEncounter(
            entry=entry,
            entry_type=entry_type,
            category=category,
            region=context.region if category == EncounterCategory.REGIONAL else None,
            number_appearing_dice=num_appearing_dice,
            number_appearing=num_appearing,
            time_of_day=context.time_of_day,
            location_type=context.location_type,
            terrain_type=context.terrain_type,
            encounter_type_roll=type_roll,
            creature_roll=creature_roll,
            activity=activity,
            in_lair=lair_result.in_lair,
            lair_chance=lair_result.lair_chance,
            lair_description=lair_result.lair_description,
            hoard=lair_result.hoard,
        )

    def _check_unseason_encounter(
        self,
        unseason: str,
        check_lair: bool = True,
    ) -> Optional[RolledEncounter]:
        """
        Check if unseason encounter triggers and roll on unseason table.

        Args:
            unseason: The active unseason ("chame" or "vague")
            check_lair: Whether to check for lair encounter

        Returns:
            RolledEncounter if unseason triggers, None otherwise
        """
        # 2-in-6 chance of unseason encounter
        trigger_roll = DiceRoller.roll("1d6", f"{unseason} trigger check").total
        if trigger_roll > 2:
            return None  # Normal encounter

        # Roll on unseason table
        table = get_unseason_table(unseason)
        if not table:
            return None

        die = table.get("die", "d10")
        roll = DiceRoller.roll(f"1{die}", f"{unseason} encounter").total
        entry = table["entries"].get(roll)

        if entry is None:
            return None

        num_appearing = _roll_number_appearing(entry.number_appearing, entry.name)
        entry_type = self._determine_entry_type(entry)

        # Check for lair using monster-specific data
        lair_result = LairCheckResult()
        if check_lair and entry_type in (EncounterEntryType.MONSTER, EncounterEntryType.ANIMAL):
            lair_result = self._check_lair(entry.monster_id)

        return RolledEncounter(
            entry=entry,
            entry_type=entry_type,
            category=EncounterCategory.REGIONAL,  # Treat as regional
            unseason=unseason,
            number_appearing_dice=entry.number_appearing,
            number_appearing=num_appearing,
            creature_roll=roll,
            in_lair=lair_result.in_lair,
            lair_chance=lair_result.lair_chance,
            lair_description=lair_result.lair_description,
            hoard=lair_result.hoard,
        )

    def _roll_aquatic_encounter(
        self,
        context: EncounterContext,
        roll_activity: bool,
        check_lair: bool,
    ) -> RolledEncounter:
        """Roll directly on the Aquatic regional table."""
        table = get_regional_table("aquatic")
        if not table:
            # Fallback to monster table
            entry, creature_roll = self._roll_common(EncounterCategory.MONSTER)
        else:
            die = table.get("die", "d20")
            creature_roll = DiceRoller.roll(f"1{die}", "Aquatic encounter").total
            entry = table["entries"].get(creature_roll)

        if entry is None:
            # Fallback
            entry = EncounterEntry(name="Fish", number_appearing="1d6", monster_id="fish")

        num_appearing = _roll_number_appearing(entry.number_appearing, entry.name)
        entry_type = self._determine_entry_type(entry)

        # Check for lair using monster-specific data
        lair_result = LairCheckResult()
        if check_lair and entry_type in (EncounterEntryType.MONSTER, EncounterEntryType.ANIMAL):
            lair_result = self._check_lair(entry.monster_id)

        activity = None
        if roll_activity:
            activity = self._roll_activity()

        return RolledEncounter(
            entry=entry,
            entry_type=entry_type,
            category=EncounterCategory.REGIONAL,
            region="aquatic",
            number_appearing_dice=entry.number_appearing,
            number_appearing=num_appearing,
            time_of_day=context.time_of_day,
            location_type=context.location_type,
            terrain_type="water",
            creature_roll=creature_roll,
            activity=activity,
            in_lair=lair_result.in_lair,
            lair_chance=lair_result.lair_chance,
            lair_description=lair_result.lair_description,
            hoard=lair_result.hoard,
        )

    def _roll_common(
        self,
        category: EncounterCategory
    ) -> tuple[EncounterEntry, int]:
        """Roll on a common encounter table."""
        table = get_common_table(category)
        if not table:
            # Fallback
            return EncounterEntry(name="Unknown", number_appearing="1"), 0

        die = table.get("die", "d20")
        roll = DiceRoller.roll(f"1{die}", f"{category.value} encounter").total
        entry = table["entries"].get(roll)

        if entry is None:
            entry = EncounterEntry(name="Unknown", number_appearing="1")

        return entry, roll

    def _roll_regional(self, region: str) -> tuple[EncounterEntry, int]:
        """Roll on a regional encounter table."""
        table = get_regional_table(region)
        if not table:
            logger.warning(f"Unknown region '{region}', using Tithelands")
            table = get_regional_table("tithelands")

        if not table:
            # Ultimate fallback
            return EncounterEntry(name="Unknown", number_appearing="1"), 0

        die = table.get("die", "d20")
        roll = DiceRoller.roll(f"1{die}", f"{region} encounter").total
        entry = table["entries"].get(roll)

        if entry is None:
            entry = EncounterEntry(name="Unknown", number_appearing="1")

        return entry, roll

    def _determine_entry_type(self, entry: EncounterEntry) -> EncounterEntryType:
        """Determine the type of encounter entry."""
        if entry.entry_type == "party" or entry.name == "Adventuring Party":
            return EncounterEntryType.ADVENTURING_PARTY
        elif entry.entry_type == "adventurer" or entry.name.endswith("†"):
            return EncounterEntryType.ADVENTURER
        elif entry.entry_type == "everyday_mortal" or entry.name.endswith("‡"):
            return EncounterEntryType.EVERYDAY_MORTAL
        elif entry.entry_type == "animal" or entry.name.endswith("*"):
            return EncounterEntryType.ANIMAL
        else:
            return EncounterEntryType.MONSTER

    def _roll_activity(self) -> str:
        """Roll on the creature activity table."""
        from src.npc.everyday_mortal_data import CREATURE_ACTIVITY

        die = CREATURE_ACTIVITY.get("die", "d20")
        roll = DiceRoller.roll(f"1{die}", "Creature activity").total
        return CREATURE_ACTIVITY["entries"].get(roll, "Wandering")

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def roll_encounter_simple(
        self,
        region: str,
        is_day: bool = True,
        on_road: bool = False,
        has_fire: bool = True,
    ) -> RolledEncounter:
        """
        Roll an encounter with simplified parameters.

        Args:
            region: Region identifier
            is_day: True for daytime, False for night
            on_road: True if on road/track
            has_fire: True if party has fire/camp (nighttime only)

        Returns:
            RolledEncounter
        """
        time_of_day = TimeOfDay.DAYTIME if is_day else TimeOfDay.NIGHTTIME

        if is_day:
            location_type = LocationType.ROAD if on_road else LocationType.WILD
        else:
            location_type = LocationType.FIRE if has_fire else LocationType.NO_FIRE

        context = EncounterContext(
            time_of_day=time_of_day,
            location_type=location_type,
            region=region,
        )

        return self.roll_encounter(context)

    def roll_surprise(self) -> tuple[bool, bool]:
        """
        Roll surprise for both sides.

        Returns:
            Tuple of (party_surprised, enemy_surprised)
        """
        party_roll = DiceRoller.roll("1d6", "Party surprise").total
        enemy_roll = DiceRoller.roll("1d6", "Enemy surprise").total

        party_surprised = party_roll <= 2
        enemy_surprised = enemy_roll <= 2

        return party_surprised, enemy_surprised

    def roll_encounter_distance(
        self,
        both_surprised: bool = False
    ) -> int:
        """
        Roll encounter distance.

        Args:
            both_surprised: If both sides are surprised, use shorter distance

        Returns:
            Distance in feet
        """
        if both_surprised:
            # 1d4 × 30'
            roll = DiceRoller.roll("1d4", "Encounter distance (both surprised)").total
        else:
            # 2d6 × 30'
            roll = DiceRoller.roll("2d6", "Encounter distance").total

        return roll * 30


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================

_roller: Optional[EncounterRoller] = None


def get_encounter_roller() -> EncounterRoller:
    """Get the shared EncounterRoller instance."""
    global _roller
    if _roller is None:
        _roller = EncounterRoller()
    return _roller


def roll_wilderness_encounter(
    region: str,
    time_of_day: TimeOfDay = TimeOfDay.DAYTIME,
    location_type: LocationType = LocationType.WILD,
    active_unseason: Optional[str] = None,
    is_aquatic: bool = False,
) -> RolledEncounter:
    """
    Convenience function to roll a wilderness encounter.

    Args:
        region: Region identifier
        time_of_day: Daytime or nighttime
        location_type: Road, wild, fire, or no_fire
        active_unseason: Current unseason if any
        is_aquatic: True for water encounters

    Returns:
        RolledEncounter with full details
    """
    roller = get_encounter_roller()
    context = EncounterContext(
        time_of_day=time_of_day,
        location_type=location_type,
        region=region,
        active_unseason=active_unseason,
        is_aquatic=is_aquatic,
    )
    return roller.roll_encounter(context)
