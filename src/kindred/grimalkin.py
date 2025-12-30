"""
Grimalkin kindred definition for Dolmenwood.

Mercurial feline fairies who shift between three different forms.
Source: Dolmenwood Player Book, pages 40-43
"""

from src.kindred.kindred_data import (
    AspectTable,
    AspectTableEntry,
    AspectType,
    DiceFormula,
    KindredAbility,
    KindredDefinition,
    KindredType,
    NameColumn,
    NameTable,
    PhysicalRanges,
)


# =============================================================================
# GRIMALKIN ABILITIES
# =============================================================================

GRIMALKIN_SKILLS_ABILITY = KindredAbility(
    ability_id="grimalkin_skills",
    name="Grimalkin Skills",
    description="Grimalkins have a Skill Target of 5 for Listen.",
    is_passive=True,
    extra_data={
        "skill_targets": {
            "listen": 5,
        }
    },
)

GRIMALKIN_GLAMOURS_ABILITY = KindredAbility(
    ability_id="grimalkin_glamours",
    name="Glamours",
    description=(
        "Grimalkins possess minor magical talents known as glamours. "
        "Each grimalkin knows a single, randomly determined glamour."
    ),
    is_passive=False,
    extra_data={
        "glamour_count": 1,
        "randomly_determined": True,
        "spell_type": "fairy_glamour",
        "spell_source": "data/content/spells/glamours.json",
    },
)

GRIMALKIN_IMMORTALITY_ABILITY = KindredAbility(
    ability_id="grimalkin_immortality",
    name="Immortality",
    description=(
        "Grimalkins can be killed but do not die naturally. They are immune to "
        "diseases of non-magical origin. Grimalkins also cannot die of thirst or "
        "starvation, though a lack of sustenance drives them desperate and sadistic."
    ),
    is_passive=True,
    extra_data={
        "immune_to": ["natural_death", "non_magical_disease", "starvation", "thirst"],
        "starvation_effect": "becomes desperate and sadistic",
    },
)

GRIMALKIN_MAGIC_RESISTANCE_ABILITY = KindredAbility(
    ability_id="grimalkin_magic_resistance",
    name="Magic Resistance",
    description=(
        "As beings of Fairy, where magic is in the very fabric of things, "
        "grimalkins are highly resistant to magic. They gain +2 Magic Resistance."
    ),
    is_passive=True,
    extra_data={
        "magic_resistance_bonus": 2,
    },
)

GRIMALKIN_SHAPE_SHIFTING_ABILITY = KindredAbility(
    ability_id="grimalkin_shape_shifting",
    name="Shape-Shifting",
    description=(
        "A grimalkin can spend 1 Round to transform into either a fat domestic cat "
        "(chester) or a primal fey form (wilder). When transformed, a grimalkin "
        "cannot use weapons, magic, or any special Class capabilities. All gear "
        "carried is optionally transformed with the character."
    ),
    is_passive=False,
    extra_data={
        "forms": {
            "estray": {
                "description": "Humanoid cat form, normal form",
                "can_use_weapons": True,
                "can_use_magic": True,
            },
            "chester": {
                "description": "Fat domestic cat form",
                "usage": "unlimited",
                "ac": 12,
                "speed": 30,
                "attacks": ["bite (1 damage)", "claw (1 damage)", "claw (1 damage)"],
                "can_understand_language": True,
                "can_speak": False,
                "change_back_condition": "unobserved by any sentient being",
            },
            "wilder": {
                "description": "Primal fey predator form",
                "usage": "once_per_day",
                "entry_condition": "in melee and below half maximum HP",
                "on_entry_heal": "2d6",
                "ac": 13,
                "speed": 30,
                "attacks": ["bite +2 (1d4)", "claw +2 (1d4)", "claw +2 (1d4)"],
                "near_invisible": True,
                "opponent_attack_penalty": -2,
                "fey_chaos": "cannot distinguish friend from foe",
                "duration": "2d4 rounds",
            },
        },
    },
)

