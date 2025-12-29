"""
Cleric class definition for Dolmenwood.

Holy warriors who serve the deities of the Pluritine Church, wielding
divine magic and the power to turn undead.

Source: Dolmenwood Player Book
"""

from src.classes.class_data import (
    ArmorProficiency,
    ClassAbility,
    ClassDefinition,
    HitDie,
    LevelProgression,
    MagicType,
    SavingThrows,
    WeaponProficiency,
)


# =============================================================================
# CLERIC ABILITIES
# =============================================================================

CLERIC_HOLY_MAGIC = ClassAbility(
    ability_id="cleric_holy_magic",
    name="Holy Magic",
    description=(
        "Clerics can cast holy spells granted by their deity. Unlike magicians, "
        "clerics do not use spellbooks - they pray for their spells each day. "
        "The number and level of spells they can cast increases with level."
    ),
    is_passive=True,
    extra_data={
        "spell_type": "holy",
        "max_spell_level": 5,
        "requires_prayer": True,
        "requires_holy_symbol": True,
    },
)

CLERIC_TURN_UNDEAD = ClassAbility(
    ability_id="cleric_turn_undead",
    name="Turn Undead",
    description=(
        "Clerics can channel divine power to turn or destroy undead creatures. "
        "The cleric presents their holy symbol and the undead must flee or are "
        "destroyed. More powerful undead are harder to turn."
    ),
    is_passive=False,
    extra_data={
        "affects": "undead",
        "uses_holy_symbol": True,
        "turn_table": {
            # Level: {undead_hd: target_number or "T" for auto-turn or "D" for destroy}
            1: {1: 7, 2: 9, 3: 11, 4: "N", 5: "N"},
            2: {1: 5, 2: 7, 3: 9, 4: 11, 5: "N"},
            3: {1: 3, 2: 5, 3: 7, 4: 9, 5: 11},
            4: {1: "T", 2: 3, 3: 5, 4: 7, 5: 9},
            5: {1: "T", 2: "T", 3: 3, 4: 5, 5: 7},
            6: {1: "D", 2: "T", 3: "T", 4: 3, 5: 5},
            7: {1: "D", 2: "D", 3: "T", 4: "T", 5: 3},
        },
    },
)

CLERIC_TEMPLE = ClassAbility(
    ability_id="cleric_temple",
    name="Temple",
    description=(
        "At level 9, a cleric may establish a temple and attract followers. "
        "They become a religious leader with acolytes and lay followers."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "follower_type": "acolytes",
    },
)


# =============================================================================
# CLERIC LEVEL PROGRESSION
# =============================================================================

# Cleric saving throw progression
CLERIC_SAVES_1_4 = SavingThrows(doom=11, ray=12, hold=14, blast=16, spell=15)
CLERIC_SAVES_5_8 = SavingThrows(doom=9, ray=10, hold=12, blast=14, spell=12)
CLERIC_SAVES_9_12 = SavingThrows(doom=6, ray=7, hold=9, blast=11, spell=9)
CLERIC_SAVES_13_15 = SavingThrows(doom=3, ray=5, hold=7, blast=8, spell=7)

