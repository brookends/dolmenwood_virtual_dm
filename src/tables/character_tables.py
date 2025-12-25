"""
Character generation tables for Dolmenwood.

Provides kindred-specific name tables and aspect tables for character creation.
Each kindred (Breggle, Elf, Grimalkin, Human, Mossling, Woodgrue) has its own
set of tables with appropriate entries.
"""

from typing import Optional
from src.tables.table_types import (
    Kindred,
    NameColumn,
    CharacterAspectType,
    DieType,
    TableEntry,
    NameTableColumn,
    KindredNameTable,
    CharacterAspectTable,
    CharacterAspectResult,
    GeneratedCharacterAspects,
)


class CharacterTableManager:
    """
    Manages character generation tables for all kindreds.

    Provides access to name tables and aspect tables, and handles
    rolling complete character aspects.
    """

    def __init__(self):
        # Name tables indexed by kindred
        self._name_tables: dict[Kindred, KindredNameTable] = {}

        # Aspect tables indexed by (kindred, aspect_type)
        self._aspect_tables: dict[tuple[Kindred, CharacterAspectType], CharacterAspectTable] = {}

        # Register all tables
        self._register_all_tables()

    def _register_all_tables(self) -> None:
        """Register all character generation tables."""
        self._register_breggle_tables()
        self._register_elf_tables()
        self._register_grimalkin_tables()
        self._register_human_tables()
        self._register_mossling_tables()
        self._register_woodgrue_tables()

    # =========================================================================
    # NAME TABLE REGISTRATION
    # =========================================================================

    def register_name_table(self, table: KindredNameTable) -> None:
        """Register a name table for a kindred."""
        self._name_tables[table.kindred] = table

    def get_name_table(self, kindred: Kindred) -> Optional[KindredNameTable]:
        """Get the name table for a kindred."""
        return self._name_tables.get(kindred)

    # =========================================================================
    # ASPECT TABLE REGISTRATION
    # =========================================================================

    def register_aspect_table(self, table: CharacterAspectTable) -> None:
        """Register an aspect table."""
        key = (table.kindred, table.aspect_type)
        self._aspect_tables[key] = table

    def get_aspect_table(
        self,
        kindred: Kindred,
        aspect_type: CharacterAspectType
    ) -> Optional[CharacterAspectTable]:
        """Get an aspect table for a kindred."""
        return self._aspect_tables.get((kindred, aspect_type))

    def get_all_aspect_tables(self, kindred: Kindred) -> list[CharacterAspectTable]:
        """Get all aspect tables for a kindred."""
        return [
            table for (k, _), table in self._aspect_tables.items()
            if k == kindred
        ]

    # =========================================================================
    # CHARACTER GENERATION
    # =========================================================================

    def roll_name(
        self,
        kindred: Kindred,
        gender: Optional[str] = None,
        style: Optional[str] = None
    ) -> str:
        """
        Roll a name for a character of the given kindred.

        Args:
            kindred: The character's kindred
            gender: "male", "female", or None for unisex
            style: For elves: "rustic" or "courtly"

        Returns:
            Generated name
        """
        table = self._name_tables.get(kindred)
        if table:
            return table.roll_full_name(gender=gender, style=style)
        return ""

    def roll_aspect(
        self,
        kindred: Kindred,
        aspect_type: CharacterAspectType
    ) -> Optional[CharacterAspectResult]:
        """Roll on a specific aspect table."""
        table = self.get_aspect_table(kindred, aspect_type)
        if not table:
            return None

        roll, entry = table.roll()
        return CharacterAspectResult(
            kindred=kindred,
            aspect_type=aspect_type,
            roll=roll,
            result=entry.result,
            entry=entry
        )

    def generate_character(
        self,
        kindred: Kindred,
        gender: Optional[str] = None,
        style: Optional[str] = None,
        aspects_to_roll: Optional[list[CharacterAspectType]] = None
    ) -> GeneratedCharacterAspects:
        """
        Generate a complete set of character aspects.

        Args:
            kindred: The character's kindred
            gender: Gender for name generation
            style: Name style for elves
            aspects_to_roll: Specific aspects to roll, or None for all

        Returns:
            GeneratedCharacterAspects with all rolled results
        """
        character = GeneratedCharacterAspects(kindred=kindred, gender=gender)

        # Roll name
        character.name = self.roll_name(kindred, gender, style)

        # Determine which aspects to roll
        if aspects_to_roll is None:
            aspects_to_roll = [
                CharacterAspectType.BACKGROUND,
                CharacterAspectType.TRINKET,
                CharacterAspectType.HEAD,
                CharacterAspectType.DEMEANOUR,
                CharacterAspectType.DESIRES,
                CharacterAspectType.FACE,
                CharacterAspectType.DRESS,
                CharacterAspectType.BELIEFS,
                CharacterAspectType.FUR_BODY,
                CharacterAspectType.SPEECH,
            ]

        # Roll each aspect
        for aspect_type in aspects_to_roll:
            result = self.roll_aspect(kindred, aspect_type)
            if result:
                character.set_aspect(aspect_type, result)

        return character

    # =========================================================================
    # BREGGLE TABLES
    # =========================================================================

    def _register_breggle_tables(self) -> None:
        """Register all Breggle character tables."""
        # Name table
        self.register_name_table(KindredNameTable(
            kindred=Kindred.BREGGLE,
            description="Breggle names - goat-headed fairy folk",
            columns={
                NameColumn.MALE: NameTableColumn(
                    column_type=NameColumn.MALE,
                    die_type=DieType.D20,
                    names=[
                        "Barnaby", "Bramwell", "Buckthorn", "Cedric", "Clover",
                        "Daffyd", "Elderberry", "Fenwick", "Godfrey", "Hawthorn",
                        "Jasper", "Kestrel", "Linden", "Mallow", "Nettle",
                        "Oakley", "Pippin", "Quince", "Rowan", "Sorrel"
                    ]
                ),
                NameColumn.FEMALE: NameTableColumn(
                    column_type=NameColumn.FEMALE,
                    die_type=DieType.D20,
                    names=[
                        "Acacia", "Briar", "Bryony", "Clementine", "Dahlia",
                        "Eglantine", "Fern", "Ginger", "Heather", "Ivy",
                        "Juniper", "Lavender", "Marigold", "Nettle", "Olive",
                        "Petunia", "Primrose", "Rosemary", "Sage", "Willow"
                    ]
                ),
                NameColumn.UNISEX: NameTableColumn(
                    column_type=NameColumn.UNISEX,
                    die_type=DieType.D20,
                    names=[
                        "Ash", "Basil", "Birch", "Brook", "Clover",
                        "Dill", "Elm", "Fennel", "Glen", "Holly",
                        "Iris", "Jay", "Kale", "Leaf", "Moss",
                        "Oak", "Parsley", "Reed", "Rue", "Wren"
                    ]
                ),
                NameColumn.SURNAME: NameTableColumn(
                    column_type=NameColumn.SURNAME,
                    die_type=DieType.D20,
                    names=[
                        "Blackhorn", "Bramblehoof", "Cloverfield", "Dewgrass", "Fernhollow",
                        "Goatleap", "Greenmeadow", "Hedgerow", "Hillgrazer", "Ivybrook",
                        "Meadowsweet", "Mossglen", "Nettlebuck", "Oakenbrow", "Pasturegate",
                        "Ramblehorn", "Springfoot", "Thornback", "Tussock", "Willowdale"
                    ]
                ),
            }
        ))

        # Aspect tables
        self._register_aspect_table_set(
            Kindred.BREGGLE,
            background=[
                "Keeper of the sacred meadow", "Former court servant", "Wandering herbalist",
                "Exiled noble", "Village wise-one", "Shepherd of the high pastures",
                "Runaway apprentice", "Fairy ring guardian", "Traveling merchant",
                "Disgraced knight"
            ],
            trinket=[
                "A silver bell that never rings", "Pressed four-leaf clover in amber",
                "Lock of fairy hair", "Acorn from the Great Oak", "Tiny hourglass with golden sand",
                "Goat horn carved with runes", "Vial of morning dew", "Feather from a talking bird",
                "Stone that hums in moonlight", "Copper ring that belonged to a fairy lord"
            ],
            head=[
                "Long, curved horns", "Short, stubby horns", "Spiral horns",
                "Broken horn (left)", "Broken horn (right)", "Ornately decorated horns",
                "Unusually pale horns", "Dark, ridged horns", "Horns with silver tips",
                "Asymmetrical horns"
            ],
            demeanour=[
                "Gentle and patient", "Skittish and nervous", "Proud and dignified",
                "Curious and meddlesome", "Gruff and taciturn", "Merry and carefree",
                "Wise and contemplative", "Stubborn and obstinate", "Kindly but condescending",
                "Melancholic and wistful"
            ],
            desires=[
                "Return to the fairy court", "Protect the sacred groves", "Find a legendary meadow",
                "Earn gold through honest trade", "Learn the old songs", "Discover their true parentage",
                "Break an ancient curse", "Find a worthy master to serve", "Preserve the old ways",
                "Prove themselves to their clan"
            ],
            face=[
                "Rectangular pupils in golden eyes", "Wise, knowing expression",
                "Wispy beard on chin", "Long, floppy ears", "Short, alert ears",
                "Scarred muzzle", "Grey-flecked fur", "Pure white face fur",
                "Brown and white patches", "Black face with white star"
            ],
            dress=[
                "Simple homespun robes", "Embroidered waistcoat and breeches",
                "Tattered noble finery", "Practical traveling clothes", "Ceremonial vestments",
                "Shepherd's cloak", "Patchwork garments", "Fine but outdated fashion",
                "Leather jerkin and trousers", "Flowing silken robes"
            ],
            beliefs=[
                "The old pacts must be honored", "Mortals are to be pitied",
                "The fairy court will return", "Nature knows best", "Gold corrupts all",
                "Music heals all wounds", "The stars guide our fate", "Oaths are sacred",
                "The Drune must be stopped", "Balance must be maintained"
            ],
            fur_body=[
                "Sleek brown coat", "Shaggy grey fur", "White with brown spots",
                "Pure black", "Reddish-brown", "Silver-grey", "Cream colored",
                "Piebald pattern", "Brindled", "Golden tan"
            ],
            speech=[
                "Speaks in proverbs", "Gentle, musical voice", "Bleating laugh",
                "Formal, archaic speech", "Tends to ramble", "Speaks in third person",
                "Whispers secrets", "Loud and boisterous", "Measured and thoughtful",
                "Interrupts with 'baah'"
            ]
        )

    # =========================================================================
    # ELF TABLES
    # =========================================================================

    def _register_elf_tables(self) -> None:
        """Register all Elf character tables."""
        self.register_name_table(KindredNameTable(
            kindred=Kindred.ELF,
            description="Elven names - rustic or courtly styles",
            columns={
                NameColumn.RUSTIC: NameTableColumn(
                    column_type=NameColumn.RUSTIC,
                    die_type=DieType.D20,
                    names=[
                        "Ashwillow", "Birchsong", "Crowfeather", "Dewmist", "Elderbloom",
                        "Fernwhisper", "Gloaming", "Hawthorne", "Ivymere", "Junipershade",
                        "Kestrelwind", "Lichenmoss", "Moonvale", "Nighthollow", "Owlsong",
                        "Pinecrest", "Quietbrook", "Ravenwood", "Starfall", "Thornrose"
                    ]
                ),
                NameColumn.COURTLY: NameTableColumn(
                    column_type=NameColumn.COURTLY,
                    die_type=DieType.D20,
                    names=[
                        "Aelindril", "Caelanthir", "Elowen", "Faelindra", "Galadhrim",
                        "Ithilwen", "Lorindel", "Maeglin", "Náriel", "Orodreth",
                        "Rúmil", "Silmarien", "Thalion", "Úmarth", "Valandil",
                        "Celeborn", "Míriel", "Elendil", "Glorfindel", "Idril"
                    ]
                ),
            }
        ))

        self._register_aspect_table_set(
            Kindred.ELF,
            background=[
                "Exiled from the Cold Prince's court", "Wanderer between worlds",
                "Keeper of forgotten lore", "Hunter of the deep wood", "Former courtier",
                "Warden of ancient boundaries", "Seeker of mortal experiences",
                "Fugitive from fairy justice", "Ambassador to mortal lands", "Dream-walker"
            ],
            trinket=[
                "Leaf that never wilts", "Vial of starlight", "Ring of woven moonbeams",
                "Feather that writes in silver", "Crystal that shows memories",
                "Acorn from the World Tree", "Lock of a lover's hair (centuries old)",
                "Key to a door that no longer exists", "Mirror showing one's true self",
                "Flower that blooms at midnight"
            ],
            head=[
                "Long, flowing silver hair", "Hair like autumn leaves", "Raven-black tresses",
                "Hair that shifts with mood", "Crowned with living flowers",
                "Moss-green hair", "Hair like spun gold", "White hair with dark roots",
                "Hair that glows faintly", "Braided with ancient tokens"
            ],
            demeanour=[
                "Distant and otherworldly", "Curious about mortals", "Haughty and dismissive",
                "Melancholic and world-weary", "Playful and mischievous", "Stern and dutiful",
                "Languid and indolent", "Fierce and passionate", "Serene and patient",
                "Cold and calculating"
            ],
            desires=[
                "Experience true mortality", "Return to the fairy realm",
                "Find something worth dying for", "Collect mortal art and music",
                "Understand human emotions", "Atone for ancient wrongs",
                "Escape the Cold Prince's notice", "Find a cure for ennui",
                "Protect the wild places", "Learn the secret of human creativity"
            ],
            face=[
                "Eyes like pools of starlight", "Sharp, angular features",
                "Perpetual slight smile", "Eyes that change with emotion",
                "Unearthly beauty", "Face marked by ancient scars",
                "Appears young despite great age", "Eyes of solid color (no pupil)",
                "Faintly luminous skin", "Features that seem to shift"
            ],
            dress=[
                "Gossamer robes of impossible colors", "Practical woodland garb",
                "Armor of leaves and bark", "Courtly finery centuries out of fashion",
                "Simple but impossibly fine cloth", "Cloaked in living shadows",
                "Dressed in mortal fashion (poorly)", "Robes that shimmer like water",
                "Hunting leathers with silver trim", "Tattered remnants of glory"
            ],
            beliefs=[
                "Mortals are brief but beautiful", "The old ways must be preserved",
                "Change is the only constant", "Duty above all else",
                "Beauty justifies all actions", "Oaths bind beyond death",
                "The Cold Prince's rule is just", "Chaos must be embraced",
                "All things return to the wood", "Love transcends all barriers"
            ],
            fur_body=[
                "Impossibly slender", "Tall and willowy", "Graceful as flowing water",
                "Still as ancient stone", "Moves like a shadow", "Ethereally beautiful",
                "Scarred from ancient battles", "Ageless but weary", "Luminously pale",
                "Sun-bronzed like old copper"
            ],
            speech=[
                "Speaks in riddles", "Voice like distant music", "Archaic formal speech",
                "Long, contemplative pauses", "Speaks of decades as moments",
                "Poetic and elaborate", "Clipped and precise", "Whispers secrets to the wind",
                "Laughs at inappropriate moments", "References events centuries past"
            ]
        )

    # =========================================================================
    # GRIMALKIN TABLES
    # =========================================================================

    def _register_grimalkin_tables(self) -> None:
        """Register all Grimalkin character tables."""
        self.register_name_table(KindredNameTable(
            kindred=Kindred.GRIMALKIN,
            description="Grimalkin names - cat-folk with no gender distinction",
            columns={
                NameColumn.UNISEX: NameTableColumn(
                    column_type=NameColumn.UNISEX,
                    die_type=DieType.D20,
                    names=[
                        "Ash", "Bramble", "Cinder", "Dusk", "Echo",
                        "Flicker", "Ghost", "Haze", "Ink", "Jade",
                        "Kindle", "Luna", "Mist", "Nettle", "Onyx",
                        "Pounce", "Quill", "Rustle", "Shadow", "Thistle"
                    ]
                ),
                NameColumn.SURNAME: NameTableColumn(
                    column_type=NameColumn.SURNAME,
                    die_type=DieType.D20,
                    names=[
                        "Blackpaw", "Clawmark", "Darkwhisker", "Embertail", "Fangsworth",
                        "Greymane", "Hollowpurr", "Inkspot", "Jadeeye", "Knifeear",
                        "Longtail", "Moonstalker", "Nightprowl", "Owlheart", "Prowlfoot",
                        "Quickstep", "Ratcatcher", "Silentpaw", "Thornback", "Velvetpaw"
                    ]
                ),
            }
        ))

        self._register_aspect_table_set(
            Kindred.GRIMALKIN,
            background=[
                "Former witch's familiar", "Alley cat turned adventurer",
                "Escaped from a wizard's menagerie", "Temple guardian",
                "Rat-catcher turned monster-hunter", "Spy for a noble house",
                "Raised by humans, seeking cat-kind", "Exiled from a grimalkin colony",
                "Former ship's cat", "Wandering mouser"
            ],
            trinket=[
                "Ball of yarn that never tangles", "Collar with a tiny bell (silent)",
                "Preserved mouse (first catch)", "Shard of mirror showing true form",
                "Whisker from a dead elder", "Feather toy from kittenhood",
                "Vial of catnip (emergency use)", "Claw shed during first transformation",
                "Silver fish on a chain", "Key to a human door"
            ],
            head=[
                "Large, pointed ears", "Torn left ear", "Torn right ear",
                "Tufted ear tips", "Folded ears", "Unusually small ears",
                "One ear always twitches", "Ears with dark tips",
                "Notched ears (many fights)", "Fluffy ear fur"
            ],
            demeanour=[
                "Aloof and independent", "Curious and nosy", "Lazy but alert",
                "Playful and mischievous", "Haughty and superior", "Nervous and jumpy",
                "Calm and collected", "Fierce and territorial", "Affectionate but fickle",
                "Suspicious of everyone"
            ],
            desires=[
                "Find the perfect sunny spot", "Catch the legendary great mouse",
                "Earn a comfortable retirement", "Prove cats are superior to dogs",
                "Find their human family", "Rule a territory of their own",
                "Learn the secrets of magic", "Taste every type of fish",
                "Sleep in the finest bed", "Discover why they became awakened"
            ],
            face=[
                "Bright green eyes", "Golden eyes", "One blue, one green eye",
                "Scarred across muzzle", "White chin", "Black nose",
                "Pink nose", "Very long whiskers", "Short, stubby whiskers",
                "Perpetual scowl"
            ],
            dress=[
                "Refuses to wear clothes", "Simple collar and belt",
                "Tiny waistcoat", "Cloak with many pockets", "Leather harness for gear",
                "Miniature human outfit", "Just a jaunty hat", "Practical adventuring gear",
                "Tattered but dignified clothing", "Stolen noble finery"
            ],
            beliefs=[
                "Cats are inherently superior", "Curiosity is worth any risk",
                "Trust must be earned slowly", "Naps solve most problems",
                "Birds are the true enemy", "Humans are useful servants",
                "Independence above all", "The best things come to those who wait",
                "Never show weakness", "Always land on your feet"
            ],
            fur_body=[
                "Sleek black coat", "Orange tabby", "Grey striped",
                "White with patches", "Calico", "Tuxedo pattern",
                "Long, fluffy fur", "Short, dense coat", "Spotted like a leopard",
                "Solid grey"
            ],
            speech=[
                "Tends to purr when pleased", "Hisses when angry",
                "Very few words, meaningful looks", "Surprisingly eloquent",
                "Speaks in short, clipped sentences", "Frequently meows mid-sentence",
                "Sophisticated vocabulary", "Mumbles while grooming",
                "Makes clicking sounds at birds", "Speaks only when necessary"
            ]
        )

    # =========================================================================
    # HUMAN TABLES
    # =========================================================================

    def _register_human_tables(self) -> None:
        """Register all Human character tables."""
        self.register_name_table(KindredNameTable(
            kindred=Kindred.HUMAN,
            description="Human names - common folk of Dolmenwood",
            columns={
                NameColumn.MALE: NameTableColumn(
                    column_type=NameColumn.MALE,
                    die_type=DieType.D20,
                    names=[
                        "Aldric", "Bram", "Cedric", "Dunstan", "Edmund",
                        "Fulke", "Godwin", "Harold", "Ivan", "Jasper",
                        "Kenric", "Leofric", "Malcolm", "Norbert", "Osric",
                        "Percival", "Quentin", "Roland", "Silas", "Thom"
                    ]
                ),
                NameColumn.FEMALE: NameTableColumn(
                    column_type=NameColumn.FEMALE,
                    die_type=DieType.D20,
                    names=[
                        "Agnes", "Beatrice", "Cecily", "Drusilla", "Edith",
                        "Frieda", "Gwendolyn", "Hilda", "Isolde", "Joan",
                        "Katherine", "Lettice", "Margery", "Nest", "Osanna",
                        "Petronilla", "Rohese", "Sabina", "Thomasina", "Ursula"
                    ]
                ),
                NameColumn.UNISEX: NameTableColumn(
                    column_type=NameColumn.UNISEX,
                    die_type=DieType.D20,
                    names=[
                        "Aelfric", "Blair", "Carey", "Dale", "Ellis",
                        "Florian", "Garnet", "Hollis", "Ira", "Jules",
                        "Kerry", "Linden", "Morgan", "Noel", "Oakley",
                        "Perry", "Quinn", "Raven", "Shannon", "Terry"
                    ]
                ),
                NameColumn.SURNAME: NameTableColumn(
                    column_type=NameColumn.SURNAME,
                    die_type=DieType.D20,
                    names=[
                        "Ashford", "Baker", "Cooper", "Draper", "Fletcher",
                        "Greenwood", "Harper", "Ironside", "Joiner", "Keller",
                        "Lockwood", "Miller", "Northcott", "Oakenshield", "Potter",
                        "Quarry", "Roper", "Smith", "Thatcher", "Weaver"
                    ]
                ),
            }
        ))

        self._register_aspect_table_set(
            Kindred.HUMAN,
            background=[
                "Farmer's child seeking fortune", "Disgraced soldier", "Runaway apprentice",
                "Orphan of the plague years", "Former servant to nobility",
                "Traveling peddler", "Failed priest or nun", "Hunter and trapper",
                "Village wise-woman's student", "Refugee from a burned village"
            ],
            trinket=[
                "Father's lucky coin", "Mother's wedding ring", "Lock of a loved one's hair",
                "Carved wooden holy symbol", "Pressed flower from home",
                "Letter never delivered", "Child's toy kept for luck",
                "Tooth from first monster killed", "Candle stub from a vigil",
                "Ribbon from a festival"
            ],
            head=[
                "Thick, unruly hair", "Balding prematurely", "Grey at the temples",
                "Distinctive widow's peak", "Hair always covered", "Wild, unkempt mane",
                "Neatly trimmed", "Long and braided", "Recently shorn",
                "Unusual color for the region"
            ],
            demeanour=[
                "Cheerful despite hardship", "Bitter and cynical", "Quietly determined",
                "Nervously optimistic", "Grimly fatalistic", "Earnestly helpful",
                "Suspicious of strangers", "Eager to please", "World-weary but kind",
                "Brash and overconfident"
            ],
            desires=[
                "Earn enough to retire", "Find a missing family member",
                "Prove themselves worthy", "Escape their past", "Gain land and title",
                "Learn to read and write", "See the world beyond Dolmenwood",
                "Revenge against the Drune", "Find true love", "Build something lasting"
            ],
            face=[
                "Weathered and lined", "Youthful and fresh", "Scarred from pox",
                "Strong jaw", "Soft features", "Broken nose",
                "Missing teeth", "Remarkably handsome/beautiful", "Plain and forgettable",
                "Distinctive birthmark"
            ],
            dress=[
                "Patched but clean homespun", "Sturdy work clothes", "Hand-me-down finery",
                "Practical traveling gear", "Church-day best (worn daily)",
                "Beggar's rags", "Stolen noble clothes", "Hunter's leathers",
                "Craftsman's apron and tools", "Soldier's old uniform"
            ],
            beliefs=[
                "Hard work brings reward", "The Church protects us",
                "Trust no one fully", "Family above all", "The old ways are best",
                "Gold is the only truth", "Honor must be defended",
                "The woods are dangerous", "Fate cannot be escaped",
                "Everyone deserves a second chance"
            ],
            fur_body=[
                "Sturdy and stocky", "Tall and gangly", "Short but strong",
                "Heavy-set", "Wiry and lean", "Broad-shouldered",
                "Slight and nimble", "Average in every way", "Unusually large",
                "Small but fierce"
            ],
            speech=[
                "Speaks with rural accent", "Surprisingly well-spoken",
                "Tends to mumble", "Loud and boisterous", "Quiet and measured",
                "Uses many local expressions", "Speaks with a stammer",
                "Voice roughened by smoke", "Gentle, soothing tone",
                "Speaks too quickly when nervous"
            ]
        )

    # =========================================================================
    # MOSSLING TABLES
    # =========================================================================

    def _register_mossling_tables(self) -> None:
        """Register all Mossling character tables."""
        self.register_name_table(KindredNameTable(
            kindred=Kindred.MOSSLING,
            description="Mossling names - small moss-covered folk",
            columns={
                NameColumn.MALE: NameTableColumn(
                    column_type=NameColumn.MALE,
                    die_type=DieType.D20,
                    names=[
                        "Boggle", "Clump", "Damp", "Earthy", "Fungus",
                        "Grime", "Humus", "Ivy", "Jumble", "Knurl",
                        "Lichen", "Mulch", "Nodule", "Ooze", "Peat",
                        "Quirk", "Root", "Spore", "Tangle", "Umber"
                    ]
                ),
                NameColumn.FEMALE: NameTableColumn(
                    column_type=NameColumn.FEMALE,
                    die_type=DieType.D20,
                    names=[
                        "Algae", "Bloom", "Cushion", "Dewdrop", "Emerald",
                        "Frond", "Greenie", "Herb", "Iris", "Jade",
                        "Kelp", "Liverwort", "Meadow", "Nettle", "Orchid",
                        "Petal", "Quag", "Rosette", "Sprout", "Thyme"
                    ]
                ),
                NameColumn.UNISEX: NameTableColumn(
                    column_type=NameColumn.UNISEX,
                    die_type=DieType.D20,
                    names=[
                        "Amber", "Bracket", "Cap", "Duff", "Earthstar",
                        "Fern", "Gill", "Hummock", "Inkcap", "Jelly",
                        "Knob", "Loam", "Mire", "Nub", "Oyster",
                        "Puff", "Russet", "Slime", "Toadstool", "Verdant"
                    ]
                ),
                NameColumn.SURNAME: NameTableColumn(
                    column_type=NameColumn.SURNAME,
                    die_type=DieType.D20,
                    names=[
                        "Bogbottom", "Damphollow", "Earthmound", "Fernbed", "Greenknoll",
                        "Hollowstump", "Ivyroot", "Logfall", "Marshbank", "Moldhill",
                        "Mossback", "Mudfoot", "Puddlejump", "Rotwood", "Soggybank",
                        "Sporecap", "Stumpkin", "Toadhollow", "Wetlog", "Wurzelbed"
                    ]
                ),
            }
        ))

        self._register_aspect_table_set(
            Kindred.MOSSLING,
            background=[
                "Mushroom tender", "Bog guide", "Colony scout",
                "Healer using swamp remedies", "Escaped pet of a witch",
                "Curious explorer of dry lands", "Trader in rare fungi",
                "Guardian of a sacred pool", "Survivor of a destroyed colony",
                "Apprentice to a moss dwarf"
            ],
            trinket=[
                "Preserved mushroom (edible?)", "Snail shell whistle",
                "Jar of glowing spores", "Tiny carved frog", "Vial of swamp water",
                "Beetle carapace mirror", "Dried lily pad map", "Slug slime in a bottle",
                "Lucky stone from the deeps", "Feather from a crane"
            ],
            head=[
                "Covered in thick moss", "Sparse, patchy moss", "Mushrooms growing from head",
                "Tiny flowers blooming", "Wet and glistening", "Dried and cracked",
                "Bright green moss", "Dark green, almost black", "Yellow-tinged moss",
                "Moss with silver threads"
            ],
            demeanour=[
                "Perpetually damp enthusiasm", "Shy and retiring", "Bouncy and energetic",
                "Slow and contemplative", "Nervously cheerful", "Stoically calm",
                "Excitedly curious", "Grumpily helpful", "Dreamily absent",
                "Surprisingly fierce"
            ],
            desires=[
                "Find the perfect damp spot", "Catalog every mushroom",
                "Return with tales for the colony", "Taste foods of the dry-landers",
                "Find a cure for the colony's ailment", "Experience a desert",
                "Befriend a big folk", "Grow the rarest fungus", "See the ocean",
                "Become a great hero"
            ],
            face=[
                "Wide, frog-like mouth", "Enormous dark eyes", "Tiny, beady eyes",
                "Warty skin", "Smooth, moist skin", "Perpetually smiling",
                "Solemn expression", "Mushroom growing from cheek",
                "Spots and speckles", "Translucent in places"
            ],
            dress=[
                "Woven reed clothing", "Bark strips and leaves", "Nothing but moss",
                "Tiny human-style clothes", "Snail shell accessories",
                "Frog-leather vest", "Lily pad hat", "Spider silk garments",
                "Dried mushroom cap hat", "Toad-skin boots"
            ],
            beliefs=[
                "Dampness is next to godliness", "The colony comes first",
                "All life is connected through the soil", "Big folk mean big trouble",
                "Mushrooms hold all wisdom", "Water finds its own level",
                "Slow and steady wins", "The swamp provides",
                "Decay feeds new growth", "Never trust anything that stays dry"
            ],
            fur_body=[
                "Round and squat", "Tall for a mossling (6 inches)", "Tiny and compact",
                "Lumpy and uneven", "Sleek and smooth", "Covered in bumps",
                "Semi-translucent", "Bark-like skin", "Rubbery texture",
                "Slightly squishy"
            ],
            speech=[
                "Speaks in croaks", "High-pitched and squeaky", "Gurgles between words",
                "Surprisingly deep voice", "Whispers everything", "Speaks in questions",
                "Uses water metaphors constantly", "Hums when thinking",
                "Makes popping sounds", "Speaks very slowly"
            ]
        )

    # =========================================================================
    # WOODGRUE TABLES
    # =========================================================================

    def _register_woodgrue_tables(self) -> None:
        """Register all Woodgrue character tables."""
        self.register_name_table(KindredNameTable(
            kindred=Kindred.WOODGRUE,
            description="Woodgrue names - small forest tricksters",
            columns={
                NameColumn.MALE: NameTableColumn(
                    column_type=NameColumn.MALE,
                    die_type=DieType.D20,
                    names=[
                        "Barkle", "Chitter", "Dingle", "Fizzle", "Gnarr",
                        "Hickle", "Jangle", "Knick", "Lirrup", "Mizzle",
                        "Natter", "Ozzle", "Prattle", "Quibble", "Razzle",
                        "Snicker", "Twigget", "Uzzel", "Whirr", "Zizzle"
                    ]
                ),
                NameColumn.FEMALE: NameTableColumn(
                    column_type=NameColumn.FEMALE,
                    die_type=DieType.D20,
                    names=[
                        "Acorna", "Brindel", "Chirrup", "Dazzle", "Fawna",
                        "Glimmer", "Hazella", "Jinx", "Kira", "Leaflet",
                        "Nutkin", "Oriole", "Pippa", "Quirrel", "Ribbita",
                        "Sparkle", "Trill", "Vespa", "Whimsy", "Zephyra"
                    ]
                ),
                NameColumn.UNISEX: NameTableColumn(
                    column_type=NameColumn.UNISEX,
                    die_type=DieType.D20,
                    names=[
                        "Acorn", "Bounce", "Cricket", "Dash", "Ember",
                        "Fidget", "Glint", "Hop", "Itch", "Jitter",
                        "Keen", "Leap", "Midge", "Nimble", "Oddkin",
                        "Prance", "Quick", "Rush", "Skip", "Tumble"
                    ]
                ),
                NameColumn.SURNAME: NameTableColumn(
                    column_type=NameColumn.SURNAME,
                    die_type=DieType.D20,
                    names=[
                        "Acornsnatch", "Branchswing", "Cobwebweaver", "Dingleberry", "Flickertail",
                        "Gadabout", "Hickorynut", "Ivytangle", "Jumpabout", "Knothider",
                        "Leafdancer", "Mistmaker", "Nutcracker", "Oakwhisper", "Pinesap",
                        "Quickfoot", "Rootdigger", "Shadowskip", "Thornprick", "Willowwisp"
                    ]
                ),
            }
        ))

        self._register_aspect_table_set(
            Kindred.WOODGRUE,
            background=[
                "Prankster gone too far", "Escaped from fairy service",
                "Curious explorer", "Collector of shiny things", "Former pest, reformed",
                "Messenger between settlements", "Thief with a heart of gold",
                "Survivor of a destroyed warren", "Seeker of the perfect joke",
                "Would-be hero"
            ],
            trinket=[
                "Stolen noble's button", "Bell that only woodgrues hear",
                "Acorn cap drinking cup", "Thorn dagger", "Firefly in a jar",
                "Map to a forgotten cache", "Tuft of giant's beard",
                "Wishbone never broken", "Feather pen", "Tiny mirror"
            ],
            head=[
                "Large, batlike ears", "Pointed ears that swivel", "Tiny horns",
                "Wild, sticking-up hair", "Bald with spots", "Feathery tuft",
                "Leaves tangled in hair", "Acorn cap worn as hat",
                "Hair that changes with seasons", "Twigs growing from head"
            ],
            demeanour=[
                "Mischievous and gleeful", "Paranoid but friendly", "Hyperactive",
                "Cunning and scheming", "Surprisingly solemn", "Easily distracted",
                "Fiercely loyal", "Cowardly but brave when needed",
                "Endlessly curious", "Grumpy but lovable"
            ],
            desires=[
                "Pull off the greatest prank", "Collect every type of button",
                "Find the legendary acorn", "Make a giant friend",
                "Prove woodgrues aren't just pests", "Fill their hidey-hole with treasure",
                "Learn real magic", "Taste every food in the world",
                "Have a song written about them", "Find their true family"
            ],
            face=[
                "Huge eyes, always wide", "Pointed nose like a beak",
                "Wide, froggy grin", "Whiskers like a mouse", "Tiny, beady eyes",
                "Constantly twitching nose", "Crooked smile",
                "Surprisingly handsome for a woodgrue", "Covered in freckles",
                "Missing teeth (lost in adventures)"
            ],
            dress=[
                "Patchwork of stolen cloth", "Leaves and bark", "Acorn cap hat and nothing else",
                "Miniature adventurer outfit", "Spider silk cape",
                "Vest made of mouse fur", "Belt of woven grass with many pouches",
                "Found human doll clothes", "Bark armor", "Mushroom cap helmet"
            ],
            beliefs=[
                "Everything can be stolen", "Laughter is the best medicine",
                "The strong protect the weak", "Rules are suggestions",
                "Secrets are treasures", "Big folk are slow and silly",
                "Always have an escape route", "Share with the warren",
                "Never betray a friend", "If it's not nailed down, it's fair game"
            ],
            fur_body=[
                "Tiny, about 8 inches", "Large for a woodgrue (foot tall)",
                "Wiry and lean", "Pudgy from too many acorns", "All arms and legs",
                "Covered in fine fur", "Scaly patches", "Bark-like skin",
                "Striped like a chipmunk", "Spotted like a fawn"
            ],
            speech=[
                "Speaks incredibly fast", "Rhymes without meaning to",
                "Giggles between words", "Speaks in third person",
                "Uses too many big words", "Makes up words constantly",
                "Whispers conspiratorially", "Squeaks when excited",
                "Surprisingly eloquent", "Chatters like a squirrel"
            ]
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _register_aspect_table_set(
        self,
        kindred: Kindred,
        background: list[str],
        trinket: list[str],
        head: list[str],
        demeanour: list[str],
        desires: list[str],
        face: list[str],
        dress: list[str],
        beliefs: list[str],
        fur_body: list[str],
        speech: list[str],
    ) -> None:
        """Helper to register a complete set of aspect tables for a kindred."""
        aspects = [
            (CharacterAspectType.BACKGROUND, "Background", background),
            (CharacterAspectType.TRINKET, "Trinket", trinket),
            (CharacterAspectType.HEAD, "Head", head),
            (CharacterAspectType.DEMEANOUR, "Demeanour", demeanour),
            (CharacterAspectType.DESIRES, "Desires", desires),
            (CharacterAspectType.FACE, "Face", face),
            (CharacterAspectType.DRESS, "Dress", dress),
            (CharacterAspectType.BELIEFS, "Beliefs", beliefs),
            (CharacterAspectType.FUR_BODY, "Fur/Body", fur_body),
            (CharacterAspectType.SPEECH, "Speech", speech),
        ]

        for aspect_type, name, entries_list in aspects:
            entries = [
                TableEntry(roll_min=i+1, roll_max=i+1, result=entry)
                for i, entry in enumerate(entries_list)
            ]

            self.register_aspect_table(CharacterAspectTable(
                table_id=f"{kindred.value}_{aspect_type.value}",
                kindred=kindred,
                aspect_type=aspect_type,
                name=f"{kindred.value.title()} {name}",
                die_type=DieType.D10,
                entries=entries,
            ))


# Global instance
_character_manager: Optional[CharacterTableManager] = None


def get_character_table_manager() -> CharacterTableManager:
    """Get the global CharacterTableManager instance."""
    global _character_manager
    if _character_manager is None:
        _character_manager = CharacterTableManager()
    return _character_manager
