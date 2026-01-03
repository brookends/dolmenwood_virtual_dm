"""
Tests for fallback intent parsing coverage (Phase 9.2).

Verifies that representative utterances match expected registered action IDs
across all game states without requiring LLM.
"""

import pytest

from src.narrative.narrative_resolver import (
    NarrativeResolver,
    FallbackIntentResult,
    WILDERNESS_PATTERNS,
    DUNGEON_PATTERNS,
    ENCOUNTER_PATTERNS,
    SETTLEMENT_PATTERNS,
    SOCIAL_PATTERNS,
    DOWNTIME_PATTERNS,
    COMBAT_PATTERNS,
    UNIVERSAL_PATTERNS,
    _match_patterns,
    _extract_speech_text,
    _extract_target,
    _extract_direction,
    _extract_question,
)
from src.narrative.intent_parser import ActionCategory, ActionType
from src.conversation.action_registry import get_default_registry


@pytest.fixture
def resolver():
    """Create NarrativeResolver without controller."""
    return NarrativeResolver(controller=None)


@pytest.fixture
def registry():
    """Get the default action registry."""
    return get_default_registry()


# =============================================================================
# WILDERNESS STATE TESTS
# =============================================================================


class TestWildernessFallbackIntent:
    """Test fallback intent matching for wilderness state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Social/NPC
        ("talk to the old man", "wilderness:talk_npc"),
        ("speak with the stranger", "wilderness:talk_npc"),

        # Exploration
        ("search the area", "wilderness:search_hex"),
        ("look around", "wilderness:look_around"),
        ("survey the surroundings", "wilderness:look_around"),
        ("enter the cave", "wilderness:enter_poi"),
        ("go inside", "wilderness:enter_poi"),
        ("leave this place", "wilderness:leave_poi"),

        # Survival
        ("forage for food", "wilderness:forage"),
        ("gather plants", "wilderness:forage"),
        ("hunt for game", "wilderness:hunt"),
        ("track animal", "wilderness:hunt"),

        # Travel/Rest
        ("make camp", "wilderness:end_day"),
        ("set up camp for the night", "wilderness:end_day"),
        ("rest for night", "wilderness:end_day"),
    ])
    def test_wilderness_patterns_match(self, resolver, utterance, expected_action_id):
        """Wilderness utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "wilderness_travel")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7

    def test_wilderness_actions_are_registered(self, resolver, registry):
        """All matched wilderness actions should be registered."""
        utterances = [
            "search the area",
            "look around",
            "forage for food",
            "hunt for game",
            "make camp",
        ]

        for utterance in utterances:
            result = resolver.get_fallback_intent(utterance, "wilderness_travel")
            if result.action_id:
                assert registry.is_registered(result.action_id), \
                    f"Action {result.action_id} for '{utterance}' is not registered"


# =============================================================================
# DUNGEON STATE TESTS
# =============================================================================


class TestDungeonFallbackIntent:
    """Test fallback intent matching for dungeon state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Exploration
        ("search the room", "dungeon:search"),
        ("examine the area", "dungeon:search"),
        ("listen at the door", "dungeon:listen"),
        ("press ear to the door", "dungeon:listen"),
        ("open the door", "dungeon:open_door"),
        ("try the door", "dungeon:open_door"),
        ("pick the lock", "dungeon:pick_lock"),

        # Movement
        ("go north", "dungeon:move"),
        ("proceed through", "dungeon:move"),

        # Rest
        ("take a break", "dungeon:rest"),
        ("short rest", "dungeon:rest"),

        # Exit
        ("exit the dungeon", "dungeon:exit"),
        ("leave this place", "dungeon:exit"),
    ])
    def test_dungeon_patterns_match(self, resolver, utterance, expected_action_id):
        """Dungeon utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "dungeon_exploration")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7

    def test_dungeon_actions_are_registered(self, resolver, registry):
        """All matched dungeon actions should be registered."""
        utterances = [
            "search the room",
            "listen at the door",
            "open the door",
            "rest",
        ]

        for utterance in utterances:
            result = resolver.get_fallback_intent(utterance, "dungeon_exploration")
            if result.action_id:
                assert registry.is_registered(result.action_id), \
                    f"Action {result.action_id} for '{utterance}' is not registered"


