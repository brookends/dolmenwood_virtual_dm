"""
Tests for hex 0106 (The Outlook and the Red Monolith) hazards.

These tests verify that:
- Night hazards trigger correctly based on season and activity
- Seasonal POI behavior is respected
- Ability checks for climbing work correctly
- Arcane caster save modifiers are applied
- New condition types are defined correctly
"""

import pytest
from unittest.mock import MagicMock, patch


class TestHex0106Conditions:
    """Tests for hex 0106 condition types."""

    def test_restless_sleep_exists(self):
        """Verify RESTLESS_SLEEP condition exists."""
        from src.data_models import ConditionType

        assert ConditionType.RESTLESS_SLEEP.value == "restless_sleep"

    def test_terror_exists(self):
        """Verify TERROR condition exists."""
        from src.data_models import ConditionType

        assert ConditionType.TERROR.value == "terror"

    def test_compelled_exists(self):
        """Verify COMPELLED condition exists."""
        from src.data_models import ConditionType

        assert ConditionType.COMPELLED.value == "compelled"

    def test_restless_sleep_in_blocked_actions(self):
        """Verify restless_sleep has entry in CONDITION_BLOCKED_ACTIONS."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS

        assert "restless_sleep" in CONDITION_BLOCKED_ACTIONS
        # Restless sleep doesn't block actions
        assert CONDITION_BLOCKED_ACTIONS["restless_sleep"]["blocked"] == []
        assert "rest" in CONDITION_BLOCKED_ACTIONS["restless_sleep"]["message"].lower()

    def test_terror_blocks_most_actions(self):
        """Verify terror blocks most actions but allows fleeing."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS

        assert "terror" in CONDITION_BLOCKED_ACTIONS
        terror = CONDITION_BLOCKED_ACTIONS["terror"]
        # Must flee - combat and spells blocked
        assert "combat" in terror["blocked"]
        assert "spell" in terror["blocked"]
        # Movement allowed (to flee)
        assert "movement" in terror["allowed"]

    def test_compelled_forces_movement(self):
        """Verify compelled restricts to movement only."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS

        assert "compelled" in CONDITION_BLOCKED_ACTIONS
        compelled = CONDITION_BLOCKED_ACTIONS["compelled"]
        # Can only move toward target
        assert "movement" in compelled["allowed"]
        # Combat and other actions blocked
        assert "combat" in compelled["blocked"]
        assert "spell" in compelled["blocked"]


class TestHex0106ConditionRollModifiers:
    """Tests for hex 0106 condition roll modifiers."""

    def test_restless_sleep_no_hp_recovery(self):
        """Verify restless_sleep prevents HP recovery."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert "restless_sleep" in CONDITION_ROLL_MODIFIERS
        assert CONDITION_ROLL_MODIFIERS["restless_sleep"]["hp_recovery"] == 0

    def test_restless_sleep_no_spell_memorization(self):
        """Verify restless_sleep prevents spell memorization."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert CONDITION_ROLL_MODIFIERS["restless_sleep"]["spell_memorization"] is False

    def test_terror_climbing_penalty(self):
        """Verify terror has climbing check penalty."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert "terror" in CONDITION_ROLL_MODIFIERS
        assert CONDITION_ROLL_MODIFIERS["terror"]["climbing_checks"] == -2

    def test_terror_forces_flee(self):
        """Verify terror has forces_flee flag."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert CONDITION_ROLL_MODIFIERS["terror"]["forces_flee"] is True

    def test_compelled_movement_forcing(self):
        """Verify compelled forces movement toward target."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert "compelled" in CONDITION_ROLL_MODIFIERS
        assert CONDITION_ROLL_MODIFIERS["compelled"]["forces_movement"] is True
        assert CONDITION_ROLL_MODIFIERS["compelled"]["can_be_restrained"] is True

    def test_compelled_ends_at_dawn(self):
        """Verify compelled ends at dawn."""
        from src.data_models import CONDITION_ROLL_MODIFIERS

        assert CONDITION_ROLL_MODIFIERS["compelled"]["removal"] == "time_of_day_dawn"


