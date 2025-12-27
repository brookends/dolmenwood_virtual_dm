"""
Hex Crawl Engine for Dolmenwood Virtual DM.

Implements the Wilderness Travel Loop from Section 5.2 of the specification.
Handles overland movement, navigation checks, encounter rolls, and terrain effects.

The hex crawl loop per travel segment:
1. Advance time (segment length depends on terrain)
2. Consume food/water if threshold crossed
3. Check navigation (lost check)
4. Check encounter (1-in-X)
5. If encounter -> Generate encounter -> Transition to WILDERNESS_ENCOUNTER
6. Apply weather & terrain effects
7. Update party location
8. Request LLM description (terrain + atmosphere only)
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
)


logger = logging.getLogger(__name__)


class NavigationResult(str, Enum):
    """Result of navigation check."""
    SUCCESS = "success"
    VEERED = "veered"  # Went to adjacent hex instead
    LOST = "lost"  # Wandered randomly


class TravelPace(str, Enum):
    """Travel pace affecting speed and encounters."""
    CAUTIOUS = "cautious"  # Half speed, +1 surprise others
    NORMAL = "normal"  # 8 hours travel, 4 hours rest (p156)
    FORCED_MARCH = "forced_march"  # 12 hours travel, 50% more Travel Points (p156)


class TerrainDifficulty(str, Enum):
    """Terrain difficulty categories per Dolmenwood rules (p157)."""
    LIGHT = "light"      # 2 TP to enter/search, 1-in-6 lost/encounters
    MODERATE = "moderate"  # 3 TP to enter/search, 2-in-6 lost/encounters
    DIFFICULT = "difficult"  # 4 TP to enter/search, 3-in-6 lost/encounters
    ROAD = "road"        # 2 TP per 6 miles, no lost chance
    TRACK = "track"      # 2 TP per 6 miles, 1-in-6 lost chance


class MountVehicleRestriction(str, Enum):
    """Mount and vehicle restrictions by terrain (p157)."""
    ALLOWED = "allowed"  # Mounts and vehicles may enter
    MOUNTS_LED = "mounts_led"  # Mounts must be led, no vehicles
    NONE = "none"  # No mounts or vehicles


@dataclass
class TerrainInfo:
    """
    Information about terrain type per Dolmenwood rules (p157).

    Terrain is categorized as Light, Moderate, or Difficult:
    - Light: 2 TP, 1-in-6 lost/encounters, mounts/vehicles allowed
    - Moderate: 3 TP, 2-in-6 lost/encounters, mounts led only
    - Difficult: 4 TP, 3-in-6 lost/encounters, no mounts/vehicles
    """
    terrain_type: TerrainType
    difficulty: TerrainDifficulty
    travel_points: int  # Travel Points to enter/search hex (p157)
    lost_chance: int  # X-in-6 chance of getting lost (p157)
    encounter_chance: int  # X-in-6 chance of encounter (p157)
    mount_vehicle: MountVehicleRestriction
    description: str = ""


# Terrain definitions per Dolmenwood rules (p157)
TERRAIN_DATA: dict[TerrainType, TerrainInfo] = {
    # Roads and Tracks (p156) - 2 TP per 6 miles
    TerrainType.ROAD: TerrainInfo(
        TerrainType.ROAD,
        TerrainDifficulty.ROAD,
        travel_points=2,  # Per 6 miles
        lost_chance=0,  # No chance of getting lost on roads
        encounter_chance=1,
        mount_vehicle=MountVehicleRestriction.ALLOWED,
        description="Well-maintained road through the woods"
    ),
    TerrainType.TRAIL: TerrainInfo(
        TerrainType.TRAIL,
        TerrainDifficulty.TRACK,
        travel_points=2,  # Per 6 miles
        lost_chance=1,  # 1-in-6 on tracks (p157)
        encounter_chance=1,
        mount_vehicle=MountVehicleRestriction.ALLOWED,
        description="Winding forest trail"
    ),
    # Light Terrain (p157) - 2 TP, 1-in-6
    TerrainType.FARMLAND: TerrainInfo(
        TerrainType.FARMLAND,
        TerrainDifficulty.LIGHT,
        travel_points=2,
        lost_chance=1,
        encounter_chance=1,
        mount_vehicle=MountVehicleRestriction.ALLOWED,
        description="Tilled fields and lanes"
    ),
    TerrainType.HILLS: TerrainInfo(
        TerrainType.HILLS,
        TerrainDifficulty.LIGHT,
        travel_points=2,
        lost_chance=1,
        encounter_chance=1,
        mount_vehicle=MountVehicleRestriction.ALLOWED,
        description="Undulating grassland"
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
        TerrainType.MOOR,
        TerrainDifficulty.MODERATE,
        travel_points=3,
        lost_chance=2,
        encounter_chance=2,
        mount_vehicle=MountVehicleRestriction.MOUNTS_LED,
        description="Treeless mire (bog)"
    ),
    TerrainType.DEEP_FOREST: TerrainInfo(
        TerrainType.DEEP_FOREST,
        TerrainDifficulty.MODERATE,
        travel_points=3,
        lost_chance=2,
        encounter_chance=2,
        mount_vehicle=MountVehicleRestriction.MOUNTS_LED,
        description="Dense, gloomy tangled forest"
    ),
    TerrainType.RIVER: TerrainInfo(
        TerrainType.RIVER,
        TerrainDifficulty.MODERATE,
        travel_points=3,
        lost_chance=2,
        encounter_chance=2,
        mount_vehicle=MountVehicleRestriction.MOUNTS_LED,
        description="River crossing required"
    ),
    # Difficult Terrain (p157) - 4 TP, 3-in-6
    TerrainType.SWAMP: TerrainInfo(
        TerrainType.SWAMP,
        TerrainDifficulty.DIFFICULT,
        travel_points=4,
        lost_chance=3,
        encounter_chance=3,
        mount_vehicle=MountVehicleRestriction.NONE,
        description="Wetland with sparse trees"
    ),
    TerrainType.MOUNTAINS: TerrainInfo(
        TerrainType.MOUNTAINS,
        TerrainDifficulty.DIFFICULT,
        travel_points=4,
        lost_chance=3,
        encounter_chance=3,
        mount_vehicle=MountVehicleRestriction.NONE,
        description="Craggy forest with broken terrain"
    ),
    TerrainType.LAKE: TerrainInfo(
        TerrainType.LAKE,
        TerrainDifficulty.DIFFICULT,
        travel_points=4,
        lost_chance=3,
        encounter_chance=3,
        mount_vehicle=MountVehicleRestriction.NONE,
        description="Lake - requires boat or detour"
    ),
    TerrainType.SETTLEMENT: TerrainInfo(
        TerrainType.SETTLEMENT,
        TerrainDifficulty.LIGHT,
        travel_points=2,
        lost_chance=0,
        encounter_chance=1,
        mount_vehicle=MountVehicleRestriction.ALLOWED,
        description="Settled area"
    ),
}


@dataclass
class TravelSegmentResult:
    """Result of processing one travel segment per Dolmenwood rules (p156-157)."""
    success: bool
    travel_points_spent: int  # Travel Points consumed (p156)
    travel_points_remaining: int  # TP remaining for the day
    navigation_result: NavigationResult
    encounter_occurred: bool
    encounter: Optional[EncounterState] = None
    destination_hex: str = ""
    actual_hex: str = ""  # May differ if lost/veered
    weather_effect: Optional[str] = None
    terrain_effect: Optional[str] = None
    resource_consumed: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    # Mount/vehicle restrictions (p157)
    mount_restriction: Optional[str] = None
    vehicle_restriction: Optional[str] = None


@dataclass
class TravelDayState:
    """
    Tracks travel state for a single day per Dolmenwood rules (p156).

    Travel Points per day = Speed / 5:
    - Speed 40 (mounted): 8 TP normal, 12 TP forced march
    - Speed 30 (cart/wagon): 6 TP normal, 9 TP forced march
    - Speed 20: 4 TP normal, 6 TP forced march
    """
    base_speed: int = 30  # Party base speed
    travel_points_max: int = 6  # TP for the day (speed / 5)
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
    - Travel Points system (Speed / 5 per day)
    - Movement between hexes (2-4 TP depending on terrain)
    - Navigation checks (X-in-6 based on terrain, visibility modifiers)
    - Random encounter checks (X-in-6 based on terrain)
    - Weather and terrain effects
    - Forced march and exhaustion
    - Weekly rest requirements
    - Mount and vehicle restrictions
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

        # Current travel state per Dolmenwood rules (p156)
        self._travel_day: TravelDayState = TravelDayState()
        self._is_mounted: bool = False  # Mounted party has Speed 40 (p156)
        self._has_vehicle: bool = False  # Cart/wagon = Speed 30 (p156)
        self._has_guide: bool = False
        self._has_map: bool = False

        # Callbacks for external systems (like LLM description requests)
        self._description_callback: Optional[Callable] = None

    # =========================================================================
    # TRAVEL POINTS MANAGEMENT (p156)
    # =========================================================================

    def start_travel_day(self, forced_march: bool = False) -> TravelDayState:
        """
        Start a new travel day and calculate Travel Points.

        Travel Points = Speed / 5 (p156)
        - Speed 40 (mounted): 8 TP normal, 12 TP forced march
        - Speed 30 (cart/wagon): 6 TP normal, 9 TP forced march
        - Speed 20: 4 TP normal, 6 TP forced march

        Forced march adds 50% more TP but requires rest next day (p156).
        """
        # Determine base speed
        if self._is_mounted:
            base_speed = 40
        elif self._has_vehicle:
            base_speed = 30
        else:
            base_speed = 30  # Default walking speed

        # Calculate Travel Points
        base_tp = base_speed // 5
        if forced_march:
            travel_points = int(base_tp * 1.5)  # 50% more for forced march
        else:
            travel_points = base_tp

        # Check for forced march exhaustion (p156)
        warnings = []
        if self._travel_day.is_forced_march and not forced_march:
            # Previous day was forced march, need rest or exhaustion
            warnings.append("Must rest today after forced march or become exhausted")

        # Check weekly rest requirement (p157)
        if self._travel_day.days_since_rest >= 6:
            warnings.append("Must rest - 6 days of travel without rest causes exhaustion")

        self._travel_day = TravelDayState(
            base_speed=base_speed,
            travel_points_max=travel_points,
            travel_points_remaining=travel_points,
            is_forced_march=forced_march,
            days_since_rest=self._travel_day.days_since_rest + 1,
            consecutive_forced_marches=(
                self._travel_day.consecutive_forced_marches + 1 if forced_march
                else 0
            ),
        )

        return self._travel_day

    def get_travel_points_remaining(self) -> int:
        """Get remaining Travel Points for today."""
        return self._travel_day.travel_points_remaining

    def rest_day(self) -> dict[str, Any]:
        """
        Take a rest day (p157).

        Characters must rest 1 day per week (6 days travel, 1 day rest)
        or become exhausted.
        """
        result = {
            "rested": True,
            "days_since_rest_before": self._travel_day.days_since_rest,
            "forced_march_recovery": self._travel_day.is_forced_march,
        }

        self._travel_day.days_since_rest = 0
        self._travel_day.consecutive_forced_marches = 0
        self._travel_day.is_forced_march = False
        self._travel_day.travel_points_remaining = 0

        return result

    def set_mounted(self, mounted: bool) -> None:
        """Set whether party is mounted (Speed 40)."""
        self._is_mounted = mounted

    def set_has_vehicle(self, has_vehicle: bool) -> None:
        """Set whether party has cart/wagon (Speed 30)."""
        self._has_vehicle = has_vehicle

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
        terrain_override: Optional[TerrainType] = None
    ) -> TravelSegmentResult:
        """
        Execute one travel segment to an adjacent hex per Dolmenwood rules (p156-157).

        Travel Procedure Per Day:
        1. Weather (determined by Referee)
        2. Decide course
        3. Losing direction check (once per day)
        4. Wandering monster check (once per day)
        5. Description of terrain and sites
        6. End of day - camping, time updates

        Args:
            destination_hex: Target hex ID
            terrain_override: Override terrain type (for special situations)

        Returns:
            TravelSegmentResult with all outcomes
        """
        # Validate we're in the right state
        if self.controller.current_state != GameState.WILDERNESS_TRAVEL:
            return TravelSegmentResult(
                success=False,
                travel_points_spent=0,
                travel_points_remaining=self._travel_day.travel_points_remaining,
                navigation_result=NavigationResult.SUCCESS,
                encounter_occurred=False,
                warnings=["Not in WILDERNESS_TRAVEL state"]
            )

        # Get terrain info
        terrain = terrain_override or self.get_terrain_for_hex(destination_hex)
        terrain_info = self.get_terrain_info(terrain)

        # Check mount/vehicle restrictions (p157)
        restriction_result = self._check_mount_vehicle_restrictions(terrain_info)
        if not restriction_result["allowed"]:
            return TravelSegmentResult(
                success=False,
                travel_points_spent=0,
                travel_points_remaining=self._travel_day.travel_points_remaining,
                navigation_result=NavigationResult.SUCCESS,
                encounter_occurred=False,
                warnings=[restriction_result["reason"]],
                mount_restriction=restriction_result.get("mount_restriction"),
                vehicle_restriction=restriction_result.get("vehicle_restriction"),
            )

        # Check if enough Travel Points remain
        tp_cost = terrain_info.travel_points
        if self._travel_day.travel_points_remaining < tp_cost:
            # Not enough TP - partial progress (p157)
            partial_tp = self._travel_day.travel_points_remaining
            self._travel_day.travel_points_remaining = 0
            return TravelSegmentResult(
                success=False,
                travel_points_spent=partial_tp,
                travel_points_remaining=0,
                navigation_result=NavigationResult.SUCCESS,
                encounter_occurred=False,
                destination_hex=destination_hex,
                actual_hex="",  # Didn't reach destination
                messages=[
                    f"Not enough Travel Points to enter hex. "
                    f"Spent {partial_tp} TP, need {tp_cost - partial_tp} more tomorrow."
                ],
            )

        result = TravelSegmentResult(
            success=True,
            travel_points_spent=tp_cost,
            travel_points_remaining=self._travel_day.travel_points_remaining - tp_cost,
            navigation_result=NavigationResult.SUCCESS,
            encounter_occurred=False,
            destination_hex=destination_hex,
            actual_hex=destination_hex,
        )

        # Spend Travel Points
        self._travel_day.travel_points_remaining -= tp_cost
        result.messages.append(
            f"Spent {tp_cost} Travel Points ({result.travel_points_remaining} remaining)"
        )

        # 3. Navigation/lost check (once per day at start) (p157)
        if not self._travel_day.lost_check_made:
            nav_result = self._check_navigation(terrain_info)
            result.navigation_result = nav_result
            self._travel_day.lost_check_made = True

            if nav_result == NavigationResult.LOST:
                result.actual_hex = self._get_random_adjacent_hex(destination_hex)
                result.warnings.append("The party has become lost!")
                result.messages.append(f"Wandered to hex {result.actual_hex} instead")
            elif nav_result == NavigationResult.VEERED:
                result.actual_hex = self._get_veered_hex(destination_hex)
                result.warnings.append("The party veered off course")
                result.messages.append(f"Arrived at hex {result.actual_hex} instead")

        # 4. Encounter check (once per day) (p157)
        if not self._travel_day.encounter_check_made:
            encounter_roll = self._check_encounter(terrain_info)
            self._travel_day.encounter_check_made = True

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

        # 5. Apply weather effects
        weather = self.controller.world_state.weather
        weather_effect = self._apply_weather_effects(weather)
        if weather_effect:
            result.weather_effect = weather_effect
            result.messages.append(f"Weather: {weather_effect}")

        # 6. Apply terrain effects
        terrain_effect = self._apply_terrain_effects(terrain_info)
        if terrain_effect:
            result.terrain_effect = terrain_effect
            result.messages.append(f"Terrain: {terrain_effect}")

        # 7. Update party location (if no encounter, or after encounter resolves)
        if not result.encounter_occurred:
            self.controller.set_party_location(
                LocationType.HEX,
                result.actual_hex
            )

        # Mark hex as explored
        self._explored_hexes.add(result.actual_hex)

        # 8. Request description (if callback registered)
        if self._description_callback and not result.encounter_occurred:
            self._description_callback(
                location=result.actual_hex,
                terrain=terrain.value,
                weather=weather.value,
                time_of_day=self.controller.time_tracker.game_time.get_time_of_day().value,
            )

        return result

    def _check_mount_vehicle_restrictions(
        self, terrain_info: TerrainInfo
    ) -> dict[str, Any]:
        """
        Check if mounts and vehicles can enter terrain (p157).

        - Light terrain: Mounts and vehicles may enter
        - Moderate terrain: Mounts must be led, no vehicles
        - Difficult terrain: No mounts or vehicles
        """
        result = {"allowed": True}

        restriction = terrain_info.mount_vehicle

        if restriction == MountVehicleRestriction.NONE:
            if self._is_mounted:
                result["allowed"] = False
                result["reason"] = "Mounts cannot enter this terrain"
                result["mount_restriction"] = "not_allowed"
            if self._has_vehicle:
                result["allowed"] = False
                result["reason"] = "Vehicles cannot enter this terrain"
                result["vehicle_restriction"] = "not_allowed"
        elif restriction == MountVehicleRestriction.MOUNTS_LED:
            if self._has_vehicle:
                result["allowed"] = False
                result["reason"] = "Vehicles cannot enter this terrain"
                result["vehicle_restriction"] = "not_allowed"
            if self._is_mounted:
                result["mount_restriction"] = "must_be_led"
                result["allowed"] = True  # Can enter but must lead mount

        return result

    def _check_navigation(self, terrain_info: TerrainInfo) -> NavigationResult:
        """
        Check if party gets lost per Dolmenwood rules (p157).

        Chance of getting lost:
        - Roads: No chance (0-in-6)
        - Tracks: 1-in-6
        - Light terrain: 1-in-6
        - Moderate terrain: 2-in-6
        - Difficult terrain: 3-in-6

        Visibility modifiers:
        - Fog/blizzard: +1 to lost chance
        - Darkness: +2 to lost chance

        Modifiers:
        - Guide: -1 to lost chance
        - Map: -1 to lost chance

        Returns:
            NavigationResult indicating success/failure
        """
        lost_chance = terrain_info.lost_chance

        # Roads never get lost (p157)
        if terrain_info.difficulty == TerrainDifficulty.ROAD:
            return NavigationResult.SUCCESS

        # Visibility modifiers (p157)
        weather = self.controller.world_state.weather
        if weather in {Weather.FOG, Weather.BLIZZARD}:
            lost_chance += 1  # +1 for reduced visibility
        if not self.controller.time_tracker.game_time.is_daylight():
            lost_chance += 2  # +2 for darkness

        # Apply helper modifiers
        if self._has_guide:
            lost_chance -= 1
        if self._has_map:
            lost_chance -= 1

        # Clamp to valid range
        lost_chance = max(0, min(6, lost_chance))

        if lost_chance == 0:
            return NavigationResult.SUCCESS

        # Roll for getting lost (X-in-6 chance)
        roll = self.dice.roll_d6(1, "lost check")

        if roll.total <= lost_chance:
            # Lost - effects described in Dolmenwood Campaign Book
            return NavigationResult.LOST

        return NavigationResult.SUCCESS

    def _check_encounter(self, terrain_info: TerrainInfo) -> bool:
        """
        Check for wandering monsters per Dolmenwood rules (p157).

        Chance of encounter (X-in-6):
        - Light terrain: 1-in-6
        - Moderate terrain: 2-in-6
        - Difficult terrain: 3-in-6

        One check per day, made at start, middle, or end of travel day.

        Returns:
            True if encounter occurs
        """
        encounter_chance = terrain_info.encounter_chance

        # Roll for encounter (X-in-6 chance)
        roll = self.dice.roll_d6(1, "wandering monster check")

        return roll.total <= encounter_chance

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

        # Cautious pace gives bonus
        party_threshold = 2
        enemy_threshold = 2

        if self._travel_pace == TravelPace.CAUTIOUS:
            enemy_threshold = 3  # Easier to surprise enemies

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

    def _apply_terrain_effects(self, terrain_info: TerrainInfo) -> Optional[str]:
        """Apply terrain-specific effects."""
        if terrain_info.terrain_type == TerrainType.SWAMP:
            # Check for disease/environmental hazard
            roll = self.dice.roll_d6(1, "swamp hazard")
            if roll.total == 1:
                return "Miasma - save vs poison or become ill"
        elif terrain_info.terrain_type == TerrainType.DEEP_FOREST:
            # Fairy influence check
            roll = self.dice.roll_d6(1, "fairy influence")
            if roll.total == 1:
                return "Strange lights glimpsed between the trees"
        return None

    # =========================================================================
    # ENCOUNTER RESOLUTION
    # =========================================================================

    def resolve_encounter_reaction(self) -> ReactionResult:
        """
        Roll reaction for current encounter.

        2d6 Reaction Table:
        2: Hostile, attacks
        3-5: Unfriendly, may attack
        6-8: Neutral, uncertain
        9-11: Friendly, may help
        12: Helpful, will assist

        Returns:
            ReactionResult
        """
        encounter = self.controller.get_encounter()
        if not encounter:
            return ReactionResult.NEUTRAL

        roll = self.dice.roll_2d6("reaction roll")

        # Apply modifiers based on party charisma, etc.
        # (Would get from party leader's CHA modifier)
        total = roll.total

        if total <= 2:
            result = ReactionResult.HOSTILE
        elif total <= 5:
            result = ReactionResult.UNFRIENDLY
        elif total <= 8:
            result = ReactionResult.NEUTRAL
        elif total <= 11:
            result = ReactionResult.FRIENDLY
        else:
            result = ReactionResult.HELPFUL

        encounter.reaction_result = result
        return result

    def handle_encounter_outcome(self, reaction: ReactionResult) -> str:
        """
        Handle the outcome of an encounter based on reaction.

        Note: This method is deprecated. Use the EncounterEngine instead for
        handling encounter outcomes with the unified ENCOUNTER state.

        Args:
            reaction: The reaction roll result

        Returns:
            Trigger name for state transition
        """
        if reaction == ReactionResult.HOSTILE:
            # Transition to combat
            return "encounter_to_combat"
        elif reaction in {ReactionResult.FRIENDLY, ReactionResult.HELPFUL}:
            # May lead to social interaction
            return "encounter_to_parley"
        elif reaction == ReactionResult.UNFRIENDLY:
            # Could go either way - might attack
            roll = self.dice.roll_d6(1, "unfriendly escalation")
            if roll.total <= 2:
                return "encounter_to_combat"
            return "encounter_end_wilderness"
        else:
            # Neutral - cautious, watching
            return "encounter_end_wilderness"

    def avoid_encounter(self) -> bool:
        """
        Attempt to avoid current encounter.

        Note: This method is deprecated. Use the EncounterEngine.execute_action()
        with EncounterAction.EVASION instead.

        Success depends on:
        - Distance
        - Surprise status
        - Terrain
        - Party movement rate

        Returns:
            True if successfully avoided
        """
        encounter = self.controller.get_encounter()
        if not encounter:
            return True

        # Can't avoid if party is surprised
        if encounter.surprise_status == SurpriseStatus.PARTY_SURPRISED:
            return False

        # Easier to avoid at greater distance
        distance_mod = encounter.distance // 30  # +1 per 30 feet

        # Roll to avoid
        roll = self.dice.roll_d6(1, "avoid encounter")
        target = 4 - distance_mod
        target = max(1, min(6, target))  # Clamp to 1-6

        if roll.total >= target:
            self.controller.clear_encounter()
            self.controller.transition("encounter_end_wilderness")
            return True

        return False

    # =========================================================================
    # EXPLORATION FEATURES
    # =========================================================================

    def search_hex(self, hex_id: str) -> dict[str, Any]:
        """
        Search current hex for hidden features per Dolmenwood rules (p157).

        Searching costs the same Travel Points as entering the hex.

        Returns:
            Dictionary with search results
        """
        terrain = self.get_terrain_for_hex(hex_id)
        terrain_info = self.get_terrain_info(terrain)
        tp_cost = terrain_info.travel_points

        result = {
            "hex_id": hex_id,
            "features_found": [],
            "lairs_found": [],
            "landmarks_found": [],
            "travel_points_spent": 0,
            "travel_points_remaining": self._travel_day.travel_points_remaining,
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

        # Search roll for each hidden feature
        for feature in hex_data.features:
            if feature.hidden and not feature.discovered:
                roll = self.dice.roll_d6(1, f"search for {feature.name}")
                if roll.total >= 5:  # Base 2-in-6 chance
                    feature.discovered = True
                    result["features_found"].append(feature.name)

        # Check for lairs
        for lair in hex_data.lairs:
            if not lair.discovered:
                roll = self.dice.roll_d6(1, "find lair")
                if roll.total == 6:  # 1-in-6 chance
                    lair.discovered = True
                    result["lairs_found"].append(lair.monster_type)

        return result

    def is_hex_explored(self, hex_id: str) -> bool:
        """Check if hex has been explored."""
        return hex_id in self._explored_hexes

    def get_visible_landmarks(self, hex_id: str) -> list[str]:
        """Get landmarks visible from current hex."""
        landmarks = []
        hex_data = self._hex_data.get(hex_id)

        if hex_data:
            for landmark in hex_data.landmarks:
                landmarks.append(landmark.name)

        # Also check adjacent hexes for visible landmarks
        # (Would implement hex adjacency logic)

        return landmarks

    def get_exploration_summary(self) -> dict[str, Any]:
        """Get summary of exploration progress and travel state."""
        return {
            "explored_hexes": list(self._explored_hexes),
            "total_explored": len(self._explored_hexes),
            "current_location": str(self.controller.party_state.location),
            # Travel Points state (p156)
            "travel_points_remaining": self._travel_day.travel_points_remaining,
            "travel_points_max": self._travel_day.travel_points_max,
            "is_forced_march": self._travel_day.is_forced_march,
            "days_since_rest": self._travel_day.days_since_rest,
            # Party configuration
            "is_mounted": self._is_mounted,
            "has_vehicle": self._has_vehicle,
            "has_guide": self._has_guide,
            "has_map": self._has_map,
            # Daily check status
            "lost_check_made": self._travel_day.lost_check_made,
            "encounter_check_made": self._travel_day.encounter_check_made,
        }
