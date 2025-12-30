"""
Human kindred definition for Dolmenwood.

The folk of the day-to-day world, in all the variety we know.
Source: Dolmenwood Player Book, pages 44-47
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
# HUMAN ABILITIES
# =============================================================================

HUMAN_DECISIVENESS_ABILITY = KindredAbility(
    ability_id="human_decisiveness",
    name="Decisiveness",
    description=(
        "When an Initiative Roll is tied, humans act first, as if they had "
        "won initiative. Treat humans as a separate side, acting before others."
    ),
    is_passive=True,
    extra_data={
        "initiative_tie_breaker": True,
        "acts_first_on_tie": True,
    },
)

HUMAN_LEADERSHIP_ABILITY = KindredAbility(
    ability_id="human_leadership",
    name="Leadership",
    description=(
        "The Loyalty rating of retainers in the employ of a human character " "is increased by 1."
    ),
    is_passive=True,
    extra_data={
        "retainer_loyalty_bonus": 1,
    },
)

HUMAN_SPIRITED_ABILITY = KindredAbility(
    ability_id="human_spirited",
    name="Spirited",
    description=(
        "Humans are quick to learn and adapt and gain a +10% bonus to all "
        "Experience Points earned. This is in addition to any XP bonus due "
        "to the character's Prime Ability."
    ),
    is_passive=True,
    extra_data={
        "xp_bonus_percent": 10,
    },
)


# =============================================================================
# HUMAN NAME TABLE
# =============================================================================

HUMAN_NAME_TABLE = NameTable(
    columns={
        NameColumn.MALE: [
            "Arfred",
            "Brom",
            "Bunk",
            "Chydewick",
            "Crump",
            "Dimothy",
            "Guillem",
            "Henrick",
            "Hogrid",
            "Jappser",
            "Joremey",
            "Josprey",
            "Jymes",
            "Mollequip",
            "Rodger",
            "Rogbert",
            "Samwise",
            "Shadwell",
            "Shank",
            "Sidley",
        ],
        NameColumn.FEMALE: [
            "Agnel",
            "Amonie",
            "Celenia",
            "Emelda",
            "Gertwinne",
            "Gilly",
            "Gretchen",
            "Gwendolyne",
            "Hilda",
            "Illabell",
            "Katerynne",
            "Lillibeth",
            "Lillith",
            "Lisabeth",
            "Mabel",
            "Maydrid",
            "Melysse",
            "Molly",
            "Pansy",
            "Roese",
        ],
        NameColumn.UNISEX: [
            "Andred",
            "Arda",
            "Aubrey",
            "Clement",
            "Clewyd",
            "Dayle",
            "Gemrand",
            "Hank",
            "Lyren",
            "Maude",
            "Megynne",
            "Moss",
            "Robyn",
            "Rowan",
            "Sage",
            "Tamrin",
            "Ursequine",
            "Waldra",
            "Waydred",
            "Wendlow",
        ],
        NameColumn.SURNAME: [
            "Addercapper",
            "Burl",
            "Candleswick",
            "Crumwaller",
            "Dogoode",
            "Dregger",
            "Dunwallow",
            "Fraggleton",
            "Gruewater",
            "Harper",
            "Lank",
            "Logueweave",
            "Loomer",
            "Malksmilk",
            "Smith",
            "Sunderman",
            "Swinney",
            "Tolmen",
            "Weavilman",
            "Wolder",
        ],
    }
)


# =============================================================================
# HUMAN ASPECT TABLES
# =============================================================================

# Humans have a d100 background table with weighted entries
HUMAN_BACKGROUND_TABLE = AspectTable(
    aspect_type=AspectType.BACKGROUND,
    die_size=100,
    entries=[
        AspectTableEntry(1, 1, "Actor"),
        AspectTableEntry(2, 5, "Angler"),
        AspectTableEntry(6, 6, "Animal trainer"),
        AspectTableEntry(7, 7, "Apothecary"),
        AspectTableEntry(8, 10, "Baker"),
        AspectTableEntry(11, 11, "Barber"),
        AspectTableEntry(12, 12, "Beekeeper"),
        AspectTableEntry(13, 15, "Beggar"),
        AspectTableEntry(16, 18, "Blacksmith"),
        AspectTableEntry(19, 19, "Bookbinder"),
        AspectTableEntry(20, 21, "Brewer"),
        AspectTableEntry(22, 24, "Butcher"),
        AspectTableEntry(25, 28, "Carpenter"),
        AspectTableEntry(29, 29, "Cartographer"),
        AspectTableEntry(30, 32, "Cattle farmer"),
        AspectTableEntry(33, 33, "Chandler"),
        AspectTableEntry(34, 34, "Cheesemaker"),
        AspectTableEntry(35, 35, "Cobbler"),
        AspectTableEntry(36, 36, "Cooper"),
        AspectTableEntry(37, 37, "Dockhand"),
        AspectTableEntry(38, 38, "Fortune-teller"),
        AspectTableEntry(39, 39, "Fur trapper"),
        AspectTableEntry(40, 41, "Gambler"),
        AspectTableEntry(42, 42, "Glassblower"),
        AspectTableEntry(43, 43, "Grave digger"),
        AspectTableEntry(44, 45, "Hog farmer"),
        AspectTableEntry(46, 49, "Hunter"),
        AspectTableEntry(50, 50, "Jester"),
        AspectTableEntry(51, 51, "Jeweller"),
        AspectTableEntry(52, 52, "Leather worker"),
        AspectTableEntry(53, 53, "Locksmith"),
        AspectTableEntry(54, 54, "Merchant"),
        AspectTableEntry(55, 56, "Miner"),
        AspectTableEntry(57, 58, "Outlaw"),
        AspectTableEntry(59, 60, "Pedlar"),
        AspectTableEntry(61, 61, "Pilgrim"),
        AspectTableEntry(62, 63, "Poacher"),
        AspectTableEntry(64, 64, "Potter"),
        AspectTableEntry(65, 65, "Roper"),
        AspectTableEntry(66, 66, "Sailor"),
        AspectTableEntry(67, 67, "Scribe"),
        AspectTableEntry(68, 71, "Servant"),
        AspectTableEntry(72, 73, "Sheep farmer"),
        AspectTableEntry(74, 74, "Shipwright"),
        AspectTableEntry(75, 75, "Smuggler"),
        AspectTableEntry(76, 76, "Stable hand"),
        AspectTableEntry(77, 77, "Stonemason"),
        AspectTableEntry(78, 78, "Swindler"),
        AspectTableEntry(79, 79, "Tailor"),
        AspectTableEntry(80, 80, "Tax collector"),
        AspectTableEntry(81, 81, "Thatcher"),
        AspectTableEntry(82, 84, "Turnip farmer"),
        AspectTableEntry(85, 85, "Unicorn hunter"),
        AspectTableEntry(86, 87, "Vagrant"),
        AspectTableEntry(88, 88, "Wainwright"),
        AspectTableEntry(89, 90, "Wayfarer"),
        AspectTableEntry(91, 92, "Weaver"),
        AspectTableEntry(93, 95, "Wheat farmer"),
        AspectTableEntry(96, 96, "Wizard's assistant"),
        AspectTableEntry(97, 100, "Woodcutter"),
    ],
)

HUMAN_HEAD_TABLE = AspectTable(
    aspect_type=AspectType.HEAD,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Cropped or shaven hair"),
        AspectTableEntry(2, 2, "Embroidered skull cap"),
        AspectTableEntry(3, 3, "Fur hat with animal tail"),
        AspectTableEntry(4, 4, "Jaunty cap with feather"),
        AspectTableEntry(5, 5, "Jug ears"),
        AspectTableEntry(6, 6, "Long braids"),
        AspectTableEntry(7, 7, "Meticulously oiled hair"),
        AspectTableEntry(8, 8, "Misshapen skull"),
        AspectTableEntry(9, 9, "Patchy, straggly hair"),
        AspectTableEntry(10, 10, "Poised atop an elegant neck"),
        AspectTableEntry(11, 11, "Thick, lustrous hair"),
        AspectTableEntry(12, 12, "Wild, curly hair"),
    ],
)

HUMAN_DEMEANOUR_TABLE = AspectTable(
    aspect_type=AspectType.DEMEANOUR,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Brooding, quick-tempered"),
        AspectTableEntry(2, 2, "Curious, broad-minded"),
        AspectTableEntry(3, 3, "Dour, single-minded"),
        AspectTableEntry(4, 4, "Enthusiastic, gullible"),
        AspectTableEntry(5, 5, "Gregarious"),
        AspectTableEntry(6, 6, "Impatient and rash"),
        AspectTableEntry(7, 7, "Kindly"),
        AspectTableEntry(8, 8, "Miserly"),
        AspectTableEntry(9, 9, "Scheming"),
        AspectTableEntry(10, 10, "Self-aggrandising"),
        AspectTableEntry(11, 11, "Slovenly"),
        AspectTableEntry(12, 12, "Suave"),
    ],
)

HUMAN_DESIRES_TABLE = AspectTable(
    aspect_type=AspectType.DESIRES,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Build castle and new village"),
        AspectTableEntry(2, 2, "Clear family name"),
        AspectTableEntry(3, 3, "Collect saintly relics"),
        AspectTableEntry(4, 4, "Domestic bliss"),
        AspectTableEntry(5, 5, "Explore Fairy"),
        AspectTableEntry(6, 6, "Found business empire"),
        AspectTableEntry(7, 7, "Infamy"),
        AspectTableEntry(8, 8, "Map stones of Dolmenwood"),
        AspectTableEntry(9, 9, "Marry into nobility"),
        AspectTableEntry(10, 10, "Redeem past misdeeds"),
        AspectTableEntry(11, 11, "Secret underground lair"),
        AspectTableEntry(12, 12, "Squander fortune on luxury"),
    ],
)

HUMAN_FACE_TABLE = AspectTable(
    aspect_type=AspectType.FACE,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Bent nose"),
        AspectTableEntry(2, 2, "Button nose"),
        AspectTableEntry(3, 3, "Darting eyes"),
        AspectTableEntry(4, 4, "Droll, lupine mouth"),
        AspectTableEntry(5, 5, "Gap-toothed"),
        AspectTableEntry(6, 6, "Hirsute"),
        AspectTableEntry(7, 7, "Large, regal nose"),
        AspectTableEntry(8, 8, "Narrow, pinched"),
        AspectTableEntry(9, 9, "Pimples"),
        AspectTableEntry(10, 10, "Prominent scar"),
        AspectTableEntry(11, 11, "Rosy"),
        AspectTableEntry(12, 12, "Wide, spaced out features"),
    ],
)

HUMAN_DRESS_TABLE = AspectTable(
    aspect_type=AspectType.DRESS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Colourful patchwork"),
        AspectTableEntry(2, 2, "Dashing doublet and hose"),
        AspectTableEntry(3, 3, "Enigmatic cloak and hood"),
        AspectTableEntry(4, 4, "Filthy woollens"),
        AspectTableEntry(5, 5, "Hessian rags"),
        AspectTableEntry(6, 6, "Lace, posies, and frills"),
        AspectTableEntry(7, 7, "Noisome furs"),
        AspectTableEntry(8, 8, "Padded vest and breeches"),
        AspectTableEntry(9, 9, "Sheepskin coat"),
        AspectTableEntry(10, 10, "Smoking jacket and slacks"),
        AspectTableEntry(11, 11, "Sturdy boots and raincoat"),
        AspectTableEntry(12, 12, "Way-worn leathers"),
    ],
)

HUMAN_BELIEFS_TABLE = AspectTable(
    aspect_type=AspectType.BELIEFS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Bishop is a werewolf"),
        AspectTableEntry(2, 2, "Drune will enslave the duke"),
        AspectTableEntry(3, 3, "Fairies steal human souls"),
        AspectTableEntry(4, 4, "Nag-Lord brings final doom"),
        AspectTableEntry(5, 5, "One parent was an elf"),
        AspectTableEntry(6, 6, "Prayers redeem evil deeds"),
        AspectTableEntry(7, 7, "Shroom of immortality"),
        AspectTableEntry(8, 8, "Sunken village in Longmere"),
        AspectTableEntry(9, 9, "Talking beasts plot uprising"),
        AspectTableEntry(10, 10, "The dead are rising"),
        AspectTableEntry(11, 11, "Visions from the Cold Prince"),
        AspectTableEntry(12, 12, "Witches serve the Nag-Lord"),
    ],
)

# Humans use "Body" instead of "Fur"
HUMAN_BODY_TABLE = AspectTable(
    aspect_type=AspectType.FUR_BODY,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Barrel chest"),
        AspectTableEntry(2, 2, "Big hands"),
        AspectTableEntry(3, 3, "Blotchy skin"),
        AspectTableEntry(4, 4, "Excessively hairy"),
        AspectTableEntry(5, 5, "Freckles"),
        AspectTableEntry(6, 6, "Long legs"),
        AspectTableEntry(7, 7, "Long, elegant fingers"),
        AspectTableEntry(8, 8, "Oily skin"),
        AspectTableEntry(9, 9, "Pocked with plague-scars"),
        AspectTableEntry(10, 10, "Pot belly"),
        AspectTableEntry(11, 11, "Smooth, supple skin"),
        AspectTableEntry(12, 12, "Warts"),
    ],
)

HUMAN_SPEECH_TABLE = AspectTable(
    aspect_type=AspectType.SPEECH,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Agitated"),
        AspectTableEntry(2, 2, "Bellowing"),
        AspectTableEntry(3, 3, "Cackling"),
        AspectTableEntry(4, 4, "Coarse"),
        AspectTableEntry(5, 5, "Conspiratorial"),
        AspectTableEntry(6, 6, "Gravelly"),
        AspectTableEntry(7, 7, "Inane banter"),
        AspectTableEntry(8, 8, "Mellow"),
        AspectTableEntry(9, 9, "Mumbling"),
        AspectTableEntry(10, 10, "Nasal whine"),
        AspectTableEntry(11, 11, "Rapid"),
        AspectTableEntry(12, 12, "Sighing"),
    ],
)

# Trinket table - references item IDs in adventuring_gear_human_trinkets.json
HUMAN_TRINKET_TABLE = AspectTable(
    aspect_type=AspectType.TRINKET,
    die_size=100,
    entries=[
        AspectTableEntry(
            1,
            2,
            "A black stone which always points towards the sun",
            item_id="black_stone_sun_pointer",
        ),
        AspectTableEntry(
            3, 4, "A blood sausage, allegedly made of wyrm's blood", item_id="wyrm_blood_sausage"
        ),
        AspectTableEntry(
            5,
            6,
            "A blood-stained handkerchief that won't wash clean",
            item_id="bloodstained_handkerchief",
        ),
        AspectTableEntry(
            7,
            8,
            "A bone statuette of a mermaid with prodigiously hairy armpits",
            item_id="mermaid_bone_statuette",
        ),
        AspectTableEntry(
            9, 10, "A bright red egg that was given to you by a sprite", item_id="sprite_red_egg"
        ),
        AspectTableEntry(
            11,
            12,
            "A clay effigy that whispers to you in your sleep",
            item_id="whispering_clay_effigy",
        ),
        AspectTableEntry(
            13, 14, "A cracked marble that falls in slow motion", item_id="slow_motion_marble"
        ),
        AspectTableEntry(
            15,
            16,
            "A deck of cards illustrated with blindfolded kings, queens, knaves, etc.",
            item_id="blindfolded_card_deck",
        ),
        AspectTableEntry(
            17, 18, "A drinking horn carved with cavorting nymphs", item_id="nymph_drinking_horn"
        ),
        AspectTableEntry(
            19, 20, "A dubious fake moustache made of rat fur", item_id="rat_fur_moustache"
        ),
        AspectTableEntry(
            21,
            22,
            "A fine set of silver cutlery and a floral china tea-set, all packed in a wicker hamper",
            item_id="silver_cutlery_tea_set",
        ),
        AspectTableEntry(23, 24, "A foot-long, spicy sausage", item_id="spicy_sausage"),
        AspectTableEntry(25, 26, "A gauntlet of wyrm scales", item_id="wyrm_scale_gauntlet"),
        AspectTableEntry(27, 28, "A goatskin pouch full of giblets", item_id="giblet_pouch"),
        AspectTableEntry(
            29, 30, "A head-sized glass sphere with a neck opening", item_id="glass_sphere"
        ),
        AspectTableEntry(
            31, 32, "A hunk of ancient, mouldy cheese", item_id="ancient_mouldy_cheese"
        ),
        AspectTableEntry(
            33, 34, "A jar that breeds flies, even when tightly sealed", item_id="fly_breeding_jar"
        ),
        AspectTableEntry(
            35,
            36,
            "A jaunty cap (with a feather stuck in it) which jumps up whenever anyone says your name",
            item_id="jumping_feathered_cap",
        ),
        AspectTableEntry(
            37,
            38,
            "A lavender scented cushion embroidered with black roses and thorns",
            item_id="lavender_rose_cushion",
        ),
        AspectTableEntry(
            39,
            40,
            "A lock of hair from the first person you killed",
            item_id="first_kill_hair_lock",
        ),
        AspectTableEntry(41, 42, "A long kilt of woven moss", item_id="moss_kilt"),
        AspectTableEntry(
            43,
            44,
            "A love letter you are penning in silver ink to your fairy betrothed",
            item_id="fairy_love_letter",
        ),
        AspectTableEntry(
            45,
            46,
            "A miniature brass gnome that appears on your pillow looking at you each morning",
            item_id="brass_gnome_miniature",
        ),
        AspectTableEntry(
            47,
            48,
            "A napkin and cutlery that you stole from a fancy inn",
            item_id="stolen_inn_cutlery",
        ),
        AspectTableEntry(
            49,
            50,
            "A note from your mother admonishing you to return home as soon as able",
            item_id="mothers_note",
        ),
        AspectTableEntry(
            51,
            52,
            "A pair of stripy woollen socks that keep your feet as warm and dry as fine boots",
            item_id="warm_stripy_socks",
        ),
        AspectTableEntry(
            53, 54, "A pebble that glows faintly in the dark", item_id="glowing_pebble"
        ),
        AspectTableEntry(
            55,
            56,
            "A piece of the moon that fell to earth (or is it a hunk of desiccated cheese?)",
            item_id="moon_piece",
        ),
        AspectTableEntry(
            57,
            58,
            "A porcelain teapot painted with a scene of owls devouring humans",
            item_id="owl_human_teapot",
        ),
        AspectTableEntry(
            59, 60, "A raven's feather quill that writes without ink", item_id="inkless_raven_quill"
        ),
        AspectTableEntry(
            61, 62, "A silver belt woven from the mane of a kelpie", item_id="kelpie_mane_belt"
        ),
        AspectTableEntry(
            63, 64, "A silver mirror that always reflects the sky", item_id="sky_reflecting_mirror"
        ),
        AspectTableEntry(
            65,
            66,
            "A silver ring that shrinks or expands to fit whatever finger it is placed upon",
            item_id="size_changing_ring",
        ),
        AspectTableEntry(
            67,
            68,
            "A tiny fish in a jar of water that whispers the names of everyone within 5' at night",
            item_id="whispering_fish_jar",
        ),
        AspectTableEntry(
            69,
            70,
            "A tiny wicker effigy that you stole from a witch's hut",
            item_id="stolen_wicker_effigy",
        ),
        AspectTableEntry(
            71,
            72,
            "A unicorn statuette carved out of mushroom-wood",
            item_id="mushroom_wood_unicorn",
        ),
        AspectTableEntry(73, 74, "A wanted poster for yourself", item_id="wanted_poster_self"),
        AspectTableEntry(
            75, 76, "A well-thumbed and annotated book of psalms", item_id="annotated_psalms_book"
        ),
        AspectTableEntry(
            77, 78, "An ash wand stained with the blood of a troll", item_id="troll_blood_ash_wand"
        ),
        AspectTableEntry(
            79, 80, "An enormous Green Man brass belt buckle", item_id="green_man_belt_buckle"
        ),
        AspectTableEntry(81, 82, "An ornate lantern you found in a bog", item_id="bog_lantern"),
        AspectTableEntry(
            83,
            84,
            "Sixteen silver pieces, greased with slippery magical oil that cannot be washed off",
            item_id="greased_silver_pieces",
        ),
        AspectTableEntry(
            85, 86, "The broken tip of a unicorn's horn", item_id="broken_unicorn_horn_tip"
        ),
        AspectTableEntry(
            87, 88, "The fairy sword that slew your father", item_id="fairy_sword_fathers_killer"
        ),
        AspectTableEntry(89, 90, "The mummified hand of a bog body", item_id="bog_body_hand"),
        AspectTableEntry(
            91, 92, "The scintillating, silvery feather of a witch owl", item_id="witch_owl_feather"
        ),
        AspectTableEntry(
            93,
            94,
            "The skeleton of an especially large toad, in pieces",
            item_id="large_toad_skeleton",
        ),
        AspectTableEntry(
            95, 96, "The skull of a Drune, stolen from a forbidden crypt", item_id="drune_skull"
        ),
        AspectTableEntry(
            97,
            98,
            "The wobbly, pink severed hand of a gelatinous ape, still fresh and sweet",
            item_id="gelatinous_ape_hand",
        ),
        AspectTableEntry(
            99,
            100,
            "Your grandfather's beard, rolled up in a hessian cloth",
            item_id="grandfathers_beard",
        ),
    ],
)


# =============================================================================
# COMPLETE HUMAN DEFINITION
# =============================================================================

HUMAN_DEFINITION = KindredDefinition(
    kindred_id="human",
    name="Human",
    description=(
        "As is the way in the wider world beyond the forest, humans prevail within "
        "the settled reaches of Dolmenwood. Possessed of a restless and curious spirit, "
        "humans venture into unexplored regions, found great dominions, and delve into "
        "perilous secrets of magic. Human settlements are found throughout Dolmenwood, "
        "from the isolated hamlets of hunters and woodcutters, to welcoming wayside inns, "
        "to trade villages and market towns, to the great city of Castle Brackenwold."
    ),
    kindred_type=KindredType.MORTAL,
    physical=PhysicalRanges(
        # Age at Level 1: 15 + 2d10 years
        age_base=15,
        age_dice=DiceFormula(2, 10),
        # Lifespan: 50 + 2d20 years
        lifespan_base=50,
        lifespan_dice=DiceFormula(2, 20),
        # Height: Male 5'4" + 2d6", Female 5' + 2d6"
        # Using male height as base, generator will handle gender differences
        height_base=64,  # Male: 5'4" = 64 inches
        height_dice=DiceFormula(2, 6),
        # Weight: 120 + 6d10 lbs
        weight_base=120,
        weight_dice=DiceFormula(6, 10),
        size="Medium",
        # Store female height difference for generator
        extra_data={
            "female_height_base": 60,  # Female: 5' = 60 inches
        },
    ),
    native_languages=["Woldish"],
    abilities=[
        HUMAN_DECISIVENESS_ABILITY,
        HUMAN_LEADERSHIP_ABILITY,
        HUMAN_SPIRITED_ABILITY,
    ],
    level_progression=[],  # Humans don't have level-based kindred progression
    preferred_classes=[
        "Fighter",
        "Cleric",
        "Thief",
        "Magician",
        "Knight",
        "Friar",
        "Bard",
        "Hunter",
    ],
    restricted_classes=["Enchanter"],  # Rare for humans to have connection to Fairy
    name_table=HUMAN_NAME_TABLE,
    aspect_tables={
        AspectType.BACKGROUND: HUMAN_BACKGROUND_TABLE,
        AspectType.HEAD: HUMAN_HEAD_TABLE,
        AspectType.DEMEANOUR: HUMAN_DEMEANOUR_TABLE,
        AspectType.DESIRES: HUMAN_DESIRES_TABLE,
        AspectType.FACE: HUMAN_FACE_TABLE,
        AspectType.DRESS: HUMAN_DRESS_TABLE,
        AspectType.BELIEFS: HUMAN_BELIEFS_TABLE,
        AspectType.FUR_BODY: HUMAN_BODY_TABLE,  # Humans use "Body" instead of "Fur"
        AspectType.SPEECH: HUMAN_SPEECH_TABLE,
        AspectType.TRINKET: HUMAN_TRINKET_TABLE,
    },
    trinket_item_ids=[
        "black_stone_sun_pointer",
        "wyrm_blood_sausage",
        "bloodstained_handkerchief",
        "mermaid_bone_statuette",
        "sprite_red_egg",
        "whispering_clay_effigy",
        "slow_motion_marble",
        "blindfolded_card_deck",
        "nymph_drinking_horn",
        "rat_fur_moustache",
        "silver_cutlery_tea_set",
        "spicy_sausage",
        "wyrm_scale_gauntlet",
        "giblet_pouch",
        "glass_sphere",
        "ancient_mouldy_cheese",
        "fly_breeding_jar",
        "jumping_feathered_cap",
        "lavender_rose_cushion",
        "first_kill_hair_lock",
        "moss_kilt",
        "fairy_love_letter",
        "brass_gnome_miniature",
        "stolen_inn_cutlery",
        "mothers_note",
        "warm_stripy_socks",
        "glowing_pebble",
        "moon_piece",
        "owl_human_teapot",
        "inkless_raven_quill",
        "kelpie_mane_belt",
        "sky_reflecting_mirror",
        "size_changing_ring",
        "whispering_fish_jar",
        "stolen_wicker_effigy",
        "mushroom_wood_unicorn",
        "wanted_poster_self",
        "annotated_psalms_book",
        "troll_blood_ash_wand",
        "green_man_belt_buckle",
        "bog_lantern",
        "greased_silver_pieces",
        "broken_unicorn_horn_tip",
        "fairy_sword_fathers_killer",
        "bog_body_hand",
        "witch_owl_feather",
        "large_toad_skeleton",
        "drune_skull",
        "gelatinous_ape_hand",
        "grandfathers_beard",
    ],
    kindred_relations=(
        "Humans are on friendly terms with mortal and demi-fey Kindreds and live "
        "alongside breggles in the High Wold region. Most non-adventuring humans have "
        "never met a fairy and regard them with awe and caution. Human folklore is rife "
        "with tales of the treachery and mischief of fairies, not least the wicked Cold "
        "Prince and his servants, who ruled Dolmenwood in ancient times."
    ),
    religion_notes=(
        "While most everyday humans in Dolmenwood are adherents of the Pluritine Church, "
        "whispers of the worship of the old gods live on in folklore. The local belief "
        "in mead and ale as a means of communion with greater powers hearkens back to "
        "worship of the Green Man—god of feast, ale, revelry, and hunting."
    ),
    source_book="Dolmenwood Player Book",
    source_page=44,
)