GRIMALKIN_DEFENSIVE_BONUS_ABILITY = KindredAbility(
    ability_id="grimalkin_defensive_bonus",
    name="Defensive Bonus",
    description=(
        "In melee with Large creatures, grimalkins gain a +2 Armour Class bonus, "
        "due to their small size."
    ),
    is_passive=True,
    extra_data={
        "ac_bonus": 2,
        "condition": "in melee with Large creatures",
    },
)

GRIMALKIN_EATING_RODENTS_ABILITY = KindredAbility(
    ability_id="grimalkin_eating_rodents",
    name="Eating Giant Rodents",
    description=(
        "After spending 1 Turn devouring a freshly killed giant rodent, "
        "a grimalkin heals 1 Hit Point."
    ),
    is_passive=False,
    extra_data={
        "healing": 1,
        "duration": "1 Turn",
        "target": "freshly killed giant rodent",
    },
)

GRIMALKIN_COLD_IRON_VULNERABILITY_ABILITY = KindredAbility(
    ability_id="grimalkin_cold_iron_vulnerability",
    name="Vulnerable to Cold Iron",
    description=(
        "As fairies, cold iron weapons inflict +1 damage on grimalkins. "
        "(e.g. a cold iron shortsword would inflict 1d6+1 damage on a grimalkin, "
        "rather than the standard 1d6)."
    ),
    is_passive=True,
    extra_data={
        "cold_iron_extra_damage": 1,
        "is_vulnerability": True,
    },
)


# =============================================================================
# GRIMALKIN NAME TABLE
# =============================================================================

# Grimalkin names are mostly non-gendered. Some have male/female variants
# (Jack/Jill, Lord/Lady, etc.) but we'll treat all as unisex for simplicity.
GRIMALKIN_NAME_TABLE = NameTable(
    columns={
        NameColumn.UNISEX: [
            "Boots",
            "Fripple",
            "Ginger",
            "Jack",
            "Jill",
            "Jaspy",
            "Jasqueline",
            "Kitty",
            "Little",
            "Lord",
            "Lady",
            "Mogget",
            "Moggle",
            "Monsieur",
            "Madame",
            "Nibbles",
            "Penny",
            "Poppet",
            "Prince",
            "Princess",
            "Prissy",
            "Tippsy",
            "Tomkin",
            "Toppsy",
        ],
        NameColumn.SURNAME: [
            "Bobblewhisk",
            "Cottonsocks",
            "Flip-a-tail",
            "Flippancy",
            "Fluff-a-kin",
            "Grimalgrime",
            "Grinser",
            "Lickling",
            "Milktongue",
            "Mogglin",
            "Poppletail",
            "Pouncemouse",
            "Pusskin",
            "Ratbane",
            "Snuffle",
            "Tailwhisk",
            "Tippler",
            "Whippletongue",
            "Whipsy",
            "Whiskers",
        ],
    }
)


# =============================================================================
# GRIMALKIN ASPECT TABLES
# =============================================================================

GRIMALKIN_BACKGROUND_TABLE = AspectTable(
    aspect_type=AspectType.BACKGROUND,
    die_size=20,
    entries=[
        AspectTableEntry(1, 1, "Alchemist's aide"),
        AspectTableEntry(2, 2, "Angler"),
        AspectTableEntry(3, 3, "Barber"),
        AspectTableEntry(4, 4, "Card-sharp"),
        AspectTableEntry(5, 5, "Catnip brewer"),
        AspectTableEntry(6, 6, "Clothier"),
        AspectTableEntry(7, 7, "Duellist"),
        AspectTableEntry(8, 8, "Highway robber"),
        AspectTableEntry(9, 9, "Knifemaker"),
        AspectTableEntry(10, 10, "Libertine"),
        AspectTableEntry(11, 11, "Mariner"),
        AspectTableEntry(12, 12, "Pheasant poacher"),
        AspectTableEntry(13, 13, "Rat hunter"),
        AspectTableEntry(14, 14, "Spy"),
        AspectTableEntry(15, 15, "Stage magician"),
        AspectTableEntry(16, 16, "Swindler"),
        AspectTableEntry(17, 17, "Thespian"),
        AspectTableEntry(18, 18, "Trapper / furrier"),
        AspectTableEntry(19, 19, "Vole farmer"),
        AspectTableEntry(20, 20, "Weasel tamer"),
    ],
)

