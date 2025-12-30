"""
Fighter class definition for Dolmenwood.

Mercenaries, soldiers, and ruffians who turn their talents to the
adventuring life. Experienced in combat and warfare, whether as brigands,
tavern brawlers, town guards, or veterans of a noble house's army.

Source: Dolmenwood Player Book, pages 64-65
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
# FIGHTER ABILITIES
# =============================================================================

FIGHTER_COMBAT_TALENTS = ClassAbility(
    ability_id="fighter_combat_talents",
    name="Combat Talents",
    description=(
        "Fighters' expert training grants them special talents to aid in battle. "
        "At Levels 2, 6, 10, and 14 the player should roll or choose one talent."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "talent_levels": [2, 6, 10, 14],
        "talents": {
            "battle_rage": {
                "name": "Battle Rage",
                "description": (
                    "When in melee, the fighter can choose to enter a berserk rage "
                    "that lasts until the end of combat. While in the rage, the "
                    "fighter gains a +2 bonus to Attack and Damage Rolls, but "
                    "suffers a –4 penalty to Armour Class and is unable to flee."
                ),
                "attack_bonus": 2,
                "damage_bonus": 2,
                "ac_penalty": -4,
                "cannot_flee": True,
                "duration": "until end of combat",
            },
            "cleave": {
                "name": "Cleave",
                "description": (
                    "When in melee with multiple foes, if the fighter strikes a "
                    "killing blow, they may immediately make another attack against "
                    "a second foe. The second Attack Roll is penalised at –2."
                ),
                "trigger": "killing blow in melee",
                "second_attack_penalty": -2,
            },
            "defender": {
                "name": "Defender",
                "description": (
                    "When the fighter is in melee with a foe, any Attack Rolls the "
                    "foe makes against characters other than the fighter are "
                    "penalised at –2."
                ),
                "foe_attack_penalty_vs_others": -2,
            },
            "last_stand": {
                "name": "Last Stand",
                "description": (
                    "If the fighter is killed by being reduced to 0 Hit Points, "
                    "they can continue to act for up to 5 additional Rounds before "
                    "dying. Each time the fighter suffers further damage during "
                    "this period, they must Save Versus Doom or die. Magical "
                    "healing is effective during this period, but the fighter must "
                    "still Save Versus Doom when damaged, even if healed to above 0 HP."
                ),
                "extra_rounds": 5,
                "save_on_damage": "Doom",
            },
            "leader": {
                "name": "Leader",
                "description": (
                    "Mercenaries or retainers under the fighter's command and "
                    "within 60′ gain a +1 bonus to Morale or Loyalty. All the "
                    "fighter's allies within 60′ gain a +2 bonus to Saving Throws "
                    "against fear effects."
                ),
                "range_feet": 60,
                "retainer_morale_bonus": 1,
                "ally_fear_save_bonus": 2,
            },
            "main_gauche": {
                "name": "Main Gauche",
                "description": (
                    "When fighting with a Small melee weapon (e.g. a dagger or "
                    "hand axe) in the off hand (in place of a shield), the fighter "
                    "may choose each Round to gain either a +1 Armour Class bonus "
                    "or a +1 Attack bonus."
                ),
                "requires": "Small melee weapon in off hand",
                "choice_per_round": ["+1 AC", "+1 Attack"],
            },
            "slayer": {
                "name": "Slayer",
                "description": (
                    "The fighter gains a +1 bonus to Attack and Damage Rolls when "
                    "in combat with foes of a specific type. The type of enemy "
                    "must be chosen when this talent is selected (examples: bears, "
                    "crookhorns, undead, wyrms, etc.). This talent may be chosen "
                    "multiple times, each time for a different type of foe."
                ),
                "attack_bonus": 1,
                "damage_bonus": 1,
                "requires_enemy_type_selection": True,
                "can_select_multiple": True,
            },
            "weapon_specialist": {
                "name": "Weapon Specialist",
                "description": (
                    "The fighter is an expert with a specific type of weapon "
                    "chosen by the player (e.g. maces, two-handed swords, longbows, "
                    "etc.). They gain a +1 bonus to Attack and Damage Rolls using "
                    "this type of weapon. This talent may be chosen multiple times, "
                    "each time for a different type of weapon."
                ),
                "attack_bonus": 1,
                "damage_bonus": 1,
                "requires_weapon_type_selection": True,
                "can_select_multiple": True,
            },
        },
    },
)


# =============================================================================
# FIGHTER LEVEL PROGRESSION
# =============================================================================

# Fighter saving throws (irregular progression - each unique set defined)
FIGHTER_SAVES_1_2 = SavingThrows(doom=12, ray=13, hold=14, blast=15, spell=16)
FIGHTER_SAVES_3 = SavingThrows(doom=11, ray=12, hold=13, blast=14, spell=15)
FIGHTER_SAVES_4_5 = SavingThrows(doom=10, ray=11, hold=12, blast=13, spell=14)
FIGHTER_SAVES_6 = SavingThrows(doom=9, ray=10, hold=11, blast=12, spell=13)
FIGHTER_SAVES_7_8 = SavingThrows(doom=8, ray=9, hold=10, blast=11, spell=12)
FIGHTER_SAVES_9 = SavingThrows(doom=7, ray=8, hold=9, blast=10, spell=11)
FIGHTER_SAVES_10_11 = SavingThrows(doom=6, ray=7, hold=8, blast=9, spell=10)
FIGHTER_SAVES_12 = SavingThrows(doom=5, ray=6, hold=7, blast=8, spell=9)
FIGHTER_SAVES_13_14 = SavingThrows(doom=4, ray=5, hold=6, blast=7, spell=8)
FIGHTER_SAVES_15 = SavingThrows(doom=3, ray=4, hold=5, blast=6, spell=7)

FIGHTER_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=1,
        saving_throws=FIGHTER_SAVES_1_2,
        hit_dice="1d8",
    ),
    LevelProgression(
        level=2,
        experience_required=2000,
        attack_bonus=1,
        saving_throws=FIGHTER_SAVES_1_2,
        hit_dice="2d8",
        abilities_gained=["fighter_combat_talents"],  # First talent
    ),
    LevelProgression(
        level=3,
        experience_required=4000,
        attack_bonus=2,
        saving_throws=FIGHTER_SAVES_3,
        hit_dice="3d8",
    ),
    LevelProgression(
        level=4,
        experience_required=8000,
        attack_bonus=3,
        saving_throws=FIGHTER_SAVES_4_5,
        hit_dice="4d8",
    ),
    LevelProgression(
        level=5,
        experience_required=16000,
        attack_bonus=3,
        saving_throws=FIGHTER_SAVES_4_5,
        hit_dice="5d8",
    ),
    LevelProgression(
        level=6,
        experience_required=32000,
        attack_bonus=4,
        saving_throws=FIGHTER_SAVES_6,
        hit_dice="6d8",
        abilities_gained=["fighter_combat_talents"],  # Second talent
    ),
    LevelProgression(
        level=7,
        experience_required=64000,
        attack_bonus=5,
        saving_throws=FIGHTER_SAVES_7_8,
        hit_dice="7d8",
    ),
    LevelProgression(
        level=8,
        experience_required=128000,
        attack_bonus=5,
        saving_throws=FIGHTER_SAVES_7_8,
        hit_dice="8d8",
    ),
    LevelProgression(
        level=9,
        experience_required=260000,
        attack_bonus=6,
        saving_throws=FIGHTER_SAVES_9,
        hit_dice="9d8",
    ),
    LevelProgression(
        level=10,
        experience_required=380000,
        attack_bonus=7,
        saving_throws=FIGHTER_SAVES_10_11,
        hit_dice="10d8",
        abilities_gained=["fighter_combat_talents"],  # Third talent
    ),
    LevelProgression(
        level=11,
        experience_required=500000,
        attack_bonus=7,
        saving_throws=FIGHTER_SAVES_10_11,
        hit_dice="10d8+2",
    ),
    LevelProgression(
        level=12,
        experience_required=620000,
        attack_bonus=8,
        saving_throws=FIGHTER_SAVES_12,
        hit_dice="10d8+4",
    ),
    LevelProgression(
        level=13,
        experience_required=740000,
        attack_bonus=9,
        saving_throws=FIGHTER_SAVES_13_14,
        hit_dice="10d8+6",
    ),
    LevelProgression(
        level=14,
        experience_required=860000,
        attack_bonus=9,
        saving_throws=FIGHTER_SAVES_13_14,
        hit_dice="10d8+8",
        abilities_gained=["fighter_combat_talents"],  # Fourth talent
    ),
    LevelProgression(
        level=15,
        experience_required=980000,
        attack_bonus=10,
        saving_throws=FIGHTER_SAVES_15,
        hit_dice="10d8+10",
    ),
]


# =============================================================================
# COMPLETE FIGHTER DEFINITION
# =============================================================================

FIGHTER_DEFINITION = ClassDefinition(
    class_id="fighter",
    name="Fighter",
    description=(
        "Fighters are experienced in combat and warfare, whether as brigands, "
        "tavern brawlers, town guards, or veterans of a noble house's army. "
        "In an adventuring party, fighters usually take the front-line, "
        "battling foes and defending weaker characters."
    ),
    hit_die=HitDie.D8,
    prime_ability="STR",
    magic_type=MagicType.NONE,
    armor_proficiencies=[
        ArmorProficiency.ALL,
        ArmorProficiency.SHIELDS,
    ],
    weapon_proficiencies=[
        WeaponProficiency.ALL,
    ],
    level_progression=FIGHTER_LEVEL_PROGRESSION,
    abilities=[
        FIGHTER_COMBAT_TALENTS,
    ],
    # No kindred restrictions - any kindred can be a fighter
    restricted_kindreds=[],
    starting_equipment=[
        # Armour (roll 1d6): 1. Leather armour. 2. Leather armour + shield.
        # 3. Chainmail. 4. Chainmail + shield. 5. Plate mail. 6. Plate mail + shield.
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): 1. Crossbow + 20 quarrels. 2. Dagger.
        # 3. Longsword. 4. Mace. 5. Shortsword. 6. Spear.
        "weapon_roll_1d6_twice",
    ],
    extra_data={
        "combat_aptitude": "Martial",
    },
    source_book="Dolmenwood Player Book",
    source_page=64,
)
