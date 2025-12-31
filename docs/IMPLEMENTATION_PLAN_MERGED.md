# Dolmenwood Virtual DM — Conversation-First Refactor Plan (Merged)

**Generated:** 2025-12-31
**Approach:** MVP-first with detailed specifications for upgrade phases

This plan merges the pragmatic MVP approach of the Starter Patch with comprehensive specifications from the detailed implementation plan.

---

## Executive Summary

Transform the command-driven CLI into a **conversation-first interface** with system-generated suggested actions. The refactor leverages significant existing infrastructure that's already wired:

**Already implemented (use directly):**
- `HexCrawlEngine.handle_player_action()` → routes to NarrativeResolver
- `DungeonEngine.handle_player_action()` → routes to NarrativeResolver
- `NarrativeResolver.set_narration_callback()` → already wired in VirtualDM
- `RunLog.subscribe()` → event streaming ready
- All engine callback registrations (`register_description_callback`, etc.)

**To build:**
- Thin `src/conversation/` orchestration layer (~5 files)
- Modifications to existing `DolmenwoodCLI` (~50 lines)
- Engine context accessors (as needed for suggestions)

---

## Phase 0: MVP (Get It Running)

### Goal
User can type natural language OR select numbered suggestions. System executes procedures and returns narration.

### New Package: `src/conversation/`

#### `src/conversation/__init__.py`
```python
"""Conversation-first interface for Dolmenwood Virtual DM."""
from .types import ChatMessage, SuggestedAction, TurnResponse
from .conversation_facade import ConversationFacade
from .suggestion_builder import build_suggestions
from .state_export import export_public_state, EventStream
```

#### `src/conversation/types.py`
```python
"""Wire-level types for conversation interface."""
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class MessageRole(str, Enum):
    """Role of a chat message."""
    SYSTEM = "system"
    DM = "dm"
    PLAYER = "player"
    MECHANICAL = "mechanical"


@dataclass
class ChatMessage:
    """A single message in the conversation."""
    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuggestedAction:
    """
    A suggested action the player can execute.

    Designed for both CLI (numbered list) and future Foundry (clickable buttons).
    """
    id: str                          # Stable action ID, e.g., "dungeon:search"
    label: str                       # Display text, e.g., "Search the room"
    params: dict[str, Any] = field(default_factory=dict)  # Pre-filled parameters
    params_schema: Optional[dict] = None  # JSON schema for params (Foundry use)
    category: str = "general"        # For grouping in UI
    enabled: bool = True
    disabled_reason: Optional[str] = None

    # For keyboard shortcuts in CLI
    shortcut: Optional[str] = None


@dataclass
class TurnResponse:
    """
    Complete response to a player turn.

    Contains everything the UI needs to render and offer next actions.
    """
    messages: list[ChatMessage] = field(default_factory=list)
    suggested_actions: list[SuggestedAction] = field(default_factory=list)

    # Optional state/events for Foundry compatibility
    state_snapshot: Optional[dict] = None
    events: list[dict] = field(default_factory=list)

    # For error handling
    success: bool = True
    error: Optional[str] = None
```

