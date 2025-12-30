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
    COMBAT_CONCLUSION = "combat_conclusion"
    DUNGEON_EVENT = "dungeon_event"
    REST_EXPERIENCE = "rest_experience"
    POI_APPROACH = "poi_approach"
    POI_ENTRY = "poi_entry"
    POI_FEATURE = "poi_feature"
    RESOLVED_ACTION = "resolved_action"


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
# SCHEMA 7: COMBAT CONCLUSION
# =============================================================================


@dataclass
class CombatConclusionInputs:
    """Inputs for combat conclusion narration."""
    outcome: str  # "victory", "defeat", "fled", "morale_broken"
    victor_side: str  # "party", "enemies", "none"
    party_casualties: list[str] = field(default_factory=list)  # Names of fallen
    enemy_casualties: list[str] = field(default_factory=list)  # Names of slain
    fled_combatants: list[str] = field(default_factory=list)  # Who fled
    rounds_fought: int = 0
    notable_moments: list[str] = field(default_factory=list)  # Key events
    terrain: str = ""


class CombatConclusionSchema(PromptSchema):
    """
    Schema for narrating the end of combat.

    Used when:
    - All enemies defeated
    - Party defeated/captured
    - One side flees
    - Morale breaks cause rout

    Constraints:
    - Summarize what happened
    - Do not invent new casualties or effects
    - Transition to post-combat state
    """

    def __init__(self, inputs: CombatConclusionInputs):
        super().__init__(
            schema_type=PromptSchemaType.COMBAT_CONCLUSION,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "outcome": str,
            "victor_side": str,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

COMBAT CONCLUSION TASK:
You are narrating the end of a battle in Dolmenwood.
The mechanical outcome has already been determined.

SPECIFIC CONSTRAINTS:
- Describe the final moments and aftermath
- Acknowledge casualties listed (do not invent others)
- If enemies fled, describe their retreat
- Transition to aftermath/recovery
- Maintain appropriate tone for outcome (triumph/grief/relief)"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        prompt = f"""Narrate the conclusion of this combat:

OUTCOME: {inputs.outcome}
VICTOR: {inputs.victor_side}
ROUNDS FOUGHT: {inputs.rounds_fought}
TERRAIN: {inputs.terrain or 'unknown'}

PARTY CASUALTIES: {', '.join(inputs.party_casualties) if inputs.party_casualties else 'None'}
ENEMY CASUALTIES: {', '.join(inputs.enemy_casualties) if inputs.enemy_casualties else 'None'}
FLED: {', '.join(inputs.fled_combatants) if inputs.fled_combatants else 'None'}

NOTABLE MOMENTS:
{chr(10).join('- ' + m for m in inputs.notable_moments) if inputs.notable_moments else '- A hard-fought battle'}

Write a brief conclusion (2-3 sentences) that:
1. Describes the final moments
2. Acknowledges the fallen (if any)
3. Sets the scene for aftermath"""

        return prompt


# =============================================================================
# SCHEMA 8: DUNGEON EVENT
# =============================================================================


@dataclass
class DungeonEventInputs:
    """Inputs for dungeon event narration."""
    event_type: str  # "trap_triggered", "trap_disarmed", "trap_discovered",
                     # "secret_found", "feature_discovered", "sound_heard"
    event_name: str  # Name of trap/secret/feature
    success: bool  # Was the event handled successfully?
    damage_taken: int = 0  # If trap triggered
    damage_type: str = ""  # Type of damage
    character_name: str = ""  # Who triggered/found it
    description: str = ""  # Brief description of the thing
    room_context: str = ""  # Where this happened
    narrative_hints: list[str] = field(default_factory=list)  # From resolver


class DungeonEventSchema(PromptSchema):
    """
    Schema for narrating dungeon events.

    Used when:
    - Trap triggered or disarmed
    - Secret door/passage found
    - Hidden feature discovered
    - Strange sound heard

    Constraints:
    - Describe the event dramatically
    - Use provided damage numbers exactly
    - Do not invent additional effects
    """

    def __init__(self, inputs: DungeonEventInputs):
        super().__init__(
            schema_type=PromptSchemaType.DUNGEON_EVENT,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "event_type": str,
            "event_name": str,
            "success": bool,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

DUNGEON EVENT TASK:
You are narrating a dungeon event in Dolmenwood.
The mechanical outcome has already been determined.

SPECIFIC CONSTRAINTS:
- Describe the event dramatically
- If damage was taken, mention the EXACT amount provided
- Do not invent additional effects or damage
- Match the tone to the event (danger for traps, triumph for discoveries)
- Use narrative hints provided as inspiration"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        event_descriptions = {
            "trap_triggered": "A trap has been triggered",
            "trap_disarmed": "A trap has been disarmed",
            "trap_discovered": "A trap has been discovered",
            "secret_found": "A secret has been discovered",
            "feature_discovered": "Something interesting has been found",
            "sound_heard": "A sound was detected",
        }

        prompt = f"""Narrate this dungeon event:

EVENT: {event_descriptions.get(inputs.event_type, inputs.event_type)}
NAME: {inputs.event_name}
OUTCOME: {'Success' if inputs.success else 'Failure'}
CHARACTER: {inputs.character_name or 'A party member'}
LOCATION: {inputs.room_context or 'In the dungeon'}
DESCRIPTION: {inputs.description or 'A dungeon hazard'}"""

        if inputs.damage_taken > 0:
            prompt += f"""
DAMAGE: {inputs.damage_taken} {inputs.damage_type} damage"""

        if inputs.narrative_hints:
            prompt += f"""

NARRATIVE HINTS:
{chr(10).join('- ' + h for h in inputs.narrative_hints)}"""

        prompt += """

Write a dramatic description (2-3 sentences) of this event."""

        return prompt


# =============================================================================
# SCHEMA 9: REST EXPERIENCE
# =============================================================================


@dataclass
class RestExperienceInputs:
    """Inputs for rest/camping narration."""
    rest_type: str  # "short", "long", "full", "camping"
    location_type: str  # "wilderness", "dungeon", "settlement", "camp"
    watch_events: list[str] = field(default_factory=list)  # What happened on watches
    sleep_quality: str = "normal"  # "good", "normal", "poor", "impossible"
    healing_done: dict[str, int] = field(default_factory=dict)  # Character -> HP
    resources_consumed: dict[str, int] = field(default_factory=dict)  # food, water, etc.
    time_of_day_start: str = ""  # When rest started
    time_of_day_end: str = ""  # When rest ended
    weather: str = ""
    interruptions: list[str] = field(default_factory=list)  # Any disturbances


class RestExperienceSchema(PromptSchema):
    """
    Schema for narrating rest/camping experiences.

    Used when:
    - Short rest completed
    - Long rest completed
    - Camping in wilderness
    - Sleeping in dungeon

    Constraints:
    - Describe the rest period evocatively
    - Mention any watch events or disturbances
    - Note healing if significant
    - Set appropriate mood for location
    """

    def __init__(self, inputs: RestExperienceInputs):
        super().__init__(
            schema_type=PromptSchemaType.REST_EXPERIENCE,
            inputs=inputs.__dict__,
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "rest_type": str,
            "location_type": str,
        }

    def get_system_prompt(self) -> str:
        base = self._get_base_system_prompt()
        return f"""{base}

REST EXPERIENCE TASK:
You are narrating a rest period in Dolmenwood.
The mechanical outcomes have already been determined.

SPECIFIC CONSTRAINTS:
- Create atmosphere appropriate to location
- Mention watch events if any occurred
- Note sleep quality and any disturbances
- Transition smoothly to waking/continuing
- Match Dolmenwood's atmospheric tone (mysterious, slightly ominous)"""

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        rest_descriptions = {
            "short": "a brief rest",
            "long": "an extended rest",
            "full": "a full day of recuperation",
            "camping": "making camp for the night",
        }

        location_moods = {
            "wilderness": "under the ancient trees of Dolmenwood",
            "dungeon": "in the cold darkness of the dungeon",
            "settlement": "in the relative safety of civilization",
            "camp": "at the campsite",
        }

        prompt = f"""Narrate this rest period:

REST TYPE: {rest_descriptions.get(inputs.rest_type, inputs.rest_type)}
LOCATION: {location_moods.get(inputs.location_type, inputs.location_type)}
SLEEP QUALITY: {inputs.sleep_quality}
WEATHER: {inputs.weather or 'unremarkable'}"""

        if inputs.time_of_day_start:
            prompt += f"\nTIME: {inputs.time_of_day_start} to {inputs.time_of_day_end}"

        if inputs.watch_events:
            prompt += f"""

WATCH EVENTS:
{chr(10).join('- ' + e for e in inputs.watch_events)}"""

        if inputs.interruptions:
            prompt += f"""

DISTURBANCES:
{chr(10).join('- ' + i for i in inputs.interruptions)}"""

        if inputs.healing_done:
            total_healing = sum(inputs.healing_done.values())
            prompt += f"\n\nHEALING: {total_healing} HP recovered across the party"

        prompt += """

Write a brief narration (2-3 sentences) that:
1. Evokes the rest experience
2. Mentions any notable events
3. Transitions to waking/continuing"""

        return prompt


# =============================================================================
# SCHEMA 10: POI APPROACH
# =============================================================================


@dataclass
class POIApproachInputs:
    """Inputs for POI approach narration."""
    poi_name: str
    poi_type: str  # manse, ruin, grove, cave, etc.
    description: str  # Exterior description
    tagline: str = ""  # Short evocative description
    distance: str = "near"  # near, medium, far
    time_of_day: str = ""
    weather: str = ""
    season: str = ""
    discovery_hints: list[str] = field(default_factory=list)  # Sensory clues
    visible_hazards: list[str] = field(default_factory=list)
    visible_npcs: list[str] = field(default_factory=list)
    party_approach: str = "cautious"  # cautious, direct, stealthy


@dataclass
class POIApproachSchema(PromptSchema):
    """Schema for describing approach to a Point of Interest."""

    def __init__(self, inputs: POIApproachInputs):
        super().__init__(
            schema_type=PromptSchemaType.POI_APPROACH,
            inputs=vars(inputs)
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "poi_name": str,
            "poi_type": str,
            "description": str,
        }

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        prompt = f"""Describe the party approaching this Point of Interest:

NAME: {inputs.poi_name}
TYPE: {inputs.poi_type}
DESCRIPTION: {inputs.description}"""

        if inputs.tagline:
            prompt += f"\nTAGLINE: {inputs.tagline}"

        prompt += f"\nDISTANCE: {inputs.distance}"
        prompt += f"\nAPPROACH: {inputs.party_approach}"

        if inputs.time_of_day:
            prompt += f"\nTIME: {inputs.time_of_day}"
        if inputs.weather:
            prompt += f"\nWEATHER: {inputs.weather}"
        if inputs.season:
            prompt += f"\nSEASON: {inputs.season}"

        if inputs.discovery_hints:
            prompt += f"""

SENSORY CLUES (what draws attention):
{chr(10).join('- ' + h for h in inputs.discovery_hints)}"""

        if inputs.visible_hazards:
            prompt += f"""

VISIBLE HAZARDS:
{chr(10).join('- ' + h for h in inputs.visible_hazards)}"""

        if inputs.visible_npcs:
            prompt += f"""

VISIBLE FIGURES:
{chr(10).join('- ' + n for n in inputs.visible_npcs)}"""

        prompt += """

Write a brief narration (2-3 sentences) that:
1. Describes what the party sees as they approach
2. Evokes the atmosphere and mystery of the location
3. Hints at sensory details without revealing hidden secrets
4. Do NOT reveal traps, hidden enemies, or secrets"""

        return prompt


# =============================================================================
# SCHEMA 11: POI ENTRY
# =============================================================================


@dataclass
class POIEntryInputs:
    """Inputs for POI entry narration."""
    poi_name: str
    poi_type: str
    entering: str  # Entry description from data model
    interior: str = ""  # Interior description
    time_of_day: str = ""
    inhabitants_visible: list[str] = field(default_factory=list)
    atmosphere: list[str] = field(default_factory=list)  # Sensory tags
    entry_method: str = "normal"  # normal, forced, secret, magical
    entry_condition: str = ""  # diving, climbing, etc.


@dataclass
class POIEntrySchema(PromptSchema):
    """Schema for describing entry into a Point of Interest."""

    def __init__(self, inputs: POIEntryInputs):
        super().__init__(
            schema_type=PromptSchemaType.POI_ENTRY,
            inputs=vars(inputs)
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "poi_name": str,
            "poi_type": str,
            "entering": str,
        }

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        entry_methods = {
            "normal": "The party enters normally",
            "forced": "The party forces their way in",
            "secret": "The party enters through a hidden passage",
            "magical": "The party uses magic to enter",
        }

        prompt = f"""Describe the party entering this location:

NAME: {inputs.poi_name}
TYPE: {inputs.poi_type}
ENTRY: {inputs.entering}
METHOD: {entry_methods.get(inputs.entry_method, inputs.entry_method)}"""

        if inputs.entry_condition:
            prompt += f"\nCONDITION: {inputs.entry_condition}"

        if inputs.interior:
            prompt += f"\nINTERIOR: {inputs.interior}"

        if inputs.time_of_day:
            prompt += f"\nTIME: {inputs.time_of_day}"

        if inputs.atmosphere:
            prompt += f"""

ATMOSPHERE:
{chr(10).join('- ' + a for a in inputs.atmosphere)}"""

        if inputs.inhabitants_visible:
            prompt += f"""

VISIBLE INHABITANTS:
{chr(10).join('- ' + i for i in inputs.inhabitants_visible)}"""

        prompt += """

Write a brief narration (2-3 sentences) that:
1. Describes the moment of crossing the threshold
2. Captures the first impressions of the interior
3. Establishes the mood and atmosphere
4. Do NOT reveal hidden dangers or secrets"""

        return prompt


# =============================================================================
# SCHEMA 12: POI FEATURE
# =============================================================================


@dataclass
class POIFeatureInputs:
    """Inputs for POI feature exploration narration."""
    poi_name: str
    feature_name: str
    feature_description: str
    interaction_type: str  # examine, search, touch, activate
    discovery_success: bool = True
    found_items: list[str] = field(default_factory=list)
    found_secrets: list[str] = field(default_factory=list)
    hazard_triggered: bool = False
    hazard_description: str = ""
    character_name: str = ""
    sub_location_name: str = ""  # If exploring a sub-location


@dataclass
class POIFeatureSchema(PromptSchema):
    """Schema for describing POI feature exploration."""

    def __init__(self, inputs: POIFeatureInputs):
        super().__init__(
            schema_type=PromptSchemaType.POI_FEATURE,
            inputs=vars(inputs)
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "poi_name": str,
            "feature_name": str,
            "feature_description": str,
            "interaction_type": str,
        }

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        interaction_verbs = {
            "examine": "carefully examines",
            "search": "searches",
            "touch": "touches",
            "activate": "activates",
            "open": "opens",
            "read": "reads",
        }

        actor = inputs.character_name or "The party"
        verb = interaction_verbs.get(inputs.interaction_type, inputs.interaction_type)

        prompt = f"""Describe this feature exploration:

LOCATION: {inputs.poi_name}"""

        if inputs.sub_location_name:
            prompt += f" ({inputs.sub_location_name})"

        prompt += f"""
FEATURE: {inputs.feature_name}
DESCRIPTION: {inputs.feature_description}
ACTION: {actor} {verb} the {inputs.feature_name}
SUCCESS: {"Yes" if inputs.discovery_success else "No"}"""

        if inputs.found_items:
            prompt += f"""

ITEMS DISCOVERED:
{chr(10).join('- ' + i for i in inputs.found_items)}"""

        if inputs.found_secrets:
            prompt += f"""

SECRETS REVEALED:
{chr(10).join('- ' + s for s in inputs.found_secrets)}"""

        if inputs.hazard_triggered:
            prompt += f"""

HAZARD TRIGGERED: {inputs.hazard_description}"""

        prompt += """

Write a brief narration (2-3 sentences) that:
1. Describes the interaction with the feature
2. Reveals discoveries dramatically if any were made
3. Conveys the character's reaction
4. If a hazard triggered, describe the danger"""

        return prompt


# =============================================================================
# SCHEMA 13: RESOLVED ACTION
# =============================================================================


@dataclass
class ResolvedActionInputs:
    """Inputs for narrating a mechanically resolved action."""
    action_description: str  # What the character attempted
    action_category: str  # spell, hazard, exploration, survival, creative
    action_type: str  # climb, swim, cast_spell, search, etc.
    success: bool
    partial_success: bool = False
    character_name: str = ""
    target_description: str = ""
    # Dice results
    dice_rolled: str = ""  # e.g., "1d20+3"
    dice_result: int = 0
    dice_target: int = 0
    # Outcomes
    damage_dealt: int = 0
    damage_taken: int = 0
    conditions_applied: list[str] = field(default_factory=list)
    effects_created: list[str] = field(default_factory=list)
    resources_consumed: dict[str, int] = field(default_factory=dict)
    # Context
    narrative_hints: list[str] = field(default_factory=list)
    location_context: str = ""
    rule_reference: str = ""


@dataclass
class ResolvedActionSchema(PromptSchema):
    """Schema for narrating mechanically resolved actions."""

    def __init__(self, inputs: ResolvedActionInputs):
        super().__init__(
            schema_type=PromptSchemaType.RESOLVED_ACTION,
            inputs=vars(inputs)
        )
        self.typed_inputs = inputs

    def get_required_inputs(self) -> dict[str, type]:
        return {
            "action_description": str,
            "action_category": str,
            "success": bool,
        }

    def build_prompt(self) -> str:
        inputs = self.typed_inputs

        actor = inputs.character_name or "The adventurer"
        outcome = "succeeds" if inputs.success else ("partially succeeds" if inputs.partial_success else "fails")

        prompt = f"""Narrate this resolved action:

ACTION: {inputs.action_description}
CATEGORY: {inputs.action_category}
TYPE: {inputs.action_type}
ACTOR: {actor}
OUTCOME: {outcome.upper()}"""

        if inputs.target_description:
            prompt += f"\nTARGET: {inputs.target_description}"

        if inputs.dice_rolled:
            prompt += f"""

DICE: Rolled {inputs.dice_rolled} = {inputs.dice_result} (target: {inputs.dice_target})"""

        outcomes = []
        if inputs.damage_dealt > 0:
            outcomes.append(f"Dealt {inputs.damage_dealt} damage")
        if inputs.damage_taken > 0:
            outcomes.append(f"Took {inputs.damage_taken} damage")
        if inputs.conditions_applied:
            outcomes.append(f"Applied: {', '.join(inputs.conditions_applied)}")
        if inputs.effects_created:
            outcomes.append(f"Created: {', '.join(inputs.effects_created)}")

        if outcomes:
            prompt += f"""

MECHANICAL OUTCOMES:
{chr(10).join('- ' + o for o in outcomes)}"""

        if inputs.narrative_hints:
            prompt += f"""

NARRATIVE HINTS:
{chr(10).join('- ' + h for h in inputs.narrative_hints)}"""

        if inputs.location_context:
            prompt += f"\nLOCATION: {inputs.location_context}"

        prompt += """

Write a brief narration (2-3 sentences) that:
1. Describes the action attempt
2. Conveys the outcome dramatically
3. Reflects the mechanical results in narrative form
4. Use the EXACT damage/effect values provided"""

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

    elif schema_type == PromptSchemaType.POI_APPROACH:
        typed_inputs = POIApproachInputs(**inputs)
        return POIApproachSchema(typed_inputs)

    elif schema_type == PromptSchemaType.POI_ENTRY:
        typed_inputs = POIEntryInputs(**inputs)
        return POIEntrySchema(typed_inputs)

    elif schema_type == PromptSchemaType.POI_FEATURE:
        typed_inputs = POIFeatureInputs(**inputs)
        return POIFeatureSchema(typed_inputs)

    elif schema_type == PromptSchemaType.RESOLVED_ACTION:
        typed_inputs = ResolvedActionInputs(**inputs)
        return ResolvedActionSchema(typed_inputs)

    else:
        raise ValueError(f"Unknown schema type: {schema_type}")
