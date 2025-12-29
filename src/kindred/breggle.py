"""
Breggle kindred definition for Dolmenwood.

Goat-headed folk whose horn length indicates their social standing.
Source: Dolmenwood Player Book, pages 32-35
"""

from src.kindred.kindred_data import (
    AspectTable,
    AspectTableEntry,
    AspectType,
    DiceFormula,
    KindredAbility,
    KindredDefinition,
    KindredType,
    LevelProgression,
    NameColumn,
    NameTable,
    PhysicalRanges,
)


# =============================================================================
# BREGGLE ABILITIES
# =============================================================================

BREGGLE_FUR_ABILITY = KindredAbility(
    ability_id="breggle_fur",
    name="Fur",
    description=(
        "A breggle character's thick, woolly fur grants them +1 AC "
        "when unarmoured or wearing Light armour."
    ),
    is_passive=True,
    ac_bonus=1,
    ac_conditions=["unarmoured", "light_armour"],
)

BREGGLE_HORNS_ABILITY = KindredAbility(
    ability_id="breggle_horns",
    name="Horns",
    description=(
        "Breggles may make a melee attack with their horns instead of a weapon. "
        "The damage inflicted increases with Level."
    ),
    is_passive=False,
    is_attack=True,
    damage_by_level={
        1: "1d4",
        2: "1d4",
        3: "1d4+1",
        4: "1d4+1",
        5: "1d4+1",
        6: "1d6",
        7: "1d6",
        8: "1d6",
        9: "1d6+1",
        10: "1d6+2",
    },
)

BREGGLE_GAZE_ABILITY = KindredAbility(
    ability_id="breggle_gaze",
    name="Gaze",
    description=(
        "Upon attaining longhorn status (from Level 4), a breggle character "
        "can use their gaze to charm humans and shorthorns into obeisance. "
        "The longhorn must gaze intently at an individual human or shorthorn. "
        "If the target fails a Save Versus Spell, they are charmed to view "
        "the longhorn character with awe and respect. While charmed, the target "
        "is unable to harm the longhorn, either directly or indirectly. "
        "The effect lasts until next sunrise. The holy spell Mantle of Protection "
        "counters a longhorn's gaze. The gaze may be used on a specific subject "
        "at most once a day."
    ),
    is_passive=False,
    min_level=4,
    save_type="spell",
    duration="until next sunrise",
    uses_per_day_by_level={
        4: 1,
        5: 1,
        6: 2,
        7: 2,
        8: 3,
        9: 3,
        10: 4,
    },
    extra_data={
        "targets": ["human", "shorthorn_breggle"],
        "countered_by": ["Mantle of Protection"],
        "once_per_target_per_day": True,
    },
)


# =============================================================================
# BREGGLE LEVEL PROGRESSION
# =============================================================================

BREGGLE_PROGRESSION = [
    LevelProgression(level=1, horn_length='1"', horn_damage="1d4", gaze_uses=0),
    LevelProgression(level=2, horn_length='2"', horn_damage="1d4", gaze_uses=0),
    LevelProgression(level=3, horn_length='3"', horn_damage="1d4+1", gaze_uses=0),
    LevelProgression(level=4, horn_length='4"', horn_damage="1d4+1", gaze_uses=1),
    LevelProgression(level=5, horn_length='6"', horn_damage="1d4+1", gaze_uses=1),
    LevelProgression(level=6, horn_length='8"', horn_damage="1d6", gaze_uses=2),
    LevelProgression(level=7, horn_length='10"', horn_damage="1d6", gaze_uses=2),
    LevelProgression(level=8, horn_length='12"', horn_damage="1d6", gaze_uses=3),
    LevelProgression(level=9, horn_length='14"', horn_damage="1d6+1", gaze_uses=3),
    LevelProgression(level=10, horn_length='16"', horn_damage="1d6+2", gaze_uses=4),
]


# =============================================================================
# BREGGLE NAME TABLE
# =============================================================================