GRIMALKIN_HEAD_TABLE = AspectTable(
    aspect_type=AspectType.HEAD,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Carefully sculpted quiff"),
        AspectTableEntry(2, 2, "Dapper top hat"),
        AspectTableEntry(3, 3, "Extravagant ear fur"),
        AspectTableEntry(4, 4, "Floppy beret"),
        AspectTableEntry(5, 5, "Floppy ear"),
        AspectTableEntry(6, 6, "Jaunty tricorn hat"),
        AspectTableEntry(7, 7, "Plumed hat"),
        AspectTableEntry(8, 8, "Pointy ear tufts"),
        AspectTableEntry(9, 9, "Shaggy mane"),
        AspectTableEntry(10, 10, "Spotted headscarf"),
        AspectTableEntry(11, 11, "Torn ear"),
        AspectTableEntry(12, 12, "Unrealistically large"),
    ],
)

GRIMALKIN_DEMEANOUR_TABLE = AspectTable(
    aspect_type=AspectType.DEMEANOUR,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Boastful"),
        AspectTableEntry(2, 2, "Fastidious and precise"),
        AspectTableEntry(3, 3, "Irreverently jocund"),
        AspectTableEntry(4, 4, "Jittery and on edge"),
        AspectTableEntry(5, 5, "Loose with money"),
        AspectTableEntry(6, 6, "Mercurial"),
        AspectTableEntry(7, 7, "Reckless swashbuckler"),
        AspectTableEntry(8, 8, "Self-indulgent preening"),
        AspectTableEntry(9, 9, "Slumbersome"),
        AspectTableEntry(10, 10, "Sneaky and larcenous"),
        AspectTableEntry(11, 11, "Snobbish gourmet"),
        AspectTableEntry(12, 12, "Tipsy and frolicsome"),
    ],
)

GRIMALKIN_DESIRES_TABLE = AspectTable(
    aspect_type=AspectType.DESIRES,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Become a crime lord"),
        AspectTableEntry(2, 2, "Become fat eating rodents"),
        AspectTableEntry(3, 3, "Build a secret palace"),
        AspectTableEntry(4, 4, "Build a sky ship to the moon"),
        AspectTableEntry(5, 5, "Commune with lost cat gods"),
        AspectTableEntry(6, 6, "Fame as a slayer of monsters"),
        AspectTableEntry(7, 7, "Found a catnip distillery"),
        AspectTableEntry(8, 8, "Infamy as a supreme gambler"),
        AspectTableEntry(9, 9, "Inhabit Hoarblight Keep"),
        AspectTableEntry(10, 10, "Live in exorbitant luxury"),
        AspectTableEntry(11, 11, "Marry into human nobility"),
        AspectTableEntry(12, 12, "Steal the duke's jewels"),
    ],
)

GRIMALKIN_FACE_TABLE = AspectTable(
    aspect_type=AspectType.FACE,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Bug-eyed"),
        AspectTableEntry(2, 2, "Constantly looks surprised"),
        AspectTableEntry(3, 3, "Copper, saucer-like eyes"),
        AspectTableEntry(4, 4, "Extra fluffy cheeks"),
        AspectTableEntry(5, 5, "Extravagantly long whiskers"),
        AspectTableEntry(6, 6, "Flabby jowls"),
        AspectTableEntry(7, 7, "Flashing silver eyes"),
        AspectTableEntry(8, 8, "Long, pointy snout"),
        AspectTableEntry(9, 9, "Mostly mouth"),
        AspectTableEntry(10, 10, "Snaggle-toothed"),
        AspectTableEntry(11, 11, "Snub nose"),
        AspectTableEntry(12, 12, "Tongue pokes out"),
    ],
)

GRIMALKIN_DRESS_TABLE = AspectTable(
    aspect_type=AspectType.DRESS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Cape and spurs"),
        AspectTableEntry(2, 2, "Dandyish lace and silks"),
        AspectTableEntry(3, 3, "Festooned with rat bones"),
        AspectTableEntry(4, 4, "Jet black woollens"),
        AspectTableEntry(5, 5, "Long gloves and chaps"),
        AspectTableEntry(6, 6, "Long, colourful knitted scarf"),
        AspectTableEntry(7, 7, "Pied doublet and breeches"),
        AspectTableEntry(8, 8, "Ratskin vest and breeches"),
        AspectTableEntry(9, 9, "Regal ermine cloak"),
        AspectTableEntry(10, 10, "Shiny red boots"),
        AspectTableEntry(11, 11, "Smart tweed"),
        AspectTableEntry(12, 12, "Tassels and fringes"),
    ],
)

