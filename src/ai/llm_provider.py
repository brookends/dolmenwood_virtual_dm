"""
LLM Provider abstraction for Dolmenwood Virtual DM.

This module provides a clean interface to LLM services with:
- Support for multiple providers (Anthropic Claude, OpenAI)
- Rate limiting and retry logic
- Response validation and sanitization
- Strict authority boundary enforcement

CRITICAL: The LLM is ADVISORY ONLY. It cannot:
- Roll dice or generate random numbers
- Decide success or failure of actions
- Alter game state in any way
- Invent rules or mechanics
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import logging
import time
import os

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"  # Local models via Ollama
    MOCK = "mock"  # For testing


class LLMRole(str, Enum):
    """Roles for messages in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    """A message in an LLM conversation."""

    role: LLMRole
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    provider: LLMProvider
    usage: dict[str, int] = field(default_factory=dict)  # tokens used
    raw_response: Optional[Any] = None

    # Validation flags
    authority_violations: list[str] = field(default_factory=list)
    sanitized: bool = False


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""

    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.7
    api_key: Optional[str] = None

    # Ollama-specific settings
    ollama_host: Optional[str] = None  # Default: http://localhost:11434

    # Rate limiting
    max_retries: int = 3
    retry_delay: float = 1.0

    # Response constraints
    max_response_length: int = 4000


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a completion from the LLM."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Anthropic client."""
        try:
            import anthropic

            api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
            else:
                logger.warning(
                    "ANTHROPIC_API_KEY not set. Set the environment variable or pass api_key in config."
                )
        except ImportError:
            logger.warning(
                "anthropic package not installed. "
                "Install with: pip install dolmenwood-virtual-dm[llm-anthropic]"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")

    def is_available(self) -> bool:
        """Check if Anthropic API is available."""
        return self._client is not None

    def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate completion using Claude."""
        if not self._client:
            return LLMResponse(
                content="[LLM unavailable - using fallback]",
                model=self.config.model,
                provider=LLMProvider.ANTHROPIC,
                authority_violations=["client_unavailable"],
            )

        # Convert messages to Anthropic format
        anthropic_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
            if msg.role != LLMRole.SYSTEM
        ]

        for attempt in range(self.config.max_retries):
            try:
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt or "",
                    messages=anthropic_messages,
                )

                content = response.content[0].text if response.content else ""

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=LLMProvider.ANTHROPIC,
                    usage={
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                    raw_response=response,
                )
            except Exception as e:
                logger.warning(f"Anthropic API attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))

        return LLMResponse(
            content="[LLM request failed after retries]",
            model=self.config.model,
            provider=LLMProvider.ANTHROPIC,
            authority_violations=["request_failed"],
        )


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the OpenAI client."""
        try:
            import openai

            api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
            if api_key:
                self._client = openai.OpenAI(api_key=api_key)
            else:
                logger.warning(
                    "OPENAI_API_KEY not set. Set the environment variable or pass api_key in config."
                )
        except ImportError:
            logger.warning(
                "openai package not installed. "
                "Install with: pip install dolmenwood-virtual-dm[llm-openai]"
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")

    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        return self._client is not None

    def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate completion using OpenAI."""
        if not self._client:
            return LLMResponse(
                content="[LLM unavailable - using fallback]",
                model=self.config.model,
                provider=LLMProvider.OPENAI,
                authority_violations=["client_unavailable"],
            )

        # Convert messages to OpenAI format
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            openai_messages.append(
                {
                    "role": msg.role.value,
                    "content": msg.content,
                }
            )

        for attempt in range(self.config.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=openai_messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )

                content = response.choices[0].message.content or ""

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=LLMProvider.OPENAI,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                    },
                    raw_response=response,
                )
            except Exception as e:
                logger.warning(f"OpenAI API attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))

        return LLMResponse(
            content="[LLM request failed after retries]",
            model=self.config.model,
            provider=LLMProvider.OPENAI,
            authority_violations=["request_failed"],
        )


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama local LLM server.

    Ollama provides a simple way to run LLMs locally. This client connects
    to a local Ollama server (default: http://localhost:11434) and uses
    the chat API for completions.

    Recommended models for Dolmenwood DM:
    - mistral:7b - Good balance of speed and quality
    - llama3:8b - Strong instruction following
    - mixtral:8x7b - Higher quality, needs more RAM
    - llama3:70b - Best quality, requires significant hardware

    Usage:
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="mistral:7b",  # or any model you have pulled
            ollama_host="http://localhost:11434",  # optional
        )
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._host = config.ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Ollama client."""
        try:
            import ollama

            # Test connection by listing models
            self._client = ollama.Client(host=self._host)
            # Verify server is reachable
            try:
                self._client.list()
                logger.info(f"Connected to Ollama server at {self._host}")
            except Exception as e:
                logger.warning(f"Ollama server not reachable at {self._host}: {e}")
                self._client = None
        except ImportError:
            logger.warning(
                "ollama package not installed. "
                "Install with: pip install ollama"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")

    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        if not self._client:
            return False
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def _check_model_available(self) -> bool:
        """Check if the configured model is available locally."""
        if not self._client:
            return False
        try:
            models = self._client.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            # Check for exact match or partial match (e.g., "mistral:7b" matches "mistral:7b-instruct")
            return any(
                self.config.model in name or name.startswith(self.config.model.split(":")[0])
                for name in model_names
            )
        except Exception:
            return False

    def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate completion using Ollama."""
        if not self._client:
            return LLMResponse(
                content="[Ollama unavailable - server not running or not reachable]",
                model=self.config.model,
                provider=LLMProvider.OLLAMA,
                authority_violations=["client_unavailable"],
            )

        # Convert messages to Ollama format
        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            ollama_messages.append(
                {
                    "role": msg.role.value,
                    "content": msg.content,
                }
            )

        for attempt in range(self.config.max_retries):
            try:
                response = self._client.chat(
                    model=self.config.model,
                    messages=ollama_messages,
                    options={
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    },
                )

                content = response.get("message", {}).get("content", "")

                # Extract token usage if available
                usage = {}
                if "eval_count" in response:
                    usage["output_tokens"] = response["eval_count"]
                if "prompt_eval_count" in response:
                    usage["input_tokens"] = response["prompt_eval_count"]

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=LLMProvider.OLLAMA,
                    usage=usage,
                    raw_response=response,
                )
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Ollama API attempt {attempt + 1} failed: {e}")

                # Check for common errors
                if "model" in error_msg.lower() and "not found" in error_msg.lower():
                    return LLMResponse(
                        content=f"[Model '{self.config.model}' not found. Run: ollama pull {self.config.model}]",
                        model=self.config.model,
                        provider=LLMProvider.OLLAMA,
                        authority_violations=["model_not_found"],
                    )

                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))

        return LLMResponse(
            content="[Ollama request failed after retries]",
            model=self.config.model,
            provider=LLMProvider.OLLAMA,
            authority_violations=["request_failed"],
        )

    def list_models(self) -> list[str]:
        """List available models on the Ollama server."""
        if not self._client:
            return []
        try:
            models = self._client.list()
            return [m.get("name", "") for m in models.get("models", [])]
        except Exception:
            return []

    def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from the Ollama library.

        Args:
            model_name: Model to pull (e.g., "mistral:7b", "llama3:8b")

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        try:
            logger.info(f"Pulling model {model_name}... (this may take a while)")
            self._client.pull(model_name)
            logger.info(f"Successfully pulled {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._responses: list[str] = []
        self._response_index = 0

    def set_responses(self, responses: list[str]) -> None:
        """Set canned responses for testing."""
        self._responses = responses
        self._response_index = 0

    def is_available(self) -> bool:
        """Mock client is always available."""
        return True

    def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Return mock response."""
        if self._responses:
            content = self._responses[self._response_index % len(self._responses)]
            self._response_index += 1
        else:
            content = "[Mock LLM response]"

        return LLMResponse(
            content=content,
            model="mock",
            provider=LLMProvider.MOCK,
            usage={"tokens": 100},
        )


class LLMManager:
    """
    Central manager for LLM interactions.

    Provides:
    - Client initialization and fallback
    - Response validation and sanitization
    - Authority boundary enforcement
    - Logging and monitoring
    """

    # Compiled regex patterns for authority violations (using word boundaries)
    # These detect when the LLM tries to usurp mechanical authority
    import re as _re

    # Patterns for dice/roll mechanics (LLM shouldn't invoke these)
    _DICE_ROLL_PATTERNS = _re.compile(
        r"""
        \broll\b                    # "roll" as a word (not troll, scroll, stroll)
        | \brolls\b                 # "rolls"
        | \brolling\b               # "rolling"
        | \brolled\s+a?\s*\d+       # "rolled 15" or "rolled a 15" (deciding outcomes)
        | \bd20\b                   # dice notation
        | \bd12\b
        | \bd10\b
        | \bd8\b
        | \bd6\b
        | \bd4\b
        | \bd100\b
        | \d+d\d+                   # XdY notation like "2d6"
        | \bmake\s+a\s+.*\b(check|save|roll)\b  # "make a saving throw", "make a check"
        | \bsave\s+vs\b             # "save vs poison"
        | \bsaving\s+throw\b        # "saving throw"
        """,
        _re.VERBOSE | _re.IGNORECASE,
    )

    # Patterns for outcome determination (LLM shouldn't decide these)
    _OUTCOME_PATTERNS = _re.compile(
        r"""
        \byou\s+take\s+\d+          # "you take 5 damage" (deciding damage amounts)
        | \byou\s+lose\s+\d+        # "you lose 3 hp"
        | \byou\s+gain\s+\d+        # "you gain 50 xp"
        | \byou\s+succeed\b         # "you succeed"
        | \byou\s+fail\b            # "you fail"
        | \bdeals?\s+\d+\s+damage\b # "deals 5 damage" (deciding damage)
        | \binflicts?\s+\d+\s+damage\b  # "inflicts 8 damage"
        """,
        _re.VERBOSE | _re.IGNORECASE,
    )

    # Patterns allowed when narrating already-resolved actions
    NARRATION_CONTEXT_ALLOWED = [
        "damage",  # OK when describing what happened (without numbers)
        "hit",  # OK when describing combat results
        "miss",  # OK when describing combat results
        "wounded",  # OK for describing injury
        "injured",  # OK for describing injury
    ]

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM manager.

        Args:
            config: LLM configuration. If None, uses defaults.
        """
        self.config = config or LLMConfig()
        self._client: Optional[BaseLLMClient] = None
        self._fallback_client: Optional[BaseLLMClient] = None
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize primary and fallback clients."""
        if self.config.provider == LLMProvider.ANTHROPIC:
            self._client = AnthropicClient(self.config)
            # Could add OpenAI as fallback
        elif self.config.provider == LLMProvider.OPENAI:
            self._client = OpenAIClient(self.config)
        elif self.config.provider == LLMProvider.OLLAMA:
            self._client = OllamaClient(self.config)
        elif self.config.provider == LLMProvider.MOCK:
            self._client = MockLLMClient(self.config)

    def is_available(self) -> bool:
        """Check if any LLM is available."""
        if self._client and self._client.is_available():
            return True
        if self._fallback_client and self._fallback_client.is_available():
            return True
        return False

    def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        allow_narration_context: bool = False,
    ) -> LLMResponse:
        """
        Generate an LLM completion with validation.

        Args:
            messages: Conversation messages
            system_prompt: System prompt to prepend
            allow_narration_context: If True, allows damage/hit narration

        Returns:
            Validated and potentially sanitized LLMResponse
        """
        # Try primary client
        if self._client and self._client.is_available():
            response = self._client.complete(messages, system_prompt)
        elif self._fallback_client and self._fallback_client.is_available():
            response = self._fallback_client.complete(messages, system_prompt)
        else:
            return LLMResponse(
                content="[No LLM available]",
                model="none",
                provider=LLMProvider.MOCK,
                authority_violations=["no_provider_available"],
            )

        # Validate and sanitize response
        response = self._validate_response(response, allow_narration_context)

        return response

    def _validate_response(
        self,
        response: LLMResponse,
        allow_narration_context: bool,
    ) -> LLMResponse:
        """
        Validate response for authority violations.

        The LLM MUST NOT:
        - Roll dice or generate random numbers
        - Decide success or failure
        - Alter game state
        - Invent rules or mechanics

        Uses word-boundary regex patterns to avoid false positives
        (e.g., "troll" should not trigger "roll" violation).
        """
        violations = []
        content = response.content

        # Check for dice/roll mechanic violations
        for match in self._DICE_ROLL_PATTERNS.finditer(content):
            matched_text = match.group(0).strip()
            violations.append(f"dice_mechanic_violation:{matched_text}")

        # Check for outcome determination violations
        for match in self._OUTCOME_PATTERNS.finditer(content):
            matched_text = match.group(0).strip()
            violations.append(f"outcome_determination_violation:{matched_text}")

        if violations:
            response.authority_violations.extend(violations)
            logger.warning(f"LLM authority violations detected: {violations}")

        # Truncate if too long
        if len(response.content) > self.config.max_response_length:
            response.content = response.content[: self.config.max_response_length] + "..."
            response.sanitized = True

        return response

    def get_mock_client(self) -> MockLLMClient:
        """Get a mock client for testing."""
        return MockLLMClient(self.config)


def get_llm_manager(config: Optional[LLMConfig] = None) -> LLMManager:
    """Factory function to get an LLM manager instance."""
    return LLMManager(config)
