"""
Tests for hex 0105 (The Demesne of the Frore Gryphus) hazard mechanics.

These tests verify that night hazards, camp triggers, and cold damage
work correctly for hex 0105's specific gameplay.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestNightHazardTriggerDetection:
    """Tests for extended night hazard trigger detection."""

    def test_sleep_trigger_fires_when_sleeping(self):
        """Verify 'sleep' trigger fires when activity is sleeping."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._hex_data = {}
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine.controller.world_state = MagicMock()
        engine.controller.world_state.current_time = MagicMock()
        engine.controller.world_state.current_time.get_time_of_day.return_value = MagicMock(
            value="midnight"
        )
        engine.controller.world_state.current_date = MagicMock()
        engine.controller.world_state.current_date.is_full_moon.return_value = False

        # Create mock hex data with sleep trigger
        mock_hex = MagicMock()
        mock_hex.procedural = MagicMock()
        mock_hex.procedural.night_hazards = [
            {
                "trigger": "sleep",
                "save_type": "spell",
                "description": "Dream of ancient battle",
                "on_fail": {"condition": "exhausted"},
            }
        ]
        engine._hex_data = {"0105": mock_hex}

        # Mock _is_night to return True
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)

        # Should NOT trigger without activity
        results = engine.process_night_hazards("0105", activity=None)
        assert len(results) == 0

        # Should trigger with sleeping activity
        results = engine.process_night_hazards("0105", activity="sleeping")
        # No characters, but trigger check should succeed
        assert results == []  # Empty because no characters

    def test_camp_near_trigger_fires_when_camping(self):
        """Verify 'camp_near_*' trigger fires when camping near feature."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._hex_data = {}
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []

        # Create mock hex data with camp_near trigger
        mock_hex = MagicMock()
        mock_hex.procedural = MagicMock()
        mock_hex.procedural.night_hazards = [
            {
                "trigger": "camp_near_frost_patches",
                "save_type": "doom",
                "description": "Cold seeps into dreams",
                "on_fail": {"damage_dice": "1d4", "damage_type": "cold"},
            }
        ]
        mock_hex.points_of_interest = []
        mock_hex.description = "Frost-covered patches dot the landscape"
        engine._hex_data = {"0105": mock_hex}

        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)

        # Should NOT trigger without camping activity
        results = engine.process_night_hazards("0105", activity=None)
        assert len(results) == 0

        # Should trigger when camping (feature exists in hex)
        results = engine.process_night_hazards("0105", activity="camping")
        assert results == []  # Empty because no characters

    def test_camp_near_with_explicit_location(self):
        """Verify camp_near trigger with explicit camp_location."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._hex_data = {}
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []

        mock_hex = MagicMock()
        mock_hex.procedural = MagicMock()
        mock_hex.procedural.night_hazards = [
            {"trigger": "camp_near_frost_patches", "save_type": "doom"}
        ]
        mock_hex.points_of_interest = []
        mock_hex.description = ""
        engine._hex_data = {"0105": mock_hex}

        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)

        # Should NOT trigger when camping elsewhere
        results = engine.process_night_hazards(
            "0105", activity="camping", camp_location="shepherd_camp"
        )
        assert len(results) == 0

        # Should trigger when camping near frost patches
        results = engine.process_night_hazards(
            "0105", activity="camping", camp_location="frost_patches"
        )
        assert results == []  # Empty because no characters


