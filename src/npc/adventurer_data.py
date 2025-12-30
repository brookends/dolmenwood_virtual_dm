"""
Adventurer data definitions for Dolmenwood.

Contains pre-built stat block templates for all 9 character classes
at levels 1, 3, and 5. Used for generating adventurer encounters,
bandits, guild members, town guards, etc.

Each template includes:
- Combat stats (AC, HP, saves, attack bonus)
- Equipment and weapons
- Spells (for casters)
- Skills (for skill-based classes)
- Companions (for higher level characters)
"""

from typing import Any, Optional


# =============================================================================
# BARD TEMPLATES
# =============================================================================

BARD_TEMPLATES = {
    1: {
        "title": "Rhymer",
        "level": 1,
        "armor_class": 12,
        "hp_dice": "1d6",
        "hp_average": 3,
        "saves": {"doom": 13, "ray": 14, "hold": 13, "blast": 15, "spell": 15},
        "attack_bonus": 0,
        "speed": 30,
        "morale": 7,
        "xp": 15,
        "number_appearing": "1d6",
        "gear": [
            "Leather armour",
            "Shortsword (1d6)",
            "Sling + 20 stones (1d4)",
        ],
        "attacks": [
            {"name": "Shortsword", "damage": "1d6", "bonus": 0},
            {"name": "Sling", "damage": "1d4", "bonus": 0},
        ],
        "magic": ["Counter charm", "Enchantment (1/day—mortals)"],
        "skills": {
            "Decipher Document": 6,
            "Legerdemain": 6,
            "Listen": 5,
            "Monster Lore": 5,
        },
        "companions": [],
    },
    3: {
        "title": "Troubadour",
        "level": 3,
        "armor_class": 14,
        "hp_dice": "3d6",
        "hp_average": 10,
        "saves": {"doom": 12, "ray": 13, "hold": 12, "blast": 14, "spell": 14},
        "attack_bonus": 1,
        "speed": 20,
        "morale": 8,
        "xp": 65,
        "number_appearing": "1d3",
        "gear": [
            "Chainmail",
            "Shortsword (1d6)",
            "Silver dagger (1d4)",
            "Shortbow + 20 arrows (1d4)",
            "Vaporous Spirits",
        ],
        "attacks": [
            {"name": "Shortsword", "damage": "1d6", "bonus": 1},
            {"name": "Silver dagger", "damage": "1d4", "bonus": 1},
            {"name": "Shortbow", "damage": "1d4", "bonus": 1},
        ],
        "magic": ["Counter charm", "Enchantment (3/day—mortals)"],
        "skills": {
            "Decipher Document": 5,
            "Legerdemain": 6,
            "Listen": 5,
            "Monster Lore": 4,
        },
        "companions": ["1d4 rhymers"],
    },
    5: {
        "title": "Lore-Master",
        "level": 5,
        "armor_class": 15,
        "hp_dice": "5d6",
        "hp_average": 17,
        "saves": {"doom": 11, "ray": 12, "hold": 11, "blast": 13, "spell": 13},
        "attack_bonus": 2,
        "speed": 20,
        "morale": 9,
        "xp": 360,
        "number_appearing": "1",
        "gear": [
            "Chainmail + shield",
            "Arcane Shortsword (1d6+2, +2 Attack)",
            "Silver dagger (1d4)",
            "Shortbow + 20 arrows (1d6)",
            "Lute of Obscurement",
            "Prismatic Elixir",
        ],
        "attacks": [
            {"name": "Arcane Shortsword", "damage": "1d6+2", "bonus": 4},
            {"name": "Silver dagger", "damage": "1d4", "bonus": 2},
            {"name": "Shortbow", "damage": "1d6", "bonus": 2},
        ],
        "magic": ["Counter charm", "Enchantment (5/day—animals, demi-fey, mortals)"],
        "skills": {
            "Decipher Document": 5,
            "Legerdemain": 5,
            "Listen": 4,
            "Monster Lore": 4,
        },
        "companions": ["1d4 troubadours", "1d4 Level 1 enchanters, hunters, or thieves"],
    },
}


