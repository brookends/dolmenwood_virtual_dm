"""
Thief class definition for Dolmenwood.

Rogues who live by skills of deception and stealth.
Inveterate scoundrels, thieves are always on the lookout for their next
mark, scam, or get rich quick scheme. Many thieves are drawn to a life
of adventure, relishing exploration, peril, and the promise of great wealth.

Source: Dolmenwood Player Book, pages 74-75
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

THIEF_BACKSTAB = ClassAbility(
    ability_id="thief_backstab",
    name="Back-Stab",
    description=(
        "Thieves are proficient in dealing deadly blows when attacking from "
        "behind with a dagger in melee."
    ),
    is_passive=False,
    is_attack=True,
    extra_data={
        "conditions": {
            "position": "Must be positioned behind the target",
            "awareness": (
                "Target must be unaware of the thief's presence. If the thief "
                "successfully used their Stealth skill to hide or sneak, the "
                "target is considered unaware."
            ),
        },
        "valid_targets": "Mortals, fairies, or demi-fey of Small or Medium size",
        "bonuses": {
            "attack_bonus": 4,
            "damage": "3d4",
            "damage_modifiers": ["Strength", "magic dagger enchantment bonus"],
        },
        "natural_1": (
            "On a roll of natural 1, the thief must Save Versus Doom to avoid "
            "being noticed. The Referee determines the victim's reaction."
        ),
    },
)

THIEF_SKILLS = ClassAbility(
    ability_id="thief_skills",
    name="Thief Skills",
    description=(
        "As they advance in level, thieves improve their chance of success "
        "with the Listen and Search skills. They also have six additional, "
        "specialised skills."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "skills": [
            "climb_wall",
            "decipher_document",
            "disarm_mechanism",
            "legerdemain",
            "pick_lock",
            "listen",
            "search",
            "stealth",
        ],
        # Skill Targets by level (roll d6 >= target to succeed)
        "skill_targets": {
            1: {
                "climb_wall": 4,
                "decipher_document": 6,
                "disarm_mechanism": 6,
                "legerdemain": 6,
                "pick_lock": 6,
                "listen": 5,
                "search": 6,
                "stealth": 5,
            },
            2: {
                "climb_wall": 4,
                "decipher_document": 6,
                "disarm_mechanism": 5,
                "legerdemain": 6,
                "pick_lock": 6,
                "listen": 5,
                "search": 5,
                "stealth": 5,
            },
            3: {
                "climb_wall": 4,
                "decipher_document": 6,
                "disarm_mechanism": 5,
                "legerdemain": 5,
                "pick_lock": 5,
                "listen": 5,
                "search": 5,
                "stealth": 5,
            },
            4: {
                "climb_wall": 3,
                "decipher_document": 5,
                "disarm_mechanism": 5,
                "legerdemain": 5,
                "pick_lock": 5,
                "listen": 5,
                "search": 5,
                "stealth": 5,
            },
            5: {
                "climb_wall": 3,
                "decipher_document": 5,
                "disarm_mechanism": 5,
                "legerdemain": 5,
                "pick_lock": 5,
                "listen": 4,
                "search": 5,
                "stealth": 4,
            },
            6: {
                "climb_wall": 3,
                "decipher_document": 5,
                "disarm_mechanism": 4,
                "legerdemain": 5,
                "pick_lock": 5,
                "listen": 4,
                "search": 4,
                "stealth": 4,
            },
            7: {
                "climb_wall": 3,
                "decipher_document": 5,
                "disarm_mechanism": 4,
                "legerdemain": 4,
                "pick_lock": 4,
                "listen": 4,
                "search": 4,
                "stealth": 4,
            },
            8: {
                "climb_wall": 2,
                "decipher_document": 4,
                "disarm_mechanism": 4,
                "legerdemain": 4,
                "pick_lock": 4,
                "listen": 4,
                "search": 4,
                "stealth": 4,
            },
            9: {
                "climb_wall": 2,
                "decipher_document": 4,
                "disarm_mechanism": 4,
                "legerdemain": 4,
                "pick_lock": 4,
                "listen": 3,
                "search": 4,
                "stealth": 3,
            },
            10: {
                "climb_wall": 2,
                "decipher_document": 4,
                "disarm_mechanism": 3,
                "legerdemain": 4,
                "pick_lock": 4,
                "listen": 3,
                "search": 3,
                "stealth": 3,
            },
            11: {
                "climb_wall": 2,
                "decipher_document": 4,
                "disarm_mechanism": 3,
                "legerdemain": 3,
                "pick_lock": 3,
                "listen": 3,
                "search": 3,
                "stealth": 3,
            },
            12: {
                "climb_wall": 2,
                "decipher_document": 3,
                "disarm_mechanism": 3,
                "legerdemain": 3,
                "pick_lock": 3,
                "listen": 2,
                "search": 3,
                "stealth": 3,
            },
            13: {
                "climb_wall": 2,
                "decipher_document": 3,
                "disarm_mechanism": 3,
                "legerdemain": 3,
                "pick_lock": 3,
                "listen": 2,
                "search": 2,
                "stealth": 2,
            },
            14: {
                "climb_wall": 2,
                "decipher_document": 3,
                "disarm_mechanism": 2,
                "legerdemain": 3,
                "pick_lock": 2,
                "listen": 2,
                "search": 2,
                "stealth": 2,
            },
            15: {
                "climb_wall": 2,
                "decipher_document": 2,
                "disarm_mechanism": 2,
                "legerdemain": 2,
                "pick_lock": 2,
                "listen": 2,
                "search": 2,
                "stealth": 2,
            },
        },
        "skill_details": {
            "climb_wall": {
                "description": (
                    "A successful check allows a thief to climb vertical or very "
                    "steep surfaces with only minimal handholds. The thief does "
                    "not require any special climbing equipment."
                ),
                "easier_circumstances": "Thieves make easier climbs without a roll",
                "long_climbs": (
                    "For climbs of over 100′, a Climb Wall Check is required for "
                    "each stretch of up to 100′. For example, a climb of 150′ "
                    "requires two checks."
                ),
                "failure": (
                    "The thief is unable to find suitable handholds and makes "
                    "no progress with the climb."
                ),
                "natural_1": (
                    "On a roll of natural 1, the thief must Save Versus Doom or "
                    "fall from the halfway point, suffering 1d6 damage per 10′ "
                    "of the fall."
                ),
                "retry": "May retry failed attempts (1 Turn each)",
            },
            "decipher_document": {
                "description": (
                    "A successful check allows a thief to understand the gist of "
                    "a non-magical text in a language they do not speak, unravel "
                    "a cypher, or identify cryptically labelled landmarks on a map."
                ),
                "retry": "May only attempt to read the same document again after gaining a Level",
            },
            "disarm_mechanism": {
                "description": (
                    "A successful check allows a thief to disarm complex, "
                    "clockwork-like trap mechanisms hidden in a lock, lid, door "
                    "handle, or similar."
                ),
                "requires": "Thieves' tools",
                "time": "1 Turn per attempt",
                "retry": "May retry failed attempts (1 Turn each)",
                "natural_1": (
                    "On a roll of natural 1, the thief must Save Versus Doom or "
                    "accidentally spring the trap."
                ),
            },
            "legerdemain": {
                "description": (
                    "A successful check allows a thief to pilfer a small item in "
                    "the possession of another creature or perform a trick of "
                    "sleight of hand, such as palming a small object or slipping "
                    "a poison into a drink."
                ),
                "difficulty": "-1 penalty per three Levels of the victim or observer",
                "natural_1": (
                    "On a roll of natural 1, the thief must Save Versus Doom to "
                    "avoid being noticed. The Referee determines the victim's reaction."
                ),
            },
            "pick_lock": {
                "description": (
                    "A successful check allows a thief to open a lock without the key."
                ),
                "requires": "Thieves' tools",
                "time": "1 Turn per attempt",
                "retry": "May retry failed attempts (1 Turn each)",
                "difficult_locks": (
                    "The Referee may rule that certain locks are more difficult. "
                    "Advanced locks incur a penalty to the Pick Lock Check or only "
                    "allow a fixed number of attempts, after which the thief is "
                    "stymied and may only try again after gaining a Level."
                ),
            },
            "listen": {
                "description": "Standard skill, improved by thief class advancement.",
            },
            "search": {
                "description": "Standard skill, improved by thief class advancement.",
            },
            "stealth": {
                "description": (
                    "Hiding: A thief may make a Stealth Check to remain undetected "
                    "when shadows are the only cover available. "
                    "Sneaking: If a Surprise Roll indicates that a thief's party "
                    "has been detected, the thief may make a Stealth Check to "
                    "remain undetected."
                ),
                "references": ["Hiding and Ambushes under Stealth, p154", "Surprise, p164"],
            },
        },
        "optional_customisation": {
            "description": (
                "Players wishing to customise their character's skill advancement "
                "may use this optional rule."
            ),
            "base_skill_target": 6,
            "starting_expertise_points": 4,
            "expertise_per_level": 2,
            "minimum_skill_target": 2,
        },
    },
)

THIEF_THIEVES_CANT = ClassAbility(
    ability_id="thief_thieves_cant",
    name="Thieves' Cant",
    description=(
        "In addition to their native languages, thieves learn a secret language "
        "of gestures and code words that allows them to hide messages in "
        "seemingly normal conversations."
    ),
    is_passive=True,
    extra_data={
        "language_type": "secret",
        "components": ["gestures", "code words"],
        "usage": "Hide messages in seemingly normal conversations",
    },
)


# =============================================================================
# THIEF LEVEL PROGRESSION
# =============================================================================

# Thief saving throws (improve every 2 levels)
# Note: Doom=Hold, Ray=Doom+1, Blast=Spell
THIEF_SAVES_1_2 = SavingThrows(doom=13, ray=14, hold=13, blast=15, spell=15)
THIEF_SAVES_3_4 = SavingThrows(doom=12, ray=13, hold=12, blast=14, spell=14)
THIEF_SAVES_5_6 = SavingThrows(doom=11, ray=12, hold=11, blast=13, spell=13)
THIEF_SAVES_7_8 = SavingThrows(doom=10, ray=11, hold=10, blast=12, spell=12)
THIEF_SAVES_9_10 = SavingThrows(doom=9, ray=10, hold=9, blast=11, spell=11)
THIEF_SAVES_11_12 = SavingThrows(doom=8, ray=9, hold=8, blast=10, spell=10)
THIEF_SAVES_13_14 = SavingThrows(doom=7, ray=8, hold=7, blast=9, spell=9)
THIEF_SAVES_15 = SavingThrows(doom=6, ray=7, hold=6, blast=8, spell=8)

THIEF_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=0,
        saving_throws=THIEF_SAVES_1_2,
        hit_dice="1d4",
    ),
    LevelProgression(
        level=2,
        experience_required=1200,
        attack_bonus=0,
        saving_throws=THIEF_SAVES_1_2,
        hit_dice="2d4",
    ),
    LevelProgression(
        level=3,
        experience_required=2400,
        attack_bonus=1,
        saving_throws=THIEF_SAVES_3_4,
        hit_dice="3d4",
    ),
    LevelProgression(
        level=4,
        experience_required=4800,
        attack_bonus=1,
        saving_throws=THIEF_SAVES_3_4,
        hit_dice="4d4",
    ),
    LevelProgression(
        level=5,
        experience_required=9600,
        attack_bonus=2,
        saving_throws=THIEF_SAVES_5_6,
        hit_dice="5d4",
    ),
    LevelProgression(
        level=6,
        experience_required=19200,
        attack_bonus=2,
        saving_throws=THIEF_SAVES_5_6,
        hit_dice="6d4",
    ),
    LevelProgression(
        level=7,
        experience_required=38400,
        attack_bonus=3,
        saving_throws=THIEF_SAVES_7_8,
        hit_dice="7d4",
    ),
    LevelProgression(
        level=8,
        experience_required=76800,
        attack_bonus=3,
        saving_throws=THIEF_SAVES_7_8,
        hit_dice="8d4",
    ),
    LevelProgression(
        level=9,
        experience_required=150000,
        attack_bonus=4,
        saving_throws=THIEF_SAVES_9_10,
        hit_dice="9d4",
    ),
    LevelProgression(
        level=10,
        experience_required=270000,
        attack_bonus=4,
        saving_throws=THIEF_SAVES_9_10,
        hit_dice="10d4",
    ),
    LevelProgression(
        level=11,
        experience_required=390000,
        attack_bonus=5,
        saving_throws=THIEF_SAVES_11_12,
        hit_dice="10d4+1",
    ),
    LevelProgression(
        level=12,
        experience_required=510000,
        attack_bonus=5,
        saving_throws=THIEF_SAVES_11_12,
        hit_dice="10d4+2",
    ),
    LevelProgression(
        level=13,
        experience_required=630000,
        attack_bonus=6,
        saving_throws=THIEF_SAVES_13_14,
        hit_dice="10d4+3",
    ),
    LevelProgression(
        level=14,
        experience_required=750000,
        attack_bonus=6,
        saving_throws=THIEF_SAVES_13_14,
        hit_dice="10d4+4",
    ),
    LevelProgression(
        level=15,
        experience_required=870000,
        attack_bonus=7,
        saving_throws=THIEF_SAVES_15,
        hit_dice="10d4+5",
    ),
]


# =============================================================================
# COMPLETE THIEF DEFINITION
# =============================================================================

THIEF_DEFINITION = ClassDefinition(
    class_id="thief",
    name="Thief",
    description=(
        "Inveterate scoundrels, thieves are always on the lookout for their "
        "next mark, scam, or get rich quick scheme. Many thieves are drawn to "
        "a life of adventure, relishing exploration, peril, and the promise "
        "of great wealth."
    ),
    hit_die=HitDie.D4,
    prime_ability="DEX",
    magic_type=MagicType.NONE,
    armor_proficiencies=[
        ArmorProficiency.LIGHT,
        # Note: No shields
    ],
    weapon_proficiencies=[
        WeaponProficiency.SIMPLE,  # Small weapons
        WeaponProficiency.MARTIAL,  # Medium weapons
    ],
    level_progression=THIEF_LEVEL_PROGRESSION,
    abilities=[
        THIEF_BACKSTAB,
        THIEF_SKILLS,
        THIEF_THIEVES_CANT,
    ],
    # No kindred restrictions
    restricted_kindreds=[],
    starting_equipment=[
        # Armour (roll 1d6): 1-3. None. 4-6. Leather.
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): 1. Club. 2. 3 daggers. 3. Longsword.
        # 4. Shortbow + 20 arrows. 5. Shortsword. 6. Sling + 20 stones.
        "weapon_roll_1d6_twice",
        # Class items
        "thieves_tools",
    ],
    extra_data={
        "combat_aptitude": "Semi-martial",
        "armor_restriction": "Light armour only, no shields",
        "weapon_restriction": "Small and Medium weapons",
    },
    source_book="Dolmenwood Player Book",
    source_page=74,
)