BREGGLE_NAME_TABLE = NameTable(
    columns={
        NameColumn.MALE: [
            "Aele", "Braembel", "Broob", "Crump", "Drerdl",
            "Frennig", "Grerg", "Gripe", "Llerg", "Llrod",
            "Lope", "Mashker", "Olledg", "Rheg", "Shadgore",
            "Shadwell", "Shadwicke", "Shandor", "Shank", "Snerd",
        ],
        NameColumn.FEMALE: [
            "Aedel", "Berrild", "Bredhr", "Draed", "Fannigrew",
            "Frandorup", "Grendilore", "Grendl", "Grewigg", "Hildrup",
            "Hraigl", "Hwendl", "Maybel", "Myrkle", "Nannigrew",
            "Pettigrew", "Rrhimbr", "Shord", "Smethra", "Wheld",
        ],
        NameColumn.UNISEX: [
            "Addle", "Andred", "Blocke", "Clover", "Crewwin",
            "Curlip", "Eleye", "Ellip", "Frannidore", "Ghrend",
            "Grennigore", "Gwendl", "Hrannick", "Hwoldrup", "Lindor",
            "Merrild", "Smenthard", "Snerg", "Wendlow", "Windor",
        ],
        NameColumn.SURNAME: [
            "Blathergripe", "Bluegouge", "Bockbrugh", "Bockstump", "Elbowgen",
            "Forlocke", "Hwodlow", "Lankshorn", "Lockehorn", "Longbeard",
            "Longshanks", "Shankwold", "Smallbuck", "Snicklebock", "Snidebleat",
            "Snoode", "Underbleat", "Underbuck", "Wolder", "Woldleap",
        ],
    }
)


# =============================================================================
# BREGGLE ASPECT TABLES
# =============================================================================

BREGGLE_BACKGROUND_TABLE = AspectTable(
    aspect_type=AspectType.BACKGROUND,
    die_size=20,
    entries=[
        AspectTableEntry(1, 1, "Alchemist's assistant"),
        AspectTableEntry(2, 2, "Angler"),
        AspectTableEntry(3, 3, "Beekeeper"),
        AspectTableEntry(4, 4, "Blacksmith"),
        AspectTableEntry(5, 5, "Brewer"),
        AspectTableEntry(6, 6, "Chandler"),
        AspectTableEntry(7, 7, "Devil goat handler",
                         description="Devil goats (Augfrlad in Caprice): Large, carnivorous goats bred by certain breggle nobles for use as fiercely loyal guardians or ceremonial mounts."),
        AspectTableEntry(8, 8, "Gambler"),
        AspectTableEntry(9, 9, "Grave digger"),
        AspectTableEntry(10, 10, "Merchant"),
        AspectTableEntry(11, 11, "Onion farmer"),
        AspectTableEntry(12, 12, "Page"),
        AspectTableEntry(13, 13, "Pig farmer"),
        AspectTableEntry(14, 14, "Servant"),
        AspectTableEntry(15, 15, "Smuggler"),
        AspectTableEntry(16, 16, "Sorcerer's assistant"),
        AspectTableEntry(17, 17, "Standard-bearer"),
        AspectTableEntry(18, 18, "Thatcher"),
        AspectTableEntry(19, 19, "Turnip farmer"),
        AspectTableEntry(20, 20, "Vagrant"),
    ]
)

BREGGLE_HEAD_TABLE = AspectTable(
    aspect_type=AspectType.HEAD,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Dented helm with coat of arms"),
        AspectTableEntry(2, 2, "Ears pierced with nails or rings"),
        AspectTableEntry(3, 3, "Long, curly locks"),
        AspectTableEntry(4, 4, "Long, floppy ears"),
        AspectTableEntry(5, 5, "Narrow, pointed ears"),
        AspectTableEntry(6, 6, "One bent horn, one straight"),
        AspectTableEntry(7, 7, "One horn broken off"),
        AspectTableEntry(8, 8, "Silver stripe in hair"),
        AspectTableEntry(9, 9, "Slick, oiled hair"),
        AspectTableEntry(10, 10, "Spiky ginger hair"),
        AspectTableEntry(11, 11, "Thin neck, hefty head"),
        AspectTableEntry(12, 12, "Third nub horn on forehead"),
    ]
)

