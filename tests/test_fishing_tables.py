"""
Tests for the Dolmenwood fishing tables.

Tests the fishing mechanics from Campaign Book p116-117:
- 20 fish species on d20 table
- Landing requirements (DEX/STR checks)
- Catch effects (danger, treasure, combat, monster attraction)
- Variable ration yields
- Special conditions (pipe music for Wraithfish)
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tables.fishing_tables import (
    EDIBLE_FISH,
    CatchableFish,
    CatchEffect,
    LandingRequirement,
    LandingType,
    FishEffectType,
    roll_fish,
    roll_fish_rations,
    get_fish_by_name,
    get_all_fish,
    check_treasure_in_fish,
    check_first_timer_danger,
    check_monster_attracted,
    fish_requires_landing_check,
    fish_triggers_combat,
    fish_is_fairy,
    fish_to_inventory_item,
)


class TestFishingTables:
    """Test the fish table structure."""

    def test_fish_table_has_20_entries(self):
        """Fish table should have exactly 20 entries for d20."""
        assert len(EDIBLE_FISH) == 20

    def test_all_fish_have_required_fields(self):
        """All fish should have name and description."""
        for fish in EDIBLE_FISH:
            assert fish.name, f"Fish missing name"
            assert fish.description, f"{fish.name} missing description"
            assert isinstance(fish.landing, LandingRequirement)
            assert isinstance(fish.catch_effect, CatchEffect)

    def test_fish_names_are_unique(self):
        """All fish names should be unique."""
        names = [fish.name for fish in EDIBLE_FISH]
        assert len(names) == len(set(names))

    def test_default_ration_yield_is_2d6(self):
        """Most fish should yield 2d6 rations by default."""
        default_fish = [f for f in EDIBLE_FISH if f.rations_yield == "2d6"]
        # Most fish have 2d6, some have special yields
        assert len(default_fish) >= 15


class TestSpecificFish:
    """Test specific fish mechanics per Campaign Book."""

    def test_butter_eel_requires_dex_check(self):
        """Butter-eel should require DEX check from 2 PCs."""
        fish = get_fish_by_name("Butter-eel")
        assert fish is not None
        assert fish.landing.landing_type == LandingType.DEX_CHECK
        assert fish.landing.num_characters == 2

    def test_nag_pike_requires_str_check(self):
        """Nag-pike should require STR check from 2 PCs."""
        fish = get_fish_by_name("Nag-pike")
        assert fish is not None
        assert fish.landing.landing_type == LandingType.STR_CHECK
        assert fish.landing.num_characters == 2

    def test_giant_catfish_triggers_combat(self):
        """Giant catfish should trigger combat encounter."""
        fish = get_fish_by_name("Giant catfish")
        assert fish is not None
        assert fish_triggers_combat(fish)
        assert fish.rations_per_hp == 4
        assert fish.monster_id == "giant_catfish"

    def test_hameth_sprat_reduced_yield(self):
        """Hameth sprat should only yield 2d4 rations."""
        fish = get_fish_by_name("Hameth sprat")
        assert fish is not None
        assert fish.rations_yield == "2d4"

    def test_wraithfish_reduced_yield_without_music(self):
        """Wraithfish should yield 1d6 without pipe music."""
        fish = get_fish_by_name("Wraithfish")
        assert fish is not None
        assert fish.rations_yield == "1d6"
        assert "pipe music" in fish.special_condition.lower()

    def test_queens_salmon_is_fairy_fish(self):
        """Queen's salmon should be a fairy fish with blessing."""
        fish = get_fish_by_name("Queen's salmon")
        assert fish is not None
        assert fish_is_fairy(fish)
        assert fish.catch_effect.blessing_if_released
        assert fish.catch_effect.blessing_bonus == 4

    def test_screaming_jenny_attracts_monsters(self):
        """Screaming jenny should have monster attraction effect."""
        fish = get_fish_by_name("Screaming jenny")
        assert fish is not None
        assert fish.catch_effect.attracts_monster
        assert fish.catch_effect.chance == "3-in-6"

    def test_groper_has_treasure_chance(self):
        """Groper should have chance for trinket in belly."""
        fish = get_fish_by_name("Groper")
        assert fish is not None
        assert fish.catch_effect.effect_type == FishEffectType.TREASURE_TRINKET
        assert fish.catch_effect.chance == "2-in-6"

    def test_smuggler_fish_has_gem_chance(self):
        """Smuggler-fish should have chance for gem in belly."""
        fish = get_fish_by_name("Smuggler-fish")
        assert fish is not None
        assert fish.catch_effect.effect_type == FishEffectType.TREASURE_GEM
        assert "1d20" in fish.catch_effect.treasure_value

    def test_gurney_first_timer_danger(self):
        """Gurney should damage first-time catchers."""
        fish = get_fish_by_name("Gurney")
        assert fish is not None
        assert fish.catch_effect.requires_experience
        assert fish.catch_effect.save_type == "doom"
        assert fish.catch_effect.damage == "1"

    def test_puffer_first_timer_danger(self):
        """Puffer should damage first-time catchers."""
        fish = get_fish_by_name("Puffer")
        assert fish is not None
        assert fish.catch_effect.requires_experience
        assert fish.catch_effect.save_type == "blast"
        assert fish.catch_effect.damage == "1d3"

    def test_bally_tom_hypnotic_effect(self):
        """Bally-tom should have hypnotic effect."""
        fish = get_fish_by_name("Bally-tom")
        assert fish is not None
        assert fish.catch_effect.effect_type == FishEffectType.HYPNOTIC
        assert fish.catch_effect.save_type == "hold"


