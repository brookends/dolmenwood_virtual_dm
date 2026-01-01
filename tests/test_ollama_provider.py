"""
Tests for the Ollama LLM provider integration.

Tests cover:
- OllamaClient initialization
- Connection handling (server up/down)
- Model availability checking
- Message formatting
- Response parsing
- Error handling (model not found, connection refused)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ai.llm_provider import (
    LLMConfig,
    LLMProvider,
    LLMMessage,
    LLMRole,
    LLMResponse,
    LLMManager,
    OllamaClient,
)


class TestOllamaClientInitialization:
    """Tests for OllamaClient initialization."""

    def test_ollama_provider_enum_exists(self):
        """Test that OLLAMA provider is in the enum."""
        assert hasattr(LLMProvider, "OLLAMA")
        assert LLMProvider.OLLAMA.value == "ollama"

    def test_config_has_ollama_host(self):
        """Test that LLMConfig has ollama_host field."""
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="mistral:7b",
            ollama_host="http://localhost:11434",
        )
        assert config.ollama_host == "http://localhost:11434"

    def test_config_ollama_host_default(self):
        """Test that ollama_host defaults to None."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)
        assert config.ollama_host is None

    @patch("src.ai.llm_provider.OllamaClient._initialize_client")
    def test_client_uses_default_host(self, mock_init):
        """Test that client uses default host when not specified."""
        mock_init.return_value = None  # Don't actually initialize
        config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")

        with patch.dict("os.environ", {}, clear=True):
            client = OllamaClient(config)
            assert client._host == "http://localhost:11434"

    @patch("src.ai.llm_provider.OllamaClient._initialize_client")
    def test_client_uses_custom_host(self, mock_init):
        """Test that client uses custom host when specified."""
        mock_init.return_value = None
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="mistral:7b",
            ollama_host="http://192.168.1.100:11434",
        )
        client = OllamaClient(config)
        assert client._host == "http://192.168.1.100:11434"

    @patch("src.ai.llm_provider.OllamaClient._initialize_client")
    def test_client_uses_env_var_host(self, mock_init):
        """Test that client uses OLLAMA_HOST env var."""
        mock_init.return_value = None
        config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")

        with patch.dict("os.environ", {"OLLAMA_HOST": "http://remote:11434"}):
            client = OllamaClient(config)
            assert client._host == "http://remote:11434"


class TestOllamaClientWithMockedOllama:
    """Tests for OllamaClient with mocked ollama package."""

    @pytest.fixture
    def mock_ollama_module(self):
        """Create a mock ollama module."""
        mock_module = MagicMock()
        mock_client_instance = MagicMock()
        mock_module.Client.return_value = mock_client_instance
        return mock_module, mock_client_instance

    def test_is_available_when_connected(self, mock_ollama_module):
        """Test is_available returns True when server is reachable."""
        mock_module, mock_client = mock_ollama_module
        mock_client.list.return_value = {"models": []}

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            client = OllamaClient(config)
            # Manually set the client since we're mocking
            client._client = mock_client

            assert client.is_available() is True

    def test_is_available_when_disconnected(self, mock_ollama_module):
        """Test is_available returns False when server is unreachable."""
        mock_module, mock_client = mock_ollama_module
        mock_client.list.side_effect = ConnectionError("Connection refused")

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            client = OllamaClient(config)
            client._client = mock_client

            assert client.is_available() is False

    def test_complete_success(self, mock_ollama_module):
        """Test successful completion."""
        mock_module, mock_client = mock_ollama_module
        mock_client.chat.return_value = {
            "message": {"content": "The ancient forest looms before you..."},
            "eval_count": 50,
            "prompt_eval_count": 100,
        }

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(
                provider=LLMProvider.OLLAMA,
                model="mistral:7b",
                temperature=0.7,
            )
            client = OllamaClient(config)
            client._client = mock_client

            messages = [LLMMessage(LLMRole.USER, "Describe the forest")]
            response = client.complete(messages, system_prompt="You are a DM")

            assert response.content == "The ancient forest looms before you..."
            assert response.provider == LLMProvider.OLLAMA
            assert response.model == "mistral:7b"
            assert response.usage.get("output_tokens") == 50
            assert response.usage.get("input_tokens") == 100

    def test_complete_with_system_prompt(self, mock_ollama_module):
        """Test that system prompt is included in messages."""
        mock_module, mock_client = mock_ollama_module
        mock_client.chat.return_value = {
            "message": {"content": "Response"},
        }

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            client = OllamaClient(config)
            client._client = mock_client

            messages = [LLMMessage(LLMRole.USER, "Hello")]
            client.complete(messages, system_prompt="You are a helpful assistant")

            # Verify system message was included
            call_args = mock_client.chat.call_args
            ollama_messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))

            assert len(ollama_messages) >= 2
            assert ollama_messages[0]["role"] == "system"
            assert ollama_messages[0]["content"] == "You are a helpful assistant"

    def test_complete_model_not_found(self, mock_ollama_module):
        """Test handling of model not found error."""
        mock_module, mock_client = mock_ollama_module
        mock_client.chat.side_effect = Exception("model 'nonexistent' not found")

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="nonexistent")
            client = OllamaClient(config)
            client._client = mock_client

            messages = [LLMMessage(LLMRole.USER, "Hello")]
            response = client.complete(messages)

            assert "not found" in response.content.lower()
            assert "model_not_found" in response.authority_violations

    def test_complete_no_client(self):
        """Test completion when client is not initialized."""
        config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")

        with patch("src.ai.llm_provider.OllamaClient._initialize_client"):
            client = OllamaClient(config)
            client._client = None  # No client

            messages = [LLMMessage(LLMRole.USER, "Hello")]
            response = client.complete(messages)

            assert "unavailable" in response.content.lower()
            assert "client_unavailable" in response.authority_violations

    def test_list_models(self, mock_ollama_module):
        """Test listing available models."""
        mock_module, mock_client = mock_ollama_module
        mock_client.list.return_value = {
            "models": [
                {"name": "mistral:7b"},
                {"name": "llama3:8b"},
                {"name": "mixtral:8x7b"},
            ]
        }

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            client = OllamaClient(config)
            client._client = mock_client

            models = client.list_models()

            assert "mistral:7b" in models
            assert "llama3:8b" in models
            assert len(models) == 3

    def test_pull_model_success(self, mock_ollama_module):
        """Test pulling a model successfully."""
        mock_module, mock_client = mock_ollama_module
        mock_client.pull.return_value = None  # Success

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            client = OllamaClient(config)
            client._client = mock_client

            result = client.pull_model("llama3:8b")

            assert result is True
            mock_client.pull.assert_called_once_with("llama3:8b")

    def test_pull_model_failure(self, mock_ollama_module):
        """Test handling pull failure."""
        mock_module, mock_client = mock_ollama_module
        mock_client.pull.side_effect = Exception("Network error")

        with patch.dict("sys.modules", {"ollama": mock_module}):
            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            client = OllamaClient(config)
            client._client = mock_client

            result = client.pull_model("llama3:8b")

            assert result is False