#### `src/conversation/suggestion_builder.py`
```python
"""Builds context-aware suggested actions based on current game state."""
from typing import TYPE_CHECKING
from src.game_state.state_machine import GameState

if TYPE_CHECKING:
    from src.main import VirtualDM

from .types import SuggestedAction


def build_suggestions(dm: "VirtualDM", character_id: str = None) -> list[SuggestedAction]:
    """
    Build suggested actions for current game state.

    Uses existing engine state methods where available.
    Returns up to 12 suggestions, prioritized by relevance.
    """
    state = dm.current_state
    suggestions = []

    if state == GameState.WILDERNESS_TRAVEL:
        suggestions = _build_wilderness_suggestions(dm)
    elif state == GameState.DUNGEON_EXPLORATION:
        suggestions = _build_dungeon_suggestions(dm)
    elif state == GameState.ENCOUNTER:
        suggestions = _build_encounter_suggestions(dm)
    elif state == GameState.COMBAT:
        suggestions = _build_combat_suggestions(dm, character_id)
    elif state == GameState.SETTLEMENT_EXPLORATION:
        suggestions = _build_settlement_suggestions(dm)
    elif state == GameState.SOCIAL_INTERACTION:
        suggestions = _build_social_suggestions(dm)
    elif state == GameState.DOWNTIME:
        suggestions = _build_downtime_suggestions(dm)

    # Always offer Mythic oracle as last option
    suggestions.append(SuggestedAction(
        id="oracle:fate_check",
        label="Ask the Oracle (Yes/No)",
        category="oracle",
    ))

    # Add valid state transitions as suggestions
    suggestions.extend(_build_transition_suggestions(dm))

    return suggestions[:12]  # Cap at 12


def _build_wilderness_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build wilderness travel suggestions."""
    suggestions = []

    # Get current hex info
    party_state = dm.controller.party_state
    current_hex = party_state.current_hex if party_state else None

    # Adjacent hex travel options
    if current_hex:
        try:
            hex_data = dm.hex_crawl.get_hex_data(current_hex)
            if hex_data and hasattr(hex_data, 'adjacent_hexes'):
                for adj_hex in hex_data.adjacent_hexes[:4]:  # Limit to 4 directions
                    suggestions.append(SuggestedAction(
                        id="wilderness:travel",
                        label=f"Travel to hex {adj_hex}",
                        params={"hex_id": adj_hex},
                        category="movement",
                    ))
        except Exception:
            pass  # Graceful degradation if method not available

    # Standard wilderness actions
    suggestions.append(SuggestedAction(
        id="wilderness:search_hex",
        label="Search this hex",
        category="exploration",
    ))

    suggestions.append(SuggestedAction(
        id="wilderness:make_camp",
        label="Make camp",
        category="survival",
    ))

    suggestions.append(SuggestedAction(
        id="wilderness:end_day",
        label="End travel day",
        category="time",
    ))

    return suggestions


def _build_dungeon_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build dungeon exploration suggestions."""
    from src.dungeon.dungeon_engine import DungeonActionType

    suggestions = []
    dungeon_state = None

    # Try to get current dungeon state
    try:
        dungeon_state = dm.dungeon.state
    except Exception:
        pass

    # Room exits as movement options
    if dungeon_state and dungeon_state.current_room:
        try:
            room = dungeon_state.rooms.get(dungeon_state.current_room)
            if room and room.exits:
                for direction, dest in list(room.exits.items())[:4]:
                    suggestions.append(SuggestedAction(
                        id="dungeon:move",
                        label=f"Go {direction}",
                        params={"direction": direction, "destination": dest},
                        category="movement",
                    ))

            # Door interactions
            if room and room.doors:
                for door_id, door_state in room.doors.items():
                    suggestions.append(SuggestedAction(
                        id="dungeon:listen",
                        label=f"Listen at {door_id}",
                        params={"door_id": door_id},
                        category="exploration",
                    ))
        except Exception:
            pass

    # Standard dungeon turn actions
    suggestions.append(SuggestedAction(
        id="dungeon:search",
        label="Search the area",
        category="exploration",
    ))

    suggestions.append(SuggestedAction(
        id="dungeon:listen",
        label="Listen carefully",
        category="exploration",
    ))

    suggestions.append(SuggestedAction(
        id="dungeon:map",
        label="Map this area",
        category="exploration",
    ))

    # Rest suggestion (with urgency indicator if needed)
    rest_label = "Rest for a turn"
    if dungeon_state and dungeon_state.turns_since_rest >= 5:
        rest_label = "Rest for a turn (REQUIRED)"

    suggestions.append(SuggestedAction(
        id="dungeon:rest",
        label=rest_label,
        category="survival",
    ))

    return suggestions


def _build_encounter_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build encounter phase suggestions."""
    from src.encounter.encounter_engine import EncounterAction

    suggestions = []

    # Core encounter actions
    suggestions.append(SuggestedAction(
        id="encounter:parley",
        label="Attempt to parley",
        category="social",
    ))

    suggestions.append(SuggestedAction(
        id="encounter:evade",
        label="Attempt to evade",
        category="movement",
    ))

    suggestions.append(SuggestedAction(
        id="encounter:attack",
        label="Attack!",
        category="combat",
    ))

    suggestions.append(SuggestedAction(
        id="encounter:wait",
        label="Wait and observe",
        category="tactical",
    ))

    return suggestions


def _build_combat_suggestions(dm: "VirtualDM", character_id: str = None) -> list[SuggestedAction]:
    """Build combat round suggestions."""
    suggestions = []

    # Basic combat actions
    suggestions.append(SuggestedAction(
        id="combat:attack",
        label="Attack",
        params={"character_id": character_id} if character_id else {},
        category="offense",
    ))

    suggestions.append(SuggestedAction(
        id="combat:defend",
        label="Defend",
        category="defense",
    ))

    suggestions.append(SuggestedAction(
        id="combat:flee",
        label="Attempt to flee",
        category="movement",
    ))

    suggestions.append(SuggestedAction(
        id="combat:parley",
        label="Attempt to parley",
        category="social",
    ))

    # TODO: Add spell casting, item use based on character inventory

    return suggestions


def _build_settlement_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build settlement exploration suggestions."""
    suggestions = []

    suggestions.append(SuggestedAction(
        id="settlement:explore",
        label="Explore the settlement",
        category="exploration",
    ))

    suggestions.append(SuggestedAction(
        id="settlement:find_inn",
        label="Find an inn",
        category="survival",
    ))

    suggestions.append(SuggestedAction(
        id="settlement:find_shop",
        label="Find a shop",
        category="commerce",
    ))

    suggestions.append(SuggestedAction(
        id="settlement:gather_rumors",
        label="Gather rumors",
        category="social",
    ))

    return suggestions


def _build_social_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build social interaction suggestions."""
    suggestions = []

    suggestions.append(SuggestedAction(
        id="social:continue",
        label="Continue conversation",
        category="social",
    ))

    suggestions.append(SuggestedAction(
        id="social:persuade",
        label="Attempt to persuade",
        category="social",
    ))

    suggestions.append(SuggestedAction(
        id="social:intimidate",
        label="Attempt to intimidate",
        category="social",
    ))

    suggestions.append(SuggestedAction(
        id="social:end",
        label="End conversation",
        category="social",
    ))

    return suggestions


def _build_downtime_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build downtime activity suggestions."""
    suggestions = []

    suggestions.append(SuggestedAction(
        id="downtime:rest",
        label="Rest and recover",
        category="survival",
    ))

    suggestions.append(SuggestedAction(
        id="downtime:forage",
        label="Forage for food",
        category="survival",
    ))

    suggestions.append(SuggestedAction(
        id="downtime:hunt",
        label="Hunt for game",
        category="survival",
    ))

    suggestions.append(SuggestedAction(
        id="downtime:end",
        label="Break camp and resume",
        category="time",
    ))

    return suggestions


def _build_transition_suggestions(dm: "VirtualDM") -> list[SuggestedAction]:
    """Build suggestions from valid state machine transitions."""
    suggestions = []

    try:
        valid_triggers = dm.state_machine.get_valid_triggers()
        for trigger in valid_triggers[:3]:  # Limit to 3 transition options
            # Make trigger human-readable
            label = trigger.replace("_", " ").title()
            suggestions.append(SuggestedAction(
                id=f"transition:{trigger}",
                label=label,
                category="transition",
            ))
    except Exception:
        pass

    return suggestions
```