class TestFishingRolls:
    """Test rolling functions."""

    def test_roll_fish_returns_fish(self):
        """roll_fish should return a CatchableFish."""
        fish = roll_fish()
        assert isinstance(fish, CatchableFish)
        assert fish.name in [f.name for f in EDIBLE_FISH]

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_roll_fish_uses_d20(self, mock_roll):
        """roll_fish should use d20."""
        mock_result = MagicMock()
        mock_result.total = 1
        mock_roll.return_value = mock_result

        fish = roll_fish()
        mock_roll.assert_called_with("1d20", "Fishing table")
        assert fish == EDIBLE_FISH[0]  # Index 0 for roll of 1

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_roll_fish_all_indices(self, mock_roll):
        """All d20 results should map to valid fish."""
        mock_result = MagicMock()

        for i in range(1, 21):
            mock_result.total = i
            mock_roll.return_value = mock_result
            fish = roll_fish()
            assert fish == EDIBLE_FISH[i - 1]

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_roll_fish_rations_default_2d6(self, mock_roll):
        """Default fish should roll 2d6 for rations."""
        mock_result = MagicMock()
        mock_result.total = 7
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Gaffer")  # Normal fish with 2d6
        rations = roll_fish_rations(fish)

        mock_roll.assert_called_with("2d6", "Gaffer rations yield")
        assert rations == 7

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_roll_fish_rations_hameth_sprat_2d4(self, mock_roll):
        """Hameth sprat should roll 2d4 for rations."""
        mock_result = MagicMock()
        mock_result.total = 5
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Hameth sprat")
        rations = roll_fish_rations(fish)

        mock_roll.assert_called_with("2d4", "Hameth sprat rations yield")
        assert rations == 5

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_roll_fish_rations_wraithfish_without_music(self, mock_roll):
        """Wraithfish without pipe music should roll 1d6."""
        mock_result = MagicMock()
        mock_result.total = 3
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Wraithfish")
        rations = roll_fish_rations(fish, has_pipe_music=False)

        mock_roll.assert_called_with("1d6", "Wraithfish rations yield")
        assert rations == 3

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_roll_fish_rations_wraithfish_with_music(self, mock_roll):
        """Wraithfish with pipe music should roll 2d6."""
        mock_result = MagicMock()
        mock_result.total = 8
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Wraithfish")
        rations = roll_fish_rations(fish, has_pipe_music=True)

        mock_roll.assert_called_with("2d6", "Wraithfish rations yield")
        assert rations == 8

    def test_roll_fish_rations_combat_fish_returns_zero(self):
        """Combat fish should return 0 rations (calculated from HP)."""
        fish = get_fish_by_name("Giant catfish")
        rations = roll_fish_rations(fish)
        assert rations == 0


class TestLookupFunctions:
    """Test fish lookup functions."""

    def test_get_fish_by_name_case_insensitive(self):
        """get_fish_by_name should be case insensitive."""
        fish1 = get_fish_by_name("Butter-eel")
        fish2 = get_fish_by_name("butter-eel")
        fish3 = get_fish_by_name("BUTTER-EEL")

        assert fish1 is not None
        assert fish1 == fish2 == fish3

    def test_get_fish_by_name_not_found(self):
        """get_fish_by_name should return None for unknown fish."""
        fish = get_fish_by_name("Nonexistent Fish")
        assert fish is None

    def test_get_all_fish_returns_copy(self):
        """get_all_fish should return a copy of the list."""
        fish_list = get_all_fish()
        assert len(fish_list) == 20
        fish_list.pop()
        assert len(EDIBLE_FISH) == 20  # Original unchanged


