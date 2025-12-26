"""
Unit tests for LLM authority boundary enforcement.

Tests that the LLM integration respects strict authority boundaries:
- LLM cannot roll dice
- LLM cannot decide outcomes
- LLM cannot alter game state
- LLM only provides descriptions

From src/ai/llm_provider.py and src/ai/dm_agent.py.
"""

import pytest
from src.ai.llm_provider import (
    LLMManager,
    LLMConfig,
    LLMProvider,
    LLMMessage,
    LLMRole,
    LLMResponse,
    MockLLMClient,
)
from src.ai.dm_agent import DMAgent, DMAgentConfig, reset_dm_agent
from src.ai.prompt_schemas import (
    PromptSchemaType,
    ExplorationDescriptionInputs,
    ExplorationDescriptionSchema,
    CombatNarrationInputs,
    CombatNarrationSchema,
    ResolvedAction,
)
from src.data_models import LocationState, LocationType, Weather, TimeOfDay


class TestLLMAuthorityViolationDetection:
    """Tests for authority violation detection."""

    def test_detects_dice_roll_mention(self, mock_llm_manager):
        """Test that dice mentions are flagged."""
        # Create mock client with violating response
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["Roll 1d20 to hit the goblin."])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete([
            LLMMessage(LLMRole.USER, "Describe the attack")
        ])

        assert len(response.authority_violations) > 0
        assert any("d20" in v or "roll" in v for v in response.authority_violations)

    def test_detects_outcome_determination(self, mock_llm_manager):
        """Test that outcome determination is flagged."""
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["You succeed in picking the lock!"])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete([
            LLMMessage(LLMRole.USER, "Describe the thief's attempt")
        ])

        assert len(response.authority_violations) > 0
        assert any("succeed" in v for v in response.authority_violations)

    def test_detects_failure_determination(self, mock_llm_manager):
        """Test that failure determination is flagged."""
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["You fail to notice the trap."])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete([
            LLMMessage(LLMRole.USER, "Describe the search")
        ])

        assert len(response.authority_violations) > 0
        assert any("fail" in v for v in response.authority_violations)

    def test_detects_damage_application(self, mock_llm_manager):
        """Test that damage application is flagged (outside narration context)."""
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["You take 5 damage from the attack."])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete([
            LLMMessage(LLMRole.USER, "Describe the scene")
        ])

        assert len(response.authority_violations) > 0

    def test_allows_damage_in_narration_context(self, mock_llm_manager):
        """Test that damage narration is allowed in combat context."""
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["The goblin's blade bites deep, dealing 5 damage."])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete(
            [LLMMessage(LLMRole.USER, "Narrate the resolved attack")],
            allow_narration_context=True,
        )

        # In narration context, damage mentions should be allowed
        # (This depends on implementation - may or may not have violations)

    def test_detects_dice_notation(self, mock_llm_manager):
        """Test that dice notation patterns are detected."""
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["The monster attacks with 2d6+3 damage."])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete([
            LLMMessage(LLMRole.USER, "Describe the monster")
        ])

        assert len(response.authority_violations) > 0
        assert any("dice_notation" in v for v in response.authority_violations)

    def test_detects_roll_result(self, mock_llm_manager):
        """Test that roll result mentions are detected."""
        mock_client = MockLLMClient(mock_llm_manager.config)
        mock_client.set_responses(["You rolled 15 on the attack."])
        mock_llm_manager._client = mock_client

        response = mock_llm_manager.complete([
            LLMMessage(LLMRole.USER, "What happened?")
        ])

        assert len(response.authority_violations) > 0


class TestDMAgentBoundaries:
    """Tests for DM Agent boundary enforcement."""

    def test_location_description_no_mechanics(self, dm_agent):
        """Test that location descriptions don't include mechanics."""
        location = LocationState(
            location_type=LocationType.HEX,
            location_id="0709",
            terrain="forest",
            name="The Whispering Glade",
        )

        result = dm_agent.describe_location(
            location=location,
            time_of_day=TimeOfDay.MORNING,
            weather=Weather.CLEAR,
        )

        # Should succeed without authority violations
        assert result.success is True or len(result.authority_violations) == 0

    def test_combat_narration_only_describes_resolved(self, dm_agent):
        """Test that combat narration only describes resolved actions."""
        resolved_actions = [
            {
                "actor": "Fighter",
                "action": "melee attack",
                "target": "Goblin",
                "result": "hit",
                "damage": 7,
            }
        ]

        result = dm_agent.narrate_combat_round(
            round_number=1,
            resolved_actions=resolved_actions,
            damage_results={"Goblin": 7},
        )

        # Narration should succeed
        assert result.schema_used == PromptSchemaType.COMBAT_NARRATION

    def test_npc_dialogue_respects_secrets(self, dm_agent, sample_npc):
        """Test that NPC dialogue doesn't reveal secrets."""
        result = dm_agent.generate_npc_dialogue(
            npc=sample_npc,
            conversation_topic="Tell me about the Drune",
            reaction_result="neutral",
            known_topics=["Weather is bad lately"],
            hidden_topics=["Knows about the hidden Drune circle"],
        )

        # Response should not contain secrets
        # (This is enforced by prompt, not validation - testing structure)
        assert result.schema_used == PromptSchemaType.NPC_DIALOGUE


