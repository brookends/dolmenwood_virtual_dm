"""
Encounter tables for Dolmenwood.

Provides comprehensive encounter table management including:
- Common encounter type and encounter tables
- Regional encounter tables
- Settlement encounter tables (day/night variants)
- Fairy Road encounter tables
- Unseason encounter tables (Chame, Vague)
- Integration with hex-specific encounter tables
"""

from typing import Optional
import random

from src.tables.table_types import (
    DieType,
    EncounterLocationType,
    EncounterTimeOfDay,
    EncounterSeason,
    EncounterResultType,
    DolmenwoodRegion,
    DolmenwoodSettlement,
    EncounterTableContext,
    EncounterEntry,
    EncounterTable,
    EncounterResult,
    TableCategory,
)


class EncounterTableManager:
    """
    Manages all encounter tables for Dolmenwood.

    Handles the hierarchical encounter table system:
    1. Check for hex-specific encounters (from hex data)
    2. Check for settlement encounters (if in settlement)
    3. Check for fairy road encounters (if on fairy road)
    4. Check for unseason encounters (if during unseason)
    5. Check for regional encounters
    6. Fall back to common encounters
    """

    def __init__(self):
        # All registered encounter tables
        self._tables: dict[str, EncounterTable] = {}

        # Indexes for quick lookup
        self._by_settlement: dict[DolmenwoodSettlement, dict[EncounterTimeOfDay, str]] = {}
        self._by_region: dict[DolmenwoodRegion, str] = {}
        self._by_season: dict[EncounterSeason, str] = {}
        self._fairy_road_table: Optional[str] = None
        self._common_type_table: Optional[str] = None
        self._common_encounter_table: Optional[str] = None

        # Register all tables
        self._register_all_tables()

    def _register_all_tables(self) -> None:
        """Register all encounter tables."""
        self._register_common_tables()
        self._register_regional_tables()
        self._register_settlement_tables()
        self._register_fairy_road_tables()
        self._register_unseason_tables()

    # =========================================================================
    # TABLE REGISTRATION
    # =========================================================================

    def register_table(self, table: EncounterTable) -> None:
        """Register an encounter table."""
        self._tables[table.table_id] = table

        # Index by settlement
        if table.settlement is not None:
            if table.settlement not in self._by_settlement:
                self._by_settlement[table.settlement] = {}
            self._by_settlement[table.settlement][table.time_of_day] = table.table_id

        # Index by region
        if table.region is not None and table.location_type == EncounterLocationType.REGIONAL:
            self._by_region[table.region] = table.table_id

        # Index by season (for unseasons)
        if table.season in [EncounterSeason.CHAME, EncounterSeason.VAGUE]:
            self._by_season[table.season] = table.table_id

    def get_table(self, table_id: str) -> Optional[EncounterTable]:
        """Get a table by ID."""
        return self._tables.get(table_id)

    # =========================================================================
    # ENCOUNTER RESOLUTION
    # =========================================================================

    def roll_encounter(
        self,
        context: EncounterTableContext,
        hex_tables: Optional[dict[str, EncounterTable]] = None
    ) -> Optional[EncounterResult]:
        """
        Roll for an encounter based on context.

        Follows the hierarchical system to select the appropriate table.

        Args:
            context: Current encounter context
            hex_tables: Optional hex-specific tables (from hex data)

        Returns:
            EncounterResult or None if no table matches
        """
        table = self._select_table(context, hex_tables)
        if table is None:
            return None

        roll, entry = table.roll()

        # Roll number appearing if specified
        num_appearing = None
        if entry.number_appearing:
            num_appearing = self._roll_dice(entry.number_appearing)

        result = EncounterResult(
            table_id=table.table_id,
            table_name=table.name,
            roll=roll,
            entry=entry,
            location_type=context.location_type,
            time_of_day=context.time_of_day,
            season=context.season,
            description=entry.result,
            monsters=entry.monster_refs.copy(),
            npcs=entry.npc_refs.copy(),
            number_appearing_rolled=num_appearing,
        )

        # Handle sub-table rolls (e.g., regional table reference)
        if entry.regional_table and context.region:
            regional_result = self._roll_regional(context)
            if regional_result:
                result.sub_result = regional_result

        elif entry.sub_table:
            sub_table = self._tables.get(entry.sub_table)
            if sub_table:
                sub_roll, sub_entry = sub_table.roll()
                result.sub_result = EncounterResult(
                    table_id=sub_table.table_id,
                    table_name=sub_table.name,
                    roll=sub_roll,
                    entry=sub_entry,
                    location_type=context.location_type,
                    time_of_day=context.time_of_day,
                    season=context.season,
                    description=sub_entry.result,
                )

        return result

    def _select_table(
        self,
        context: EncounterTableContext,
        hex_tables: Optional[dict[str, EncounterTable]] = None
    ) -> Optional[EncounterTable]:
        """Select the appropriate encounter table based on context."""
        # 1. Check hex-specific tables first
        if hex_tables and context.hex_id:
            for table in hex_tables.values():
                if table.matches_context(context):
                    return table

        # 2. Check settlement tables
        if context.settlement:
            settlement_tables = self._by_settlement.get(context.settlement, {})
            # Try specific time first
            if context.time_of_day in settlement_tables:
                return self._tables.get(settlement_tables[context.time_of_day])
            # Try day/night based on current time
            if context.time_of_day in [EncounterTimeOfDay.DAY, EncounterTimeOfDay.DAWN]:
                if EncounterTimeOfDay.DAY in settlement_tables:
                    return self._tables.get(settlement_tables[EncounterTimeOfDay.DAY])
            elif context.time_of_day in [EncounterTimeOfDay.NIGHT, EncounterTimeOfDay.DUSK]:
                if EncounterTimeOfDay.NIGHT in settlement_tables:
                    return self._tables.get(settlement_tables[EncounterTimeOfDay.NIGHT])

        # 3. Check fairy road
        if context.on_fairy_road and self._fairy_road_table:
            return self._tables.get(self._fairy_road_table)

        # 4. Check unseason tables
        if context.is_unseason and context.season in self._by_season:
            return self._tables.get(self._by_season[context.season])

        # 5. Check regional tables
        if context.region and context.region in self._by_region:
            return self._tables.get(self._by_region[context.region])

        # 6. Fall back to common encounter table
        if self._common_encounter_table:
            return self._tables.get(self._common_encounter_table)

        return None

    def _roll_regional(self, context: EncounterTableContext) -> Optional[EncounterResult]:
        """Roll on the regional table for the current context."""
        if context.region and context.region in self._by_region:
            table = self._tables.get(self._by_region[context.region])
            if table:
                roll, entry = table.roll()
                return EncounterResult(
                    table_id=table.table_id,
                    table_name=table.name,
                    roll=roll,
                    entry=entry,
                    location_type=context.location_type,
                    time_of_day=context.time_of_day,
                    season=context.season,
                    description=entry.result,
                )
        return None

    def _roll_dice(self, notation: str) -> int:
        """Roll dice using standard notation."""
        # Handle plain numbers (e.g., "1" or "5")
        if 'd' not in notation.lower():
            return int(notation)

        modifier = 0
        if '+' in notation:
            dice_part, mod_part = notation.split('+')
            modifier = int(mod_part)
        elif '-' in notation:
            dice_part, mod_part = notation.split('-')
            modifier = -int(mod_part)
        else:
            dice_part = notation

        num_dice, die_size = dice_part.lower().split('d')
        num_dice = int(num_dice) if num_dice else 1
        die_size = int(die_size)

        return sum(random.randint(1, die_size) for _ in range(num_dice)) + modifier

    # =========================================================================
    # COMMON ENCOUNTER TABLES (Campaign Book p.114)
    # =========================================================================

    def _register_common_tables(self) -> None:
        """Register common encounter type and encounter tables."""
        # Common Encounter Type Table (p.114)
        common_type = EncounterTable(
            table_id="common_encounter_type",
            name="Common Encounter Type",
            location_type=EncounterLocationType.WILDERNESS,
            die_type=DieType.D6,
            source_reference="Campaign Book",
            page_number=114,
            entries=[
                EncounterEntry(roll_min=1, roll_max=2, result="Monster",
                               result_type=EncounterResultType.MONSTER,
                               sub_table="common_encounters"),
                EncounterEntry(roll_min=3, roll_max=3, result="Lair",
                               result_type=EncounterResultType.LAIR, is_lair=True),
                EncounterEntry(roll_min=4, roll_max=4, result="Spoor",
                               result_type=EncounterResultType.SPOOR),
                EncounterEntry(roll_min=5, roll_max=5, result="Tracks",
                               result_type=EncounterResultType.SPOOR),
                EncounterEntry(roll_min=6, roll_max=6, result="Traces",
                               result_type=EncounterResultType.SPOOR),
            ]
        )
        self.register_table(common_type)
        self._common_type_table = common_type.table_id

        # Common Encounters Table (p.114)
        common_enc = EncounterTable(
            table_id="common_encounters",
            name="Common Encounters",
            location_type=EncounterLocationType.WILDERNESS,
            die_type=DieType.D12,
            source_reference="Campaign Book",
            page_number=114,
            entries=[
                EncounterEntry(roll_min=1, roll_max=1, result="Bandit",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["bandit"], number_appearing="2d6"),
                EncounterEntry(roll_min=2, roll_max=2, result="Bear, Black",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["bear_black"], number_appearing="1d2"),
                EncounterEntry(roll_min=3, roll_max=3, result="Boar, Wild",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["boar_wild"], number_appearing="1d6"),
                EncounterEntry(roll_min=4, roll_max=4, result="Deer",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["deer"], number_appearing="2d6"),
                EncounterEntry(roll_min=5, roll_max=5, result="Goatfolk",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["goatfolk"], number_appearing="2d4"),
                EncounterEntry(roll_min=6, roll_max=6, result="Outlaw",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["outlaw"], number_appearing="2d6"),
                EncounterEntry(roll_min=7, roll_max=7, result="Regional Encounter",
                               result_type=EncounterResultType.SPECIAL,
                               regional_table=True),
                EncounterEntry(roll_min=8, roll_max=8, result="Snake, Giant",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["snake_giant"], number_appearing="1d3"),
                EncounterEntry(roll_min=9, roll_max=9, result="Spider, Giant",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["spider_giant"], number_appearing="1d4"),
                EncounterEntry(roll_min=10, roll_max=10, result="Traveller",
                               result_type=EncounterResultType.NPC,
                               sub_table="traveller_type"),
                EncounterEntry(roll_min=11, roll_max=11, result="Wolf",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["wolf"], number_appearing="2d6"),
                EncounterEntry(roll_min=12, roll_max=12, result="Woodwose",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["woodwose"], number_appearing="1d6"),
            ]
        )
        self.register_table(common_enc)
        self._common_encounter_table = common_enc.table_id

    # =========================================================================
    # REGIONAL ENCOUNTER TABLES (Campaign Book p.115)
    # =========================================================================

    def _register_regional_tables(self) -> None:
        """Register regional encounter tables."""
        # Define regional encounters - placeholder data
        regions_data = {
            DolmenwoodRegion.NORTHERN_SCRATCH: [
                ("Bog Body", "bog_body", "1d3"),
                ("Drune", "drune", "1d4"),
                ("Giant, Bog", "giant_bog", "1"),
                ("Moss Dwarf", "moss_dwarf", "2d4"),
                ("Troll, Moss", "troll_moss", "1"),
                ("Will-o'-Wisp", "will_o_wisp", "1d3"),
            ],
            DolmenwoodRegion.LAKE_LONGMERE: [
                ("Fisherman", "npc_fisherman", "1d4"),
                ("Giant Frog", "giant_frog", "1d6"),
                ("Lake Spirit", "lake_spirit", "1"),
                ("Nixie", "nixie", "2d4"),
                ("River Drake", "river_drake", "1d2"),
                ("Swan, Giant", "swan_giant", "1d3"),
            ],
            DolmenwoodRegion.ALDWEALD: [
                ("Elf", "elf", "1d4"),
                ("Fairy, Petty", "fairy_petty", "2d6"),
                ("Grimalkin", "grimalkin", "1d3"),
                ("Unicorn", "unicorn", "1"),
                ("Wood Elf Patrol", "wood_elf", "1d6+2"),
                ("Treant", "treant", "1"),
            ],
            DolmenwoodRegion.TITHELANDS: [
                ("Farmer", "npc_farmer", "1d6"),
                ("Knight", "knight", "1d3"),
                ("Merchant Caravan", "npc_merchant", "2d4"),
                ("Pilgrim", "npc_pilgrim", "2d6"),
                ("Tax Collector", "npc_tax_collector", "1d4"),
                ("Village Militia", "militia", "2d6"),
            ],
            DolmenwoodRegion.HIGH_WOLD: [
                ("Centaur", "centaur", "1d6"),
                ("Giant Eagle", "eagle_giant", "1d2"),
                ("Goatfolk", "goatfolk", "2d4"),
                ("Harpy", "harpy", "1d4"),
                ("Hill Giant", "giant_hill", "1"),
                ("Wyvern", "wyvern", "1"),
            ],
            DolmenwoodRegion.FEVER_MARSH: [
                ("Crocodile, Giant", "crocodile_giant", "1d3"),
                ("Ghoul", "ghoul", "1d6"),
                ("Lizardfolk", "lizardfolk", "2d4"),
                ("Plague Spirit", "plague_spirit", "1"),
                ("Shambling Mound", "shambling_mound", "1"),
                ("Zombie", "zombie", "2d6"),
            ],
        }

        for region, encounters in regions_data.items():
            entries = []
            for i, (name, ref, num) in enumerate(encounters):
                entries.append(EncounterEntry(
                    roll_min=i+1, roll_max=i+1,
                    result=name,
                    result_type=EncounterResultType.MONSTER,
                    monster_refs=[ref],
                    number_appearing=num
                ))

            table = EncounterTable(
                table_id=f"regional_{region.value}",
                name=f"Regional Encounters: {region.value.replace('_', ' ').title()}",
                location_type=EncounterLocationType.REGIONAL,
                region=region,
                die_type=DieType.D6,
                source_reference="Campaign Book",
                page_number=115,
                entries=entries
            )
            self.register_table(table)

    # =========================================================================
    # SETTLEMENT ENCOUNTER TABLES (Campaign Book various pages)
    # =========================================================================

    def _register_settlement_tables(self) -> None:
        """Register settlement encounter tables (day and night variants)."""
        settlements_data = {
            DolmenwoodSettlement.BLACKESWELL: {
                "page": 125,
                "day": [
                    ("Merchant", EncounterResultType.NPC),
                    ("Town Guard", EncounterResultType.PATROL),
                    ("Local Farmer", EncounterResultType.NPC),
                    ("Traveling Performer", EncounterResultType.NPC),
                    ("Priest of the One True God", EncounterResultType.NPC),
                    ("Suspicious Stranger", EncounterResultType.NPC),
                ],
                "night": [
                    ("Town Watch", EncounterResultType.PATROL),
                    ("Drunk Reveler", EncounterResultType.NPC),
                    ("Thief", EncounterResultType.NPC),
                    ("Secret Cult Meeting", EncounterResultType.EVENT),
                    ("Wandering Ghost", EncounterResultType.MONSTER),
                    ("Mysterious Figure", EncounterResultType.NPC),
                ],
            },
            DolmenwoodSettlement.CASTLE_BRACKENWOLD: {
                "page": 129,
                "day": [
                    ("Noble's Entourage", EncounterResultType.NPC),
                    ("City Guard Patrol", EncounterResultType.PATROL),
                    ("Merchant with Goods", EncounterResultType.MERCHANT),
                    ("Beggar", EncounterResultType.NPC),
                    ("Street Performer", EncounterResultType.NPC),
                    ("Courier", EncounterResultType.NPC),
                ],
                "night": [
                    ("Night Watch", EncounterResultType.PATROL),
                    ("Footpad", EncounterResultType.NPC),
                    ("Secret Assignation", EncounterResultType.EVENT),
                    ("Drunken Noble", EncounterResultType.NPC),
                    ("Cloaked Figure", EncounterResultType.NPC),
                    ("Rats, Giant", EncounterResultType.MONSTER),
                ],
            },
            DolmenwoodSettlement.PRIGWORT: {
                "page": 175,
                "day": [
                    ("Herbalist", EncounterResultType.NPC),
                    ("Witch Hunter", EncounterResultType.NPC),
                    ("Village Elder", EncounterResultType.NPC),
                    ("Traveling Peddler", EncounterResultType.MERCHANT),
                    ("Suspicious Goat", EncounterResultType.MONSTER),
                    ("Moss Dwarf Trader", EncounterResultType.NPC),
                ],
                "night": [
                    ("Village Watch", EncounterResultType.PATROL),
                    ("Grimalkin Prowler", EncounterResultType.MONSTER),
                    ("Fairy Light", EncounterResultType.FAIRY),
                    ("Drunken Local", EncounterResultType.NPC),
                    ("Mysterious Fog", EncounterResultType.ENVIRONMENTAL),
                    ("Nocturnal Ritual", EncounterResultType.EVENT),
                ],
            },
            DolmenwoodSettlement.LANKSHORN: {
                "page": 157,
                "day": [
                    ("Fisher", EncounterResultType.NPC),
                    ("Boat Builder", EncounterResultType.NPC),
                    ("Traveling Merchant", EncounterResultType.MERCHANT),
                    ("Duke's Patrol", EncounterResultType.PATROL),
                    ("Pilgrim", EncounterResultType.PILGRIM),
                    ("Local Guide", EncounterResultType.NPC),
                ],
                "night": [
                    ("Harbor Watch", EncounterResultType.PATROL),
                    ("Smuggler", EncounterResultType.NPC),
                    ("Drunken Sailor", EncounterResultType.NPC),
                    ("River Spirit", EncounterResultType.MONSTER),
                    ("Secret Meeting", EncounterResultType.EVENT),
                    ("Fog Bank", EncounterResultType.ENVIRONMENTAL),
                ],
            },
        }

        # Add remaining settlements with generic placeholder data
        remaining_settlements = [
            (DolmenwoodSettlement.COBTON, 137),
            (DolmenwoodSettlement.DREG, 141),
            (DolmenwoodSettlement.FORT_VULGAR, 147),
            (DolmenwoodSettlement.HIGH_HANKLE, 151),
            (DolmenwoodSettlement.MEAGRES_REACH, 163),
            (DolmenwoodSettlement.ODD, 167),
            (DolmenwoodSettlement.ORBSWALLOW, 171),
            (DolmenwoodSettlement.WOODCUTTERS_ENCAMPMENT, 183),
        ]

        for settlement, page in remaining_settlements:
            settlements_data[settlement] = {
                "page": page,
                "day": [
                    ("Local Resident", EncounterResultType.NPC),
                    ("Merchant", EncounterResultType.MERCHANT),
                    ("Guard Patrol", EncounterResultType.PATROL),
                    ("Traveler", EncounterResultType.NPC),
                    ("Worker", EncounterResultType.NPC),
                    ("Local Event", EncounterResultType.EVENT),
                ],
                "night": [
                    ("Night Watch", EncounterResultType.PATROL),
                    ("Local Drunk", EncounterResultType.NPC),
                    ("Suspicious Figure", EncounterResultType.NPC),
                    ("Stray Animal", EncounterResultType.MONSTER),
                    ("Strange Sound", EncounterResultType.EVENT),
                    ("Quiet Night", EncounterResultType.SPECIAL),
                ],
            }

        # Register all settlement tables
        for settlement, data in settlements_data.items():
            page = data["page"]

            # Day table
            day_entries = []
            for i, (name, result_type) in enumerate(data["day"]):
                day_entries.append(EncounterEntry(
                    roll_min=i+1, roll_max=i+1,
                    result=name,
                    result_type=result_type
                ))

            day_table = EncounterTable(
                table_id=f"settlement_{settlement.value}_day",
                name=f"{settlement.value.replace('_', ' ').title()} Day Encounters",
                location_type=EncounterLocationType.SETTLEMENT,
                settlement=settlement,
                time_of_day=EncounterTimeOfDay.DAY,
                die_type=DieType.D6,
                source_reference="Campaign Book",
                page_number=page,
                entries=day_entries
            )
            self.register_table(day_table)

            # Night table
            night_entries = []
            for i, (name, result_type) in enumerate(data["night"]):
                night_entries.append(EncounterEntry(
                    roll_min=i+1, roll_max=i+1,
                    result=name,
                    result_type=result_type
                ))

            night_table = EncounterTable(
                table_id=f"settlement_{settlement.value}_night",
                name=f"{settlement.value.replace('_', ' ').title()} Night Encounters",
                location_type=EncounterLocationType.SETTLEMENT,
                settlement=settlement,
                time_of_day=EncounterTimeOfDay.NIGHT,
                die_type=DieType.D6,
                source_reference="Campaign Book",
                page_number=page,
                entries=night_entries
            )
            self.register_table(night_table)

    # =========================================================================
    # FAIRY ROAD ENCOUNTER TABLES (Campaign Book p.26)
    # =========================================================================

    def _register_fairy_road_tables(self) -> None:
        """Register Fairy Road encounter tables."""
        fairy_road = EncounterTable(
            table_id="fairy_road_encounters",
            name="Fairy Road Encounters",
            location_type=EncounterLocationType.FAIRY_ROAD,
            die_type=DieType.D12,
            source_reference="Campaign Book",
            page_number=26,
            entries=[
                EncounterEntry(roll_min=1, roll_max=1, result="Elf Procession",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["elf_noble"], number_appearing="2d6",
                               activity="Traveling to the Cold Prince's court"),
                EncounterEntry(roll_min=2, roll_max=2, result="Fairy Ring",
                               result_type=EncounterResultType.FAIRY,
                               is_special=True),
                EncounterEntry(roll_min=3, roll_max=3, result="Grimalkin Scout",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["grimalkin"], number_appearing="1d3"),
                EncounterEntry(roll_min=4, roll_max=4, result="Lost Traveler",
                               result_type=EncounterResultType.NPC,
                               activity="Confused and disoriented"),
                EncounterEntry(roll_min=5, roll_max=5, result="Petty Fairy Swarm",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["fairy_petty"], number_appearing="3d6"),
                EncounterEntry(roll_min=6, roll_max=6, result="Redcap",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["redcap"], number_appearing="1d3"),
                EncounterEntry(roll_min=7, roll_max=7, result="Seelie Noble",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["seelie_noble"], number_appearing="1",
                               disposition="Aloof and curious"),
                EncounterEntry(roll_min=8, roll_max=8, result="Time Slip",
                               result_type=EncounterResultType.SPECIAL,
                               is_special=True),
                EncounterEntry(roll_min=9, roll_max=9, result="Unseelie Hunters",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["unseelie_hunter"], number_appearing="1d4+1"),
                EncounterEntry(roll_min=10, roll_max=10, result="Will-o'-Wisp",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["will_o_wisp"], number_appearing="1d3"),
                EncounterEntry(roll_min=11, roll_max=11, result="Woodwose Band",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["woodwose"], number_appearing="2d4"),
                EncounterEntry(roll_min=12, roll_max=12, result="Road Shifts",
                               result_type=EncounterResultType.SPECIAL,
                               is_special=True,
                               activity="The path behind you has changed"),
            ]
        )
        self.register_table(fairy_road)
        self._fairy_road_table = fairy_road.table_id

    # =========================================================================
    # UNSEASON ENCOUNTER TABLES (Campaign Book p.111)
    # =========================================================================

    def _register_unseason_tables(self) -> None:
        """Register Unseason encounter tables (Chame and Vague)."""
        # Unseason of Chame encounters
        chame = EncounterTable(
            table_id="unseason_chame",
            name="Encounters During the Unseason of Chame",
            location_type=EncounterLocationType.WILDERNESS,
            season=EncounterSeason.CHAME,
            die_type=DieType.D8,
            source_reference="Campaign Book",
            page_number=111,
            entries=[
                EncounterEntry(roll_min=1, roll_max=1, result="Frost Fairy",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["frost_fairy"], number_appearing="1d6"),
                EncounterEntry(roll_min=2, roll_max=2, result="Ice Troll",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["troll_ice"], number_appearing="1"),
                EncounterEntry(roll_min=3, roll_max=3, result="Winter Wolf",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["wolf_winter"], number_appearing="1d4"),
                EncounterEntry(roll_min=4, roll_max=4, result="Cold Prince's Herald",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["cold_prince_herald"], number_appearing="1"),
                EncounterEntry(roll_min=5, roll_max=5, result="Frozen Dead",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["frozen_dead"], number_appearing="2d6"),
                EncounterEntry(roll_min=6, roll_max=6, result="Snow Storm",
                               result_type=EncounterResultType.ENVIRONMENTAL,
                               is_special=True),
                EncounterEntry(roll_min=7, roll_max=7, result="Yule Hunters",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["yule_hunter"], number_appearing="1d6"),
                EncounterEntry(roll_min=8, roll_max=8, result="Common Encounter",
                               result_type=EncounterResultType.SPECIAL,
                               sub_table="common_encounters"),
            ]
        )
        self.register_table(chame)

        # Unseason of Vague encounters
        vague = EncounterTable(
            table_id="unseason_vague",
            name="Encounters During the Unseason of Vague",
            location_type=EncounterLocationType.WILDERNESS,
            season=EncounterSeason.VAGUE,
            die_type=DieType.D8,
            source_reference="Campaign Book",
            page_number=111,
            entries=[
                EncounterEntry(roll_min=1, roll_max=1, result="Mist Wraith",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["mist_wraith"], number_appearing="1d3"),
                EncounterEntry(roll_min=2, roll_max=2, result="Lost Soul",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["lost_soul"], number_appearing="1d6"),
                EncounterEntry(roll_min=3, roll_max=3, result="Twilight Fairy",
                               result_type=EncounterResultType.FAIRY,
                               monster_refs=["twilight_fairy"], number_appearing="1d4"),
                EncounterEntry(roll_min=4, roll_max=4, result="Dream Stalker",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["dream_stalker"], number_appearing="1"),
                EncounterEntry(roll_min=5, roll_max=5, result="Wandering Ghost",
                               result_type=EncounterResultType.MONSTER,
                               monster_refs=["ghost"], number_appearing="1"),
                EncounterEntry(roll_min=6, roll_max=6, result="Dense Fog",
                               result_type=EncounterResultType.ENVIRONMENTAL,
                               is_special=True),
                EncounterEntry(roll_min=7, roll_max=7, result="Reality Rift",
                               result_type=EncounterResultType.SPECIAL,
                               is_special=True),
                EncounterEntry(roll_min=8, roll_max=8, result="Common Encounter",
                               result_type=EncounterResultType.SPECIAL,
                               sub_table="common_encounters"),
            ]
        )
        self.register_table(vague)

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_settlement_table(
        self,
        settlement: DolmenwoodSettlement,
        time_of_day: EncounterTimeOfDay
    ) -> Optional[EncounterTable]:
        """Get a specific settlement encounter table."""
        if settlement in self._by_settlement:
            table_id = self._by_settlement[settlement].get(time_of_day)
            if table_id:
                return self._tables.get(table_id)
        return None

    def get_regional_table(self, region: DolmenwoodRegion) -> Optional[EncounterTable]:
        """Get a specific regional encounter table."""
        if region in self._by_region:
            return self._tables.get(self._by_region[region])
        return None

    def list_settlements(self) -> list[DolmenwoodSettlement]:
        """List all settlements with encounter tables."""
        return list(self._by_settlement.keys())

    def list_regions(self) -> list[DolmenwoodRegion]:
        """List all regions with encounter tables."""
        return list(self._by_region.keys())


# Global instance
_encounter_manager: Optional[EncounterTableManager] = None


def get_encounter_table_manager() -> EncounterTableManager:
    """Get the global EncounterTableManager instance."""
    global _encounter_manager
    if _encounter_manager is None:
        _encounter_manager = EncounterTableManager()
    return _encounter_manager
