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
    NORMAL = "normal"
    FAST = "fast"  # 1.5x speed, -1 surprise check


@dataclass
class TerrainInfo:
    """Information about terrain type."""
    terrain_type: TerrainType
    movement_cost: float  # Multiplier (1.0 = normal, 2.0 = half speed)
    encounter_chance: int  # X in 1-in-X chance (6 = 1-in-6)
    navigation_difficulty: int  # Modifier to navigation check
    description: str = ""


# Terrain definitions
TERRAIN_DATA: dict[TerrainType, TerrainInfo] = {
    TerrainType.ROAD: TerrainInfo(
        TerrainType.ROAD, 0.5, 8, -2,
        "Well-maintained road through the woods"
    ),
    TerrainType.TRAIL: TerrainInfo(
        TerrainType.TRAIL, 0.75, 6, -1,
        "Winding forest trail"
    ),
    TerrainType.FOREST: TerrainInfo(
        TerrainType.FOREST, 1.0, 6, 0,
        "Dense Dolmenwood forest"
    ),
    TerrainType.DEEP_FOREST: TerrainInfo(
        TerrainType.DEEP_FOREST, 1.5, 4, 2,
        "Primeval deep forest with ancient trees"
    ),
    TerrainType.MOOR: TerrainInfo(
        TerrainType.MOOR, 1.25, 6, 1,
        "Misty moorland"
    ),
    TerrainType.RIVER: TerrainInfo(
        TerrainType.RIVER, 2.0, 4, 0,
        "River crossing required"
    ),
    TerrainType.LAKE: TerrainInfo(
        TerrainType.LAKE, 3.0, 4, 0,
        "Lake - requires boat or detour"
    ),
    TerrainType.HILLS: TerrainInfo(
        TerrainType.HILLS, 1.5, 6, 1,
        "Wooded hills"
    ),
    TerrainType.MOUNTAINS: TerrainInfo(
        TerrainType.MOUNTAINS, 2.0, 4, 2,
        "Mountain terrain"
    ),
    TerrainType.SWAMP: TerrainInfo(
        TerrainType.SWAMP, 2.0, 3, 2,
        "Treacherous swampland"
    ),
    TerrainType.FARMLAND: TerrainInfo(
        TerrainType.FARMLAND, 0.75, 8, -1,
        "Cultivated farmland"
    ),
    TerrainType.SETTLEMENT: TerrainInfo(
        TerrainType.SETTLEMENT, 0.5, 12, -2,
        "Settled area"
    ),
}


@dataclass
class TravelSegmentResult:
    """Result of processing one travel segment."""
    success: bool
    time_spent_turns: int
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


