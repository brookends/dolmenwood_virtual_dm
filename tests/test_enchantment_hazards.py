"""
Tests for enchantment hazard resolution and condition handling.

These tests verify that the new enchantment hazard system works correctly
for hex 0107's dance-until-dawn gameplay and similar fairy magic effects.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import (
    CharacterState,
    Condition,
    ConditionType,
    TimeOfDay,
    DiceRoller,
)
from src.narrative.hazard_resolver import HazardResolver, HazardType, HazardResult


@pytest.fixture
def mock_character():
    """Create a mock character for testing."""
    char = MagicMock(spec=CharacterState)
    char.character_id = "test_char_1"
    char.name = "Test Hero"
    char.saving_throws = {"spell": 15, "doom": 14}
    char.get_ability_modifier = MagicMock(return_value=0)
    return char


@pytest.fixture
def hazard_resolver():
    """Create a hazard resolver with mocked dice."""
    resolver = HazardResolver()
    return resolver


class TestEnchantmentHazardResolution:
    """Tests for the enchantment hazard resolver."""

    def test_enchantment_success_on_high_roll(self, hazard_resolver, mock_character):
        """Verify successful save resists enchantment."""
        # Mock the save to succeed (return high roll)
        mock_character.make_saving_throw = MagicMock(return_value=(20, True))

        result = hazard_resolver.resolve_hazard(
            hazard_type=HazardType.ENCHANTMENT,
            character=mock_character,
            effect_name="The Woman's Tears",
            save_modifier=0,
        )

        assert result.success is True
        assert result.hazard_type == HazardType.ENCHANTMENT
        assert "Resisted" in result.description
        assert len(result.conditions_applied) == 0

    def test_enchantment_failure_applies_condition(self, hazard_resolver, mock_character):
        """Verify failed save applies the specified condition."""
        # Mock the save to fail (return low roll)
        mock_character.make_saving_throw = MagicMock(return_value=(5, False))

        result = hazard_resolver.resolve_hazard(
            hazard_type=HazardType.ENCHANTMENT,
            character=mock_character,
            effect_name="The Woman's Tears",
            condition_on_fail="enchanted_hearing",
            save_modifier=0,
        )

        assert result.success is False
        assert "enchanted_hearing" in result.conditions_applied
        assert len(result.apply_conditions) == 1
        assert result.apply_conditions[0] == ("test_char_1", "enchanted_hearing")

    def test_automatic_enchantment_no_save(self, hazard_resolver, mock_character):
        """Verify automatic effects don't allow saves."""
        # Should not call make_saving_throw for automatic effects
        mock_character.make_saving_throw = MagicMock()

        result = hazard_resolver.resolve_hazard(
            hazard_type=HazardType.ENCHANTMENT,
            character=mock_character,
            effect_name="Enchanted Reverie",
            condition_on_fail="compelled_dancing",
            automatic=True,
        )

        assert result.success is False
        mock_character.make_saving_throw.assert_not_called()
        assert "compelled_dancing" in result.conditions_applied

    def test_save_modifier_applied(self, hazard_resolver, mock_character):
        """Verify save modifiers are passed to the save roll."""
        # Track what modifier was passed
        mock_character.make_saving_throw = MagicMock(return_value=(10, False))

        hazard_resolver.resolve_hazard(
            hazard_type=HazardType.ENCHANTMENT,
            character=mock_character,
            effect_name="Full Moon Compulsion",
            save_modifier=-4,  # Full moon penalty
        )

        mock_character.make_saving_throw.assert_called_once_with("spell", -4)

    def test_ends_at_time_of_day_in_hints(self, hazard_resolver, mock_character):
        """Verify time-of-day ending is mentioned in narrative hints."""
        mock_character.make_saving_throw = MagicMock(return_value=(5, False))

        result = hazard_resolver.resolve_hazard(
            hazard_type=HazardType.ENCHANTMENT,
            character=mock_character,
            effect_name="Compelled Dancing",
            condition_on_fail="compelled_dancing",
            ends_at_time_of_day="dawn",
        )

        assert any("dawn" in hint for hint in result.narrative_hints)


class TestConditionTimeOfDayExpiry:
    """Tests for condition time-of-day expiry."""

    def test_condition_ends_at_dawn(self):
        """Verify condition ends when time matches ends_at_time_of_day."""
        condition = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            ends_at_time_of_day="dawn",
        )

        assert condition.should_end_at_time(TimeOfDay.DAWN) is True
        assert condition.should_end_at_time(TimeOfDay.MIDNIGHT) is False
        assert condition.should_end_at_time(TimeOfDay.MORNING) is False

    def test_condition_without_time_never_expires_by_time(self):
        """Verify conditions without ends_at_time_of_day don't expire by time."""
        condition = Condition(
            condition_type=ConditionType.CHARMED,
            source="Charm spell",
        )

        assert condition.should_end_at_time(TimeOfDay.DAWN) is False
        assert condition.should_end_at_time(TimeOfDay.MIDNIGHT) is False

    def test_condition_transition_data(self):
        """Verify get_end_transition returns correct data."""
        condition = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            ends_at_time_of_day="dawn",
            healing_on_end={"dice": "1d6", "condition": "undisturbed"},
            leads_to_condition={"condition_type": "magical_sleep", "source": "dawn_slumber"},
        )

        transition = condition.get_end_transition()
        assert transition["healing"]["dice"] == "1d6"
        assert transition["next_condition"]["condition_type"] == "magical_sleep"


