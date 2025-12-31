"""
Foundry VTT Integration Bridge (Upgrade C).

This module provides the seam between the Virtual DM engine and Foundry VTT.
It exports state and events in Foundry-compatible formats.

Supports two modes:
- Snapshot mode: Full state export each turn
- Delta mode: Only state changes for efficiency

Events are translated to Foundry socket message format.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import json
import copy

if TYPE_CHECKING:
    from src.main import VirtualDM


class FoundryExportMode(str, Enum):
    """Export mode for Foundry integration."""
    SNAPSHOT = "snapshot"  # Full state each turn
    DELTA = "delta"  # Only changes


class FoundryEventType(str, Enum):
    """Types of events sent to Foundry."""
    STATE_UPDATE = "state_update"
    CHAT_MESSAGE = "chat_message"
    ROLL_RESULT = "roll_result"
    COMBAT_UPDATE = "combat_update"
    ACTOR_UPDATE = "actor_update"
    TOKEN_UPDATE = "token_update"
    SCENE_UPDATE = "scene_update"
    EFFECT_APPLIED = "effect_applied"
    ITEM_CHANGE = "item_change"
    NARRATION = "narration"


@dataclass
class FoundryEvent:
    """
    An event to be sent to Foundry VTT.

    Matches Foundry's socket message format.
    """
    event_type: FoundryEventType
    data: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "dolmenwood_vdm"

    def to_socket_message(self) -> dict[str, Any]:
        """Convert to Foundry socket message format."""
        return {
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }


@dataclass
class FoundryStateExport:
    """
    Complete state export for Foundry.

    Contains all information needed to sync Foundry state.
    """
    version: int = 1
    mode: str = "snapshot"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Core state
    game_state: str = ""  # Current GameState value
    location: dict[str, Any] = field(default_factory=dict)
    time: dict[str, Any] = field(default_factory=dict)
    weather: dict[str, Any] = field(default_factory=dict)

    # Party state
    party: dict[str, Any] = field(default_factory=dict)
    characters: list[dict[str, Any]] = field(default_factory=list)

    # Combat state (if active)
    combat: Optional[dict[str, Any]] = None

    # Encounter state (if active)
    encounter: Optional[dict[str, Any]] = None

    # Pending events
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class FoundryBridge:
    """
    Bridge between Virtual DM and Foundry VTT.

    Handles:
    - State export (snapshot or delta mode)
    - Event translation to Foundry format
    - Efficient delta computation
    """

    def __init__(
        self,
        dm: VirtualDM,
        mode: FoundryExportMode = FoundryExportMode.SNAPSHOT
    ):
        self.dm = dm
        self.mode = mode

        # For delta mode
        self._last_state: Optional[dict[str, Any]] = None
        self._pending_events: list[FoundryEvent] = []

    def export_state(self) -> FoundryStateExport:
        """
        Export current state for Foundry.

        In snapshot mode, exports full state.
        In delta mode, exports only changes since last export.
        """
        current = self._build_current_state()

        if self.mode == FoundryExportMode.DELTA and self._last_state:
            # Compute delta
            delta_export = self._compute_delta(self._last_state, current)
            delta_export.mode = "delta"
            self._last_state = copy.deepcopy(current.to_dict())
            return delta_export
        else:
            # Full snapshot
            self._last_state = copy.deepcopy(current.to_dict())
            current.mode = "snapshot"
            return current

    def _build_current_state(self) -> FoundryStateExport:
        """Build current state export from VirtualDM."""
        export = FoundryStateExport()

        # Game state
        export.game_state = self.dm.current_state.value

        # Location
        ps = self.dm.controller.party_state
        export.location = {
            "location_id": ps.location.location_id if ps.location else "",
            "location_type": str(ps.location.location_type) if ps.location and hasattr(ps.location, 'location_type') else "",
            "name": str(ps.location) if ps.location else "",
        }

        # Time and weather
        ws = self.dm.controller.world_state
        if ws:
            export.time = {
                "date": str(ws.current_date) if hasattr(ws, 'current_date') else "",
                "time": str(ws.current_time) if hasattr(ws, 'current_time') else "",
                "time_of_day": ws.current_time.get_time_of_day().value if hasattr(ws, 'current_time') else "",
            }
            if hasattr(ws, 'weather') and ws.weather:
                export.weather = {
                    "condition": ws.weather.condition.value if hasattr(ws.weather, 'condition') else "",
                    "temperature": ws.weather.temperature if hasattr(ws.weather, 'temperature') else "",
                    "wind": ws.weather.wind if hasattr(ws.weather, 'wind') else "",
                }

        # Party resources
        if hasattr(ps, 'resources') and ps.resources:
            export.party = {
                "food_days": ps.resources.food_days,
                "water_days": ps.resources.water_days,
                "torches": ps.resources.torches,
                "lantern_oil_flasks": ps.resources.lantern_oil_flasks,
                "active_light_source": ps.active_light_source,
                "light_remaining_turns": ps.light_remaining_turns,
            }

        # Characters
        export.characters = self._export_characters()

        # Combat (if active)
        if hasattr(self.dm, 'combat') and self.dm.combat and self.dm.combat.in_combat:
            export.combat = self._export_combat()

        # Encounter (if active)
        if self.dm.current_state.value == "encounter" and hasattr(self.dm, 'encounter'):
            export.encounter = self._export_encounter()

        # Pending events
        export.events = [e.to_socket_message() for e in self._pending_events]
        self._pending_events = []

        return export

    def _export_characters(self) -> list[dict[str, Any]]:
        """Export all character states."""
        characters = []
        for char in self.dm.controller.get_all_characters():
            char_data = {
                "character_id": char.character_id,
                "name": char.name,
                "class": char.character_class.value if hasattr(char, 'character_class') else "",
                "level": char.level if hasattr(char, 'level') else 1,
                "hp_current": char.hp_current if hasattr(char, 'hp_current') else 0,
                "hp_max": char.hp_max if hasattr(char, 'hp_max') else 0,
                "ac": char.armor_class if hasattr(char, 'armor_class') else 10,
                "conditions": [c.value if hasattr(c, 'value') else str(c) for c in getattr(char, 'conditions', [])],
                "is_alive": char.is_alive() if hasattr(char, 'is_alive') else True,
                "is_conscious": char.is_conscious() if hasattr(char, 'is_conscious') else True,
            }

            # Abilities
            if hasattr(char, 'abilities'):
                char_data["abilities"] = {
                    "str": char.abilities.get('str', 10) if isinstance(char.abilities, dict) else 10,
                    "dex": char.abilities.get('dex', 10) if isinstance(char.abilities, dict) else 10,
                    "con": char.abilities.get('con', 10) if isinstance(char.abilities, dict) else 10,
                    "int": char.abilities.get('int', 10) if isinstance(char.abilities, dict) else 10,
                    "wis": char.abilities.get('wis', 10) if isinstance(char.abilities, dict) else 10,
                    "cha": char.abilities.get('cha', 10) if isinstance(char.abilities, dict) else 10,
                }

            characters.append(char_data)
        return characters

    def _export_combat(self) -> dict[str, Any]:
        """Export combat state."""
        combat = self.dm.combat
        return {
            "active": combat.in_combat,
            "round": combat.current_round if hasattr(combat, 'current_round') else 0,
            "turn": combat.current_turn if hasattr(combat, 'current_turn') else 0,
            "initiative_order": [],  # Would need initiative tracking
            "combatants": [],  # Would need combatant list
        }

    def _export_encounter(self) -> dict[str, Any]:
        """Export encounter state."""
        encounter = self.dm.encounter
        if not hasattr(encounter, 'encounter_state') or not encounter.encounter_state:
            return {}

        es = encounter.encounter_state
        return {
            "active": not getattr(es, 'resolved', True),
            "encounter_type": getattr(es, 'encounter_type', ''),
            "creature_name": getattr(es, 'creature_name', ''),
            "creature_count": getattr(es, 'creature_count', 0),
            "disposition": getattr(es, 'disposition', ''),
            "surprise": getattr(es, 'surprise_type', ''),
        }

    def _compute_delta(
        self,
        old_state: dict[str, Any],
        new_state: FoundryStateExport
    ) -> FoundryStateExport:
        """
        Compute delta between old and new state.

        Only includes fields that have changed.
        """
        new_dict = new_state.to_dict()
        delta = FoundryStateExport()

        # Always include these
        delta.game_state = new_state.game_state
        delta.timestamp = new_state.timestamp

        # Check each section for changes
        if old_state.get("location") != new_dict.get("location"):
            delta.location = new_state.location

        if old_state.get("time") != new_dict.get("time"):
            delta.time = new_state.time

        if old_state.get("weather") != new_dict.get("weather"):
            delta.weather = new_state.weather

        if old_state.get("party") != new_dict.get("party"):
            delta.party = new_state.party

        if old_state.get("characters") != new_dict.get("characters"):
            delta.characters = new_state.characters

        if old_state.get("combat") != new_dict.get("combat"):
            delta.combat = new_state.combat

        if old_state.get("encounter") != new_dict.get("encounter"):
            delta.encounter = new_state.encounter

        # Always include events
        delta.events = new_state.events

        return delta

    # -------------------------------------------------------------------------
    # Event helpers
    # -------------------------------------------------------------------------

    def emit_chat(self, speaker: str, content: str, message_type: str = "ic") -> None:
        """Emit a chat message event."""
        self._pending_events.append(FoundryEvent(
            event_type=FoundryEventType.CHAT_MESSAGE,
            data={
                "speaker": speaker,
                "content": content,
                "type": message_type,  # "ic", "ooc", "emote", "whisper"
            }
        ))

    def emit_roll(
        self,
        roller: str,
        roll_type: str,
        dice: str,
        result: int,
        target: Optional[int] = None,
        success: Optional[bool] = None
    ) -> None:
        """Emit a dice roll event."""
        self._pending_events.append(FoundryEvent(
            event_type=FoundryEventType.ROLL_RESULT,
            data={
                "roller": roller,
                "roll_type": roll_type,
                "dice": dice,
                "result": result,
                "target": target,
                "success": success,
            }
        ))

    def emit_narration(self, content: str, narrator: str = "DM") -> None:
        """Emit a narration event."""
        self._pending_events.append(FoundryEvent(
            event_type=FoundryEventType.NARRATION,
            data={
                "narrator": narrator,
                "content": content,
            }
        ))

    def emit_actor_update(self, actor_id: str, changes: dict[str, Any]) -> None:
        """Emit an actor update event."""
        self._pending_events.append(FoundryEvent(
            event_type=FoundryEventType.ACTOR_UPDATE,
            data={
                "actor_id": actor_id,
                "changes": changes,
            }
        ))

    def emit_effect_applied(
        self,
        target_id: str,
        effect_name: str,
        duration: Optional[int] = None
    ) -> None:
        """Emit an effect applied event."""
        self._pending_events.append(FoundryEvent(
            event_type=FoundryEventType.EFFECT_APPLIED,
            data={
                "target_id": target_id,
                "effect_name": effect_name,
                "duration": duration,
            }
        ))

    def emit_combat_update(self, update_type: str, data: dict[str, Any]) -> None:
        """Emit a combat update event."""
        self._pending_events.append(FoundryEvent(
            event_type=FoundryEventType.COMBAT_UPDATE,
            data={
                "update_type": update_type,  # "start", "end", "turn", "round"
                **data,
            }
        ))

    def clear_pending_events(self) -> list[FoundryEvent]:
        """Clear and return pending events."""
        events = self._pending_events
        self._pending_events = []
        return events