class TestLandingChecks:
    """Test landing requirement detection."""

    def test_fish_requires_landing_check_butter_eel(self):
        """Butter-eel should require landing check."""
        fish = get_fish_by_name("Butter-eel")
        assert fish_requires_landing_check(fish)

    def test_fish_requires_landing_check_nag_pike(self):
        """Nag-pike should require landing check."""
        fish = get_fish_by_name("Nag-pike")
        assert fish_requires_landing_check(fish)

    def test_fish_requires_landing_check_normal_fish(self):
        """Normal fish should not require special landing check."""
        fish = get_fish_by_name("Gaffer")
        assert not fish_requires_landing_check(fish)


class TestTreasureChecks:
    """Test treasure checking functions."""

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_check_treasure_groper_found(self, mock_roll):
        """Groper should return trinket when roll succeeds."""
        mock_result = MagicMock()
        mock_result.total = 1  # Success (1-2 on d6)
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Groper")
        treasure = check_treasure_in_fish(fish)

        assert treasure is not None
        assert treasure["type"] == "trinket"

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_check_treasure_groper_not_found(self, mock_roll):
        """Groper should return None when roll fails."""
        mock_result = MagicMock()
        mock_result.total = 5  # Failure (3-6 on d6)
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Groper")
        treasure = check_treasure_in_fish(fish)

        assert treasure is None

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_check_treasure_smuggler_fish_gem(self, mock_roll):
        """Smuggler-fish should return gem with value when roll succeeds."""
        mock_result = MagicMock()
        mock_result.total = 2  # First call: success, second call: gem value
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Smuggler-fish")

        # Reset mock to return different values
        mock_roll.side_effect = [
            MagicMock(total=1),  # Treasure check succeeds
            MagicMock(total=15),  # Gem value roll (15 * 10 = 150gp)
        ]

        treasure = check_treasure_in_fish(fish)

        assert treasure is not None
        assert treasure["type"] == "gem"
        assert treasure["value_gp"] == 150

    def test_check_treasure_normal_fish(self):
        """Normal fish should have no treasure."""
        fish = get_fish_by_name("Gaffer")
        treasure = check_treasure_in_fish(fish)
        assert treasure is None


class TestMonsterAttraction:
    """Test monster attraction mechanics."""

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_screaming_jenny_attracts_monster(self, mock_roll):
        """Screaming jenny should attract monster on low roll."""
        mock_result = MagicMock()
        mock_result.total = 2  # Success (1-3 on d6)
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Screaming jenny")
        attracted = check_monster_attracted(fish)

        assert attracted is True

    @patch("src.tables.fishing_tables.DiceRoller.roll")
    def test_screaming_jenny_no_monster(self, mock_roll):
        """Screaming jenny should not attract monster on high roll."""
        mock_result = MagicMock()
        mock_result.total = 5  # Failure (4-6 on d6)
        mock_roll.return_value = mock_result

        fish = get_fish_by_name("Screaming jenny")
        attracted = check_monster_attracted(fish)

        assert attracted is False

    def test_normal_fish_no_monster(self):
        """Normal fish should not attract monsters."""
        fish = get_fish_by_name("Gaffer")
        attracted = check_monster_attracted(fish)
        assert attracted is False


class TestFirstTimerDanger:
    """Test first-timer danger mechanics."""

    def test_gurney_danger_first_timer(self):
        """Gurney should be dangerous for first-timers."""
        fish = get_fish_by_name("Gurney")
        danger = check_first_timer_danger(fish, has_experience=False)

        assert danger is not None
        assert danger["save_type"] == "doom"
        assert danger["damage"] == "1"

    def test_gurney_safe_experienced(self):
        """Gurney should be safe for experienced anglers."""
        fish = get_fish_by_name("Gurney")
        danger = check_first_timer_danger(fish, has_experience=True)

        assert danger is None

    def test_puffer_danger_first_timer(self):
        """Puffer should be dangerous for first-timers."""
        fish = get_fish_by_name("Puffer")
        danger = check_first_timer_danger(fish, has_experience=False)

        assert danger is not None
        assert danger["save_type"] == "blast"
        assert danger["damage"] == "1d3"

    def test_normal_fish_no_danger(self):
        """Normal fish should have no first-timer danger."""
        fish = get_fish_by_name("Gaffer")
        danger = check_first_timer_danger(fish, has_experience=False)

        assert danger is None


class TestFishSerialization:
    """Test fish serialization."""

    def test_fish_to_dict(self):
        """Fish should serialize to dictionary."""
        fish = get_fish_by_name("Butter-eel")
        data = fish.to_dict()

        assert data["name"] == "Butter-eel"
        assert data["description"]
        assert "landing" in data
        assert "catch_effect" in data
        assert data["landing"]["landing_type"] == "dex_check"
        assert data["landing"]["num_characters"] == 2

    def test_fish_from_dict_roundtrip(self):
        """Fish should survive serialization roundtrip."""
        original = get_fish_by_name("Queen's salmon")
        data = original.to_dict()
        restored = CatchableFish.from_dict(data)

        assert restored.name == original.name
        assert restored.catch_effect.blessing_bonus == original.catch_effect.blessing_bonus
        assert restored.catch_effect.blessing_if_released == original.catch_effect.blessing_if_released


