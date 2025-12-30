"""
Tests for hunting tables per Campaign Book (p120-121).

Tests cover:
- Game animal data structure and completeness
- Terrain-specific hunting tables
- Roll functions for animals and number appearing
- Encounter distance and ration yield calculations
- Integration with HazardResolver
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tables.hunting_tables import (
    GameAnimal,
    AnimalSize,
    TerrainType,
    GAME_ANIMALS,
    HUNTING_TABLES,
    get_game_animal,
    get_game_animal_by_name,
    roll_game_animal,
    roll_number_appearing,
    roll_encounter_distance,
    calculate_rations_yield,
    get_hunting_terrain,
    get_all_animals,
    get_animals_in_terrain,
    animal_appears_in_terrain,
)


class TestGameAnimalData:
    """Tests for game animal data structure."""

    def test_all_14_game_animals_exist(self):
        """Campaign Book p121 lists 14 game animals."""
        expected_animals = {
            "boar",
            "false_unicorn",
            "gelatinous_ape",
            "gobble",
            "headhog",
            "honey_badger",
            "lurkey",
            "merriman",
            "moss_mole",
            "puggle",
            "red_deer",
            "swamp_sloth",
            "trotteling",
            "woad",
            "yegril",
        }
        assert set(GAME_ANIMALS.keys()) == expected_animals

    def test_all_animals_have_required_fields(self):
        """Each game animal should have all required fields."""
        for animal_id, animal in GAME_ANIMALS.items():
            assert animal.name, f"{animal_id} missing name"
            assert animal.monster_id, f"{animal_id} missing monster_id"
            assert animal.size in AnimalSize, f"{animal_id} has invalid size"
            assert animal.number_appearing, f"{animal_id} missing number_appearing"
            assert animal.description, f"{animal_id} missing description"

    def test_animal_sizes_match_monster_book(self):
        """Verify size categories match Monster Book entries."""
        # Small animals (1 ration per HP)
        small_animals = [
            "gelatinous_ape",
            "gobble",
            "headhog",
            "honey_badger",
            "lurkey",
            "merriman",
            "moss_mole",
            "puggle",
            "swamp_sloth",
            "trotteling",
            "woad",
        ]
        for animal_id in small_animals:
            assert GAME_ANIMALS[animal_id].size == AnimalSize.SMALL

        # Medium animals (2 rations per HP)
        medium_animals = ["boar", "false_unicorn"]
        for animal_id in medium_animals:
            assert GAME_ANIMALS[animal_id].size == AnimalSize.MEDIUM

        # Large animals (4 rations per HP)
        large_animals = ["red_deer", "yegril"]
        for animal_id in large_animals:
            assert GAME_ANIMALS[animal_id].size == AnimalSize.LARGE

    def test_number_appearing_matches_monster_book(self):
        """Verify number appearing dice match Monster Book entries."""
        expected = {
            "boar": "1d6",
            "false_unicorn": "3d4",
            "gelatinous_ape": "1d12",
            "gobble": "3d6",
            "headhog": "2d6",
            "honey_badger": "1d4",
            "lurkey": "2d4",
            "merriman": "1d6",
            "moss_mole": "1d6",
            "puggle": "2d4",
            "red_deer": "3d10",
            "swamp_sloth": "1d6",
            "trotteling": "2d6",
            "woad": "3d6",
            "yegril": "3d8",
        }
        for animal_id, dice in expected.items():
            assert GAME_ANIMALS[animal_id].number_appearing == dice

    def test_rations_per_hp_by_size(self):
        """Verify rations per HP calculation by size."""
        # Small = 1 ration/HP
        assert GAME_ANIMALS["gobble"].rations_per_hp == 1
        # Medium = 2 rations/HP
        assert GAME_ANIMALS["boar"].rations_per_hp == 2
        # Large = 4 rations/HP
        assert GAME_ANIMALS["red_deer"].rations_per_hp == 4


class TestHuntingTables:
    """Tests for terrain-specific hunting tables."""

    def test_all_12_terrain_types_have_tables(self):
        """Campaign Book p121 shows 12 terrain types."""
        expected_terrains = {
            TerrainType.BOG,
            TerrainType.FARMLAND,
            TerrainType.FOREST_BOGGY,
            TerrainType.FOREST_CRAGGY,
            TerrainType.FOREST_HILLY,
            TerrainType.FOREST_OPEN,
            TerrainType.FOREST_TANGLED,
            TerrainType.FOREST_THORNY,
            TerrainType.FUNGAL_FOREST,
            TerrainType.HILLS,
            TerrainType.MEADOW,
            TerrainType.SWAMP,
        }
        assert set(HUNTING_TABLES.keys()) == expected_terrains

    def test_each_table_has_20_entries(self):
        """Each terrain table should map d20 rolls 1-20."""
        for terrain, table in HUNTING_TABLES.items():
            assert set(table.keys()) == set(range(1, 21)), f"{terrain} missing rolls"

    def test_all_table_entries_are_valid_animals(self):
        """All table entries should reference valid game animals."""
        for terrain, table in HUNTING_TABLES.items():
            for roll, animal_id in table.items():
                assert animal_id in GAME_ANIMALS, f"{terrain} roll {roll}: {animal_id} not found"

    def test_bog_table_has_swamp_sloth(self):
        """Bog terrain should include Swamp Sloth (unique to boggy areas)."""
        bog_animals = set(HUNTING_TABLES[TerrainType.BOG].values())
        assert "swamp_sloth" in bog_animals

    def test_farmland_has_no_swamp_animals(self):
        """Farmland shouldn't have Swamp Sloth (wrong habitat)."""
        farmland_animals = set(HUNTING_TABLES[TerrainType.FARMLAND].values())
        assert "swamp_sloth" not in farmland_animals

    def test_forest_thorny_has_many_trottelings(self):
        """Forest Thorny is dominated by Trottelings (rolls 15-20)."""
        thorny_table = HUNTING_TABLES[TerrainType.FOREST_THORNY]
        trotteling_count = sum(1 for a in thorny_table.values() if a == "trotteling")
        assert trotteling_count >= 6  # At least 6 entries


