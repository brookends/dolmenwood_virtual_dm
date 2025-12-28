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
)
from src.narrative.narrative_resolver import (
    NarrativeResolver,
    ResolutionResult,
    NarrationContext,
    DivingState,
)
from src.narrative.hazard_resolver import HazardResolver, HazardType, HazardResult
from src.narrative.intent_parser import ActionType


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


# Terrain definitions per Dolmenwood travel table
TERRAIN_DATA: dict[TerrainType, TerrainInfo] = {
    TerrainType.FARMLAND: TerrainInfo(
        TerrainType.FARMLAND, travel_point_cost=2, lost_chance=1, encounter_chance=1,
        mount_allowed=True, vehicle_allowed=True, description="Tilled fields and lanes"
    ),
    TerrainType.MEADOW if hasattr(TerrainType, "MEADOW") else TerrainType.FARMLAND: TerrainInfo(  # type: ignore[attr-defined]
        TerrainType.FARMLAND, travel_point_cost=2, lost_chance=1, encounter_chance=1,
        mount_allowed=True, vehicle_allowed=True, description="Open meadow or grassland"
    ),
    TerrainType.FOREST: TerrainInfo(
        TerrainType.FOREST, travel_point_cost=2, lost_chance=1, encounter_chance=1,
        mount_allowed=True, vehicle_allowed=True, description="Open forest"
    ),
    # Moderate Terrain (p157) - 3 TP, 2-in-6
    TerrainType.MOOR: TerrainInfo(
        TerrainType.MOOR, travel_point_cost=3, lost_chance=2, encounter_chance=2,
        mount_allowed=True, vehicle_allowed=False, description="Boggy or hilly forest/moor"
    ),
    TerrainType.HILLS: TerrainInfo(
        TerrainType.HILLS, travel_point_cost=3, lost_chance=2, encounter_chance=2,
        mount_allowed=True, vehicle_allowed=False, description="Hilly forest/terrain"
    ),
    TerrainType.DEEP_FOREST: TerrainInfo(
        TerrainType.DEEP_FOREST, travel_point_cost=4, lost_chance=3, encounter_chance=3,
        mount_allowed=False, vehicle_allowed=False, description="Tangled or thorny forest"
    ),
    TerrainType.SWAMP: TerrainInfo(
        TerrainType.SWAMP, travel_point_cost=4, lost_chance=3, encounter_chance=3,
        mount_allowed=False, vehicle_allowed=False, description="Wetland or bog"
    ),
    TerrainType.MOUNTAINS: TerrainInfo(
        TerrainType.MOUNTAINS, travel_point_cost=4, lost_chance=3, encounter_chance=3,
        mount_allowed=False, vehicle_allowed=False, description="Craggy forest or steep slopes"
    ),
    TerrainType.SETTLEMENT: TerrainInfo(
        TerrainType.SETTLEMENT, travel_point_cost=2, lost_chance=0, encounter_chance=0,
        mount_allowed=True, vehicle_allowed=True, description="Settled area"
    ),
    TerrainType.TRAIL: TerrainInfo(  # Treated as track context
        TerrainType.TRAIL, travel_point_cost=2, lost_chance=1, encounter_chance=1,
        mount_allowed=True, vehicle_allowed=True, description="Track"
    ),
    TerrainType.ROAD: TerrainInfo(
        TerrainType.ROAD, travel_point_cost=2, lost_chance=0, encounter_chance=0,
        mount_allowed=True, vehicle_allowed=True, description="Road"
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

        # Callbacks for external systems (like LLM description requests)
        self._description_callback: Optional[Callable] = None

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

    def get_terrain_for_hex(self, hex_id: str) -> TerrainType:
        """Get terrain type for a hex."""
        hex_data = self._hex_data.get(hex_id)
        if hex_data:
            return TerrainType(hex_data.terrain)
        return TerrainType.FOREST  # Default

    def get_terrain_info(self, terrain: TerrainType) -> TerrainInfo:
        """Get terrain information."""
        return TERRAIN_DATA.get(terrain, TERRAIN_DATA[TerrainType.FOREST])

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
        cost = 2 if route_type in {RouteType.ROAD, RouteType.TRACK} else terrain_info.travel_point_cost

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
            encounter_roll = self._check_encounter(terrain_info, route_type)
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
                    }
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
            self._travel_points_total = MovementCalculator.get_forced_march_travel_points(party_speed)
        else:
            self._travel_points_total = MovementCalculator.get_travel_points(party_speed)

        self._travel_points_remaining = self._travel_points_total
        self._pending_entry_cost = self._pending_entry_cost  # carry-over from prior day
        self._encounter_checked_today = False

        # Lost check once per day (none on roads, 1-in-6 on tracks, terrain-based in wild)
        lost_chance = 0
        if route_type == RouteType.TRACK:
            lost_chance = 1
        elif route_type == RouteType.WILD:
            # Use current terrain if available
            current_hex = self.controller.party_state.location.location_id
            terrain = self.get_terrain_for_hex(current_hex)
            lost_chance = self.get_terrain_info(terrain).lost_chance

        # Visibility modifiers could increase lost_chance; handled externally if needed
        if lost_chance > 0:
            nav_roll = self.dice.roll_d6(1, "lost check")
            self._lost_today = nav_roll.total <= lost_chance
        else:
            self._lost_today = False

    def _get_party_speed(self) -> int:
        """
        Get party movement speed per Dolmenwood rules (p146, p148-149).

        Party speed is determined by the slowest member's encumbered speed.

        Returns:
            Party movement speed in feet (encumbrance-adjusted)
        """
        # Get encumbrance-adjusted party speed from controller
        return self.controller.get_party_speed()

    def _check_encounter(self, terrain_info: TerrainInfo, route_type: RouteType) -> bool:
        """Daily wandering monster check based on terrain and route."""
        if route_type == RouteType.ROAD:
            return False

        chance = terrain_info.encounter_chance
        roll = self.dice.roll_d6(1, "wandering encounter")
        return roll.total <= chance

    def _generate_encounter(
        self,
        hex_id: str,
        terrain: TerrainType
    ) -> EncounterState:
        """
        Generate an encounter for the current hex per Dolmenwood rules (p157).

        Uses encounter tables from the Campaign Book.
        """
        # Determine surprise first (affects distance)
        surprise = self._check_surprise()

        # Determine distance based on surprise (p157)
        distance = self._roll_encounter_distance(surprise)

        # Create encounter state
        encounter = EncounterState(
            encounter_type=EncounterType.MONSTER,  # Default, would be rolled
            distance=distance,
            surprise_status=surprise,
            terrain=terrain.value,
            context=self._determine_encounter_context(),
        )

        self.controller.set_encounter(encounter)
        return encounter

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

    def search_hex(self, hex_id: str, terrain_override: Optional[TerrainType] = None) -> dict[str, Any]:
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
        }

        # Check if enough Travel Points
        if self._travel_day.travel_points_remaining < tp_cost:
            result["message"] = f"Not enough Travel Points to search. Need {tp_cost}, have {self._travel_day.travel_points_remaining}"
            return result

        # Spend Travel Points
        self._travel_day.travel_points_remaining -= tp_cost
        result["travel_points_spent"] = tp_cost
        result["travel_points_remaining"] = self._travel_day.travel_points_remaining

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
        }

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
        action_context.update({
            "game_state": "wilderness_travel",
            "current_hex": str(self.controller.party_state.location),
            "terrain": self.get_terrain_for_hex(
                str(self.controller.party_state.location)
            ).value if self.controller.party_state else "unknown",
            "weather": self.controller.world_state.weather.value if self.controller.world_state else "clear",
            "season": self.controller.world_state.season.value if self.controller.world_state else "normal",
            "time_of_day": self.controller.world_state.time_of_day.value if self.controller.world_state else "day",
        })

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
            # Apply condition through controller if available
            pass  # Condition handling would go through controller

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
    ) -> HazardResult:
        """
        Attempt to find food in the wild per Dolmenwood rules (p152).

        Args:
            character_id: ID of the foraging character
            method: "foraging", "fishing", or "hunting"
            full_day: Whether spending full day foraging (+2 bonus)

        Returns:
            HazardResult with outcomes including rations found
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

        from src.narrative.intent_parser import ActionType
        return self.narrative_resolver.hazard_resolver.resolve_foraging(
            character=character,
            method=method,
            season=season,
            full_day=full_day,
        )

    # =========================================================================
    # HEX OVERVIEW AND POI VISIBILITY
    # =========================================================================

    def _is_night(self) -> bool:
        """Check if it's currently night time."""
        if not self.controller.world_state:
            return False
        time_of_day = self.controller.world_state.time_of_day
        return time_of_day in (TimeOfDay.DUSK, TimeOfDay.NIGHT, TimeOfDay.MIDNIGHT)

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
        if self.controller.world_state:
            time_of_day = self.controller.world_state.time_of_day
            time_descriptions = {
                TimeOfDay.DAWN: "The first light of dawn spreads across the land",
                TimeOfDay.MORNING: "Morning light filters through",
                TimeOfDay.MIDDAY: "The sun hangs high overhead",
                TimeOfDay.AFTERNOON: "Afternoon shadows begin to lengthen",
                TimeOfDay.DUSK: "The fading light of dusk casts long shadows",
                TimeOfDay.EVENING: "Evening settles over the landscape",
                TimeOfDay.NIGHT: "Darkness blankets the land",
                TimeOfDay.MIDNIGHT: "Deep night shrouds everything in darkness",
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

    def _get_time_specific_observations(
        self,
        hex_data: HexLocation,
        is_night: bool
    ) -> list[str]:
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
                weather_effects=self._apply_weather_effects(
                    self.controller.world_state.weather
                ) if self.controller.world_state else None,
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
            weather_effects=self._apply_weather_effects(
                self.controller.world_state.weather
            ) if self.controller.world_state else None,
            time_specific_observations=time_observations,
        )

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
                    f for f in poi.special_features
                    if any(
                        kw in f.lower()
                        for kw in ["at night", "nighttime", "darkness", "hours of darkness"]
                    )
                ]
                if night_features:
                    poi_info["notable"] = night_features[0]

            visible.append(poi_info)

        return visible

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

        # Check for approach hazards in special_features
        hazards = []
        for feature in poi.special_features:
            feature_lower = feature.lower()
            if any(
                kw in feature_lower
                for kw in ["climbing", "thorns", "dangerous", "treacherous"]
            ):
                hazards.append(feature)

        result = {
            "success": True,
            "poi_type": poi.poi_type,
            "description": "\n\n".join(description_parts),
            "can_enter": poi.entering is not None or poi.interior is not None,
            "is_dungeon": poi.is_dungeon,
            "hazards": hazards,
            "state": POIExplorationState.APPROACHING.value,
        }

        # If there are inhabitants, note them (without revealing secrets)
        if poi.inhabitants and not is_night:
            # Some inhabitants might only be present at certain times
            result["activity_noted"] = True

        return result

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

        is_night = self._is_night()

        # Check if this is a dungeon - if so, should transition state
        if poi.is_dungeon:
            return {
                "success": False,
                "is_dungeon": True,
                "message": "This location requires dungeon exploration mode",
                "dungeon_levels": poi.dungeon_levels,
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

        result = {
            "success": True,
            "poi_type": poi.poi_type,
            "description": "\n\n".join(description_parts),
            "state": POIExplorationState.AT_ENTRANCE.value,
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
                kw in feature.lower()
                for kw in ["night", "day", "darkness", "light"]
            ),
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
            "description": parent.get_interior_description(is_night) or parent.get_description(is_night),
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

    def _apply_magical_effect_from_text(
        self,
        text: str,
        effects: HexMagicalEffects
    ) -> None:
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
                            npc_info["demeanor"] = npc_data.demeanor[0] if npc_data.demeanor else None
                        npcs.append(npc_info)
                    else:
                        # Minimal info from reference
                        npcs.append({
                            "name": npc_ref,
                            "met_before": npc_ref in self._met_npcs,
                        })

                # Check inhabitants field for additional NPCs
                if poi.inhabitants:
                    # Parse inhabitants string for NPC info
                    # This might be a dice notation like "1d4 bandits"
                    npcs.append({
                        "inhabitants": poi.inhabitants,
                        "is_group": True,
                    })

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
            result.update({
                "description": npc_data.description,
                "demeanor": npc_data.demeanor,
                "speech": npc_data.speech,
                "desires": npc_data.desires,  # What they want
            })

        # Trigger transition to SOCIAL_INTERACTION
        self.controller.transition(
            "npc_interaction_started",
            context={
                "npc_id": npc_id,
                "hex_id": hex_id,
                "poi_name": self._current_poi,
            }
        )

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
                    }
                )

                return encounter

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
                # Filter out already taken items
                visit_key = f"{hex_id}:{self._current_poi}"
                taken_items = []
                if visit_key in self._poi_visits:
                    taken_items = self._poi_visits[visit_key].items_taken

                available_items = []
                for item in poi.items:
                    item_name = item.get("name", "unknown")
                    if item_name not in taken_items and not item.get("taken", False):
                        available_items.append({
                            "name": item_name,
                            "description": item.get("description", ""),
                            "value": item.get("value"),
                        })

                return available_items

        return []

    def take_item(
        self,
        hex_id: str,
        item_name: str,
        character_id: str,
    ) -> dict[str, Any]:
        """
        Take an item from the current POI.

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
                        if item.get("taken", False):
                            return {"success": False, "error": "Item already taken"}

                        # Mark as taken
                        item["taken"] = True

                        # Track in visit
                        visit_key = f"{hex_id}:{self._current_poi}"
                        if visit_key in self._poi_visits:
                            self._poi_visits[visit_key].items_taken.append(item.get("name"))
                            if item.get("name") not in self._poi_visits[visit_key].items_found:
                                self._poi_visits[visit_key].items_found.append(item.get("name"))

                        return {
                            "success": True,
                            "item_name": item.get("name"),
                            "description": item.get("description", ""),
                            "value": item.get("value"),
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
                            hazard.get("hazard_type", "environmental")
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
            armor_weight = character.armor_weight.value if hasattr(character, 'armor_weight') else "unarmoured"
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
                        blocking_locks.append({
                            "index": i,
                            "type": lock.get("type"),
                            "description": lock.get("description", "A barrier blocks your way"),
                            "requirement_hint": self._get_lock_hint(lock),
                        })

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
                    }
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
                    poi_info["locks"] = [
                        lock.get("type") for lock in poi.get_active_locks()
                    ]

                if poi.hazards:
                    poi_info["hazards"] = [
                        h.get("hazard_type") for h in poi.hazards
                    ]

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
            occurred_at=self.controller.world_state.current_date if self.controller.world_state else None,
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
            narrative_description=narrative_description or f"The {curse_name.replace('_', ' ')} has been lifted.",
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
                        result["items"].append({
                            "name": item.get("name"),
                            "description": item.get("description", ""),
                        })

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
        armor_weight = character.armor_weight.value if hasattr(character, 'armor_weight') else "unarmoured"
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

        armor_weight = character.armor_weight.value if hasattr(character, 'armor_weight') else "unarmoured"
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
        return [
            char_id for char_id, state in self._diving_states.items()
            if state.is_diving
        ]

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
                results["failed"].append({
                    "item": item_name,
                    "error": "No POI specified",
                })
                continue

            success = hex_data.migrate_item_to_poi(item_name, poi_name, sub_location_name)

            if success:
                results["migrated"].append({
                    "item": item_name,
                    "poi": poi_name,
                    "sub_location": sub_location_name,
                })
            else:
                results["failed"].append({
                    "item": item_name,
                    "error": "Item or POI not found",
                })

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
