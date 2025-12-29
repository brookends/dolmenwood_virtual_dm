"""
Knight class definition for Dolmenwood.

Noble warriors trained in mounted combat and the arts of chivalry.
Masters of arms who fight with honor.

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
# KNIGHT ABILITIES
# =============================================================================

KNIGHT_COMBAT_MASTERY = ClassAbility(
    ability_id="knight_combat_mastery",
    name="Combat Mastery",
    description=(
        "Knights are trained in all forms of combat. They can use any weapon "
        "and wear any armor, including the heaviest plate."
    ),
    is_passive=True,
)

KNIGHT_MOUNTED_COMBAT = ClassAbility(
    ability_id="knight_mounted_combat",
    name="Mounted Combat",
    description=(
        "Knights are trained riders and excel at mounted combat. They gain +1 "
        "to attack rolls when mounted and their mount gains +1 to AC. At level 5, "
        "these bonuses increase to +2."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "mounted_attack_bonus_by_level": {
            1: 1,
            5: 2,
        },
        "mount_ac_bonus_by_level": {
            1: 1,
            5: 2,
        },
    },
)

KNIGHT_LEADERSHIP = ClassAbility(
    ability_id="knight_leadership",
    name="Leadership",
    description=(
        "Knights inspire those around them. Allies within 30 feet gain +1 to "
        "morale checks. At level 7, this increases to +2."
    ),
    min_level=3,
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "morale_bonus_by_level": {
            3: 1,
            7: 2,
        },
        "range_feet": 30,
    },
)

KNIGHT_CHALLENGE = ClassAbility(
    ability_id="knight_challenge",
    name="Challenge",
    description=(
        "A knight may issue a formal challenge to a single opponent. If the "
        "opponent accepts, they must face the knight in single combat. The "
        "knight gains +2 to attack and damage against the challenged foe."
    ),
    min_level=3,
    is_passive=False,
    uses_per_day=1,
    extra_data={
        "attack_bonus": 2,
        "damage_bonus": 2,
        "requires_acceptance": True,
    },
)

KNIGHT_STRONGHOLD = ClassAbility(
    ability_id="knight_stronghold",
    name="Stronghold",
    description=(
        "At level 9, a knight may establish a keep or castle and attract "
        "a retinue of men-at-arms and squires."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "follower_types": ["men-at-arms", "squires"],
    },
)


# =============================================================================
# KNIGHT LEVEL PROGRESSION
# =============================================================================

# Knight uses fighter saves
KNIGHT_SAVES_1_3 = SavingThrows(doom=12, ray=13, hold=14, blast=15, spell=16)
KNIGHT_SAVES_4_6 = SavingThrows(doom=10, ray=11, hold=12, blast=13, spell=14)
KNIGHT_SAVES_7_9 = SavingThrows(doom=8, ray=9, hold=10, blast=11, spell=12)
KNIGHT_SAVES_10_12 = SavingThrows(doom=6, ray=7, hold=8, blast=9, spell=10)
KNIGHT_SAVES_13_15 = SavingThrows(doom=4, ray=5, hold=6, blast=7, spell=8)

KNIGHT_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=KNIGHT_SAVES_1_3,
        hit_dice="1d8",
    ),
    LevelProgression(
        level=2,
        experience_required=2500,
        attack_bonus=1,
        saving_throws=KNIGHT_SAVES_1_3,
        hit_dice="2d8",
    ),
    LevelProgression(
        level=3,
        experience_required=5000,
        attack_bonus=2,
        saving_throws=KNIGHT_SAVES_1_3,
        hit_dice="3d8",
        abilities_gained=["knight_leadership", "knight_challenge"],
    ),
    LevelProgression(
        level=4,
        experience_required=10000,
        attack_bonus=2,
        saving_throws=KNIGHT_SAVES_4_6,
        hit_dice="4d8",
    ),
    LevelProgression(
        level=5,
        experience_required=20000,
        attack_bonus=3,
        saving_throws=KNIGHT_SAVES_4_6,
        hit_dice="5d8",
    ),
    LevelProgression(
        level=6,
        experience_required=40000,
        attack_bonus=4,
        saving_throws=KNIGHT_SAVES_4_6,
        hit_dice="6d8",
    ),
    LevelProgression(
        level=7,
        experience_required=80000,
        attack_bonus=4,
        saving_throws=KNIGHT_SAVES_7_9,
        hit_dice="7d8",
    ),
    LevelProgression(
        level=8,
        experience_required=150000,
        attack_bonus=5,
        saving_throws=KNIGHT_SAVES_7_9,
        hit_dice="8d8",
    ),
    LevelProgression(
        level=9,
        experience_required=300000,
        attack_bonus=6,
        saving_throws=KNIGHT_SAVES_7_9,
        hit_dice="9d8",
        abilities_gained=["knight_stronghold"],
    ),
    LevelProgression(
        level=10,
        experience_required=450000,
        attack_bonus=6,
        saving_throws=KNIGHT_SAVES_10_12,
        hit_dice="9d8+2",
    ),
    LevelProgression(
        level=11,
        experience_required=600000,
        attack_bonus=7,
        saving_throws=KNIGHT_SAVES_10_12,
        hit_dice="9d8+4",
    ),
    LevelProgression(
        level=12,
        experience_required=750000,
        attack_bonus=8,
        saving_throws=KNIGHT_SAVES_10_12,
        hit_dice="9d8+6",
    ),
    LevelProgression(
        level=13,
        experience_required=900000,
        attack_bonus=8,
        saving_throws=KNIGHT_SAVES_13_15,
        hit_dice="9d8+8",
    ),
    LevelProgression(
        level=14,
        experience_required=1050000,
        attack_bonus=9,
        saving_throws=KNIGHT_SAVES_13_15,
        hit_dice="9d8+10",
    ),
    LevelProgression(
        level=15,
        experience_required=1200000,
        attack_bonus=10,
        saving_throws=KNIGHT_SAVES_13_15,
        hit_dice="9d8+12",
    ),
]


# =============================================================================
# COMPLETE KNIGHT DEFINITION
# =============================================================================

KNIGHT_DEFINITION = ClassDefinition(
    class_id="knight",
    name="Knight",
    description=(
        "Knights are noble warriors trained in the arts of mounted combat and "
        "chivalry. Whether sworn to a lord, dedicated to a holy cause, or simply "
        "seeking glory, knights are paragons of martial prowess. They excel when "
        "fighting from horseback and inspire those around them with their courage."
    ),

    hit_die=HitDie.D8,
    prime_ability="STR",

    magic_type=MagicType.NONE,  # No magic

    armor_proficiencies=[
        ArmorProficiency.ALL,
        ArmorProficiency.SHIELDS,
    ],
    weapon_proficiencies=[
        WeaponProficiency.ALL,
    ],

    level_progression=KNIGHT_LEVEL_PROGRESSION,

    abilities=[
        KNIGHT_COMBAT_MASTERY,
        KNIGHT_MOUNTED_COMBAT,
        KNIGHT_LEADERSHIP,
        KNIGHT_CHALLENGE,
        KNIGHT_STRONGHOLD,
    ],

    # Cannot be certain kindreds (small size, lack of noble traditions)
    restricted_kindreds=["mossling", "woodgrue"],

    starting_equipment=[
        "longsword",
        "lance",
        "plate_armor",
        "shield",
        "warhorse",
    ],

    source_book="Dolmenwood Player Book",
    source_page=66,
)