class TestRollFunctions:
    """Tests for roll functions."""

    def test_roll_game_animal_returns_valid_animal(self):
        """roll_game_animal should return a valid GameAnimal."""
        for terrain in TerrainType:
            animal = roll_game_animal(terrain)
            assert isinstance(animal, GameAnimal)
            assert animal.monster_id in GAME_ANIMALS

    def test_roll_number_appearing_respects_dice(self):
        """roll_number_appearing should roll appropriate dice."""
        # Test boar (1d6) - should be 1-6
        boar = GAME_ANIMALS["boar"]
        for _ in range(50):
            num = roll_number_appearing(boar)
            assert 1 <= num <= 6

        # Test red deer (3d10) - should be 3-30
        deer = GAME_ANIMALS["red_deer"]
        for _ in range(50):
            num = roll_number_appearing(deer)
            assert 3 <= num <= 30

    def test_roll_encounter_distance_is_30_60_90_or_120(self):
        """Encounter distance is 1d4 × 30' = 30, 60, 90, or 120."""
        valid_distances = {30, 60, 90, 120}
        for _ in range(50):
            distance = roll_encounter_distance()
            assert distance in valid_distances


class TestRationYield:
    """Tests for ration yield calculations."""

    def test_small_animal_1_ration_per_hp(self):
        """Small animals yield 1 ration per HP killed."""
        gobble = GAME_ANIMALS["gobble"]  # HP 2, Small
        assert calculate_rations_yield(gobble, 2) == 2
        assert calculate_rations_yield(gobble, 10) == 10

    def test_medium_animal_2_rations_per_hp(self):
        """Medium animals yield 2 rations per HP killed."""
        boar = GAME_ANIMALS["boar"]  # HP 13, Medium
        assert calculate_rations_yield(boar, 13) == 26
        assert calculate_rations_yield(boar, 26) == 52  # Two boars

    def test_large_animal_4_rations_per_hp(self):
        """Large animals yield 4 rations per HP killed."""
        deer = GAME_ANIMALS["red_deer"]  # HP 13, Large
        assert calculate_rations_yield(deer, 13) == 52
        assert calculate_rations_yield(deer, 39) == 156  # Three deer


