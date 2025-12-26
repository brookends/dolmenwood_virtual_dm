"""
Prompt Schemas for Dolmenwood Virtual DM.

Implements all 6 prompt schemas from Section 8.2 of the specification.
Each schema defines:
- Required inputs with validation
- Output structure
- Strict instructions for LLM behavior

CRITICAL: These schemas enforce that the LLM is ADVISORY ONLY.
The LLM may NOT decide outcomes, roll dice, or alter game state.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import json


class PromptSchemaType(str, Enum):
    """Types of prompt schemas."""
    EXPLORATION_DESCRIPTION = "exploration_description"
    ENCOUNTER_FRAMING = "encounter_framing"
    COMBAT_NARRATION = "combat_narration"
    NPC_DIALOGUE = "npc_dialogue"
    FAILURE_CONSEQUENCE = "failure_consequence_description"
    DOWNTIME_SUMMARY = "downtime_summary"


# =============================================================================
# BASE SCHEMA
# =============================================================================


@dataclass
class PromptSchema:
    """Base class for prompt schemas."""
    schema_type: PromptSchemaType
    inputs: dict[str, Any]
    instructions: str = ""

    def validate_inputs(self) -> list[str]:
        """Validate that all required inputs are present."""
        errors = []
        for key, value in self.get_required_inputs().items():
            if key not in self.inputs or self.inputs[key] is None:
                errors.append(f"Missing required input: {key}")
        return errors

    def get_required_inputs(self) -> dict[str, type]:
        """Return dict of required input names and their types."""
        return {}

    def build_prompt(self) -> str:
        """Build the complete prompt string."""
        raise NotImplementedError

    def get_system_prompt(self) -> str:
        """Get the system prompt for this schema."""
        return self._get_base_system_prompt()

    def _get_base_system_prompt(self) -> str:
        """Base system prompt enforcing authority boundaries."""
        return """You are the descriptive voice of a Dolmenwood virtual DM assistant.

CRITICAL CONSTRAINTS - You MUST follow these rules:
1. You may ONLY provide descriptions and narration
2. You may NEVER decide outcomes, success, or failure
3. You may NEVER roll dice or generate random numbers
4. You may NEVER alter game state or apply effects
5. You may NEVER invent rules or mechanics
6. You may NEVER reveal hidden information unless explicitly provided
7. You may NEVER suggest specific actions the player should take

Your role is purely descriptive and atmospheric. The Python game system handles
all mechanical resolutions. You bring the world to life through evocative prose."""


# =============================================================================
# SCHEMA 1: EXPLORATION DESCRIPTION
# =============================================================================


@dataclass
class ExplorationDescriptionInputs:
    """Inputs for exploration description schema."""
    current_state: str  # GameState enum value
    location_summary: str  # From LocationState
    sensory_tags: list[str]  # ["damp", "echoing", "dim"]
    known_threats: list[str] = field(default_factory=list)  # Only if detected
    time_of_day: str = ""  # Affects lighting, mood
    weather: str = ""  # If outdoors
    season: str = ""  # Current season


@dataclass
class ExplorationDescriptionOutput:
    """Output structure for exploration description."""
    sensory_description: str  # What they see, hear, smell
    atmosphere: str  # Emotional tone


class ExplorationDescriptionSchema(PromptSchema):
    """
    Schema for describing exploration environments.

    Used when:
    - Entering a new hex or dungeon room
    - Looking around an area
    - Describing the current location

    Constraints:
    - Describe environment only
    - Do not imply danger unless specified in known_threats
    - Do not suggest actions
    - Do not describe NPC behaviors
    """

    def __init__(self, inputs: ExplorationDescriptionInputs):
        super().__init__(
            schema_type=PromptSchemaType.EXPLORATION_DESCRIPTION,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "current_state": str,
            "location_summary": str,
            "sensory_tags": list,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

EXPLORATION DESCRIPTION TASK:
You are describing an environment in the Dolmenwood setting.
Focus on sensory details: what can be seen, heard, smelled, felt.

SPECIFIC CONSTRAINTS:
- Describe ONLY the environment, not creature actions or behaviors
- Do NOT imply hidden dangers unless explicitly listed in known_threats
- Do NOT suggest what the player should do
- Keep descriptions evocative but concise (2-4 sentences)
- Match the mood to time of day and weather if provided
- Use Dolmenwood's fairy-tale horror aesthetic"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        prompt = f"""Describe this location in Dolmenwood:

