"""
Friar class definition for Dolmenwood.

Wandering ascetics who spread the gospel of the Pluritine Church.
Monks or nuns who have taken to a life of wandering, doing good
wherever they can. Only loosely affiliated with the Church and
beloved by the common folk.

Source: Dolmenwood Player Book, pages 66-67
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
# FRIAR ABILITIES
# =============================================================================

FRIAR_ARMOUR_OF_FAITH = ClassAbility(
    ability_id="friar_armour_of_faith",
    name="Armour of Faith",
    description=(
        "The divine blessing of the One True God grants friars a bonus to "
        "Armour Class, depending on their Level."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "ac_bonus_by_level": {
            1: 2,   # Levels 1-3
            2: 2,
            3: 2,
            4: 3,   # Levels 4-6
            5: 3,
            6: 3,
            7: 4,   # Levels 7-10
            8: 4,
            9: 4,
            10: 4,
            11: 5,  # Levels 11-15
            12: 5,
            13: 5,
            14: 5,
            15: 5,
        },
    },
)

FRIAR_CULINARY_IMPLEMENTS = ClassAbility(
    ability_id="friar_culinary_implements",
    name="Culinary Implements",
    description=(
        "A friar can employ a frying pan, cured sausage, or even a ham shank "
        "as a melee weapon, doing 1d4 damage."
    ),
    is_passive=True,
    extra_data={
        "improvised_weapons": ["frying pan", "cured sausage", "ham shank"],
        "damage": "1d4",
    },
)

FRIAR_SKILLS = ClassAbility(
    ability_id="friar_skills",
    name="Friar Skills",
    description=(
        "Friars have a Skill Target of 5 for Survival when foraging."
    ),
    is_passive=True,
    extra_data={
        "skills": ["survival_foraging"],
        "skill_targets": {
            "survival_foraging": 5,
        },
    },
)

FRIAR_HERBALISM = ClassAbility(
    ability_id="friar_herbalism",
    name="Herbalism",
    description=(
        "In the hands of a friar, a single dose of a medicinal herb "
        "(for example those listed under Common Fungi and Herbs, p130) "
        "is sufficient for 2 subjects."
    ),
    is_passive=True,
    extra_data={
        "herb_efficiency_multiplier": 2,
    },
)

FRIAR_HOLY_MAGIC = ClassAbility(
    ability_id="friar_holy_magic",
    name="Holy Magic",
    description=(
        "Friars may pray to the host of saints and receive blessings in the "
        "form of holy spells. Friars can also use magic items exclusive to "
        "holy spell-casters (for example, magic rods or scrolls of holy spells)."
    ),
    is_passive=True,
    extra_data={
        "spell_type": "holy",
        "max_spell_rank": 5,
        "requires_prayer": True,
        "requires_holy_symbol": True,
        "can_use_holy_magic_items": True,
    },
)

FRIAR_LANGUAGES = ClassAbility(
    ability_id="friar_languages",
    name="Languages",
    description=(
        "In addition to their native languages, friars speak Liturgic, the "
        "language of Church scripture."
    ),
    is_passive=True,
    extra_data={
        "bonus_languages": ["Liturgic"],
    },
)

FRIAR_POVERTY = ClassAbility(
    ability_id="friar_poverty",
    name="Poverty",
    description=(
        "Due to their monastic vows, a friar's worldly possessions are limited "
        "to that which can be carried on their person or mount. Excess wealth "
        "must be donated to worthy causes (not other PCs). Furthermore, a friar "
        "must dress in a simple habit and cut their hair in a traditional tonsure."
    ),
    is_passive=True,
    extra_data={
        "possession_limit": "carried on person or mount",
        "excess_wealth": "donated to worthy causes",
        "dress_code": "simple habit",
        "hair_style": "tonsure",
    },
)

FRIAR_TURN_UNDEAD = ClassAbility(
    ability_id="friar_turn_undead",
    name="Turning the Undead",
    description=(
        "A friar may attempt to drive off undead monsters by presenting their "
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
            "7_to_12": "2d4 undead flee from the friar for 1 Turn",
            "13_or_higher": "2d4 undead are permanently destroyed",
        },
        "level_modifiers": {
            "lower_level_undead": "+2 per Level difference (maximum +6)",
            "higher_level_undead": "-2 per Level difference (maximum -6)",
        },
        "mixed_groups": (
            "In encounters with multiple types of undead, those of lowest Level "
            "are affected first. On a successful turning roll, the friar may "
            "make another roll the following Round, affecting the next lowest "
            "Level type of undead present."
        ),
        "concealed_undead": "Undead behind doors or in coffers are unaffected",
    },
)


# =============================================================================
# FRIAR LEVEL PROGRESSION
# =============================================================================

# Friar saving throws (improve every 3 levels)
FRIAR_SAVES_1_3 = SavingThrows(doom=11, ray=12, hold=13, blast=16, spell=14)
FRIAR_SAVES_4_6 = SavingThrows(doom=10, ray=11, hold=12, blast=15, spell=13)
FRIAR_SAVES_7_9 = SavingThrows(doom=9, ray=10, hold=11, blast=14, spell=12)
FRIAR_SAVES_10_12 = SavingThrows(doom=8, ray=9, hold=10, blast=13, spell=11)
FRIAR_SAVES_13_15 = SavingThrows(doom=7, ray=8, hold=9, blast=12, spell=10)

FRIAR_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=FRIAR_SAVES_1_3,
        hit_dice="1d4",
        spell_slots={1: 1},
    ),
    LevelProgression(
        level=2,
        experience_required=1750,
        attack_bonus=0,
        saving_throws=FRIAR_SAVES_1_3,
        hit_dice="2d4",
        spell_slots={1: 2},
    ),
    LevelProgression(
        level=3,
        experience_required=3500,
        attack_bonus=0,
        saving_throws=FRIAR_SAVES_1_3,
        hit_dice="3d4",
        spell_slots={1: 2, 2: 1},
    ),
    LevelProgression(
        level=4,
        experience_required=7000,
        attack_bonus=1,
        saving_throws=FRIAR_SAVES_4_6,
        hit_dice="4d4",
        spell_slots={1: 2, 2: 2},
    ),
    LevelProgression(
        level=5,
        experience_required=14000,
        attack_bonus=1,
        saving_throws=FRIAR_SAVES_4_6,
        hit_dice="5d4",
        spell_slots={1: 3, 2: 2, 3: 1},
    ),
    LevelProgression(
        level=6,
        experience_required=28000,
        attack_bonus=1,
        saving_throws=FRIAR_SAVES_4_6,
        hit_dice="6d4",
        spell_slots={1: 3, 2: 2, 3: 2},
    ),
    LevelProgression(
        level=7,
        experience_required=56000,
        attack_bonus=2,
        saving_throws=FRIAR_SAVES_7_9,
        hit_dice="7d4",
        spell_slots={1: 3, 2: 3, 3: 2, 4: 1},
    ),
    LevelProgression(
        level=8,
        experience_required=112000,
        attack_bonus=2,
        saving_throws=FRIAR_SAVES_7_9,
        hit_dice="8d4",
        spell_slots={1: 4, 2: 3, 3: 2, 4: 2},
    ),
    LevelProgression(
        level=9,
        experience_required=220000,
        attack_bonus=2,
        saving_throws=FRIAR_SAVES_7_9,
        hit_dice="9d4",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 2, 5: 1},
    ),
    LevelProgression(
        level=10,
        experience_required=340000,
        attack_bonus=3,
        saving_throws=FRIAR_SAVES_10_12,
        hit_dice="10d4",
        spell_slots={1: 4, 2: 4, 3: 3, 4: 2, 5: 2},
    ),
    LevelProgression(
        level=11,
        experience_required=460000,
        attack_bonus=3,
        saving_throws=FRIAR_SAVES_10_12,
        hit_dice="10d4+1",
        spell_slots={1: 5, 2: 4, 3: 3, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=12,
        experience_required=580000,
        attack_bonus=3,
        saving_throws=FRIAR_SAVES_10_12,
        hit_dice="10d4+2",
        spell_slots={1: 5, 2: 4, 3: 4, 4: 3, 5: 2},
    ),
    LevelProgression(
        level=13,
        experience_required=700000,
        attack_bonus=4,
        saving_throws=FRIAR_SAVES_13_15,
        hit_dice="10d4+3",
        spell_slots={1: 5, 2: 5, 3: 4, 4: 3, 5: 3},
    ),
    LevelProgression(
        level=14,
        experience_required=820000,
        attack_bonus=4,
        saving_throws=FRIAR_SAVES_13_15,
        hit_dice="10d4+4",
        spell_slots={1: 6, 2: 5, 3: 4, 4: 4, 5: 3},
    ),
    LevelProgression(
        level=15,
        experience_required=940000,
        attack_bonus=4,
        saving_throws=FRIAR_SAVES_13_15,
        hit_dice="10d4+5",
        spell_slots={1: 6, 2: 5, 3: 5, 4: 4, 5: 3},
    ),
]


# =============================================================================
# COMPLETE FRIAR DEFINITION
# =============================================================================

FRIAR_DEFINITION = ClassDefinition(
    class_id="friar",
    name="Friar",
    description=(
        "Friars are monks or nuns who have taken to a life of wandering, doing "
        "good wherever they can. They are only loosely affiliated with the Church "
        "and exist outside the strict religious hierarchy of the clergy. Friars "
        "are thus beloved by the common folk, whom they often aid where the "
        "Church does not."
    ),

    hit_die=HitDie.D4,
    prime_ability="INT,WIS",  # Dual prime abilities

    magic_type=MagicType.HOLY,

    armor_proficiencies=[
        ArmorProficiency.NONE,
        # Note: Armour of Faith provides AC bonus instead
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,  # Club, dagger, sling, staff, torch
        # Also: holy water, oil (see weapons list)
    ],

    level_progression=FRIAR_LEVEL_PROGRESSION,

    abilities=[
        FRIAR_ARMOUR_OF_FAITH,
        FRIAR_CULINARY_IMPLEMENTS,
        FRIAR_SKILLS,
        FRIAR_HERBALISM,
        FRIAR_HOLY_MAGIC,
        FRIAR_LANGUAGES,
        FRIAR_POVERTY,
        FRIAR_TURN_UNDEAD,
    ],

    # Only mortals can be friars - fairies and demi-fey have no spiritual
    # connection with the deities of mortals
    restricted_kindreds=["elf", "grimalkin", "woodgrue", "mossling"],

    starting_equipment=[
        # Weapon (roll 1d6): 1. Club. 2. Dagger. 3–4. Sling + 20 stones. 5–6. Staff.
        "weapon_roll_1d6",
        # Class items
        "friars_habit",
        "wooden_holy_symbol",
    ],

    extra_data={
        "combat_aptitude": "Non-martial",
        "alignment_restriction": ["Lawful", "Neutral"],
        "allowed_weapons": ["club", "dagger", "holy_water", "oil", "sling", "staff", "torch"],
        "tenets": {
            "sanctity_of_life": (
                "All life is sacred. Friars must protect and aid the needy "
                "with all means available."
            ),
            "monotheism": (
                "Only One True God exists, and His name is ineffable. Other "
                "religions worship personifications of divine aspects of God "
                "or the anointed saints."
            ),
            "spiritual_insight": (
                "Each individual must form their own relationship with God, "
                "through study and insight."
            ),
            "mentorship": (
                "Friars must share their wisdom with common folk and non-believers, "
                "guiding them into the ways of the Pluritine Church."
            ),
        },
        "falling_from_grace": (
            "Friars must be faithful to the tenets of their order. A friar "
            "who transgresses or becomes Chaotic falls from grace and loses "
            "the ability to pray for spells. The Referee may allow the "
            "character to perform a quest of atonement to regain favour."
        ),
    },

    source_book="Dolmenwood Player Book",
    source_page=66,
)