class TestTerrainMapping:
    """Tests for terrain type mapping."""

    def test_direct_terrain_mappings(self):
        """Test direct terrain type mappings."""
        assert get_hunting_terrain("bog") == TerrainType.BOG
        assert get_hunting_terrain("farmland") == TerrainType.FARMLAND
        assert get_hunting_terrain("swamp") == TerrainType.SWAMP
        assert get_hunting_terrain("hills") == TerrainType.HILLS
        assert get_hunting_terrain("meadow") == TerrainType.MEADOW

    def test_forest_subtype_mappings(self):
        """Test forest subtype mappings using official Dolmenwood terrain names."""
        # data_models.TerrainType uses: boggy_forest, craggy_forest, hilly_forest, etc.
        # These map to hunting TerrainType: FOREST_BOGGY, FOREST_CRAGGY, FOREST_HILLY, etc.
        assert get_hunting_terrain("boggy_forest") == TerrainType.FOREST_BOGGY
        assert get_hunting_terrain("craggy_forest") == TerrainType.FOREST_CRAGGY
        assert get_hunting_terrain("hilly_forest") == TerrainType.FOREST_HILLY
        assert get_hunting_terrain("open_forest") == TerrainType.FOREST_OPEN
        assert get_hunting_terrain("tangled_forest") == TerrainType.FOREST_TANGLED
        assert get_hunting_terrain("thorny_forest") == TerrainType.FOREST_THORNY

    def test_fungal_forest_mapping(self):
        """Fungal forest should map correctly."""
        assert get_hunting_terrain("fungal_forest") == TerrainType.FUNGAL_FOREST

    def test_settlement_defaults_to_farmland(self):
        """Settlements should use farmland tables (though hunting in settlements is unlikely)."""
        assert get_hunting_terrain("settlement") == TerrainType.FARMLAND

    def test_unknown_terrain_defaults_to_forest_open(self):
        """Unknown terrain should default to forest_open."""
        assert get_hunting_terrain("unknown_terrain") == TerrainType.FOREST_OPEN
        assert get_hunting_terrain("") == TerrainType.FOREST_OPEN


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_game_animal(self):
        """get_game_animal should find animals by ID."""
        boar = get_game_animal("boar")
        assert boar is not None
        assert boar.name == "Boar"

        assert get_game_animal("nonexistent") is None

    def test_get_game_animal_by_name(self):
        """get_game_animal_by_name should find animals by name."""
        boar = get_game_animal_by_name("Boar")
        assert boar is not None
        assert boar.monster_id == "boar"

        # Case insensitive
        assert get_game_animal_by_name("BOAR") is not None
        assert get_game_animal_by_name("boar") is not None

        assert get_game_animal_by_name("nonexistent") is None

    def test_get_all_animals(self):
        """get_all_animals should return all 14 animals."""
        animals = get_all_animals()
        assert len(animals) == 15  # 15 game animals total

    def test_get_animals_in_terrain(self):
        """get_animals_in_terrain should return unique animals for terrain."""
        bog_animals = get_animals_in_terrain(TerrainType.BOG)
        assert len(bog_animals) > 0
        assert all(isinstance(a, GameAnimal) for a in bog_animals)

        # Bog should have swamp sloth
        animal_ids = [a.monster_id for a in bog_animals]
        assert "swamp_sloth" in animal_ids

    def test_animal_appears_in_terrain(self):
        """animal_appears_in_terrain should check terrain tables correctly."""
        # Swamp sloth appears in bog
        assert animal_appears_in_terrain("swamp_sloth", TerrainType.BOG)
        # Swamp sloth doesn't appear in farmland
        assert not animal_appears_in_terrain("swamp_sloth", TerrainType.FARMLAND)