# =============================================================================
# CLERIC TEMPLATES
# =============================================================================

CLERIC_TEMPLATES = {
    1: {
        "title": "Acolyte",
        "level": 1,
        "armor_class": 15,
        "hp_dice": "1d6",
        "hp_average": 3,
        "saves": {"doom": 11, "ray": 12, "hold": 13, "blast": 16, "spell": 14},
        "attack_bonus": 0,
        "speed": 20,
        "morale": 8,
        "xp": 10,
        "number_appearing": "1d20",
        "alignment": ["Lawful", "Neutral"],
        "gear": [
            "Chainmail + shield",
            "Longsword (1d8)",
            "Shortbow + 20 arrows (1d6)",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 0},
            {"name": "Shortbow", "damage": "1d6", "bonus": 0},
        ],
        "spells": [],
        "companions": [],
    },
    3: {
        "title": "Warden",
        "level": 3,
        "armor_class": 17,
        "hp_dice": "3d6",
        "hp_average": 10,
        "saves": {"doom": 10, "ray": 11, "hold": 12, "blast": 15, "spell": 13},
        "attack_bonus": 1,
        "speed": 20,
        "morale": 9,
        "xp": 65,
        "number_appearing": "1d4",
        "alignment": ["Lawful", "Neutral"],
        "gear": [
            "Plate mail + shield",
            "Longsword (1d8)",
            "Shortbow + 20 arrows (1d6)",
            "Vial of holy water",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 1},
            {"name": "Shortbow", "damage": "1d6", "bonus": 1},
        ],
        "spells": ["Lesser Healing", "Mantle of Protection"],
        "holy_order": True,  # Roll for holy order
        "companions": ["1d6 acolytes"],
    },
    5: {
        "title": "Elder",
        "level": 5,
        "armor_class": 19,
        "hp_dice": "5d6",
        "hp_average": 17,
        "saves": {"doom": 9, "ray": 10, "hold": 11, "blast": 14, "spell": 12},
        "attack_bonus": 2,
        "speed": 20,
        "morale": 10,
        "xp": 360,
        "number_appearing": "1",
        "alignment": ["Lawful", "Neutral"],
        "gear": [
            "Plate mail + Holy Shield",
            "Holy Longsword (1d8+2, +2 Attack)",
            "Shortbow + 20 arrows (1d6)",
            "3 vials of holy water",
            "Prismatic Elixir",
            "Scroll of Cure Affliction",
        ],
        "attacks": [
            {"name": "Holy Longsword", "damage": "1d8+2", "bonus": 4},
            {"name": "Shortbow", "damage": "1d6", "bonus": 2},
        ],
        "spells": ["Lesser Healing", "Light", "Bless", "Hold Person"],
        "holy_order": True,
        "companions": ["1d4 wardens", "2d6 acolytes"],
    },
}

# Holy orders for Clerics level 3+
CLERIC_HOLY_ORDERS = {
    "die": "d6",
    "entries": {
        1: {
            "name": "St Faxis",
            "benefit": "+2 to saves against arcane magic; arcane spell-casters suffer -2 to saves against cleric's spells",
        },
        2: {
            "name": "St Faxis",
            "benefit": "+2 to saves against arcane magic; arcane spell-casters suffer -2 to saves against cleric's spells",
        },
        3: {
            "name": "St Sedge",
            "benefit": "Lay on hands once a day (1 HP / Level)",
        },
        4: {
            "name": "St Sedge",
            "benefit": "Lay on hands once a day (1 HP / Level)",
        },
        5: {
            "name": "St Signis",
            "benefit": "+1 Attack vs undead; harms undead even without silver or magic weapons",
        },
        6: {
            "name": "St Signis",
            "benefit": "+1 Attack vs undead; harms undead even without silver or magic weapons",
        },
    },
}


