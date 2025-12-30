"""
Tests for Dolmenwood foraging tables and mechanics.

Tests the Campaign Book (p118-119) foraging implementation including:
- 20 Edible Fungi species
- 20 Edible Plants species
- Consumption effect metadata
- Foraging rolls and Colliggwyld bonus
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tables.foraging_tables import (
    ForageableItem,
    ForageType,
    EffectType,
    ConsumptionEffect,
    EDIBLE_FUNGI,
    EDIBLE_PLANTS,
    roll_forage_type,
    roll_foraged_item,
    roll_forage_quantity,
    get_foraged_item_by_name,
    get_all_fungi,
    get_all_plants,
    is_fungi,
)
from src.narrative.hazard_resolver import HazardResolver, HazardResult
from src.data_models import CharacterState


class TestForagingTables:
    """Test the foraging table data."""

    def test_fungi_table_has_20_entries(self):
        """Verify the fungi table has exactly 20 entries for d20 roll."""
        assert len(EDIBLE_FUNGI) == 20

    def test_plants_table_has_20_entries(self):
        """Verify the plants table has exactly 20 entries for d20 roll."""
        assert len(EDIBLE_PLANTS) == 20

    def test_all_fungi_have_required_fields(self):
        """Each fungi entry should have all required fields."""
        for i, fungus in enumerate(EDIBLE_FUNGI, 1):
            assert fungus.name, f"Fungi #{i} missing name"
            assert fungus.forage_type == ForageType.FUNGI, f"{fungus.name} has wrong type"
            assert fungus.description, f"{fungus.name} missing description"
            assert fungus.smell, f"{fungus.name} missing smell"
            assert fungus.taste, f"{fungus.name} missing taste"
            assert fungus.effect is not None, f"{fungus.name} missing effect"

    def test_all_plants_have_required_fields(self):
        """Each plant entry should have all required fields."""
        for i, plant in enumerate(EDIBLE_PLANTS, 1):
            assert plant.name, f"Plant #{i} missing name"
            assert plant.forage_type == ForageType.PLANT, f"{plant.name} has wrong type"
            assert plant.description, f"{plant.name} missing description"
            assert plant.smell, f"{plant.smell} missing smell"
            assert plant.taste, f"{plant.name} missing taste"
            assert plant.effect is not None, f"{plant.name} missing effect"

    def test_fungi_names_are_unique(self):
        """All fungi should have unique names."""
        names = [f.name for f in EDIBLE_FUNGI]
        assert len(names) == len(set(names)), "Duplicate fungi names found"

    def test_plants_names_are_unique(self):
        """All plants should have unique names."""
        names = [p.name for p in EDIBLE_PLANTS]
        assert len(names) == len(set(names)), "Duplicate plant names found"


class TestSpecialEffects:
    """Test consumption effects metadata."""

    def test_hell_horns_double_nourishment(self):
        """Hell horns should have double nourishment effect."""
        item = get_foraged_item_by_name("Hell horns")
        assert item is not None
        assert item.effect.effect_type == EffectType.DOUBLE_NOURISHMENT

    def test_hob_nut_save_penalty(self):
        """Hob nuts should give -2 to saves vs magic."""
        item = get_foraged_item_by_name("Hob nut")
        assert item is not None
        assert item.effect.effect_type == EffectType.SAVE_PENALTY
        assert item.effect.modifier == -2
        assert item.effect.save_type == "magic"
        assert item.effect.duration_hours == 8

    def test_moonchook_valuable(self):
        """Moonchook should be valuable (sellable for gold)."""
        item = get_foraged_item_by_name("Moonchook")
        assert item is not None
        assert item.effect.effect_type == EffectType.VALUABLE
        assert item.effect.gold_value == "1d6"

    def test_jellycup_psychedelia(self):
        """Jellycups should cause psychedelia after dark."""
        item = get_foraged_item_by_name("Jellycup")
        assert item is not None
        assert item.effect.effect_type == EffectType.PSYCHEDELIA
        assert "after dark" in item.effect.condition.lower()

    def test_gorger_bean_double_nourishment(self):
        """Gorger beans should have double nourishment like Hell horns."""
        item = get_foraged_item_by_name("Gorger bean")
        assert item is not None
        assert item.effect.effect_type == EffectType.DOUBLE_NOURISHMENT

    def test_sage_toe_poison_resistance(self):
        """Sage toe should give poison resistance bonus."""
        item = get_foraged_item_by_name("Sage toe")
        assert item is not None
        assert item.effect.effect_type == EffectType.POISON_RESISTANCE
        assert item.effect.modifier == 1
        assert item.effect.save_type == "poison"

    def test_wanderers_friend_healing(self):
        """Wanderer's friend should heal 1 HP."""
        item = get_foraged_item_by_name("Wanderer's friend")
        assert item is not None
        assert item.effect.effect_type == EffectType.HEALING
        assert item.effect.modifier == 1


