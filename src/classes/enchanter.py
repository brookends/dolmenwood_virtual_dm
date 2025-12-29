"""
Enchanter class definition for Dolmenwood.

Masters of fairy magic who wield glamours and runes. The only class
capable of casting runes - powerful fairy magic granted by fairy nobles.

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
# ENCHANTER ABILITIES
# =============================================================================

ENCHANTER_GLAMOUR_MAGIC = ClassAbility(
    ability_id="enchanter_glamour_magic",
    name="Glamour Magic",
    description=(
        "Enchanters can cast fairy glamours - minor magical talents of fairy "
        "origin. Unlike kindred glamours which are innate, enchanters learn "
        "glamours through study and practice. They can know multiple glamours "
        "and cast them at will."
    ),
    is_passive=True,
    extra_data={
        "spell_type": "glamour",
        "spell_source": "data/content/spells/glamours.json",
        "glamours_known_by_level": {
            1: 2,
            3: 3,
            5: 4,
            7: 5,
            9: 6,
            11: 7,
            13: 8,
            15: 9,
        },
    },
)

ENCHANTER_RUNE_MAGIC = ClassAbility(
    ability_id="enchanter_rune_magic",
    name="Rune Magic",
    description=(
        "Enchanters are the ONLY class capable of casting runes - powerful "
        "fairy magic granted by fairy nobles. Runes are one-use magical effects "
        "inscribed on objects. Enchanters gain access to lesser runes at level 1, "
        "greater runes at level 5, and mighty runes at level 9."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "spell_type": "rune",
        "spell_sources": {
            "lesser": "data/content/spells/lesser_runes.json",
            "greater": "data/content/spells/greater_runes.json",
            "mighty": "data/content/spells/mighty_runes.json",
        },
        "rune_access_by_level": {
            1: ["lesser"],
            5: ["lesser", "greater"],
            9: ["lesser", "greater", "mighty"],
        },
        "runes_known_by_level": {
            1: 1,
            3: 2,
            5: 3,
            7: 4,
            9: 5,
            11: 6,
            13: 7,
            15: 8,
        },
    },
)

ENCHANTER_FAIRY_TONGUE = ClassAbility(
    ability_id="enchanter_fairy_tongue",
    name="Fairy Tongue",
    description=(
        "Enchanters learn the ancient language of Fairy (Sylvan). They can "
        "communicate with fairy creatures and read fairy inscriptions."
    ),
    is_passive=True,
    extra_data={
        "languages_gained": ["Sylvan"],
    },
)

ENCHANTER_FAIRY_AFFINITY = ClassAbility(
    ability_id="enchanter_fairy_affinity",
    name="Fairy Affinity",
    description=(
        "Enchanters have a natural affinity with fairy creatures. They gain +2 "
        "to reaction rolls with fairies and can sense fairy magic within 30 feet."
    ),
    is_passive=True,
    extra_data={
        "fairy_reaction_bonus": 2,
        "sense_magic_range_feet": 30,
        "sense_magic_types": ["fairy_glamour", "rune"],
    },
)

ENCHANTER_FAIRY_PACT = ClassAbility(
    ability_id="enchanter_fairy_pact",
    name="Fairy Pact",
    description=(
        "At level 9, an enchanter may forge a pact with a fairy noble, gaining "
        "access to more powerful runes and the ability to call upon fairy aid. "
        "The terms of such pacts are always... interesting."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "requires": "fairy_noble_pact",
        "benefits": ["mighty_runes", "fairy_summons"],
    },
)


# =============================================================================
# ENCHANTER LEVEL PROGRESSION
# =============================================================================

# Enchanter saves (similar to magician but with better spell saves)
ENCHANTER_SAVES_1_5 = SavingThrows(doom=13, ray=14, hold=13, blast=16, spell=13)
ENCHANTER_SAVES_6_10 = SavingThrows(doom=11, ray=12, hold=11, blast=14, spell=10)
ENCHANTER_SAVES_11_15 = SavingThrows(doom=8, ray=9, hold=8, blast=11, spell=6)

ENCHANTER_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=ENCHANTER_SAVES_1_5,
        hit_dice="1d4",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=2,
        experience_required=2500,
        attack_bonus=0,
        saving_throws=ENCHANTER_SAVES_1_5,
        hit_dice="2d4",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=3,
        experience_required=5000,
        attack_bonus=0,
        saving_throws=ENCHANTER_SAVES_1_5,
        hit_dice="3d4",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=4,
        experience_required=10000,
        attack_bonus=1,
        saving_throws=ENCHANTER_SAVES_1_5,
        hit_dice="4d4",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=5,
        experience_required=20000,
        attack_bonus=1,
        saving_throws=ENCHANTER_SAVES_1_5,
        hit_dice="5d4",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=6,
        experience_required=40000,
        attack_bonus=2,
        saving_throws=ENCHANTER_SAVES_6_10,
        hit_dice="6d4",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=7,
        experience_required=80000,
        attack_bonus=2,
        saving_throws=ENCHANTER_SAVES_6_10,
        hit_dice="7d4",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=8,
        experience_required=150000,
        attack_bonus=2,
        saving_throws=ENCHANTER_SAVES_6_10,
        hit_dice="8d4",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=9,
        experience_required=300000,
        attack_bonus=3,
        saving_throws=ENCHANTER_SAVES_6_10,
        hit_dice="9d4",
        rune_access=["lesser", "greater", "mighty"],
        abilities_gained=["enchanter_fairy_pact"],
    ),
    LevelProgression(
        level=10,
        experience_required=450000,
        attack_bonus=3,
        saving_throws=ENCHANTER_SAVES_6_10,
        hit_dice="9d4+1",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=11,
        experience_required=600000,
        attack_bonus=3,
        saving_throws=ENCHANTER_SAVES_11_15,
        hit_dice="9d4+2",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=12,
        experience_required=750000,
        attack_bonus=4,
        saving_throws=ENCHANTER_SAVES_11_15,
        hit_dice="9d4+3",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=13,
        experience_required=900000,
        attack_bonus=4,
        saving_throws=ENCHANTER_SAVES_11_15,
        hit_dice="9d4+4",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=14,
        experience_required=1050000,
        attack_bonus=4,
        saving_throws=ENCHANTER_SAVES_11_15,
        hit_dice="9d4+5",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=15,
        experience_required=1200000,
        attack_bonus=5,
        saving_throws=ENCHANTER_SAVES_11_15,
        hit_dice="9d4+6",
        rune_access=["lesser", "greater", "mighty"],
    ),
]


# =============================================================================
# COMPLETE ENCHANTER DEFINITION
# =============================================================================

ENCHANTER_DEFINITION = ClassDefinition(
    class_id="enchanter",
    name="Enchanter",
    description=(
        "Enchanters are masters of fairy magic, wielding glamours and the "
        "powerful runes granted by fairy nobles. They are the ONLY class capable "
        "of casting runes - one-use magical effects of tremendous power. While "
        "physically frail like magicians, their fairy magic grants them unique "
        "abilities and a special connection to the realm of Fairy."
    ),

    hit_die=HitDie.D4,
    prime_ability="CHA",

    magic_type=MagicType.GLAMOUR,  # Covers both glamours and runes

    armor_proficiencies=[
        ArmorProficiency.NONE,
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,
    ],

    level_progression=ENCHANTER_LEVEL_PROGRESSION,

    abilities=[
        ENCHANTER_GLAMOUR_MAGIC,
        ENCHANTER_RUNE_MAGIC,
        ENCHANTER_FAIRY_TONGUE,
        ENCHANTER_FAIRY_AFFINITY,
        ENCHANTER_FAIRY_PACT,
    ],

    # Rare among humans, common among fairy kindreds
    restricted_kindreds=["mossling", "breggle"],

    starting_equipment=[
        "dagger",
        "staff",
        "fairy_token",
        "adventuring_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=60,
)