BREGGLE_DEMEANOUR_TABLE = AspectTable(
    aspect_type=AspectType.DEMEANOUR,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Ale-addled"),
        AspectTableEntry(2, 2, "Cool-headed pragmatist"),
        AspectTableEntry(3, 3, "Cultivated aristocratic air"),
        AspectTableEntry(4, 4, "Dour, pessimistic"),
        AspectTableEntry(5, 5, "Earnest, loyal"),
        AspectTableEntry(6, 6, "Endlessly scheming"),
        AspectTableEntry(7, 7, "Flighty, mercurial"),
        AspectTableEntry(8, 8, "Jocular with violent outbursts"),
        AspectTableEntry(9, 9, "Mellow, unflappable"),
        AspectTableEntry(10, 10, "Single-minded, stubborn"),
        AspectTableEntry(11, 11, "Wild hedonist"),
        AspectTableEntry(12, 12, "Wryly philosophical"),
    ]
)

BREGGLE_DESIRES_TABLE = AspectTable(
    aspect_type=AspectType.DESIRES,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Eradicate the Drune"),
        AspectTableEntry(2, 2, "Escape justice for past crime"),
        AspectTableEntry(3, 3, "Found a crime syndicate"),
        AspectTableEntry(4, 4, "Free the common folk"),
        AspectTableEntry(5, 5, "Imprison all crookhorns"),
        AspectTableEntry(6, 6, "Marry into nobility"),
        AspectTableEntry(7, 7, "Outrageous wealth and luxury"),
        AspectTableEntry(8, 8, "Popularise turnip ale"),
        AspectTableEntry(9, 9, "Recover ancient breggle lore"),
        AspectTableEntry(10, 10, "Restore High Wold to Ramius"),
        AspectTableEntry(11, 11, "Swindle Lord Murkin's wealth"),
        AspectTableEntry(12, 12, "Travel and discovery"),
    ]
)

BREGGLE_FACE_TABLE = AspectTable(
    aspect_type=AspectType.FACE,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Black eyes, silver pupils"),
        AspectTableEntry(2, 2, "Buck teeth"),
        AspectTableEntry(3, 3, "Bushy brows"),
        AspectTableEntry(4, 4, "Golden eyes"),
        AspectTableEntry(5, 5, "Lank forelock droops over eyes"),
        AspectTableEntry(6, 6, "Long, wispy chin-beard"),
        AspectTableEntry(7, 7, "Milky white eyes, blue flecks"),
        AspectTableEntry(8, 8, "Missing teeth"),
        AspectTableEntry(9, 9, "Prominent scar"),
        AspectTableEntry(10, 10, "Shaggy chin-beard"),
        AspectTableEntry(11, 11, "Small eyes, close set"),
        AspectTableEntry(12, 12, "Wide, drooling mouth"),
    ]
)

BREGGLE_DRESS_TABLE = AspectTable(
    aspect_type=AspectType.DRESS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Doublet and frilly shirt"),
        AspectTableEntry(2, 2, "Greasy woollens"),
        AspectTableEntry(3, 3, "Grimy apron"),
        AspectTableEntry(4, 4, "Huge, hairy overcoat"),
        AspectTableEntry(5, 5, "Long skirts and cloak"),
        AspectTableEntry(6, 6, "Patched leather, many pockets"),
        AspectTableEntry(7, 7, "Rabbit and squirrel fur"),
        AspectTableEntry(8, 8, "Servant's livery"),
        AspectTableEntry(9, 9, "Thigh boots and waistcoat"),
        AspectTableEntry(10, 10, "Thong and dashing cape"),
        AspectTableEntry(11, 11, "Tweed and deerstalker"),
        AspectTableEntry(12, 12, "Wide, armless frock"),
    ]
)

