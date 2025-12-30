"""
Woodgrue kindred definition for Dolmenwood.

Bat-faced demi-fey goblins, known for their love of music, revelry, and arson.
Source: Dolmenwood Player Book, pages 52-55
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
# WOODGRUE ABILITIES
# =============================================================================

WOODGRUE_COMPULSIVE_JUBILATION_ABILITY = KindredAbility(
    ability_id="woodgrue_compulsive_jubilation",
    name="Compulsive Jubilation",
    description=(
        "A woodgrue who witnesses a party, feast, celebration, or festival must "
        "partake; they are utterly compelled with every fibre of their being. "
        "If, for some reason, a woodgrue wishes to resist this compulsion, they "
        "may Save Versus Spell (but feel drained and downtrodden for the length "
        "of the engagement)."
    ),
    is_passive=True,
    save_type="spell",
    extra_data={
        "compulsion_triggers": ["party", "feast", "celebration", "festival"],
        "resist_effect": "drained and downtrodden",
    },
)

WOODGRUE_DEFENSIVE_BONUS_ABILITY = KindredAbility(
    ability_id="woodgrue_defensive_bonus",
    name="Defensive Bonus",
    description=(
        "In melee with Large creatures, woodgrues gain a +2 Armour Class bonus, "
        "due to their small size."
    ),
    is_passive=True,
    ac_bonus=2,
    ac_conditions=["vs Large creatures"],
)

WOODGRUE_MAD_REVELRY_ABILITY = KindredAbility(
    ability_id="woodgrue_mad_revelry",
    name="Mad Revelry",
    description=(
        "Once per day, a woodgrue may play one of the enchanted melodies on a "
        "wind instrument while hooting and dancing terribly. All living creatures "
        "within 30' (including allies) must Save Versus Spell or be afflicted. "
        "Fairies and demi-fey gain +2 to the Saving Throw. Effects last as long "
        "as the woodgrue keeps playing. The woodgrue may move but cannot attack "
        "or perform other actions while playing."
    ),
    is_passive=False,
    uses_per_day_by_level={1: 1},
    save_type="spell",
    extra_data={
        "range_feet": 30,
        "affects_allies": True,
        "fairy_save_bonus": 2,
        "requires_wind_instrument": True,
        "melodies": {
            "confide": {
                "description": "Subjects speak in a slurred voice, confessing some deeply hidden emotion or revealing an ally's secret.",
            },
            "dance": {
                "description": "Subjects begin dancing a profane, nonsensical jig. Those affected gain a +1 bonus to Armour Class, but cannot move from the spot where they dance.",
                "ac_bonus": 1,
                "immobilized": True,
            },
            "imbibe": {
                "description": "Subjects ravenously consume any liquids, herbs, mushrooms, and such like that are available and proceed to act as though drunk.",
                "attack_penalty": -2,
            },
            "jape": {
                "description": "Subjects mock the immediately preceding occurrence, be it a deed of words or acts.",
            },
            "jubilate": {
                "description": "Subjects burst into irrepressible laughter, preventing them from speech. There is a 1-in-6 chance each Round of falling over in a laughing fit.",
                "prevents_speech": True,
                "fall_chance": "1-in-6",
            },
            "mount": {
                "description": "Subjects attempt to mount nearby creatures, be they friend or foe, and ride them piggyback. Save Versus Hold to resist being mounted. Unaffected creatures may Save Versus Hold once per Round to buck off a rider.",
                "secondary_save": "hold",
            },
            "revel": {
                "description": "Subjects cannot speak; instead they bark out terrible scats of sound, in an attempt to keep up with the woodgrue's maddening melodies. Speed is halved if subjects are not headed in the direction of the woodgrue.",
                "prevents_speech": True,
                "speed_halved_condition": "not heading toward woodgrue",
            },
        },
    },
)

WOODGRUE_MOON_SIGHT_ABILITY = KindredAbility(
    ability_id="woodgrue_moon_sight",
    name="Moon Sight",
    description=(
        "A woodgrue can see in darkness up to 60', viewing the world as though "
        "it glows in faint moonlight. This does not incur low light penalties, "
        "but fine detail (e.g. writing) cannot be perceived."
    ),
    is_passive=True,
    extra_data={
        "darkvision_range_feet": 60,
        "no_low_light_penalty": True,
        "cannot_read_in_darkness": True,
        # Note: This is the same as the "Moon Sight" glamour, but woodgrues
        # receive it as a racial ability rather than through the Glamours system.
        "equivalent_glamour_id": "moon_sight",
    },
)

WOODGRUE_MUSICAL_INSTRUMENTS_ABILITY = KindredAbility(
    ability_id="woodgrue_musical_instruments",
    name="Musical Instruments",
    description=("A woodgrue can employ a musical instrument as a melee weapon, doing 1d4 damage."),
    is_passive=True,
    is_attack=True,
    damage_by_level={1: "1d4"},
    extra_data={
        "weapon_type": "musical_instrument",
    },
)

WOODGRUE_COLD_IRON_VULNERABILITY_ABILITY = KindredAbility(
    ability_id="woodgrue_cold_iron_vulnerability",
    name="Vulnerable to Cold Iron",
    description=(
        "As demi-fey, cold iron weapons inflict +1 damage on woodgrues. "
        "(e.g. a cold iron shortsword would inflict 1d6+1 damage on a woodgrue, "
        "rather than the standard 1d6)."
    ),
    is_passive=True,
    extra_data={
        "cold_iron_extra_damage": 1,
        "vulnerability_type": "cold_iron",
    },
)

WOODGRUE_SKILLS_ABILITY = KindredAbility(
    ability_id="woodgrue_skills",
    name="Woodgrue Skills",
    description=("Woodgrues have a Skill Target of 5 for Listen."),
    is_passive=True,
    extra_data={
        "skill_bonuses": {
            "listen": {"target": 5},
        },
    },
)


# =============================================================================
# WOODGRUE NAME TABLE
# =============================================================================

WOODGRUE_NAME_TABLE = NameTable(
    columns={
        NameColumn.MALE: [
            "Bagnack",
            "Barmcudgel",
            "Bloomfext",
            "Bunglebone",
            "Capratt",
            "Chimm",
            "Delgodand",
            "Drunker",
            "Eortban",
            "Grunkle",
            "Gubber",
            "Gumroot",
            "Gunkuss",
            "Kungus",
            "Longtittle",
            "Lubbal",
            "Olpipes",
            "Runkelgate",
            "Weepooze",
            "Wumpus",
        ],
        NameColumn.FEMALE: [
            "Bishga",
            "Canaghoop",
            "Cheruffue",
            "Doola",
            "Frogfyrr",
            "Gruecalle",
            "Hoolbootes",
            "Maulspoorer",
            "Mogsmote",
            "Molemoch",
            "Moonmilk",
            "Munmun",
            "Nettaclare",
            "Oorcha",
            "Palliepalm",
            "Pimplepook",
            "Puggump",
            "Rolliepolk",
            "Sasserpipe",
            "Whipsee",
        ],
        NameColumn.UNISEX: [
            "Bogfrink",
            "Bongwretch",
            "Chunder",
            "Danklob",
            "Frondbong",
            "Gobblebag",
            "Hootbra",
            "Longsnipe",
            "Lumpfrisk",
            "Mabmungle",
            "Mungus",
            "Obblehob",
            "Oddler",
            "Oodler",
            "Pipplepoke",
            "Slovend",
            "Umple",
            "Unclord",
            "Undermap",
            "Whoopla",
        ],
        NameColumn.SURNAME: [
            "Bobbleslime",
            "Bogbabble",
            "Bootswap",
            "Chumley",
            "Cobwallop",
            "Drooglight",
            "Dungobble",
            "Eggmumble",
            "Hogslapper",
            "Hortleswoop",
            "Hungerslip",
            "Lankwobble",
            "Moorsnob",
            "Mundersnog",
            "Pencecrump",
            "Persnickle",
            "Shunderbog",
            "Snodgrass",
            "Wallerbog",
            "Woodfuffle",
        ],
    }
)


# =============================================================================
# WOODGRUE ASPECT TABLES
# =============================================================================

WOODGRUE_BACKGROUND_TABLE = AspectTable(
    aspect_type=AspectType.BACKGROUND,
    die_size=20,
    entries=[
        AspectTableEntry(1, 1, "Circus performer"),
        AspectTableEntry(2, 2, "Convicted arsonist"),
        AspectTableEntry(3, 3, "Court jester"),
        AspectTableEntry(4, 4, "Crow hunter"),
        AspectTableEntry(5, 5, "Dung collector"),
        AspectTableEntry(6, 6, "Egg thief"),
        AspectTableEntry(7, 7, "Errant piper"),
        AspectTableEntry(8, 8, "Firework maker"),
        AspectTableEntry(9, 9, "Fungus trader"),
        AspectTableEntry(10, 10, "Juggler"),
        AspectTableEntry(11, 11, "Maggot farmer"),
        AspectTableEntry(12, 12, "Mead brewer"),
        AspectTableEntry(13, 13, "Moth trapper"),
        AspectTableEntry(14, 14, "Mushroom forager"),
        AspectTableEntry(15, 15, "Pedlar"),
        AspectTableEntry(16, 16, "Pipe carver"),
        AspectTableEntry(17, 17, "Ragpicker"),
        AspectTableEntry(18, 18, "Tent maker"),
        AspectTableEntry(19, 19, "Tomb robber"),
        AspectTableEntry(20, 20, "Wizard's servant"),
    ],
)

WOODGRUE_HEAD_TABLE = AspectTable(
    aspect_type=AspectType.HEAD,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Bald, veiny ears"),
        AspectTableEntry(2, 2, "Blotchy bald pate"),
        AspectTableEntry(3, 3, "Cap of shiny beetle shells"),
        AspectTableEntry(4, 4, "Ears ooze orange wax"),
        AspectTableEntry(5, 5, "Elongated, teetering neck"),
        AspectTableEntry(6, 6, "Felt hat with long liripipe"),
        AspectTableEntry(7, 7, "Floppy hat, way too big"),
        AspectTableEntry(8, 8, "Long, bristling hair tufts"),
        AspectTableEntry(9, 9, "Pink mohawk (natural)"),
        AspectTableEntry(10, 10, "Round, droopy ears"),
        AspectTableEntry(11, 11, "Stripe of silver hair"),
        AspectTableEntry(12, 12, "Twitching, pointy ears"),
    ],
)

WOODGRUE_DEMEANOUR_TABLE = AspectTable(
    aspect_type=AspectType.DEMEANOUR,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Bends the truth"),
        AspectTableEntry(2, 2, "Capers and japes"),
        AspectTableEntry(3, 3, "Childlike and curious"),
        AspectTableEntry(4, 4, "Cunning, scheming"),
        AspectTableEntry(5, 5, "Dour, gallows humour"),
        AspectTableEntry(6, 6, "Feigned mysticism"),
        AspectTableEntry(7, 7, "Frivolous and petty"),
        AspectTableEntry(8, 8, "Penchant for pilfery"),
        AspectTableEntry(9, 9, "Practical joker"),
        AspectTableEntry(10, 10, "Shady and unscrupulous"),
        AspectTableEntry(11, 11, "Trickster (but loyal friend)"),
        AspectTableEntry(12, 12, "Wide-eyed innocence"),
    ],
)

WOODGRUE_DESIRES_TABLE = AspectTable(
    aspect_type=AspectType.DESIRES,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Be accepted as a saint (as a joke)"),
        AspectTableEntry(2, 2, "Build manor half in Fairy"),
        AspectTableEntry(3, 3, "Burn down a castle"),
        AspectTableEntry(4, 4, "Found a secret society"),
        AspectTableEntry(5, 5, "Giant bee mead brewery"),
        AspectTableEntry(6, 6, "Live in a castle of bats"),
        AspectTableEntry(7, 7, "Marry a goblin merchant"),
        AspectTableEntry(8, 8, "Organise largest moot ever"),
        AspectTableEntry(9, 9, "Perform for the Nag-Lord"),
        AspectTableEntry(10, 10, "Popularise moth sausages"),
        AspectTableEntry(11, 11, "Rule a human town in secret"),
        AspectTableEntry(12, 12, "Steal secrets of the Drune"),
    ],
)

WOODGRUE_FACE_TABLE = AspectTable(
    aspect_type=AspectType.FACE,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Droopy nose"),
        AspectTableEntry(2, 2, "Lavishly preened moustache"),
        AspectTableEntry(3, 3, "Lustrous black beard"),
        AspectTableEntry(4, 4, "Nose flesh changes colour"),
        AspectTableEntry(5, 5, "Nostrils flap when excited"),
        AspectTableEntry(6, 6, "Nostrils dripping yellow snot"),
        AspectTableEntry(7, 7, "Oiled moustache"),
        AspectTableEntry(8, 8, "One large eye, one small"),
        AspectTableEntry(9, 9, "Protruding fangs"),
        AspectTableEntry(10, 10, "Sagging, bloated throat"),
        AspectTableEntry(11, 11, "Shifty eyes constantly blink"),
        AspectTableEntry(12, 12, "Straggly beard"),
    ],
)

WOODGRUE_DRESS_TABLE = AspectTable(
    aspect_type=AspectType.DRESS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Dangling bells and baubles"),
        AspectTableEntry(2, 2, "Enigmatic black cloak"),
        AspectTableEntry(3, 3, "Heavily patched"),
        AspectTableEntry(4, 4, "Hessian loin cloth"),
        AspectTableEntry(5, 5, "Knotted cords"),
        AspectTableEntry(6, 6, "Long, ragged cape"),
        AspectTableEntry(7, 7, "Mismatched, stolen clothes"),
        AspectTableEntry(8, 8, "Paint-daubed rags"),
        AspectTableEntry(9, 9, "Pied jester's outfit"),
        AspectTableEntry(10, 10, "Soft brushed suede"),
        AspectTableEntry(11, 11, "Stockings and baggy jumper"),
        AspectTableEntry(12, 12, "Stripy hose and bodice"),
    ],
)

WOODGRUE_BELIEFS_TABLE = AspectTable(
    aspect_type=AspectType.BELIEFS,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Crows are spies from Fairy"),
        AspectTableEntry(2, 2, "Fairies are illusory"),
        AspectTableEntry(3, 3, "Fungi are souls of the dead"),
        AspectTableEntry(4, 4, "Get all agreements in writing"),
        AspectTableEntry(5, 5, "Gold buried in graveyards"),
        AspectTableEntry(6, 6, "Humans can't dance"),
        AspectTableEntry(7, 7, "Immune to fire"),
        AspectTableEntry(8, 8, "Live on cake alone"),
        AspectTableEntry(9, 9, "Nearly perfected deadly song"),
        AspectTableEntry(10, 10, "Never reveal your name"),
        AspectTableEntry(11, 11, "Penal system must be a joke"),
        AspectTableEntry(12, 12, "The Nag-Lord really is a wag"),
    ],
)

WOODGRUE_BODY_TABLE = AspectTable(
    aspect_type=AspectType.FUR_BODY,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Flaps of skin between fingers"),
        AspectTableEntry(2, 2, "Hunchback"),
        AspectTableEntry(3, 3, "Knock-kneed"),
        AspectTableEntry(4, 4, "Pink skin with white fuzz"),
        AspectTableEntry(5, 5, "Prehensile feet"),
        AspectTableEntry(6, 6, "Rotund"),
        AspectTableEntry(7, 7, "Scrawny"),
        AspectTableEntry(8, 8, "Skin flaps under arms"),
        AspectTableEntry(9, 9, "Spindly, 4-knuckled fingers"),
        AspectTableEntry(10, 10, "Thick, matted, auburn fur"),
        AspectTableEntry(11, 11, "Utterly hairless"),
        AspectTableEntry(12, 12, "Vestigial wings (flightless)"),
    ],
)

WOODGRUE_SPEECH_TABLE = AspectTable(
    aspect_type=AspectType.SPEECH,
    die_size=12,
    entries=[
        AspectTableEntry(1, 1, "Childish giggling"),
        AspectTableEntry(2, 2, "Excited screeching"),
        AspectTableEntry(3, 3, "Guffawing"),
        AspectTableEntry(4, 4, "Hesitant warbling"),
        AspectTableEntry(5, 5, "Hissing and slurping"),
        AspectTableEntry(6, 6, "Intermittent gibbering"),
        AspectTableEntry(7, 7, "Languid rumbling"),
        AspectTableEntry(8, 8, "Melodious"),
        AspectTableEntry(9, 9, "Punctuated with hoots"),
        AspectTableEntry(10, 10, "Shrill"),
        AspectTableEntry(11, 11, "Sinister whispering"),
        AspectTableEntry(12, 12, "Staccato"),
    ],
)

# Trinket table - references item IDs in adventuring_gear_woodgrue_trinkets.json
WOODGRUE_TRINKET_TABLE = AspectTable(
    aspect_type=AspectType.TRINKET,
    die_size=100,
    entries=[
        AspectTableEntry(1, 2, "A bag of delicious boiled sweets", item_id="bag_of_boiled_sweets"),
        AspectTableEntry(
            3, 4, "A basket of snakes, intended for juggling", item_id="basket_of_snakes"
        ),
        AspectTableEntry(
            5,
            6,
            "A battered hat with a stuffed swan's head stitched proudly at the summit",
            item_id="battered_hat_with_swan_head",
        ),
        AspectTableEntry(
            7,
            8,
            "A bone whistle. When blown at night, it sends nearby bats and night birds into a frenzy",
            item_id="bone_whistle",
        ),
        AspectTableEntry(
            9,
            10,
            "A bottle containing dirty water from the Baths of Astralon",
            item_id="bottle_of_dirty_water",
        ),
        AspectTableEntry(
            11,
            12,
            "A bottle of ink that always seems to spill everywhere when opened",
            item_id="spilling_ink_bottle",
        ),
        AspectTableEntry(
            13,
            14,
            "A bronze statuette of a chimera made up of a dozen different animals. The person who gave it to you insists it depicts a real creature",
            item_id="bronze_chimera_statuette",
        ),
        AspectTableEntry(
            15,
            16,
            "A burial shroud seemingly imprinted with a face. The face becomes more distinguishable every day",
            item_id="burial_shroud_with_face",
        ),
        AspectTableEntry(
            17,
            18,
            "A ceramic plate that emits a simple tune when scratched",
            item_id="musical_ceramic_plate",
        ),
        AspectTableEntry(
            19,
            20,
            "A collection of fungi, loaned to you by a mossling",
            item_id="collection_of_fungi",
        ),
        AspectTableEntry(
            21,
            22,
            "A dead crow in a bag. Before you killed it, you were pretty sure it was spying on you",
            item_id="dead_crow_in_bag",
        ),
        AspectTableEntry(
            23,
            24,
            "A fake moustache. When worn, you appear to have a full beard",
            item_id="fake_moustache",
        ),
        AspectTableEntry(
            25,
            26,
            "A forbidden treatise claiming grimalkins and woodgrues share the same ancestors",
            item_id="forbidden_treatise",
        ),
        AspectTableEntry(
            27, 28, "A glass case with a giant moth pinned inside", item_id="glass_case_with_moth"
        ),
        AspectTableEntry(
            29,
            30,
            "A harp shaped like a duck. Playing it attracts the attention of nearby waterfowl",
            item_id="duck_shaped_harp",
        ),
        AspectTableEntry(
            31, 32, "A harp string, sharp and tinged with blood", item_id="bloody_harp_string"
        ),
        AspectTableEntry(
            33,
            34,
            "A hooded cloak made from thousands of moth wings stitched together",
            item_id="moth_wing_cloak",
        ),
        AspectTableEntry(
            35, 36, "A mead tankard that is perpetually sticky", item_id="sticky_mead_tankard"
        ),
        AspectTableEntry(
            37,
            38,
            "A misshapen ocarina. Each note sounds eerily similar to a baby's cries",
            item_id="misshapen_ocarina",
        ),
        AspectTableEntry(
            39,
            40,
            "A mossling pipe you found in a pile of compost. Its smoke makes people nostalgic",
            item_id="nostalgic_mossling_pipe",
        ),
        AspectTableEntry(
            41,
            42,
            "A note promising that a 'Mr Fox' will come to your aid in your hour of greatest need",
            item_id="mr_fox_note",
        ),
        AspectTableEntry(
            43,
            44,
            "A pair of matching eyeballs. Whenever possible, they rotate to stare at you",
            item_id="staring_eyeballs",
        ),
        AspectTableEntry(45, 46, "A pair of small, bronze cymbals", item_id="bronze_cymbals"),
        AspectTableEntry(
            47,
            48,
            "A personalised invitation to 'THE FEAST.' No further details are provided",
            item_id="feast_invitation",
        ),
        AspectTableEntry(
            49,
            50,
            "A pocketbook of bad jokes. Emits the occasional snicker",
            item_id="snickering_joke_book",
        ),
        AspectTableEntry(
            51,
            52,
            "A poster for your parent's last, ill-fated circus performance",
            item_id="circus_performance_poster",
        ),
        AspectTableEntry(
            53, 54, "A quill made from a stirge-owl feather", item_id="stirge_owl_quill"
        ),
        AspectTableEntry(
            55, 56, "A rope woven from a mix of human and breggle hair", item_id="hair_rope"
        ),
        AspectTableEntry(
            57,
            58,
            "A stack of angry letters, all accusing you of arson",
            item_id="arson_accusation_letters",
        ),
        AspectTableEntry(
            59,
            60,
            "A strange disk that produces the sound of flatulence whenever a weight is placed atop it",
            item_id="flatulence_disk",
        ),
        AspectTableEntry(
            61,
            62,
            "A tent that slowly raises itself when you loudly sing it a jaunty song",
            item_id="self_raising_tent",
        ),
        AspectTableEntry(
            63,
            64,
            "A vial of guano. Your last reminder of a deceased loved one",
            item_id="vial_of_guano",
        ),
        AspectTableEntry(
            65,
            66,
            "A wooden sceptre topped with a jester's head. When struck, the head tells an ill-considered joke",
            item_id="jester_sceptre",
        ),
        AspectTableEntry(
            67,
            68,
            "An advice book that ultimately suggests a liberal application of fire as the solution to every problem",
            item_id="fire_solution_book",
        ),
        AspectTableEntry(
            69,
            70,
            "An ancient coin, stolen from a grave. Far colder to the touch than it should be",
            item_id="cold_ancient_coin",
        ),
        AspectTableEntry(
            71, 72, "An empty pan flute case, its contents stolen", item_id="empty_pan_flute_case"
        ),
        AspectTableEntry(
            73,
            74,
            "An enormous firework with a tag that reads 'Untested'",
            item_id="untested_firework",
        ),
        AspectTableEntry(
            75,
            76,
            "An extravagant wig, stolen from the head of an elf noble",
            item_id="stolen_elf_wig",
        ),
        AspectTableEntry(
            77,
            78,
            "An ordinary-looking metal bucket. When filled with water, leeches appear inside",
            item_id="leech_bucket",
        ),
        AspectTableEntry(
            79,
            80,
            "An ornate flute, said to be handed down by your ancestors since before they left Fairy",
            item_id="ancestral_flute",
        ),
        AspectTableEntry(
            81, 82, "An unhatched egg that sweats blood", item_id="blood_sweating_egg"
        ),
        AspectTableEntry(
            83,
            84,
            "Faded parchment that lists the names of everyone you've ever wronged. It updates itself periodically",
            item_id="updating_wronged_list",
        ),
        AspectTableEntry(
            85,
            86,
            "Light from a fireworks display, caught in a shard of glass",
            item_id="captured_fireworks_light",
        ),
        AspectTableEntry(
            87,
            88,
            "Lyrics to a half-written song about rodents visiting from the moon",
            item_id="moon_rodent_lyrics",
        ),
        AspectTableEntry(
            89,
            90,
            "Small vials of syrups, each labelled with the type of mood they're supposed to cure",
            item_id="mood_cure_syrups",
        ),
        AspectTableEntry(
            91, 92, "The corpse of a mouse, dressed in tiny clothes", item_id="dressed_mouse_corpse"
        ),
        AspectTableEntry(
            93,
            94,
            "The crest of an unknown longhorn noble house, found on a dead breggle",
            item_id="unknown_longhorn_crest",
        ),
        AspectTableEntry(
            95, 96, "The squirming pieces for maggot chess", item_id="maggot_chess_pieces"
        ),
        AspectTableEntry(
            97,
            98,
            "Woollen ear warmers, knitted by your grandmother",
            item_id="woollen_ear_warmers",
        ),
        AspectTableEntry(
            99, 100, "Your uncle's famed recipe for moth cakes", item_id="moth_cake_recipe"
        ),
    ],
)


# =============================================================================
# COMPLETE WOODGRUE DEFINITION
# =============================================================================

WOODGRUE_DEFINITION = KindredDefinition(
    kindred_id="woodgrue",
    name="Woodgrue",
    description=(
        "Bat-faced demi-fey goblins, known for their love of music, revelry, and arson. "
        "Woodgrues are capricious goblins who, many generations ago, forsook their ancestral "
        "home in Fairy and migrated to the musty dells of the mortal world. They have massive, "
        "flapping ears and soft, downy fur upon their heads and chests, while the rest of their "
        "body appears like that of a human child. Woodgrues live a nomadic lifestyle, wandering "
        "Dolmenwood alone or in small groups, following where their whims and noses lead."
    ),
    kindred_type=KindredType.DEMI_FEY,
    physical=PhysicalRanges(
        # Age at Level 1: 50 + 3d6 years
        age_base=50,
        age_dice=DiceFormula(3, 6),
        # Lifespan: 300 + 2d100 years
        lifespan_base=300,
        lifespan_dice=DiceFormula(2, 100),
        # Height: 3' + 2d6" (Small)
        height_base=36,  # 3' = 36 inches
        height_dice=DiceFormula(2, 6),
        # Weight: 60 + 2d10 lbs
        weight_base=60,
        weight_dice=DiceFormula(2, 10),
        size="Small",
    ),
    native_languages=["Woldish", "Sylvan"],
    abilities=[
        WOODGRUE_COMPULSIVE_JUBILATION_ABILITY,
        WOODGRUE_DEFENSIVE_BONUS_ABILITY,
        WOODGRUE_MAD_REVELRY_ABILITY,
        WOODGRUE_MOON_SIGHT_ABILITY,
        WOODGRUE_MUSICAL_INSTRUMENTS_ABILITY,
        WOODGRUE_COLD_IRON_VULNERABILITY_ABILITY,
        WOODGRUE_SKILLS_ABILITY,
    ],
    level_progression=[],
    preferred_classes=["Bard", "Magician", "Thief"],
    restricted_classes=["Knight", "Cleric", "Friar"],
    name_table=WOODGRUE_NAME_TABLE,
    aspect_tables={
        AspectType.BACKGROUND: WOODGRUE_BACKGROUND_TABLE,
        AspectType.HEAD: WOODGRUE_HEAD_TABLE,
        AspectType.DEMEANOUR: WOODGRUE_DEMEANOUR_TABLE,
        AspectType.DESIRES: WOODGRUE_DESIRES_TABLE,
        AspectType.FACE: WOODGRUE_FACE_TABLE,
        AspectType.DRESS: WOODGRUE_DRESS_TABLE,
        AspectType.BELIEFS: WOODGRUE_BELIEFS_TABLE,
        AspectType.FUR_BODY: WOODGRUE_BODY_TABLE,
        AspectType.SPEECH: WOODGRUE_SPEECH_TABLE,
        AspectType.TRINKET: WOODGRUE_TRINKET_TABLE,
    },
    trinket_item_ids=[
        "bag_of_boiled_sweets",
        "basket_of_snakes",
        "battered_hat_with_swan_head",
        "bone_whistle",
        "bottle_of_dirty_water",
        "spilling_ink_bottle",
        "bronze_chimera_statuette",
        "burial_shroud_with_face",
        "musical_ceramic_plate",
        "collection_of_fungi",
        "dead_crow_in_bag",
        "fake_moustache",
        "forbidden_treatise",
        "glass_case_with_moth",
        "duck_shaped_harp",
        "bloody_harp_string",
        "moth_wing_cloak",
        "sticky_mead_tankard",
        "misshapen_ocarina",
        "nostalgic_mossling_pipe",
        "mr_fox_note",
        "staring_eyeballs",
        "bronze_cymbals",
        "feast_invitation",
        "snickering_joke_book",
        "circus_performance_poster",
        "stirge_owl_quill",
        "hair_rope",
        "arson_accusation_letters",
        "flatulence_disk",
        "self_raising_tent",
        "vial_of_guano",
        "jester_sceptre",
        "fire_solution_book",
        "cold_ancient_coin",
        "empty_pan_flute_case",
        "untested_firework",
        "stolen_elf_wig",
        "leech_bucket",
        "ancestral_flute",
        "blood_sweating_egg",
        "updating_wronged_list",
        "captured_fireworks_light",
        "moon_rodent_lyrics",
        "mood_cure_syrups",
        "dressed_mouse_corpse",
        "unknown_longhorn_crest",
        "maggot_chess_pieces",
        "woollen_ear_warmers",
        "moth_cake_recipe",
    ],
    kindred_relations=(
        "Woodgrues enjoy the company of all Kindreds, mortal, fairy, or demi-fey, "
        "though they favour those who share their raucous sense of humour. In human "
        "settlements in Dolmenwood, woodgrues may be met with caution, as folk are "
        "aware of their rambunctious nature. However, it is known that barring "
        "woodgrues entry would likely only lead to greater misfortune."
    ),
    religion_notes=(
        "Woodgrues cannot be clerics or friars as they have no spiritual connection "
        "with the deities of mortals."
    ),
    source_book="Dolmenwood Player Book",
    source_page=52,
)
