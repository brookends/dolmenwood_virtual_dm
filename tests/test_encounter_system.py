"""
Tests for the Dolmenwood encounter system.

Tests the encounter tables, NPC generators, and encounter roller.
"""

import pytest

from src.data_models import DiceRoller, StatBlock

# Everyday mortal data
from src.npc.everyday_mortal_data import (
    EVERYDAY_MORTAL_STATS,
    EVERYDAY_MORTAL_TYPES,
    BASIC_DETAILS,
    get_mortal_type,
    get_all_mortal_types,
)

# Adventurer data
from src.npc.adventurer_data import (
    ADVENTURER_TEMPLATES,
    KINDRED_TRAITS,
    get_adventurer_template,
    get_all_class_ids,
    get_template_levels,
)

# Adventurer tables
from src.npc.adventurer_tables import (
    ADVENTURER_KINDRED,
    CLASS_BY_KINDRED,
    ALIGNMENT,
    get_class_for_kindred,
    get_available_classes_for_kindred,
    is_spell_caster,
)

# Encounter NPC generator
from src.npc.encounter_npc_generator import (
    EncounterNPCGenerator,
    EverydayMortalResult,
    AdventurerResult,
    AdventuringPartyResult,
    get_encounter_npc_generator,
)

# Encounter tables
from src.tables.wilderness_encounter_tables import (
    TimeOfDay,
    LocationType,
    EncounterCategory,
    EncounterEntry,
    ENCOUNTER_TYPE_TABLE,
    COMMON_TABLES,
    REGIONAL_TABLES,
    UNSEASON_TABLES,
    get_encounter_type_table,
    get_regional_table,
    get_all_regions,
)

# Encounter roller
from src.tables.encounter_roller import (
    EncounterRoller,
    EncounterContext,
    RolledEncounter,
    EncounterEntryType,
    LairCheckResult,
    get_encounter_roller,
    roll_wilderness_encounter,
)


# =============================================================================
# EVERYDAY MORTAL DATA TESTS
# =============================================================================


class TestEverydayMortalData:
    """Tests for everyday mortal data definitions."""

    def test_everyday_mortal_stats_complete(self):
        """Test that shared stats are complete."""
        stats = EVERYDAY_MORTAL_STATS
        assert stats["level"] == 1
        assert stats["armor_class"] == 10
        assert stats["hp_dice"] == "1d4"
        assert stats["morale"] == 6
        assert stats["xp"] == 10
        assert "saves" in stats
        assert len(stats["weapons"]) == 3

    def test_all_mortal_types_defined(self):
        """Test that all expected mortal types are defined."""
        expected_types = [
            "angler",
            "crier",
            "fortune_teller",
            "lost_soul",
            "merchant",
            "pedlar",
            "pilgrim",
            "priest",
            "villager",
        ]
        for type_id in expected_types:
            assert type_id in EVERYDAY_MORTAL_TYPES

    def test_get_mortal_type(self):
        """Test getting a mortal type definition."""
        mortal_type = get_mortal_type("villager")
        assert mortal_type is not None
        assert mortal_type.name == "Villager"
        assert mortal_type.type_id == "villager"

    def test_get_mortal_type_not_found(self):
        """Test getting a nonexistent mortal type."""
        mortal_type = get_mortal_type("nonexistent")
        assert mortal_type is None

    def test_basic_details_tables(self):
        """Test that basic details tables are complete."""
        assert "sex" in BASIC_DETAILS
        assert "age" in BASIC_DETAILS
        assert "dress" in BASIC_DETAILS
        assert "feature" in BASIC_DETAILS
        assert "kindred" in BASIC_DETAILS

    def test_mortal_type_has_roll_tables(self):
        """Test that mortal types with roll tables have valid entries."""
        crier = EVERYDAY_MORTAL_TYPES["crier"]
        assert "news" in crier["roll_tables"]
        assert len(crier["roll_tables"]["news"]["entries"]) == 6


# =============================================================================
# ADVENTURER DATA TESTS
# =============================================================================


