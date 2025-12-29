"""
Fighter class definition for Dolmenwood.

Masters of armed combat, fighters are trained warriors who rely on
strength, skill, and tactical prowess.

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
# FIGHTER ABILITIES
# =============================================================================

FIGHTER_COMBAT_EXPERTISE = ClassAbility(
    ability_id="fighter_combat_expertise",
    name="Combat Expertise",
    description=(
        "Fighters are trained in all forms of combat. They can use any weapon "
        "and wear any armor, including shields."
    ),
    is_passive=True,
)

FIGHTER_EXTRA_ATTACKS = ClassAbility(
    ability_id="fighter_extra_attacks",
    name="Extra Attacks",
    description=(
        "At higher levels, fighters gain additional attacks per round against "
        "foes of 1 HD or less. At level 7, fighters can make 2 attacks per round. "
        "At level 13, this increases to 3 attacks per round."
    ),
    min_level=7,
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "attacks_by_level": {
            1: 1,
            7: 2,
            13: 3,
        },
        "applies_to": "foes of 1 HD or less",
    },
)

FIGHTER_STRONGHOLD = ClassAbility(
    ability_id="fighter_stronghold",
    name="Stronghold",
    description=(
        "At level 9, a fighter may establish a stronghold and attract followers. "
        "The fighter becomes a lord or lady, attracting men-at-arms to their service."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "follower_type": "men-at-arms",
    },
)


# =============================================================================
# FIGHTER LEVEL PROGRESSION
# =============================================================================

# Fighter saving throw progression (improves every 3 levels)
FIGHTER_SAVES_1_3 = SavingThrows(doom=12, ray=13, hold=14, blast=15, spell=16)
FIGHTER_SAVES_4_6 = SavingThrows(doom=10, ray=11, hold=12, blast=13, spell=14)
FIGHTER_SAVES_7_9 = SavingThrows(doom=8, ray=9, hold=10, blast=11, spell=12)
FIGHTER_SAVES_10_12 = SavingThrows(doom=6, ray=7, hold=8, blast=9, spell=10)
FIGHTER_SAVES_13_15 = SavingThrows(doom=4, ray=5, hold=6, blast=7, spell=8)

FIGHTER_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=FIGHTER_SAVES_1_3,
        hit_dice="1d8",
    ),
    LevelProgression(
        level=2,
        experience_required=2000,
        attack_bonus=1,
        saving_throws=FIGHTER_SAVES_1_3,
        hit_dice="2d8",
    ),
    LevelProgression(
        level=3,
        experience_required=4000,
        attack_bonus=2,
        saving_throws=FIGHTER_SAVES_1_3,
        hit_dice="3d8",
    ),
    LevelProgression(
        level=4,
        experience_required=8000,
        attack_bonus=2,
        saving_throws=FIGHTER_SAVES_4_6,
        hit_dice="4d8",
    ),
    LevelProgression(
        level=5,
        experience_required=16000,
        attack_bonus=3,
        saving_throws=FIGHTER_SAVES_4_6,
        hit_dice="5d8",
    ),
    LevelProgression(
        level=6,
        experience_required=32000,
        attack_bonus=4,
        saving_throws=FIGHTER_SAVES_4_6,
        hit_dice="6d8",
    ),
    LevelProgression(
        level=7,
        experience_required=64000,
        attack_bonus=4,
        saving_throws=FIGHTER_SAVES_7_9,
        hit_dice="7d8",
        attacks_per_round=2,
        abilities_gained=["fighter_extra_attacks"],
    ),
    LevelProgression(
        level=8,
        experience_required=120000,
        attack_bonus=5,
        saving_throws=FIGHTER_SAVES_7_9,
        hit_dice="8d8",
        attacks_per_round=2,
    ),
    LevelProgression(
        level=9,
        experience_required=240000,
        attack_bonus=6,
        saving_throws=FIGHTER_SAVES_7_9,
        hit_dice="9d8",
        attacks_per_round=2,
        abilities_gained=["fighter_stronghold"],
    ),
    LevelProgression(
        level=10,
        experience_required=360000,
        attack_bonus=6,
        saving_throws=FIGHTER_SAVES_10_12,
        hit_dice="9d8+2",
        attacks_per_round=2,
    ),
    LevelProgression(
        level=11,
        experience_required=480000,
        attack_bonus=7,
        saving_throws=FIGHTER_SAVES_10_12,
        hit_dice="9d8+4",
        attacks_per_round=2,
    ),
    LevelProgression(
        level=12,
        experience_required=600000,
        attack_bonus=8,
        saving_throws=FIGHTER_SAVES_10_12,
        hit_dice="9d8+6",
        attacks_per_round=2,
    ),
    LevelProgression(
        level=13,
        experience_required=720000,
        attack_bonus=8,
        saving_throws=FIGHTER_SAVES_13_15,
        hit_dice="9d8+8",
        attacks_per_round=3,
    ),
    LevelProgression(
        level=14,
        experience_required=840000,
        attack_bonus=9,
        saving_throws=FIGHTER_SAVES_13_15,
        hit_dice="9d8+10",
        attacks_per_round=3,
    ),
    LevelProgression(
        level=15,
        experience_required=960000,
        attack_bonus=10,
        saving_throws=FIGHTER_SAVES_13_15,
        hit_dice="9d8+12",
        attacks_per_round=3,
    ),
]


# =============================================================================
# COMPLETE FIGHTER DEFINITION
# =============================================================================

FIGHTER_DEFINITION = ClassDefinition(
    class_id="fighter",
    name="Fighter",
    description=(
        "Fighters are warriors trained in the arts of combat. Whether mercenaries, "
        "soldiers, knights-errant, or dungeon delvers, fighters excel at dealing "
        "and surviving physical violence. They are the most straightforward of "
        "adventuring classes, relying on strength of arms rather than magic or guile."
    ),

    hit_die=HitDie.D8,
    prime_ability="STR",

    magic_type=MagicType.NONE,

    armor_proficiencies=[
        ArmorProficiency.ALL,
        ArmorProficiency.SHIELDS,
    ],
    weapon_proficiencies=[
        WeaponProficiency.ALL,
    ],

    level_progression=FIGHTER_LEVEL_PROGRESSION,

    abilities=[
        FIGHTER_COMBAT_EXPERTISE,
        FIGHTER_EXTRA_ATTACKS,
        FIGHTER_STRONGHOLD,
    ],

    # No kindred restrictions - any kindred can be a fighter
    restricted_kindreds=[],

    starting_equipment=[
        "weapon_of_choice",
        "armor_of_choice",
        "shield_optional",
        "adventuring_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=56,
)