class TestForagingRolls:
    """Test the foraging roll mechanics."""

    def test_roll_forage_type_returns_fungi_or_plant(self):
        """roll_forage_type should return FUNGI or PLANT."""
        # Run multiple times to verify distribution
        results = [roll_forage_type() for _ in range(100)]
        assert ForageType.FUNGI in results
        assert ForageType.PLANT in results
        # All results should be valid types
        for r in results:
            assert r in (ForageType.FUNGI, ForageType.PLANT)

    @patch("src.tables.foraging_tables.DiceRoller.roll")
    def test_forage_type_d6_1_to_3_is_fungi(self, mock_roll):
        """d6 rolls of 1-3 should result in fungi."""
        for roll_value in [1, 2, 3]:
            mock_roll.return_value = MagicMock(total=roll_value)
            result = roll_forage_type()
            assert result == ForageType.FUNGI, f"Roll of {roll_value} should be fungi"

    @patch("src.tables.foraging_tables.DiceRoller.roll")
    def test_forage_type_d6_4_to_6_is_plant(self, mock_roll):
        """d6 rolls of 4-6 should result in plants."""
        for roll_value in [4, 5, 6]:
            mock_roll.return_value = MagicMock(total=roll_value)
            result = roll_forage_type()
            assert result == ForageType.PLANT, f"Roll of {roll_value} should be plant"

    @patch("src.tables.foraging_tables.DiceRoller.roll")
    def test_roll_foraged_item_uses_d20(self, mock_roll):
        """roll_foraged_item should roll d20 to select from table."""
        # Mock d20 roll of 8 should get index 7 (8th item)
        mock_roll.return_value = MagicMock(total=8)
        item = roll_foraged_item(ForageType.FUNGI)
        assert item == EDIBLE_FUNGI[7]  # 0-indexed

    @patch("src.tables.foraging_tables.DiceRoller.roll")
    def test_roll_foraged_item_all_indices(self, mock_roll):
        """Each d20 result should map to correct table index."""
        for d20_roll in range(1, 21):
            mock_roll.return_value = MagicMock(total=d20_roll)
            item = roll_foraged_item(ForageType.FUNGI)
            expected_index = d20_roll - 1
            assert item == EDIBLE_FUNGI[expected_index]

    def test_roll_forage_quantity_returns_1_to_6(self):
        """Quantity roll should return 1-6 rations."""
        results = [roll_forage_quantity() for _ in range(100)]
        for r in results:
            assert 1 <= r <= 6, f"Quantity {r} outside 1-6 range"