Location: {inputs.location_summary}
State: {inputs.current_state}
Sensory details to incorporate: {', '.join(inputs.sensory_tags)}"""

        if inputs.time_of_day:
            prompt += f"\nTime of day: {inputs.time_of_day}"
        if inputs.weather:
            prompt += f"\nWeather: {inputs.weather}"
        if inputs.season:
            prompt += f"\nSeason: {inputs.season}"
        if inputs.known_threats:
            prompt += f"\nKnown threats (can be referenced): {', '.join(inputs.known_threats)}"

        prompt += """

Provide:
1. A sensory description (what is seen, heard, smelled - 2-3 sentences)
2. The atmosphere (emotional tone - 1 sentence)

Remember: Describe only. No actions, no suggestions, no hidden dangers."""

        return prompt


# =============================================================================
# SCHEMA 2: ENCOUNTER FRAMING
# =============================================================================


@dataclass
class EncounterFramingInputs:
    """Inputs for encounter framing schema."""
    encounter_type: str  # Monster name or NPC type
    number_appearing: int  # How many
    distance_feet: int  # Determined by system
    surprise_status: str  # Who is surprised (don't reveal in narration)
    terrain: str  # Current terrain
    context: str  # traveling, guarding, hunting, etc.
    time_of_day: str = ""
    weather: str = ""


@dataclass
class EncounterFramingOutput:
    """Output structure for encounter framing."""
    initial_sight: str  # First visual impression
    notable_details: str  # Distinctive features


class EncounterFramingSchema(PromptSchema):
    """
    Schema for framing encounter introductions.

    Used when:
    - A random encounter is triggered
    - Entering a room with occupants
    - Discovering a lair

    Constraints:
    - Frame encounter visually only
    - Describe what is SEEN, not intentions
    - Do NOT reveal surprise status narratively
    - Do NOT describe actions or dialogue
    """

    def __init__(self, inputs: EncounterFramingInputs):
        super().__init__(
            schema_type=PromptSchemaType.ENCOUNTER_FRAMING,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "encounter_type": str,
            "number_appearing": int,
            "distance_feet": int,
            "terrain": str,
            "context": str,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

ENCOUNTER FRAMING TASK:
You are introducing an encounter in Dolmenwood.
Describe ONLY what is visually apparent at first glance.

SPECIFIC CONSTRAINTS:
- Describe what is SEEN, not thoughts, intentions, or actions
- Do NOT reveal whether anyone is surprised (this is mechanical)
- Do NOT have creatures speak or act
- Do NOT describe what they are about to do
- Focus on visual appearance and positioning
- Match tone to the Dolmenwood aesthetic (fairy-tale horror)"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        # Pluralize if needed
        creature_text = inputs.encounter_type
        if inputs.number_appearing > 1:
            creature_text = f"{inputs.number_appearing} {inputs.encounter_type}s"

        prompt = f"""Frame this encounter:

Creatures: {creature_text}
Distance: {inputs.distance_feet} feet away
Terrain: {inputs.terrain}
What they appear to be doing: {inputs.context}"""

        if inputs.time_of_day:
            prompt += f"\nTime: {inputs.time_of_day}"
        if inputs.weather:
            prompt += f"\nWeather: {inputs.weather}"

        prompt += """

Provide:
1. Initial sight (first visual impression - 1-2 sentences)
2. Notable details (distinctive features - 1 sentence)

