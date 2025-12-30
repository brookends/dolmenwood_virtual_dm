"""
Cleric class definition for Dolmenwood.

Holy warriors in the service of the Pluritine Church. Organised in a
strict religious hierarchy, they wield divine magic and the power
to turn undead.

Source: Dolmenwood Player Book, pages 60-61
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
# CLERIC ABILITIES
# =============================================================================

CLERIC_DETECT_HOLY_MAGIC = ClassAbility(
    ability_id="cleric_detect_holy_magic",
    name="Detect Holy Magic Items",
    description=(
        "A cleric can detect whether an item is enchanted with holy magic. "
        "The cleric must touch the object and concentrate without distraction."
    ),
    is_passive=False,
    extra_data={
        "requires": "touch object, concentrate without distraction",
        "time": "1 Turn",
    },
)

CLERIC_HOLY_MAGIC = ClassAbility(
    ability_id="cleric_holy_magic",
    name="Holy Magic",
    description=(
        "Once a cleric has proven their devotion (from Level 2), the character "
        "may pray to the host of saints to receive their blessings in the form "
        "of holy spells. Clerics can also use magic items exclusive to holy "
        "spell-casters (such as magic rods or scrolls of holy spells)."
    ),
    min_level=2,
    is_passive=True,
    extra_data={
        "spell_type": "holy",
        "max_spell_rank": 5,
        "requires_prayer": True,
        "requires_holy_symbol": True,
        "can_use_holy_magic_items": True,
    },
)

CLERIC_HOLY_ORDER = ClassAbility(
    ability_id="cleric_holy_order",
    name="Holy Order",
    description=(
        "Upon reaching Level 2, a cleric is initiated into one of three holy "
        "orders, each granting a special power and unique holy symbol."
    ),
    min_level=2,
    is_passive=True,
    extra_data={
        "orders": {
            "order_of_st_faxis": {
                "name": "The Order of St Faxis",
                "description": (
                    "The order of seekers; clerics who follow an edict to root out "
                    "practitioners of dark magic—those who truck with devils or "
                    "deal in necromancy."
                ),
                "power": "Arcane Antipathy",
                "power_description": (
                    "A cleric of St Faxis gains a +2 bonus to Saving Throws against "
                    "arcane magic. Arcane spell-casters suffer a –2 penalty to Saving "
                    "Throws against spells cast by a cleric of St Faxis."
                ),
                "holy_symbol": "Three crossed swords",
                "save_bonus_vs_arcane": 2,
                "arcane_caster_save_penalty": -2,
            },
            "order_of_st_sedge": {
                "name": "The Order of St Sedge",
                "description": (
                    "The defenders of the Church; clerics who protect the lands of "
                    "the Church from invaders."
                ),
                "power": "Laying on Hands",
                "power_description": (
                    "A cleric of St Sedge can heal by laying their hands on wounded "
                    "characters. Once a day, the cleric can heal a total of up to "
                    "1 Hit Point per Level."
                ),
                "holy_symbol": "A hand with two fingers raised",
                "healing_per_day": "1 HP per Level",
            },
            "order_of_st_signis": {
                "name": "The Order of St Signis",
                "description": (
                    "The order of Lichwards; clerics who watch over the dead and "
                    "hunt those which rise again as undead."
                ),
                "power": "Undead Slayer",
                "power_description": (
                    "A cleric of St Signis gains a +1 Attack bonus against undead "
                    "monsters. Their attacks harm undead monsters that can normally "
                    "only be harmed by magical or silver weapons, even when not "
                    "wielding a weapon of the appropriate type."
                ),
                "holy_symbol": "A human skull crowned with ivy",
                "attack_bonus_vs_undead": 1,
                "bypasses_undead_resistance": True,
            },
        },
    },
)

CLERIC_TURN_UNDEAD = ClassAbility(
    ability_id="cleric_turn_undead",
    name="Turning the Undead",
    description=(
        "A cleric may attempt to drive off undead monsters by presenting their "
        "holy symbol and invoking the might of the One True God."
    ),
    is_passive=False,
    extra_data={
        "range_feet": 30,
        "uses_per_turn": 1,
        "roll": "2d6",
        "results": {
            "4_or_lower": "The undead are unaffected",
            "5_to_6": "2d4 undead are stunned for 1 Round, unable to act",
            "7_to_12": "2d4 undead flee from the cleric for 1 Turn",
            "13_or_higher": "2d4 undead are permanently destroyed",
        },
        "level_modifiers": {
            "lower_level_undead": "+2 per Level difference (maximum +6)",
            "higher_level_undead": "-2 per Level difference (maximum -6)",
        },
        "mixed_groups": (
            "In encounters with multiple types of undead, those of lowest Level "
            "are affected first. On a successful turning roll, the cleric may "
            "make another roll the following Round, affecting the next lowest "
            "Level type of undead present."
        ),
        "concealed_undead": "Undead behind doors or in coffers are unaffected",
    },
)

CLERIC_LANGUAGES = ClassAbility(
    ability_id="cleric_languages",
    name="Languages",
    description=(
        "In addition to their native languages, clerics speak Liturgic, the "
        "language of Church scripture."
    ),
    is_passive=True,
    extra_data={
        "bonus_languages": ["Liturgic"],
    },
)


# =============================================================================
# CLERIC LEVEL PROGRESSION
# =============================================================================

# Cleric saving throws (improve every 2 levels)
CLERIC_SAVES_1_2 = SavingThrows(doom=11, ray=12, hold=13, blast=16, spell=14)
CLERIC_SAVES_3_4 = SavingThrows(doom=10, ray=11, hold=12, blast=15, spell=13)
CLERIC_SAVES_5_6 = SavingThrows(doom=9, ray=10, hold=11, blast=14, spell=12)
CLERIC_SAVES_7_8 = SavingThrows(doom=8, ray=9, hold=10, blast=13, spell=11)
CLERIC_SAVES_9_10 = SavingThrows(doom=7, ray=8, hold=9, blast=12, spell=10)
CLERIC_SAVES_11_12 = SavingThrows(doom=6, ray=7, hold=8, blast=11, spell=9)
CLERIC_SAVES_13_14 = SavingThrows(doom=5, ray=6, hold=7, blast=10, spell=8)
CLERIC_SAVES_15 = SavingThrows(doom=4, ray=5, hold=6, blast=9, spell=7)

CLERIC_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=CLERIC_SAVES_1_2,
        hit_dice="1d6",
        spell_slots={},  # No spells at level 1
    ),
    LevelProgression(
        level=2,
        experience_required=1500,
        attack_bonus=0,
        saving_throws=CLERIC_SAVES_1_2,
        hit_dice="2d6",
        spell_slots={1: 1},
        abilities_gained=["cleric_holy_magic", "cleric_holy_order"],
    ),
    LevelProgression(
        level=3,
        experience_required=3000,
        attack_bonus=1,
        saving_throws=CLERIC_SAVES_3_4,
        hit_dice="3d6",
        spell_slots={1: 2},
    ),
    LevelProgression(
        level=4,
        experience_required=6000,
        attack_bonus=1,
        saving_throws=CLERIC_SAVES_3_4,
        hit_dice="4d6",
        spell_slots={1: 2, 2: 1},
    ),
    LevelProgression(
        level=5,
        experience_required=12000,
        attack_bonus=2,
        saving_throws=CLERIC_SAVES_5_6,
        hit_dice="5d6",
        spell_slots={1: 2, 2: 2},
    ),
    LevelProgression(
        level=6,
        experience_required=24000,
        attack_bonus=2,
        saving_throws=CLERIC_SAVES_5_6,
        hit_dice="6d6",
        spell_slots={1: 2, 2: 2, 3: 1},
    ),
    LevelProgression(
        level=7,
        experience_required=48000,
        attack_bonus=3,
        saving_throws=CLERIC_SAVES_7_8,
        hit_dice="7d6",
        spell_slots={1: 3, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=8,
        experience_required=96000,
        attack_bonus=3,
        saving_throws=CLERIC_SAVES_7_8,
        hit_dice="8d6",
        spell_slots={1: 3, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=9,
        experience_required=190000,
        attack_bonus=4,
        saving_throws=CLERIC_SAVES_9_10,
        hit_dice="9d6",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 1},
    ),
    LevelProgression(
        level=10,
        experience_required=290000,
        attack_bonus=4,
        saving_throws=CLERIC_SAVES_9_10,
        hit_dice="10d6",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 2},
    ),
    LevelProgression(
        level=11,
        experience_required=390000,
        attack_bonus=5,
        saving_throws=CLERIC_SAVES_11_12,
        hit_dice="10d6+1",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 2},
    ),
    LevelProgression(
        level=12,
        experience_required=490000,
        attack_bonus=5,
        saving_throws=CLERIC_SAVES_11_12,
        hit_dice="10d6+2",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 2, 5: 1},
    ),
    LevelProgression(
        level=13,
        experience_required=590000,
        attack_bonus=6,
        saving_throws=CLERIC_SAVES_13_14,
        hit_dice="10d6+3",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 2, 5: 2},
    ),
    LevelProgression(
        level=14,
        experience_required=690000,
        attack_bonus=6,
        saving_throws=CLERIC_SAVES_13_14,
        hit_dice="10d6+4",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=15,
        experience_required=790000,
        attack_bonus=7,
        saving_throws=CLERIC_SAVES_15,
        hit_dice="10d6+5",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 3, 5: 2},
    ),
]


# =============================================================================
# COMPLETE CLERIC DEFINITION
# =============================================================================

CLERIC_DEFINITION = ClassDefinition(
    class_id="cleric",
    name="Cleric",
    description=(
        "Clerics are members of an order of holy warriors sworn to the service "
        "of the Pluritine Church. They are organised in a strict religious "
        "hierarchy, under the command of higher-ranking Church officials. "
        "Player Character clerics are typically granted a writ of self-"
        "determination, allowing them to roam freely and carry out the will "
        "of God as they see fit."
    ),
    hit_die=HitDie.D6,
    prime_ability="WIS",
    magic_type=MagicType.HOLY,
    armor_proficiencies=[
        ArmorProficiency.ALL,
        ArmorProficiency.SHIELDS,
        # Note: Cannot use arcane or fairy magic armor
    ],
    weapon_proficiencies=[
        WeaponProficiency.ALL,
        # Note: Cannot use arcane or fairy magic weapons
    ],
    level_progression=CLERIC_LEVEL_PROGRESSION,
    abilities=[
        CLERIC_DETECT_HOLY_MAGIC,
        CLERIC_HOLY_MAGIC,
        CLERIC_HOLY_ORDER,
        CLERIC_TURN_UNDEAD,
        CLERIC_LANGUAGES,
    ],
    # Only mortals can be clerics - fairies and demi-fey have no spiritual
    # connection with the deities of mortals
    restricted_kindreds=["elf", "grimalkin", "woodgrue", "mossling"],
    starting_equipment=[
        # Armour (roll 1d6): 1. Leather. 2. Leather + shield. 3. Chainmail.
        # 4. Chainmail + shield. 5. Plate mail. 6. Plate mail + shield.
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): 1. Dagger. 2. Longsword. 3. Mace.
        # 4. Shortbow + 20 arrows. 5. Shortsword. 6. Warhammer.
        "weapon_roll_1d6_twice",
        # Class items
        "wooden_holy_symbol",
    ],
    extra_data={
        "alignment_restriction": ["Lawful", "Neutral"],
        "magic_item_restriction": (
            "Cannot use magic weapons, armour, or shields of arcane or fairy "
            "origin. May only use holy magic armaments."
        ),
        "tenets": {
            "evangelism": "Non-believers are to be brought into the fold and converted.",
            "hierarchy": (
                "The hierarchy of the Church is to be upheld. Those of lesser "
                "rank must obey their superiors."
            ),
            "monotheism": (
                "Only One True God exists, and His name is ineffable. Other "
                "religions worship personifications of divine aspects of God "
                "or the anointed saints."
            ),
            "sanctity_of_life": (
                "Sentient life is sacred. Clerics must protect the innocent "
                "with all means available."
            ),
        },
        "falling_from_grace": (
            "Clerics must be faithful to the tenets of their order. A cleric "
            "who transgresses or becomes Chaotic falls from grace and loses "
            "the ability to pray for spells. The Referee may allow the "
            "character to perform a quest of atonement to regain favour."
        ),
    },
    source_book="Dolmenwood Player Book",
    source_page=60,
)
