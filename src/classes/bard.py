"""
Bard class definition for Dolmenwood.

Wandering performers and lorekeepers who use music and storytelling
to create magical effects without casting true spells.

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
# BARD ABILITIES
# =============================================================================

BARD_BARDIC_MUSIC = ClassAbility(
    ability_id="bard_bardic_music",
    name="Bardic Music",
    description=(
        "Bards can perform music that creates magical effects. These are not "
        "spells but special abilities powered by performance. Effects include "
        "Inspire Courage, Fascinate, Countersong, and more as the bard levels."
    ),
    is_passive=False,
    extra_data={
        "requires_instrument": True,
        "requires_performance": True,
        "performances": {
            "inspire_courage": {
                "min_level": 1,
                "description": "Allies gain +1 to attack and saves vs fear",
                "duration": "while performing",
            },
            "fascinate": {
                "min_level": 1,
                "description": "Creatures within 30' are fascinated if they fail a save",
                "duration": "while performing",
            },
            "countersong": {
                "min_level": 3,
                "description": "Counter magical sonic or language-dependent effects",
                "duration": "while performing",
            },
            "inspire_competence": {
                "min_level": 5,
                "description": "One ally gains +2 to skill checks",
                "duration": "while performing",
            },
            "suggestion": {
                "min_level": 7,
                "description": "Implant a suggestion in a fascinated creature",
                "uses_per_day": 1,
            },
            "inspire_heroics": {
                "min_level": 9,
                "description": "Allies gain +2 to attack and +2 AC",
                "duration": "while performing",
            },
        },
    },
)

BARD_LORE = ClassAbility(
    ability_id="bard_lore",
    name="Bardic Lore",
    description=(
        "Bards accumulate knowledge of legends, stories, and obscure facts. "
        "They have a chance to know relevant information about notable people, "
        "places, or items. The chance is 2-in-6 at level 1, improving with level."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "lore_chance_by_level": {
            1: 2,   # 2-in-6
            4: 3,   # 3-in-6
            7: 4,   # 4-in-6
            10: 5,  # 5-in-6
        },
    },
)

BARD_JACK_OF_ALL_TRADES = ClassAbility(
    ability_id="bard_jack_of_all_trades",
    name="Jack of All Trades",
    description=(
        "Bards pick up a little of everything in their travels. They can attempt "
        "thief skills (at half the normal chance) and can use any magic item "
        "that is not class-restricted."
    ),
    is_passive=True,
    extra_data={
        "thief_skill_penalty": 0.5,
        "can_use_magic_items": True,
    },
)

BARD_INFLUENCE = ClassAbility(
    ability_id="bard_influence",
    name="Influence",
    description=(
        "Bards are skilled at swaying opinions and gathering information. "
        "They gain +2 to reaction rolls when speaking and can gather rumors "
        "in half the normal time."
    ),
    is_passive=True,
    extra_data={
        "reaction_bonus": 2,
        "rumor_time_multiplier": 0.5,
    },
)

BARD_COLLEGE = ClassAbility(
    ability_id="bard_college",
    name="Bardic College",
    description=(
        "At level 9, a bard may establish a bardic college or performance hall "
        "and attract a retinue of apprentice performers and admirers."
    ),
    min_level=9,
    is_passive=True,
    extra_data={
        "follower_types": ["apprentice_bards", "admirers"],
    },
)


# =============================================================================
# BARD LEVEL PROGRESSION
# =============================================================================

# Bard saves (similar to thief)
BARD_SAVES_1_4 = SavingThrows(doom=13, ray=14, hold=13, blast=16, spell=15)
BARD_SAVES_5_8 = SavingThrows(doom=11, ray=12, hold=11, blast=14, spell=13)
BARD_SAVES_9_12 = SavingThrows(doom=9, ray=10, hold=9, blast=12, spell=11)
BARD_SAVES_13_15 = SavingThrows(doom=7, ray=8, hold=7, blast=10, spell=9)

BARD_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=BARD_SAVES_1_4,
        hit_dice="1d6",
    ),
    LevelProgression(
        level=2,
        experience_required=1500,
        attack_bonus=0,
        saving_throws=BARD_SAVES_1_4,
        hit_dice="2d6",
    ),
    LevelProgression(
        level=3,
        experience_required=3000,
        attack_bonus=1,
        saving_throws=BARD_SAVES_1_4,
        hit_dice="3d6",
    ),
    LevelProgression(
        level=4,
        experience_required=6000,
        attack_bonus=1,
        saving_throws=BARD_SAVES_1_4,
        hit_dice="4d6",
    ),
    LevelProgression(
        level=5,
        experience_required=12000,
        attack_bonus=2,
        saving_throws=BARD_SAVES_5_8,
        hit_dice="5d6",
    ),
    LevelProgression(
        level=6,
        experience_required=25000,
        attack_bonus=2,
        saving_throws=BARD_SAVES_5_8,
        hit_dice="6d6",
    ),
    LevelProgression(
        level=7,
        experience_required=50000,
        attack_bonus=3,
        saving_throws=BARD_SAVES_5_8,
        hit_dice="7d6",
    ),
    LevelProgression(
        level=8,
        experience_required=100000,
        attack_bonus=3,
        saving_throws=BARD_SAVES_5_8,
        hit_dice="8d6",
    ),
    LevelProgression(
        level=9,
        experience_required=200000,
        attack_bonus=4,
        saving_throws=BARD_SAVES_9_12,
        hit_dice="9d6",
        abilities_gained=["bard_college"],
    ),
    LevelProgression(
        level=10,
        experience_required=300000,
        attack_bonus=4,
        saving_throws=BARD_SAVES_9_12,
        hit_dice="9d6+1",
    ),
    LevelProgression(
        level=11,
        experience_required=400000,
        attack_bonus=5,
        saving_throws=BARD_SAVES_9_12,
        hit_dice="9d6+2",
    ),
    LevelProgression(
        level=12,
        experience_required=500000,
        attack_bonus=5,
        saving_throws=BARD_SAVES_9_12,
        hit_dice="9d6+3",
    ),
    LevelProgression(
        level=13,
        experience_required=600000,
        attack_bonus=6,
        saving_throws=BARD_SAVES_13_15,
        hit_dice="9d6+4",
    ),
    LevelProgression(
        level=14,
        experience_required=700000,
        attack_bonus=6,
        saving_throws=BARD_SAVES_13_15,
        hit_dice="9d6+5",
    ),
    LevelProgression(
        level=15,
        experience_required=800000,
        attack_bonus=7,
        saving_throws=BARD_SAVES_13_15,
        hit_dice="9d6+6",
    ),
]


# =============================================================================
# COMPLETE BARD DEFINITION
# =============================================================================

BARD_DEFINITION = ClassDefinition(
    class_id="bard",
    name="Bard",
    description=(
        "Bards are wandering performers and lorekeepers who travel the land "
        "collecting stories, songs, and secrets. Their music creates magical "
        "effects that can inspire allies, fascinate enemies, or counter hostile "
        "magic. While not true spellcasters, their bardic music grants them "
        "unique abilities that blur the line between performance and magic."
    ),

    hit_die=HitDie.D6,
    prime_ability="CHA",

    magic_type=MagicType.NONE,  # Bardic music is not spellcasting

    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        ArmorProficiency.MEDIUM,
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,
        WeaponProficiency.RANGED,
    ],

    level_progression=BARD_LEVEL_PROGRESSION,

    abilities=[
        BARD_BARDIC_MUSIC,
        BARD_LORE,
        BARD_JACK_OF_ALL_TRADES,
        BARD_INFLUENCE,
        BARD_COLLEGE,
    ],

    # No kindred restrictions
    restricted_kindreds=[],

    starting_equipment=[
        "musical_instrument",
        "rapier",
        "leather_armor",
        "traveling_gear",
    ],

    source_book="Dolmenwood Player Book",
    source_page=54,
)