class TestLLMManagerOllamaIntegration:
    """Tests for LLMManager with Ollama provider."""

    def test_manager_creates_ollama_client(self):
        """Test that manager creates OllamaClient for OLLAMA provider."""
        with patch("src.ai.llm_provider.OllamaClient") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            manager = LLMManager(config)

            mock_class.assert_called_once_with(config)
            assert manager._client == mock_instance

    def test_manager_ollama_availability(self):
        """Test manager reports availability correctly for Ollama."""
        with patch("src.ai.llm_provider.OllamaClient") as mock_class:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = True
            mock_class.return_value = mock_instance

            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            manager = LLMManager(config)

            assert manager.is_available() is True

    def test_manager_ollama_unavailable(self):
        """Test manager reports unavailability correctly for Ollama."""
        with patch("src.ai.llm_provider.OllamaClient") as mock_class:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = False
            mock_class.return_value = mock_instance

            config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")
            manager = LLMManager(config)

            assert manager.is_available() is False


class TestOllamaMessageFormatting:
    """Tests for message formatting in OllamaClient."""

    @pytest.fixture
    def client_with_mock(self):
        """Create an OllamaClient with a mocked internal client."""
        config = LLMConfig(provider=LLMProvider.OLLAMA, model="mistral:7b")

        with patch("src.ai.llm_provider.OllamaClient._initialize_client"):
            client = OllamaClient(config)
            client._client = MagicMock()
            client._client.chat.return_value = {"message": {"content": "OK"}}
            return client

    def test_user_message_formatting(self, client_with_mock):
        """Test that user messages are formatted correctly."""
        messages = [LLMMessage(LLMRole.USER, "Hello, DM!")]
        client_with_mock.complete(messages)

        call_args = client_with_mock._client.chat.call_args
        ollama_messages = call_args.kwargs.get("messages", [])

        assert len(ollama_messages) == 1
        assert ollama_messages[0]["role"] == "user"
        assert ollama_messages[0]["content"] == "Hello, DM!"

    def test_assistant_message_formatting(self, client_with_mock):
        """Test that assistant messages are formatted correctly."""
        messages = [
            LLMMessage(LLMRole.USER, "Hello"),
            LLMMessage(LLMRole.ASSISTANT, "Greetings, adventurer!"),
            LLMMessage(LLMRole.USER, "What do I see?"),
        ]
        client_with_mock.complete(messages)

        call_args = client_with_mock._client.chat.call_args
        ollama_messages = call_args.kwargs.get("messages", [])

        assert len(ollama_messages) == 3
        assert ollama_messages[1]["role"] == "assistant"
        assert ollama_messages[1]["content"] == "Greetings, adventurer!"

    def test_options_passed_correctly(self, client_with_mock):
        """Test that temperature and max_tokens are passed correctly."""
        client_with_mock.config.temperature = 0.5
        client_with_mock.config.max_tokens = 500

        messages = [LLMMessage(LLMRole.USER, "Test")]
        client_with_mock.complete(messages)

        call_args = client_with_mock._client.chat.call_args
        options = call_args.kwargs.get("options", {})

        assert options.get("temperature") == 0.5
        assert options.get("num_predict") == 500


class TestOllamaRecommendedModels:
    """Documentation tests for recommended models."""

    def test_recommended_models_documented(self):
        """Verify that OllamaClient documents recommended models."""
        # This is a documentation check - the docstring should mention models
        docstring = OllamaClient.__doc__

        assert "mistral" in docstring.lower()
        assert "llama" in docstring.lower()
        assert "7b" in docstring or "8b" in docstring
