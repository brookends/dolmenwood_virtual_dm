"""
Friar class definition for Dolmenwood.

Wandering holy folk who travel the land, aiding the common people
and spreading the word of their faith.

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
# FRIAR ABILITIES
# =============================================================================

FRIAR_HOLY_MAGIC = ClassAbility(
    ability_id="friar_holy_magic",
    name="Holy Magic",
    description=(
        "Friars can cast holy spells through prayer. They have access to the "
        "same spell list as clerics but gain spells at a slower rate."
    ),
    is_passive=True,
    extra_data={
        "spell_type": "holy",
        "max_spell_level": 5,
        "requires_prayer": True,
    },
)

FRIAR_TURN_UNDEAD = ClassAbility(
    ability_id="friar_turn_undead",
    name="Turn Undead",
    description=(
        "Friars can turn undead, though less effectively than clerics. "
        "They turn undead as a cleric of 2 levels lower."
    ),
    is_passive=False,
    extra_data={
        "affects": "undead",
        "level_penalty": -2,
    },
)

FRIAR_WANDERER = ClassAbility(
    ability_id="friar_wanderer",
    name="Wanderer",
    description=(
        "Friars are experienced travelers. They have a Skill Target of 4 for "
        "Survival when foraging and navigating wilderness."
    ),
    is_passive=True,
    extra_data={
        "skill_targets": {
            "survival_foraging": 4,
            "navigation": 4,
        },
    },
)

FRIAR_HEALING_HANDS = ClassAbility(
    ability_id="friar_healing_hands",
    name="Healing Hands",
    description=(
        "Once per day, a friar can lay hands on a wounded creature to heal "
        "1d6 hit points plus 1 per friar level."
    ),
    is_passive=False,
    uses_per_day=1,
    extra_data={
        "healing": "1d6 + level",
    },
)


# =============================================================================
# FRIAR LEVEL PROGRESSION
# =============================================================================

# Friar uses same saves as cleric
FRIAR_SAVES_1_4 = SavingThrows(doom=11, ray=12, hold=14, blast=16, spell=15)
FRIAR_SAVES_5_8 = SavingThrows(doom=9, ray=10, hold=12, blast=14, spell=12)
FRIAR_SAVES_9_12 = SavingThrows(doom=6, ray=7, hold=9, blast=11, spell=9)
FRIAR_SAVES_13_15 = SavingThrows(doom=3, ray=5, hold=7, blast=8, spell=7)

FRIAR_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=FRIAR_SAVES_1_4,
        hit_dice="1d6",
        spell_slots={},
    ),
    LevelProgression(
        level=2,
        experience_required=1500,
        attack_bonus=0,
        saving_throws=FRIAR_SAVES_1_4,
        hit_dice="2d6",
        spell_slots={1: 1},
    ),
    LevelProgression(
        level=3,
        experience_required=3000,
        attack_bonus=1,
        saving_throws=FRIAR_SAVES_1_4,
        hit_dice="3d6",
        spell_slots={1: 2},
    ),
    LevelProgression(
        level=4,
        experience_required=6000,
        attack_bonus=1,
        saving_throws=FRIAR_SAVES_1_4,
        hit_dice="4d6",
        spell_slots={1: 2, 2: 1},
    ),
    LevelProgression(
        level=5,
        experience_required=12000,
        attack_bonus=2,
        saving_throws=FRIAR_SAVES_5_8,
        hit_dice="5d6",
        spell_slots={1: 2, 2: 2},
    ),
    LevelProgression(
        level=6,
        experience_required=25000,
        attack_bonus=2,
        saving_throws=FRIAR_SAVES_5_8,
        hit_dice="6d6",
        spell_slots={1: 2, 2: 2, 3: 1},
    ),
    LevelProgression(
        level=7,
        experience_required=50000,
        attack_bonus=3,
        saving_throws=FRIAR_SAVES_5_8,
        hit_dice="7d6",
        spell_slots={1: 2, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=8,
        experience_required=100000,
        attack_bonus=3,
        saving_throws=FRIAR_SAVES_5_8,
        hit_dice="8d6",
        spell_slots={1: 3, 2: 2, 3: 2, 4: 1},
    ),
    LevelProgression(
        level=9,
        experience_required=200000,
        attack_bonus=4,
        saving_throws=FRIAR_SAVES_9_12,
        hit_dice="9d6",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 2},
    ),
    LevelProgression(
        level=10,
        experience_required=300000,
        attack_bonus=4,
        saving_throws=FRIAR_SAVES_9_12,
        hit_dice="9d6+1",
        spell_slots={1: 3, 2: 3, 3: 3, 4: 2, 5: 1},
    ),
    LevelProgression(
        level=11,
        experience_required=400000,
        attack_bonus=5,
        saving_throws=FRIAR_SAVES_9_12,
        hit_dice="9d6+2",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=12,
        experience_required=500000,
        attack_bonus=5,
        saving_throws=FRIAR_SAVES_9_12,
        hit_dice="9d6+3",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=13,
        experience_required=600000,
        attack_bonus=6,
        saving_throws=FRIAR_SAVES_13_15,
        hit_dice="9d6+4",
        spell_slots={1: 4, 2: 4, 3: 4, 4: 3, 5: 3},
    ),
    LevelProgression(
        level=14,
        experience_required=700000,
        attack_bonus=6,
        saving_throws=FRIAR_SAVES_13_15,
        hit_dice="9d6+5",
        spell_slots={1: 4, 2: 4, 3: 4, 4: 4, 5: 3},
    ),
    LevelProgression(
        level=15,
        experience_required=800000,
        attack_bonus=7,
        saving_throws=FRIAR_SAVES_13_15,
        hit_dice="9d6+6",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 4, 5: 4},
    ),
]


# =============================================================================
# COMPLETE FRIAR DEFINITION
# =============================================================================

FRIAR_DEFINITION = ClassDefinition(
    class_id="friar",
    name="Friar",
    description=(
        "Friars are wandering holy folk who travel the land, ministering to the "
        "common people and spreading their faith. Unlike clerics who are tied to "
        "temples, friars are itinerant, at home on the road and in the wild. "
        "They combine modest combat ability with healing magic and survival skills."
    ),

    hit_die=HitDie.D6,
    prime_ability="WIS",

    magic_type=MagicType.HOLY,

    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        ArmorProficiency.MEDIUM,
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,
    ],

    level_progression=FRIAR_LEVEL_PROGRESSION,

    abilities=[
        FRIAR_HOLY_MAGIC,
        FRIAR_TURN_UNDEAD,
        FRIAR_WANDERER,
        FRIAR_HEALING_HANDS,
    ],

    # Cannot be fairy kindreds
    restricted_kindreds=["elf", "grimalkin", "woodgrue", "mossling", "breggle"],

    starting_equipment=[
        "holy_symbol",
        "quarterstaff",
        "leather_armor",
        "traveling_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=62,
)