class TestHazardResolverIntegration:
    """Tests for HazardResolver hunting integration."""

    @pytest.fixture
    def resolver(self):
        """Create a HazardResolver for testing."""
        from src.narrative.hazard_resolver import HazardResolver
        return HazardResolver()

    @pytest.fixture
    def mock_character(self):
        """Create a mock character for testing."""
        from src.data_models import CharacterState
        return CharacterState(
            character_id="test_hunter",
            name="Test Hunter",
            character_class="Hunter",
            level=1,
            ability_scores={"STR": 12, "DEX": 14, "CON": 10, "INT": 10, "WIS": 14, "CHA": 10},
            hp_current=8,
            hp_max=8,
            armor_class=12,
            base_speed=40,
        )

    @patch("src.narrative.hazard_resolver.roll_game_animal")
    @patch("src.narrative.hazard_resolver.roll_number_appearing")
    @patch("src.narrative.hazard_resolver.roll_encounter_distance")
    def test_hunting_returns_game_animal(
        self, mock_distance, mock_num, mock_animal, resolver, mock_character
    ):
        """Hunting should return game_animal data."""
        mock_animal.return_value = get_game_animal("boar")
        mock_num.return_value = 3
        mock_distance.return_value = 60

        result = resolver.resolve_foraging(
            character=mock_character,
            method="hunting",
            terrain="forest",
            difficulty=1,  # Ensure success
        )

        assert result.success
        assert result.game_animal is not None
        assert result.game_animal["name"] == "Boar"
        assert result.game_animal["monster_id"] == "boar"

    @patch("src.narrative.hazard_resolver.roll_game_animal")
    @patch("src.narrative.hazard_resolver.roll_number_appearing")
    @patch("src.narrative.hazard_resolver.roll_encounter_distance")
    def test_hunting_sets_encounter_distance(
        self, mock_distance, mock_num, mock_animal, resolver, mock_character
    ):
        """Hunting should set encounter distance (1d4 × 30')."""
        mock_animal.return_value = get_game_animal("red_deer")
        mock_num.return_value = 5
        mock_distance.return_value = 90  # 3 × 30'

        result = resolver.resolve_foraging(
            character=mock_character,
            method="hunting",
            terrain="meadow",
            difficulty=1,
        )

        assert result.encounter_distance == 90

    @patch("src.narrative.hazard_resolver.roll_game_animal")
    @patch("src.narrative.hazard_resolver.roll_number_appearing")
    @patch("src.narrative.hazard_resolver.roll_encounter_distance")
    def test_hunting_party_has_surprise(
        self, mock_distance, mock_num, mock_animal, resolver, mock_character
    ):
        """Party should always have surprise when hunting."""
        mock_animal.return_value = get_game_animal("lurkey")
        mock_num.return_value = 4
        mock_distance.return_value = 30

        result = resolver.resolve_foraging(
            character=mock_character,
            method="hunting",
            terrain="forest_open",
            difficulty=1,
        )

        assert result.party_has_surprise is True

    @patch("src.narrative.hazard_resolver.roll_game_animal")
    @patch("src.narrative.hazard_resolver.roll_number_appearing")
    @patch("src.narrative.hazard_resolver.roll_encounter_distance")
    def test_hunting_triggers_combat(
        self, mock_distance, mock_num, mock_animal, resolver, mock_character
    ):
        """Hunting should trigger combat encounter."""
        mock_animal.return_value = get_game_animal("yegril")
        mock_num.return_value = 2
        mock_distance.return_value = 120

        result = resolver.resolve_foraging(
            character=mock_character,
            method="hunting",
            terrain="hills",
            difficulty=1,
        )

        assert result.combat_triggered is True

    @patch("src.narrative.hazard_resolver.roll_game_animal")
    @patch("src.narrative.hazard_resolver.roll_number_appearing")
    @patch("src.narrative.hazard_resolver.roll_encounter_distance")
    def test_hunting_calculates_potential_rations(
        self, mock_distance, mock_num, mock_animal, resolver, mock_character
    ):
        """Hunting should calculate potential rations from kill."""
        # Red deer: Large (4 rations/HP), HP 13, 2 appearing = 2 × 13 × 4 = 104
        mock_animal.return_value = get_game_animal("red_deer")
        mock_num.return_value = 2
        mock_distance.return_value = 60

        result = resolver.resolve_foraging(
            character=mock_character,
            method="hunting",
            terrain="meadow",
            difficulty=1,
        )

        # 2 deer × 13 HP × 4 rations/HP = 104 potential rations
        assert result.potential_rations == 104

    def test_hunting_failure_returns_no_animal(self, resolver, mock_character):
        """Failed survival check should return no game animal."""
        # Force failure by requiring 7+ on d6 (impossible)
        result = resolver.resolve_foraging(
            character=mock_character,
            method="hunting",
            terrain="forest",
            difficulty=10,
        )

        assert not result.success
        assert result.game_animal is None


class TestGameAnimalToDict:
    """Tests for GameAnimal serialization."""

    def test_to_dict_includes_all_fields(self):
        """to_dict should include all relevant fields."""
        boar = GAME_ANIMALS["boar"]
        data = boar.to_dict()

        assert data["name"] == "Boar"
        assert data["monster_id"] == "boar"
        assert data["size"] == "medium"
        assert data["number_appearing"] == "1d6"
        assert data["description"]
        assert data["rations_per_hp"] == 2

    def test_to_dict_is_json_serializable(self):
        """to_dict output should be JSON serializable."""
        import json

        for animal in GAME_ANIMALS.values():
            data = animal.to_dict()
            # Should not raise
            json.dumps(data)