#### `src/conversation/state_export.py`
```python
"""State export and event streaming for UI/Foundry compatibility."""
from typing import TYPE_CHECKING, Any, Callable, Optional
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from src.main import VirtualDM

from src.observability.run_log import get_run_log, LogEvent


SCHEMA_VERSION = "0.1.0"


def export_public_state(dm: "VirtualDM") -> dict[str, Any]:
    """
    Export player-visible state (no secrets).

    Versioned schema for Foundry compatibility.
    """
    controller = dm.controller

    state = {
        "schema_version": SCHEMA_VERSION,
        "game_state": controller.current_state.value,
        "time": controller.time_tracker.get_time_summary(),
    }

    # Party state (safe to expose)
    if controller.party_state:
        state["party"] = {
            "current_hex": controller.party_state.current_hex,
            "location_type": controller.party_state.location_type.value if controller.party_state.location_type else None,
        }

    # Add resources if available
    try:
        resources = dm.get_resources()
        if resources:
            state["resources"] = resources
    except Exception:
        pass

    # Current encounter summary (no hidden info)
    if controller.current_encounter:
        enc = controller.current_encounter
        state["encounter"] = {
            "encounter_type": enc.encounter_type.value if enc.encounter_type else None,
            "creature_count": enc.number_appearing if hasattr(enc, 'number_appearing') else None,
        }

    return state


def export_gm_state(dm: "VirtualDM") -> dict[str, Any]:
    """
    Export full state including secrets (for debugging/dev).
    """
    public = export_public_state(dm)
    public["_debug"] = True

    # Add full state from controller
    try:
        public["_full_state"] = dm.get_full_state()
    except Exception:
        pass

    return public


class EventStream:
    """
    Wrapper for RunLog subscriptions.

    Buffers events and provides drain() for UI consumption.
    """

    def __init__(self):
        self._buffer: list[dict[str, Any]] = []
        self._subscribed = False

    def start(self) -> None:
        """Start capturing events from RunLog."""
        if self._subscribed:
            return
        run_log = get_run_log()
        run_log.subscribe(self._on_event)
        self._subscribed = True

    def stop(self) -> None:
        """Stop capturing events."""
        if not self._subscribed:
            return
        run_log = get_run_log()
        run_log.unsubscribe(self._on_event)
        self._subscribed = False

    def _on_event(self, event: LogEvent) -> None:
        """Callback for RunLog events."""
        self._buffer.append(event.to_dict())

    def drain(self) -> list[dict[str, Any]]:
        """
        Get all buffered events and clear buffer.

        Returns:
            List of event dictionaries since last drain
        """
        events = self._buffer
        self._buffer = []
        return events

    def peek(self) -> list[dict[str, Any]]:
        """Get buffered events without clearing."""
        return list(self._buffer)
```