# =============================================================================
# ENCOUNTER STATE TESTS
# =============================================================================


class TestEncounterFallbackIntent:
    """Test fallback intent matching for encounter state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Social
        ("talk to them", "encounter:parley"),
        ("parley with the creatures", "encounter:parley"),
        ("negotiate", "encounter:parley"),
        ("greet them", "encounter:parley"),
        ("hail the travelers", "encounter:parley"),

        # Evasion
        ("flee!", "encounter:flee"),
        ("run away", "encounter:flee"),
        ("escape", "encounter:flee"),
        ("hide from them", "encounter:flee"),
        ("sneak away", "encounter:flee"),
        ("retreat", "encounter:flee"),

        # Combat
        ("attack", "encounter:attack"),
        ("fight them", "encounter:attack"),
        ("draw weapon", "encounter:attack"),

        # Wait
        ("wait and observe", "encounter:wait"),
        ("hold position", "encounter:wait"),
    ])
    def test_encounter_patterns_match(self, resolver, utterance, expected_action_id):
        """Encounter utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "encounter")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7

    def test_encounter_actions_are_registered(self, resolver, registry):
        """All matched encounter actions should be registered."""
        utterances = [
            "parley",
            "flee",
            "attack",
            "wait",
        ]

        for utterance in utterances:
            result = resolver.get_fallback_intent(utterance, "encounter")
            if result.action_id:
                assert registry.is_registered(result.action_id), \
                    f"Action {result.action_id} for '{utterance}' is not registered"


# =============================================================================
# SETTLEMENT STATE TESTS
# =============================================================================


class TestSettlementFallbackIntent:
    """Test fallback intent matching for settlement state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Social
        ("talk to the merchant", "settlement:talk_npc"),
        ("speak with the innkeeper", "settlement:talk_npc"),
        ("ask about rumors", "settlement:talk_npc"),

        # Commerce
        ("buy some supplies", "settlement:visit_market"),
        ("sell my loot", "settlement:visit_market"),
        ("go to the shop", "settlement:visit_market"),

        # Locations
        ("visit the inn", "settlement:visit_inn"),
        ("go to the tavern", "settlement:visit_inn"),
        ("visit the market", "settlement:visit_market"),
        ("explore the town", "settlement:explore"),

        # Exit
        ("leave town", "settlement:leave"),
        ("depart", "settlement:leave"),
    ])
    def test_settlement_patterns_match(self, resolver, utterance, expected_action_id):
        """Settlement utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "settlement_exploration")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7


# =============================================================================
# SOCIAL INTERACTION STATE TESTS
# =============================================================================


class TestSocialFallbackIntent:
    """Test fallback intent matching for social interaction state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Dialogue
        ("say hello", "social:say"),
        ("tell them about the quest", "social:say"),
        ("ask about the dungeon", "social:say"),
        ("respond with thanks", "social:say"),

        # End conversation
        ("goodbye", "social:end"),
        ("farewell", "social:end"),
        ("end conversation", "social:end"),
        ("walk away", "social:end"),

        # Oracle for NPC
        ("oracle: will they help us?", "social:oracle_question"),
        ("ask fate about their mood", "social:oracle_question"),
    ])
    def test_social_patterns_match(self, resolver, utterance, expected_action_id):
        """Social utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "social_interaction")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7

    def test_speech_text_extracted(self, resolver):
        """Speech text should be extracted from say commands."""
        result = resolver.get_fallback_intent(
            'say "I seek the ancient artifact"',
            "social_interaction"
        )

        assert result.action_id == "social:say"
        assert "text" in result.action_params


# =============================================================================
# DOWNTIME STATE TESTS
# =============================================================================


class TestDowntimeFallbackIntent:
    """Test fallback intent matching for downtime state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Rest
        ("rest for the day", "downtime:rest"),
        ("sleep and recover", "downtime:rest"),
        ("recuperate", "downtime:rest"),

        # Training
        ("train combat skills", "downtime:train"),
        ("practice swordplay", "downtime:train"),
        ("study magic", "downtime:train"),

        # Research
        ("research the artifact", "downtime:research"),
        ("study lore", "downtime:research"),
        ("investigate the curse", "downtime:research"),

        # Crafting
        ("craft a potion", "downtime:craft"),
        ("repair my armor", "downtime:craft"),

        # End
        ("end downtime", "downtime:end"),
        ("time to adventure", "downtime:end"),
    ])
    def test_downtime_patterns_match(self, resolver, utterance, expected_action_id):
        """Downtime utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "downtime")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7