class TestForageableItemSerialization:
    """Test ForageableItem serialization for inventory storage."""

    def test_to_dict_includes_all_fields(self):
        """to_dict should include all item fields."""
        item = get_foraged_item_by_name("Hell horns")
        data = item.to_dict()

        assert data["name"] == "Hell horns"
        assert data["forage_type"] == "fungi"
        assert "description" in data
        assert "smell" in data
        assert "taste" in data
        assert "effect" in data

    def test_effect_serialization(self):
        """Effect should serialize correctly."""
        item = get_foraged_item_by_name("Hob nut")
        data = item.to_dict()

        effect = data["effect"]
        assert effect["effect_type"] == "save_penalty"
        assert effect["modifier"] == -2
        assert effect["save_type"] == "magic"
        assert effect["duration_hours"] == 8

    def test_from_dict_roundtrip(self):
        """Serialization should be reversible."""
        original = get_foraged_item_by_name("Moonchook")
        data = original.to_dict()
        restored = ForageableItem.from_dict(data)

        assert restored.name == original.name
        assert restored.forage_type == original.forage_type
        assert restored.description == original.description
        assert restored.effect.effect_type == original.effect.effect_type
        assert restored.effect.gold_value == original.effect.gold_value


class TestIsFungiHelper:
    """Test the is_fungi helper function."""

    def test_fungi_items_detected(self):
        """All fungi should be detected as fungi."""
        for fungus in EDIBLE_FUNGI:
            assert is_fungi(fungus), f"{fungus.name} should be detected as fungi"

    def test_plants_not_detected_as_fungi(self):
        """Plants should not be detected as fungi."""
        for plant in EDIBLE_PLANTS:
            assert not is_fungi(plant), f"{plant.name} should not be fungi"


class TestLookupFunctions:
    """Test the lookup helper functions."""

    def test_get_foraged_item_by_name_case_insensitive(self):
        """Name lookup should be case insensitive."""
        assert get_foraged_item_by_name("hell horns") is not None
        assert get_foraged_item_by_name("HELL HORNS") is not None
        assert get_foraged_item_by_name("Hell Horns") is not None

    def test_get_foraged_item_by_name_not_found(self):
        """Non-existent items should return None."""
        assert get_foraged_item_by_name("Nonexistent Item") is None

    def test_get_all_fungi_returns_copy(self):
        """get_all_fungi should return a copy, not the original list."""
        fungi1 = get_all_fungi()
        fungi2 = get_all_fungi()
        assert fungi1 is not fungi2
        assert fungi1 == fungi2

    def test_get_all_plants_returns_copy(self):
        """get_all_plants should return a copy, not the original list."""
        plants1 = get_all_plants()
        plants2 = get_all_plants()
        assert plants1 is not plants2
        assert plants1 == plants2