class TestAdventurerData:
    """Tests for adventurer data definitions."""

    def test_all_classes_defined(self):
        """Test that all 9 classes are defined."""
        expected_classes = [
            "bard",
            "cleric",
            "enchanter",
            "fighter",
            "friar",
            "hunter",
            "knight",
            "magician",
            "thief",
        ]
        for class_id in expected_classes:
            assert class_id in ADVENTURER_TEMPLATES

    def test_all_classes_have_three_levels(self):
        """Test that each class has levels 1, 3, and 5."""
        for class_id in get_all_class_ids():
            levels = get_template_levels(class_id)
            assert 1 in levels
            assert 3 in levels
            assert 5 in levels

    def test_get_adventurer_template(self):
        """Test getting an adventurer template."""
        template = get_adventurer_template("fighter", 3)
        assert template is not None
        assert template["title"] == "Lieutenant"
        assert template["level"] == 3

    def test_get_adventurer_template_level_mapping(self):
        """Test that intermediate levels map to correct templates."""
        # Level 2 should get level 3 template
        template = get_adventurer_template("fighter", 2)
        assert template["level"] == 3

        # Level 4 should get level 5 template
        template = get_adventurer_template("fighter", 4)
        assert template["level"] == 5

    def test_template_has_required_fields(self):
        """Test that templates have all required fields."""
        template = get_adventurer_template("fighter", 1)
        required_fields = [
            "title",
            "level",
            "armor_class",
            "hp_dice",
            "hp_average",
            "saves",
            "attack_bonus",
            "speed",
            "morale",
            "xp",
            "number_appearing",
            "gear",
            "attacks",
        ]
        for field_name in required_fields:
            assert field_name in template, f"Missing field: {field_name}"

    def test_kindred_traits_defined(self):
        """Test that kindred traits are defined."""
        expected_kindreds = ["breggle", "elf", "grimalkin", "human", "mossling", "woodgrue"]
        for kindred in expected_kindreds:
            assert kindred in KINDRED_TRAITS


# =============================================================================
# ADVENTURER TABLES TESTS
# =============================================================================


class TestAdventurerTables:
    """Tests for adventurer generation tables."""

    def test_adventurer_kindred_table(self):
        """Test kindred table has all entries."""
        for roll in range(1, 13):
            assert roll in ADVENTURER_KINDRED["entries"]

    def test_class_by_kindred_all_kindreds(self):
        """Test that all kindreds have class mappings."""
        expected_kindreds = ["breggle", "elf", "grimalkin", "human", "mossling", "woodgrue"]
        for kindred in expected_kindreds:
            assert kindred in CLASS_BY_KINDRED

    def test_get_class_for_kindred(self):
        """Test getting class for a kindred roll."""
        # Human roll 7-10 should be fighter
        class_id = get_class_for_kindred("human", 7)
        assert class_id == "fighter"

    def test_get_available_classes_for_kindred(self):
        """Test getting available classes for a kindred."""
        human_classes = get_available_classes_for_kindred("human")
        assert "fighter" in human_classes
        assert "cleric" in human_classes

        # Elves can't be clerics or friars
        elf_classes = get_available_classes_for_kindred("elf")
        assert "cleric" not in elf_classes
        assert "friar" not in elf_classes

    def test_is_spell_caster(self):
        """Test spell caster identification."""
        assert is_spell_caster("magician") is True
        assert is_spell_caster("cleric") is True
        assert is_spell_caster("fighter") is False
        assert is_spell_caster("thief") is False


# =============================================================================
# ENCOUNTER NPC GENERATOR TESTS
# =============================================================================


