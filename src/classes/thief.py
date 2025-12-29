"""
Thief class definition for Dolmenwood.

Skilled infiltrators who rely on stealth, cunning, and specialized skills
rather than direct combat.

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
# THIEF ABILITIES
# =============================================================================

THIEF_SKILLS = ClassAbility(
    ability_id="thief_skills",
    name="Thief Skills",
    description=(
        "Thieves have specialized skills: Climb, Find/Remove Traps, Hear Noise, "
        "Hide in Shadows, Move Silently, Open Locks, Pick Pockets. "
        "These skills improve with level."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skills": [
            "climb",
            "find_remove_traps",
            "hear_noise",
            "hide_in_shadows",
            "move_silently",
            "open_locks",
            "pick_pockets",
        ],
        # Skill targets by level (2-in-6 at level 1, improves)
        "skill_progression": {
            1: {"base": 2, "hear_noise": 3},
            3: {"base": 3, "hear_noise": 4},
            5: {"base": 4, "hear_noise": 4},
            7: {"base": 4, "hear_noise": 5},
            9: {"base": 5, "hear_noise": 5},
            11: {"base": 5, "hear_noise": 5},
            13: {"base": 5, "hear_noise": 6},
        },
    },
)

THIEF_BACKSTAB = ClassAbility(
    ability_id="thief_backstab",
    name="Backstab",
    description=(
        "When attacking an unaware opponent from behind, a thief gains +4 to hit "
        "and deals double damage. At level 5, this increases to triple damage, "
        "and at level 9, quadruple damage."
    ),
    is_passive=False,
    is_attack=True,
    scales_with_level=True,
    extra_data={
        "attack_bonus": 4,
        "damage_multiplier_by_level": {
            1: 2,
            5: 3,
            9: 4,
        },
        "requires": "unaware target, attack from behind",
    },
)

THIEF_READ_LANGUAGES = ClassAbility(
    ability_id="thief_read_languages",
    name="Read Languages",
    description=(
        "At level 4, a thief gains the ability to read languages, including "
        "magical writings (though not cast spells from them). There is an 80% "
        "chance of successfully reading any language."
    ),
    min_level=4,
    is_passive=True,
    extra_data={
        "success_chance": 80,
        "includes_magical": True,
        "cannot_cast_spells": True,
    },
)

THIEF_USE_SCROLLS = ClassAbility(
    ability_id="thief_use_scrolls",
    name="Use Scrolls",
    description=(
        "At level 10, a thief can attempt to use arcane spell scrolls. "
        "There is a 10% chance of the spell backfiring."
    ),
    min_level=10,
    is_passive=True,
    extra_data={
        "scroll_types": ["arcane"],
        "backfire_chance": 10,
    },
)

THIEF_GUILD = ClassAbility(
    ability_id="thief_guild",
    name="Thieves' Guild",
    description=(
        "At level 9, a thief may establish a hideout and attract a band of "
        "lesser thieves as followers."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "follower_type": "thieves",
    },
)


# =============================================================================
# THIEF LEVEL PROGRESSION
# =============================================================================

# Thief saving throw progression
THIEF_SAVES_1_4 = SavingThrows(doom=13, ray=14, hold=13, blast=16, spell=15)
THIEF_SAVES_5_8 = SavingThrows(doom=11, ray=12, hold=11, blast=14, spell=13)
THIEF_SAVES_9_12 = SavingThrows(doom=9, ray=10, hold=9, blast=12, spell=11)
THIEF_SAVES_13_15 = SavingThrows(doom=7, ray=8, hold=7, blast=10, spell=9)

THIEF_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=THIEF_SAVES_1_4,
        hit_dice="1d4",
    ),
    LevelProgression(
        level=2,
        experience_required=1200,
        attack_bonus=0,
        saving_throws=THIEF_SAVES_1_4,
        hit_dice="2d4",
    ),
    LevelProgression(
        level=3,
        experience_required=2400,
        attack_bonus=1,
        saving_throws=THIEF_SAVES_1_4,
        hit_dice="3d4",
    ),
    LevelProgression(
        level=4,
        experience_required=4800,
        attack_bonus=1,
        saving_throws=THIEF_SAVES_1_4,
        hit_dice="4d4",
        abilities_gained=["thief_read_languages"],
    ),
    LevelProgression(
        level=5,
        experience_required=9600,
        attack_bonus=2,
        saving_throws=THIEF_SAVES_5_8,
        hit_dice="5d4",
    ),
    LevelProgression(
        level=6,
        experience_required=20000,
        attack_bonus=2,
        saving_throws=THIEF_SAVES_5_8,
        hit_dice="6d4",
    ),
    LevelProgression(
        level=7,
        experience_required=40000,
        attack_bonus=3,
        saving_throws=THIEF_SAVES_5_8,
        hit_dice="7d4",
    ),
    LevelProgression(
        level=8,
        experience_required=80000,
        attack_bonus=3,
        saving_throws=THIEF_SAVES_5_8,
        hit_dice="8d4",
    ),
    LevelProgression(
        level=9,
        experience_required=160000,
        attack_bonus=4,
        saving_throws=THIEF_SAVES_9_12,
        hit_dice="9d4",
        abilities_gained=["thief_guild"],
    ),
    LevelProgression(
        level=10,
        experience_required=280000,
        attack_bonus=4,
        saving_throws=THIEF_SAVES_9_12,
        hit_dice="9d4+2",
        abilities_gained=["thief_use_scrolls"],
    ),
    LevelProgression(
        level=11,
        experience_required=400000,
        attack_bonus=5,
        saving_throws=THIEF_SAVES_9_12,
        hit_dice="9d4+4",
    ),
    LevelProgression(
        level=12,
        experience_required=520000,
        attack_bonus=5,
        saving_throws=THIEF_SAVES_9_12,
        hit_dice="9d4+6",
    ),
    LevelProgression(
        level=13,
        experience_required=640000,
        attack_bonus=6,
        saving_throws=THIEF_SAVES_13_15,
        hit_dice="9d4+8",
    ),
    LevelProgression(
        level=14,
        experience_required=760000,
        attack_bonus=6,
        saving_throws=THIEF_SAVES_13_15,
        hit_dice="9d4+10",
    ),
    LevelProgression(
        level=15,
        experience_required=880000,
        attack_bonus=7,
        saving_throws=THIEF_SAVES_13_15,
        hit_dice="9d4+12",
    ),
]


# =============================================================================
# COMPLETE THIEF DEFINITION
# =============================================================================

THIEF_DEFINITION = ClassDefinition(
    class_id="thief",
    name="Thief",
    description=(
        "Thieves are skilled infiltrators who rely on stealth, cunning, and "
        "specialized abilities rather than brute force. They excel at sneaking, "
        "picking locks, disarming traps, and striking from the shadows. While "
        "not as tough as fighters, a thief's backstab can be devastating."
    ),

    hit_die=HitDie.D4,
    prime_ability="DEX",

    magic_type=MagicType.NONE,

    armor_proficiencies=[
        ArmorProficiency.LIGHT,  # Leather only
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,
        WeaponProficiency.RANGED,
    ],

    level_progression=THIEF_LEVEL_PROGRESSION,

    abilities=[
        THIEF_SKILLS,
        THIEF_BACKSTAB,
        THIEF_READ_LANGUAGES,
        THIEF_USE_SCROLLS,
        THIEF_GUILD,
    ],

    # No kindred restrictions
    restricted_kindreds=[],

    starting_equipment=[
        "leather_armor",
        "dagger",
        "thieves_tools",
        "adventuring_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=78,
)