Remember: Visual description only. No actions, no speech, no intentions."""

        return prompt


# =============================================================================
# SCHEMA 3: COMBAT NARRATION
# =============================================================================


@dataclass
class ResolvedAction:
    """A combat action that has been mechanically resolved."""
    actor: str  # Who acted
    action: str  # What they did
    target: str  # Who they targeted
    result: str  # hit, miss, etc.
    damage: int = 0  # If applicable
    special_effects: list[str] = field(default_factory=list)


@dataclass
class CombatNarrationInputs:
    """Inputs for combat narration schema."""
    round_number: int  # Current round
    resolved_actions: list[ResolvedAction]  # Already determined outcomes
    damage_results: dict[str, int]  # Who took how much damage
    conditions_applied: list[str]  # New conditions this round
    morale_results: list[str] = field(default_factory=list)  # Morale check outcomes
    deaths: list[str] = field(default_factory=list)  # Who died this round


@dataclass
class CombatNarrationOutput:
    """Output structure for combat narration."""
    narration: str  # Dramatic description of what happened


class CombatNarrationSchema(PromptSchema):
    """
    Schema for narrating combat that has already been resolved.

    Used when:
    - After a combat round is mechanically resolved
    - The system has determined all hits, damage, and effects

    Constraints:
    - Narrate ONLY what has been determined by the system
    - Do NOT add new outcomes or effects
    - Do NOT describe actions not in resolved_actions
    - Deaths should be dramatic but not gratuitous
    """

    def __init__(self, inputs: CombatNarrationInputs):
        super().__init__(
            schema_type=PromptSchemaType.COMBAT_NARRATION,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "round_number": int,
            "resolved_actions": list,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

COMBAT NARRATION TASK:
You are narrating combat that has ALREADY been resolved mechanically.
All outcomes (hits, misses, damage, deaths) are provided to you.

SPECIFIC CONSTRAINTS:
- Narrate ONLY the actions and outcomes provided
- Do NOT add any outcomes not in the data (no extra hits, damage, or effects)
- Do NOT roll dice or suggest rolls
- Deaths should be described dramatically but not excessively gory
- Keep narration punchy and action-focused
- Reference specific damage amounts if provided
- This allows narration context for words like "damage", "hit", "miss\""""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        # Format resolved actions
        actions_text = []
        for action in inputs.resolved_actions:
            if isinstance(action, dict):
                action_line = f"- {action.get('actor', 'Someone')} {action.get('action', 'acts')}"
                if action.get('target'):
                    action_line += f" targeting {action['target']}"
                if action.get('result'):
                    action_line += f" -> {action['result']}"
                if action.get('damage'):
                    action_line += f" ({action['damage']} damage)"
                actions_text.append(action_line)
            else:
                action_line = f"- {action.actor} {action.action}"
                if action.target:
                    action_line += f" targeting {action.target}"
                action_line += f" -> {action.result}"
                if action.damage:
                    action_line += f" ({action.damage} damage)"
                actions_text.append(action_line)

        prompt = f"""Narrate Round {inputs.round_number} of combat:

RESOLVED ACTIONS (these happened - narrate them):
{chr(10).join(actions_text) if actions_text else "No actions this round"}

DAMAGE DEALT:
{json.dumps(inputs.damage_results) if inputs.damage_results else "None"}

CONDITIONS APPLIED: {', '.join(inputs.conditions_applied) if inputs.conditions_applied else 'None'}
MORALE BREAKS: {', '.join(inputs.morale_results) if inputs.morale_results else 'None'}
DEATHS: {', '.join(inputs.deaths) if inputs.deaths else 'None'}

Write a dramatic narration (2-4 sentences) describing exactly what happened.
Include specific damage numbers when characters are wounded.
Remember: Describe ONLY what is listed above. Add no new outcomes."""

        return prompt


# =============================================================================
# SCHEMA 4: NPC DIALOGUE
# =============================================================================


@dataclass
class NPCDialogueInputs:
    """Inputs for NPC dialogue schema."""
    npc_name: str
    npc_personality: str  # Brief personality description
    npc_voice: str  # Speech patterns, accent hints
    reaction_result: str  # Current disposition toward party
    conversation_topic: str  # What player is asking about
    known_to_npc: list[str]  # Topics NPC knows and CAN share
    hidden_from_player: list[str] = field(default_factory=list)  # Won't reveal
    faction_context: str = ""  # Relevant faction relationships
    previous_interactions: list[str] = field(default_factory=list)


@dataclass
class NPCDialogueOutput:
    """Output structure for NPC dialogue."""
    dialogue: str  # What NPC says
    body_language: str  # Non-verbal cues
    hidden_reaction: str  # Internal thoughts (DM reference)


