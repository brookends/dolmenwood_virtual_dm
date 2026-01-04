"""
Tests for hex 0107 (The Weeping Woman) hazard mechanics.

These tests verify that full moon triggers, enchantment chains,
and fairy magic hazards work correctly for hex 0107's specific gameplay.
"""

import pytest
from unittest.mock import MagicMock


class TestFullMoonTrigger:
    """Tests for full moon night hazard triggers."""

    def test_full_moon_trigger_only_fires_on_full_moon(self):
        """Verify full_moon trigger only fires when is_full_moon is True."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)  # NOT full moon
        engine._is_winter = MagicMock(return_value=False)
        engine.dice = MagicMock()

        # Create mock hex with full_moon trigger hazard (from hex 0107)
        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "description": "The moon's light draws you to dance",
                "on_fail": {"condition": "moon_dance_compulsion"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should NOT trigger when not full moon
        results = engine.process_night_hazards("0107")
        assert len(results) == 0

    def test_full_moon_trigger_fires_on_full_moon(self):
        """Verify full_moon trigger fires when is_full_moon is True."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=10)
        engine.narrative_resolver = MagicMock()
        engine._current_hex = "0107"  # Required for chain hazard processing
        engine._current_poi = None  # No POI

        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.name = "Test Character"
        char.make_saving_throw = MagicMock(return_value=(5, False))  # Failed save

        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = [char]
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=True)  # Full moon!
        engine._is_winter = MagicMock(return_value=False)

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "description": "The moon's light draws you to dance",
                "on_fail": {"condition": "compelled"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should trigger on full moon
        results = engine.process_night_hazards("0107")
        assert len(results) == 1
        assert results[0]["character_id"] == "test_char"

    def test_full_moon_trigger_requires_night(self):
        """Verify full_moon trigger requires it to be night."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine._is_night = MagicMock(return_value=False)  # NOT night (daytime)
        engine._is_full_moon = MagicMock(return_value=True)  # Full moon
        engine._is_winter = MagicMock(return_value=False)
        engine.dice = MagicMock()

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "on_fail": {"condition": "compelled"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should NOT trigger during day even on full moon
        results = engine.process_night_hazards("0107")
        assert len(results) == 0

    def test_full_moon_excluded_from_generic_night_trigger(self):
        """Verify full_moon hazard does NOT fire on regular night triggers."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = []
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)  # Regular night
        engine._is_winter = MagicMock(return_value=False)
        engine.dice = MagicMock()

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            # Regular night hazard
            {
                "trigger": "night",
                "save_type": "spell",
                "description": "Night whispers",
                "on_fail": {"condition": "frightened"},
            },
            # Full moon only hazard
            {
                "trigger": "full_moon",
                "save_type": "spell",
                "description": "Moon compulsion",
                "on_fail": {"condition": "compelled"},
            },
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Mock _resolve_hazard to track which hazards are called
        resolved_triggers = []

        def track_resolve(hazard, char, apply_effects=True):
            resolved_triggers.append(hazard.get("trigger"))
            return MagicMock(
                success=True,
                conditions_applied=[],
                damage_taken=0,
                apply_damage=[],
                apply_conditions=[],
            )

        # Add a mock character
        char = MagicMock()
        char.character_id = "test"
        char.name = "Test"
        engine.controller.get_all_characters.return_value = [char]
        engine._resolve_hazard = track_resolve

        results = engine.process_night_hazards("0107")

        # Only "night" trigger should fire, not "full_moon"
        assert "night" in resolved_triggers
        assert "full_moon" not in resolved_triggers