BREGGLE_BELIEFS_TABLE = AspectTable(
    aspect_type=AspectType.BELIEFS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Ancestors demand sacrifices"),
        AspectTableEntry(2, 2, "Breggles made standing stones"),
        AspectTableEntry(3, 3, "Breggles originate in Fairy"),
        AspectTableEntry(4, 4, "Church hides breggle saints"),
        AspectTableEntry(5, 5, "Daily garlic wards fairy hexes"),
        AspectTableEntry(6, 6, "Descendant of a mighty wizard"),
        AspectTableEntry(7, 7, "Duke is thrall of the Drune"),
        AspectTableEntry(8, 8, "Fairy is purely mythical"),
        AspectTableEntry(9, 9, "Malbleat serves the Nag-Lord"),
        AspectTableEntry(10, 10, "Malbleat will rule High Wold"),
        AspectTableEntry(11, 11, "Nag-Lord is breggle messiah"),
        AspectTableEntry(12, 12, "The end is nigh"),
    ]
)

BREGGLE_FUR_TABLE = AspectTable(
    aspect_type=AspectType.FUR_BODY,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Black, flecked with silver"),
        AspectTableEntry(2, 2, "Black, glossy"),
        AspectTableEntry(3, 3, "Ginger, curly"),
        AspectTableEntry(4, 4, "Ginger, rough"),
        AspectTableEntry(5, 5, "Grey, greasy"),
        AspectTableEntry(6, 6, "Grey, lustrous"),
        AspectTableEntry(7, 7, "Russet, spiky"),
        AspectTableEntry(8, 8, "Russet, wavy"),
        AspectTableEntry(9, 9, "Tan, coarse"),
        AspectTableEntry(10, 10, "Tan, shaggy"),
        AspectTableEntry(11, 11, "White, dirty"),
        AspectTableEntry(12, 12, "White, fluffy"),
    ]
)

BREGGLE_SPEECH_TABLE = AspectTable(
    aspect_type=AspectType.SPEECH,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Cackling"),
        AspectTableEntry(2, 2, "Circuitous"),
        AspectTableEntry(3, 3, "Coarse"),
        AspectTableEntry(4, 4, "Gurgling"),
        AspectTableEntry(5, 5, "High-pitched"),
        AspectTableEntry(6, 6, "Lackadaisical"),
        AspectTableEntry(7, 7, "Mumbling"),
        AspectTableEntry(8, 8, "Rumbling"),
        AspectTableEntry(9, 9, "Staccato"),
        AspectTableEntry(10, 10, "Throaty"),
        AspectTableEntry(11, 11, "Warbling"),
        AspectTableEntry(12, 12, "Whining"),
    ]
)

