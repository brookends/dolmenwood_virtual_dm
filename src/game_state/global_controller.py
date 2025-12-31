"""
Global Controller for Dolmenwood Virtual DM.

Manages global game state including time tracking, world state, and party state.
This is the central coordinator that ties together all game systems.

Implements Section 5.1 Global Loop Invariants and Section 6.6 TimeTracker.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
import logging

from src.game_state.state_machine import GameState, StateMachine
from src.oracle.spell_adjudicator import (
    MythicSpellAdjudicator,
    AdjudicationContext,
    AdjudicationResult,
    SpellAdjudicationType,
)
from src.data_models import (
    WorldState,
    PartyState,
    CharacterState,
    LocationState,
    EncounterState,
    GameDate,
    GameTime,
    Season,
    Weather,
    Location,
    LocationType,
    PartyResources,
    DiceRoller,
    Condition,
    ConditionType,
    LightSourceType,
    AreaEffect,
    AreaEffectType,
    PolymorphOverlay,
    Glyph,
    GlyphType,
    SocialContext,
    SocialOrigin,
    SocialParticipant,
    SocialParticipantType,
    ReactionResult,
    KnownTopic,
    SecretInfo,
    SecretStatus,
)

# Import new Dolmenwood weather system
try:
    from src.weather import (
        roll_weather as roll_dolmenwood_weather,
        WeatherResult,
        WeatherEffect,
        Unseason,
        UnseasonState,
        check_unseason_trigger,
        get_active_unseason_effects,
    )

    DOLMENWOOD_WEATHER_AVAILABLE = True
except ImportError:
    DOLMENWOOD_WEATHER_AVAILABLE = False

# Import NarrativeResolver (optional, may not be initialized yet)
try:
    from src.narrative import NarrativeResolver, ActiveSpellEffect

    NARRATIVE_AVAILABLE = True
except ImportError:
    NARRATIVE_AVAILABLE = False
    NarrativeResolver = None
    ActiveSpellEffect = None

# Import XPManager for advancement tracking
try:
    from src.advancement import XPManager

    XP_MANAGER_AVAILABLE = True
except ImportError:
    XP_MANAGER_AVAILABLE = False
    XPManager = None


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class TimeTracker:
    """
    Tracks game time at multiple scales.
    From Section 6.6 of the specification.

    Time scales:
    - Exploration turns: 10 minutes (dungeon time)
    - Watches: 4 hours (travel/rest time)
    - Days: 24 hours
    - Seasons: Quarterly

    All time advancement flows through this class to ensure consistency.
    """

    exploration_turns: int = 0
    watches: int = 0
    days: int = 0
    game_date: GameDate = field(default_factory=lambda: GameDate(year=1, month=1, day=1))
    game_time: GameTime = field(default_factory=lambda: GameTime(hour=8, minute=0))
    season: Season = field(default_factory=lambda: Season.SPRING)

    # Callbacks for time-based triggers
    _turn_callbacks: list[Callable] = field(default_factory=list)
    _watch_callbacks: list[Callable] = field(default_factory=list)
    _day_callbacks: list[Callable] = field(default_factory=list)
    _season_callbacks: list[Callable] = field(default_factory=list)

    def advance_turn(self, turns: int = 1) -> dict[str, Any]:
        """
        Advance time by exploration turns (10 minutes each).

        This is the base unit of dungeon time.

        Args:
            turns: Number of turns to advance

        Returns:
            Dictionary with time changes and triggered thresholds
        """
        self.exploration_turns += turns

        new_time, days_passed = self.game_time.advance_turns(turns)
        self.game_time = new_time

        result = {
            "turns_advanced": turns,
            "new_time": str(self.game_time),
            "watches_passed": 0,
            "days_passed": 0,
            "season_changed": False,
        }

        # Check watch threshold (24 turns = 4 hours)
        watches_from_turns = self.exploration_turns // 24
        if watches_from_turns > self.watches:
            watch_diff = watches_from_turns - self.watches
            self.watches = watches_from_turns
            result["watches_passed"] = watch_diff
            for callback in self._watch_callbacks:
                callback(watch_diff)

        # Handle days passed
        if days_passed > 0:
            self.days += days_passed
            self.game_date = self.game_date.advance_days(days_passed)
            result["days_passed"] = days_passed
            result["new_date"] = str(self.game_date)
            for callback in self._day_callbacks:
                callback(days_passed)

            # Check season change
            new_season = self.game_date.get_season()
            if new_season != self.season:
                old_season = self.season
                self.season = new_season
                result["season_changed"] = True
                result["old_season"] = old_season.value
                result["new_season"] = new_season.value
                for callback in self._season_callbacks:
                    callback(old_season, new_season)

        # Run turn callbacks
        for callback in self._turn_callbacks:
            callback(turns)

        return result

    def advance_watch(self, watches: int = 1) -> dict[str, Any]:
        """
        Advance time by watches (4 hours each).

        Args:
            watches: Number of watches to advance

        Returns:
            Dictionary with time changes
        """
        # Each watch is 24 turns
        return self.advance_turn(watches * 24)

    def advance_day(self, days: int = 1) -> dict[str, Any]:
        """
        Advance time by full days.

        Args:
            days: Number of days to advance

        Returns:
            Dictionary with time changes
        """
        # Each day is 6 watches = 144 turns
        return self.advance_turn(days * 144)

    def advance_hours(self, hours: int) -> dict[str, Any]:
        """
        Advance time by hours.

        Args:
            hours: Number of hours to advance

        Returns:
            Dictionary with time changes
        """
        # Each hour is 6 turns
        return self.advance_turn(hours * 6)

    def check_seasonal_threshold(self) -> bool:
        """
        Check if we've crossed a seasonal boundary.

        Returns:
            True if season changed since last check
        """
        current_season = self.game_date.get_season()
        return current_season != self.season

    def register_turn_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for turn advancement."""
        self._turn_callbacks.append(callback)

    def register_watch_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for watch advancement."""
        self._watch_callbacks.append(callback)

    def register_day_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for day advancement."""
        self._day_callbacks.append(callback)

    def register_season_callback(self, callback: Callable[[Season, Season], None]) -> None:
        """Register callback for season changes."""
        self._season_callbacks.append(callback)

    def get_time_summary(self) -> dict[str, Any]:
        """Get a summary of current time state."""
        return {
            "date": str(self.game_date),
            "time": str(self.game_time),
            "time_of_day": self.game_time.get_time_of_day().value,
            "watch": self.game_time.get_current_watch().value,
            "season": self.season.value,
            "is_daylight": self.game_time.is_daylight(),
            "total_turns": self.exploration_turns,
            "total_days": self.days,
        }


