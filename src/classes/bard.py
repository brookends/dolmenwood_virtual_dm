"""
Bard class definition for Dolmenwood.

Musicians and poets drawn to a life of wandering and adventure.
Their music and songs are woven with magic, which can both
protect and beguile.

Source: Dolmenwood Player Book, pages 58-59
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

BARD_SKILLS = ClassAbility(
    ability_id="bard_skills",
    name="Bard Skills",
    description=(
        "As they advance in Level, bards improve their chance of success with "
        "the Listen skill. They also have three additional specialized skills: "
        "Decipher Document, Legerdemain, and Monster Lore."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skills": ["listen", "decipher_document", "legerdemain", "monster_lore"],
        # Skill Targets by level (lower is better, roll d6 >= target to succeed)
        "skill_targets": {
            1:  {"listen": 6, "decipher_document": 6, "legerdemain": 5, "monster_lore": 5},
            2:  {"listen": 5, "decipher_document": 6, "legerdemain": 5, "monster_lore": 5},
            3:  {"listen": 5, "decipher_document": 6, "legerdemain": 5, "monster_lore": 4},
            4:  {"listen": 5, "decipher_document": 5, "legerdemain": 5, "monster_lore": 4},
            5:  {"listen": 5, "decipher_document": 5, "legerdemain": 4, "monster_lore": 4},
            6:  {"listen": 4, "decipher_document": 5, "legerdemain": 4, "monster_lore": 4},
            7:  {"listen": 4, "decipher_document": 5, "legerdemain": 4, "monster_lore": 3},
            8:  {"listen": 4, "decipher_document": 4, "legerdemain": 4, "monster_lore": 3},
            9:  {"listen": 4, "decipher_document": 4, "legerdemain": 3, "monster_lore": 3},
            10: {"listen": 3, "decipher_document": 4, "legerdemain": 3, "monster_lore": 3},
            11: {"listen": 3, "decipher_document": 3, "legerdemain": 3, "monster_lore": 3},
            12: {"listen": 3, "decipher_document": 3, "legerdemain": 3, "monster_lore": 2},
            13: {"listen": 2, "decipher_document": 3, "legerdemain": 3, "monster_lore": 2},
            14: {"listen": 2, "decipher_document": 3, "legerdemain": 2, "monster_lore": 2},
            15: {"listen": 2, "decipher_document": 2, "legerdemain": 2, "monster_lore": 2},
        },
        "skill_details": {
            "decipher_document": {
                "description": (
                    "Understand the gist of a non-magical text in a language they "
                    "do not speak, unravel a cypher, or identify cryptically labelled "
                    "landmarks on a map."
                ),
                "retry": "Only after gaining a Level",
            },
            "legerdemain": {
                "description": (
                    "Perform a trick of sleight of hand, such as palming a small object, "
                    "slipping a poison into a drink, or pilfering a small item."
                ),
                "difficulty": "-1 penalty per 3 Levels of the victim or observer",
                "natural_1": "Must Save Versus Doom to avoid being noticed",
            },
            "monster_lore": {
                "description": (
                    "Identify monsters and their basic powers and vulnerabilities, "
                    "based on their appearances in myth and folklore."
                ),
                "retry": "Only after gaining a Level",
            },
        },
    },
)

BARD_COUNTER_CHARM = ClassAbility(
    ability_id="bard_counter_charm",
    name="Counter Charm",
    description=(
        "While the bard plays music and sings, allies within 30' are immune to "
        "magical effects based on music or song and gain a +2 bonus to Saving "
        "Throws against fairy magic."
    ),
    is_passive=False,
    extra_data={
        "range_feet": 30,
        "uses_per_turn": 1,
        "effects": {
            "immunity": "magical effects based on music or song",
            "save_bonus": {"fairy_magic": 2},
        },
        "restrictions": {
            "movement": "half Speed",
            "cannot_attack": True,
            "cannot_perform_other_actions": True,
        },
        "duration": "as long as the bard keeps playing",
        "disruption": "If the bard is harmed or fails a Saving Throw, the counter charm ends",
    },
)

BARD_ENCHANTMENT = ClassAbility(
    ability_id="bard_enchantment",
    name="Enchantment",
    description=(
        "By playing music and singing, the bard can fascinate subjects in a 30' "
        "radius. Subjects whose Levels total up to twice the bard's Level can be "
        "affected. If the performance lasts at least 1 Turn and ends without "
        "interruption, fascinated subjects must save again or be charmed."
    ),
    is_passive=False,
    scales_with_level=True,
    extra_data={
        "range_feet": 30,
        "uses_per_day_formula": "1 per bard Level",
        "cannot_use_in_combat": True,
        "max_levels_affected": "2 x bard Level",
        "save_type": "spell",
        # Types of subjects affected by level
        "subject_types_by_level": {
            1: ["mortals"],
            4: ["mortals", "animals", "demi-fey"],
            7: ["mortals", "animals", "demi-fey", "fairies", "monstrosities"],
        },
        "fascinated_effects": {
            "attention": "fully bent on the bard's performance",
            "follow": "if the bard walks while playing, fascinated subjects follow",
            "interruption": "loud noise or violence ends fascination immediately",
        },
        "charm_effects": {
            "trigger": "performance lasts at least 1 Turn without interruption",
            "save": "Save Versus Spell with +2 bonus",
            "friendship": "charmed subjects regard the bard as a trusted friend",
            "commands": "charmed subjects obey commands if they share a language",
            "resistance": "may resist commands contradicting habits or Alignment",
            "refusal": "suicidal or clearly harmful commands always refused",
            "duration": "1 Turn per Level of the bard",
        },
        "restrictions": {
            "movement": "half Speed",
            "cannot_attack": True,
            "cannot_perform_other_actions": True,
        },
    },
)


# =============================================================================
# BARD LEVEL PROGRESSION
# =============================================================================

# Bard saving throws (improve every 2 levels)
BARD_SAVES_1_2 = SavingThrows(doom=13, ray=14, hold=13, blast=15, spell=15)
BARD_SAVES_3_4 = SavingThrows(doom=12, ray=13, hold=12, blast=14, spell=14)
BARD_SAVES_5_6 = SavingThrows(doom=11, ray=12, hold=11, blast=13, spell=13)
BARD_SAVES_7_8 = SavingThrows(doom=10, ray=11, hold=10, blast=12, spell=12)
BARD_SAVES_9_10 = SavingThrows(doom=9, ray=10, hold=9, blast=11, spell=11)
BARD_SAVES_11_12 = SavingThrows(doom=8, ray=9, hold=8, blast=10, spell=10)
BARD_SAVES_13_14 = SavingThrows(doom=7, ray=8, hold=7, blast=9, spell=9)
BARD_SAVES_15 = SavingThrows(doom=6, ray=7, hold=6, blast=8, spell=8)

BARD_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=BARD_SAVES_1_2,
        hit_dice="1d6",
    ),
    LevelProgression(
        level=2,
        experience_required=1750,
        attack_bonus=0,
        saving_throws=BARD_SAVES_1_2,
        hit_dice="2d6",
    ),
    LevelProgression(
        level=3,
        experience_required=3500,
        attack_bonus=1,
        saving_throws=BARD_SAVES_3_4,
        hit_dice="3d6",
    ),
    LevelProgression(
        level=4,
        experience_required=7000,
        attack_bonus=1,
        saving_throws=BARD_SAVES_3_4,
        hit_dice="4d6",
    ),
    LevelProgression(
        level=5,
        experience_required=14000,
        attack_bonus=2,
        saving_throws=BARD_SAVES_5_6,
        hit_dice="5d6",
    ),
    LevelProgression(
        level=6,
        experience_required=28000,
        attack_bonus=2,
        saving_throws=BARD_SAVES_5_6,
        hit_dice="6d6",
    ),
    LevelProgression(
        level=7,
        experience_required=56000,
        attack_bonus=3,
        saving_throws=BARD_SAVES_7_8,
        hit_dice="7d6",
    ),
    LevelProgression(
        level=8,
        experience_required=112000,
        attack_bonus=3,
        saving_throws=BARD_SAVES_7_8,
        hit_dice="8d6",
    ),
    LevelProgression(
        level=9,
        experience_required=220000,
        attack_bonus=4,
        saving_throws=BARD_SAVES_9_10,
        hit_dice="9d6",
    ),
    LevelProgression(
        level=10,
        experience_required=340000,
        attack_bonus=4,
        saving_throws=BARD_SAVES_9_10,
        hit_dice="10d6",
    ),
    LevelProgression(
        level=11,
        experience_required=460000,
        attack_bonus=5,
        saving_throws=BARD_SAVES_11_12,
        hit_dice="10d6+1",
    ),
    LevelProgression(
        level=12,
        experience_required=580000,
        attack_bonus=5,
        saving_throws=BARD_SAVES_11_12,
        hit_dice="10d6+2",
    ),
    LevelProgression(
        level=13,
        experience_required=700000,
        attack_bonus=6,
        saving_throws=BARD_SAVES_13_14,
        hit_dice="10d6+3",
    ),
    LevelProgression(
        level=14,
        experience_required=820000,
        attack_bonus=6,
        saving_throws=BARD_SAVES_13_14,
        hit_dice="10d6+4",
    ),
    LevelProgression(
        level=15,
        experience_required=940000,
        attack_bonus=7,
        saving_throws=BARD_SAVES_15,
        hit_dice="10d6+5",
    ),
]


# =============================================================================
# COMPLETE BARD DEFINITION
# =============================================================================

BARD_DEFINITION = ClassDefinition(
    class_id="bard",
    name="Bard",
    description=(
        "Musicians and poets drawn to a life of wandering and adventure. "
        "Worldly and well-travelled, bards are storehouses of folklore and hearsay. "
        "Their music and songs are woven with magic, which can both protect and beguile."
    ),

    hit_die=HitDie.D6,
    prime_ability="CHA,DEX",  # Dual prime abilities

    magic_type=MagicType.NONE,  # Bardic music is magical but not spellcasting

    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        ArmorProficiency.MEDIUM,
        # Note: No shields
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,   # Small weapons
        WeaponProficiency.MARTIAL,  # Medium weapons
    ],

    level_progression=BARD_LEVEL_PROGRESSION,

    abilities=[
        BARD_SKILLS,
        BARD_COUNTER_CHARM,
        BARD_ENCHANTMENT,
    ],

    # No kindred restrictions
    restricted_kindreds=[],

    starting_equipment=[
        # Armour (roll 1d6): 1-2 None, 3-4 Leather, 5-6 Chainmail
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): Club, 3 daggers, Longsword, Sling+20, Shortbow+20, Shortsword
        "weapon_roll_1d6_twice",
        # Class items
        "musical_instrument_stringed_or_wind",
    ],

    source_book="Dolmenwood Player Book",
    source_page=58,
)
