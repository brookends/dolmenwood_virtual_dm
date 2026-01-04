"""
Tests for forced behavior effects (terror flee, compelled movement, compelled dancing).

These tests verify that:
- Terror condition forces flee and blocks other actions
- Compelled condition forces movement toward target
- Compelled dancing blocks non-dancing actions until dawn
- Action blocking returns deterministic messages
"""

import pytest
from unittest.mock import MagicMock

from src.data_models import (
    CharacterState,
    Condition,
    ConditionType,
    CONDITION_BLOCKED_ACTIONS,
)
from src.narrative.narrative_resolver import NarrativeResolver, ParsedIntent, ActionCategory
from src.narrative.intent_parser import ActionType


class TestConditionBlockedActionsConfig:
    """Tests for CONDITION_BLOCKED_ACTIONS configuration."""

    def test_terror_has_forced_flee_action(self):
        """Verify terror condition has forced_action='flee'."""
        terror = CONDITION_BLOCKED_ACTIONS.get("terror")
        assert terror is not None
        assert terror["forced_action"] == "flee"
        assert "flee" in terror["forced_action_description"].lower()

    def test_terror_blocks_spell_actions(self):
        """Verify terror blocks spell actions."""
        terror = CONDITION_BLOCKED_ACTIONS.get("terror")
        assert "spell" in terror["blocked"]

    def test_terror_blocks_combat_actions(self):
        """Verify terror blocks combat actions."""
        terror = CONDITION_BLOCKED_ACTIONS.get("terror")
        assert "combat" in terror["blocked"]

    def test_terror_allows_movement(self):
        """Verify terror allows movement (for fleeing)."""
        terror = CONDITION_BLOCKED_ACTIONS.get("terror")
        assert "movement" in terror["allowed"]

    def test_compelled_has_move_toward_target_action(self):
        """Verify compelled condition has forced_action='move_toward_target'."""
        compelled = CONDITION_BLOCKED_ACTIONS.get("compelled")
        assert compelled is not None
        assert compelled["forced_action"] == "move_toward_target"
        assert "monolith" in compelled["forced_action_description"].lower()

    def test_compelled_can_be_restrained(self):
        """Verify compelled condition has can_be_restrained=True."""
        compelled = CONDITION_BLOCKED_ACTIONS.get("compelled")
        assert compelled.get("can_be_restrained") is True

    def test_compelled_blocks_spell_actions(self):
        """Verify compelled blocks spell actions."""
        compelled = CONDITION_BLOCKED_ACTIONS.get("compelled")
        assert "spell" in compelled["blocked"]

    def test_compelled_allows_movement(self):
        """Verify compelled allows movement (forced movement toward target)."""
        compelled = CONDITION_BLOCKED_ACTIONS.get("compelled")
        assert "movement" in compelled["allowed"]

    def test_compelled_dancing_has_dance_action(self):
        """Verify compelled_dancing has forced_action='dance'."""
        dancing = CONDITION_BLOCKED_ACTIONS.get("compelled_dancing")
        assert dancing is not None
        assert dancing["forced_action"] == "dance"
        assert "dance" in dancing["forced_action_description"].lower()

    def test_compelled_dancing_ends_at_dawn(self):
        """Verify compelled_dancing ends at dawn."""
        dancing = CONDITION_BLOCKED_ACTIONS.get("compelled_dancing")
        assert dancing.get("ends_at") == "dawn"

    def test_compelled_dancing_blocks_spell_and_movement(self):
        """Verify compelled_dancing blocks spell and movement actions."""
        dancing = CONDITION_BLOCKED_ACTIONS.get("compelled_dancing")
        assert "spell" in dancing["blocked"]
        assert "movement" in dancing["blocked"]

    def test_compelled_dancing_allows_social(self):
        """Verify compelled_dancing allows social actions (can speak while dancing)."""
        dancing = CONDITION_BLOCKED_ACTIONS.get("compelled_dancing")
        assert "social" in dancing["allowed"]