# =============================================================================
# ENCHANTER TEMPLATES
# =============================================================================

ENCHANTER_TEMPLATES = {
    1: {
        "title": "Wanderer",
        "level": 1,
        "armor_class": 12,
        "hp_dice": "1d6",
        "hp_average": 3,
        "saves": {"doom": 11, "ray": 12, "hold": 13, "blast": 16, "spell": 14},
        "attack_bonus": 0,
        "speed": 30,
        "morale": 7,
        "xp": 15,
        "number_appearing": "1d6",
        "kindred_preference": ["elf", "grimalkin", "woodgrue"],
        "gear": [
            "Leather armour",
            "Shortsword (1d6)",
        ],
        "attacks": [
            {"name": "Shortsword", "damage": "1d6", "bonus": 0},
        ],
        "magic": ["Beguilement", "Rune of Vanishing (1/day)"],
        "skills": {"Detect Magic": 5},
        "companions": [],
    },
    3: {
        "title": "Beguiler",
        "level": 3,
        "armor_class": 14,
        "hp_dice": "3d6",
        "hp_average": 10,
        "saves": {"doom": 10, "ray": 11, "hold": 12, "blast": 15, "spell": 13},
        "attack_bonus": 1,
        "speed": 20,
        "morale": 8,
        "xp": 90,
        "number_appearing": "1d3",
        "kindred_preference": ["elf", "grimalkin", "woodgrue"],
        "gear": [
            "Chainmail",
            "Longsword (1d8)",
            "Fairy Dagger (1d4+2, +2 Attack)",
            "Bottled Light",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 1},
            {"name": "Fairy Dagger", "damage": "1d4+2", "bonus": 3},
        ],
        "magic": [
            "Fool's Gold", "Forgetting", "Subtle Sight",
            "Deathly Blossom (1/day)", "Gust of Wind (1/day)", "Proof Against Deadly Harm (1/day)",
        ],
        "skills": {"Detect Magic": 5},
        "companions": ["1d4 wanderers"],
    },
    5: {
        "title": "Bewitcher",
        "level": 5,
        "armor_class": 14,
        "hp_dice": "5d6",
        "hp_average": 17,
        "saves": {"doom": 9, "ray": 10, "hold": 11, "blast": 14, "spell": 12},
        "attack_bonus": 2,
        "speed": 20,
        "morale": 9,
        "xp": 460,
        "number_appearing": "1",
        "kindred_preference": ["elf", "grimalkin", "woodgrue"],
        "gear": [
            "Chainmail",
            "Longsword (1d8)",
            "Fairy Dagger (1d4+2, +2 Attack)",
            "Liquid Time",
            "Wand of Phantasm (10 charges)",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 2},
            {"name": "Fairy Dagger", "damage": "1d4+2", "bonus": 4},
        ],
        "magic": [
            "Awe", "Cloak of Darkness", "Disguise Object", "Masquerade",
            "Fog Cloud (2/day)", "Gust of Wind (2/day)", "Sway the Mortal Mind (2/day)",
            "Arcane Unbinding (1/week)", "Fairy Gold (1/week)",
        ],
        "skills": {"Detect Magic": 4},
        "companions": ["1d4 beguilers", "1d4 Level 1 bards, hunters, or thieves"],
    },
}


# =============================================================================
# FIGHTER TEMPLATES
# =============================================================================

