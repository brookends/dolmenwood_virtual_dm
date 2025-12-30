"""
Dolmenwood-specific game tables.

Contains all the standard tables for the Dolmenwood setting including
encounter tables, character aspect tables, treasure tables, and more.
"""

from typing import Optional
from src.tables.table_types import (
    TableCategory,
    DieType,
    TableEntry,
    DolmenwoodTable,
    TableResult,
    TableContext,
)
from src.tables.table_manager import TableManager, get_table_manager


class DolmenwoodTables:
    """
    Collection of Dolmenwood-specific game tables.

    Provides access to all standard tables for the setting,
    organized by category and context.
    """

    def __init__(self, manager: Optional[TableManager] = None):
        self.manager = manager or get_table_manager()
        self._register_dolmenwood_tables()

    def _register_dolmenwood_tables(self) -> None:
        """Register all Dolmenwood-specific tables."""
        # Character aspect tables
        self._register_character_tables()

        # Encounter tables
        self._register_encounter_tables()

        # Treasure tables
        self._register_treasure_tables()

        # NPC tables
        self._register_npc_tables()

        # Rumor tables
        self._register_rumor_tables()

        # Flavor tables
        self._register_flavor_tables()

        # Dungeon tables
        self._register_dungeon_tables()

    # =========================================================================
    # CHARACTER ASPECT TABLES
    # =========================================================================

    def _register_character_tables(self) -> None:
        """Register character creation/aspect tables."""

        # Physical appearance
        self.manager.register_table(
            DolmenwoodTable(
                table_id="character_hair_color",
                name="Hair Color",
                category=TableCategory.CHARACTER_ASPECT,
                die_type=DieType.D8,
                description="Random hair color for character creation",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Black"),
                    TableEntry(roll_min=2, roll_max=2, result="Brown"),
                    TableEntry(roll_min=3, roll_max=3, result="Auburn"),
                    TableEntry(roll_min=4, roll_max=4, result="Red"),
                    TableEntry(roll_min=5, roll_max=5, result="Blonde"),
                    TableEntry(roll_min=6, roll_max=6, result="White/Grey"),
                    TableEntry(roll_min=7, roll_max=7, result="Unusual (green, blue, etc.)"),
                    TableEntry(roll_min=8, roll_max=8, result="Bald or shaved"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="character_eye_color",
                name="Eye Color",
                category=TableCategory.CHARACTER_ASPECT,
                die_type=DieType.D6,
                description="Random eye color",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Brown"),
                    TableEntry(roll_min=2, roll_max=2, result="Blue"),
                    TableEntry(roll_min=3, roll_max=3, result="Green"),
                    TableEntry(roll_min=4, roll_max=4, result="Grey"),
                    TableEntry(roll_min=5, roll_max=5, result="Hazel"),
                    TableEntry(roll_min=6, roll_max=6, result="Unusual (violet, gold, etc.)"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="character_distinguishing_feature",
                name="Distinguishing Feature",
                category=TableCategory.CHARACTER_ASPECT,
                die_type=DieType.D12,
                description="Notable physical feature",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Prominent scar"),
                    TableEntry(roll_min=2, roll_max=2, result="Missing finger or ear"),
                    TableEntry(roll_min=3, roll_max=3, result="Unusual birthmark"),
                    TableEntry(roll_min=4, roll_max=4, result="Extremely tall or short"),
                    TableEntry(roll_min=5, roll_max=5, result="Distinctive tattoo"),
                    TableEntry(roll_min=6, roll_max=6, result="Limp or other gait"),
                    TableEntry(
                        roll_min=7, roll_max=7, result="Distinctive voice (deep, squeaky, etc.)"
                    ),
                    TableEntry(roll_min=8, roll_max=8, result="Unusual complexion"),
                    TableEntry(roll_min=9, roll_max=9, result="Crooked nose"),
                    TableEntry(roll_min=10, roll_max=10, result="Heterochromatic eyes"),
                    TableEntry(roll_min=11, roll_max=11, result="Exceptionally attractive"),
                    TableEntry(roll_min=12, roll_max=12, result="Exceptionally plain"),
                ],
            )
        )

        # Background/Origin
        self.manager.register_table(
            DolmenwoodTable(
                table_id="character_background",
                name="Background",
                category=TableCategory.CHARACTER_ASPECT,
                die_type=DieType.D20,
                description="Character's previous occupation or background",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Farmer or peasant"),
                    TableEntry(roll_min=2, roll_max=2, result="Woodcutter"),
                    TableEntry(roll_min=3, roll_max=3, result="Hunter or trapper"),
                    TableEntry(roll_min=4, roll_max=4, result="Fisher"),
                    TableEntry(roll_min=5, roll_max=5, result="Shepherd"),
                    TableEntry(roll_min=6, roll_max=6, result="Craftsman (smith, carpenter, etc.)"),
                    TableEntry(roll_min=7, roll_max=7, result="Merchant or trader"),
                    TableEntry(roll_min=8, roll_max=8, result="Soldier or guard"),
                    TableEntry(roll_min=9, roll_max=9, result="Sailor or riverfolk"),
                    TableEntry(roll_min=10, roll_max=10, result="Servant or laborer"),
                    TableEntry(roll_min=11, roll_max=11, result="Herbalist or healer"),
                    TableEntry(roll_min=12, roll_max=12, result="Entertainer (minstrel, jester)"),
                    TableEntry(roll_min=13, roll_max=13, result="Scribe or scholar"),
                    TableEntry(roll_min=14, roll_max=14, result="Thief or pickpocket"),
                    TableEntry(roll_min=15, roll_max=15, result="Beggar or vagrant"),
                    TableEntry(roll_min=16, roll_max=16, result="Noble's child (disgraced)"),
                    TableEntry(roll_min=17, roll_max=17, result="Monastery (escaped or expelled)"),
                    TableEntry(roll_min=18, roll_max=18, result="Orphan raised by strangers"),
                    TableEntry(roll_min=19, roll_max=19, result="Outlaw's band"),
                    TableEntry(roll_min=20, roll_max=20, result="Unknown or mysterious origin"),
                ],
            )
        )

        # Personality/Beliefs
        self.manager.register_table(
            DolmenwoodTable(
                table_id="character_personality_trait",
                name="Personality Trait",
                category=TableCategory.CHARACTER_ASPECT,
                die_type=DieType.D10,
                description="Dominant personality trait",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Cautious and methodical"),
                    TableEntry(roll_min=2, roll_max=2, result="Reckless and impulsive"),
                    TableEntry(roll_min=3, roll_max=3, result="Kind and generous"),
                    TableEntry(roll_min=4, roll_max=4, result="Suspicious and paranoid"),
                    TableEntry(roll_min=5, roll_max=5, result="Ambitious and driven"),
                    TableEntry(roll_min=6, roll_max=6, result="Lazy and unmotivated"),
                    TableEntry(roll_min=7, roll_max=7, result="Curious and inquisitive"),
                    TableEntry(roll_min=8, roll_max=8, result="Stoic and reserved"),
                    TableEntry(roll_min=9, roll_max=9, result="Jovial and boisterous"),
                    TableEntry(roll_min=10, roll_max=10, result="Melancholic and brooding"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="character_motivation",
                name="Motivation",
                category=TableCategory.CHARACTER_ASPECT,
                die_type=DieType.D8,
                description="What drives this character",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Wealth and material comfort"),
                    TableEntry(roll_min=2, roll_max=2, result="Fame and glory"),
                    TableEntry(roll_min=3, roll_max=3, result="Knowledge and secrets"),
                    TableEntry(roll_min=4, roll_max=4, result="Revenge against a specific enemy"),
                    TableEntry(roll_min=5, roll_max=5, result="Protecting family or loved ones"),
                    TableEntry(roll_min=6, roll_max=6, result="Religious devotion or crusade"),
                    TableEntry(roll_min=7, roll_max=7, result="Wanderlust and adventure"),
                    TableEntry(roll_min=8, roll_max=8, result="Escaping a troubled past"),
                ],
            )
        )

    # =========================================================================
    # ENCOUNTER TABLES
    # =========================================================================

    def _register_encounter_tables(self) -> None:
        """Register wilderness and dungeon encounter tables."""

        # Generic wilderness encounter by terrain
        self.manager.register_table(
            DolmenwoodTable(
                table_id="encounter_forest",
                name="Forest Encounters",
                category=TableCategory.ENCOUNTER_GENERIC,
                die_type=DieType.D12,
                description="Random encounters in forest terrain",
                entries=[
                    TableEntry(
                        roll_min=1,
                        roll_max=1,
                        result="Wild boar (1d4)",
                        monster_refs=["wild_boar"],
                        quantity="1d4",
                    ),
                    TableEntry(
                        roll_min=2,
                        roll_max=2,
                        result="Giant spider (1d3)",
                        monster_refs=["giant_spider"],
                        quantity="1d3",
                    ),
                    TableEntry(
                        roll_min=3,
                        roll_max=3,
                        result="Wolves (2d4)",
                        monster_refs=["wolf"],
                        quantity="2d4",
                    ),
                    TableEntry(
                        roll_min=4,
                        roll_max=4,
                        result="Bandits (2d6)",
                        monster_refs=["bandit"],
                        quantity="2d6",
                    ),
                    TableEntry(
                        roll_min=5,
                        roll_max=5,
                        result="Woodwose (1d6)",
                        monster_refs=["woodwose"],
                        quantity="1d6",
                    ),
                    TableEntry(
                        roll_min=6,
                        roll_max=6,
                        result="Moss dwarf patrol (1d4+1)",
                        monster_refs=["moss_dwarf"],
                        quantity="1d4+1",
                    ),
                    TableEntry(
                        roll_min=7,
                        roll_max=7,
                        result="Grimalkin (1)",
                        monster_refs=["grimalkin"],
                        quantity="1",
                    ),
                    TableEntry(
                        roll_min=8,
                        roll_max=8,
                        result="Deer or elk (peaceful)",
                        monster_refs=["deer"],
                    ),
                    TableEntry(roll_min=9, roll_max=9, result="Traveling merchant NPC"),
                    TableEntry(roll_min=10, roll_max=10, result="Lost peasant seeking help"),
                    TableEntry(roll_min=11, roll_max=11, result="Fairy ring (roll on Fairy table)"),
                    TableEntry(
                        roll_min=12, roll_max=12, result="Special encounter (roll on hex table)"
                    ),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="encounter_bog",
                name="Bog Encounters",
                category=TableCategory.ENCOUNTER_GENERIC,
                die_type=DieType.D10,
                description="Random encounters in bog/swamp terrain",
                entries=[
                    TableEntry(
                        roll_min=1,
                        roll_max=1,
                        result="Giant frog (1d4)",
                        monster_refs=["giant_frog"],
                        quantity="1d4",
                    ),
                    TableEntry(
                        roll_min=2,
                        roll_max=2,
                        result="Giant leech (1d3)",
                        monster_refs=["giant_leech"],
                        quantity="1d3",
                    ),
                    TableEntry(
                        roll_min=3,
                        roll_max=3,
                        result="Bog body (1d2)",
                        monster_refs=["bog_body"],
                        quantity="1d2",
                    ),
                    TableEntry(
                        roll_min=4,
                        roll_max=4,
                        result="Will-o'-wisp (1)",
                        monster_refs=["will_o_wisp"],
                    ),
                    TableEntry(
                        roll_min=5, roll_max=5, result="Banshee (1)", monster_refs=["banshee"]
                    ),
                    TableEntry(
                        roll_min=6,
                        roll_max=6,
                        result="Giant snake (1d2)",
                        monster_refs=["giant_snake"],
                        quantity="1d2",
                    ),
                    TableEntry(
                        roll_min=7, roll_max=7, result="Drune scouts (1d4)", monster_refs=["drune"]
                    ),
                    TableEntry(roll_min=8, roll_max=8, result="Lost traveler"),
                    TableEntry(roll_min=9, roll_max=9, result="Herbalist gathering ingredients"),
                    TableEntry(roll_min=10, roll_max=10, result="Special encounter"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="encounter_road",
                name="Road Encounters",
                category=TableCategory.ENCOUNTER_GENERIC,
                die_type=DieType.D10,
                description="Random encounters on roads and trails",
                entries=[
                    TableEntry(
                        roll_min=1,
                        roll_max=1,
                        result="Bandits (2d6)",
                        monster_refs=["bandit"],
                        quantity="2d6",
                    ),
                    TableEntry(roll_min=2, roll_max=2, result="Merchant caravan"),
                    TableEntry(roll_min=3, roll_max=3, result="Patrol (1d6 soldiers)"),
                    TableEntry(roll_min=4, roll_max=4, result="Pilgrims (2d6)"),
                    TableEntry(roll_min=5, roll_max=5, result="Traveling performer"),
                    TableEntry(roll_min=6, roll_max=6, result="Noble's entourage"),
                    TableEntry(roll_min=7, roll_max=7, result="Refugees fleeing something"),
                    TableEntry(
                        roll_min=8, roll_max=8, result="Wandering monster (roll terrain table)"
                    ),
                    TableEntry(roll_min=9, roll_max=9, result="Overturned cart"),
                    TableEntry(roll_min=10, roll_max=10, result="Mysterious stranger"),
                ],
            )
        )

        # Encounter distance
        self.manager.register_table(
            DolmenwoodTable(
                table_id="encounter_distance",
                name="Encounter Distance",
                category=TableCategory.ENCOUNTER_GENERIC,
                die_type=DieType.D6,
                description="Starting distance for wilderness encounters",
                entries=[
                    TableEntry(
                        roll_min=1, roll_max=1, result="40 feet", mechanical_effect="distance_40"
                    ),
                    TableEntry(
                        roll_min=2, roll_max=2, result="60 feet", mechanical_effect="distance_60"
                    ),
                    TableEntry(
                        roll_min=3, roll_max=3, result="80 feet", mechanical_effect="distance_80"
                    ),
                    TableEntry(
                        roll_min=4, roll_max=4, result="100 feet", mechanical_effect="distance_100"
                    ),
                    TableEntry(
                        roll_min=5, roll_max=5, result="120 feet", mechanical_effect="distance_120"
                    ),
                    TableEntry(
                        roll_min=6, roll_max=6, result="160 feet", mechanical_effect="distance_160"
                    ),
                ],
            )
        )

        # Monster activity
        self.manager.register_table(
            DolmenwoodTable(
                table_id="monster_activity",
                name="Monster Activity",
                category=TableCategory.ENCOUNTER_GENERIC,
                die_type=DieType.D6,
                description="What the encountered creatures are doing",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Hunting/searching for food"),
                    TableEntry(roll_min=2, roll_max=2, result="Traveling/migrating"),
                    TableEntry(roll_min=3, roll_max=3, result="Guarding territory/lair"),
                    TableEntry(roll_min=4, roll_max=4, result="Resting/sleeping"),
                    TableEntry(
                        roll_min=5, roll_max=5, result="Fighting/arguing with another group"
                    ),
                    TableEntry(roll_min=6, roll_max=6, result="Engaged in unusual activity"),
                ],
            )
        )

    # =========================================================================
    # TREASURE TABLES
    # =========================================================================

    def _register_treasure_tables(self) -> None:
        """Register treasure generation tables."""

        # Treasure presence
        self.manager.register_table(
            DolmenwoodTable(
                table_id="treasure_type_minor",
                name="Minor Treasure",
                category=TableCategory.TREASURE_TYPE,
                die_type=DieType.D6,
                description="Minor treasure found on creatures",
                entries=[
                    TableEntry(roll_min=1, roll_max=2, result="Copper coins (3d6)", quantity="3d6"),
                    TableEntry(roll_min=3, roll_max=4, result="Silver coins (2d6)", quantity="2d6"),
                    TableEntry(roll_min=5, roll_max=5, result="Gold coins (1d6)", quantity="1d6"),
                    TableEntry(roll_min=6, roll_max=6, result="Small gem or jewelry piece"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="treasure_type_standard",
                name="Standard Treasure",
                category=TableCategory.TREASURE_TYPE,
                die_type=DieType.D8,
                description="Standard treasure hoard",
                entries=[
                    TableEntry(
                        roll_min=1, roll_max=2, result="Copper coins (2d100)", quantity="2d100"
                    ),
                    TableEntry(
                        roll_min=3, roll_max=4, result="Silver coins (1d100)", quantity="1d100"
                    ),
                    TableEntry(roll_min=5, roll_max=6, result="Gold coins (3d20)", quantity="3d20"),
                    TableEntry(
                        roll_min=7,
                        roll_max=7,
                        result="Gems (1d4)",
                        quantity="1d4",
                        sub_table="gem_value",
                    ),
                    TableEntry(
                        roll_min=8, roll_max=8, result="Magic item", sub_table="magic_item_minor"
                    ),
                ],
            )
        )

        # Gem values
        self.manager.register_table(
            DolmenwoodTable(
                table_id="gem_value",
                name="Gem Value",
                category=TableCategory.TREASURE_ITEM,
                die_type=DieType.D6,
                description="Value of a found gem",
                entries=[
                    TableEntry(
                        roll_min=1, roll_max=1, result="10gp - Ornamental (agate, turquoise)"
                    ),
                    TableEntry(
                        roll_min=2, roll_max=2, result="50gp - Semiprecious (amethyst, jade)"
                    ),
                    TableEntry(roll_min=3, roll_max=3, result="100gp - Fancy (garnet, pearl)"),
                    TableEntry(roll_min=4, roll_max=4, result="500gp - Precious (opal, topaz)"),
                    TableEntry(roll_min=5, roll_max=5, result="1000gp - Gem (ruby, sapphire)"),
                    TableEntry(roll_min=6, roll_max=6, result="5000gp - Jewel (diamond, emerald)"),
                ],
            )
        )

        # Magic item tables
        self.manager.register_table(
            DolmenwoodTable(
                table_id="magic_item_minor",
                name="Minor Magic Item",
                category=TableCategory.MAGIC_ITEM,
                die_type=DieType.D12,
                description="Minor magic item",
                entries=[
                    TableEntry(roll_min=1, roll_max=2, result="Potion of Healing"),
                    TableEntry(roll_min=3, roll_max=3, result="Potion of Invisibility"),
                    TableEntry(roll_min=4, roll_max=4, result="Scroll (1 spell, level 1-2)"),
                    TableEntry(roll_min=5, roll_max=5, result="+1 Dagger"),
                    TableEntry(roll_min=6, roll_max=6, result="+1 Arrows (2d6)", quantity="2d6"),
                    TableEntry(roll_min=7, roll_max=7, result="Ring of Protection +1"),
                    TableEntry(
                        roll_min=8,
                        roll_max=8,
                        result="Wand of Magic Detection (1d10 charges)",
                        quantity="1d10",
                    ),
                    TableEntry(roll_min=9, roll_max=9, result="Cloak of Elvenkind"),
                    TableEntry(roll_min=10, roll_max=10, result="Boots of Elvenkind"),
                    TableEntry(roll_min=11, roll_max=11, result="Bag of Holding"),
                    TableEntry(
                        roll_min=12,
                        roll_max=12,
                        result="Roll on major magic item table",
                        sub_table="magic_item_major",
                    ),
                ],
            )
        )

    # =========================================================================
    # NPC TABLES
    # =========================================================================

    def _register_npc_tables(self) -> None:
        """Register NPC generation tables."""

        self.manager.register_table(
            DolmenwoodTable(
                table_id="npc_demeanor",
                name="NPC Demeanor",
                category=TableCategory.NPC_TRAIT,
                die_type=DieType.D10,
                description="NPC's current mood/demeanor",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Friendly and talkative"),
                    TableEntry(roll_min=2, roll_max=2, result="Suspicious and curt"),
                    TableEntry(roll_min=3, roll_max=3, result="Nervous and jumpy"),
                    TableEntry(roll_min=4, roll_max=4, result="Drunk or addled"),
                    TableEntry(roll_min=5, roll_max=5, result="Busy and distracted"),
                    TableEntry(roll_min=6, roll_max=6, result="Bored and listless"),
                    TableEntry(roll_min=7, roll_max=7, result="Angry about something"),
                    TableEntry(roll_min=8, roll_max=8, result="Secretive and evasive"),
                    TableEntry(roll_min=9, roll_max=9, result="Helpful and eager"),
                    TableEntry(roll_min=10, roll_max=10, result="Haughty and dismissive"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="npc_quirk",
                name="NPC Quirk",
                category=TableCategory.NPC_TRAIT,
                die_type=DieType.D20,
                description="Distinctive quirk or habit",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Constantly sniffs or clears throat"),
                    TableEntry(roll_min=2, roll_max=2, result="Speaks in rhyme when nervous"),
                    TableEntry(roll_min=3, roll_max=3, result="Collects something unusual"),
                    TableEntry(roll_min=4, roll_max=4, result="Refuses to make eye contact"),
                    TableEntry(roll_min=5, roll_max=5, result="Always eating or chewing something"),
                    TableEntry(roll_min=6, roll_max=6, result="Excessive hand gestures"),
                    TableEntry(roll_min=7, roll_max=7, result="Speaks very slowly or quickly"),
                    TableEntry(roll_min=8, roll_max=8, result="Laughs at inappropriate times"),
                    TableEntry(roll_min=9, roll_max=9, result="Obsessed with cleanliness"),
                    TableEntry(roll_min=10, roll_max=10, result="Superstitious (won't do X)"),
                    TableEntry(roll_min=11, roll_max=11, result="Hums or whistles constantly"),
                    TableEntry(roll_min=12, roll_max=12, result="Exaggerates everything"),
                    TableEntry(roll_min=13, roll_max=13, result="Fidgets with a specific object"),
                    TableEntry(roll_min=14, roll_max=14, result="Unusual speech pattern or accent"),
                    TableEntry(roll_min=15, roll_max=15, result="Always complaining"),
                    TableEntry(roll_min=16, roll_max=16, result="Paranoid about specific thing"),
                    TableEntry(roll_min=17, roll_max=17, result="Overly formal or informal"),
                    TableEntry(roll_min=18, roll_max=18, result="Tells long, rambling stories"),
                    TableEntry(roll_min=19, roll_max=19, result="Has an imaginary friend"),
                    TableEntry(roll_min=20, roll_max=20, result="Knows an unusual fact about PCs"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="npc_secret",
                name="NPC Secret",
                category=TableCategory.NPC_TRAIT,
                die_type=DieType.D8,
                description="Hidden secret the NPC has",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Secretly works for a faction"),
                    TableEntry(roll_min=2, roll_max=2, result="Witnessed a crime"),
                    TableEntry(roll_min=3, roll_max=3, result="Has forbidden knowledge"),
                    TableEntry(roll_min=4, roll_max=4, result="Is not who they claim to be"),
                    TableEntry(roll_min=5, roll_max=5, result="Owes a debt to dangerous people"),
                    TableEntry(roll_min=6, roll_max=6, result="Has fairy blood or connection"),
                    TableEntry(roll_min=7, roll_max=7, result="Knows the location of treasure"),
                    TableEntry(roll_min=8, roll_max=8, result="Is cursed or blessed"),
                ],
            )
        )

    # =========================================================================
    # RUMOR TABLES
    # =========================================================================

    def _register_rumor_tables(self) -> None:
        """Register rumor generation tables."""

        self.manager.register_table(
            DolmenwoodTable(
                table_id="rumor_type",
                name="Rumor Type",
                category=TableCategory.RUMOR_GENERIC,
                die_type=DieType.D6,
                description="Type of rumor heard",
                entries=[
                    TableEntry(roll_min=1, roll_max=2, result="True and useful"),
                    TableEntry(roll_min=3, roll_max=3, result="True but misleading context"),
                    TableEntry(roll_min=4, roll_max=4, result="Partly true, partly false"),
                    TableEntry(roll_min=5, roll_max=5, result="False but believed"),
                    TableEntry(roll_min=6, roll_max=6, result="Completely false/trap"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="rumor_topic_generic",
                name="Rumor Topic",
                category=TableCategory.RUMOR_GENERIC,
                die_type=DieType.D10,
                description="What the rumor is about",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Treasure hidden in nearby location"),
                    TableEntry(roll_min=2, roll_max=2, result="Monster sightings"),
                    TableEntry(roll_min=3, roll_max=3, result="Political intrigue"),
                    TableEntry(roll_min=4, roll_max=4, result="Supernatural occurrence"),
                    TableEntry(roll_min=5, roll_max=5, result="Missing persons"),
                    TableEntry(roll_min=6, roll_max=6, result="New arrival in area"),
                    TableEntry(roll_min=7, roll_max=7, result="Ancient history/legend"),
                    TableEntry(roll_min=8, roll_max=8, result="Local scandal"),
                    TableEntry(roll_min=9, roll_max=9, result="Trade/economic news"),
                    TableEntry(roll_min=10, roll_max=10, result="Warning about danger"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="rumor_monster",
                name="Monster Rumor",
                category=TableCategory.RUMOR_MONSTER,
                die_type=DieType.D8,
                description="Rumor about a specific monster type",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Location of lair"),
                    TableEntry(roll_min=2, roll_max=2, result="Weakness or vulnerability"),
                    TableEntry(roll_min=3, roll_max=3, result="Treasure it guards"),
                    TableEntry(roll_min=4, roll_max=4, result="Recent victims"),
                    TableEntry(roll_min=5, roll_max=5, result="Unusual behavior"),
                    TableEntry(roll_min=6, roll_max=6, result="Origin or history"),
                    TableEntry(roll_min=7, roll_max=7, result="How to appease/bargain with it"),
                    TableEntry(roll_min=8, roll_max=8, result="False information (danger!)"),
                ],
            )
        )

    # =========================================================================
    # FLAVOR TABLES
    # =========================================================================

    def _register_flavor_tables(self) -> None:
        """Register atmospheric/flavor tables."""

        self.manager.register_table(
            DolmenwoodTable(
                table_id="forest_ambiance",
                name="Forest Ambiance",
                category=TableCategory.FLAVOR,
                die_type=DieType.D10,
                description="Atmospheric details in forest",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Distant howling wolves"),
                    TableEntry(roll_min=2, roll_max=2, result="Eerie silence, no birdsong"),
                    TableEntry(roll_min=3, roll_max=3, result="Thick mist between the trees"),
                    TableEntry(roll_min=4, roll_max=4, result="Strange lights in the distance"),
                    TableEntry(roll_min=5, roll_max=5, result="The smell of decay"),
                    TableEntry(roll_min=6, roll_max=6, result="Trees seem to be watching"),
                    TableEntry(roll_min=7, roll_max=7, result="Sound of distant music"),
                    TableEntry(roll_min=8, roll_max=8, result="Unusual mushrooms everywhere"),
                    TableEntry(roll_min=9, roll_max=9, result="Animal bones scattered about"),
                    TableEntry(
                        roll_min=10,
                        roll_max=10,
                        result="Everything seems too perfect, too peaceful",
                    ),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="dolmenwood_omen",
                name="Dolmenwood Omen",
                category=TableCategory.FLAVOR,
                die_type=DieType.D12,
                description="Strange omen or portent",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="A crow speaks a single word"),
                    TableEntry(roll_min=2, roll_max=2, result="Frost forms in an unusual pattern"),
                    TableEntry(roll_min=3, roll_max=3, result="A bell tolls from nowhere"),
                    TableEntry(roll_min=4, roll_max=4, result="Your shadow moves independently"),
                    TableEntry(roll_min=5, roll_max=5, result="Animals flee in one direction"),
                    TableEntry(roll_min=6, roll_max=6, result="A standing stone hums"),
                    TableEntry(roll_min=7, roll_max=7, result="Blood-red moon rises"),
                    TableEntry(roll_min=8, roll_max=8, result="A child's laughter echoes"),
                    TableEntry(roll_min=9, roll_max=9, result="Flowers bloom out of season"),
                    TableEntry(roll_min=10, roll_max=10, result="All fires burn blue"),
                    TableEntry(roll_min=11, roll_max=11, result="A path appears that wasn't there"),
                    TableEntry(roll_min=12, roll_max=12, result="Time seems to skip"),
                ],
            )
        )

    # =========================================================================
    # DUNGEON TABLES
    # =========================================================================

    def _register_dungeon_tables(self) -> None:
        """Register dungeon exploration tables."""

        self.manager.register_table(
            DolmenwoodTable(
                table_id="dungeon_room_contents",
                name="Room Contents",
                category=TableCategory.DUNGEON_ROOM,
                die_type=DieType.D6,
                description="What is in a dungeon room",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Monster with treasure"),
                    TableEntry(roll_min=2, roll_max=2, result="Monster, no treasure"),
                    TableEntry(roll_min=3, roll_max=3, result="Trap"),
                    TableEntry(roll_min=4, roll_max=4, result="Special feature"),
                    TableEntry(roll_min=5, roll_max=6, result="Empty"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="dungeon_door_type",
                name="Door Type",
                category=TableCategory.DUNGEON_FEATURE,
                die_type=DieType.D6,
                description="Type of door encountered",
                entries=[
                    TableEntry(roll_min=1, roll_max=3, result="Wooden door (normal)"),
                    TableEntry(roll_min=4, roll_max=4, result="Stuck door (force required)"),
                    TableEntry(roll_min=5, roll_max=5, result="Locked door"),
                    TableEntry(roll_min=6, roll_max=6, result="Secret door"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="dungeon_trap_type",
                name="Trap Type",
                category=TableCategory.DUNGEON_TRAP,
                die_type=DieType.D8,
                description="Type of trap",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Pit trap (1d6 damage)"),
                    TableEntry(roll_min=2, roll_max=2, result="Arrow trap (1d6 damage)"),
                    TableEntry(roll_min=3, roll_max=3, result="Poison needle (save or 1d6 damage)"),
                    TableEntry(roll_min=4, roll_max=4, result="Scything blade (2d6 damage)"),
                    TableEntry(roll_min=5, roll_max=5, result="Falling block (2d6 damage)"),
                    TableEntry(roll_min=6, roll_max=6, result="Gas trap (save or sleep)"),
                    TableEntry(roll_min=7, roll_max=7, result="Alarm (alerts monsters)"),
                    TableEntry(roll_min=8, roll_max=8, result="Magic trap (roll effect)"),
                ],
            )
        )

        self.manager.register_table(
            DolmenwoodTable(
                table_id="dungeon_special_feature",
                name="Special Feature",
                category=TableCategory.DUNGEON_FEATURE,
                die_type=DieType.D10,
                description="Special dungeon feature",
                entries=[
                    TableEntry(roll_min=1, roll_max=1, result="Altar or shrine"),
                    TableEntry(roll_min=2, roll_max=2, result="Pool of water (magical?)"),
                    TableEntry(roll_min=3, roll_max=3, result="Statue with inscription"),
                    TableEntry(roll_min=4, roll_max=4, result="Unusual architecture"),
                    TableEntry(roll_min=5, roll_max=5, result="Evidence of past battle"),
                    TableEntry(roll_min=6, roll_max=6, result="Strange sounds/smells"),
                    TableEntry(roll_min=7, roll_max=7, result="Hidden compartment"),
                    TableEntry(roll_min=8, roll_max=8, result="Magical effect zone"),
                    TableEntry(roll_min=9, roll_max=9, result="NPC prisoner or corpse"),
                    TableEntry(roll_min=10, roll_max=10, result="Portal or gateway"),
                ],
            )
        )

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def roll_encounter(
        self, terrain: str, hex_id: Optional[str] = None, context: Optional[TableContext] = None
    ) -> TableResult:
        """
        Roll for a wilderness encounter appropriate to the terrain.

        Args:
            terrain: Terrain type (forest, bog, road, etc.)
            hex_id: Optional hex ID for hex-specific tables
            context: Optional context for modifiers

        Returns:
            TableResult with encounter details
        """
        # Check for hex-specific table first
        if hex_id:
            hex_tables = self.manager.get_hex_tables(hex_id)
            for name, table in hex_tables.items():
                if "encounter" in name.lower():
                    return self.manager.roll_table(table.table_id, context)

        # Fall back to terrain-based table
        table_id = f"encounter_{terrain.lower()}"
        if self.manager.get_table(table_id):
            return self.manager.roll_table(table_id, context)

        # Default to forest encounters
        return self.manager.roll_table("encounter_forest", context)

    def roll_treasure(
        self, treasure_type: str = "standard", context: Optional[TableContext] = None
    ) -> TableResult:
        """Roll for treasure."""
        table_id = f"treasure_type_{treasure_type}"
        return self.manager.roll_table(table_id, context)

    def roll_npc_traits(self) -> dict[str, TableResult]:
        """Roll a complete set of NPC traits."""
        return {
            "demeanor": self.manager.roll_table("npc_demeanor"),
            "quirk": self.manager.roll_table("npc_quirk"),
            "secret": self.manager.roll_table("npc_secret"),
        }

    def roll_rumor(self, rumor_category: str = "generic") -> tuple[TableResult, TableResult]:
        """
        Roll for a rumor.

        Returns:
            Tuple of (rumor_type, rumor_topic)
        """
        rumor_type = self.manager.roll_table("rumor_type")

        topic_table = f"rumor_topic_{rumor_category}"
        if not self.manager.get_table(topic_table):
            topic_table = "rumor_topic_generic"

        rumor_topic = self.manager.roll_table(topic_table)
        return rumor_type, rumor_topic

    def roll_weather(self, season: str) -> TableResult:
        """Roll weather for the given season."""
        return self.manager.roll_table(f"weather_{season.lower()}")

    def roll_character_aspects(self) -> dict[str, TableResult]:
        """Roll a complete set of character aspects."""
        return {
            "hair_color": self.manager.roll_table("character_hair_color"),
            "eye_color": self.manager.roll_table("character_eye_color"),
            "distinguishing_feature": self.manager.roll_table("character_distinguishing_feature"),
            "background": self.manager.roll_table("character_background"),
            "personality": self.manager.roll_table("character_personality_trait"),
            "motivation": self.manager.roll_table("character_motivation"),
        }


# Global instance
_dolmenwood_tables: Optional[DolmenwoodTables] = None


def get_dolmenwood_tables() -> DolmenwoodTables:
    """Get the global DolmenwoodTables instance."""
    global _dolmenwood_tables
    if _dolmenwood_tables is None:
        _dolmenwood_tables = DolmenwoodTables()
    return _dolmenwood_tables