class TestCheckConditionRestrictionsWithForcedAction:
    """Tests for _check_condition_restrictions returning forced action info."""

    @pytest.fixture
    def resolver(self):
        """Create a NarrativeResolver for testing."""
        resolver = NarrativeResolver.__new__(NarrativeResolver)
        resolver.controller = MagicMock()
        return resolver

    @pytest.fixture
    def character_with_terror(self):
        """Create a character with terror condition."""
        char = CharacterState(
            character_id="test_char",
            name="Terrified Fighter",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.TERROR, source="vorpal_monolith")
        )
        return char

    @pytest.fixture
    def character_with_compelled(self):
        """Create a character with compelled condition."""
        char = CharacterState(
            character_id="test_char",
            name="Compelled Wizard",
            character_class="Magic-User",
            level=3,
            ability_scores={"STR": 8, "INT": 16, "WIS": 14, "DEX": 10, "CON": 10, "CHA": 12},
            hp_current=8,
            hp_max=8,
            armor_class=10,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.COMPELLED, source="vorpal_monolith")
        )
        return char

    @pytest.fixture
    def character_with_dancing(self):
        """Create a character with compelled_dancing condition."""
        char = CharacterState(
            character_id="test_char",
            name="Dancing Thief",
            character_class="Thief",
            level=2,
            ability_scores={"STR": 10, "INT": 12, "WIS": 10, "DEX": 16, "CON": 12, "CHA": 14},
            hp_current=10,
            hp_max=10,
            armor_class=12,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.COMPELLED_DANCING, source="fairy_music")
        )
        return char

    def test_terrified_cast_spell_blocked_with_flee_message(self, resolver, character_with_terror):
        """Verify casting spell while terrified returns block with flee action."""
        # Create parsed intent for casting a spell
        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="I cast magic missile",
        )

        result = resolver._check_condition_restrictions(character_with_terror, parsed)

        assert result is not None
        assert result["condition_type"] == "terror"
        assert "flee" in result["message"].lower() or "running away" in result["message"].lower()
        assert result["forced_action"] == "flee"
        assert "flee" in result["forced_action_description"].lower()

    def test_terrified_attack_blocked_with_flee_message(self, resolver, character_with_terror):
        """Verify attacking while terrified returns block with flee action."""
        parsed = ParsedIntent(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            raw_input="I attack the monster",
        )

        result = resolver._check_condition_restrictions(character_with_terror, parsed)

        assert result is not None
        assert result["condition_type"] == "terror"
        assert result["forced_action"] == "flee"

    def test_terrified_movement_allowed(self, resolver, character_with_terror):
        """Verify movement is allowed while terrified (for fleeing)."""
        parsed = ParsedIntent(
            action_category=ActionCategory.MOVEMENT,
            action_type=ActionType.FLEE,
            raw_input="I run away",
        )

        result = resolver._check_condition_restrictions(character_with_terror, parsed)

        # Should not be blocked
        assert result is None

    def test_compelled_cast_spell_blocked_with_move_toward_target(self, resolver, character_with_compelled):
        """Verify casting spell while compelled returns block with move_toward_target action."""
        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="I cast shield",
        )

        result = resolver._check_condition_restrictions(character_with_compelled, parsed)

        assert result is not None
        assert result["condition_type"] == "compelled"
        assert result["forced_action"] == "move_toward_target"
        assert "monolith" in result["forced_action_description"].lower()
        assert result["can_be_restrained"] is True

    def test_compelled_movement_allowed(self, resolver, character_with_compelled):
        """Verify movement is allowed while compelled."""
        parsed = ParsedIntent(
            action_category=ActionCategory.MOVEMENT,
            action_type=ActionType.TRAVEL,
            raw_input="I walk toward the monolith",
        )

        result = resolver._check_condition_restrictions(character_with_compelled, parsed)

        # Should not be blocked
        assert result is None

    def test_dancing_cast_spell_blocked_with_dance_action(self, resolver, character_with_dancing):
        """Verify casting spell while dancing returns block with dance action."""
        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="I cast fireball",
        )

        result = resolver._check_condition_restrictions(character_with_dancing, parsed)

        assert result is not None
        assert result["condition_type"] == "compelled_dancing"
        assert result["forced_action"] == "dance"
        assert "dance" in result["forced_action_description"].lower()
        assert result["ends_at"] == "dawn"

    def test_dancing_movement_blocked(self, resolver, character_with_dancing):
        """Verify movement is blocked while dancing (can't stop dancing to walk)."""
        parsed = ParsedIntent(
            action_category=ActionCategory.MOVEMENT,
            action_type=ActionType.TRAVEL,
            raw_input="I try to walk away",
        )

        result = resolver._check_condition_restrictions(character_with_dancing, parsed)

        assert result is not None
        assert result["condition_type"] == "compelled_dancing"

    def test_dancing_social_allowed(self, resolver, character_with_dancing):
        """Verify social actions are allowed while dancing (can speak)."""
        parsed = ParsedIntent(
            action_category=ActionCategory.SOCIAL,
            action_type=ActionType.PARLEY,
            raw_input="I shout for help",
        )

        result = resolver._check_condition_restrictions(character_with_dancing, parsed)

        # Should not be blocked
        assert result is None