class GlobalController:
    """
    Central game controller that coordinates all subsystems.

    This class is the authoritative source for:
    - Game state management via StateMachine
    - Time tracking via TimeTracker
    - World state persistence
    - Party state management
    - Character roster

    Implements Section 5.1 Global Loop Invariants:
    1. Validate current state
    2. Load shared state (World, Party, Location)
    3. Enforce procedure ordering
    4. Log all state mutations
    5. Disallow LLM authority over outcomes

    Transition hooks allow engines to initialize when states change.
    """

    def __init__(
        self,
        initial_state: GameState = GameState.WILDERNESS_TRAVEL,
        game_date: Optional[GameDate] = None,
        game_time: Optional[GameTime] = None,
    ):
        """
        Initialize the global controller.

        Args:
            initial_state: Starting game state
            game_date: Starting date (default: Year 1, Month 1, Day 1)
            game_time: Starting time (default: 08:00)
        """
        # Core subsystems
        self.state_machine = StateMachine(initial_state)
        self.time_tracker = TimeTracker(
            game_date=game_date or GameDate(year=1, month=1, day=1),
            game_time=game_time or GameTime(hour=8, minute=0),
        )
        self.dice_roller = DiceRoller()

        # Game state storage
        self.world_state = WorldState(
            current_date=self.time_tracker.game_date,
            current_time=self.time_tracker.game_time,
            season=self.time_tracker.season,
            weather=Weather.CLEAR,
        )

        self.party_state = PartyState(
            location=Location(LocationType.HEX, "0101"),
            resources=PartyResources(),
        )

        # Character roster
        self._characters: dict[str, CharacterState] = {}

        # NPC roster (generated NPCs with class abilities)
        self._npcs: dict[str, CharacterState] = {}

        # Location cache
        self._locations: dict[str, LocationState] = {}

        # Current encounter (if any)
        self._current_encounter: Optional[EncounterState] = None

        # Current combat engine (if any)
        self._combat_engine: Optional[Any] = None

        # Current social context (if any)
        self._social_context: Optional[SocialContext] = None

        # Narrative resolver for effect tracking (optional)
        self._narrative_resolver: Optional["NarrativeResolver"] = None
        if NARRATIVE_AVAILABLE:
            self._narrative_resolver = NarrativeResolver(controller=self)

        # XP Manager for advancement tracking (optional)
        self._xp_manager: Optional["XPManager"] = None
        if XP_MANAGER_AVAILABLE:
            self._xp_manager = XPManager(controller=self)

        # Spell adjudicator for oracle-based spell resolution (lazy init)
        self._spell_adjudicator: Optional[MythicSpellAdjudicator] = None

        # Session log
        self._session_log: list[dict[str, Any]] = []

        # Glyph tracking (glyphs on doors/objects)
        self._glyphs: dict[str, Glyph] = {}  # glyph_id -> Glyph

        # Transition hooks: (from_state, to_state) -> list of callbacks
        # Callbacks receive (from_state, to_state, trigger, context)
        self._transition_hooks: dict[
            tuple[GameState, GameState], list[Callable[[GameState, GameState, str, dict], None]]
        ] = {}

        # Wildcard hooks: to_state -> list of callbacks (fire on ANY transition to that state)
        self._on_enter_hooks: dict[
            GameState, list[Callable[[GameState, GameState, str, dict], None]]
        ] = {}
        self._on_exit_hooks: dict[
            GameState, list[Callable[[GameState, GameState, str, dict], None]]
        ] = {}

        # Register state machine hooks
        self.state_machine.register_post_hook(self._on_state_transition)

        # Register time callbacks
        self.time_tracker.register_turn_callback(self._on_turn_advance)
        self.time_tracker.register_watch_callback(self._on_watch_advance)
        self.time_tracker.register_day_callback(self._on_day_advance)
        self.time_tracker.register_season_callback(self._on_season_change)

        # Register default transition hooks for engine initialization
        self._register_default_transition_hooks()

        logger.info(f"GlobalController initialized in state: {initial_state.value}")

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    @property
    def current_state(self) -> GameState:
        """Get current game state."""
        return self.state_machine.current_state

    @property
    def xp_manager(self) -> Optional["XPManager"]:
        """Get the XP manager for advancement tracking."""
        return self._xp_manager

    def transition(self, trigger: str, context: Optional[dict[str, Any]] = None) -> GameState:
        """
        Transition to a new game state.

        Args:
            trigger: The trigger causing the transition
            context: Optional context data

        Returns:
            The new game state
        """
        return self.state_machine.transition(trigger, context)

    def can_transition(self, trigger: str) -> bool:
        """Check if a transition is valid from current state."""
        return self.state_machine.can_transition(trigger)

    def get_valid_actions(self) -> list[str]:
        """Get valid triggers/actions from current state."""
        return self.state_machine.get_valid_triggers()

    # =========================================================================
    # TRANSITION HOOKS
    # =========================================================================

    def register_transition_hook(
        self,
        from_state: GameState,
        to_state: GameState,
        callback: Callable[[GameState, GameState, str, dict], None],
    ) -> None:
        """
        Register a callback for a specific state transition.

        The callback will be called with (from_state, to_state, trigger, context)
        after the transition completes.

        Args:
            from_state: The starting state
            to_state: The target state
            callback: Function to call on this transition
        """
        key = (from_state, to_state)
        if key not in self._transition_hooks:
            self._transition_hooks[key] = []
        self._transition_hooks[key].append(callback)
        logger.debug(f"Registered transition hook: {from_state.value} -> {to_state.value}")

    def register_on_enter_hook(
        self, state: GameState, callback: Callable[[GameState, GameState, str, dict], None]
    ) -> None:
        """
        Register a callback for entering a state (from any source state).

        The callback will be called with (from_state, to_state, trigger, context).

        Args:
            state: The state to monitor for entry
            callback: Function to call when entering this state
        """
        if state not in self._on_enter_hooks:
            self._on_enter_hooks[state] = []
        self._on_enter_hooks[state].append(callback)
        logger.debug(f"Registered on-enter hook for state: {state.value}")

    def register_on_exit_hook(
        self, state: GameState, callback: Callable[[GameState, GameState, str, dict], None]
    ) -> None:
        """
        Register a callback for exiting a state (to any target state).

        The callback will be called with (from_state, to_state, trigger, context).

        Args:
            state: The state to monitor for exit
            callback: Function to call when exiting this state
        """
        if state not in self._on_exit_hooks:
            self._on_exit_hooks[state] = []
        self._on_exit_hooks[state].append(callback)
        logger.debug(f"Registered on-exit hook for state: {state.value}")

    def _fire_transition_hooks(
        self, from_state: GameState, to_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """
        Fire all registered transition hooks for a state change.

        Fires in order:
        1. On-exit hooks for the old state
        2. Specific (from_state, to_state) hooks
        3. On-enter hooks for the new state

        Args:
            from_state: The state being left
            to_state: The state being entered
            trigger: The trigger that caused the transition
            context: Transition context data
        """
        # 1. Fire on-exit hooks
        for callback in self._on_exit_hooks.get(from_state, []):
            try:
                callback(from_state, to_state, trigger, context)
            except Exception as e:
                logger.error(f"Error in on-exit hook for {from_state.value}: {e}")

        # 2. Fire specific transition hooks
        key = (from_state, to_state)
        for callback in self._transition_hooks.get(key, []):
            try:
                callback(from_state, to_state, trigger, context)
            except Exception as e:
                logger.error(f"Error in transition hook {from_state.value}->{to_state.value}: {e}")

        # 3. Fire on-enter hooks
        for callback in self._on_enter_hooks.get(to_state, []):
            try:
                callback(from_state, to_state, trigger, context)
            except Exception as e:
                logger.error(f"Error in on-enter hook for {to_state.value}: {e}")

    def _register_default_transition_hooks(self) -> None:
        """
        Register default transition hooks for engine initialization.

        These hooks ensure that when transitioning to a state, the appropriate
        engine is initialized and ready to handle operations.
        """
        # Hook: Entering COMBAT initializes combat from the current encounter
        self.register_on_enter_hook(GameState.COMBAT, self._on_enter_combat)

        # Hook: Exiting COMBAT cleans up combat state
        self.register_on_exit_hook(GameState.COMBAT, self._on_exit_combat)

        # Hook: Exiting ENCOUNTER clears encounter if transitioning to non-combat
        self.register_on_exit_hook(GameState.ENCOUNTER, self._on_exit_encounter)

        # Hook: Entering SOCIAL_INTERACTION initializes social context
        self.register_on_enter_hook(GameState.SOCIAL_INTERACTION, self._on_enter_social)

        # Hook: Exiting SOCIAL_INTERACTION cleans up social context
        self.register_on_exit_hook(GameState.SOCIAL_INTERACTION, self._on_exit_social)

        logger.debug("Default transition hooks registered")

    def _on_enter_combat(
        self, from_state: GameState, to_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """
        Hook called when entering COMBAT state.

        Initializes the CombatEngine with the current encounter.
        """
        # Import here to avoid circular import
        from src.combat.combat_engine import CombatEngine

        if self._current_encounter is None:
            logger.warning("Entering COMBAT without an active encounter")
            return

        # Determine the return state based on the previous state
        return_state = from_state
        if from_state == GameState.ENCOUNTER:
            # Get the origin from the encounter or previous state
            return_state = self.state_machine.previous_state or GameState.WILDERNESS_TRAVEL

        # Create and initialize the combat engine
        self._combat_engine = CombatEngine(self)
        result = self._combat_engine.start_combat(
            encounter=self._current_encounter,
            return_state=return_state,
        )

        if result.get("combat_started"):
            logger.info(
                f"Combat initialized from {from_state.value} with {len(self._current_encounter.combatants)} combatants"
            )
        else:
            logger.error(f"Failed to start combat: {result.get('error', 'Unknown error')}")

    def _on_exit_combat(
        self, from_state: GameState, to_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """
        Hook called when exiting COMBAT state.

        Cleans up the combat engine.
        """
        if self._combat_engine:
            logger.debug("Clearing combat engine on exit from COMBAT")
            self._combat_engine = None

    def _on_exit_encounter(
        self, from_state: GameState, to_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """
        Hook called when exiting ENCOUNTER state.

        Clears encounter if transitioning to a non-combat state.
        Combat needs the encounter state, so don't clear if going to COMBAT.
        """
        if to_state != GameState.COMBAT and to_state != GameState.SOCIAL_INTERACTION:
            # Clear the encounter when returning to exploration states
            if self._current_encounter:
                logger.debug("Clearing encounter on exit to exploration state")
                self.clear_encounter()

    @property
    def combat_engine(self) -> Optional[Any]:
        """Get the current combat engine (if combat is active)."""
        return self._combat_engine

    def _on_enter_social(
        self, from_state: GameState, to_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """
        Hook called when entering SOCIAL_INTERACTION state.

        Initializes social context from the current encounter or transition context.
        This provides the narrative layer with participant information for dialogue.
        """
        # Determine the origin based on where we came from
        if from_state == GameState.ENCOUNTER:
            origin = SocialOrigin.ENCOUNTER_PARLEY
        elif from_state == GameState.COMBAT:
            origin = SocialOrigin.COMBAT_PARLEY
        elif from_state == GameState.SETTLEMENT_EXPLORATION:
            origin = SocialOrigin.SETTLEMENT
        else:
            origin = SocialOrigin.HEX_NPC

        # Create social context
        self._social_context = SocialContext(
            origin=origin,
            trigger_context=dict(context),
        )

        # Determine return state
        if from_state == GameState.ENCOUNTER:
            # Return to the exploration state before the encounter
            # Check the encounter context or infer from location
            return_state = self._determine_exploration_return_state(context)
            self._social_context.return_state = return_state.value
        else:
            self._social_context.return_state = from_state.value

        # Extract reaction result from context or encounter
        reaction = context.get("reaction")
        if reaction:
            if isinstance(reaction, str):
                try:
                    self._social_context.initial_reaction = ReactionResult(reaction)
                except ValueError:
                    pass
            elif isinstance(reaction, ReactionResult):
                self._social_context.initial_reaction = reaction

        # Get location context
        self._social_context.hex_id = context.get("hex_id")
        self._social_context.poi_name = context.get("poi_name")

        # Extract source encounter ID if coming from encounter
        if self._current_encounter:
            self._social_context.source_encounter_id = self._current_encounter.encounter_id

        # Build participants from current encounter or context
        self._build_social_participants(context)

        # Log the social context creation
        participant_names = [p.name for p in self._social_context.participants]
        can_parley = self._social_context.can_parley()
        logger.info(
            f"Social context initialized from {from_state.value}: "
            f"participants={participant_names}, can_parley={can_parley}"
        )

        if not can_parley:
            logger.warning(
                "Entering SOCIAL_INTERACTION but no participants can communicate. "
                "Narrative will need to handle non-verbal interaction."
            )

    def _build_social_participants(self, context: dict[str, Any]) -> None:
        """
        Build social participants from encounter actors or context.

        This method attempts to look up full NPC/monster data from the
        encounter's actors and create SocialParticipant entries.
        """
        if not self._social_context:
            return

        participants = []

        # Check if participants were provided directly in context
        if "participants" in context:
            for p_data in context["participants"]:
                if isinstance(p_data, SocialParticipant):
                    participants.append(p_data)
                elif isinstance(p_data, dict):
                    # Try to build from dict
                    participants.append(
                        SocialParticipant(
                            participant_id=p_data.get("id", "unknown"),
                            name=p_data.get("name", "Unknown"),
                            participant_type=SocialParticipantType.NPC,
                            **{k: v for k, v in p_data.items() if k not in ("id", "name")},
                        )
                    )

        # If no explicit participants, try to extract from encounter
        if not participants and self._current_encounter:
            # Get actors from encounter
            actors = self._current_encounter.actors
            reaction = self._social_context.initial_reaction

            # Check for contextual encounter data with topic intelligence
            contextual_data = getattr(self._current_encounter, "contextual_data", None)

            for actor_id in actors:
                participant = self._lookup_and_build_participant(actor_id, reaction, context)
                if participant:
                    # Apply topic intelligence from contextual encounter if available
                    if contextual_data and contextual_data.get("topic_intelligence"):
                        self._apply_contextual_topic_intelligence(participant, contextual_data)
                    participants.append(participant)

        # Check context for NPC data (from settlement conversations, etc.)
        if not participants and "npc_id" in context:
            npc_id = context["npc_id"]
            npc_name = context.get("npc_name", npc_id)

            # Create a basic participant from context
            participant = SocialParticipant(
                participant_id=npc_id,
                name=npc_name,
                participant_type=SocialParticipantType.NPC,
                hex_id=context.get("hex_id"),
                poi_name=context.get("poi_name"),
            )
            participants.append(participant)

        self._social_context.participants = participants

        # Aggregate available quest hooks and secrets
        self._social_context.available_quest_hooks = self._social_context.get_all_quest_hooks()
        self._social_context.available_secrets = self._social_context.get_all_secrets()

    def _lookup_and_build_participant(
        self,
        actor_id: str,
        reaction: Optional[ReactionResult],
        context: dict[str, Any],
    ) -> Optional[SocialParticipant]:
        """
        Look up an actor by ID and build a SocialParticipant.

        Attempts to find the actor in:
        1. Monster registry
        2. NPC registry
        3. Context-provided data
        """
        from src.data_models import Monster, NPC

        hex_id = context.get("hex_id")

        # Try monster registry first
        try:
            from src.content_loader import get_monster_registry

            registry = get_monster_registry()
            result = registry.lookup(actor_id)
            if result.found and result.monster:
                return SocialParticipant.from_monster(
                    result.monster,
                    reaction=reaction,
                    hex_id=hex_id,
                )
        except (ImportError, Exception) as e:
            logger.debug(f"Could not lookup monster {actor_id}: {e}")

        # Try NPC lookup from context or internal registry
        if actor_id in self._npcs:
            # We have the NPC in our character registry
            char_state = self._npcs[actor_id]
            return SocialParticipant(
                participant_id=actor_id,
                name=char_state.name,
                participant_type=SocialParticipantType.NPC,
                hex_id=hex_id,
            )

        # Check context for embedded NPC/monster data
        if "actor_data" in context and actor_id in context["actor_data"]:
            data = context["actor_data"][actor_id]
            return SocialParticipant(
                participant_id=actor_id,
                name=data.get("name", actor_id),
                participant_type=SocialParticipantType(data.get("type", "npc")),
                sentience=data.get("sentience", "Sentient"),
                alignment=data.get("alignment", "Neutral"),
                languages=data.get("languages", []),
                demeanor=data.get("demeanor", []),
                speech=data.get("speech"),
                desires=data.get("desires", []),
                goals=data.get("goals", []),
                secrets=data.get("secrets", []),
                quest_hooks=data.get("quest_hooks", []),
                possessions=data.get("possessions", []),
                hex_id=hex_id,
                reaction_result=reaction,
                can_communicate=data.get("can_communicate", True),
            )

        # Fallback: create minimal participant from ID
        logger.debug(f"Creating minimal participant for unknown actor: {actor_id}")
        return SocialParticipant(
            participant_id=actor_id,
            name=actor_id.replace("_", " ").title(),
            participant_type=SocialParticipantType.MONSTER,
            hex_id=hex_id,
            reaction_result=reaction,
        )

    def _apply_contextual_topic_intelligence(
        self,
        participant: SocialParticipant,
        contextual_data: dict[str, Any],
    ) -> None:
        """
        Apply topic intelligence from a contextual encounter to a participant.

        This injects known_topics and secret_info from hex-specific encounter
        modifiers into the SocialParticipant for social interaction.

        Args:
            participant: The participant to enhance
            contextual_data: Dict with topic_intelligence, behavior, demeanor, speech
        """
        topic_intel = contextual_data.get("topic_intelligence", {})

        # Apply known topics
        known_topics_data = topic_intel.get("known_topics", [])
        for topic_data in known_topics_data:
            topic = KnownTopic(
                topic_id=topic_data.get("topic_id", ""),
                content=topic_data.get("content", ""),
                keywords=topic_data.get("keywords", []),
                required_disposition=topic_data.get("required_disposition", -5),
                category=topic_data.get("category", "general"),
                shared=topic_data.get("shared", False),
                priority=topic_data.get("priority", 0),
            )
            participant.known_topics.append(topic)

        # Apply secret info
        secret_info_data = topic_intel.get("secret_info", [])
        for secret_data in secret_info_data:
            status_str = secret_data.get("status", "unknown")
            try:
                status = SecretStatus(status_str)
            except ValueError:
                status = SecretStatus.UNKNOWN

            secret = SecretInfo(
                secret_id=secret_data.get("secret_id", ""),
                content=secret_data.get("content", ""),
                hint=secret_data.get("hint", ""),
                keywords=secret_data.get("keywords", []),
                required_disposition=secret_data.get("required_disposition", 3),
                required_trust=secret_data.get("required_trust", 2),
                can_be_bribed=secret_data.get("can_be_bribed", False),
                bribe_amount=secret_data.get("bribe_amount", 0),
                status=status,
                hint_count=secret_data.get("hint_count", 0),
            )
            participant.secret_info.append(secret)

        # Apply behavioral modifiers
        if contextual_data.get("demeanor"):
            demeanor = contextual_data["demeanor"]
            if isinstance(demeanor, list):
                participant.demeanor = demeanor
            else:
                participant.demeanor = [demeanor]

        if contextual_data.get("speech"):
            participant.speech = contextual_data["speech"]

        if contextual_data.get("behavior"):
            # Store behavior hint in personality
            behavior = contextual_data["behavior"]
            if behavior == "non_hostile":
                if participant.personality:
                    participant.personality += ". Appears non-hostile."
                else:
                    participant.personality = "Appears non-hostile."

        logger.debug(
            f"Applied contextual topic intelligence to {participant.name}: "
            f"{len(participant.known_topics)} topics, {len(participant.secret_info)} secrets"
        )

    def _determine_exploration_return_state(self, context: dict[str, Any]) -> GameState:
        """
        Determine the exploration state to return to after social interaction.

        Uses party location or context to infer the appropriate exploration state.
        """
        # Check if context explicitly specifies return state
        if "return_state" in context:
            try:
                return GameState(context["return_state"])
            except ValueError:
                pass

        # Check party's current location type
        if self.party_state and self.party_state.location:
            location_type = self.party_state.location.location_type
            if location_type == LocationType.DUNGEON_ROOM:
                return GameState.DUNGEON_EXPLORATION
            elif location_type == LocationType.SETTLEMENT:
                return GameState.SETTLEMENT_EXPLORATION

        # Default to wilderness travel
        return GameState.WILDERNESS_TRAVEL

    def _on_exit_social(
        self, from_state: GameState, to_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """
        Hook called when exiting SOCIAL_INTERACTION state.

        Preserves any conversation outcomes and cleans up social context.
        """
        if self._social_context:
            # Log the conversation summary
            logger.debug(
                f"Exiting social interaction: "
                f"topics={self._social_context.topics_discussed}, "
                f"secrets_revealed={len(self._social_context.secrets_revealed)}, "
                f"quests_offered={self._social_context.quests_offered}"
            )

            # Clear the social context
            self._social_context = None

        # If going back to exploration and not to combat, clear encounter
        if to_state not in {GameState.COMBAT} and self._current_encounter:
            logger.debug("Clearing encounter after social interaction")
            self.clear_encounter()

    @property
    def social_context(self) -> Optional[SocialContext]:
        """Get the current social context (if in social interaction)."""
        return self._social_context

    def set_social_context(self, context: SocialContext) -> None:
        """
        Manually set social context.

        Use this when initiating social interaction through an engine
        (like SettlementEngine) that builds its own context.
        """
        self._social_context = context

    # =========================================================================
    # TIME MANAGEMENT
    # =========================================================================

    def advance_time(self, turns: int = 1) -> dict[str, Any]:
        """
        Advance game time and trigger any time-based effects.

        Args:
            turns: Number of 10-minute turns to advance

        Returns:
            Dictionary with time changes and effects
        """
        result = self.time_tracker.advance_turn(turns)

        # Sync world state with time tracker
        self.world_state.current_time = self.time_tracker.game_time
        self.world_state.current_date = self.time_tracker.game_date
        self.world_state.season = self.time_tracker.season

        # Deplete light sources
        if self.party_state.active_light_source:
            self.party_state.light_remaining_turns -= turns
            if self.party_state.light_remaining_turns <= 0:
                result["light_extinguished"] = True
                result["light_source"] = self.party_state.active_light_source.value
                self.party_state.active_light_source = None
                self.party_state.light_remaining_turns = 0

        # Tick conditions on all characters
        expired_conditions = self._tick_conditions(turns)
        if expired_conditions:
            result["expired_conditions"] = expired_conditions

        self._log_event("time_advance", result)
        return result

    def advance_travel_segment(self, terrain_modifier: float = 1.0) -> dict[str, Any]:
        """
        Advance time for a travel segment.

        A standard travel segment is 4 hours (1 watch) in clear terrain.

        Args:
            terrain_modifier: Multiplier for difficult terrain (>1 = slower)

        Returns:
            Dictionary with travel results
        """
        base_hours = 4
        actual_hours = int(base_hours * terrain_modifier)
        return self.advance_time(actual_hours * 6)  # 6 turns per hour

    # =========================================================================
    # CHARACTER MANAGEMENT
    # =========================================================================

    def add_character(self, character: CharacterState) -> None:
        """Add a character to the roster."""
        self._characters[character.character_id] = character
        if character.character_id not in self.party_state.marching_order:
            self.party_state.marching_order.append(character.character_id)
        self._log_event("character_added", {"character_id": character.character_id})

    def get_character(self, character_id: str) -> Optional[CharacterState]:
        """Get a character by ID (checks party members and NPCs)."""
        char = self._characters.get(character_id)
        if char:
            return char
        # Also check NPC roster
        return self._npcs.get(character_id)

    def get_all_characters(self) -> list[CharacterState]:
        """Get all characters in the party."""
        return list(self._characters.values())

    def get_active_characters(self) -> list[CharacterState]:
        """Get all conscious, active characters."""
        return [c for c in self._characters.values() if c.is_conscious()]

    def get_party_speed(self) -> int:
        """
        Get party movement speed per Dolmenwood rules (p146, p148-149).

        Party speed is determined by the slowest member's encumbered speed.

        Returns:
            Party movement speed (slowest member's encumbered speed)
        """
        characters = self.get_active_characters()
        if not characters:
            return 40  # Default unencumbered speed

        # Update party state with current member speeds
        self.party_state.update_member_speeds(characters)

        return self.party_state.get_movement_rate()

    def get_party_movement_rate(self) -> int:
        """
        Get party movement rate for use in encounter/evasion calculations.

        Alias for get_party_speed() with semantics suited to encounter rules.
        Movement rate represents feet per round during combat/encounters.

        Returns:
            Party movement rate (slowest member's encumbered speed in feet/round)
        """
        return self.get_party_speed()

    def update_party_encumbrance(self) -> dict[str, Any]:
        """
        Update party encumbrance state from all characters.

        Call this after any inventory changes.

        Returns:
            Dictionary with encumbrance status for each character
        """
        characters = self.get_all_characters()
        self.party_state.update_member_speeds(characters)

        result = {
            "party_speed": self.party_state.get_movement_rate(),
            "total_weight": self.party_state.encumbrance_total,
            "members": {},
        }

        for char in characters:
            enc_state = char.get_encumbrance_state()
            result["members"][char.character_id] = {
                "name": char.name,
                "speed": char.get_encumbered_speed(),
                "weight": enc_state.total_weight,
                "equipped_slots": enc_state.equipped_slots,
                "stowed_slots": enc_state.stowed_slots,
                "over_capacity": char.is_over_capacity(),
            }

        return result

    def is_party_over_capacity(self) -> bool:
        """
        Check if any party member is over carrying capacity.

        Returns:
            True if any member is over capacity
        """
        return self.party_state.any_over_capacity(self.get_all_characters())

    def remove_character(self, character_id: str) -> Optional[CharacterState]:
        """Remove a character from the roster."""
        character = self._characters.pop(character_id, None)
        if character and character_id in self.party_state.marching_order:
            self.party_state.marching_order.remove(character_id)
        return character

    # =========================================================================
    # NPC MANAGEMENT
    # =========================================================================

    def register_npc(self, npc: CharacterState) -> None:
        """
        Register an NPC with class abilities for use in combat.

        NPCs registered here can be referenced by combatants via character_ref
        and will have their class abilities applied in combat.

        Args:
            npc: The CharacterState representing the NPC
        """
        self._npcs[npc.character_id] = npc
        self._log_event(
            "npc_registered",
            {
                "character_id": npc.character_id,
                "name": npc.name,
                "class": npc.character_class,
                "level": npc.level,
            },
        )

    def get_npc(self, npc_id: str) -> Optional[CharacterState]:
        """Get a registered NPC by ID."""
        return self._npcs.get(npc_id)

    def get_all_npcs(self) -> list[CharacterState]:
        """Get all registered NPCs."""
        return list(self._npcs.values())

    def remove_npc(self, npc_id: str) -> Optional[CharacterState]:
        """Remove an NPC from the registry."""
        npc = self._npcs.pop(npc_id, None)
        if npc:
            self._log_event("npc_removed", {"character_id": npc_id})
        return npc

    def clear_npcs(self) -> int:
        """
        Clear all registered NPCs.

        Typically called at the end of an encounter.

        Returns:
            Number of NPCs cleared
        """
        count = len(self._npcs)
        self._npcs.clear()
        self._log_event("npcs_cleared", {"count": count})
        return count

    def apply_damage(
        self, character_id: str, damage: int, damage_type: str = "physical"
    ) -> dict[str, Any]:
        """
        Apply damage to a character.

        Automatically breaks concentration per Dolmenwood rules.

        Args:
            character_id: The character to damage
            damage: Amount of damage
            damage_type: Type of damage for resistance checks

        Returns:
            Dictionary with damage results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        old_hp = character.hp_current
        character.hp_current = max(0, character.hp_current - damage)
        actual_damage = old_hp - character.hp_current

        result = {
            "character_id": character_id,
            "damage_dealt": actual_damage,
            "hp_remaining": character.hp_current,
            "hp_max": character.hp_max,
        }

        # Break concentration on damage (per Dolmenwood rules)
        if actual_damage > 0 and self._narrative_resolver:
            broken_effects = self._narrative_resolver.break_concentration(character_id)
            if broken_effects:
                result["concentration_broken"] = [effect.spell_name for effect in broken_effects]

        if character.hp_current <= 0:
            character.conditions.append(Condition(ConditionType.UNCONSCIOUS, source="damage"))
            result["unconscious"] = True

            # Check for death at -10 or negative equal to max HP
            if character.hp_current <= -10 or character.hp_current <= -character.hp_max:
                character.conditions.append(Condition(ConditionType.DEAD, source="damage"))
                result["dead"] = True

        self._log_event("damage_applied", result)
        return result

    def heal_character(self, character_id: str, healing: int) -> dict[str, Any]:
        """
        Heal a character.

        Args:
            character_id: The character to heal
            healing: Amount of healing

        Returns:
            Dictionary with healing results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        old_hp = character.hp_current
        character.hp_current = min(character.hp_max, character.hp_current + healing)
        actual_healing = character.hp_current - old_hp

        # Remove unconscious if healed above 0
        if old_hp <= 0 and character.hp_current > 0:
            character.conditions = [
                c for c in character.conditions if c.condition_type != ConditionType.UNCONSCIOUS
            ]

        result = {
            "character_id": character_id,
            "healing_received": actual_healing,
            "hp_current": character.hp_current,
            "hp_max": character.hp_max,
        }

        self._log_event("healing_applied", result)
        return result

    def apply_condition(
        self, character_id: str, condition: str, source: str = "hazard"
    ) -> dict[str, Any]:
        """
        Apply a condition to a character.

        Args:
            character_id: The character to affect
            condition: Condition name (e.g., "exhausted", "drowning", "poisoned")
            source: What caused the condition

        Returns:
            Dictionary with condition application results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Map string conditions to ConditionType enum
        condition_map = {
            "exhausted": ConditionType.EXHAUSTED,
            "frightened": ConditionType.FRIGHTENED,
            "poisoned": ConditionType.POISONED,
            "paralyzed": ConditionType.PARALYZED,
            "unconscious": ConditionType.UNCONSCIOUS,
            "dead": ConditionType.DEAD,
            "drowning": ConditionType.DROWNING,
            "holding_breath": ConditionType.HOLDING_BREATH,
            "hungry": ConditionType.HUNGRY,
            "starving": ConditionType.STARVING,
            "dehydrated": ConditionType.DEHYDRATED,
            "blinded": ConditionType.BLINDED,
            "deafened": ConditionType.DEAFENED,
            "stunned": ConditionType.STUNNED,
            "prone": ConditionType.PRONE,
            "restrained": ConditionType.RESTRAINED,
            "charmed": ConditionType.CHARMED,
            "invisible": ConditionType.INVISIBLE,
            "incapacitated": ConditionType.INCAPACITATED,
        }

        condition_lower = condition.lower()
        condition_type = condition_map.get(condition_lower)

        if not condition_type:
            # Create a generic condition if type not recognized
            logger.warning(f"Unknown condition type: {condition}")
            # Use a fallback for unknown conditions
            return {
                "character_id": character_id,
                "condition": condition,
                "applied": False,
                "reason": f"Unknown condition type: {condition}",
            }

        # Check if character already has this condition
        existing = any(c.condition_type == condition_type for c in character.conditions)
        if existing:
            return {
                "character_id": character_id,
                "condition": condition,
                "applied": False,
                "reason": "Character already has this condition",
            }

        # Apply the condition
        new_condition = Condition(condition_type, source=source)
        character.conditions.append(new_condition)

        result = {
            "character_id": character_id,
            "condition": condition,
            "condition_type": condition_type.value,
            "source": source,
            "applied": True,
        }

        self._log_event("condition_applied", result)
        return result

    def remove_condition(self, character_id: str, condition: str) -> dict[str, Any]:
        """
        Remove a condition from a character.

        Args:
            character_id: The character to affect
            condition: Condition name to remove

        Returns:
            Dictionary with condition removal results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Map string conditions to ConditionType enum
        condition_map = {
            "exhausted": ConditionType.EXHAUSTED,
            "frightened": ConditionType.FRIGHTENED,
            "poisoned": ConditionType.POISONED,
            "paralyzed": ConditionType.PARALYZED,
            "unconscious": ConditionType.UNCONSCIOUS,
            "drowning": ConditionType.DROWNING,
            "holding_breath": ConditionType.HOLDING_BREATH,
            "hungry": ConditionType.HUNGRY,
            "starving": ConditionType.STARVING,
            "dehydrated": ConditionType.DEHYDRATED,
            "blinded": ConditionType.BLINDED,
            "deafened": ConditionType.DEAFENED,
            "stunned": ConditionType.STUNNED,
            "prone": ConditionType.PRONE,
            "restrained": ConditionType.RESTRAINED,
            "charmed": ConditionType.CHARMED,
            "invisible": ConditionType.INVISIBLE,
            "incapacitated": ConditionType.INCAPACITATED,
        }

        condition_lower = condition.lower()
        condition_type = condition_map.get(condition_lower)

        if not condition_type:
            return {
                "character_id": character_id,
                "condition": condition,
                "removed": False,
                "reason": f"Unknown condition type: {condition}",
            }

        # Remove the condition
        original_count = len(character.conditions)
        character.conditions = [
            c for c in character.conditions if c.condition_type != condition_type
        ]
        removed = len(character.conditions) < original_count

        result = {
            "character_id": character_id,
            "condition": condition,
            "removed": removed,
        }

        if removed:
            self._log_event("condition_removed", result)

        return result

    def has_condition(self, character_id: str, condition_type: ConditionType) -> bool:
        """
        Check if a character has a specific condition.

        Args:
            character_id: The character to check
            condition_type: The condition type to look for

        Returns:
            True if the character has the condition
        """
        character = self.get_character(character_id)
        if not character:
            return False
        return any(c.condition_type == condition_type for c in character.conditions)

    def get_condition_attack_modifier(self, character_id: str) -> int:
        """
        Get total attack roll modifier from active conditions.

        Condition effects (per Dolmenwood/OSE rules):
        - BLINDED: -4 to attack
        - POISONED: -2 to attack
        - PRONE: -4 to melee attacks
        - FRIGHTENED: -2 to attacks while source visible
        - EXHAUSTED: -1 per exhaustion level

        Args:
            character_id: The character to check

        Returns:
            Total attack modifier (negative = penalty)
        """
        character = self.get_character(character_id)
        if not character:
            return 0

        modifier = 0
        for cond in character.conditions:
            if cond.condition_type == ConditionType.BLINDED:
                modifier -= 4
            elif cond.condition_type == ConditionType.POISONED:
                modifier -= 2
            elif cond.condition_type == ConditionType.PRONE:
                modifier -= 4  # Melee attacks; ranged would be different
            elif cond.condition_type == ConditionType.FRIGHTENED:
                modifier -= 2
            elif cond.condition_type == ConditionType.EXHAUSTED:
                # Exhaustion stacks; check exhaustion_level if tracked
                modifier -= 1

        return modifier

    def get_condition_defense_modifier(self, character_id: str) -> int:
        """
        Get AC/defense modifier from active conditions (for enemies attacking this character).

        Condition effects:
        - BLINDED: +4 for enemies to hit (AC effectively -4)
        - PRONE: +4 for melee attackers, -4 for ranged (simplified to +2)
        - PARALYZED: Melee attacks auto-hit (represented as large bonus)
        - STUNNED: Auto-fail DEX-based AC (represented as +4)
        - RESTRAINED: +2 for enemies to hit

        Args:
            character_id: The character being attacked

        Returns:
            Modifier for attackers (positive = easier to hit)
        """
        character = self.get_character(character_id)
        if not character:
            return 0

        modifier = 0
        for cond in character.conditions:
            if cond.condition_type == ConditionType.BLINDED:
                modifier += 4  # Enemies have advantage
            elif cond.condition_type == ConditionType.PRONE:
                modifier += 2  # Simplified (melee +4, ranged -4)
            elif cond.condition_type == ConditionType.PARALYZED:
                modifier += 10  # Effectively auto-hit for melee
            elif cond.condition_type == ConditionType.STUNNED:
                modifier += 4
            elif cond.condition_type == ConditionType.RESTRAINED:
                modifier += 2

        return modifier

    def get_condition_save_modifier(self, character_id: str, save_type: str = "") -> int:
        """
        Get saving throw modifier from active conditions.

        Condition effects:
        - POISONED: -2 to all saves
        - EXHAUSTED: -1 per level to saves
        - FRIGHTENED: -2 to saves while source visible

        Args:
            character_id: The character making the save
            save_type: Optional save type for specific modifiers

        Returns:
            Modifier to saving throw (negative = penalty)
        """
        character = self.get_character(character_id)
        if not character:
            return 0

        modifier = 0
        for cond in character.conditions:
            if cond.condition_type == ConditionType.POISONED:
                modifier -= 2
            elif cond.condition_type == ConditionType.EXHAUSTED:
                modifier -= 1
            elif cond.condition_type == ConditionType.FRIGHTENED:
                modifier -= 2

        return modifier

    def can_character_act(self, character_id: str) -> tuple[bool, str]:
        """
        Check if a character can take actions based on conditions.

        Returns:
            Tuple of (can_act, reason_if_not)
        """
        character = self.get_character(character_id)
        if not character:
            return False, "Character not found"

        for cond in character.conditions:
            if cond.condition_type == ConditionType.PARALYZED:
                return False, "Paralyzed - cannot move or act"
            elif cond.condition_type == ConditionType.STUNNED:
                return False, "Stunned - cannot act"
            elif cond.condition_type == ConditionType.PETRIFIED:
                return False, "Petrified - turned to stone"
            elif cond.condition_type == ConditionType.UNCONSCIOUS:
                return False, "Unconscious"
            elif cond.condition_type == ConditionType.INCAPACITATED:
                return False, "Incapacitated"

        return True, ""

    def apply_charm(
        self,
        character_id: str,
        caster_id: str,
        source_spell_id: str,
        source: str = "",
        recurring_save: Optional[dict[str, Any]] = None,
        duration_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Apply a charm effect to a character.

        This method properly sets up the charm condition with all the
        tracking needed for recurring saves, caster relationships, etc.

        Args:
            character_id: The character being charmed
            caster_id: The character doing the charming
            source_spell_id: ID of the charm spell
            source: Description (spell name)
            recurring_save: Config for recurring saves:
                           {"save_type": "spell", "frequency": "daily",
                            "modifier": 0, "ends_on_success": True}
            duration_days: Duration in days (None for indefinite until save)

        Returns:
            Dictionary with charm application results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Check if already charmed (by anyone)
        if character.is_charmed():
            return {
                "character_id": character_id,
                "charmed": False,
                "reason": "Already charmed",
                "existing_charmer": character.get_charm_caster(),
            }

        # Apply the charm using CharacterState's method
        charm_condition = character.apply_charm(
            caster_id=caster_id,
            source_spell_id=source_spell_id,
            source=source,
            recurring_save=recurring_save,
            duration_days=duration_days,
        )

        result = {
            "character_id": character_id,
            "charmed": True,
            "caster_id": caster_id,
            "source": source,
            "spell_id": source_spell_id,
            "has_recurring_save": recurring_save is not None,
            "recurring_save_frequency": recurring_save.get("frequency") if recurring_save else None,
        }

        self._log_event("charm_applied", result)
        return result

    def break_charm(
        self,
        character_id: str,
        caster_id: Optional[str] = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Break a charm effect on a character.

        Args:
            character_id: The charmed character
            caster_id: Optional specific caster's charm to break
            reason: Why the charm is breaking (save, spell dispel, etc.)

        Returns:
            Dictionary with charm removal results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        removed_charm = character.break_charm(caster_id)

        if removed_charm:
            result = {
                "character_id": character_id,
                "charm_broken": True,
                "former_charmer": removed_charm.caster_id,
                "reason": reason,
            }
            self._log_event("charm_broken", result)
            return result
        else:
            return {
                "character_id": character_id,
                "charm_broken": False,
                "reason": "Character was not charmed",
            }

    # =========================================================================
    # GLYPH MANAGEMENT (Magical seals on doors/portals)
    # =========================================================================

    def place_glyph(
        self,
        caster_id: str,
        target_id: str,
        glyph_type: GlyphType,
        source_spell_id: str,
        name: str = "",
        target_type: str = "door",
        duration_turns: Optional[int] = None,
        password: Optional[str] = None,
        can_be_bypassed_by_level: Optional[int] = None,
        trigger_condition: Optional[str] = None,
        trap_effect: Optional[str] = None,
        trap_damage: Optional[str] = None,
        trap_save_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Place a magical glyph on a door or object.

        Args:
            caster_id: ID of the character placing the glyph
            target_id: ID of the door/object
            glyph_type: Type of glyph (SEALING, LOCKING, TRAP)
            source_spell_id: ID of the spell creating the glyph
            name: Name of the glyph (e.g., "Glyph of Sealing")
            target_type: Type of target ("door", "chest", "portal")
            duration_turns: Duration in turns (None = permanent)
            password: Password for locking glyphs
            can_be_bypassed_by_level: Higher-level casters can bypass
            trigger_condition: For trap glyphs
            trap_effect: Effect when triggered
            trap_damage: Damage when triggered
            trap_save_type: Save type for traps

        Returns:
            Dictionary with glyph placement results
        """
        caster = self._characters.get(caster_id)
        if not caster:
            return {"error": f"Caster {caster_id} not found"}

        # Create the glyph
        glyph = Glyph(
            glyph_type=glyph_type,
            name=name or f"Glyph of {glyph_type.value.title()}",
            source_spell_id=source_spell_id,
            caster_id=caster_id,
            caster_level=caster.level,
            target_type=target_type,
            target_id=target_id,
            duration_turns=duration_turns,
            turns_remaining=duration_turns,
            password=password,
            can_be_bypassed_by_level=can_be_bypassed_by_level,
            trigger_condition=trigger_condition,
            trap_effect=trap_effect,
            trap_damage=trap_damage,
            trap_save_type=trap_save_type,
            placed_at_turn=self.time_tracker.exploration_turns,
        )

        self._glyphs[glyph.glyph_id] = glyph

        result = {
            "glyph_id": glyph.glyph_id,
            "glyph_type": glyph_type.value,
            "target_id": target_id,
            "target_type": target_type,
            "caster_id": caster_id,
            "caster_level": caster.level,
            "placed": True,
            "has_password": password is not None,
        }

        self._log_event("glyph_placed", result)
        return result

    def get_glyphs_on_target(
        self,
        target_id: str,
        active_only: bool = True,
    ) -> list[Glyph]:
        """
        Get all glyphs on a specific target.

        Args:
            target_id: ID of the door/object
            active_only: Only return active glyphs

        Returns:
            List of Glyph objects
        """
        current_turn = self.time_tracker.exploration_turns
        return [
            g for g in self._glyphs.values()
            if g.target_id == target_id
            and (not active_only or g.is_active(current_turn))
        ]

    def dispel_glyph(
        self,
        glyph_id: str,
        dispeller_id: Optional[str] = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Dispel (permanently remove) a glyph.

        Args:
            glyph_id: ID of the glyph to dispel
            dispeller_id: Who is dispelling (optional)
            reason: Why it's being dispelled

        Returns:
            Dictionary with dispel results
        """
        glyph = self._glyphs.get(glyph_id)
        if not glyph:
            return {"error": f"Glyph {glyph_id} not found"}

        glyph.dispel()

        result = {
            "glyph_id": glyph_id,
            "glyph_type": glyph.glyph_type.value,
            "target_id": glyph.target_id,
            "dispelled": True,
            "dispeller_id": dispeller_id,
            "reason": reason,
        }

        self._log_event("glyph_dispelled", result)
        return result

    def disable_glyph_temporarily(
        self,
        glyph_id: str,
        duration_turns: int,
        disabler_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Temporarily disable a glyph (e.g., by Knock spell).

        Args:
            glyph_id: ID of the glyph to disable
            duration_turns: How many turns to disable
            disabler_id: Who is disabling (optional)

        Returns:
            Dictionary with disable results
        """
        glyph = self._glyphs.get(glyph_id)
        if not glyph:
            return {"error": f"Glyph {glyph_id} not found"}

        current_turn = self.time_tracker.exploration_turns
        glyph.disable_temporarily(duration_turns, current_turn)

        result = {
            "glyph_id": glyph_id,
            "glyph_type": glyph.glyph_type.value,
            "target_id": glyph.target_id,
            "disabled": True,
            "disabled_until_turn": glyph.disabled_until_turn,
            "disabler_id": disabler_id,
        }

        self._log_event("glyph_disabled", result)
        return result

    def check_glyph_bypass(
        self,
        target_id: str,
        character_id: str,
        password: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Check if a character can bypass glyphs on a target.

        Args:
            target_id: ID of the door/object
            character_id: ID of the character trying to pass
            password: Password to try (for locking glyphs)

        Returns:
            Dictionary with bypass check results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        glyphs = self.get_glyphs_on_target(target_id, active_only=True)

        if not glyphs:
            return {
                "can_bypass": True,
                "blocking_glyphs": [],
                "bypassed_glyphs": [],
            }

        blocking = []
        bypassed = []

        for glyph in glyphs:
            can_bypass, reason = glyph.check_bypass(
                character_id=character_id,
                character_level=character.level,
                password_given=password,
            )

            if can_bypass:
                bypassed.append({
                    "glyph_id": glyph.glyph_id,
                    "glyph_type": glyph.glyph_type.value,
                    "reason": reason,
                })
            else:
                blocking.append({
                    "glyph_id": glyph.glyph_id,
                    "glyph_type": glyph.glyph_type.value,
                    "name": glyph.name,
                    "caster_level": glyph.caster_level,
                })

        return {
            "can_bypass": len(blocking) == 0,
            "blocking_glyphs": blocking,
            "bypassed_glyphs": bypassed,
        }

    def trigger_trap_glyph(
        self,
        glyph_id: str,
        triggerer_id: str,
    ) -> dict[str, Any]:
        """
        Trigger a trap glyph.

        Args:
            glyph_id: ID of the glyph
            triggerer_id: ID of the character who triggered it

        Returns:
            Dictionary with trap trigger results
        """
        glyph = self._glyphs.get(glyph_id)
        if not glyph:
            return {"error": f"Glyph {glyph_id} not found"}

        if glyph.glyph_type != GlyphType.TRAP:
            return {"error": "Glyph is not a trap"}

        trigger_result = glyph.trigger_trap()
        trigger_result["triggerer_id"] = triggerer_id

        if trigger_result["triggered"]:
            self._log_event("trap_glyph_triggered", trigger_result)

        return trigger_result

    def cast_knock(
        self,
        caster_id: str,
        target_id: str,
    ) -> dict[str, Any]:
        """
        Cast Knock on a door/portal.

        Unlocks mundane locks, dispels Glyphs of Sealing,
        and temporarily disables other glyphs.

        Args:
            caster_id: ID of the caster
            target_id: ID of the door/portal

        Returns:
            Dictionary with Knock results
        """
        glyphs = self.get_glyphs_on_target(target_id, active_only=True)

        dispelled = []
        disabled = []

        for glyph in glyphs:
            if glyph.glyph_type == GlyphType.SEALING:
                # Glyph of Sealing is dispelled
                self.dispel_glyph(glyph.glyph_id, caster_id, "Knock spell")
                dispelled.append({
                    "glyph_id": glyph.glyph_id,
                    "name": glyph.name,
                })
            else:
                # Other glyphs are disabled for 1 turn
                self.disable_glyph_temporarily(glyph.glyph_id, 1, caster_id)
                disabled.append({
                    "glyph_id": glyph.glyph_id,
                    "name": glyph.name,
                    "disabled_for_turns": 1,
                })

        result = {
            "target_id": target_id,
            "caster_id": caster_id,
            "glyphs_dispelled": dispelled,
            "glyphs_disabled": disabled,
            "mundane_locks_opened": True,  # Knock also opens mundane locks
        }

        self._log_event("knock_cast", result)
        return result

    def tick_glyphs(self) -> list[dict[str, Any]]:
        """
        Process turn advancement for all glyphs.

        Called automatically on turn advance.

        Returns:
            List of expired glyph info
        """
        expired = []

        for glyph_id, glyph in list(self._glyphs.items()):
            if not glyph.tick_turn():
                # Glyph expired
                expired.append({
                    "glyph_id": glyph_id,
                    "name": glyph.name,
                    "target_id": glyph.target_id,
                })
                del self._glyphs[glyph_id]

        return expired

    # =========================================================================
    # COMBAT MODIFIER MANAGEMENT (Mirror Image, Haste, Confusion, Fear)
    # =========================================================================

    def apply_mirror_images(
        self,
        character_id: str,
        dice: str = "1d4",
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply Mirror Image spell to a character.

        Args:
            character_id: Target character ID
            dice: Dice expression for number of images (default "1d4")
            caster_id: ID of the caster (for dispel tracking)

        Returns:
            Result with image count
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        # Roll for number of images
        from src.data_models import DiceRoller
        dice_roller = DiceRoller()
        roll = dice_roller.roll(dice, "Mirror images")

        character.mirror_image_count = roll.total

        return {
            "success": True,
            "character_id": character_id,
            "images_created": roll.total,
            "dice_rolled": dice,
            "roll_details": str(roll),
        }

    def remove_mirror_images(self, character_id: str) -> dict[str, Any]:
        """
        Remove all mirror images from a character.

        Args:
            character_id: Target character ID

        Returns:
            Result info
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        previous_count = character.mirror_image_count
        character.mirror_image_count = 0

        return {
            "success": True,
            "character_id": character_id,
            "images_removed": previous_count,
        }

    def apply_haste(
        self,
        character_id: str,
        duration_turns: int,
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply Haste spell to a character.

        Haste grants: +2 AC, +2 initiative, extra action per round.

        Args:
            character_id: Target character ID
            duration_turns: Duration in turns
            caster_id: ID of the caster

        Returns:
            Result info
        """
        from src.data_models import Condition, ConditionType

        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        # Apply hasted condition
        condition = Condition(
            condition_type=ConditionType.HASTED,
            source="Haste spell",
            duration_turns=duration_turns,
            caster_id=caster_id,
        )
        character.conditions.append(condition)

        # Apply AC buff
        self.apply_buff(
            character_id=character_id,
            stat="AC",
            value=2,
            source="Haste",
            source_id=caster_id,
            duration_turns=duration_turns,
        )

        return {
            "success": True,
            "character_id": character_id,
            "duration_turns": duration_turns,
            "bonuses": {"ac": 2, "initiative": 2, "extra_action": True},
        }

    def apply_confusion(
        self,
        character_id: str,
        duration_turns: int,
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply Confusion spell to a character.

        Confused creatures must roll for behavior each round.

        Args:
            character_id: Target character ID
            duration_turns: Duration in turns
            caster_id: ID of the caster

        Returns:
            Result info
        """
        from src.data_models import Condition, ConditionType

        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        condition = Condition(
            condition_type=ConditionType.CONFUSED,
            source="Confusion spell",
            duration_turns=duration_turns,
            caster_id=caster_id,
        )
        character.conditions.append(condition)

        return {
            "success": True,
            "character_id": character_id,
            "duration_turns": duration_turns,
            "behavior_table": "2d6: 2-5=attack party, 6-8=stand confused, 9-11=attack nearest, 12=act normally",
        }

    def roll_confusion_behavior(self, character_id: str) -> dict[str, Any]:
        """
        Roll confusion behavior for a confused character.

        Args:
            character_id: Target character ID

        Returns:
            Behavior result
        """
        from src.data_models import ConfusionBehavior

        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        if not character.is_confused():
            return {"success": False, "error": f"{character.name} is not confused"}

        behavior = character.roll_confusion_behavior()

        behavior_descriptions = {
            ConfusionBehavior.ATTACK_PARTY: "Attack nearest ally",
            ConfusionBehavior.STAND_CONFUSED: "Stand confused (no action)",
            ConfusionBehavior.ATTACK_NEAREST: "Attack nearest creature",
            ConfusionBehavior.ACT_NORMALLY: "Act normally this round",
        }

        return {
            "success": True,
            "character_id": character_id,
            "behavior": behavior.value,
            "description": behavior_descriptions.get(behavior, "Unknown behavior"),
        }

    def apply_fear(
        self,
        character_id: str,
        duration_turns: int,
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply Fear effect to a character.

        Frightened creatures must flee or cower if cornered.

        Args:
            character_id: Target character ID
            duration_turns: Duration in turns
            caster_id: ID of the caster

        Returns:
            Result info
        """
        from src.data_models import Condition, ConditionType

        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        condition = Condition(
            condition_type=ConditionType.FRIGHTENED,
            source="Fear spell",
            duration_turns=duration_turns,
            caster_id=caster_id,
        )
        character.conditions.append(condition)

        return {
            "success": True,
            "character_id": character_id,
            "duration_turns": duration_turns,
            "effect": "Must flee; if cornered, cower (-2 attacks and saves)",
        }

    def apply_attack_modifier(
        self,
        character_id: str,
        modifier: int,
        duration_turns: int,
        source: str = "Spell",
        source_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply an attack roll modifier to a character.

        Args:
            character_id: Target character ID
            modifier: Attack bonus/penalty
            duration_turns: Duration in turns
            source: Source name (e.g., "Ginger Snap")
            source_id: Source ID for tracking

        Returns:
            Result info
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        self.apply_buff(
            character_id=character_id,
            stat="attack",
            value=modifier,
            source=source,
            source_id=source_id,
            duration_turns=duration_turns,
        )

        return {
            "success": True,
            "character_id": character_id,
            "attack_modifier": modifier,
            "duration_turns": duration_turns,
            "source": source,
        }

    # =========================================================================
    # BUFF/DEBUFF MANAGEMENT (stat modifiers from spells, items, abilities)
    # =========================================================================

    def apply_buff(
        self,
        character_id: str,
        stat: str,
        value: int,
        source: str,
        source_id: Optional[str] = None,
        duration_turns: Optional[int] = None,
        duration_rounds: Optional[int] = None,
        condition: Optional[str] = None,
        stacks: bool = False,
        stack_group: Optional[str] = None,
        is_override: bool = False,
    ) -> dict[str, Any]:
        """
        Apply a stat modifier (buff or debuff) to a character.

        Args:
            character_id: The character to buff/debuff
            stat: Stat to modify (e.g., "AC", "attack", "damage", "STR")
            value: Modifier value (positive = buff, negative = debuff)
                   For is_override=True, this is the target value to set
            source: What caused this modifier (spell name, item, ability)
            source_id: Optional ID for removal (spell effect ID, item ID)
            duration_turns: Duration in exploration turns (10 min each)
            duration_rounds: Duration in combat rounds
            condition: When this applies (e.g., "vs_missiles", "vs_melee")
            stacks: Whether multiple instances stack
            stack_group: Group name for non-stacking (highest wins)
            is_override: If True, set stat to value instead of adding to it
                        (e.g., "AC becomes 17" instead of "AC +2")

        Returns:
            Dictionary with buff application results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Generate unique modifier ID
        import uuid
        modifier_id = f"mod_{uuid.uuid4().hex[:8]}"

        # Create the modifier
        from src.data_models import StatModifier
        modifier = StatModifier(
            modifier_id=modifier_id,
            stat=stat,
            value=value,
            source=source,
            source_id=source_id,
            mode="set" if is_override else "add",
            duration_turns=duration_turns,
            duration_rounds=duration_rounds,
            condition=condition,
            stacks=stacks,
            stack_group=stack_group,
        )

        # Add to character
        character.add_stat_modifier(modifier)

        result = {
            "character_id": character_id,
            "modifier_id": modifier_id,
            "stat": stat,
            "value": value,
            "source": source,
            "condition": condition,
            "duration_turns": duration_turns,
            "duration_rounds": duration_rounds,
            "is_override": is_override,
            "applied": True,
        }

        self._log_event("buff_applied", result)
        return result

    def remove_buff(
        self, character_id: str, modifier_id: Optional[str] = None, source_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Remove a stat modifier from a character.

        Args:
            character_id: The character to affect
            modifier_id: Specific modifier ID to remove
            source_id: Remove all modifiers from this source

        Returns:
            Dictionary with removal results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        removed_count = 0

        if modifier_id:
            removed = character.remove_stat_modifier(modifier_id)
            if removed:
                removed_count = 1
        elif source_id:
            removed = character.remove_modifiers_by_source(source_id)
            removed_count = len(removed)

        result = {
            "character_id": character_id,
            "removed_count": removed_count,
            "modifier_id": modifier_id,
            "source_id": source_id,
        }

        if removed_count > 0:
            self._log_event("buff_removed", result)

        return result

    def tick_character_modifiers(self, character_id: str, time_unit: str = "turn") -> dict[str, Any]:
        """
        Advance all stat modifiers for a character by one time unit.

        Args:
            character_id: The character to advance
            time_unit: "turn" for exploration turns, "round" for combat rounds

        Returns:
            Dictionary with expired modifier info
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        if time_unit == "round":
            expired = character.tick_stat_modifiers_round()
        else:
            expired = character.tick_stat_modifiers_turn()

        result = {
            "character_id": character_id,
            "time_unit": time_unit,
            "expired_count": len(expired),
            "expired_modifiers": [
                {"modifier_id": m.modifier_id, "stat": m.stat, "source": m.source}
                for m in expired
            ],
        }

        if expired:
            self._log_event("modifiers_expired", result)

        return result

    # =========================================================================
    # VISIBILITY MANAGEMENT
    # =========================================================================

    def make_invisible(
        self,
        character_id: str,
        source: str,
    ) -> dict[str, Any]:
        """
        Make a character invisible.

        Args:
            character_id: The character to make invisible
            source: Source of invisibility (spell ID, item ID)

        Returns:
            Dictionary with result info
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        character.make_invisible(source)

        result = {
            "character_id": character_id,
            "visibility_state": "invisible",
            "source": source,
        }
        self._log_event("visibility_changed", result)
        return result

    def break_invisibility(
        self,
        character_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Break a character's invisibility (e.g., on hostile action).

        Args:
            character_id: The character whose invisibility to break
            reason: Why invisibility was broken

        Returns:
            Dictionary with result info
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        was_invisible = character.break_invisibility(reason)

        result = {
            "character_id": character_id,
            "was_invisible": was_invisible,
            "reason": reason,
            "visibility_state": str(character.visibility_state.value),
        }
        if was_invisible:
            self._log_event("invisibility_broken", result)
        return result

    def grant_see_invisible(
        self,
        character_id: str,
        source: str,
    ) -> dict[str, Any]:
        """
        Grant a character the ability to see invisible creatures.

        Args:
            character_id: The character to grant the ability to
            source: Source of the ability (spell ID, item ID)

        Returns:
            Dictionary with result info
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        character.grant_see_invisible(source)

        result = {
            "character_id": character_id,
            "can_see_invisible": True,
            "source": source,
        }
        self._log_event("see_invisible_granted", result)
        return result

    def remove_see_invisible(self, character_id: str) -> dict[str, Any]:
        """
        Remove a character's ability to see invisible creatures.

        Args:
            character_id: The character to remove the ability from

        Returns:
            Dictionary with result info
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        character.remove_see_invisible()

        result = {
            "character_id": character_id,
            "can_see_invisible": False,
        }
        self._log_event("see_invisible_removed", result)
        return result

    # =========================================================================
    # LOCATION MANAGEMENT
    # =========================================================================

    def set_party_location(
        self, location_type: LocationType, location_id: str, sub_location: Optional[str] = None
    ) -> None:
        """Set the party's current location."""
        self.party_state.location = Location(
            location_type=location_type, location_id=location_id, sub_location=sub_location
        )
        self._log_event("location_changed", {"location": str(self.party_state.location)})

    def get_location_state(self, location_id: str) -> Optional[LocationState]:
        """Get state for a specific location."""
        return self._locations.get(location_id)

    def set_location_state(self, location_id: str, state: LocationState) -> None:
        """Set state for a location."""
        self._locations[location_id] = state

    # =========================================================================
    # ENCOUNTER MANAGEMENT
    # =========================================================================

    def set_encounter(self, encounter: EncounterState) -> None:
        """Set the current encounter."""
        self._current_encounter = encounter
        self._log_event(
            "encounter_started",
            {
                "encounter_id": encounter.encounter_id,
                "encounter_type": encounter.encounter_type.value,
            },
        )

    def get_encounter(self) -> Optional[EncounterState]:
        """Get the current encounter."""
        return self._current_encounter

    def clear_encounter(self) -> None:
        """Clear the current encounter."""
        if self._current_encounter:
            self._log_event(
                "encounter_ended",
                {
                    "encounter_id": self._current_encounter.encounter_id,
                },
            )
        self._current_encounter = None

    # =========================================================================
    # RESOURCE MANAGEMENT
    # =========================================================================

    def consume_resources(
        self, food_days: float = 0, water_days: float = 0, torches: int = 0, oil_flasks: int = 0
    ) -> dict[str, Any]:
        """
        Consume party resources.

        Returns:
            Dictionary with consumption results and warnings
        """
        party_size = len(self.get_active_characters())
        result = {"consumed": {}, "warnings": []}

        if food_days > 0:
            sufficient = self.party_state.resources.consume_food(food_days, party_size)
            result["consumed"]["food"] = food_days * party_size
            if not sufficient:
                result["warnings"].append("Party is out of food!")

        if water_days > 0:
            sufficient = self.party_state.resources.consume_water(water_days, party_size)
            result["consumed"]["water"] = water_days * party_size
            if not sufficient:
                result["warnings"].append("Party is out of water!")

        if torches > 0:
            self.party_state.resources.torches -= torches
            result["consumed"]["torches"] = torches
            if self.party_state.resources.torches < 0:
                self.party_state.resources.torches = 0
                result["warnings"].append("No more torches!")

        if oil_flasks > 0:
            self.party_state.resources.lantern_oil_flasks -= oil_flasks
            result["consumed"]["oil_flasks"] = oil_flasks
            if self.party_state.resources.lantern_oil_flasks < 0:
                self.party_state.resources.lantern_oil_flasks = 0
                result["warnings"].append("No more lantern oil!")

        if result["consumed"]:
            self._log_event("resources_consumed", result)

        return result

    def light_source(self, source_type: LightSourceType) -> dict[str, Any]:
        """
        Activate a light source.

        Returns:
            Dictionary with light source status
        """
        duration_map = {
            LightSourceType.TORCH: 6,  # 1 hour
            LightSourceType.LANTERN: 24,  # 4 hours
            LightSourceType.CANDLE: 12,  # 2 hours
            LightSourceType.MAGICAL: 144,  # 24 hours
        }

        if source_type == LightSourceType.TORCH:
            if self.party_state.resources.torches <= 0:
                return {"error": "No torches available"}
            self.party_state.resources.torches -= 1

        elif source_type == LightSourceType.LANTERN:
            if self.party_state.resources.lantern_oil_flasks <= 0:
                return {"error": "No lantern oil available"}
            self.party_state.resources.lantern_oil_flasks -= 1

        self.party_state.active_light_source = source_type
        self.party_state.light_remaining_turns = duration_map.get(source_type, 6)

        result = {
            "light_source": source_type.value,
            "duration_turns": self.party_state.light_remaining_turns,
        }
        self._log_event("light_activated", result)
        return result

    # =========================================================================
    # WEATHER AND ENVIRONMENT
    # =========================================================================

    def set_weather(
        self,
        weather: Weather,
        description: str = "",
        effects_flags: int = 0,
    ) -> None:
        """
        Set current weather.

        Args:
            weather: The simplified Weather enum value
            description: Evocative weather description from tables
            effects_flags: WeatherEffect flags as int (I=1, V=2, W=4)
        """
        old_weather = self.world_state.weather
        old_description = self.world_state.weather_description

        self.world_state.weather = weather
        self.world_state.weather_description = description
        self.world_state.weather_effects_flags = effects_flags

        self._log_event(
            "weather_changed",
            {
                "old_weather": old_weather.value,
                "old_description": old_description,
                "new_weather": weather.value,
                "new_description": description,
                "effects_flags": effects_flags,
            },
        )

    def roll_weather(self) -> Weather:
        """
        Roll for random weather appropriate to season and active unseason.

        Uses the Dolmenwood Campaign Book weather tables with evocative
        descriptions and mechanical effects (I/V/W).

        Returns:
            The simplified Weather enum value
        """
        # Use new Dolmenwood weather system if available
        if DOLMENWOOD_WEATHER_AVAILABLE:
            return self._roll_dolmenwood_weather()

        # Fallback to simplified tables
        return self._roll_simple_weather()

    def _roll_dolmenwood_weather(self) -> Weather:
        """Roll weather using the full Dolmenwood tables."""
        month = self.world_state.current_date.month

        # Determine active unseason
        active_unseason = Unseason(self.world_state.active_unseason)

        # Roll on the appropriate table
        result = roll_dolmenwood_weather(month, active_unseason)

        # Map description to simplified Weather enum for backward compatibility
        simple_weather = self._map_description_to_weather(result.description)

        # Store the full result
        self.set_weather(
            weather=simple_weather,
            description=result.description,
            effects_flags=result.effects.value,
        )

        self._log_event(
            "dolmenwood_weather_rolled",
            {
                "month": month,
                "unseason": active_unseason.value,
                "roll": result.roll,
                "table": result.table_used,
                "description": result.description,
                "effects": str(result.effects),
                "simple_weather": simple_weather.value,
            },
        )

        return simple_weather

    def _map_description_to_weather(self, description: str) -> Weather:
        """
        Map an evocative weather description to a simple Weather enum.

        This maintains backward compatibility with code that uses the
        simplified Weather enum.
        """
        desc_lower = description.lower()

        # Check for specific conditions
        if "blizzard" in desc_lower:
            return Weather.BLIZZARD
        elif "snow" in desc_lower:
            return Weather.SNOW
        elif "storm" in desc_lower or "thunder" in desc_lower:
            return Weather.STORM
        elif "rain" in desc_lower or "drizzle" in desc_lower or "torrential" in desc_lower:
            return Weather.RAIN
        elif "fog" in desc_lower or "mist" in desc_lower:
            return Weather.FOG
        elif "overcast" in desc_lower or "cloud" in desc_lower or "gloomy" in desc_lower:
            return Weather.OVERCAST
        elif "clear" in desc_lower or "sunny" in desc_lower or "bright" in desc_lower:
            return Weather.CLEAR
        else:
            # Default based on temperature/condition words
            if any(w in desc_lower for w in ["freeze", "frigid", "icy", "cold", "chill"]):
                return Weather.OVERCAST
            elif any(w in desc_lower for w in ["hot", "warm", "balmy", "humid"]):
                return Weather.CLEAR
            else:
                return Weather.OVERCAST

    def _roll_simple_weather(self) -> Weather:
        """Fallback: Roll weather using simplified tables."""
        season = self.world_state.season
        roll = self.dice_roller.roll_2d6("weather").total

        if season == Season.WINTER:
            weather_table = {
                2: Weather.BLIZZARD,
                3: Weather.BLIZZARD,
                4: Weather.SNOW,
                5: Weather.SNOW,
                6: Weather.OVERCAST,
                7: Weather.OVERCAST,
                8: Weather.OVERCAST,
                9: Weather.FOG,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }
        elif season == Season.SPRING:
            weather_table = {
                2: Weather.STORM,
                3: Weather.RAIN,
                4: Weather.RAIN,
                5: Weather.RAIN,
                6: Weather.OVERCAST,
                7: Weather.OVERCAST,
                8: Weather.FOG,
                9: Weather.CLEAR,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }
        elif season == Season.SUMMER:
            weather_table = {
                2: Weather.STORM,
                3: Weather.RAIN,
                4: Weather.OVERCAST,
                5: Weather.OVERCAST,
                6: Weather.CLEAR,
                7: Weather.CLEAR,
                8: Weather.CLEAR,
                9: Weather.CLEAR,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }
        else:  # Autumn
            weather_table = {
                2: Weather.STORM,
                3: Weather.RAIN,
                4: Weather.RAIN,
                5: Weather.FOG,
                6: Weather.FOG,
                7: Weather.OVERCAST,
                8: Weather.OVERCAST,
                9: Weather.OVERCAST,
                10: Weather.CLEAR,
                11: Weather.CLEAR,
                12: Weather.CLEAR,
            }

        new_weather = weather_table.get(roll, Weather.CLEAR)
        self.set_weather(new_weather)
        return new_weather

    def check_unseason_trigger(self) -> Optional[str]:
        """
        Check if an unseason should trigger on the current date.

        Should be called at the start of each day.

        Returns:
            Name of triggered unseason, or None
        """
        if not DOLMENWOOD_WEATHER_AVAILABLE:
            return None

        month = self.world_state.current_date.month
        day = self.world_state.current_date.day

        # Build current state from world state
        current_state = UnseasonState(
            active=Unseason(self.world_state.active_unseason),
            days_remaining=self.world_state.unseason_days_remaining,
        )

        # Check for trigger
        result = check_unseason_trigger(month, day, current_state)

        if result:
            unseason, duration = result
            self.world_state.active_unseason = unseason.value
            self.world_state.unseason_days_remaining = duration

            self._log_event(
                "unseason_started",
                {
                    "unseason": unseason.value,
                    "duration": duration,
                    "month": month,
                    "day": day,
                },
            )

            return unseason.value

        return None

    def advance_unseason_day(self) -> Optional[str]:
        """
        Advance the unseason tracker by one day.

        Should be called when the day advances.

        Returns:
            Name of ended unseason, or None
        """
        if self.world_state.unseason_days_remaining > 0:
            self.world_state.unseason_days_remaining -= 1

            if self.world_state.unseason_days_remaining == 0:
                ended_unseason = self.world_state.active_unseason
                self.world_state.active_unseason = "none"

                self._log_event(
                    "unseason_ended",
                    {"unseason": ended_unseason},
                )

                return ended_unseason

        return None

    def get_unseason_effects(self) -> dict[str, Any]:
        """
        Get the special effects for the currently active unseason.

        Returns dict with:
        - special_encounters: bool
        - special_encounter_chance: int (X-in-6)
        - foraging_bonus: float (multiplier)
        - description: str or None
        """
        if not DOLMENWOOD_WEATHER_AVAILABLE:
            return {
                "special_encounters": False,
                "special_encounter_chance": 0,
                "foraging_bonus": 1.0,
                "description": None,
            }

        state = UnseasonState(
            active=Unseason(self.world_state.active_unseason),
            days_remaining=self.world_state.unseason_days_remaining,
        )
        return get_active_unseason_effects(state)

    # =========================================================================
    # EFFECT MANAGEMENT
    # =========================================================================

    def get_narrative_resolver(self) -> Optional["NarrativeResolver"]:
        """Get the narrative resolver for effect tracking."""
        return self._narrative_resolver

    def tick_spell_effects(self, time_unit: str = "turns") -> list[dict[str, Any]]:
        """
        Tick all spell effects and return expired ones.

        Args:
            time_unit: "rounds" or "turns"

        Returns:
            List of expired effect info
        """
        if not self._narrative_resolver:
            return []

        expired_effects = self._narrative_resolver.tick_effects(time_unit)

        return [
            {
                "effect_id": e.effect_id,
                "spell_name": e.spell_name,
                "caster_id": e.caster_id,
                "target_id": e.target_id,
            }
            for e in expired_effects
        ]

    def tick_location_effects(self, location_id: str) -> list[dict[str, Any]]:
        """
        Tick all area effects at a location and return expired ones.

        Args:
            location_id: The location to tick effects for

        Returns:
            List of expired effect info
        """
        location = self._locations.get(location_id)
        if not location:
            return []

        expired_effects = location.tick_effects()

        return [
            {
                "effect_id": e.effect_id,
                "name": e.name,
                "effect_type": e.effect_type.value,
            }
            for e in expired_effects
        ]

    def tick_polymorph_effects(self) -> list[dict[str, Any]]:
        """
        Tick all polymorph overlays and return expired ones.

        Returns:
            List of expired polymorph info
        """
        expired = []

        for character in self._characters.values():
            if character.polymorph_overlay and character.polymorph_overlay.is_active:
                if character.polymorph_overlay.tick():
                    expired.append(
                        {
                            "character_id": character.character_id,
                            "character_name": character.name,
                            "form_name": character.polymorph_overlay.form_name,
                        }
                    )
                    character.polymorph_overlay = None

        return expired

    def add_area_effect(self, location_id: str, effect: AreaEffect) -> dict[str, Any]:
        """
        Add an area effect to a location.

        Args:
            location_id: The location to add the effect to
            effect: The area effect to add

        Returns:
            Result of adding the effect
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        location.add_area_effect(effect)

        result = {
            "effect_id": effect.effect_id,
            "name": effect.name,
            "location_id": location_id,
            "duration_turns": effect.duration_turns,
        }

        self._log_event("area_effect_added", result)
        return result

    def remove_area_effect(self, location_id: str, effect_id: str) -> dict[str, Any]:
        """
        Remove an area effect from a location.

        Args:
            location_id: The location to remove the effect from
            effect_id: The effect ID to remove

        Returns:
            Result of removing the effect
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        effect = location.remove_area_effect(effect_id)
        if not effect:
            return {"error": f"Effect {effect_id} not found"}

        result = {
            "effect_id": effect_id,
            "name": effect.name,
            "location_id": location_id,
        }

        self._log_event("area_effect_removed", result)
        return result

    def get_area_effect(self, location_id: str, effect_id: str) -> dict[str, Any]:
        """
        Get details of a specific area effect.

        Args:
            location_id: The location containing the effect
            effect_id: The effect ID to retrieve

        Returns:
            Effect details or error
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        for effect in location.area_effects:
            if effect.effect_id == effect_id:
                return {
                    "effect_id": effect.effect_id,
                    "name": effect.name,
                    "effect_type": effect.effect_type.value,
                    "is_active": effect.is_active,
                    "duration_turns": effect.duration_turns,
                    "blocks": effect.get_all_blocks(),
                    "damage_info": effect.get_damage_info(),
                    "can_be_escaped": effect.can_be_escaped,
                    "escape_method": effect.get_escape_method(),
                    "escape_dc": effect.get_escape_dc(),
                    "trapped_characters": effect.trapped_characters.copy(),
                }

        return {"error": f"Effect {effect_id} not found"}

    def process_area_entry(
        self,
        character_id: str,
        location_id: str,
        effect_id: str,
    ) -> dict[str, Any]:
        """
        Process a character entering an area effect.

        Handles trapping, entry damage, and other entry effects.

        Args:
            character_id: The character entering the effect
            location_id: The location containing the effect
            effect_id: The effect being entered

        Returns:
            Result of entry processing
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        effect = None
        for e in location.area_effects:
            if e.effect_id == effect_id:
                effect = e
                break

        if not effect:
            return {"error": f"Effect {effect_id} not found"}

        if not effect.is_active:
            return {"error": "Effect is not active"}

        result: dict[str, Any] = {
            "character_id": character_id,
            "effect_id": effect_id,
            "effect_name": effect.name,
            "trapped": False,
            "entry_damage": None,
            "effects_applied": [],
        }

        # Handle trapping (Web, Entangle, etc.)
        if effect.blocks_movement and effect.can_be_escaped:
            effect.trap_character(character_id)
            result["trapped"] = True
            result["effects_applied"].append("trapped")

        # Handle entry damage
        if effect.has_entry_damage():
            result["entry_damage"] = {
                "damage_dice": effect.entry_damage,
                "damage_type": effect.entry_damage_type,
                "save_type": effect.save_type,
                "save_avoids": effect.entry_save_avoids,
            }
            result["effects_applied"].append("entry_damage")

        self._log_event("area_effect_entry", result)
        return result

    def attempt_escape(
        self,
        character_id: str,
        location_id: str,
        effect_id: str,
        roll_result: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Attempt to escape from a trapping area effect.

        Args:
            character_id: The character attempting escape
            location_id: The location containing the effect
            effect_id: The effect to escape from
            roll_result: The result of the escape roll (if applicable)

        Returns:
            Result of escape attempt
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        effect = None
        for e in location.area_effects:
            if e.effect_id == effect_id:
                effect = e
                break

        if not effect:
            return {"error": f"Effect {effect_id} not found"}

        if not effect.is_character_trapped(character_id):
            return {"error": "Character is not trapped in this effect"}

        if not effect.can_be_escaped:
            return {"error": "This effect cannot be escaped"}

        result: dict[str, Any] = {
            "character_id": character_id,
            "effect_id": effect_id,
            "escape_method": effect.get_escape_method(),
            "escape_dc": effect.get_escape_dc(),
            "roll_result": roll_result,
            "escaped": False,
        }

        # Determine success if roll provided
        dc = effect.get_escape_dc()
        if roll_result is not None and dc is not None:
            if roll_result >= dc:
                effect.free_character(character_id)
                result["escaped"] = True

        self._log_event("escape_attempt", result)
        return result

    def get_trapped_in_effect(
        self,
        character_id: str,
        location_id: str,
    ) -> dict[str, Any]:
        """
        Check if a character is trapped in any effect at a location.

        Args:
            character_id: The character to check
            location_id: The location to check

        Returns:
            Information about trapping effects
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        trapping_effects = []
        for effect in location.area_effects:
            if effect.is_active and effect.is_character_trapped(character_id):
                trapping_effects.append({
                    "effect_id": effect.effect_id,
                    "name": effect.name,
                    "effect_type": effect.effect_type.value,
                    "escape_method": effect.get_escape_method(),
                    "escape_dc": effect.get_escape_dc(),
                })

        return {
            "character_id": character_id,
            "location_id": location_id,
            "is_trapped": len(trapping_effects) > 0,
            "trapping_effects": trapping_effects,
        }

    # =========================================================================
    # SPELL-SPECIFIC AREA EFFECT METHODS
    # =========================================================================

    def cast_web(
        self,
        location_id: str,
        caster_id: str,
        duration_turns: int = 48,  # 8 hours default per OSE
        area_radius_feet: int = 10,
    ) -> dict[str, Any]:
        """
        Cast Web spell, creating entangling webs in an area.

        Args:
            location_id: Target location
            caster_id: ID of the caster
            duration_turns: Duration in turns (default 48 = 8 hours)
            area_radius_feet: Radius of the web area

        Returns:
            Result info
        """
        effect = AreaEffect(
            effect_type=AreaEffectType.WEB,
            name="Web",
            description="Sticky magical webs fill the area, trapping creatures",
            source_spell_id="web",
            caster_id=caster_id,
            location_id=location_id,
            area_radius_feet=area_radius_feet,
            duration_turns=duration_turns,
            blocks_movement=True,
            escape_mechanism={
                "method": "strength_check",
                "dc": 0,  # Simple check, no DC in OSE
                "requires_action": True,
                "description": "Struggle free with Strength check",
            },
        )

        result = self.add_area_effect(location_id, effect)
        result["spell"] = "Web"
        result["effect_type"] = "web"
        return result

    def cast_silence(
        self,
        location_id: str,
        caster_id: str,
        duration_turns: int = 12,  # 2 hours default
        area_radius_feet: int = 15,
    ) -> dict[str, Any]:
        """
        Cast Silence spell, creating a zone where no sound can be made.

        Args:
            location_id: Target location
            caster_id: ID of the caster
            duration_turns: Duration in turns
            area_radius_feet: Radius of the silence zone

        Returns:
            Result info
        """
        effect = AreaEffect(
            effect_type=AreaEffectType.SILENCE,
            name="Silence",
            description="A zone of complete silence; no sound can be made or heard",
            source_spell_id="silence",
            caster_id=caster_id,
            location_id=location_id,
            area_radius_feet=area_radius_feet,
            duration_turns=duration_turns,
            blocks_sound=True,
            blocks_magic=True,  # Blocks verbal spellcasting
        )

        result = self.add_area_effect(location_id, effect)
        result["spell"] = "Silence"
        result["effect_type"] = "silence"
        result["blocks_verbal_spells"] = True
        return result

    def cast_darkness(
        self,
        location_id: str,
        caster_id: str,
        duration_turns: int = 6,  # 1 hour default
        area_radius_feet: int = 15,
    ) -> dict[str, Any]:
        """
        Cast Darkness spell, creating magical darkness.

        Args:
            location_id: Target location
            caster_id: ID of the caster
            duration_turns: Duration in turns
            area_radius_feet: Radius of the darkness zone

        Returns:
            Result info
        """
        effect = AreaEffect(
            effect_type=AreaEffectType.DARKNESS,
            name="Darkness",
            description="Impenetrable magical darkness; even magical light cannot penetrate",
            source_spell_id="darkness",
            caster_id=caster_id,
            location_id=location_id,
            area_radius_feet=area_radius_feet,
            duration_turns=duration_turns,
            blocks_vision=True,
        )

        result = self.add_area_effect(location_id, effect)
        result["spell"] = "Darkness"
        result["effect_type"] = "darkness"
        return result

    def cast_fog_cloud(
        self,
        location_id: str,
        caster_id: str,
        duration_turns: int = 6,
        area_radius_feet: int = 20,
    ) -> dict[str, Any]:
        """
        Cast Fog Cloud, creating an obscuring mist.

        Args:
            location_id: Target location
            caster_id: ID of the caster
            duration_turns: Duration in turns
            area_radius_feet: Radius of the fog

        Returns:
            Result info
        """
        effect = AreaEffect(
            effect_type=AreaEffectType.FOG,
            name="Fog Cloud",
            description="Thick fog obscures vision in the area",
            source_spell_id="fog_cloud",
            caster_id=caster_id,
            location_id=location_id,
            area_radius_feet=area_radius_feet,
            duration_turns=duration_turns,
            blocks_vision=True,
        )

        result = self.add_area_effect(location_id, effect)
        result["spell"] = "Fog Cloud"
        result["effect_type"] = "fog"
        return result

    def cast_stinking_cloud(
        self,
        location_id: str,
        caster_id: str,
        duration_turns: int = 1,  # Short duration
        area_radius_feet: int = 20,
    ) -> dict[str, Any]:
        """
        Cast Stinking Cloud, creating nauseating gas.

        Args:
            location_id: Target location
            caster_id: ID of the caster
            duration_turns: Duration in turns
            area_radius_feet: Radius of the cloud

        Returns:
            Result info
        """
        effect = AreaEffect(
            effect_type=AreaEffectType.STINKING_CLOUD,
            name="Stinking Cloud",
            description="Nauseating gas fills the area; creatures must save or be incapacitated",
            source_spell_id="stinking_cloud",
            caster_id=caster_id,
            location_id=location_id,
            area_radius_feet=area_radius_feet,
            duration_turns=duration_turns,
            blocks_vision=True,
            save_type="spell",
            save_negates=True,
            enter_effect="Must save vs Poison or be helpless with nausea",
        )

        result = self.add_area_effect(location_id, effect)
        result["spell"] = "Stinking Cloud"
        result["effect_type"] = "stinking_cloud"
        result["save_required"] = "poison"
        return result

    def cast_entangle(
        self,
        location_id: str,
        caster_id: str,
        duration_turns: int = 6,
        area_radius_feet: int = 20,
    ) -> dict[str, Any]:
        """
        Cast Entangle, causing plants to grasp creatures.

        Args:
            location_id: Target location
            caster_id: ID of the caster
            duration_turns: Duration in turns
            area_radius_feet: Radius of the entangle area

        Returns:
            Result info
        """
        effect = AreaEffect(
            effect_type=AreaEffectType.ENTANGLE,
            name="Entangle",
            description="Plants wrap around creatures, restraining them",
            source_spell_id="entangle",
            caster_id=caster_id,
            location_id=location_id,
            area_radius_feet=area_radius_feet,
            duration_turns=duration_turns,
            blocks_movement=True,
            save_type="spell",
            save_negates=True,
            escape_mechanism={
                "method": "strength_check",
                "dc": 0,
                "requires_action": True,
                "description": "Break free from vines",
            },
        )

        result = self.add_area_effect(location_id, effect)
        result["spell"] = "Entangle"
        result["effect_type"] = "entangle"
        return result

    # =========================================================================
    # BUFF ENHANCEMENT SPELL METHODS
    # =========================================================================

    def grant_immunity(
        self,
        character_id: str,
        immunity_type: str,
        duration_turns: int,
        source: str = "Spell",
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Grant immunity to a damage type or effect.

        Args:
            character_id: Target character
            immunity_type: Type of immunity ("missiles", "drowning", "gas", "fire", etc.)
            duration_turns: Duration in turns
            source: Source name (spell name)
            caster_id: Caster ID for tracking

        Returns:
            Result info
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        # Apply as a special buff
        self.apply_buff(
            character_id=character_id,
            stat=f"immunity_{immunity_type}",
            value=1,  # 1 = has immunity
            source=source,
            source_id=caster_id,
            duration_turns=duration_turns,
        )

        return {
            "success": True,
            "character_id": character_id,
            "immunity_type": immunity_type,
            "duration_turns": duration_turns,
            "source": source,
        }

    def grant_vision_enhancement(
        self,
        character_id: str,
        vision_type: str,
        duration_turns: int,
        range_feet: int = 60,
        source: str = "Spell",
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Grant enhanced vision (darkvision, see invisible, etc.).

        Args:
            character_id: Target character
            vision_type: Type of vision ("darkvision", "infravision", "see_invisible", "truesight")
            duration_turns: Duration in turns
            range_feet: Range of the vision in feet
            source: Source name
            caster_id: Caster ID for tracking

        Returns:
            Result info
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        # Special handling for see_invisible
        if vision_type == "see_invisible":
            character.can_see_invisible = True
            character.see_invisible_source = source

        # Apply as a buff for tracking
        self.apply_buff(
            character_id=character_id,
            stat=f"vision_{vision_type}",
            value=range_feet,
            source=source,
            source_id=caster_id,
            duration_turns=duration_turns,
        )

        return {
            "success": True,
            "character_id": character_id,
            "vision_type": vision_type,
            "range_feet": range_feet,
            "duration_turns": duration_turns,
            "source": source,
        }

    def apply_stat_override(
        self,
        character_id: str,
        stat: str,
        value: int,
        duration_turns: int,
        source: str = "Spell",
        caster_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Override a stat to a fixed value (Feeblemind, etc.).

        Args:
            character_id: Target character
            stat: Stat to override (STR, INT, WIS, etc.)
            value: Value to set the stat to
            duration_turns: Duration in turns
            source: Source name
            caster_id: Caster ID

        Returns:
            Result info
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        original_value = character.ability_scores.get(stat, 10)

        # Apply as an override buff
        self.apply_buff(
            character_id=character_id,
            stat=stat,
            value=value,
            source=source,
            source_id=caster_id,
            duration_turns=duration_turns,
            is_override=True,
        )

        return {
            "success": True,
            "character_id": character_id,
            "stat": stat,
            "original_value": original_value,
            "new_value": value,
            "duration_turns": duration_turns,
            "source": source,
        }

    def dispel_magic(
        self,
        target_id: str,
        caster_level: int,
        target_type: str = "character",
    ) -> dict[str, Any]:
        """
        Dispel magical effects on a target.

        Per OSE rules, there's a chance to dispel based on caster level comparison.

        Args:
            target_id: Target character or location ID
            caster_level: Level of the dispelling caster
            target_type: "character" or "location"

        Returns:
            Result with list of dispelled effects
        """
        from src.data_models import DiceRoller

        dispelled = []
        failed = []

        if target_type == "character":
            character = self.get_character(target_id)
            if not character:
                return {"success": False, "error": f"Character {target_id} not found"}

            # Remove magical conditions
            for condition in list(character.conditions):
                if condition.source_spell_id:
                    # Calculate dispel chance based on relative caster levels
                    # Base 50% + 5% per level difference
                    spell_level = condition.severity if condition.severity else caster_level
                    base_chance = 50 + (caster_level - spell_level) * 5
                    base_chance = max(5, min(95, base_chance))  # Clamp 5-95%

                    dice = DiceRoller()
                    roll = dice.roll("1d100", "Dispel check")

                    if roll.total <= base_chance:
                        character.conditions.remove(condition)
                        dispelled.append({
                            "type": "condition",
                            "name": condition.condition_type.value,
                            "source": condition.source_spell_id,
                        })
                    else:
                        failed.append({
                            "type": "condition",
                            "name": condition.condition_type.value,
                            "roll": roll.total,
                            "needed": base_chance,
                        })

            # Remove stat modifiers from spells
            for modifier in list(character.stat_modifiers):
                if modifier.source and "spell" in modifier.source.lower():
                    character.stat_modifiers.remove(modifier)
                    dispelled.append({
                        "type": "buff",
                        "stat": modifier.stat,
                        "source": modifier.source,
                    })

            # Reset special states
            if character.mirror_image_count > 0:
                dispelled.append({"type": "mirror_images", "count": character.mirror_image_count})
                character.mirror_image_count = 0

            if character.can_see_invisible and character.see_invisible_source:
                dispelled.append({"type": "see_invisible", "source": character.see_invisible_source})
                character.can_see_invisible = False
                character.see_invisible_source = None

        elif target_type == "location":
            location = self._locations.get(target_id)
            if not location:
                return {"success": False, "error": f"Location {target_id} not found"}

            # Remove area effects
            for effect in list(location.area_effects):
                if effect.source_spell_id:
                    location.area_effects.remove(effect)
                    dispelled.append({
                        "type": "area_effect",
                        "name": effect.name,
                        "effect_type": effect.effect_type.value,
                    })

        return {
            "success": True,
            "target_id": target_id,
            "target_type": target_type,
            "caster_level": caster_level,
            "dispelled": dispelled,
            "failed": failed,
            "total_dispelled": len(dispelled),
        }

    def remove_condition(
        self,
        character_id: str,
        condition_type: str,
    ) -> dict[str, Any]:
        """
        Remove a specific condition from a character.

        Used by Remove Curse, Remove Poison, Cure Affliction, etc.

        Args:
            character_id: Target character
            condition_type: Type of condition to remove ("cursed", "poisoned", "diseased")

        Returns:
            Result info
        """
        character = self.get_character(character_id)
        if not character:
            return {"success": False, "error": f"Character {character_id} not found"}

        removed = []
        for condition in list(character.conditions):
            if condition.condition_type.value == condition_type:
                character.conditions.remove(condition)
                removed.append({
                    "condition_type": condition.condition_type.value,
                    "source": condition.source,
                })

        return {
            "success": True,
            "character_id": character_id,
            "condition_type": condition_type,
            "removed_count": len(removed),
            "removed": removed,
        }

    def apply_polymorph(self, character_id: str, overlay: PolymorphOverlay) -> dict[str, Any]:
        """
        Apply a polymorph transformation to a character.

        Args:
            character_id: The character to transform
            overlay: The polymorph overlay to apply

        Returns:
            Result of applying the transformation
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Remove existing polymorph if any
        old_form = None
        if character.polymorph_overlay:
            old_form = character.polymorph_overlay.form_name

        character.apply_polymorph(overlay)

        result = {
            "character_id": character_id,
            "character_name": character.name,
            "new_form": overlay.form_name,
            "previous_form": old_form,
            "duration_turns": overlay.duration_turns,
        }

        self._log_event("polymorph_applied", result)
        return result

    def remove_polymorph(self, character_id: str) -> dict[str, Any]:
        """
        Remove a polymorph transformation from a character.

        Args:
            character_id: The character to restore

        Returns:
            Result of removing the transformation
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        overlay = character.remove_polymorph()
        if not overlay:
            return {"error": f"Character {character_id} is not polymorphed"}

        result = {
            "character_id": character_id,
            "character_name": character.name,
            "restored_from": overlay.form_name,
        }

        self._log_event("polymorph_removed", result)
        return result

    def get_active_effects_on_character(self, character_id: str) -> dict[str, Any]:
        """
        Get all active effects on a character.

        Args:
            character_id: The character to check

        Returns:
            Dictionary with all active effects
        """
        result = {
            "character_id": character_id,
            "spell_effects": [],
            "polymorph": None,
            "conditions": [],
        }

        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        # Spell effects from narrative resolver
        if self._narrative_resolver:
            spell_effects = self._narrative_resolver.get_active_effects(character_id)
            result["spell_effects"] = [
                {
                    "effect_id": e.effect_id,
                    "spell_name": e.spell_name,
                    "duration_remaining": e.duration_remaining,
                    "requires_concentration": e.requires_concentration,
                }
                for e in spell_effects
            ]

        # Polymorph overlay
        if character.polymorph_overlay and character.polymorph_overlay.is_active:
            result["polymorph"] = {
                "form_name": character.polymorph_overlay.form_name,
                "duration_remaining": character.polymorph_overlay.duration_turns,
            }

        # Conditions
        result["conditions"] = [
            {
                "type": c.condition_type.value,
                "duration": c.duration_turns,
                "source": c.source,
            }
            for c in character.conditions
        ]

        return result

    def get_location_effects(self, location_id: str) -> dict[str, Any]:
        """
        Get all area effects at a location.

        Args:
            location_id: The location to check

        Returns:
            Dictionary with all active area effects
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        return {
            "location_id": location_id,
            "effects": [
                {
                    "effect_id": e.effect_id,
                    "name": e.name,
                    "effect_type": e.effect_type.value,
                    "duration_remaining": e.duration_turns,
                    "blocks_movement": e.blocks_movement,
                    "blocks_vision": e.blocks_vision,
                    "blocks_sound": e.blocks_sound,
                }
                for e in location.get_active_effects()
            ],
            "has_blocking_movement": location.has_blocking_effect("movement"),
            "has_blocking_vision": location.has_blocking_effect("vision"),
            "has_blocking_sound": location.has_blocking_effect("sound"),
        }

    # =========================================================================
    # SUMMON/CONTROL METHODS
    # =========================================================================

    def summon_creatures(
        self,
        caster_id: str,
        location_id: str,
        creature_type: str,
        count: int,
        hd_max: Optional[int] = None,
        duration_turns: int = 6,
        caster_controls: bool = True,
    ) -> dict[str, Any]:
        """
        Summon creatures at a location under caster's control.

        Args:
            caster_id: The summoner
            location_id: Where to summon
            creature_type: Type of creature (undead, animal, elemental, etc.)
            count: Number of creatures to summon
            hd_max: Maximum HD of creatures
            duration_turns: How long the summon lasts
            caster_controls: Whether caster controls the creatures

        Returns:
            Result of the summoning
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        caster = self._characters.get(caster_id)
        if not caster:
            return {"error": f"Caster {caster_id} not found"}

        # Create summoned creatures (placeholder IDs)
        summoned_ids = []
        for i in range(count):
            creature_id = f"summoned_{creature_type}_{caster_id}_{i}"
            summoned_ids.append(creature_id)

        result = {
            "success": True,
            "spell": "Summon Creatures",
            "caster_id": caster_id,
            "location_id": location_id,
            "creature_type": creature_type,
            "count": count,
            "hd_max": hd_max,
            "duration_turns": duration_turns,
            "caster_controls": caster_controls,
            "summoned_creature_ids": summoned_ids,
        }

        self._log_event("creatures_summoned", result)
        return result

    def animate_dead(
        self,
        caster_id: str,
        location_id: str,
        corpse_count: int,
        hd_per_level: int = 1,
    ) -> dict[str, Any]:
        """
        Animate dead corpses as undead.

        Args:
            caster_id: The necromancer
            location_id: Where the corpses are
            corpse_count: Number of corpses to animate
            hd_per_level: HD of undead per caster level

        Returns:
            Result of the animation
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        caster = self._characters.get(caster_id)
        if not caster:
            return {"error": f"Caster {caster_id} not found"}

        # Calculate total HD that can be animated based on caster level
        max_hd = caster.level * hd_per_level

        # Create undead (placeholder IDs)
        undead_ids = []
        for i in range(corpse_count):
            undead_id = f"undead_{caster_id}_{i}"
            undead_ids.append(undead_id)

        result = {
            "success": True,
            "spell": "Animate Dead",
            "caster_id": caster_id,
            "location_id": location_id,
            "corpses_animated": corpse_count,
            "max_hd_controlled": max_hd,
            "undead_ids": undead_ids,
            "caster_controls": True,
            "permanent": True,
        }

        self._log_event("animate_dead", result)
        return result

    def dismiss_summoned(
        self,
        caster_id: str,
        creature_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Dismiss summoned creatures.

        Args:
            caster_id: The summoner
            creature_ids: Specific creatures to dismiss (None = all)

        Returns:
            Result of the dismissal
        """
        dismissed = creature_ids or []

        result = {
            "success": True,
            "caster_id": caster_id,
            "dismissed_count": len(dismissed),
            "dismissed_ids": dismissed,
        }

        self._log_event("creatures_dismissed", result)
        return result

    # =========================================================================
    # CURSE METHODS
    # =========================================================================

    def apply_curse(
        self,
        caster_id: str,
        target_id: str,
        curse_type: str = "major",
        stat_affected: Optional[str] = None,
        modifier: Optional[int] = None,
        is_permanent: bool = True,
    ) -> dict[str, Any]:
        """
        Apply a curse to a target.

        Args:
            caster_id: The caster
            target_id: The target of the curse
            curse_type: Type of curse (minor, major, ability_drain, wasting)
            stat_affected: Which stat is affected (if any)
            modifier: Modifier to apply to the stat
            is_permanent: Whether the curse is permanent

        Returns:
            Result of applying the curse
        """
        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        # Add cursed condition
        curse_condition = Condition(
            condition_type=ConditionType.CURSED,
            source=f"Curse ({curse_type})",
            duration_turns=None if is_permanent else 6,
            caster_id=caster_id,
        )
        target.conditions.append(curse_condition)

        # Apply stat modifier if specified
        if stat_affected and modifier:
            from src.data_models import StatModifier
            import uuid
            curse_modifier = StatModifier(
                modifier_id=f"curse_{uuid.uuid4().hex[:8]}",
                stat=stat_affected,
                value=modifier,
                source=f"Curse ({curse_type})",
                source_id=caster_id,
                duration_turns=None if is_permanent else 6,
            )
            target.add_stat_modifier(curse_modifier)

        result = {
            "success": True,
            "spell": "Curse",
            "caster_id": caster_id,
            "target_id": target_id,
            "target_name": target.name,
            "curse_type": curse_type,
            "stat_affected": stat_affected,
            "modifier": modifier,
            "is_permanent": is_permanent,
            "requires_remove_curse": is_permanent,
        }

        self._log_event("curse_applied", result)
        return result

    def remove_curse_from_target(
        self,
        caster_id: str,
        target_id: str,
    ) -> dict[str, Any]:
        """
        Remove a curse from a target.

        Args:
            caster_id: The caster attempting removal
            target_id: The cursed target

        Returns:
            Result of the removal attempt
        """
        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        # Find and remove cursed conditions
        removed_curses = []
        remaining_conditions = []
        for condition in target.conditions:
            if condition.condition_type == ConditionType.CURSED:
                removed_curses.append({
                    "source": condition.source,
                    "caster_id": condition.caster_id,
                })
            else:
                remaining_conditions.append(condition)

        target.conditions = remaining_conditions

        # Clear any curse-related stat modifiers
        # (In a full implementation, we'd track which modifiers came from curses)

        result = {
            "success": len(removed_curses) > 0,
            "spell": "Remove Curse",
            "caster_id": caster_id,
            "target_id": target_id,
            "target_name": target.name,
            "curses_removed": len(removed_curses),
            "removed_details": removed_curses,
        }

        self._log_event("curse_removed", result)
        return result

    def bestow_curse(
        self,
        caster_id: str,
        target_id: str,
        effect_choice: str = "stat_penalty",
        stat: str = "STR",
    ) -> dict[str, Any]:
        """
        Bestow a curse with specific effect choice.

        Args:
            caster_id: The caster
            target_id: The target
            effect_choice: Type of curse effect
            stat: Which stat for stat_penalty

        Returns:
            Result of the curse
        """
        # Map effect_choice to specific curse parameters
        if effect_choice == "stat_penalty":
            return self.apply_curse(
                caster_id=caster_id,
                target_id=target_id,
                curse_type="ability_drain",
                stat_affected=stat,
                modifier=-4,
                is_permanent=True,
            )
        elif effect_choice == "attack_penalty":
            return self.apply_curse(
                caster_id=caster_id,
                target_id=target_id,
                curse_type="minor",
                stat_affected="attack",
                modifier=-4,
                is_permanent=True,
            )
        elif effect_choice == "action_loss":
            return self.apply_curse(
                caster_id=caster_id,
                target_id=target_id,
                curse_type="major",
                is_permanent=True,
            )
        else:
            return self.apply_curse(
                caster_id=caster_id,
                target_id=target_id,
                curse_type="major",
                is_permanent=True,
            )

    # =========================================================================
    # MISCELLANEOUS SPELL METHODS
    # =========================================================================

    def teleport_character(
        self,
        caster_id: str,
        target_id: str,
        destination_location_id: str,
        teleport_type: str = "long",
        passengers: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Teleport a character to a destination.

        Args:
            caster_id: The caster
            target_id: The primary target (usually caster)
            destination_location_id: Where to teleport to
            teleport_type: Type of teleport (short, long, planar)
            passengers: List of character IDs traveling with

        Returns:
            Result of teleportation
        """
        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        destination = self._locations.get(destination_location_id)
        if not destination:
            return {"error": f"Destination {destination_location_id} not found"}

        # Move the primary target
        teleported = [target_id]

        # Move any passengers
        if passengers:
            for passenger_id in passengers:
                if passenger_id in self._characters:
                    teleported.append(passenger_id)

        result = {
            "success": True,
            "spell": "Teleport",
            "caster_id": caster_id,
            "teleport_type": teleport_type,
            "destination": destination_location_id,
            "destination_name": destination.name,
            "teleported": teleported,
            "total_teleported": len(teleported),
        }

        self._log_event("teleport", result)
        return result

    def cast_detect_magic(
        self,
        caster_id: str,
        location_id: str,
        duration_turns: int = 2,
    ) -> dict[str, Any]:
        """
        Cast Detect Magic to sense magical auras.

        Args:
            caster_id: The caster
            location_id: Location to scan
            duration_turns: How long detection lasts

        Returns:
            Detection results
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        # Find magical items/effects in location
        magical_items = []
        for effect in location.get_active_effects():
            magical_items.append({
                "name": effect.name,
                "type": effect.effect_type.value,
            })

        result = {
            "success": True,
            "spell": "Detect Magic",
            "caster_id": caster_id,
            "location_id": location_id,
            "duration_turns": duration_turns,
            "magical_auras_detected": len(magical_items),
            "detected_items": magical_items,
        }

        self._log_event("detect_magic", result)
        return result

    def grant_flight(
        self,
        caster_id: str,
        target_id: str,
        duration_turns: int = 6,
        speed: int = 120,
    ) -> dict[str, Any]:
        """
        Grant flight to a character.

        Args:
            caster_id: The caster
            target_id: The target to grant flight
            duration_turns: Duration of flight
            speed: Flight speed in feet

        Returns:
            Result of granting flight
        """
        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        from src.data_models import StatModifier
        import uuid

        # Grant flight via a movement modifier
        flight_modifier = StatModifier(
            modifier_id=f"fly_{uuid.uuid4().hex[:8]}",
            stat="movement_fly",
            value=speed,
            source="Fly spell",
            source_id=caster_id,
            duration_turns=duration_turns,
        )
        target.add_stat_modifier(flight_modifier)

        result = {
            "success": True,
            "spell": "Fly",
            "caster_id": caster_id,
            "target_id": target_id,
            "target_name": target.name,
            "speed": speed,
            "duration_turns": duration_turns,
        }

        self._log_event("flight_granted", result)
        return result

    def grant_invisibility(
        self,
        caster_id: str,
        target_id: str,
        duration_turns: int = 24,
        invisibility_type: str = "normal",
    ) -> dict[str, Any]:
        """
        Grant invisibility to a character.

        Args:
            caster_id: The caster
            target_id: The target
            duration_turns: Duration
            invisibility_type: Type (normal, improved, greater)

        Returns:
            Result of granting invisibility
        """
        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        # Add invisible condition
        invisible_condition = Condition(
            condition_type=ConditionType.INVISIBLE,
            source=f"Invisibility ({invisibility_type})",
            duration_turns=duration_turns,
            caster_id=caster_id,
        )
        target.conditions.append(invisible_condition)

        result = {
            "success": True,
            "spell": "Invisibility",
            "caster_id": caster_id,
            "target_id": target_id,
            "target_name": target.name,
            "invisibility_type": invisibility_type,
            "duration_turns": duration_turns,
        }

        self._log_event("invisibility_granted", result)
        return result

    def cast_protection_from_evil(
        self,
        caster_id: str,
        target_id: str,
        duration_turns: int = 6,
    ) -> dict[str, Any]:
        """
        Cast Protection from Evil on a target.

        Args:
            caster_id: The caster
            target_id: The target to protect
            duration_turns: Duration

        Returns:
            Result of protection
        """
        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        from src.data_models import StatModifier
        import uuid

        # Add AC bonus vs evil creatures
        protection_modifier = StatModifier(
            modifier_id=f"prot_evil_{uuid.uuid4().hex[:8]}",
            stat="AC",
            value=1,
            source="Protection from Evil",
            source_id=caster_id,
            duration_turns=duration_turns,
            condition="vs_evil",
        )
        target.add_stat_modifier(protection_modifier)

        # Add save bonus vs evil
        save_modifier = StatModifier(
            modifier_id=f"prot_evil_save_{uuid.uuid4().hex[:8]}",
            stat="saves",
            value=1,
            source="Protection from Evil",
            source_id=caster_id,
            duration_turns=duration_turns,
            condition="vs_evil",
        )
        target.add_stat_modifier(save_modifier)

        result = {
            "success": True,
            "spell": "Protection from Evil",
            "caster_id": caster_id,
            "target_id": target_id,
            "target_name": target.name,
            "ac_bonus": 1,
            "save_bonus": 1,
            "duration_turns": duration_turns,
        }

        self._log_event("protection_from_evil", result)
        return result

    # =========================================================================
    # BARRIER/WALL SPELL METHODS
    # =========================================================================

    def create_barrier(
        self,
        caster_id: str,
        location_id: str,
        barrier_type: str,
        duration_turns: int = 12,
        length_feet: int = 20,
        height_feet: int = 10,
        contact_damage: Optional[str] = None,
        damage_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a magical barrier/wall at a location.

        Args:
            caster_id: The caster
            location_id: Where to create the barrier
            barrier_type: Type of barrier (fire, ice, stone, force)
            duration_turns: How long the barrier lasts
            length_feet: Length of the barrier
            height_feet: Height of the barrier
            contact_damage: Damage dice on contact
            damage_type: Type of damage

        Returns:
            Result of barrier creation
        """
        from src.data_models import BarrierEffect, BarrierType

        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        # Map string to enum
        barrier_type_enum = BarrierType.FORCE
        try:
            barrier_type_enum = BarrierType(barrier_type.lower())
        except ValueError:
            pass

        barrier = BarrierEffect(
            barrier_type=barrier_type_enum,
            name=f"Wall of {barrier_type.title()}",
            caster_id=caster_id,
            spell_name=f"Wall of {barrier_type.title()}",
            location_id=location_id,
            length_feet=length_feet,
            height_feet=height_feet,
            duration_turns=duration_turns,
            contact_damage=contact_damage,
            damage_type=damage_type,
            blocks_movement=True,
            blocks_vision=barrier_type in ("stone", "ice", "iron"),
        )

        # Store barrier in location (if location supports it)
        if hasattr(location, 'barriers'):
            location.barriers.append(barrier)

        result = {
            "success": True,
            "spell": f"Wall of {barrier_type.title()}",
            "caster_id": caster_id,
            "location_id": location_id,
            "barrier_id": barrier.barrier_id,
            "barrier_type": barrier_type,
            "dimensions": f"{length_feet}' x {height_feet}'",
            "duration_turns": duration_turns,
            "contact_damage": contact_damage,
            "blocks_movement": barrier.blocks_movement,
            "blocks_vision": barrier.blocks_vision,
        }

        self._log_event("barrier_created", result)
        return result

    def destroy_barrier(
        self,
        barrier_id: str,
        location_id: str,
    ) -> dict[str, Any]:
        """
        Destroy or dispel a barrier.

        Args:
            barrier_id: The barrier to destroy
            location_id: Location containing the barrier

        Returns:
            Result of barrier destruction
        """
        location = self._locations.get(location_id)
        if not location:
            return {"error": f"Location {location_id} not found"}

        # Remove barrier if location supports it
        if hasattr(location, 'barriers'):
            for barrier in location.barriers:
                if barrier.barrier_id == barrier_id:
                    barrier.is_active = False
                    location.barriers.remove(barrier)
                    return {
                        "success": True,
                        "barrier_id": barrier_id,
                        "destroyed": True,
                    }

        return {"success": False, "error": "Barrier not found"}

    # =========================================================================
    # GEAS/COMPULSION METHODS
    # =========================================================================

    def apply_geas(
        self,
        caster_id: str,
        target_id: str,
        goal: str,
        forbidden_actions: Optional[list[str]] = None,
        duration_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Apply a Geas or Holy Quest to a target.

        Args:
            caster_id: The caster
            target_id: The target of the geas
            goal: What the target must accomplish
            forbidden_actions: Actions that violate the geas
            duration_days: Duration in days (None = until completed)

        Returns:
            Result of applying the geas
        """
        from src.data_models import CompulsionState

        target = self._characters.get(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        compulsion = CompulsionState(
            target_id=target_id,
            caster_id=caster_id,
            spell_name="Geas",
            goal=goal,
            forbidden_actions=forbidden_actions or [],
            duration_days=duration_days,
        )

        target.add_compulsion(compulsion)

        result = {
            "success": True,
            "spell": "Geas",
            "caster_id": caster_id,
            "target_id": target_id,
            "target_name": target.name,
            "compulsion_id": compulsion.compulsion_id,
            "goal": goal,
            "forbidden_actions": forbidden_actions or [],
            "duration_days": duration_days,
        }

        self._log_event("geas_applied", result)
        return result

    def check_geas_violation(
        self,
        character_id: str,
        action: str,
    ) -> dict[str, Any]:
        """
        Check if an action violates any active geas.

        Args:
            character_id: The character taking the action
            action: Description of the action

        Returns:
            Violation results
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        violations = character.check_compulsion_violation(action)

        result = {
            "character_id": character_id,
            "action": action,
            "violations": violations,
            "violated": len(violations) > 0,
            "penalty": character.get_compulsion_penalty(),
        }

        if violations:
            self._log_event("geas_violation", result)

        return result

    def complete_geas(
        self,
        character_id: str,
        compulsion_id: str,
    ) -> dict[str, Any]:
        """
        Mark a geas as completed.

        Args:
            character_id: The character who completed the geas
            compulsion_id: The specific geas to complete

        Returns:
            Completion result
        """
        character = self._characters.get(character_id)
        if not character:
            return {"error": f"Character {character_id} not found"}

        for compulsion in character.compulsions:
            if compulsion.compulsion_id == compulsion_id:
                result = compulsion.complete()
                result["character_id"] = character_id
                result["compulsion_id"] = compulsion_id
                self._log_event("geas_completed", result)
                return result

        return {"error": f"Compulsion {compulsion_id} not found"}

    # =========================================================================
    # TELEPORTATION METHODS (with mishap system)
    # =========================================================================

    def teleport_with_familiarity(
        self,
        caster_id: str,
        target_ids: list[str],
        destination_id: str,
        familiarity: str = "visited",
    ) -> dict[str, Any]:
        """
        Teleport characters with familiarity-based accuracy.

        Args:
            caster_id: The caster
            target_ids: Characters to teleport
            destination_id: Destination location
            familiarity: Familiarity level with destination

        Returns:
            Teleportation result including mishap check
        """
        from src.data_models import LocationFamiliarity, DiceRoller

        destination = self._locations.get(destination_id)
        if not destination:
            return {"error": f"Destination {destination_id} not found"}

        # Get familiarity enum
        try:
            fam_level = LocationFamiliarity(familiarity)
        except ValueError:
            fam_level = LocationFamiliarity.VISITED

        # Roll for success/mishap
        roll_result = DiceRoller.roll("1d100")
        roll = roll_result.total
        success_threshold = fam_level.success_chance
        mishap_threshold = 100 - fam_level.mishap_chance

        teleported = []
        mishap = False
        mishap_type = None

        if roll <= success_threshold:
            # Success - teleport all targets
            for target_id in target_ids:
                if target_id in self._characters:
                    teleported.append(target_id)
        elif roll >= mishap_threshold:
            # Mishap!
            mishap = True
            mishap_roll = DiceRoller.roll("1d6").total
            if mishap_roll <= 2:
                mishap_type = "scattered"  # Targets arrive in different locations
            elif mishap_roll <= 4:
                mishap_type = "off_target"  # Arrive at wrong location
            else:
                mishap_type = "damage"  # Take 1d10 damage per teleporter level
        else:
            # Off target - arrive nearby
            mishap_type = "off_target"
            for target_id in target_ids:
                if target_id in self._characters:
                    teleported.append(target_id)

        result = {
            "success": not mishap,
            "spell": "Teleport",
            "caster_id": caster_id,
            "destination_id": destination_id,
            "familiarity": familiarity,
            "roll": roll,
            "success_threshold": success_threshold,
            "teleported": teleported,
            "mishap": mishap,
            "mishap_type": mishap_type,
        }

        self._log_event("teleport_attempt", result)
        return result

    # =========================================================================
    # ORACLE SPELL ADJUDICATION (Phase 4)
    # =========================================================================

    def get_spell_adjudicator(self) -> MythicSpellAdjudicator:
        """
        Get or create the spell adjudicator for oracle-based resolution.

        Returns:
            MythicSpellAdjudicator instance
        """
        if self._spell_adjudicator is None:
            self._spell_adjudicator = MythicSpellAdjudicator()
        return self._spell_adjudicator

    def adjudicate_oracle_spell(
        self,
        spell_name: str,
        caster_id: str,
        adjudication_type: str,
        oracle_question: Optional[str] = None,
        target_id: Optional[str] = None,
        intention: Optional[str] = None,
        **kwargs: Any,
    ) -> AdjudicationResult:
        """
        Adjudicate a spell that requires oracle resolution.

        This is the main entry point for Phase 4 oracle-based spell resolution.
        It routes to the appropriate MythicSpellAdjudicator method based on
        the adjudication type identified during spell parsing.

        Args:
            spell_name: Name of the spell being cast
            caster_id: ID of the caster
            adjudication_type: Type of adjudication (from SpellAdjudicationType)
            oracle_question: Optional specific question for the oracle
            target_id: Optional target character/entity
            intention: What the caster is trying to achieve
            **kwargs: Additional context for specific adjudication types

        Returns:
            AdjudicationResult with success level and interpretation context
        """
        caster = self._characters.get(caster_id)
        if not caster:
            caster = self._npcs.get(caster_id)

        caster_name = caster.name if caster else "Unknown Caster"
        caster_level = caster.level if caster else 1

        # Build target description
        target_description = ""
        if target_id:
            target = self._characters.get(target_id) or self._npcs.get(target_id)
            if target:
                target_description = target.name

        # Create adjudication context
        context = AdjudicationContext(
            spell_name=spell_name,
            caster_name=caster_name,
            caster_level=caster_level,
            target_description=target_description,
            intention=intention or oracle_question or f"Cast {spell_name}",
            target_power_level=kwargs.get("target_power_level", "normal"),
            magical_resistance=kwargs.get("magical_resistance", False),
            curse_source=kwargs.get("curse_source", ""),
            previous_attempts=kwargs.get("previous_attempts", 0),
        )

        adjudicator = self.get_spell_adjudicator()

        # Route to appropriate adjudicator method
        try:
            adj_type = SpellAdjudicationType(adjudication_type)
        except ValueError:
            adj_type = SpellAdjudicationType.GENERIC

        if adj_type == SpellAdjudicationType.WISH:
            wish_text = kwargs.get("wish_text", intention or oracle_question or "")
            wish_power = kwargs.get("wish_power", "standard")
            result = adjudicator.adjudicate_wish(wish_text, context, wish_power)

        elif adj_type == SpellAdjudicationType.DIVINATION:
            question = oracle_question or intention or f"What does {spell_name} reveal?"
            divination_type = kwargs.get("divination_type", "general")
            protected = kwargs.get("target_is_protected", False)
            result = adjudicator.adjudicate_divination(
                question, context, divination_type, protected
            )

        elif adj_type == SpellAdjudicationType.ILLUSION_BELIEF:
            quality = kwargs.get("illusion_quality", "standard")
            intelligence = kwargs.get("viewer_intelligence", "average")
            has_doubt = kwargs.get("viewer_has_reason_to_doubt", False)
            result = adjudicator.adjudicate_illusion_belief(
                context, quality, intelligence, has_doubt
            )

        elif adj_type == SpellAdjudicationType.SUMMONING_CONTROL:
            creature_type = kwargs.get("creature_type", "creature")
            creature_power = kwargs.get("creature_power", "normal")
            binding = kwargs.get("binding_strength", "standard")
            result = adjudicator.adjudicate_summoning_control(
                context, creature_type, creature_power, binding
            )

        elif adj_type == SpellAdjudicationType.CURSE_BREAK:
            curse_power = kwargs.get("curse_power", "normal")
            specifically_counters = kwargs.get("spell_specifically_counters", True)
            result = adjudicator.adjudicate_curse_break(
                context, curse_power, specifically_counters
            )

        else:
            # Generic adjudication
            from src.oracle.mythic_gme import Likelihood
            question = oracle_question or f"Does {spell_name} succeed as intended?"
            base_likelihood = Likelihood.FIFTY_FIFTY
            result = adjudicator.adjudicate_generic(question, context, base_likelihood)

        # Log the adjudication
        self._log_event(
            "oracle_spell_adjudication",
            {
                "spell": spell_name,
                "caster_id": caster_id,
                "adjudication_type": adj_type.value,
                "success_level": result.success_level.value,
                "summary": result.summary,
                "has_complication": result.has_complication,
            },
        )

        return result

    def resolve_oracle_spell_effects(
        self,
        result: AdjudicationResult,
        caster_id: str,
        target_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Apply effects from an oracle spell adjudication.

        Takes the AdjudicationResult and applies any predetermined effects
        while returning context for LLM interpretation of narrative results.

        Args:
            result: The adjudication result from adjudicate_oracle_spell
            caster_id: ID of the caster
            target_id: Optional target ID

        Returns:
            Dictionary with applied effects and LLM interpretation context
        """
        applied_effects = []

        # Apply predetermined effects (like curse removal on success)
        for effect_cmd in result.predetermined_effects:
            parts = effect_cmd.split(":")
            if parts[0] == "remove_condition" and len(parts) >= 2:
                condition_name = parts[1]
                effect_target = parts[2] if len(parts) > 2 else target_id

                # Find and remove the condition
                if effect_target:
                    target = self._characters.get(effect_target) or self._npcs.get(effect_target)
                    if target:
                        try:
                            cond_type = ConditionType(condition_name)
                            target.conditions = [
                                c for c in target.conditions
                                if c.condition_type != cond_type
                            ]
                            applied_effects.append({
                                "type": "condition_removed",
                                "condition": condition_name,
                                "target": effect_target,
                            })
                        except ValueError:
                            pass

        return {
            "success_level": result.success_level.value,
            "summary": result.summary,
            "applied_effects": applied_effects,
            "requires_interpretation": result.requires_interpretation(),
            "llm_context": result.to_llm_context() if result.requires_interpretation() else {},
            "has_complication": result.has_complication,
        }

    # =========================================================================
    # INTERNAL CALLBACKS
    # =========================================================================

    def _on_state_transition(
        self, old_state: GameState, new_state: GameState, trigger: str, context: dict[str, Any]
    ) -> None:
        """Called after any state transition."""
        self._log_event(
            "state_transition",
            {
                "from": old_state.value,
                "to": new_state.value,
                "trigger": trigger,
                "context": context,
            },
        )

        # Fire transition hooks
        self._fire_transition_hooks(old_state, new_state, trigger, context)

    def _on_turn_advance(self, turns: int) -> None:
        """Called when exploration turns advance."""
        # Tick spell effects
        for _ in range(turns):
            self.tick_spell_effects("turns")
            self.tick_polymorph_effects()

            # Tick area effects at current location
            if self.party_state.location:
                self.tick_location_effects(self.party_state.location.location_id)

    def _on_watch_advance(self, watches: int) -> None:
        """Called when watches advance (every 4 hours)."""
        current_watch = self.time_tracker.game_time.get_current_watch()
        self._log_event(
            "watch_advanced",
            {
                "watches_passed": watches,
                "current_watch": current_watch.value,
                "time": str(self.time_tracker.game_time),
            },
        )

    def _on_day_advance(self, days: int) -> None:
        """Called when days advance."""
        # Consume daily resources
        self.consume_resources(food_days=days, water_days=days)

        # Check for spoiled rations in all character inventories
        current_day = self.time_tracker.days
        spoiled_items = self._check_ration_spoilage(current_day)
        if spoiled_items:
            self._log_event(
                "rations_spoiled",
                {
                    "current_day": current_day,
                    "spoiled_items": spoiled_items,
                },
            )

    def _check_ration_spoilage(self, current_day: int) -> list[dict[str, Any]]:
        """
        Check all character inventories for spoiled rations.

        Args:
            current_day: The current game day

        Returns:
            List of spoiled items with character and item info
        """
        spoiled_items = []
        for character in self._characters.values():
            for item in character.inventory:
                if item.is_perishable and item.is_spoiled(current_day):
                    # Only report newly spoiled items (check if just crossed threshold)
                    days_remaining = item.days_until_spoiled(current_day)
                    if days_remaining == 0:
                        spoiled_items.append({
                            "character_id": character.character_id,
                            "character_name": character.name,
                            "item_name": item.name,
                            "item_id": item.item_id,
                        })
        return spoiled_items

    def _on_season_change(self, old_season: Season, new_season: Season) -> None:
        """Called when season changes."""
        self._log_event(
            "season_changed",
            {
                "old_season": old_season.value,
                "new_season": new_season.value,
            },
        )

    def _tick_conditions(self, turns: int) -> list[dict[str, Any]]:
        """Tick all conditions and return expired ones."""
        expired = []

        for character in self._characters.values():
            still_active = []
            for condition in character.conditions:
                for _ in range(turns):
                    if condition.tick():
                        expired.append(
                            {
                                "character_id": character.character_id,
                                "condition": condition.condition_type.value,
                            }
                        )
                        break
                else:
                    still_active.append(condition)
            character.conditions = still_active

        return expired

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event to the session log."""
        self._session_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "game_time": str(self.time_tracker.game_time),
                "game_date": str(self.time_tracker.game_date),
                "data": data,
            }
        )
        logger.debug(f"Event: {event_type} - {data}")

    # =========================================================================
    # STATE PERSISTENCE
    # =========================================================================

    def get_full_state(self) -> dict[str, Any]:
        """
        Get complete game state for persistence or display.

        Returns:
            Dictionary with all game state
        """
        return {
            "state_machine": self.state_machine.get_state_info(),
            "time": self.time_tracker.get_time_summary(),
            "world": {
                "date": str(self.world_state.current_date),
                "time": str(self.world_state.current_time),
                "season": self.world_state.season.value,
                "weather": self.world_state.weather.value,
                "global_flags": self.world_state.global_flags,
                "cleared_locations": list(self.world_state.cleared_locations),
            },
            "party": {
                "location": str(self.party_state.location),
                "marching_order": self.party_state.marching_order,
                "resources": {
                    "food_days": self.party_state.resources.food_days,
                    "water_days": self.party_state.resources.water_days,
                    "torches": self.party_state.resources.torches,
                    "oil_flasks": self.party_state.resources.lantern_oil_flasks,
                },
                "light_source": (
                    self.party_state.active_light_source.value
                    if self.party_state.active_light_source
                    else None
                ),
                "light_remaining": self.party_state.light_remaining_turns,
            },
            "characters": {
                cid: {
                    "name": c.name,
                    "class": c.character_class,
                    "level": c.level,
                    "hp": f"{c.hp_current}/{c.hp_max}",
                    "conditions": [cond.condition_type.value for cond in c.conditions],
                }
                for cid, c in self._characters.items()
            },
            "encounter": {
                "active": self._current_encounter is not None,
                "type": (
                    self._current_encounter.encounter_type.value
                    if self._current_encounter
                    else None
                ),
            },
        }

    def get_session_log(self) -> list[dict[str, Any]]:
        """Get the session log."""
        return self._session_log.copy()

    def clear_session_log(self) -> None:
        """Clear the session log."""
        self._session_log = []
