"""
Hex Crawl Engine for Dolmenwood Virtual DM.

Implements Dolmenwood wilderness travel using daily Travel Points, terrain
costs, getting lost checks, and daily encounter checks.

Daily travel loop (per Campaign Book travel rules):
1. Weather already set on WorldState
2. Choose course (destination hex/route type)
3. Getting lost check (terrain dependent; none on roads, 1-in-6 on tracks)
4. Wandering monster check once per travel day (terrain-based chance)
5. Spend Travel Points to enter/search hexes; log descriptions
6. End of day: if still in wild, camp and carry over any partial entry cost
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import logging

from src.game_state.state_machine import GameState
from src.game_state.global_controller import GlobalController
from src.game_state.condition_parser import check_acquisition_condition
from src.data_models import (
    DiceRoller,
    EncounterState,
    EncounterType,
    SurpriseStatus,
    ReactionResult,
    TerrainType,
    Weather,
    LocationType,
    HexLocation,
    Season,
    TimeOfDay,
    MovementCalculator,
    MovementMode,
    CharacterState,
    PointOfInterest,
    HexStateChange,
    WorldStateChanges,
    EventScheduler,
    ScheduledEvent,
    EventType,
    GameDate,
    AbilityGrantTracker,
    GrantedAbility,
    AbilityType,
    Combatant,
    KnownTopic,
    SecretInfo,
    SecretStatus,
    FactionState,
    FactionRelationship,
)
from src.content_loader.monster_registry import get_monster_registry

# Import narrative components (optional, may not be initialized yet)
try:
    from src.narrative.narrative_resolver import (
        NarrativeResolver,
        ResolutionResult,
        NarrationContext,
        DivingState,
    )
    from src.narrative.hazard_resolver import HazardResolver, HazardType, HazardResult
    from src.narrative.intent_parser import ActionType

    NARRATIVE_AVAILABLE = True
except ImportError:
    NARRATIVE_AVAILABLE = False
    NarrativeResolver = None
    ResolutionResult = None
    NarrationContext = None
    DivingState = None
    HazardResolver = None
    HazardType = None
    HazardResult = None
    ActionType = None


logger = logging.getLogger(__name__)


# =============================================================================
# POI EXPLORATION STATE
# =============================================================================


class POIExplorationState(str, Enum):
    """State of POI exploration within a hex."""

    DISTANT = "distant"  # Visible from afar
    APPROACHING = "approaching"  # Moving toward POI
    AT_ENTRANCE = "at_entrance"  # At the entrance
    INSIDE = "inside"  # Exploring interior
    LEAVING = "leaving"  # Departing


@dataclass
class POIVisit:
    """Tracks a visit to a point of interest."""

    poi_name: str
    state: POIExplorationState = POIExplorationState.DISTANT
    entered: bool = False
    rooms_explored: list[str] = field(default_factory=list)
    npcs_encountered: list[str] = field(default_factory=list)
    items_found: list[str] = field(default_factory=list)
    items_taken: list[str] = field(default_factory=list)  # Items picked up
    secrets_discovered: list[str] = field(default_factory=list)  # Secrets found here
    time_spent_turns: int = 0


@dataclass
class SecretCheck:
    """Result of checking for a secret."""

    secret_name: str
    found: bool
    ability_used: str  # e.g., "INT", "WIS", "perception"
    roll_result: Optional[int] = None
    dc: int = 10
    description: Optional[str] = None


@dataclass
class HexMagicalEffects:
    """
    Magical effects active in a hex or POI.

    Based on Dolmenwood lore - areas like the Falls of Naon
    may have anti-teleportation effects.
    """

    no_teleportation: bool = False
    no_scrying: bool = False
    no_divination: bool = False
    no_summoning: bool = False
    wild_magic_zone: bool = False
    fairy_realm_overlay: bool = False
    enhanced_healing: bool = False
    suppressed_magic: bool = False
    custom_effects: list[str] = field(default_factory=list)


@dataclass
class HexOverview:
    """
    Player-facing overview of a hex.

    Contains only information the characters would perceive,
    without meta-information like hex IDs or location names.
    """

    # What the characters see
    terrain_description: str
    atmosphere: str  # Weather/time of day mood
    visible_features: list[str]  # Obvious landscape features

    # Visible points of interest (without revealing hidden ones)
    visible_locations: list[dict[str, Any]]

    # Travel information
    terrain_difficulty: str  # Easy/Moderate/Difficult
    travel_points_to_cross: int

    # Current conditions
    is_night: bool
    weather_effects: Optional[str]

    # Special time-of-day observations
    time_specific_observations: list[str]


class RouteType(str, Enum):
    """Travel context."""

    ROAD = "road"
    TRACK = "track"
    WILD = "wild"


@dataclass
class TerrainInfo:
    """Dolmenwood travel data per terrain category."""

    terrain_type: TerrainType
    travel_point_cost: int  # points to enter/search hex
    lost_chance: int  # X-in-6
    encounter_chance: int  # X-in-6
    mount_allowed: bool
    vehicle_allowed: bool
    description: str = ""


# Terrain definitions per Dolmenwood Campaign Book p156-157
TERRAIN_DATA: dict[TerrainType, TerrainInfo] = {
    # ==========================================================================
    # LIGHT TERRAIN - 2 TP, 1-in-6 lost/encounter, mounts and vehicles allowed
    # ==========================================================================
    TerrainType.FARMLAND: TerrainInfo(
        TerrainType.FARMLAND,
        travel_point_cost=2,
        lost_chance=1,
        encounter_chance=1,
        mount_allowed=True,
        vehicle_allowed=True,
        description="Tilled fields and lanes",
    ),
    TerrainType.FUNGAL_FOREST: TerrainInfo(
        TerrainType.FUNGAL_FOREST,
        travel_point_cost=2,
        lost_chance=1,
        encounter_chance=1,
        mount_allowed=True,
        vehicle_allowed=True,
        description="Giant fungi, few trees",
    ),
    TerrainType.HILLS: TerrainInfo(
        TerrainType.HILLS,
        travel_point_cost=2,
        lost_chance=1,
        encounter_chance=1,
        mount_allowed=True,
        vehicle_allowed=True,
        description="Undulating grassland",
    ),
    TerrainType.MEADOW: TerrainInfo(
        TerrainType.MEADOW,
        travel_point_cost=2,
        lost_chance=1,
        encounter_chance=1,
        mount_allowed=True,
        vehicle_allowed=True,
        description="Flat grassland",
    ),
    TerrainType.OPEN_FOREST: TerrainInfo(
        TerrainType.OPEN_FOREST,
        travel_point_cost=2,
        lost_chance=1,
        encounter_chance=1,
        mount_allowed=True,
        vehicle_allowed=True,
        description="Light, airy woods",
    ),
    # ==========================================================================
    # MODERATE TERRAIN - 3 TP, 2-in-6 lost/encounter, mounts led, no vehicles
    # ==========================================================================
    TerrainType.BOG: TerrainInfo(
        TerrainType.BOG,
        travel_point_cost=3,
        lost_chance=2,
        encounter_chance=2,
        mount_allowed=True,  # Must be led, not ridden
        vehicle_allowed=False,
        description="Treeless mire",
    ),
    TerrainType.HILLY_FOREST: TerrainInfo(
        TerrainType.HILLY_FOREST,
        travel_point_cost=3,
        lost_chance=2,
        encounter_chance=2,
        mount_allowed=True,  # Must be led, not ridden
        vehicle_allowed=False,
        description="Undulating woods",
    ),
    TerrainType.TANGLED_FOREST: TerrainInfo(
        TerrainType.TANGLED_FOREST,
        travel_point_cost=3,
        lost_chance=2,
        encounter_chance=2,
        mount_allowed=True,  # Must be led, not ridden
        vehicle_allowed=False,
        description="Dense, gloomy woods",
    ),
    # ==========================================================================
    # DIFFICULT TERRAIN - 4 TP, 3-in-6 lost/encounter, no mounts or vehicles
    # ==========================================================================
    TerrainType.BOGGY_FOREST: TerrainInfo(
        TerrainType.BOGGY_FOREST,
        travel_point_cost=4,
        lost_chance=3,
        encounter_chance=3,
        mount_allowed=False,
        vehicle_allowed=False,
        description="Wet, muddy woods",
    ),
    TerrainType.CRAGGY_FOREST: TerrainInfo(
        TerrainType.CRAGGY_FOREST,
        travel_point_cost=4,
        lost_chance=3,
        encounter_chance=3,
        mount_allowed=False,
        vehicle_allowed=False,
        description="Broken terrain, cliffs",
    ),
    TerrainType.SWAMP: TerrainInfo(
        TerrainType.SWAMP,
        travel_point_cost=4,
        lost_chance=3,
        encounter_chance=3,
        mount_allowed=False,
        vehicle_allowed=False,
        description="Wetland, sparse trees",
    ),
    TerrainType.THORNY_FOREST: TerrainInfo(
        TerrainType.THORNY_FOREST,
        travel_point_cost=4,
        lost_chance=3,
        encounter_chance=3,
        mount_allowed=False,
        vehicle_allowed=False,
        description="Dense thorn thickets",
    ),
    # ==========================================================================
    # SPECIAL - Settlements don't use standard terrain rules
    # ==========================================================================
    TerrainType.SETTLEMENT: TerrainInfo(
        TerrainType.SETTLEMENT,
        travel_point_cost=2,
        lost_chance=0,
        encounter_chance=0,
        mount_allowed=True,
        vehicle_allowed=True,
        description="Settled area",
    ),
}


@dataclass
class TravelSegmentResult:
    """Result of processing one travel segment per Dolmenwood rules (p156-157)."""

    success: bool
    travel_points_spent: int
    remaining_travel_points: int
    encounter_occurred: bool
    encounter: Optional[EncounterState] = None
    destination_hex: str = ""
    actual_hex: str = ""  # May differ if lost
    lost_today: bool = False
    weather_effect: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    # Mount/vehicle restrictions (p157)
    mount_restriction: Optional[str] = None
    vehicle_restriction: Optional[str] = None
    # Player-facing hex description (no meta info like hex IDs)
    hex_overview: Optional[HexOverview] = None
    # First time entering this hex?
    first_visit: bool = False


@dataclass
class TravelDayState:
    """
    Tracks travel state for a single day per Dolmenwood rules (p146-147, p156).

    Travel Points per day = Speed ÷ 5 (p147):
    - Speed 40 (mounted): 8 TP normal, 12 TP forced march
    - Speed 30 (cart/wagon): 6 TP normal, 9 TP forced march
    - Speed 20 (encumbered): 4 TP normal, 6 TP forced march

    Forced march grants 50% more TP but requires exhaustion checks.
    """

    base_speed: int = 30  # Party base speed (slowest member per p146)
    travel_points_max: int = 6  # TP for the day (speed ÷ 5)
    travel_points_remaining: int = 6
    is_forced_march: bool = False
    days_since_rest: int = 0  # For weekly rest requirement (p157)
    consecutive_forced_marches: int = 0  # For cumulative exhaustion (p156)
    lost_check_made: bool = False  # One lost check per day (p157)
    encounter_check_made: bool = False  # One encounter check per day (p157)


class HexCrawlEngine:
    """
    Engine for wilderness/hex crawl exploration per Dolmenwood rules (p156-157).

    Manages:
    - Daily travel points spending
    - Getting lost checks (per day)
    - Daily wandering encounter checks
    - Weather and terrain effects
    - Hex entry/search costs by terrain
    """

    def __init__(
        self,
        controller: GlobalController,
        narrative_resolver: Optional[NarrativeResolver] = None,
    ):
        """
        Initialize the hex crawl engine.

        Args:
            controller: The global game controller
            narrative_resolver: Optional resolver for player actions (hazards, foraging, etc.)
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Narrative resolution for player actions (climbing, swimming, foraging, etc.)
        self.narrative_resolver = narrative_resolver or NarrativeResolver(controller)

        # Hex data storage (would be populated from content manager)
        self._hex_data: dict[str, HexLocation] = {}

        # Track exploration
        self._explored_hexes: set[str] = set()

        # Travel day state
        self._forced_march: bool = False
        self._travel_points_total: int = 0
        self._travel_points_remaining: int = 0
        self._pending_entry_cost: int = 0
        self._lost_today: bool = False
        self._encounter_checked_today: bool = False
        self._route_type: RouteType = RouteType.WILD

        # Maze/trap hex state - party stuck until lost check succeeds
        self._trapped_in_maze: bool = False
        self._maze_hex_id: Optional[str] = None

        # Current travel state
        self._has_guide: bool = False
        self._has_map: bool = False

        # POI exploration state
        self._current_poi: Optional[str] = None  # Name of POI currently at/in
        self._poi_state: POIExplorationState = POIExplorationState.DISTANT
        self._poi_visits: dict[str, POIVisit] = {}  # hex_id:poi_name -> visit state

        # Secret discovery tracking (global across hexes)
        self._discovered_secrets: set[str] = set()

        # NPC interaction tracking
        self._met_npcs: set[str] = set()  # NPC IDs we've interacted with

        # World-state change tracking
        self._world_state_changes: WorldStateChanges = WorldStateChanges()

        # Current exploration context (surface, diving, etc.)
        self._exploration_context: str = "surface"

        # Diving state tracking per character
        self._diving_states: dict[str, DivingState] = {}

        # Scheduled events and invitations
        self._event_scheduler: EventScheduler = EventScheduler()

        # Granted abilities tracker
        self._ability_tracker: AbilityGrantTracker = AbilityGrantTracker()

        # Faction relationship tracking per hex
        self._faction_states: dict[str, FactionState] = {}

        # Callbacks for external systems (like LLM description requests)
        self._description_callback: Optional[Callable] = None

        # Register hook to process hunting results when combat ends
        self._register_combat_exit_hook()

    def _register_combat_exit_hook(self) -> None:
        """Register a hook to process hunting rations when combat ends."""
        from src.game_state.state_machine import GameState

        def on_exit_combat(
            from_state: GameState,
            to_state: GameState,
            trigger: str,
            context: dict[str, Any],
        ) -> None:
            """Process hunting combat results before encounter is cleared."""
            self._process_hunting_combat_result(context)

        self.controller.register_on_exit_hook(GameState.COMBAT, on_exit_combat)

    def _process_hunting_combat_result(self, combat_context: dict[str, Any]) -> None:
        """
        Process the result of a hunting combat and add rations to inventory.

        Per Campaign Book p120-121:
        - Calculate rations based on HP of killed animals
        - Small: 1 ration/HP, Medium: 2 rations/HP, Large: 4 rations/HP
        - Add rations to party inventory

        Args:
            combat_context: Context from combat end transition
        """
        # Get the encounter before it's cleared
        encounter = self.controller.get_encounter()
        if not encounter:
            return

        # Check if this was a hunting encounter
        contextual_data = encounter.contextual_data
        if not contextual_data or contextual_data.get("source") != "hunting":
            return

        # Get hunting data
        game_animal_data = contextual_data.get("game_animal")
        hex_id = contextual_data.get("hex_id")

        if not game_animal_data:
            return

        # Calculate total HP killed from defeated enemy combatants
        total_hp_killed = 0
        for combatant in encounter.combatants:
            if combatant.is_enemy and not combatant.is_active:
                # Combatant was defeated - add their max HP
                total_hp_killed += combatant.hp_max

        if total_hp_killed <= 0:
            # No animals were killed, no rations
            return

        # Import hunting table functions
        from src.tables.hunting_tables import (
            GAME_ANIMALS,
            AnimalSize,
            hunting_to_rations_item,
        )

        # Get the GameAnimal instance
        monster_id = game_animal_data.get("monster_id")
        if monster_id and monster_id in GAME_ANIMALS:
            animal = GAME_ANIMALS[monster_id]
        else:
            # Fallback: create a temporary GameAnimal from the data
            from src.tables.hunting_tables import GameAnimal
            size_str = game_animal_data.get("size", "medium")
            size = AnimalSize(size_str) if size_str in [s.value for s in AnimalSize] else AnimalSize.MEDIUM
            animal = GameAnimal(
                name=game_animal_data.get("name", "Game Animal"),
                monster_id=monster_id or "unknown",
                size=size,
                number_appearing="1",
                description=game_animal_data.get("description", ""),
            )

        # Create rations item
        rations_item = hunting_to_rations_item(
            animal=animal,
            total_hp_killed=total_hp_killed,
            source_hex=hex_id,
        )

        if not rations_item:
            return

        # Add rations to party leader's inventory (or first available character)
        party_leader = self._state.party_leader if self._state else None
        if not party_leader:
            # Get first party member
            characters = list(self.controller._characters.values())
            if characters:
                party_leader = characters[0].character_id

        if party_leader:
            character = self.controller.get_character(party_leader)
            if character:
                character.inventory.append(rations_item)

                # Log the rations gained
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    f"Hunting yielded {rations_item.quantity} rations of {animal.name} meat "
                    f"(from {total_hp_killed} HP killed) - added to {character.name}'s inventory"
                )

    def set_has_guide(self, has_guide: bool) -> None:
        """Set whether party has a local guide."""
        self._has_guide = has_guide

    def set_has_map(self, has_map: bool) -> None:
        """Set whether party has a map."""
        self._has_map = has_map

    def register_description_callback(self, callback: Callable) -> None:
        """Register callback for requesting LLM descriptions."""
        self._description_callback = callback

    def load_hex_data(self, hex_id: str, data: HexLocation) -> None:
        """Load hex data into the engine."""
        self._hex_data[hex_id] = data

    def get_hex_data(self, hex_id: str) -> Optional[HexLocation]:
        """Get hex data if available."""
        return self._hex_data.get(hex_id)

    def _get_hex_data(self, hex_id: str) -> Optional[HexLocation]:
        """Internal alias for get_hex_data (used by internal methods)."""
        return self.get_hex_data(hex_id)

    def get_terrain_for_hex(self, hex_id: str) -> TerrainType:
        """Get terrain type for a hex."""
        hex_data = self._hex_data.get(hex_id)
        if hex_data:
            return TerrainType(hex_data.terrain)
        return TerrainType.OPEN_FOREST  # Default

    def get_terrain_info(self, terrain: TerrainType) -> TerrainInfo:
        """Get terrain information."""
        return TERRAIN_DATA.get(terrain, TERRAIN_DATA[TerrainType.OPEN_FOREST])

    # =========================================================================
    # MAIN TRAVEL LOOP (p156-157)
    # =========================================================================

    def travel_to_hex(
        self,
        destination_hex: str,
        route_type: RouteType = RouteType.WILD,
        terrain_override: Optional[TerrainType] = None,
        forced_march: bool = False,
    ) -> TravelSegmentResult:
        """
        Spend Travel Points to enter an adjacent hex per Dolmenwood rules.

        Args:
            destination_hex: Target hex ID
            route_type: Road, track, or wild travel
            terrain_override: Override terrain type (for special situations)
            forced_march: Use forced march Travel Points for the day

        Returns:
            TravelSegmentResult with all outcomes
        """
        if self.controller.current_state != GameState.WILDERNESS_TRAVEL:
            return TravelSegmentResult(
                success=False,
                travel_points_spent=0,
                remaining_travel_points=self._travel_points_remaining,
                encounter_occurred=False,
                warnings=["Not in WILDERNESS_TRAVEL state"],
                destination_hex=destination_hex,
                actual_hex=destination_hex,
            )

        # Check if trapped in maze hex - cannot leave until lost check succeeds
        if self._trapped_in_maze:
            current_hex = self.controller.party_state.location.location_id
            if current_hex == self._maze_hex_id:
                return TravelSegmentResult(
                    success=False,
                    travel_points_spent=0,
                    remaining_travel_points=0,
                    encounter_occurred=False,
                    warnings=[
                        "Party is trapped in a maze and must wait for next day's navigation check"
                    ],
                    destination_hex=destination_hex,
                    actual_hex=current_hex,
                )

        # Initialize day if not already done
        if self._travel_points_total == 0 or forced_march != self._forced_march:
            self._start_travel_day(forced_march, route_type)

        result = TravelSegmentResult(
            success=True,
            travel_points_spent=0,
            remaining_travel_points=self._travel_points_remaining,
            encounter_occurred=False,
            destination_hex=destination_hex,
            actual_hex=destination_hex,
            lost_today=self._lost_today,
        )

        terrain = terrain_override or self.get_terrain_for_hex(destination_hex)
        terrain_info = self.get_terrain_info(terrain)

        # Determine cost based on route type
        cost = (
            2 if route_type in {RouteType.ROAD, RouteType.TRACK} else terrain_info.travel_point_cost
        )

        # Apply pending cost carry-over
        if self._pending_entry_cost > 0:
            cost = self._pending_entry_cost

        # Spend travel points
        if self._travel_points_remaining < cost:
            # Not enough points; spend what remains and carry over
            result.travel_points_spent = self._travel_points_remaining
            self._pending_entry_cost = cost - self._travel_points_remaining
            self._travel_points_remaining = 0
            result.remaining_travel_points = 0
            result.messages.append(
                f"Not enough Travel Points to enter hex. {self._pending_entry_cost} needed next day."
            )
            return result

        self._travel_points_remaining -= cost
        result.travel_points_spent = cost
        result.remaining_travel_points = self._travel_points_remaining
        self._pending_entry_cost = 0

        # Apply lost result once per day when leaving course
        if self._lost_today:
            result.actual_hex = self._get_random_adjacent_hex(destination_hex)
            result.warnings.append("The party is lost and strays into another hex.")

        # Daily encounter check (only once per day)
        if not self._encounter_checked_today:
            encounter_roll = self._check_encounter(terrain_info, route_type, result.actual_hex)
            self._encounter_checked_today = True
            if encounter_roll:
                result.encounter_occurred = True
                result.encounter = self._generate_encounter(result.actual_hex, terrain)

                # Transition to unified ENCOUNTER state
                self.controller.transition(
                    "encounter_triggered",
                    context={
                        "hex_id": result.actual_hex,
                        "terrain": terrain.value,
                        "encounter_type": result.encounter.encounter_type.value,
                        "source": "wilderness_travel",
                    },
                )
                result.messages.append("Encounter!")

        # Update party location if no active encounter
        if not result.encounter_occurred:
            self.controller.set_party_location(LocationType.HEX, result.actual_hex)

        # Check if this is first visit
        first_visit = result.actual_hex not in self._explored_hexes
        result.first_visit = first_visit

        # Mark hex as explored
        self._explored_hexes.add(result.actual_hex)

        # Weather and terrain notes
        weather = self.controller.world_state.weather
        weather_effect = self._apply_weather_effects(weather)
        if weather_effect:
            result.weather_effect = weather_effect
            result.messages.append(f"Weather: {weather_effect}")

        # Get hex overview for player-facing description (no hex IDs or names)
        result.hex_overview = self.get_hex_overview(result.actual_hex)

        # Clear any previous POI state when entering a new hex
        if first_visit or result.actual_hex != destination_hex:
            self._current_poi = None
            self._poi_state = POIExplorationState.DISTANT

        # Request description if callback registered
        if self._description_callback and not result.encounter_occurred:
            self._description_callback(
                location=result.actual_hex,
                terrain=terrain.value,
                weather=weather.value,
                time_of_day=self.controller.time_tracker.game_time.get_time_of_day().value,
            )

        return result

    def _start_travel_day(self, forced_march: bool, route_type: RouteType) -> None:
        """
        Initialize daily travel points, lost and encounter checks.

        Per Dolmenwood rules (p146-147):
        - Party speed = slowest member's speed
        - Travel Points = Speed ÷ 5
        - Forced march = 50% more TP
        """
        self._forced_march = forced_march
        self._route_type = route_type

        # Get party speed from slowest member (p146)
        party_speed = self._get_party_speed()

        # Calculate Travel Points per day using MovementCalculator (p147)
        if forced_march:
            self._travel_points_total = MovementCalculator.get_forced_march_travel_points(
                party_speed
            )
        else:
            self._travel_points_total = MovementCalculator.get_travel_points(party_speed)

        self._travel_points_remaining = self._travel_points_total
        self._pending_entry_cost = self._pending_entry_cost  # carry-over from prior day
        self._encounter_checked_today = False

        # Get current hex data for lost chance and maze behavior
        current_hex = self.controller.party_state.location.location_id
        hex_data = self._get_hex_data(current_hex)

        # Determine lost chance
        lost_chance = 0
        if route_type == RouteType.TRACK:
            lost_chance = 1
        elif route_type == RouteType.WILD:
            terrain = self.get_terrain_for_hex(current_hex)
            lost_chance = self.get_terrain_info(terrain).lost_chance

        # Check hex-specific lost_chance override
        if hex_data and hex_data.procedural and hex_data.procedural.lost_chance:
            lost_chance = self._parse_x_in_6_chance(hex_data.procedural.lost_chance)

        # Visibility modifiers could increase lost_chance; handled externally if needed
        if lost_chance > 0:
            nav_roll = self.dice.roll_d6(1, "lost check")
            self._lost_today = nav_roll.total <= lost_chance
        else:
            self._lost_today = False

        # Handle maze/trap hex behavior
        if self._trapped_in_maze and current_hex == self._maze_hex_id:
            if self._lost_today:
                # Still lost - remain trapped in maze
                self._travel_points_remaining = 0  # Entire day spent wandering
                return {
                    "maze_trapped": True,
                    "hex_id": current_hex,
                    "message": "The party wanders in circles through the maze, unable to find a way out.",
                    "travel_points": 0,
                }
            else:
                # Escaped the maze!
                self._trapped_in_maze = False
                self._maze_hex_id = None
                # Note: Travel points remain available for normal travel

        # Check if getting lost in a maze hex
        if self._lost_today and hex_data and hex_data.procedural:
            lost_behavior = hex_data.procedural.lost_behavior
            if lost_behavior and lost_behavior.get("type") == "maze":
                self._trapped_in_maze = True
                self._maze_hex_id = current_hex
                self._travel_points_remaining = 0  # Entire day spent wandering
                return {
                    "maze_trapped": True,
                    "hex_id": current_hex,
                    "message": lost_behavior.get(
                        "description",
                        "The party becomes lost in the labyrinthine terrain, spending the day wandering in circles.",
                    ),
                    "travel_points": 0,
                }

    def _get_party_speed(self) -> int:
        """
        Get party movement speed per Dolmenwood rules (p146, p148-149).

        Party speed is determined by the slowest member's encumbered speed.

        Returns:
            Party movement speed in feet (encumbrance-adjusted)
        """
        # Get encumbrance-adjusted party speed from controller
        return self.controller.get_party_speed()

    def _check_encounter(
        self,
        terrain_info: TerrainInfo,
        route_type: RouteType,
        hex_id: Optional[str] = None,
    ) -> bool:
        """
        Daily wandering monster check based on terrain and route.

        Args:
            terrain_info: Terrain information for the hex
            route_type: Type of route being traveled
            hex_id: Optional hex ID for faction modifier lookup

        Returns:
            True if an encounter occurs
        """
        if route_type == RouteType.ROAD:
            return False

        chance = terrain_info.encounter_chance

        # Apply faction standing modifier if available
        if hex_id:
            faction_modifier = self._get_faction_encounter_modifier(hex_id)
            chance = max(0, min(6, chance + faction_modifier))

        roll = self.dice.roll_d6(1, "wandering encounter")
        return roll.total <= chance

    def _get_faction_encounter_modifier(self, hex_id: str) -> int:
        """
        Get encounter probability modifier based on faction control of hex.

        Good standing with the controlling faction reduces encounter chance.
        Bad standing increases encounter chance.

        Args:
            hex_id: The hex identifier

        Returns:
            Modifier to add to encounter chance (-2 to +2)
        """
        try:
            # Access faction engine via controller's dm reference
            dm = getattr(self.controller, "dm", None)
            if not dm:
                return 0

            factions = getattr(dm, "factions", None)
            if not factions:
                return 0

            from src.factions.faction_hooks import HexFactionLookup, get_encounter_modifier

            lookup = HexFactionLookup(factions)
            standing = lookup.get_standing_for_hex(hex_id)
            return get_encounter_modifier(standing)
        except Exception:
            # Fail silently - faction system is optional
            return 0

    def _generate_encounter(self, hex_id: str, terrain: TerrainType) -> EncounterState:
        """
        Generate an encounter for the current hex per Dolmenwood rules (p157).

        Uses encounter tables from the Campaign Book, modified by contextual
        encounter modifiers from nearby POIs (e.g., "2-in-6 likely to be a
        bewildered banshee heading to a ball at the Spectral Manse").
        """
        # Check for contextual encounter modifiers from POIs in this hex
        contextual_result = self._apply_contextual_encounter_modifiers(hex_id)

        # Determine surprise first (affects distance)
        surprise = self._check_surprise()

        # Determine distance based on surprise (p157)
        distance = self._roll_encounter_distance(surprise)

        # Create encounter state
        if contextual_result:
            # Use the contextual encounter - create proper combatants if monster_id provided
            modifier = contextual_result.get("modifier", {})
            monster_id = modifier.get("monster_id")
            combatants = []

            if monster_id:
                # Create combatant(s) from monster registry
                num_appearing = modifier.get("number_appearing", 1)
                combatants = self._create_contextual_combatants(
                    monster_id=monster_id,
                    num_appearing=num_appearing,
                    modifier=modifier,
                )

            encounter = EncounterState(
                encounter_type=EncounterType.MONSTER,
                distance=distance,
                surprise_status=surprise,
                terrain=terrain.value,
                context=contextual_result.get("context", ""),
                actors=[contextual_result.get("result", "unknown creature")],
                combatants=combatants,
            )

            # Store topic intelligence for social interaction use
            if modifier.get("topic_intelligence"):
                encounter.contextual_data = {
                    "topic_intelligence": modifier.get("topic_intelligence"),
                    "behavior": modifier.get("behavior", "neutral"),
                    "demeanor": modifier.get("demeanor", []),
                    "speech": modifier.get("speech", ""),
                }
        else:
            # Standard encounter - use encounter tables via factory
            from src.encounter.encounter_factory import start_wilderness_encounter

            # Get hex data for region
            hex_data = self._get_hex_data(hex_id)
            region = hex_data.region.lower().replace(" ", "_") if hex_data and hex_data.region else "tithelands"

            # Determine context for encounter
            is_night = self._is_night()
            on_road = self._route_type in (RouteType.ROAD, RouteType.TRACK)

            try:
                result = start_wilderness_encounter(
                    controller=self.controller,
                    region=region,
                    terrain=terrain.value,
                    is_day=not is_night,
                    on_road=on_road,
                    hex_id=hex_id,
                )
                encounter = result["encounter_state"]
            except Exception as e:
                # Fallback to basic encounter if factory fails
                logger.warning(f"Encounter factory failed, using fallback: {e}")
                encounter = EncounterState(
                    encounter_type=EncounterType.MONSTER,
                    distance=distance,
                    surprise_status=surprise,
                    terrain=terrain.value,
                    context=self._determine_encounter_context(),
                )

        self.controller.set_encounter(encounter)
        return encounter

    def _apply_contextual_encounter_modifiers(self, hex_id: str) -> Optional[dict[str, Any]]:
        """
        Check hex-level and POI-level contextual encounter modifiers.

        Hex-level modifiers are checked first (from procedural.encounter_modifiers),
        then POI-level modifiers. For example, hex 0101 has:
        "Encounters are 2-in-6 likely to be with a bewildered banshee
        heading to a ball at the Spectral Manse"

        Args:
            hex_id: The current hex ID

        Returns:
            Dictionary with contextual encounter details if triggered, None otherwise
        """
        hex_data = self._get_hex_data(hex_id)
        if not hex_data:
            return None

        # First check hex-level encounter modifiers (procedural.encounter_modifiers)
        if hex_data.procedural and hex_data.procedural.encounter_modifiers:
            for modifier in hex_data.procedural.encounter_modifiers:
                chance_str = modifier.get("chance", "")
                chance = self._parse_x_in_6_chance(chance_str)

                if chance > 0:
                    roll = self.dice.roll_d6(1, f"hex contextual encounter: {hex_id}")
                    if roll.total <= chance:
                        return {
                            "triggered": True,
                            "source": "hex",
                            "hex_id": hex_id,
                            "result": modifier.get("result", "unknown creature"),
                            "context": modifier.get("context", ""),
                            "modifier": modifier,
                        }

        # Then check each POI for encounter modifiers
        for poi in hex_data.points_of_interest:
            for modifier in poi.encounter_modifiers:
                # Parse the chance (e.g., "2-in-6")
                chance_str = modifier.get("chance", "")
                chance = self._parse_x_in_6_chance(chance_str)

                if chance > 0:
                    roll = self.dice.roll_d6(1, f"POI contextual encounter: {poi.name}")
                    if roll.total <= chance:
                        return {
                            "triggered": True,
                            "source": "poi",
                            "poi_name": poi.name,
                            "result": modifier.get("result", "unknown creature"),
                            "context": modifier.get("context", ""),
                            "modifier": modifier,
                        }

        return None

    def _parse_x_in_6_chance(self, chance_str: str) -> int:
        """
        Parse a chance string like "2-in-6" or "3-in-6" to an integer.

        Args:
            chance_str: String in format "X-in-6"

        Returns:
            Integer value of X, or 0 if parsing fails
        """
        if not chance_str:
            return 0
        try:
            # Handle formats like "2-in-6", "3 in 6", "2/6"
            chance_str = chance_str.lower().strip()
            if "-in-" in chance_str:
                return int(chance_str.split("-in-")[0])
            elif " in " in chance_str:
                return int(chance_str.split(" in ")[0])
            elif "/" in chance_str:
                return int(chance_str.split("/")[0])
            return 0
        except (ValueError, IndexError):
            return 0

    def _create_contextual_combatants(
        self,
        monster_id: str,
        num_appearing: int,
        modifier: dict[str, Any],
    ) -> list[Combatant]:
        """
        Create combatants for a contextual encounter.

        Uses the monster registry to create proper combatants with stat blocks,
        and applies any behavioral modifiers from the encounter definition.

        Args:
            monster_id: ID of the monster in the registry
            num_appearing: Number of creatures to create
            modifier: The encounter modifier dict with behavior, demeanor, etc.

        Returns:
            List of Combatant objects ready for combat or social interaction
        """
        combatants = []
        registry = get_monster_registry()

        for i in range(num_appearing):
            # Try to create combatant from monster registry
            combatant = registry.create_combatant(
                monster_id=monster_id,
                name_override=modifier.get("result") if num_appearing == 1 else None,
            )

            if combatant:
                combatant.side = "enemy"
                # Store contextual behavior for social interaction
                if modifier.get("behavior"):
                    combatant.behavior = modifier.get("behavior")
                combatants.append(combatant)
            else:
                # Fallback: create a basic combatant with the name
                logger.warning(
                    f"Could not find monster '{monster_id}' in registry, "
                    f"creating placeholder combatant"
                )
                from uuid import uuid4

                fallback_name = modifier.get("result", monster_id)
                if num_appearing > 1:
                    fallback_name = f"{fallback_name} #{i + 1}"
                combatants.append(
                    Combatant(
                        combatant_id=f"{monster_id}_{uuid4().hex[:8]}",
                        name=fallback_name,
                        side="enemy",
                        current_hp=1,
                        max_hp=1,
                        armor_class=10,
                        attack_bonus=0,
                        damage="1d4",
                        is_active=True,
                    )
                )

        return combatants

    def _roll_encounter_distance(self, surprise: SurpriseStatus) -> int:
        """
        Roll initial encounter distance per Dolmenwood rules (p157).

        Distance: 2d6 × 30'
        If both sides are surprised: 1d4 × 30'
        """
        if surprise == SurpriseStatus.MUTUAL_SURPRISE:
            return self.dice.roll("1d4", "encounter distance (mutual surprise)").total * 30
        else:
            return self.dice.roll("2d6", "encounter distance").total * 30

    def _check_surprise(self) -> SurpriseStatus:
        """Check for surprise on both sides."""
        party_roll = self.dice.roll_d6(1, "party surprise check")
        enemy_roll = self.dice.roll_d6(1, "enemy surprise check")

        party_threshold = 2
        enemy_threshold = 2

        party_surprised = party_roll.total <= party_threshold
        enemy_surprised = enemy_roll.total <= enemy_threshold

        if party_surprised and enemy_surprised:
            return SurpriseStatus.MUTUAL_SURPRISE
        elif party_surprised:
            return SurpriseStatus.PARTY_SURPRISED
        elif enemy_surprised:
            return SurpriseStatus.ENEMIES_SURPRISED
        return SurpriseStatus.NO_SURPRISE

    def _determine_encounter_context(self) -> str:
        """Determine what the encountered creatures are doing."""
        roll = self.dice.roll_d6(1, "encounter context")
        contexts = {
            1: "traveling",
            2: "hunting",
            3: "foraging",
            4: "resting",
            5: "guarding",
            6: "pursuing something",
        }
        return contexts.get(roll.total, "traveling")

    def _get_random_adjacent_hex(self, intended_hex: str) -> str:
        """Get a random adjacent hex when lost."""
        # Simple implementation - in full version would use hex grid math
        # For now, modify the hex ID slightly
        try:
            col = int(intended_hex[:2])
            row = int(intended_hex[2:])
            direction = self.dice.roll_d6(1, "lost direction").total
            if direction == 1:
                row -= 1
            elif direction == 2:
                col += 1
            elif direction == 3:
                col += 1
                row += 1
            elif direction == 4:
                row += 1
            elif direction == 5:
                col -= 1
            else:
                col -= 1
                row -= 1
            return f"{col:02d}{row:02d}"
        except (ValueError, IndexError):
            return intended_hex

    # =========================================================================
    # DAY MANAGEMENT AND SEARCH
    # =========================================================================

    def end_travel_day(self) -> dict[str, Any]:
        """
        End the travel day, advance time by one day, and reset daily flags.
        """
        time_result = self.controller.advance_time(144)  # 12 hours travel + rest window
        summary = {
            "travel_points_spent": self._travel_points_total - self._travel_points_remaining,
            "travel_points_total": self._travel_points_total,
            "remaining_travel_points": self._travel_points_remaining,
            "pending_entry_cost": self._pending_entry_cost,
            "time_advanced": time_result,
        }

        # Reset daily flags
        self._travel_points_total = 0
        self._travel_points_remaining = 0
        self._encounter_checked_today = False
        self._lost_today = False
        return summary

    def search_hex(
        self, hex_id: str, terrain_override: Optional[TerrainType] = None
    ) -> dict[str, Any]:
        """
        Search a hex for hidden features. Costs Travel Points equal to terrain entry cost.
        """
        terrain = terrain_override or self.get_terrain_for_hex(hex_id)
        terrain_info = self.get_terrain_info(terrain)
        cost = terrain_info.travel_point_cost

        if self._travel_points_remaining < cost:
            return {
                "success": False,
                "travel_points_needed": cost - self._travel_points_remaining,
                "message": "Not enough Travel Points to search hex today.",
            }

        self._travel_points_remaining -= cost

        result = {
            "hex_id": hex_id,
            "features_found": [],
            "lairs_found": [],
            "landmarks_found": [],
            "travel_points_spent": cost,
            "travel_points_remaining": self._travel_points_remaining,
        }

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            result["message"] = "No detailed hex data available"
            return result

        # Search roll for each hidden feature (2-in-6)
        for feature in hex_data.features:
            if getattr(feature, "hidden", False) and not getattr(feature, "discovered", False):
                roll = self.dice.roll_d6(1, f"search for {feature.name}")
                if roll.total >= 5:
                    feature.discovered = True
                    result["features_found"].append(feature.name)

        # Check for lairs (1-in-6)
        for lair in getattr(hex_data, "lairs", []):
            if not getattr(lair, "discovered", False):
                roll = self.dice.roll_d6(1, "find lair")
                if roll.total == 6:
                    lair.discovered = True
                    result["lairs_found"].append(getattr(lair, "monster_type", "lair"))

        # Visible landmarks
        for landmark in getattr(hex_data, "landmarks", []):
            result["landmarks_found"].append(getattr(landmark, "name", "landmark"))

        return result

    def is_hex_explored(self, hex_id: str) -> bool:
        """Check if hex has been explored."""
        return hex_id in self._explored_hexes

    def get_exploration_summary(self) -> dict[str, Any]:
        """Get summary of exploration progress and travel state."""
        return {
            "explored_hexes": list(self._explored_hexes),
            "total_explored": len(self._explored_hexes),
            "current_location": str(self.controller.party_state.location),
            "travel_points_remaining": self._travel_points_remaining,
            "lost_today": self._lost_today,
            "encounter_checked_today": self._encounter_checked_today,
            "has_guide": self._has_guide,
            "has_map": self._has_map,
            # Daily check status
            "lost_check_made": self._travel_day.lost_check_made,
            "encounter_check_made": self._travel_day.encounter_check_made,
            # Maze/trap hex state
            "trapped_in_maze": self._trapped_in_maze,
            "maze_hex_id": self._maze_hex_id,
        }

    # =========================================================================
    # PUBLIC ACCESSORS (for SuggestionBuilder and other consumers)
    # =========================================================================

    def get_travel_points_remaining(self) -> int:
        """Get the number of travel points remaining for the current day."""
        return self._travel_points_remaining

    def get_travel_points_total(self) -> int:
        """Get the total travel points for the current day."""
        return self._travel_points_total

    def get_current_hex_id(self) -> str:
        """Get the current hex ID."""
        return self.controller.party_state.location.location_id

    def _get_veered_hex(self, intended_hex: str) -> str:
        """Get adjacent hex when veered off course."""
        # Similar to lost but only one hex off
        return self._get_random_adjacent_hex(intended_hex)

    def _apply_weather_effects(self, weather: Weather) -> Optional[str]:
        """Apply weather effects and return description."""
        effects = {
            Weather.CLEAR: None,
            Weather.OVERCAST: None,
            Weather.FOG: "Visibility reduced, navigation harder",
            Weather.RAIN: "Movement slowed, tracks washed away",
            Weather.STORM: "Dangerous conditions, seek shelter",
            Weather.SNOW: "Movement slowed, cold damage risk",
            Weather.BLIZZARD: "Extreme danger, must seek shelter",
        }
        return effects.get(weather)

    # =========================================================================
    # PLAYER ACTION HANDLING (via NarrativeResolver)
    # =========================================================================

    def handle_player_action(
        self,
        player_input: str,
        character_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ResolutionResult:
        """
        Handle a player action during wilderness travel via NarrativeResolver.

        This routes non-travel actions to the NarrativeResolver for resolution:
        - Climbing (cliffs, trees, obstacles)
        - Swimming (rivers, lakes)
        - Jumping (ravines, gaps)
        - Foraging, Fishing, Hunting
        - Other environmental hazards

        For travel-specific actions (move to hex, search hex), use the
        dedicated methods like travel_to_hex() and search_hex().

        Args:
            player_input: The player's action description
            character_id: ID of the character performing the action
            context: Optional additional context

        Returns:
            ResolutionResult with outcomes and narration context
        """
        # Get character state
        character = self.controller.get_character(character_id)
        if not character:
            from src.narrative.intent_parser import ActionCategory, ActionType, ParsedIntent

            return ResolutionResult(
                success=False,
                narration_context=NarrationContext(
                    action_category=ActionCategory.UNKNOWN,
                    action_type=ActionType.UNKNOWN,
                    player_input=player_input,
                    success=False,
                    errors=[f"Character not found: {character_id}"],
                ),
                parsed_intent=ParsedIntent(
                    raw_input=player_input,
                    action_category=ActionCategory.UNKNOWN,
                    action_type=ActionType.UNKNOWN,
                ),
            )

        # Build context with wilderness-specific information
        action_context = context or {}
        action_context.update(
            {
                "game_state": "wilderness_travel",
                "current_hex": str(self.controller.party_state.location),
                "terrain": (
                    self.get_terrain_for_hex(str(self.controller.party_state.location)).value
                    if self.controller.party_state
                    else "unknown"
                ),
                "weather": (
                    self.controller.world_state.weather.value
                    if self.controller.world_state
                    else "clear"
                ),
                "season": (
                    self.controller.world_state.season.value
                    if self.controller.world_state
                    else "normal"
                ),
                "time_of_day": (
                    self.controller.world_state.current_time.get_time_of_day().value
                    if self.controller.world_state
                    else "day"
                ),
            }
        )

        # Resolve through NarrativeResolver
        result = self.narrative_resolver.resolve_player_input(
            player_input=player_input,
            character=character,
            context=action_context,
        )

        # Apply any damage from the action
        for target_id, damage in result.apply_damage:
            self.controller.apply_damage(target_id, damage, "environmental")

        # Apply any conditions
        for target_id, condition in result.apply_conditions:
            self.controller.apply_condition(target_id, condition, "narrative_action")

        return result

    def attempt_climb(
        self,
        character_id: str,
        height_feet: int = 10,
        is_trivial: bool = False,
        difficulty: int = 10,
    ) -> HazardResult:
        """
        Attempt to climb an obstacle per Dolmenwood rules (p150).

        Args:
            character_id: ID of the climbing character
            height_feet: Height of the climb in feet
            is_trivial: Whether this is a trivial climb (no roll needed)
            difficulty: DC for the climb check

        Returns:
            HazardResult with outcomes
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.CLIMBING,
                action_type=ActionType.CLIMB,
                description="Character not found",
            )

        from src.narrative.intent_parser import ActionType

        result = self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.CLIMBING,
            character=character,
            height_feet=height_feet,
            is_trivial=is_trivial,
            difficulty=difficulty,
        )

        # Apply any damage from falling
        if result.damage_dealt > 0:
            self.controller.apply_damage(character_id, result.damage_dealt, "falling")

        return result

    def attempt_swim(
        self,
        character_id: str,
        armor_weight: str = "unarmoured",
        rough_waters: bool = False,
        difficulty: int = 10,
    ) -> HazardResult:
        """
        Attempt to swim per Dolmenwood rules (p154).

        Args:
            character_id: ID of the swimming character
            armor_weight: Weight of armor (unarmoured, light, medium, heavy)
            rough_waters: Whether waters are rough/turbulent
            difficulty: DC for the swim check

        Returns:
            HazardResult with outcomes
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.SWIMMING,
                action_type=ActionType.SWIM,
                description="Character not found",
            )

        from src.narrative.intent_parser import ActionType

        return self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.SWIMMING,
            character=character,
            armor_weight=armor_weight,
            rough_waters=rough_waters,
            difficulty=difficulty,
        )

    def attempt_jump(
        self,
        character_id: str,
        distance_feet: int = 5,
        is_high_jump: bool = False,
        has_runup: bool = True,
        armor_weight: str = "unarmoured",
    ) -> HazardResult:
        """
        Attempt a jump per Dolmenwood rules (p153).

        Args:
            character_id: ID of the jumping character
            distance_feet: Distance to jump in feet
            is_high_jump: Whether this is a vertical jump
            has_runup: Whether character has 20' run-up
            armor_weight: Weight of armor

        Returns:
            HazardResult with outcomes
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.JUMPING,
                action_type=ActionType.JUMP,
                description="Character not found",
            )

        from src.narrative.intent_parser import ActionType

        return self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.JUMPING,
            character=character,
            distance_feet=distance_feet,
            is_high_jump=is_high_jump,
            has_runup=has_runup,
            armor_weight=armor_weight,
        )

    def attempt_forage(
        self,
        character_id: str,
        method: str = "foraging",
        full_day: bool = False,
        accept_blessing: bool = False,
    ) -> HazardResult:
        """
        Attempt to find food in the wild per Dolmenwood rules (p152).

        Includes hex-specific foraging_special yields when available.
        For example, hex 0102 yields Sage Toe in addition to normal foraging.

        For fishing (Campaign Book p116-117), this also handles:
        - First-timer dangers (Gurney/Puffer damage)
        - Monster attraction (Screaming jenny triggers wandering monster)
        - Fairy blessings (Queen's salmon offers +4 save bonus if released)

        Args:
            character_id: ID of the foraging character
            method: "foraging", "fishing", or "hunting"
            full_day: Whether spending full day foraging (+2 bonus)
            accept_blessing: Whether to accept a fairy fish blessing (releases fish)

        Returns:
            HazardResult with outcomes including rations found and special yields
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.HUNGER,
                action_type=ActionType.FORAGE,
                description="Character not found",
            )

        # Determine season from world state
        season = "normal"
        if self.controller.world_state:
            if self.controller.world_state.season == Season.WINTER:
                season = "winter"
            elif self.controller.world_state.season == Season.AUTUMN:
                season = "autumn"

        # Get hex-specific foraging special yields
        foraging_special = []
        current_hex = self._state.current_hex
        if current_hex:
            hex_data = self._get_hex_data(current_hex)
            if hex_data and hex_data.procedural and hex_data.procedural.foraging_special:
                foraging_special = hex_data.procedural.foraging_special

        from src.narrative.intent_parser import ActionType

        # Get terrain for hunting tables
        terrain_str = "forest"  # Default
        current_hex = self._state.current_hex
        if current_hex:
            hex_data = self._get_hex_data(current_hex)
            if hex_data:
                terrain_str = hex_data.terrain_type.value if hex_data.terrain_type else "forest"

        result = self.narrative_resolver.hazard_resolver.resolve_foraging(
            character=character,
            method=method,
            season=season,
            full_day=full_day,
            foraging_special=foraging_special,
            terrain=terrain_str,
        )

        # Apply fishing-specific effects (Campaign Book p116-117)
        if method == "fishing" and result.success:
            # Apply damage from first-timer dangers (Gurney, Puffer)
            if result.damage_dealt > 0:
                self.controller.apply_damage(
                    character_id, result.damage_dealt, result.damage_type
                )

            # Apply conditions
            for condition in result.conditions_applied:
                self.controller.apply_condition(character_id, condition, "fishing")

            # Handle fairy fish blessing (Queen's salmon)
            if result.blessing_offered and accept_blessing:
                # Player chose to release the fish for the blessing
                # Add the save bonus (+4 to next save vs deadly effect)
                blessing_bonus = 4  # Default Queen's salmon bonus
                fish_name = result.fish_caught.get("name", "fairy fish")
                for event in result.catch_events:
                    if event.get("type") == "blessing_offered":
                        blessing_bonus = event.get("bonus", 4)
                        break

                # Apply the blessing as a temporary save bonus
                character.add_save_bonus(
                    save_category="deadly",
                    bonus=blessing_bonus,
                    source=fish_name,
                    one_time=True,
                )

                # Fish was released, no rations gained
                result.rations_found = 0
                result.description = (
                    f"Released the {fish_name} in exchange for its blessing! "
                    f"(+{blessing_bonus} to next save vs deadly effect)"
                )

            # Trigger wandering monster encounter if fish attracted one
            if result.monster_attracted:
                # Screaming jenny attracted a wandering monster!
                current_hex = self._state.current_hex
                if current_hex:
                    hex_data = self._get_hex_data(current_hex)
                    terrain = hex_data.terrain_type if hex_data else TerrainType.OPEN_FOREST

                    # Generate and trigger the encounter
                    encounter = self._generate_encounter(current_hex, terrain)
                    self.controller.set_encounter(encounter)
                    self.controller.transition(
                        "encounter_triggered",
                        context={
                            "hex_id": current_hex,
                            "source": "screaming_jenny",
                            "description": "The fish's shriek attracted something!",
                        },
                    )
                    # Add to result for caller awareness
                    result.catch_events.append({
                        "type": "monster_encounter_triggered",
                        "description": "The shriek attracted a wandering monster!",
                    })

        # Apply hunting-specific effects (Campaign Book p120-121)
        if method == "hunting" and result.success and result.combat_triggered:
            # Set up combat encounter with the game animals
            if result.game_animal:
                current_hex = self._state.current_hex
                if current_hex:
                    # Create encounter with the game animals
                    monster_id = result.game_animal.get("monster_id")
                    num_appearing = result.number_appearing
                    distance = result.encounter_distance

                    if monster_id:
                        # Create combatants from monster registry
                        combatants = self._create_hunting_combatants(
                            monster_id=monster_id,
                            num_appearing=num_appearing,
                            animal_name=result.game_animal.get("name", "game animal"),
                        )

                        if combatants:
                            # Create the hunting encounter
                            encounter = EncounterState(
                                encounter_id=f"hunt_{current_hex}_{monster_id}",
                                encounter_type=EncounterType.COMBAT,
                                description=result.description,
                                combatants=combatants,
                                distance=distance,
                                party_surprised=False,  # Party is NOT surprised
                                enemies_surprised=True,  # Enemies ARE surprised
                                context=f"Hunting {result.game_animal.get('name', 'game')} in {current_hex}",
                            )

                            # Store hunting-specific data for post-combat ration calculation
                            encounter.contextual_data = {
                                "source": "hunting",
                                "hex_id": current_hex,
                                "game_animal": result.game_animal,
                                "number_appearing": num_appearing,
                                "potential_rations": result.potential_rations,
                            }

                            self.controller.set_encounter(encounter)
                            self.controller.transition(
                                "encounter_triggered",
                                context={
                                    "hex_id": current_hex,
                                    "source": "hunting",
                                    "animal": result.game_animal.get("name"),
                                    "number": num_appearing,
                                    "distance": distance,
                                    "party_has_surprise": True,
                                },
                            )

        return result

    def _create_hunting_combatants(
        self,
        monster_id: str,
        num_appearing: int,
        animal_name: str,
    ) -> list:
        """
        Create combatants for a hunting encounter.

        Args:
            monster_id: The monster ID from the game animal
            num_appearing: How many animals in the group
            animal_name: Display name for the animal

        Returns:
            List of Combatant objects for the encounter
        """
        from src.data_models import Combatant

        combatants = []

        # Get monster stats from registry
        monster_stats = self.monster_registry.get(monster_id) if self.monster_registry else None

        for i in range(num_appearing):
            if monster_stats:
                # Create combatant from monster registry
                combatant = Combatant(
                    combatant_id=f"{monster_id}_{i+1}",
                    name=f"{animal_name} #{i+1}" if num_appearing > 1 else animal_name,
                    monster_id=monster_id,
                    hp_current=monster_stats.hp,
                    hp_max=monster_stats.hp,
                    armor_class=monster_stats.armor_class,
                    attack_bonus=monster_stats.level,  # Use level as attack bonus
                    damage=monster_stats.damage[0] if monster_stats.damage else "1d4",
                    morale=monster_stats.morale,
                    is_enemy=True,
                    is_active=True,
                )
            else:
                # Fallback with default stats
                combatant = Combatant(
                    combatant_id=f"{monster_id}_{i+1}",
                    name=f"{animal_name} #{i+1}" if num_appearing > 1 else animal_name,
                    monster_id=monster_id,
                    hp_current=4,
                    hp_max=4,
                    armor_class=12,
                    attack_bonus=0,
                    damage="1d4",
                    morale=6,
                    is_enemy=True,
                    is_active=True,
                )
            combatants.append(combatant)

        return combatants

    # =========================================================================
    # HEX OVERVIEW AND POI VISIBILITY
    # =========================================================================

    def _is_night(self) -> bool:
        """Check if it's currently night time."""
        if not self.controller.world_state:
            return False
        if not self.controller.world_state.current_time:
            return False
        time_of_day = self.controller.world_state.current_time.get_time_of_day()
        # Night periods: DUSK, EVENING, MIDNIGHT, PREDAWN
        return time_of_day in (TimeOfDay.DUSK, TimeOfDay.EVENING, TimeOfDay.MIDNIGHT, TimeOfDay.PREDAWN)

    def _get_terrain_difficulty_description(self, terrain: TerrainType) -> str:
        """Get human-readable terrain difficulty description."""
        terrain_info = self.get_terrain_info(terrain)
        if terrain_info.travel_point_cost <= 2:
            return "easy"
        elif terrain_info.travel_point_cost == 3:
            return "moderate"
        else:
            return "difficult"

    def _get_atmosphere_description(self) -> str:
        """Generate atmospheric description based on time and weather."""
        parts = []

        # Time of day
        if self.controller.world_state and self.controller.world_state.current_time:
            time_of_day = self.controller.world_state.current_time.get_time_of_day()
            time_descriptions = {
                TimeOfDay.DAWN: "The first light of dawn spreads across the land",
                TimeOfDay.MORNING: "Morning light filters through",
                TimeOfDay.MIDDAY: "The sun hangs high overhead",
                TimeOfDay.AFTERNOON: "Afternoon shadows begin to lengthen",
                TimeOfDay.DUSK: "The fading light of dusk casts long shadows",
                TimeOfDay.EVENING: "Evening settles over the landscape",
                TimeOfDay.MIDNIGHT: "Deep night shrouds everything in darkness",
                TimeOfDay.PREDAWN: "The darkness before dawn hangs heavy",
            }
            if time_of_day in time_descriptions:
                parts.append(time_descriptions[time_of_day])

            # Weather
            weather = self.controller.world_state.weather
            weather_descriptions = {
                Weather.CLEAR: "",
                Weather.OVERCAST: "under an overcast sky",
                Weather.FOG: "as mist hangs heavy in the air",
                Weather.RAIN: "as rain patters down steadily",
                Weather.STORM: "as thunder rumbles in the distance",
                Weather.SNOW: "as snow drifts down silently",
                Weather.BLIZZARD: "as a howling blizzard reduces visibility",
            }
            if weather in weather_descriptions and weather_descriptions[weather]:
                parts.append(weather_descriptions[weather])

        return ", ".join(parts) + "." if parts else "The area stretches before you."

    def _get_time_specific_observations(self, hex_data: HexLocation, is_night: bool) -> list[str]:
        """
        Get observations specific to the current time of day.

        Examines POI special_features for time-dependent descriptions.
        """
        observations = []

        for poi in hex_data.points_of_interest:
            if not poi.is_visible(self._discovered_secrets):
                continue

            # Look for time-specific special features
            for feature in poi.special_features:
                feature_lower = feature.lower()
                if is_night and any(
                    keyword in feature_lower
                    for keyword in ["at night", "nighttime", "darkness", "hours of darkness"]
                ):
                    # Extract the visible description
                    observations.append(feature)
                elif not is_night and any(
                    keyword in feature_lower
                    for keyword in ["daytime", "daylight", "during the day"]
                ):
                    observations.append(feature)

        return observations

    def get_hex_overview(self, hex_id: str) -> HexOverview:
        """
        Get a player-facing overview of a hex.

        Returns only information the characters would perceive,
        without meta-information like hex IDs or named locations.
        Characters see what's visible, not what the map says.

        Args:
            hex_id: The hex identifier (internal use only)

        Returns:
            HexOverview with player-perceivable information
        """
        hex_data = self._hex_data.get(hex_id)
        is_night = self._is_night()

        if not hex_data:
            # Unknown hex - provide generic description based on terrain
            terrain = self.get_terrain_for_hex(hex_id)
            terrain_info = self.get_terrain_info(terrain)
            return HexOverview(
                terrain_description=terrain_info.description,
                atmosphere=self._get_atmosphere_description(),
                visible_features=[],
                visible_locations=[],
                terrain_difficulty=self._get_terrain_difficulty_description(terrain),
                travel_points_to_cross=terrain_info.travel_point_cost,
                is_night=is_night,
                weather_effects=(
                    self._apply_weather_effects(self.controller.world_state.weather)
                    if self.controller.world_state
                    else None
                ),
                time_specific_observations=[],
            )

        # Build terrain description (use tagline, not hex name)
        terrain_desc = hex_data.tagline or hex_data.description or hex_data.terrain_description

        # Get visible features from the landscape
        visible_features = []

        # Add visible landmarks
        for landmark in getattr(hex_data, "landmarks", []):
            if hasattr(landmark, "name"):
                visible_features.append(landmark.name)

        # Get visible POIs (not hidden, or discovered)
        visible_locations = self.get_visible_pois(hex_id)

        # Get time-specific observations
        time_observations = self._get_time_specific_observations(hex_data, is_night)

        terrain = self.get_terrain_for_hex(hex_id)
        terrain_info = self.get_terrain_info(terrain)

        return HexOverview(
            terrain_description=terrain_desc,
            atmosphere=self._get_atmosphere_description(),
            visible_features=visible_features,
            visible_locations=visible_locations,
            terrain_difficulty=self._get_terrain_difficulty_description(terrain),
            travel_points_to_cross=terrain_info.travel_point_cost,
            is_night=is_night,
            weather_effects=(
                self._apply_weather_effects(self.controller.world_state.weather)
                if self.controller.world_state
                else None
            ),
            time_specific_observations=time_observations,
        )

    def check_poi_availability(self, poi: "PointOfInterest") -> dict[str, Any]:
        """
        Check if a POI is currently available based on its availability conditions.

        POIs can have availability conditions like:
        - Moon phase requirements (e.g., only visible during full moon)
        - Time of day requirements
        - Seasonal requirements
        - Conditional requirements

        Args:
            poi: The PointOfInterest to check

        Returns:
            Dictionary with availability status and message
        """
        if not poi.availability:
            return {"available": True}

        availability = poi.availability
        avail_type = availability.get("type", "")
        required = availability.get("required", "")
        hidden_message = availability.get(
            "hidden_message", "This location is not currently accessible."
        )

        # Check based on availability type
        if avail_type == "moon_phase":
            if self.controller.world_state and self.controller.world_state.current_date:
                current_moon = self.controller.world_state.current_date.get_moon_phase()
                # Handle required as string or list
                required_phases = [required] if isinstance(required, str) else required
                # Check if current moon matches any required phase
                for phase in required_phases:
                    # Match by name (e.g., "full_moon", "grinning_moon")
                    if phase.lower().replace(" ", "_") == current_moon.value:
                        return {"available": True}
                return {
                    "available": False,
                    "type": "moon_phase",
                    "required": required,
                    "current": current_moon.value,
                    "message": hidden_message,
                }
            # No date tracking - assume available
            return {"available": True}

        elif avail_type == "time_of_day":
            is_night = self._is_night()
            if required == "night" and not is_night:
                return {
                    "available": False,
                    "type": "time_of_day",
                    "required": "night",
                    "message": hidden_message,
                }
            elif required == "day" and is_night:
                return {
                    "available": False,
                    "type": "time_of_day",
                    "required": "day",
                    "message": hidden_message,
                }
            return {"available": True}

        elif avail_type == "seasonal":
            if self.controller.world_state and self.controller.world_state.current_date:
                current_season = self.controller.world_state.current_date.get_season()
                required_seasons = [required] if isinstance(required, str) else required
                for season in required_seasons:
                    if season.lower() == current_season.value:
                        return {"available": True}
                return {
                    "available": False,
                    "type": "seasonal",
                    "required": required,
                    "current": current_season.value,
                    "message": hidden_message,
                }
            return {"available": True}

        elif avail_type == "condition":
            # Condition-based availability - check world state
            condition_key = availability.get("condition_key", "")
            if condition_key and self.controller.world_state:
                # Check if condition is met in world state
                # This would be tracked in hex state changes
                if hasattr(self.controller.world_state, "conditions"):
                    if self.controller.world_state.conditions.get(condition_key):
                        return {"available": True}
                return {
                    "available": False,
                    "type": "condition",
                    "required": condition_key,
                    "message": hidden_message,
                }
            return {"available": True}

        # Unknown type - assume available
        return {"available": True}

    def get_visible_pois(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get list of visible points of interest in a hex.

        A POI is visible if:
        - It's not marked as hidden, OR
        - It has been discovered through searching

        Does NOT include hex names or IDs - only what characters can see.

        Args:
            hex_id: The hex identifier

        Returns:
            List of visible POI information for players
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        is_night = self._is_night()
        visible = []

        for poi in hex_data.points_of_interest:
            if not poi.is_visible(self._discovered_secrets):
                continue

            # Build player-facing POI info
            poi_info = {
                "type": poi.poi_type,
                "description": poi.get_description(is_night),
                "can_approach": poi.visible_from_distance,
                "is_dungeon": poi.is_dungeon,
            }

            # Add tagline if available (short evocative description)
            if poi.tagline:
                poi_info["brief"] = poi.tagline

            # Add time-specific observations
            if is_night:
                night_features = [
                    f
                    for f in poi.special_features
                    if any(
                        kw in f.lower()
                        for kw in ["at night", "nighttime", "darkness", "hours of darkness"]
                    )
                ]
                if night_features:
                    poi_info["notable"] = night_features[0]

            visible.append(poi_info)

        return visible

    def get_sensory_hints(
        self,
        hex_id: str,
        include_adjacent: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get sensory discovery hints from POIs in the current and adjacent hexes.

        These hints help players discover hidden POIs through sound, smell, or
        visual cues even before they search for them.

        Args:
            hex_id: The hex the party is currently in
            include_adjacent: Whether to include hints from adjacent hexes

        Returns:
            Dict with keys 'nearby', 'adjacent', 'distant' containing hint lists
        """
        is_night = self._is_night()
        hints: dict[str, list[dict[str, Any]]] = {
            "nearby": [],
            "adjacent": [],
            "distant": [],
        }

        # Get hints from current hex
        hex_data = self._hex_data.get(hex_id)
        if hex_data:
            for poi in hex_data.points_of_interest:
                poi_hints = poi.get_active_discovery_hints(
                    is_night=is_night,
                    current_range="nearby",
                )
                for hint in poi_hints:
                    hint["hex_id"] = hex_id
                    hints["nearby"].append(hint)

        # Get hints from adjacent hexes
        if include_adjacent and hex_data:
            adjacent_hexes = hex_data.adjacent_hexes or []
            for adj_hex_id in adjacent_hexes:
                adj_hex = self._hex_data.get(adj_hex_id)
                if not adj_hex:
                    continue

                for poi in adj_hex.points_of_interest:
                    # Only get hints that carry to adjacent range
                    poi_hints = poi.get_active_discovery_hints(
                        is_night=is_night,
                        current_range="adjacent",
                    )
                    for hint in poi_hints:
                        hint["hex_id"] = adj_hex_id
                        hints["adjacent"].append(hint)

        return hints

    def describe_sensory_hints(self, hex_id: str) -> list[str]:
        """
        Get narrative descriptions of sensory hints for the current location.

        Returns atmospheric text suitable for reading to players that hints
        at nearby discoverable POIs without revealing their names.

        Args:
            hex_id: The hex the party is currently in

        Returns:
            List of narrative description strings
        """
        hints = self.get_sensory_hints(hex_id)
        descriptions = []

        # Process nearby hints (strongest)
        for hint in hints["nearby"]:
            sense = hint["sense_type"]
            desc = hint["description"]
            if sense == "sound":
                descriptions.append(f"You hear {desc}")
            elif sense == "smell":
                descriptions.append(f"You catch the scent of {desc}")
            elif sense == "visual":
                descriptions.append(f"You notice {desc}")
            else:
                descriptions.append(desc)

        # Process adjacent hints (fainter)
        for hint in hints["adjacent"]:
            sense = hint["sense_type"]
            desc = hint["description"]
            if sense == "sound":
                descriptions.append(f"Faintly, in the distance, you hear {desc}")
            elif sense == "smell":
                descriptions.append(f"A faint scent of {desc} drifts on the wind")
            elif sense == "visual":
                descriptions.append(f"In the distance, you can just make out {desc}")
            else:
                descriptions.append(f"From somewhere nearby: {desc}")

        return descriptions

    def discover_poi(self, hex_id: str, poi_name: str) -> bool:
        """
        Mark a hidden POI as discovered.

        Called when a search roll succeeds in finding a hidden location.

        Args:
            hex_id: The hex containing the POI
            poi_name: Name of the POI to discover

        Returns:
            True if POI was found and marked discovered
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return False

        for poi in hex_data.points_of_interest:
            if poi.name.lower() == poi_name.lower():
                poi.mark_discovered()
                return True

        return False

    # =========================================================================
    # POI APPROACH AND EXPLORATION
    # =========================================================================

    def approach_poi(
        self,
        hex_id: str,
        poi_index: int,
    ) -> dict[str, Any]:
        """
        Approach a visible point of interest within a hex.

        This moves the party from the general hex to the specific location,
        potentially triggering approach descriptions and hazards.

        Args:
            hex_id: The hex containing the POI
            poi_index: Index of the POI in visible_locations list

        Returns:
            Dictionary with approach results and description
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        # Get visible POIs
        visible_pois = [poi for poi in hex_data.points_of_interest if poi.is_visible()]
        if poi_index < 0 or poi_index >= len(visible_pois):
            return {"success": False, "error": "Invalid location index"}

        poi = visible_pois[poi_index]
        is_night = self._is_night()

        # Update POI exploration state
        self._current_poi = poi.name
        self._poi_state = POIExplorationState.APPROACHING

        # Track visit
        visit_key = f"{hex_id}:{poi.name}"
        if visit_key not in self._poi_visits:
            self._poi_visits[visit_key] = POIVisit(poi_name=poi.name)

        # Build approach description
        description_parts = []

        # Add POI description based on time
        description_parts.append(poi.get_description(is_night))

        # Add exploring description if available
        if poi.exploring:
            description_parts.append(poi.exploring)

        # Get approach hazards from the hazards field
        approach_hazards = poi.get_hazards_for_trigger("on_approach")

        # Also check for hazards in special_features (legacy support)
        feature_hazards = []
        for feature in poi.special_features:
            feature_lower = feature.lower()
            if any(
                kw in feature_lower for kw in ["climbing", "thorns", "dangerous", "treacherous"]
            ):
                feature_hazards.append(feature)

        result = {
            "success": True,
            "poi_type": poi.poi_type,
            "description": "\n\n".join(description_parts),
            "can_enter": poi.entering is not None or poi.interior is not None,
            "is_dungeon": poi.is_dungeon,
            "hazards": feature_hazards,  # Legacy feature hazards
            "approach_hazards": approach_hazards,  # Proper hazard definitions
            "state": POIExplorationState.APPROACHING.value,
            "requires_hazard_resolution": len(approach_hazards) > 0,
        }

        # If there are inhabitants, note them (without revealing secrets)
        if poi.inhabitants and not is_night:
            # Some inhabitants might only be present at certain times
            result["activity_noted"] = True

        return result

    def resolve_poi_hazard(
        self,
        hex_id: str,
        hazard_index: int,
        character_id: str,
        approach_method: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Resolve a hazard required to access a POI.

        Uses the narrative resolver to handle climbing, swimming, or
        other hazards that must be overcome to reach a POI.

        Args:
            hex_id: The hex containing the POI
            hazard_index: Index of the hazard in the approach_hazards list
            character_id: Character attempting to overcome the hazard
            approach_method: Optional method being used (e.g., "rope", "flying")

        Returns:
            HazardResult-style dictionary with success/failure and consequences
        """
        if not self._current_poi:
            return {"success": False, "error": "Not approaching any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex not found"}

        # Find the current POI
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "POI not found"}

        # Get approach hazards
        approach_hazards = poi.get_hazards_for_trigger("on_approach")
        if hazard_index < 0 or hazard_index >= len(approach_hazards):
            return {"success": False, "error": "Invalid hazard index"}

        hazard = approach_hazards[hazard_index]
        hazard_type = hazard.get("hazard_type", "environmental")
        difficulty = hazard.get("difficulty", "moderate")

        # Get character
        character = self._get_character(character_id)
        if not character:
            return {"success": False, "error": "Character not found"}

        # Resolve using narrative resolver if available
        if self.narrative_resolver:
            # Map hazard type to HazardType enum
            try:
                h_type = HazardType(hazard_type.upper())
            except ValueError:
                h_type = HazardType.ENVIRONMENTAL

            result = self.narrative_resolver.hazard_resolver.resolve_hazard(
                character=character,
                hazard_type=h_type,
                difficulty=difficulty,
                context={
                    "poi_name": poi.name,
                    "hazard_description": hazard.get("description", ""),
                    "approach_method": approach_method,
                },
            )

            return {
                "success": result.success,
                "hazard_type": hazard_type,
                "description": hazard.get("description", ""),
                "damage": result.damage_taken,
                "effect": result.effect_applied,
                "narrative": result.narrative,
                "can_proceed": result.success,
            }
        else:
            # Basic resolution without narrative resolver
            roll = self.dice.roll("1d6").total
            difficulty_threshold = {"easy": 2, "moderate": 3, "hard": 4, "extreme": 5}
            threshold = difficulty_threshold.get(difficulty, 3)

            success = roll >= threshold

            return {
                "success": success,
                "hazard_type": hazard_type,
                "description": hazard.get("description", ""),
                "roll": roll,
                "threshold": threshold,
                "can_proceed": success,
            }

    def enter_poi(self, hex_id: str) -> dict[str, Any]:
        """
        Enter the currently approached POI.

        Must have called approach_poi first.

        Args:
            hex_id: The hex containing the POI

        Returns:
            Dictionary with entry results and interior description
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location - approach first"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        # Find the current POI
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        # Check POI availability (e.g., moon phase requirements)
        availability_check = self.check_poi_availability(poi)
        if not availability_check["available"]:
            return {
                "success": False,
                "unavailable": True,
                "message": availability_check.get(
                    "message", "This location is not currently accessible"
                ),
                "availability": availability_check,
            }

        is_night = self._is_night()

        # Check if this is a dungeon - if so, should transition state
        if poi.is_dungeon:
            return {
                "success": False,
                "is_dungeon": True,
                "message": "This location requires dungeon exploration mode",
                "dungeon_levels": poi.dungeon_levels,
            }

        # Check for entry conditions
        if poi.has_entry_conditions():
            return {
                "success": False,
                "requires_entry_check": True,
                "entry_condition_type": poi.get_entry_condition_type(),
                "entry_conditions": poi.entry_conditions,
                "message": "This location has entry requirements",
            }

        # Update state
        self._poi_state = POIExplorationState.AT_ENTRANCE

        # Build entry description
        description_parts = []

        # Add entering description
        entering_desc = poi.get_entering_description(is_night)
        if entering_desc:
            description_parts.append(entering_desc)

        # Add interior description
        interior_desc = poi.get_interior_description(is_night)
        if interior_desc:
            description_parts.append(interior_desc)

        # Track visit
        visit_key = f"{hex_id}:{poi.name}"
        if visit_key in self._poi_visits:
            self._poi_visits[visit_key].entered = True

        # Check for entry hazards
        entry_hazards = poi.get_hazards_for_trigger("on_enter")

        # Check for entry alerts
        entry_alerts = poi.get_alerts_for_trigger("on_enter")

        # Get variable inhabitants if any
        inhabitants = poi.get_current_inhabitants(self.dice)

        result = {
            "success": True,
            "poi_type": poi.poi_type,
            "description": "\n\n".join(description_parts),
            "state": POIExplorationState.AT_ENTRANCE.value,
            "entry_hazards": entry_hazards,
            "requires_hazard_resolution": len(entry_hazards) > 0,
            "entry_alerts": entry_alerts,
            "inhabitants": inhabitants,
        }

        # Include relevant special features for exploration
        explorable_features = []
        for feature in poi.special_features:
            # Filter for features relevant to current time
            feature_lower = feature.lower()
            if is_night:
                if "daytime" in feature_lower or "(daytime)" in feature_lower:
                    continue
            else:
                if "nighttime" in feature_lower or "(nighttime)" in feature_lower:
                    continue
                if "at night" in feature_lower:
                    continue
            explorable_features.append(feature)

        if explorable_features:
            result["features_to_explore"] = explorable_features

        # Note NPCs present (if any)
        if poi.npcs:
            result["npcs_present"] = True
            result["npc_count"] = len(poi.npcs)

        return result

    def enter_dungeon_from_poi(
        self,
        hex_id: str,
        dungeon_engine: Any,
    ) -> dict[str, Any]:
        """
        Enter a dungeon POI using the dungeon engine.

        This bridges the hex POI data to the dungeon engine, converting the
        POI's roll tables to the format expected by the dungeon engine.

        Args:
            hex_id: The hex containing the dungeon POI
            dungeon_engine: The DungeonEngine instance to use

        Returns:
            Dictionary with entry results from dungeon engine
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location - approach first"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        # Find the current POI
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        if not poi.is_dungeon:
            return {"success": False, "error": "This location is not a dungeon"}

        # Check POI availability
        availability_check = self.check_poi_availability(poi)
        if not availability_check["available"]:
            return {
                "success": False,
                "unavailable": True,
                "message": availability_check.get("message", "This location is not accessible"),
                "availability": availability_check,
            }

        # Build POI config for dungeon engine
        poi_config = self._build_dungeon_poi_config(poi, hex_id)

        # Generate dungeon ID from POI name
        dungeon_id = poi.name.lower().replace(" ", "_").replace("-", "_")

        # Enter dungeon via dungeon engine
        result = dungeon_engine.enter_dungeon(
            dungeon_id=dungeon_id,
            entry_room="entry",
            poi_config=poi_config,
        )

        # Track the POI visit
        visit_key = f"{hex_id}:{poi.name}"
        if visit_key in self._poi_visits:
            self._poi_visits[visit_key].entered = True

        # Clear hex crawl POI state (we're in dungeon mode now)
        self._poi_state = None

        return result

    def _build_dungeon_poi_config(
        self,
        poi: PointOfInterest,
        hex_id: str,
    ) -> dict[str, Any]:
        """
        Build dungeon POI configuration from a PointOfInterest.

        Converts the POI's roll_tables to the format expected by DungeonEngine,
        extracting room_table and encounter_table by name.

        Args:
            poi: The dungeon POI
            hex_id: The hex containing the POI

        Returns:
            Dictionary with dungeon configuration
        """
        config = {
            "poi_name": poi.name,
            "hex_id": hex_id,
            "roll_tables": poi.roll_tables,
            "room_table": None,
            "encounter_table": None,
            "dynamic_layout": poi.dynamic_layout,
            "item_persistence": poi.item_persistence,
            "leaving": poi.leaving,
        }

        # Extract room and encounter tables by name
        for table in poi.roll_tables:
            table_name = table.name.lower()
            if table_name == "rooms" or table_name == "room":
                config["room_table"] = table
            elif table_name == "encounters" or table_name == "encounter":
                config["encounter_table"] = table

        # If no explicit tables found, check for dynamic_layout references
        if config["dynamic_layout"]:
            layout = config["dynamic_layout"]
            room_table_name = layout.get("room_table", "Rooms")
            encounter_table_name = layout.get("encounter_table", "Encounters")

            for table in poi.roll_tables:
                if table.name.lower() == room_table_name.lower():
                    config["room_table"] = table
                if table.name.lower() == encounter_table_name.lower():
                    config["encounter_table"] = table

        return config

    def explore_poi_feature(
        self,
        hex_id: str,
        feature_description: str,
    ) -> dict[str, Any]:
        """
        Examine or interact with a specific feature within a POI.

        Args:
            hex_id: The hex containing the POI
            feature_description: Description/name of the feature to examine

        Returns:
            Dictionary with examination results
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        # Find the current POI
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        is_night = self._is_night()

        # Find matching feature
        feature_lower = feature_description.lower()
        matching_features = []
        for feature in poi.special_features:
            if feature_lower in feature.lower() or feature.lower() in feature_lower:
                matching_features.append(feature)

        if not matching_features:
            return {
                "success": False,
                "error": "That feature is not present or visible",
            }

        # Check time-appropriateness
        feature = matching_features[0]
        if is_night and "(daytime)" in feature.lower():
            return {
                "success": False,
                "error": "This feature is not visible at night",
            }
        if not is_night and "at night" in feature.lower():
            return {
                "success": True,
                "description": "Nothing notable is happening here at this time of day.",
                "hint": "This location may be different at other times.",
            }

        # Track feature exploration
        visit_key = f"{hex_id}:{poi.name}"
        if visit_key in self._poi_visits:
            if feature not in self._poi_visits[visit_key].rooms_explored:
                self._poi_visits[visit_key].rooms_explored.append(feature)

        return {
            "success": True,
            "description": feature,
            "is_time_specific": any(
                kw in feature.lower() for kw in ["night", "day", "darkness", "light"]
            ),
        }

    def enter_poi_with_conditions(
        self,
        hex_id: str,
        has_permission: bool = False,
        payment_offered: int = 0,
        password_given: Optional[str] = None,
        social_result: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Attempt to enter a POI that has entry conditions.

        Used when enter_poi returns requires_entry_check=True.

        Args:
            hex_id: The hex containing the POI
            has_permission: Whether party has permission
            payment_offered: Payment for toll entry
            password_given: Password if required
            social_result: Result of social encounter (success, failure, hostile)

        Returns:
            Dictionary with entry results
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        # Check entry conditions
        entry_result = poi.check_entry_allowed(
            has_permission=has_permission,
            payment_offered=payment_offered,
            password_given=password_given,
            social_result=social_result,
        )

        if not entry_result.get("allowed", False):
            # Check if unauthorized entry triggers an alert
            if entry_result.get("triggers_alert"):
                alerts = poi.get_alerts_for_trigger("on_enter_unauthorized")
                entry_result["alerts_triggered"] = alerts
                # Trigger the alerts
                for i, alert in enumerate(poi.alerts):
                    if alert.get("trigger") == "on_enter_unauthorized":
                        poi.trigger_alert(i)

            return entry_result

        # Entry allowed - proceed with normal entry
        # Clear entry conditions temporarily to allow normal entry
        saved_conditions = poi.entry_conditions
        poi.entry_conditions = None
        result = self.enter_poi(hex_id)
        poi.entry_conditions = saved_conditions

        result["entry_outcome"] = entry_result.get("outcome")
        if entry_result.get("payment_taken"):
            result["payment_taken"] = entry_result["payment_taken"]

        return result

    def search_poi_location(
        self,
        hex_id: str,
        search_location: str,
        thorough: bool = False,
    ) -> dict[str, Any]:
        """
        Search a specific location within the current POI for concealed items.

        Args:
            hex_id: The hex containing the POI
            search_location: What to search (e.g., "trophies", "bookshelf")
            thorough: If True, perform a thorough/careful search

        Returns:
            Dictionary with search results and any found items
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        # Roll for search
        search_roll = self.dice.roll("1d6").total

        # Check for concealed items
        found_items = poi.search_for_concealed(
            location=search_location,
            search_roll=search_roll,
            thorough=thorough,
        )

        # Check if searching triggers any alerts
        search_alerts = poi.get_alerts_for_trigger("on_search")
        for i, alert in enumerate(poi.alerts):
            if alert.get("trigger") == "on_search":
                poi.trigger_alert(i)

        result = {
            "success": True,
            "search_location": search_location,
            "search_roll": search_roll,
            "thorough": thorough,
            "items_found": found_items,
            "found_count": len(found_items),
        }

        if search_alerts:
            result["alerts_triggered"] = search_alerts

        if not found_items:
            result["message"] = "You find nothing of interest."
        else:
            item_names = [item.get("name", "unknown") for item in found_items]
            result["message"] = f"You discover: {', '.join(item_names)}"

        return result

    def get_poi_quests(
        self,
        hex_id: str,
        party_disposition: str = "neutral",
        party_level: int = 1,
    ) -> dict[str, Any]:
        """
        Get available quest hooks at the current POI.

        Args:
            hex_id: The hex containing the POI
            party_disposition: Party's standing (friendly, neutral, hostile)
            party_level: Average party level

        Returns:
            Dictionary with available quests
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        # Get completed quests from tracking
        completed_quests = getattr(self, "_completed_quests", set())

        available_quests = poi.get_available_quests(
            party_disposition=party_disposition,
            party_level=party_level,
            completed_quests=completed_quests,
        )

        return {
            "success": True,
            "quests_available": len(available_quests) > 0,
            "quests": available_quests,
        }

    def trigger_poi_alert(
        self,
        hex_id: str,
        trigger_type: str,
    ) -> dict[str, Any]:
        """
        Manually trigger alerts at the current POI.

        Args:
            hex_id: The hex containing the POI
            trigger_type: Type of trigger (on_enter, on_combat, etc.)

        Returns:
            Dictionary with triggered alert effects
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        if not poi:
            return {"success": False, "error": "Current location not found"}

        # Get and trigger alerts
        alerts = poi.get_alerts_for_trigger(trigger_type)
        triggered = []

        for i, alert in enumerate(poi.alerts):
            if alert.get("trigger") == trigger_type and not alert.get("triggered", False):
                triggered_alert = poi.trigger_alert(i)
                triggered.append(triggered_alert)

        return {
            "success": True,
            "trigger_type": trigger_type,
            "alerts_triggered": triggered,
            "alert_count": len(triggered),
        }

    def get_npc_relationships(
        self,
        hex_id: str,
        npc_id: str,
    ) -> dict[str, Any]:
        """
        Get relationships for a specific NPC.

        Args:
            hex_id: The hex containing the NPC
            npc_id: ID of the NPC

        Returns:
            Dictionary with NPC relationship information
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        npc = None
        for n in hex_data.npcs:
            if n.npc_id == npc_id:
                npc = n
                break

        if not npc:
            return {"success": False, "error": "NPC not found"}

        return {
            "success": True,
            "npc_id": npc_id,
            "npc_name": npc.name,
            "relationships": npc.relationships,
            "faction": npc.faction,
            "loyalty": npc.loyalty,
            "is_secretly_disloyal": npc.is_secretly_disloyal(),
            "cross_hex_connections": npc.get_cross_hex_connections(),
        }

    def leave_poi(self, hex_id: str) -> dict[str, Any]:
        """
        Leave the current POI and return to hex exploration.

        Args:
            hex_id: The hex containing the POI

        Returns:
            Dictionary with departure results
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            # Still allow leaving even without data
            poi_name = self._current_poi
            self._current_poi = None
            self._poi_state = POIExplorationState.DISTANT
            return {
                "success": True,
                "message": f"You depart from the {poi_name}.",
            }

        # Find the current POI for leaving description
        poi = None
        for p in hex_data.points_of_interest:
            if p.name == self._current_poi:
                poi = p
                break

        # Update state
        poi_name = self._current_poi
        self._current_poi = None
        self._poi_state = POIExplorationState.DISTANT

        result = {
            "success": True,
            "message": f"You depart and return to the surrounding terrain.",
        }

        if poi and poi.leaving:
            result["description"] = poi.leaving

        return result

    def get_current_poi_state(self) -> dict[str, Any]:
        """
        Get the current POI exploration state.

        Returns:
            Dictionary with current POI info or None if not at a POI
        """
        if not self._current_poi:
            return {"at_poi": False}

        return {
            "at_poi": True,
            "poi_name": self._current_poi,
            "state": self._poi_state.value,
        }

    # =========================================================================
    # SECRET DISCOVERY SYSTEM
    # =========================================================================

    def check_for_secret(
        self,
        hex_id: str,
        character_id: str,
        secret_name: Optional[str] = None,
        ability: str = "INT",
        dc: int = 10,
    ) -> SecretCheck:
        """
        Attempt to discover a secret using an ability check.

        Per Dolmenwood rules, secrets may require specific ability checks
        (INT for noticing patterns, WIS for intuition, etc.).

        Args:
            hex_id: The hex containing the secret
            character_id: Character attempting the check
            secret_name: Specific secret to check for (or None for general search)
            ability: Ability score to use (INT, WIS, etc.)
            dc: Difficulty class for the check

        Returns:
            SecretCheck with results
        """
        character = self.controller.get_character(character_id)
        if not character:
            return SecretCheck(
                secret_name=secret_name or "unknown",
                found=False,
                ability_used=ability,
                dc=dc,
                description="Character not found",
            )

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return SecretCheck(
                secret_name=secret_name or "unknown",
                found=False,
                ability_used=ability,
                dc=dc,
                description="No secrets to find here",
            )

        # Get ability modifier
        ability_mod = character.get_ability_modifier(ability)

        # Roll the check
        roll = self.dice.roll_d20(f"secret check ({ability})")
        total = roll.total + ability_mod

        # Determine which secret(s) could be found
        secrets_to_check = []
        if secret_name:
            secrets_to_check = [secret_name]
        else:
            # Check all secrets at current POI
            if self._current_poi:
                for poi in hex_data.points_of_interest:
                    if poi.name == self._current_poi:
                        secrets_to_check.extend(poi.secrets)
                        break
            else:
                # Check hex-level secrets
                secrets_to_check.extend(hex_data.secrets)

        if not secrets_to_check:
            return SecretCheck(
                secret_name="none",
                found=False,
                ability_used=ability,
                roll_result=total,
                dc=dc,
                description="You search carefully but find nothing hidden.",
            )

        # Check if roll beats DC
        found = total >= dc
        found_secret = secrets_to_check[0] if found and secrets_to_check else None

        if found and found_secret:
            # Mark secret as discovered
            self._discovered_secrets.add(found_secret)

            # Track in POI visit
            if self._current_poi:
                visit_key = f"{hex_id}:{self._current_poi}"
                if visit_key in self._poi_visits:
                    if found_secret not in self._poi_visits[visit_key].secrets_discovered:
                        self._poi_visits[visit_key].secrets_discovered.append(found_secret)

            return SecretCheck(
                secret_name=found_secret,
                found=True,
                ability_used=ability,
                roll_result=total,
                dc=dc,
                description=f"You discover: {found_secret}",
            )
        else:
            return SecretCheck(
                secret_name=secret_name or "unknown",
                found=False,
                ability_used=ability,
                roll_result=total,
                dc=dc,
                description="Your search reveals nothing of note.",
            )

    def get_discovered_secrets(self) -> set[str]:
        """Get all secrets discovered by the party."""
        return self._discovered_secrets.copy()

    def has_discovered_secret(self, secret_name: str) -> bool:
        """Check if a specific secret has been discovered."""
        return secret_name in self._discovered_secrets

    # =========================================================================
    # POI-TO-POI NAVIGATION
    # =========================================================================

    def get_accessible_pois(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get POIs accessible from the current location.

        Handles nested POIs - if inside a POI with children,
        shows those children. If at hex level, shows top-level POIs.

        Args:
            hex_id: Current hex

        Returns:
            List of accessible POI information
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        accessible = []
        is_night = self._is_night()

        for poi in hex_data.points_of_interest:
            # Check visibility with discovered secrets
            if not poi.is_visible(self._discovered_secrets):
                continue

            # Check accessibility from current location
            if not poi.is_accessible_from(self._current_poi):
                continue

            poi_info = {
                "name": poi.name,
                "type": poi.poi_type,
                "description": poi.get_description(is_night),
                "is_dungeon": poi.is_dungeon,
                "has_children": len(poi.child_pois) > 0,
            }

            if poi.tagline:
                poi_info["brief"] = poi.tagline

            accessible.append(poi_info)

        return accessible

    def navigate_to_child_poi(
        self,
        hex_id: str,
        child_poi_name: str,
    ) -> dict[str, Any]:
        """
        Navigate from current POI to a child POI within it.

        For example, navigating from "Falls of Naon" to "Embassy" inside it.

        Args:
            hex_id: Current hex
            child_poi_name: Name of the child POI to enter

        Returns:
            Dictionary with navigation results
        """
        if not self._current_poi:
            return {"success": False, "error": "Must be at a location first"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        # Find the current POI
        current = None
        child = None
        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                current = poi
            if poi.name == child_poi_name:
                child = poi

        if not current:
            return {"success": False, "error": "Current location not found"}

        if not child:
            return {"success": False, "error": f"'{child_poi_name}' not found"}

        # Verify this is actually a child of current POI
        if child.parent_poi != self._current_poi:
            return {
                "success": False,
                "error": f"'{child_poi_name}' is not accessible from here",
            }

        # Check visibility with secrets
        if not child.is_visible(self._discovered_secrets):
            return {
                "success": False,
                "error": "You cannot find a way to access that location",
            }

        is_night = self._is_night()

        # Navigate to child POI
        self._current_poi = child.name
        self._poi_state = POIExplorationState.AT_ENTRANCE

        # Track visit
        visit_key = f"{hex_id}:{child.name}"
        if visit_key not in self._poi_visits:
            self._poi_visits[visit_key] = POIVisit(poi_name=child.name)

        description_parts = []
        entering_desc = child.get_entering_description(is_night)
        if entering_desc:
            description_parts.append(entering_desc)

        interior_desc = child.get_interior_description(is_night)
        if interior_desc:
            description_parts.append(interior_desc)

        return {
            "success": True,
            "poi_name": child.name,
            "poi_type": child.poi_type,
            "description": "\n\n".join(description_parts) or child.get_description(is_night),
            "is_dungeon": child.is_dungeon,
            "state": POIExplorationState.AT_ENTRANCE.value,
        }

    def navigate_to_parent_poi(self, hex_id: str) -> dict[str, Any]:
        """
        Navigate from current POI back to its parent POI.

        Args:
            hex_id: Current hex

        Returns:
            Dictionary with navigation results
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            # Still allow leaving
            self._current_poi = None
            self._poi_state = POIExplorationState.DISTANT
            return {
                "success": True,
                "message": "You leave and return to the surrounding area.",
            }

        # Find the current POI
        current = None
        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                current = poi
                break

        if not current or not current.parent_poi:
            # No parent, go back to hex level
            return self.leave_poi(hex_id)

        # Find parent POI
        parent = None
        for poi in hex_data.points_of_interest:
            if poi.name == current.parent_poi:
                parent = poi
                break

        if not parent:
            return self.leave_poi(hex_id)

        is_night = self._is_night()

        # Navigate to parent
        self._current_poi = parent.name
        self._poi_state = POIExplorationState.INSIDE

        return {
            "success": True,
            "poi_name": parent.name,
            "poi_type": parent.poi_type,
            "description": parent.get_interior_description(is_night)
            or parent.get_description(is_night),
            "state": POIExplorationState.INSIDE.value,
        }

    # =========================================================================
    # HEX-LEVEL MAGICAL EFFECTS
    # =========================================================================

    def get_hex_magical_effects(self, hex_id: str) -> HexMagicalEffects:
        """
        Get magical effects active in a hex.

        Checks both hex-level effects and current POI effects.

        Args:
            hex_id: The hex to check

        Returns:
            HexMagicalEffects with all active restrictions
        """
        effects = HexMagicalEffects()
        hex_data = self._hex_data.get(hex_id)

        if not hex_data:
            return effects

        # Check hex-level effects (from secrets or special features)
        for secret in hex_data.secrets:
            self._apply_magical_effect_from_text(secret, effects)

        # Check current POI effects
        if self._current_poi:
            for poi in hex_data.points_of_interest:
                if poi.name == self._current_poi:
                    for effect in poi.magical_effects:
                        self._apply_magical_effect_from_text(effect, effects)
                    # Also check special features
                    for feature in poi.special_features:
                        self._apply_magical_effect_from_text(feature, effects)
                    break

        return effects

    def _apply_magical_effect_from_text(self, text: str, effects: HexMagicalEffects) -> None:
        """Parse text for magical effect keywords and apply them."""
        text_lower = text.lower()

        if "no teleport" in text_lower or "teleportation impossible" in text_lower:
            effects.no_teleportation = True
        if "no scrying" in text_lower or "scrying fails" in text_lower:
            effects.no_scrying = True
        if "no divination" in text_lower or "divination blocked" in text_lower:
            effects.no_divination = True
        if "no summoning" in text_lower or "summoning fails" in text_lower:
            effects.no_summoning = True
        if "wild magic" in text_lower:
            effects.wild_magic_zone = True
        if "fairy realm" in text_lower or "faerie overlay" in text_lower:
            effects.fairy_realm_overlay = True
        if "enhanced healing" in text_lower:
            effects.enhanced_healing = True
        if "magic suppressed" in text_lower or "no magic" in text_lower:
            effects.suppressed_magic = True

        # Any other magical note becomes a custom effect
        magical_keywords = ["magic", "enchant", "spell", "curse", "bless"]
        if any(kw in text_lower for kw in magical_keywords):
            if text not in effects.custom_effects:
                effects.custom_effects.append(text)

    def check_spell_allowed(
        self,
        hex_id: str,
        spell_type: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a spell type is allowed in the current location.

        Args:
            hex_id: Current hex
            spell_type: Type of spell (teleportation, scrying, summoning, etc.)

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        effects = self.get_hex_magical_effects(hex_id)

        spell_lower = spell_type.lower()

        if effects.suppressed_magic:
            return False, "All magic is suppressed in this area"

        if "teleport" in spell_lower and effects.no_teleportation:
            return False, "Teleportation magic fails in this area"

        if "scry" in spell_lower and effects.no_scrying:
            return False, "Scrying magic is blocked here"

        if "divin" in spell_lower and effects.no_divination:
            return False, "Divination magic does not function here"

        if "summon" in spell_lower and effects.no_summoning:
            return False, "Summoning magic fails in this area"

        return True, None

    # =========================================================================
    # NPC INTERACTION AT POIs
    # =========================================================================

    def get_npcs_at_poi(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get NPCs present at the current POI.

        Args:
            hex_id: Current hex

        Returns:
            List of NPC information for interaction
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        is_night = self._is_night()
        npcs = []

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                # Get NPCs from POI
                for npc_ref in poi.npcs:
                    # Try to find full NPC data in hex
                    npc_data = None
                    for hex_npc in hex_data.npcs:
                        if hex_npc.npc_id == npc_ref or hex_npc.name == npc_ref:
                            npc_data = hex_npc
                            break

                    if npc_data:
                        npc_info = {
                            "npc_id": npc_data.npc_id,
                            "name": npc_data.name,
                            "description": npc_data.description,
                            "kindred": npc_data.kindred,
                            "met_before": npc_data.npc_id in self._met_npcs,
                        }
                        if npc_data.title:
                            npc_info["title"] = npc_data.title
                        if npc_data.demeanor:
                            npc_info["demeanor"] = (
                                npc_data.demeanor[0] if npc_data.demeanor else None
                            )
                        npcs.append(npc_info)
                    else:
                        # Minimal info from reference
                        npcs.append(
                            {
                                "name": npc_ref,
                                "met_before": npc_ref in self._met_npcs,
                            }
                        )

                # Check inhabitants field for additional NPCs
                if poi.inhabitants:
                    # Parse inhabitants string for NPC info
                    # This might be a dice notation like "1d4 bandits"
                    npcs.append(
                        {
                            "inhabitants": poi.inhabitants,
                            "is_group": True,
                        }
                    )

                break

        return npcs

    def interact_with_npc(
        self,
        hex_id: str,
        npc_id: str,
    ) -> dict[str, Any]:
        """
        Begin interaction with an NPC at the current POI.

        This transitions to SOCIAL_INTERACTION state if appropriate.

        Args:
            hex_id: Current hex
            npc_id: ID or name of NPC to interact with

        Returns:
            Dictionary with interaction setup
        """
        npcs = self.get_npcs_at_poi(hex_id)
        if not npcs:
            return {"success": False, "error": "No NPCs present here"}

        # Find the NPC
        target_npc = None
        for npc in npcs:
            if npc.get("npc_id") == npc_id or npc.get("name") == npc_id:
                target_npc = npc
                break

        if not target_npc:
            return {"success": False, "error": f"NPC '{npc_id}' not found here"}

        # Mark as met
        self._met_npcs.add(npc_id)

        # Track in POI visit
        visit_key = f"{hex_id}:{self._current_poi}"
        if visit_key in self._poi_visits:
            if npc_id not in self._poi_visits[visit_key].npcs_encountered:
                self._poi_visits[visit_key].npcs_encountered.append(npc_id)

        # Get full NPC data if available
        hex_data = self._hex_data.get(hex_id)
        npc_data = None
        if hex_data:
            for hex_npc in hex_data.npcs:
                if hex_npc.npc_id == npc_id or hex_npc.name == npc_id:
                    npc_data = hex_npc
                    break

        result = {
            "success": True,
            "npc_id": npc_id,
            "npc_name": target_npc.get("name", npc_id),
            "first_meeting": npc_id not in self._met_npcs,
        }

        if npc_data:
            result.update(
                {
                    "description": npc_data.description,
                    "demeanor": npc_data.demeanor,
                    "speech": npc_data.speech,
                    "desires": npc_data.desires,  # What they want
                }
            )

        # Trigger transition to SOCIAL_INTERACTION
        self.controller.transition(
            "initiate_conversation",
            context={
                "npc_id": npc_id,
                "npc_name": npc_name if 'npc_name' in dir() else "",
                "hex_id": hex_id,
                "poi_name": self._current_poi,
                "return_to": "wilderness",
            },
        )

        return result

    def engage_poi_npc(
        self,
        hex_id: str,
        npc_id: str,
    ) -> dict[str, Any]:
        """
        Initiate combat encounter with a combatant NPC at the current POI.

        This creates an EncounterState from the NPC's stat_reference and
        transitions to ENCOUNTER state.

        Args:
            hex_id: Current hex
            npc_id: ID or name of NPC to engage in combat

        Returns:
            Dictionary with encounter setup or error
        """
        from src.content_loader.monster_registry import get_monster_registry

        if not self._current_poi:
            return {"success": False, "error": "Not at a POI"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": f"Hex {hex_id} not loaded"}

        # Find the NPC
        target_npc = None
        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                # Check if NPC is at this POI
                if npc_id not in poi.npcs and npc_id.lower().replace(" ", "_") not in poi.npcs:
                    return {"success": False, "error": f"NPC '{npc_id}' not at this POI"}

                # Find full NPC data
                for hex_npc in hex_data.npcs:
                    if hex_npc.npc_id == npc_id or hex_npc.name == npc_id:
                        target_npc = hex_npc
                        break
                    # Also check slug form
                    if hex_npc.npc_id == npc_id.lower().replace(" ", "_"):
                        target_npc = hex_npc
                        break
                break

        if not target_npc:
            return {"success": False, "error": f"NPC '{npc_id}' not found in hex data"}

        # Check if NPC is a combatant
        if not getattr(target_npc, "is_combatant", False):
            return {
                "success": False,
                "error": f"'{target_npc.name}' is not a combatant. Use interact_with_npc for social interaction.",
            }

        # Check for stat_reference
        if not getattr(target_npc, "stat_reference", None):
            return {
                "success": False,
                "error": f"'{target_npc.name}' has no combat stats (stat_reference missing)",
            }

        # Create combatant from NPC
        registry = get_monster_registry()
        import uuid

        combatant_id = f"{target_npc.npc_id}_{uuid.uuid4().hex[:8]}"
        combatant = registry.create_combatant_from_hex_npc(
            npc=target_npc,
            combatant_id=combatant_id,
            side="enemy",
        )

        if not combatant:
            return {
                "success": False,
                "error": f"Failed to create combatant from '{target_npc.name}'",
            }

        # Check surprise
        surprise_status = self._check_surprise()
        distance = self._roll_encounter_distance(surprise_status)

        # Create EncounterState
        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,
            distance=distance,
            surprise_status=surprise_status,
            actors=[target_npc.name],
            context=f"Engaging {target_npc.name} at {self._current_poi}",
            terrain=hex_data.terrain_type,
            combatants=[combatant],
        )

        # Set encounter on controller
        self.controller.set_encounter(encounter)

        # Transition to encounter state
        self.controller.transition(
            "encounter_triggered",
            context={
                "hex_id": hex_id,
                "poi_name": self._current_poi,
                "npc_id": target_npc.npc_id,
                "npc_name": target_npc.name,
            },
        )

        return {
            "success": True,
            "encounter_id": encounter.encounter_id,
            "combatant": {
                "id": combatant.combatant_id,
                "name": combatant.name,
                "ac": combatant.stat_block.armor_class if combatant.stat_block else None,
                "hp": combatant.stat_block.hp_max if combatant.stat_block else None,
                "attacks": len(combatant.stat_block.attacks) if combatant.stat_block else 0,
            },
            "distance": distance,
            "surprise": surprise_status.value if hasattr(surprise_status, "value") else str(surprise_status),
            "context": encounter.context,
        }

    def attempt_creative_approach(
        self,
        hex_id: str,
        npc_id: str,
        approach_description: str,
        items_used: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Attempt a creative, non-combat approach to dealing with an NPC.

        Uses the Mythic GME oracle to adjudicate uncertain outcomes based on:
        - NPC desires and motivations
        - Approach plausibility
        - Items/resources used

        Args:
            hex_id: Current hex
            npc_id: ID or name of NPC to approach
            approach_description: What the player is trying to do
            items_used: Optional list of items being used in the approach

        Returns:
            Dictionary with approach result including oracle outcome
        """
        from src.oracle import MythicGME, Likelihood, FateResult

        if not self._current_poi:
            return {"success": False, "error": "Not at a POI"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": f"Hex {hex_id} not loaded"}

        # Find the NPC
        target_npc = None
        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                # Find full NPC data
                for hex_npc in hex_data.npcs:
                    if hex_npc.npc_id == npc_id or hex_npc.name == npc_id:
                        target_npc = hex_npc
                        break
                    if hex_npc.npc_id == npc_id.lower().replace(" ", "_"):
                        target_npc = hex_npc
                        break
                break

        if not target_npc:
            return {"success": False, "error": f"NPC '{npc_id}' not found"}

        # Analyze the approach against NPC characteristics
        likelihood = self._evaluate_approach_likelihood(
            target_npc, approach_description, items_used or []
        )

        # Use Mythic GME for fate check
        mythic = MythicGME(chaos_factor=5)  # Default balanced chaos

        # Formulate the question based on approach
        question = self._formulate_approach_question(
            target_npc, approach_description
        )

        fate_result = mythic.fate_check(question, likelihood)

        # Build result based on oracle outcome
        result = self._interpret_creative_result(
            target_npc, approach_description, fate_result, items_used or []
        )

        return result

    def _evaluate_approach_likelihood(
        self,
        npc: Any,  # HexNPC
        approach: str,
        items_used: list[str],
    ) -> "Likelihood":
        """
        Evaluate how likely an approach is to succeed based on NPC traits.

        Args:
            npc: The target NPC
            approach: Description of the approach
            items_used: Items being used

        Returns:
            Likelihood enum for Mythic GME
        """
        from src.oracle import Likelihood

        approach_lower = approach.lower()
        base_likelihood = Likelihood.UNLIKELY  # Default: creative solutions are hard

        # Check NPC desires - if approach aligns with desires, increase likelihood
        npc_desires = getattr(npc, "desires", []) or []
        for desire in npc_desires:
            desire_lower = desire.lower()

            # Direct alignment with desire
            if any(word in approach_lower for word in desire_lower.split()):
                base_likelihood = Likelihood.LIKELY
                break

            # Offering what they want (magic for magic-hungry, etc.)
            if "magic" in desire_lower and "magic" in approach_lower:
                base_likelihood = Likelihood.LIKELY
                break
            if "feed" in desire_lower and ("food" in approach_lower or "bait" in approach_lower):
                base_likelihood = Likelihood.LIKELY
                break

        # Check NPC intelligence/alignment for modifiers
        npc_kindred = getattr(npc, "kindred", "").lower()
        npc_alignment = getattr(npc, "alignment", "").lower()

        # Animal intelligence creatures are easier to manipulate with basic desires
        if "animal" in str(getattr(npc, "stat_reference", "")).lower():
            if "lure" in approach_lower or "bait" in approach_lower or "distract" in approach_lower:
                # Upgrade likelihood for simple creature manipulation
                if base_likelihood == Likelihood.UNLIKELY:
                    base_likelihood = Likelihood.FIFTY_FIFTY
                elif base_likelihood == Likelihood.FIFTY_FIFTY:
                    base_likelihood = Likelihood.LIKELY

        # Using magical items on magic-hungry creatures
        if items_used:
            items_lower = " ".join(items_used).lower()
            if "magic" in items_lower or "enchant" in items_lower or "spell" in items_lower:
                for desire in npc_desires:
                    if "magic" in desire.lower():
                        base_likelihood = Likelihood.LIKELY
                        break

        # Hostile/predatory NPCs are harder to negotiate with
        npc_demeanor = getattr(npc, "demeanor", []) or []
        if any("predator" in d.lower() or "hostile" in d.lower() for d in npc_demeanor):
            if base_likelihood.value > Likelihood.UNLIKELY.value:
                # Reduce by one step
                base_likelihood = Likelihood(max(base_likelihood.value - 1, 0))

        # Check if approach leverages known vulnerabilities (significant boost)
        npc_vulnerabilities = getattr(npc, "vulnerabilities", []) or []
        for vuln in npc_vulnerabilities:
            vuln_lower = vuln.lower().replace("_", " ")
            if vuln_lower in approach_lower or vuln.lower() in approach_lower:
                # Leveraging vulnerability is very effective
                base_likelihood = Likelihood.VERY_LIKELY
                break
            # Also check items used for vulnerabilities
            if items_used:
                items_lower = " ".join(items_used).lower()
                if vuln_lower in items_lower or vuln.lower() in items_lower:
                    base_likelihood = Likelihood.VERY_LIKELY
                    break

        return base_likelihood

    def _formulate_approach_question(
        self,
        npc: Any,  # HexNPC
        approach: str,
    ) -> str:
        """
        Formulate a yes/no question for the oracle.

        Args:
            npc: The target NPC
            approach: The approach description

        Returns:
            A yes/no question string
        """
        npc_name = getattr(npc, "name", "the creature")

        # Determine what kind of outcome we're checking
        approach_lower = approach.lower()

        if "lure" in approach_lower or "bait" in approach_lower:
            return f"Is {npc_name} successfully lured away?"
        elif "distract" in approach_lower:
            return f"Is {npc_name} distracted long enough?"
        elif "scare" in approach_lower or "frighten" in approach_lower:
            return f"Is {npc_name} frightened into leaving?"
        elif "convince" in approach_lower or "persuade" in approach_lower:
            return f"Is {npc_name} convinced by this approach?"
        elif "sneak" in approach_lower or "avoid" in approach_lower:
            return f"Can the party bypass {npc_name} unnoticed?"
        elif "trick" in approach_lower or "deceive" in approach_lower:
            return f"Is {npc_name} fooled by the deception?"
        else:
            return f"Does the creative approach to {npc_name} succeed?"

    def _interpret_creative_result(
        self,
        npc: Any,  # HexNPC
        approach: str,
        fate_result: Any,  # FateCheckResult
        items_used: list[str],
    ) -> dict[str, Any]:
        """
        Interpret the oracle result into a structured game outcome.

        Args:
            npc: The target NPC
            approach: The approach attempted
            fate_result: Result from Mythic GME
            items_used: Items used in the approach

        Returns:
            Structured result dictionary
        """
        from src.oracle import FateResult

        npc_name = getattr(npc, "name", "the creature")
        npc_desires = getattr(npc, "desires", []) or []

        result = {
            "success": False,
            "npc_id": getattr(npc, "npc_id", "unknown"),
            "npc_name": npc_name,
            "approach": approach,
            "items_used": items_used,
            "oracle": {
                "question": fate_result.question,
                "likelihood": fate_result.likelihood.name,
                "roll": fate_result.roll,
                "result": fate_result.result.value,
            },
            "narrative_hints": [],
            "mechanical_effects": [],
            "follow_up_options": [],
        }

        # Interpret based on fate result
        if fate_result.result == FateResult.EXCEPTIONAL_YES:
            result["success"] = True
            result["outcome"] = "exceptional_success"
            result["narrative_hints"] = [
                f"{npc_name} is completely taken by the approach",
                "the plan works even better than expected",
                "an unexpected bonus or advantage emerges",
            ]
            result["mechanical_effects"] = [
                "npc_leaves_area",
                "no_combat_required",
                "bonus_opportunity",
            ]
            result["follow_up_options"] = [
                "claim_objective",
                "explore_bonus",
                "press_advantage",
            ]

        elif fate_result.result == FateResult.YES:
            result["success"] = True
            result["outcome"] = "success"
            result["narrative_hints"] = [
                f"{npc_name} responds to the approach",
                "the creative solution works",
            ]
            result["mechanical_effects"] = [
                "npc_temporarily_distracted" if "distract" in approach.lower()
                else "npc_leaves_area",
            ]
            result["follow_up_options"] = [
                "proceed_carefully",
                "claim_objective",
            ]

        elif fate_result.result == FateResult.NO:
            result["success"] = False
            result["outcome"] = "failure"
            result["narrative_hints"] = [
                f"{npc_name} is not fooled or interested",
                "the approach doesn't work as planned",
            ]
            result["mechanical_effects"] = [
                "npc_alerted" if "sneak" in approach.lower() else "npc_unaffected",
            ]
            result["follow_up_options"] = [
                "try_different_approach",
                "attempt_combat",
                "retreat",
            ]

        elif fate_result.result == FateResult.EXCEPTIONAL_NO:
            result["success"] = False
            result["outcome"] = "catastrophic_failure"
            result["narrative_hints"] = [
                f"{npc_name} reacts violently to the attempt",
                "the situation escalates dangerously",
                "combat may be unavoidable",
            ]
            result["mechanical_effects"] = [
                "npc_hostile",
                "surprise_lost",
                "immediate_reaction",
            ]
            result["follow_up_options"] = [
                "prepare_for_combat",
                "flee",
            ]

        # Add random event if triggered
        if fate_result.random_event_triggered and fate_result.random_event:
            result["random_event"] = {
                "focus": fate_result.random_event.focus.value,
                "meaning": fate_result.random_event.meaning_pair,
            }
            result["narrative_hints"].append(
                f"unexpected twist: {fate_result.random_event.meaning_pair}"
            )

        # Add context about NPC desires for narration
        if npc_desires:
            result["npc_context"] = {
                "desires": npc_desires,
                "can_leverage": any(
                    d.lower() in approach.lower() for d in npc_desires
                ),
            }

        return result

    # =========================================================================
    # ENVIRONMENTAL CREATIVE SOLUTIONS
    # =========================================================================

    # Known patterns for avoiding/mitigating environmental hazards
    ENVIRONMENTAL_PATTERNS = {
        "avoid_sleep": {
            "triggers": ["stay awake", "take shifts", "watch", "guard", "no sleep"],
            "check_type": "constitution",
            "difficulty": 12,
            "time_cost_hours": 8,
            "success_effect": "hazard_avoided",
            "failure_effect": "exhaustion",
        },
        "create_shelter": {
            "triggers": ["tent", "shelter", "cover", "seal", "ward", "protect"],
            "check_type": "auto_success",
            "conditions": ["has_shelter_materials"],
            "success_effect": "hazard_blocked",
        },
        "magical_protection": {
            "triggers": ["cast", "spell", "magic", "ward", "protection"],
            "check_type": "auto_success",
            "conditions": ["has_protective_spell"],
            "success_effect": "hazard_blocked",
        },
        "navigate_maze": {
            "triggers": ["rope", "mark", "trail", "compass", "climb", "vantage"],
            "check_type": "wisdom",
            "difficulty": 10,
            "success_effect": "navigation_bonus",
        },
        "avoid_hazard_area": {
            "triggers": ["avoid", "go around", "detour", "bypass"],
            "check_type": "auto_success",
            "time_cost_hours": 4,
            "success_effect": "hazard_avoided",
        },
    }

    def attempt_environmental_solution(
        self,
        hex_id: str,
        hazard_type: str,
        approach_description: str,
        items_used: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Attempt creative solution to environmental hazard.

        Handles hazards like night_hazard (mist, dreamlessness), terrain
        challenges (maze navigation), and other environmental obstacles.

        Args:
            hex_id: Current hex
            hazard_type: Type of hazard ("night_hazard", "terrain", "lost")
            approach_description: What the player is trying to do
            items_used: Optional list of items being used

        Returns:
            Dictionary with solution result
        """
        from src.oracle import MythicGME, Likelihood

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": f"Hex {hex_id} not loaded"}

        # Get hazard info from hex procedural data
        hazard_info = self._get_hazard_info(hex_data, hazard_type)
        if not hazard_info:
            return {"success": False, "error": f"No {hazard_type} found in hex"}

        # Match approach against known patterns
        pattern_match = self._match_environmental_pattern(
            approach_description, items_used or []
        )

        approach_lower = approach_description.lower()

        if pattern_match:
            # Use matched pattern for resolution
            return self._resolve_environmental_pattern(
                pattern_match, hazard_info, approach_description, items_used or []
            )
        else:
            # Use oracle for unknown approaches
            mythic = MythicGME(chaos_factor=5)

            question = f"Does the creative approach to avoid {hazard_info.get('description', hazard_type)} succeed?"
            likelihood = Likelihood.FIFTY_FIFTY

            # Boost likelihood if using relevant items
            if items_used:
                items_lower = " ".join(items_used).lower()
                if any(word in items_lower for word in ["tent", "shelter", "rope", "magic", "ward"]):
                    likelihood = Likelihood.LIKELY

            fate_result = mythic.fate_check(question, likelihood)

            return self._interpret_environmental_result(
                hazard_info, approach_description, fate_result, items_used or []
            )

    def _get_hazard_info(
        self, hex_data: Any, hazard_type: str
    ) -> Optional[dict[str, Any]]:
        """Extract hazard information from hex procedural data."""
        proc = getattr(hex_data, "procedural", None)
        if not proc:
            return None

        if hazard_type == "night_hazard":
            night_hazards = getattr(proc, "night_hazards", None)
            if night_hazards and len(night_hazards) > 0:
                hazard = night_hazards[0]
                if isinstance(hazard, dict):
                    return {
                        "type": "night_hazard",
                        "trigger": hazard.get("trigger", "sleep"),
                        "save_type": hazard.get("save_type", "doom"),
                        "description": hazard.get("description", "night hazard"),
                        "on_fail": hazard.get("on_fail", {}),
                    }
        elif hazard_type == "lost" or hazard_type == "terrain":
            lost_behavior = getattr(proc, "lost_behavior", None)
            if lost_behavior:
                return {
                    "type": "terrain",
                    "description": lost_behavior.get("description", "maze-like terrain"),
                    "escape_requires": lost_behavior.get("escape_requires", "successful_lost_check"),
                }
            else:
                return {
                    "type": "terrain",
                    "description": f"difficult {hex_data.terrain_type} terrain",
                    "lost_chance": getattr(proc, "lost_chance", "1-in-6"),
                }

        return None

    def _match_environmental_pattern(
        self, approach: str, items_used: list[str]
    ) -> Optional[dict[str, Any]]:
        """Match approach against known environmental solution patterns."""
        approach_lower = approach.lower()
        items_lower = " ".join(items_used).lower() if items_used else ""

        for pattern_name, pattern in self.ENVIRONMENTAL_PATTERNS.items():
            triggers = pattern.get("triggers", [])
            for trigger in triggers:
                if trigger in approach_lower or trigger in items_lower:
                    return {"name": pattern_name, **pattern}

        return None

    def _resolve_environmental_pattern(
        self,
        pattern: dict[str, Any],
        hazard_info: dict[str, Any],
        approach: str,
        items_used: list[str],
    ) -> dict[str, Any]:
        """Resolve using a matched environmental pattern."""
        check_type = pattern.get("check_type", "auto_success")
        success = False
        check_result = None

        if check_type == "auto_success":
            # Check conditions if any
            conditions = pattern.get("conditions", [])
            if conditions:
                # For now, assume conditions are met if relevant items are used
                items_lower = " ".join(items_used).lower() if items_used else ""
                if "has_shelter_materials" in conditions:
                    success = any(w in items_lower for w in ["tent", "tarp", "shelter"])
                elif "has_protective_spell" in conditions:
                    success = any(w in items_lower for w in ["scroll", "wand", "spell", "ward"])
                else:
                    success = True
            else:
                success = True
        else:
            # Roll check
            difficulty = pattern.get("difficulty", 12)
            roll = DiceRoller.roll("1d20", f"Environmental check ({check_type})")
            check_result = roll.total
            success = roll.total >= difficulty

        result = {
            "success": success,
            "pattern_used": pattern.get("name", "unknown"),
            "hazard_type": hazard_info.get("type", "unknown"),
            "approach": approach,
            "items_used": items_used,
            "narrative_hints": [],
            "mechanical_effects": [],
        }

        if check_result is not None:
            result["check"] = {
                "type": check_type,
                "roll": check_result,
                "difficulty": pattern.get("difficulty", 12),
            }

        if success:
            result["outcome"] = pattern.get("success_effect", "hazard_avoided")
            result["narrative_hints"] = [
                "the creative approach works",
                f"the {hazard_info.get('type', 'hazard')} is avoided or mitigated",
            ]
            result["mechanical_effects"] = [pattern.get("success_effect", "hazard_avoided")]

            if pattern.get("time_cost_hours"):
                result["time_cost_hours"] = pattern["time_cost_hours"]
                result["narrative_hints"].append(
                    f"this takes {pattern['time_cost_hours']} hours"
                )
        else:
            result["outcome"] = pattern.get("failure_effect", "hazard_not_avoided")
            result["narrative_hints"] = [
                "the approach doesn't fully work",
                f"the {hazard_info.get('type', 'hazard')} still poses a threat",
            ]
            result["mechanical_effects"] = ["partial_mitigation"]

        return result

    def _interpret_environmental_result(
        self,
        hazard_info: dict[str, Any],
        approach: str,
        fate_result: Any,
        items_used: list[str],
    ) -> dict[str, Any]:
        """Interpret oracle result for environmental solution."""
        from src.oracle import FateResult

        result = {
            "success": False,
            "hazard_type": hazard_info.get("type", "unknown"),
            "approach": approach,
            "items_used": items_used,
            "oracle": {
                "question": fate_result.question,
                "likelihood": fate_result.likelihood.name,
                "roll": fate_result.roll,
                "result": fate_result.result.value,
            },
            "narrative_hints": [],
            "mechanical_effects": [],
        }

        if fate_result.result == FateResult.EXCEPTIONAL_YES:
            result["success"] = True
            result["outcome"] = "exceptional_success"
            result["narrative_hints"] = [
                "the creative solution works perfectly",
                "additional benefit discovered",
            ]
            result["mechanical_effects"] = ["hazard_avoided", "bonus_discovered"]

        elif fate_result.result == FateResult.YES:
            result["success"] = True
            result["outcome"] = "success"
            result["narrative_hints"] = [
                "the approach successfully mitigates the hazard",
            ]
            result["mechanical_effects"] = ["hazard_avoided"]

        elif fate_result.result == FateResult.NO:
            result["success"] = False
            result["outcome"] = "failure"
            result["narrative_hints"] = [
                "the approach doesn't work as planned",
                f"the {hazard_info.get('description', 'hazard')} remains a threat",
            ]
            result["mechanical_effects"] = ["hazard_active"]

        elif fate_result.result == FateResult.EXCEPTIONAL_NO:
            result["success"] = False
            result["outcome"] = "catastrophic_failure"
            result["narrative_hints"] = [
                "the attempt backfires",
                "the situation becomes more dangerous",
            ]
            result["mechanical_effects"] = ["hazard_worsened"]

        return result

    # =========================================================================
    # FACTION RELATIONSHIP TRACKING
    # =========================================================================

    def get_faction_state(self, hex_id: str) -> FactionState:
        """
        Get or create faction state for a hex.

        Args:
            hex_id: The hex ID

        Returns:
            FactionState for the hex
        """
        if hex_id not in self._faction_states:
            self._faction_states[hex_id] = FactionState(hex_id=hex_id)
            # Initialize from hex NPC data if available
            self._initialize_faction_state(hex_id)
        return self._faction_states[hex_id]

    def _initialize_faction_state(self, hex_id: str) -> None:
        """
        Initialize faction relationships from hex NPC data.

        Parses NPC faction/loyalty fields and faction_relationships
        in hex JSON to populate initial relationship state.
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return

        faction_state = self._faction_states[hex_id]

        # Parse NPC relationships
        for npc in hex_data.npcs:
            npc_id = getattr(npc, "npc_id", None)
            if not npc_id:
                continue

            # Check faction/loyalty fields
            faction = getattr(npc, "faction", None)
            loyalty = getattr(npc, "loyalty", "loyal")

            if faction:
                # Create relationship to faction/employer
                disposition = {
                    "loyal": 75,
                    "bought": 40,
                    "coerced": 20,
                    "secret_traitor": -50,
                }.get(loyalty, 50)

                faction_state.relationships.append(FactionRelationship(
                    entity_a=npc_id,
                    entity_b=faction,
                    disposition=disposition,
                    relationship_type="employer",
                    loyalty_basis="payment" if loyalty == "bought" else (
                        "fear" if loyalty == "coerced" else "ideology"
                    ),
                ))

            # Parse explicit relationships list
            relationships = getattr(npc, "relationships", [])
            for rel in relationships:
                if isinstance(rel, dict):
                    target_id = rel.get("npc_id", "")
                    rel_type = rel.get("relationship_type", "neutral")

                    disposition = {
                        "ally": 60,
                        "family": 80,
                        "employer": 50,
                        "subordinate": 30,
                        "rival": -20,
                        "enemy": -75,
                    }.get(rel_type, 0)

                    faction_state.relationships.append(FactionRelationship(
                        entity_a=npc_id,
                        entity_b=target_id,
                        disposition=disposition,
                        relationship_type=rel_type,
                    ))

    def get_npc_disposition_to_party(self, hex_id: str, npc_id: str) -> int:
        """Get an NPC's disposition toward the party."""
        faction_state = self.get_faction_state(hex_id)
        return faction_state.get_party_reputation(npc_id)

    def modify_npc_disposition_to_party(
        self, hex_id: str, npc_id: str, delta: int, reason: str = ""
    ) -> int:
        """
        Modify an NPC's disposition toward the party.

        Args:
            hex_id: Current hex
            npc_id: NPC whose disposition changes
            delta: Amount to change (-100 to +100 scale)
            reason: Optional reason for logging

        Returns:
            New disposition value
        """
        faction_state = self.get_faction_state(hex_id)
        return faction_state.modify_party_reputation(npc_id, delta)

    def get_turnable_npcs(self, hex_id: str, target: str) -> list[dict[str, Any]]:
        """
        Get list of NPCs who could be turned against a target.

        Useful for creative approaches like "convince the ruffians to
        betray Sidney."

        Args:
            hex_id: Current hex
            target: NPC/faction to turn others against

        Returns:
            List of {npc_id, current_loyalty, loyalty_basis} dicts
        """
        faction_state = self.get_faction_state(hex_id)
        turnable_ids = faction_state.get_turnable_npcs(target)

        result = []
        for npc_id in turnable_ids:
            rel = faction_state.get_relationship(npc_id, target)
            if rel:
                result.append({
                    "npc_id": npc_id,
                    "current_loyalty": rel.disposition,
                    "loyalty_basis": rel.loyalty_basis,
                    "relationship_type": rel.relationship_type,
                })
        return result

    def attempt_turn_npc(
        self,
        hex_id: str,
        npc_id: str,
        against: str,
        approach: str,
        incentive: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Attempt to turn an NPC against their employer/ally.

        Uses faction state + oracle to determine success.

        Args:
            hex_id: Current hex
            npc_id: NPC to turn
            against: Target they'd betray
            approach: How player is trying to turn them
            incentive: What's being offered (money, safety, etc.)

        Returns:
            Result dict with success, new disposition, narrative hints
        """
        from src.oracle import MythicGME, Likelihood

        faction_state = self.get_faction_state(hex_id)
        rel = faction_state.get_relationship(npc_id, against)

        if not rel:
            return {
                "success": False,
                "error": f"No relationship found between {npc_id} and {against}",
            }

        # Determine base likelihood from current loyalty
        if rel.disposition >= 75:
            base = Likelihood.VERY_UNLIKELY
        elif rel.disposition >= 50:
            base = Likelihood.UNLIKELY
        elif rel.disposition >= 25:
            base = Likelihood.FIFTY_FIFTY
        elif rel.disposition >= 0:
            base = Likelihood.LIKELY
        else:
            base = Likelihood.VERY_LIKELY

        # Modify based on loyalty basis
        if rel.loyalty_basis == "payment" and incentive and "money" in incentive.lower():
            # Bought loyalty can be outbought
            base = Likelihood(min(base.value + 2, 9))
        elif rel.loyalty_basis == "fear":
            # Fear-based loyalty can be broken with protection offer
            if incentive and any(w in incentive.lower() for w in ["protect", "safe", "escape"]):
                base = Likelihood(min(base.value + 2, 9))
        elif rel.loyalty_basis == "ideology":
            # Ideological loyalty is hardest to break
            base = Likelihood(max(base.value - 1, 0))

        # Use oracle
        mythic = MythicGME(chaos_factor=5)
        question = f"Can {npc_id} be convinced to turn against {against}?"
        fate_result = mythic.fate_check(question, base)

        from src.oracle import FateResult

        result = {
            "npc_id": npc_id,
            "target": against,
            "approach": approach,
            "incentive": incentive,
            "oracle": {
                "question": question,
                "likelihood": base.name,
                "roll": fate_result.roll,
                "result": fate_result.result.value,
            },
            "narrative_hints": [],
            "mechanical_effects": [],
        }

        if fate_result.result in [FateResult.YES, FateResult.EXCEPTIONAL_YES]:
            result["success"] = True
            # Flip the relationship
            faction_state.modify_disposition(npc_id, against, -75)
            result["new_disposition"] = faction_state.get_disposition(npc_id, against)
            result["narrative_hints"] = [
                f"{npc_id} agrees to betray {against}",
                "a new alliance is formed",
            ]
            result["mechanical_effects"] = ["npc_turned", "new_ally"]

            if fate_result.result == FateResult.EXCEPTIONAL_YES:
                result["narrative_hints"].append("they're eager to help")
                result["mechanical_effects"].append("bonus_information")
        else:
            result["success"] = False
            result["narrative_hints"] = [
                f"{npc_id} refuses to betray {against}",
            ]
            result["mechanical_effects"] = ["attempt_failed"]

            if fate_result.result == FateResult.EXCEPTIONAL_NO:
                # They report to their employer!
                result["narrative_hints"].append(f"they warn {against} about the attempt")
                result["mechanical_effects"].append("target_alerted")
                faction_state.modify_party_reputation(against, -30)

        return result

    # =========================================================================
    # ENCOUNTER GENERATION FOR POI INHABITANTS
    # =========================================================================

    def generate_poi_encounter(
        self,
        hex_id: str,
    ) -> Optional[EncounterState]:
        """
        Generate an encounter with inhabitants at the current POI.

        If inhabitants field uses dice notation (e.g., "2d6 bandits"),
        rolls for number appearing and creates an encounter.

        Args:
            hex_id: Current hex

        Returns:
            EncounterState if inhabitants present, None otherwise
        """
        if not self._current_poi:
            return None

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return None

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                if not poi.inhabitants:
                    return None

                # Parse inhabitants string
                inhabitants = poi.inhabitants
                number_appearing = 1
                creature_type = inhabitants

                # Check for dice notation (e.g., "2d6 orcs", "1d4+1 guards")
                import re

                dice_match = re.match(r"(\d+d\d+(?:[+-]\d+)?)\s+(.+)", inhabitants)
                if dice_match:
                    dice_notation = dice_match.group(1)
                    creature_type = dice_match.group(2)
                    roll_result = self.dice.roll(dice_notation, f"inhabitants at {poi.name}")
                    number_appearing = roll_result.total

                # Check surprise
                surprise = self._check_surprise()
                distance = self._roll_encounter_distance(surprise)

                encounter = EncounterState(
                    encounter_type=EncounterType.NPC,  # Could be MONSTER depending on creature
                    distance=distance,
                    surprise_status=surprise,
                    actors=[creature_type],
                    context=f"encountered at {poi.name}",
                    terrain=hex_data.terrain_type,
                )

                # Store number appearing in encounter
                encounter.context = f"{number_appearing} {creature_type} at {poi.name}"

                # Transition to encounter state
                self.controller.set_encounter(encounter)
                self.controller.transition(
                    "encounter_triggered",
                    context={
                        "hex_id": hex_id,
                        "poi_name": poi.name,
                        "creatures": creature_type,
                        "number": number_appearing,
                    },
                )

                return encounter

        return None

    def evaluate_reaction_conditions(
        self,
        reaction_conditions: dict[str, Any],
        party_alignments: list[str],
    ) -> dict[str, Any]:
        """
        Evaluate alignment-based reaction conditions for a roll table entry.

        This is used by the ENCOUNTERS state to determine creature reactions
        based on party member alignments (e.g., "attacks non-Neutral characters").

        Args:
            reaction_conditions: The reaction_conditions from RollTableEntry
                Format: {hostile_if: {alignment_not: ["Neutral"]},
                        friendly_if: {alignment: ["Lawful"]}}
            party_alignments: List of party member alignments

        Returns:
            Dictionary with reaction modification:
            {
                "hostile": True/False,
                "friendly": True/False,
                "affected_alignments": [...],
                "description": str
            }
        """
        result = {
            "hostile": False,
            "friendly": False,
            "affected_alignments": [],
            "description": "",
        }

        if not reaction_conditions or not party_alignments:
            return result

        # Check hostile conditions
        hostile_if = reaction_conditions.get("hostile_if", {})
        if hostile_if:
            # Check alignment_not condition (hostile to those NOT in list)
            alignment_not = hostile_if.get("alignment_not", [])
            if alignment_not:
                non_matching = [align for align in party_alignments if align not in alignment_not]
                if non_matching:
                    result["hostile"] = True
                    result["affected_alignments"] = non_matching
                    result["description"] = (
                        f"Hostile toward {', '.join(alignment_not)}-aligned characters"
                    )

            # Check alignment condition (hostile to those IN list)
            alignment_match = hostile_if.get("alignment", [])
            if alignment_match:
                matching = [align for align in party_alignments if align in alignment_match]
                if matching:
                    result["hostile"] = True
                    result["affected_alignments"] = matching
                    result["description"] = (
                        f"Hostile toward {', '.join(matching)}-aligned characters"
                    )

        # Check friendly conditions
        friendly_if = reaction_conditions.get("friendly_if", {})
        if friendly_if:
            alignment_match = friendly_if.get("alignment", [])
            if alignment_match:
                matching = [align for align in party_alignments if align in alignment_match]
                if matching:
                    result["friendly"] = True
                    if not result["hostile"]:
                        result["affected_alignments"] = matching
                        result["description"] = (
                            f"Friendly toward {', '.join(matching)}-aligned characters"
                        )

        return result

    def get_poi_roll_tables(self, hex_id: str, poi_name: Optional[str] = None) -> list["RollTable"]:
        """
        Get roll tables from a POI for use in ENCOUNTERS or DUNGEON states.

        This allows encounters and dungeon exploration to use POI-specific
        room tables and encounter tables.

        Args:
            hex_id: The hex ID
            poi_name: Optional POI name (defaults to current POI)

        Returns:
            List of RollTable objects from the POI
        """
        target_poi = poi_name or self._current_poi
        if not target_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        for poi in hex_data.points_of_interest:
            if poi.name == target_poi:
                return poi.roll_tables

        return []

    def roll_on_poi_table(
        self, hex_id: str, table_name: str, poi_name: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Roll on a POI's roll table from the wilderness.

        This allows accessing POI roll tables (like "Leavings in the Mud")
        without entering a dungeon, useful for treasure_site POIs.

        For tables with unique_entries=True, tracks which entries have been
        found and re-rolls duplicates.

        Args:
            hex_id: The hex ID
            table_name: Name of the table to roll on
            poi_name: Optional POI name (defaults to current POI)

        Returns:
            Dictionary with roll result, or None if table not found.
            Returns {"exhausted": True} if all unique entries have been found.
        """
        target_poi = poi_name or self._current_poi
        if not target_poi:
            return None

        tables = self.get_poi_roll_tables(hex_id, target_poi)
        if not tables:
            return None

        # Find the target table
        target_table = None
        for table in tables:
            if table.name.lower() == table_name.lower():
                target_table = table
                break

        if not target_table:
            return None

        # For unique entry tables, check session manager
        session_mgr = self.controller.session_manager
        if target_table.unique_entries and session_mgr:
            all_roll_values = [e.roll for e in target_table.entries]
            unfound = session_mgr.get_unfound_roll_table_entries(
                hex_id, target_poi, table_name, all_roll_values
            )
            if not unfound:
                return {
                    "exhausted": True,
                    "table": table_name,
                    "poi": target_poi,
                    "message": f"All entries in {table_name} have been found.",
                }
            # Roll until we get an unfound entry
            max_attempts = 20
            for _ in range(max_attempts):
                roll = self.dice.roll(f"1{target_table.die_type}", f"roll on {table_name}")
                if roll.total in unfound:
                    break
            else:
                # Fallback: pick random unfound entry
                import random
                roll_value = random.choice(unfound)
                roll = type("Roll", (), {"total": roll_value})()
        else:
            # Regular roll
            roll = self.dice.roll(f"1{target_table.die_type}", f"roll on {table_name}")

        # Find the entry
        entry = None
        for e in target_table.entries:
            if e.roll == roll.total:
                entry = e
                break

        if not entry:
            return {"roll": roll.total, "table": table_name, "poi": target_poi, "entry": None}

        # Mark entry as found for unique tables
        if target_table.unique_entries and session_mgr:
            session_mgr.mark_roll_table_entry_found(
                hex_id, target_poi, table_name, roll.total
            )

        return {
            "roll": roll.total,
            "table": table_name,
            "poi": target_poi,
            "title": entry.title,
            "description": entry.description,
            "monsters": entry.monsters,
            "npcs": entry.npcs,
            "items": entry.items,
            "mechanical_effect": entry.mechanical_effect,
            "sub_table": entry.sub_table,
            "quest_hook": entry.quest_hook,
        }

    def get_poi_dungeon_config(
        self, hex_id: str, poi_name: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Get dungeon configuration for a POI with dynamic layout.

        Returns the dynamic_layout, item_persistence, and roll_tables
        needed for the DUNGEON_EXPLORATION state.

        Args:
            hex_id: The hex ID
            poi_name: Optional POI name (defaults to current POI)

        Returns:
            Dictionary with dungeon configuration or None
        """
        target_poi = poi_name or self._current_poi
        if not target_poi:
            return None

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return None

        for poi in hex_data.points_of_interest:
            if poi.name == target_poi:
                if not poi.is_dungeon:
                    return None

                return {
                    "poi_name": poi.name,
                    "dungeon_levels": poi.dungeon_levels,
                    "dynamic_layout": poi.dynamic_layout,
                    "item_persistence": poi.item_persistence,
                    "roll_tables": poi.roll_tables,
                    "room_table": self._find_table_by_name(poi.roll_tables, "Rooms"),
                    "encounter_table": self._find_table_by_name(poi.roll_tables, "Encounters"),
                    "interior": poi.interior,
                    "exploring": poi.exploring,
                    "leaving": poi.leaving,
                }

        return None

    def _find_table_by_name(self, tables: list["RollTable"], name: str) -> Optional["RollTable"]:
        """Find a roll table by name (case-insensitive)."""
        for table in tables:
            if table.name.lower() == name.lower():
                return table
        return None

    # =========================================================================
    # ITEM AND TREASURE TRACKING AT POIs
    # =========================================================================

    def get_items_at_poi(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get visible items at the current POI.

        Args:
            hex_id: Current hex

        Returns:
            List of items available at this POI
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                # Filter out already taken items from multiple sources:
                # 1. Engine-local visit tracking
                # 2. Persistent session delta
                # 3. Item's own "taken" flag
                visit_key = f"{hex_id}:{self._current_poi}"
                taken_items = set()

                # Check engine-local visit state
                if visit_key in self._poi_visits:
                    taken_items.update(self._poi_visits[visit_key].items_taken)

                # Check persistent session delta
                if hasattr(self.controller, "session_manager") and self.controller.session_manager:
                    session_taken = self.controller.session_manager.get_items_taken_from_poi(
                        hex_id, self._current_poi
                    )
                    taken_items.update(session_taken)

                available_items = []
                for item in poi.items:
                    item_name = item.get("name", "unknown")
                    if item_name not in taken_items and not item.get("taken", False):
                        available_items.append(
                            {
                                "name": item_name,
                                "description": item.get("description", ""),
                                "value": item.get("value"),
                                "is_unique": item.get("is_unique", False),
                            }
                        )

                return available_items

        return []

    def take_item(
        self,
        hex_id: str,
        item_name: str,
        character_id: str,
    ) -> dict[str, Any]:
        """
        Take an item from the current POI and add to character inventory.

        Items are tracked at the hex/POI level so they no longer appear
        once taken. Unique items are also registered globally.

        Args:
            hex_id: Current hex
            item_name: Name of item to take
            character_id: Character taking the item

        Returns:
            Dictionary with result and item details
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                # Find the item
                for item in poi.items:
                    if item.get("name", "").lower() == item_name.lower():
                        # Check if already taken (shouldn't appear in available items, but safety check)
                        if item.get("taken", False):
                            return {"success": False, "error": "Item not found here"}

                        # Check acquisition condition if present
                        acquisition_condition = item.get("acquisition_condition")
                        if acquisition_condition:
                            session_mgr = None
                            if (
                                hasattr(self.controller, "session_manager")
                                and self.controller.session_manager
                            ):
                                session_mgr = self.controller.session_manager

                            if session_mgr:
                                is_satisfied, reason = check_acquisition_condition(
                                    condition_text=acquisition_condition,
                                    hex_id=hex_id,
                                    session_manager=session_mgr,
                                    controller=self.controller,
                                )
                                if not is_satisfied:
                                    return {
                                        "success": False,
                                        "error": reason,
                                        "condition_blocked": True,
                                        "acquisition_condition": acquisition_condition,
                                    }

                        # Check if this is a unique item
                        is_unique = item.get("is_unique", False)
                        unique_item_id = item.get("unique_item_id")

                        # Construct unique ID if not provided but marked unique
                        if is_unique and not unique_item_id:
                            unique_item_id = f"{hex_id}:{self._current_poi}:{item.get('name')}"

                        # Mark as taken in POI data
                        item["taken"] = True

                        # Track in engine-local visit state
                        visit_key = f"{hex_id}:{self._current_poi}"
                        if visit_key in self._poi_visits:
                            self._poi_visits[visit_key].items_taken.append(item.get("name"))
                            if item.get("name") not in self._poi_visits[visit_key].items_found:
                                self._poi_visits[visit_key].items_found.append(item.get("name"))

                        # Persist to session manager (for cross-session tracking)
                        if (
                            hasattr(self.controller, "session_manager")
                            and self.controller.session_manager
                        ):
                            self.controller.session_manager.add_item_taken(
                                hex_id=hex_id,
                                poi_name=self._current_poi,
                                item_name=item.get("name"),
                            )

                            # Also register in unique item registry for global tracking
                            if is_unique and unique_item_id:
                                self.controller.session_manager.register_unique_item(
                                    unique_item_id=unique_item_id,
                                    item_name=item.get("name"),
                                    acquired_by=character_id,
                                    hex_id=hex_id,
                                    poi_name=self._current_poi,
                                )

                        # Create Item object for character inventory
                        # Normalize field variations from hex JSON data
                        from src.data_models import Item

                        # Normalize value (value_gp, value, cost, cost_sp -> value_gp)
                        value_gp = item.get("value_gp") or item.get("value")
                        if value_gp is None and item.get("cost_sp"):
                            # Convert silver pieces to gold pieces (10 sp = 1 gp)
                            value_gp = item.get("cost_sp") / 10.0
                        elif value_gp is None and item.get("cost"):
                            value_gp = item.get("cost")

                        # Normalize weight (weight, weight_coins)
                        weight = item.get("weight") or item.get("weight_coins", 0)

                        new_item = Item(
                            item_id=item.get(
                                "item_id", item.get("name", "").lower().replace(" ", "_")
                            ),
                            name=item.get("name"),
                            weight=weight,
                            quantity=item.get("quantity", 1),
                            is_unique=is_unique,
                            unique_item_id=unique_item_id,
                            source_hex=hex_id,
                            source_poi=self._current_poi,
                            description=item.get("description"),
                            value_gp=value_gp,
                            magical=item.get("magical", False),
                            cursed=item.get("cursed", False),
                            # Magic item properties (if present in hex data)
                            enchantment_type=item.get("enchantment_type"),
                            special_powers=item.get("special_powers", []),
                            oddities=item.get("oddities", []),
                            appearance=item.get("appearance"),
                            magic_item_category=item.get("magic_item_category"),
                            # Materialization (for template items)
                            is_materialized=item.get("is_materialized", True),
                            materialization_template=item.get("materialization_template"),
                        )

                        # Add to character inventory
                        character = self.controller.get_character(character_id)
                        if character:
                            character.inventory.append(new_item)

                        return {
                            "success": True,
                            "item_name": item.get("name"),
                            "description": item.get("description", ""),
                            "value": item.get("value"),
                            "is_unique": is_unique,
                            "unique_item_id": unique_item_id,
                            "added_to_inventory": character is not None,
                            "message": f"You take the {item.get('name')}.",
                        }

                return {"success": False, "error": f"Item '{item_name}' not found here"}

        return {"success": False, "error": "Current location not found"}

    def get_poi_visit_summary(self, hex_id: str) -> dict[str, Any]:
        """
        Get a summary of the current POI visit.

        Args:
            hex_id: Current hex

        Returns:
            Dictionary with visit summary
        """
        if not self._current_poi:
            return {"at_poi": False}

        visit_key = f"{hex_id}:{self._current_poi}"
        visit = self._poi_visits.get(visit_key)

        if not visit:
            return {
                "at_poi": True,
                "poi_name": self._current_poi,
                "first_visit": True,
            }

        return {
            "at_poi": True,
            "poi_name": self._current_poi,
            "state": visit.state.value,
            "entered": visit.entered,
            "features_explored": visit.rooms_explored,
            "npcs_met": visit.npcs_encountered,
            "items_found": visit.items_found,
            "items_taken": visit.items_taken,
            "secrets_found": visit.secrets_discovered,
            "time_spent_turns": visit.time_spent_turns,
        }

    # =========================================================================
    # AUTOMATIC HAZARD TRIGGERS
    # =========================================================================

    def trigger_poi_hazards(
        self,
        hex_id: str,
        trigger: str,
        character_id: str,
    ) -> list[HazardResult]:
        """
        Trigger automatic hazards at a POI.

        Called when approaching, entering, or exiting a POI to check
        for hazards that trigger automatically (e.g., turbulent waters,
        collapsing floors, magical wards).

        Args:
            hex_id: Current hex
            trigger: "on_approach", "on_enter", "on_exit"
            character_id: Character facing the hazard

        Returns:
            List of HazardResults for each triggered hazard
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        character = self.controller.get_character(character_id)
        if not character:
            return []

        results = []

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                hazards = poi.get_hazards_for_trigger(trigger)

                for hazard in hazards:
                    result = self._resolve_hazard(hazard, character)
                    results.append(result)

                    # Apply damage if any
                    if result.damage_dealt > 0:
                        self.controller.apply_damage(
                            character_id,
                            result.damage_dealt,
                            hazard.get("hazard_type", "environmental"),
                        )

                break

        return results

    def _resolve_hazard(
        self,
        hazard: dict[str, Any],
        character: CharacterState,
    ) -> HazardResult:
        """
        Resolve a single hazard check.

        Args:
            hazard: Hazard definition dict
            character: Character facing the hazard

        Returns:
            HazardResult with outcomes
        """
        hazard_type_str = hazard.get("hazard_type", "environmental")
        difficulty = hazard.get("difficulty", 10)
        description = hazard.get("description", "You encounter a hazard.")
        save_type = hazard.get("save_type", "DEX")
        damage = hazard.get("damage", "1d6")

        # Map string to HazardType enum
        hazard_type_map = {
            "swimming": HazardType.SWIMMING,
            "climbing": HazardType.CLIMBING,
            "jumping": HazardType.JUMPING,
            "trap": HazardType.TRAP,
            "falling": HazardType.FALLING,
            "environmental": HazardType.ENVIRONMENTAL,
        }
        hazard_type = hazard_type_map.get(hazard_type_str, HazardType.ENVIRONMENTAL)

        # Use the narrative resolver's hazard resolver
        if hazard_type == HazardType.SWIMMING:
            armor_weight = (
                character.armor_weight.value if hasattr(character, "armor_weight") else "unarmoured"
            )
            return self.narrative_resolver.hazard_resolver.resolve_hazard(
                hazard_type=HazardType.SWIMMING,
                character=character,
                armor_weight=armor_weight,
                rough_waters=True,
                difficulty=difficulty,
            )
        elif hazard_type == HazardType.CLIMBING:
            return self.narrative_resolver.hazard_resolver.resolve_hazard(
                hazard_type=HazardType.CLIMBING,
                character=character,
                height_feet=hazard.get("height", 20),
                is_trivial=False,
                difficulty=difficulty,
            )
        elif hazard_type == HazardType.TRAP:
            return self.narrative_resolver.hazard_resolver.resolve_hazard(
                hazard_type=HazardType.TRAP,
                character=character,
                difficulty=difficulty,
                damage_dice=damage,
                save_type=save_type,
            )
        else:
            # Generic environmental hazard - saving throw
            ability_mod = character.get_ability_modifier(save_type)
            roll = self.dice.roll_d20(f"hazard save ({save_type})")
            total = roll.total + ability_mod
            success = total >= difficulty

            damage_dealt = 0
            if not success and damage:
                damage_roll = self.dice.roll(damage, "hazard damage")
                damage_dealt = damage_roll.total

            from src.narrative.intent_parser import ActionType

            return HazardResult(
                success=success,
                hazard_type=hazard_type,
                action_type=ActionType.UNKNOWN,
                description=description,
                damage_dealt=damage_dealt,
                save_made=success,
                roll_total=total,
            )

    def get_poi_hazards(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get all hazards at the current POI.

        Args:
            hex_id: Current hex

        Returns:
            List of hazard definitions
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                return [
                    {
                        "trigger": h.get("trigger", "always"),
                        "type": h.get("hazard_type", "environmental"),
                        "difficulty": h.get("difficulty", 10),
                        "description": h.get("description", ""),
                    }
                    for h in poi.hazards
                ]

        return []

    # =========================================================================
    # LOCK AND BARRIER SYSTEM
    # =========================================================================

    def get_poi_locks(self, hex_id: str, poi_name: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Get active locks at a POI.

        Args:
            hex_id: Current hex
            poi_name: Specific POI to check (or current POI if None)

        Returns:
            List of active lock definitions
        """
        target_poi = poi_name or self._current_poi
        if not target_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        for poi in hex_data.points_of_interest:
            if poi.name == target_poi:
                return [
                    {
                        "index": i,
                        "type": lock.get("type", "physical"),
                        "requirement": lock.get("requirement", ""),
                        "description": lock.get("description", "A locked barrier"),
                        "bypassed": lock.get("bypassed", False),
                    }
                    for i, lock in enumerate(poi.locks)
                    if not lock.get("bypassed", False)
                ]

        return []

    def check_poi_access(
        self,
        hex_id: str,
        poi_name: str,
        available_spells: Optional[list[str]] = None,
        available_items: Optional[list[str]] = None,
        available_keys: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Check if party can access a POI (checking locks).

        Args:
            hex_id: Current hex
            poi_name: Name of POI to check
            available_spells: Spells the party can cast
            available_items: Magic items the party has
            available_keys: Keys the party possesses

        Returns:
            Dictionary with access status and blocking locks
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"can_access": False, "error": "Hex data not found"}

        spells = available_spells or []
        items = available_items or []
        keys = available_keys or []

        for poi in hex_data.points_of_interest:
            if poi.name == poi_name:
                active_locks = poi.get_active_locks()

                if not active_locks:
                    return {"can_access": True, "locks": []}

                blocking_locks = []
                for i, lock in enumerate(active_locks):
                    can_bypass = poi.check_lock_requirement(lock, spells, items, keys)
                    if not can_bypass:
                        blocking_locks.append(
                            {
                                "index": i,
                                "type": lock.get("type"),
                                "description": lock.get("description", "A barrier blocks your way"),
                                "requirement_hint": self._get_lock_hint(lock),
                            }
                        )

                return {
                    "can_access": len(blocking_locks) == 0,
                    "locks": blocking_locks,
                }

        return {"can_access": False, "error": "POI not found"}

    def _get_lock_hint(self, lock: dict[str, Any]) -> str:
        """Generate a hint about how to bypass a lock."""
        lock_type = lock.get("type", "physical")

        if lock_type == "magical":
            return "This barrier seems to respond to magical power."
        elif lock_type == "key":
            return "A keyhole suggests the need for a specific key."
        elif lock_type == "physical":
            return "A sturdy lock that might be picked or forced."
        elif lock_type == "puzzle":
            return "Some kind of mechanism or puzzle controls this barrier."
        return "Something blocks the way forward."

    def attempt_bypass_lock(
        self,
        hex_id: str,
        poi_name: str,
        lock_index: int,
        method: str,
        character_id: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Attempt to bypass a lock using a specific method.

        Args:
            hex_id: Current hex
            poi_name: POI with the lock
            lock_index: Index of the lock to bypass
            method: "spell", "item", "key", "pick", "force", "puzzle"
            character_id: Character making the attempt
            **kwargs: Additional parameters (spell_name, item_name, etc.)

        Returns:
            Dictionary with bypass attempt result
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        character = self.controller.get_character(character_id)
        if not character:
            return {"success": False, "error": "Character not found"}

        for poi in hex_data.points_of_interest:
            if poi.name == poi_name:
                if lock_index >= len(poi.locks):
                    return {"success": False, "error": "Invalid lock index"}

                lock = poi.locks[lock_index]
                if lock.get("bypassed", False):
                    return {"success": True, "message": "Already bypassed"}

                lock_type = lock.get("type", "physical")

                # Handle different bypass methods
                if method == "spell":
                    spell_name = kwargs.get("spell_name", "")
                    if lock_type == "magical" and spell_name:
                        requirement = lock.get("requirement", "").lower()
                        if requirement in spell_name.lower() or spell_name.lower() in requirement:
                            poi.bypass_lock(lock_index)
                            return {
                                "success": True,
                                "message": f"The {spell_name} spell causes the barrier to dissipate.",
                            }
                        return {
                            "success": False,
                            "message": "The spell has no effect on this barrier.",
                        }

                elif method == "item":
                    item_name = kwargs.get("item_name", "")
                    if lock_type == "magical" and item_name:
                        requirement = lock.get("requirement", "").lower()
                        if requirement in item_name.lower() or item_name.lower() in requirement:
                            poi.bypass_lock(lock_index)
                            return {
                                "success": True,
                                "message": f"The {item_name} reacts with the barrier, opening the way.",
                            }
                        return {
                            "success": False,
                            "message": "The item has no effect on this barrier.",
                        }

                elif method == "key":
                    key_id = kwargs.get("key_id", "")
                    if lock_type == "key":
                        if key_id == lock.get("requirement"):
                            poi.bypass_lock(lock_index)
                            return {
                                "success": True,
                                "message": "The key turns smoothly and the lock opens.",
                            }
                        return {
                            "success": False,
                            "message": "This key doesn't fit the lock.",
                        }

                elif method == "pick":
                    if lock_type == "physical":
                        # Lockpicking check using DEX
                        difficulty = lock.get("difficulty", 15)
                        dex_mod = character.get_ability_modifier("DEX")
                        roll = self.dice.roll_d20("lockpicking")
                        total = roll.total + dex_mod

                        if total >= difficulty:
                            poi.bypass_lock(lock_index)
                            return {
                                "success": True,
                                "roll": total,
                                "message": "You successfully pick the lock.",
                            }
                        return {
                            "success": False,
                            "roll": total,
                            "message": "You fail to pick the lock.",
                        }

                elif method == "force":
                    if lock_type == "physical":
                        # Force check using STR
                        difficulty = lock.get("difficulty", 18)
                        str_mod = character.get_ability_modifier("STR")
                        roll = self.dice.roll_d20("forcing lock")
                        total = roll.total + str_mod

                        if total >= difficulty:
                            poi.bypass_lock(lock_index)
                            return {
                                "success": True,
                                "roll": total,
                                "message": "You force the barrier open with a mighty effort.",
                            }
                        return {
                            "success": False,
                            "roll": total,
                            "message": "The barrier holds firm against your efforts.",
                        }

                return {
                    "success": False,
                    "error": f"Cannot bypass a {lock_type} lock using {method}",
                }

        return {"success": False, "error": "POI not found"}

    # =========================================================================
    # DUNGEON ACCESS THROUGH POI
    # =========================================================================

    def enter_dungeon_from_poi(
        self,
        hex_id: str,
        poi_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Transition from a POI to dungeon exploration.

        Called when entering a POI that leads to a dungeon, triggering
        a state transition to DUNGEON_EXPLORATION.

        Args:
            hex_id: Current hex
            poi_name: POI leading to dungeon (or current POI if None)

        Returns:
            Dictionary with transition details
        """
        target_poi = poi_name or self._current_poi
        if not target_poi:
            return {"success": False, "error": "Not at any POI"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        for poi in hex_data.points_of_interest:
            if poi.name == target_poi:
                if not poi.leads_to_dungeon():
                    return {
                        "success": False,
                        "error": "This location does not lead to a dungeon",
                    }

                # Check for locks first
                if poi.has_active_locks():
                    locks = poi.get_active_locks()
                    return {
                        "success": False,
                        "blocked": True,
                        "locks": [
                            {
                                "type": lock.get("type"),
                                "description": lock.get("description"),
                            }
                            for lock in locks
                        ],
                        "message": "The way is blocked.",
                    }

                # Trigger entry hazards
                # (Would trigger hazard resolution here in practice)

                dungeon_id = poi.dungeon_id or poi.name
                entrance_room = poi.dungeon_entrance_room or "entrance"

                # Transition to dungeon state
                self.controller.transition(
                    "enter_dungeon",
                    context={
                        "from_hex": hex_id,
                        "from_poi": target_poi,
                        "dungeon_id": dungeon_id,
                        "entrance_room": entrance_room,
                    },
                )

                return {
                    "success": True,
                    "dungeon_id": dungeon_id,
                    "entrance_room": entrance_room,
                    "message": f"You enter the depths of {target_poi}...",
                    "state_changed": True,
                }

        return {"success": False, "error": "POI not found"}

    def get_dungeon_access_info(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get information about dungeon access points in the current hex.

        Args:
            hex_id: Current hex

        Returns:
            List of POIs that lead to dungeons with access info
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        dungeon_pois = []
        for poi in hex_data.points_of_interest:
            if poi.leads_to_dungeon() and poi.is_visible(self._discovered_secrets):
                poi_info = {
                    "poi_name": poi.name,
                    "dungeon_id": poi.dungeon_id or poi.name,
                    "entrance_room": poi.dungeon_entrance_room,
                    "is_accessible": poi.is_accessible_from(self._current_poi),
                    "has_locks": poi.has_active_locks(),
                    "has_hazards": len(poi.hazards) > 0,
                }

                if poi.has_active_locks():
                    poi_info["locks"] = [lock.get("type") for lock in poi.get_active_locks()]

                if poi.hazards:
                    poi_info["hazards"] = [h.get("hazard_type") for h in poi.hazards]

                dungeon_pois.append(poi_info)

        return dungeon_pois

    # =========================================================================
    # WORLD-STATE CHANGE TRACKING
    # =========================================================================

    def record_state_change(
        self,
        hex_id: str,
        change_type: str,
        trigger_action: str,
        trigger_details: Optional[dict[str, Any]] = None,
        poi_name: Optional[str] = None,
        before_state: Optional[dict[str, Any]] = None,
        after_state: Optional[dict[str, Any]] = None,
        narrative_description: str = "",
        reversible: bool = False,
        reverse_condition: Optional[str] = None,
    ) -> HexStateChange:
        """
        Record a permanent world-state change caused by player action.

        Examples:
        - Removing a cursed item lifts a curse
        - Killing an NPC removes them from the location
        - Solving a puzzle grants permanent access

        Args:
            hex_id: Hex where the change occurred
            change_type: Type of change (e.g., "curse_lifted", "npc_removed")
            trigger_action: What triggered the change (e.g., "item_removed", "npc_killed")
            trigger_details: Details about the trigger (e.g., {"item": "Hand of St Howarth"})
            poi_name: Specific POI affected (if applicable)
            before_state: State before the change
            after_state: State after the change
            narrative_description: Player-facing description of what happened
            reversible: Whether the change can be undone
            reverse_condition: How to reverse the change

        Returns:
            The recorded HexStateChange
        """
        change = HexStateChange(
            hex_id=hex_id,
            poi_name=poi_name,
            trigger_action=trigger_action,
            trigger_details=trigger_details or {},
            change_type=change_type,
            before_state=before_state or {},
            after_state=after_state or {},
            narrative_description=narrative_description,
            occurred_at=(
                self.controller.world_state.current_date if self.controller.world_state else None
            ),
            reversible=reversible,
            reverse_condition=reverse_condition,
        )

        self._world_state_changes.add_change(change)
        logger.info(f"Recorded world-state change: {change_type} at {hex_id}/{poi_name or 'hex'}")

        return change

    def get_hex_state_changes(self, hex_id: str) -> list[HexStateChange]:
        """Get all state changes that have occurred in a hex."""
        return self._world_state_changes.get_changes_for_hex(hex_id)

    def get_poi_state_changes(self, hex_id: str, poi_name: str) -> list[HexStateChange]:
        """Get all state changes at a specific POI."""
        return self._world_state_changes.get_changes_for_poi(hex_id, poi_name)

    def is_curse_active(
        self,
        hex_id: str,
        curse_name: str,
        poi_name: Optional[str] = None,
    ) -> bool:
        """
        Check if a curse is still active in a location.

        Args:
            hex_id: Hex to check
            curse_name: Name of the curse (e.g., "blood_curse")
            poi_name: Specific POI if applicable

        Returns:
            True if curse is still active (no "curse_lifted" change recorded)
        """
        return self._world_state_changes.is_condition_active(hex_id, curse_name, poi_name)

    def lift_curse(
        self,
        hex_id: str,
        curse_name: str,
        trigger_action: str,
        trigger_details: Optional[dict[str, Any]] = None,
        poi_name: Optional[str] = None,
        narrative_description: str = "",
    ) -> HexStateChange:
        """
        Record that a curse has been lifted.

        Args:
            hex_id: Hex where the curse was
            curse_name: Name of the curse
            trigger_action: What lifted the curse
            trigger_details: Details about what triggered the lifting
            poi_name: POI if specific to a location
            narrative_description: Description of what happened

        Returns:
            The recorded state change
        """
        return self.record_state_change(
            hex_id=hex_id,
            change_type=f"{curse_name}_lifted",
            trigger_action=trigger_action,
            trigger_details=trigger_details,
            poi_name=poi_name,
            before_state={"curse_active": True, "curse_name": curse_name},
            after_state={"curse_active": False, "curse_name": curse_name},
            narrative_description=narrative_description
            or f"The {curse_name.replace('_', ' ')} has been lifted.",
            reversible=False,
        )

    def get_current_state_value(
        self,
        hex_id: str,
        state_key: str,
        poi_name: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Get the current value of a state key after all changes.

        Args:
            hex_id: Hex to check
            state_key: Key to look up
            poi_name: POI if specific

        Returns:
            Current value or None if not changed
        """
        return self._world_state_changes.get_current_state(hex_id, state_key, poi_name)

    # =========================================================================
    # SCHEDULED EVENTS AND INVITATIONS
    # =========================================================================

    def issue_invitation(
        self,
        hex_id: str,
        poi_name: str,
        character_ids: list[str],
        title: str,
        player_message: str,
        effect_type: str,
        effect_details: dict[str, Any],
        trigger_condition: str = "return",
        expiry_days: Optional[int] = None,
    ) -> ScheduledEvent:
        """
        Issue an invitation for characters to return to a location for a reward.

        Used when POIs offer delayed benefits (e.g., healing, blessings,
        magical item grants) to worthy visitors.

        Args:
            hex_id: Source hex
            poi_name: Source POI
            character_ids: Characters who receive the invitation
            title: Event title (e.g., "The Grove's Blessing")
            player_message: Message told to players (e.g., "Return when in need")
            effect_type: Type of effect (healing, spell_grant, item_grant)
            effect_details: Effect parameters
            trigger_condition: When effect triggers (default: "return")
            expiry_days: Days until invitation expires (None = never)

        Returns:
            The created ScheduledEvent
        """
        current_date = self._get_current_date()
        return self._event_scheduler.create_invitation(
            source_hex=hex_id,
            source_poi=poi_name,
            character_ids=character_ids,
            title=title,
            player_message=player_message,
            effect_type=effect_type,
            effect_details=effect_details,
            current_date=current_date,
            trigger_condition=trigger_condition,
            expiry_days=expiry_days,
        )

    def check_scheduled_events(
        self,
        hex_id: Optional[str] = None,
        poi_name: Optional[str] = None,
        conditions_met: Optional[dict[str, bool]] = None,
    ) -> list[dict[str, Any]]:
        """
        Check for and trigger any scheduled events that should fire.

        Called when entering a hex, approaching a POI, or on date changes.

        Args:
            hex_id: Current hex (if any)
            poi_name: Current POI (if any)
            conditions_met: Dict of event_id -> bool for narrative conditions

        Returns:
            List of triggered event effects
        """
        current_date = self._get_current_date()
        return self._event_scheduler.check_triggers(
            current_date=current_date,
            current_hex=hex_id,
            current_poi=poi_name,
            conditions_met=conditions_met,
        )

    def get_pending_invitations(
        self,
        character_id: Optional[str] = None,
    ) -> list[ScheduledEvent]:
        """
        Get pending invitations.

        Args:
            character_id: If provided, filter to this character only

        Returns:
            List of pending invitation events
        """
        current_date = self._get_current_date()

        if character_id:
            return self._event_scheduler.get_active_events_for_character(character_id, current_date)
        else:
            return self._event_scheduler.get_pending_invitations(current_date)

    def get_invitations_at_location(
        self,
        hex_id: str,
        poi_name: Optional[str] = None,
    ) -> list[ScheduledEvent]:
        """
        Get invitations tied to a specific location.

        Args:
            hex_id: Hex to check
            poi_name: POI to check

        Returns:
            List of events at this location
        """
        return self._event_scheduler.get_events_at_location(hex_id, poi_name)

    def _get_current_date(self) -> GameDate:
        """Get the current game date from the controller."""
        world_state = self.controller.get_world_state()
        if world_state and world_state.date:
            return world_state.date
        # Default date if not set
        return GameDate(year=1, month=1, day=1)

    # =========================================================================
    # ABILITY GRANTING FROM POI FEATURES
    # =========================================================================

    def get_available_ability_grants(
        self,
        hex_id: str,
        poi_name: str,
        character_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get abilities that can be granted to a character at this POI.

        Returns only abilities the character hasn't already received
        and that meet any requirements.

        Args:
            hex_id: Current hex
            poi_name: POI name
            character_id: Character to check eligibility for

        Returns:
            List of grantable ability definitions
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        poi = None
        for p in hex_data.points_of_interest:
            if p.name.lower() == poi_name.lower():
                poi = p
                break

        if not poi or not poi.ability_grants:
            return []

        available = []
        current_date = self._get_current_date()

        for grant in poi.ability_grants:
            ability_name = grant.get("name", "")
            once_per = grant.get("once_per_character", True)

            # Check if already granted
            if once_per and self._ability_tracker.was_ability_granted(
                character_id, hex_id, poi_name, ability_name
            ):
                continue

            # Check requirements (if any)
            requirements = grant.get("requirements", {})
            if requirements:
                # Get character data
                character = self._get_character(character_id)
                if character:
                    # Check alignment requirement
                    if "alignment" in requirements:
                        # Would need alignment from character - skip for now
                        pass
                    # Check class requirement
                    if "class" in requirements:
                        if character.character_class.lower() != requirements["class"].lower():
                            continue

            available.append(grant)

        return available

    def grant_ability_to_character(
        self,
        hex_id: str,
        poi_name: str,
        character_id: str,
        ability_name: str,
    ) -> dict[str, Any]:
        """
        Grant a specific ability from a POI to a character.

        Args:
            hex_id: Current hex
            poi_name: POI name
            character_id: Character receiving the ability
            ability_name: Name of the ability to grant

        Returns:
            Dict with success status and details
        """
        # Find the POI and ability
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex not found"}

        poi = None
        for p in hex_data.points_of_interest:
            if p.name.lower() == poi_name.lower():
                poi = p
                break

        if not poi:
            return {"success": False, "error": "POI not found"}

        grant_def = None
        for g in poi.ability_grants:
            if g.get("name", "").lower() == ability_name.lower():
                grant_def = g
                break

        if not grant_def:
            return {"success": False, "error": "Ability not found at this POI"}

        # Check if already granted
        once_per = grant_def.get("once_per_character", True)
        if once_per and self._ability_tracker.was_ability_granted(
            character_id, hex_id, poi_name, ability_name
        ):
            return {"success": False, "error": "Ability already granted to this character"}

        # Grant the ability
        current_date = self._get_current_date()
        ability_type_str = grant_def.get("ability_type", "spell")
        try:
            ability_type = AbilityType(ability_type_str)
        except ValueError:
            ability_type = AbilityType.SPECIAL

        granted = self._ability_tracker.grant_ability(
            character_id=character_id,
            ability_name=ability_name,
            ability_type=ability_type,
            source_hex_id=hex_id,
            source_poi_name=poi_name,
            description=grant_def.get("description", ""),
            current_date=current_date,
            duration=grant_def.get("duration", "permanent"),
            spell_level=grant_def.get("spell_level"),
            spell_school=grant_def.get("spell_school"),
            spell_data=grant_def.get("spell_data"),
            uses=grant_def.get("uses"),
            once_per_character=once_per,
        )

        if granted:
            return {
                "success": True,
                "ability": ability_name,
                "ability_type": ability_type.value,
                "description": granted.description,
                "duration": granted.duration,
                "message": f"Granted {ability_name} to character",
            }
        else:
            return {"success": False, "error": "Failed to grant ability"}

    def get_character_granted_abilities(
        self,
        character_id: str,
        ability_type: Optional[str] = None,
    ) -> list[GrantedAbility]:
        """
        Get all granted abilities for a character.

        Args:
            character_id: Character to check
            ability_type: Filter to specific type (spell, blessing, etc.)

        Returns:
            List of GrantedAbility objects
        """
        current_date = self._get_current_date()
        abilities = self._ability_tracker.get_character_abilities(character_id, current_date)

        if ability_type:
            try:
                filter_type = AbilityType(ability_type)
                abilities = [a for a in abilities if a.ability_type == filter_type]
            except ValueError:
                pass

        return abilities

    def use_granted_ability(
        self,
        character_id: str,
        ability_name: str,
    ) -> dict[str, Any]:
        """
        Use a granted ability (for limited-use abilities).

        Args:
            character_id: Character using the ability
            ability_name: Name of the ability to use

        Returns:
            Dict with success status and remaining uses
        """
        current_date = self._get_current_date()
        abilities = self._ability_tracker.get_character_abilities(character_id, current_date)

        for ability in abilities:
            if ability.ability_name.lower() == ability_name.lower():
                if ability.use():
                    return {
                        "success": True,
                        "ability": ability_name,
                        "uses_remaining": ability.uses_remaining,
                        "still_active": ability.is_active,
                    }
                else:
                    return {
                        "success": False,
                        "error": "Ability already exhausted",
                    }

        return {"success": False, "error": "Ability not found"}

    def _get_character(self, character_id: str) -> Optional[CharacterState]:
        """Get a character from the controller."""
        party_state = self.controller.get_party_state()
        if party_state:
            for char in party_state.characters:
                if char.character_id == character_id:
                    return char
        return None

    # =========================================================================
    # SUB-LOCATION EXPLORATION
    # =========================================================================

    def get_exploration_context(self) -> str:
        """Get the current exploration context (surface, diving, inside, etc.)."""
        return self._exploration_context

    def set_exploration_context(self, context: str) -> None:
        """
        Set the current exploration context.

        Args:
            context: New context (surface, diving, underwater, inside, climbing)
        """
        self._exploration_context = context

    def get_visible_sub_locations(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get sub-locations visible from the current context.

        Args:
            hex_id: Current hex

        Returns:
            List of visible sub-location info
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                return poi.get_sub_locations(self._exploration_context)

        return []

    def explore_sub_location(
        self,
        hex_id: str,
        sub_location_name: str,
        character_id: str,
    ) -> dict[str, Any]:
        """
        Explore a sub-location within the current POI.

        Args:
            hex_id: Current hex
            sub_location_name: Name of sub-location to explore
            character_id: Character doing the exploration

        Returns:
            Dict with exploration results
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        character = self.controller.get_character(character_id)
        if not character:
            return {"success": False, "error": "Character not found"}

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                # Check if sub-location exists
                sub_loc = poi.get_sub_location_by_name(sub_location_name)
                if not sub_loc:
                    return {
                        "success": False,
                        "error": f"'{sub_location_name}' not found at this location",
                    }

                # Check access
                can_access, required = poi.can_access_sub_location(
                    sub_location_name,
                    self._exploration_context,
                )

                if not can_access:
                    return {
                        "success": False,
                        "error": f"Cannot access this area from {self._exploration_context}",
                        "requires": required,
                    }

                # Successfully exploring sub-location
                result = {
                    "success": True,
                    "sub_location_name": sub_loc.get("name"),
                    "description": sub_loc.get("description", ""),
                    "features": sub_loc.get("features", []),
                    "items": [],
                }

                # Get items at this sub-location
                for item in sub_loc.get("items", []):
                    if not item.get("taken", False):
                        result["items"].append(
                            {
                                "name": item.get("name"),
                                "description": item.get("description", ""),
                            }
                        )

                # Track visit
                visit_key = f"{hex_id}:{self._current_poi}"
                if visit_key in self._poi_visits:
                    self._poi_visits[visit_key].rooms_explored.append(sub_location_name)

                return result

        return {"success": False, "error": "Current location not found"}

    def take_sub_location_item(
        self,
        hex_id: str,
        sub_location_name: str,
        item_name: str,
        character_id: str,
    ) -> dict[str, Any]:
        """
        Take an item from a sub-location.

        Args:
            hex_id: Current hex
            sub_location_name: Sub-location containing the item
            item_name: Name of item to take
            character_id: Character taking the item

        Returns:
            Dict with result
        """
        if not self._current_poi:
            return {"success": False, "error": "Not at any location"}

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                sub_loc = poi.get_sub_location_by_name(sub_location_name)
                if not sub_loc:
                    return {"success": False, "error": "Sub-location not found"}

                # Check access
                can_access, _ = poi.can_access_sub_location(
                    sub_location_name,
                    self._exploration_context,
                )
                if not can_access:
                    return {"success": False, "error": "Cannot access this area"}

                # Find and take the item
                for item in sub_loc.get("items", []):
                    if item.get("name", "").lower() == item_name.lower():
                        if item.get("taken", False):
                            return {"success": False, "error": "Item already taken"}

                        # Check acquisition condition if present
                        acquisition_condition = item.get("acquisition_condition")
                        if acquisition_condition:
                            session_mgr = None
                            if (
                                hasattr(self.controller, "session_manager")
                                and self.controller.session_manager
                            ):
                                session_mgr = self.controller.session_manager

                            if session_mgr:
                                is_satisfied, reason = check_acquisition_condition(
                                    condition_text=acquisition_condition,
                                    hex_id=hex_id,
                                    session_manager=session_mgr,
                                    controller=self.controller,
                                )
                                if not is_satisfied:
                                    return {
                                        "success": False,
                                        "error": reason,
                                        "condition_blocked": True,
                                        "acquisition_condition": acquisition_condition,
                                    }

                        # Mark as taken
                        item["taken"] = True

                        # Track in visit
                        visit_key = f"{hex_id}:{self._current_poi}"
                        if visit_key in self._poi_visits:
                            self._poi_visits[visit_key].items_taken.append(item.get("name"))

                        result = {
                            "success": True,
                            "item_name": item.get("name"),
                            "description": item.get("description", ""),
                        }

                        # Check for special consequences
                        if item.get("on_take"):
                            result["special_effect"] = item.get("on_take")

                        return result

                return {"success": False, "error": f"Item '{item_name}' not found"}

        return {"success": False, "error": "Current location not found"}

    def get_context_features(self, hex_id: str) -> list[str]:
        """
        Get features visible from the current exploration context.

        Args:
            hex_id: Current hex

        Returns:
            List of visible feature descriptions
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        for poi in hex_data.points_of_interest:
            if poi.name == self._current_poi:
                return poi.get_visible_features_from_context(self._exploration_context)

        return []

    # =========================================================================
    # DIVING/UNDERWATER EXPLORATION
    # =========================================================================

    def start_dive(
        self,
        character_id: str,
        depth_feet: int = 0,
    ) -> HazardResult:
        """
        Start diving underwater.

        Per Dolmenwood rules (p154):
        - A character can survive for 1 Round (10 seconds) per CON point
        - Swimming is at half speed
        - Armor imposes penalties on swimming checks

        Args:
            character_id: Character starting to dive
            depth_feet: Initial depth in feet

        Returns:
            HazardResult with diving initiation details
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.DIVING,
                action_type=ActionType.SWIM,
                description="Character not found",
            )

        # Create diving state for this character
        diving_state = self.narrative_resolver.hazard_resolver.create_diving_state(character)
        diving_state.start_dive(character.ability_scores.get("CON", 10))
        diving_state.depth_feet = depth_feet
        self._diving_states[character_id] = diving_state

        # Update exploration context
        self._exploration_context = "diving"

        # Resolve the initial dive
        armor_weight = (
            character.armor_weight.value if hasattr(character, "armor_weight") else "unarmoured"
        )
        result = self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.DIVING,
            character=character,
            diving_state=diving_state,
            rounds_to_spend=1,
            armor_weight=armor_weight,
            action="dive",
        )

        return result

    def continue_diving(
        self,
        character_id: str,
        rounds: int = 1,
        action: str = "swim",
    ) -> HazardResult:
        """
        Continue underwater exploration, spending rounds of breath.

        Args:
            character_id: Character continuing dive
            rounds: Number of rounds this action takes
            action: "swim" for movement, "action" for exploring/grabbing items

        Returns:
            HazardResult with breath status
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.DIVING,
                action_type=ActionType.SWIM,
                description="Character not found",
            )

        diving_state = self._diving_states.get(character_id)
        if not diving_state or not diving_state.is_diving:
            return HazardResult(
                success=False,
                hazard_type=HazardType.DIVING,
                action_type=ActionType.SWIM,
                description="Character is not diving",
            )

        armor_weight = (
            character.armor_weight.value if hasattr(character, "armor_weight") else "unarmoured"
        )
        result = self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.DIVING,
            character=character,
            diving_state=diving_state,
            rounds_to_spend=rounds,
            armor_weight=armor_weight,
            action=action,
        )

        # If character drowned, remove from diving states
        if "dead" in result.conditions_applied:
            self._exploration_context = "surface"
            del self._diving_states[character_id]

        return result

    def surface_from_dive(self, character_id: str) -> HazardResult:
        """
        Surface from underwater and catch breath.

        Args:
            character_id: Character surfacing

        Returns:
            HazardResult confirming surfacing
        """
        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.DIVING,
                action_type=ActionType.SWIM,
                description="Character not found",
            )

        diving_state = self._diving_states.get(character_id)
        if not diving_state:
            return HazardResult(
                success=True,
                hazard_type=HazardType.DIVING,
                action_type=ActionType.SWIM,
                description="Already on surface",
            )

        result = self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.DIVING,
            character=character,
            diving_state=diving_state,
            action="surface",
        )

        # Update state
        diving_state.surface()
        self._exploration_context = "surface"

        return result

    def get_diving_status(self, character_id: str) -> dict[str, Any]:
        """
        Get current diving status for a character.

        Args:
            character_id: Character to check

        Returns:
            Dict with diving status information
        """
        diving_state = self._diving_states.get(character_id)
        if not diving_state or not diving_state.is_diving:
            return {
                "is_diving": False,
                "rounds_remaining": None,
                "warning_level": None,
            }

        return {
            "is_diving": True,
            "rounds_underwater": diving_state.rounds_underwater,
            "rounds_remaining": diving_state.get_rounds_remaining(),
            "max_rounds": diving_state.max_rounds,
            "warning_level": diving_state.get_warning_level(),
            "depth_feet": diving_state.depth_feet,
        }

    def get_all_diving_characters(self) -> list[str]:
        """Get IDs of all characters currently diving."""
        return [char_id for char_id, state in self._diving_states.items() if state.is_diving]

    # =========================================================================
    # HEX-LEVEL TO POI-LEVEL ITEM MIGRATION
    # =========================================================================

    def migrate_hex_item_to_poi(
        self,
        hex_id: str,
        item_name: str,
        poi_name: str,
        sub_location_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Migrate a hex-level item to a POI or sub-location.

        Used to move items from the hex's top-level items list to the
        appropriate POI/sub-location where they should be found through
        exploration.

        Args:
            hex_id: Hex containing the item
            item_name: Name of the item to migrate
            poi_name: Target POI name
            sub_location_name: Optional sub-location within the POI

        Returns:
            Dict with migration result
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        success = hex_data.migrate_item_to_poi(item_name, poi_name, sub_location_name)

        if success:
            location_desc = poi_name
            if sub_location_name:
                location_desc += f" / {sub_location_name}"
            return {
                "success": True,
                "item_name": item_name,
                "location": location_desc,
                "message": f"Migrated '{item_name}' to {location_desc}",
            }

        return {
            "success": False,
            "error": f"Could not migrate '{item_name}' - item or POI not found",
        }

    def get_hex_item_location(
        self,
        hex_id: str,
        item_name: str,
    ) -> Optional[dict[str, Any]]:
        """
        Get the POI/sub-location where a hex-level item is found.

        Args:
            hex_id: Hex to check
            item_name: Name of the item

        Returns:
            Dict with 'poi' and 'sub_location' keys, or None if not mapped
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return None

        return hex_data.get_item_location(item_name)

    def get_unmapped_hex_items(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get hex-level items that haven't been mapped to POI locations.

        Args:
            hex_id: Hex to check

        Returns:
            List of items without location mappings
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        return hex_data.get_unmapped_hex_items()

    def auto_migrate_hex_items(
        self,
        hex_id: str,
        item_mappings: dict[str, dict[str, Optional[str]]],
    ) -> dict[str, Any]:
        """
        Automatically migrate multiple hex-level items based on a mapping.

        Args:
            hex_id: Hex containing the items
            item_mappings: Dict mapping item names to their locations
                          Format: {"item_name": {"poi": "POI Name", "sub_location": "Sub-Location"}}

        Returns:
            Dict with migration results
        """
        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return {"success": False, "error": "Hex data not found"}

        results = {"migrated": [], "failed": []}

        for item_name, location in item_mappings.items():
            poi_name = location.get("poi")
            sub_location_name = location.get("sub_location")

            if not poi_name:
                results["failed"].append(
                    {
                        "item": item_name,
                        "error": "No POI specified",
                    }
                )
                continue

            success = hex_data.migrate_item_to_poi(item_name, poi_name, sub_location_name)

            if success:
                results["migrated"].append(
                    {
                        "item": item_name,
                        "poi": poi_name,
                        "sub_location": sub_location_name,
                    }
                )
            else:
                results["failed"].append(
                    {
                        "item": item_name,
                        "error": "Item or POI not found",
                    }
                )

        return {
            "success": len(results["failed"]) == 0,
            "migrated_count": len(results["migrated"]),
            "failed_count": len(results["failed"]),
            "details": results,
        }

    def get_items_at_current_location(self, hex_id: str) -> list[dict[str, Any]]:
        """
        Get items at the current exploration location.

        Returns items based on current POI and exploration context.
        If diving, only returns items at underwater sub-locations.

        Args:
            hex_id: Current hex

        Returns:
            List of accessible items
        """
        if not self._current_poi:
            return []

        hex_data = self._hex_data.get(hex_id)
        if not hex_data:
            return []

        # Get items from current POI
        poi_items = hex_data.get_items_at_poi(self._current_poi)

        # If in a specific exploration context, also check sub-locations
        if self._exploration_context in ("diving", "underwater"):
            for poi in hex_data.points_of_interest:
                if poi.name == self._current_poi:
                    # Get items from underwater sub-locations
                    for sub_loc in poi.get_sub_locations("underwater"):
                        sub_items = sub_loc.get("items", [])
                        for item in sub_items:
                            if item not in poi_items and not item.get("taken", False):
                                poi_items.append(item)
                    break

        # Filter out taken items
        return [item for item in poi_items if not item.get("taken", False)]