FIGHTER_TEMPLATES = {
    1: {
        "title": "Soldier",
        "level": 1,
        "armor_class": 15,
        "hp_dice": "1d8",
        "hp_average": 4,
        "saves": {"doom": 12, "ray": 13, "hold": 14, "blast": 15, "spell": 16},
        "attack_bonus": 1,
        "speed": 20,
        "morale": 7,
        "xp": 10,
        "number_appearing": "2d6",
        "gear": [
            "Chainmail + shield",
            "Longsword (1d8)",
            "Shortbow + 20 arrows (1d6)",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 1},
            {"name": "Shortbow", "damage": "1d6", "bonus": 1},
        ],
        "combat_talents": [],
        "companions": [],
    },
    3: {
        "title": "Lieutenant",
        "level": 3,
        "armor_class": 17,
        "hp_dice": "3d8",
        "hp_average": 13,
        "saves": {"doom": 11, "ray": 12, "hold": 13, "blast": 14, "spell": 15},
        "attack_bonus": 2,
        "speed": 20,
        "morale": 8,
        "xp": 40,
        "number_appearing": "1d4",
        "gear": [
            "Plate mail + shield",
            "Longsword (1d8)",
            "Shortbow + 20 arrows (1d6)",
            "Orgon's Scintillating Philtre",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 2},
            {"name": "Shortbow", "damage": "1d6", "bonus": 2},
        ],
        "combat_talents": ["Cleave"],
        "companions": ["2d4 soldiers"],
    },
    5: {
        "title": "Captain",
        "level": 5,
        "armor_class": 19,
        "hp_dice": "5d8",
        "hp_average": 22,
        "saves": {"doom": 10, "ray": 11, "hold": 12, "blast": 13, "spell": 14},
        "attack_bonus": 3,
        "speed": 20,
        "morale": 9,
        "xp": 260,
        "number_appearing": "1",
        "gear": [
            "Plate mail + Arcane Shield",
            "Fairy Longsword (1d8+2, +2 Attack)",
            "Shortbow + 20 arrows (1d6)",
            "Prismatic Elixir",
            "Wereform Elixir",
        ],
        "attacks": [
            {"name": "Fairy Longsword", "damage": "1d8+2", "bonus": 5},
            {"name": "Shortbow", "damage": "1d6", "bonus": 3},
        ],
        "combat_talents": ["Leader"],
        "companions": ["1d4 lieutenants", "2d6 soldiers"],
    },
}


# =============================================================================
# FRIAR TEMPLATES
# =============================================================================

FRIAR_TEMPLATES = {
    1: {
        "title": "Mendicant",
        "level": 1,
        "armor_class": 12,
        "hp_dice": "1d4",
        "hp_average": 2,
        "saves": {"doom": 11, "ray": 12, "hold": 13, "blast": 16, "spell": 14},
        "attack_bonus": 0,
        "speed": 40,
        "morale": 7,
        "xp": 15,
        "number_appearing": "1d6",
        "alignment": ["Lawful", "Neutral"],
        "gear": ["Staff (1d4)"],
        "attacks": [
            {"name": "Staff", "damage": "1d4", "bonus": 0},
        ],
        "spells": ["Lesser Healing"],
        "companions": [],
    },
    3: {
        "title": "Preacher",
        "level": 3,
        "armor_class": 12,
        "hp_dice": "3d4",
        "hp_average": 7,
        "saves": {"doom": 11, "ray": 12, "hold": 13, "blast": 16, "spell": 14},
        "attack_bonus": 0,
        "speed": 40,
        "morale": 8,
        "xp": 65,
        "number_appearing": "1d3",
        "alignment": ["Lawful", "Neutral"],
        "gear": [
            "Staff (1d4)",
            "Sling + 20 stones (1d4)",
            "Vial of holy water",
            "Scroll of Holy Light",
        ],
        "attacks": [
            {"name": "Staff", "damage": "1d4", "bonus": 0},
            {"name": "Sling", "damage": "1d4", "bonus": 0},
        ],
        "spells": ["Detect Evil", "Lesser Healing", "Speak With Animals"],
        "companions": ["1d4 mendicants"],
    },
    5: {
        "title": "Healer",
        "level": 5,
        "armor_class": 13,
        "hp_dice": "5d4",
        "hp_average": 12,
        "saves": {"doom": 10, "ray": 11, "hold": 12, "blast": 15, "spell": 13},
        "attack_bonus": 1,
        "speed": 40,
        "morale": 9,
        "xp": 460,
        "number_appearing": "1",
        "alignment": ["Lawful", "Neutral"],
        "gear": [
            "Holy Staff (1d4+2, +2 Attack)",
            "Sling + 20 stones (1d4)",
            "2 vials of holy water",
            "Scroll of Remove Poison",
            "Rod of Silence (5 charges)",
        ],
        "attacks": [
            {"name": "Holy Staff", "damage": "1d4+2", "bonus": 3},
            {"name": "Sling", "damage": "1d4", "bonus": 1},
        ],
        "spells": [
            "Detect Magic", "Lesser Healing", "Mantle of Protection",
            "Bless", "Reveal Alignment", "Holy Light",
        ],
        "companions": ["1d4 preachers", "2d4 mendicants"],
    },
}


