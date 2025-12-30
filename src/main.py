"""
Dolmenwood Virtual DM - Main Entry Point

A Python-based companion tool for solo TTRPG play in Dolmenwood.
Designed for use with Mythic Game Master Emulator 2e.

This module provides the main entry point and the VirtualDM class
that coordinates all game subsystems.
"""

import sys
from pathlib import Path

# Add the project root to the Python path for module discovery
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import argparse
import logging
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from src.data_models import (
    GameDate,
    GameTime,
    CharacterState,
    PartyResources,
    LocationType,
    LocationState,
    Season,
    Weather,
    TimeOfDay,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    Combatant,
    StatBlock,
    DiceRoller,
    LightSourceType,
)
from src.game_state import GameState, StateMachine, GlobalController, TimeTracker
from src.hex_crawl import HexCrawlEngine
from src.dungeon import DungeonEngine
from src.combat import CombatEngine
from src.settlement import SettlementEngine
from src.downtime import DowntimeEngine
from src.encounter import EncounterEngine, EncounterOrigin, EncounterAction
from src.ai import (
    DMAgent,
    DMAgentConfig,
    LLMProvider,
    DescriptionResult,
)
from src.ai.lore_search import create_lore_search, LoreSearchInterface
from src.narrative import NarrationContext


# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class GameConfig:
    """Configuration for the game session."""

    data_dir: Path = field(default_factory=lambda: Path("data"))
    campaign_name: str = "default"
    dm_style: str = "standard"

    # LLM Configuration
    llm_provider: str = "mock"  # mock, anthropic, openai, local
    llm_model: Optional[str] = None
    llm_url: Optional[str] = None

    # Narration settings
    enable_narration: bool = True  # Enable LLM-generated narrative descriptions

    # Database options
    use_vector_db: bool = True
    mock_embeddings: bool = False
    local_embeddings: bool = False
    skip_indexing: bool = False

    # Content options
    content_dir: Optional[Path] = None
    ingest_pdf: Optional[Path] = None
    load_content: bool = False

    # Runtime options
    verbose: bool = False

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.content_dir, str):
            self.content_dir = Path(self.content_dir)
        if isinstance(self.ingest_pdf, str):
            self.ingest_pdf = Path(self.ingest_pdf)


# =============================================================================
# VIRTUAL DM CLASS
# =============================================================================

