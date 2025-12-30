"""
Adventuring Party generation tables for Dolmenwood.

Contains tables for generating complete adventuring parties including:
- Kindred selection
- Class by kindred
- Alignment
- Quests by alignment
- Treasure and magic items
"""

from typing import Any


# =============================================================================
# ADVENTURER KINDRED TABLE
# =============================================================================

ADVENTURER_KINDRED = {
    "die": "d12",
    "entries": {
        1: "breggle",
        2: "breggle",
        3: "breggle",
        4: "elf",
        5: "grimalkin",
        6: "human",
        7: "human",
        8: "human",
        9: "human",
        10: "human",
        11: "mossling",
        12: "woodgrue",
    },
}


# =============================================================================
# CLASS BY KINDRED TABLE
# Each kindred has different class probability distributions
# Roll d20 and find the matching range
# =============================================================================

CLASS_BY_KINDRED = {
    "breggle": {
        # d20 ranges: (min, max): class_id
        (1, 1): "bard",
        (2, 2): "cleric",
        (3, 3): "enchanter",
        (4, 8): "fighter",
        (9, 9): "friar",
        (10, 11): "hunter",
        (12, 15): "knight",
        (16, 18): "magician",
        (19, 20): "thief",
    },
    "elf": {
        (1, 2): "bard",
        # No cleric for elves
        (3, 8): "enchanter",
        (9, 12): "fighter",
        # No friar for elves
        (13, 15): "hunter",
        # No knight for elves
        (16, 17): "magician",
        (18, 20): "thief",
    },
    "grimalkin": {
        (1, 4): "bard",
        # No cleric for grimalkin
        (5, 8): "enchanter",
        (9, 10): "fighter",
        # No friar for grimalkin
        (11, 14): "hunter",
        # No knight for grimalkin
        (15, 16): "magician",
        (17, 20): "thief",
    },
    "human": {
        (1, 2): "bard",
        (3, 5): "cleric",
        (6, 6): "enchanter",
        (7, 10): "fighter",
        (11, 12): "friar",
        (13, 14): "hunter",
        (15, 16): "knight",
        (17, 18): "magician",
        (19, 20): "thief",
    },
    "mossling": {
        (1, 3): "bard",
        # No cleric for mosslings
        (4, 4): "enchanter",
        (5, 10): "fighter",
        # No friar for mosslings
        (11, 16): "hunter",
        # No knight for mosslings
        (17, 17): "magician",
        (18, 20): "thief",
    },
    "woodgrue": {
        (1, 5): "bard",
        # No cleric for woodgrues
        (6, 8): "enchanter",
        (9, 10): "fighter",
        # No friar for woodgrues
        (11, 14): "hunter",
        # No knight for woodgrues
        (15, 16): "magician",
        (17, 20): "thief",
    },
}


def get_class_for_kindred(kindred: str, roll: int) -> str:
    """
    Get the class for a kindred given a d20 roll.

    Args:
        kindred: The kindred identifier
        roll: A d20 roll result (1-20)

    Returns:
        Class identifier
    """
    kindred_classes = CLASS_BY_KINDRED.get(kindred.lower(), CLASS_BY_KINDRED["human"])

    for (min_val, max_val), class_id in kindred_classes.items():
        if min_val <= roll <= max_val:
            return class_id

    # Fallback to fighter if roll doesn't match (shouldn't happen)
    return "fighter"


# =============================================================================
# ALIGNMENT TABLE
# =============================================================================

ALIGNMENT = {
    "die": "d6",
    "entries": {
        1: "Lawful",
        2: "Lawful",
        3: "Neutral",
        4: "Neutral",
        5: "Chaotic",
        6: "Chaotic",
    },
}


# =============================================================================
# QUEST TABLES BY ALIGNMENT
# =============================================================================

QUEST_LAWFUL = {
    "die": "d6",
    "entries": {
        1: "Locate a lost shrine and report to the Bishop of Brackenwold (e.g. St Sedge in 0202, St Hamfast in 0309, St Cornice in 1505).",
        2: "Secretly carry a holy magic item to a patron (e.g. a Horn of Blasting, a Rod of Greater Healing, a Holy Mace).",
        3: "Destroy a powerful undead monster (e.g. the spectres in 0701, the gloam in 0906, the Descendant in 1409).",
        4: "Scout the movements of crookhorn troops and report to the duke (e.g. around Fort Vulgar in 0604, the ruined abbey in 0906, Prigwort in 1106).",
        5: "Capture a Chaotic NPC and bring them to Castle Brackenwold (e.g. Praephator Lenore in 0111, Captain Snarkscorn in 0803, Shub's Nanna in 0911).",
        6: "Locate the lost relics of St Jorrael, rumoured to have been buried in hex 1705 in Mulchgrove. The adventurers do not have a map.",
    },
}