class TestEncounterNPCGenerator:
    """Tests for the EncounterNPCGenerator class."""

    @pytest.fixture
    def generator(self):
        return EncounterNPCGenerator()

    def test_generate_everyday_mortals(self, generator):
        """Test generating everyday mortals."""
        results = generator.generate_everyday_mortals("villager", count=3)
        assert len(results) == 3
        for result in results:
            assert isinstance(result, EverydayMortalResult)
            assert result.mortal_type == "villager"
            assert result.stat_block is not None
            assert result.stat_block.armor_class == 10

    def test_everyday_mortal_has_basic_details(self, generator):
        """Test that everyday mortals have basic details when requested."""
        results = generator.generate_everyday_mortals(
            "pilgrim", count=1, include_basic_details=True
        )
        assert len(results) == 1
        assert results[0].basic_details is not None
        assert "sex" in results[0].basic_details

    def test_everyday_mortal_type_details(self, generator):
        """Test that type-specific details are rolled."""
        results = generator.generate_everyday_mortals("crier", count=1, roll_type_tables=True)
        assert len(results) == 1
        assert "news" in results[0].type_details

    def test_generate_adventurer(self, generator):
        """Test generating a single adventurer."""
        result = generator.generate_adventurer(class_id="fighter", level=3, kindred="human")
        assert result is not None
        assert isinstance(result, AdventurerResult)
        assert result.class_id == "fighter"
        assert result.title == "Lieutenant"
        assert result.kindred == "human"

    def test_adventurer_has_stat_block(self, generator):
        """Test that adventurer has valid stat block."""
        result = generator.generate_adventurer("cleric", level=5)
        assert result.stat_block is not None
        assert result.stat_block.armor_class > 0
        assert result.stat_block.hp_current > 0

    def test_adventurer_has_gear_and_spells(self, generator):
        """Test that casters have spells."""
        result = generator.generate_adventurer("cleric", level=5)
        assert len(result.gear) > 0
        assert len(result.spells) > 0

    def test_generate_adventuring_party(self, generator):
        """Test generating an adventuring party."""
        party = generator.generate_adventuring_party()
        assert isinstance(party, AdventuringPartyResult)
        assert 5 <= len(party.members) <= 8
        assert party.alignment in ["Lawful", "Neutral", "Chaotic"]
        assert party.quest is not None
        assert "cp" in party.treasure

    def test_adventuring_party_has_marching_order(self, generator):
        """Test that party has marching order."""
        party = generator.generate_adventuring_party()
        assert len(party.marching_order) == len(party.members)

    def test_roll_creature_activity(self, generator):
        """Test rolling creature activity."""
        activity = generator.roll_creature_activity()
        assert activity is not None
        assert len(activity) > 0


# =============================================================================
# ENCOUNTER TABLES TESTS
# =============================================================================


class TestEncounterTables:
    """Tests for encounter table definitions."""

    def test_encounter_type_table_complete(self):
        """Test that encounter type table has all combinations."""
        combinations = [
            (TimeOfDay.DAYTIME, LocationType.ROAD),
            (TimeOfDay.DAYTIME, LocationType.WILD),
            (TimeOfDay.NIGHTTIME, LocationType.FIRE),
            (TimeOfDay.NIGHTTIME, LocationType.NO_FIRE),
        ]
        for combo in combinations:
            assert combo in ENCOUNTER_TYPE_TABLE
            table = ENCOUNTER_TYPE_TABLE[combo]
            # Should have entries for d8 (1-8)
            for roll in range(1, 9):
                assert roll in table

    def test_common_tables_complete(self):
        """Test that all common tables are defined."""
        categories = [
            EncounterCategory.ANIMAL,
            EncounterCategory.MONSTER,
            EncounterCategory.MORTAL,
            EncounterCategory.SENTIENT,
        ]
        for category in categories:
            assert category in COMMON_TABLES
            table = COMMON_TABLES[category]
            # Should have 20 entries
            for roll in range(1, 21):
                assert roll in table["entries"]

    def test_all_regions_defined(self):
        """Test that all 12 regions are defined."""
        expected_regions = [
            "aldweald",
            "aquatic",
            "dwelmfurgh",
            "fever_marsh",
            "hags_addle",
            "high_wold",
            "mulchgrove",
            "nagwood",
            "northern_scratch",
            "table_downs",
            "tithelands",
            "valley_of_wise_beasts",
        ]
        for region in expected_regions:
            assert region in REGIONAL_TABLES

    def test_regional_tables_have_20_entries(self):
        """Test that regional tables have 20 entries each."""
        for region_id, table in REGIONAL_TABLES.items():
            for roll in range(1, 21):
                assert roll in table["entries"], f"Missing entry {roll} in {region_id}"

    def test_unseason_tables_defined(self):
        """Test that unseason tables are defined."""
        assert "chame" in UNSEASON_TABLES
        assert "vague" in UNSEASON_TABLES

    def test_encounter_entry_type_detection(self):
        """Test that entry types are correctly detected."""
        # Animal (ends with *)
        entry = EncounterEntry(name="Bear*", number_appearing="1d4")
        assert entry.entry_type == "animal"

        # Adventurer (ends with †)
        entry = EncounterEntry(name="Fighter†", number_appearing="2d6")
        assert entry.entry_type == "adventurer"

        # Everyday mortal (ends with ‡)
        entry = EncounterEntry(name="Villager‡", number_appearing="2d10")
        assert entry.entry_type == "everyday_mortal"

        # Monster (no marker)
        entry = EncounterEntry(name="Goblin", number_appearing="2d6")
        assert entry.entry_type == "monster"