#### `src/conversation/conversation_facade.py`
```python
"""
Conversation Facade - Main orchestration layer for chat-first interface.

Routes player input to appropriate engine procedures or freeform resolution.
"""
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.main import VirtualDM

from src.game_state.state_machine import GameState

from .types import ChatMessage, MessageRole, SuggestedAction, TurnResponse
from .suggestion_builder import build_suggestions
from .state_export import export_public_state, EventStream


class ConversationFacade:
    """
    Single orchestration surface for conversation-first UI.

    Handles:
    - Natural language input -> action resolution
    - Direct action execution (button clicks / numbered selection)
    - State export for UI rendering
    - Suggestion generation

    Uses existing engine infrastructure:
    - handle_player_action() for freeform resolution
    - execute_turn() / execute_action() for procedural actions
    """

    def __init__(self, dm: "VirtualDM"):
        self.dm = dm
        self.event_stream = EventStream()
        self.event_stream.start()

        # Compile patterns for routing
        self._hex_pattern = re.compile(r'\b(\d{4})\b')  # 4-digit hex IDs
        self._dungeon_actions = {
            'search': 'dungeon:search',
            'listen': 'dungeon:listen',
            'map': 'dungeon:map',
            'rest': 'dungeon:rest',
        }

    def handle_chat(self, text: str, character_id: str = None) -> TurnResponse:
        """
        Process natural language input from player.

        Routing logic:
        1. Check for procedural action patterns (hex travel, dungeon turns)
        2. If no pattern matches, delegate to engine's handle_player_action()
        3. Generate narration via existing callbacks
        4. Build suggestions for next turn
        """
        text_lower = text.lower().strip()
        state = self.dm.current_state

        messages = []
        result = None

        try:
            # Route based on current state and input patterns
            if state == GameState.WILDERNESS_TRAVEL:
                result = self._handle_wilderness_input(text, text_lower)
            elif state == GameState.DUNGEON_EXPLORATION:
                result = self._handle_dungeon_input(text, text_lower, character_id)
            elif state == GameState.ENCOUNTER:
                result = self._handle_encounter_input(text, text_lower)
            elif state == GameState.COMBAT:
                result = self._handle_combat_input(text, text_lower, character_id)
            else:
                # Default: freeform resolution via NarrativeResolver
                result = self._handle_freeform(text, character_id)

            # Build response messages from result
            if result:
                messages = self._build_messages_from_result(result)

        except Exception as e:
            messages = [ChatMessage(
                role=MessageRole.SYSTEM,
                content=f"Error processing input: {str(e)}",
            )]

        return TurnResponse(
            messages=messages,
            suggested_actions=build_suggestions(self.dm, character_id),
            state_snapshot=export_public_state(self.dm),
            events=self.event_stream.drain(),
        )

    def handle_action(self, action_id: str, params: dict = None) -> TurnResponse:
        """
        Execute a specific action by ID (from suggestion click).

        Action ID format: "category:action" (e.g., "dungeon:search")
        """
        params = params or {}
        messages = []

        try:
            # Parse action ID
            if ':' in action_id:
                category, action = action_id.split(':', 1)
            else:
                category, action = 'general', action_id

            result = None

            # Route to appropriate handler
            if category == 'wilderness':
                result = self._execute_wilderness_action(action, params)
            elif category == 'dungeon':
                result = self._execute_dungeon_action(action, params)
            elif category == 'encounter':
                result = self._execute_encounter_action(action, params)
            elif category == 'combat':
                result = self._execute_combat_action(action, params)
            elif category == 'settlement':
                result = self._execute_settlement_action(action, params)
            elif category == 'social':
                result = self._execute_social_action(action, params)
            elif category == 'downtime':
                result = self._execute_downtime_action(action, params)
            elif category == 'oracle':
                result = self._execute_oracle_action(action, params)
            elif category == 'transition':
                result = self._execute_transition(action, params)
            else:
                messages = [ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=f"Unknown action category: {category}",
                )]

            if result:
                messages = self._build_messages_from_result(result)

        except Exception as e:
            messages = [ChatMessage(
                role=MessageRole.SYSTEM,
                content=f"Error executing action: {str(e)}",
            )]

        return TurnResponse(
            messages=messages,
            suggested_actions=build_suggestions(self.dm, params.get('character_id')),
            state_snapshot=export_public_state(self.dm),
            events=self.event_stream.drain(),
        )

    # =========================================================================
    # Input Routing (Natural Language -> Procedures)
    # =========================================================================

    def _handle_wilderness_input(self, text: str, text_lower: str) -> dict:
        """Route wilderness travel input."""
        # Check for hex ID in input
        hex_match = self._hex_pattern.search(text)
        if hex_match:
            hex_id = hex_match.group(1)
            return self.dm.travel_to_hex(hex_id)

        # Check for camp/rest
        if any(word in text_lower for word in ['camp', 'rest', 'sleep']):
            return self.dm.rest('short')

        # Check for search
        if 'search' in text_lower:
            return self.dm.hex_crawl.search_hex(
                self.dm.controller.party_state.current_hex
            )

        # Freeform resolution
        return self._handle_freeform(text, None)

    def _handle_dungeon_input(self, text: str, text_lower: str, character_id: str) -> dict:
        """Route dungeon exploration input."""
        from src.dungeon.dungeon_engine import DungeonActionType

        # Check for standard dungeon actions
        for keyword, action_id in self._dungeon_actions.items():
            if keyword in text_lower:
                return self._execute_dungeon_action(
                    action_id.split(':')[1],
                    {'character_id': character_id}
                )

        # Check for movement
        directions = ['north', 'south', 'east', 'west', 'up', 'down']
        for direction in directions:
            if direction in text_lower:
                return self.dm.dungeon.execute_turn(
                    DungeonActionType.MOVE,
                    direction=direction
                )

        # Freeform resolution via existing handle_player_action
        return self.dm.dungeon.handle_player_action(text, character_id)

    def _handle_encounter_input(self, text: str, text_lower: str) -> dict:
        """Route encounter input."""
        from src.encounter.encounter_engine import EncounterAction

        if any(word in text_lower for word in ['attack', 'fight', 'charge']):
            return self.dm.encounter.execute_action(EncounterAction.ATTACK)
        if any(word in text_lower for word in ['parley', 'talk', 'negotiate']):
            return self.dm.encounter.execute_action(EncounterAction.PARLEY)
        if any(word in text_lower for word in ['evade', 'flee', 'run', 'escape']):
            return self.dm.encounter.execute_action(EncounterAction.EVADE)
        if any(word in text_lower for word in ['wait', 'observe', 'watch']):
            return self.dm.encounter.execute_action(EncounterAction.WAIT)

        # Freeform
        return self._handle_freeform(text, None)

    def _handle_combat_input(self, text: str, text_lower: str, character_id: str) -> dict:
        """Route combat input."""
        if any(word in text_lower for word in ['attack', 'hit', 'strike']):
            return self._execute_combat_action('attack', {'character_id': character_id})
        if any(word in text_lower for word in ['flee', 'run', 'escape']):
            return self._execute_combat_action('flee', {'character_id': character_id})
        if any(word in text_lower for word in ['defend', 'block', 'parry']):
            return self._execute_combat_action('defend', {'character_id': character_id})

        # Freeform for creative combat actions
        return self._handle_freeform(text, character_id)

    def _handle_freeform(self, text: str, character_id: str) -> dict:
        """
        Handle freeform input via existing NarrativeResolver pipeline.

        Uses engine's handle_player_action() which already routes to
        NarrativeResolver -> HazardResolver/CreativeSolutionResolver/etc.
        """
        state = self.dm.current_state

        # Route to appropriate engine's handle_player_action
        if state == GameState.WILDERNESS_TRAVEL:
            return self.dm.hex_crawl.handle_player_action(text, character_id)
        elif state == GameState.DUNGEON_EXPLORATION:
            return self.dm.dungeon.handle_player_action(text, character_id)
        else:
            # Generic freeform - try NarrativeResolver directly
            resolver = self.dm.controller.get_narrative_resolver()
            if resolver:
                result = resolver.resolve(text, character_id)
                return {
                    'success': result.success if result else False,
                    'narration': result.narration if result else None,
                    'result': result,
                }
            return {'success': False, 'error': 'No resolver available'}

    # =========================================================================
    # Action Execution (Suggestion Click -> Procedures)
    # =========================================================================

    def _execute_wilderness_action(self, action: str, params: dict) -> dict:
        """Execute wilderness actions."""
        if action == 'travel':
            return self.dm.travel_to_hex(params.get('hex_id'))
        elif action == 'search_hex':
            return self.dm.hex_crawl.search_hex(
                self.dm.controller.party_state.current_hex
            )
        elif action == 'make_camp':
            return self.dm.rest('short')
        elif action == 'end_day':
            return self.dm.hex_crawl.end_travel_day()
        return {'error': f'Unknown wilderness action: {action}'}

    def _execute_dungeon_action(self, action: str, params: dict) -> dict:
        """Execute dungeon turn actions."""
        from src.dungeon.dungeon_engine import DungeonActionType

        action_map = {
            'move': DungeonActionType.MOVE,
            'search': DungeonActionType.SEARCH,
            'listen': DungeonActionType.LISTEN,
            'map': DungeonActionType.MAP,
            'rest': DungeonActionType.REST,
            'open_door': DungeonActionType.OPEN_DOOR,
        }

        action_type = action_map.get(action)
        if action_type:
            return self.dm.dungeon.execute_turn(action_type, **params)
        return {'error': f'Unknown dungeon action: {action}'}

    def _execute_encounter_action(self, action: str, params: dict) -> dict:
        """Execute encounter actions."""
        from src.encounter.encounter_engine import EncounterAction

        action_map = {
            'attack': EncounterAction.ATTACK,
            'parley': EncounterAction.PARLEY,
            'evade': EncounterAction.EVADE,
            'wait': EncounterAction.WAIT,
        }

        enc_action = action_map.get(action)
        if enc_action:
            return self.dm.encounter.execute_action(enc_action, **params)
        return {'error': f'Unknown encounter action: {action}'}

    def _execute_combat_action(self, action: str, params: dict) -> dict:
        """Execute combat actions."""
        if action == 'attack':
            # Use combat engine attack method
            return self.dm.combat.player_attack(params.get('target_id'))
        elif action == 'flee':
            return self.dm.combat.attempt_flee(params.get('character_id'))
        elif action == 'defend':
            return self.dm.combat.declare_defense(params.get('character_id'))
        return {'error': f'Unknown combat action: {action}'}

    def _execute_settlement_action(self, action: str, params: dict) -> dict:
        """Execute settlement actions."""
        if action == 'explore':
            return self.dm.settlement.explore()
        elif action == 'find_inn':
            return self.dm.settlement.find_service('inn')
        elif action == 'find_shop':
            return self.dm.settlement.find_service('shop')
        elif action == 'gather_rumors':
            return self.dm.settlement.gather_rumors()
        return {'error': f'Unknown settlement action: {action}'}

    def _execute_social_action(self, action: str, params: dict) -> dict:
        """Execute social interaction actions."""
        if action == 'continue':
            return self.dm.settlement.continue_conversation(params.get('text', ''))
        elif action == 'persuade':
            return self.dm.settlement.attempt_persuade()
        elif action == 'intimidate':
            return self.dm.settlement.attempt_intimidate()
        elif action == 'end':
            return self.dm.settlement.end_conversation()
        return {'error': f'Unknown social action: {action}'}

    def _execute_downtime_action(self, action: str, params: dict) -> dict:
        """Execute downtime actions."""
        if action == 'rest':
            return self.dm.rest(params.get('rest_type', 'long'))
        elif action == 'forage':
            return self.dm.downtime.forage()
        elif action == 'hunt':
            return self.dm.downtime.hunt()
        elif action == 'end':
            return self.dm.downtime.break_camp()
        return {'error': f'Unknown downtime action: {action}'}

    def _execute_oracle_action(self, action: str, params: dict) -> dict:
        """Execute Mythic oracle actions."""
        if action == 'fate_check':
            try:
                from src.oracle.mythic_gme import MythicGME, Likelihood
                oracle = MythicGME()
                likelihood = Likelihood(params.get('likelihood', 'likely'))
                result = oracle.fate_check(
                    question=params.get('question', 'Is it so?'),
                    likelihood=likelihood,
                )
                return {
                    'success': True,
                    'oracle_result': result.answer.value,
                    'exceptional': result.exceptional,
                    'random_event': result.random_event,
                    'meaning': result.meaning_pair if result.random_event else None,
                }
            except ImportError:
                return {'error': 'Oracle module not available'}
        return {'error': f'Unknown oracle action: {action}'}

    def _execute_transition(self, trigger: str, params: dict) -> dict:
        """Execute state machine transition."""
        try:
            new_state = self.dm.controller.transition(trigger)
            return {
                'success': True,
                'new_state': new_state.value,
                'message': f'Transitioned to {new_state.value}',
            }
        except Exception as e:
            return {'error': str(e)}

    # =========================================================================
    # Message Building
    # =========================================================================

    def _build_messages_from_result(self, result: dict) -> list[ChatMessage]:
        """Convert engine result dict to chat messages."""
        messages = []

        if not result:
            return messages

        # Check for error
        if 'error' in result:
            messages.append(ChatMessage(
                role=MessageRole.SYSTEM,
                content=f"Error: {result['error']}",
            ))
            return messages

        # Add mechanical result
        if result.get('success') is not None:
            status = "Success" if result.get('success') else "Failed"
            if result.get('partial_success'):
                status = "Partial success"

            mech_parts = [f"[{status}]"]

            # Dice rolls
            if 'dice_result' in result:
                mech_parts.append(f"Rolled: {result['dice_result']}")
            if 'roll' in result:
                mech_parts.append(f"Roll: {result['roll']}")

            # Damage
            if result.get('damage_dealt'):
                mech_parts.append(f"Damage: {result['damage_dealt']}")

            messages.append(ChatMessage(
                role=MessageRole.MECHANICAL,
                content=" | ".join(mech_parts),
            ))

        # Add narration
        narration = result.get('narration') or result.get('description') or result.get('message')
        if narration:
            messages.append(ChatMessage(
                role=MessageRole.DM,
                content=narration,
            ))

        # Add warnings
        for warning in result.get('warnings', []):
            messages.append(ChatMessage(
                role=MessageRole.SYSTEM,
                content=f"Warning: {warning}",
            ))

        return messages
```