CLERIC_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=CLERIC_SAVES_1_4,
        hit_dice="1d6",
        spell_slots={},  # No spells at level 1
    ),
    LevelProgression(
        level=2,
        experience_required=1500,
        attack_bonus=0,
        saving_throws=CLERIC_SAVES_1_4,
        hit_dice="2d6",
        spell_slots={1: 1},
    ),
    LevelProgression(
        level=3,
        experience_required=3000,
        attack_bonus=1,
        saving_throws=CLERIC_SAVES_1_4,
        hit_dice="3d6",
        spell_slots={1: 2},
    ),
    LevelProgression(
        level=4,
        experience_required=6000,
        attack_bonus=1,
        saving_throws=CLERIC_SAVES_1_4,
        hit_dice="4d6",
        spell_slots={1: 2, 2: 1},
    ),
    LevelProgression(
        level=5,
        experience_required=12000,
        attack_bonus=2,
        saving_throws=CLERIC_SAVES_5_8,
        hit_dice="5d6",
        spell_slots={1: 2, 2: 2},
    ),
    LevelProgression(
        level=6,
        experience_required=25000,
        attack_bonus=2,
        saving_throws=CLERIC_SAVES_5_8,
        hit_dice="6d6",
        spell_slots={1: 2, 2: 2, 3: 1},
    ),
    LevelProgression(
        level=7,
        experience_required=50000,
        attack_bonus=3,
        saving_throws=CLERIC_SAVES_5_8,
        hit_dice="7d6",
        spell_slots={1: 2, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=8,
        experience_required=100000,
        attack_bonus=3,
        saving_throws=CLERIC_SAVES_5_8,
        hit_dice="8d6",
        spell_slots={1: 3, 2: 2, 3: 2, 4: 1},
    ),
    LevelProgression(
        level=9,
        experience_required=200000,
        attack_bonus=4,
        saving_throws=CLERIC_SAVES_9_12,
        hit_dice="9d6",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 2},
        abilities_gained=["cleric_temple"],
    ),
    LevelProgression(
        level=10,
        experience_required=300000,
        attack_bonus=4,
        saving_throws=CLERIC_SAVES_9_12,
        hit_dice="9d6+1",
        spell_slots={1: 3, 2: 3, 3: 3, 4: 2, 5: 1},
    ),
    LevelProgression(
        level=11,
        experience_required=400000,
        attack_bonus=5,
        saving_throws=CLERIC_SAVES_9_12,
        hit_dice="9d6+2",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=12,
        experience_required=500000,
        attack_bonus=5,
        saving_throws=CLERIC_SAVES_9_12,
        hit_dice="9d6+3",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=13,
        experience_required=600000,
        attack_bonus=6,
        saving_throws=CLERIC_SAVES_13_15,
        hit_dice="9d6+4",
        spell_slots={1: 4, 2: 4, 3: 4, 4: 3, 5: 3},
    ),
    LevelProgression(
        level=14,
        experience_required=700000,
        attack_bonus=6,
        saving_throws=CLERIC_SAVES_13_15,
        hit_dice="9d6+5",
        spell_slots={1: 4, 2: 4, 3: 4, 4: 4, 5: 3},
    ),
    LevelProgression(
        level=15,
        experience_required=800000,
        attack_bonus=7,
        saving_throws=CLERIC_SAVES_13_15,
        hit_dice="9d6+6",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 4, 5: 4},
    ),
]


# =============================================================================
# COMPLETE CLERIC DEFINITION
# =============================================================================

CLERIC_DEFINITION = ClassDefinition(
    class_id="cleric",
    name="Cleric",
    description=(
        "Clerics are holy warriors who serve the deities of the Pluritine Church. "
        "They combine martial prowess with divine magic, able to heal the wounded, "
        "protect the faithful, and turn undead creatures. Unlike magicians, clerics "
        "receive their spells through prayer rather than study."
    ),

    hit_die=HitDie.D6,
    prime_ability="WIS",

    magic_type=MagicType.HOLY,

    armor_proficiencies=[
        ArmorProficiency.ALL,
        ArmorProficiency.SHIELDS,
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,  # Blunt weapons only (maces, staves, etc.)
    ],

    level_progression=CLERIC_LEVEL_PROGRESSION,

    abilities=[
        CLERIC_HOLY_MAGIC,
        CLERIC_TURN_UNDEAD,
        CLERIC_TEMPLE,
    ],

    # Cannot be fairy kindreds (no spiritual connection with mortal deities)
    restricted_kindreds=["elf", "grimalkin", "woodgrue"],

    starting_equipment=[
        "holy_symbol",
        "mace",
        "chain_armor",
        "shield",
        "adventuring_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=58,
)