class TestNewConditionTypes:
    """Tests for new enchantment condition types."""

    def test_enchanted_hearing_exists(self):
        """Verify ENCHANTED_HEARING condition type exists."""
        assert ConditionType.ENCHANTED_HEARING == "enchanted_hearing"

    def test_compelled_dancing_exists(self):
        """Verify COMPELLED_DANCING condition type exists."""
        assert ConditionType.COMPELLED_DANCING == "compelled_dancing"

    def test_magical_sleep_exists(self):
        """Verify MAGICAL_SLEEP condition type exists."""
        assert ConditionType.MAGICAL_SLEEP == "magical_sleep"

    def test_fairy_marked_exists(self):
        """Verify FAIRY_MARKED condition type exists."""
        assert ConditionType.FAIRY_MARKED == "fairy_marked"

    def test_create_compelled_dancing_condition(self):
        """Verify compelled dancing condition can be created with all fields."""
        condition = Condition(
            condition_type=ConditionType.COMPELLED_DANCING,
            source="The Weeping Woman",
            ends_at_time_of_day="dawn",
            protection_effects={"elements": True},
            leads_to_condition={
                "condition_type": "magical_sleep",
                "source": "dawn_slumber",
            },
        )

        assert condition.condition_type == ConditionType.COMPELLED_DANCING
        assert condition.ends_at_time_of_day == "dawn"
        assert condition.protection_effects["elements"] is True

    def test_create_magical_sleep_condition(self):
        """Verify magical sleep condition can be created with healing on end."""
        condition = Condition(
            condition_type=ConditionType.MAGICAL_SLEEP,
            source="Dawn Slumber",
            duration_turns=48,  # 8 hours = 48 turns
            protection_effects={"elements": True, "damage_types": ["cold", "fire"]},
            healing_on_end={"dice": "1d6", "condition": "undisturbed"},
            leads_to_condition={
                "condition_type": "fairy_marked",
                "source": "neveryon_dreams",
            },
        )

        assert condition.condition_type == ConditionType.MAGICAL_SLEEP
        assert condition.healing_on_end["dice"] == "1d6"
        assert "cold" in condition.protection_effects["damage_types"]


class TestHazardTypeEnchantment:
    """Tests for ENCHANTMENT hazard type registration."""

    def test_enchantment_hazard_type_exists(self):
        """Verify ENCHANTMENT hazard type is defined."""
        assert HazardType.ENCHANTMENT == "enchantment"

    def test_hazard_resolver_handles_enchantment(self, hazard_resolver, mock_character):
        """Verify hazard resolver can handle ENCHANTMENT type."""
        mock_character.make_saving_throw = MagicMock(return_value=(15, True))

        result = hazard_resolver.resolve_hazard(
            hazard_type=HazardType.ENCHANTMENT,
            character=mock_character,
        )

        assert isinstance(result, HazardResult)
        assert result.hazard_type == HazardType.ENCHANTMENT


class TestConditionBlockedActions:
    """Tests for condition-based action restrictions."""

    def test_blocked_actions_dict_exists(self):
        """Verify CONDITION_BLOCKED_ACTIONS is defined."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS
        assert isinstance(CONDITION_BLOCKED_ACTIONS, dict)
        assert "compelled_dancing" in CONDITION_BLOCKED_ACTIONS
        assert "magical_sleep" in CONDITION_BLOCKED_ACTIONS

    def test_dancing_blocks_combat(self):
        """Verify compelled dancing blocks combat actions."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS
        dancing = CONDITION_BLOCKED_ACTIONS["compelled_dancing"]
        assert "combat" in dancing["blocked"]
        assert "spell" in dancing["blocked"]
        assert "movement" in dancing["blocked"]

    def test_dancing_allows_narrative(self):
        """Verify compelled dancing allows narrative actions."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS
        dancing = CONDITION_BLOCKED_ACTIONS["compelled_dancing"]
        assert "narrative" in dancing["allowed"]
        assert "social" in dancing["allowed"]

    def test_magical_sleep_blocks_all_actions(self):
        """Verify magical sleep blocks almost all actions."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS
        sleep = CONDITION_BLOCKED_ACTIONS["magical_sleep"]
        assert len(sleep["blocked"]) >= 8
        assert len(sleep["allowed"]) == 0

    def test_restriction_has_message(self):
        """Verify each restriction has a user-facing message."""
        from src.data_models import CONDITION_BLOCKED_ACTIONS
        for condition_key, restriction in CONDITION_BLOCKED_ACTIONS.items():
            assert "message" in restriction, f"{condition_key} missing message"
            assert len(restriction["message"]) > 0