# Trinket table - references item IDs in adventuring_gear_breggle_trinkets.json
# Format: (roll_min, roll_max, trinket_name, item_id)
BREGGLE_TRINKET_TABLE = AspectTable(
    aspect_type=AspectType.TRINKET,
    die_size=100,
    entries=[
        AspectTableEntry(1, 2, "A bag of divination stones that always answer 'Panic' to any question", item_id="bag_of_divination_stones"),
        AspectTableEntry(3, 4, "A bloodstained jester's hat", item_id="bloodstained_jesters_hat"),
        AspectTableEntry(5, 6, "A bloody knife that cannot be cleaned", item_id="bloody_knife_uncleaned"),
        AspectTableEntry(7, 8, "A blue velvet jacket with a hidden pocket which moves when you're not looking", item_id="blue_velvet_jacket_hidden_pocket"),
        AspectTableEntry(9, 10, "A book of poetry that consists primarily of bleating", item_id="book_of_bleating_poetry"),
        AspectTableEntry(11, 12, "A bottle of noxious perfume that can be smelt up to half a mile away", item_id="bottle_of_noxious_perfume"),
        AspectTableEntry(13, 14, "A brass owl statue with eerie black eyes", item_id="brass_owl_statue_black_eyes"),
        AspectTableEntry(15, 16, "A broken fishing rod that still displays teeth marks from an enormous fish", item_id="broken_fishing_rod_teeth_marks"),
        AspectTableEntry(17, 18, "A circular ceramic amulet which displays the current moon phase", item_id="circular_ceramic_moon_amulet"),
        AspectTableEntry(19, 20, "A clay pot labelled 'Frog Paste,' containing what appears to be frog paste", item_id="clay_pot_frog_paste"),
        AspectTableEntry(21, 22, "A clump of writhing, black moss that you scraped off a looming monolith one lonely night", item_id="clump_writhing_black_moss"),
        AspectTableEntry(23, 24, "A collection of papers with scrawled notes detailing your life story, found on a stranger drowned in a ditch", item_id="collection_life_story_papers"),
        AspectTableEntry(25, 26, "A curious mossling wind instrument carved out of a gourd", item_id="mossling_wind_instrument_gourd"),
        AspectTableEntry(27, 28, "A diorama of two stuffed mice riding stuffed squirrels, jousting", item_id="diorama_mice_squirrels_jousting"),
        AspectTableEntry(29, 30, "A dried mushroom with a face", item_id="dried_mushroom_with_face"),
        AspectTableEntry(31, 32, "A folio of pressed sprite-wings", item_id="folio_pressed_sprite_wings"),
        AspectTableEntry(33, 34, "A gnarled root shaped like a mossling", item_id="gnarled_root_mossling_shaped"),
        AspectTableEntry(35, 36, "A letter warning that several high-ranked longhorns are secretly crookhorns in disguise", item_id="letter_warning_crookhorn_longhorns"),
        AspectTableEntry(37, 38, "A locket with a portrait of a fluffy cat wearing a crown inscribed 'For the love of King Pusskin'", item_id="locket_king_pusskin_portrait"),
        AspectTableEntry(39, 40, "A long-nosed masquerade mask", item_id="long_nosed_masquerade_mask"),
        AspectTableEntry(41, 42, "A moleskin wristband, anointed with exotic fairy perfume", item_id="moleskin_wristband_fairy_perfume"),
        AspectTableEntry(43, 44, "A mossling pipe that blows rainbow-coloured smoke rings", item_id="mossling_pipe_rainbow_smoke"),
        AspectTableEntry(45, 46, "A necklace of miscellaneous humanoid teeth", item_id="necklace_humanoid_teeth"),
        AspectTableEntry(47, 48, "A petrified turnip", item_id="petrified_turnip"),
        AspectTableEntry(49, 50, "A pig heart that oozes ichor when squeezed", item_id="pig_heart_oozing_ichor"),
        AspectTableEntry(51, 52, "A pouch which feels heavy (as if full of pebbles) even when empty", item_id="pouch_feels_heavy_when_empty"),
        AspectTableEntry(53, 54, "A rusty scalpel that once belonged to Lord Malbleat", item_id="rusty_scalpel_lord_malbleat"),
        AspectTableEntry(55, 56, "A sack of tasty fried chicken legs", item_id="sack_fried_chicken_legs"),
        AspectTableEntry(57, 58, "A scale said to be from a breggle with a fishtail instead of legs", item_id="scale_breggle_fishtail"),
        AspectTableEntry(59, 60, "A scroll containing a prophetic warning from an esteemed ancestor, almost indecipherable with age", item_id="scroll_prophetic_warning_ancestor"),
        AspectTableEntry(61, 62, "A sheet of parchment with a charcoal sketch of your long lost love", item_id="parchment_charcoal_sketch_love"),
        AspectTableEntry(63, 64, "A short length of silver cord and a delicate hook, said to catch fairy fish in puddles", item_id="silver_cord_delicate_hook"),
        AspectTableEntry(65, 66, "A shovel stained with the dirt of a thousand graves", item_id="shovel_thousand_graves_dirt"),
        AspectTableEntry(67, 68, "A stuffed vole dressed in a charming waistcoat", item_id="stuffed_vole_charming_waistcoat"),
        AspectTableEntry(69, 70, "A thigh-bone flute", item_id="thigh_bone_flute"),
        AspectTableEntry(71, 72, "A tin whistle whose tones drive cats wild", item_id="tin_whistle_drives_cats_wild"),
        AspectTableEntry(73, 74, "A tiny book of nonsense poetry, bound in purple leather", item_id="tiny_book_nonsense_poetry"),
        AspectTableEntry(75, 76, "A tiny painting of a four-horned goat", item_id="tiny_painting_four_horned_goat"),
        AspectTableEntry(77, 78, "A well-loved walking stick with a goat's head handle", item_id="walking_stick_goat_head_handle"),
        AspectTableEntry(79, 80, "A wooden Chapes (holy symbol of the Pluritine Church) studded with nails", item_id="wooden_chapes_studded_nails"),
        AspectTableEntry(81, 82, "An empty notebook where anything written disappears at sunrise", item_id="empty_notebook_disappearing_writing"),
        AspectTableEntry(83, 84, "An ornate pie pan, pilfered from a noble's kitchen", item_id="ornate_pie_pan_pilfered"),
        AspectTableEntry(85, 86, "Black stone dice with white skulls for pips", item_id="black_stone_dice_skull_pips"),
        AspectTableEntry(87, 88, "Expensive-looking (but worthless) jewellery, designed for breggle horns", item_id="worthless_breggle_horn_jewellery"),
        AspectTableEntry(89, 90, "String from the bow of a legendary hunter", item_id="string_legendary_hunter_bow"),
        AspectTableEntry(91, 92, "The board pieces for fairy chess, rules unknown", item_id="fairy_chess_board_pieces"),
        AspectTableEntry(93, 94, "The cured skin of a whole deer", item_id="cured_deer_skin_whole"),
        AspectTableEntry(95, 96, "The horn of an ancestor, hung from a necklace", item_id="ancestor_horn_necklace"),
        AspectTableEntry(97, 98, "The key to the prison cell you escaped from", item_id="prison_cell_key_escaped"),
        AspectTableEntry(99, 100, "Your grandmother's creepy glass eye, sometimes you feel her presence watching", item_id="grandmother_creepy_glass_eye"),
    ]
)


