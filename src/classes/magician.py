"""
Magician class definition for Dolmenwood.

Arcane spellcasters who study the mystical arts, commanding powerful
magic through memorized spells.

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
# MAGICIAN ABILITIES
# =============================================================================

MAGICIAN_ARCANE_MAGIC = ClassAbility(
    ability_id="magician_arcane_magic",
    name="Arcane Magic",
    description=(
        "Magicians can cast arcane spells. They must memorize spells from their "
        "spellbook each day. The number and level of spells they can memorize "
        "increases with level."
    ),
    is_passive=True,
    extra_data={
        "spell_type": "arcane",
        "max_spell_level": 6,
        "requires_spellbook": True,
        "requires_memorization": True,
    },
)

MAGICIAN_SPELLBOOK = ClassAbility(
    ability_id="magician_spellbook",
    name="Spellbook",
    description=(
        "A magician keeps a spellbook containing all the spells they have learned. "
        "At first level, the spellbook contains Read Magic plus 1d4 additional "
        "first level spells. New spells can be added by copying from scrolls or "
        "other spellbooks."
    ),
    is_passive=True,
    extra_data={
        "starting_spells": {
            "guaranteed": ["read_magic"],
            "random_count": "1d4",
            "random_level": 1,
        },
    },
)

MAGICIAN_MAGICAL_RESEARCH = ClassAbility(
    ability_id="magician_magical_research",
    name="Magical Research",
    description=(
        "At level 9, a magician may establish a tower and begin magical research, "
        "including creating new spells and magic items. They may also attract "
        "apprentices."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "can_create_spells": True,
        "can_create_items": True,
        "follower_type": "apprentices",
    },
)


# =============================================================================
# MAGICIAN LEVEL PROGRESSION
# =============================================================================

# Magician saving throw progression (worst saves, improve every 5 levels)
MAGICIAN_SAVES_1_5 = SavingThrows(doom=13, ray=14, hold=13, blast=16, spell=15)
MAGICIAN_SAVES_6_10 = SavingThrows(doom=11, ray=12, hold=11, blast=14, spell=12)
MAGICIAN_SAVES_11_15 = SavingThrows(doom=8, ray=9, hold=8, blast=11, spell=8)

# Spell slots by level: {spell_level: number_of_slots}
MAGICIAN_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=MAGICIAN_SAVES_1_5,
        hit_dice="1d4",
        spell_slots={1: 1},
    ),
    LevelProgression(
        level=2,
        experience_required=2500,
        attack_bonus=0,
        saving_throws=MAGICIAN_SAVES_1_5,
        hit_dice="2d4",
        spell_slots={1: 2},
    ),
    LevelProgression(
        level=3,
        experience_required=5000,
        attack_bonus=0,
        saving_throws=MAGICIAN_SAVES_1_5,
        hit_dice="3d4",
        spell_slots={1: 2, 2: 1},
    ),
    LevelProgression(
        level=4,
        experience_required=10000,
        attack_bonus=1,
        saving_throws=MAGICIAN_SAVES_1_5,
        hit_dice="4d4",
        spell_slots={1: 2, 2: 2},
    ),
    LevelProgression(
        level=5,
        experience_required=20000,
        attack_bonus=1,
        saving_throws=MAGICIAN_SAVES_1_5,
        hit_dice="5d4",
        spell_slots={1: 2, 2: 2, 3: 1},
    ),
    LevelProgression(
        level=6,
        experience_required=40000,
        attack_bonus=2,
        saving_throws=MAGICIAN_SAVES_6_10,
        hit_dice="6d4",
        spell_slots={1: 2, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=7,
        experience_required=80000,
        attack_bonus=2,
        saving_throws=MAGICIAN_SAVES_6_10,
        hit_dice="7d4",
        spell_slots={1: 3, 2: 2, 3: 2, 4: 1},
    ),
    LevelProgression(
        level=8,
        experience_required=150000,
        attack_bonus=2,
        saving_throws=MAGICIAN_SAVES_6_10,
        hit_dice="8d4",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 2},
    ),
    LevelProgression(
        level=9,
        experience_required=300000,
        attack_bonus=3,
        saving_throws=MAGICIAN_SAVES_6_10,
        hit_dice="9d4",
        spell_slots={1: 3, 2: 3, 3: 3, 4: 2, 5: 1},
        abilities_gained=["magician_magical_research"],
    ),
    LevelProgression(
        level=10,
        experience_required=450000,
        attack_bonus=3,
        saving_throws=MAGICIAN_SAVES_6_10,
        hit_dice="9d4+1",
        spell_slots={1: 3, 2: 3, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=11,
        experience_required=600000,
        attack_bonus=3,
        saving_throws=MAGICIAN_SAVES_11_15,
        hit_dice="9d4+2",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    ),
    LevelProgression(
        level=12,
        experience_required=750000,
        attack_bonus=4,
        saving_throws=MAGICIAN_SAVES_11_15,
        hit_dice="9d4+3",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 3, 5: 3, 6: 2},
    ),
    LevelProgression(
        level=13,
        experience_required=900000,
        attack_bonus=4,
        saving_throws=MAGICIAN_SAVES_11_15,
        hit_dice="9d4+4",
        spell_slots={1: 4, 2: 4, 3: 4, 4: 3, 5: 3, 6: 2},
    ),
    LevelProgression(
        level=14,
        experience_required=1050000,
        attack_bonus=4,
        saving_throws=MAGICIAN_SAVES_11_15,
        hit_dice="9d4+5",
        spell_slots={1: 4, 2: 4, 3: 4, 4: 4, 5: 3, 6: 3},
    ),
    LevelProgression(
        level=15,
        experience_required=1200000,
        attack_bonus=5,
        saving_throws=MAGICIAN_SAVES_11_15,
        hit_dice="9d4+6",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 4, 5: 4, 6: 3},
    ),
]


# =============================================================================
# COMPLETE MAGICIAN DEFINITION
# =============================================================================

MAGICIAN_DEFINITION = ClassDefinition(
    class_id="magician",
    name="Magician",
    description=(
        "Magicians are scholars of the arcane arts, wielding powerful spells "
        "through years of study and memorization. While physically frail, their "
        "magical abilities can turn the tide of any encounter. They must "
        "carefully manage their limited spell slots and choose which spells to "
        "memorize each day from their precious spellbooks."
    ),

    hit_die=HitDie.D4,
    prime_ability="INT",

    magic_type=MagicType.ARCANE,

    armor_proficiencies=[
        ArmorProficiency.NONE,  # Cannot wear armor
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,  # Daggers, staves, darts
    ],

    level_progression=MAGICIAN_LEVEL_PROGRESSION,

    abilities=[
        MAGICIAN_ARCANE_MAGIC,
        MAGICIAN_SPELLBOOK,
        MAGICIAN_MAGICAL_RESEARCH,
    ],

    # No kindred restrictions
    restricted_kindreds=[],

    starting_equipment=[
        "spellbook",
        "dagger",
        "staff",
        "adventuring_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=70,
)