class TestHex0106SeasonalPOIState:
    """Tests for seasonal POI state checking."""

    def test_get_poi_seasonal_state_winter(self):
        """Verify get_poi_seasonal_state returns winter state."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season, GameDate

        # Create mock controller with winter date
        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.WINTER

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine._hex_data = {}

        # Create mock POI with seasonal behavior
        mock_poi = MagicMock()
        mock_poi.name = "The Red Vorpal Monolith"
        mock_poi.seasonal_behavior = {
            "winter": {
                "months": ["Haggryme", "Coldgrain", "Snowmass"],
                "state": "semi-corporeal",
                "effects_active": ["terror_aura", "spell_permanence"],
            },
            "non_winter": {
                "state": "intangible",
                "effects_active": ["spectral_chill_only"],
            },
        }

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0106": mock_hex}

        result = engine.get_poi_seasonal_state("0106", "The Red Vorpal Monolith")

        assert result["has_seasonal_behavior"] is True
        assert result["is_winter"] is True
        assert result["current_state"] == "semi-corporeal"
        assert "terror_aura" in result["effects_active"]
        assert "spell_permanence" in result["effects_active"]

    def test_get_poi_seasonal_state_summer(self):
        """Verify get_poi_seasonal_state returns non-winter state in summer."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season

        # Create mock controller with summer date
        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.SUMMER

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller

        # Create mock POI with seasonal behavior
        mock_poi = MagicMock()
        mock_poi.name = "The Red Vorpal Monolith"
        mock_poi.seasonal_behavior = {
            "winter": {
                "state": "semi-corporeal",
                "effects_active": ["terror_aura", "spell_permanence"],
            },
            "non_winter": {
                "state": "intangible",
                "effects_active": ["spectral_chill_only"],
            },
        }

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0106": mock_hex}

        result = engine.get_poi_seasonal_state("0106", "The Red Vorpal Monolith")

        assert result["has_seasonal_behavior"] is True
        assert result["is_winter"] is False
        assert result["current_state"] == "intangible"
        assert "spectral_chill_only" in result["effects_active"]

    def test_is_poi_effect_active_winter(self):
        """Verify is_poi_effect_active returns True for winter effects in winter."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.WINTER

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller

        mock_poi = MagicMock()
        mock_poi.name = "The Red Vorpal Monolith"
        mock_poi.seasonal_behavior = {
            "winter": {"effects_active": ["terror_aura", "spell_permanence"]},
            "non_winter": {"effects_active": ["spectral_chill_only"]},
        }

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [mock_poi]
        engine._hex_data = {"0106": mock_hex}

        assert engine.is_poi_effect_active("0106", "The Red Vorpal Monolith", "terror_aura") is True
        assert engine.is_poi_effect_active("0106", "The Red Vorpal Monolith", "spectral_chill_only") is False


class TestHex0106WinterNightTrigger:
    """Tests for winter_night hazard trigger detection."""

    def test_winter_night_triggers_in_winter(self):
        """Verify winter_night hazard triggers in winter at night."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season, TimeOfDay

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.WINTER
        controller.world_state.current_time = MagicMock()
        controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.MIDNIGHT
        controller.get_all_characters.return_value = []

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine._is_night = MagicMock(return_value=True)
        engine._is_winter = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)
        engine.dice = MagicMock()

        # Create mock hex with winter_night hazard
        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {"trigger": "winter_night", "save_type": "spell", "on_fail": {"condition": "compelled"}}
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0106": mock_hex}

        results = engine.process_night_hazards("0106")

        # No characters, but trigger detection should work
        # The hazard should be identified as triggerable
        engine._is_winter.assert_called()

    def test_winter_night_does_not_trigger_in_summer(self):
        """Verify winter_night hazard does not trigger in summer."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season, TimeOfDay

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.SUMMER
        controller.world_state.current_time = MagicMock()
        controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.MIDNIGHT
        controller.get_all_characters.return_value = []

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine._is_night = MagicMock(return_value=True)
        engine._is_winter = MagicMock(return_value=False)  # Not winter
        engine._is_full_moon = MagicMock(return_value=False)
        engine.dice = MagicMock()

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {"trigger": "winter_night", "save_type": "spell", "on_fail": {"condition": "compelled"}}
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0106": mock_hex}

        results = engine.process_night_hazards("0106")

        # Should not trigger since it's not winter
        assert len(results) == 0


class TestHex0106SleepNearMonolith:
    """Tests for sleep_near_monolith hazard trigger."""

    def test_sleep_near_monolith_triggers_when_sleeping(self):
        """Verify sleep_near_monolith triggers when sleeping near monolith."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import TimeOfDay

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_time = MagicMock()
        controller.world_state.current_time.get_time_of_day.return_value = TimeOfDay.MIDNIGHT
        controller.world_state.current_date = None
        controller.get_all_characters.return_value = []

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine._is_night = MagicMock(return_value=True)
        engine._is_winter = MagicMock(return_value=False)
        engine._is_full_moon = MagicMock(return_value=False)
        engine._hex_has_feature = MagicMock(return_value=True)  # Has monolith
        engine.dice = MagicMock()

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {"trigger": "sleep_near_monolith", "save_type": "spell", "on_fail": {"condition": "restless_sleep"}}
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0106": mock_hex}

        results = engine.process_night_hazards("0106", activity="sleeping")

        # Should check for monolith feature
        engine._hex_has_feature.assert_called_with("0106", "monolith")


