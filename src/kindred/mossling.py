"""
Mossling kindred definition for Dolmenwood.

Gnarled, woody humanoids whose fertile flesh hosts mosses, moulds, and fungi.
Source: Dolmenwood Player Book, pages 48-51
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
# MOSSLING ABILITIES
# =============================================================================

MOSSLING_KNACKS_ABILITY = KindredAbility(
    ability_id="mossling_knacks",
    name="Knacks",
    description=(
        "Mosslings practice carefully guarded, quasi-magical crafts known as knacks. "
        "Each mossling knows one knack, rolled or chosen at character creation."
    ),
    is_passive=True,
    extra_data={
        "knack_count": 1,
        "see_reference": "Mossling Knacks, p112",
    },
)

MOSSLING_SKILLS_ABILITY = KindredAbility(
    ability_id="mossling_skills",
    name="Mossling Skills",
    description=(
        "Mosslings have a Skill Target of 5 for Survival when foraging."
    ),
    is_passive=True,
    extra_data={
        "skill_bonuses": {
            "survival_foraging": {"target": 5},
        },
    },
)

MOSSLING_RESILIENCE_ABILITY = KindredAbility(
    ability_id="mossling_resilience",
    name="Resilience",
    description=(
        "Mosslings are hardy and resilient like the gnarled bole of an old tree. "
        "They gain a +4 bonus to Saving Throws against fungal spores or poisons "
        "and a +2 bonus to all other Saving Throws."
    ),
    is_passive=True,
    extra_data={
        "save_bonus_fungal_poison": 4,
        "save_bonus_other": 2,
    },
)

MOSSLING_SYMBIOTIC_FLESH_ABILITY = KindredAbility(
    ability_id="mossling_symbiotic_flesh",
    name="Symbiotic Flesh",
    description=(
        "As a mossling ages, their dank, fertile flesh picks up seeds and spores "
        "which germinate into symbiotic plants and fungi. At each Level (including "
        "Level 1), the character acquires a random trait from the Symbiotic Flesh table. "
        "Duplicates may be re-rolled or taken to indicate an amplification of the trait."
    ),
    is_passive=True,
    extra_data={
        "trait_per_level": True,
        "symbiotic_flesh_table": [
            "Outer parts of ears replaced by jelly fungus",
            "Patches of lichen",
            "Dainty flowers bloom in the beard in springtime",
            "Yeast infections in moist places",
            "Toadstools growing from joints",
            "Covered in slimy, green jelly",
            "Miniature tree growing from ear",
            "Skin riddled with mycelia",
            "Eyes fur over with transparent, yellow mould",
            "Edible toe cheese",
            "Growths of woody, bracket fungus in the armpits",
            "Mossy feet",
            "Climbing vines wrapped around limbs and torso",
            "Radical fern growth around groin",
            "Mossy biceps",
            "Puffball growths around the buttocks and knees",
            "Parsley chest hair",
            "Blackberry brambles tangled in the hair",
            "Edible mushrooms growing in hair",
            "Semi-sentient mushroom growing from top of head",
        ],
    },
)


# =============================================================================
# MOSSLING NAME TABLE
# =============================================================================

MOSSLING_NAME_TABLE = NameTable(
    columns={
        NameColumn.MALE: [
            "Dombo", "Gobd", "Gobulom", "Golobd", "Gremo",
            "Gwomotom", "Hollogowl", "Kabob", "Kollobom", "Limbly",
            "Loblow", "Mobdemold", "Nyoma", "Obolm", "Oglom",
            "Omb", "Shmold", "Slumbred", "Umbertop", "Wobobold",
        ],
        NameColumn.FEMALE: [
            "Bilibom", "Brimbul", "Ebbli", "Ghibli", "Gobbli",
            "Gwedim", "Higwold", "Ibulold", "Imbwi", "Klibli",
            "Klimbim", "Libib", "Limimb", "Marib", "Milik",
            "Shlirimi", "Shobd", "Skimbim", "Slimpk", "Smodri",
        ],
        NameColumn.UNISEX: [
            "Bendiom", "Blobul", "Ebdwol", "Glob", "Gombly",
            "Greblim", "Gwoodwom", "Hollb", "Klolb", "Kwolotomb",
            "Lambop", "Morromb", "Mwoomb", "Olob", "Oobl",
            "Shlurbel", "Smodron", "Tomdown", "Tomumbolo", "Worrib",
        ],
        NameColumn.SURNAME: [
            "Barkhop", "Conker", "Danklow", "Fernhead", "Frother",
            "Grimehump", "Hogscap", "Mossbeard", "Mossfurrow", "Mould",
            "Mouldfinger", "Mudfoot", "Mugfoam", "Mulchwump", "Mushrump",
            "Oddpolyp", "Puffhelm", "Smallcheese", "Sodwallow", "Twiggler",
        ],
    }
)


# =============================================================================
# MOSSLING ASPECT TABLES
# =============================================================================

MOSSLING_BACKGROUND_TABLE = AspectTable(
    aspect_type=AspectType.BACKGROUND,
    die_size=20,
    entries=[
        AspectTableEntry(1, 1, "Bark tailor"),
        AspectTableEntry(2, 2, "Boar hunter"),
        AspectTableEntry(3, 3, "Cheesemaker"),
        AspectTableEntry(4, 4, "Compost raker"),
        AspectTableEntry(5, 5, "Fungologist"),
        AspectTableEntry(6, 6, "Fungus farmer"),
        AspectTableEntry(7, 7, "Gambler"),
        AspectTableEntry(8, 8, "Horn blower"),
        AspectTableEntry(9, 9, "Moss brewer"),
        AspectTableEntry(10, 10, "Moss farmer"),
        AspectTableEntry(11, 11, "Night forager"),
        AspectTableEntry(12, 12, "Oracle's apprentice"),
        AspectTableEntry(13, 13, "Pipe maker"),
        AspectTableEntry(14, 14, "Sausage maker"),
        AspectTableEntry(15, 15, "Squirrel trainer"),
        AspectTableEntry(16, 16, "Swineherd"),
        AspectTableEntry(17, 17, "Tavernkeep"),
        AspectTableEntry(18, 18, "Vagrant"),
        AspectTableEntry(19, 19, "Worm farmer"),
        AspectTableEntry(20, 20, "Yeast farmer"),
    ]
)

MOSSLING_HEAD_TABLE = AspectTable(
    aspect_type=AspectType.HEAD,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Bald like a polished nut"),
        AspectTableEntry(2, 2, "Buzzing with flies"),
        AspectTableEntry(3, 3, "Floppy hat droops over eyes"),
        AspectTableEntry(4, 4, "Fuzzy green hair"),
        AspectTableEntry(5, 5, "Huge floppy ears"),
        AspectTableEntry(6, 6, "Long greasy hair"),
        AspectTableEntry(7, 7, "Much too big"),
        AspectTableEntry(8, 8, "No neck"),
        AspectTableEntry(9, 9, "Patchy orange hair"),
        AspectTableEntry(10, 10, "Pointy felt hat"),
        AspectTableEntry(11, 11, "Wobbly"),
        AspectTableEntry(12, 12, "Wrinkled like a walnut"),
    ]
)

MOSSLING_DEMEANOUR_TABLE = AspectTable(
    aspect_type=AspectType.DEMEANOUR,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Blustery"),
        AspectTableEntry(2, 2, "Brooding"),
        AspectTableEntry(3, 3, "Cowardly"),
        AspectTableEntry(4, 4, "Dozy"),
        AspectTableEntry(5, 5, "Flustered"),
        AspectTableEntry(6, 6, "Grumpy"),
        AspectTableEntry(7, 7, "Impertinent"),
        AspectTableEntry(8, 8, "Lethargic"),
        AspectTableEntry(9, 9, "Miserly"),
        AspectTableEntry(10, 10, "Overbearingly affable"),
        AspectTableEntry(11, 11, "Shrewd"),
        AspectTableEntry(12, 12, "Tells terrible jokes"),
    ]
)

MOSSLING_DESIRES_TABLE = AspectTable(
    aspect_type=AspectType.DESIRES,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "A dozen spouses"),
        AspectTableEntry(2, 2, "Acquire moon cheese"),
        AspectTableEntry(3, 3, "Become a fungus giant"),
        AspectTableEntry(4, 4, "Breed a sentient swine"),
        AspectTableEntry(5, 5, "Brew the universal elixir"),
        AspectTableEntry(6, 6, "Consume sentient fungi"),
        AspectTableEntry(7, 7, "Found a moss brewery"),
        AspectTableEntry(8, 8, "Found underground realm"),
        AspectTableEntry(9, 9, "Grow clones of self"),
        AspectTableEntry(10, 10, "Meld with the fungal mind"),
        AspectTableEntry(11, 11, "Own a sprawling inn"),
        AspectTableEntry(12, 12, "Sample all known ales"),
    ]
)

MOSSLING_FACE_TABLE = AspectTable(
    aspect_type=AspectType.FACE,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Beard of frothy yeast"),
        AspectTableEntry(2, 2, "Darting tongue"),
        AspectTableEntry(3, 3, "Eyes as big as fists"),
        AspectTableEntry(4, 4, "Eyes like pools of deep space"),
        AspectTableEntry(5, 5, "Eyes like tiny black marbles"),
        AspectTableEntry(6, 6, "Long, floppy nose"),
        AspectTableEntry(7, 7, "Looks like a carved potato"),
        AspectTableEntry(8, 8, "Massive flared nostrils"),
        AspectTableEntry(9, 9, "Mouth foaming with yeast"),
        AspectTableEntry(10, 10, "Nostrils ooze purple slime"),
        AspectTableEntry(11, 11, "Pointy root nose"),
        AspectTableEntry(12, 12, "Wobbly lips"),
    ]
)

MOSSLING_DRESS_TABLE = AspectTable(
    aspect_type=AspectType.DRESS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Brushed felt"),
        AspectTableEntry(2, 2, "Cosy knitwear"),
        AspectTableEntry(3, 3, "Dapper tweed"),
        AspectTableEntry(4, 4, "Greasy leathers"),
        AspectTableEntry(5, 5, "Grubby rags"),
        AspectTableEntry(6, 6, "Knitted ivy"),
        AspectTableEntry(7, 7, "Loincloth"),
        AspectTableEntry(8, 8, "Naturist"),
        AspectTableEntry(9, 9, "Pelts"),
        AspectTableEntry(10, 10, "Pig suede"),
        AspectTableEntry(11, 11, "Scratchy wool"),
        AspectTableEntry(12, 12, "Woven fungus stems"),
    ]
)

MOSSLING_BELIEFS_TABLE = AspectTable(
    aspect_type=AspectType.BELIEFS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Ale is essential for life"),
        AspectTableEntry(2, 2, "Bathing is inimical to health"),
        AspectTableEntry(3, 3, "Daily sacrifice to the elders"),
        AspectTableEntry(4, 4, "Gets visions from the moon"),
        AspectTableEntry(5, 5, "Humans are naked monkeys"),
        AspectTableEntry(6, 6, "Pursued by vengeful ghosts"),
        AspectTableEntry(7, 7, "Stone circles hide buried gold"),
        AspectTableEntry(8, 8, "Talking owls are plotting"),
        AspectTableEntry(9, 9, "The Drune will conquer all"),
        AspectTableEntry(10, 10, "The duke is secretly a fairy"),
        AspectTableEntry(11, 11, "The fungal mind is supreme"),
        AspectTableEntry(12, 12, "The trees have eyes"),
    ]
)

MOSSLING_BODY_TABLE = AspectTable(
    aspect_type=AspectType.FUR_BODY,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Blubbery"),
        AspectTableEntry(2, 2, "Covered in downy fur"),
        AspectTableEntry(3, 3, "Flabby rolls"),
        AspectTableEntry(4, 4, "Lumpy"),
        AspectTableEntry(5, 5, "Rampant belly button fur"),
        AspectTableEntry(6, 6, "Spherical"),
        AspectTableEntry(7, 7, "Stubby legs"),
        AspectTableEntry(8, 8, "Stumpy arms"),
        AspectTableEntry(9, 9, "Whorled like knotted wood"),
        AspectTableEntry(10, 10, "Wider than tall"),
        AspectTableEntry(11, 11, "Wobbly paunch"),
        AspectTableEntry(12, 12, "Wrinkled folds of skin"),
    ]
)

MOSSLING_SPEECH_TABLE = AspectTable(
    aspect_type=AspectType.SPEECH,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Baritone"),
        AspectTableEntry(2, 2, "Filthy"),
        AspectTableEntry(3, 3, "Grumbling"),
        AspectTableEntry(4, 4, "Meandering"),
        AspectTableEntry(5, 5, "Mumbling"),
        AspectTableEntry(6, 6, "Muttering"),
        AspectTableEntry(7, 7, "Obtuse"),
        AspectTableEntry(8, 8, "Phlegmy"),
        AspectTableEntry(9, 9, "Squeaking"),
        AspectTableEntry(10, 10, "Squelchy"),
        AspectTableEntry(11, 11, "Stammering"),
        AspectTableEntry(12, 12, "Wheezy"),
    ]
)

# Trinket table - references item IDs in adventuring_gear_mossling_trinkets.json
MOSSLING_TRINKET_TABLE = AspectTable(
    aspect_type=AspectType.TRINKET,
    die_size=100,
    entries=[
        AspectTableEntry(1, 2, "A bag of stone marbles. Each has a name and rolls towards whoever speaks it", item_id="bag_of_stone_marbles"),
        AspectTableEntry(3, 4, "A block of cheese infected with hallucinogenic fungus", item_id="hallucinogenic_cheese_block"),
        AspectTableEntry(5, 6, "A bloodstained hat that once belonged to a redcap", item_id="bloodstained_redcap_hat"),
        AspectTableEntry(7, 8, "A book alleging crimes by each of the 100 saints of Dolmenwood. Found on the body of a murdered man", item_id="saints_crime_book"),
        AspectTableEntry(9, 10, "A bottle of yeast-froth shampoo, essential for maintaining the lustre of mossy manes", item_id="yeast_froth_shampoo"),
        AspectTableEntry(11, 12, "A bouquet of honeysuckle that drips real honey. The honey attracts wasps", item_id="honeysuckle_bouquet"),
        AspectTableEntry(13, 14, "A brass cowbell. When struck, nearby milk and cheese products jump half a foot towards it", item_id="brass_cowbell"),
        AspectTableEntry(15, 16, "A broad-brimmed hat covered in shimmering moss", item_id="moss_covered_hat"),
        AspectTableEntry(17, 18, "A bronze idol to a two-headed mushroom god", item_id="bronze_mushroom_idol"),
        AspectTableEntry(19, 20, "A chunk of volcanic rock, warm to the touch. A single Old Woldish rune has been carved into it", item_id="volcanic_rock_chunk"),
        AspectTableEntry(21, 22, "A clay figurine of a pot-bellied giant with a single eye", item_id="clay_giant_figurine"),
        AspectTableEntry(23, 24, "A cluster of fungus consisting of a dozen different kinds of mushrooms living in symbiosis", item_id="symbiotic_fungus_cluster"),
        AspectTableEntry(25, 26, "A collection of small rocks, all chipped from different gravestones", item_id="gravestone_rock_collection"),
        AspectTableEntry(27, 28, "A cooking pot that adds mushrooms to every dish cooked inside it", item_id="mushroom_cooking_pot"),
        AspectTableEntry(29, 30, "A flower pressed inside a dead man's journal", item_id="pressed_flower_journal"),
        AspectTableEntry(31, 32, "A hunting horn fashioned from a great boar tusk", item_id="boar_tusk_hunting_horn"),
        AspectTableEntry(33, 34, "A jar of blue cheese massage oil", item_id="blue_cheese_massage_oil"),
        AspectTableEntry(35, 36, "A jar of green jelly with the label 'Don't Eat Me'", item_id="green_jelly_jar"),
        AspectTableEntry(37, 38, "A large egg, entrusted to you by a panicked woodgrue", item_id="woodgrue_egg"),
        AspectTableEntry(39, 40, "A large gooseberry that appears to have a creature growing inside it", item_id="creature_gooseberry"),
        AspectTableEntry(41, 42, "A large, pink sausage. Tries to crawl away if left unattended", item_id="crawling_pink_sausage"),
        AspectTableEntry(43, 44, "A leaf that changes with the seasons, dying by winter only to rejuvenate in spring", item_id="seasonal_leaf"),
        AspectTableEntry(45, 46, "A mossy rock. When placed on the ground for at least a minute and then lifted, bugs scurry out from underneath it", item_id="bug_spawning_mossy_rock"),
        AspectTableEntry(47, 48, "A mould-riddled tapestry depicting the hunt for a swine of mythic size", item_id="swine_hunt_tapestry"),
        AspectTableEntry(49, 50, "A puffball with dozens of tiny mouths which burp in unison at dawn", item_id="burping_puffball"),
        AspectTableEntry(51, 52, "A puffball-skin pouch filled with jelly", item_id="puffball_jelly_pouch"),
        AspectTableEntry(53, 54, "A sack of half-empty ale bottles", item_id="half_empty_ale_bottles"),
        AspectTableEntry(55, 56, "A sealed bottle of spirits, brewed from the composted remains of one of your ancestors", item_id="ancestor_spirits_bottle"),
        AspectTableEntry(57, 58, "A shepherd's crook that induces fear in farm animals when brandished", item_id="fear_inducing_shepherds_crook"),
        AspectTableEntry(59, 60, "A single hair from the head of an elven lady; a token of her affection", item_id="elven_lady_hair"),
        AspectTableEntry(61, 62, "A small beetle you found on the road. You have since received a letter from an angry grimalkin charging you with its theft", item_id="stolen_beetle"),
        AspectTableEntry(63, 64, "A small effigy of a breggle made from dried mushroom flesh", item_id="breggle_effigy"),
        AspectTableEntry(65, 66, "A small pouch of magic nuts. When a nut is broken open, it emits a pearl of wisdom", item_id="magic_wisdom_nuts"),
        AspectTableEntry(67, 68, "A small snake with a 'Return to' note attached. The owner's name is smudged out", item_id="return_snake"),
        AspectTableEntry(69, 70, "A small, hollow toadstool with a tiny wooden door", item_id="tiny_toadstool_house"),
        AspectTableEntry(71, 72, "A snail shell that grows a new snail at dawn if the old one is removed or killed", item_id="regenerating_snail_shell"),
        AspectTableEntry(73, 74, "A squirrel-sized collar and leash", item_id="squirrel_collar_and_leash"),
        AspectTableEntry(75, 76, "A story book about the charming exploits of the rat-people of the moon", item_id="moon_rat_people_story_book"),
        AspectTableEntry(77, 78, "A unique pipeweed mix of your own invention. A bit too combustible", item_id="combustible_pipeweed"),
        AspectTableEntry(79, 80, "A watering can that constantly trickles water from its spout", item_id="trickling_watering_can"),
        AspectTableEntry(81, 82, "A waterskin of yellow slime that drips upwards when unstoppered", item_id="upward_dripping_waterskin"),
        AspectTableEntry(83, 84, "A wheel of cheese that never loses momentum once it starts rolling", item_id="perpetual_cheese_wheel"),
        AspectTableEntry(85, 86, "A wooden carving of yourself that ages as you do", item_id="aging_wooden_carving"),
        AspectTableEntry(87, 88, "A wooden peg leg that you found and converted into an incubator for rare fungi", item_id="fungi_incubator_peg_leg"),
        AspectTableEntry(89, 90, "A worm whose squirming slowly spells out threatening prophecies", item_id="prophecy_worm"),
        AspectTableEntry(91, 92, "An adorable red-and-white button mushroom. Whispers to you when no one else is listening", item_id="whispering_mushroom"),
        AspectTableEntry(93, 94, "An incomplete, and possibly inaccurate, map of all the inns in Dolmenwood", item_id="dolmenwood_inn_map"),
        AspectTableEntry(95, 96, "An onion shaped like a baby", item_id="baby_shaped_onion"),
        AspectTableEntry(97, 98, "Blueprints for a marvellous mechanical mouse organ clock", item_id="mouse_organ_clock_blueprints"),
        AspectTableEntry(99, 100, "Dozens of different kinds of bark, stitched together like a book", item_id="bark_book"),
    ]
)


# =============================================================================
# COMPLETE MOSSLING DEFINITION
# =============================================================================

MOSSLING_DEFINITION = KindredDefinition(
    kindred_id="mossling",
    name="Mossling",
    description=(
        "Gnarled, woody humanoids whose fertile flesh hosts mosses, moulds, and fungi. "
        "Mosslings are an obscure, stunted folk native to Dolmenwood, with an affinity "
        "for the dank plants and moulds of the deep woods. They are of stocky, pudgy build, "
        "with green, yellow, or brown skin, textured like wrinkled bark and patched with "
        "mould, lichen, fungus, and creeping plants. Their hair and beards are green or "
        "black and plant-like, akin to moss, ferns, or tangled roots. If injured, mosslings "
        "ooze white, sap-like blood."
    ),
    kindred_type=KindredType.MORTAL,

    physical=PhysicalRanges(
        # Age at Level 1: 50 + 3d6 years
        age_base=50,
        age_dice=DiceFormula(3, 6),
        # Lifespan: 200 + 5d8 × 10 years
        lifespan_base=200,
        lifespan_dice=DiceFormula(5, 8),
        # Height: 3'6" + 2d6" (Small)
        height_base=42,  # 3'6" = 42 inches
        height_dice=DiceFormula(2, 6),
        # Weight: 150 + 2d20 lbs
        weight_base=150,
        weight_dice=DiceFormula(2, 20),
        size="Small",
        extra_data={
            "lifespan_multiplier": 10,  # Lifespan dice result is multiplied by 10
        },
    ),

    native_languages=["Woldish", "Mulch"],

    abilities=[
        MOSSLING_KNACKS_ABILITY,
        MOSSLING_SKILLS_ABILITY,
        MOSSLING_RESILIENCE_ABILITY,
        MOSSLING_SYMBIOTIC_FLESH_ABILITY,
    ],

    level_progression=[],  # Mosslings use symbiotic flesh table per level instead

    preferred_classes=["Fighter", "Hunter"],
    restricted_classes=["Knight", "Cleric", "Friar", "Enchanter"],

    name_table=MOSSLING_NAME_TABLE,

    aspect_tables={
        AspectType.BACKGROUND: MOSSLING_BACKGROUND_TABLE,
        AspectType.HEAD: MOSSLING_HEAD_TABLE,
        AspectType.DEMEANOUR: MOSSLING_DEMEANOUR_TABLE,
        AspectType.DESIRES: MOSSLING_DESIRES_TABLE,
        AspectType.FACE: MOSSLING_FACE_TABLE,
        AspectType.DRESS: MOSSLING_DRESS_TABLE,
        AspectType.BELIEFS: MOSSLING_BELIEFS_TABLE,
        AspectType.FUR_BODY: MOSSLING_BODY_TABLE,
        AspectType.SPEECH: MOSSLING_SPEECH_TABLE,
        AspectType.TRINKET: MOSSLING_TRINKET_TABLE,
    },

    trinket_item_ids=[
        "bag_of_stone_marbles", "hallucinogenic_cheese_block", "bloodstained_redcap_hat",
        "saints_crime_book", "yeast_froth_shampoo", "honeysuckle_bouquet",
        "brass_cowbell", "moss_covered_hat", "bronze_mushroom_idol",
        "volcanic_rock_chunk", "clay_giant_figurine", "symbiotic_fungus_cluster",
        "gravestone_rock_collection", "mushroom_cooking_pot", "pressed_flower_journal",
        "boar_tusk_hunting_horn", "blue_cheese_massage_oil", "green_jelly_jar",
        "woodgrue_egg", "creature_gooseberry", "crawling_pink_sausage",
        "seasonal_leaf", "bug_spawning_mossy_rock", "swine_hunt_tapestry",
        "burping_puffball", "puffball_jelly_pouch", "half_empty_ale_bottles",
        "ancestor_spirits_bottle", "fear_inducing_shepherds_crook", "elven_lady_hair",
        "stolen_beetle", "breggle_effigy", "magic_wisdom_nuts",
        "return_snake", "tiny_toadstool_house", "regenerating_snail_shell",
        "squirrel_collar_and_leash", "moon_rat_people_story_book", "combustible_pipeweed",
        "trickling_watering_can", "upward_dripping_waterskin", "perpetual_cheese_wheel",
        "aging_wooden_carving", "fungi_incubator_peg_leg", "prophecy_worm",
        "whispering_mushroom", "dolmenwood_inn_map", "baby_shaped_onion",
        "mouse_organ_clock_blueprints", "bark_book",
    ],

    kindred_relations=(
        "Mosslings are on friendly terms with mortal and demi-fey Kindreds. While most "
        "non-adventuring mosslings have never met a fairy, they tend to treat fairies "
        "with curiosity as wanderers from afar with tales to share. Mosslings are welcomed "
        "in human settlements in Dolmenwood, where they sometimes travel to sell mushrooms, "
        "ale, or cheese at a market."
    ),

    religion_notes=(
        "As subjects of the Duke of Brackenwold, mosslings are nominally adherents of the "
        "Pluritine Church. However, in practice they worship their own gods of the deep "
        "forest and the fecund underworld—see Mogba, p179."
    ),

    source_book="Dolmenwood Player Book",
    source_page=48,
)