QUEST_NEUTRAL = {
    "die": "d6",
    "entries": {
        1: "Search for magical herbs/fungi (e.g. Grinning Jenny in 0908, Horridwort in 1002, Purple Nightcap in 0510).",
        2: "Locate a fairy door (e.g. the emerald door in 0602, the moggle door in 0711, the dungle-crack in 1402).",
        3: "Loot a fabulous treasure hoard (e.g. the bicorne's hoard in 0510, the Big Chook's hoard in 0606, the wyrm's hoard in 1107).",
        4: "Spy on the arcane doings of a wizard, on behalf of another wizard (e.g. Mostlemyre Drouge in 1106, Tamrin Tweede in 1110, Ygraine in 1802).",
        5: "Find a means of curing a party member's curse (e.g. by bathing in the Lethean Well in 0209, at the hill in 0805, by visiting the Hag in 0908).",
        6: "Secretly carry a magic item to the Drune (e.g. a Crystal Ball, a Mirror of Life Trapping, a Ring of Protection).",
    },
}

QUEST_CHAOTIC = {
    "die": "d6",
    "entries": {
        1: "Scout the movements of human troops and report to Atanuwë (e.g. around Fort Vulgar in 0604, Prigwort in 1106, Castle Brackenwold in 1508).",
        2: "Rob any weaker looking groups they encounter.",
        3: "Assassinate or kidnap a Lawful NPC (e.g. Sir Osric Hazelmire from Fort Vulgar in 0604, Lady Harrowmoor from Harrowmoor Keep in 1105, Abbot Spatulard from the Refuge of St Keye in 1307).",
        4: "Secretly carry the remains of a saint to Atanuwë.",
        5: "Steal a precious item from an NPC (e.g. the Rod of the Wyrd from Nodding Castle in 0210, the magic mirror from Chateau Shantywood in 1110, the Mornblade from Ferneddbole House in 1209).",
        6: "Sell poisonous substances (e.g. Angel's Lament, Purple Nightcap) to a paying client (e.g. Wyrmspittle the herbalist from Prigwort in 1106, Madame Shantywood from Chateau Shantywood in 1110).",
    },
}

QUESTS = {
    "Lawful": QUEST_LAWFUL,
    "Neutral": QUEST_NEUTRAL,
    "Chaotic": QUEST_CHAOTIC,
}


def get_quest_table(alignment: str) -> dict:
    """Get the quest table for the given alignment."""
    return QUESTS.get(alignment, QUEST_NEUTRAL)


# =============================================================================
# PARTY TREASURE
# =============================================================================

PARTY_TREASURE = {
    "copper": "1d100",
    "silver": "1d100",
    "gold": "1d100",
    "gems": {
        "chance_percent": 10,
        "count": "1d4",
    },
    "art_objects": {
        "chance_percent": 10,
        "count": "1d4",
    },
}

# Possessions per adventurer
ADVENTURER_POSSESSIONS = {
    "gold_per_level": "2d8",
}


# =============================================================================
# MAGIC ITEM CHANCES
# Per character, 5% per Level for each category
# =============================================================================

MAGIC_ITEM_CATEGORIES = [
    "magic_armour",
    "magic_ring",
    "magic_weapon",
    "potion",
    "rod_staff_wand",  # Spell-casters only
    "scroll_book",  # Spell-casters only
    "wondrous_item",
]

SPELL_CASTER_CLASSES = ["bard", "cleric", "enchanter", "friar", "magician"]


def is_spell_caster(class_id: str) -> bool:
    """Check if a class is a spell-caster."""
    return class_id.lower() in SPELL_CASTER_CLASSES


def get_magic_item_chance(level: int) -> int:
    """Get magic item chance percentage for a given level."""
    return 5 * level  # 5% per level


# =============================================================================
# PARTY GENERATION PARAMETERS
# =============================================================================

PARTY_SIZE = {
    "dice": "1d4+4",
    "min": 5,
    "max": 8,
}

PARTY_LEVEL = {
    "normal": {
        "dice": "1d3",
        "description": "Low level party",
    },
    "high_level": {
        "dice": "1d6+3",
        "chance": "1-in-6",
        "description": "High level party",
    },
}

MOUNTED_CHANCE = {
    "on_road": 75,  # 75% chance of being mounted on roads/settled areas
    "mount_type": "riding_horse",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_available_classes_for_kindred(kindred: str) -> list[str]:
    """
    Get list of classes available to a kindred.

    Args:
        kindred: The kindred identifier

    Returns:
        List of class identifiers available to this kindred
    """
    kindred_classes = CLASS_BY_KINDRED.get(kindred.lower(), CLASS_BY_KINDRED["human"])
    return list(set(class_id for (_, _), class_id in kindred_classes.items()))


def get_all_kindreds() -> list[str]:
    """Get list of all kindred identifiers."""
    return list(CLASS_BY_KINDRED.keys())