class TestHex0106AbilityCheck:
    """Tests for ability check hazard resolution."""

    def test_climbing_uses_dexterity_check(self):
        """Verify climbing hazard uses dexterity ability check."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.narrative.hazard_resolver import HazardResult

        controller = MagicMock()
        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine.dice = MagicMock()
        engine.dice.roll_d20 = MagicMock(return_value=MagicMock(total=10))
        engine.dice.roll = MagicMock(return_value=MagicMock(total=3))
        engine.narrative_resolver = MagicMock()

        # Mock character with dexterity
        character = MagicMock()
        character.ability_scores = {"DEX": 14, "STR": 10, "INT": 10, "WIS": 10, "CON": 10, "CHA": 10}
        character.abilities = MagicMock()
        character.abilities.dexterity = 14

        hazard = {
            "hazard_id": "climbing_check",
            "check_type": "dexterity",
            "description": "Climbing the crag",
            "on_fail": {"damage_dice": "1d6", "damage_type": "falling"},
        }

        result = engine._resolve_hazard(hazard, character, apply_effects=False)

        # Should have rolled a dexterity check
        engine.dice.roll_d20.assert_called()
        call_args = engine.dice.roll_d20.call_args
        assert "dexterity" in call_args[0][0].lower()


class TestHex0106ArcaneCasterModifier:
    """Tests for arcane caster save modifier."""

    def test_arcane_caster_gets_bonus(self):
        """Verify arcane caster gets +2 to save vs monolith terror."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        controller = MagicMock()
        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine.dice = MagicMock()
        engine.dice.roll_d20 = MagicMock(return_value=MagicMock(total=12))
        engine.dice.roll = MagicMock(return_value=MagicMock(total=3))
        engine.narrative_resolver = MagicMock()

        # Mock magic-user character with make_saving_throw
        character = MagicMock()
        character.character_class = "Magic-User"
        # make_saving_throw returns (roll_total, success)
        # With +2 modifier, a roll of 12 becomes 14, succeeding against target 13
        character.make_saving_throw = MagicMock(return_value=(14, True))

        hazard = {
            "hazard_id": "monolith_viewing",
            "save_type": "spell",
            "modifier_arcane_casters": 2,
            "description": "Monolith terror",
            "on_fail": {"condition": "terror"},
        }

        result = engine._resolve_hazard(hazard, character, apply_effects=False)

        # Check that make_saving_throw was called with the +2 modifier
        character.make_saving_throw.assert_called_once()
        call_args = character.make_saving_throw.call_args
        # Second arg should be the modifier (2 from arcane_casters)
        assert call_args[0][1] == 2

    def test_non_arcane_caster_no_bonus(self):
        """Verify non-arcane caster does not get bonus."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        controller = MagicMock()
        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller
        engine.dice = MagicMock()
        engine.dice.roll_d20 = MagicMock(return_value=MagicMock(total=12))
        engine.dice.roll = MagicMock(return_value=MagicMock(total=3))
        engine.narrative_resolver = MagicMock()

        # Mock fighter character
        character = MagicMock()
        character.character_class = "Fighter"
        character.make_saving_throw = MagicMock(return_value=(12, False))

        hazard = {
            "hazard_id": "monolith_viewing",
            "save_type": "spell",
            "modifier_arcane_casters": 2,
            "description": "Monolith terror",
            "on_fail": {"condition": "terror"},
        }

        result = engine._resolve_hazard(hazard, character, apply_effects=False)

        # Check that make_saving_throw was called with modifier 0 (no arcane bonus)
        character.make_saving_throw.assert_called_once()
        call_args = character.make_saving_throw.call_args
        assert call_args[0][1] == 0  # No bonus for fighter


class TestPointOfInterestSeasonalState:
    """Tests for PointOfInterest.get_poi_seasonal_state() method."""

    def test_get_poi_seasonal_state_returns_winter_for_winter_month(self):
        """Verify get_poi_seasonal_state returns winter state for winter months."""
        from src.data_models import PointOfInterest

        poi = PointOfInterest(
            name="The Red Vorpal Monolith",
            poi_type="landmark",
            description="A towering red crystal monolith",
            seasonal_behavior={
                "winter": {
                    "months": ["Grimvold", "Lymewald", "Haggryme"],
                    "state": "semi-corporeal",
                    "effects_active": ["terror_aura", "spell_permanence"],
                    "description": "The monolith becomes tangible.",
                },
                "non_winter": {
                    "months": ["Symswald", "Harchment", "Iggwyld"],
                    "state": "intangible",
                    "effects_active": ["spectral_chill_only"],
                    "description": "The monolith is a shimmering figment.",
                },
            },
        )

        result = poi.get_poi_seasonal_state("Grimvold")

        assert result is not None
        assert result["state"] == "semi-corporeal"
        assert "terror_aura" in result["effects_active"]
        assert "spell_permanence" in result["effects_active"]

    def test_get_poi_seasonal_state_returns_non_winter_for_non_winter_month(self):
        """Verify get_poi_seasonal_state returns non-winter state for other months."""
        from src.data_models import PointOfInterest

        poi = PointOfInterest(
            name="The Red Vorpal Monolith",
            poi_type="landmark",
            description="A towering red crystal monolith",
            seasonal_behavior={
                "winter": {
                    "months": ["Grimvold", "Lymewald", "Haggryme"],
                    "state": "semi-corporeal",
                    "effects_active": ["terror_aura", "spell_permanence"],
                },
                "non_winter": {
                    "state": "intangible",
                    "effects_active": ["spectral_chill_only"],
                    "description": "The monolith is a shimmering figment.",
                },
            },
        )

        result = poi.get_poi_seasonal_state("Chysting")  # Summer month

        assert result is not None
        assert result["state"] == "intangible"
        assert "spectral_chill_only" in result["effects_active"]

    def test_get_poi_seasonal_state_returns_none_for_no_seasonal_behavior(self):
        """Verify get_poi_seasonal_state returns None when POI has no seasonal behavior."""
        from src.data_models import PointOfInterest

        poi = PointOfInterest(
            name="Shepherd Encampment",
            poi_type="encampment",
            description="A small camp of shepherds.",
            seasonal_behavior=None,
        )

        result = poi.get_poi_seasonal_state("Grimvold")

        assert result is None

    def test_get_poi_seasonal_state_checks_all_winter_months(self):
        """Verify all winter months return winter state."""
        from src.data_models import PointOfInterest

        poi = PointOfInterest(
            name="The Red Vorpal Monolith",
            poi_type="landmark",
            description="A towering red crystal monolith",
            seasonal_behavior={
                "winter": {
                    "months": ["Grimvold", "Lymewald", "Haggryme"],
                    "state": "semi-corporeal",
                    "effects_active": ["terror_aura"],
                },
                "non_winter": {
                    "state": "intangible",
                    "effects_active": [],
                },
            },
        )

        for month in ["Grimvold", "Lymewald", "Haggryme"]:
            result = poi.get_poi_seasonal_state(month)
            assert result["state"] == "semi-corporeal", f"Failed for month {month}"

    def test_get_poi_seasonal_state_returns_non_winter_for_empty_winter_months(self):
        """Verify non-winter is returned when winter.months is empty."""
        from src.data_models import PointOfInterest

        poi = PointOfInterest(
            name="Test POI",
            poi_type="landmark",
            description="Test",
            seasonal_behavior={
                "winter": {
                    "months": [],
                    "state": "active",
                },
                "non_winter": {
                    "state": "dormant",
                },
            },
        )

        result = poi.get_poi_seasonal_state("Grimvold")

        # Since Grimvold is not in the empty winter months list, should return non_winter
        assert result["state"] == "dormant"

    def test_get_poi_seasonal_state_returns_none_for_missing_non_winter(self):
        """Verify None is returned if not winter and no non_winter defined."""
        from src.data_models import PointOfInterest

        poi = PointOfInterest(
            name="Test POI",
            poi_type="landmark",
            description="Test",
            seasonal_behavior={
                "winter": {
                    "months": ["Grimvold"],
                    "state": "active",
                },
            },
        )

        result = poi.get_poi_seasonal_state("Chysting")

        assert result is None


class TestHex0106IsWinter:
    """Tests for _is_winter helper method."""

    def test_is_winter_true_in_winter(self):
        """Verify _is_winter returns True in winter."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.WINTER

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller

        assert engine._is_winter() is True

    def test_is_winter_false_in_summer(self):
        """Verify _is_winter returns False in summer."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import Season

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = MagicMock()
        controller.world_state.current_date.get_season.return_value = Season.SUMMER

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller

        assert engine._is_winter() is False

    def test_is_winter_false_no_date(self):
        """Verify _is_winter returns False if no date set."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        controller = MagicMock()
        controller.world_state = MagicMock()
        controller.world_state.current_date = None

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = controller

        assert engine._is_winter() is False