### CLI Integration: Modify `src/main.py`

Add these changes to the existing `DolmenwoodCLI` class:

```python
# At top of file, add import:
from src.conversation import ConversationFacade, TurnResponse

# In DolmenwoodCLI.__init__, add:
class DolmenwoodCLI:
    def __init__(self, dm: VirtualDM):
        self.dm = dm
        self.conv = ConversationFacade(dm)  # ADD THIS
        self.last_suggestions = []           # ADD THIS
        # ... rest of existing init

# In process_command() method, add at the START (before existing command parsing):
def process_command(self, user_input: str) -> bool:
    """Process a command and return True to continue, False to exit."""

    # NEW: Handle numeric input as suggestion selection
    if user_input.strip().isdigit() and self.last_suggestions:
        idx = int(user_input.strip()) - 1
        if 0 <= idx < len(self.last_suggestions):
            action = self.last_suggestions[idx]
            turn = self.conv.handle_action(action.id, action.params)
            self._render_turn(turn)
            return True

    # ... existing command parsing ...

    # At the end, where "Unknown command" would be printed, replace with:
    # (This makes unknown commands go through conversation)
    turn = self.conv.handle_chat(user_input)
    self._render_turn(turn)
    return True

# Add these new methods to DolmenwoodCLI:
def _render_turn(self, turn: TurnResponse) -> None:
    """Render a conversation turn response."""
    # Messages
    for msg in turn.messages:
        if msg.role.value == "mechanical":
            print(f"  {msg.content}")
        elif msg.role.value == "dm":
            print(f"\n{msg.content}")
        elif msg.role.value == "system":
            print(f"[System] {msg.content}")
        else:
            print(msg.content)

    # Suggestions
    self._render_suggestions(turn.suggested_actions)

def _render_suggestions(self, suggestions: list) -> None:
    """Render numbered suggestions."""
    self.last_suggestions = suggestions[:9]  # Max 9 for single-digit selection

    if not self.last_suggestions:
        return

    print("\n--- Suggested Actions ---")
    for i, action in enumerate(self.last_suggestions, 1):
        status = ""
        if not action.enabled:
            status = f" (disabled: {action.disabled_reason})"
        print(f"  {i}. {action.label}{status}")
    print()
```

