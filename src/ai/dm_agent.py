"""
DM Agent for Dolmenwood Virtual DM.

The central orchestrator for LLM-based descriptions and narration.
This agent is STRICTLY ADVISORY - it provides descriptions and dialogue
but NEVER decides outcomes or alters game state.

The DM Agent provides:
- Exploration descriptions for locations
- Encounter framing for new encounters
- Combat narration for resolved actions
- NPC dialogue with lore integration
- Failure consequence descriptions
- Downtime summaries

CRITICAL: All mechanical resolution happens in Python.
The LLM only provides evocative descriptions of what has been determined.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import logging

from src.ai.llm_provider import (
    LLMManager,
    LLMConfig,
    LLMMessage,
    LLMRole,
    LLMResponse,
    LLMProvider,
    get_llm_manager,
)
from src.ai.prompt_schemas import (
    PromptSchemaType,
    PromptSchema,
    ExplorationDescriptionInputs,
    ExplorationDescriptionSchema,
    EncounterFramingInputs,
    EncounterFramingSchema,
    CombatNarrationInputs,
    CombatNarrationSchema,
    ResolvedAction,
    NPCDialogueInputs,
    NPCDialogueSchema,
    FailureConsequenceInputs,
    FailureConsequenceSchema,
    DowntimeSummaryInputs,
    DowntimeSummarySchema,
    CombatConclusionInputs,
    CombatConclusionSchema,
    DungeonEventInputs,
    DungeonEventSchema,
    RestExperienceInputs,
    RestExperienceSchema,
    POIApproachInputs,
    POIApproachSchema,
    POIEntryInputs,
    POIEntrySchema,
    POIFeatureInputs,
    POIFeatureSchema,
    ResolvedActionInputs,
    ResolvedActionSchema,
    IntentParseInputs,
    IntentParseSchema,
    IntentParseOutput,
    NarrativeIntentInputs,
    NarrativeIntentSchema,
    NarrativeIntentOutput,
    create_schema,
)
from src.data_models import (
    LocationState,
    EncounterState,
    NPC,
    Weather,
    Season,
    TimeOfDay,
    SocialContext,
    SocialParticipant,
    SocialOrigin,
)

# Import lore search types (optional integration)
from src.ai.lore_search import (
    LoreSearchInterface,
    LoreSearchQuery,
    LoreSearchResult,
    LoreCategory,
    NullLoreSearch,
)


logger = logging.getLogger(__name__)


@dataclass
class DMAgentConfig:
    """Configuration for the DM Agent."""

    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    llm_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.7

    # Behavior settings
    verbose_logging: bool = False
    cache_responses: bool = True
    validate_all_responses: bool = True


@dataclass
class DescriptionResult:
    """Result of a description request."""

    content: str
    schema_used: PromptSchemaType
    success: bool
    warnings: list[str] = field(default_factory=list)
    authority_violations: list[str] = field(default_factory=list)


class DMAgent:
    """
    The Dolmenwood Virtual DM Agent.

    Provides evocative descriptions and narration while strictly
    avoiding any mechanical authority. The Python game system is
    the sole arbiter of outcomes - this agent only describes them.
    """

    def __init__(
        self,
        config: Optional[DMAgentConfig] = None,
        lore_search: Optional[LoreSearchInterface] = None,
    ):
        """
        Initialize the DM Agent.

        Args:
            config: Agent configuration. If None, uses defaults.
            lore_search: Optional lore search interface for content enrichment.
                         If None, uses NullLoreSearch (returns empty results).
        """
        self.config = config or DMAgentConfig()

        # Initialize LLM manager
        llm_config = LLMConfig(
            provider=self.config.llm_provider,
            model=self.config.llm_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        self._llm = get_llm_manager(llm_config)

        # Initialize lore search (optional enrichment)
        self._lore_search: LoreSearchInterface = lore_search or NullLoreSearch()

        # Response cache (simple dict-based)
        self._cache: dict[str, str] = {}

        # Track recent descriptions for context
        self._recent_descriptions: list[str] = []
        self._max_recent = 5

    def is_available(self) -> bool:
        """Check if the LLM is available."""
        return self._llm.is_available()

    # =========================================================================
    # LORE SEARCH INTEGRATION
    # =========================================================================

    def retrieve_lore(
        self,
        query: str,
        category: Optional[LoreCategory] = None,
        max_results: int = 3,
        current_hex: Optional[str] = None,
        current_npc: Optional[str] = None,
        current_faction: Optional[str] = None,
    ) -> list[LoreSearchResult]:
        """
        Retrieve relevant lore from the content database.

        This is used to enrich LLM prompts with setting-specific information.
        Returns empty list if lore search is disabled or unavailable.

        Args:
            query: Natural language search query
            category: Optional category filter (e.g., FACTION, NPC, HEX)
            max_results: Maximum number of results
            current_hex: Current hex ID for relevance boosting
            current_npc: Current NPC name for relevance boosting
            current_faction: Current faction for relevance boosting

        Returns:
            List of LoreSearchResult with content and citations
        """
        if not self._lore_search.is_available():
            return []

        search_query = LoreSearchQuery(
            query=query,
            categories=[category] if category else [],
            max_results=max_results,
            current_hex=current_hex,
            current_npc=current_npc,
            current_faction=current_faction,
        )

        return self._lore_search.search(search_query)

    def get_lore_enrichment(
        self,
        query: str,
        category: Optional[LoreCategory] = None,
        max_results: int = 2,
    ) -> str:
        """
        Get lore as a formatted string for prompt enrichment.

        Args:
            query: Search query
            category: Optional category filter
            max_results: Maximum results

        Returns:
            Formatted lore string, or empty string if none found
        """
        results = self.retrieve_lore(query, category, max_results)
        if not results:
            return ""

        lines = ["Relevant lore:"]
        for result in results:
            lines.append(f"- {result.content} [{result.source}]")
        return "\n".join(lines)

    def get_lore_status(self) -> dict[str, Any]:
        """Get status of the lore search system."""
        return self._lore_search.get_status()

    @property
    def lore_search_available(self) -> bool:
        """Check if lore search is available."""
        return self._lore_search.is_available()

    # =========================================================================
    # EXPLORATION DESCRIPTIONS
    # =========================================================================

    def describe_location(
        self,
        location: LocationState,
        time_of_day: Optional[TimeOfDay] = None,
        weather: Optional[Weather] = None,
        season: Optional[Season] = None,
        known_threats: Optional[list[str]] = None,
        sensory_tags: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Generate a description of a location.

        Args:
            location: The location state to describe
            time_of_day: Current time of day
            weather: Current weather (for outdoor locations)
            season: Current season
            known_threats: Threats the party is aware of
            sensory_tags: Specific sensory details to include

        Returns:
            DescriptionResult with the location description
        """
        # Build sensory tags from location if not provided
        if sensory_tags is None:
            sensory_tags = self._infer_sensory_tags(location, weather)

        # Build location summary
        location_summary = self._build_location_summary(location)

        inputs = ExplorationDescriptionInputs(
            current_state=location.location_type.value,
            location_summary=location_summary,
            sensory_tags=sensory_tags,
            known_threats=known_threats or [],
            time_of_day=time_of_day.value if time_of_day else "",
            weather=weather.value if weather else "",
            season=season.value if season else "",
        )

        schema = ExplorationDescriptionSchema(inputs)
        return self._execute_schema(schema)

    def describe_hex(
        self,
        hex_id: str,
        terrain: str,
        name: Optional[str] = None,
        features: Optional[list[str]] = None,
        time_of_day: Optional[TimeOfDay] = None,
        weather: Optional[Weather] = None,
        season: Optional[Season] = None,
    ) -> DescriptionResult:
        """
        Convenience method to describe a wilderness hex.

        Args:
            hex_id: The hex identifier (e.g., "0709")
            terrain: Terrain type
            name: Named location in hex, if any
            features: Visible features
            time_of_day: Current time
            weather: Current weather
            season: Current season

        Returns:
            DescriptionResult with the hex description
        """
        # Build location summary
        summary = f"Hex {hex_id}: {terrain}"
        if name:
            summary += f" ({name})"
        if features:
            summary += f". Features: {', '.join(features)}"

        # Infer sensory tags from terrain
        sensory_tags = self._get_terrain_sensory_tags(terrain)
        if weather:
            sensory_tags.extend(self._get_weather_sensory_tags(weather))

        inputs = ExplorationDescriptionInputs(
            current_state="wilderness_travel",
            location_summary=summary,
            sensory_tags=sensory_tags,
            time_of_day=time_of_day.value if time_of_day else "",
            weather=weather.value if weather else "",
            season=season.value if season else "",
        )

        schema = ExplorationDescriptionSchema(inputs)
        return self._execute_schema(schema)

    def describe_dungeon_room(
        self,
        room_name: str,
        room_description: str,
        features: Optional[list[str]] = None,
        light_level: str = "dark",
        known_threats: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Convenience method to describe a dungeon room.

        Args:
            room_name: Name or identifier of the room
            room_description: Base description from content
            features: Visible features
            light_level: Current lighting
            known_threats: Detected threats

        Returns:
            DescriptionResult with the room description
        """
        summary = f"{room_name}: {room_description}"
        if features:
            summary += f" Features: {', '.join(features)}"

        sensory_tags = ["stone", "underground"]
        if light_level == "dark":
            sensory_tags.extend(["shadows", "darkness"])
        elif light_level == "dim":
            sensory_tags.extend(["flickering light", "shadows"])

        inputs = ExplorationDescriptionInputs(
            current_state="dungeon_exploration",
            location_summary=summary,
            sensory_tags=sensory_tags,
            known_threats=known_threats or [],
        )

        schema = ExplorationDescriptionSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # ENCOUNTER FRAMING
    # =========================================================================

    def frame_encounter(
        self,
        encounter: EncounterState,
        creature_name: str,
        number_appearing: int,
        terrain: str,
        time_of_day: Optional[TimeOfDay] = None,
        weather: Optional[Weather] = None,
    ) -> DescriptionResult:
        """
        Generate the initial framing for an encounter.

        This describes what the party SEES when the encounter begins.
        It does NOT reveal surprise status or creature intentions.

        Args:
            encounter: The encounter state
            creature_name: Name of the encountered creature(s)
            number_appearing: How many
            terrain: Current terrain type
            time_of_day: Current time
            weather: Current weather

        Returns:
            DescriptionResult with encounter framing
        """
        inputs = EncounterFramingInputs(
            encounter_type=creature_name,
            number_appearing=number_appearing,
            distance_feet=encounter.distance,
            surprise_status=encounter.surprise_status.value,  # Not revealed
            terrain=terrain,
            context=encounter.context or "traveling",
            time_of_day=time_of_day.value if time_of_day else "",
            weather=weather.value if weather else "",
        )

        schema = EncounterFramingSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # COMBAT NARRATION
    # =========================================================================

    def narrate_combat_round(
        self,
        round_number: int,
        resolved_actions: list[dict[str, Any]],
        damage_results: Optional[dict[str, int]] = None,
        conditions_applied: Optional[list[str]] = None,
        morale_results: Optional[list[str]] = None,
        deaths: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Generate narration for a combat round that has been resolved.

        CRITICAL: All outcomes must already be determined by the combat engine.
        This method only describes what happened, it does not determine outcomes.

        Args:
            round_number: Current round number
            resolved_actions: List of resolved action dicts with keys:
                - actor: Who acted
                - action: What they did
                - target: Who they targeted
                - result: hit/miss/etc
                - damage: damage dealt if any
            damage_results: Dict of combatant -> damage taken
            conditions_applied: New conditions this round
            morale_results: Morale check results
            deaths: Who died this round

        Returns:
            DescriptionResult with combat narration
        """
        # Convert dicts to ResolvedAction objects if needed
        action_objects = []
        for action in resolved_actions:
            if isinstance(action, dict):
                action_objects.append(
                    ResolvedAction(
                        actor=action.get("actor", "Unknown"),
                        action=action.get("action", "acts"),
                        target=action.get("target", ""),
                        result=action.get("result", ""),
                        damage=action.get("damage", 0),
                        special_effects=action.get("special_effects", []),
                    )
                )
            else:
                action_objects.append(action)

        inputs = CombatNarrationInputs(
            round_number=round_number,
            resolved_actions=action_objects,
            damage_results=damage_results or {},
            conditions_applied=conditions_applied or [],
            morale_results=morale_results or [],
            deaths=deaths or [],
        )

        schema = CombatNarrationSchema(inputs)
        return self._execute_schema(schema, allow_narration_context=True)

    # =========================================================================
    # NPC DIALOGUE
    # =========================================================================

    def generate_npc_dialogue(
        self,
        npc: NPC,
        conversation_topic: str,
        reaction_result: str,
        known_topics: Optional[list[str]] = None,
        hidden_topics: Optional[list[str]] = None,
        faction_context: str = "",
    ) -> DescriptionResult:
        """
        Generate dialogue for an NPC conversation.

        The NPC will stay in character and respect information boundaries.
        They will NOT reveal hidden topics under any circumstances.

        Args:
            npc: The NPC data
            conversation_topic: What the player is asking about
            reaction_result: Current disposition (hostile, neutral, friendly, etc.)
            known_topics: Topics the NPC knows and can share
            hidden_topics: Topics the NPC knows but must not reveal
            faction_context: Relevant faction information

        Returns:
            DescriptionResult with NPC dialogue
        """
        # Build known topics from NPC data if not provided
        if known_topics is None:
            known_topics = npc.dialogue_hooks.copy()
            if npc.goals:
                known_topics.extend([f"Their goal: {g}" for g in npc.goals])

        # Secrets are always hidden
        if hidden_topics is None:
            hidden_topics = npc.secrets.copy()

        inputs = NPCDialogueInputs(
            npc_name=npc.name,
            npc_personality=npc.personality,
            npc_voice="Period-appropriate speech",  # Could be enhanced
            reaction_result=reaction_result,
            conversation_topic=conversation_topic,
            known_to_npc=known_topics,
            hidden_from_player=hidden_topics,
            faction_context=faction_context,
            previous_interactions=[],  # Could track this
        )

        schema = NPCDialogueSchema(inputs)
        return self._execute_schema(schema)

    def generate_simple_npc_dialogue(
        self,
        npc_name: str,
        personality: str,
        topic: str,
        disposition: str = "neutral",
        known_info: Optional[list[str]] = None,
        secrets: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Simplified NPC dialogue generation without full NPC object.

        Args:
            npc_name: Name of the NPC
            personality: Brief personality description
            topic: What the player is asking about
            disposition: hostile, neutral, friendly, etc.
            known_info: Information NPC can share
            secrets: Information NPC must not reveal

        Returns:
            DescriptionResult with NPC dialogue
        """
        inputs = NPCDialogueInputs(
            npc_name=npc_name,
            npc_personality=personality,
            npc_voice="Period-appropriate speech",
            reaction_result=disposition,
            conversation_topic=topic,
            known_to_npc=known_info or [],
            hidden_from_player=secrets or [],
        )

        schema = NPCDialogueSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # SOCIAL CONTEXT INTEGRATION
    # =========================================================================

    def generate_dialogue_from_context(
        self,
        social_context: SocialContext,
        conversation_topic: str,
        participant_index: int = 0,
    ) -> DescriptionResult:
        """
        Generate NPC dialogue using the active social context.

        This is the primary integration point between the game state's
        SocialContext and the AI dialogue generation. Uses the enhanced
        topic matching system to:
        - Match player questions to relevant known topics
        - Filter topics by disposition requirements
        - Track and hint at secrets
        - Monitor NPC patience

        Args:
            social_context: The active social context from GlobalController
            conversation_topic: What the player is asking about
            participant_index: Which participant to speak (0 = primary)

        Returns:
            DescriptionResult with the NPC dialogue and metadata
        """
        if not social_context.participants:
            return DescriptionResult(
                content="[No participants in social context]",
                schema_used=PromptSchemaType.NPC_DIALOGUE,
                success=False,
                warnings=["No participants available for dialogue"],
            )

        # Get the speaking participant
        if participant_index >= len(social_context.participants):
            participant_index = 0
        participant = social_context.participants[participant_index]

        # Check if participant can communicate
        warning = participant.get_communication_warning()
        if warning and not participant.can_communicate:
            return DescriptionResult(
                content=f"[{participant.name} cannot communicate verbally]",
                schema_used=PromptSchemaType.NPC_DIALOGUE,
                success=False,
                warnings=[warning],
            )

        # Check if conversation has ended due to patience
        if participant.conversation and participant.conversation.conversation_ended:
            return DescriptionResult(
                content=f"[{participant.name} has ended the conversation: "
                f"{participant.conversation.end_reason}]",
                schema_used=PromptSchemaType.NPC_DIALOGUE,
                success=False,
                warnings=[participant.conversation.end_reason],
            )

        # Get previous interactions from context
        previous = social_context.topics_discussed.copy()

        # Convert participant to dialogue inputs (uses enhanced topic system)
        dialogue_data = participant.to_dialogue_inputs(
            conversation_topic=conversation_topic,
            previous_interactions=previous,
        )

        # Check for conversation ended after processing query
        if dialogue_data.get("_conversation_ended"):
            patience_warning = dialogue_data.get("_patience_warning", "")
            return DescriptionResult(
                content=f"[{participant.name} has lost patience and ends the conversation]",
                schema_used=PromptSchemaType.NPC_DIALOGUE,
                success=False,
                warnings=[patience_warning] if patience_warning else [],
            )

        # Extract enhanced metadata before creating schema inputs
        query_result = dialogue_data.pop("_query_result", None)
        is_relevant = dialogue_data.pop("_is_relevant", True)
        dialogue_data.pop("_conversation_ended", None)
        patience_warning = dialogue_data.pop("_patience_warning", None)

        # Create inputs and schema (without underscore-prefixed keys)
        inputs = NPCDialogueInputs(**dialogue_data)
        schema = NPCDialogueSchema(inputs)

        # Execute and track the topic
        result = self._execute_schema(schema)

        # Add topic to discussed list if successful
        if result.success and conversation_topic not in social_context.topics_discussed:
            social_context.topics_discussed.append(conversation_topic)

        # Track secrets that were hinted or revealed
        if query_result:
            for hint_info in query_result.get("hints_to_give", []):
                secret = hint_info.get("secret")
                if secret and secret.secret_id not in social_context.secrets_revealed:
                    if hasattr(secret, "status"):
                        from src.data_models import SecretStatus

                        secret.status = SecretStatus.HINTED
                        secret.hint_count += 1

            for reveal_info in query_result.get("secrets_to_reveal", []):
                secret = reveal_info.get("secret")
                if secret:
                    if hasattr(secret, "status"):
                        from src.data_models import SecretStatus

                        secret.status = SecretStatus.REVEALED
                    if reveal_info.get("content") not in social_context.secrets_revealed:
                        social_context.secrets_revealed.append(reveal_info["content"])

        # Add warnings
        warnings_to_add = []
        if warning:
            warnings_to_add.append(warning)
        if patience_warning:
            warnings_to_add.append(f"NPC patience: {patience_warning}")
        if not is_relevant:
            warnings_to_add.append("Question was not relevant to NPC's knowledge")

        for w in warnings_to_add:
            result.warnings.append(w)

        return result

    def generate_dialogue_for_participant(
        self,
        participant: SocialParticipant,
        conversation_topic: str,
        previous_topics: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Generate dialogue for a specific SocialParticipant.

        Use this when you have a participant but not a full SocialContext,
        such as when talking to a fixed hex NPC directly.

        Args:
            participant: The SocialParticipant to voice
            conversation_topic: What the player is asking about
            previous_topics: Previously discussed topics

        Returns:
            DescriptionResult with the NPC dialogue
        """
        # Check communication capability
        warning = participant.get_communication_warning()
        if warning and not participant.can_communicate:
            return DescriptionResult(
                content=f"[{participant.name} cannot communicate verbally]",
                schema_used=PromptSchemaType.NPC_DIALOGUE,
                success=False,
                warnings=[warning],
            )

        # Convert to dialogue inputs
        dialogue_data = participant.to_dialogue_inputs(
            conversation_topic=conversation_topic,
            previous_interactions=previous_topics,
        )

        inputs = NPCDialogueInputs(**dialogue_data)
        schema = NPCDialogueSchema(inputs)
        result = self._execute_schema(schema)

        if warning:
            result.warnings.append(warning)

        return result

    def frame_social_encounter(
        self,
        social_context: SocialContext,
    ) -> DescriptionResult:
        """
        Generate the opening framing for a social interaction.

        This describes the initial scene when entering SOCIAL_INTERACTION state,
        setting the mood and introducing the participants.

        Args:
            social_context: The social context being entered

        Returns:
            DescriptionResult with the scene framing
        """
        if not social_context.participants:
            return DescriptionResult(
                content="[No participants to describe]",
                schema_used=PromptSchemaType.EXPLORATION_DESCRIPTION,
                success=False,
                warnings=["No participants in social context"],
            )

        # Build participant descriptions
        participant_descs = []
        for p in social_context.participants:
            desc_parts = [p.name]
            if p.demeanor:
                desc_parts.append(f"({', '.join(p.demeanor)})")
            if p.stat_reference:
                desc_parts.append(f"[{p.stat_reference}]")
            participant_descs.append(" ".join(desc_parts))

        # Determine the tone based on reaction
        if social_context.initial_reaction:
            reaction = social_context.initial_reaction.value
        else:
            reaction = "neutral"

        tone_map = {
            "hostile": "tense, dangerous",
            "unfriendly": "wary, suspicious",
            "neutral": "cautious, evaluating",
            "friendly": "open, welcoming",
            "helpful": "warm, eager to assist",
        }
        tone = tone_map.get(reaction, "uncertain")

        # Build location context
        location_parts = []
        if social_context.poi_name:
            location_parts.append(social_context.poi_name)
        if social_context.hex_id:
            location_parts.append(f"Hex {social_context.hex_id}")
        if social_context.location_description:
            location_parts.append(social_context.location_description)

        location_summary = ". ".join(location_parts) if location_parts else "The encounter location"

        # Origin context
        origin_text = {
            SocialOrigin.ENCOUNTER_PARLEY: "After the initial encounter, conversation has begun",
            SocialOrigin.COMBAT_PARLEY: "Combat has paused as both sides attempt to negotiate",
            SocialOrigin.SETTLEMENT: "In the settlement, a conversation begins",
            SocialOrigin.HEX_NPC: "You encounter a notable figure",
            SocialOrigin.POI_NPC: "At this location, you meet someone",
        }.get(social_context.origin, "A social encounter begins")

        # Use exploration description schema for framing
        sensory_tags = [
            "voices",
            "tension" if reaction in ("hostile", "unfriendly") else "anticipation",
        ]

        inputs = ExplorationDescriptionInputs(
            current_state="social_interaction",
            location_summary=f"{origin_text}. Participants: {', '.join(participant_descs)}. "
            f"Location: {location_summary}. Mood: {tone}.",
            sensory_tags=sensory_tags,
            known_threats=(
                [] if reaction not in ("hostile", "unfriendly") else ["Potential hostility"]
            ),
        )

        schema = ExplorationDescriptionSchema(inputs)
        return self._execute_schema(schema)

    def get_social_context_summary(self, social_context: SocialContext) -> str:
        """
        Get a text summary of the social context for logging or debugging.

        Args:
            social_context: The social context to summarize

        Returns:
            Human-readable summary string
        """
        lines = [
            f"Social Context ({social_context.origin.value}):",
            f"  Participants: {len(social_context.participants)}",
        ]

        for i, p in enumerate(social_context.participants):
            can_talk = "can communicate" if p.can_communicate else "CANNOT communicate"
            lines.append(f"    {i+1}. {p.name} ({p.participant_type.value}) - {can_talk}")
            if p.secrets:
                lines.append(f"       Secrets: {len(p.secrets)} hidden topics")
            if p.quest_hooks:
                lines.append(f"       Quest hooks: {len(p.quest_hooks)} available")

        if social_context.initial_reaction:
            lines.append(f"  Initial reaction: {social_context.initial_reaction.value}")
        if social_context.topics_discussed:
            lines.append(f"  Topics discussed: {', '.join(social_context.topics_discussed)}")
        if social_context.return_state:
            lines.append(f"  Return state: {social_context.return_state}")

        return "\n".join(lines)

    # =========================================================================
    # FAILURE DESCRIPTIONS
    # =========================================================================

    def describe_failure(
        self,
        failed_action: str,
        failure_type: str,
        consequence_type: str,
        consequence_details: str,
        visible_warning: str = "",
    ) -> DescriptionResult:
        """
        Describe the consequence of a failed action.

        This makes failures feel fair by referencing warning signs
        and describing consequences dramatically without adding to them.

        Args:
            failed_action: What was attempted
            failure_type: Type of failure (missed attack, failed save, etc.)
            consequence_type: Category of consequence (damage, condition, etc.)
            consequence_details: Specific mechanical result
            visible_warning: Warning signs that were present

        Returns:
            DescriptionResult with failure description
        """
        inputs = FailureConsequenceInputs(
            failed_action=failed_action,
            failure_type=failure_type,
            visible_warning=visible_warning,
            consequence_type=consequence_type,
            consequence_details=consequence_details,
        )

        schema = FailureConsequenceSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # DOWNTIME SUMMARIES
    # =========================================================================

    def summarize_downtime(
        self,
        days_elapsed: int,
        activities: list[str],
        world_events: Optional[list[str]] = None,
        faction_changes: Optional[list[str]] = None,
        rumors: Optional[list[str]] = None,
        healing: Optional[dict[str, int]] = None,
        season: Optional[Season] = None,
        weather: Optional[Weather] = None,
    ) -> DescriptionResult:
        """
        Generate a summary of a downtime period.

        This creates an evocative transition from rest back to adventure.

        Args:
            days_elapsed: How long downtime lasted
            activities: What characters did during downtime
            world_events: Events that occurred in the world
            faction_changes: Faction clock advancements
            rumors: New rumors heard
            healing: Character -> HP recovered
            season: Season at end of downtime
            weather: Weather at end of downtime

        Returns:
            DescriptionResult with downtime summary
        """
        inputs = DowntimeSummaryInputs(
            days_elapsed=days_elapsed,
            activities=activities,
            world_events=world_events or [],
            faction_changes=faction_changes or [],
            rumors_gained=rumors or [],
            healing_done=healing or {},
            season_at_end=season.value if season else "",
            weather_at_end=weather.value if weather else "",
        )

        schema = DowntimeSummarySchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # COMBAT CONCLUSION
    # =========================================================================

    def narrate_combat_end(
        self,
        outcome: str,
        victor_side: str,
        party_casualties: Optional[list[str]] = None,
        enemy_casualties: Optional[list[str]] = None,
        fled_combatants: Optional[list[str]] = None,
        rounds_fought: int = 0,
        notable_moments: Optional[list[str]] = None,
        terrain: str = "",
    ) -> DescriptionResult:
        """
        Generate narrative for the conclusion of combat.

        Args:
            outcome: "victory", "defeat", "fled", "morale_broken"
            victor_side: "party", "enemies", "none"
            party_casualties: Names of fallen party members
            enemy_casualties: Names of slain enemies
            fled_combatants: Names of those who fled
            rounds_fought: How many rounds combat lasted
            notable_moments: Key events during the battle
            terrain: Where combat took place

        Returns:
            DescriptionResult with combat conclusion narration
        """
        inputs = CombatConclusionInputs(
            outcome=outcome,
            victor_side=victor_side,
            party_casualties=party_casualties or [],
            enemy_casualties=enemy_casualties or [],
            fled_combatants=fled_combatants or [],
            rounds_fought=rounds_fought,
            notable_moments=notable_moments or [],
            terrain=terrain,
        )

        schema = CombatConclusionSchema(inputs)
        return self._execute_schema(schema, allow_narration_context=True)

    # =========================================================================
    # DUNGEON EVENTS
    # =========================================================================

    def narrate_dungeon_event(
        self,
        event_type: str,
        event_name: str,
        success: bool,
        damage_taken: int = 0,
        damage_type: str = "",
        character_name: str = "",
        description: str = "",
        room_context: str = "",
        narrative_hints: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Generate narrative for a dungeon event (trap, discovery, etc.).

        Args:
            event_type: "trap_triggered", "trap_disarmed", "trap_discovered",
                       "secret_found", "feature_discovered", "sound_heard"
            event_name: Name of the trap/secret/feature
            success: Was the event handled successfully?
            damage_taken: Damage if trap triggered (use exact number)
            damage_type: Type of damage (piercing, poison, etc.)
            character_name: Who triggered/discovered it
            description: Brief description of the thing
            room_context: Where this happened
            narrative_hints: Hints from the resolver

        Returns:
            DescriptionResult with dungeon event narration
        """
        inputs = DungeonEventInputs(
            event_type=event_type,
            event_name=event_name,
            success=success,
            damage_taken=damage_taken,
            damage_type=damage_type,
            character_name=character_name,
            description=description,
            room_context=room_context,
            narrative_hints=narrative_hints or [],
        )

        schema = DungeonEventSchema(inputs)
        return self._execute_schema(schema, allow_narration_context=True)

    # =========================================================================
    # REST EXPERIENCE
    # =========================================================================

    def narrate_rest(
        self,
        rest_type: str,
        location_type: str,
        watch_events: Optional[list[str]] = None,
        sleep_quality: str = "normal",
        healing_done: Optional[dict[str, int]] = None,
        resources_consumed: Optional[dict[str, int]] = None,
        time_of_day_start: str = "",
        time_of_day_end: str = "",
        weather: str = "",
        interruptions: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """
        Generate narrative for a rest/camping period.

        Args:
            rest_type: "short", "long", "full", "camping"
            location_type: "wilderness", "dungeon", "settlement", "camp"
            watch_events: What happened during watches
            sleep_quality: "good", "normal", "poor", "impossible"
            healing_done: Character name -> HP recovered
            resources_consumed: Resource name -> amount used
            time_of_day_start: When rest started
            time_of_day_end: When rest ended
            weather: Weather during rest
            interruptions: Any disturbances

        Returns:
            DescriptionResult with rest narration
        """
        inputs = RestExperienceInputs(
            rest_type=rest_type,
            location_type=location_type,
            watch_events=watch_events or [],
            sleep_quality=sleep_quality,
            healing_done=healing_done or {},
            resources_consumed=resources_consumed or {},
            time_of_day_start=time_of_day_start,
            time_of_day_end=time_of_day_end,
            weather=weather,
            interruptions=interruptions or [],
        )

        schema = RestExperienceSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # POI NARRATION
    # =========================================================================

    def describe_poi_approach(
        self,
        poi_name: str,
        poi_type: str,
        description: str,
        tagline: str = "",
        distance: str = "near",
        time_of_day: Optional[TimeOfDay] = None,
        weather: Optional[Weather] = None,
        season: Optional[Season] = None,
        discovery_hints: Optional[list[str]] = None,
        visible_hazards: Optional[list[str]] = None,
        visible_npcs: Optional[list[str]] = None,
        party_approach: str = "cautious",
    ) -> DescriptionResult:
        """
        Generate narrative for approaching a Point of Interest.

        Args:
            poi_name: Name of the POI
            poi_type: Type (manse, ruin, grove, cave, etc.)
            description: Exterior description
            tagline: Short evocative description
            distance: near, medium, far
            time_of_day: Current time of day
            weather: Current weather
            season: Current season
            discovery_hints: Sensory clues that drew attention
            visible_hazards: Hazards visible from approach
            visible_npcs: Figures visible from approach
            party_approach: cautious, direct, stealthy

        Returns:
            DescriptionResult with approach narration
        """
        inputs = POIApproachInputs(
            poi_name=poi_name,
            poi_type=poi_type,
            description=description,
            tagline=tagline,
            distance=distance,
            time_of_day=time_of_day.value if time_of_day else "",
            weather=weather.value if weather else "",
            season=season.value if season else "",
            discovery_hints=discovery_hints or [],
            visible_hazards=visible_hazards or [],
            visible_npcs=visible_npcs or [],
            party_approach=party_approach,
        )

        schema = POIApproachSchema(inputs)
        return self._execute_schema(schema)

    def describe_poi_entry(
        self,
        poi_name: str,
        poi_type: str,
        entering: str,
        interior: str = "",
        time_of_day: Optional[TimeOfDay] = None,
        inhabitants_visible: Optional[list[str]] = None,
        atmosphere: Optional[list[str]] = None,
        entry_method: str = "normal",
        entry_condition: str = "",
    ) -> DescriptionResult:
        """
        Generate narrative for entering a Point of Interest.

        Args:
            poi_name: Name of the POI
            poi_type: Type of POI
            entering: Entry description from data model
            interior: Interior description
            time_of_day: Current time of day
            inhabitants_visible: Visible inhabitants
            atmosphere: Sensory tags for atmosphere
            entry_method: normal, forced, secret, magical
            entry_condition: diving, climbing, etc.

        Returns:
            DescriptionResult with entry narration
        """
        inputs = POIEntryInputs(
            poi_name=poi_name,
            poi_type=poi_type,
            entering=entering,
            interior=interior,
            time_of_day=time_of_day.value if time_of_day else "",
            inhabitants_visible=inhabitants_visible or [],
            atmosphere=atmosphere or [],
            entry_method=entry_method,
            entry_condition=entry_condition,
        )

        schema = POIEntrySchema(inputs)
        return self._execute_schema(schema)

    def describe_poi_feature(
        self,
        poi_name: str,
        feature_name: str,
        feature_description: str,
        interaction_type: str,
        discovery_success: bool = True,
        found_items: Optional[list[str]] = None,
        found_secrets: Optional[list[str]] = None,
        hazard_triggered: bool = False,
        hazard_description: str = "",
        character_name: str = "",
        sub_location_name: str = "",
    ) -> DescriptionResult:
        """
        Generate narrative for exploring a POI feature.

        Args:
            poi_name: Name of the POI
            feature_name: Name of the feature being explored
            feature_description: Description of the feature
            interaction_type: examine, search, touch, activate
            discovery_success: Was the search/interaction successful?
            found_items: Items discovered
            found_secrets: Secrets revealed
            hazard_triggered: Was a hazard triggered?
            hazard_description: Description of triggered hazard
            character_name: Who performed the action
            sub_location_name: Sub-location within POI if applicable

        Returns:
            DescriptionResult with feature exploration narration
        """
        inputs = POIFeatureInputs(
            poi_name=poi_name,
            feature_name=feature_name,
            feature_description=feature_description,
            interaction_type=interaction_type,
            discovery_success=discovery_success,
            found_items=found_items or [],
            found_secrets=found_secrets or [],
            hazard_triggered=hazard_triggered,
            hazard_description=hazard_description,
            character_name=character_name,
            sub_location_name=sub_location_name,
        )

        schema = POIFeatureSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # RESOLVED ACTION NARRATION
    # =========================================================================

    def narrate_resolved_action(
        self,
        action_description: str,
        action_category: str,
        action_type: str,
        success: bool,
        partial_success: bool = False,
        character_name: str = "",
        target_description: str = "",
        dice_rolled: str = "",
        dice_result: int = 0,
        dice_target: int = 0,
        damage_dealt: int = 0,
        damage_taken: int = 0,
        conditions_applied: Optional[list[str]] = None,
        effects_created: Optional[list[str]] = None,
        resources_consumed: Optional[dict[str, int]] = None,
        narrative_hints: Optional[list[str]] = None,
        location_context: str = "",
        rule_reference: str = "",
    ) -> DescriptionResult:
        """
        Generate narrative for a mechanically resolved action.

        This is the generic method for narrating any action that has been
        resolved by the narrative resolvers (spell, hazard, creative, etc.).

        Args:
            action_description: What the character attempted
            action_category: spell, hazard, exploration, survival, creative
            action_type: Specific action type
            success: Was the action successful?
            partial_success: Was it a partial success?
            character_name: Who performed the action
            target_description: Target of the action
            dice_rolled: Dice expression (e.g., "1d20+3")
            dice_result: Result of the roll
            dice_target: Target number to beat
            damage_dealt: Damage dealt to target
            damage_taken: Damage taken by character
            conditions_applied: Conditions applied
            effects_created: Effects created
            resources_consumed: Resources used
            narrative_hints: Hints from the resolver
            location_context: Where this happened
            rule_reference: Rule reference if any

        Returns:
            DescriptionResult with action narration
        """
        inputs = ResolvedActionInputs(
            action_description=action_description,
            action_category=action_category,
            action_type=action_type,
            success=success,
            partial_success=partial_success,
            character_name=character_name,
            target_description=target_description,
            dice_rolled=dice_rolled,
            dice_result=dice_result,
            dice_target=dice_target,
            damage_dealt=damage_dealt,
            damage_taken=damage_taken,
            conditions_applied=conditions_applied or [],
            effects_created=effects_created or [],
            resources_consumed=resources_consumed or {},
            narrative_hints=narrative_hints or [],
            location_context=location_context,
            rule_reference=rule_reference,
        )

        schema = ResolvedActionSchema(inputs)
        return self._execute_schema(schema)

    # =========================================================================
    # INTENT PARSING (Upgrade A)
    # =========================================================================

    def parse_intent(
        self,
        player_input: str,
        current_state: str,
        available_actions: list[str],
        location_context: str = "",
        recent_context: str = "",
    ) -> IntentParseOutput:
        """
        Parse player natural language input into a structured action intent.

        Uses LLM to understand what the player wants to do and map it to
        one of the available action IDs.

        Args:
            player_input: Raw natural language from player
            current_state: Current GameState value
            available_actions: List of valid action IDs for current state
            location_context: Description of current location
            recent_context: Recent events/actions for context

        Returns:
            IntentParseOutput with action_id, params, confidence, etc.
        """
        import json

        inputs = IntentParseInputs(
            player_input=player_input,
            current_state=current_state,
            available_actions=available_actions,
            location_context=location_context,
            recent_context=recent_context,
        )

        schema = IntentParseSchema(inputs)

        # Execute and get raw result
        result = self._execute_schema(schema)

        # Parse the JSON response
        try:
            parsed = json.loads(result.content)
            return IntentParseOutput(
                action_id=parsed.get("action_id", "unknown"),
                params=parsed.get("params", {}),
                confidence=float(parsed.get("confidence", 0.0)),
                requires_clarification=parsed.get("requires_clarification", True),
                clarification_prompt=parsed.get("clarification_prompt", "What would you like to do?"),
                reasoning=parsed.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse intent response: {e}")
            # Return a safe fallback
            return IntentParseOutput(
                action_id="unknown",
                params={},
                confidence=0.0,
                requires_clarification=True,
                clarification_prompt="I didn't understand that. What would you like to do?",
                reasoning=f"Parse error: {e}",
            )

    # =========================================================================
    # NARRATIVE INTENT PARSING (Upgrade A Extension)
    # =========================================================================

    def parse_narrative_intent(
        self,
        player_input: str,
        current_state: str,
        character_name: str = "",
        character_class: str = "",
        character_level: int = 1,
        character_abilities: Optional[dict[str, int]] = None,
        location_type: str = "",
        location_description: str = "",
        visible_features: Optional[list[str]] = None,
        in_combat: bool = False,
        visible_enemies: Optional[list[str]] = None,
        recent_actions: Optional[list[str]] = None,
        known_spell_names: Optional[list[str]] = None,
    ) -> NarrativeIntentOutput:
        """
        Parse player natural language input for mechanical action classification.

        This is used by the NarrativeResolver to understand what the player wants
        to do and classify it for routing to the appropriate resolver (spell,
        hazard, exploration, creative, etc.).

        Unlike parse_intent() which maps to action IDs (dungeon:search),
        this method maps to ActionCategory/ActionType for mechanical resolution.

        Args:
            player_input: Raw natural language from player
            current_state: Current GameState value
            character_name: Name of the acting character
            character_class: Character's class
            character_level: Character's level
            character_abilities: Dict of ability scores {STR: 14, DEX: 12, ...}
            location_type: wilderness, dungeon, settlement
            location_description: Brief description of current location
            visible_features: List of visible features (doors, items, NPCs)
            in_combat: Whether combat is active
            visible_enemies: List of visible enemies
            recent_actions: Recent player actions for context
            known_spell_names: List of spells the character knows

        Returns:
            NarrativeIntentOutput with action classification, resolution hints, etc.
        """
        import json

        inputs = NarrativeIntentInputs(
            player_input=player_input,
            current_state=current_state,
            character_name=character_name,
            character_class=character_class,
            character_level=character_level,
            character_abilities=character_abilities or {},
            location_type=location_type,
            location_description=location_description,
            visible_features=visible_features or [],
            in_combat=in_combat,
            visible_enemies=visible_enemies or [],
            recent_actions=recent_actions or [],
            known_spell_names=known_spell_names or [],
        )

        schema = NarrativeIntentSchema(inputs)

        # Execute and get raw result
        result = self._execute_schema(schema)

        # Parse the JSON response
        try:
            parsed = json.loads(result.content)
            return NarrativeIntentOutput(
                action_category=parsed.get("action_category", "narrative"),
                action_type=parsed.get("action_type", "narrative_action"),
                confidence=float(parsed.get("confidence", 0.5)),
                target_type=parsed.get("target_type", ""),
                target_description=parsed.get("target_description", ""),
                spell_name=parsed.get("spell_name", ""),
                proposed_approach=parsed.get("proposed_approach", ""),
                suggested_resolution=parsed.get("suggested_resolution", "check_required"),
                suggested_check=parsed.get("suggested_check", "none"),
                check_modifier=int(parsed.get("check_modifier", 0)),
                rule_reference=parsed.get("rule_reference", ""),
                is_adventurer_competency=parsed.get("is_adventurer_competency", False),
                requires_clarification=parsed.get("requires_clarification", False),
                clarification_prompt=parsed.get("clarification_prompt", ""),
                reasoning=parsed.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse narrative intent response: {e}")
            # Return a safe fallback - treat as narrative action
            return NarrativeIntentOutput(
                action_category="narrative",
                action_type="narrative_action",
                confidence=0.3,
                suggested_resolution="narrative_only",
                suggested_check="none",
                requires_clarification=True,
                clarification_prompt="What exactly are you trying to do?",
                reasoning=f"Parse error: {e}",
            )

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _execute_schema(
        self,
        schema: PromptSchema,
        allow_narration_context: bool = False,
    ) -> DescriptionResult:
        """
        Execute a prompt schema and return the result.

        Args:
            schema: The prompt schema to execute
            allow_narration_context: If True, allows combat narration words

        Returns:
            DescriptionResult with the LLM response
        """
        # Validate inputs
        errors = schema.validate_inputs()
        if errors:
            return DescriptionResult(
                content="[Input validation failed]",
                schema_used=schema.schema_type,
                success=False,
                warnings=errors,
            )

        # Check cache if enabled
        if self.config.cache_responses:
            cache_key = self._make_cache_key(schema)
            if cache_key in self._cache:
                return DescriptionResult(
                    content=self._cache[cache_key],
                    schema_used=schema.schema_type,
                    success=True,
                    warnings=["from_cache"],
                )

        # Build messages
        system_prompt = schema.get_system_prompt()
        user_prompt = schema.build_prompt()

        messages = [LLMMessage(role=LLMRole.USER, content=user_prompt)]

        # Get LLM response with timing for observability
        import time
        start_time = time.time()
        error_message = ""
        try:
            response = self._llm.complete(
                messages=messages,
                system_prompt=system_prompt,
                allow_narration_context=allow_narration_context,
            )
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            # Log to RunLog for observability (Phase 4.1)
            try:
                from src.observability.run_log import get_run_log
                get_run_log().log_llm_call(
                    call_type=schema.schema_type.value if hasattr(schema, 'schema_type') else "unknown",
                    schema_name=type(schema).__name__,
                    success=not error_message,
                    latency_ms=elapsed_ms,
                    error_message=error_message,
                    input_summary=user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt,
                    output_summary=(response.content[:100] + "...") if not error_message and len(response.content) > 100 else (response.content if not error_message else ""),
                )
            except (ImportError, NameError):
                pass  # RunLog not available or response not defined

        # Build result
        result = DescriptionResult(
            content=response.content,
            schema_used=schema.schema_type,
            success=len(response.authority_violations) == 0,
            authority_violations=response.authority_violations,
        )

        # Cache if enabled and successful
        if self.config.cache_responses and result.success:
            cache_key = self._make_cache_key(schema)
            self._cache[cache_key] = result.content

        # Track for context
        self._add_to_recent(result.content)

        if self.config.verbose_logging:
            logger.info(f"DM Agent: {schema.schema_type.value} -> {len(result.content)} chars")
            if result.authority_violations:
                logger.warning(f"Authority violations: {result.authority_violations}")

        return result

    def _make_cache_key(self, schema: PromptSchema) -> str:
        """Create a cache key for a schema."""
        import hashlib
        import json
        from dataclasses import asdict, is_dataclass

        def serialize(obj):
            """Custom serializer for dataclasses and other non-JSON types."""
            if is_dataclass(obj) and not isinstance(obj, type):
                return asdict(obj)
            elif isinstance(obj, list):
                return [serialize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            return obj

        data = json.dumps(
            {
                "type": schema.schema_type.value,
                "inputs": serialize(schema.inputs),
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.md5(data.encode()).hexdigest()

    def _add_to_recent(self, content: str) -> None:
        """Add to recent descriptions."""
        self._recent_descriptions.append(content)
        if len(self._recent_descriptions) > self._max_recent:
            self._recent_descriptions.pop(0)

    def _build_location_summary(self, location: LocationState) -> str:
        """Build a text summary of a location."""
        parts = [f"{location.location_type.value}: {location.location_id}"]

        if location.name:
            parts.append(location.name)

        parts.append(f"Terrain: {location.terrain}")

        if location.known_features:
            feature_names = [f.name for f in location.known_features]
            parts.append(f"Features: {', '.join(feature_names)}")

        if location.fairy_influence:
            parts.append(f"Fairy influence: {location.fairy_influence}")

        if location.drune_presence:
            parts.append("Signs of Drune activity present")

        return ". ".join(parts)

    def _infer_sensory_tags(
        self,
        location: LocationState,
        weather: Optional[Weather] = None,
    ) -> list[str]:
        """Infer sensory tags from location and conditions."""
        tags = []

        # Terrain-based tags
        terrain_tags = self._get_terrain_sensory_tags(location.terrain)
        tags.extend(terrain_tags)

        # Light-based tags
        if location.light_level == "dark":
            tags.extend(["darkness", "shadows"])
        elif location.light_level == "dim":
            tags.append("dim light")

        # Weather tags
        if weather:
            tags.extend(self._get_weather_sensory_tags(weather))

        # Fairy influence
        if location.fairy_influence:
            tags.extend(["otherworldly", "strange"])

        # Drune presence
        if location.drune_presence:
            tags.extend(["unsettling", "ancient"])

        return tags

    def _get_terrain_sensory_tags(self, terrain: str) -> list[str]:
        """Get sensory tags for terrain type."""
        terrain_lower = terrain.lower()
        tags_map = {
            "forest": ["rustling leaves", "dappled light", "earthy smell"],
            "deep_forest": ["ancient trees", "thick undergrowth", "oppressive canopy"],
            "moor": ["windswept", "boggy ground", "distant mists"],
            "swamp": ["murky water", "decay", "buzzing insects"],
            "hills": ["rolling terrain", "wind", "distant views"],
            "mountains": ["rocky", "thin air", "echoes"],
            "river": ["rushing water", "damp air", "slippery stones"],
            "road": ["worn path", "travelers' marks", "open sky"],
            "settlement": ["voices", "smoke", "activity"],
        }
        return tags_map.get(terrain_lower, ["quiet", "still"])

    def _get_weather_sensory_tags(self, weather: Weather) -> list[str]:
        """Get sensory tags for weather."""
        tags_map = {
            Weather.CLEAR: ["bright sky", "clear air"],
            Weather.OVERCAST: ["grey sky", "diffuse light"],
            Weather.FOG: ["mist", "limited visibility", "damp"],
            Weather.RAIN: ["wet", "drumming rain", "muddy"],
            Weather.STORM: ["thunder", "lightning", "howling wind"],
            Weather.SNOW: ["cold", "white blanket", "muffled sounds"],
            Weather.BLIZZARD: ["biting wind", "blinding snow", "freezing"],
        }
        return tags_map.get(weather, [])

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()

    def get_recent_descriptions(self) -> list[str]:
        """Get recent descriptions for context."""
        return self._recent_descriptions.copy()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


_dm_agent_instance: Optional[DMAgent] = None


def get_dm_agent(config: Optional[DMAgentConfig] = None) -> DMAgent:
    """
    Get or create the DM Agent singleton.

    Args:
        config: Configuration for the agent. Only used if creating new instance.

    Returns:
        The DM Agent instance
    """
    global _dm_agent_instance
    if _dm_agent_instance is None:
        _dm_agent_instance = DMAgent(config)
    return _dm_agent_instance


def reset_dm_agent() -> None:
    """Reset the DM Agent singleton (for testing)."""
    global _dm_agent_instance
    _dm_agent_instance = None