class TestHex0107NightNearWeepingWoman:
    """Tests for night_near_weeping_woman trigger."""

    def test_night_near_weeping_woman_triggers_at_night(self):
        """Verify night_near_weeping_woman trigger works at night."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.dice.roll_d20.return_value = MagicMock(total=10)
        engine.narrative_resolver = MagicMock()

        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.name = "Test Character"
        char.make_saving_throw = MagicMock(return_value=(5, False))

        engine.controller = MagicMock()
        engine.controller.get_all_characters.return_value = [char]
        engine._is_night = MagicMock(return_value=True)
        engine._is_full_moon = MagicMock(return_value=False)
        engine._is_winter = MagicMock(return_value=False)
        engine._hex_has_feature = MagicMock(return_value=True)  # Near weeping woman

        mock_procedural = MagicMock()
        mock_procedural.night_hazards = [
            {
                "trigger": "sleep_near_weeping_woman",
                "save_type": "spell",
                "description": "Dreams of the fairy woman haunt your sleep",
                "on_fail": {"condition": "enchanted_reverie"},
            }
        ]

        mock_hex = MagicMock()
        mock_hex.procedural = mock_procedural
        engine._hex_data = {"0107": mock_hex}

        # Should trigger when sleeping near the feature
        results = engine.process_night_hazards("0107", activity="sleeping")
        assert len(results) == 1


class TestDanceChainIntegration:
    """
    Integration tests for the full dance chain:
    drink tears → enchanted_hearing → compelled_dancing → magical_sleep → fairy_marked
    """

    def test_enchanted_hearing_triggers_compelled_dancing_chain(self):
        """
        When enchanted_hearing condition is applied, it should automatically
        trigger the enchanted_reverie hazard which applies compelled_dancing.
        """
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState, PointOfInterest

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.dice = MagicMock()
        engine.narrative_resolver = MagicMock()
        engine._current_hex = "0107"
        engine._current_poi = "The Weeping Woman"

        # Create a character with apply_condition mock
        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.name = "Test Adventurer"

        # Controller that returns our character
        engine.controller = MagicMock()
        engine.controller.apply_condition.return_value = {"applied": True}

        # Create POI with the hazard chain from 0107
        poi = MagicMock(spec=PointOfInterest)
        poi.name = "The Weeping Woman"
        poi.hazards = [
            {
                "hazard_id": "enchanted_reverie",
                "name": "The Enchanted Reverie",
                "trigger": "hearing the music",
                "automatic": True,
                "condition_required": "enchanted_hearing",
                "effect": {
                    "condition": "compelled_dancing",
                    "duration": "until dawn",
                    "ends_at_time_of_day": "dawn",
                },
            }
        ]
        poi.get_automatic_hazards_for_condition = MagicMock(
            return_value=[poi.hazards[0]]
        )

        mock_hex = MagicMock()
        mock_hex.points_of_interest = [poi]
        engine._hex_data = {"0107": mock_hex}

        # Trigger chain hazards for enchanted_hearing
        results = engine._trigger_chain_hazards(char, "enchanted_hearing")

        # Should have triggered the enchanted_reverie hazard
        assert len(results) == 1
        assert results[0]["hazard_name"] == "The Enchanted Reverie"
        assert results[0]["triggered_by_condition"] == "enchanted_hearing"
        assert "compelled_dancing" in results[0]["conditions_applied"]

    def test_automatic_hazard_resolution_no_save(self):
        """Automatic hazards should apply without requiring a save."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from src.data_models import CharacterState

        engine = HexCrawlEngine.__new__(HexCrawlEngine)

        char = MagicMock(spec=CharacterState)
        char.character_id = "test_char"
        char.name = "Test Adventurer"
        char.make_saving_throw = MagicMock()  # Should not be called

        # Automatic hazard from 0107
        automatic_hazard = {
            "hazard_id": "dawn_slumber",
            "name": "Dawn Slumber",
            "automatic": True,
            "condition_required": "compelled_dancing",
            "effect": {
                "condition": "magical_sleep",
                "duration": "8 hours",
            },
        }

        result = engine._resolve_automatic_hazard(automatic_hazard, char)

        # Should not have called make_saving_throw
        char.make_saving_throw.assert_not_called()
        # Should have applied the condition
        assert result.success is False  # False = effect applies
        assert "magical_sleep" in result.conditions_applied

    def test_condition_end_transition_chains_conditions(self):
        """
        When compelled_dancing ends at dawn, it should:
        1. Remove compelled_dancing
        2. Apply healing (1d6 HP)
        3. Apply magical_sleep condition
        """
        from src.game_state.global_controller import GlobalController
        from src.data_models import CharacterState, Condition, ConditionType, TimeOfDay

        controller = GlobalController()

        # Create a character with compelled_dancing that ends at dawn
        char = CharacterState(
            character_id="test_char",
            name="Test Dancer",
            character_class="fighter",
            level=1,
            hp_current=5,  # Below max to test healing
            hp_max=20,
            armor_class=10,
            base_speed=40,
            ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        )

        # Create dancing condition with dawn expiry
        dancing_condition = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            duration_turns=None,  # No turn duration, uses time of day
            ends_at_time_of_day="dawn",
            leads_to_condition="magical_sleep",
            healing_on_end="1d6",
        )
        char.conditions.append(dancing_condition)

        controller.add_character(char)

        # Process time-of-day condition ends at DAWN
        events = controller._process_time_of_day_condition_ends(TimeOfDay.DAWN)

        # Should have one event
        assert len(events) == 1
        event = events[0]
        assert event["character_id"] == "test_char"
        assert event["condition"] == "compelled_dancing"
        assert event["ended_at"] == "dawn"
        assert event["chained_to"] == "magical_sleep"

        # Character should now have magical_sleep instead of compelled_dancing
        current_conditions = [c.condition_type for c in char.conditions]
        assert ConditionType.COMPELLED_DANCING not in current_conditions
        assert ConditionType.MAGICAL_SLEEP in current_conditions

    def test_full_dance_chain_from_drink_to_fairy_marked(self):
        """
        End-to-end test of the full dance chain:
        1. Drink tears (fail save) → enchanted_hearing
        2. enchanted_hearing → compelled_dancing (automatic)
        3. Dawn arrives → compelled_dancing ends → magical_sleep + healing
        4. 8 hours pass → magical_sleep ends → fairy_marked

        This test verifies the condition chain metadata is correct.
        """
        from src.data_models import Condition, ConditionType, TimeOfDay

        # Step 1: Create initial enchanted_hearing condition (from failed save)
        enchanted_hearing = Condition(
            condition_type=ConditionType.ENCHANTED_HEARING,
            source="The Woman's Tears",
            leads_to_condition="compelled_dancing",
        )

        # Verify leads_to is set
        transition = enchanted_hearing.get_end_transition()
        assert transition is not None
        assert transition.get("next_condition") == "compelled_dancing"

        # Step 2: Create compelled_dancing that ends at dawn
        compelled_dancing = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            ends_at_time_of_day="dawn",
            leads_to_condition="magical_sleep",
            healing_on_end="1d6",
        )

        # Verify dawn expiry
        assert compelled_dancing.should_end_at_time(TimeOfDay.DAWN)
        assert not compelled_dancing.should_end_at_time(TimeOfDay.MIDDAY)

        # Verify transition to magical_sleep with healing
        transition = compelled_dancing.get_end_transition()
        assert transition is not None
        assert transition.get("next_condition") == "magical_sleep"
        assert transition.get("healing") == "1d6"

        # Step 3: Create magical_sleep (8 hours = 48 turns)
        magical_sleep = Condition(
            condition_type=ConditionType.MAGICAL_SLEEP,
            source="Dawn Slumber",
            duration_turns=48,  # 8 hours
            leads_to_condition="fairy_marked",
        )

        # Verify 48 turn duration
        assert magical_sleep.duration_turns == 48

        # Verify transition to fairy_marked
        transition = magical_sleep.get_end_transition()
        assert transition is not None
        assert transition.get("next_condition") == "fairy_marked"

        # Step 4: Create fairy_marked (6 months)
        fairy_marked = Condition(
            condition_type=ConditionType.FAIRY_MARKED,
            source="neveryon",
            duration_days=180,  # 6 months
        )

        # Verify 6 month duration
        assert fairy_marked.duration_days == 180

    def test_poi_get_automatic_hazards_for_condition(self):
        """Test PointOfInterest.get_automatic_hazards_for_condition method."""
        from src.data_models import PointOfInterest

        # Create POI with hazards from 0107
        poi = PointOfInterest(
            name="The Weeping Woman",
            poi_type="natural_formation",
            description="A weeping stone figure",
            hazards=[
                {
                    "hazard_id": "drinking_tears",
                    "name": "The Woman's Tears",
                    "trigger": "drinking the water",
                    "save_type": "spell",
                    "on_fail": {"condition": "enchanted_hearing"},
                },
                {
                    "hazard_id": "enchanted_reverie",
                    "name": "The Enchanted Reverie",
                    "automatic": True,
                    "condition_required": "enchanted_hearing",
                    "effect": {"condition": "compelled_dancing"},
                },
                {
                    "hazard_id": "dawn_slumber",
                    "name": "Dawn Slumber",
                    "automatic": True,
                    "condition_required": "compelled_dancing",
                    "effect": {"condition": "magical_sleep"},
                },
                {
                    "hazard_id": "neveryon_dreams",
                    "name": "Dreams of Neveryon",
                    "automatic": True,
                    "condition_required": "magical_sleep",
                    "effect": {"condition": "fairy_marked"},
                },
            ],
        )

        # Get automatic hazards for enchanted_hearing
        hearing_hazards = poi.get_automatic_hazards_for_condition("enchanted_hearing")
        assert len(hearing_hazards) == 1
        assert hearing_hazards[0]["hazard_id"] == "enchanted_reverie"

        # Get automatic hazards for compelled_dancing
        dancing_hazards = poi.get_automatic_hazards_for_condition("compelled_dancing")
        assert len(dancing_hazards) == 1
        assert dancing_hazards[0]["hazard_id"] == "dawn_slumber"

        # Non-automatic hazard should not be returned
        drinking_hazards = poi.get_automatic_hazards_for_condition("some_condition")
        assert len(drinking_hazards) == 0