---

## Upgrade A: LLM-Driven Intent Parsing

**When:** After MVP is stable and pattern matching feels limiting

### Goal
Replace pattern matching in `ConversationFacade._handle_*_input()` with LLM-based intent parsing for higher accuracy routing.

### Implementation

#### Add schema to `src/ai/prompt_schemas.py`:
```python
class IntentParseSchema(PromptSchema):
    """Schema for parsing player intent into structured action."""

    def __init__(self):
        super().__init__(
            schema_type=PromptSchemaType.INTENT_PARSE,
            system_prompt="""You are parsing player input for a Dolmenwood TTRPG game.

Given the current game state and player input, determine:
1. The most likely intended action
2. Any parameters for that action
3. Confidence level (0.0-1.0)
4. Whether clarification is needed

Available action categories by game state:
- WILDERNESS_TRAVEL: travel, search_hex, make_camp, forage, hunt
- DUNGEON_EXPLORATION: move, search, listen, open_door, rest, cast_spell
- ENCOUNTER: attack, parley, evade, wait
- COMBAT: attack, defend, flee, cast_spell, use_item
- SETTLEMENT: talk, shop, rest, gather_rumors
- DOWNTIME: rest, forage, hunt, craft

Output JSON only.""",
            input_fields={
                "player_input": "The player's natural language input",
                "current_state": "Current game state (e.g., DUNGEON_EXPLORATION)",
                "context": "Relevant context (room exits, nearby NPCs, etc.)",
            },
            output_format={
                "action_id": "string (e.g., 'dungeon:search')",
                "params": "object with action parameters",
                "confidence": "number 0.0-1.0",
                "requires_clarification": "boolean",
                "clarification_question": "string (if clarification needed)",
                "alternatives": "array of alternative action_ids",
            },
        )
```

#### Add to `DMAgent`:
```python
def parse_intent(
    self,
    player_input: str,
    current_state: str,
    context: dict,
) -> dict:
    """Parse player intent into structured action."""
    schema = IntentParseSchema()
    result = self._execute_schema(
        schema,
        player_input=player_input,
        current_state=current_state,
        context=json.dumps(context),
    )
    return result
```

