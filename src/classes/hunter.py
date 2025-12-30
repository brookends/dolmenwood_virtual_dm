"""
Hunter class definition for Dolmenwood.

Expert trackers, stalkers, and killers, at home in the wild woods.
Hardened to a life in the wilds, hunters develop a keen survival
instinct and an intuitive connection with wild animals.

Source: Dolmenwood Player Book, pages 68-69
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
# HUNTER ABILITIES
# =============================================================================

HUNTER_ANIMAL_COMPANION = ClassAbility(
    ability_id="hunter_animal_companion",
    name="Animal Companion",
    description=(
        "A hunter may attempt to forge a bond with an animal. If the bond is "
        "successfully established, the animal becomes the hunter's loyal companion."
    ),
    is_passive=True,
    extra_data={
        "max_companions": 1,
        "establishing_connection": {
            "method": "Approach animal and interact peacefully for 1 Turn",
            "check": "Charisma Check",
            "on_success": "Animal becomes hunter's companion",
        },
        "companion_behaviour": {
            "follows": "Follows hunter everywhere",
            "commands": "Understands basic commands (even if species normally wouldn't)",
            "combat": "Fights to defend hunter, never checks Morale",
        },
        "requirements": {
            "types": "Wild or domestic animals; giant/magical at Referee discretion",
            "excluded": "Sentient animal species",
            "max_level": "Companion Level cannot exceed hunter's Level",
        },
        "replacement": "If companion dies or is dismissed, hunter may bond with new animal",
    },
)

HUNTER_SKILLS = ClassAbility(
    ability_id="hunter_skills",
    name="Hunter Skills",
    description=(
        "As they advance in Level, hunters improve their chance of success with "
        "the Survival skill. They also have three additional, specialised skills: "
        "Alertness, Stalking, and Tracking."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skills": ["alertness", "stalking", "survival", "tracking"],
        # Skill Targets by level (roll d6 >= target to succeed)
        "skill_targets": {
            1: {"alertness": 6, "stalking": 6, "survival": 5, "tracking": 5},
            2: {"alertness": 6, "stalking": 6, "survival": 4, "tracking": 5},
            3: {"alertness": 6, "stalking": 6, "survival": 4, "tracking": 4},
            4: {"alertness": 6, "stalking": 5, "survival": 4, "tracking": 4},
            5: {"alertness": 5, "stalking": 5, "survival": 4, "tracking": 4},
            6: {"alertness": 5, "stalking": 5, "survival": 3, "tracking": 4},
            7: {"alertness": 5, "stalking": 5, "survival": 3, "tracking": 3},
            8: {"alertness": 5, "stalking": 4, "survival": 3, "tracking": 3},
            9: {"alertness": 4, "stalking": 4, "survival": 3, "tracking": 3},
            10: {"alertness": 4, "stalking": 3, "survival": 3, "tracking": 3},
            11: {"alertness": 4, "stalking": 3, "survival": 2, "tracking": 3},
            12: {"alertness": 4, "stalking": 3, "survival": 2, "tracking": 2},
            13: {"alertness": 3, "stalking": 3, "survival": 2, "tracking": 2},
            14: {"alertness": 3, "stalking": 2, "survival": 2, "tracking": 2},
            15: {"alertness": 2, "stalking": 2, "survival": 2, "tracking": 2},
        },
        "skill_details": {
            "alertness": {
                "description": (
                    "If a hunter's party is surprised, the hunter may make an "
                    "Alertness Check to act normally in the Surprise Round."
                ),
            },
            "stalking": {
                "description": (
                    "Hiding: A hunter may make a Stalking Check to remain undetected "
                    "when the only cover available is light brush. "
                    "Sneaking: If a Surprise Roll indicates that a hunter's party "
                    "has been detected, the hunter may make a Stalking Check to "
                    "remain undetected."
                ),
                "wilderness_only": True,
            },
            "survival": {
                "description": "General wilderness survival skill.",
            },
            "tracking": {
                "description": (
                    "A successful check allows a hunter to find tracks left by "
                    "creatures in a 30′ × 30′ area. The hunter knows the type of "
                    "creatures that made the tracks and may follow the tracks."
                ),
                "time": "1 Turn to find tracks",
                "retry": "Cannot retry in same location",
                "following": "Can follow tracks until conditions worsen, then new check required",
                "modifiers": [
                    "+1 for soft ground",
                    "-1 for hard ground",
                    "+1 for tracks by group of 10+",
                    "-2 for active attempts to cover tracks",
                    "-1 per day since tracks made",
                    "-1 per hour of rain or covering snow",
                    "-1 for poor lighting",
                ],
                "wilderness_only": True,
            },
        },
        "optional_customisation": {
            "description": (
                "Players wishing to customise their character's skill advancement "
                "may use the optional expertise points system."
            ),
            "base_skill_target": 6,
            "starting_expertise_points": 2,
            "expertise_per_level": 1,
            "minimum_skill_target": 2,
        },
    },
)

HUNTER_MISSILE_ATTACKS = ClassAbility(
    ability_id="hunter_missile_attacks",
    name="Missile Attacks",
    description=("Hunters gain a +1 Attack bonus with all missile weapons."),
    is_passive=True,
    extra_data={
        "missile_attack_bonus": 1,
    },
)

HUNTER_TROPHIES = ClassAbility(
    ability_id="hunter_trophies",
    name="Trophies",
    description=(
        "After hunting down (i.e. tracking, ambushing, or chasing) and slaying "
        "a creature, a hunter may take a trophy from it—for example, a stag's "
        "antlers, a wyrm's tooth, etc."
    ),
    is_passive=True,
    extra_data={
        "minimum_weight": "50 coins",
        "boon": {
            "requirement": "Trophy on hunter's person or mounted in their home",
            "attack_bonus": "+1 Attack Rolls against creatures of same type",
            "save_bonus": "+1 Saving Throws against their special attacks",
        },
    },
)

HUNTER_WAYFINDING = ClassAbility(
    ability_id="hunter_wayfinding",
    name="Wayfinding",
    description=(
        "If the Referee determines that the hunter's party has become lost, "
        "there is a 3-in-6 chance that the hunter can find the path again."
    ),
    is_passive=True,
    extra_data={
        "success_chance": "3-in-6",
    },
)


# =============================================================================
# HUNTER LEVEL PROGRESSION
# =============================================================================

# Hunter saving throws (irregular progression like fighter)
HUNTER_SAVES_1_2 = SavingThrows(doom=12, ray=13, hold=14, blast=15, spell=16)
HUNTER_SAVES_3 = SavingThrows(doom=11, ray=12, hold=13, blast=14, spell=15)
HUNTER_SAVES_4_5 = SavingThrows(doom=10, ray=11, hold=12, blast=13, spell=14)
HUNTER_SAVES_6 = SavingThrows(doom=9, ray=10, hold=11, blast=12, spell=13)
HUNTER_SAVES_7_8 = SavingThrows(doom=8, ray=9, hold=10, blast=11, spell=12)
HUNTER_SAVES_9 = SavingThrows(doom=7, ray=8, hold=9, blast=10, spell=11)
HUNTER_SAVES_10_11 = SavingThrows(doom=6, ray=7, hold=8, blast=9, spell=10)
HUNTER_SAVES_12 = SavingThrows(doom=5, ray=6, hold=7, blast=8, spell=9)
HUNTER_SAVES_13_14 = SavingThrows(doom=4, ray=5, hold=6, blast=7, spell=8)
HUNTER_SAVES_15 = SavingThrows(doom=3, ray=4, hold=5, blast=6, spell=7)

HUNTER_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=1,
        saving_throws=HUNTER_SAVES_1_2,
        hit_dice="1d8",
    ),
    LevelProgression(
        level=2,
        experience_required=2250,
        attack_bonus=1,
        saving_throws=HUNTER_SAVES_1_2,
        hit_dice="2d8",
    ),
    LevelProgression(
        level=3,
        experience_required=4500,
        attack_bonus=2,
        saving_throws=HUNTER_SAVES_3,
        hit_dice="3d8",
    ),
    LevelProgression(
        level=4,
        experience_required=9000,
        attack_bonus=3,
        saving_throws=HUNTER_SAVES_4_5,
        hit_dice="4d8",
    ),
    LevelProgression(
        level=5,
        experience_required=18000,
        attack_bonus=3,
        saving_throws=HUNTER_SAVES_4_5,
        hit_dice="5d8",
    ),
    LevelProgression(
        level=6,
        experience_required=36000,
        attack_bonus=4,
        saving_throws=HUNTER_SAVES_6,
        hit_dice="6d8",
    ),
    LevelProgression(
        level=7,
        experience_required=72000,
        attack_bonus=5,
        saving_throws=HUNTER_SAVES_7_8,
        hit_dice="7d8",
    ),
    LevelProgression(
        level=8,
        experience_required=144000,
        attack_bonus=5,
        saving_throws=HUNTER_SAVES_7_8,
        hit_dice="8d8",
    ),
    LevelProgression(
        level=9,
        experience_required=290000,
        attack_bonus=6,
        saving_throws=HUNTER_SAVES_9,
        hit_dice="9d8",
    ),
    LevelProgression(
        level=10,
        experience_required=420000,
        attack_bonus=7,
        saving_throws=HUNTER_SAVES_10_11,
        hit_dice="10d8",
    ),
    LevelProgression(
        level=11,
        experience_required=550000,
        attack_bonus=7,
        saving_throws=HUNTER_SAVES_10_11,
        hit_dice="10d8+2",
    ),
    LevelProgression(
        level=12,
        experience_required=680000,
        attack_bonus=8,
        saving_throws=HUNTER_SAVES_12,
        hit_dice="10d8+4",
    ),
    LevelProgression(
        level=13,
        experience_required=810000,
        attack_bonus=9,
        saving_throws=HUNTER_SAVES_13_14,
        hit_dice="10d8+6",
    ),
    LevelProgression(
        level=14,
        experience_required=940000,
        attack_bonus=9,
        saving_throws=HUNTER_SAVES_13_14,
        hit_dice="10d8+8",
    ),
    LevelProgression(
        level=15,
        experience_required=1070000,
        attack_bonus=10,
        saving_throws=HUNTER_SAVES_15,
        hit_dice="10d8+10",
    ),
]


# =============================================================================
# COMPLETE HUNTER DEFINITION
# =============================================================================

HUNTER_DEFINITION = ClassDefinition(
    class_id="hunter",
    name="Hunter",
    description=(
        "Hardened to a life in the wilds, hunters develop a keen survival "
        "instinct and an intuitive connection with wild animals. A hunter's "
        "knowledge of tracking, hunting, and survival is invaluable to any "
        "party travelling deep into Dolmenwood."
    ),
    hit_die=HitDie.D8,
    prime_ability="CON,DEX",  # Dual prime abilities
    magic_type=MagicType.NONE,
    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        ArmorProficiency.SHIELDS,
    ],
    weapon_proficiencies=[
        WeaponProficiency.ALL,
    ],
    level_progression=HUNTER_LEVEL_PROGRESSION,
    abilities=[
        HUNTER_ANIMAL_COMPANION,
        HUNTER_SKILLS,
        HUNTER_MISSILE_ATTACKS,
        HUNTER_TROPHIES,
        HUNTER_WAYFINDING,
    ],
    # No kindred restrictions
    restricted_kindreds=[],
    starting_equipment=[
        # Armour (roll 1d6): 1–3. Leather armour. 4–6. Leather armour + shield.
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): 1. Dagger. 2. Longsword.
        # 3–4. Longbow + 20 arrows (shortbow for Small). 5. Shortsword.
        # 6. Sling + 20 stones.
        "weapon_roll_1d6_twice",
    ],
    extra_data={
        "combat_aptitude": "Martial",
        "small_character_note": (
            "Small characters receive shortbow instead of longbow for "
            "starting equipment roll 3-4."
        ),
    },
    source_book="Dolmenwood Player Book",
    source_page=68,
)
