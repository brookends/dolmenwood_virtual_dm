"""
Magician class definition for Dolmenwood.

Connoisseurs of secret arcane lore who wield powerful magic.
Magicians—sometimes called wizards or sorcerers—hone innate sparks of
magical sensitivity through years of arduous study. Arcane generalists,
accumulating secret lore from any source they can get their hands on.

Source: Dolmenwood Player Book, pages 72-73
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
        "Magicians can cast arcane spells. The Magician Spells Per Day table "
        "shows the number of spells a magician may memorise, determined by "
        "the character's Level. Magicians can also use magic items exclusive "
        "to arcane spell-casters (for example, magic wands or scrolls of "
        "arcane spells)."
    ),
    is_passive=True,
    extra_data={
        "spell_type": "arcane",
        "max_spell_rank": 6,
        "requires_spellbook": True,
        "requires_memorization": True,
        "can_use_arcane_items": True,
        "item_types": ["wands", "arcane_scrolls", "arcane_magic_items"],
        "reference": "See Arcane Magic, p78 for full details",
    },
)

MAGICIAN_SKILLS = ClassAbility(
    ability_id="magician_skills",
    name="Magician Skills",
    description=("Magicians have one additional, specialised skill: Detect Magic."),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skills": ["detect_magic"],
        # Skill Targets by level (roll d6 >= target to succeed)
        "skill_targets": {
            1: {"detect_magic": 6},
            2: {"detect_magic": 6},
            3: {"detect_magic": 5},
            4: {"detect_magic": 5},
            5: {"detect_magic": 5},
            6: {"detect_magic": 4},
            7: {"detect_magic": 4},
            8: {"detect_magic": 4},
            9: {"detect_magic": 3},
            10: {"detect_magic": 3},
            11: {"detect_magic": 3},
            12: {"detect_magic": 3},
            13: {"detect_magic": 3},
            14: {"detect_magic": 3},
            15: {"detect_magic": 3},
        },
        "skill_details": {
            "detect_magic": {
                "description": (
                    "A magician can attempt to detect the subtle resonances "
                    "woven into an enchanted object, place, or creature. If the "
                    "attempt succeeds, the magician knows if the object, place, "
                    "or creature in question is magical—i.e. enchanted, affected "
                    "by a spell, or possessed of innate magic of some kind."
                ),
                "requires": "touch object, place, or creature; concentrate without distraction",
                "time": "1 Turn per attempt",
                "retry": "May retry failed attempts as often as desired (1 Turn each)",
                "referee_rolls": (
                    "The Referee rolls all Detect Magic Checks, so players do not "
                    "know if the roll failed or if there is no magic present."
                ),
                "downtime": (
                    "Given an hour of solitude in a safe location, a magician "
                    "automatically detects magic on an object, place, or creature."
                ),
            },
        },
    },
)

MAGICIAN_STARTING_SPELLBOOKS = ClassAbility(
    ability_id="magician_starting_spellbooks",
    name="Starting Spell Books",
    description=(
        "A Level 1 magician possesses a single spell book and has learned to "
        "cast the spells it describes. A magician's first spell book may be an "
        "item inherited from a mysterious ancestor, stolen from a cruel master, "
        "or meticulously copied under the tutelage of a mentor."
    ),
    is_passive=True,
    extra_data={
        "starting_books": {
            1: {
                "name": "Charms of the Fey Court",
                "spells": ["fairy_servant", "ingratiate", "ventriloquism"],
            },
            2: {
                "name": "Hogbrand's Incandescence",
                "spells": ["firelight", "ignite_extinguish", "shield_of_force"],
            },
            3: {
                "name": "Lord Oberon's Seals",
                "spells": ["decipher", "glyph_of_sealing", "vapours_of_dream"],
            },
            4: {
                "name": "Oliphan's Folio",
                "spells": ["crystal_resonance", "ioun_shard", "shield_of_force"],
            },
            5: {
                "name": "Smythe's Illuminations",
                "spells": ["decipher", "ignite_extinguish", "ioun_shard"],
            },
            6: {
                "name": "The Treatise on Force and Dissolution",
                "spells": ["crystal_resonance", "floating_disc", "vapours_of_dream"],
            },
        },
        "selection": "Roll 1d6 or choose",
        "all_spells_rank": 1,
    },
)


# =============================================================================
# MAGICIAN LEVEL PROGRESSION
# =============================================================================

# Magician saving throws (improve every 3 levels)
# Note: Doom and Ray are equal, Hold is 1 lower than Doom
MAGICIAN_SAVES_1_3 = SavingThrows(doom=14, ray=14, hold=13, blast=16, spell=14)
MAGICIAN_SAVES_4_6 = SavingThrows(doom=13, ray=13, hold=12, blast=15, spell=13)
MAGICIAN_SAVES_7_9 = SavingThrows(doom=12, ray=12, hold=11, blast=14, spell=12)
MAGICIAN_SAVES_10_12 = SavingThrows(doom=11, ray=11, hold=10, blast=13, spell=11)
MAGICIAN_SAVES_13_15 = SavingThrows(doom=10, ray=10, hold=9, blast=12, spell=10)

MAGICIAN_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=MAGICIAN_SAVES_1_3,
        hit_dice="1d4",
        spell_slots={1: 1},
    ),
    LevelProgression(
        level=2,
        experience_required=2500,
        attack_bonus=0,
        saving_throws=MAGICIAN_SAVES_1_3,
        hit_dice="2d4",
        spell_slots={1: 2},
    ),
    LevelProgression(
        level=3,
        experience_required=5000,
        attack_bonus=0,
        saving_throws=MAGICIAN_SAVES_1_3,
        hit_dice="3d4",
        spell_slots={1: 2, 2: 1},
    ),
    LevelProgression(
        level=4,
        experience_required=10000,
        attack_bonus=1,
        saving_throws=MAGICIAN_SAVES_4_6,
        hit_dice="4d4",
        spell_slots={1: 2, 2: 2},
    ),
    LevelProgression(
        level=5,
        experience_required=20000,
        attack_bonus=1,
        saving_throws=MAGICIAN_SAVES_4_6,
        hit_dice="5d4",
        spell_slots={1: 2, 2: 2, 3: 1},
    ),
    LevelProgression(
        level=6,
        experience_required=40000,
        attack_bonus=1,
        saving_throws=MAGICIAN_SAVES_4_6,
        hit_dice="6d4",
        spell_slots={1: 3, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=7,
        experience_required=80000,
        attack_bonus=2,
        saving_throws=MAGICIAN_SAVES_7_9,
        hit_dice="7d4",
        spell_slots={1: 3, 2: 2, 3: 2, 4: 1},
    ),
    LevelProgression(
        level=8,
        experience_required=160000,
        attack_bonus=2,
        saving_throws=MAGICIAN_SAVES_7_9,
        hit_dice="8d4",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 2},
    ),
    LevelProgression(
        level=9,
        experience_required=320000,
        attack_bonus=2,
        saving_throws=MAGICIAN_SAVES_7_9,
        hit_dice="9d4",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 2, 5: 1},
    ),
    LevelProgression(
        level=10,
        experience_required=470000,
        attack_bonus=3,
        saving_throws=MAGICIAN_SAVES_10_12,
        hit_dice="10d4",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 2, 5: 2},
    ),
    LevelProgression(
        level=11,
        experience_required=620000,
        attack_bonus=3,
        saving_throws=MAGICIAN_SAVES_10_12,
        hit_dice="10d4+1",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 2, 5: 2, 6: 1},
    ),
    LevelProgression(
        level=12,
        experience_required=770000,
        attack_bonus=3,
        saving_throws=MAGICIAN_SAVES_10_12,
        hit_dice="10d4+2",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 3, 5: 2, 6: 2},
    ),
    LevelProgression(
        level=13,
        experience_required=920000,
        attack_bonus=4,
        saving_throws=MAGICIAN_SAVES_13_15,
        hit_dice="10d4+3",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 3, 5: 3, 6: 2},
    ),
    LevelProgression(
        level=14,
        experience_required=1070000,
        attack_bonus=4,
        saving_throws=MAGICIAN_SAVES_13_15,
        hit_dice="10d4+4",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 3, 5: 3, 6: 2},
    ),
    LevelProgression(
        level=15,
        experience_required=1220000,
        attack_bonus=4,
        saving_throws=MAGICIAN_SAVES_13_15,
        hit_dice="10d4+5",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 3, 5: 3, 6: 3},
    ),
]


# =============================================================================
# COMPLETE MAGICIAN DEFINITION
# =============================================================================

MAGICIAN_DEFINITION = ClassDefinition(
    class_id="magician",
    name="Magician",
    description=(
        "Magicians—sometimes called wizards or sorcerers—hone innate sparks "
        "of magical sensitivity through years of arduous study. Magicians are "
        "arcane generalists, accumulating secret lore from any source they can "
        "get their hands on—magic of illusion, crystalmancy, elementalism, "
        "conjuration, and sometimes even stolen Drune spells. Their accumulation "
        "of knowledge allows magicians to cast spells and to wield powerful "
        "magic items. Magicians begin play able to cast just a single spell "
        "each day, but gain access to extremely potent magic as they advance."
    ),
    hit_die=HitDie.D4,
    prime_ability="INT",
    magic_type=MagicType.ARCANE,
    armor_proficiencies=[
        ArmorProficiency.NONE,
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,  # Dagger, holy water, oil, staff, torch
    ],
    level_progression=MAGICIAN_LEVEL_PROGRESSION,
    abilities=[
        MAGICIAN_ARCANE_MAGIC,
        MAGICIAN_SKILLS,
        MAGICIAN_STARTING_SPELLBOOKS,
    ],
    # No kindred restrictions
    restricted_kindreds=[],
    starting_equipment=[
        # Weapon (roll 1d6): 1-3. Dagger. 4-6. Staff.
        "weapon_roll_1d6",
        # Class items
        "ritual_robes",
        "spell_book",  # One of 6 starting spell books
    ],
    extra_data={
        "combat_aptitude": "Non-martial",
        "allowed_weapons": ["dagger", "holy_water", "oil", "staff", "torch"],
        "also_known_as": ["wizard", "sorcerer"],
        "magic_sources": [
            "illusion",
            "crystalmancy",
            "elementalism",
            "conjuration",
            "stolen Drune spells",
        ],
    },
    source_book="Dolmenwood Player Book",
    source_page=72,
)
