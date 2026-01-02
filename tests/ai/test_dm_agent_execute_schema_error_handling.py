"""
Tests for DMAgent _execute_schema error handling.

Phase 8: Verify that _execute_schema() handles LLM failures gracefully
by returning a safe fallback message and logging errors to RunLog.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.ai.dm_agent import DMAgent, DMAgentConfig, DescriptionResult
from src.ai.llm_provider import (
    LLMConfig,
    LLMProvider,
    LLMManager,
    LLMMessage,
    LLMRole,
    LLMResponse,
    MockLLMClient,
)
from src.ai.prompt_schemas import (
    PromptSchemaType,
    ExplorationDescriptionInputs,
    ExplorationDescriptionSchema,
)
from src.data_models import LocationState, LocationType
from src.observability.run_log import get_run_log, reset_run_log


class RaisingMockLLMClient(MockLLMClient):
    """Mock LLM client that raises an exception."""

    def __init__(self, config: LLMConfig, exception_msg: str = "LLM service unavailable"):
        super().__init__(config)
        self._exception_msg = exception_msg

    def complete(self, messages, system_prompt=None, **kwargs) -> LLMResponse:
        """Raise an exception instead of returning a response."""
        raise RuntimeError(self._exception_msg)


@pytest.fixture
def mock_llm_config():
    """Mock LLM configuration."""
    return LLMConfig(
        provider=LLMProvider.MOCK,
        model="mock-model",
        max_tokens=512,
    )


@pytest.fixture
def raising_llm_manager(mock_llm_config):
    """LLM manager that raises exceptions."""
    manager = LLMManager(mock_llm_config)
    manager._client = RaisingMockLLMClient(mock_llm_config)
    return manager


@pytest.fixture
def dm_agent_with_raising_llm(raising_llm_manager):
    """DMAgent with an LLM that raises exceptions."""
    config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
    agent = DMAgent(config)
    # Replace the internal LLM manager with our raising one
    agent._llm = raising_llm_manager
    return agent


@pytest.fixture
def sample_location_state():
    """Sample location state for testing."""
    return LocationState(
        location_type=LocationType.HEX,
        location_id="0705",
        name="Fogmire Edge",
        terrain="swamp",
    )


class TestExecuteSchemaErrorHandling:
    """Test _execute_schema handles LLM errors gracefully."""

    def test_returns_fallback_on_llm_exception(
        self, dm_agent_with_raising_llm, sample_location_state
    ):
        """When LLM raises, _execute_schema should return fallback message."""
        # Create location description request
        result = dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        # Should return a result (not raise)
        assert isinstance(result, DescriptionResult)

        # Should not be successful
        assert result.success is False

        # Should contain fallback message with oracle suggestion
        assert "oracle" in result.content.lower()
        assert "Mythic GME" in result.content or "fate check" in result.content

    def test_fallback_includes_error_in_warnings(
        self, dm_agent_with_raising_llm, sample_location_state
    ):
        """Fallback result should include error message in warnings."""
        result = dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        # Should have warnings
        assert len(result.warnings) > 0

        # Should mention the error
        assert any("LLM error" in w for w in result.warnings)
        assert any("unavailable" in w.lower() for w in result.warnings)

    def test_fallback_suggests_oracle(
        self, dm_agent_with_raising_llm, sample_location_state
    ):
        """Fallback should suggest using oracle."""
        result = dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        # Should have oracle_suggested warning
        assert "oracle_suggested" in result.warnings


class TestExecuteSchemaLogsErrors:
    """Test that _execute_schema logs errors to RunLog."""

    def test_logs_failed_llm_call_to_runlog(
        self, dm_agent_with_raising_llm, sample_location_state
    ):
        """LLM failure should be logged to RunLog."""
        reset_run_log()
        run_log = get_run_log()

        # Make the failing call
        dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        # Get LLM calls from run log
        llm_events = run_log.get_llm_calls()

        # Should have at least one failed LLM call
        assert len(llm_events) >= 1

        # Find the failed call
        failed_calls = [e for e in llm_events if not e.success]
        assert len(failed_calls) >= 1

        # Check error was logged
        failed_call = failed_calls[0]
        assert failed_call.error_message != ""
        assert "unavailable" in failed_call.error_message.lower()

    def test_logs_schema_name_on_failure(
        self, dm_agent_with_raising_llm, sample_location_state
    ):
        """Failed call should log the schema name."""
        reset_run_log()
        run_log = get_run_log()

        dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        llm_events = run_log.get_llm_calls()
        failed_calls = [e for e in llm_events if not e.success]

        assert len(failed_calls) >= 1
        # Should record schema name
        assert failed_calls[0].schema_name is not None
        assert "Schema" in failed_calls[0].schema_name or "location" in failed_calls[0].schema_name.lower()


class TestExecuteSchemaSuccessStillWorks:
    """Test that successful calls still work correctly."""

    def test_successful_call_returns_content(self, sample_location_state):
        """Successful LLM call should return normal content."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        agent = DMAgent(config)

        result = agent.describe_location(
            location=sample_location_state,
        )

        # Should be successful with mock provider
        assert result.success is True
        assert len(result.content) > 0
        # Should not have LLM error warnings
        assert not any("LLM error" in w for w in result.warnings)

    def test_successful_call_logs_to_runlog(self, sample_location_state):
        """Successful call should also be logged."""
        reset_run_log()
        run_log = get_run_log()

        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        agent = DMAgent(config)

        agent.describe_location(
            location=sample_location_state,
        )

        llm_events = run_log.get_llm_calls()
        successful_calls = [e for e in llm_events if e.success]

        assert len(successful_calls) >= 1