class HexCrawlEngine:
    """
    Engine for wilderness/hex crawl exploration.

    Manages:
    - Movement between hexes
    - Navigation checks
    - Random encounter checks
    - Weather and terrain effects
    - Resource consumption during travel
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

        # Current travel state
        self._travel_pace: TravelPace = TravelPace.NORMAL
        self._has_guide: bool = False
        self._has_map: bool = False

        # Callbacks for external systems (like LLM description requests)
        self._description_callback: Optional[Callable] = None

    def set_travel_pace(self, pace: TravelPace) -> None:
        """Set the current travel pace."""
        self._travel_pace = pace

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
    # MAIN TRAVEL LOOP (Section 5.2)
    # =========================================================================

    def travel_to_hex(
        self,
        destination_hex: str,
        terrain_override: Optional[TerrainType] = None
    ) -> TravelSegmentResult:
        """
        Execute one travel segment to an adjacent hex.

        Implements the Wilderness Travel Loop from Section 5.2.

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
                time_spent_turns=0,
                navigation_result=NavigationResult.SUCCESS,
                encounter_occurred=False,
                warnings=["Not in WILDERNESS_TRAVEL state"]
            )

        result = TravelSegmentResult(
            success=True,
            time_spent_turns=0,
            navigation_result=NavigationResult.SUCCESS,
            encounter_occurred=False,
            destination_hex=destination_hex,
            actual_hex=destination_hex,
        )

        # Get terrain info
        terrain = terrain_override or self.get_terrain_for_hex(destination_hex)
        terrain_info = self.get_terrain_info(terrain)

        # 1. Calculate and advance time
        base_turns = 24  # 4 hours base for one hex
        pace_modifier = {
            TravelPace.CAUTIOUS: 2.0,
            TravelPace.NORMAL: 1.0,
            TravelPace.FAST: 0.67,
        }
        time_multiplier = terrain_info.movement_cost * pace_modifier[self._travel_pace]
        result.time_spent_turns = int(base_turns * time_multiplier)

        time_result = self.controller.advance_time(result.time_spent_turns)
        result.messages.append(
            f"Travel time: {result.time_spent_turns // 6} hours "
            f"({result.time_spent_turns} turns)"
        )

        # 2. Check for resource consumption (handled by controller on day boundary)
        if time_result.get("days_passed", 0) > 0:
            result.resource_consumed["food_days"] = time_result["days_passed"]
            result.resource_consumed["water_days"] = time_result["days_passed"]

        # Check light expiration
        if time_result.get("light_extinguished"):
            result.warnings.append(
                f"Light source ({time_result['light_source']}) has gone out!"
            )

        # 3. Navigation check
        nav_result = self._check_navigation(terrain_info)
        result.navigation_result = nav_result

        if nav_result == NavigationResult.LOST:
            # Roll for random adjacent hex
            result.actual_hex = self._get_random_adjacent_hex(destination_hex)
            result.warnings.append("The party has become lost!")
            result.messages.append(f"Wandered to hex {result.actual_hex} instead")
        elif nav_result == NavigationResult.VEERED:
            # Went to a different adjacent hex
            result.actual_hex = self._get_veered_hex(destination_hex)
            result.warnings.append("The party veered off course")
            result.messages.append(f"Arrived at hex {result.actual_hex} instead")

        # 4. Encounter check
        encounter_roll = self._check_encounter(terrain_info)
        if encounter_roll:
            result.encounter_occurred = True
            result.encounter = self._generate_encounter(result.actual_hex, terrain)

            # Transition to WILDERNESS_ENCOUNTER state
            self.controller.transition(
                "encounter_roll_success",
                context={
                    "hex_id": result.actual_hex,
                    "terrain": terrain.value,
                    "encounter_type": result.encounter.encounter_type.value,
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

    def _check_navigation(self, terrain_info: TerrainInfo) -> NavigationResult:
        """
        Check if party navigates successfully.

        Navigation check is 1d6, must roll above navigation difficulty.
        Modifiers:
        - Guide: -2 to difficulty
        - Map: -1 to difficulty
        - Ranger/Woodgrue in party: -1 to difficulty

        Returns:
            NavigationResult indicating success/failure
        """
        difficulty = terrain_info.navigation_difficulty

        # Apply modifiers
        if self._has_guide:
            difficulty -= 2
        if self._has_map:
            difficulty -= 1

        # Roll navigation
        roll = self.dice.roll_d6(1, "navigation check")

        if roll.total <= difficulty:
            # Failed - determine severity
            severity_roll = self.dice.roll_d6(1, "navigation severity")
            if severity_roll.total <= 2:
                return NavigationResult.LOST
            else:
                return NavigationResult.VEERED

        return NavigationResult.SUCCESS

    def _check_encounter(self, terrain_info: TerrainInfo) -> bool:
        """
        Check for random encounter.

        Base chance is 1-in-X where X is terrain_info.encounter_chance.
        Modifiers:
        - Cautious pace: -1 to roll (less likely to encounter)
        - Fast pace: +1 to roll (more likely to encounter)
        - Night: +1 to roll (more likely)

        Returns:
            True if encounter occurs
        """
        encounter_threshold = terrain_info.encounter_chance

        # Roll for encounter
        roll = self.dice.roll_d6(1, "encounter check")

        modifier = 0
        if self._travel_pace == TravelPace.CAUTIOUS:
            modifier -= 1
        elif self._travel_pace == TravelPace.FAST:
            modifier += 1

        if not self.controller.time_tracker.game_time.is_daylight():
            modifier += 1

        adjusted_roll = roll.total + modifier

        # Encounter on 1 (or modified 1)
        return adjusted_roll <= 1

    def _generate_encounter(
        self,
        hex_id: str,
        terrain: TerrainType
    ) -> EncounterState:
        """
        Generate an encounter for the current hex.

        Would normally use encounter tables from the Campaign Book.
        """
        # Determine distance
        distance = self._roll_encounter_distance(terrain)

        # Determine surprise
        surprise = self._check_surprise()

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

    def _roll_encounter_distance(self, terrain: TerrainType) -> int:
        """Roll initial encounter distance based on terrain."""
        # Dense terrain = closer encounters
        if terrain in {TerrainType.DEEP_FOREST, TerrainType.SWAMP}:
            return self.dice.roll("2d6", "encounter distance").total * 10
        elif terrain in {TerrainType.FOREST, TerrainType.HILLS}:
            return self.dice.roll("4d6", "encounter distance").total * 10
        else:  # Open terrain
            return self.dice.roll("6d6", "encounter distance").total * 10

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

        Args:
            reaction: The reaction roll result

        Returns:
            Trigger name for state transition
        """
        if reaction == ReactionResult.HOSTILE:
            # Transition to combat
            return "reaction_hostile"
        elif reaction in {ReactionResult.FRIENDLY, ReactionResult.HELPFUL}:
            # May lead to social interaction
            return "reaction_parley"
        elif reaction == ReactionResult.UNFRIENDLY:
            # Could go either way - might attack
            roll = self.dice.roll_d6(1, "unfriendly escalation")
            if roll.total <= 2:
                return "reaction_hostile"
            return "encounter_avoided"
        else:
            # Neutral - cautious, watching
            return "encounter_avoided"

    def avoid_encounter(self) -> bool:
        """
        Attempt to avoid current encounter.

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
            self.controller.transition("encounter_avoided")
            return True

        return False

    # =========================================================================
    # EXPLORATION FEATURES
    # =========================================================================

    def search_hex(self, hex_id: str) -> dict[str, Any]:
        """
        Search current hex for hidden features.

        Takes 1 turn (10 minutes) per search attempt.

        Returns:
            Dictionary with search results
        """
        # Advance time for search
        self.controller.advance_time(1)

        result = {
            "hex_id": hex_id,
            "features_found": [],
            "lairs_found": [],
            "landmarks_found": [],
            "time_spent": 1,
        }

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
                roll = self.dice.roll_d6(1, f"find lair")
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
        """Get summary of exploration progress."""
        return {
            "explored_hexes": list(self._explored_hexes),
            "total_explored": len(self._explored_hexes),
            "current_location": str(self.controller.party_state.location),
            "travel_pace": self._travel_pace.value,
            "has_guide": self._has_guide,
            "has_map": self._has_map,
        }