class NPCDialogueSchema(PromptSchema):
    """
    Schema for generating NPC dialogue.

    Used when:
    - Player initiates conversation with an NPC
    - NPC responds to player questions or statements
    - Social encounters

    Constraints:
    - Stay in character per personality and voice
    - Respect reaction_result disposition
    - Do NOT reveal hidden_from_player topics
    - May hint at secrets but not expose them
    """

    def __init__(self, inputs: NPCDialogueInputs):
        super().__init__(
            schema_type=PromptSchemaType.NPC_DIALOGUE,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "npc_name": str,
            "npc_personality": str,
            "reaction_result": str,
            "conversation_topic": str,
            "known_to_npc": list,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

NPC DIALOGUE TASK:
You are voicing an NPC in Dolmenwood, staying in character.

SPECIFIC CONSTRAINTS:
- Match the NPC's personality and speech patterns exactly
- Their disposition affects how helpful/hostile they are
- They may ONLY discuss topics listed in "known_to_npc"
- They may NOT reveal topics in "hidden_from_player" under any circumstances
- They may hint at secrets but never explicitly reveal them
- Use period-appropriate speech for a dark fairy-tale setting
- Include brief body language description"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        prompt = f"""Voice this NPC in conversation:

NPC: {inputs.npc_name}
Personality: {inputs.npc_personality}
Speech style: {inputs.npc_voice}
Current disposition: {inputs.reaction_result}

Player asks about: {inputs.conversation_topic}

TOPICS NPC KNOWS AND CAN SHARE:
{chr(10).join('- ' + t for t in inputs.known_to_npc) if inputs.known_to_npc else '- Nothing relevant'}

TOPICS NPC MUST NOT REVEAL:
{chr(10).join('- ' + t for t in inputs.hidden_from_player) if inputs.hidden_from_player else '- None'}"""

        if inputs.faction_context:
            prompt += f"\n\nFaction context: {inputs.faction_context}"
        if inputs.previous_interactions:
            prompt += f"\n\nPrevious encounters: {', '.join(inputs.previous_interactions)}"

        prompt += """

Provide:
1. Dialogue (what the NPC says, in quotes, 2-4 sentences)
2. Body language (non-verbal cues, 1 sentence)
3. Hidden reaction (NPC's private thoughts, for DM reference)

Remember: Stay in character. Never reveal hidden topics."""

        return prompt


# =============================================================================
# SCHEMA 5: FAILURE CONSEQUENCE DESCRIPTION
# =============================================================================


@dataclass
class FailureConsequenceInputs:
    """Inputs for failure consequence description schema."""
    failed_action: str  # What was attempted
    failure_type: str  # Missed attack, failed save, botched skill
    visible_warning: str  # Warning signs that were present
    consequence_type: str  # Damage, condition, complication
    consequence_details: str  # Specific mechanical result


@dataclass
class FailureConsequenceOutput:
    """Output structure for failure consequence description."""
    description: str  # Narrative of what went wrong


class FailureConsequenceSchema(PromptSchema):
    """
    Schema for describing consequences of failed actions.

    Used when:
    - A skill check fails
    - A saving throw fails
    - An attack misses with consequences

    Constraints:
    - Emphasize warning signs that were present
    - Make consequences feel fair but impactful
    - Do NOT add penalties beyond consequence_details
    """

    def __init__(self, inputs: FailureConsequenceInputs):
        super().__init__(
            schema_type=PromptSchemaType.FAILURE_CONSEQUENCE,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "failed_action": str,
            "failure_type": str,
            "consequence_type": str,
            "consequence_details": str,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

FAILURE CONSEQUENCE TASK:
You are describing the consequence of a failed action.
The failure has already been determined mechanically.

SPECIFIC CONSTRAINTS:
- Describe ONLY the consequence provided, nothing additional
- Reference warning signs if provided (shows it was fair)
- Make failures feel consequential but not cruel
- Do NOT add extra damage, conditions, or effects
- Do NOT suggest this was arbitrary or unfair
- Maintain dramatic tension"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        prompt = f"""Describe this failure consequence:

ATTEMPTED ACTION: {inputs.failed_action}
FAILURE TYPE: {inputs.failure_type}
WARNING SIGNS THAT WERE PRESENT: {inputs.visible_warning or 'None obvious'}
CONSEQUENCE: {inputs.consequence_type}
SPECIFIC RESULT: {inputs.consequence_details}

Write a brief description (1-2 sentences) of what goes wrong.
If warning signs existed, reference them to show the danger was foreseeable.
Remember: Describe ONLY the consequence listed. Add nothing extra."""

        return prompt


# =============================================================================
# SCHEMA 6: DOWNTIME SUMMARY
# =============================================================================


@dataclass
class DowntimeSummaryInputs:
    """Inputs for downtime summary schema."""
    days_elapsed: int  # How long downtime lasted
    activities: list[str]  # What characters did
    world_events: list[str]  # What happened in the world
    faction_changes: list[str]  # Faction clock advancements
    rumors_gained: list[str]  # New information available
    healing_done: dict[str, int]  # Character -> HP recovered
    season_at_end: str = ""
    weather_at_end: str = ""


@dataclass
class DowntimeSummaryOutput:
    """Output structure for downtime summary."""
    summary: str  # Narrative of time passage


class DowntimeSummarySchema(PromptSchema):
    """
    Schema for summarizing downtime periods.

    Used when:
    - Extended rest periods end
    - Training or crafting projects complete
    - Time passes in settlement

    Constraints:
    - Summarize time passage evocatively
    - Hint at world events without revealing full details
    - Transition smoothly back to active play
    """

    def __init__(self, inputs: DowntimeSummaryInputs):
        super().__init__(
            schema_type=PromptSchemaType.DOWNTIME_SUMMARY,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "days_elapsed": int,
            "activities": list,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

DOWNTIME SUMMARY TASK:
You are summarizing a period of downtime in Dolmenwood.
Transition from rest back to adventure.

SPECIFIC CONSTRAINTS:
- Create a sense of time passing
- Mention activities performed
- Hint at world events without full detail
- Note rumors heard if any
- End with a feeling of readiness to continue
- Match Dolmenwood's atmospheric tone"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        day_word = "day" if inputs.days_elapsed == 1 else "days"

        prompt = f"""Summarize {inputs.days_elapsed} {day_word} of downtime:

ACTIVITIES PERFORMED:
{chr(10).join('- ' + a for a in inputs.activities) if inputs.activities else '- Rest and recovery'}

WORLD EVENTS (hint at these):
{chr(10).join('- ' + e for e in inputs.world_events) if inputs.world_events else '- The world continues its quiet patterns'}

FACTION MOVEMENTS:
{chr(10).join('- ' + f for f in inputs.faction_changes) if inputs.faction_changes else '- No notable faction activity'}

RUMORS HEARD:
{chr(10).join('- ' + r for r in inputs.rumors_gained) if inputs.rumors_gained else '- Nothing new reaches your ears'}

HEALING: {json.dumps(inputs.healing_done) if inputs.healing_done else 'None needed'}"""

        if inputs.season_at_end:
            prompt += f"\n\nSeason at end: {inputs.season_at_end}"
        if inputs.weather_at_end:
            prompt += f"\nWeather at end: {inputs.weather_at_end}"

        prompt += """

Write a summary (2-4 sentences) that:
1. Evokes the passage of time
2. Briefly mentions activities
3. Hints at world events
4. Transitions back to active adventure"""

        return prompt


# =============================================================================
# SCHEMA FACTORY
# =============================================================================


def create_schema(
    schema_type: PromptSchemaType,
    inputs: dict[str, Any],
) -> PromptSchema:
    """
    Factory function to create prompt schemas.

    Args:
        schema_type: Type of schema to create
        inputs: Dictionary of inputs for the schema

    Returns:
        Configured PromptSchema instance
    """
    if schema_type == PromptSchemaType.EXPLORATION_DESCRIPTION:
        typed_inputs = ExplorationDescriptionInputs(**inputs)
        return ExplorationDescriptionSchema(typed_inputs)

    elif schema_type == PromptSchemaType.ENCOUNTER_FRAMING:
        typed_inputs = EncounterFramingInputs(**inputs)
        return EncounterFramingSchema(typed_inputs)

    elif schema_type == PromptSchemaType.COMBAT_NARRATION:
        typed_inputs = CombatNarrationInputs(**inputs)
        return CombatNarrationSchema(typed_inputs)

    elif schema_type == PromptSchemaType.NPC_DIALOGUE:
        typed_inputs = NPCDialogueInputs(**inputs)
        return NPCDialogueSchema(typed_inputs)

    elif schema_type == PromptSchemaType.FAILURE_CONSEQUENCE:
        typed_inputs = FailureConsequenceInputs(**inputs)
        return FailureConsequenceSchema(typed_inputs)

    elif schema_type == PromptSchemaType.DOWNTIME_SUMMARY:
        typed_inputs = DowntimeSummaryInputs(**inputs)
        return DowntimeSummarySchema(typed_inputs)

    else:
        raise ValueError(f"Unknown schema type: {schema_type}")