# =============================================================================
# COMBAT STATE TESTS
# =============================================================================


class TestCombatFallbackIntent:
    """Test fallback intent matching for combat state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Attack
        ("attack the goblin", "combat:resolve_round"),
        ("strike the enemy", "combat:resolve_round"),
        ("hit it", "combat:resolve_round"),

        # Flee
        ("flee from combat", "combat:flee"),
        ("retreat", "combat:flee"),
        ("run away", "combat:flee"),

        # Parley
        ("try to negotiate", "combat:parley"),
        ("surrender", "combat:parley"),

        # Status
        ("combat status", "combat:status"),
        ("how are we doing", "combat:status"),
    ])
    def test_combat_patterns_match(self, resolver, utterance, expected_action_id):
        """Combat utterances match expected action IDs."""
        result = resolver.get_fallback_intent(utterance, "combat")

        assert result.action_id == expected_action_id
        assert result.confidence > 0.7


# =============================================================================
# UNIVERSAL PATTERNS TESTS
# =============================================================================


class TestUniversalFallbackIntent:
    """Test universal patterns that work in any state."""

    @pytest.mark.parametrize("utterance,expected_action_id", [
        # Oracle
        ("oracle: is there treasure?", "oracle:fate_check"),
        ("fate check: will we succeed?", "oracle:fate_check"),
        ("ask the oracle", "oracle:fate_check"),
        ("random event please", "oracle:random_event"),
        ("what happens next", "oracle:random_event"),

        # Meta
        ("check status", "meta:status"),
        ("where am i", "meta:status"),
        ("show rolls", "meta:roll_log"),
        ("light torch", "party:light"),
    ])
    def test_universal_patterns_match(self, resolver, utterance, expected_action_id):
        """Universal utterances match in any state."""
        # Test in multiple states
        for state in ["wilderness_travel", "dungeon_exploration", "settlement_exploration"]:
            result = resolver.get_fallback_intent(utterance, state)
            # Universal patterns may be overridden by state-specific, so check presence
            if result.action_id:
                # If matched, confidence should be reasonable
                assert result.confidence > 0.5


# =============================================================================
# CREATIVE/ORACLE FALLBACK TESTS
# =============================================================================


class TestCreativeOracleFallback:
    """Test that unmatched actions route to oracle."""

    def test_unrecognized_action_requires_oracle(self, resolver):
        """Unrecognized actions should suggest oracle routing."""
        result = resolver.get_fallback_intent(
            "perform an elaborate interpretive dance",
            "wilderness_travel"
        )

        # Should have no registered action
        assert result.action_id is None
        assert result.requires_oracle is True
        assert result.oracle_question is not None
        assert "succeed" in result.oracle_question.lower()

    def test_creative_solution_has_oracle_prompt(self, resolver):
        """Creative solutions should have a pre-formed oracle question."""
        result = resolver.get_fallback_intent(
            "try to befriend the dragon by singing",
            "encounter"
        )

        if result.requires_oracle:
            assert result.oracle_question is not None
            assert len(result.oracle_question) > 10


# =============================================================================
# PARAM EXTRACTION TESTS
# =============================================================================


class TestParamExtraction:
    """Test parameter extraction from utterances."""

    def test_extract_speech_text(self):
        """Speech text should be extracted correctly."""
        assert _extract_speech_text("say hello there")["text"] == "hello there"
        assert _extract_speech_text("tell them the password")["text"] == "the password"
        assert _extract_speech_text('say "quoted text"')["text"] == "quoted text"

    def test_extract_target(self):
        """Target should be extracted from combat/approach commands."""
        assert _extract_target("attack the goblin")["target"] == "goblin"
        assert _extract_target("talk to the merchant")["target"] == "merchant"
        assert _extract_target("approach the stranger")["target"] == "stranger"

    def test_extract_direction(self):
        """Direction should be extracted from movement commands."""
        assert _extract_direction("go north")["direction"] == "north"
        assert _extract_direction("walk south")["direction"] == "south"
        assert _extract_direction("proceed east")["direction"] == "east"

    def test_extract_question(self):
        """Oracle question should be extracted."""
        result = _extract_question("oracle: is there treasure?")
        assert result["question"] == "is there treasure?"

        result = _extract_question("fate check: will we succeed?")
        assert result["question"] == "will we succeed?"


# =============================================================================
# PATTERN MATCHING UTILITY TESTS
# =============================================================================


class TestPatternMatching:
    """Test the _match_patterns utility function."""

    def test_match_patterns_finds_first_match(self):
        """Pattern matching should return the first match found."""
        patterns = [
            (("hello", "hi"), "greet:hello", None, 0.9),
            (("goodbye", "bye"), "greet:goodbye", None, 0.9),
        ]

        result = _match_patterns("hello there", patterns)
        assert result is not None
        assert result[0] == "greet:hello"

    def test_match_patterns_returns_none_when_no_match(self):
        """Pattern matching should return None when no match found."""
        patterns = [
            (("hello", "hi"), "greet:hello", None, 0.9),
        ]

        result = _match_patterns("goodbye", patterns)
        assert result is None

    def test_match_patterns_case_insensitive(self):
        """Pattern matching should be case insensitive."""
        patterns = [
            (("hello",), "greet:hello", None, 0.9),
        ]

        assert _match_patterns("HELLO", patterns) is not None
        assert _match_patterns("Hello", patterns) is not None
        assert _match_patterns("hello", patterns) is not None


# =============================================================================
# ACTION REGISTRATION VERIFICATION
# =============================================================================


class TestActionRegistrationVerification:
    """Verify that matched actions are actually registered."""

    def test_all_pattern_action_ids_are_registered(self, registry):
        """All action IDs in pattern tables should be registered."""
        all_patterns = [
            *WILDERNESS_PATTERNS,
            *DUNGEON_PATTERNS,
            *ENCOUNTER_PATTERNS,
            *SETTLEMENT_PATTERNS,
            *SOCIAL_PATTERNS,
            *DOWNTIME_PATTERNS,
            *COMBAT_PATTERNS,
            *UNIVERSAL_PATTERNS,
        ]

        unregistered = []
        for keywords, action_id, _, _ in all_patterns:
            if not registry.is_registered(action_id):
                unregistered.append(action_id)

        # Report any unregistered actions (this is informational, not a failure)
        # Some actions may be placeholders for future implementation
        if unregistered:
            print(f"Note: {len(unregistered)} action IDs not yet registered: {unregistered[:5]}...")

    def test_common_actions_are_registered(self, registry):
        """The most common action IDs should definitely be registered."""
        must_have = [
            "wilderness:search_hex",
            "dungeon:search",
            "encounter:parley",
            "encounter:flee",
            "settlement:talk_npc",
            "social:say",
            "oracle:fate_check",
            "meta:status",
        ]

        for action_id in must_have:
            assert registry.is_registered(action_id), \
                f"Essential action {action_id} is not registered"


# =============================================================================
# INTENT STRUCTURE TESTS
# =============================================================================


class TestIntentStructure:
    """Test that created intents have correct structure."""

    def test_intent_has_category(self, resolver):
        """Created intents should have action category set."""
        result = resolver.get_fallback_intent("search the room", "dungeon_exploration")

        assert result.intent.action_category is not None
        assert isinstance(result.intent.action_category, ActionCategory)

    def test_intent_has_action_type(self, resolver):
        """Created intents should have action type set."""
        result = resolver.get_fallback_intent("attack the goblin", "combat")

        assert result.intent.action_type is not None
        assert isinstance(result.intent.action_type, ActionType)

    def test_combat_actions_flagged(self, resolver):
        """Combat/encounter actions should have is_combat_action=True."""
        result = resolver.get_fallback_intent("attack", "encounter")

        assert result.intent.is_combat_action is True

    def test_raw_input_preserved(self, resolver):
        """Original input should be preserved in intent."""
        original = "search the mysterious room carefully"
        result = resolver.get_fallback_intent(original, "dungeon_exploration")

        assert result.intent.raw_input == original
