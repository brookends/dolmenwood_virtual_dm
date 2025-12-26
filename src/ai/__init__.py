"""
AI/LLM integration module for Dolmenwood Virtual DM.

This module provides LLM-powered descriptions and narration while
strictly maintaining mechanical authority in the Python game system.

The LLM is ADVISORY ONLY - it cannot:
- Roll dice or generate random numbers
- Decide success or failure of actions
- Alter game state in any way
- Invent rules or mechanics

Components:
- LLM Provider: Abstraction over LLM APIs with rate limiting and validation
- Prompt Schemas: Structured prompts for each use case
- DM Agent: Central orchestrator for all LLM interactions
"""

from src.ai.llm_provider import (
    LLMProvider,
    LLMRole,
    LLMMessage,
    LLMResponse,
    LLMConfig,
    LLMManager,
    BaseLLMClient,
    AnthropicClient,
    OpenAIClient,
    MockLLMClient,
    get_llm_manager,
)

from src.ai.prompt_schemas import (
    PromptSchemaType,
    PromptSchema,
    ExplorationDescriptionInputs,
    ExplorationDescriptionOutput,
    ExplorationDescriptionSchema,
    EncounterFramingInputs,
    EncounterFramingOutput,
    EncounterFramingSchema,
    CombatNarrationInputs,
    CombatNarrationOutput,
    CombatNarrationSchema,
    ResolvedAction,
    NPCDialogueInputs,
    NPCDialogueOutput,
    NPCDialogueSchema,
    FailureConsequenceInputs,
    FailureConsequenceOutput,
    FailureConsequenceSchema,
    DowntimeSummaryInputs,
    DowntimeSummaryOutput,
    DowntimeSummarySchema,
    create_schema,
)

from src.ai.dm_agent import (
    DMAgentConfig,
    DescriptionResult,
    DMAgent,
    get_dm_agent,
    reset_dm_agent,
)

__all__ = [
    # LLM Provider
    "LLMProvider",
    "LLMRole",
    "LLMMessage",
    "LLMResponse",
    "LLMConfig",
    "LLMManager",
    "BaseLLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "MockLLMClient",
    "get_llm_manager",
    # Prompt Schemas
    "PromptSchemaType",
    "PromptSchema",
    "ExplorationDescriptionInputs",
    "ExplorationDescriptionOutput",
    "ExplorationDescriptionSchema",
    "EncounterFramingInputs",
    "EncounterFramingOutput",
    "EncounterFramingSchema",
    "CombatNarrationInputs",
    "CombatNarrationOutput",
    "CombatNarrationSchema",
    "ResolvedAction",
    "NPCDialogueInputs",
    "NPCDialogueOutput",
    "NPCDialogueSchema",
    "FailureConsequenceInputs",
    "FailureConsequenceOutput",
    "FailureConsequenceSchema",
    "DowntimeSummaryInputs",
    "DowntimeSummaryOutput",
    "DowntimeSummarySchema",
    "create_schema",
    # DM Agent
    "DMAgentConfig",
    "DescriptionResult",
    "DMAgent",
    "get_dm_agent",
    "reset_dm_agent",
]