class TestHazardResolverForagingIntegration:
    """Test HazardResolver foraging with the new tables."""

    @pytest.fixture
    def resolver(self):
        """Create a HazardResolver instance."""
        return HazardResolver()

    @pytest.fixture
    def mock_character(self):
        """Create a mock character for testing."""
        return CharacterState(
            character_id="test_char",
            name="Test Forager",
            character_class="Fighter",
            level=1,
            base_speed=40,
            hp_current=10,
            hp_max=10,
            armor_class=10,
            ability_scores={"STR": 12, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        )

    @patch("src.narrative.hazard_resolver.roll_forage_type")
    @patch("src.narrative.hazard_resolver.roll_foraged_item")
    @patch("src.narrative.hazard_resolver.roll_forage_quantity")
    def test_foraging_returns_foraged_items(
        self, mock_quantity, mock_item, mock_type, resolver, mock_character
    ):
        """Successful foraging should return foraged_items with metadata."""
        # Setup mocks
        mock_type.return_value = ForageType.FUNGI
        mock_item.return_value = get_foraged_item_by_name("Hell horns")
        mock_quantity.return_value = 3

        # Force successful survival check
        with patch.object(resolver.dice, "roll_d6") as mock_d6:
            mock_d6.return_value = MagicMock(total=6)  # Success

            result = resolver.resolve_foraging(mock_character, method="foraging")

        assert result.success
        assert len(result.foraged_items) >= 1
        assert result.foraged_items[0]["name"] == "Hell horns"
        assert result.foraged_items[0]["forage_type"] == "fungi"
        assert "effect" in result.foraged_items[0]

    @patch("src.narrative.hazard_resolver.roll_forage_type")
    @patch("src.narrative.hazard_resolver.roll_foraged_item")
    @patch("src.narrative.hazard_resolver.roll_forage_quantity")
    def test_foraging_colliggwyld_doubles_fungi(
        self, mock_quantity, mock_item, mock_type, resolver, mock_character
    ):
        """During Colliggwyld, fungi yields should be doubled."""
        # Setup mocks
        mock_type.return_value = ForageType.FUNGI
        mock_item.return_value = get_foraged_item_by_name("Moonchook")
        mock_quantity.return_value = 3  # Base quantity

        # Force successful survival check
        with patch.object(resolver.dice, "roll_d6") as mock_d6:
            mock_d6.return_value = MagicMock(total=6)

            result = resolver.resolve_foraging(
                mock_character,
                method="foraging",
                active_unseason="colliggwyld",
            )

        assert result.success
        assert result.rations_found == 6  # 3 * 2 = 6 (doubled)
        assert result.foraged_items[0]["colliggwyld_bonus_applied"] is True

    @patch("src.narrative.hazard_resolver.roll_forage_type")
    @patch("src.narrative.hazard_resolver.roll_foraged_item")
    @patch("src.narrative.hazard_resolver.roll_forage_quantity")
    def test_foraging_colliggwyld_does_not_double_plants(
        self, mock_quantity, mock_item, mock_type, resolver, mock_character
    ):
        """During Colliggwyld, plants should NOT be doubled."""
        # Setup mocks
        mock_type.return_value = ForageType.PLANT
        mock_item.return_value = get_foraged_item_by_name("Hob nut")
        mock_quantity.return_value = 4

        # Force successful survival check
        with patch.object(resolver.dice, "roll_d6") as mock_d6:
            mock_d6.return_value = MagicMock(total=6)

            result = resolver.resolve_foraging(
                mock_character,
                method="foraging",
                active_unseason="colliggwyld",
            )

        assert result.success
        assert result.rations_found == 4  # NOT doubled
        assert result.foraged_items[0]["colliggwyld_bonus_applied"] is False

    def test_failed_foraging_no_items(self, resolver, mock_character):
        """Failed foraging should return no items."""
        # Force failed survival check
        with patch.object(resolver.dice, "roll_d6") as mock_d6:
            mock_d6.return_value = MagicMock(total=1)  # Fail

            result = resolver.resolve_foraging(
                mock_character,
                method="foraging",
                difficulty=6,  # Make it harder
            )

        assert not result.success
        assert result.foraged_items == []
        assert result.rations_found == 0

    def test_fishing_uses_fish_tables(self, resolver, mock_character):
        """Fishing should use fish tables, not foraging tables."""
        # Force successful survival check and mock the fish roll
        from src.tables.fishing_tables import get_fish_by_name

        with patch("src.narrative.hazard_resolver.roll_fish") as mock_fish:
            mock_fish.return_value = get_fish_by_name("Gaffer")

            with patch("src.narrative.hazard_resolver.roll_fish_rations") as mock_rations:
                mock_rations.return_value = 7

                result = resolver.resolve_foraging(
                    mock_character, method="fishing", difficulty=1
                )

        assert result.success
        assert result.rations_found == 7
        assert result.foraged_items == []  # Fish stored in fish_caught, not foraged_items
        assert result.fish_caught is not None
        assert result.fish_caught["name"] == "Gaffer"


class TestEffectMetadataForConsumption:
    """Test that effect metadata is properly stored for consumption system."""

    def test_effect_has_all_consumption_fields(self):
        """Effects should have all fields needed by consumption system."""
        item = get_foraged_item_by_name("Hob nut")
        effect = item.effect

        # These fields should be accessible for consumption
        assert hasattr(effect, "effect_type")
        assert hasattr(effect, "modifier")
        assert hasattr(effect, "duration_hours")
        assert hasattr(effect, "save_type")
        assert hasattr(effect, "condition")
        assert hasattr(effect, "gold_value")

    def test_serialized_effect_usable_by_consumption(self):
        """Serialized effects should be usable by consumption system."""
        item = get_foraged_item_by_name("Moon carrot")
        data = item.to_dict()
        effect_data = data["effect"]

        # Consumption system can check these
        assert effect_data["effect_type"] == "vision"
        assert effect_data["duration_hours"] == 4
        assert effect_data["description"]  # For player feedback

    def test_conditional_effects_have_condition(self):
        """Effects with conditions should have the condition field set."""
        # Jellycups only work "after dark"
        item = get_foraged_item_by_name("Jellycup")
        assert item.effect.condition == "after dark"

        # Crake berries only if "large quantity consumed"
        item = get_foraged_item_by_name("Crake berries")
        assert "large quantity" in item.effect.condition.lower()


class TestForageableToInventoryItem:
    """Test converting ForageableItem to Item for inventory storage."""

    def test_basic_conversion(self):
        """Basic conversion should create valid Item."""
        from src.tables.foraging_tables import forageable_to_inventory_item

        foraged = get_foraged_item_by_name("Hell horns")
        item = forageable_to_inventory_item(foraged, quantity=3)

        assert item.name == "Hell horns"
        assert item.quantity == 3
        assert item.item_type == "consumable"
        assert item.forage_type == "fungi"

    def test_conversion_preserves_effect_metadata(self):
        """Conversion should preserve consumption effect metadata."""
        from src.tables.foraging_tables import forageable_to_inventory_item

        foraged = get_foraged_item_by_name("Hob nut")
        item = forageable_to_inventory_item(foraged)

        assert item.consumption_effect is not None
        assert item.consumption_effect["effect_type"] == "save_penalty"
        assert item.consumption_effect["modifier"] == -2
        assert item.consumption_effect["save_type"] == "magic"
        assert item.consumption_effect["duration_hours"] == 8

    def test_conversion_includes_sensory_data(self):
        """Conversion should include smell and taste."""
        from src.tables.foraging_tables import forageable_to_inventory_item

        foraged = get_foraged_item_by_name("Moonchook")
        item = forageable_to_inventory_item(foraged)

        assert item.smell == "Cool and ethereal, like moonlit mist"
        assert item.taste == "Light and refreshing with a minty finish"

    def test_conversion_with_source_hex(self):
        """Conversion should store source hex when provided."""
        from src.tables.foraging_tables import forageable_to_inventory_item

        foraged = get_foraged_item_by_name("Gorger bean")
        item = forageable_to_inventory_item(foraged, source_hex="0807")

        assert item.source_hex == "0807"

    def test_converted_item_serializes(self):
        """Converted item should serialize to JSON-compatible dict."""
        from src.tables.foraging_tables import forageable_to_inventory_item

        foraged = get_foraged_item_by_name("Wanderer's friend")
        item = forageable_to_inventory_item(foraged, quantity=2)

        # Should serialize without errors
        data = item.to_dict()
        assert data["name"] == "Wanderer's friend"
        assert data["quantity"] == 2
        assert data["consumption_effect"]["effect_type"] == "healing"
        assert data["consumption_effect"]["modifier"] == 1

    def test_item_roundtrip(self):
        """Item should survive serialization roundtrip."""
        from src.tables.foraging_tables import forageable_to_inventory_item
        from src.data_models import Item

        foraged = get_foraged_item_by_name("Jellycup")
        original = forageable_to_inventory_item(foraged, quantity=4)

        # Serialize and deserialize
        data = original.to_dict()
        restored = Item.from_dict(data)

        assert restored.name == original.name
        assert restored.quantity == original.quantity
        assert restored.forage_type == original.forage_type
        assert restored.consumption_effect == original.consumption_effect