# =============================================================================
# HUNTER TEMPLATES
# =============================================================================

HUNTER_TEMPLATES = {
    1: {
        "title": "Guide",
        "level": 1,
        "armor_class": 12,
        "hp_dice": "1d8",
        "hp_average": 4,
        "saves": {"doom": 12, "ray": 13, "hold": 14, "blast": 15, "spell": 16},
        "attack_bonus": 1,
        "speed": 30,
        "morale": 7,
        "xp": 10,
        "number_appearing": "3d6",
        "gear": [
            "Leather armour",
            "Shortsword (1d6)",
            "Longbow + 20 arrows (1d6)",
        ],
        "attacks": [
            {"name": "Shortsword", "damage": "1d6", "bonus": 1},
            {"name": "Longbow", "damage": "1d6", "bonus": 1},
        ],
        "skills": {
            "Alertness": 6,
            "Stalking": 6,
            "Survival": 5,
            "Tracking": 5,
        },
        "companions": ["Spookhound"],
    },
    3: {
        "title": "Pathfinder",
        "level": 3,
        "armor_class": 15,
        "hp_dice": "3d8",
        "hp_average": 13,
        "saves": {"doom": 11, "ray": 12, "hold": 13, "blast": 14, "spell": 15},
        "attack_bonus": 2,
        "speed": 30,
        "morale": 8,
        "xp": 40,
        "number_appearing": "1d4",
        "gear": [
            "Leather armour + Arcane Shield",
            "Shortsword (1d6)",
            "Longbow + 20 arrows (1d6)",
            "Wyrmsblood Elixir",
        ],
        "attacks": [
            {"name": "Shortsword", "damage": "1d6", "bonus": 2},
            {"name": "Longbow", "damage": "1d6", "bonus": 2},
        ],
        "skills": {
            "Alertness": 6,
            "Stalking": 6,
            "Survival": 4,
            "Tracking": 4,
        },
        "companions": ["Lankston mastiff", "2d4 guides"],
    },
    5: {
        "title": "Strider",
        "level": 5,
        "armor_class": 15,
        "hp_dice": "5d8",
        "hp_average": 22,
        "saves": {"doom": 10, "ray": 11, "hold": 12, "blast": 13, "spell": 14},
        "attack_bonus": 3,
        "speed": 30,
        "morale": 9,
        "xp": 260,
        "number_appearing": "1",
        "gear": [
            "Leather armour + Arcane Shield",
            "Shortsword (1d6)",
            "Fairy Longbow + 20 arrows (1d6+2, +2 Attack)",
            "Hunter's Balm",
            "Elixir of Mutability",
        ],
        "attacks": [
            {"name": "Shortsword", "damage": "1d6", "bonus": 3},
            {"name": "Fairy Longbow", "damage": "1d6+2", "bonus": 5},
        ],
        "skills": {
            "Alertness": 5,
            "Stalking": 5,
            "Survival": 4,
            "Tracking": 4,
        },
        "companions": ["Bear", "1d4 pathfinders", "2d4 guides"],
    },
}


# =============================================================================
# KNIGHT TEMPLATES
# =============================================================================