# =============================================================================
# ENCOUNTER ROLLER TESTS
# =============================================================================


class TestEncounterRoller:
    """Tests for the EncounterRoller class."""

    @pytest.fixture
    def roller(self):
        return EncounterRoller()

    def test_roll_encounter_returns_result(self, roller):
        """Test that rolling an encounter returns a result."""
        context = EncounterContext(region="tithelands")
        result = roller.roll_encounter(context)
        assert isinstance(result, RolledEncounter)
        assert result.entry is not None
        assert result.number_appearing >= 1

    def test_roll_encounter_with_activity(self, roller):
        """Test rolling with activity."""
        context = EncounterContext(region="aldweald")
        result = roller.roll_encounter(context, roll_activity=True)
        assert result.activity is not None

    def test_roll_encounter_aquatic(self, roller):
        """Test aquatic encounter."""
        context = EncounterContext(region="tithelands", is_aquatic=True)
        result = roller.roll_encounter(context)
        assert result.region == "aquatic"

    def test_roll_encounter_simple(self, roller):
        """Test simplified encounter roll."""
        result = roller.roll_encounter_simple(region="high_wold", is_day=True, on_road=True)
        assert result is not None
        assert result.time_of_day == TimeOfDay.DAYTIME
        assert result.location_type == LocationType.ROAD

    def test_roll_surprise(self, roller):
        """Test surprise rolls."""
        party_surprised, enemy_surprised = roller.roll_surprise()
        assert isinstance(party_surprised, bool)
        assert isinstance(enemy_surprised, bool)

    def test_roll_encounter_distance(self, roller):
        """Test encounter distance roll."""
        distance = roller.roll_encounter_distance()
        assert 60 <= distance <= 360  # 2d6 × 30

        distance_surprised = roller.roll_encounter_distance(both_surprised=True)
        assert 30 <= distance_surprised <= 120  # 1d4 × 30

    def test_convenience_function(self):
        """Test module-level convenience function."""
        result = roll_wilderness_encounter(
            region="fever_marsh",
            time_of_day=TimeOfDay.NIGHTTIME,
            location_type=LocationType.NO_FIRE,
        )
        assert result is not None
        assert result.time_of_day == TimeOfDay.NIGHTTIME

    def test_get_encounter_roller_singleton(self):
        """Test that get_encounter_roller returns singleton."""
        roller1 = get_encounter_roller()
        roller2 = get_encounter_roller()
        assert roller1 is roller2


# =============================================================================
# LAIR FUNCTIONALITY TESTS
# =============================================================================