GRIMALKIN_BELIEFS_TABLE = AspectTable(
    aspect_type=AspectType.BELIEFS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Catnip is poison to humans"),
        AspectTableEntry(2, 2, "Consume mouse-flesh daily"),
        AspectTableEntry(3, 3, "Dreams are the true reality"),
        AspectTableEntry(4, 4, "Evil rat realm underground"),
        AspectTableEntry(5, 5, "Human nobles serve Catland"),
        AspectTableEntry(6, 6, "Magic is fading"),
        AspectTableEntry(7, 7, "Only eat raw meat"),
        AspectTableEntry(8, 8, "The Cold Prince is long dead"),
        AspectTableEntry(9, 9, "The moon is ruled by mice"),
        AspectTableEntry(10, 10, "The Nag-Lord adores cats"),
        AspectTableEntry(11, 11, "Vegetables harm the health"),
        AspectTableEntry(12, 12, "War is brewing in Fairy"),
    ],
)

GRIMALKIN_FUR_TABLE = AspectTable(
    aspect_type=AspectType.FUR_BODY,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Black"),
        AspectTableEntry(2, 2, "Black and white"),
        AspectTableEntry(3, 3, "Blue"),
        AspectTableEntry(4, 4, "Brown tabby"),
        AspectTableEntry(5, 5, "Chocolate"),
        AspectTableEntry(6, 6, "Ginger tabby"),
        AspectTableEntry(7, 7, "Iridescent"),
        AspectTableEntry(8, 8, "Silver, fluffy"),
        AspectTableEntry(9, 9, "Tortoiseshell"),
        AspectTableEntry(10, 10, "Violet"),
        AspectTableEntry(11, 11, "White, spiky"),
        AspectTableEntry(12, 12, "White, fluffy"),
    ],
)

GRIMALKIN_SPEECH_TABLE = AspectTable(
    aspect_type=AspectType.SPEECH,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Adorable mewling"),
        AspectTableEntry(2, 2, "Conspiratorial whispering"),
        AspectTableEntry(3, 3, "Decadently fashionable"),
        AspectTableEntry(4, 4, "Eloquent and poetic"),
        AspectTableEntry(5, 5, "Impertinent"),
        AspectTableEntry(6, 6, "Languid"),
        AspectTableEntry(7, 7, "Manic"),
        AspectTableEntry(8, 8, "Meandering"),
        AspectTableEntry(9, 9, "Mirthful and mocking"),
        AspectTableEntry(10, 10, "Purring"),
        AspectTableEntry(11, 11, "Sycophantic"),
        AspectTableEntry(12, 12, "Wilfully abstruse"),
    ],
)

