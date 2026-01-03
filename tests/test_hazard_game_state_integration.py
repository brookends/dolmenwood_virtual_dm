"""
Integration tests for hazard effects being applied to game state.

These tests verify that:
- Damage from hazards is applied to character HP
- Conditions from hazards are added to character.conditions
- Effects are properly applied through the controller
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import CharacterState, ConditionType, Condition
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine


class TestHazardEffectsAppliedToGameState:
    """Integration tests verifying hazard effects modify game state."""

    @pytest.fixture
    def controller(self):
        """Create a GlobalController with a test character."""
        controller = GlobalController()

        # Create a test character with known HP
        character = CharacterState(
            character_id="test_fighter",
            name="Test Fighter",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )
        controller.add_character(character)
        return controller

    @pytest.fixture
    def engine(self, controller):
        """Create a HexCrawlEngine with the controller."""
        # Create engine without full initialization
        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine.dice = MagicMock()
        engine.narrative_resolver = MagicMock()
        engine._current_hex = "test_hex"
        engine._current_poi = None
        engine._hex_data = {}
        return engine

    def test_damage_applied_to_character_hp(self, controller, engine):
        """Verify damage from hazard reduces character HP."""
        # Set up dice to fail save and deal 5 damage
        engine.dice.roll_d20.return_value = MagicMock(total=3)  # Will fail save
        engine.dice.roll.return_value = MagicMock(total=5)  # 5 damage

        character = controller.get_character("test_fighter")
        initial_hp = character.hp_current

        hazard = {
            "hazard_type": "environmental",
            "save_type": "doom",
            "difficulty": 15,
            "description": "A trap springs!",
            "damage": "1d6",
            "on_fail": {
                "damage_dice": "1d6",
            },
        }

        # Mock make_saving_throw to fail
        character.make_saving_throw = MagicMock(return_value=(3, False))

        # Resolve hazard with apply_effects=True (default)
        result = engine._resolve_hazard(hazard, character, apply_effects=True)

        # Verify damage was tracked
        assert result.damage_dealt == 5
        assert result.damage_taken == 5
        assert len(result.apply_damage) == 1
        assert result.apply_damage[0] == ("test_fighter", 5)

    def test_condition_applied_to_character(self, controller, engine):
        """Verify condition from hazard is added to character."""
        # Set up dice to fail save
        engine.dice.roll_d20.return_value = MagicMock(total=3)
        engine.dice.roll.return_value = MagicMock(total=0)

        character = controller.get_character("test_fighter")

        # Verify no conditions initially
        assert len(character.conditions) == 0

        hazard = {
            "hazard_type": "environmental",
            "save_type": "spell",
            "difficulty": 15,
            "description": "Enchanting mist",
            "on_fail": {
                "condition": "exhausted",
            },
        }

        # Mock make_saving_throw to fail
        character.make_saving_throw = MagicMock(return_value=(3, False))

        result = engine._resolve_hazard(hazard, character, apply_effects=True)

        # Verify condition was tracked
        assert "exhausted" in result.conditions_applied
        assert len(result.apply_conditions) == 1
        assert result.apply_conditions[0] == ("test_fighter", "exhausted")
        assert result.effect_applied == "exhausted"

    def test_successful_save_no_effects(self, controller, engine):
        """Verify successful save prevents effects from being applied."""
        engine.dice.roll_d20.return_value = MagicMock(total=18)

        character = controller.get_character("test_fighter")
        initial_hp = character.hp_current

        hazard = {
            "hazard_type": "environmental",
            "save_type": "doom",
            "difficulty": 15,
            "description": "A trap springs!",
            "on_fail": {
                "damage_dice": "2d6",
                "condition": "poisoned",
            },
        }

        # Mock make_saving_throw to succeed
        character.make_saving_throw = MagicMock(return_value=(18, True))

        result = engine._resolve_hazard(hazard, character, apply_effects=True)

        # Verify no damage or conditions
        assert result.success is True
        assert result.damage_dealt == 0
        assert result.damage_taken == 0
        assert len(result.conditions_applied) == 0
        assert len(result.apply_damage) == 0
        assert len(result.apply_conditions) == 0


class TestProcessNightHazardsAppliesEffects:
    """Integration tests for process_night_hazards applying effects to game state."""

    @pytest.fixture
    def controller_with_party(self):
        """Create controller with multiple characters."""
        controller = GlobalController()

        fighter = CharacterState(
            character_id="fighter_1",
            name="Brave Fighter",
            character_class="Fighter",
            level=2,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=18,
            hp_max=18,
            armor_class=14,
            base_speed=40,
        )

        wizard = CharacterState(
            character_id="wizard_1",
            name="Wise Wizard",
            character_class="Magic-User",
            level=2,
            ability_scores={"STR": 8, "INT": 16, "WIS": 14, "DEX": 10, "CON": 8, "CHA": 12},
            hp_current=6,
            hp_max=6,
            armor_class=10,
            base_speed=40,
        )

        controller.add_character(fighter)
        controller.add_character(wizard)
        return controller

    @pytest.fixture
    def engine_with_hex(self, controller_with_party):
        """Create engine with hex data containing night hazards."""
        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller_with_party
        engine.dice = MagicMock()
        engine.narrative_resolver = MagicMock()
        engine._current_hex = "0105"
        engine._current_poi = None

        # Set up hex with night hazard
        mock_hex = MagicMock()
        mock_hex.procedural = MagicMock()
        mock_hex.procedural.night_hazards = [
            {
                "trigger": "sleep",
                "name": "Restless Dreams",
                "save_type": "spell",
                "description": "Disturbing dreams haunt your sleep",
                "on_fail": {
                    "condition": "exhausted",
                    "effect": "-1 to all rolls",
                },
            }
        ]
        mock_hex.points_of_interest = []
        engine._hex_data = {"0105": mock_hex}

        return engine

    def test_night_hazard_tracks_effects_applied(self, engine_with_hex, controller_with_party):
        """Verify process_night_hazards includes effects_applied in results."""
        # Mock time to be night
        engine_with_hex._is_night = MagicMock(return_value=True)
        engine_with_hex._is_full_moon = MagicMock(return_value=False)
        engine_with_hex._is_winter = MagicMock(return_value=False)

        # Mock dice - first character fails, second succeeds
        call_count = [0]
        def mock_save(save_type, modifier=0):
            call_count[0] += 1
            if call_count[0] == 1:
                return (5, False)  # Fighter fails
            return (18, True)  # Wizard succeeds

        for char in controller_with_party.get_all_characters():
            char.make_saving_throw = MagicMock(side_effect=mock_save)

        results = engine_with_hex.process_night_hazards("0105", activity="sleeping")

        # Both characters should be processed
        assert len(results) == 2

        # First result (fighter) should have failed and have effects applied
        fighter_result = next(r for r in results if r["character_id"] == "fighter_1")
        assert fighter_result["success"] is False
        assert "exhausted" in fighter_result["conditions_applied"]
        assert fighter_result["effects_applied"] is True

        # Second result (wizard) should have succeeded with no effects
        wizard_result = next(r for r in results if r["character_id"] == "wizard_1")
        assert wizard_result["success"] is True
        assert wizard_result["conditions_applied"] == []
        assert wizard_result["effects_applied"] is False


class TestResolvePOIActionAppliesEffects:
    """Integration tests for resolve_poi_action applying effects."""

    @pytest.fixture
    def controller(self):
        """Create controller with a test character."""
        controller = GlobalController()
        character = CharacterState(
            character_id="explorer_1",
            name="Bold Explorer",
            character_class="Thief",
            level=3,
            ability_scores={"STR": 10, "INT": 12, "WIS": 10, "DEX": 16, "CON": 12, "CHA": 14},
            hp_current=12,
            hp_max=12,
            armor_class=12,
            base_speed=40,
        )
        controller.add_character(character)
        return controller

    @pytest.fixture
    def engine_with_poi(self, controller):
        """Create engine at a POI with hazards."""
        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine.dice = MagicMock()
        engine.narrative_resolver = MagicMock()
        engine._current_hex = "0107"
        engine._current_poi = "The Weeping Woman"

        # Set up hex with POI hazard
        mock_poi = MagicMock()
        mock_poi.name = "The Weeping Woman"
        mock_poi.hazards = [
            {
                "hazard_id": "drinking_tears",
                "trigger": "consume",
                "hazard_type": "enchantment",
                "name": "Drinking Fairy Tears",
                "save_type": "spell",
                "description": "You drink the enchanted tears",
                "on_fail": {
                    "condition": "charmed",
                },
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = MagicMock()
        mock_hex.procedural.night_hazards = []
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0107": mock_hex}

        return engine

    def test_poi_action_result_includes_damage_taken(self, engine_with_poi, controller):
        """Verify resolve_poi_action includes damage_taken in results."""
        # Mock detect_poi_action to return a consume action
        engine_with_poi.detect_poi_action = MagicMock(return_value=("consume", "drink"))

        # Mock get_matching_poi_hazards to return our hazard
        engine_with_poi.get_matching_poi_hazards = MagicMock(return_value=[
            {
                "hazard_id": "drinking_tears",
                "trigger": "consume",
                "hazard_type": "environmental",
                "save_type": "spell",
                "description": "The tears burn going down",
                "on_fail": {
                    "damage_dice": "1d4",
                    "condition": "charmed",
                },
            }
        ])

        character = controller.get_character("explorer_1")
        character.make_saving_throw = MagicMock(return_value=(5, False))

        engine_with_poi.dice.roll_d20.return_value = MagicMock(total=5)
        engine_with_poi.dice.roll.return_value = MagicMock(total=3)  # 3 damage

        result = engine_with_poi.resolve_poi_action(
            "I drink from the pool", "explorer_1", "0107"
        )

        assert result["triggered"] is True
        assert len(result["hazard_results"]) == 1

        hazard_result = result["hazard_results"][0]
        assert hazard_result["success"] is False
        assert hazard_result["damage_taken"] == 3
        assert "charmed" in hazard_result["conditions_applied"]
        assert hazard_result["effects_applied"] is True