# =============================================================================
# COMPLETE BREGGLE DEFINITION
# =============================================================================

BREGGLE_DEFINITION = KindredDefinition(
    kindred_id="breggle",
    name="Breggle",
    description=(
        "The proud and stubborn breggles—sometimes called goatfolk (or hregl, in their "
        "own tongues)—have inhabited the High Wold since antiquity. Once the sole masters "
        "of that fertile region of hills, meadows, and tangled woods, the ancient breggle "
        "noble houses now rule alongside humans, swearing fealty to the Dukes of Brackenwold. "
        "Breggles live much as humans do, dwelling in hamlets, farmsteads, and castles. "
        "In the larger towns of the High Wold, breggles live side by side with humans."
    ),
    kindred_type=KindredType.MORTAL,

    physical=PhysicalRanges(
        # Age at Level 1: 15 + 2d10 years
        age_base=15,
        age_dice=DiceFormula(2, 10),
        # Lifespan: 50 + 2d20 years
        lifespan_base=50,
        lifespan_dice=DiceFormula(2, 20),
        # Height: 5'4" + 2d6" = 64 + 2d6 inches
        height_base=64,
        height_dice=DiceFormula(2, 6),
        # Weight: 120 + 6d10 lbs
        weight_base=120,
        weight_dice=DiceFormula(6, 10),
        size="Medium",
    ),

    native_languages=["Woldish", "Gaffe", "Caprice"],

    abilities=[
        BREGGLE_FUR_ABILITY,
        BREGGLE_HORNS_ABILITY,
        BREGGLE_GAZE_ABILITY,
    ],

    level_progression=BREGGLE_PROGRESSION,

    preferred_classes=["Fighter", "Knight", "Magician"],
    restricted_classes=["Cleric", "Friar", "Enchanter"],

    name_table=BREGGLE_NAME_TABLE,

    aspect_tables={
        AspectType.BACKGROUND: BREGGLE_BACKGROUND_TABLE,
        AspectType.HEAD: BREGGLE_HEAD_TABLE,
        AspectType.DEMEANOUR: BREGGLE_DEMEANOUR_TABLE,
        AspectType.DESIRES: BREGGLE_DESIRES_TABLE,
        AspectType.FACE: BREGGLE_FACE_TABLE,
        AspectType.DRESS: BREGGLE_DRESS_TABLE,
        AspectType.BELIEFS: BREGGLE_BELIEFS_TABLE,
        AspectType.FUR_BODY: BREGGLE_FUR_TABLE,
        AspectType.SPEECH: BREGGLE_SPEECH_TABLE,
        AspectType.TRINKET: BREGGLE_TRINKET_TABLE,
    },

    trinket_item_ids=[
        "bag_of_divination_stones", "bloodstained_jesters_hat", "bloody_knife_uncleaned",
        "blue_velvet_jacket_hidden_pocket", "book_of_bleating_poetry", "bottle_of_noxious_perfume",
        "brass_owl_statue_black_eyes", "broken_fishing_rod_teeth_marks", "circular_ceramic_moon_amulet",
        "clay_pot_frog_paste", "clump_writhing_black_moss", "collection_life_story_papers",
        "mossling_wind_instrument_gourd", "diorama_mice_squirrels_jousting", "dried_mushroom_with_face",
        "folio_pressed_sprite_wings", "gnarled_root_mossling_shaped", "letter_warning_crookhorn_longhorns",
        "locket_king_pusskin_portrait", "long_nosed_masquerade_mask", "moleskin_wristband_fairy_perfume",
        "mossling_pipe_rainbow_smoke", "necklace_humanoid_teeth", "petrified_turnip",
        "pig_heart_oozing_ichor", "pouch_feels_heavy_when_empty", "rusty_scalpel_lord_malbleat",
        "sack_fried_chicken_legs", "scale_breggle_fishtail", "scroll_prophetic_warning_ancestor",
        "parchment_charcoal_sketch_love", "silver_cord_delicate_hook", "shovel_thousand_graves_dirt",
        "stuffed_vole_charming_waistcoat", "thigh_bone_flute", "tin_whistle_drives_cats_wild",
        "tiny_book_nonsense_poetry", "tiny_painting_four_horned_goat", "walking_stick_goat_head_handle",
        "wooden_chapes_studded_nails", "empty_notebook_disappearing_writing", "ornate_pie_pan_pilfered",
        "black_stone_dice_skull_pips", "worthless_breggle_horn_jewellery", "string_legendary_hunter_bow",
        "fairy_chess_board_pieces", "cured_deer_skin_whole", "ancestor_horn_necklace",
        "prison_cell_key_escaped", "grandmother_creepy_glass_eye",
    ],

    kindred_relations=(
        "Breggles are on friendly terms with mortal and demi-fey Kindreds. Most "
        "non-adventuring breggles have never met a fairy and regard them with awe, "
        "wonder, and caution. Breggle folklore is filled with tales of the ancient "
        "nobility of fairies, as well as their tricksome magic. In human settlements "
        "within the High Wold, breggles are a commonplace sight, many living alongside "
        "humans. Further afield, humans tend to treat them with respect and caution, "
        "as the power of the longhorn noble houses is known and feared."
    ),

    religion_notes=(
        "As subjects of the duke, breggles are nominally adherents of the Pluritine "
        "Church. True devotion to the Church is, however, rare among breggles, who "
        "prefer to offer up prayers to esteemed ancestors from their long history."
    ),

    source_book="Dolmenwood Player Book",
    source_page=32,
)
