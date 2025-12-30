"""
Encounter NPC Generator for Dolmenwood.

Handles generation of NPCs for random encounters, including:
- Everyday Mortals (non-adventuring NPCs like anglers, criers, villagers)
- Adventurers (classed NPCs at levels 1, 3, or 5)
- Adventuring Parties (full parties with treasure and quests)

This generator uses pre-defined templates rather than dynamic generation,
as encounter NPCs have specific stat blocks defined in the rulebooks.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from src.data_models import DiceRoller, StatBlock

from src.npc.everyday_mortal_data import (
    EVERYDAY_MORTAL_STATS,
    EVERYDAY_MORTAL_TYPES,
    BASIC_DETAILS,
    CREATURE_ACTIVITY,
    get_mortal_type,
)
from src.npc.adventurer_data import (
    ADVENTURER_TEMPLATES,
    KINDRED_TRAITS,
    CLERIC_HOLY_ORDERS,
    get_adventurer_template,
)
from src.npc.adventurer_tables import (
    ADVENTURER_KINDRED,
    CLASS_BY_KINDRED,
    ALIGNMENT,
    QUESTS,
    PARTY_TREASURE,
    ADVENTURER_POSSESSIONS,
    MAGIC_ITEM_CATEGORIES,
    PARTY_SIZE,
    PARTY_LEVEL,
    MOUNTED_CHANCE,
    get_class_for_kindred,
    get_quest_table,
    is_spell_caster,
    get_magic_item_chance,
)


logger = logging.getLogger(__name__)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class EverydayMortalResult:
    """Result of generating everyday mortal(s)."""
    mortal_id: str
    mortal_type: str
    name: str
    count: int
    stat_block: StatBlock
    basic_details: Optional[dict] = None
    type_details: dict = field(default_factory=dict)
    special_mechanics: list[dict] = field(default_factory=list)
    kindred: str = "human"


@dataclass
class AdventurerResult:
    """Result of generating a single adventurer."""
    adventurer_id: str
    name: str
    class_id: str
    title: str
    level: int
    kindred: str
    alignment: str
    stat_block: StatBlock
    gear: list[str] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    skills: dict[str, int] = field(default_factory=dict)
    magic_abilities: list[str] = field(default_factory=list)
    special_abilities: list[str] = field(default_factory=list)
    companions: list[str] = field(default_factory=list)
    possessions_gp: int = 0
    magic_items: list[str] = field(default_factory=list)
    holy_order: Optional[dict] = None
    combat_talents: list[str] = field(default_factory=list)
    kindred_traits: dict = field(default_factory=dict)


@dataclass
class AdventuringPartyResult:
    """Result of generating an adventuring party."""
    party_id: str
    members: list[AdventurerResult]
    party_level_tier: int  # 1-3 for normal, 4-9 for high level
    is_high_level: bool
    alignment: str
    quest: str
    treasure: dict
    is_mounted: bool
    marching_order: list[str]


# =============================================================================
# ENCOUNTER NPC GENERATOR
# =============================================================================

class EncounterNPCGenerator:
    """
    Generator for encounter NPCs including everyday mortals and adventurers.

    Usage:
        generator = EncounterNPCGenerator()

        # Generate everyday mortals
        mortals = generator.generate_everyday_mortals("villager", count=5)

        # Generate adventurers
        fighter = generator.generate_adventurer("fighter", level=3, kindred="human")

        # Generate full adventuring party
        party = generator.generate_adventuring_party(on_road=True)
    """

    def __init__(self):
        """Initialize the encounter NPC generator."""
        pass

    # =========================================================================
    # EVERYDAY MORTALS
    # =========================================================================

    def generate_everyday_mortals(
        self,
        mortal_type: str,
        count: int = 1,
        include_basic_details: bool = True,
        roll_type_tables: bool = True,
    ) -> list[EverydayMortalResult]:
        """
        Generate one or more everyday mortals of a given type.

        Args:
            mortal_type: Type ID (e.g., "villager", "merchant", "pilgrim")
            count: Number of mortals to generate
            include_basic_details: Whether to roll basic details (sex, age, etc.)
            roll_type_tables: Whether to roll on type-specific tables

        Returns:
            List of EverydayMortalResult objects
        """
        type_data = EVERYDAY_MORTAL_TYPES.get(mortal_type.lower())
        if not type_data:
            logger.warning(f"Unknown everyday mortal type: {mortal_type}")
            return []

        results = []
        for i in range(count):
            mortal_id = f"mortal_{mortal_type}_{str(uuid.uuid4())[:8]}"

            # Create shared stat block
            stat_block = self._create_everyday_mortal_stat_block()

            # Roll basic details if requested
            basic_details = None
            if include_basic_details:
                basic_details = self._roll_basic_details()

            # Determine kindred
            kindred = "human"
            if basic_details and "kindred" in basic_details:
                kindred = basic_details["kindred"].lower()
            elif type_data.get("kindred_preference"):
                kindred = DiceRoller.choice(
                    type_data["kindred_preference"],
                    f"{mortal_type} kindred"
                )

            # Roll type-specific tables
            type_details = {}
            if roll_type_tables and type_data.get("roll_tables"):
                type_details = self._roll_type_tables(type_data["roll_tables"])

            # Generate a name
            name = self._generate_mortal_name(kindred, basic_details)

            results.append(EverydayMortalResult(
                mortal_id=mortal_id,
                mortal_type=mortal_type,
                name=name,
                count=1,
                stat_block=stat_block,
                basic_details=basic_details,
                type_details=type_details,
                special_mechanics=type_data.get("special_mechanics", []),
                kindred=kindred,
            ))

        return results

    def _create_everyday_mortal_stat_block(self) -> StatBlock:
        """Create the shared stat block for everyday mortals."""
        stats = EVERYDAY_MORTAL_STATS

        # Roll HP
        hp = DiceRoller.roll(stats["hp_dice"], "Everyday mortal HP").total

        # Random weapon
        weapon = DiceRoller.choice(stats["weapons"], "Everyday mortal weapon")
        weapon_name = weapon.split(" ")[0]
        damage = "1d4"  # All everyday mortal weapons do 1d4

        return StatBlock(
            armor_class=stats["armor_class"],
            hit_dice=stats["hp_dice"],
            hp_current=hp,
            hp_max=hp,
            movement=stats["speed"],
            attacks=[{
                "name": weapon_name,
                "damage": damage,
                "bonus": stats["attack_bonus"],
            }],
            morale=stats["morale"],
            save_as="Normal Human",
            special_abilities=[],
        )

    def _roll_basic_details(self) -> dict:
        """Roll on the basic details tables."""
        details = {}

        for detail_name, table in BASIC_DETAILS.items():
            die = table["die"]
            roll = DiceRoller.roll(die, f"Basic detail: {detail_name}").total
            details[detail_name] = table["entries"].get(roll, "Unknown")

        return details

    def _roll_type_tables(self, tables: dict) -> dict:
        """Roll on type-specific tables."""
        results = {}

        for table_name, table_data in tables.items():
            die = table_data["die"]
            roll = DiceRoller.roll(die, f"Type table: {table_name}").total
            entry = table_data["entries"].get(roll)

            if entry is not None:
                results[table_name] = entry

        return results

    def _generate_mortal_name(
        self,
        kindred: str,
        basic_details: Optional[dict]
    ) -> str:
        """Generate a name for an everyday mortal."""
        # Simple name generation - could be expanded with kindred-specific tables
        sex = "male"
        if basic_details and basic_details.get("sex"):
            sex = basic_details["sex"].lower()

        male_names = [
            "Aldric", "Bertram", "Cedric", "Dunstan", "Edmund",
            "Godwin", "Harold", "Ivor", "Kendrick", "Leofric",
        ]
        female_names = [
            "Aelfleda", "Beatrice", "Cyneburh", "Edith", "Frideswide",
            "Godgifu", "Hild", "Isolde", "Leofrun", "Mildred",
        ]

        names = female_names if sex == "female" else male_names
        return DiceRoller.choice(names, "Mortal name")

    # =========================================================================
    # ADVENTURERS
    # =========================================================================

    def generate_adventurer(
        self,
        class_id: str,
        level: int = 1,
        kindred: Optional[str] = None,
        alignment: Optional[str] = None,
        roll_magic_items: bool = False,
        name: Optional[str] = None,
    ) -> Optional[AdventurerResult]:
        """
        Generate a single adventurer from a template.

        Args:
            class_id: Class identifier (e.g., "fighter", "cleric")
            level: Character level (uses closest template: 1, 3, or 5)
            kindred: Kindred identifier (random if not specified)
            alignment: Alignment (random if not specified)
            roll_magic_items: Whether to roll for magic items
            name: Character name (generated if not specified)

        Returns:
            AdventurerResult or None if template not found
        """
        template = get_adventurer_template(class_id, level)
        if not template:
            logger.warning(f"No template found for {class_id} level {level}")
            return None

        adventurer_id = f"adv_{class_id}_{str(uuid.uuid4())[:8]}"

        # Determine kindred
        if kindred is None:
            # Check if template has kindred preference
            if "kindred_preference" in template:
                kindred = DiceRoller.choice(
                    template["kindred_preference"],
                    f"{class_id} kindred"
                )
            else:
                # Roll on kindred table
                kindred_roll = DiceRoller.roll("1d12", "Adventurer kindred").total
                kindred = ADVENTURER_KINDRED["entries"].get(kindred_roll, "human")

        # Determine alignment
        if alignment is None:
            if "alignment" in template:
                alignment = DiceRoller.choice(
                    template["alignment"],
                    f"{class_id} alignment"
                )
            else:
                alignment_roll = DiceRoller.roll("1d6", "Adventurer alignment").total
                alignment = ALIGNMENT["entries"].get(alignment_roll, "Neutral")

        # Create stat block
        stat_block = self._create_adventurer_stat_block(template, kindred)

        # Generate name
        if name is None:
            name = self._generate_adventurer_name(kindred)

        # Roll possessions
        possessions_gp = 0
        if level > 0:
            gold_roll = DiceRoller.roll(
                ADVENTURER_POSSESSIONS["gold_per_level"],
                "Adventurer gold"
            ).total
            possessions_gp = gold_roll * level

        # Roll magic items if requested
        magic_items = []
        if roll_magic_items:
            magic_items = self._roll_magic_items(class_id, level)

        # Get holy order for clerics
        holy_order = None
        if template.get("holy_order") and level >= 3:
            order_roll = DiceRoller.roll("1d6", "Cleric holy order").total
            holy_order = CLERIC_HOLY_ORDERS["entries"].get(order_roll)

        # Get kindred traits
        kindred_traits = KINDRED_TRAITS.get(kindred.lower(), {})

        return AdventurerResult(
            adventurer_id=adventurer_id,
            name=name,
            class_id=class_id,
            title=template.get("title", class_id.capitalize()),
            level=template.get("level", level),
            kindred=kindred,
            alignment=alignment,
            stat_block=stat_block,
            gear=template.get("gear", []),
            spells=template.get("spells", []),
            skills=template.get("skills", {}),
            magic_abilities=template.get("magic", []),
            special_abilities=template.get("special_abilities", []),
            companions=template.get("companions", []),
            possessions_gp=possessions_gp,
            magic_items=magic_items,
            holy_order=holy_order,
            combat_talents=template.get("combat_talents", []),
            kindred_traits=kindred_traits,
        )

    def _create_adventurer_stat_block(
        self,
        template: dict,
        kindred: str
    ) -> StatBlock:
        """Create a stat block from an adventurer template."""
        # Roll HP
        hp_dice = template.get("hp_dice", "1d8")
        hp = DiceRoller.roll(hp_dice, "Adventurer HP").total

        # Get AC (may be modified by kindred)
        ac = template.get("armor_class", 10)
        kindred_traits = KINDRED_TRAITS.get(kindred.lower(), {})

        # Apply kindred AC bonuses if applicable
        # Note: This is simplified; full implementation would check armor type
        if kindred_traits.get("ac_bonus_light_armor"):
            # Breggles get +1 AC in light or no armor
            # We'd need to check actual armor type for full accuracy
            pass

        return StatBlock(
            armor_class=ac,
            hit_dice=hp_dice,
            hp_current=hp,
            hp_max=hp,
            movement=template.get("speed", 30),
            attacks=template.get("attacks", []),
            morale=template.get("morale", 7),
            save_as=f"{template.get('title', 'Fighter')} {template.get('level', 1)}",
            special_abilities=template.get("special_abilities", []),
        )

    def _generate_adventurer_name(self, kindred: str) -> str:
        """Generate a name for an adventurer."""
        # Could be expanded with kindred-specific name tables
        names = [
            "Aldric", "Bertram", "Cedric", "Dunstan", "Edmund",
            "Godwin", "Harold", "Ivor", "Kendrick", "Leofric",
            "Aelfleda", "Beatrice", "Cyneburh", "Edith", "Frideswide",
            "Godgifu", "Hild", "Isolde", "Leofrun", "Mildred",
            "Alaric", "Branwen", "Corvin", "Drystan", "Elowen",
            "Fintan", "Gareth", "Heledd", "Idris", "Jennet",
        ]
        return DiceRoller.choice(names, "Adventurer name")

    def _roll_magic_items(self, class_id: str, level: int) -> list[str]:
        """Roll for magic items for an adventurer."""
        magic_items = []
        chance = get_magic_item_chance(level)

        for category in MAGIC_ITEM_CATEGORIES:
            # Skip spell-caster only items for non-casters
            if category in ["rod_staff_wand", "scroll_book"]:
                if not is_spell_caster(class_id):
                    continue

            if DiceRoller.percent_check(chance, f"Magic item: {category}"):
                # Just note the category; actual item would be rolled separately
                magic_items.append(category)

        return magic_items

    # =========================================================================
    # ADVENTURING PARTIES
    # =========================================================================

    def generate_adventuring_party(
        self,
        on_road: bool = False,
        force_high_level: bool = False,
        alignment: Optional[str] = None,
    ) -> AdventuringPartyResult:
        """
        Generate a complete adventuring party.

        Args:
            on_road: Whether the party is on a road (affects mount chance)
            force_high_level: Force generation of a high-level party
            alignment: Force a specific alignment for the party

        Returns:
            AdventuringPartyResult with full party details
        """
        party_id = f"party_{str(uuid.uuid4())[:8]}"

        # Determine party size (1d4+4 = 5-8 members)
        size_roll = DiceRoller.roll(PARTY_SIZE["dice"], "Party size").total
        party_size = max(PARTY_SIZE["min"], min(PARTY_SIZE["max"], size_roll))

        # Determine if high level (1-in-6 chance)
        is_high_level = force_high_level
        if not force_high_level:
            is_high_level = DiceRoller.roll("1d6", "High level check").total == 1

        # Determine party level tier
        if is_high_level:
            level_tier = DiceRoller.roll(
                PARTY_LEVEL["high_level"]["dice"],
                "Party level (high)"
            ).total
        else:
            level_tier = DiceRoller.roll(
                PARTY_LEVEL["normal"]["dice"],
                "Party level (normal)"
            ).total

        # Determine party alignment
        if alignment is None:
            alignment_roll = DiceRoller.roll("1d6", "Party alignment").total
            alignment = ALIGNMENT["entries"].get(alignment_roll, "Neutral")

        # Generate party members
        members = []
        for i in range(party_size):
            # Roll kindred
            kindred_roll = DiceRoller.roll("1d12", f"Member {i+1} kindred").total
            kindred = ADVENTURER_KINDRED["entries"].get(kindred_roll, "human")

            # Roll class for kindred
            class_roll = DiceRoller.roll("1d20", f"Member {i+1} class").total
            class_id = get_class_for_kindred(kindred, class_roll)

            # Roll individual level within tier
            if is_high_level:
                member_level = DiceRoller.roll("1d6+3", f"Member {i+1} level").total
            else:
                member_level = DiceRoller.roll("1d3", f"Member {i+1} level").total

            # Generate the adventurer
            adventurer = self.generate_adventurer(
                class_id=class_id,
                level=member_level,
                kindred=kindred,
                alignment=alignment,
                roll_magic_items=True,
            )

            if adventurer:
                members.append(adventurer)

        # Roll party treasure
        treasure = self._roll_party_treasure()

        # Roll for mounts
        is_mounted = False
        if on_road:
            is_mounted = DiceRoller.percent_check(
                MOUNTED_CHANCE["on_road"],
                "Party mounted"
            )

        # Roll quest
        quest_table = get_quest_table(alignment)
        quest_roll = DiceRoller.roll(quest_table["die"], "Party quest").total
        quest = quest_table["entries"].get(quest_roll, "Seeking adventure")

        # Determine marching order (simple: fighters front, casters back)
        marching_order = self._determine_marching_order(members)

        return AdventuringPartyResult(
            party_id=party_id,
            members=members,
            party_level_tier=level_tier,
            is_high_level=is_high_level,
            alignment=alignment,
            quest=quest,
            treasure=treasure,
            is_mounted=is_mounted,
            marching_order=marching_order,
        )

    def _roll_party_treasure(self) -> dict:
        """Roll treasure for an adventuring party."""
        treasure = {
            "cp": DiceRoller.roll(PARTY_TREASURE["copper"], "Party cp").total,
            "sp": DiceRoller.roll(PARTY_TREASURE["silver"], "Party sp").total,
            "gp": DiceRoller.roll(PARTY_TREASURE["gold"], "Party gp").total,
            "gems": 0,
            "art_objects": 0,
        }

        # Check for gems
        gems_chance = PARTY_TREASURE["gems"]["chance_percent"]
        if DiceRoller.percent_check(gems_chance, "Party gems"):
            treasure["gems"] = DiceRoller.roll(
                PARTY_TREASURE["gems"]["count"],
                "Party gem count"
            ).total

        # Check for art objects
        art_chance = PARTY_TREASURE["art_objects"]["chance_percent"]
        if DiceRoller.percent_check(art_chance, "Party art"):
            treasure["art_objects"] = DiceRoller.roll(
                PARTY_TREASURE["art_objects"]["count"],
                "Party art count"
            ).total

        return treasure

    def _determine_marching_order(
        self,
        members: list[AdventurerResult]
    ) -> list[str]:
        """Determine marching order for the party."""
        # Simple ordering: heavy fighters front, casters back
        front_classes = ["fighter", "knight", "cleric"]
        middle_classes = ["hunter", "thief", "bard", "friar", "enchanter"]
        back_classes = ["magician"]

        front = []
        middle = []
        back = []

        for member in members:
            if member.class_id in front_classes:
                front.append(member.name)
            elif member.class_id in back_classes:
                back.append(member.name)
            else:
                middle.append(member.name)

        return front + middle + back

    # =========================================================================
    # CREATURE ACTIVITY (Optional)
    # =========================================================================

    def roll_creature_activity(self) -> str:
        """
        Roll on the creature activity table.

        Returns:
            Activity description (may contain '?' indicating another creature)
        """
        roll = DiceRoller.roll(
            CREATURE_ACTIVITY["die"],
            "Creature activity"
        ).total
        return CREATURE_ACTIVITY["entries"].get(roll, "Wandering")


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_generator: Optional[EncounterNPCGenerator] = None


def get_encounter_npc_generator() -> EncounterNPCGenerator:
    """Get the shared EncounterNPCGenerator instance."""
    global _generator
    if _generator is None:
        _generator = EncounterNPCGenerator()
    return _generator