class TestDeterministicBlockedMessages:
    """Tests verifying blocked messages are deterministic (not random)."""

    @pytest.fixture
    def resolver(self):
        """Create a NarrativeResolver for testing."""
        resolver = NarrativeResolver.__new__(NarrativeResolver)
        resolver.controller = MagicMock()
        return resolver

    def test_terror_spell_block_message_is_deterministic(self, resolver):
        """Verify terror spell block returns the same message every time."""
        char = CharacterState(
            character_id="test_char",
            name="Test Character",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 10, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=10,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.TERROR, source="test")
        )

        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="cast spell",
        )

        # Call multiple times and verify same result
        results = [
            resolver._check_condition_restrictions(char, parsed)
            for _ in range(5)
        ]

        # All messages should be identical
        messages = [r["message"] for r in results]
        assert len(set(messages)) == 1, "Message should be deterministic"

        # All forced actions should be identical
        forced_actions = [r["forced_action"] for r in results]
        assert len(set(forced_actions)) == 1, "Forced action should be deterministic"
        assert forced_actions[0] == "flee"

    def test_compelled_spell_block_message_is_deterministic(self, resolver):
        """Verify compelled spell block returns the same message every time."""
        char = CharacterState(
            character_id="test_char",
            name="Test Character",
            character_class="Magic-User",
            level=1,
            ability_scores={"STR": 10, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=5,
            hp_max=5,
            armor_class=10,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.COMPELLED, source="test")
        )

        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="cast spell",
        )

        # Call multiple times and verify same result
        results = [
            resolver._check_condition_restrictions(char, parsed)
            for _ in range(5)
        ]

        # All messages should be identical
        messages = [r["message"] for r in results]
        assert len(set(messages)) == 1, "Message should be deterministic"

    def test_dancing_spell_block_message_is_deterministic(self, resolver):
        """Verify compelled_dancing spell block returns the same message every time."""
        char = CharacterState(
            character_id="test_char",
            name="Test Character",
            character_class="Thief",
            level=1,
            ability_scores={"STR": 10, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=5,
            hp_max=5,
            armor_class=10,
            base_speed=40,
        )
        char.conditions.append(
            Condition(condition_type=ConditionType.COMPELLED_DANCING, source="test")
        )

        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="cast spell",
        )

        # Call multiple times and verify same result
        results = [
            resolver._check_condition_restrictions(char, parsed)
            for _ in range(5)
        ]

        # All messages should be identical
        messages = [r["message"] for r in results]
        assert len(set(messages)) == 1, "Message should be deterministic"

        # Check ends_at is included
        assert all(r.get("ends_at") == "dawn" for r in results)


class TestNoConditionsAllowsActions:
    """Tests verifying actions are allowed when no blocking conditions present."""

    @pytest.fixture
    def resolver(self):
        """Create a NarrativeResolver for testing."""
        resolver = NarrativeResolver.__new__(NarrativeResolver)
        resolver.controller = MagicMock()
        return resolver

    @pytest.fixture
    def healthy_character(self):
        """Create a character with no conditions."""
        return CharacterState(
            character_id="test_char",
            name="Healthy Fighter",
            character_class="Fighter",
            level=3,
            ability_scores={"STR": 14, "INT": 10, "WIS": 10, "DEX": 12, "CON": 14, "CHA": 10},
            hp_current=20,
            hp_max=20,
            armor_class=14,
            base_speed=40,
        )

    def test_spell_allowed_without_conditions(self, resolver, healthy_character):
        """Verify spells are allowed when no blocking conditions."""
        parsed = ParsedIntent(
            action_category=ActionCategory.SPELL,
            action_type=ActionType.CAST_SPELL,
            raw_input="I cast magic missile",
        )

        result = resolver._check_condition_restrictions(healthy_character, parsed)

        assert result is None

    def test_combat_allowed_without_conditions(self, resolver, healthy_character):
        """Verify combat is allowed when no blocking conditions."""
        parsed = ParsedIntent(
            action_category=ActionCategory.COMBAT,
            action_type=ActionType.ATTACK,
            raw_input="I attack the goblin",
        )

        result = resolver._check_condition_restrictions(healthy_character, parsed)

        assert result is None

    def test_movement_allowed_without_conditions(self, resolver, healthy_character):
        """Verify movement is allowed when no blocking conditions."""
        parsed = ParsedIntent(
            action_category=ActionCategory.MOVEMENT,
            action_type=ActionType.TRAVEL,
            raw_input="I walk north",
        )

        result = resolver._check_condition_restrictions(healthy_character, parsed)

        assert result is None