KNIGHT_TEMPLATES = {
    1: {
        "title": "Squire",
        "level": 1,
        "armor_class": 17,
        "hp_dice": "1d8",
        "hp_average": 4,
        "saves": {"doom": 12, "ray": 13, "hold": 12, "blast": 15, "spell": 15},
        "attack_bonus": 1,
        "speed": 20,
        "morale": 8,
        "xp": 10,
        "number_appearing": "2d6",
        "kindred_preference": ["human", "breggle"],
        "gear": [
            "Plate mail + shield",
            "Longsword (1d8)",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 1},
        ],
        "companions": [],
    },
    3: {
        "title": "Armiger",
        "level": 3,
        "armor_class": 19,
        "hp_dice": "3d8",
        "hp_average": 13,
        "saves": {"doom": 11, "ray": 12, "hold": 11, "blast": 14, "spell": 14},
        "attack_bonus": 2,
        "speed": 20,
        "morale": 9,
        "xp": 40,
        "number_appearing": "1d4",
        "kindred_preference": ["human", "breggle"],
        "gear": [
            "Arcane Plate Mail + shield",
            "Longsword (1d8)",
            "Lance (1d6)",
            "Alchemical Tonic",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 2},
            {"name": "Lance", "damage": "1d6", "bonus": 2},
        ],
        "companions": ["Charger", "1d4 squires"],
    },
    5: {
        "title": "Gallant",
        "level": 5,
        "armor_class": 19,
        "hp_dice": "5d8",
        "hp_average": 22,
        "saves": {"doom": 10, "ray": 11, "hold": 10, "blast": 13, "spell": 13},
        "attack_bonus": 3,
        "speed": 20,
        "morale": 10,
        "xp": 260,
        "number_appearing": "1",
        "kindred_preference": ["human", "breggle"],
        "gear": [
            "Arcane Plate Mail + shield",
            "Longsword (1d8)",
            "Holy Lance (1d6+2, +2 Attack)",
            "Prismatic Elixir",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 3},
            {"name": "Holy Lance", "damage": "1d6+2", "bonus": 5},
        ],
        "companions": ["Charger", "1d4 armigers", "2d4 squires"],
    },
}


# =============================================================================
# MAGICIAN TEMPLATES
# =============================================================================

MAGICIAN_TEMPLATES = {
    1: {
        "title": "Apprentice",
        "level": 1,
        "armor_class": 10,
        "hp_dice": "1d4",
        "hp_average": 2,
        "saves": {"doom": 14, "ray": 14, "hold": 13, "blast": 16, "spell": 14},
        "attack_bonus": 0,
        "speed": 40,
        "morale": 7,
        "xp": 15,
        "number_appearing": "1d4",
        "gear": ["Staff (1d4)"],
        "attacks": [
            {"name": "Staff", "damage": "1d4", "bonus": 0},
        ],
        "spells": ["Vapours of Dream"],
        "skills": {"Detect Magic": 6},
        "companions": ["Level 1 fighter"],
    },
    3: {
        "title": "Conjurer",
        "level": 3,
        "armor_class": 10,
        "hp_dice": "3d4",
        "hp_average": 7,
        "saves": {"doom": 14, "ray": 14, "hold": 13, "blast": 16, "spell": 14},
        "attack_bonus": 0,
        "speed": 40,
        "morale": 8,
        "xp": 90,
        "number_appearing": "1d2",
        "gear": [
            "Staff (1d4)",
            "Silver dagger (1d4)",
            "Scroll of Dispel Magic",
        ],
        "attacks": [
            {"name": "Staff", "damage": "1d4", "bonus": 0},
            {"name": "Silver dagger", "damage": "1d4", "bonus": 0},
        ],
        "spells": ["Fairy Servant", "Ioun Shard", "Phantasm"],
        "skills": {"Detect Magic": 5},
        "companions": ["1d3 apprentices", "1d4 Level 1 fighters"],
    },
    5: {
        "title": "Wizard",
        "level": 5,
        "armor_class": 10,
        "hp_dice": "5d4",
        "hp_average": 12,
        "saves": {"doom": 13, "ray": 13, "hold": 12, "blast": 15, "spell": 13},
        "attack_bonus": 1,
        "speed": 40,
        "morale": 9,
        "xp": 460,
        "number_appearing": "1",
        "gear": [
            "Arcane Staff (1d4+2, +2 Attack)",
            "Silver dagger (1d4)",
            "Scrolls of Knock and Fireball",
            "Staff of Rainbow Hues (10 charges)",
        ],
        "attacks": [
            {"name": "Arcane Staff", "damage": "1d4+2", "bonus": 3},
            {"name": "Silver dagger", "damage": "1d4", "bonus": 1},
        ],
        "spells": [
            "Glyph of Sealing", "Ingratiate", "Dweomerlight",
            "Flaming Spirit", "Circle of Invisibility",
        ],
        "skills": {"Detect Magic": 5},
        "companions": ["1d2 conjurers", "1d4 apprentices", "1 Level 3 fighter", "2d4 Level 1 fighters"],
    },
}


