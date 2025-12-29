"""
Elf kindred definition for Dolmenwood.

Ageless fairies who have crossed into the mortal world for reasons they seldom reveal.
Source: Dolmenwood Player Book, pages 36-39
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
# ELF ABILITIES
# =============================================================================

ELF_SKILLS_ABILITY = KindredAbility(
    ability_id="elf_skills",
    name="Elf Skills",
    description="Elves have a Skill Target of 5 for Listen and Search.",
    is_passive=True,
    extra_data={
        "skill_targets": {
            "listen": 5,
            "search": 5,
        }
    },
)

ELF_GLAMOURS_ABILITY = KindredAbility(
    ability_id="elf_glamours",
    name="Glamours",
    description=(
        "Elves possess minor magical talents known as glamours. "
        "Each elf knows a single, randomly determined glamour."
    ),
    is_passive=False,
    extra_data={
        "glamour_count": 1,
        "randomly_determined": True,
    },
)

ELF_IMMORTALITY_ABILITY = KindredAbility(
    ability_id="elf_immortality",
    name="Immortality",
    description=(
        "Elves can be killed but do not die naturally. They are immune to "
        "diseases of non-magical origin. Elves also cannot die of thirst or "
        "starvation, though a lack of sustenance drives them desperate and sadistic."
    ),
    is_passive=True,
    extra_data={
        "immune_to": ["natural_death", "non_magical_disease", "starvation", "thirst"],
        "starvation_effect": "becomes desperate and sadistic",
    },
)

ELF_MAGIC_RESISTANCE_ABILITY = KindredAbility(
    ability_id="elf_magic_resistance",
    name="Magic Resistance",
    description=(
        "As beings of Fairy, where magic is in the very fabric of things, "
        "elves are highly resistant to magic. They gain +2 Magic Resistance."
    ),
    is_passive=True,
    extra_data={
        "magic_resistance_bonus": 2,
    },
)

ELF_UNEARTHLY_BEAUTY_ABILITY = KindredAbility(
    ability_id="elf_unearthly_beauty",
    name="Unearthly Beauty",
    description=(
        "Elves—both benevolent and wicked—are beautiful by mortal standards. "
        "When interacting with mortals, an elf gains a +2 bonus to Charisma "
        "(to a maximum of 18)."
    ),
    is_passive=True,
    extra_data={
        "charisma_bonus": 2,
        "charisma_max": 18,
        "applies_to": "mortal_interactions",
    },
)

ELF_COLD_IRON_VULNERABILITY_ABILITY = KindredAbility(
    ability_id="elf_cold_iron_vulnerability",
    name="Vulnerable to Cold Iron",
    description=(
        "As fairies, cold iron weapons inflict +1 damage on elves. "
        "(e.g. a cold iron shortsword would inflict 1d6+1 damage on an elf, "
        "rather than the standard 1d6)."
    ),
    is_passive=True,
    extra_data={
        "cold_iron_extra_damage": 1,
        "is_vulnerability": True,
    },
)


# =============================================================================
# ELF NAME TABLE
# =============================================================================

ELF_NAME_TABLE = NameTable(
    columns={
        NameColumn.RUSTIC: [
            "Bucket-and-Broth", "Candle-Bent-Sidewise", "Glance-Askew-Guillem",
            "Jack-of-Many-Colours", "Lace-and-Polkadot", "Lament-of-Bones-Broken",
            "Lightly-Come-Softly", "Lillies-o'er-Heartsight", "Prick-of-the-Nail",
            "Silver-and-Quicksilver", "Spring-to-the-Queen", "Sprue-Upon-Gallows",
            "Sun's-Turning-Tide", "Supper-Before-Noon", "Too-Soon-Begotten",
            "Trick-of-the-Light", "Tryst-about-Town", "Tumble-and-Thimble",
            "Wine-By-The-Goblet", "Youth-Turned-Curdled",
        ],
        NameColumn.COURTLY: [
            "Begets-Only-Dreams", "Breath-Upon-Candlelight", "Chalice-of-Duskviolet",
            "Dream-of-Remembrance", "Gleanings-of-Lost-Days", "Hands-Bound-By-Crows",
            "Impudence-Hath-Victory", "Indigo-and-Patchwork", "Marry-No-Man",
            "Morning's-Last-Mists", "Murder-of-Ravens", "Quavering-of-Night",
            "Revenge's-Sweet-Scent", "Seven-Steps-At-Dawn", "Shade-of-Winter-Betrayal",
            "Shallow-Pained-Plight", "Shallow-Spirit's-Lament", "Slips-Behind-Shadows",
            "Spring-Noon's-Arrogance", "Violet-and-Clementine",
        ],
    }
)


# =============================================================================
# ELF ASPECT TABLES
# =============================================================================

ELF_BACKGROUND_TABLE = AspectTable(
    aspect_type=AspectType.BACKGROUND,
    die_size=20,
    entries=[
        AspectTableEntry(1, 1, "Chronicler"),
        AspectTableEntry(2, 2, "Coiffeur"),
        AspectTableEntry(3, 3, "Confectioner"),
        AspectTableEntry(4, 4, "Courtier"),
        AspectTableEntry(5, 5, "Dream thief"),
        AspectTableEntry(6, 6, "Elk hunter"),
        AspectTableEntry(7, 7, "Explorer"),
        AspectTableEntry(8, 8, "Frost sculptor"),
        AspectTableEntry(9, 9, "Harpist"),
        AspectTableEntry(10, 10, "Highway robber"),
        AspectTableEntry(11, 11, "Librarian"),
        AspectTableEntry(12, 12, "Mountebank"),
        AspectTableEntry(13, 13, "Nut forager"),
        AspectTableEntry(14, 14, "Peacock trainer"),
        AspectTableEntry(15, 15, "Poet"),
        AspectTableEntry(16, 16, "Swordsmith"),
        AspectTableEntry(17, 17, "Tailor"),
        AspectTableEntry(18, 18, "Thespian"),
        AspectTableEntry(19, 19, "Unicorn handler"),
        AspectTableEntry(20, 20, "Vintner"),
    ]
)

ELF_HEAD_TABLE = AspectTable(
    aspect_type=AspectType.HEAD,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Delicate, pointed ears"),
        AspectTableEntry(2, 2, "Floppy, ass-like ears"),
        AspectTableEntry(3, 3, "Flowing, silver hair"),
        AspectTableEntry(4, 4, "Foppish wig"),
        AspectTableEntry(5, 5, "Glossy, iridescent hair"),
        AspectTableEntry(6, 6, "Gold hair at day, grey at night"),
        AspectTableEntry(7, 7, "Hair as white as snow"),
        AspectTableEntry(8, 8, "Hair like cobwebs"),
        AspectTableEntry(9, 9, "Lustrous, waist-length hair"),
        AspectTableEntry(10, 10, "Ragged, cropped hair"),
        AspectTableEntry(11, 11, "Shadowy locks"),
        AspectTableEntry(12, 12, "Small, ivory horn nubs"),
    ]
)

ELF_DEMEANOUR_TABLE = AspectTable(
    aspect_type=AspectType.DEMEANOUR,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Affected nobility"),
        AspectTableEntry(2, 2, "Aloof and amoral"),
        AspectTableEntry(3, 3, "Childlike and mischievous"),
        AspectTableEntry(4, 4, "Decadent"),
        AspectTableEntry(5, 5, "Gleeful enthusiasm"),
        AspectTableEntry(6, 6, "Keenly naive"),
        AspectTableEntry(7, 7, "Loquacious"),
        AspectTableEntry(8, 8, "Melancholic aesthete"),
        AspectTableEntry(9, 9, "Obsessive"),
        AspectTableEntry(10, 10, "Sardonic observer"),
        AspectTableEntry(11, 11, "Wilful and whimsical"),
        AspectTableEntry(12, 12, "World-weary"),
    ]
)

ELF_DESIRES_TABLE = AspectTable(
    aspect_type=AspectType.DESIRES,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Break mortal hearts"),
        AspectTableEntry(2, 2, "Collect exotic stuffed beasts"),
        AspectTableEntry(3, 3, "Depose fairy lord or lady"),
        AspectTableEntry(4, 4, "Distil wines from emotions"),
        AspectTableEntry(5, 5, "Forbidden arcane lore"),
        AspectTableEntry(6, 6, "Library of dreams"),
        AspectTableEntry(7, 7, "Odd magical trinkets"),
        AspectTableEntry(8, 8, "Return of the Cold Prince"),
        AspectTableEntry(9, 9, "Savour finest of mortal life"),
        AspectTableEntry(10, 10, "To grow old and die"),
        AspectTableEntry(11, 11, "Understand mortal religion"),
        AspectTableEntry(12, 12, "Usurp noble house"),
    ]
)

ELF_FACE_TABLE = AspectTable(
    aspect_type=AspectType.FACE,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Androgynous"),
        AspectTableEntry(2, 2, "Eye colour shifts with season"),
        AspectTableEntry(3, 3, "Feline eyes"),
        AspectTableEntry(4, 4, "Frosted blue lips"),
        AspectTableEntry(5, 5, "Glow of candlelight on skin"),
        AspectTableEntry(6, 6, "Long, distinguished nose"),
        AspectTableEntry(7, 7, "Pale and mask-like"),
        AspectTableEntry(8, 8, "Spotted with soot"),
        AspectTableEntry(9, 9, "Star-shaped pupils"),
        AspectTableEntry(10, 10, "Violet eyes"),
        AspectTableEntry(11, 11, "Wide-eyed, childlike"),
        AspectTableEntry(12, 12, "Wide-set almond eyes"),
    ]
)

ELF_DRESS_TABLE = AspectTable(
    aspect_type=AspectType.DRESS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Chequered harlequin"),
        AspectTableEntry(2, 2, "Cloak of black feathers"),
        AspectTableEntry(3, 3, "Cloak of frost"),
        AspectTableEntry(4, 4, "Cobwebs and soot"),
        AspectTableEntry(5, 5, "Decaying regal finery"),
        AspectTableEntry(6, 6, "Elaborately embroidered"),
        AspectTableEntry(7, 7, "Extravagant, frilly lace"),
        AspectTableEntry(8, 8, "Lace and flowers"),
        AspectTableEntry(9, 9, "Mother of pearl gown"),
        AspectTableEntry(10, 10, "Sheer black"),
        AspectTableEntry(11, 11, "Silvery gossamer"),
        AspectTableEntry(12, 12, "Woven leaves"),
    ]
)

ELF_BELIEFS_TABLE = AspectTable(
    aspect_type=AspectType.BELIEFS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "All plants are sentient"),
        AspectTableEntry(2, 2, "Cats are disguised fairies"),
        AspectTableEntry(3, 3, "Daylight is to be shunned"),
        AspectTableEntry(4, 4, "Drink only fine wine"),
        AspectTableEntry(5, 5, "Magic is the true language"),
        AspectTableEntry(6, 6, "Mortal world is but a dream"),
        AspectTableEntry(7, 7, "Mortals evolved from fungi"),
        AspectTableEntry(8, 8, "Reality is a fabulous song"),
        AspectTableEntry(9, 9, "The world is dying"),
        AspectTableEntry(10, 10, "Time is seeping into Fairy"),
        AspectTableEntry(11, 11, "Understand speech of stars"),
        AspectTableEntry(12, 12, "Witches led by fairy queen"),
    ]
)

# Elves use "Body" instead of "Fur"
ELF_BODY_TABLE = AspectTable(
    aspect_type=AspectType.FUR_BODY,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Aroma of mead or honey"),
        AspectTableEntry(2, 2, "Aura of dancing glimmers"),
        AspectTableEntry(3, 3, "Bluish skin"),
        AspectTableEntry(4, 4, "Faintly insubstantial"),
        AspectTableEntry(5, 5, "Golden blood, silver tears"),
        AspectTableEntry(6, 6, "Lithe frame, sex unclear"),
        AspectTableEntry(7, 7, "Odour of fresh spring dew"),
        AspectTableEntry(8, 8, "Pale skin, black in mirrors"),
        AspectTableEntry(9, 9, "Skin appears moonlit"),
        AspectTableEntry(10, 10, "Skin of a newborn"),
        AspectTableEntry(11, 11, "Skin rimed with frost"),
        AspectTableEntry(12, 12, "Sparkling skin"),
    ]
)

ELF_SPEECH_TABLE = AspectTable(
    aspect_type=AspectType.SPEECH,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Condescending"),
        AspectTableEntry(2, 2, "Distant and slightly echoing"),
        AspectTableEntry(3, 3, "Flat and toneless"),
        AspectTableEntry(4, 4, "Flirtatious"),
        AspectTableEntry(5, 5, "Like the cracking of ice"),
        AspectTableEntry(6, 6, "Lilting"),
        AspectTableEntry(7, 7, "Mirthful"),
        AspectTableEntry(8, 8, "Pitch changes: deep/high"),
        AspectTableEntry(9, 9, "Poetic and obscure"),
        AspectTableEntry(10, 10, "Song and rhyme"),
        AspectTableEntry(11, 11, "Subtly threatening"),
        AspectTableEntry(12, 12, "Whispering"),
    ]
)

# Trinket table - references item IDs in adventuring_gear_elf_trinkets.json
ELF_TRINKET_TABLE = AspectTable(
    aspect_type=AspectType.TRINKET,
    die_size=100,
    entries=[
        AspectTableEntry(1, 2, "A bag of caterpillars whose flesh have hallucinogenic properties", item_id="bag_of_caterpillars"),
        AspectTableEntry(3, 4, "A bag of sticky sweets that never get any smaller when sucked on", item_id="bag_of_sticky_sweets"),
        AspectTableEntry(5, 6, "A ball of silvery twine that is invisible in moonlight", item_id="ball_of_silvery_twine"),
        AspectTableEntry(7, 8, "A ball of yarn, gifted to you by a grateful grimalkin", item_id="ball_of_yarn"),
        AspectTableEntry(9, 10, "A black rose that never wilts", item_id="black_rose"),
        AspectTableEntry(11, 12, "A block of chocolate made with cocoa harvested from a mossling", item_id="block_of_chocolate"),
        AspectTableEntry(13, 14, "A book of amateur poetry, suspected to be by a powerful Fairy noble", item_id="book_of_amateur_poetry"),
        AspectTableEntry(15, 16, "A crown woven from holly and poison ivy", item_id="crown_of_holly_and_poison_ivy"),
        AspectTableEntry(17, 18, "A daisy that glows in moonlight", item_id="glowing_daisy"),
        AspectTableEntry(19, 20, "A fancy hat topped with elk antlers", item_id="fancy_hat_with_elk_antlers"),
        AspectTableEntry(21, 22, "A fragment of glowing crystal that you found in a dream", item_id="fragment_of_glowing_crystal"),
        AspectTableEntry(23, 24, "A fragment of horn from an evil unicorn", item_id="fragment_of_evil_unicorn_horn"),
        AspectTableEntry(25, 26, "A glass bottle that annihilates any liquid poured into it", item_id="annihilating_glass_bottle"),
        AspectTableEntry(27, 28, "A glass jar containing the tiny, frozen form of your only sister", item_id="glass_jar_with_frozen_sister"),
        AspectTableEntry(29, 30, "A glass slipper, stained with blood", item_id="bloodstained_glass_slipper"),
        AspectTableEntry(31, 32, "A harp that plays mood-inappropriate music when left unattended", item_id="mood_inappropriate_harp"),
        AspectTableEntry(33, 34, "A Chapes (holy symbol of the Pluritine Church), given by a dying friar decades ago", item_id="chapes_holy_symbol"),
        AspectTableEntry(35, 36, "A key fashioned from ice that melts in warmth and reforms in cold", item_id="ice_key"),
        AspectTableEntry(37, 38, "A lantern that burns with a cold, blue flame when lit", item_id="cold_flame_lantern"),
        AspectTableEntry(39, 40, "A letter promising your imminent demise, written in High Elfish, delivered over a hundred years ago", item_id="death_threat_letter"),
        AspectTableEntry(41, 42, "A mortal's heart, freely given", item_id="mortals_heart"),
        AspectTableEntry(43, 44, "A mote of sunlight, trapped in a scintillating crystal", item_id="trapped_sunlight_crystal"),
        AspectTableEntry(45, 46, "A necklace composed of honeybees", item_id="honeybee_necklace"),
        AspectTableEntry(47, 48, "A nightmare, sealed inside a bottle", item_id="bottled_nightmare"),
        AspectTableEntry(49, 50, "A pan flute stolen from a woodgrue, a single pipe is missing", item_id="stolen_pan_flute"),
        AspectTableEntry(51, 52, "A peacock feather whose eye intermittently blinks", item_id="blinking_peacock_feather"),
        AspectTableEntry(53, 54, "A pleasant dream, distilled into a liquor", item_id="distilled_dream_liquor"),
        AspectTableEntry(55, 56, "A receipt for a loan of four rare tomes from a Fairy library, books no longer in possession", item_id="fairy_library_receipt"),
        AspectTableEntry(57, 58, "A scabbard taken from the fallen body of a great knight", item_id="knights_scabbard"),
        AspectTableEntry(59, 60, "A sealed scroll allegedly containing one of the Goblin King's myriad names", item_id="sealed_goblin_king_scroll"),
        AspectTableEntry(61, 62, "A seemingly ordinary acorn that screams when its cap is removed", item_id="screaming_acorn"),
        AspectTableEntry(63, 64, "A set of horseshoes, designed for a centaur", item_id="centaur_horseshoes"),
        AspectTableEntry(65, 66, "A silver spoon that drips honey on command", item_id="honey_dripping_spoon"),
        AspectTableEntry(67, 68, "A single crow feather, taken from the cloak of the Queen of Blackbirds", item_id="queen_of_blackbirds_feather"),
        AspectTableEntry(69, 70, "A skeletal finger that writes macabre prophecies at dusk when given means to make marks", item_id="prophetic_skeletal_finger"),
        AspectTableEntry(71, 72, "A small bell shaped like a breggle's eye with faint bleating when rung", item_id="breggle_eye_bell"),
        AspectTableEntry(73, 74, "A spider that slowly weaves webs in the shape of clothing", item_id="clothing_weaving_spider"),
        AspectTableEntry(75, 76, "A spyglass that always shows a view of a sea at night", item_id="night_sea_spyglass"),
        AspectTableEntry(77, 78, "A thimble that is always magically full of sweet liqueur", item_id="liqueur_filled_thimble"),
        AspectTableEntry(79, 80, "A white-and-gold parasol that creates darkness directly underneath it", item_id="darkness_creating_parasol"),
        AspectTableEntry(81, 82, "A wolf pelt cloak with the wolf's head still attached, occasionally salivating", item_id="salivating_wolf_pelt_cloak"),
        AspectTableEntry(83, 84, "An ancient bronze mask depicting a bearded face", item_id="ancient_bronze_mask"),
        AspectTableEntry(85, 86, "An empty wine bottle that draws liquid inside until full when held over liquid", item_id="liquid_drawing_wine_bottle"),
        AspectTableEntry(87, 88, "An hourglass which constantly flows in one direction and cannot be inverted", item_id="one_way_hourglass"),
        AspectTableEntry(89, 90, "An icicle that never melts", item_id="never_melting_icicle"),
        AspectTableEntry(91, 92, "Bronze chimes that tinkle in the presence of both ghosts and strong breezes", item_id="ghost_detecting_chimes"),
        AspectTableEntry(93, 94, "Sculpting tools, preternaturally cold to the touch", item_id="cold_sculpting_tools"),
        AspectTableEntry(95, 96, "Six vials of blood, each drawn from a different Kindred", item_id="six_vials_of_kindred_blood"),
        AspectTableEntry(97, 98, "Star charts that match no sky seen from Dolmenwood", item_id="unknown_star_charts"),
        AspectTableEntry(99, 100, "The severed tail of a fairy horse", item_id="fairy_horse_tail"),
    ]
)


# =============================================================================
# COMPLETE ELF DEFINITION
# =============================================================================

ELF_DEFINITION = KindredDefinition(
    kindred_id="elf",
    name="Elf",
    description=(
        "As humans dominate the mortal world with their cities and kingdoms, elves "
        "do so Fairy. Among all the myriad peoples of the undying world, elves are "
        "driven to forge vast kingdoms, to subjugate others under their rule, and to "
        "delve deeply into the secrets of magic. Among their number are mighty lords "
        "and fearsome enchantresses, ageless sages and dashing knights, lowly rogues "
        "and hapless wanderers. Elves are physically similar to humans but vary widely "
        "in appearance, with features such as pointed ears, small horns, or star-shaped "
        "pupils marking them as non-human. It is always possible to identify an elf for "
        "they carry an air of unearthliness about them (unless disguised by magic)."
    ),
    kindred_type=KindredType.FAIRY,

    physical=PhysicalRanges(
        # Age at Level 1: 1d100 × 10 years (handled specially in generator)
        # We use base=0, dice=100d10 as approximation, but generator handles this
        age_base=0,
        age_dice=DiceFormula(1, 100, 0),  # Will multiply by 10 in generator
        # Lifespan: Immortal (use very large number)
        lifespan_base=999999,
        lifespan_dice=DiceFormula(0, 0, 0),
        # Height: 5' + 2d6" = 60 + 2d6 inches
        height_base=60,
        height_dice=DiceFormula(2, 6),
        # Weight: 100 + 3d10 lbs
        weight_base=100,
        weight_dice=DiceFormula(3, 10),
        size="Medium",
    ),

    native_languages=["Woldish", "Sylvan", "High Elfish"],

    abilities=[
        ELF_SKILLS_ABILITY,
        ELF_GLAMOURS_ABILITY,
        ELF_IMMORTALITY_ABILITY,
        ELF_MAGIC_RESISTANCE_ABILITY,
        ELF_UNEARTHLY_BEAUTY_ABILITY,
        ELF_COLD_IRON_VULNERABILITY_ABILITY,
    ],

    level_progression=[],  # Elves don't have level-based progression like breggles

    preferred_classes=["Enchanter", "Fighter", "Hunter", "Magician"],
    restricted_classes=["Cleric", "Friar"],  # Cannot be clerics/friars

    name_table=ELF_NAME_TABLE,

    aspect_tables={
        AspectType.BACKGROUND: ELF_BACKGROUND_TABLE,
        AspectType.HEAD: ELF_HEAD_TABLE,
        AspectType.DEMEANOUR: ELF_DEMEANOUR_TABLE,
        AspectType.DESIRES: ELF_DESIRES_TABLE,
        AspectType.FACE: ELF_FACE_TABLE,
        AspectType.DRESS: ELF_DRESS_TABLE,
        AspectType.BELIEFS: ELF_BELIEFS_TABLE,
        AspectType.FUR_BODY: ELF_BODY_TABLE,  # Elves use "Body" instead of "Fur"
        AspectType.SPEECH: ELF_SPEECH_TABLE,
        AspectType.TRINKET: ELF_TRINKET_TABLE,
    },

    trinket_item_ids=[
        "bag_of_caterpillars", "bag_of_sticky_sweets", "ball_of_silvery_twine",
        "ball_of_yarn", "black_rose", "block_of_chocolate",
        "book_of_amateur_poetry", "crown_of_holly_and_poison_ivy", "glowing_daisy",
        "fancy_hat_with_elk_antlers", "fragment_of_glowing_crystal", "fragment_of_evil_unicorn_horn",
        "annihilating_glass_bottle", "glass_jar_with_frozen_sister", "bloodstained_glass_slipper",
        "mood_inappropriate_harp", "chapes_holy_symbol", "ice_key",
        "cold_flame_lantern", "death_threat_letter", "mortals_heart",
        "trapped_sunlight_crystal", "honeybee_necklace", "bottled_nightmare",
        "stolen_pan_flute", "blinking_peacock_feather", "distilled_dream_liquor",
        "fairy_library_receipt", "knights_scabbard", "sealed_goblin_king_scroll",
        "screaming_acorn", "centaur_horseshoes", "honey_dripping_spoon",
        "queen_of_blackbirds_feather", "prophetic_skeletal_finger", "breggle_eye_bell",
        "clothing_weaving_spider", "night_sea_spyglass", "liqueur_filled_thimble",
        "darkness_creating_parasol", "salivating_wolf_pelt_cloak", "ancient_bronze_mask",
        "liquid_drawing_wine_bottle", "one_way_hourglass", "never_melting_icicle",
        "ghost_detecting_chimes", "cold_sculpting_tools", "six_vials_of_kindred_blood",
        "unknown_star_charts", "fairy_horse_tail",
    ],

    kindred_relations=(
        "The adventuresome elves who wander in the mortal world tend to be fascinated "
        "with mortal Kindreds, their short, spirited lifespans, and their inevitable "
        "ageing and death. Some elves view mortal company as peculiar and entertaining, "
        "while others earnestly seek to comprehend the mortal mindset. Elves tend to be "
        "on good terms with demi-fey and other fairies. In Dolmenwood's human settlements, "
        "elves may be met with awe and caution. Most everyday humans have never met a "
        "fairy of any kind, and their folklore is stuffed with tales of the wickedness "
        "and treachery of elves in ancient times, when the Cold Prince ruled all of Dolmenwood."
    ),

    religion_notes=(
        "Elves cannot be clerics or friars as they have no spiritual connection with "
        "the deities of mortals."
    ),

    source_book="Dolmenwood Player Book",
    source_page=36,
)