class TestDifferentExceptionTypes:
    """Test handling of different exception types."""

    @pytest.fixture
    def agent_with_custom_error(self, mock_llm_config):
        """Create agent with custom error type."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        agent = DMAgent(config)
        return agent, mock_llm_config

    def test_handles_connection_error(self, agent_with_custom_error, sample_location_state):
        """Connection errors should be handled gracefully."""
        agent, mock_config = agent_with_custom_error

        class ConnectionErrorClient(MockLLMClient):
            def complete(self, *args, **kwargs):
                raise ConnectionError("Network unreachable")

        agent._llm._client = ConnectionErrorClient(mock_config)

        result = agent.describe_location(
            location=sample_location_state,
        )

        assert result.success is False
        assert "oracle" in result.content.lower()
        assert any("Network unreachable" in w for w in result.warnings)

    def test_handles_timeout_error(self, agent_with_custom_error, sample_location_state):
        """Timeout errors should be handled gracefully."""
        agent, mock_config = agent_with_custom_error

        class TimeoutClient(MockLLMClient):
            def complete(self, *args, **kwargs):
                raise TimeoutError("Request timed out")

        agent._llm._client = TimeoutClient(mock_config)

        result = agent.describe_location(
            location=sample_location_state,
        )

        assert result.success is False
        assert "oracle" in result.content.lower()

    def test_handles_value_error(self, agent_with_custom_error, sample_location_state):
        """Value errors should be handled gracefully."""
        agent, mock_config = agent_with_custom_error

        class ValueErrorClient(MockLLMClient):
            def complete(self, *args, **kwargs):
                raise ValueError("Invalid API response")

        agent._llm._client = ValueErrorClient(mock_config)

        result = agent.describe_location(
            location=sample_location_state,
        )

        assert result.success is False
        assert "oracle" in result.content.lower()


class TestFallbackMessageContent:
    """Test the specific content of fallback messages."""

    def test_fallback_is_bracketed(self, dm_agent_with_raising_llm, sample_location_state):
        """Fallback message should be in brackets to indicate system message."""
        result = dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        assert result.content.startswith("[")
        assert result.content.endswith("]")

    def test_fallback_mentions_describe_yourself(
        self, dm_agent_with_raising_llm, sample_location_state
    ):
        """Fallback should suggest user can describe the scene themselves."""
        result = dm_agent_with_raising_llm.describe_location(
            location=sample_location_state,
        )

        assert "yourself" in result.content.lower()
