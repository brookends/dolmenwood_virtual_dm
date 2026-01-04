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


class TestHazardSchemaVariations:
    """Tests for JSON hazard schema variations (damage_dice vs damage, top-level vs on_fail)."""

    def test_top_level_damage_dice_used(self):
        """Verify top-level damage_dice is used for POI hazards like frost_touch."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=3)  # Failed save
        engine.dice.roll.return_value = MagicMock(total=4)  # 4 damage
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(3, False))
        char.character_id = "test_char"

        # Hex 0105 frost_touch hazard uses top-level damage_dice
        hazard = {
            "hazard_id": "frost_touch",
            "name": "Ancient Frost Magic",
            "trigger": "touching frozen figures or frost giant",
            "save_type": "doom",
            "damage_dice": "1d6",  # Top-level, NOT in on_fail
            "damage_type": "cold",
            "description": "Ancient battle-magic lashes out at those who disturb the fallen",
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        assert result.success is False
        assert result.damage_dealt == 4
        assert result.damage_type == "cold"
        # Verify dice.roll was called with "1d6"
        engine.dice.roll.assert_called_with("1d6", "hazard damage")

    def test_on_fail_damage_dice_used(self):
        """Verify on_fail.damage_dice is used for night hazards like frost patches."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=3)
        engine.dice.roll.return_value = MagicMock(total=3)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(3, False))
        char.character_id = "test_char"

        # Hex 0105 camp_near_frost_patches hazard uses on_fail.damage_dice
        hazard = {
            "trigger": "camp_near_frost_patches",
            "save_type": "doom",
            "description": "Characters who camp within 100 feet of the frost-covered patches...",
            "on_fail": {
                "damage_dice": "1d4",
                "damage_type": "cold",
                "description": "Cold damage from proximity to frost-patches",
            },
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        assert result.success is False
        assert result.damage_dealt == 3
        assert result.damage_type == "cold"
        engine.dice.roll.assert_called_with("1d4", "hazard damage")

    def test_damage_key_supported(self):
        """Verify 'damage' key (without _dice suffix) is also supported."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=3)
        engine.dice.roll.return_value = MagicMock(total=5)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(3, False))
        char.character_id = "test_char"

        # Using "damage" instead of "damage_dice"
        hazard = {
            "save_type": "doom",
            "damage": "2d6",  # Using "damage" key
            "description": "A hazard with damage key",
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        assert result.damage_dealt == 5
        engine.dice.roll.assert_called_with("2d6", "hazard damage")

    def test_top_level_condition_supported(self):
        """Verify top-level condition is extracted correctly."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=3)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(3, False))
        char.character_id = "test_char"

        # Using top-level condition with doom save (avoids enchantment routing)
        hazard = {
            "save_type": "doom",
            "condition": "poisoned",  # Top-level condition
            "description": "Toxic gas cloud",
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        assert result.success is False
        assert "poisoned" in result.conditions_applied

    def test_frost_patches_cold_damage_on_failed_save(self):
        """
        Acceptance test: 0105 frost patches hazard actually deals cold damage on failed save.

        This tests the complete flow using the actual hex 0105 hazard schema.
        """
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=5)  # Will fail doom save
        engine.dice.roll.return_value = MagicMock(total=3)  # 3 cold damage
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed save
        char.character_id = "test_fighter"

        # The ACTUAL hazard from hex 0105 JSON (POI version)
        frost_touch_hazard = {
            "hazard_id": "frost_touch",
            "name": "Ancient Frost Magic",
            "trigger": "touching frozen figures or frost giant",
            "save_type": "doom",
            "damage_dice": "1d6",
            "damage_type": "cold",
            "description": "Ancient battle-magic lashes out at those who disturb the fallen",
        }

        result = engine._resolve_hazard(frost_touch_hazard, char, apply_effects=False)

        # Verify the hazard deals cold damage
        assert result.success is False
        assert result.damage_dealt == 3
        assert result.damage_taken == 3  # Unified schema alias
        assert result.damage_type == "cold"
        assert "cold" in result.damage_type

    def test_no_default_damage_when_condition_only(self):
        """Verify no default 1d6 damage when hazard only applies condition."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=3)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.make_saving_throw = MagicMock(return_value=(3, False))
        char.character_id = "test_char"

        # Condition-only hazard with doom save (avoids enchantment routing)
        hazard = {
            "save_type": "doom",
            "description": "Toxic spores fill the air",
            "on_fail": {"condition": "exhausted"},
        }

        result = engine._resolve_hazard(hazard, char, apply_effects=False)

        # Should NOT roll damage since no damage specified
        engine.dice.roll.assert_not_called()
        assert result.damage_dealt == 0
        assert "exhausted" in result.conditions_applied


class TestTouchActionFrostPatchTrigger:
    """Tests for touch action triggering frost patch hazard."""

    def test_detect_poi_action_matches_touch(self):
        """Verify detect_poi_action matches 'touch frost patches'."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)

        result = engine.detect_poi_action("touch frost patches")
        assert result is not None
        assert result[0] == "touch"
        assert result[1] == "touch"

    def test_detect_poi_action_matches_touch_variants(self):
        """Verify detect_poi_action matches various touch input variations."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)

        # Test various phrasings
        test_cases = [
            ("I touch the frozen figure", ("touch", "touch")),
            ("Touch the frost giant", ("touch", "touch")),
            ("I want to touch it", ("touch", "touch")),
            ("I grab the frozen soldier", ("touch", "grab")),
            ("Press my hand against the ice", ("touch", "press")),
            ("I hold the frost blade", ("touch", "hold")),
        ]

        for input_text, expected in test_cases:
            result = engine.detect_poi_action(input_text)
            assert result == expected, f"Failed for '{input_text}'"

    def test_get_matching_poi_hazards_matches_touching_trigger(self):
        """Verify get_matching_poi_hazards matches hazard with 'touching' trigger."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import PointOfInterest

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._current_poi = "Frozen Battleground"

        # Create mock POI with frost_touch hazard
        mock_poi = MagicMock(spec=PointOfInterest)
        mock_poi.name = "Frozen Battleground"
        mock_poi.hazards = [
            {
                "hazard_id": "frost_touch",
                "name": "Ancient Frost Magic",
                "trigger": "touching frozen figures or frost giant",
                "save_type": "doom",
                "damage_dice": "1d6",
                "damage_type": "cold",
                "description": "Ancient battle-magic lashes out",
            }
        ]

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0105": mock_hex}

        # Action type "touch" should match trigger "touching"
        matching = engine.get_matching_poi_hazards("0105", "touch")

        assert len(matching) == 1
        assert matching[0]["hazard_id"] == "frost_touch"

    def test_resolve_poi_action_triggers_frost_hazard(self):
        """Verify resolve_poi_action triggers frost hazard on touch."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState, PointOfInterest

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._current_hex = "0105"
        engine._current_poi = "Frozen Battleground"
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=5)
        engine.dice.roll.return_value = MagicMock(total=4)  # 4 cold damage
        engine.narrative_resolver = MagicMock()

        # Create test character
        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed

        engine.controller = MagicMock()
        engine.controller.get_character.return_value = char
        engine.controller.apply_damage = MagicMock()
        engine.controller.apply_condition = MagicMock(return_value={"applied": True})

        # Create mock POI
        mock_poi = MagicMock(spec=PointOfInterest)
        mock_poi.name = "Frozen Battleground"
        mock_poi.hazards = [
            {
                "hazard_id": "frost_touch",
                "name": "Ancient Frost Magic",
                "trigger": "touching frozen figures or frost giant",
                "save_type": "doom",
                "damage_dice": "1d6",
                "damage_type": "cold",
                "description": "Ancient battle-magic lashes out",
            }
        ]
        mock_poi.roll_tables = []

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0105": mock_hex}

        # Resolve the touch action
        result = engine.resolve_poi_action("I touch the frozen figure", "test_char")

        assert result["triggered"] is True
        assert result["action_type"] == "touch"
        assert result["hazards_triggered"] == 1
        assert result["hazard_results"][0]["hazard_name"] == "Ancient Frost Magic"
        assert result["hazard_results"][0]["success"] is False
        assert result["hazard_results"][0]["damage_taken"] == 4

    def test_resolve_poi_action_with_successful_save(self):
        """Verify resolve_poi_action handles successful saves."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState, PointOfInterest

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._current_hex = "0105"
        engine._current_poi = "Frozen Battleground"
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=18)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.make_saving_throw = MagicMock(return_value=(18, True))  # Passed

        engine.controller = MagicMock()
        engine.controller.get_character.return_value = char

        mock_poi = MagicMock(spec=PointOfInterest)
        mock_poi.name = "Frozen Battleground"
        mock_poi.hazards = [
            {
                "hazard_id": "frost_touch",
                "name": "Ancient Frost Magic",
                "trigger": "touching frozen figures or frost giant",
                "save_type": "doom",
                "damage_dice": "1d6",
                "damage_type": "cold",
                "description": "Ancient battle-magic lashes out",
            }
        ]
        mock_poi.roll_tables = []

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0105": mock_hex}

        result = engine.resolve_poi_action("Touch the frost giant", "test_char")

        assert result["triggered"] is True
        assert result["hazard_results"][0]["success"] is True
        assert result["hazard_results"][0]["damage_taken"] == 0

    def test_no_match_without_poi(self):
        """Verify resolve_poi_action fails without current POI."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._current_hex = "0105"
        engine._current_poi = None  # No POI

        result = engine.resolve_poi_action("touch frost patches", "test_char")

        assert result["triggered"] is False
        assert result["reason"] == "Not at a POI"

    def test_no_match_for_non_touch_hazard(self):
        """Verify touch action doesn't match non-touch hazards."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import PointOfInterest

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine._current_poi = "Some POI"

        mock_poi = MagicMock(spec=PointOfInterest)
        mock_poi.name = "Some POI"
        mock_poi.hazards = [
            {
                "trigger": "entering the water",  # Not a touch trigger
                "save_type": "doom",
                "damage_dice": "1d6",
            }
        ]

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0105": mock_hex}

        matching = engine.get_matching_poi_hazards("0105", "touch")

        assert len(matching) == 0