#### Wire in `ConversationFacade`:
```python
def __init__(self, dm: "VirtualDM"):
    # ... existing init ...
    self._intent_parser = None
    if dm._dm_agent:
        self._intent_parser = dm._dm_agent.parse_intent

def handle_chat(self, text: str, character_id: str = None) -> TurnResponse:
    # Try LLM parsing first if available
    if self._intent_parser:
        try:
            intent = self._intent_parser(
                player_input=text,
                current_state=self.dm.current_state.value,
                context=export_public_state(self.dm),
            )
            if intent.get('confidence', 0) > 0.7:
                return self.handle_action(
                    intent['action_id'],
                    intent.get('params', {}),
                )
        except Exception:
            pass  # Fall through to pattern matching

    # ... existing pattern matching logic ...
```

---

## Upgrade B: Canonical ActionRegistry

**When:** Action routing becomes complex or you want tool-guided workflows

### Goal
Make `ActionRegistry` authoritative for all executable actions with enforced schemas.

### Implementation

#### `src/conversation/action_registry.py`:
```python
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from src.game_state.state_machine import GameState


@dataclass
class ActionSpec:
    """Specification for a registered action."""
    id: str
    label: str
    category: str
    valid_states: list[GameState]
    params_schema: dict[str, Any]
    handler: Callable[[Any, dict], dict]  # (dm, params) -> result
    description: str = ""


class ActionRegistry:
    """
    Canonical registry for all executable actions.

    Benefits:
    - Single source of truth for what actions exist
    - Enforced parameter schemas
    - State validation
    - Handler discovery for tool graphs
    """

    def __init__(self):
        self._actions: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        """Register an action specification."""
        self._actions[spec.id] = spec

    def get(self, action_id: str) -> Optional[ActionSpec]:
        """Get action spec by ID."""
        return self._actions.get(action_id)

    def get_valid_actions(self, state: GameState) -> list[ActionSpec]:
        """Get all actions valid for a game state."""
        return [
            spec for spec in self._actions.values()
            if state in spec.valid_states
        ]

    def execute(self, action_id: str, dm: Any, params: dict) -> dict:
        """Execute an action by ID."""
        spec = self.get(action_id)
        if not spec:
            return {'error': f'Unknown action: {action_id}'}

        # Validate params against schema
        validation_error = self._validate_params(params, spec.params_schema)
        if validation_error:
            return {'error': validation_error}

        # Execute handler
        return spec.handler(dm, params)

    def _validate_params(self, params: dict, schema: dict) -> Optional[str]:
        """Validate params against schema. Returns error message or None."""
        for field, field_schema in schema.items():
            if field_schema.get('required') and field not in params:
                return f"Missing required parameter: {field}"
        return None


def create_default_registry() -> ActionRegistry:
    """Create registry with all default actions."""
    registry = ActionRegistry()

    # Register wilderness actions
    registry.register(ActionSpec(
        id="wilderness:travel",
        label="Travel to hex",
        category="wilderness",
        valid_states=[GameState.WILDERNESS_TRAVEL],
        params_schema={
            "hex_id": {"type": "string", "required": True},
        },
        handler=lambda dm, p: dm.travel_to_hex(p['hex_id']),
    ))

    # ... register all other actions ...

    return registry
```

---

## Upgrade C: Mythic Oracle Integration

**When:** You want oracle-based adjudication for ambiguous situations

### Goal
Wire Mythic GME into the resolution path for freeform actions and Tier-4 spells.

### Implementation

#### Add to `GlobalController`:
```python
def get_oracle(self) -> "MythicGME":
    """Get or create Mythic GME oracle instance."""
    if not hasattr(self, '_oracle'):
        from src.oracle.mythic_gme import MythicGME
        self._oracle = MythicGME(chaos_factor=5)
    return self._oracle

def set_chaos_factor(self, factor: int) -> None:
    """Set Mythic chaos factor (1-9)."""
    self.get_oracle().chaos_factor = max(1, min(9, factor))
```

#### Add to `SpellResolver` for Tier-4:
```python
def _resolve_tier4_spell(self, spell_data, context) -> ResolutionResult:
    """Resolve open-ended spell via Mythic oracle."""
    from src.oracle import MythicSpellAdjudicator
    from src.oracle.effect_commands import EffectCommandBuilder, EffectExecutor

    oracle = self.controller.get_oracle()
    adjudicator = MythicSpellAdjudicator(oracle)

    # Get adjudication
    adj_result = adjudicator.adjudicate(
        spell_id=spell_data.spell_id,
        caster_id=context.get('caster_id'),
        situation=context.get('situation'),
    )

    # Build and execute effects
    if adj_result.success:
        effects = EffectCommandBuilder.from_adjudication(adj_result)
        executor = EffectExecutor(self.controller)
        executor.execute(effects)

    return ResolutionResult(
        success=adj_result.success,
        oracle_result=adj_result,
    )
```

#### Add oracle suggestions in `ConversationFacade`:
```python
def _handle_freeform(self, text: str, character_id: str) -> dict:
    # ... existing freeform handling ...

    # If resolution is ambiguous, offer oracle
    if result.get('requires_clarification'):
        return {
            'success': False,
            'narration': "The situation is unclear...",
            'offer_oracle': True,
            'oracle_question': f"Does the attempt to {text} succeed?",
        }
```

---

## Upgrade D: Foundry VTT Seam

**When:** Ready to add visual representation

### Goal
Export state deltas and events in Foundry-compatible format.

### Implementation

