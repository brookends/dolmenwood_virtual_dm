"""
Dungeon Engine for Dolmenwood Virtual DM.

Implements the Dolmenwood dungeon exploration loop (10-minute turns):
1) Party declares actions (move, search, listen, etc.)
2) Wandering monster check as applicable (typically every 2 turns, 1-in-6)
3) Describe outcomes / apply action results
4) End of turn bookkeeping: time, light, rest cadence, noise, spell durations

Also handles light depletion, movement between rooms, search/listen odds,
and rest cadence (1 Turn of rest per 5 Turns of activity to avoid exhaustion).
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
    interpret_reaction,
    LocationState,
    LocationType,
    LightSourceType,
    Feature,
    Hazard,
    MovementCalculator,
    MovementMode,
    MINUTES_PER_TURN,
    TURNS_PER_HOUR,
    CharacterState,
    RollTableEntry,
)

# Import narrative components (optional, may not be initialized yet)
try:
    from src.narrative.narrative_resolver import (
        NarrativeResolver,
        ResolutionResult,
        NarrationContext,
    )
    from src.narrative.hazard_resolver import HazardResolver, HazardType, HazardResult
    from src.narrative.spell_resolver import SpellResolver

    NARRATIVE_AVAILABLE = True
except ImportError:
    NARRATIVE_AVAILABLE = False
    NarrativeResolver = None
    ResolutionResult = None
    NarrationContext = None
    HazardResolver = None
    HazardType = None
    HazardResult = None
    SpellResolver = None


logger = logging.getLogger(__name__)


class DungeonActionType(str, Enum):
    """Types of actions that take a dungeon turn."""

    MOVE = "move"  # Move to adjacent room/corridor
    SEARCH = "search"  # Search 10x10 area
    LISTEN = "listen"  # Listen at door
    OPEN_DOOR = "open_door"  # Open/force door
    PICK_LOCK = "pick_lock"  # Pick a lock
    DISARM_TRAP = "disarm_trap"  # Disarm detected trap
    REST = "rest"  # Short rest (1 turn) - required 1 per 5 turns (p163)
    INTERACT = "interact"  # Interact with feature
    CAST_SPELL = "cast_spell"  # Cast a spell
    MAP = "map"  # Map the current area
    FAST_TRAVEL = "fast_travel"  # Use established safe path (p162)


class DungeonDoomResult(str, Enum):
    """
    Dungeon Doom table results for failed escape saves (p163).

    Used when characters fail to exit dungeon via the escape roll option.
    """

    ESCAPED_LOST_ITEMS = "escaped_lost_items"  # 1: Escaped, 1d6 items lost
    ESCAPED_1HP = "escaped_1hp"  # 2: Escaped, 1 HP remaining
    ESCAPED_1HP_ABILITY_LOSS = "escaped_1hp_ability_loss"  # 3: Escaped, 1 HP, -1 random ability
    LOST_WANDERING = "lost_wandering"  # 4: Lost, wandering alone or captured
    LOST_TRANSFORMED = "lost_transformed"  # 5: Transformed into or controlled by monster
    DEAD_BODY_LOOTED = "dead_body_looted"  # 6: Dead, companions looted body
    DEAD_BODY_KNOWN = "dead_body_known"  # 7: Dead, companions know body location
    DEAD_BODY_UNKNOWN = "dead_body_unknown"  # 8: Dead, body location unknown
    DEAD_DESTROYED = "dead_destroyed"  # 9: Dead, body and equipment destroyed
    BETRAYAL = "betrayal"  # 10: Roll again, can switch fate with companion


class DoorState(str, Enum):
    """State of a door."""

    OPEN = "open"
    CLOSED = "closed"
    LOCKED = "locked"
    STUCK = "stuck"
    SECRET = "secret"
    BARRED = "barred"


class LightLevel(str, Enum):
    """Light levels in dungeon areas."""

    BRIGHT = "bright"  # Full visibility
    DIM = "dim"  # Reduced visibility, -2 to hit
    DARK = "dark"  # No visibility without light source


@dataclass
class DungeonRoom:
    """Represents a room or area in the dungeon."""

    room_id: str
    name: str = ""
    description: str = ""
    dimensions: str = ""  # e.g., "30x40"
    light_level: LightLevel = LightLevel.DARK
    exits: dict[str, str] = field(default_factory=dict)  # direction -> room_id or door_id
    doors: dict[str, DoorState] = field(default_factory=dict)  # door_id -> state
    features: list[Feature] = field(default_factory=list)
    hazards: list[Hazard] = field(default_factory=list)
    occupants: list[str] = field(default_factory=list)  # monster/NPC IDs
    treasure: list[dict] = field(default_factory=list)
    visited: bool = False
    searched: bool = False
    noise_level: int = 0  # Accumulated noise


@dataclass
class DungeonTurnResult:
    """Result of processing one dungeon turn."""

    success: bool
    action_type: DungeonActionType
    action_result: dict[str, Any] = field(default_factory=dict)
    time_spent: int = 1  # Turns
    light_depleted: bool = False
    light_remaining: int = 0
    encounter_triggered: bool = False
    encounter: Optional[EncounterState] = None
    noise_generated: int = 0
    warnings: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


@dataclass
class DungeonState:
    """
    Overall state of the dungeon per Dolmenwood rules (p162-163).

    Tracks exploration state, rest requirements, and escape modifiers.
    """

    dungeon_id: str
    name: str = ""
    current_room: str = ""
    rooms: dict[str, DungeonRoom] = field(default_factory=dict)
    alert_level: int = 0  # 0-5, affects wandering monster frequency
    turns_in_dungeon: int = 0
    noise_accumulator: int = 0
    monsters_alerted: set[str] = field(default_factory=set)
    # Dolmenwood dungeon exploration tracking (p162-163)
    dungeon_level: int = 1  # Current dungeon level, affects escape roll (p163)
    turns_since_rest: int = 0  # For 5 turns exploration / 1 turn rest rule (p163)
    has_map: bool = False  # +2 to escape save if mapped (p163)
    known_exit_path: bool = False  # +4 to escape save if safe path known (p163)
    explored_rooms: set[str] = field(default_factory=set)  # For fast travel (p162)
    safe_path_to_exit: list[str] = field(default_factory=list)  # Room IDs of safe path

    # POI-inherited configuration
    poi_name: Optional[str] = None  # Source POI name
    hex_id: Optional[str] = None  # Source hex ID

    # Roll tables inherited from POI (for room/encounter generation)
    roll_tables: list = field(default_factory=list)
    room_table: Optional[Any] = None  # RollTable for room generation
    encounter_table: Optional[Any] = None  # RollTable for encounters

    # Dynamic layout configuration (for procedural dungeons like The Spectral Manse)
    # Format: {connections_per_room: "1d3", room_table: "Rooms", encounter_table: "Encounters"}
    dynamic_layout: Optional[dict[str, Any]] = None

    # Item persistence rules (for locations like The Spectral Manse)
    # Format: {default: "evaporate", exceptions: [{owner_npc: "lord_hobbled...", persists: True}]}
    item_persistence: Optional[dict[str, Any]] = None

    # Exit effects (text and mechanics from POI "leaving" field)
    leaving_description: Optional[str] = None

    # Pending time effects to apply on dungeon exit
    pending_time_effects: list[dict[str, Any]] = field(default_factory=list)


class DungeonEngine:
    """
    Engine for dungeon exploration per Dolmenwood rules (p146-147, p162-163).

    Movement Rates (p146-147):
    - Exploration: Speed × 3 per Turn (e.g., Speed 30 = 90' per 10-minute Turn)
    - Familiar/Explored Areas: Speed × 10 per Turn (e.g., Speed 30 = 300' per Turn)

    Time Units (p146):
    - 1 Turn = 10 minutes (6 Turns per hour)
    - 1 Round = 10 seconds (60 Rounds per Turn)

    Manages:
    - 10-minute exploration turns
    - Movement: 3× Speed per Turn (exploration), 10× Speed in explored areas (p162)
    - Rest requirement: 1 Turn rest per 5 Turns exploration (p163)
    - Light source tracking and depletion
    - Wandering monster checks every 2 Turns, 1-in-6 chance (p163)
    - Encounter distance: 2d6 × 10' (or 1d4 × 10' if mutual surprise) (p163)
    - Room state and discovery
    - Dungeon escape roll and Doom table (p163)
    - Established safe paths for fast travel (p162)
    """

    def __init__(
        self,
        controller: GlobalController,
        narrative_resolver: Optional[NarrativeResolver] = None,
        spell_resolver: Optional[SpellResolver] = None,
    ):
        """
        Initialize the dungeon engine.

        Args:
            controller: The global game controller
            narrative_resolver: Optional resolver for player actions (hazards, etc.)
            spell_resolver: Optional resolver for spell casting in dungeon
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Narrative resolution for player actions (climbing, swimming, etc.)
        self.narrative_resolver = narrative_resolver or NarrativeResolver(controller)
        self.spell_resolver = spell_resolver or SpellResolver()

        # Current dungeon state
        self._dungeon_state: Optional[DungeonState] = None

        # Wandering monster check frequency (p163)
        self._wandering_check_interval: int = 2  # Every 2 turns
        self._turns_since_check: int = 0
        self._turns_since_rest: int = 0  # Must rest 1 turn per 5 or risk exhaustion

        # Rest requirement tracking (p163)
        self._rest_interval: int = 5  # Must rest after 5 turns of exploration

        # Noise thresholds
        self._noise_alert_threshold: int = 10

        # Callbacks
        self._description_callback: Optional[Callable] = None

    def _get_party_speed(self) -> int:
        """
        Get party movement speed per Dolmenwood rules (p146, p148-149).

        Party speed is determined by the slowest member's encumbered speed.

        Returns:
            Party movement speed in feet (encumbrance-adjusted)
        """
        # Get encumbrance-adjusted party speed from controller
        return self.controller.get_party_speed()

    def get_exploration_movement_per_turn(self) -> int:
        """
        Get exploration movement rate per Dolmenwood rules (p146-147).

        Exploration movement = Speed × 3 per Turn.

        Returns:
            Movement rate in feet per 10-minute turn
        """
        speed = self._get_party_speed()
        return MovementCalculator.get_exploration_movement(speed)

    def get_familiar_movement_per_turn(self) -> int:
        """
        Get familiar/explored area movement rate per Dolmenwood rules (p146-147).

        Familiar area movement = Speed × 10 per Turn.
        Used for fast travel through previously explored areas.

        Returns:
            Movement rate in feet per 10-minute turn
        """
        speed = self._get_party_speed()
        return MovementCalculator.get_familiar_movement(speed)

    def calculate_turns_for_route(self, distance_feet: int, is_explored: bool = False) -> int:
        """
        Calculate turns needed to travel a route.

        Per Dolmenwood rules (p146-147):
        - Unexplored areas: Speed × 3 per turn
        - Explored/familiar areas: Speed × 10 per turn

        Args:
            distance_feet: Distance to travel in feet
            is_explored: Whether the area is explored/familiar

        Returns:
            Number of turns needed (rounded up)
        """
        speed = self._get_party_speed()
        mode = MovementMode.FAMILIAR if is_explored else MovementMode.EXPLORATION
        return MovementCalculator.calculate_turns_for_distance(distance_feet, speed, mode)

    def enter_dungeon(
        self,
        dungeon_id: str,
        entry_room: str,
        dungeon_data: Optional[DungeonState] = None,
        poi_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Enter a dungeon and begin exploration.

        Args:
            dungeon_id: Unique identifier for the dungeon
            entry_room: Starting room ID
            dungeon_data: Pre-loaded dungeon data (optional)
            poi_config: Optional POI configuration from get_poi_dungeon_config()
                Contains roll_tables, dynamic_layout, item_persistence, etc.

        Returns:
            Dictionary with entry results
        """
        # Validate state
        if self.controller.current_state not in {
            GameState.WILDERNESS_TRAVEL,
            GameState.SETTLEMENT_EXPLORATION,
        }:
            return {"error": "Cannot enter dungeon from current state"}

        # Initialize or load dungeon state
        if dungeon_data:
            self._dungeon_state = dungeon_data
        else:
            self._dungeon_state = DungeonState(
                dungeon_id=dungeon_id,
                current_room=entry_room,
            )

        # Apply POI configuration if provided
        if poi_config:
            self._dungeon_state.poi_name = poi_config.get("poi_name")
            self._dungeon_state.hex_id = poi_config.get("hex_id")
            self._dungeon_state.roll_tables = poi_config.get("roll_tables", [])
            self._dungeon_state.room_table = poi_config.get("room_table")
            self._dungeon_state.encounter_table = poi_config.get("encounter_table")
            self._dungeon_state.dynamic_layout = poi_config.get("dynamic_layout")
            self._dungeon_state.item_persistence = poi_config.get("item_persistence")
            self._dungeon_state.leaving_description = poi_config.get("leaving")

            # If dynamic layout, generate initial room
            if self._dungeon_state.dynamic_layout:
                self._generate_dynamic_room(entry_room)

        # Add entry room if not exists
        if entry_room not in self._dungeon_state.rooms:
            self._dungeon_state.rooms[entry_room] = DungeonRoom(room_id=entry_room)

        # Transition to dungeon exploration
        self.controller.transition(
            "enter_dungeon",
            context={
                "dungeon_id": dungeon_id,
                "entry_room": entry_room,
                "poi_name": poi_config.get("poi_name") if poi_config else None,
            },
        )

        # Update party location
        self.controller.set_party_location(
            LocationType.DUNGEON_ROOM, entry_room, sub_location=dungeon_id
        )

        # Check if party has light
        light_status = self._check_light_status()

        result = {
            "dungeon_id": dungeon_id,
            "entry_room": entry_room,
            "light_status": light_status,
            "state": GameState.DUNGEON_EXPLORATION.value,
        }

        # Add dynamic layout info if applicable
        if self._dungeon_state.dynamic_layout:
            result["dynamic_layout"] = True
            result["exploring_description"] = poi_config.get("exploring") if poi_config else None

        return result

    def exit_dungeon(self) -> dict[str, Any]:
        """
        Exit the dungeon to wilderness.

        Returns:
            Dictionary with exit results
        """
        if self.controller.current_state != GameState.DUNGEON_EXPLORATION:
            return {"error": "Not in dungeon exploration state"}

        dungeon_id = self._dungeon_state.dungeon_id if self._dungeon_state else "unknown"

        # Transition back to wilderness
        self.controller.transition(
            "exit_dungeon",
            context={
                "dungeon_id": dungeon_id,
                "turns_spent": self._dungeon_state.turns_in_dungeon if self._dungeon_state else 0,
            },
        )

        result = {
            "dungeon_id": dungeon_id,
            "turns_spent": self._dungeon_state.turns_in_dungeon if self._dungeon_state else 0,
            "state": GameState.WILDERNESS_TRAVEL.value,
        }

        # Clear dungeon state (but could persist for re-entry)
        # self._dungeon_state = None

        return result

    def register_description_callback(self, callback: Callable) -> None:
        """Register callback for requesting LLM descriptions."""
        self._description_callback = callback

    # =========================================================================
    # MAIN DUNGEON LOOP (Section 5.3)
    # =========================================================================

    def execute_turn(
        self, action: DungeonActionType, action_params: Optional[dict[str, Any]] = None
    ) -> DungeonTurnResult:
        """
        Execute one dungeon exploration turn per Dolmenwood rules (p162).

        Dungeon Exploration Procedure Per Turn:
        1. Decide actions (handled by caller)
        2. Wandering monsters check
        3. Description (via callback)
        4. End of Turn: Update time, light sources, spell durations, rest needs

        Args:
            action: The action to perform this turn
            action_params: Parameters for the action

        Returns:
            DungeonTurnResult with all outcomes
        """
        # Validate state
        if self.controller.current_state != GameState.DUNGEON_EXPLORATION:
            return DungeonTurnResult(
                success=False, action_type=action, warnings=["Not in DUNGEON_EXPLORATION state"]
            )

        if not self._dungeon_state:
            return DungeonTurnResult(
                success=False, action_type=action, warnings=["No active dungeon"]
            )

        action_params = action_params or {}
        result = DungeonTurnResult(
            success=True,
            action_type=action,
            time_spent=1,
        )

        # 1. Advance time
        time_result = self.controller.advance_time(1)
        self._dungeon_state.turns_in_dungeon += 1
        self._turns_since_rest += 1

        # Track rest requirement (p163) - 5 turns exploration, 1 turn rest
        if action != DungeonActionType.REST:
            self._dungeon_state.turns_since_rest += 1
            if self._dungeon_state.turns_since_rest >= self._rest_interval:
                result.warnings.append(
                    "Party needs rest! Must rest 1 Turn or become exhausted (p163)"
                )

        # 2. Deplete light sources
        if self.controller.party_state.active_light_source:
            result.light_remaining = self.controller.party_state.light_remaining_turns
            if time_result.get("light_extinguished"):
                result.light_depleted = True
                result.warnings.append("Your light source has gone out!")

        # 3. Resolve declared action
        action_result = self._resolve_action(action, action_params)
        result.action_result = action_result

        if not action_result.get("success", True):
            result.success = False
            result.messages.append(action_result.get("message", "Action failed"))

        # Rest cadence: 1 Turn rest per 5 Turns of activity
        if action == DungeonActionType.REST:
            self._turns_since_rest = 0
        elif self._turns_since_rest >= 5:
            result.warnings.append("Fatigue looming: rest for 1 Turn to avoid exhaustion.")

        # Track noise from action
        result.noise_generated = action_result.get("noise", 0)
        self._dungeon_state.noise_accumulator += result.noise_generated

        # Mark room as explored for fast travel (p162)
        if action == DungeonActionType.MOVE and action_result.get("success"):
            self._dungeon_state.explored_rooms.add(self._dungeon_state.current_room)

        # 4. Check wandering monsters (p163) - every 2 Turns, 1-in-6 chance
        self._turns_since_check += 1
        if self._turns_since_check >= self._wandering_check_interval:
            self._turns_since_check = 0
            encounter = self._check_wandering_monster()
            if encounter:
                result.encounter_triggered = True
                result.encounter = encounter
                result.messages.append("Something approaches!")

        # 5. Apply noise consequences
        if self._dungeon_state.noise_accumulator >= self._noise_alert_threshold:
            self._dungeon_state.alert_level = min(5, self._dungeon_state.alert_level + 1)
            self._dungeon_state.noise_accumulator = 0
            result.warnings.append("The dungeon stirs... alert level increased!")

        # 6. Update dungeon state
        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if current_room and not current_room.visited:
            current_room.visited = True

        # 7. Request description (if callback registered and action warrants it)
        if self._description_callback and action in {
            DungeonActionType.MOVE,
            DungeonActionType.SEARCH,
        }:
            self._description_callback(
                room_id=self._dungeon_state.current_room,
                action=action.value,
                light_level=self._get_current_light_level().value,
            )

        return result

    def _resolve_action(self, action: DungeonActionType, params: dict[str, Any]) -> dict[str, Any]:
        """Resolve a specific dungeon action."""
        handlers = {
            DungeonActionType.MOVE: self._handle_move,
            DungeonActionType.SEARCH: self._handle_search,
            DungeonActionType.LISTEN: self._handle_listen,
            DungeonActionType.OPEN_DOOR: self._handle_open_door,
            DungeonActionType.PICK_LOCK: self._handle_pick_lock,
            DungeonActionType.DISARM_TRAP: self._handle_disarm_trap,
            DungeonActionType.REST: self._handle_rest,
            DungeonActionType.INTERACT: self._handle_interact,
            DungeonActionType.CAST_SPELL: self._handle_cast_spell,
            DungeonActionType.MAP: self._handle_map,
            DungeonActionType.FAST_TRAVEL: self._handle_fast_travel,
        }

        handler = handlers.get(action)
        if handler:
            return handler(params)

        return {"success": False, "message": f"Unknown action: {action}"}

    def _handle_move(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle movement to an adjacent room."""
        direction = params.get("direction", "").lower()
        target_room = params.get("target_room")

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        # Find exit in direction or by target room
        if direction and direction in current_room.exits:
            exit_target = current_room.exits[direction]
        elif target_room and target_room in current_room.exits.values():
            exit_target = target_room
        else:
            return {"success": False, "message": f"No exit in direction: {direction}"}

        # Check for door
        door_id = f"{self._dungeon_state.current_room}_{direction}"
        door_state = current_room.doors.get(door_id)

        if door_state in {DoorState.LOCKED, DoorState.STUCK, DoorState.BARRED}:
            return {
                "success": False,
                "message": f"Door is {door_state.value}",
                "door_id": door_id,
            }

        # Move to new room
        self._dungeon_state.current_room = exit_target

        # Create room if doesn't exist
        if exit_target not in self._dungeon_state.rooms:
            self._dungeon_state.rooms[exit_target] = DungeonRoom(room_id=exit_target)

        # Update party location
        self.controller.set_party_location(
            LocationType.DUNGEON_ROOM, exit_target, sub_location=self._dungeon_state.dungeon_id
        )

        # Check for undetected traps in the new room
        new_room = self._dungeon_state.rooms[exit_target]
        trap_results = self._check_room_traps(new_room, params.get("character_id"))

        result: dict[str, Any] = {
            "success": True,
            "message": f"Moved to {exit_target}",
            "new_room": exit_target,
            "noise": 1,  # Normal movement noise
        }

        if trap_results:
            result["traps_triggered"] = trap_results
            result["noise"] = 3  # Increase noise due to trap

        return result

    def _handle_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle searching the current area per Campaign Book p155.

        Search procedure:
        1. Takes 1 turn (10 minutes) per 10x10 area
        2. 2-in-6 chance to find hidden features, secret doors, and detect traps
        3. Even on failed trap detection, provide exploration clues

        Returns:
            Dictionary with found features, traps, secret doors, and exploration clues
        """
        from src.tables.trap_tables import get_exploration_clues

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        results: dict[str, Any] = {
            "success": True,
            "found_features": [],
            "found_traps": [],
            "found_secret_doors": [],
            "exploration_clues": [],  # Hints about undetected traps
            "noise": 1,
        }

        # Check for hidden features
        for feature in current_room.features:
            if feature.hidden and not feature.discovered:
                roll = self.dice.roll_d6(1, f"search: {feature.feature_id}")
                if roll.total <= 2:  # 2-in-6 chance
                    feature.discovered = True
                    results["found_features"].append(feature.name)

        # Check for traps with exploration clues
        for hazard in current_room.hazards:
            if not hazard.detected:
                roll = self.dice.roll_d6(1, f"detect trap: {hazard.hazard_id}")

                if roll.total <= 2:  # 2-in-6 chance to fully detect
                    hazard.detected = True
                    trap_info = {"name": hazard.name, "hazard_id": hazard.hazard_id}

                    # Include trap details if using new trap system
                    trap_obj = getattr(hazard, "trap_object", None)
                    if trap_obj:
                        trap_info["category"] = trap_obj.category.value
                        trap_info["trigger"] = trap_obj.trigger.value
                        trap_info["disarm_method"] = trap_obj.get_disarm_method()

                    results["found_traps"].append(trap_info)

                elif roll.total <= 4:  # 3-4: Partial clue (per Campaign Book p155)
                    # Provide exploration clues even on failed detection
                    trap_obj = getattr(hazard, "trap_object", None)
                    if trap_obj:
                        clues = get_exploration_clues(trap_obj)
                        if clues:
                            # Pick a random clue
                            clue_roll = self.dice.roll(f"1d{len(clues)}", "clue selection")
                            clue = clues[clue_roll.total - 1]
                            results["exploration_clues"].append({
                                "clue": clue,
                                "area": f"near {hazard.name}" if hazard.name != "unknown" else "this area",
                            })
                    else:
                        # Generic clue for legacy traps
                        results["exploration_clues"].append({
                            "clue": "Something seems off about this area",
                            "area": "this area",
                        })

        # Check for secret doors
        for direction, door_state in current_room.doors.items():
            if door_state == DoorState.SECRET:
                roll = self.dice.roll_d6(1, f"find secret door: {direction}")
                if roll.total <= 2:  # 2-in-6 chance
                    current_room.doors[direction] = DoorState.CLOSED
                    results["found_secret_doors"].append(direction)

        current_room.searched = True
        return results

    def _handle_listen(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle listening at a door or area."""
        door_id = params.get("door_id")

        # Base 1-in-6 chance to hear something
        roll = self.dice.roll_d6(1, "listen")

        results = {
            "success": True,
            "heard_something": roll.total == 1,
            "noise": 0,  # Listening is quiet
        }

        if results["heard_something"]:
            # Determine what was heard (would check adjacent room contents)
            results["description"] = "You hear indistinct sounds beyond"

        return results

    def _handle_open_door(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle opening a door."""
        door_id = params.get("door_id")
        direction = params.get("direction")

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        door_key = door_id or f"{self._dungeon_state.current_room}_{direction}"
        door_state = current_room.doors.get(door_key, DoorState.CLOSED)

        if door_state == DoorState.OPEN:
            return {"success": True, "message": "Door is already open", "noise": 0}

        if door_state == DoorState.LOCKED:
            return {"success": False, "message": "Door is locked", "noise": 2}

        if door_state == DoorState.BARRED:
            return {"success": False, "message": "Door is barred from the other side", "noise": 2}

        if door_state == DoorState.STUCK:
            # Strength check to force
            roll = self.dice.roll_d6(1, "force door")
            if roll.total <= 2:  # 2-in-6 base chance
                current_room.doors[door_key] = DoorState.OPEN
                return {
                    "success": True,
                    "message": "Door forced open!",
                    "noise": 4,  # Loud!
                }
            return {
                "success": False,
                "message": "Door remains stuck",
                "noise": 3,
            }

        if door_state == DoorState.SECRET:
            return {"success": False, "message": "No door visible here", "noise": 0}

        # Normal door
        current_room.doors[door_key] = DoorState.OPEN
        return {
            "success": True,
            "message": "Door opened",
            "noise": 1,
        }

    def _handle_pick_lock(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle picking a lock."""
        door_id = params.get("door_id")
        character_id = params.get("character_id")

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        door_key = door_id
        door_state = current_room.doors.get(door_key)

        if door_state != DoorState.LOCKED:
            return {"success": False, "message": "Door is not locked", "noise": 0}

        # Thief ability check (would check character class)
        # Base 15% + 5% per level for thief
        roll = self.dice.roll_percentile("pick lock")
        threshold = 20  # Placeholder

        if roll.total <= threshold:
            current_room.doors[door_key] = DoorState.CLOSED
            return {
                "success": True,
                "message": "Lock picked!",
                "noise": 1,
            }

        return {
            "success": False,
            "message": "Failed to pick lock",
            "noise": 1,
        }

    def _handle_disarm_trap(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle disarming a detected trap per Campaign Book p102-103.

        Disarm rules by category:
        - PIT: Cannot be disarmed, only bypassed (jump, bridge, climb around)
        - ARCHITECTURAL: Cannot be disarmed, only bypassed (jam, avoid)
        - MECHANISM: Requires thief with Disarm Mechanism ability
        - MAGICAL: Requires Dispel Magic spell or knowing the password

        Args:
            params: Must include trap_id, character_id, and optionally:
                - disarm_chance: Thief's Disarm Mechanism percentage
                - has_dispel_magic: Whether using Dispel Magic spell
                - dispel_check: Caster level for dispel check
                - knows_password: Whether character knows the password

        Returns:
            Result of disarm attempt
        """
        from src.tables.trap_tables import (
            TrapCategory,
            can_attempt_disarm,
            attempt_disarm,
            get_bypass_options,
        )

        trap_id = params.get("trap_id")
        character_id = params.get("character_id")

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        # Find the trap hazard
        trap_hazard = None
        for hazard in current_room.hazards:
            if hazard.hazard_id == trap_id:
                trap_hazard = hazard
                break

        if not trap_hazard:
            return {"success": False, "message": "Trap not found", "noise": 0}

        if not trap_hazard.detected:
            return {"success": False, "message": "Must detect trap first", "noise": 0}

        if trap_hazard.disarmed:
            return {"success": True, "message": "Trap already disarmed", "noise": 0}

        # Get character info
        character = self.controller.get_character(character_id) if character_id else None
        character_class = "fighter"  # Default
        if character and hasattr(character, "character_class"):
            character_class = character.character_class.lower()

        # Get trap object if it has the new category system
        trap_obj = getattr(trap_hazard, "trap_object", None)

        if trap_obj is None:
            # Legacy trap without category - use old behavior
            roll = self.dice.roll_percentile("disarm trap")
            threshold = params.get("disarm_chance", 20)

            if roll.total <= threshold:
                trap_hazard.disarmed = True
                return {
                    "success": True,
                    "message": "Trap disarmed!",
                    "noise": 1,
                }

            trigger_roll = self.dice.roll_d6(1, "trap trigger")
            if trigger_roll.total == 1:
                # Resolve and apply legacy trap effects
                trap_result = self._resolve_and_apply_trap(
                    None, character_id, trap_hazard
                )
                return {
                    "success": False,
                    "message": "Trap triggered!",
                    "trap_triggered": True,
                    "trap_effect": trap_hazard.effect,
                    "trap_result": {
                        "damage_dealt": trap_result.damage_dealt,
                        "conditions_applied": trap_result.conditions_applied,
                        "description": trap_result.description,
                    },
                    "noise": 3,
                }

            return {
                "success": False,
                "message": "Failed to disarm trap",
                "noise": 1,
            }

        # Use category-based disarm rules
        has_dispel = params.get("has_dispel_magic", False)
        knows_password = params.get("knows_password", False)

        # Check if disarm is even possible
        can_disarm, reason = can_attempt_disarm(
            trap_obj, character_class, has_dispel, knows_password
        )

        if not can_disarm:
            # Provide bypass options for non-disarmable traps
            bypass_options = get_bypass_options(trap_obj)
            return {
                "success": False,
                "message": reason,
                "can_disarm": False,
                "bypass_options": bypass_options,
                "noise": 0,
            }

        # Attempt disarm
        disarm_chance = params.get("disarm_chance", 20)
        dispel_check = params.get("dispel_check")

        result = attempt_disarm(
            trap=trap_obj,
            character_class=character_class,
            disarm_chance=disarm_chance,
            dice=self.dice,
            has_dispel_magic=has_dispel,
            dispel_check=dispel_check,
            knows_password=knows_password,
        )

        if result.success:
            trap_hazard.disarmed = True
            return {
                "success": True,
                "message": result.message,
                "method": result.method_used,
                "noise": 1,
            }

        response = {
            "success": False,
            "message": result.message,
            "method": result.method_used,
            "noise": 1,
        }

        if result.trap_triggered:
            # Resolve and apply trap effects to the character
            trap_result = self._resolve_and_apply_trap(
                trap_obj, character_id, trap_hazard
            )
            response["trap_triggered"] = True
            response["trap_effect"] = trap_obj.effect.to_dict()
            response["trap_result"] = {
                "damage_dealt": trap_result.damage_dealt,
                "conditions_applied": trap_result.conditions_applied,
                "description": trap_result.description,
            }
            response["noise"] = 3

        return response

    def _check_room_traps(
        self,
        room: "DungeonRoom",
        character_id: Optional[str],
    ) -> list[dict[str, Any]]:
        """
        Check for and trigger undetected traps when entering a room.

        Per Campaign Book p102-103, undetected traps have a chance to trigger
        when characters interact with the trapped area.

        Args:
            room: The room being entered
            character_id: ID of the character entering (leader of marching order)

        Returns:
            List of trap results if any traps triggered
        """
        triggered_traps = []

        for hazard in room.hazards:
            # Skip detected, disarmed, or already triggered traps
            if hazard.detected or hazard.disarmed or getattr(hazard, 'triggered', False):
                continue

            # Get trap object if using new system
            trap_obj = getattr(hazard, "trap_object", None)

            # Determine trigger chance
            trigger_chance = getattr(hazard, 'trigger_chance', 2)

            # Roll to see if trap triggers
            trigger_roll = self.dice.roll_d6(1, f"trap trigger: {hazard.hazard_id}")

            if trigger_roll.total <= trigger_chance:
                # Trap triggered!
                trap_result = self._resolve_and_apply_trap(
                    trap_obj, character_id, hazard
                )

                triggered_traps.append({
                    "hazard_id": hazard.hazard_id,
                    "name": hazard.name,
                    "damage_dealt": trap_result.damage_dealt,
                    "conditions_applied": trap_result.conditions_applied,
                    "description": trap_result.description,
                    "narrative_hints": trap_result.narrative_hints,
                })

        return triggered_traps

    def _resolve_and_apply_trap(
        self,
        trap_obj: Optional[Any],
        character_id: Optional[str],
        trap_hazard: Any,
    ) -> "HazardResult":
        """
        Resolve a triggered trap and apply its effects to the game state.

        This method:
        1. Uses the hazard resolver to determine trap effects
        2. Applies damage to the affected character(s)
        3. Applies any conditions from the trap

        Args:
            trap_obj: Trap object from trap_tables (or None for legacy traps)
            character_id: ID of the character who triggered the trap
            trap_hazard: The hazard object from the room

        Returns:
            HazardResult with trap resolution details
        """
        from src.narrative.hazard_resolver import HazardResult, HazardType, ActionType

        # Get the character
        character = None
        if character_id:
            character = self.controller.get_character(character_id)

        if character is None:
            # No character to apply effects to - return minimal result
            return HazardResult(
                success=False,
                hazard_type=HazardType.TRAP,
                action_type=ActionType.NARRATIVE_ACTION,
                description="Trap triggered but no target",
            )

        # Get trap parameters
        trap_type = getattr(trap_hazard, 'trap_type', 'generic')
        trap_damage = getattr(trap_hazard, 'damage', '1d6')
        trigger_chance = getattr(trap_hazard, 'trigger_chance', 2)

        # Use hazard resolver to resolve the trap (trigger check already passed)
        # We call _resolve_trap directly with trigger_chance high enough to guarantee trigger
        result = self.narrative_resolver.hazard_resolver._resolve_trap(
            character=character,
            trap_type=trap_type,
            trap_damage=trap_damage,
            trigger_chance=6,  # Guarantee trigger since we already determined it triggered
            trap=trap_obj,
        )

        # Apply damage to the character
        for target_id, damage in result.apply_damage:
            self.controller.apply_damage(target_id, damage, "trap")

        # Apply conditions to the character
        for target_id, condition in result.apply_conditions:
            self.controller.apply_condition(target_id, condition, "trap")

        # Mark trap as triggered (it may reset or be destroyed depending on type)
        trap_hazard.triggered = True

        return result

    def _handle_rest(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle short rest (1 turn) per Dolmenwood rules (p163).

        Characters must rest 1 Turn per hour (5 Turns exploration, 1 Turn rest)
        or become exhausted.
        """
        # Reset the rest counter
        self._dungeon_state.turns_since_rest = 0

        return {
            "success": True,
            "message": "Rested for one turn (rest requirement fulfilled)",
            "noise": 0,
            "rest_fulfilled": True,
        }

    def _handle_fast_travel(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle established safe path travel per Dolmenwood rules (p162).

        To speed up play, the Referee may accelerate travel along safe,
        previously explored routes:
        1. Gauge route length
        2. Calculate Turns required (route length / 10× Speed)
        3. Check resources (light sources)
        4. Make wandering monster checks for each Turn
        5. Brief journey description (if no encounter)

        Args:
            params: Must include "route" (list of room IDs) or "destination"

        Returns:
            Result of fast travel attempt
        """
        destination = params.get("destination")
        route = params.get("route", [])

        if not route and not destination:
            return {"success": False, "message": "Must specify route or destination"}

        # If only destination provided, try to find route through explored rooms
        if not route and destination:
            if destination not in self._dungeon_state.explored_rooms:
                return {"success": False, "message": "Cannot fast travel to unexplored area"}
            # Simplified: direct travel if destination is explored
            route = [self._dungeon_state.current_room, destination]

        # Verify all rooms in route are explored
        for room_id in route:
            if room_id not in self._dungeon_state.explored_rooms:
                return {"success": False, "message": f"Route includes unexplored room: {room_id}"}

        # Calculate Turns required (simplified: 1 Turn per room transition)
        turns_required = len(route) - 1
        if turns_required <= 0:
            return {"success": False, "message": "Invalid route"}

        # Check resources - do we have enough light?
        light_remaining = self.controller.party_state.light_remaining_turns
        if light_remaining < turns_required:
            return {
                "success": False,
                "message": f"Not enough light. Need {turns_required} Turns, have {light_remaining}",
            }

        # Make wandering monster checks for the journey
        encounters = []
        for turn in range(turns_required):
            self._turns_since_check += 1
            if self._turns_since_check >= self._wandering_check_interval:
                self._turns_since_check = 0
                # Check for wandering monster
                roll = self.dice.roll_d6(1, f"fast travel monster check {turn + 1}")
                if roll.total <= (1 + self._dungeon_state.alert_level):
                    encounters.append(
                        {
                            "turn": turn + 1,
                            "room": route[turn + 1] if turn + 1 < len(route) else route[-1],
                        }
                    )
                    break  # Stop at first encounter

        if encounters:
            # Generate encounter at that point
            encounter_room = encounters[0]["room"]
            self._dungeon_state.current_room = encounter_room
            encounter = self._check_wandering_monster()
            return {
                "success": False,
                "message": f"Encountered monsters at {encounter_room}!",
                "turns_traveled": encounters[0]["turn"],
                "encounter": True,
                "noise": 0,
            }

        # Successful fast travel
        self._dungeon_state.current_room = route[-1]
        self._dungeon_state.turns_in_dungeon += turns_required

        # Update party location
        self.controller.set_party_location(
            LocationType.DUNGEON_ROOM, route[-1], sub_location=self._dungeon_state.dungeon_id
        )

        return {
            "success": True,
            "message": f"Traveled safely to {route[-1]} ({turns_required} Turns)",
            "turns_used": turns_required,
            "destination": route[-1],
            "noise": 0,
        }

    def _handle_interact(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle interacting with a feature."""
        feature_id = params.get("feature_id")

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        # Find the feature
        feature = None
        for f in current_room.features:
            if f.feature_id == feature_id:
                feature = f
                break

        if not feature:
            return {"success": False, "message": "Feature not found", "noise": 0}

        return {
            "success": True,
            "message": f"Interacted with {feature.name}",
            "feature": feature.name,
            "description": feature.description,
            "noise": 1,
        }

    def _handle_cast_spell(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Handle casting a spell during dungeon exploration.

        Integrates with SpellResolver for actual spell mechanics:
        - Spell lookup and validation
        - Slot consumption
        - Effect application
        - Concentration management
        """
        spell_name = params.get("spell_name")
        spell_id = params.get("spell_id")
        character_id = params.get("character_id")
        target_id = params.get("target_id")
        target_description = params.get("target_description")

        if not character_id:
            return {"success": False, "message": "No caster specified"}

        # Get character state
        character = self.controller.get_character(character_id)
        if not character:
            return {"success": False, "message": f"Character not found: {character_id}"}

        # Look up the spell
        spell = None
        if spell_id:
            spell = self.spell_resolver.lookup_spell(spell_id)
        elif spell_name:
            spell = self.spell_resolver.lookup_spell_by_name(spell_name)

        if not spell:
            return {
                "success": False,
                "message": f"Unknown spell: {spell_name or spell_id}",
            }

        # Resolve the spell through SpellResolver
        result = self.spell_resolver.resolve_spell(
            caster=character,
            spell=spell,
            target_id=target_id,
            target_description=target_description,
            dice_roller=self.dice,
        )

        # Build response
        response = {
            "success": result.success,
            "spell_name": spell.name,
            "caster": character.name,
            "noise": 2,  # Most spells make some noise
        }

        if result.success:
            response["message"] = f"Cast {spell.name}"
            if result.slot_consumed:
                response["slot_consumed"] = result.slot_level
            if result.effect_created:
                response["effect_created"] = {
                    "duration_type": result.effect_created.duration_type.value,
                    "duration_remaining": result.effect_created.duration_remaining,
                    "requires_concentration": result.effect_created.requires_concentration,
                }
            if result.save_required:
                response["save_required"] = result.save_result
        else:
            response["message"] = result.reason or result.error

        return response

    def _handle_map(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle mapping the current area."""
        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        return {
            "success": True,
            "message": "Area mapped",
            "room_id": self._dungeon_state.current_room,
            "exits": list(current_room.exits.keys()),
            "noise": 0,
        }

    # =========================================================================
    # WANDERING MONSTERS
    # =========================================================================

    def _check_wandering_monster(self) -> Optional[EncounterState]:
        """
        Check for wandering monster encounter per Dolmenwood rules (p163).

        Check every 2 Turns, 1-in-6 chance of encounter.
        Base 1-in-6 chance, modified by:
        - Alert level (+1 per level)
        - Recent noise

        Returns:
            EncounterState if encounter triggered, None otherwise
        """
        roll = self.dice.roll_d6(1, "wandering monster")

        # Standard Dolmenwood check: 1-in-6 every 2 Turns
        if roll.total <= 1:
            surprise = self._check_dungeon_surprise()
            distance = self._roll_dungeon_distance(
                mutual_surprise=surprise == SurpriseStatus.MUTUAL_SURPRISE
            )

            encounter = EncounterState(
                encounter_type=EncounterType.MONSTER,
                distance=distance,
                surprise_status=surprise,
                context="wandering",
            )

            self.controller.set_encounter(encounter)
            self.controller.transition(
                "encounter_triggered",
                context={
                    "dungeon_id": self._dungeon_state.dungeon_id,
                    "room_id": self._dungeon_state.current_room,
                    "source": "wandering_monster",
                    # Pass roll tables for EncounterEngine to use
                    "roll_tables": self._dungeon_state.roll_tables,
                    "poi_name": self._dungeon_state.poi_name,
                    "hex_id": self._dungeon_state.hex_id,
                },
            )

            return encounter

        return None

    def _roll_dungeon_distance(self, mutual_surprise: bool = False) -> int:
        """Roll encounter distance in dungeon (typically close)."""
        if mutual_surprise:
            roll = self.dice.roll("1d4", "dungeon distance (mutual surprise)")
        else:
            roll = self.dice.roll("2d6", "dungeon distance")
        return roll.total * 10  # 10-120 feet

    def _check_dungeon_surprise(self) -> SurpriseStatus:
        """Check for surprise in dungeon encounter."""
        party_roll = self.dice.roll_d6(1, "party surprise")
        monster_roll = self.dice.roll_d6(1, "monster surprise")

        # Light affects surprise
        light_level = self._get_current_light_level()
        party_threshold = 2 if light_level != LightLevel.DARK else 3
        monster_threshold = 2

        party_surprised = party_roll.total <= party_threshold
        monster_surprised = monster_roll.total <= monster_threshold

        if party_surprised and monster_surprised:
            return SurpriseStatus.MUTUAL_SURPRISE
        elif party_surprised:
            return SurpriseStatus.PARTY_SURPRISED
        elif monster_surprised:
            return SurpriseStatus.ENEMIES_SURPRISED
        return SurpriseStatus.NO_SURPRISE

    # =========================================================================
    # LIGHT MANAGEMENT
    # =========================================================================

    def _check_light_status(self) -> dict[str, Any]:
        """Check current light status."""
        light_source = self.controller.party_state.active_light_source
        remaining = self.controller.party_state.light_remaining_turns

        return {
            "has_light": light_source is not None and remaining > 0,
            "source": light_source.value if light_source else None,
            "remaining_turns": remaining,
            "remaining_hours": remaining / 6 if remaining > 0 else 0,
        }

    def _get_current_light_level(self) -> LightLevel:
        """Get current light level based on light sources."""
        if not self.controller.party_state.active_light_source:
            return LightLevel.DARK
        if self.controller.party_state.light_remaining_turns <= 0:
            return LightLevel.DARK

        # Check room natural light
        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if current_room and current_room.light_level == LightLevel.BRIGHT:
            return LightLevel.BRIGHT

        # Party light provides bright light
        return LightLevel.BRIGHT

    # =========================================================================
    # ENCOUNTER RESOLUTION
    # =========================================================================

    def resolve_dungeon_reaction(self) -> ReactionResult:
        """Roll reaction for dungeon encounter."""
        encounter = self.controller.get_encounter()
        if not encounter:
            return ReactionResult.UNCERTAIN

        roll = self.dice.roll_2d6("dungeon reaction")

        # Dungeon monsters often more hostile
        modifier = -1 if self._dungeon_state.alert_level > 2 else 0
        total = roll.total + modifier

        # Use canonical interpretation
        result = interpret_reaction(total)

        encounter.reaction_result = result
        return result

    def handle_dungeon_encounter_outcome(self, reaction: ReactionResult) -> str:
        """
        Handle encounter outcome and return trigger for state transition.

        Note: This method is deprecated. Use the EncounterEngine instead for
        handling encounter outcomes with the unified ENCOUNTER state.

        Args:
            reaction: Reaction roll result

        Returns:
            Trigger name for state transition
        """
        if reaction == ReactionResult.ATTACKS:
            return "encounter_to_combat"
        elif reaction == ReactionResult.FRIENDLY:
            return "encounter_to_parley"
        elif reaction == ReactionResult.HOSTILE:
            # More likely to attack in dungeon
            roll = self.dice.roll_d6(1, "hostile action")
            if roll.total <= 3:
                return "encounter_to_combat"
            return "encounter_end_dungeon"
        else:
            return "encounter_end_dungeon"

    # =========================================================================
    # DUNGEON ESCAPE ROLL (p163)
    # =========================================================================

    def attempt_escape_roll(self, character_id: str) -> dict[str, Any]:
        """
        Attempt dungeon escape roll per Dolmenwood rules (p163).

        When a character becomes lost or cannot find their way out of a dungeon,
        they may attempt an escape roll: Save vs Doom with modifiers.

        Modifiers:
        - -1 per dungeon level
        - +2 if the character has a map
        - +4 if the character knows a safe path to the exit

        On success: Character escapes safely
        On failure: Roll on Dungeon Doom table

        Args:
            character_id: ID of character attempting escape

        Returns:
            Result of escape attempt including Doom table result if failed
        """
        if not self._dungeon_state:
            return {"success": False, "error": "No active dungeon"}

        # Calculate modifiers
        level_penalty = -(self._dungeon_state.dungeon_level - 1)  # -1 per level below 1
        map_bonus = 2 if self._dungeon_state.has_map else 0
        path_bonus = 4 if self._dungeon_state.known_exit_path else 0
        total_modifier = level_penalty + map_bonus + path_bonus

        # Save vs Doom roll (assume base save of 14, modified)
        roll = self.dice.roll("1d20", "escape save vs doom")
        target = 14 - total_modifier  # Lower target is better for player

        escaped = roll.total >= target

        result = {
            "character_id": character_id,
            "roll": roll.total,
            "target": target,
            "modifier": total_modifier,
            "modifier_breakdown": {
                "dungeon_level": level_penalty,
                "has_map": map_bonus,
                "known_exit_path": path_bonus,
            },
            "escaped": escaped,
        }

        if escaped:
            result["message"] = "Successfully escaped the dungeon!"
            # Exit dungeon
            self.exit_dungeon()
        else:
            # Roll on Dungeon Doom table
            doom_result = self._roll_dungeon_doom()
            result["doom_result"] = doom_result
            result["message"] = f"Failed to escape! {doom_result['description']}"

        return result

    def _roll_dungeon_doom(self) -> dict[str, Any]:
        """
        Roll on the Dungeon Doom table per Dolmenwood rules (p163).

        d10 results:
        1: Escaped, 1d6 items lost
        2: Escaped, 1 HP remaining
        3: Escaped, 1 HP remaining, -1 to random ability score
        4: Lost (wandering alone, captured, etc.)
        5: Lost (transformed/controlled by monster)
        6: Dead (companions looted body)
        7: Dead (companions know body location)
        8: Dead (body location unknown)
        9: Dead (body and equipment destroyed)
        10: Roll again, may switch fate with companion

        Returns:
            Dictionary with doom result details
        """
        roll = self.dice.roll("1d10", "dungeon doom")

        doom_results = {
            1: {
                "result": DungeonDoomResult.ESCAPED_LOST_ITEMS,
                "description": "Escaped, but lost 1d6 items along the way",
                "items_lost": self.dice.roll("1d6", "items lost").total,
                "escaped": True,
                "alive": True,
            },
            2: {
                "result": DungeonDoomResult.ESCAPED_1HP,
                "description": "Escaped, barely alive with only 1 HP remaining",
                "hp_remaining": 1,
                "escaped": True,
                "alive": True,
            },
            3: {
                "result": DungeonDoomResult.ESCAPED_1HP_ABILITY_LOSS,
                "description": "Escaped with 1 HP, permanently lost 1 point from a random ability",
                "hp_remaining": 1,
                "ability_loss": self.dice.roll("1d6", "ability affected").total,
                "escaped": True,
                "alive": True,
            },
            4: {
                "result": DungeonDoomResult.LOST_WANDERING,
                "description": "Lost in the dungeon - wandering alone, captured, or worse",
                "escaped": False,
                "alive": True,  # Potentially
                "status": "lost",
            },
            5: {
                "result": DungeonDoomResult.LOST_TRANSFORMED,
                "description": "Transformed into or controlled by a dungeon monster",
                "escaped": False,
                "alive": False,  # Effectively
                "status": "transformed",
            },
            6: {
                "result": DungeonDoomResult.DEAD_BODY_LOOTED,
                "description": "Dead - companions found and looted the body",
                "escaped": False,
                "alive": False,
                "body_recovered": True,
                "equipment_recovered": True,
            },
            7: {
                "result": DungeonDoomResult.DEAD_BODY_KNOWN,
                "description": "Dead - companions know where the body lies",
                "escaped": False,
                "alive": False,
                "body_location_known": True,
            },
            8: {
                "result": DungeonDoomResult.DEAD_BODY_UNKNOWN,
                "description": "Dead - body location unknown to companions",
                "escaped": False,
                "alive": False,
                "body_location_known": False,
            },
            9: {
                "result": DungeonDoomResult.DEAD_DESTROYED,
                "description": "Dead - body and all equipment utterly destroyed",
                "escaped": False,
                "alive": False,
                "body_destroyed": True,
            },
            10: {
                "result": DungeonDoomResult.BETRAYAL,
                "description": "Roll again - may switch fate with a companion",
                "reroll": True,
            },
        }

        result = doom_results[roll.total]
        result["roll"] = roll.total

        # Handle result 10 - roll again
        if result.get("reroll"):
            reroll_result = self._roll_dungeon_doom()
            result["switched_fate"] = reroll_result
            # Keep the BETRAYAL as main result but include what they would face

        return result

    def update_escape_modifiers(
        self,
        has_map: Optional[bool] = None,
        known_exit_path: Optional[bool] = None,
        dungeon_level: Optional[int] = None,
    ) -> None:
        """
        Update escape roll modifiers for the current dungeon.

        Args:
            has_map: Whether party has mapped the dungeon (+2 to escape)
            known_exit_path: Whether party knows safe path to exit (+4 to escape)
            dungeon_level: Current dungeon level (-1 per level to escape)
        """
        if not self._dungeon_state:
            return

        if has_map is not None:
            self._dungeon_state.has_map = has_map
        if known_exit_path is not None:
            self._dungeon_state.known_exit_path = known_exit_path
        if dungeon_level is not None:
            self._dungeon_state.dungeon_level = dungeon_level

    def establish_safe_path(self, room_ids: list[str]) -> dict[str, Any]:
        """
        Establish a safe path to the exit for fast travel and escape bonus.

        Per Dolmenwood rules (p162), a safe path through explored areas
        allows for accelerated travel and provides +4 to escape rolls.

        Args:
            room_ids: List of room IDs forming the safe path to exit

        Returns:
            Result of establishing the path
        """
        if not self._dungeon_state:
            return {"success": False, "error": "No active dungeon"}

        # Verify all rooms are explored
        unexplored = [
            room_id for room_id in room_ids if room_id not in self._dungeon_state.explored_rooms
        ]

        if unexplored:
            return {
                "success": False,
                "error": f"Cannot establish path through unexplored rooms: {unexplored}",
            }

        self._dungeon_state.safe_path_to_exit = room_ids
        self._dungeon_state.known_exit_path = True

        return {
            "success": True,
            "message": f"Safe path established through {len(room_ids)} rooms",
            "path": room_ids,
        }

    # =========================================================================
    # ROOM MANAGEMENT
    # =========================================================================

    def add_room(self, room: DungeonRoom) -> None:
        """Add a room to the dungeon."""
        if self._dungeon_state:
            self._dungeon_state.rooms[room.room_id] = room

    def get_current_room(self) -> Optional[DungeonRoom]:
        """Get the current room."""
        if self._dungeon_state:
            return self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        return None

    def get_room(self, room_id: str) -> Optional[DungeonRoom]:
        """Get a specific room."""
        if self._dungeon_state:
            return self._dungeon_state.rooms.get(room_id)
        return None

    def get_dungeon_state(self) -> Optional[DungeonState]:
        """Get the current dungeon state."""
        return self._dungeon_state

    def get_exploration_summary(self) -> dict[str, Any]:
        """
        Get summary of dungeon exploration per Dolmenwood rules (p162-163).

        Includes all Dolmenwood-specific tracking fields.
        """
        if not self._dungeon_state:
            return {"active": False}

        visited_rooms = [
            room_id for room_id, room in self._dungeon_state.rooms.items() if room.visited
        ]

        # Calculate turns until rest needed (p163)
        turns_until_rest = max(0, self._rest_interval - self._dungeon_state.turns_since_rest)
        needs_rest = self._dungeon_state.turns_since_rest >= self._rest_interval

        return {
            "active": True,
            "dungeon_id": self._dungeon_state.dungeon_id,
            "dungeon_name": self._dungeon_state.name,
            "current_room": self._dungeon_state.current_room,
            "visited_rooms": visited_rooms,
            "total_rooms_known": len(self._dungeon_state.rooms),
            "turns_in_dungeon": self._dungeon_state.turns_in_dungeon,
            "alert_level": self._dungeon_state.alert_level,
            "light_status": self._check_light_status(),
            # Dolmenwood-specific tracking (p162-163)
            "dungeon_level": self._dungeon_state.dungeon_level,
            "turns_since_rest": self._dungeon_state.turns_since_rest,
            "turns_until_rest_required": turns_until_rest,
            "needs_rest": needs_rest,
            "has_map": self._dungeon_state.has_map,
            "known_exit_path": self._dungeon_state.known_exit_path,
            "explored_rooms": list(self._dungeon_state.explored_rooms),
            "safe_path_to_exit": self._dungeon_state.safe_path_to_exit,
        }

    # =========================================================================
    # PLAYER ACTION HANDLING (via NarrativeResolver for hazards)
    # =========================================================================

    def handle_player_action(
        self,
        player_input: str,
        character_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ResolutionResult:
        """
        Handle a player action during dungeon exploration via NarrativeResolver.

        This routes non-standard actions to the NarrativeResolver for resolution:
        - Climbing (walls, pits)
        - Swimming (underwater areas)
        - Jumping (gaps, chasms)
        - Other environmental hazards

        Note: Standard dungeon actions (search, listen, open_door, etc.) use
        the hardcoded implementations via execute_turn() for consistency
        with Dolmenwood rules (p162-163).

        Args:
            player_input: The player's action description
            character_id: ID of the character performing the action
            context: Optional additional context

        Returns:
            ResolutionResult with outcomes and narration context
        """
        from src.narrative.intent_parser import ActionCategory, ActionType, ParsedIntent

        # Get character state
        character = self.controller.get_character(character_id)
        if not character:
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

        # Build context with dungeon-specific information
        action_context = context or {}
        action_context.update(
            {
                "game_state": "dungeon_exploration",
                "current_room": (
                    self._dungeon_state.current_room if self._dungeon_state else "unknown"
                ),
                "dungeon_id": self._dungeon_state.dungeon_id if self._dungeon_state else "unknown",
                "light_level": (
                    self._check_light_status().get("level", "dark")
                    if self._dungeon_state
                    else "dark"
                ),
                "turns_in_dungeon": (
                    self._dungeon_state.turns_in_dungeon if self._dungeon_state else 0
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
        Attempt to climb in dungeon per Dolmenwood rules (p150).

        Args:
            character_id: ID of the climbing character
            height_feet: Height of the climb in feet
            is_trivial: Whether this is a trivial climb (no roll needed)
            difficulty: DC for the climb check

        Returns:
            HazardResult with outcomes
        """
        from src.narrative.intent_parser import ActionType

        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.CLIMBING,
                action_type=ActionType.CLIMB,
                description="Character not found",
            )

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
        Attempt to swim in dungeon per Dolmenwood rules (p154).

        Args:
            character_id: ID of the swimming character
            armor_weight: Weight of armor
            rough_waters: Whether waters are rough/turbulent
            difficulty: DC for the swim check

        Returns:
            HazardResult with outcomes
        """
        from src.narrative.intent_parser import ActionType

        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.SWIMMING,
                action_type=ActionType.SWIM,
                description="Character not found",
            )

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
        Attempt a jump in dungeon per Dolmenwood rules (p153).

        Args:
            character_id: ID of the jumping character
            distance_feet: Distance to jump in feet
            is_high_jump: Whether this is a vertical jump
            has_runup: Whether character has 20' run-up
            armor_weight: Weight of armor

        Returns:
            HazardResult with outcomes
        """
        from src.narrative.intent_parser import ActionType

        character = self.controller.get_character(character_id)
        if not character:
            return HazardResult(
                success=False,
                hazard_type=HazardType.JUMPING,
                action_type=ActionType.JUMP,
                description="Character not found",
            )

        return self.narrative_resolver.hazard_resolver.resolve_hazard(
            hazard_type=HazardType.JUMPING,
            character=character,
            distance_feet=distance_feet,
            is_high_jump=is_high_jump,
            has_runup=has_runup,
            armor_weight=armor_weight,
        )

    def cast_spell(
        self,
        character_id: str,
        spell_name: Optional[str] = None,
        spell_id: Optional[str] = None,
        target_id: Optional[str] = None,
        target_description: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Cast a spell during dungeon exploration.

        Convenience method that wraps _handle_cast_spell.

        Args:
            character_id: ID of the spellcaster
            spell_name: Name of the spell to cast
            spell_id: Alternative: ID of the spell to cast
            target_id: Optional target ID
            target_description: Optional description of target

        Returns:
            Dictionary with spell casting results
        """
        return self._handle_cast_spell(
            {
                "character_id": character_id,
                "spell_name": spell_name,
                "spell_id": spell_id,
                "target_id": target_id,
                "target_description": target_description,
            }
        )

    # =========================================================================
    # DYNAMIC ROOM GENERATION (for POIs like The Spectral Manse)
    # =========================================================================

    def _generate_dynamic_room(self, room_id: str) -> Optional[DungeonRoom]:
        """
        Generate a room dynamically using the POI's room table.

        Used for dungeons with dynamic_layout like The Spectral Manse where
        "Each room connects to 1d3 other rooms, via crooked doors and lurching hallways."

        Args:
            room_id: The room ID to generate

        Returns:
            Generated DungeonRoom or None if generation fails
        """
        if not self._dungeon_state or not self._dungeon_state.room_table:
            return None

        room_table = self._dungeon_state.room_table
        dynamic_layout = self._dungeon_state.dynamic_layout or {}

        # Roll on room table
        die_type = room_table.die_type
        roll = self.dice.roll(f"1{die_type}", "generate room")

        # Find entry
        entry = None
        for e in room_table.entries:
            if e.roll == roll.total:
                entry = e
                break

        if not entry:
            return None

        # Create the room
        room = DungeonRoom(
            room_id=room_id,
            name=entry.title or f"Room {roll.total}",
            description=entry.description,
        )

        # Generate exits based on dynamic layout
        connections_dice = dynamic_layout.get("connections_per_room", "1d3")
        num_exits = self.dice.roll(connections_dice, "room connections").total

        # Create exits to new rooms
        directions = ["north", "south", "east", "west", "up", "down"]
        for i in range(min(num_exits, len(directions))):
            direction = directions[i]
            new_room_id = f"room_{len(self._dungeon_state.rooms) + i + 1}"
            room.exits[direction] = new_room_id
            room.doors[f"{room_id}_{direction}"] = DoorState.CLOSED

        # Add items from the entry
        for item_name in entry.items:
            room.treasure.append({"name": item_name, "found": False})

        # Store the room
        self._dungeon_state.rooms[room_id] = room

        return room

    def generate_room_encounter(self) -> Optional[dict[str, Any]]:
        """
        Generate an encounter for the current room using the POI's encounter table.

        Used for procedural dungeons where encounters are rolled per room.
        Categorizes the encounter type to guide handling:
        - "npc": NPC encounter, may allow social interaction
        - "monster": Combat-capable encounter, transitions to ENCOUNTER state
        - "item": Item discovery, adds to room description
        - "hazard": Environmental hazard requiring save
        - "ambient": Atmospheric description, no mechanical effect

        Returns:
            Dictionary with encounter result including:
            - encounter_type: Category of encounter
            - requires_transition: Whether to transition to ENCOUNTER state
            - allows_social: Whether social interaction is an option
        """
        if not self._dungeon_state or not self._dungeon_state.encounter_table:
            return None

        encounter_table = self._dungeon_state.encounter_table

        # Roll on encounter table
        die_type = encounter_table.die_type
        roll = self.dice.roll(f"1{die_type}", "room encounter")

        # Find entry
        entry = None
        for e in encounter_table.entries:
            if e.roll == roll.total:
                entry = e
                break

        if not entry:
            return {"roll": roll.total, "encounter": None}

        # Categorize the encounter
        encounter_type, requires_transition, allows_social = self._categorize_encounter(entry)

        result = {
            "roll": roll.total,
            "title": entry.title,
            "description": entry.description,
            "monsters": entry.monsters,
            "npcs": entry.npcs,
            "items": entry.items,
            "mechanical_effect": entry.mechanical_effect,
            "encounter_type": encounter_type,
            "requires_transition": requires_transition,
            "allows_social": allows_social,
        }

        # Include quest hook if present
        if entry.quest_hook:
            result["quest_hook"] = entry.quest_hook

        # Check for special effects
        if entry.reaction_conditions:
            result["reaction_conditions"] = entry.reaction_conditions

        if entry.transportation_effect:
            self._dungeon_state.pending_time_effects.append(entry.transportation_effect)
            result["transportation_effect"] = entry.transportation_effect

        if entry.time_effect:
            self._dungeon_state.pending_time_effects.append(entry.time_effect)
            result["time_effect"] = entry.time_effect

        if entry.sub_table:
            result["sub_table"] = entry.sub_table

        return result

    def _categorize_encounter(
        self,
        entry: "RollTableEntry",
    ) -> tuple[str, bool, bool]:
        """
        Categorize a dungeon encounter entry.

        Args:
            entry: The RollTableEntry to categorize

        Returns:
            Tuple of (encounter_type, requires_transition, allows_social)
            - encounter_type: "npc", "monster", "item", "hazard", or "ambient"
            - requires_transition: Whether to transition to ENCOUNTER state
            - allows_social: Whether social interaction is possible
        """
        has_monsters = bool(entry.monsters)
        has_npcs = bool(entry.npcs)
        has_items = bool(entry.items)
        has_mechanical = bool(entry.mechanical_effect)
        has_quest = bool(entry.quest_hook)
        has_transport = bool(entry.transportation_effect)
        has_time_effect = bool(entry.time_effect)

        # NPC encounters: have NPCs listed, possibly with quest
        if has_npcs and not has_monsters:
            return ("npc", True, True)

        # Monster encounters: have monsters listed
        if has_monsters:
            # Check if social option is mentioned in description
            desc_lower = (entry.description or "").lower()
            social_hints = ["if asked", "can be", "may be", "parley", "negotiate", "speak"]
            allows_social = any(hint in desc_lower for hint in social_hints)
            return ("monster", True, allows_social)

        # Hazard encounters: have dangerous mechanical effects, transport, or time effects
        # Check this BEFORE items since some hazards also have items
        if has_transport or has_time_effect:
            return ("hazard", False, False)

        if has_mechanical:
            mech_lower = entry.mechanical_effect.lower()
            hazard_keywords = ["save", "ejected", "transported", "damage", "attack", "must", "pass"]
            if any(keyword in mech_lower for keyword in hazard_keywords):
                return ("hazard", False, False)

        # Item discoveries: have items but no monsters/NPCs/hazards
        if has_items and not has_monsters and not has_npcs:
            return ("item", False, False)

        # Ambient: everything else (atmospheric descriptions)
        return ("ambient", False, False)

    # =========================================================================
    # ITEM PERSISTENCE (for locations like The Spectral Manse)
    # =========================================================================

    def check_item_persistence(
        self,
        item_name: str,
        owner_npc: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Check if an item persists when taken from this dungeon.

        For locations like The Spectral Manse where "items from the manse
        evaporate into mist when taken into the real world" except for
        items belonging to specific NPCs.

        Args:
            item_name: Name of the item
            owner_npc: Optional NPC ID who owns the item

        Returns:
            Dictionary with persistence status
        """
        if not self._dungeon_state or not self._dungeon_state.item_persistence:
            return {"persists": True, "reason": "No persistence rules"}

        persistence = self._dungeon_state.item_persistence
        default = persistence.get("default", "persists")
        exceptions = persistence.get("exceptions", [])

        # Check exceptions
        for exception in exceptions:
            # Check NPC ownership exception
            if owner_npc and exception.get("owner_npc") == owner_npc:
                return {
                    "persists": exception.get("persists", True),
                    "reason": f"Exception: owned by {owner_npc}",
                    "owner_npc": owner_npc,
                }

            # Check item name exception
            if exception.get("item_name") == item_name:
                return {
                    "persists": exception.get("persists", True),
                    "reason": f"Exception: {item_name} is special",
                }

        # Apply default
        if default == "evaporate":
            return {
                "persists": False,
                "reason": "Items from this location evaporate when taken outside",
                "effect": persistence.get("effect_description", "evaporates into mist"),
            }

        return {"persists": True, "reason": "Default persistence"}

    def get_leaving_effects(self) -> dict[str, Any]:
        """
        Get effects that occur when leaving this dungeon.

        Returns:
            Dictionary with leaving effects and description
        """
        if not self._dungeon_state:
            return {}

        result = {}

        if self._dungeon_state.leaving_description:
            result["description"] = self._dungeon_state.leaving_description

        if self._dungeon_state.pending_time_effects:
            result["pending_time_effects"] = self._dungeon_state.pending_time_effects

        if self._dungeon_state.item_persistence:
            result["item_persistence"] = self._dungeon_state.item_persistence

        return result

    def roll_on_table(self, table_name: str) -> Optional[dict[str, Any]]:
        """
        Roll on a roll table inherited from the POI.

        Args:
            table_name: Name of the table to roll on

        Returns:
            Dictionary with roll result or None if table not found
        """
        if not self._dungeon_state or not self._dungeon_state.roll_tables:
            return None

        # Find the table
        target_table = None
        for table in self._dungeon_state.roll_tables:
            if table.name.lower() == table_name.lower():
                target_table = table
                break

        if not target_table:
            return None

        # Roll on the table
        die_type = target_table.die_type
        roll = self.dice.roll(f"1{die_type}", f"roll on {table_name}")

        # Find the entry
        entry = None
        for e in target_table.entries:
            if e.roll == roll.total:
                entry = e
                break

        if not entry:
            return {"roll": roll.total, "table": table_name, "entry": None}

        return {
            "roll": roll.total,
            "table": table_name,
            "title": entry.title,
            "description": entry.description,
            "monsters": entry.monsters,
            "npcs": entry.npcs,
            "items": entry.items,
            "mechanical_effect": entry.mechanical_effect,
            "sub_table": entry.sub_table,
            "quest_hook": entry.quest_hook,
        }

    def get_available_tables(self) -> list[str]:
        """Get names of available roll tables for this dungeon."""
        if not self._dungeon_state or not self._dungeon_state.roll_tables:
            return []
        return [table.name for table in self._dungeon_state.roll_tables]

    def get_encounter_context(self) -> dict[str, Any]:
        """
        Get context data for passing to EncounterEngine when starting an encounter.

        This method provides all the information needed to start an encounter
        with full POI context, including roll tables, location info, and
        pending effects.

        Returns:
            Dictionary with:
            - roll_tables: List of RollTable objects from the POI
            - poi_name: Name of the POI (dungeon)
            - hex_id: Hex where the dungeon is located
            - pending_time_effects: Any time effects that should carry over

        Example usage:
            context = dungeon_engine.get_encounter_context()
            encounter_engine.start_encounter(
                encounter=encounter,
                origin=EncounterOrigin.DUNGEON,
                roll_tables=context["roll_tables"],
                poi_name=context["poi_name"],
                hex_id=context["hex_id"],
            )
        """
        if not self._dungeon_state:
            return {
                "roll_tables": [],
                "poi_name": None,
                "hex_id": None,
                "pending_time_effects": [],
            }

        return {
            "roll_tables": self._dungeon_state.roll_tables,
            "poi_name": self._dungeon_state.poi_name,
            "hex_id": self._dungeon_state.hex_id,
            "pending_time_effects": list(self._dungeon_state.pending_time_effects),
        }