# =============================================================================
# THIEF TEMPLATES
# =============================================================================

THIEF_TEMPLATES = {
    1: {
        "title": "Footpad",
        "level": 1,
        "armor_class": 12,
        "hp_dice": "1d4",
        "hp_average": 2,
        "saves": {"doom": 13, "ray": 14, "hold": 13, "blast": 15, "spell": 15},
        "attack_bonus": 0,
        "speed": 30,
        "morale": 7,
        "xp": 15,
        "number_appearing": "3d10",
        "note": "Often encountered as bandits or pirates",
        "gear": [
            "Leather armour",
            "Longsword (1d8)",
            "3 daggers (1d4)",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 0},
            {"name": "Dagger", "damage": "1d4", "bonus": 0},
        ],
        "special_abilities": ["Back-stab: +4 Attack with dagger, 3d4 damage"],
        "skills": {
            "Climb Wall": 4,
            "Decipher Document": 6,
            "Disarm Mechanism": 6,
            "Legerdemain": 6,
            "Listen": 6,
            "Pick Lock": 5,
            "Search": 6,
            "Stealth": 5,
        },
        "companions": [],
    },
    3: {
        "title": "Robber",
        "level": 3,
        "armor_class": 14,
        "hp_dice": "3d4",
        "hp_average": 7,
        "saves": {"doom": 12, "ray": 13, "hold": 12, "blast": 14, "spell": 14},
        "attack_bonus": 1,
        "speed": 30,
        "morale": 8,
        "xp": 65,
        "number_appearing": "1d6",
        "note": "Often encountered as bandits or pirates",
        "gear": [
            "Fairy Leather Armour",
            "Longsword (1d8)",
            "3 silver daggers (1d4)",
            "Vanishing Philtre",
        ],
        "attacks": [
            {"name": "Longsword", "damage": "1d8", "bonus": 1},
            {"name": "Silver dagger", "damage": "1d4", "bonus": 1},
        ],
        "special_abilities": ["Back-stab: +4 Attack with dagger, 3d4 damage"],
        "skills": {
            "Climb Wall": 4,
            "Decipher Document": 6,
            "Disarm Mechanism": 5,
            "Legerdemain": 5,
            "Listen": 5,
            "Pick Lock": 5,
            "Search": 5,
            "Stealth": 5,
        },
        "companions": ["1d6 footpads"],
    },
    5: {
        "title": "Leader",
        "level": 5,
        "armor_class": 14,
        "hp_dice": "5d4",
        "hp_average": 12,
        "saves": {"doom": 11, "ray": 12, "hold": 11, "blast": 13, "spell": 13},
        "attack_bonus": 2,
        "speed": 30,
        "morale": 9,
        "xp": 360,
        "number_appearing": "1",
        "note": "Often encountered as bandits or pirates",
        "gear": [
            "Fairy Leather Armour",
            "Arcane Shortsword (1d6+2, +2 Attack)",
            "3 silver daggers (1d4)",
            "Liquid Time",
            "Orgon's Scintillating Philtre",
        ],
        "attacks": [
            {"name": "Arcane Shortsword", "damage": "1d6+2", "bonus": 4},
            {"name": "Silver dagger", "damage": "1d4", "bonus": 2},
        ],
        "special_abilities": ["Back-stab: +4 Attack with dagger, 3d4 damage"],
        "skills": {
            "Climb Wall": 3,
            "Decipher Document": 5,
            "Disarm Mechanism": 5,
            "Legerdemain": 5,
            "Listen": 5,
            "Pick Lock": 4,
            "Search": 5,
            "Stealth": 4,
        },
        "companions": ["1d4 robbers", "2d6 footpads"],
    },
}