class TestFishToInventoryItem:
    """Test converting fish to inventory items."""

    def test_basic_conversion(self):
        """Basic conversion should create valid Item."""
        fish = get_fish_by_name("Gaffer")
        item = fish_to_inventory_item(fish, quantity=7)

        assert item.name == "Gaffer"
        assert item.quantity == 7
        assert item.item_type == "consumable"

    def test_conversion_with_source_hex(self):
        """Conversion should store source hex."""
        fish = get_fish_by_name("Braithgilly")
        item = fish_to_inventory_item(fish, quantity=5, source_hex="0603")

        assert item.source_hex == "0603"

    def test_conversion_includes_flavor_text(self):
        """Conversion should include flavor text in consumption effect."""
        fish = get_fish_by_name("Maid-o'-the-lake")
        item = fish_to_inventory_item(fish, quantity=4)

        assert item.consumption_effect is not None
        assert "flavor_text" in item.consumption_effect
        assert "witch" in item.consumption_effect["flavor_text"].lower()

    def test_converted_item_serializes(self):
        """Converted item should serialize to JSON-compatible dict."""
        fish = get_fish_by_name("Orbling")
        item = fish_to_inventory_item(fish, quantity=6)

        data = item.to_dict()
        assert data["name"] == "Orbling"
        assert data["quantity"] == 6
        assert data["consumption_effect"]["effect_type"] == "rations"


class TestHazardResolverFishingIntegration:
    """Test fishing integration with HazardResolver."""

    @pytest.fixture
    def resolver(self):
        """Create a HazardResolver instance."""
        from src.narrative.hazard_resolver import HazardResolver
        return HazardResolver()

    @pytest.fixture
    def mock_character(self):
        """Create a mock character for testing."""
        from src.data_models import CharacterState
        return CharacterState(
            character_id="test_angler",
            name="Test Angler",
            character_class="Fighter",
            level=1,
            base_speed=40,
            hp_current=10,
            hp_max=10,
            armor_class=10,
            ability_scores={"STR": 12, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        )

    @patch("src.narrative.hazard_resolver.roll_fish")
    @patch("src.narrative.hazard_resolver.roll_fish_rations")
    def test_fishing_returns_fish_caught(
        self, mock_rations, mock_fish, resolver, mock_character
    ):
        """Fishing should return fish_caught data."""
        mock_fish.return_value = get_fish_by_name("Gaffer")
        mock_rations.return_value = 8

        result = resolver.resolve_foraging(
            character=mock_character,
            method="fishing",
            difficulty=1,  # Ensure survival check always passes
        )

        assert result.success
        assert result.fish_caught is not None
        assert result.fish_caught["name"] == "Gaffer"
        assert result.rations_found == 8

    @patch("src.narrative.hazard_resolver.roll_fish")
    def test_fishing_giant_catfish_triggers_combat(
        self, mock_fish, resolver, mock_character
    ):
        """Giant catfish should trigger combat."""
        mock_fish.return_value = get_fish_by_name("Giant catfish")

        result = resolver.resolve_foraging(
            character=mock_character,
            method="fishing",
            difficulty=1,  # Ensure survival check always passes
        )

        assert result.success
        assert result.combat_triggered
        assert result.fish_caught["name"] == "Giant catfish"

    @patch("src.narrative.hazard_resolver.roll_fish")
    @patch("src.narrative.hazard_resolver.roll_fish_rations")
    def test_fishing_butter_eel_requires_landing(
        self, mock_rations, mock_fish, resolver, mock_character
    ):
        """Butter-eel should require landing check."""
        mock_fish.return_value = get_fish_by_name("Butter-eel")
        mock_rations.return_value = 6

        result = resolver.resolve_foraging(
            character=mock_character,
            method="fishing",
            difficulty=1,  # Ensure survival check always passes
        )

        assert result.landing_required is not None
        assert result.landing_required["landing_type"] == "dex_check"
        assert result.landing_required["num_characters"] == 2

    @patch("src.narrative.hazard_resolver.roll_fish")
    @patch("src.narrative.hazard_resolver.roll_fish_rations")
    def test_fishing_queens_salmon_offers_blessing(
        self, mock_rations, mock_fish, resolver, mock_character
    ):
        """Queen's salmon should offer blessing."""
        mock_fish.return_value = get_fish_by_name("Queen's salmon")
        mock_rations.return_value = 7

        result = resolver.resolve_foraging(
            character=mock_character,
            method="fishing",
            difficulty=1,  # Ensure survival check always passes
        )

        assert result.blessing_offered
        assert any("blessing" in event["type"] for event in result.catch_events)
