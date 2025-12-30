"""
Knight class definition for Dolmenwood.

Warriors who serve a noble, doing their bidding and upholding their honour.
Masters of heavily armoured, mounted combat and, as vassals of a noble house,
hold a special rank in society.

Source: Dolmenwood Player Book, pages 70-71
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
# KNIGHT ABILITIES
# =============================================================================

KNIGHT_CHIVALRIC_CODE = ClassAbility(
    ability_id="knight_chivalric_code",
    name="Chivalric Code",
    description=(
        "Knights strive to uphold a stringent code of honour which binds all "
        "decision and deed. The repercussions of performing acts at odds with "
        "the code depend on the Alignment of the knight and their liege."
    ),
    is_passive=True,
    extra_data={
        "code": {
            "honour": (
                "A knight must behave honourably in all deeds. A knight's honour "
                "is of utmost importance. Death is preferable to dishonour."
            ),
            "service": "Service to one's liege is the greatest honour.",
            "glory": ("A knight must seek glory in battle—especially in single combat."),
            "protecting_the_weak": (
                "Any person in the knight's charge must be defended to the death."
            ),
            "hierarchy": (
                "The hierarchy that binds society is to be upheld. Superiors must "
                "be honoured, equals respected, inferiors commanded, and the "
                "ignoble scorned."
            ),
        },
        "consequences_by_alignment": {
            "lawful_or_neutral": (
                "The knight brings dishonour upon their liege, thus risking Disfavour."
            ),
            "chaotic": (
                "The knight is unlikely to bring dishonour upon their liege, whose "
                "reputation is already villainous. Unchivalrous deeds are, however, "
                "perceived as besmirching the institution of knighthood. Other "
                "knights hunt the Chaotic knight and attempt to bring them to justice."
            ),
        },
    },
)

KNIGHT_HORSEMANSHIP = ClassAbility(
    ability_id="knight_horsemanship",
    name="Horsemanship",
    description=(
        "Knights are expert riders. They can assess the worth of any steed and, "
        "from Level 5, can urge their steed to great haste."
    ),
    is_passive=True,
    scales_with_level=True,
    extra_data={
        "assess_steeds": (
            "Determine whether an animal has low, average, or high Hit Points " "for its type."
        ),
        "urge_great_speed": {
            "min_level": 5,
            "uses_per_day": 1,
            "speed_bonus": 10,
            "duration": "up to 6 Turns",
        },
    },
)

KNIGHT_KNIGHTHOOD = ClassAbility(
    ability_id="knight_knighthood",
    name="Knighthood",
    description=(
        "Knights of Levels 1–2 are known as squires and are not yet regarded as "
        "true knights. Upon reaching Level 3, the character is knighted by their "
        "liege and gains the right to bear a coat of arms."
    ),
    min_level=3,
    is_passive=True,
    extra_data={
        "squire_levels": [1, 2],
        "knighted_at": 3,
        "coat_of_arms": "Typically emblazoned upon the knight's shield",
        "hospitality": (
            "Once knighted, the character earns rights of hospitality and aid "
            "from nobles and other knights of the same Alignment. Hospitality "
            "extends to any companions the knight is willing to vouch for. "
            "The knight is expected to extend such hospitality in kind."
        ),
    },
)

KNIGHT_MONSTER_SLAYER = ClassAbility(
    ability_id="knight_monster_slayer",
    name="Monster Slayer",
    description=(
        "From Level 5, a knight gains a +2 bonus to Attack and Damage Rolls "
        "against Large creatures."
    ),
    min_level=5,
    is_passive=True,
    extra_data={
        "attack_bonus": 2,
        "damage_bonus": 2,
        "applies_to": "Large creatures",
    },
)

KNIGHT_MOUNTED_COMBAT = ClassAbility(
    ability_id="knight_mounted_combat",
    name="Mounted Combat",
    description=("Knights gain a +1 Attack bonus when mounted."),
    is_passive=True,
    extra_data={
        "mounted_attack_bonus": 1,
    },
)

KNIGHT_STRENGTH_OF_WILL = ClassAbility(
    ability_id="knight_strength_of_will",
    name="Strength of Will",
    description=(
        "Knights gain a +2 bonus to Saving Throws against fairy magic and "
        "effects that cause fear."
    ),
    is_passive=True,
    extra_data={
        "save_bonus": 2,
        "applies_to": ["fairy magic", "fear effects"],
    },
)


# =============================================================================
# KNIGHT LEVEL PROGRESSION
# =============================================================================

# Knight saving throws (unique - Hold equals Doom, irregular progression)
KNIGHT_SAVES_1_2 = SavingThrows(doom=12, ray=13, hold=12, blast=15, spell=15)
KNIGHT_SAVES_3 = SavingThrows(doom=11, ray=12, hold=11, blast=14, spell=14)
KNIGHT_SAVES_4_5 = SavingThrows(doom=10, ray=11, hold=10, blast=13, spell=13)
KNIGHT_SAVES_6 = SavingThrows(doom=9, ray=10, hold=9, blast=12, spell=12)
KNIGHT_SAVES_7_8 = SavingThrows(doom=8, ray=9, hold=8, blast=11, spell=11)
KNIGHT_SAVES_9 = SavingThrows(doom=7, ray=8, hold=7, blast=10, spell=10)
KNIGHT_SAVES_10_11 = SavingThrows(doom=6, ray=7, hold=6, blast=9, spell=9)
KNIGHT_SAVES_12 = SavingThrows(doom=5, ray=6, hold=5, blast=8, spell=8)
KNIGHT_SAVES_13_14 = SavingThrows(doom=4, ray=5, hold=4, blast=7, spell=7)
KNIGHT_SAVES_15 = SavingThrows(doom=3, ray=4, hold=3, blast=6, spell=6)

KNIGHT_LEVEL_PROGRESSION = [
    LevelProgression(
        level=1,
        experience_required=0,
        attack_bonus=1,
        saving_throws=KNIGHT_SAVES_1_2,
        hit_dice="1d8",
    ),
    LevelProgression(
        level=2,
        experience_required=2250,
        attack_bonus=1,
        saving_throws=KNIGHT_SAVES_1_2,
        hit_dice="2d8",
    ),
    LevelProgression(
        level=3,
        experience_required=4500,
        attack_bonus=2,
        saving_throws=KNIGHT_SAVES_3,
        hit_dice="3d8",
        abilities_gained=["knight_knighthood"],
    ),
    LevelProgression(
        level=4,
        experience_required=9000,
        attack_bonus=3,
        saving_throws=KNIGHT_SAVES_4_5,
        hit_dice="4d8",
    ),
    LevelProgression(
        level=5,
        experience_required=18000,
        attack_bonus=3,
        saving_throws=KNIGHT_SAVES_4_5,
        hit_dice="5d8",
        abilities_gained=["knight_monster_slayer"],
    ),
    LevelProgression(
        level=6,
        experience_required=36000,
        attack_bonus=4,
        saving_throws=KNIGHT_SAVES_6,
        hit_dice="6d8",
    ),
    LevelProgression(
        level=7,
        experience_required=72000,
        attack_bonus=5,
        saving_throws=KNIGHT_SAVES_7_8,
        hit_dice="7d8",
    ),
    LevelProgression(
        level=8,
        experience_required=144000,
        attack_bonus=5,
        saving_throws=KNIGHT_SAVES_7_8,
        hit_dice="8d8",
    ),
    LevelProgression(
        level=9,
        experience_required=290000,
        attack_bonus=6,
        saving_throws=KNIGHT_SAVES_9,
        hit_dice="9d8",
    ),
    LevelProgression(
        level=10,
        experience_required=420000,
        attack_bonus=7,
        saving_throws=KNIGHT_SAVES_10_11,
        hit_dice="10d8",
    ),
    LevelProgression(
        level=11,
        experience_required=550000,
        attack_bonus=7,
        saving_throws=KNIGHT_SAVES_10_11,
        hit_dice="10d8+2",
    ),
    LevelProgression(
        level=12,
        experience_required=680000,
        attack_bonus=8,
        saving_throws=KNIGHT_SAVES_12,
        hit_dice="10d8+4",
    ),
    LevelProgression(
        level=13,
        experience_required=810000,
        attack_bonus=9,
        saving_throws=KNIGHT_SAVES_13_14,
        hit_dice="10d8+6",
    ),
    LevelProgression(
        level=14,
        experience_required=940000,
        attack_bonus=9,
        saving_throws=KNIGHT_SAVES_13_14,
        hit_dice="10d8+8",
    ),
    LevelProgression(
        level=15,
        experience_required=1070000,
        attack_bonus=10,
        saving_throws=KNIGHT_SAVES_15,
        hit_dice="10d8+10",
    ),
]


# =============================================================================
# COMPLETE KNIGHT DEFINITION
# =============================================================================

KNIGHT_DEFINITION = ClassDefinition(
    class_id="knight",
    name="Knight",
    description=(
        "Knights are masters of heavily armoured, mounted combat and, as vassals "
        "of a noble house, hold a special rank in society. Knights earn great "
        "respect from the common folk and exemplify the qualities of nobility, "
        "honour, and decency in all their deeds. Player Character knights are "
        "typically knights-errant—those who wander the land in pursuit of "
        "adventure to prove their chivalric virtues."
    ),
    hit_die=HitDie.D8,
    prime_ability="CHA,STR",  # Dual prime abilities
    magic_type=MagicType.NONE,
    armor_proficiencies=[
        ArmorProficiency.MEDIUM,
        ArmorProficiency.HEAVY,
        ArmorProficiency.SHIELDS,
        # Note: Knights scorn Light armour as suitable only for peasants
    ],
    weapon_proficiencies=[
        WeaponProficiency.MARTIAL,  # Melee weapons only
        # Note: Knights CANNOT use missile weapons (dishonourable)
    ],
    level_progression=KNIGHT_LEVEL_PROGRESSION,
    abilities=[
        KNIGHT_CHIVALRIC_CODE,
        KNIGHT_HORSEMANSHIP,
        KNIGHT_KNIGHTHOOD,
        KNIGHT_MONSTER_SLAYER,
        KNIGHT_MOUNTED_COMBAT,
        KNIGHT_STRENGTH_OF_WILL,
    ],
    # Typically humans and breggles, uncommon for other kindreds
    restricted_kindreds=["elf", "grimalkin", "woodgrue", "mossling"],
    starting_equipment=[
        # Armour (roll 1d6): 1. Chainmail. 2–3. Chainmail + shield.
        # 4. Plate mail. 5–6. Plate mail + shield.
        "armor_roll_1d6",
        # Weapons (roll 1d6 twice): 1. Dagger. 2–4. Lance (spear for Small).
        # 5. Longsword. 6. Mace.
        "weapon_roll_1d6_twice",
    ],
    extra_data={
        "combat_aptitude": "Martial",
        "alignment_restriction": "Must match liege's Alignment",
        "weapon_restriction": (
            "Knights can use all melee weapons (preferring the lance) but "
            "cannot use missile weapons, which they regard as dishonourable."
        ),
        "armour_preference": (
            "Knights regard armour as a symbol of prowess and status, always "
            "favouring the most impressive and impervious-looking armour "
            "available. They scorn Light armour as suitable only for peasants "
            "and villains."
        ),
        "liege": {
            "description": (
                "A knight serves one of the lower noble houses of Dolmenwood. "
                "Knighthood may be revoked if a knight displeases or dishonours "
                "their liege. In this case, the character becomes a fighter of "
                "equivalent Level."
            ),
            "houses": {
                "house_guillefer": {
                    "name": "House Guillefer",
                    "alignment": "Neutral",
                    "trait": "Dreamy and aloof",
                    "ruler": "Lord Edwin Guillefer (rotating rulership)",
                },
                "house_harrowmoor": {
                    "name": "House Harrowmoor",
                    "alignment": "Lawful",
                    "trait": "Steadfast and militant",
                    "ruler": "Lady Theatrice Harrowmoor",
                },
                "house_hogwarsh": {
                    "name": "House Hogwarsh",
                    "alignment": "Neutral",
                    "trait": "Lax and debauched",
                    "ruler": "Baron Sagewine Hogwarsh",
                },
                "house_malbleat": {
                    "name": "House Malbleat",
                    "alignment": "Chaotic",
                    "trait": "Conniving and tyrannical",
                    "ruler": "Lord Gryphius Malbleat",
                    "note": "Ancient breggle noble house",
                },
                "house_mulbreck": {
                    "name": "House Mulbreck",
                    "alignment": "Lawful",
                    "trait": "Reclusive and detached",
                    "ruler": "Lady Pulsephine Mulbreck",
                },
                "house_murkin": {
                    "name": "House Murkin",
                    "alignment": "Chaotic",
                    "trait": "Belligerent and ambitious",
                    "ruler": "Lord Simeone Murkin",
                    "note": "Ancient breggle noble house",
                },
                "house_nodlock": {
                    "name": "House Nodlock",
                    "alignment": "Neutral",
                    "trait": "Bombastic and decaying",
                    "ruler": "Lord Harald Nodlock",
                },
                "house_ramius": {
                    "name": "House Ramius",
                    "alignment": "Neutral",
                    "trait": "Dignified and shrewd",
                    "ruler": "Lord Shadgore Ramius",
                    "note": "Ancient breggle noble house",
                },
            },
        },
        "small_character_note": (
            "Small characters receive spear instead of lance for starting " "equipment roll 2-4."
        ),
    },
    source_book="Dolmenwood Player Book",
    source_page=70,
)