class TestLairFunctionality:
    """Tests for lair encounter functionality."""

    @pytest.fixture
    def roller(self):
        return EncounterRoller()

    def test_lair_check_result_dataclass(self):
        """Test LairCheckResult dataclass defaults."""
        result = LairCheckResult()
        assert result.in_lair is False
        assert result.lair_chance is None
        assert result.lair_description is None
        assert result.hoard is None

    def test_rolled_encounter_has_lair_fields(self, roller):
        """Test that RolledEncounter includes lair fields."""
        context = EncounterContext(region="tithelands")
        result = roller.roll_encounter(context)

        # These fields should exist (may be None or have values)
        assert hasattr(result, "in_lair")
        assert hasattr(result, "lair_chance")
        assert hasattr(result, "lair_description")
        assert hasattr(result, "hoard")

    def test_lair_check_only_for_monsters_and_animals(self, roller):
        """Test that lair checks only apply to monster/animal entries."""
        # Create a mock entry that's an everyday mortal
        from src.tables.wilderness_encounter_tables import EncounterEntry

        entry = EncounterEntry(name="Pilgrim‡", number_appearing="4d8")

        # Everyday mortals shouldn't have lair checks
        entry_type = roller._determine_entry_type(entry)
        assert entry_type == EncounterEntryType.EVERYDAY_MORTAL

    def test_check_lair_with_unknown_monster(self, roller):
        """Test lair check with unknown monster returns empty result."""
        result = roller._check_lair("nonexistent_monster_id")
        assert result.in_lair is False
        assert result.lair_chance is None

    def test_check_lair_with_no_monster_id(self, roller):
        """Test lair check with None monster_id returns empty result."""
        result = roller._check_lair(None)
        assert result.in_lair is False
        assert result.lair_chance is None

    def test_encounter_respects_check_lair_flag(self, roller):
        """Test that check_lair=False skips lair checking."""
        context = EncounterContext(region="aldweald")
        result = roller.roll_encounter(context, check_lair=False)

        # When check_lair=False, lair fields should be default
        assert result.in_lair is False

    def test_aquatic_encounter_includes_lair_fields(self, roller):
        """Test that aquatic encounters include lair fields."""
        context = EncounterContext(region="lake_dolemere", is_aquatic=True)
        result = roller.roll_encounter(context)

        # Should have lair fields
        assert hasattr(result, "in_lair")
        assert hasattr(result, "lair_chance")
        assert hasattr(result, "hoard")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestEncounterSystemIntegration:
    """Integration tests for the encounter system."""

    def test_full_encounter_flow(self):
        """Test complete encounter generation flow."""
        # 1. Roll encounter
        roller = get_encounter_roller()
        context = EncounterContext(
            time_of_day=TimeOfDay.DAYTIME,
            location_type=LocationType.WILD,
            region="aldweald",
        )
        result = roller.roll_encounter(context, roll_activity=True)

        # 2. Verify result
        assert result.entry is not None
        assert result.number_appearing >= 1
        assert result.entry_type in EncounterEntryType

        # 3. If it's an everyday mortal, generate them
        if result.entry_type == EncounterEntryType.EVERYDAY_MORTAL:
            generator = get_encounter_npc_generator()
            # Parse mortal type from entry name
            name = result.entry.name.rstrip("‡").lower().replace("-", "_").replace(" ", "_")
            mortals = generator.generate_everyday_mortals(name, count=result.number_appearing)
            assert len(mortals) == result.number_appearing

        # 4. If it's an adventurer, generate them
        elif result.entry_type == EncounterEntryType.ADVENTURER:
            generator = get_encounter_npc_generator()
            # Parse class from entry name
            name = result.entry.name.rstrip("†").lower()
            if "(" in name:
                name = name.split("(")[0].strip()
            # Generate adventurers
            for _ in range(result.number_appearing):
                adventurer = generator.generate_adventurer(class_id=name, level=1)
                if adventurer:
                    assert adventurer.stat_block is not None

    def test_party_generation_flow(self):
        """Test adventuring party generation flow."""
        generator = get_encounter_npc_generator()
        party = generator.generate_adventuring_party()

        # Verify party
        assert len(party.members) >= 5
        assert party.quest is not None

        # Each member should have valid stats
        for member in party.members:
            assert member.stat_block is not None
            assert member.stat_block.hp_current > 0
            assert member.class_id in get_all_class_ids()

    def test_all_regions_can_be_rolled(self):
        """Test that all regions can generate encounters."""
        roller = get_encounter_roller()
        for region in get_all_regions():
            context = EncounterContext(region=region)
            result = roller.roll_encounter(context)
            assert result is not None
            assert result.entry is not None
