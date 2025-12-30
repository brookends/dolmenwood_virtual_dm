"""
Encounter Factory for Dolmenwood Virtual DM.

Creates EncounterState instances from RolledEncounter results.
This bridges the gap between:
- EncounterRoller (which generates RolledEncounter from tables)
- EncounterEngine (which handles the encounter sequence)

The factory:
1. Creates Combatants from the rolled entry
2. Rolls surprise and encounter distance
3. Builds a complete EncounterState ready for the EncounterEngine
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.data_models import (
    Combatant,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    StatBlock,
)
from src.content_loader.monster_registry import MonsterRegistry, get_monster_registry
from src.npc.encounter_npc_generator import (
    EncounterNPCGenerator,
    get_encounter_npc_generator,
    EverydayMortalResult,
    AdventurerResult,
    AdventuringPartyResult,
)
from src.tables.encounter_roller import (
    EncounterRoller,
    RolledEncounter,
    EncounterEntryType,
    EncounterContext,
    get_encounter_roller,
)


logger = logging.getLogger(__name__)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class EncounterFactoryResult:
    """
    Result of creating an encounter from a RolledEncounter.

    Contains the EncounterState plus additional context useful for
    the DM Agent or other systems.
    """
    encounter_state: EncounterState

    # Original roll details
    rolled_encounter: RolledEncounter

    # Generated NPCs (for reference)
    everyday_mortals: list[EverydayMortalResult] = field(default_factory=list)
    adventurers: list[AdventurerResult] = field(default_factory=list)
    adventuring_party: Optional[AdventuringPartyResult] = None

    # Lair information
    in_lair: bool = False
    lair_description: Optional[str] = None
    hoard: Optional[str] = None

    # Surprise details
    party_surprised: bool = False
    enemies_surprised: bool = False

    # Distance
    encounter_distance: int = 60


# =============================================================================
# ENCOUNTER FACTORY
# =============================================================================

class EncounterFactory:
    """
    Factory for creating EncounterState from RolledEncounter.

    Usage:
        # Using defaults
        factory = EncounterFactory()
        result = factory.create_encounter(rolled_encounter)
        encounter_state = result.encounter_state

        # With explicit dependencies
        factory = EncounterFactory(
            monster_registry=my_registry,
            npc_generator=my_generator,
            encounter_roller=my_roller,
        )
    """

    def __init__(
        self,
        monster_registry: Optional[MonsterRegistry] = None,
        npc_generator: Optional[EncounterNPCGenerator] = None,
        encounter_roller: Optional[EncounterRoller] = None,
    ):
        """
        Initialize the encounter factory.

        Args:
            monster_registry: Registry for monster lookup (uses default if None)
            npc_generator: Generator for NPCs (uses default if None)
            encounter_roller: Roller for surprise/distance (uses default if None)
        """
        self._monster_registry = monster_registry
        self._npc_generator = npc_generator
        self._encounter_roller = encounter_roller

    @property
    def monster_registry(self) -> MonsterRegistry:
        """Get the monster registry."""
        if self._monster_registry is None:
            self._monster_registry = get_monster_registry()
        return self._monster_registry

    @property
    def npc_generator(self) -> EncounterNPCGenerator:
        """Get the NPC generator."""
        if self._npc_generator is None:
            self._npc_generator = get_encounter_npc_generator()
        return self._npc_generator

    @property
    def encounter_roller(self) -> EncounterRoller:
        """Get the encounter roller."""
        if self._encounter_roller is None:
            self._encounter_roller = get_encounter_roller()
        return self._encounter_roller

    def create_encounter(
        self,
        rolled_encounter: RolledEncounter,
        terrain: str = "",
        is_outdoor: bool = True,
    ) -> EncounterFactoryResult:
        """
        Create an EncounterState from a RolledEncounter.

        Args:
            rolled_encounter: The result of rolling on encounter tables
            terrain: Terrain description for the encounter
            is_outdoor: True for wilderness, False for dungeon (affects distance)

        Returns:
            EncounterFactoryResult with the EncounterState and details
        """
        # Step 1: Create combatants based on entry type
        combatants, npcs = self._create_combatants(rolled_encounter)

        # Step 2: Roll surprise
        party_surprised, enemies_surprised = self.encounter_roller.roll_surprise()
        surprise_status = self._determine_surprise_status(
            party_surprised, enemies_surprised
        )

        # Step 3: Roll encounter distance
        both_surprised = party_surprised and enemies_surprised
        if is_outdoor:
            distance = self.encounter_roller.roll_encounter_distance(both_surprised)
        else:
            # Dungeon: 2d6 × 10' (or 1d4 × 10' if both surprised)
            from src.data_models import DiceRoller
            if both_surprised:
                distance = DiceRoller.roll("1d4", "Dungeon encounter distance").total * 10
            else:
                distance = DiceRoller.roll("2d6", "Dungeon encounter distance").total * 10

        # Step 4: Determine encounter type
        encounter_type = self._determine_encounter_type(rolled_encounter)

        # Step 5: Build actor IDs list
        actor_ids = [c.combatant_id for c in combatants]

        # Step 6: Determine context from activity
        context = rolled_encounter.activity or ""

        # Step 7: Use terrain from context or parameter
        final_terrain = terrain or rolled_encounter.terrain_type or ""

        # Step 8: Create EncounterState
        encounter_state = EncounterState(
            encounter_type=encounter_type,
            distance=distance,
            surprise_status=surprise_status,
            actors=actor_ids,
            context=context,
            terrain=final_terrain,
            combatants=combatants,
        )

        return EncounterFactoryResult(
            encounter_state=encounter_state,
            rolled_encounter=rolled_encounter,
            everyday_mortals=npcs.get("mortals", []),
            adventurers=npcs.get("adventurers", []),
            adventuring_party=npcs.get("party"),
            in_lair=rolled_encounter.in_lair,
            lair_description=rolled_encounter.lair_description,
            hoard=rolled_encounter.hoard,
            party_surprised=party_surprised,
            enemies_surprised=enemies_surprised,
            encounter_distance=distance,
        )

    def _create_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> tuple[list[Combatant], dict]:
        """
        Create combatants based on the encounter entry type.

        Returns:
            Tuple of (combatants list, dict of generated NPCs)
        """
        entry_type = rolled_encounter.entry_type
        npcs: dict = {"mortals": [], "adventurers": [], "party": None}

        if entry_type == EncounterEntryType.MONSTER:
            combatants = self._create_monster_combatants(rolled_encounter)

        elif entry_type == EncounterEntryType.ANIMAL:
            combatants = self._create_animal_combatants(rolled_encounter)

        elif entry_type == EncounterEntryType.ADVENTURER:
            combatants, adventurers = self._create_adventurer_combatants(rolled_encounter)
            npcs["adventurers"] = adventurers

        elif entry_type == EncounterEntryType.EVERYDAY_MORTAL:
            combatants, mortals = self._create_mortal_combatants(rolled_encounter)
            npcs["mortals"] = mortals

        elif entry_type == EncounterEntryType.ADVENTURING_PARTY:
            combatants, party = self._create_party_combatants(rolled_encounter)
            npcs["party"] = party
            npcs["adventurers"] = party.members if party else []

        else:
            logger.warning(f"Unknown entry type: {entry_type}, creating basic combatant")
            combatants = self._create_fallback_combatants(rolled_encounter)

        return combatants, npcs

    def _create_monster_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> list[Combatant]:
        """Create combatants for monster encounters."""
        combatants = []
        monster_id = rolled_encounter.entry.monster_id

        if not monster_id:
            # Try to derive from name
            monster_id = rolled_encounter.entry.name.lower().replace(" ", "_").replace(",", "")

        for i in range(rolled_encounter.number_appearing):
            combatant_id = f"{monster_id}_{uuid.uuid4().hex[:8]}"

            # Create unique name if multiple
            if rolled_encounter.number_appearing > 1:
                name = f"{rolled_encounter.entry.name} #{i + 1}"
            else:
                name = rolled_encounter.entry.name

            combatant = self.monster_registry.create_combatant(
                monster_id=monster_id,
                combatant_id=combatant_id,
                side="enemy",
                name_override=name,
                roll_hp=True,
            )

            if combatant:
                combatants.append(combatant)
            else:
                # Fallback: create basic combatant
                logger.warning(f"Monster '{monster_id}' not found, creating fallback")
                combatants.append(self._create_basic_combatant(
                    combatant_id, name
                ))

        return combatants

    def _create_animal_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> list[Combatant]:
        """Create combatants for animal encounters."""
        # Animals use the same logic as monsters
        return self._create_monster_combatants(rolled_encounter)

    def _create_adventurer_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> tuple[list[Combatant], list[AdventurerResult]]:
        """Create combatants for adventurer encounters."""
        combatants = []
        adventurers = []

        # Parse class from entry name (e.g., "Fighter†" -> "fighter")
        class_name = rolled_encounter.entry.name.rstrip("†").strip()

        # Handle special cases like "Thief (Bandit)†"
        if "(" in class_name:
            class_name = class_name.split("(")[0].strip()

        class_id = class_name.lower()

        for i in range(rolled_encounter.number_appearing):
            # Roll a random level (1-5 range, weighted toward lower)
            from src.data_models import DiceRoller
            level_roll = DiceRoller.roll("1d6", "Adventurer level").total
            level = min(level_roll, 5)  # Cap at 5

            adventurer = self.npc_generator.generate_adventurer(
                class_id=class_id,
                level=level,
            )

            if adventurer:
                adventurers.append(adventurer)
                combatants.append(Combatant(
                    combatant_id=adventurer.adventurer_id,
                    name=adventurer.name,
                    side="enemy",
                    stat_block=adventurer.stat_block,
                ))
            else:
                # Fallback
                combatant_id = f"adventurer_{uuid.uuid4().hex[:8]}"
                combatants.append(self._create_basic_combatant(
                    combatant_id, f"{class_name} #{i + 1}"
                ))

        return combatants, adventurers

    def _create_mortal_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> tuple[list[Combatant], list[EverydayMortalResult]]:
        """Create combatants for everyday mortal encounters."""
        combatants = []
        mortals_list = []

        # Parse mortal type from entry name (e.g., "Pilgrim‡" -> "pilgrim")
        mortal_name = rolled_encounter.entry.name.rstrip("‡").strip()
        mortal_type = mortal_name.lower().replace("-", "_").replace(" ", "_")

        # Generate the mortals as a group
        mortals = self.npc_generator.generate_everyday_mortals(
            mortal_type=mortal_type,
            count=rolled_encounter.number_appearing,
        )

        for mortal in mortals:
            mortals_list.append(mortal)
            combatants.append(Combatant(
                combatant_id=mortal.mortal_id,
                name=mortal.name,
                side="enemy",  # Default to enemy, can change based on reaction
                stat_block=mortal.stat_block,
            ))

        return combatants, mortals_list

    def _create_party_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> tuple[list[Combatant], Optional[AdventuringPartyResult]]:
        """Create combatants for adventuring party encounters."""
        party = self.npc_generator.generate_adventuring_party()

        combatants = []
        for member in party.members:
            combatants.append(Combatant(
                combatant_id=member.adventurer_id,
                name=member.name,
                side="enemy",  # Default, changes based on alignment/reaction
                stat_block=member.stat_block,
            ))

        return combatants, party

    def _create_fallback_combatants(
        self,
        rolled_encounter: RolledEncounter,
    ) -> list[Combatant]:
        """Create basic combatants when entry type is unknown."""
        combatants = []
        for i in range(rolled_encounter.number_appearing):
            combatant_id = f"unknown_{uuid.uuid4().hex[:8]}"
            name = rolled_encounter.entry.name
            if rolled_encounter.number_appearing > 1:
                name = f"{name} #{i + 1}"
            combatants.append(self._create_basic_combatant(combatant_id, name))
        return combatants

    def _create_basic_combatant(
        self,
        combatant_id: str,
        name: str,
    ) -> Combatant:
        """Create a basic combatant with minimal stats."""
        return Combatant(
            combatant_id=combatant_id,
            name=name,
            side="enemy",
            stat_block=StatBlock(
                armor_class=10,
                hit_dice="1d4",
                hp_max=4,
                hp_current=4,
                movement=30,
                attacks=[{"name": "Attack", "damage": "1d4", "bonus": 0}],
                morale=6,
            ),
        )

    def _determine_surprise_status(
        self,
        party_surprised: bool,
        enemies_surprised: bool,
    ) -> SurpriseStatus:
        """Determine the surprise status from roll results."""
        if party_surprised and enemies_surprised:
            return SurpriseStatus.MUTUAL_SURPRISE
        elif party_surprised:
            return SurpriseStatus.PARTY_SURPRISED
        elif enemies_surprised:
            return SurpriseStatus.ENEMIES_SURPRISED
        else:
            return SurpriseStatus.NO_SURPRISE

    def _determine_encounter_type(
        self,
        rolled_encounter: RolledEncounter,
    ) -> EncounterType:
        """Determine the EncounterType from the rolled entry."""
        entry_type = rolled_encounter.entry_type

        # Lair encounters
        if rolled_encounter.in_lair:
            return EncounterType.LAIR

        # Map entry types to encounter types
        if entry_type == EncounterEntryType.MONSTER:
            return EncounterType.MONSTER
        elif entry_type == EncounterEntryType.ANIMAL:
            return EncounterType.MONSTER  # Animals use monster encounter type
        elif entry_type in (
            EncounterEntryType.ADVENTURER,
            EncounterEntryType.EVERYDAY_MORTAL,
            EncounterEntryType.ADVENTURING_PARTY,
        ):
            return EncounterType.NPC
        else:
            return EncounterType.MONSTER


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================

_factory: Optional[EncounterFactory] = None


def get_encounter_factory() -> EncounterFactory:
    """Get the shared EncounterFactory instance."""
    global _factory
    if _factory is None:
        _factory = EncounterFactory()
    return _factory


def reset_encounter_factory() -> None:
    """Reset the shared EncounterFactory instance."""
    global _factory
    _factory = None


def create_encounter_from_roll(
    rolled_encounter: RolledEncounter,
    terrain: str = "",
    is_outdoor: bool = True,
) -> EncounterFactoryResult:
    """
    Convenience function to create an encounter from a rolled result.

    Args:
        rolled_encounter: The result of rolling on encounter tables
        terrain: Terrain description
        is_outdoor: True for wilderness, False for dungeon

    Returns:
        EncounterFactoryResult with the EncounterState
    """
    factory = get_encounter_factory()
    return factory.create_encounter(rolled_encounter, terrain, is_outdoor)


def create_wilderness_encounter(
    region: str,
    terrain: str = "",
    is_day: bool = True,
    on_road: bool = False,
    has_fire: bool = True,
    is_aquatic: bool = False,
    active_unseason: Optional[str] = None,
) -> EncounterFactoryResult:
    """
    Convenience function to roll and create a wilderness encounter.

    This combines the EncounterRoller and EncounterFactory into one call.

    Args:
        region: Region identifier
        terrain: Terrain description
        is_day: True for daytime, False for night
        on_road: True if on road/track
        has_fire: True if party has fire (nighttime only)
        is_aquatic: True for water encounters
        active_unseason: Current unseason if any

    Returns:
        EncounterFactoryResult with the EncounterState
    """
    roller = get_encounter_roller()
    rolled = roller.roll_encounter_simple(
        region=region,
        is_day=is_day,
        on_road=on_road,
        has_fire=has_fire,
    )

    # Update context if aquatic
    if is_aquatic:
        context = EncounterContext(
            region=region,
            is_aquatic=True,
            active_unseason=active_unseason,
        )
        rolled = roller.roll_encounter(context, roll_activity=True)

    factory = get_encounter_factory()
    return factory.create_encounter(rolled, terrain=terrain, is_outdoor=True)