class TestNarrativeResolverConditionRestrictions:
    """Tests for condition restriction checks in NarrativeResolver."""

    def test_check_condition_restrictions_allows_unrestricted(self):
        """Verify unrestricted actions pass through."""
        from src.narrative.narrative_resolver import NarrativeResolver
        from src.narrative.intent_parser import ParsedIntent, ActionCategory, ActionType

        resolver = NarrativeResolver()
        character = MagicMock()
        character.conditions = []  # No conditions

        parsed = ParsedIntent(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            raw_input="attack",
        )

        result = resolver._check_condition_restrictions(character, parsed)
        assert result is None  # No restriction

    def test_check_condition_restrictions_blocks_dancing_combat(self):
        """Verify compelled dancing blocks combat."""
        from src.narrative.narrative_resolver import NarrativeResolver
        from src.narrative.intent_parser import ParsedIntent, ActionCategory, ActionType

        resolver = NarrativeResolver()
        character = MagicMock()
        character.conditions = [
            Condition(
                condition_type=ConditionType.COMPELLED_DANCING,
                source="The Weeping Woman",
            )
        ]

        parsed = ParsedIntent(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            raw_input="attack",
        )

        result = resolver._check_condition_restrictions(character, parsed)
        assert result is not None
        assert result["condition_type"] == "compelled_dancing"
        assert "cannot stop dancing" in result["message"].lower()

    def test_check_condition_restrictions_allows_dancing_narrative(self):
        """Verify compelled dancing allows narrative actions."""
        from src.narrative.narrative_resolver import NarrativeResolver
        from src.narrative.intent_parser import ParsedIntent, ActionCategory, ActionType

        resolver = NarrativeResolver()
        character = MagicMock()
        character.conditions = [
            Condition(
                condition_type=ConditionType.COMPELLED_DANCING,
                source="The Weeping Woman",
            )
        ]

        parsed = ParsedIntent(
            action_category=ActionCategory.NARRATIVE,
            action_type=ActionType.NARRATIVE_ACTION,
            raw_input="look around",
        )

        result = resolver._check_condition_restrictions(character, parsed)
        assert result is None  # Narrative is allowed


class TestTimeOfDayAdvancement:
    """Tests for time-of-day advancement and condition expiry."""

    def test_advance_to_time_of_day_exists(self):
        """Verify advance_to_time_of_day method exists on GlobalController."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()
        assert hasattr(controller, "advance_to_time_of_day")

    def test_check_time_of_day_expirations_exists(self):
        """Verify _check_time_of_day_expirations method exists."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()
        assert hasattr(controller, "_check_time_of_day_expirations")

    def test_create_chained_condition_exists(self):
        """Verify _create_chained_condition method exists."""
        from src.game_state.global_controller import GlobalController
        controller = GlobalController()
        assert hasattr(controller, "_create_chained_condition")


class TestPOITriggerDetection:
    """Tests for POI action trigger detection."""

    def test_poi_action_patterns_defined(self):
        """Verify POI action patterns are defined."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        assert hasattr(HexCrawlEngine, "POI_ACTION_PATTERNS")
        patterns = HexCrawlEngine.POI_ACTION_PATTERNS
        assert "consume" in patterns
        assert "touch" in patterns
        assert "drink" in patterns["consume"]

    def test_detect_poi_action_consume(self):
        """Verify 'drink' input is detected as consume action."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        from unittest.mock import MagicMock

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.POI_ACTION_PATTERNS = HexCrawlEngine.POI_ACTION_PATTERNS

        result = engine.detect_poi_action("I drink the water")
        assert result is not None
        assert result[0] == "consume"
        assert result[1] == "drink"

    def test_detect_poi_action_touch(self):
        """Verify 'touch' input is detected as touch action."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.POI_ACTION_PATTERNS = HexCrawlEngine.POI_ACTION_PATTERNS

        result = engine.detect_poi_action("I touch the monolith")
        assert result is not None
        assert result[0] == "touch"

    def test_detect_poi_action_no_match(self):
        """Verify unrelated input returns None."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        engine = HexCrawlEngine.__new__(HexCrawlEngine)
        engine.POI_ACTION_PATTERNS = HexCrawlEngine.POI_ACTION_PATTERNS

        result = engine.detect_poi_action("I attack the goblin")
        assert result is None


class TestFullMoonVariation:
    """Tests for full moon variation triggers."""

    def test_is_full_moon_method_exists(self):
        """Verify _is_full_moon method exists on HexCrawlEngine."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        assert hasattr(HexCrawlEngine, "_is_full_moon")

    def test_process_night_hazards_exists(self):
        """Verify process_night_hazards method exists."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        assert hasattr(HexCrawlEngine, "process_night_hazards")

    def test_check_hex_night_entry_exists(self):
        """Verify check_hex_night_entry method exists."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
        assert hasattr(HexCrawlEngine, "check_hex_night_entry")
