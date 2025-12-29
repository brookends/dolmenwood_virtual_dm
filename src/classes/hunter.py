"""
Hunter class definition for Dolmenwood.

Wilderness warriors skilled in tracking, survival, and ranged combat.
At home in the wild forests of Dolmenwood.

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
# HUNTER ABILITIES
# =============================================================================

HUNTER_TRACKING = ClassAbility(
    ability_id="hunter_tracking",
    name="Tracking",
    description=(
        "Hunters can track creatures through the wilderness. They have a Skill "
        "Target of 4 for Survival when tracking. This improves to 3 at level 5 "
        "and 2 at level 9."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skill_target_by_level": {
            1: 4,
            5: 3,
            9: 2,
        },
    },
)

HUNTER_WILDERNESS_SURVIVAL = ClassAbility(
    ability_id="hunter_wilderness_survival",
    name="Wilderness Survival",
    description=(
        "Hunters are experts at surviving in the wild. They have a Skill Target "
        "of 3 for Survival when foraging, finding shelter, and avoiding hazards."
    ),
    is_passive=True,
    extra_data={
        "skill_targets": {
            "foraging": 3,
            "find_shelter": 3,
            "avoid_hazards": 3,
        },
    },
)

HUNTER_AMBUSH = ClassAbility(
    ability_id="hunter_ambush",
    name="Ambush",
    description=(
        "When attacking from a hidden position, a hunter gains +2 to hit and "
        "deals an extra 1d6 damage. At level 7, the bonus increases to +4 and "
        "2d6 extra damage."
    ),
    is_passive=False,
    is_attack=True,
    scales_with_level=True,
    extra_data={
        "requires": "hidden position",
        "attack_bonus_by_level": {
            1: 2,
            7: 4,
        },
        "extra_damage_by_level": {
            1: "1d6",
            7: "2d6",
        },
    },
)

HUNTER_ANIMAL_COMPANION = ClassAbility(
    ability_id="hunter_animal_companion",
    name="Animal Companion",
    description=(
        "At level 5, a hunter may befriend an animal companion that serves as "
        "a loyal ally. The companion can be a hunting dog, hawk, or similar "
        "creature native to Dolmenwood."
    ),
    min_level=5,
    is_passive=True,
    extra_data={
        "companion_types": ["dog", "hawk", "wolf", "boar"],
    },
)

HUNTER_HIDEOUT = ClassAbility(
    ability_id="hunter_hideout",
    name="Hideout",
    description=(
        "At level 9, a hunter may establish a hidden lodge in the wilderness "
        "and attract a band of fellow hunters and woodfolk."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "follower_types": ["hunters", "woodfolk"],
    },
)


# =============================================================================
# HUNTER LEVEL PROGRESSION
# =============================================================================

# Hunter saves (between fighter and thief)
HUNTER_SAVES_1_3 = SavingThrows(doom=12, ray=13, hold=13, blast=15, spell=16)
HUNTER_SAVES_4_6 = SavingThrows(doom=10, ray=11, hold=11, blast=13, spell=14)
HUNTER_SAVES_7_9 = SavingThrows(doom=8, ray=9, hold=9, blast=11, spell=12)
HUNTER_SAVES_10_12 = SavingThrows(doom=6, ray=7, hold=7, blast=9, spell=10)
HUNTER_SAVES_13_15 = SavingThrows(doom=4, ray=5, hold=5, blast=7, spell=8)

HUNTER_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=HUNTER_SAVES_1_3,
        hit_dice="1d6",
    ),
    LevelProgression(
        level=2,
        experience_required=2000,
        attack_bonus=1,
        saving_throws=HUNTER_SAVES_1_3,
        hit_dice="2d6",
    ),
    LevelProgression(
        level=3,
        experience_required=4000,
        attack_bonus=2,
        saving_throws=HUNTER_SAVES_1_3,
        hit_dice="3d6",
    ),
    LevelProgression(
        level=4,
        experience_required=8000,
        attack_bonus=2,
        saving_throws=HUNTER_SAVES_4_6,
        hit_dice="4d6",
    ),
    LevelProgression(
        level=5,
        experience_required=16000,
        attack_bonus=3,
        saving_throws=HUNTER_SAVES_4_6,
        hit_dice="5d6",
        abilities_gained=["hunter_animal_companion"],
    ),
    LevelProgression(
        level=6,
        experience_required=32000,
        attack_bonus=4,
        saving_throws=HUNTER_SAVES_4_6,
        hit_dice="6d6",
    ),
    LevelProgression(
        level=7,
        experience_required=64000,
        attack_bonus=4,
        saving_throws=HUNTER_SAVES_7_9,
        hit_dice="7d6",
    ),
    LevelProgression(
        level=8,
        experience_required=120000,
        attack_bonus=5,
        saving_throws=HUNTER_SAVES_7_9,
        hit_dice="8d6",
    ),
    LevelProgression(
        level=9,
        experience_required=240000,
        attack_bonus=6,
        saving_throws=HUNTER_SAVES_7_9,
        hit_dice="9d6",
        abilities_gained=["hunter_hideout"],
    ),
    LevelProgression(
        level=10,
        experience_required=360000,
        attack_bonus=6,
        saving_throws=HUNTER_SAVES_10_12,
        hit_dice="9d6+2",
    ),
    LevelProgression(
        level=11,
        experience_required=480000,
        attack_bonus=7,
        saving_throws=HUNTER_SAVES_10_12,
        hit_dice="9d6+4",
    ),
    LevelProgression(
        level=12,
        experience_required=600000,
        attack_bonus=8,
        saving_throws=HUNTER_SAVES_10_12,
        hit_dice="9d6+6",
    ),
    LevelProgression(
        level=13,
        experience_required=720000,
        attack_bonus=8,
        saving_throws=HUNTER_SAVES_13_15,
        hit_dice="9d6+8",
    ),
    LevelProgression(
        level=14,
        experience_required=840000,
        attack_bonus=9,
        saving_throws=HUNTER_SAVES_13_15,
        hit_dice="9d6+10",
    ),
    LevelProgression(
        level=15,
        experience_required=960000,
        attack_bonus=10,
        saving_throws=HUNTER_SAVES_13_15,
        hit_dice="9d6+12",
    ),
]


# =============================================================================
# COMPLETE HUNTER DEFINITION
# =============================================================================

HUNTER_DEFINITION = ClassDefinition(
    class_id="hunter",
    name="Hunter",
    description=(
        "Hunters are wilderness warriors skilled in tracking, survival, and "
        "ranged combat. They are at home in the wild forests of Dolmenwood, "
        "able to live off the land and pursue their quarry across any terrain. "
        "While not as tough as fighters, hunters excel at ambush tactics and "
        "can befriend animal companions."
    ),

    hit_die=HitDie.D6,
    prime_ability="DEX",

    magic_type=MagicType.NONE,

    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        ArmorProficiency.MEDIUM,
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,
        WeaponProficiency.MARTIAL,
        WeaponProficiency.RANGED,
    ],

    level_progression=HUNTER_LEVEL_PROGRESSION,

    abilities=[
        HUNTER_TRACKING,
        HUNTER_WILDERNESS_SURVIVAL,
        HUNTER_AMBUSH,
        HUNTER_ANIMAL_COMPANION,
        HUNTER_HIDEOUT,
    ],

    # No kindred restrictions
    restricted_kindreds=[],

    starting_equipment=[
        "longbow",
        "arrows_20",
        "short_sword",
        "leather_armor",
        "traveling_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=64,
)