class TestWaitUntilDawnAction:
    """Tests for the wait_until_dawn action and its integration with the dance chain."""

    def test_wait_until_dawn_action_registered(self):
        """Verify wilderness:wait_until_dawn action is registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("wilderness:wait_until_dawn")

        assert spec is not None
        assert spec.label == "Wait until dawn"
        assert spec.requires_state == "wilderness_travel"
        assert spec.executor is not None

    def test_advance_to_time_of_day_reaches_dawn(self):
        """Verify advance_to_time_of_day() reaches DAWN and returns correct info."""
        from src.game_state.global_controller import GlobalController
        from src.data_models import TimeOfDay

        controller = GlobalController()

        # Set time to night (e.g., 22:00)
        controller.time_tracker.game_time.hour = 22

        result = controller.advance_to_time_of_day(TimeOfDay.DAWN, reason="waiting")

        assert result["success"] is True
        assert result["time_of_day"] == "dawn"
        assert result["hours_passed"] > 0

    def test_check_time_of_day_expirations_processes_dawn_conditions(self):
        """Verify _check_time_of_day_expirations processes dawn conditions."""
        from src.game_state.global_controller import GlobalController
        from src.data_models import CharacterState, Condition, ConditionType, TimeOfDay

        controller = GlobalController()

        # Create a character with compelled_dancing that ends at dawn
        char = CharacterState(
            character_id="test_dancer",
            name="Test Dancer",
            character_class="fighter",
            level=1,
            hp_current=15,
            hp_max=20,
            armor_class=10,
            base_speed=40,
            ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        )

        # Add dancing condition with dawn expiry and chain to magical_sleep
        dancing = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            ends_at_time_of_day="dawn",
            leads_to_condition="magical_sleep",
            healing_on_end="1d6",
        )
        char.conditions.append(dancing)
        controller.add_character(char)

        # Directly call the expiration check at DAWN
        expirations = controller._check_time_of_day_expirations(TimeOfDay.DAWN)

        # Verify condition expired
        assert len(expirations) >= 1
        expired = expirations[0]
        assert expired["condition"] == "compelled_dancing"
        assert expired["chained_to"] == "magical_sleep"

        # Verify character now has magical_sleep instead of dancing
        current_conditions = [c.condition_type for c in char.conditions]
        assert ConditionType.COMPELLED_DANCING not in current_conditions
        assert ConditionType.MAGICAL_SLEEP in current_conditions

    def test_dancing_block_suggests_wait_until_dawn(self):
        """Verify blocked action suggests wait_until_dawn when dancing."""
        from src.narrative.narrative_resolver import NarrativeResolver
        from src.narrative.intent_parser import ParsedIntent, ActionType, ActionCategory
        from src.data_models import CharacterState, Condition, ConditionType

        resolver = NarrativeResolver()

        char = CharacterState(
            character_id="test_char",
            name="Test Character",
            character_class="fighter",
            level=1,
            hp_current=20,
            hp_max=20,
            armor_class=10,
            base_speed=40,
            ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        )

        # Add dancing condition with dawn expiry
        dancing = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            ends_at_time_of_day="dawn",
        )
        char.conditions.append(dancing)

        # Try to attack (which should be blocked by dancing)
        parsed = ParsedIntent(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            raw_input="I attack the monster",
        )

        result = resolver._check_condition_restrictions(char, parsed)

        # Should be blocked with suggestion
        assert result is not None
        assert result["condition_type"] == "compelled_dancing"
        assert result["suggested_action"] == "wilderness:wait_until_dawn"
        assert result["suggested_action_label"] == "Wait until dawn"

    def test_resolution_result_fields_exist(self):
        """Verify ResolutionResult has suggested_action fields for blocked actions."""
        from src.narrative.narrative_resolver import ResolutionResult, ResolutionType

        # Create a result that would be returned when blocked by dancing
        result = ResolutionResult(
            success=False,
            resolution_type=ResolutionType.AUTO_FAIL,
            description="You cannot stop dancing to attack.",
            narrative_hints=["struggles against the condition"],
            blocked_by_condition="compelled_dancing",
            suggested_action="wilderness:wait_until_dawn",
            suggested_action_label="Wait until dawn",
        )

        # Verify fields are set correctly
        assert result.success is False
        assert result.blocked_by_condition == "compelled_dancing"
        assert result.suggested_action == "wilderness:wait_until_dawn"
        assert result.suggested_action_label == "Wait until dawn"
