"""
Enchanter class definition for Dolmenwood.

Wanderers who wield the magic of Fairy, currying favour with fairy nobles.
Individuals whose contact with Fairy has imbued them with innate magic
known as glamours. Enchanters are also blessed with the use of the fairy
runes, guarded by the lords of Fairy.

Source: Dolmenwood Player Book, pages 62-63
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

ENCHANTER_SKILLS = ClassAbility(
    ability_id="enchanter_skills",
    name="Enchanter Skills",
    description=("Enchanters have one additional, specialised skill: Detect Magic."),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skills": ["detect_magic"],
        # Skill Targets by level (roll d6 >= target to succeed)
        "skill_targets": {
            1: {"detect_magic": 5},
            2: {"detect_magic": 5},
            3: {"detect_magic": 5},
            4: {"detect_magic": 5},
            5: {"detect_magic": 4},
            6: {"detect_magic": 4},
            7: {"detect_magic": 3},
            8: {"detect_magic": 3},
            9: {"detect_magic": 2},
            10: {"detect_magic": 2},
            11: {"detect_magic": 2},
            12: {"detect_magic": 2},
            13: {"detect_magic": 2},
            14: {"detect_magic": 2},
            15: {"detect_magic": 2},
        },
        "skill_details": {
            "detect_magic": {
                "description": (
                    "An enchanter can attempt to detect the subtle resonances "
                    "woven into an enchanted object, place, or creature. If the "
                    "attempt succeeds, the enchanter knows if the target is "
                    "magical—i.e. enchanted, affected by a spell, or possessed "
                    "of innate magic of some kind."
                ),
                "requires": "touch object, place, or creature; concentrate without distraction",
                "time": "1 Turn per attempt",
                "retry": "May retry failed attempts as often as desired (1 Turn each)",
                "referee_rolls": (
                    "The Referee rolls all Detect Magic Checks, so players do not "
                    "know if the roll failed or if there is no magic present."
                ),
                "downtime": (
                    "Given an hour of solitude in a safe location, an enchanter "
                    "automatically detects magic on an object, place, or creature."
                ),
            },
        },
    },
)

ENCHANTER_GLAMOURS = ClassAbility(
    ability_id="enchanter_glamours",
    name="Glamours",
    description=(
        "Enchanters possess minor magical talents known as glamours. The number "
        "of glamours known is determined by the character's level. Known glamours "
        "are determined randomly."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "spell_type": "glamour",
        "spell_source": "data/content/spells/glamours.json",
        # Glamours known by level (from Enchanter Advancement table)
        "glamours_known": {
            1: 1,
            2: 2,
            3: 3,
            4: 3,
            5: 4,
            6: 5,
            7: 6,
            8: 6,
            9: 7,
            10: 7,
            11: 8,
            12: 8,
            13: 9,
            14: 9,
            15: 10,
        },
        "kindred_glamours_note": (
            "Some Kindreds (e.g. elf, grimalkin) gain glamours as a result of "
            "their ancestry. Such glamours are in addition to glamours gained "
            "by this Class. For example, a Level 1 human enchanter knows 1 "
            "glamour, whereas a Level 1 elf enchanter knows 2 glamours—one "
            "from their Kindred and one from their Class."
        ),
    },
)

ENCHANTER_FAIRY_RUNES = ClassAbility(
    ability_id="enchanter_fairy_runes",
    name="Fairy Runes",
    description=(
        "Enchanters are granted the use of fairy runes—the secret, magical sigils "
        "guarded by the rulers of Fairy. As a character advances, fairy nobles "
        "may be drawn by the enchanter's great deeds and grant new runes."
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
        "starting_runes": {
            "count": 1,
            "magnitude": "lesser",
            "selection": "random",
        },
        "learning_runes": (
            "Each time the character gains a Level, the player should roll for "
            "the chance of acquiring a new rune. See Learning Runes, p92."
        ),
        "reference": "See Fairy Magic, p92 for details on the fairy runes.",
    },
)

ENCHANTER_MAGIC_ITEMS = ClassAbility(
    ability_id="enchanter_magic_items",
    name="Magic Items",
    description=(
        "The enchanter's natural affinities allow the use of magical items "
        "exclusive to arcane spell-casters (for example, magic wands or scrolls "
        "of arcane spells)."
    ),
    is_passive=True,
    extra_data={
        "can_use_arcane_items": True,
        "item_types": ["wands", "arcane_scrolls", "arcane_magic_items"],
    },
)

ENCHANTER_DIVINE_RESISTANCE = ClassAbility(
    ability_id="enchanter_divine_resistance",
    name="Resistance to Divine Aid",
    description=(
        "The saints of the Pluritine Church are loath to aid those allied with "
        "the godless world of Fairy. If an enchanter is the subject of a "
        "beneficial holy spell, there is a 2-in-6 chance it has no effect."
    ),
    is_passive=True,
    extra_data={
        "holy_spell_failure_chance": "2-in-6",
        "affects": "beneficial holy spells only",
    },
)


# =============================================================================
# ENCHANTER LEVEL PROGRESSION
# =============================================================================

# Enchanter saving throws (improve every 2 levels)
ENCHANTER_SAVES_1_2 = SavingThrows(doom=11, ray=12, hold=13, blast=16, spell=14)
ENCHANTER_SAVES_3_4 = SavingThrows(doom=10, ray=11, hold=12, blast=15, spell=13)
ENCHANTER_SAVES_5_6 = SavingThrows(doom=9, ray=10, hold=11, blast=14, spell=12)
ENCHANTER_SAVES_7_8 = SavingThrows(doom=8, ray=9, hold=10, blast=13, spell=11)
ENCHANTER_SAVES_9_10 = SavingThrows(doom=7, ray=8, hold=9, blast=12, spell=10)
ENCHANTER_SAVES_11_12 = SavingThrows(doom=6, ray=7, hold=8, blast=11, spell=9)
ENCHANTER_SAVES_13_14 = SavingThrows(doom=5, ray=6, hold=7, blast=10, spell=8)
ENCHANTER_SAVES_15 = SavingThrows(doom=4, ray=5, hold=6, blast=9, spell=7)

ENCHANTER_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=ENCHANTER_SAVES_1_2,
        hit_dice="1d6",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=2,
        experience_required=1750,
        attack_bonus=0,
        saving_throws=ENCHANTER_SAVES_1_2,
        hit_dice="2d6",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=3,
        experience_required=3500,
        attack_bonus=1,
        saving_throws=ENCHANTER_SAVES_3_4,
        hit_dice="3d6",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=4,
        experience_required=7000,
        attack_bonus=1,
        saving_throws=ENCHANTER_SAVES_3_4,
        hit_dice="4d6",
        rune_access=["lesser"],
    ),
    LevelProgression(
        level=5,
        experience_required=14000,
        attack_bonus=2,
        saving_throws=ENCHANTER_SAVES_5_6,
        hit_dice="5d6",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=6,
        experience_required=28000,
        attack_bonus=2,
        saving_throws=ENCHANTER_SAVES_5_6,
        hit_dice="6d6",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=7,
        experience_required=56000,
        attack_bonus=3,
        saving_throws=ENCHANTER_SAVES_7_8,
        hit_dice="7d6",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=8,
        experience_required=112000,
        attack_bonus=3,
        saving_throws=ENCHANTER_SAVES_7_8,
        hit_dice="8d6",
        rune_access=["lesser", "greater"],
    ),
    LevelProgression(
        level=9,
        experience_required=220000,
        attack_bonus=4,
        saving_throws=ENCHANTER_SAVES_9_10,
        hit_dice="9d6",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=10,
        experience_required=340000,
        attack_bonus=4,
        saving_throws=ENCHANTER_SAVES_9_10,
        hit_dice="10d6",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=11,
        experience_required=460000,
        attack_bonus=5,
        saving_throws=ENCHANTER_SAVES_11_12,
        hit_dice="10d6+1",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=12,
        experience_required=580000,
        attack_bonus=5,
        saving_throws=ENCHANTER_SAVES_11_12,
        hit_dice="10d6+2",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=13,
        experience_required=700000,
        attack_bonus=6,
        saving_throws=ENCHANTER_SAVES_13_14,
        hit_dice="10d6+3",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=14,
        experience_required=820000,
        attack_bonus=6,
        saving_throws=ENCHANTER_SAVES_13_14,
        hit_dice="10d6+4",
        rune_access=["lesser", "greater", "mighty"],
    ),
    LevelProgression(
        level=15,
        experience_required=940000,
        attack_bonus=7,
        saving_throws=ENCHANTER_SAVES_15,
        hit_dice="10d6+5",
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
        "Individuals whose contact with Fairy has imbued them with innate magic "
        "known as glamours. Enchanters are also blessed with the use of the "
        "fairy runes, guarded by the lords of Fairy, though such gifts are not "
        "always without cost."
    ),
    hit_die=HitDie.D6,
    prime_ability="CHA,INT",  # Dual prime abilities
    magic_type=MagicType.GLAMOUR,  # Covers both glamours and runes
    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        ArmorProficiency.MEDIUM,
        # Note: No shields
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,  # Small weapons
        WeaponProficiency.MARTIAL,  # Medium weapons
    ],
    level_progression=ENCHANTER_LEVEL_PROGRESSION,
    abilities=[
        ENCHANTER_SKILLS,
        ENCHANTER_GLAMOURS,
        ENCHANTER_FAIRY_RUNES,
        ENCHANTER_MAGIC_ITEMS,
        ENCHANTER_DIVINE_RESISTANCE,
    ],
    # Typically only fairies and demi-fey, but mortals with strong Fairy
    # connection can also be enchanters
    restricted_kindreds=[],  # No hard restrictions, but typically fey/demi-fey
    starting_equipment=[
        # Armour (roll 1d6): 1-2. None. 3-4. Leather armour. 5-6. Chainmail.
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): 1. Club. 2. Dagger. 3. Longsword.
        # 4. Shortbow + 20 arrows. 5. Spear. 6. Staff.
        "weapon_roll_1d6_twice",
    ],
    extra_data={
        "kindred_note": (
            "Typically only fairies and demi-fey (elves, grimalkins, and "
            "woodgrues) are enchanters. Occasionally a mortal with a strong "
            "connection to Fairy may also be an enchanter—for example, a human "
            "with mixed elfish ancestry, an individual kidnapped by fairies in "
            "childhood, or someone who wandered lost in Fairy for many years."
        ),
        "combat_aptitude": "Semi-martial",
    },
    source_book="Dolmenwood Player Book",
    source_page=62,
)