# Trinket table - references item IDs in adventuring_gear_grimalkin_trinkets.json
GRIMALKIN_TRINKET_TABLE = AspectTable(
    aspect_type=AspectType.TRINKET,
    die_size=100,
    entries=[
        AspectTableEntry(
            1,
            2,
            "A bicorne hat that is a foot deeper on the inside than it appears",
            item_id="bicorne_hat",
        ),
        AspectTableEntry(
            3,
            4,
            "A book of long-forgotten laws, written in Old Woldish",
            item_id="book_old_woldish_laws",
        ),
        AspectTableEntry(
            5,
            6,
            "A brass thimble that turns water into milk",
            item_id="brass_thimble_water_to_milk",
        ),
        AspectTableEntry(7, 8, "A breggle tongue, still moist", item_id="breggle_tongue"),
        AspectTableEntry(
            9,
            10,
            "A cherry tart pilfered from the kitchen of a fairy noble",
            item_id="cherry_tart_fairy_noble",
        ),
        AspectTableEntry(
            11, 12, "A cloak fashioned from a hundred voles", item_id="cloak_hundred_voles"
        ),
        AspectTableEntry(
            13,
            14,
            "A copper coin that always lands on the same side when deliberately flipped",
            item_id="copper_coin_same_side",
        ),
        AspectTableEntry(
            15,
            16,
            "A crimson feather from an enormous bird",
            item_id="crimson_feather_enormous_bird",
        ),
        AspectTableEntry(17, 18, "A dead crow that never rots", item_id="dead_crow_never_rots"),
        AspectTableEntry(
            19,
            20,
            "A deck of playing cards that shuffles itself when left unattended",
            item_id="self_shuffling_cards",
        ),
        AspectTableEntry(
            21, 22, "A dried heart the size of an acorn", item_id="dried_heart_acorn_size"
        ),
        AspectTableEntry(
            23,
            24,
            "A hairball coughed up by a famous grimalkin",
            item_id="famous_grimalkin_hairball",
        ),
        AspectTableEntry(
            25,
            26,
            "A handkerchief stained with the kiss of Queen Abyssinia",
            item_id="handkerchief_queen_abyssinia_kiss",
        ),
        AspectTableEntry(
            27,
            28,
            "A heart-shaped locket that contains a portrait of a different cat each time it's opened",
            item_id="heart_shaped_locket_cat_portraits",
        ),
        AspectTableEntry(
            29,
            30,
            "A human eye that dilates just before it rains",
            item_id="human_eye_rain_predictor",
        ),
        AspectTableEntry(
            31,
            32,
            "A hundred-year-old note offering a favour from a witch, her descendants might be obligated to fulfil it",
            item_id="witch_favor_note",
        ),
        AspectTableEntry(
            33,
            34,
            "A leaf from the tallest tree in Dolmenwood",
            item_id="leaf_tallest_tree_dolmenwood",
        ),
        AspectTableEntry(
            35,
            36,
            "A letter begging you to aid a miller's youngest child",
            item_id="letter_miller_child_aid",
        ),
        AspectTableEntry(
            37,
            38,
            "A live cockroach tied to a thin gold string, if removed or killed a new one appears at sunrise",
            item_id="cockroach_gold_string",
        ),
        AspectTableEntry(39, 40, "A lucky tortoise shell", item_id="lucky_tortoise_shell"),
        AspectTableEntry(
            41,
            42,
            "A lute that is always out of tune in the morning and in tune in the evening",
            item_id="lute_tune_cycle",
        ),
        AspectTableEntry(
            43, 44, "A luxurious, gold-embroidered cushion", item_id="gold_embroidered_cushion"
        ),
        AspectTableEntry(
            45,
            46,
            "A mouse skull on a string, allegedly a mouse from the moon",
            item_id="mouse_skull_moon",
        ),
        AspectTableEntry(
            47,
            48,
            "A mushroom stolen from the head of a mossling",
            item_id="mushroom_mossling_head",
        ),
        AspectTableEntry(
            49, 50, "A nightingale's song, trapped in a locket", item_id="nightingale_song_locket"
        ),
        AspectTableEntry(
            51, 52, "A pair of boots that will never go out of fashion", item_id="fashionable_boots"
        ),
        AspectTableEntry(
            53,
            54,
            "A pair of dice that, when rolled together, always total to nine",
            item_id="dice_always_nine",
        ),
        AspectTableEntry(
            55,
            56,
            "A pink bow that cannot turn invisible under any circumstances",
            item_id="pink_bow_never_invisible",
        ),
        AspectTableEntry(
            57,
            58,
            "A pocket watch that always tells you the correct time an hour ago",
            item_id="pocket_watch_hour_ago",
        ),
        AspectTableEntry(
            59,
            60,
            "A porcelain teacup with a salamander painted on the side, warm liquids it holds never cool down",
            item_id="porcelain_teacup_salamander",
        ),
        AspectTableEntry(
            61, 62, "A rabbit's foot that sporadically twitches", item_id="twitching_rabbit_foot"
        ),
        AspectTableEntry(
            63,
            64,
            "A rat king in a sack, each rat inside claims to be the 'King of All Rats'",
            item_id="rat_king_sack",
        ),
        AspectTableEntry(65, 66, "A realistic mask of a human child", item_id="human_child_mask"),
        AspectTableEntry(
            67,
            68,
            "A scroll depicting your royal lineage, of dubious authenticity",
            item_id="royal_lineage_scroll",
        ),
        AspectTableEntry(
            69,
            70,
            "A set of keys on a golden ring, purloined from a noble",
            item_id="noble_keys_golden_ring",
        ),
        AspectTableEntry(
            71, 72, "A severed head of a sprite, dried and preserved", item_id="severed_sprite_head"
        ),
        AspectTableEntry(
            73,
            74,
            "A sewing needle, sized for a giant (treat as a dagger)",
            item_id="giant_sewing_needle",
        ),
        AspectTableEntry(
            75,
            76,
            "A shard of cold iron, trapped in a glass sphere",
            item_id="cold_iron_shard_sphere",
        ),
        AspectTableEntry(
            77,
            78,
            "A single cat whisker, given to you as a sign of commitment",
            item_id="cat_whisker_commitment",
        ),
        AspectTableEntry(
            79, 80, "A singular pipe, taken from a woodgrue's pan flute", item_id="woodgrue_pipe"
        ),
        AspectTableEntry(
            81,
            82,
            "A small vial containing a legendarily potent strain of catnip",
            item_id="potent_catnip_vial",
        ),
        AspectTableEntry(83, 84, "A tiny bell that makes no sound", item_id="silent_bell"),
        AspectTableEntry(
            85, 86, "A trained, but not particularly smart, weasel", item_id="trained_weasel"
        ),
        AspectTableEntry(
            87, 88, "A whistle that only dogs can't hear", item_id="whistle_dogs_cant_hear"
        ),
        AspectTableEntry(
            89,
            90,
            "A wolf's paw that bleeds when the wolf is thinking of you",
            item_id="wolf_paw_bleeding",
        ),
        AspectTableEntry(
            91, 92, "A wooden door the shape and size of a mouse", item_id="wooden_mouse_door"
        ),
        AspectTableEntry(93, 94, "An eyepatch, stained with old blood", item_id="bloody_eyepatch"),
        AspectTableEntry(
            95,
            96,
            "An ogre's toenail, tough as steel, its owner still lives",
            item_id="ogre_toenail",
        ),
        AspectTableEntry(
            97,
            98,
            "Eyeglasses haunted by benign ghosts, wearing them allows you to see the ghosts",
            item_id="ghost_eyeglasses",
        ),
        AspectTableEntry(
            99,
            100,
            "One of a pair of bracelets made from braided mouse tails",
            item_id="mouse_tail_bracelet",
        ),
    ],
)


