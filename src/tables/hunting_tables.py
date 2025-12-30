"""
Hunting Tables for Dolmenwood Virtual DM.

Implements game animal hunting tables per Campaign Book (p120-121).

Hunting Procedure:
1. Survival check (highest party member, +2 if full day devoted)
2. On success, roll d20 on terrain-specific Game Animals table
3. Roll number appearing dice for the animal type
4. Combat encounter with party having surprise, starting 1d4 × 30' away
5. Yield: 1 ration/HP (Small), 2 rations/HP (Medium), 4 rations/HP (Large)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import random


class TerrainType(str, Enum):
    """Terrain types for hunting tables."""

    BOG = "bog"
    FARMLAND = "farmland"
    FOREST_BOGGY = "forest_boggy"
    FOREST_CRAGGY = "forest_craggy"
    FOREST_HILLY = "forest_hilly"
    FOREST_OPEN = "forest_open"
    FOREST_TANGLED = "forest_tangled"
    FOREST_THORNY = "forest_thorny"
    FUNGAL_FOREST = "fungal_forest"
    HILLS = "hills"
    MEADOW = "meadow"
    SWAMP = "swamp"


class AnimalSize(str, Enum):
    """Size categories for game animals, affects ration yield."""

    SMALL = "small"  # 1 ration per HP
    MEDIUM = "medium"  # 2 rations per HP
    LARGE = "large"  # 4 rations per HP


@dataclass
class GameAnimal:
    """A game animal that can be hunted."""

    name: str
    monster_id: str
    size: AnimalSize
    number_appearing: str  # Dice expression like "1d6", "3d4"
    description: str
    flavor_text: str = ""  # Additional description for narrative

    @property
    def rations_per_hp(self) -> int:
        """Rations yielded per HP of killed animal."""
        if self.size == AnimalSize.SMALL:
            return 1
        elif self.size == AnimalSize.MEDIUM:
            return 2
        else:  # LARGE
            return 4

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "monster_id": self.monster_id,
            "size": self.size.value,
            "number_appearing": self.number_appearing,
            "description": self.description,
            "flavor_text": self.flavor_text,
            "rations_per_hp": self.rations_per_hp,
        }


# =============================================================================
# GAME ANIMALS (Campaign Book p120-121, Monster Book entries)
# =============================================================================

GAME_ANIMALS: dict[str, GameAnimal] = {
    "boar": GameAnimal(
        name="Boar",
        monster_id="boar",
        size=AnimalSize.MEDIUM,
        number_appearing="1d6",
        description="Omnivorous wild boars that dwell throughout Dolmenwood. Irascible and dangerous, if disturbed.",
        flavor_text="The boars root through the undergrowth, tusks gleaming.",
    ),
    "false_unicorn": GameAnimal(
        name="False Unicorn",
        monster_id="false_unicorn",
        size=AnimalSize.MEDIUM,
        number_appearing="3d4",
        description="White-furred deer with a single horn. Gamy and reasonably tasty flesh. Timid and skittish.",
        flavor_text="The creatures' distinctive stench betrays their presence.",
    ),
    "gelatinous_ape": GameAnimal(
        name="Gelatinous Ape",
        monster_id="gelatinous_ape",
        size=AnimalSize.SMALL,
        number_appearing="1d12",
        description="Hairless, transparent apes with sweet, chewy jelly-like flesh.",
        flavor_text="The colorful apes creep through the branches, trusting and curious.",
    ),
    "gobble": GameAnimal(
        name="Gobble",
        monster_id="gobble",
        size=AnimalSize.SMALL,
        number_appearing="3d6",
        description="Fluffy, purple primates with huge, adorable eyes. Shy and timid.",
        flavor_text="The gobbles babble their single words incessantly.",
    ),
    "headhog": GameAnimal(
        name="Headhog",
        monster_id="headhog",
        size=AnimalSize.SMALL,
        number_appearing="2d6",
        description="Black-spined, flea-ridden hedgehogs with long, pink tongues.",
        flavor_text="The headhogs scuttle through the undergrowth, tongues probing for insects.",
    ),
    "honey_badger": GameAnimal(
        name="Honey Badger",
        monster_id="honey_badger",
        size=AnimalSize.SMALL,
        number_appearing="1d4",
        description="White-furred badgers slick with honey-like substance. Grossly fatty flesh, but delectable slime.",
        flavor_text="The badgers are slick with their sweet secretion.",
    ),
    "lurkey": GameAnimal(
        name="Lurkey",
        monster_id="lurkey",
        size=AnimalSize.SMALL,
        number_appearing="2d4",
        description="Ungainly ground birds with stiff black feathers and outrageous pink wattles. Easy prey if cornered.",
        flavor_text="The lurkeys strut about, wattles wobbling ridiculously.",
    ),
    "merriman": GameAnimal(
        name="Merriman",
        monster_id="merriman",
        size=AnimalSize.SMALL,
        number_appearing="1d6",
        description="Miniature, golden swine with curly tusks. Sing haunting songs when bedding down.",
        flavor_text="The merrimen scuttle through the bracken, snuffling for mushrooms.",
    ),
    "moss_mole": GameAnimal(
        name="Moss Mole",
        monster_id="moss_mole",
        size=AnimalSize.SMALL,
        number_appearing="1d6",
        description="Cat-sized moles with mottled green/brown fur. Placid and easily startled.",
        flavor_text="The moss moles burrow in their mossy mounds, letting out girlish shrieks when disturbed.",
    ),
    "puggle": GameAnimal(
        name="Puggle",
        monster_id="puggle",
        size=AnimalSize.SMALL,
        number_appearing="2d4",
        description="Silver-furred, flat-faced dogs with bulging eyes. Flesh tastes of garlic-fried mushrooms.",
        flavor_text="The puggles emerge from their fungal burrows, tongues lolling.",
    ),
    "red_deer": GameAnimal(
        name="Red Deer",
        monster_id="red_deer",
        size=AnimalSize.LARGE,
        number_appearing="3d10",
        description="Elegant, red-furred deer with dappled flanks. Timid and skittish.",
        flavor_text="The deer graze peacefully, their flanks dappled in the forest light.",
    ),
    "swamp_sloth": GameAnimal(
        name="Swamp Sloth",
        monster_id="swamp_sloth",
        size=AnimalSize.SMALL,
        number_appearing="1d6",
        description="Lazy, infant-sized mammals covered in moss and lichen. Found in boggy regions.",
        flavor_text="The sloths creep through the treetops, appearing as moving clumps of moss.",
    ),
    "trotteling": GameAnimal(
        name="Trotteling",
        monster_id="trotteling",
        size=AnimalSize.SMALL,
        number_appearing="2d6",
        description="Naked miniature pigs with toddler faces. Flesh is delectable when roasted, though incredibly greasy.",
        flavor_text="The trottelings bicker and squabble like crows as they forage.",
    ),
    "woad": GameAnimal(
        name="Woad",
        monster_id="woad",
        size=AnimalSize.SMALL,
        number_appearing="3d6",
        description="Great, warty toads with shocking scarlet tongues. Dry but palatable flesh.",
        flavor_text="The woads squat in the undergrowth, ready to spray if threatened.",
    ),
    "yegril": GameAnimal(
        name="Yegril",
        monster_id="yegril",
        size=AnimalSize.LARGE,
        number_appearing="3d8",
        description="Gigantic, fluffy moose with purple fur and moon-yellow eyes. Gentle creatures.",
        flavor_text="The yegrils mewl plaintively as they strip moss from high branches.",
    ),
}


def get_game_animal(animal_id: str) -> Optional[GameAnimal]:
    """Get a game animal by its ID."""
    return GAME_ANIMALS.get(animal_id)


def get_game_animal_by_name(name: str) -> Optional[GameAnimal]:
    """Get a game animal by its name (case-insensitive)."""
    name_lower = name.lower()
    for animal in GAME_ANIMALS.values():
        if animal.name.lower() == name_lower:
            return animal
    return None


# =============================================================================
# TERRAIN-SPECIFIC GAME ANIMAL TABLES (Campaign Book p121)
# =============================================================================
# Each table maps d20 roll (1-20) to animal_id

HUNTING_TABLES: dict[TerrainType, dict[int, str]] = {
    TerrainType.BOG: {
        1: "false_unicorn",
        2: "false_unicorn",
        3: "headhog",
        4: "headhog",
        5: "headhog",
        6: "honey_badger",
        7: "lurkey",
        8: "moss_mole",
        9: "moss_mole",
        10: "moss_mole",
        11: "red_deer",
        12: "swamp_sloth",
        13: "swamp_sloth",
        14: "swamp_sloth",
        15: "swamp_sloth",
        16: "trotteling",
        17: "trotteling",
        18: "woad",
        19: "woad",
        20: "woad",
    },
    TerrainType.FARMLAND: {
        1: "boar",
        2: "boar",
        3: "boar",
        4: "false_unicorn",
        5: "false_unicorn",
        6: "false_unicorn",
        7: "headhog",
        8: "honey_badger",
        9: "honey_badger",
        10: "lurkey",
        11: "lurkey",
        12: "lurkey",
        13: "lurkey",
        14: "merriman",
        15: "merriman",
        16: "red_deer",
        17: "red_deer",
        18: "red_deer",
        19: "trotteling",
        20: "trotteling",
    },
    TerrainType.FOREST_BOGGY: {
        1: "boar",
        2: "false_unicorn",
        3: "gelatinous_ape",
        4: "gelatinous_ape",
        5: "gobble",
        6: "headhog",
        7: "honey_badger",
        8: "honey_badger",
        9: "lurkey",
        10: "merriman",
        11: "moss_mole",
        12: "moss_mole",
        13: "moss_mole",
        14: "puggle",
        15: "red_deer",
        16: "swamp_sloth",
        17: "swamp_sloth",
        18: "trotteling",
        19: "woad",
        20: "yegril",
    },
    TerrainType.FOREST_CRAGGY: {
        1: "boar",
        2: "false_unicorn",
        3: "false_unicorn",
        4: "gelatinous_ape",
        5: "gelatinous_ape",
        6: "gelatinous_ape",
        7: "gobble",
        8: "gobble",
        9: "gobble",
        10: "honey_badger",
        11: "lurkey",
        12: "moss_mole",
        13: "moss_mole",
        14: "puggle",
        15: "puggle",
        16: "red_deer",
        17: "trotteling",
        18: "yegril",
        19: "yegril",
        20: "yegril",
    },
    TerrainType.FOREST_HILLY: {
        1: "boar",
        2: "boar",
        3: "false_unicorn",
        4: "false_unicorn",
        5: "false_unicorn",
        6: "gelatinous_ape",
        7: "gobble",
        8: "headhog",
        9: "honey_badger",
        10: "honey_badger",
        11: "honey_badger",
        12: "lurkey",
        13: "lurkey",
        14: "lurkey",
        15: "moss_mole",
        16: "moss_mole",
        17: "puggle",
        18: "red_deer",
        19: "trotteling",
        20: "yegril",
    },
    TerrainType.FOREST_OPEN: {
        1: "boar",
        2: "boar",
        3: "false_unicorn",
        4: "false_unicorn",
        5: "false_unicorn",
        6: "headhog",
        7: "honey_badger",
        8: "lurkey",
        9: "lurkey",
        10: "merriman",
        11: "merriman",
        12: "puggle",
        13: "puggle",
        14: "red_deer",
        15: "red_deer",
        16: "red_deer",
        17: "trotteling",
        18: "woad",
        19: "yegril",
        20: "yegril",
    },
    TerrainType.FOREST_TANGLED: {
        1: "boar",
        2: "boar",
        3: "gelatinous_ape",
        4: "gelatinous_ape",
        5: "gelatinous_ape",
        6: "gelatinous_ape",
        7: "gobble",
        8: "headhog",
        9: "headhog",
        10: "honey_badger",
        11: "honey_badger",
        12: "lurkey",
        13: "merriman",
        14: "merriman",
        15: "moss_mole",
        16: "moss_mole",
        17: "red_deer",
        18: "red_deer",
        19: "trotteling",
        20: "woad",
    },
    TerrainType.FOREST_THORNY: {
        1: "gobble",
        2: "gobble",
        3: "gobble",
        4: "headhog",
        5: "headhog",
        6: "honey_badger",
        7: "lurkey",
        8: "merriman",
        9: "merriman",
        10: "merriman",
        11: "merriman",
        12: "moss_mole",
        13: "moss_mole",
        14: "red_deer",
        15: "trotteling",
        16: "trotteling",
        17: "trotteling",
        18: "trotteling",
        19: "trotteling",
        20: "trotteling",
    },
    TerrainType.FUNGAL_FOREST: {
        1: "boar",
        2: "boar",
        3: "gelatinous_ape",
        4: "gelatinous_ape",
        5: "gobble",
        6: "headhog",
        7: "honey_badger",
        8: "merriman",
        9: "merriman",
        10: "merriman",
        11: "merriman",
        12: "moss_mole",
        13: "puggle",
        14: "puggle",
        15: "puggle",
        16: "puggle",
        17: "red_deer",
        18: "swamp_sloth",
        19: "trotteling",
        20: "yegril",
    },
    TerrainType.HILLS: {
        1: "false_unicorn",
        2: "false_unicorn",
        3: "false_unicorn",
        4: "false_unicorn",
        5: "headhog",
        6: "headhog",
        7: "honey_badger",
        8: "honey_badger",
        9: "honey_badger",
        10: "lurkey",
        11: "lurkey",
        12: "lurkey",
        13: "moss_mole",
        14: "moss_mole",
        15: "red_deer",
        16: "red_deer",
        17: "red_deer",
        18: "trotteling",
        19: "trotteling",
        20: "yegril",
    },
    TerrainType.MEADOW: {
        1: "false_unicorn",
        2: "false_unicorn",
        3: "headhog",
        4: "headhog",
        5: "honey_badger",
        6: "honey_badger",
        7: "lurkey",
        8: "lurkey",
        9: "lurkey",
        10: "lurkey",
        11: "merriman",
        12: "merriman",
        13: "merriman",
        14: "moss_mole",
        15: "red_deer",
        16: "red_deer",
        17: "trotteling",
        18: "trotteling",
        19: "woad",
        20: "yegril",
    },
    TerrainType.SWAMP: {
        1: "boar",
        2: "false_unicorn",
        3: "gelatinous_ape",
        4: "gelatinous_ape",
        5: "gobble",
        6: "headhog",
        7: "honey_badger",
        8: "lurkey",
        9: "merriman",
        10: "moss_mole",
        11: "puggle",
        12: "red_deer",
        13: "swamp_sloth",
        14: "swamp_sloth",
        15: "swamp_sloth",
        16: "trotteling",
        17: "woad",
        18: "woad",
        19: "yegril",
        20: "yegril",
    },
}


def roll_game_animal(terrain: TerrainType) -> GameAnimal:
    """
    Roll for a game animal on the terrain-specific table.

    Args:
        terrain: The terrain type to roll on

    Returns:
        The GameAnimal found
    """
    roll = random.randint(1, 20)
    table = HUNTING_TABLES.get(terrain, HUNTING_TABLES[TerrainType.FOREST_OPEN])
    animal_id = table[roll]
    return GAME_ANIMALS[animal_id]


def roll_number_appearing(animal: GameAnimal) -> int:
    """
    Roll the number of animals appearing.

    Args:
        animal: The game animal to roll for

    Returns:
        Number of animals in the group
    """
    dice_expr = animal.number_appearing
    # Parse dice expression like "1d6", "3d4", "2d6"
    if "d" in dice_expr:
        parts = dice_expr.lower().split("d")
        num_dice = int(parts[0]) if parts[0] else 1
        die_size = int(parts[1])
        return sum(random.randint(1, die_size) for _ in range(num_dice))
    return int(dice_expr)


def roll_encounter_distance() -> int:
    """
    Roll the starting distance for the hunting encounter.

    Per Campaign Book p120: 1d4 × 30 feet

    Returns:
        Distance in feet
    """
    return random.randint(1, 4) * 30


def calculate_rations_yield(animal: GameAnimal, total_hp_killed: int) -> int:
    """
    Calculate rations yielded from killed game.

    Per Campaign Book p120:
    - Small: 1 ration per HP
    - Medium: 2 rations per HP
    - Large: 4 rations per HP

    Args:
        animal: The type of animal killed
        total_hp_killed: Total HP of animals killed

    Returns:
        Number of rations yielded
    """
    return total_hp_killed * animal.rations_per_hp


# =============================================================================
# TERRAIN TYPE MAPPING
# =============================================================================

# Map hex terrain types to hunting terrain types
TERRAIN_TO_HUNTING: dict[str, TerrainType] = {
    # Direct mappings
    "bog": TerrainType.BOG,
    "farmland": TerrainType.FARMLAND,
    "forest_boggy": TerrainType.FOREST_BOGGY,
    "forest_craggy": TerrainType.FOREST_CRAGGY,
    "forest_hilly": TerrainType.FOREST_HILLY,
    "forest_open": TerrainType.FOREST_OPEN,
    "forest_tangled": TerrainType.FOREST_TANGLED,
    "forest_thorny": TerrainType.FOREST_THORNY,
    "fungal_forest": TerrainType.FUNGAL_FOREST,
    "hills": TerrainType.HILLS,
    "meadow": TerrainType.MEADOW,
    "swamp": TerrainType.SWAMP,
    # Generic forest defaults to open forest
    "forest": TerrainType.FOREST_OPEN,
    # Settlement surroundings default to farmland
    "settlement": TerrainType.FARMLAND,
    "village": TerrainType.FARMLAND,
    "town": TerrainType.FARMLAND,
    # Water areas default to swamp (river banks, lake shores)
    "river": TerrainType.SWAMP,
    "lake": TerrainType.SWAMP,
    # Mountain areas default to hills
    "mountain": TerrainType.HILLS,
    "crag": TerrainType.HILLS,
}


def get_hunting_terrain(hex_terrain: str) -> TerrainType:
    """
    Convert a hex terrain type to a hunting table terrain type.

    Args:
        hex_terrain: The terrain type from hex data

    Returns:
        The corresponding hunting terrain type
    """
    terrain_lower = hex_terrain.lower().replace(" ", "_")
    return TERRAIN_TO_HUNTING.get(terrain_lower, TerrainType.FOREST_OPEN)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_animals() -> list[GameAnimal]:
    """Get all game animals as a list."""
    return list(GAME_ANIMALS.values())


def get_animals_in_terrain(terrain: TerrainType) -> list[GameAnimal]:
    """Get all unique animals that can appear in a terrain."""
    table = HUNTING_TABLES.get(terrain, {})
    animal_ids = set(table.values())
    return [GAME_ANIMALS[aid] for aid in animal_ids if aid in GAME_ANIMALS]


def animal_appears_in_terrain(animal_id: str, terrain: TerrainType) -> bool:
    """Check if an animal can appear in a given terrain."""
    table = HUNTING_TABLES.get(terrain, {})
    return animal_id in table.values()