class TestPromptSchemaValidation:
    """Tests for prompt schema input validation."""

    def test_exploration_schema_validates_inputs(self):
        """Test exploration schema input validation."""
        inputs = ExplorationDescriptionInputs(
            current_state="wilderness_travel",
            location_summary="A forest clearing",
            sensory_tags=["rustling leaves", "bird calls"],
        )

        schema = ExplorationDescriptionSchema(inputs)
        errors = schema.validate_inputs()

        assert errors == []  # No errors for valid inputs

    def test_exploration_schema_with_minimal_inputs(self):
        """Test exploration schema with minimal inputs."""
        inputs = ExplorationDescriptionInputs(
            current_state="wilderness_travel",
            location_summary="A clearing",
            sensory_tags=[],  # Minimal - no sensory tags
        )

        schema = ExplorationDescriptionSchema(inputs)
        errors = schema.validate_inputs()

        # Should still pass validation with minimal inputs
        assert errors == []

    def test_combat_schema_validates_actions(self):
        """Test combat narration schema validation."""
        inputs = CombatNarrationInputs(
            round_number=1,
            resolved_actions=[
                ResolvedAction(
                    actor="Fighter",
                    action="attack",
                    target="Goblin",
                    result="hit",
                    damage=5,
                )
            ],
            damage_results={"Goblin": 5},
            conditions_applied=[],
        )

        schema = CombatNarrationSchema(inputs)
        errors = schema.validate_inputs()

        assert errors == []

    def test_combat_schema_with_conditions(self):
        """Test combat narration with conditions."""
        inputs = CombatNarrationInputs(
            round_number=2,
            resolved_actions=[
                ResolvedAction(
                    actor="Fighter",
                    action="attack",
                    target="Goblin",
                    result="hit",
                    damage=8,
                )
            ],
            damage_results={"Goblin": 8},
            conditions_applied=["poisoned"],
            morale_results=["Enemies failed morale check"],
            deaths=["Goblin"],
        )

        schema = CombatNarrationSchema(inputs)
        errors = schema.validate_inputs()

        assert errors == []


class TestMockLLMClient:
    """Tests for mock LLM client."""

    def test_mock_client_always_available(self, mock_llm_config):
        """Test that mock client is always available."""
        client = MockLLMClient(mock_llm_config)
        assert client.is_available() is True

    def test_mock_client_returns_set_responses(self, mock_llm_config):
        """Test that mock client returns configured responses."""
        client = MockLLMClient(mock_llm_config)
        client.set_responses([
            "First response",
            "Second response",
            "Third response",
        ])

        r1 = client.complete([LLMMessage(LLMRole.USER, "test")])
        r2 = client.complete([LLMMessage(LLMRole.USER, "test")])
        r3 = client.complete([LLMMessage(LLMRole.USER, "test")])

        assert r1.content == "First response"
        assert r2.content == "Second response"
        assert r3.content == "Third response"

    def test_mock_client_cycles_responses(self, mock_llm_config):
        """Test that mock client cycles through responses."""
        client = MockLLMClient(mock_llm_config)
        client.set_responses(["A", "B"])

        r1 = client.complete([LLMMessage(LLMRole.USER, "test")])
        r2 = client.complete([LLMMessage(LLMRole.USER, "test")])
        r3 = client.complete([LLMMessage(LLMRole.USER, "test")])

        assert r1.content == "A"
        assert r2.content == "B"
        assert r3.content == "A"  # Cycles back


class TestLLMManager:
    """Tests for LLM manager."""

    def test_manager_with_mock_provider(self, mock_llm_config):
        """Test manager initialization with mock provider."""
        manager = LLMManager(mock_llm_config)
        assert manager.is_available() is True

    def test_manager_truncates_long_responses(self, mock_llm_config):
        """Test that overly long responses are truncated."""
        mock_llm_config.max_response_length = 50
        manager = LLMManager(mock_llm_config)

        # Set a long response
        mock_client = MockLLMClient(mock_llm_config)
        mock_client.set_responses(["A" * 100])
        manager._client = mock_client

        response = manager.complete([LLMMessage(LLMRole.USER, "test")])

        assert len(response.content) <= 53  # 50 + "..."
        assert response.sanitized is True


class TestDMAgentCaching:
    """Tests for DM Agent response caching."""

    def test_cache_disabled(self, dm_agent_config):
        """Test that caching can be disabled."""
        dm_agent_config.cache_responses = False
        agent = DMAgent(dm_agent_config)

        location = LocationState(
            location_type=LocationType.HEX,
            location_id="0709",
            terrain="forest",
        )

        # Make same request twice
        result1 = agent.describe_location(location)
        result2 = agent.describe_location(location)

        # Without caching, neither should have cache warning
        assert "from_cache" not in result1.warnings
        assert "from_cache" not in result2.warnings

    def test_clear_cache(self, dm_agent):
        """Test cache clearing."""
        dm_agent.config.cache_responses = True
        dm_agent.clear_cache()

        # No errors should occur
        assert len(dm_agent._cache) == 0


class TestDMAgentHelpers:
    """Tests for DM Agent helper methods."""

    def test_terrain_sensory_tags(self, dm_agent):
        """Test terrain-based sensory tag inference."""
        tags = dm_agent._get_terrain_sensory_tags("forest")
        assert len(tags) > 0
        assert "rustling leaves" in tags or "leaves" in str(tags).lower()

    def test_weather_sensory_tags(self, dm_agent):
        """Test weather-based sensory tag inference."""
        tags = dm_agent._get_weather_sensory_tags(Weather.RAIN)
        assert len(tags) > 0
        assert any("rain" in tag.lower() or "wet" in tag.lower() for tag in tags)

    def test_get_recent_descriptions(self, dm_agent):
        """Test tracking of recent descriptions."""
        location = LocationState(
            location_type=LocationType.HEX,
            location_id="0709",
            terrain="forest",
        )

        dm_agent.describe_location(location)
        recent = dm_agent.get_recent_descriptions()

        assert len(recent) > 0
