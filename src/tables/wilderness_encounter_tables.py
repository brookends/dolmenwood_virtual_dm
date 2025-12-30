"""
Wilderness Encounter Tables for Dolmenwood.

Contains all encounter roll tables from the Campaign Book including:
- Encounter Type table (determines which sub-table to roll on)
- Common encounter tables (Animal, Monster, Mortal, Sentient)
- Regional encounter tables (12 regions)
- Unseason encounter tables (Chame, Vague)

Table Entry Format:
- Plain text: monster_id to look up in MonsterRegistry
- Ends with '*': Animal from DMB (just use monster_id)
- Ends with '†': Adventurer (use EncounterNPCGenerator)
- Ends with '‡': Everyday Mortal (use EncounterNPCGenerator)
- "Adventuring Party": Special case for full party generation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =============================================================================
# ENUMS
# =============================================================================


class TimeOfDay(str, Enum):
    """Time of day for encounter type determination."""

    DAYTIME = "daytime"
    NIGHTTIME = "nighttime"


class LocationType(str, Enum):
    """Location type for encounter type determination."""

    ROAD = "road"  # Road or track
    WILD = "wild"  # Wilderness, off road
    FIRE = "fire"  # Nighttime with fire/camp
    NO_FIRE = "no_fire"  # Nighttime without fire


class EncounterCategory(str, Enum):
    """Categories of encounters."""

    ANIMAL = "animal"
    MONSTER = "monster"
    MORTAL = "mortal"
    SENTIENT = "sentient"
    REGIONAL = "regional"


# =============================================================================
# ENCOUNTER TYPE TABLE (d8)
# Determines which sub-table to roll on based on time and location
# =============================================================================

ENCOUNTER_TYPE_TABLE = {
    # Daytime encounters
    (TimeOfDay.DAYTIME, LocationType.ROAD): {
        1: EncounterCategory.ANIMAL,
        2: EncounterCategory.MONSTER,
        3: EncounterCategory.MORTAL,
        4: EncounterCategory.MORTAL,
        5: EncounterCategory.SENTIENT,
        6: EncounterCategory.SENTIENT,
        7: EncounterCategory.REGIONAL,
        8: EncounterCategory.REGIONAL,
    },
    (TimeOfDay.DAYTIME, LocationType.WILD): {
        1: EncounterCategory.ANIMAL,
        2: EncounterCategory.MONSTER,
        3: EncounterCategory.MORTAL,
        4: EncounterCategory.SENTIENT,
        5: EncounterCategory.REGIONAL,
        6: EncounterCategory.REGIONAL,
        7: EncounterCategory.REGIONAL,
        8: EncounterCategory.REGIONAL,
    },
    # Nighttime encounters
    (TimeOfDay.NIGHTTIME, LocationType.FIRE): {
        1: EncounterCategory.MONSTER,
        2: EncounterCategory.MONSTER,
        3: EncounterCategory.MORTAL,
        4: EncounterCategory.MORTAL,
        5: EncounterCategory.SENTIENT,
        6: EncounterCategory.SENTIENT,
        7: EncounterCategory.REGIONAL,
        8: EncounterCategory.REGIONAL,
    },
    (TimeOfDay.NIGHTTIME, LocationType.NO_FIRE): {
        1: EncounterCategory.ANIMAL,
        2: EncounterCategory.ANIMAL,
        3: EncounterCategory.MONSTER,
        4: EncounterCategory.MONSTER,
        5: EncounterCategory.MONSTER,
        6: EncounterCategory.REGIONAL,
        7: EncounterCategory.REGIONAL,
        8: EncounterCategory.REGIONAL,
    },
}


# =============================================================================
# COMMON ENCOUNTER TABLES (d20)
# =============================================================================


@dataclass
class EncounterEntry:
    """An entry in an encounter table."""

    name: str
    number_appearing: str
    monster_id: Optional[str] = None  # For MonsterRegistry lookup
    entry_type: str = "monster"  # monster, animal, adventurer, everyday_mortal, party

    def __post_init__(self):
        # Auto-detect entry type from markers
        if self.name.endswith("*"):
            self.entry_type = "animal"
            if self.monster_id is None:
                # Convert name to monster_id: "Bat, Giant*" -> "bat_giant"
                clean_name = self.name.rstrip("*").strip()
                self.monster_id = (
                    clean_name.lower().replace(", ", "_").replace(" ", "_").replace("—", "_")
                )
        elif self.name.endswith("†"):
            self.entry_type = "adventurer"
        elif self.name.endswith("‡"):
            self.entry_type = "everyday_mortal"
        elif self.name == "Adventuring Party":
            self.entry_type = "party"
        else:
            if self.monster_id is None:
                # Convert name to monster_id
                self.monster_id = (
                    self.name.lower().replace(", ", "_").replace(" ", "_").replace("—", "_")
                )


# Helper function to create entries
def E(name: str, num: str, monster_id: Optional[str] = None) -> EncounterEntry:
    """Shorthand for creating EncounterEntry."""
    return EncounterEntry(name=name, number_appearing=num, monster_id=monster_id)


ANIMAL_TABLE = {
    "die": "d20",
    "entries": {
        1: E("Bat, Giant*", "1d10", "bat_giant"),
        2: E("Bear*", "1d4", "bear"),
        3: E("Boar*", "1d6", "boar"),
        4: E("Burrowing Beetle*", "2d4", "burrowing_beetle"),
        5: E("Carrion Worm*", "1d3", "carrion_worm"),
        6: E("Centipede, Giant*", "1d8", "centipede_giant"),
        7: E("False Unicorn*", "3d4", "false_unicorn"),
        8: E("Fire Beetle, Giant*", "2d6", "fire_beetle_giant"),
        9: E("Fly, Giant*", "2d6", "fly_giant"),
        10: E("Insect Swarm*", "1d3", "insect_swarm"),
        11: E("Rapacious Beetle*", "2d4", "rapacious_beetle"),
        12: E("Rat, Giant*", "3d6", "rat_giant"),
        13: E("Red Deer*", "3d10", "red_deer"),
        14: E("Shaggy Mammoth*", "2d8", "shaggy_mammoth"),
        15: E("Snake—Adder*", "1d8", "snake_adder"),
        16: E("Stirge*", "2d6", "stirge"),
        17: E("Toad, Giant*", "1d4", "toad_giant"),
        18: E("Weasel, Giant*", "1d6", "weasel_giant"),
        19: E("Wolf*", "3d6", "wolf"),
        20: E("Yegril*", "3d8", "yegril"),
    },
}

MONSTER_TABLE = {
    "die": "d20",
    "entries": {
        1: E("Ant, Giant*", "3d4", "ant_giant"),
        2: E("Centaur—Bestial", "1", "centaur_bestial"),
        3: E("Cockatrice", "1d4", "cockatrice"),
        4: E("Ghoul", "2d4", "ghoul"),
        5: E("Griffon*", "2d8", "griffon"),
        6: E("Headless Rider", "1d4", "headless_rider"),
        7: E("Mogglewomp", "1", "mogglewomp"),
        8: E("Mugwudge", "1d4", "mugwudge"),
        9: E("Ogre", "1d6", "ogre"),
        10: E("Owlbear*", "1d4", "owlbear"),
        11: E("Root Thing", "1d4", "root_thing"),
        12: E("Snail, Giant—Mutant", "1d3", "snail_giant_mutant"),
        13: E("Spinning Spider, Giant*", "1d3", "spinning_spider_giant"),
        14: E("Stirge*", "2d6", "stirge"),
        15: E("Treowere", "1d8", "treowere"),
        16: E("Werewolf", "1d6", "werewolf"),
        17: E("Wolf, Dire*", "2d4", "wolf_dire"),
        18: E("Wyrm—Black Bile", "1", "wyrm_black_bile"),
        19: E("Wyrm—Blood", "1", "wyrm_blood"),
        20: E("Yickerwill", "1d6", "yickerwill"),
    },
}

MORTAL_TABLE = {
    "die": "d20",
    "entries": {
        1: E("Adventuring Party", "1"),
        2: E("Cleric†", "1d20"),
        3: E("Crier‡", "1d6"),
        4: E("Drune—Cottager", "1d4", "drune_cottager"),
        5: E("Fighter†", "2d6"),
        6: E("Fortune-Teller‡", "1d3"),
        7: E("Friar†", "1d6"),
        8: E("Hunter†", "3d6"),
        9: E("Knight†", "2d6"),
        10: E("Lost Soul‡", "1d4"),
        11: E("Magician†", "1d4"),
        12: E("Merchant‡", "1d20"),
        13: E("Pedlar‡", "1d4"),
        14: E("Pedlar‡", "1d4"),
        15: E("Pilgrim‡", "4d8"),
        16: E("Priest‡", "1d6"),
        17: E("Thief (Bandit)†", "3d10"),
        18: E("Thief (Bandit)†", "3d10"),
        19: E("Villager‡", "2d10"),
        20: E("Witch", "1d6", "witch"),
    },
}

SENTIENT_TABLE = {
    "die": "d20",
    "entries": {
        1: E("Barrowbogey", "2d6", "barrowbogey"),
        2: E("Breggle—Shorthorn", "3d10", "breggle_shorthorn"),
        3: E("Crookhorn", "3d10", "crookhorn"),
        4: E("Deorling—Stag", "1d6", "deorling_stag"),
        5: E("Elf—Courtier or Knight", "1d4", "elf_courtier"),
        6: E("Elf—Wanderer", "1d6", "elf_wanderer"),
        7: E("Goblin", "2d6", "goblin"),
        8: E("Grimalkin", "1d4", "grimalkin"),
        9: E("Mossling", "2d8", "mossling"),
        10: E("Nutcap", "2d6", "nutcap"),
        11: E("Redcap", "2d6", "redcap"),
        12: E("Scarecrow", "1d4", "scarecrow"),
        13: E("Scrabey", "1d6", "scrabey"),
        14: E("Shape-Stealer", "1d6", "shape_stealer"),
        15: E("Sprite", "3d6", "sprite"),
        16: E("Talking Animal", "1d4", "talking_animal"),
        17: E("Treowere", "1d8", "treowere"),
        18: E("Troll", "1d3", "troll"),
        19: E("Wodewose", "1d6", "wodewose"),
        20: E("Woodgrue", "3d6", "woodgrue"),
    },
}

COMMON_TABLES = {
    EncounterCategory.ANIMAL: ANIMAL_TABLE,
    EncounterCategory.MONSTER: MONSTER_TABLE,
    EncounterCategory.MORTAL: MORTAL_TABLE,
    EncounterCategory.SENTIENT: SENTIENT_TABLE,
}


# =============================================================================
# REGIONAL ENCOUNTER TABLES (d20)
# =============================================================================

ALDWEALD_TABLE = {
    "die": "d20",
    "region": "Aldweald",
    "entries": {
        1: E("Antler Wraith", "2d4", "antler_wraith"),
        2: E("Breggle—Shorthorn", "3d10", "breggle_shorthorn"),
        3: E("Centaur—Sylvan", "2d6", "centaur_sylvan"),
        4: E("Deorling—Doe", "4d4", "deorling_doe"),
        5: E("Elf—Knight", "1d4", "elf_knight"),
        6: E("Elf—Wanderer", "1d6", "elf_wanderer"),
        7: E("Fairy Horse", "1", "fairy_horse"),
        8: E("Gelatinous Hulk", "1d4", "gelatinous_hulk"),
        9: E("Gloam", "1", "gloam"),
        10: E("Goblin", "2d6", "goblin"),
        11: E("Grimalkin", "1d4", "grimalkin"),
        12: E("Pedlar‡", "1d4"),
        13: E("Redcap", "2d6", "redcap"),
        14: E("Snail, Giant—Psionic", "1", "snail_giant_psionic"),
        15: E("Sprite", "3d6", "sprite"),
        16: E("Thief (Bandit)†", "3d10"),
        17: E("Unicorn—Blessed", "1d6", "unicorn_blessed"),
        18: E("Wild Hunt", "1", "wild_hunt"),  # See p355
        19: E("Witch", "1d6", "witch"),
        20: E("Woodgrue", "3d6", "woodgrue"),
    },
}

AQUATIC_TABLE = {
    "die": "d20",
    "region": "Aquatic",
    "entries": {
        1: E("Adventuring Party", "1"),
        2: E("Angler‡", "2d4"),
        3: E("Boggin", "1d6", "boggin"),
        4: E("Catfish, Giant*", "1d2", "catfish_giant"),
        5: E("Crab, Giant*", "1d6", "crab_giant"),
        6: E("Fly, Giant*", "2d6", "fly_giant"),
        7: E("Insect Swarm*", "1d3", "insect_swarm"),
        8: E("Kelpie", "1", "kelpie"),
        9: E("Killer Bee*", "2d6", "killer_bee"),
        10: E("Leech, Giant*", "1d4", "leech_giant"),
        11: E("Madtom", "1d12", "madtom"),
        12: E("Merchant‡", "1d20"),
        13: E("Merfaun", "2d6", "merfaun"),
        14: E("Pedlar‡", "1d4"),
        15: E("Pike, Giant*", "1d4", "pike_giant"),
        16: E("Stirge*", "2d6", "stirge"),
        17: E("Thief (Pirate)†", "3d10"),
        18: E("Toad, Giant*", "1d4", "toad_giant"),
        19: E("Water Termite, Giant*", "1d3", "water_termite_giant"),
        20: E("Wyrm—Phlegm", "1", "wyrm_phlegm"),
    },
}

DWELMFURGH_TABLE = {
    "die": "d20",
    "region": "Dwelmfurgh",
    "entries": {
        1: E("Antler Wraith", "2d4", "antler_wraith"),
        2: E("Basilisk", "1d6", "basilisk"),
        3: E("Brambling", "1d4", "brambling"),
        4: E("Centipede, Giant*", "1d8", "centipede_giant"),
        5: E("Crookhorn", "3d10", "crookhorn"),
        6: E("Drune—Audrune", "1", "drune_audrune"),
        7: E("Drune—Braithmaid", "1d4", "drune_braithmaid"),
        8: E("Drune—Cottager", "1d4", "drune_cottager"),
        9: E("Drune—Cottager", "2d6", "drune_cottager"),
        10: E("Drune—Drunewife", "1", "drune_drunewife"),
        11: E("Lost Soul‡", "1d4"),
        12: E("Shadow", "1d8", "shadow"),
        13: E("Skeleton", "3d6", "skeleton"),
        14: E("Spinning Spider, Giant*", "1d3", "spinning_spider_giant"),
        15: E("Sprite", "3d6", "sprite"),
        16: E("Thief (Bandit)†", "3d10"),
        17: E("Wicker Giant", "1", "wicker_giant"),
        18: E("Wight", "1d6", "wight"),
        19: E("Witch", "1d6", "witch"),
        20: E("Wyrm—Yellow Bile", "1", "wyrm_yellow_bile"),
    },
}

FEVER_MARSH_TABLE = {
    "die": "d20",
    "region": "Fever Marsh",
    "entries": {
        1: E("Bat, Vampire*", "1d10", "bat_vampire"),
        2: E("Black Tentacles", "1d4", "black_tentacles"),
        3: E("Bog Salamander", "1d3", "bog_salamander"),
        4: E("Centaur—Bestial", "1", "centaur_bestial"),
        5: E("Crookhorn", "3d10", "crookhorn"),
        6: E("Fly, Giant*", "2d6", "fly_giant"),
        7: E("Galosher", "2d6", "galosher"),
        8: E("Gelatinous Hulk", "1d4", "gelatinous_hulk"),
        9: E("Harridan", "1d3", "harridan"),
        10: E("Insect Swarm*", "1d3", "insect_swarm"),
        11: E("Jack-o'-Lantern", "1d8", "jack_o_lantern"),
        12: E("Leech, Giant*", "1d4", "leech_giant"),
        13: E("Madtom", "1d12", "madtom"),
        14: E("Marsh Lantern", "1d12", "marsh_lantern"),
        15: E("Mugwudge", "1d4", "mugwudge"),
        16: E("Redcap", "2d6", "redcap"),
        17: E("Shadow", "1d8", "shadow"),
        18: E("Toad, Giant*", "1d4", "toad_giant"),
        19: E("Troll", "1d3", "troll"),
        20: E("Wyrm—Phlegm", "1", "wyrm_phlegm"),
    },
}

HAGS_ADDLE_TABLE = {
    "die": "d20",
    "region": "Hag's Addle",
    "entries": {
        1: E("Banshee", "1", "banshee"),
        2: E("Bat, Giant*", "1d10", "bat_giant"),
        3: E("Black Tentacles", "1d4", "black_tentacles"),
        4: E("Bog Corpse", "2d4", "bog_corpse"),
        5: E("Bog Salamander", "1d3", "bog_salamander"),
        6: E("Boggin", "1d6", "boggin"),
        7: E("Galosher", "2d6", "galosher"),
        8: E("Ghoul", "2d4", "ghoul"),
        9: E("Gloam", "1", "gloam"),
        10: E("Leech, Giant*", "1d4", "leech_giant"),
        11: E("Marsh Lantern", "1d12", "marsh_lantern"),
        12: E("Mugwudge", "1d4", "mugwudge"),
        13: E("Shadow", "1d8", "shadow"),
        14: E("Swamp Sloth*", "1d6", "swamp_sloth"),
        15: E("Swamp Spider, Giant*", "1d3", "swamp_spider_giant"),
        16: E("The Hag", "1", "the_hag"),  # See p82
        17: E("Toad, Giant*", "1d4", "toad_giant"),
        18: E("Troll", "1d3", "troll"),
        19: E("Unicorn—Corrupt", "1d6", "unicorn_corrupt"),
        20: E("Wronguncle", "1", "wronguncle"),
    },
}

HIGH_WOLD_TABLE = {
    "die": "d20",
    "region": "High Wold",
    "entries": {
        1: E("Barrowbogey", "2d6", "barrowbogey"),
        2: E("Breggle—Longhorn", "2d4", "breggle_longhorn"),
        3: E("Breggle—Shorthorn", "3d10", "breggle_shorthorn"),
        4: E("Breggle—Shorthorn", "3d10", "breggle_shorthorn"),
        5: E("Crier‡", "1d6"),
        6: E("Devil Goat", "1d4", "devil_goat"),
        7: E("Drune—Braithmaid", "1d4", "drune_braithmaid"),
        8: E("Drune—Cottager", "1d4", "drune_cottager"),
        9: E("Elf—Knight", "1d4", "elf_knight"),
        10: E("Goblin", "2d6", "goblin"),
        11: E("Grimalkin", "1d4", "grimalkin"),
        12: E("Knight†", "2d6"),
        13: E("Merchant‡", "1d20"),
        14: E("Pedlar‡", "1d4"),
        15: E("Priest‡", "1d6"),
        16: E("Scrabey", "1d6", "scrabey"),
        17: E("Thief (Bandit)†", "3d10"),
        18: E("Witch", "1d6", "witch"),
        19: E("Witch Owl", "1d6", "witch_owl"),
        20: E("Woodgrue", "3d6", "woodgrue"),
    },
}

MULCHGROVE_TABLE = {
    "die": "d20",
    "region": "Mulchgrove",
    "entries": {
        1: E("Bat, Vampire*", "1d10", "bat_vampire"),
        2: E("Bog Corpse", "2d4", "bog_corpse"),
        3: E("Bog Salamander", "1d3", "bog_salamander"),
        4: E("Brainconk", "1d8", "brainconk"),
        5: E("Gelatinous Hulk", "1d4", "gelatinous_hulk"),
        6: E("Jack-o'-Lantern", "1d8", "jack_o_lantern"),
        7: E("Mossling", "2d8", "mossling"),
        8: E("Mossling", "2d8", "mossling"),
        9: E("Mossling", "2d8", "mossling"),
        10: E("Mossling", "4d8", "mossling"),
        11: E("Mould Oracle", "1d3", "mould_oracle"),
        12: E("Ochre Slime-Hulk", "1", "ochre_slime_hulk"),
        13: E("Ochre Slime-Hulk", "1", "ochre_slime_hulk"),
        14: E("Onyx Blob", "1", "onyx_blob"),
        15: E("Pook Morel", "2d10", "pook_morel"),
        16: E("Pook Morel", "2d10", "pook_morel"),
        17: E("Redslob", "1d4", "redslob"),
        18: E("Redslob", "1d4", "redslob"),
        19: E("Wodewose", "1d6", "wodewose"),
        20: E("Wronguncle", "1", "wronguncle"),
    },
}

NAGWOOD_TABLE = {
    "die": "d20",
    "region": "Nagwood",
    "entries": {
        1: E("Atanuwë", "1", "atanuwe"),  # See p45
        2: E("Bat, Vampire*", "1d10", "bat_vampire"),
        3: E("Bog Corpse", "2d4", "bog_corpse"),
        4: E("Centaur—Bestial", "1", "centaur_bestial"),
        5: E("Crookhorn", "3d10", "crookhorn"),
        6: E("Crookhorn", "3d10", "crookhorn"),
        7: E("Crookhorn", "6d10", "crookhorn"),
        8: E("Harpy", "2d4", "harpy"),
        9: E("Harridan", "1d3", "harridan"),
        10: E("Manticore", "1d4", "manticore"),
        11: E("Ochre Slime-Hulk", "1", "ochre_slime_hulk"),
        12: E("Ogre", "1d6", "ogre"),
        13: E("Ogre", "1d6", "ogre"),
        14: E("Owlbear*", "1d4", "owlbear"),
        15: E("Snail, Giant—Mutant", "1d3", "snail_giant_mutant"),
        16: E("Spinning Spider, Giant", "1d4", "spinning_spider_giant"),
        17: E("Treowere (Chaotic)", "1d8", "treowere_chaotic"),
        18: E("Unicorn—Corrupt", "1d6", "unicorn_corrupt"),
        19: E("Wolf, Dire*", "2d4", "wolf_dire"),
        20: E("Wyrm—Black Bile", "1", "wyrm_black_bile"),
    },
}

NORTHERN_SCRATCH_TABLE = {
    "die": "d20",
    "region": "Northern Scratch",
    "entries": {
        1: E("Banshee", "1", "banshee"),
        2: E("Bat, Vampire*", "1d10", "bat_vampire"),
        3: E("Black Tentacles", "1d4", "black_tentacles"),
        4: E("Bog Corpse", "2d4", "bog_corpse"),
        5: E("Bog Salamander", "1d3", "bog_salamander"),
        6: E("Deorling—Stag", "1d6", "deorling_stag"),
        7: E("Fomorian", "1d3", "fomorian"),
        8: E("Galosher", "2d6", "galosher"),
        9: E("Gloam", "1", "gloam"),
        10: E("Harridan", "1d3", "harridan"),
        11: E("Leech, Giant*", "1d4", "leech_giant"),
        12: E("Madtom", "1d12", "madtom"),
        13: E("Marsh Lantern", "1d12", "marsh_lantern"),
        14: E("Mugwudge", "1d4", "mugwudge"),
        15: E("Redcap", "2d6", "redcap"),
        16: E("Scarecrow", "1d4", "scarecrow"),
        17: E("Shadow", "1d8", "shadow"),
        18: E("Spectre", "1d4", "spectre"),
        19: E("Wight", "1d6", "wight"),
        20: E("Witch Owl", "1d6", "witch_owl"),
    },
}

TABLE_DOWNS_TABLE = {
    "die": "d20",
    "region": "Table Downs",
    "entries": {
        1: E("Banshee", "1", "banshee"),
        2: E("Crookhorn", "3d10", "crookhorn"),
        3: E("Deorling—Doe", "4d4", "deorling_doe"),
        4: E("Drune—Cottager", "1d4", "drune_cottager"),
        5: E("Elf—Wanderer", "1d6", "elf_wanderer"),
        6: E("Fly, Giant*", "2d6", "fly_giant"),
        7: E("Ghoul", "2d4", "ghoul"),
        8: E("Gloam", "1", "gloam"),
        9: E("Harpy", "2d4", "harpy"),
        10: E("Headless Rider", "1d4", "headless_rider"),
        11: E("Lost Soul‡", "1d4"),
        12: E("Peryton", "2d4", "peryton"),
        13: E("Peryton", "2d4", "peryton"),
        14: E("Shadow", "1d8", "shadow"),
        15: E("Shape-Stealer", "1d6", "shape_stealer"),
        16: E("Skeleton", "3d6", "skeleton"),
        17: E("Spectre", "1d4", "spectre"),
        18: E("Wight", "1d6", "wight"),
        19: E("Witch", "1d6", "witch"),
        20: E("Woodgrue", "3d6", "woodgrue"),
    },
}

TITHELANDS_TABLE = {
    "die": "d20",
    "region": "Tithelands",
    "entries": {
        1: E("Breggle—Shorthorn", "3d10", "breggle_shorthorn"),
        2: E("Cleric†", "1d20"),
        3: E("Elf—Wanderer", "1d6", "elf_wanderer"),
        4: E("Fighter†", "2d6"),
        5: E("Friar†", "1d6"),
        6: E("Gloam", "1", "gloam"),
        7: E("Goblin", "2d6", "goblin"),
        8: E("Griffon", "2d8", "griffon"),
        9: E("Grimalkin", "1d4", "grimalkin"),
        10: E("Killer Bee*", "2d6", "killer_bee"),
        11: E("Knight†", "2d6"),
        12: E("Merchant‡", "1d20"),
        13: E("Mossling", "2d8", "mossling"),
        14: E("Pilgrim‡", "4d8"),
        15: E("Pook Morel", "2d10", "pook_morel"),
        16: E("Scrabey", "1d6", "scrabey"),
        17: E("Sprite", "3d6", "sprite"),
        18: E("Villager‡", "2d10"),
        19: E("Witch", "1d6", "witch"),
        20: E("Woodgrue", "3d6", "woodgrue"),
    },
}

VALLEY_OF_WISE_BEASTS_TABLE = {
    "die": "d20",
    "region": "Valley of Wise Beasts",
    "entries": {
        1: E("Cobbin", "1d4", "cobbin"),
        2: E("Cobbin", "1d4", "cobbin"),
        3: E("Cobbin", "1d4", "cobbin"),
        4: E("Cobbin", "3d8", "cobbin"),
        5: E("Crookhorn", "3d10", "crookhorn"),
        6: E("Crookhorn", "3d10", "crookhorn"),
        7: E("Crookhorn", "3d10", "crookhorn"),
        8: E("Deorling—Stag", "1d6", "deorling_stag"),
        9: E("Goblin", "2d6", "goblin"),
        10: E("Grimalkin", "1d4", "grimalkin"),
        11: E("Lost Soul‡", "1d4"),
        12: E("Mossling", "2d8", "mossling"),
        13: E("Ochre Slime-Hulk", "1", "ochre_slime_hulk"),
        14: E("Ogre", "1d6", "ogre"),
        15: E("Owlbear*", "1d4", "owlbear"),
        16: E("Redslob", "1d4", "redslob"),
        17: E("Sprite", "3d6", "sprite"),
        18: E("Troll", "1d3", "troll"),
        19: E("Wodewose", "1d6", "wodewose"),
        20: E("Woodgrue", "3d6", "woodgrue"),
    },
}

REGIONAL_TABLES = {
    "aldweald": ALDWEALD_TABLE,
    "aquatic": AQUATIC_TABLE,
    "dwelmfurgh": DWELMFURGH_TABLE,
    "fever_marsh": FEVER_MARSH_TABLE,
    "hags_addle": HAGS_ADDLE_TABLE,
    "high_wold": HIGH_WOLD_TABLE,
    "mulchgrove": MULCHGROVE_TABLE,
    "nagwood": NAGWOOD_TABLE,
    "northern_scratch": NORTHERN_SCRATCH_TABLE,
    "table_downs": TABLE_DOWNS_TABLE,
    "tithelands": TITHELANDS_TABLE,
    "valley_of_wise_beasts": VALLEY_OF_WISE_BEASTS_TABLE,
}


# =============================================================================
# UNSEASON ENCOUNTER TABLES
# =============================================================================

CHAME_TABLE = {
    "die": "d10",
    "unseason": "Chame",
    "description": "Serpents and wyrms during the Chame unseason",
    "trigger_chance": "2-in-6",
    "entries": {
        1: E("Galosher", "2d6", "galosher"),
        2: E("Snake—Adder", "1d8", "snake_adder"),
        3: E("Snake—Adder", "1d8", "snake_adder"),
        4: E("Snake—Adder", "1d8", "snake_adder"),
        5: E("Snake—Giant Python", "1d3", "snake_giant_python"),
        6: E("Snake—Giant Python", "1d3", "snake_giant_python"),
        7: E("Wyrm—Black Bile", "1", "wyrm_black_bile"),
        8: E("Wyrm—Blood", "1", "wyrm_blood"),
        9: E("Wyrm—Phlegm", "1", "wyrm_phlegm"),
        10: E("Wyrm—Yellow Bile", "1", "wyrm_yellow_bile"),
    },
}

VAGUE_TABLE = {
    "die": "d10",
    "unseason": "Vague",
    "description": "Undead during the Vague unseason",
    "trigger_chance": "2-in-6",
    "entries": {
        1: E("Banshee", "1", "banshee"),
        2: E("Bog Corpse", "2d4", "bog_corpse"),
        3: E("Bog Corpse", "2d4", "bog_corpse"),
        4: E("Ghoul", "2d4", "ghoul"),
        5: E("Ghoul", "2d4", "ghoul"),
        6: E("Gloam", "1", "gloam"),
        7: E("Headless Rider", "1", "headless_rider"),
        8: E("Skeleton", "3d6", "skeleton"),
        9: E("Spectre", "1d4", "spectre"),
        10: E("Wight", "1d6", "wight"),
    },
}

UNSEASON_TABLES = {
    "chame": CHAME_TABLE,
    "vague": VAGUE_TABLE,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_encounter_type_table(
    time_of_day: TimeOfDay, location_type: LocationType
) -> dict[int, EncounterCategory]:
    """Get the encounter type table for the given conditions."""
    return ENCOUNTER_TYPE_TABLE.get(
        (time_of_day, location_type), ENCOUNTER_TYPE_TABLE[(TimeOfDay.DAYTIME, LocationType.WILD)]
    )


def get_common_table(category: EncounterCategory) -> dict:
    """Get a common encounter table by category."""
    return COMMON_TABLES.get(category)


def get_regional_table(region: str) -> Optional[dict]:
    """Get a regional encounter table by region name."""
    # Normalize region name
    region_key = region.lower().replace(" ", "_").replace("'", "")
    return REGIONAL_TABLES.get(region_key)


def get_unseason_table(unseason: str) -> Optional[dict]:
    """Get an unseason encounter table."""
    return UNSEASON_TABLES.get(unseason.lower())


def get_all_regions() -> list[str]:
    """Get list of all region identifiers."""
    return list(REGIONAL_TABLES.keys())