# =============================================================================
# KINDRED TRAITS
# =============================================================================

KINDRED_TRAITS = {
    "breggle": {
        "ac_bonus_light_armor": 1,  # +1 AC in Light or no armour
        "horn_attack": {
            1: "1d4",
            3: "1d4+1",
            5: "1d4+1",
        },
        "gaze_at_level_5": True,
    },
    "elf": {
        "random_glamour": True,
        "magic_resistance": 2,  # +2 Magic Resistance
        "cold_iron_vulnerability": 1,  # +1 damage from cold iron
    },
    "grimalkin": {
        "ac_bonus_vs_large": 2,  # +2 AC versus Large creatures
        "random_glamour": True,
        "magic_resistance": 2,
        "forms": ["Chester", "Wilder"],
        "cold_iron_vulnerability": 1,
    },
    "human": {
        "initiative_bonus": "Act first on tied initiative",
    },
    "mossling": {
        "random_knack": True,
        "save_bonus_fungal": 4,  # +4 to saves vs fungal spores/poisons
        "save_bonus_other": 2,  # +2 for other saves
    },
    "woodgrue": {
        "moon_sight": 60,  # Moon sight to 60'
        "ac_bonus_vs_large": 2,
        "mad_revelry": True,  # Once a day
        "cold_iron_vulnerability": 1,
    },
}


# =============================================================================
# MASTER TEMPLATE REGISTRY
# =============================================================================

ADVENTURER_TEMPLATES = {
    "bard": BARD_TEMPLATES,
    "cleric": CLERIC_TEMPLATES,
    "enchanter": ENCHANTER_TEMPLATES,
    "fighter": FIGHTER_TEMPLATES,
    "friar": FRIAR_TEMPLATES,
    "hunter": HUNTER_TEMPLATES,
    "knight": KNIGHT_TEMPLATES,
    "magician": MAGICIAN_TEMPLATES,
    "thief": THIEF_TEMPLATES,
}


def get_adventurer_template(class_id: str, level: int) -> Optional[dict]:
    """
    Get an adventurer template for the given class and level.

    Args:
        class_id: Class identifier (e.g., "fighter", "cleric")
        level: Character level (1, 3, or 5)

    Returns:
        Template dictionary or None if not found
    """
    class_templates = ADVENTURER_TEMPLATES.get(class_id.lower())
    if not class_templates:
        return None

    # Find the appropriate level template
    # Levels 1, 3, 5 are defined; use closest lower level for others
    if level <= 1:
        return class_templates.get(1)
    elif level <= 3:
        return class_templates.get(3)
    else:
        return class_templates.get(5)


def get_all_class_ids() -> list[str]:
    """Get list of all adventurer class IDs."""
    return list(ADVENTURER_TEMPLATES.keys())


def get_template_levels(class_id: str) -> list[int]:
    """Get available template levels for a class."""
    class_templates = ADVENTURER_TEMPLATES.get(class_id.lower())
    if not class_templates:
        return []
    return list(class_templates.keys())