#### `src/integrations/foundry/foundry_bridge.py`:
```python
"""Bridge between VirtualDM and Foundry VTT."""
import json
from typing import Any
from src.conversation.state_export import export_public_state, EventStream


class FoundryBridge:
    """
    Translates VirtualDM state/events to Foundry format.

    Can operate in two modes:
    - Snapshot mode: Full state each turn
    - Delta mode: Only state changes
    """

    def __init__(self, dm, mode: str = "snapshot"):
        self.dm = dm
        self.mode = mode
        self.event_stream = EventStream()
        self.event_stream.start()
        self._last_state = None

    def get_update(self) -> dict[str, Any]:
        """Get update for Foundry."""
        current_state = export_public_state(self.dm)
        events = self.event_stream.drain()

        if self.mode == "snapshot":
            return {
                "type": "snapshot",
                "state": current_state,
                "events": events,
            }
        else:
            delta = self._compute_delta(self._last_state, current_state)
            self._last_state = current_state
            return {
                "type": "delta",
                "changes": delta,
                "events": events,
            }

    def _compute_delta(self, old: dict, new: dict) -> dict:
        """Compute state delta."""
        # Simple diff implementation
        if not old:
            return new

        delta = {}
        for key, value in new.items():
            if old.get(key) != value:
                delta[key] = value
        return delta
```

---

## Testing Strategy

### Unit Tests

| Component | Test File | Key Tests |
|-----------|-----------|-----------|
| types.py | `tests/test_conversation_types.py` | Serialization, validation |
| suggestion_builder.py | `tests/test_suggestions.py` | Per-state suggestions, context awareness |
| conversation_facade.py | `tests/test_facade.py` | Routing, action execution |
| state_export.py | `tests/test_state_export.py` | Schema versioning, event streaming |

### Integration Tests

```python
# tests/test_conversation_integration.py

def test_full_chat_flow():
    """Test complete conversation turn."""
    dm = VirtualDM(initial_state=GameState.DUNGEON_EXPLORATION)
    facade = ConversationFacade(dm)

    # Natural language
    response = facade.handle_chat("I search the room carefully")
    assert response.success
    assert len(response.suggested_actions) > 0
    assert response.state_snapshot is not None

def test_suggestion_selection():
    """Test selecting numbered suggestion."""
    dm = VirtualDM(initial_state=GameState.DUNGEON_EXPLORATION)
    facade = ConversationFacade(dm)

    # Get initial suggestions
    initial = facade.handle_chat("look around")
    assert len(initial.suggested_actions) > 0

    # Select first suggestion
    action = initial.suggested_actions[0]
    response = facade.handle_action(action.id, action.params)
    assert response.success

def test_state_transitions_update_suggestions():
    """Verify suggestions change with state."""
    dm = VirtualDM(initial_state=GameState.WILDERNESS_TRAVEL)
    facade = ConversationFacade(dm)

    wilderness_suggestions = facade.handle_chat("what can I do?").suggested_actions
    wilderness_ids = {s.id for s in wilderness_suggestions}

    # Trigger encounter
    dm.controller.transition("encounter_triggered")

    encounter_suggestions = facade.handle_chat("what now?").suggested_actions
    encounter_ids = {s.id for s in encounter_suggestions}

    # Suggestions should be different
    assert wilderness_ids != encounter_ids
    assert any("encounter:" in s.id for s in encounter_suggestions)
```

---

## Definition of Done

### MVP Complete When:
- [ ] User can type natural language in CLI
- [ ] System returns narration + numbered suggestions (5-12)
- [ ] Typing a number executes that suggestion
- [ ] All procedural actions route to correct engine methods
- [ ] Freeform input routes to `handle_player_action()`
- [ ] RunLog captures all events

### Upgrade A Complete When:
- [ ] LLM parses intent with >70% accuracy
- [ ] Graceful fallback to pattern matching

### Upgrade B Complete When:
- [ ] All actions registered in ActionRegistry
- [ ] Parameter validation enforced
- [ ] State validation enforced

### Upgrade C Complete When:
- [ ] Oracle accessible from conversation
- [ ] Tier-4 spells adjudicated via Mythic
- [ ] Chaos factor tracked in controller

### Upgrade D Complete When:
- [ ] State exports in versioned schema
- [ ] Event stream consumable by Foundry
- [ ] Delta mode working for efficiency

---

## Quick Start (What To Do Now)

1. **Create the package:**
   ```bash
   mkdir -p src/conversation
   touch src/conversation/__init__.py
   ```

2. **Copy the 4 core files** from Phase 0:
   - `types.py`
   - `suggestion_builder.py`
   - `state_export.py`
   - `conversation_facade.py`

3. **Modify `src/main.py`** per the CLI Integration section

4. **Test the MVP:**
   ```bash
   python -m src.main
   # Type: "search the room"
   # Type: "1" (to select first suggestion)
   ```

5. **Iterate:** Fix routing issues, add missing action handlers

6. **When stable:** Implement Upgrade A (LLM intent parsing)

---

## File Summary

### New Files (MVP)
```
src/conversation/
├── __init__.py
├── types.py              (~80 lines)
├── suggestion_builder.py (~250 lines)
├── state_export.py       (~100 lines)
└── conversation_facade.py (~400 lines)
```

### Modified Files (MVP)
```
src/main.py              (+50 lines to DolmenwoodCLI)
```

### New Files (Upgrades)
```
src/conversation/
└── action_registry.py    (Upgrade B)

src/ai/prompt_schemas.py  (Upgrade A: add IntentParseSchema)

src/integrations/foundry/
└── foundry_bridge.py     (Upgrade D)
```

### Modified Files (Upgrades)
```
src/ai/dm_agent.py        (Upgrade A: add parse_intent)
src/game_state/global_controller.py  (Upgrade C: add get_oracle)
src/narrative/spell_resolver.py      (Upgrade C: add Tier-4 path)
```
