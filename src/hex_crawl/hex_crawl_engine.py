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
)


logger = logging.getLogger(__name__)


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
    TerrainType.FOREST: TerrainInfo(
        TerrainType.FOREST,
        TerrainDifficulty.LIGHT,
        travel_points=2,
        lost_chance=1,
        encounter_chance=1,
        mount_vehicle=MountVehicleRestriction.ALLOWED,
        description="Light, airy woods (open forest)"
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

    def __init__(self, controller: GlobalController):
        """
        Initialize the hex crawl engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

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

        # Mark hex as explored
        self._explored_hexes.add(result.actual_hex)

        # Weather and terrain notes
        weather = self.controller.world_state.weather
        weather_effect = self._apply_weather_effects(weather)
        if weather_effect:
            result.weather_effect = weather_effect
            result.messages.append(f"Weather: {weather_effect}")

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