# =============================================================================
# COMPLETE GRIMALKIN DEFINITION
# =============================================================================

GRIMALKIN_DEFINITION = KindredDefinition(
    kindred_id="grimalkin",
    name="Grimalkin",
    description=(
        "Grimalkins are shape-shifting cat-fairies renowned for their magic of "
        "illusion and their love of eating rats. They can take on three different "
        "forms: estray (humanoid cat), chester (fat domestic cat), and wilder "
        "(primal fey predator). Grimalkins originate in the fairy realm of Catland, "
        "ruled over by the fearsome Queen Abyssinia—the Queen of All Cats. Those "
        "grimalkins who enter Dolmenwood live as wanderers and adventurers."
    ),
    kindred_type=KindredType.FAIRY,
    physical=PhysicalRanges(
        # Age at Level 1: 1d100 × 10 years (like elves)
        age_base=0,
        age_dice=DiceFormula(1, 100, 0),  # Will multiply by 10 in generator
        # Lifespan: Immortal
        lifespan_base=999999,
        lifespan_dice=DiceFormula(0, 0, 0),
        # Height: 2'6" + 2d6" = 30 + 2d6 inches (Small)
        height_base=30,
        height_dice=DiceFormula(2, 6),
        # Weight: 50 + 3d10 lbs
        weight_base=50,
        weight_dice=DiceFormula(3, 10),
        size="Small",
    ),
    native_languages=["Woldish", "Mewl"],
    abilities=[
        GRIMALKIN_SKILLS_ABILITY,
        GRIMALKIN_GLAMOURS_ABILITY,
        GRIMALKIN_IMMORTALITY_ABILITY,
        GRIMALKIN_MAGIC_RESISTANCE_ABILITY,
        GRIMALKIN_SHAPE_SHIFTING_ABILITY,
        GRIMALKIN_DEFENSIVE_BONUS_ABILITY,
        GRIMALKIN_EATING_RODENTS_ABILITY,
        GRIMALKIN_COLD_IRON_VULNERABILITY_ABILITY,
    ],
    level_progression=[],  # Grimalkins don't have level-based progression
    preferred_classes=["Bard", "Enchanter", "Hunter", "Thief"],
    restricted_classes=["Cleric", "Friar"],  # No spiritual connection with mortal deities
    name_table=GRIMALKIN_NAME_TABLE,
    aspect_tables={
        AspectType.BACKGROUND: GRIMALKIN_BACKGROUND_TABLE,
        AspectType.HEAD: GRIMALKIN_HEAD_TABLE,
        AspectType.DEMEANOUR: GRIMALKIN_DEMEANOUR_TABLE,
        AspectType.DESIRES: GRIMALKIN_DESIRES_TABLE,
        AspectType.FACE: GRIMALKIN_FACE_TABLE,
        AspectType.DRESS: GRIMALKIN_DRESS_TABLE,
        AspectType.BELIEFS: GRIMALKIN_BELIEFS_TABLE,
        AspectType.FUR_BODY: GRIMALKIN_FUR_TABLE,
        AspectType.SPEECH: GRIMALKIN_SPEECH_TABLE,
        AspectType.TRINKET: GRIMALKIN_TRINKET_TABLE,
    },
    trinket_item_ids=[
        "bicorne_hat",
        "book_old_woldish_laws",
        "brass_thimble_water_to_milk",
        "breggle_tongue",
        "cherry_tart_fairy_noble",
        "cloak_hundred_voles",
        "copper_coin_same_side",
        "crimson_feather_enormous_bird",
        "dead_crow_never_rots",
        "self_shuffling_cards",
        "dried_heart_acorn_size",
        "famous_grimalkin_hairball",
        "handkerchief_queen_abyssinia_kiss",
        "heart_shaped_locket_cat_portraits",
        "human_eye_rain_predictor",
        "witch_favor_note",
        "leaf_tallest_tree_dolmenwood",
        "letter_miller_child_aid",
        "cockroach_gold_string",
        "lucky_tortoise_shell",
        "lute_tune_cycle",
        "gold_embroidered_cushion",
        "mouse_skull_moon",
        "mushroom_mossling_head",
        "nightingale_song_locket",
        "fashionable_boots",
        "dice_always_nine",
        "pink_bow_never_invisible",
        "pocket_watch_hour_ago",
        "porcelain_teacup_salamander",
        "twitching_rabbit_foot",
        "rat_king_sack",
        "human_child_mask",
        "royal_lineage_scroll",
        "noble_keys_golden_ring",
        "severed_sprite_head",
        "giant_sewing_needle",
        "cold_iron_shard_sphere",
        "cat_whisker_commitment",
        "woodgrue_pipe",
        "potent_catnip_vial",
        "silent_bell",
        "trained_weasel",
        "whistle_dogs_cant_hear",
        "wolf_paw_bleeding",
        "wooden_mouse_door",
        "bloody_eyepatch",
        "ogre_toenail",
        "ghost_eyeglasses",
        "mouse_tail_bracelet",
    ],
    kindred_relations=(
        "The adventuresome grimalkins who wander in the mortal world tend to become "
        "jealous and furtive among their own kind, so they prefer the company of other "
        "Kindreds. They enjoy the companionship of other fairies and demi-fey, holding "
        "a special fondness for the frivolity of woodgrues. They regard the earnest "
        "undertakings of humans and other mortal Kindreds as comical and somewhat absurd. "
        "Grimalkins are greeted with curiosity and wonder in human settlements in "
        "Dolmenwood, perhaps due to humans' affection for domestic cats."
    ),
    religion_notes=(
        "Grimalkins cannot be clerics or friars as they have no spiritual connection "
        "with the deities of mortals."
    ),
    source_book="Dolmenwood Player Book",
    source_page=40,
)