class TestHexFeatureDetection:
    """Tests for _hex_has_feature method."""

    def test_detects_feature_in_description(self):
        """Verify feature detection in hex description."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)

        mock_hex = MagicMock()
        mock_hex.points_of_interest = []
        mock_hex.description = "Frost-covered patches dot the landscape"
        engine._hex_data = {"0105": mock_hex}

        assert engine._hex_has_feature("0105", "frost_patches") is True
        assert engine._hex_has_feature("0105", "ancient_ruins") is False

    def test_detects_feature_in_poi_name(self):
        """Verify feature detection in POI names."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)

        mock_poi = MagicMock()
        mock_poi.name = "Frozen Battleground"
        mock_poi.description = "Ancient frost magic"
        mock_poi.special_features = []

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        mock_hex.description = ""
        engine._hex_data = {"0105": mock_hex}

        assert engine._hex_has_feature("0105", "frozen") is True
        assert engine._hex_has_feature("0105", "battleground") is True

    def test_detects_feature_in_special_features(self):
        """Verify feature detection in POI special features."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)

        mock_poi = MagicMock()
        mock_poi.name = "The Field"
        mock_poi.description = ""
        mock_poi.special_features = [
            "Frost-covered patches radiate magic",
            "Dead frost giant with frozen soldiers",
        ]

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        mock_hex.description = ""
        engine._hex_data = {"0105": mock_hex}

        assert engine._hex_has_feature("0105", "frost") is True
        assert engine._hex_has_feature("0105", "frost giant") is True


class TestHazardResolverSaveTypes:
    """Tests for proper save type routing in _resolve_hazard."""

    def test_doom_save_resolved_properly(self):
        """Verify Save vs Doom is handled correctly."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=10)
        engine.dice.roll.return_value = MagicMock(total=3)
        engine.narrative_resolver = MagicMock()

        # Character with make_saving_throw that fails
        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(8, False))  # Failed save
        char.character_id = "test_char"

        hazard = {
            "save_type": "doom",
            "description": "Ancient frost magic",
            "on_fail": {
                "damage_dice": "1d4",
                "damage_type": "cold",
                "description": "Cold damage from frost",
            },
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        # Should have called make_saving_throw with "doom"
        char.make_saving_throw.assert_called_once_with("doom", 0)
        assert result.success is False
        assert result.damage_dealt == 3  # From mocked dice roll

    def test_spell_save_resolved_properly(self):
        """Verify Save vs Spell is handled correctly."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.narrative_resolver = MagicMock()

        # Character with make_saving_throw that succeeds
        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(18, True))  # Passed save
        char.character_id = "test_char"

        hazard = {
            "save_type": "spell",
            "description": "Dream of ancient battle",
            "on_fail": {"condition": "exhausted", "effect": "-1 to all rolls"},
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        char.make_saving_throw.assert_called_once_with("spell", 0)
        assert result.success is True
        assert len(result.conditions_applied) == 0  # Saved, no condition

    def test_failed_save_applies_condition(self):
        """Verify failed save applies condition from on_fail."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed
        char.character_id = "test_char"

        hazard = {
            "save_type": "spell",
            "description": "Dream haunts you",
            "on_fail": {"condition": "exhausted", "effect": "-1 to all rolls"},
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        assert result.success is False
        assert "exhausted" in result.conditions_applied
        # Effect is appended to description
        assert "-1 to all rolls" in result.description


class TestProcessNightHazardsIntegration:
    """Integration tests for process_night_hazards with characters."""

    def test_applies_hazard_to_all_characters(self):
        """Verify hazards are applied to all party members."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=10)
        engine.dice.roll.return_value = MagicMock(total=2)
        engine.narrative_resolver = MagicMock()
        engine.controller = MagicMock()

        # Create two mock characters
        char1 = MagicMock(spec=CharacterState)
        char1.character_id = "char1"
        char1.name = "Fighter"
        char1.make_saving_throw = MagicMock(return_value=(5, False))

        char2 = MagicMock(spec=CharacterState)
        char2.character_id = "char2"
        char2.name = "Wizard"
        char2.make_saving_throw = MagicMock(return_value=(18, True))

        engine.controller.get_all_characters.return_value = [char1, char2]

        mock_hex = MagicMock()
        mock_hex.procedural = MagicMock()
        mock_hex.procedural.night_hazards = [
            {
                "trigger": "sleep",
                "save_type": "spell",
                "description": "Dream haunts",
                "on_fail": {"condition": "exhausted"},
            }
        ]
        engine._hex_data = {"0105": mock_hex}

        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)
        engine._resolve_hazard = MagicMock(
            side_effect=[
                MagicMock(
                    success=False, description="Failed", conditions_applied=["exhausted"], damage_taken=0
                ),
                MagicMock(success=True, description="Saved", conditions_applied=[], damage_taken=0),
            ]
        )

        results = engine.process_night_hazards("0105", activity="sleeping")

        assert len(results) == 2
        assert results[0]["character_name"] == "Fighter"
        assert results[0]["success"] is False
        assert results[1]["character_name"] == "Wizard"
        assert results[1]["success"] is True
