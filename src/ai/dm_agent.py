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
    create_schema,
)
from src.data_models import (
    LocationState,
    EncounterState,
    NPC,
    Weather,
    Season,
    TimeOfDay,
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

    def __init__(self, config: Optional[DMAgentConfig] = None):
        """
        Initialize the DM Agent.

        Args:
            config: Agent configuration. If None, uses defaults.
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

        # Response cache (simple dict-based)
        self._cache: dict[str, str] = {}

        # Track recent descriptions for context
        self._recent_descriptions: list[str] = []
        self._max_recent = 5

    def is_available(self) -> bool:
        """Check if the LLM is available."""
        return self._llm.is_available()

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
                action_objects.append(ResolvedAction(
                    actor=action.get("actor", "Unknown"),
                    action=action.get("action", "acts"),
                    target=action.get("target", ""),
                    result=action.get("result", ""),
                    damage=action.get("damage", 0),
                    special_effects=action.get("special_effects", []),
                ))
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

        # Get LLM response
        response = self._llm.complete(
            messages=messages,
            system_prompt=system_prompt,
            allow_narration_context=allow_narration_context,
        )

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

        data = json.dumps({
            "type": schema.schema_type.value,
            "inputs": serialize(schema.inputs),
        }, sort_keys=True, default=str)
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