class VirtualDM:
    """
    The Virtual DM orchestrates all game subsystems.

    This is the main interface for the Dolmenwood Virtual DM system.
    It provides access to all engines and manages the game state.

    The Virtual DM acts as a procedural referee and world simulator,
    not a storyteller. It enforces OSR procedures with mechanical
    precision while the LLM layer (external) adds atmospheric description.

    Key Design Principles (from spec):
    - Hard-code procedures, not judgment
    - LLM provides description only (external to this system)
    - All uncertainty via explicit procedures (dice rolls, tables)
    - Failure precedes success
    - Time, risk, resources drive play
    """

    def __init__(
        self,
        config: Optional[GameConfig] = None,
        initial_state: GameState = GameState.WILDERNESS_TRAVEL,
        game_date: Optional[GameDate] = None,
        game_time: Optional[GameTime] = None,
    ):
        """
        Initialize the Virtual DM.

        Args:
            config: Game configuration object
            initial_state: Starting game state (default: WILDERNESS_TRAVEL)
            game_date: Starting date (default: Year 1, Month 1, Day 1)
            game_time: Starting time (default: 08:00)
        """
        self.config = config or GameConfig()
        logger.info("Initializing Dolmenwood Virtual DM...")

        # Initialize the global controller (manages state, time, characters)
        self.controller = GlobalController(
            initial_state=initial_state,
            game_date=game_date,
            game_time=game_time,
        )

        # Initialize all engines
        self.hex_crawl = HexCrawlEngine(self.controller)
        self.dungeon = DungeonEngine(self.controller)
        self.combat = CombatEngine(self.controller)
        self.settlement = SettlementEngine(self.controller)
        self.downtime = DowntimeEngine(self.controller)
        self.encounter = EncounterEngine(self.controller)

        # Initialize the DM Agent for narrative descriptions
        self._dm_agent: Optional[DMAgent] = None
        if self.config.enable_narration:
            self._init_dm_agent()

        logger.info(f"Virtual DM initialized in state: {initial_state.value}")

    def _init_dm_agent(self) -> None:
        """Initialize the DM Agent for narrative generation."""
        provider_map = {
            "mock": LLMProvider.MOCK,
            "anthropic": LLMProvider.ANTHROPIC,
            "openai": LLMProvider.OPENAI,
        }
        provider = provider_map.get(self.config.llm_provider, LLMProvider.MOCK)

        dm_config = DMAgentConfig(
            llm_provider=provider,
            llm_model=self.config.llm_model or "claude-sonnet-4-20250514",
        )

        # Create lore search based on config
        lore_search = create_lore_search(
            use_vector_db=self.config.use_vector_db,
            mock_embeddings=self.config.mock_embeddings,
        )
        lore_status = lore_search.get_status()
        logger.info(f"Lore search initialized: {lore_status}")

        self._dm_agent = DMAgent(dm_config, lore_search=lore_search)
        logger.info(f"DM Agent initialized with provider: {provider.value}")

        # Set up narration callback on NarrativeResolver
        narrative_resolver = self.controller.get_narrative_resolver()
        if narrative_resolver:
            narrative_resolver.set_narration_callback(self._narrate_from_context)

    def _narrate_from_context(
        self,
        context: NarrationContext,
        character_name: str,
    ) -> Optional[str]:
        """
        Convert NarrationContext to narrated text.

        This is the callback used by NarrativeResolver to generate
        LLM narration for resolved actions.
        """
        if not self._dm_agent:
            return None

        # Extract damage totals from the context
        damage_dealt = sum(context.damage_dealt.values()) if context.damage_dealt else 0
        damage_taken = sum(context.healing_done.values()) if context.healing_done else 0

        # Get dice info if available
        dice_rolled = ""
        dice_result = 0
        dice_target = 0
        if context.dice_results:
            dice_info = context.dice_results[0]
            dice_rolled = f"1d6"  # Default for Dolmenwood X-in-6 system
            dice_result = dice_info.get("result", 0)
            dice_target = dice_info.get("target", 0)

        return self.narrate_resolved_action(
            action_description=context.player_input,
            action_category=context.action_category.value if context.action_category else "unknown",
            action_type=context.action_type.value if context.action_type else "unknown",
            success=context.success,
            partial_success=context.partial_success,
            character_name=character_name,
            dice_rolled=dice_rolled,
            dice_result=dice_result,
            dice_target=dice_target,
            damage_dealt=damage_dealt,
            damage_taken=damage_taken,
            conditions_applied=context.conditions_applied,
            effects_created=context.effects_created,
            resources_consumed=context.resources_consumed,
            narrative_hints=context.narrative_hints,
            rule_reference=context.rule_reference or "",
        )

    # =========================================================================
    # STATE ACCESS
    # =========================================================================

    @property
    def current_state(self) -> GameState:
        """Get the current game state."""
        return self.controller.current_state

    @property
    def state_machine(self) -> StateMachine:
        """Get the state machine."""
        return self.controller.state_machine

    @property
    def time_tracker(self) -> TimeTracker:
        """Get the time tracker."""
        return self.controller.time_tracker

    def get_full_state(self) -> dict[str, Any]:
        """
        Get complete game state for display or persistence.

        Returns:
            Dictionary with all game state
        """
        return self.controller.get_full_state()

    def get_valid_actions(self) -> list[str]:
        """
        Get valid actions/triggers from current state.

        Returns:
            List of valid action names
        """
        return self.controller.get_valid_actions()

    # =========================================================================
    # CHARACTER MANAGEMENT
    # =========================================================================

    def add_character(self, character: CharacterState) -> None:
        """Add a character to the party."""
        self.controller.add_character(character)
        logger.info(f"Added character: {character.name}")

    def create_character(
        self,
        character_id: str,
        name: str,
        character_class: str,
        level: int,
        ability_scores: dict[str, int],
        hp_max: int,
        armor_class: int = 10,
        base_speed: int = 40,
    ) -> CharacterState:
        """
        Create and add a new character.

        Args:
            character_id: Unique identifier
            name: Character name
            character_class: Class (Fighter, Magic-User, etc.)
            level: Character level
            ability_scores: Dict of STR, INT, WIS, DEX, CON, CHA
            hp_max: Maximum HP
            armor_class: AC (ascending, default 10 unarmored)
            base_speed: Base Speed in feet (default 40, per p146)

        Returns:
            The created CharacterState
        """
        character = CharacterState(
            character_id=character_id,
            name=name,
            character_class=character_class,
            level=level,
            ability_scores=ability_scores,
            hp_current=hp_max,
            hp_max=hp_max,
            armor_class=armor_class,
            base_speed=base_speed,
        )
        self.add_character(character)
        return character

    def get_character(self, character_id: str) -> Optional[CharacterState]:
        """Get a character by ID."""
        return self.controller.get_character(character_id)

    def get_party(self) -> list[CharacterState]:
        """Get all party members."""
        return self.controller.get_all_characters()

    # =========================================================================
    # RESOURCE MANAGEMENT
    # =========================================================================

    def set_party_resources(
        self,
        food_days: float = 0,
        water_days: float = 0,
        torches: int = 0,
        lantern_oil: int = 0,
    ) -> None:
        """Set party resources."""
        resources = PartyResources(
            food_days=food_days,
            water_days=water_days,
            torches=torches,
            lantern_oil_flasks=lantern_oil,
        )
        self.controller.party_state.resources = resources

    def get_resources(self) -> PartyResources:
        """Get current party resources."""
        return self.controller.party_state.resources

    # =========================================================================
    # QUICK ACTIONS
    # =========================================================================

    def travel_to_hex(
        self,
        hex_id: str,
        narrate: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Travel to an adjacent hex.

        Only valid in WILDERNESS_TRAVEL state.

        Args:
            hex_id: Target hex ID
            narrate: Generate narrative description (default: use config setting)

        Returns:
            Travel result dictionary with optional 'narration' key
        """
        if self.current_state != GameState.WILDERNESS_TRAVEL:
            return {"error": f"Cannot travel from state: {self.current_state.value}"}

        result = self.hex_crawl.travel_to_hex(hex_id)

        # Add narration if enabled and travel succeeded
        should_narrate = narrate if narrate is not None else self.config.enable_narration
        if should_narrate and self._dm_agent and "error" not in result:
            narration = self._narrate_hex_arrival(hex_id, result)
            if narration:
                result["narration"] = narration

        return result

    def _narrate_hex_arrival(
        self,
        hex_id: str,
        travel_result: dict[str, Any],
    ) -> Optional[str]:
        """Generate narrative description for arriving at a hex."""
        if not self._dm_agent:
            return None

        # Extract hex info from result or controller
        terrain = travel_result.get("terrain", "wilderness")
        hex_name = travel_result.get("hex_name")
        features = travel_result.get("features", [])

        # Get current conditions
        time_summary = self.time_tracker.get_time_summary()
        time_of_day = TimeOfDay(time_summary.get("time_of_day", "day"))
        weather = self.controller.world_state.weather
        season = Season(time_summary.get("season", "summer"))

        try:
            desc_result = self._dm_agent.describe_hex(
                hex_id=hex_id,
                terrain=terrain,
                name=hex_name,
                features=features,
                time_of_day=time_of_day,
                weather=weather,
                season=season,
            )
            if desc_result.success:
                return desc_result.content
            else:
                logger.warning(f"Narration failed: {desc_result.warnings}")
                return None
        except Exception as e:
            logger.warning(f"Error generating hex narration: {e}")
            return None

    def enter_dungeon(self, dungeon_id: str, entry_room: str) -> dict[str, Any]:
        """
        Enter a dungeon.

        Args:
            dungeon_id: Dungeon identifier
            entry_room: Entry room ID

        Returns:
            Entry result dictionary
        """
        return self.dungeon.enter_dungeon(dungeon_id, entry_room)

    def enter_settlement(self, settlement_id: str) -> dict[str, Any]:
        """
        Enter a settlement.

        Args:
            settlement_id: Settlement identifier

        Returns:
            Entry result dictionary
        """
        return self.settlement.enter_settlement(settlement_id)

    def rest(self, rest_type: str = "long") -> dict[str, Any]:
        """
        Rest the party.

        Args:
            rest_type: "short", "long", or "full"

        Returns:
            Rest result dictionary
        """
        from src.downtime.downtime_engine import RestType

        type_map = {
            "short": RestType.SHORT_REST,
            "long": RestType.LONG_REST,
            "full": RestType.FULL_REST,
        }

        return self.downtime.rest(type_map.get(rest_type, RestType.LONG_REST))

    # =========================================================================
    # NARRATION METHODS
    # =========================================================================

    def narrate_encounter_start(
        self,
        encounter: EncounterState,
        creature_name: str,
        number_appearing: int,
        terrain: str,
    ) -> Optional[str]:
        """
        Generate narrative framing for the start of an encounter.

        This should be called AFTER mechanical setup (distance, surprise)
        has been determined. The narration describes what the party SEES.

        Args:
            encounter: The resolved encounter state
            creature_name: Name of the encountered creature(s)
            number_appearing: How many creatures
            terrain: Current terrain type

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        time_summary = self.time_tracker.get_time_summary()
        time_of_day = TimeOfDay(time_summary.get("time_of_day", "day"))
        weather = self.controller.world_state.weather

        try:
            result = self._dm_agent.frame_encounter(
                encounter=encounter,
                creature_name=creature_name,
                number_appearing=number_appearing,
                terrain=terrain,
                time_of_day=time_of_day,
                weather=weather,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating encounter narration: {e}")
            return None

    def narrate_combat_round(
        self,
        round_number: int,
        resolved_actions: list[dict[str, Any]],
        damage_results: Optional[dict[str, int]] = None,
        conditions_applied: Optional[list[str]] = None,
        morale_results: Optional[list[str]] = None,
        deaths: Optional[list[str]] = None,
    ) -> Optional[str]:
        """
        Generate narrative description for a resolved combat round.

        CRITICAL: All outcomes must already be determined by the combat engine.
        This method only describes what happened.

        Args:
            round_number: Current round number
            resolved_actions: List of resolved actions with actor, action,
                              target, result, damage keys
            damage_results: Dict of combatant_id -> damage taken
            conditions_applied: New conditions this round
            morale_results: Morale check results
            deaths: Who died this round

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            result = self._dm_agent.narrate_combat_round(
                round_number=round_number,
                resolved_actions=resolved_actions,
                damage_results=damage_results,
                conditions_applied=conditions_applied,
                morale_results=morale_results,
                deaths=deaths,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating combat narration: {e}")
            return None

    def narrate_failure(
        self,
        failed_action: str,
        failure_type: str,
        consequence_type: str,
        consequence_details: str,
        visible_warning: str = "",
    ) -> Optional[str]:
        """
        Generate narrative description for a failed action.

        Makes failures feel fair by describing consequences dramatically.

        Args:
            failed_action: What was attempted
            failure_type: Type of failure (missed attack, failed save, etc.)
            consequence_type: Category of consequence
            consequence_details: Specific mechanical result
            visible_warning: Warning signs that were present

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            result = self._dm_agent.describe_failure(
                failed_action=failed_action,
                failure_type=failure_type,
                consequence_type=consequence_type,
                consequence_details=consequence_details,
                visible_warning=visible_warning,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating failure narration: {e}")
            return None

    def narrate_combat_end(
        self,
        *,
        combat_outcome: str,
        surviving_party: list[str],
        fallen_party: list[str],
        defeated_enemies: list[str],
        fled_enemies: list[str],
        significant_moments: list[str],
        total_rounds: int,
        xp_gained: int = 0,
        treasure_found: list[str] | None = None,
    ) -> Optional[str]:
        """
        Generate narrative description for combat conclusion.

        Describes the aftermath of combat, honoring the fallen and
        celebrating victories without minimizing consequences.

        Args:
            combat_outcome: Result (victory, retreat, defeat, rout)
            surviving_party: Party members still standing
            fallen_party: Party members who fell in combat
            defeated_enemies: Enemies killed or incapacitated
            fled_enemies: Enemies who escaped
            significant_moments: Notable events during combat
            total_rounds: How long combat lasted
            xp_gained: Experience points earned
            treasure_found: Items discovered on enemies

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            # Derive victor_side from combat_outcome
            victor_side = "party" if combat_outcome in ("victory", "rout") else (
                "enemies" if combat_outcome == "defeat" else "none"
            )

            result = self._dm_agent.narrate_combat_end(
                outcome=combat_outcome,
                victor_side=victor_side,
                party_casualties=fallen_party,
                enemy_casualties=defeated_enemies,
                fled_combatants=fled_enemies,
                rounds_fought=total_rounds,
                notable_moments=significant_moments,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating combat end narration: {e}")
            return None

    def narrate_dungeon_event(
        self,
        *,
        event_type: str,
        event_description: str,
        location_name: str,
        location_atmosphere: str = "",
        party_formation: list[str] | None = None,
        triggering_action: str = "",
        mechanical_outcome: str = "",
        damage_dealt: dict[str, int] | None = None,
        items_involved: list[str] | None = None,
        hidden_elements: list[str] | None = None,
    ) -> Optional[str]:
        """
        Generate narrative description for dungeon events.

        Covers traps, discoveries, environmental hazards, and
        atmospheric moments in dungeon exploration.

        Args:
            event_type: Type of event (trap, discovery, hazard, secret)
            event_description: What happened mechanically
            location_name: Where this occurred
            location_atmosphere: Ambient description
            party_formation: Who was where in marching order
            triggering_action: What triggered the event
            mechanical_outcome: Game mechanics result
            damage_dealt: Damage to party members if any
            items_involved: Relevant items
            hidden_elements: Things that might be discovered

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            # Extract damage from first affected character
            damage_dict = damage_dealt or {}
            first_victim = list(damage_dict.keys())[0] if damage_dict else ""
            total_damage = sum(damage_dict.values()) if damage_dict else 0

            # Determine success from mechanical_outcome
            success = "succeeded" in mechanical_outcome.lower() or "saved" in mechanical_outcome.lower()

            result = self._dm_agent.narrate_dungeon_event(
                event_type=event_type,
                event_name=event_description,
                success=success,
                damage_taken=total_damage,
                damage_type="",  # Could be enhanced to extract from description
                character_name=first_victim,
                description=f"{triggering_action}. {location_atmosphere}".strip(". "),
                room_context=location_name,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating dungeon event narration: {e}")
            return None

    def narrate_rest(
        self,
        *,
        rest_type: str,
        location_name: str,
        location_safety: str,
        duration_hours: int,
        healing_received: dict[str, int] | None = None,
        spells_recovered: dict[str, list[str]] | None = None,
        watch_schedule: list[str] | None = None,
        interruptions: list[str] | None = None,
        weather_conditions: str = "",
        ambient_events: list[str] | None = None,
        resources_consumed: dict[str, int] | None = None,
    ) -> Optional[str]:
        """
        Generate narrative description for rest and camping.

        Creates atmospheric rest scenes that emphasize fellowship,
        respite, and the quiet moments between adventures.

        Args:
            rest_type: Type of rest (short, long, camp, safe_haven)
            location_name: Where party is resting
            location_safety: Safety level of location
            duration_hours: How long the rest lasted
            healing_received: HP restored per character
            spells_recovered: Spells recovered per caster
            watch_schedule: Who took watch and when
            interruptions: Events that disturbed rest
            weather_conditions: Current weather
            ambient_events: Atmospheric background events
            resources_consumed: Food, fuel, etc. used

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            # Determine sleep quality from interruptions
            sleep_quality = "poor" if interruptions else "good"
            if location_safety == "safe":
                sleep_quality = "good"
            elif location_safety in ("dangerous", "hostile"):
                sleep_quality = "poor"

            result = self._dm_agent.narrate_rest(
                rest_type=rest_type,
                location_type=location_name,
                watch_events=watch_schedule or [],
                sleep_quality=sleep_quality,
                healing_done=healing_received or {},
                resources_consumed=resources_consumed or {},
                weather=weather_conditions,
                interruptions=interruptions or [],
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating rest narration: {e}")
            return None

    def narrate_poi_approach(
        self,
        *,
        poi_name: str,
        poi_type: str,
        description: str,
        tagline: str = "",
        distance: str = "near",
        discovery_hints: list[str] | None = None,
        visible_hazards: list[str] | None = None,
        visible_npcs: list[str] | None = None,
        party_approach: str = "cautious",
    ) -> Optional[str]:
        """
        Generate narrative for approaching a Point of Interest.

        Args:
            poi_name: Name of the POI
            poi_type: Type (manse, ruin, grove, cave, etc.)
            description: Exterior description
            tagline: Short evocative description
            distance: near, medium, far
            discovery_hints: Sensory clues that drew attention
            visible_hazards: Hazards visible from approach
            visible_npcs: Figures visible from approach
            party_approach: cautious, direct, stealthy

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        time_summary = self.time_tracker.get_time_summary()
        time_of_day = TimeOfDay(time_summary.get("time_of_day", "day"))
        weather = self.controller.world_state.weather
        season = Season(time_summary.get("season", "summer"))

        try:
            result = self._dm_agent.describe_poi_approach(
                poi_name=poi_name,
                poi_type=poi_type,
                description=description,
                tagline=tagline,
                distance=distance,
                time_of_day=time_of_day,
                weather=weather,
                season=season,
                discovery_hints=discovery_hints or [],
                visible_hazards=visible_hazards or [],
                visible_npcs=visible_npcs or [],
                party_approach=party_approach,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating POI approach narration: {e}")
            return None

    def narrate_poi_entry(
        self,
        *,
        poi_name: str,
        poi_type: str,
        entering: str,
        interior: str = "",
        inhabitants_visible: list[str] | None = None,
        atmosphere: list[str] | None = None,
        entry_method: str = "normal",
        entry_condition: str = "",
    ) -> Optional[str]:
        """
        Generate narrative for entering a Point of Interest.

        Args:
            poi_name: Name of the POI
            poi_type: Type of POI
            entering: Entry description from data model
            interior: Interior description
            inhabitants_visible: Visible inhabitants
            atmosphere: Sensory tags for atmosphere
            entry_method: normal, forced, secret, magical
            entry_condition: diving, climbing, etc.

        Returns:
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        time_summary = self.time_tracker.get_time_summary()
        time_of_day = TimeOfDay(time_summary.get("time_of_day", "day"))

        try:
            result = self._dm_agent.describe_poi_entry(
                poi_name=poi_name,
                poi_type=poi_type,
                entering=entering,
                interior=interior,
                time_of_day=time_of_day,
                inhabitants_visible=inhabitants_visible or [],
                atmosphere=atmosphere or [],
                entry_method=entry_method,
                entry_condition=entry_condition,
            )
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating POI entry narration: {e}")
            return None

    def narrate_poi_feature(
        self,
        *,
        poi_name: str,
        feature_name: str,
        feature_description: str,
        interaction_type: str,
        discovery_success: bool = True,
        found_items: list[str] | None = None,
        found_secrets: list[str] | None = None,
        hazard_triggered: bool = False,
        hazard_description: str = "",
        character_name: str = "",
        sub_location_name: str = "",
    ) -> Optional[str]:
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
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            result = self._dm_agent.describe_poi_feature(
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
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating POI feature narration: {e}")
            return None

    def narrate_resolved_action(
        self,
        *,
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
        conditions_applied: list[str] | None = None,
        effects_created: list[str] | None = None,
        resources_consumed: dict[str, int] | None = None,
        narrative_hints: list[str] | None = None,
        location_context: str = "",
        rule_reference: str = "",
    ) -> Optional[str]:
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
            Narrative description or None if narration disabled
        """
        if not self._dm_agent or not self.config.enable_narration:
            return None

        try:
            result = self._dm_agent.narrate_resolved_action(
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
            return result.content if result.success else None
        except Exception as e:
            logger.warning(f"Error generating resolved action narration: {e}")
            return None

    @property
    def dm_agent(self) -> Optional[DMAgent]:
        """Get the DM Agent for direct access if needed."""
        return self._dm_agent

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def get_session_log(self) -> list[dict[str, Any]]:
        """Get the session event log."""
        return self.controller.get_session_log()

    def get_dice_log(self) -> list:
        """Get all dice rolls this session."""
        return DiceRoller.get_roll_log()

    def clear_dice_log(self) -> None:
        """Clear the dice roll log."""
        DiceRoller.clear_roll_log()

    def get_time_summary(self) -> dict[str, Any]:
        """Get current time state."""
        return self.time_tracker.get_time_summary()

    # =========================================================================
    # DISPLAY HELPERS
    # =========================================================================

    def status(self) -> str:
        """
        Get a formatted status string for display.

        Returns:
            Multi-line status string
        """
        state = self.get_full_state()
        time_state = state["time"]
        party = state["party"]

        lines = [
            "=" * 60,
            "DOLMENWOOD VIRTUAL DM STATUS",
            "=" * 60,
            f"State: {state['state_machine']['current_state']}",
            f"Date: {time_state['date']} ({time_state['season']})",
            f"Time: {time_state['time']} ({time_state['time_of_day']})",
            f"Location: {party['location']}",
            "",
            "Party Resources:",
            f"  Food: {party['resources']['food_days']:.1f} days",
            f"  Water: {party['resources']['water_days']:.1f} days",
            f"  Torches: {party['resources']['torches']}",
            f"  Oil: {party['resources']['oil_flasks']} flasks",
        ]

        if party["light_source"]:
            lines.append(f"  Active Light: {party['light_source']} ({party['light_remaining']} turns)")

        lines.append("")
        lines.append("Party Members:")
        for cid, cdata in state["characters"].items():
            lines.append(f"  {cdata['name']} ({cdata['class']} {cdata['level']}): {cdata['hp']}")
            if cdata["conditions"]:
                lines.append(f"    Conditions: {', '.join(cdata['conditions'])}")

        lines.append("")
        lines.append("Valid Actions: " + ", ".join(self.get_valid_actions()))
        lines.append("=" * 60)

        return "\n".join(lines)


# =============================================================================
# DEMO SESSION CREATION
# =============================================================================

def create_demo_session(config: Optional[GameConfig] = None) -> VirtualDM:
    """
    Create a demo session with sample characters.

    Returns:
        Initialized VirtualDM with demo party
    """
    dm = VirtualDM(
        config=config,
        initial_state=GameState.WILDERNESS_TRAVEL,
        game_date=GameDate(year=1, month=6, day=15),
        game_time=GameTime(hour=9, minute=0),
    )

    # Create sample party
    dm.create_character(
        character_id="char_001",
        name="Sir Aldric",
        character_class="Fighter",
        level=3,
        ability_scores={"STR": 16, "INT": 10, "WIS": 12, "DEX": 13, "CON": 14, "CHA": 11},
        hp_max=24,
        armor_class=4,  # Plate + Shield
    )

    dm.create_character(
        character_id="char_002",
        name="Mira Thornwood",
        character_class="Magic-User",
        level=3,
        ability_scores={"STR": 8, "INT": 17, "WIS": 14, "DEX": 12, "CON": 10, "CHA": 13},
        hp_max=8,
        armor_class=9,  # No armor
    )

    dm.create_character(
        character_id="char_003",
        name="Brother Cormac",
        character_class="Cleric",
        level=2,
        ability_scores={"STR": 12, "INT": 11, "WIS": 16, "DEX": 10, "CON": 13, "CHA": 14},
        hp_max=12,
        armor_class=5,  # Chain + Shield
    )

    dm.create_character(
        character_id="char_004",
        name="Wren",
        character_class="Thief",
        level=3,
        ability_scores={"STR": 11, "INT": 14, "WIS": 10, "DEX": 17, "CON": 12, "CHA": 13},
        hp_max=10,
        armor_class=7,  # Leather
    )

    # Set resources
    dm.set_party_resources(
        food_days=7,
        water_days=7,
        torches=10,
        lantern_oil=4,
    )

    # Set starting location
    dm.controller.set_party_location(LocationType.HEX, "0709")

    return dm


# =============================================================================
# CLI INTERFACE
# =============================================================================

class DolmenwoodCLI:
    """Interactive command-line interface for the game."""

    def __init__(self, dm: VirtualDM):
        self.dm = dm
        self.running = False
        self.commands = {
            "status": self.cmd_status,
            "help": self.cmd_help,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
            "travel": self.cmd_travel,
            "actions": self.cmd_actions,
            "roll": self.cmd_roll,
            "time": self.cmd_time,
            "party": self.cmd_party,
            "resources": self.cmd_resources,
            "log": self.cmd_log,
            "dice": self.cmd_dice,
            "transition": self.cmd_transition,
        }

    def run(self) -> None:
        """Run the interactive CLI loop."""
        self.running = True
        print("\n" + "=" * 60)
        print("DOLMENWOOD VIRTUAL DM - Interactive Mode")
        print("=" * 60)
        print("Type 'help' for available commands, 'quit' to exit.\n")

        while self.running:
            try:
                user_input = input(f"[{self.dm.current_state.value}]> ").strip()
                if not user_input:
                    continue

                self.process_command(user_input)

            except KeyboardInterrupt:
                print("\nInterrupted. Type 'quit' to exit.")
            except EOFError:
                self.running = False

        print("\nFarewell, adventurer!")

    def process_command(self, user_input: str) -> None:
        """Process a user command."""
        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")

    def cmd_help(self, args: str) -> None:
        """Show help information."""
        print("""
Available Commands:
  status      - Show current game status
  actions     - Show valid actions from current state
  travel HEX  - Travel to adjacent hex (e.g., 'travel 0710')
  transition  - Trigger a state transition (e.g., 'transition enter_dungeon')
  roll DICE   - Roll dice (e.g., 'roll 2d6+3')
  time        - Show current game time
  party       - Show party information
  resources   - Show party resources
  log         - Show session event log
  dice        - Show dice roll history
  help        - Show this help
  quit/exit   - Exit the game
""")

    def cmd_status(self, args: str) -> None:
        """Show game status."""
        print(self.dm.status())

    def cmd_quit(self, args: str) -> None:
        """Quit the game."""
        self.running = False

    def cmd_travel(self, args: str) -> None:
        """Travel to a hex."""
        if not args:
            print("Usage: travel HEX_ID (e.g., 'travel 0710')")
            return
        result = self.dm.travel_to_hex(args.strip())
        print(json.dumps(result, indent=2, default=str))

    def cmd_actions(self, args: str) -> None:
        """Show valid actions."""
        actions = self.dm.get_valid_actions()
        print("Valid actions from current state:")
        for action in actions:
            print(f"  - {action}")

    def cmd_roll(self, args: str) -> None:
        """Roll dice."""
        if not args:
            print("Usage: roll DICE (e.g., 'roll 2d6+3', 'roll 1d20')")
            return
        try:
            result = DiceRoller.roll(args.strip())
            print(f"Rolling {args}: {result}")
        except Exception as e:
            print(f"Error rolling dice: {e}")

    def cmd_time(self, args: str) -> None:
        """Show current time."""
        summary = self.dm.get_time_summary()
        print(f"Date: {summary['date']} ({summary['season']})")
        print(f"Time: {summary['time']} ({summary['time_of_day']})")

    def cmd_party(self, args: str) -> None:
        """Show party information."""
        party = self.dm.get_party()
        print("\nParty Members:")
        print("-" * 40)
        for char in party:
            print(f"  {char.name}")
            print(f"    Class: {char.character_class} Level {char.level}")
            print(f"    HP: {char.hp_current}/{char.hp_max}")
            print(f"    AC: {char.armor_class}")
            if char.conditions:
                print(f"    Conditions: {', '.join(c.name for c in char.conditions)}")
        print("-" * 40)

    def cmd_resources(self, args: str) -> None:
        """Show party resources."""
        res = self.dm.get_resources()
        print("\nParty Resources:")
        print(f"  Food: {res.food_days:.1f} days")
        print(f"  Water: {res.water_days:.1f} days")
        print(f"  Torches: {res.torches}")
        print(f"  Lantern Oil: {res.lantern_oil_flasks} flasks")
        print(f"  Gold: {res.gold} gp")

    def cmd_log(self, args: str) -> None:
        """Show session log."""
        log = self.dm.get_session_log()
        print("\nSession Log (last 10 entries):")
        print("-" * 40)
        for entry in log[-10:]:
            print(f"  {entry}")
        print("-" * 40)

    def cmd_dice(self, args: str) -> None:
        """Show dice roll history."""
        rolls = self.dm.get_dice_log()
        print("\nDice Roll History (last 10):")
        print("-" * 40)
        for roll in rolls[-10:]:
            print(f"  {roll}")
        print("-" * 40)

    def cmd_transition(self, args: str) -> None:
        """Trigger a state transition."""
        if not args:
            print("Usage: transition TRIGGER_NAME")
            print("Valid triggers:", ", ".join(self.dm.get_valid_actions()))
            return

        trigger = args.strip()
        try:
            new_state = self.dm.controller.transition(trigger)
            print(f"Transitioned to: {new_state.value}")
        except Exception as e:
            print(f"Transition failed: {e}")


# =============================================================================
# INDIVIDUAL LOOP TESTERS
# =============================================================================

def test_hex_exploration_loop(dm: VirtualDM) -> None:
    """Test the hex exploration/wilderness travel loop."""
    print("\n" + "=" * 60)
    print("TESTING: Hex Exploration Loop")
    print("=" * 60)

    print("\n1. Initial state:")
    print(f"   Current state: {dm.current_state.value}")
    print(f"   Location: {dm.controller.party_state.location}")

    print("\n2. Advancing travel segment...")
    result = dm.controller.advance_travel_segment()
    print(f"   Result: {json.dumps(result, indent=4, default=str)}")

    print("\n3. Rolling for encounter check...")
    roll = DiceRoller.roll("1d6", "Encounter check")
    print(f"   Encounter check roll: {roll.total}")
    if roll.total == 1:
        print("   Encounter triggered!")
    else:
        print("   No encounter.")

    print("\n4. Rolling weather...")
    weather = dm.controller.roll_weather()
    print(f"   Weather: {weather}")

    print("\n5. Checking time advancement...")
    time_summary = dm.get_time_summary()
    print(f"   Current time: {time_summary['time']} ({time_summary['time_of_day']})")

    print("\n6. Simulating travel to adjacent hex...")
    adjacent_hexes = ["0710", "0708", "0809", "0609"]
    target = adjacent_hexes[0]
    print(f"   Attempting travel to hex {target}...")
    travel_result = dm.travel_to_hex(target)
    print(f"   Travel result: {json.dumps(travel_result, indent=4, default=str)}")

    print("\n" + "=" * 60)
    print("Hex Exploration Loop Test Complete")
    print("=" * 60)


def test_encounter_loop(dm: VirtualDM) -> None:
    """Test the encounter resolution loop."""
    print("\n" + "=" * 60)
    print("TESTING: Encounter Loop")
    print("=" * 60)

    # Create a test encounter
    combatants = [
        Combatant(
            combatant_id="char_001",
            name="Sir Aldric",
            side="party",
            stat_block=StatBlock(
                armor_class=4,
                hit_dice="3d8",
                hp_current=24,
                hp_max=24,
                movement=90,
                attacks=[{"name": "Sword", "damage": "1d8+3", "bonus": 3}],
                morale=12,
            ),
        ),
        Combatant(
            combatant_id="goblin_1",
            name="Goblin Scout",
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8-1",
                hp_current=4,
                hp_max=4,
                movement=60,
                attacks=[{"name": "Short Sword", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ),
    ]

    encounter = EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=60,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=["goblin scout"],
        context="patrolling the forest",
        terrain="forest",
        combatants=combatants,
    )

    print("\n1. Starting encounter...")
    result = dm.encounter.start_encounter(
        encounter=encounter,
        origin=EncounterOrigin.WILDERNESS,
    )
    print(f"   Encounter started: {result['encounter_started']}")
    print(f"   Origin: {result['origin']}")

    print("\n2. Running automatic phases...")
    phase_result = dm.encounter.auto_run_phases()
    print(f"   Surprise status: {phase_result.get('surprise', {})}")
    print(f"   Distance: {phase_result.get('distance', {})}")
    print(f"   Initiative: {phase_result.get('initiative', {})}")

    print("\n3. Testing encounter actions...")
    print("   Available actions: ATTACK, PARLEY, EVASION, WAIT")

    # Test parley action
    print("\n   Testing PARLEY action...")
    parley_result = dm.encounter.execute_action(EncounterAction.PARLEY, actor="party")
    print(f"   Reaction roll: {parley_result.reaction_roll}")
    print(f"   Reaction result: {parley_result.reaction_result}")

    print("\n4. Encounter summary:")
    summary = dm.encounter.get_encounter_summary()
    print(f"   {json.dumps(summary, indent=4, default=str)}")

    # Reset state for other tests
    if dm.encounter.is_active():
        dm.encounter.conclude_encounter("test_complete")

    print("\n" + "=" * 60)
    print("Encounter Loop Test Complete")
    print("=" * 60)


def test_dungeon_exploration_loop(dm: VirtualDM) -> None:
    """Test the dungeon exploration loop."""
    print("\n" + "=" * 60)
    print("TESTING: Dungeon Exploration Loop")
    print("=" * 60)

    print("\n1. Current state before entering dungeon:")
    print(f"   State: {dm.current_state.value}")

    print("\n2. Entering dungeon...")
    # Transition to dungeon state
    if dm.current_state == GameState.WILDERNESS_TRAVEL:
        dm.controller.transition("enter_dungeon")
    print(f"   New state: {dm.current_state.value}")

    print("\n3. Setting dungeon location...")
    dm.controller.set_party_location(
        LocationType.DUNGEON_ROOM,
        "test_dungeon",
        "entry_chamber",
    )
    print(f"   Location: {dm.controller.party_state.location}")

    print("\n4. Activating light source...")
    dm.controller.party_state.active_light_source = LightSourceType.TORCH
    dm.controller.party_state.light_remaining_turns = 6
    print(f"   Light source: {dm.controller.party_state.active_light_source}")
    print(f"   Turns remaining: {dm.controller.party_state.light_remaining_turns}")

    print("\n5. Rolling for wandering monster check...")
    roll = DiceRoller.roll("1d6", "Wandering monster check")
    print(f"   Wandering monster check: {roll.total}")
    if roll.total == 1:
        print("   Monster encountered!")
    else:
        print("   No monster.")

    print("\n6. Simulating dungeon turn (advancing time)...")
    result = dm.controller.advance_time(1)  # 1 turn = 10 minutes
    print(f"   Time advancement result: {result}")
    print(f"   Light remaining: {dm.controller.party_state.light_remaining_turns} turns")

    print("\n7. Exiting dungeon...")
    dm.controller.transition("exit_dungeon")
    print(f"   New state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Dungeon Exploration Loop Test Complete")
    print("=" * 60)


def test_combat_loop(dm: VirtualDM) -> None:
    """Test the combat loop."""
    print("\n" + "=" * 60)
    print("TESTING: Combat Loop")
    print("=" * 60)

    # Prepare for combat
    combatants = [
        Combatant(
            combatant_id="char_001",
            name="Sir Aldric",
            side="party",
            stat_block=StatBlock(
                armor_class=4,
                hit_dice="3d8",
                hp_current=24,
                hp_max=24,
                movement=90,
                attacks=[{"name": "Longsword", "damage": "1d8+3", "bonus": 3}],
                morale=12,
            ),
        ),
        Combatant(
            combatant_id="char_002",
            name="Mira Thornwood",
            side="party",
            stat_block=StatBlock(
                armor_class=9,
                hit_dice="3d4",
                hp_current=8,
                hp_max=8,
                movement=120,
                attacks=[{"name": "Dagger", "damage": "1d4", "bonus": 0}],
                morale=8,
            ),
        ),
        Combatant(
            combatant_id="goblin_1",
            name="Goblin Warrior",
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8",
                hp_current=5,
                hp_max=5,
                movement=60,
                attacks=[{"name": "Sword", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ),
        Combatant(
            combatant_id="goblin_2",
            name="Goblin Archer",
            side="enemy",
            stat_block=StatBlock(
                armor_class=7,
                hit_dice="1d8",
                hp_current=4,
                hp_max=4,
                movement=60,
                attacks=[{"name": "Shortbow", "damage": "1d6", "bonus": 0}],
                morale=7,
            ),
        ),
    ]

    encounter = EncounterState(
        encounter_type=EncounterType.MONSTER,
        distance=30,
        surprise_status=SurpriseStatus.NO_SURPRISE,
        actors=["goblin warriors"],
        terrain="dungeon",
        combatants=combatants,
    )

    print("\n1. Setting up combat...")
    # Transition to combat state
    dm.controller.transition("encounter_triggered")
    dm.controller.transition("encounter_to_combat")
    print(f"   State: {dm.current_state.value}")

    print("\n2. Starting combat...")
    from src.combat.combat_engine import CombatAction, CombatActionType

    start_result = dm.combat.start_combat(encounter, GameState.WILDERNESS_TRAVEL)
    print(f"   Combat started: {start_result['combat_started']}")
    print(f"   Party combatants: {len(start_result['party_combatants'])}")
    print(f"   Enemy combatants: {len(start_result['enemy_combatants'])}")

    print("\n3. Executing combat round 1...")
    party_actions = [
        CombatAction(
            combatant_id="char_001",
            action_type=CombatActionType.MELEE_ATTACK,
            target_id="goblin_1",
        ),
    ]
    round_result = dm.combat.execute_round(party_actions)
    print(f"   Round number: {round_result.round_number}")
    print(f"   Party initiative: {round_result.party_initiative}")
    print(f"   Enemy initiative: {round_result.enemy_initiative}")
    print(f"   First to act: {round_result.first_side}")
    print(f"   Actions resolved: {len(round_result.actions_resolved)}")

    for action in round_result.actions_resolved[:3]:
        print(f"     - {action.attacker_id} attacked {action.defender_id}: "
              f"{'HIT' if action.hit else 'MISS'} "
              f"(roll: {action.attack_roll}, damage: {action.damage_dealt})")

    print("\n4. Combat summary:")
    summary = dm.combat.get_combat_summary()
    print(f"   {json.dumps(summary, indent=4, default=str)}")

    print("\n5. Ending combat...")
    end_result = dm.combat.end_combat()
    print(f"   Rounds fought: {end_result['rounds_fought']}")
    print(f"   New state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Combat Loop Test Complete")
    print("=" * 60)


def test_settlement_loop(dm: VirtualDM) -> None:
    """Test the settlement exploration loop."""
    print("\n" + "=" * 60)
    print("TESTING: Settlement Exploration Loop")
    print("=" * 60)

    print("\n1. Current state:")
    print(f"   State: {dm.current_state.value}")

    print("\n2. Entering settlement...")
    if dm.current_state == GameState.WILDERNESS_TRAVEL:
        dm.controller.transition("enter_settlement")
    elif dm.current_state != GameState.SETTLEMENT_EXPLORATION:
        # Reset to wilderness first
        dm.controller.force_state(GameState.WILDERNESS_TRAVEL, "test reset")
        dm.controller.transition("enter_settlement")

    print(f"   New state: {dm.current_state.value}")

    print("\n3. Setting settlement location...")
    dm.controller.set_party_location(
        LocationType.SETTLEMENT,
        "prigwort",
        "The Wicked Owl Inn",
    )
    print(f"   Location: {dm.controller.party_state.location}")

    print("\n4. Available settlement actions:")
    actions = dm.get_valid_actions()
    for action in actions:
        print(f"   - {action}")

    print("\n5. Simulating visit to inn...")
    print("   (Settlement engine would provide NPC interactions, services, rumors)")

    print("\n6. Leaving settlement...")
    dm.controller.transition("exit_settlement")
    print(f"   New state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Settlement Exploration Loop Test Complete")
    print("=" * 60)


def test_social_interaction_loop(dm: VirtualDM) -> None:
    """Test the social interaction loop."""
    print("\n" + "=" * 60)
    print("TESTING: Social Interaction Loop")
    print("=" * 60)

    print("\n1. Setting up for social interaction...")
    # Need to be in settlement first
    if dm.current_state != GameState.SETTLEMENT_EXPLORATION:
        if dm.current_state == GameState.WILDERNESS_TRAVEL:
            dm.controller.transition("enter_settlement")
        else:
            dm.controller.force_state(GameState.SETTLEMENT_EXPLORATION, "test setup")

    print(f"   State: {dm.current_state.value}")

    print("\n2. Initiating conversation...")
    dm.controller.transition("initiate_conversation")
    print(f"   New state: {dm.current_state.value}")

    print("\n3. Rolling NPC reaction...")
    reaction_result = DiceRoller.roll("2d6")
    reaction_roll = reaction_result.total
    print(f"   Reaction roll: {reaction_result}")

    # Interpret reaction
    if reaction_roll <= 2:
        reaction = "Hostile, attacks"
    elif reaction_roll <= 5:
        reaction = "Unfriendly, may attack"
    elif reaction_roll <= 8:
        reaction = "Neutral, uncertain"
    elif reaction_roll <= 11:
        reaction = "Indifferent, uninterested"
    else:
        reaction = "Friendly, helpful"
    print(f"   Reaction: {reaction}")

    print("\n4. Simulating conversation...")
    print("   (Social interaction engine would manage dialogue, information exchange)")
    print("   Topics: Local rumors, directions, services, quests")

    print("\n5. Ending conversation...")
    dm.controller.transition("conversation_end_settlement")
    print(f"   New state: {dm.current_state.value}")

    # Return to wilderness
    dm.controller.transition("exit_settlement")
    print(f"   Final state: {dm.current_state.value}")

    print("\n" + "=" * 60)
    print("Social Interaction Loop Test Complete")
    print("=" * 60)


# =============================================================================
# ARGUMENT PARSING
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Dolmenwood Virtual DM - A procedural companion for solo TTRPG play",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                          # Run interactive mode
  python -m src.main --test-hex               # Test hex exploration loop
  python -m src.main --test-combat            # Test combat loop
  python -m src.main --campaign my_campaign   # Load specific campaign
  python -m src.main --llm-provider anthropic # Use Anthropic for descriptions
        """
    )

    # General options
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory for game data storage (default: data)",
    )
    parser.add_argument(
        "--campaign",
        type=str,
        default="default",
        help="Campaign name to load/create (default: default)",
    )
    parser.add_argument(
        "--dm-style",
        type=str,
        default="standard",
        choices=["standard", "verbose", "terse", "atmospheric"],
        help="DM narration style (default: standard)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # LLM options
    llm_group = parser.add_argument_group("LLM Options")
    llm_group.add_argument(
        "--llm-provider",
        type=str,
        default="mock",
        choices=["mock", "anthropic", "openai", "local"],
        help="LLM provider for descriptions (default: mock)",
    )
    llm_group.add_argument(
        "--llm-model",
        type=str,
        help="Specific model to use (provider-dependent)",
    )
    llm_group.add_argument(
        "--llm-url",
        type=str,
        help="URL for local LLM server",
    )

    # Database options
    db_group = parser.add_argument_group("Database Options")
    db_group.add_argument(
        "--no-vector-db",
        action="store_true",
        help="Disable vector database for content search",
    )
    db_group.add_argument(
        "--mock-embeddings",
        action="store_true",
        help="Use mock embeddings (for testing)",
    )
    db_group.add_argument(
        "--local-embeddings",
        action="store_true",
        help="Use local embedding model",
    )
    db_group.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Skip content indexing on startup",
    )

    # Content options
    content_group = parser.add_argument_group("Content Options")
    content_group.add_argument(
        "--content-dir",
        type=Path,
        help="Directory containing game content files",
    )
    content_group.add_argument(
        "--ingest-pdf",
        type=Path,
        help="PDF file to ingest into content database",
    )
    content_group.add_argument(
        "--load-content",
        action="store_true",
        help="Load content from database on startup",
    )

    # Test loop options
    test_group = parser.add_argument_group("Test Loop Options")
    test_group.add_argument(
        "--test-hex",
        action="store_true",
        help="Test the hex exploration/wilderness travel loop",
    )
    test_group.add_argument(
        "--test-encounter",
        action="store_true",
        help="Test the encounter resolution loop",
    )
    test_group.add_argument(
        "--test-dungeon",
        action="store_true",
        help="Test the dungeon exploration loop",
    )
    test_group.add_argument(
        "--test-combat",
        action="store_true",
        help="Test the combat loop",
    )
    test_group.add_argument(
        "--test-settlement",
        action="store_true",
        help="Test the settlement exploration loop",
    )
    test_group.add_argument(
        "--test-social",
        action="store_true",
        help="Test the social interaction loop",
    )
    test_group.add_argument(
        "--test-all",
        action="store_true",
        help="Run all loop tests",
    )

    return parser.parse_args()


def create_config_from_args(args: argparse.Namespace) -> GameConfig:
    """Create GameConfig from parsed arguments."""
    return GameConfig(
        data_dir=args.data_dir,
        campaign_name=args.campaign,
        dm_style=args.dm_style,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_url=args.llm_url,
        use_vector_db=not args.no_vector_db,
        mock_embeddings=args.mock_embeddings,
        local_embeddings=args.local_embeddings,
        skip_indexing=args.skip_indexing,
        content_dir=args.content_dir,
        ingest_pdf=args.ingest_pdf,
        load_content=args.load_content,
        verbose=args.verbose,
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI usage."""
    args = parse_arguments()
    setup_logging(args.verbose)

    print("=" * 60)
    print("DOLMENWOOD VIRTUAL DM v0.1.0")
    print("A procedural companion for solo TTRPG play")
    print("=" * 60)

    # Create configuration
    config = create_config_from_args(args)

    # Check for PDF ingestion
    if args.ingest_pdf:
        print(f"\nPDF ingestion requested: {args.ingest_pdf}")
        print("(PDF ingestion would process the file into the content database)")
        # TODO: Implement PDF ingestion when content system is ready

    # Create demo session
    dm = create_demo_session(config)

    # Check for test loop modes
    test_any = (
        args.test_hex or args.test_encounter or args.test_dungeon or
        args.test_combat or args.test_settlement or args.test_social or
        args.test_all
    )

    if test_any:
        print("\nRunning loop tests...\n")

        if args.test_hex or args.test_all:
            test_hex_exploration_loop(dm)
            dm = create_demo_session(config)  # Reset for next test

        if args.test_encounter or args.test_all:
            test_encounter_loop(dm)
            dm = create_demo_session(config)

        if args.test_dungeon or args.test_all:
            test_dungeon_exploration_loop(dm)
            dm = create_demo_session(config)

        if args.test_combat or args.test_all:
            test_combat_loop(dm)
            dm = create_demo_session(config)

        if args.test_settlement or args.test_all:
            test_settlement_loop(dm)
            dm = create_demo_session(config)

        if args.test_social or args.test_all:
            test_social_interaction_loop(dm)

        print("\n" + "=" * 60)
        print("All requested loop tests complete!")
        print("=" * 60)
    else:
        # Display initial status
        print(dm.status())

        # Run interactive CLI
        cli = DolmenwoodCLI(dm)
        cli.run()

    return dm


if __name__ == "__main__":
    main()
