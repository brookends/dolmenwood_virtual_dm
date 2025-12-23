"""
Dungeon Engine for Dolmenwood Virtual DM.

Implements the Dungeon Exploration Loop from Section 5.3 of the specification.
Handles 10-minute turn tracking, light depletion, wandering monsters, and room exploration.

The dungeon exploration loop per 10-minute turn:
1. Advance time
2. Deplete light sources
3. Resolve declared player action
4. Check wandering monsters
5. If encounter -> Transition to DUNGEON_ENCOUNTER
6. Apply noise & consequence flags
7. Update dungeon state
8. Request LLM description (room details only)
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
    LocationState,
    LocationType,
    LightSourceType,
    Feature,
    Hazard,
)


logger = logging.getLogger(__name__)


class DungeonActionType(str, Enum):
    """Types of actions that take a dungeon turn."""
    MOVE = "move"  # Move to adjacent room/corridor
    SEARCH = "search"  # Search 10x10 area
    LISTEN = "listen"  # Listen at door
    OPEN_DOOR = "open_door"  # Open/force door
    PICK_LOCK = "pick_lock"  # Pick a lock
    DISARM_TRAP = "disarm_trap"  # Disarm detected trap
    REST = "rest"  # Short rest (1 turn)
    INTERACT = "interact"  # Interact with feature
    CAST_SPELL = "cast_spell"  # Cast a spell
    MAP = "map"  # Map the current area


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
    """Overall state of the dungeon."""
    dungeon_id: str
    name: str = ""
    current_room: str = ""
    rooms: dict[str, DungeonRoom] = field(default_factory=dict)
    alert_level: int = 0  # 0-5, affects wandering monster frequency
    turns_in_dungeon: int = 0
    noise_accumulator: int = 0
    monsters_alerted: set[str] = field(default_factory=set)


class DungeonEngine:
    """
    Engine for dungeon exploration.

    Manages:
    - 10-minute exploration turns
    - Light source tracking and depletion
    - Wandering monster checks
    - Room state and discovery
    - Noise consequences
    """

    def __init__(self, controller: GlobalController):
        """
        Initialize the dungeon engine.

        Args:
            controller: The global game controller
        """
        self.controller = controller
        self.dice = DiceRoller()

        # Current dungeon state
        self._dungeon_state: Optional[DungeonState] = None

        # Wandering monster check frequency
        self._wandering_check_interval: int = 2  # Every 2 turns
        self._turns_since_check: int = 0

        # Noise thresholds
        self._noise_alert_threshold: int = 10

        # Callbacks
        self._description_callback: Optional[Callable] = None

    def enter_dungeon(
        self,
        dungeon_id: str,
        entry_room: str,
        dungeon_data: Optional[DungeonState] = None
    ) -> dict[str, Any]:
        """
        Enter a dungeon and begin exploration.

        Args:
            dungeon_id: Unique identifier for the dungeon
            entry_room: Starting room ID
            dungeon_data: Pre-loaded dungeon data (optional)

        Returns:
            Dictionary with entry results
        """
        # Validate state
        if self.controller.current_state not in {
            GameState.WILDERNESS_TRAVEL,
            GameState.SETTLEMENT_EXPLORATION
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

        # Add entry room if not exists
        if entry_room not in self._dungeon_state.rooms:
            self._dungeon_state.rooms[entry_room] = DungeonRoom(room_id=entry_room)

        # Transition to dungeon exploration
        self.controller.transition("enter_dungeon", context={
            "dungeon_id": dungeon_id,
            "entry_room": entry_room,
        })

        # Update party location
        self.controller.set_party_location(
            LocationType.DUNGEON_ROOM,
            entry_room,
            sub_location=dungeon_id
        )

        # Check if party has light
        light_status = self._check_light_status()

        return {
            "dungeon_id": dungeon_id,
            "entry_room": entry_room,
            "light_status": light_status,
            "state": GameState.DUNGEON_EXPLORATION.value,
        }

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
        self.controller.transition("exit_dungeon", context={
            "dungeon_id": dungeon_id,
            "turns_spent": self._dungeon_state.turns_in_dungeon if self._dungeon_state else 0,
        })

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
        self,
        action: DungeonActionType,
        action_params: Optional[dict[str, Any]] = None
    ) -> DungeonTurnResult:
        """
        Execute one dungeon exploration turn.

        Implements the Dungeon Exploration Loop from Section 5.3.

        Args:
            action: The action to perform this turn
            action_params: Parameters for the action

        Returns:
            DungeonTurnResult with all outcomes
        """
        # Validate state
        if self.controller.current_state != GameState.DUNGEON_EXPLORATION:
            return DungeonTurnResult(
                success=False,
                action_type=action,
                warnings=["Not in DUNGEON_EXPLORATION state"]
            )

        if not self._dungeon_state:
            return DungeonTurnResult(
                success=False,
                action_type=action,
                warnings=["No active dungeon"]
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

        # Track noise from action
        result.noise_generated = action_result.get("noise", 0)
        self._dungeon_state.noise_accumulator += result.noise_generated

        # 4. Check wandering monsters
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
        if self._description_callback and action in {DungeonActionType.MOVE, DungeonActionType.SEARCH}:
            self._description_callback(
                room_id=self._dungeon_state.current_room,
                action=action.value,
                light_level=self._get_current_light_level().value,
            )

        return result

    def _resolve_action(
        self,
        action: DungeonActionType,
        params: dict[str, Any]
    ) -> dict[str, Any]:
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
            LocationType.DUNGEON_ROOM,
            exit_target,
            sub_location=self._dungeon_state.dungeon_id
        )

        return {
            "success": True,
            "message": f"Moved to {exit_target}",
            "new_room": exit_target,
            "noise": 1,  # Normal movement noise
        }

    def _handle_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle searching the current area."""
        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        results = {
            "success": True,
            "found_features": [],
            "found_traps": [],
            "found_secret_doors": [],
            "noise": 1,
        }

        # Check for hidden features
        for feature in current_room.features:
            if feature.hidden and not feature.discovered:
                roll = self.dice.roll_d6(1, f"search: {feature.feature_id}")
                if roll.total <= 2:  # 2-in-6 chance
                    feature.discovered = True
                    results["found_features"].append(feature.name)

        # Check for traps
        for hazard in current_room.hazards:
            if not hazard.detected:
                roll = self.dice.roll_d6(1, f"detect trap: {hazard.hazard_id}")
                if roll.total <= 2:  # 2-in-6 chance
                    hazard.detected = True
                    results["found_traps"].append(hazard.name)

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
        """Handle disarming a detected trap."""
        trap_id = params.get("trap_id")
        character_id = params.get("character_id")

        current_room = self._dungeon_state.rooms.get(self._dungeon_state.current_room)
        if not current_room:
            return {"success": False, "message": "Current room unknown"}

        # Find the trap
        trap = None
        for hazard in current_room.hazards:
            if hazard.hazard_id == trap_id:
                trap = hazard
                break

        if not trap:
            return {"success": False, "message": "Trap not found", "noise": 0}

        if not trap.detected:
            return {"success": False, "message": "Must detect trap first", "noise": 0}

        if trap.disarmed:
            return {"success": True, "message": "Trap already disarmed", "noise": 0}

        # Thief ability check
        roll = self.dice.roll_percentile("disarm trap")
        threshold = 20  # Placeholder

        if roll.total <= threshold:
            trap.disarmed = True
            return {
                "success": True,
                "message": "Trap disarmed!",
                "noise": 1,
            }

        # Check for triggering trap on failure
        trigger_roll = self.dice.roll_d6(1, "trap trigger")
        if trigger_roll.total == 1:
            return {
                "success": False,
                "message": "Trap triggered!",
                "trap_triggered": True,
                "trap_effect": trap.effect,
                "noise": 3,
            }

        return {
            "success": False,
            "message": "Failed to disarm trap",
            "noise": 1,
        }

    def _handle_rest(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle short rest (1 turn)."""
        return {
            "success": True,
            "message": "Rested for one turn",
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
        """Handle casting a spell."""
        spell_name = params.get("spell_name")
        character_id = params.get("character_id")

        # Spell casting would be handled by character/magic system
        return {
            "success": True,
            "message": f"Cast {spell_name}",
            "noise": 2,  # Most spells make some noise
        }

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
        Check for wandering monster encounter.

        Base 1-in-6 chance, modified by:
        - Alert level (+1 per level)
        - Recent noise

        Returns:
            EncounterState if encounter triggered, None otherwise
        """
        threshold = 1 + self._dungeon_state.alert_level

        roll = self.dice.roll_d6(1, "wandering monster")

        if roll.total <= threshold:
            # Generate encounter
            encounter = EncounterState(
                encounter_type=EncounterType.MONSTER,
                distance=self._roll_dungeon_distance(),
                surprise_status=self._check_dungeon_surprise(),
                context="wandering",
            )

            self.controller.set_encounter(encounter)
            self.controller.transition("wandering_monster", context={
                "dungeon_id": self._dungeon_state.dungeon_id,
                "room_id": self._dungeon_state.current_room,
            })

            return encounter

        return None

    def _roll_dungeon_distance(self) -> int:
        """Roll encounter distance in dungeon (typically close)."""
        roll = self.dice.roll("2d6", "dungeon distance")
        return roll.total * 10  # 20-120 feet

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
            return ReactionResult.NEUTRAL

        roll = self.dice.roll_2d6("dungeon reaction")

        # Dungeon monsters often more hostile
        modifier = -1 if self._dungeon_state.alert_level > 2 else 0
        total = roll.total + modifier

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

    def handle_dungeon_encounter_outcome(self, reaction: ReactionResult) -> str:
        """
        Handle encounter outcome and return trigger for state transition.

        Args:
            reaction: Reaction roll result

        Returns:
            Trigger name for state transition
        """
        if reaction == ReactionResult.HOSTILE:
            return "reaction_hostile"
        elif reaction in {ReactionResult.FRIENDLY, ReactionResult.HELPFUL}:
            return "reaction_parley"
        elif reaction == ReactionResult.UNFRIENDLY:
            # More likely to attack in dungeon
            roll = self.dice.roll_d6(1, "unfriendly action")
            if roll.total <= 3:
                return "reaction_hostile"
            return "encounter_avoided"
        else:
            return "encounter_avoided"

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
        """Get summary of dungeon exploration."""
        if not self._dungeon_state:
            return {"active": False}

        visited_rooms = [
            room_id for room_id, room in self._dungeon_state.rooms.items()
            if room.visited
        ]

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
        }
