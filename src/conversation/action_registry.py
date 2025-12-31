"""
Action registry and execution helpers.

Upgrade B: Canonical ActionRegistry
-----------------------------------
All actions are registered here with:
- stable IDs so UI can reference actions deterministically
- parameter schemas for validation
- executors that call existing engine methods

The registry serves as the single source of truth for available actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from src.main import VirtualDM


class ActionCategory(str, Enum):
    """Categories of actions for organization."""
    META = "meta"
    WILDERNESS = "wilderness"
    DUNGEON = "dungeon"
    ENCOUNTER = "encounter"
    SETTLEMENT = "settlement"
    DOWNTIME = "downtime"
    ORACLE = "oracle"
    TRANSITION = "transition"


ActionExecutor = Callable[["VirtualDM", dict[str, Any]], dict[str, Any]]


@dataclass
class ActionSpec:
    """Specification for a registered action."""
    id: str
    label: str
    category: ActionCategory
    params_schema: dict[str, Any] = field(default_factory=dict)
    executor: Optional[ActionExecutor] = None
    safe_to_execute: bool = True
    help: Optional[str] = None
    requires_state: Optional[str] = None  # GameState value if state-specific


class ActionRegistry:
    """
    Central registry for all game actions.

    Provides:
    - Action lookup by ID
    - Parameter validation
    - Execution routing
    - State validation
    """

    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}
        self._by_category: dict[ActionCategory, list[ActionSpec]] = {}

    def register(self, spec: ActionSpec) -> None:
        """Register an action specification."""
        self._actions[spec.id] = spec

        if spec.category not in self._by_category:
            self._by_category[spec.category] = []
        self._by_category[spec.category].append(spec)

    def get(self, action_id: str) -> Optional[ActionSpec]:
        """Get an action by ID."""
        return self._actions.get(action_id)

    def all(self) -> list[ActionSpec]:
        """Get all registered actions."""
        return list(self._actions.values())

    def by_category(self, category: ActionCategory) -> list[ActionSpec]:
        """Get actions by category."""
        return self._by_category.get(category, [])

    def for_state(self, state_value: str) -> list[ActionSpec]:
        """Get actions valid for a specific game state."""
        return [
            spec for spec in self._actions.values()
            if spec.requires_state is None or spec.requires_state == state_value
        ]

    def validate_params(self, action_id: str, params: dict[str, Any]) -> list[str]:
        """
        Validate parameters against action schema.

        Returns list of validation errors (empty if valid).
        """
        spec = self.get(action_id)
        if not spec:
            return [f"Unknown action: {action_id}"]

        errors = []
        schema = spec.params_schema

        # Check required params
        for param_name, param_def in schema.items():
            if isinstance(param_def, dict):
                if param_def.get("required", False) and param_name not in params:
                    errors.append(f"Missing required parameter: {param_name}")

                # Type checking
                if param_name in params and "type" in param_def:
                    expected_type = param_def["type"]
                    actual_value = params[param_name]
                    if expected_type == "string" and not isinstance(actual_value, str):
                        errors.append(f"Parameter {param_name} must be a string")
                    elif expected_type == "integer" and not isinstance(actual_value, int):
                        errors.append(f"Parameter {param_name} must be an integer")
                    elif expected_type == "boolean" and not isinstance(actual_value, bool):
                        errors.append(f"Parameter {param_name} must be a boolean")

        return errors

    def execute(
        self,
        dm: "VirtualDM",
        action_id: str,
        params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Execute an action by ID.

        Returns result dict with at least {"success": bool, "message": str}.
        """
        spec = self.get(action_id)
        if not spec:
            return {"success": False, "message": f"Unknown action: {action_id}"}

        params = params or {}

        # Validate params
        errors = self.validate_params(action_id, params)
        if errors:
            return {"success": False, "message": f"Validation failed: {'; '.join(errors)}"}

        # Check state requirement
        if spec.requires_state and dm.current_state.value != spec.requires_state:
            return {
                "success": False,
                "message": f"Action {action_id} requires state {spec.requires_state}, "
                           f"but current state is {dm.current_state.value}"
            }

        # Execute
        if spec.executor:
            try:
                return spec.executor(dm, params)
            except Exception as e:
                return {"success": False, "message": f"Execution failed: {e}"}
        else:
            return {"success": False, "message": f"No executor for action: {action_id}"}


# =============================================================================
# DEFAULT REGISTRY WITH ALL ACTIONS
# =============================================================================


def _create_default_registry() -> ActionRegistry:
    """Create the default registry with all standard actions."""
    registry = ActionRegistry()

    # -------------------------------------------------------------------------
    # Meta actions (always available)
    # -------------------------------------------------------------------------
    def _meta_status(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Generate status summary matching ConversationFacade format."""
        from src.game_state.state_machine import GameState

        ps = dm.controller.party_state
        ws = dm.controller.world_state
        parts = [f"Mode: {dm.current_state.value}"]
        parts.append(f"Location: {ps.location.location_id} ({ps.location.location_type})")
        parts.append(f"Time: {ws.current_date} {ws.current_time}")
        if ps.active_light_source and ps.light_remaining_turns > 0:
            parts.append(f"Light: {ps.active_light_source} ({ps.light_remaining_turns} turn(s) left)")
        else:
            parts.append("Light: none")
        if dm.current_state == GameState.WILDERNESS_TRAVEL:
            tp = getattr(dm.hex_crawl, "_travel_points_remaining", None)
            tpt = getattr(dm.hex_crawl, "_travel_points_total", None)
            if tp is not None and tpt is not None:
                parts.append(f"Travel Points: {tp}/{tpt}")
        if dm.current_state == GameState.DUNGEON_EXPLORATION:
            try:
                summ = dm.dungeon.get_exploration_summary()
                parts.append(f"Dungeon Turns since rest: {summ.get('turns_since_rest')}/5")
            except Exception:
                pass
        return {"success": True, "message": "\n".join(parts)}

    registry.register(ActionSpec(
        id="meta:status",
        label="Show status / summary",
        category=ActionCategory.META,
        help="Print a compact summary of current mode, time, and party state.",
        executor=_meta_status,
    ))

    # -------------------------------------------------------------------------
    # Oracle actions (always available)
    # -------------------------------------------------------------------------
    def _oracle_fate_check(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Execute oracle fate check."""
        from src.oracle.mythic_gme import MythicGME, Likelihood
        import random

        q = (p.get("question") or "").strip()
        if not q:
            return {"success": False, "message": "Oracle requires a yes/no question."}

        like = (p.get("likelihood") or "fifty_fifty").strip().lower()
        likelihood_map = {
            "impossible": Likelihood.IMPOSSIBLE,
            "very_unlikely": Likelihood.VERY_UNLIKELY,
            "unlikely": Likelihood.UNLIKELY,
            "fifty_fifty": Likelihood.FIFTY_FIFTY,
            "likely": Likelihood.LIKELY,
            "very_likely": Likelihood.VERY_LIKELY,
            "near_sure_thing": Likelihood.NEAR_SURE_THING,
            "a_sure_thing": Likelihood.A_SURE_THING,
            "has_to_be": Likelihood.HAS_TO_BE,
        }
        likelihood = likelihood_map.get(like, Likelihood.FIFTY_FIFTY)

        mythic = MythicGME(rng=random.Random())
        r = mythic.fate_check(q, likelihood)
        result_str = r.result.value.replace("_", " ").title()
        msg = f"Oracle: {result_str} (roll={r.roll}, chaos={r.chaos_factor})"
        if r.random_event_triggered and r.random_event:
            msg += f" [Random Event: {r.random_event}]"
        return {"success": True, "message": msg}

    registry.register(ActionSpec(
        id="oracle:fate_check",
        label="Ask the Oracle (yes/no)",
        category=ActionCategory.ORACLE,
        params_schema={
            "question": {"type": "string", "required": True},
            "likelihood": {"type": "string", "required": False},
        },
        help="Ask a yes/no question to the Mythic GME oracle.",
        executor=_oracle_fate_check,
    ))

    def _oracle_random_event(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Generate a random event."""
        from src.oracle.mythic_gme import MythicGME
        import random

        mythic = MythicGME(rng=random.Random())
        ev = mythic.generate_random_event()
        msg = f"Random Event — Focus: {ev.focus.value}; Meaning: {ev.action} / {ev.subject}"
        return {"success": True, "message": msg}

    registry.register(ActionSpec(
        id="oracle:random_event",
        label="Mythic: Random Event",
        category=ActionCategory.ORACLE,
        help="Generate a random event using Mythic GME.",
        executor=_oracle_random_event,
    ))

    def _oracle_detail_check(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Get a detail check word pair."""
        from src.oracle.mythic_gme import MythicGME
        import random

        mythic = MythicGME(rng=random.Random())
        m = mythic.detail_check()
        msg = f"Detail Check — {m.action} / {m.subject}"
        return {"success": True, "message": msg}

    registry.register(ActionSpec(
        id="oracle:detail_check",
        label="Mythic: Detail Check",
        category=ActionCategory.ORACLE,
        help="Get an action/subject word pair for interpretation.",
        executor=_oracle_detail_check,
    ))

    # -------------------------------------------------------------------------
    # Wilderness actions
    # -------------------------------------------------------------------------
    registry.register(ActionSpec(
        id="wilderness:travel",
        label="Travel to hex",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        params_schema={
            "hex_id": {"type": "string", "required": True},
        },
        help="Travel to an adjacent hex.",
        executor=lambda dm, p: dm.travel_to_hex(p.get("hex_id", "")),
    ))

    def _wilderness_look_around(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Survey surroundings for hints and landmarks."""
        hex_id = p.get("hex_id") or dm.hex_crawl.current_hex_id
        try:
            hints = dm.hex_crawl.get_sensory_hints(hex_id)
        except Exception:
            hints = []
        try:
            overview = dm.hex_crawl.get_hex_overview(hex_id)
            visible = getattr(overview, "visible_locations", []) or []
        except Exception:
            visible = dm.hex_crawl.get_visible_pois(hex_id)

        lines = [f"Location: {hex_id}"]
        if hints:
            lines.append("Sensory hints:")
            lines.extend([f"- {h}" for h in hints[:6]])
        if visible:
            lines.append("Visible locations:")
            for v in visible[:6]:
                if isinstance(v, dict):
                    t = v.get("type", "location")
                    b = v.get("brief")
                    lines.append(f"- {t}" + (f": {b}" if b else ""))
                else:
                    lines.append(f"- {v}")
        return {"success": True, "message": "\n".join(lines)}

    registry.register(ActionSpec(
        id="wilderness:look_around",
        label="Look around",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="Survey your surroundings for sensory hints and visible landmarks.",
        executor=_wilderness_look_around,
    ))

    def _wilderness_search_hex(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Search the current hex thoroughly."""
        hex_id = p.get("hex_id") or dm.hex_crawl.current_hex_id
        result = dm.hex_crawl.search_hex(hex_id)
        return {"success": True, "message": result.get("message", "Searched the hex.")}

    registry.register(ActionSpec(
        id="wilderness:search_hex",
        label="Search hex thoroughly",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="Spend time searching the current hex for hidden features.",
        executor=_wilderness_search_hex,
    ))

    def _wilderness_forage(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Forage for food/water."""
        character_id = p.get("character_id")
        rr = dm.hex_crawl.handle_player_action("forage", character_id)
        msg = rr.narration if rr.narration else "Foraging completed."
        return {"success": True, "message": msg}

    registry.register(ActionSpec(
        id="wilderness:forage",
        label="Forage for food/water",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="Search for edible plants, water sources, or small game.",
        executor=_wilderness_forage,
    ))

    def _wilderness_hunt(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Hunt for larger game."""
        character_id = p.get("character_id")
        rr = dm.hex_crawl.handle_player_action("hunt", character_id)
        msg = rr.narration if rr.narration else "Hunting completed."
        return {"success": True, "message": msg}

    registry.register(ActionSpec(
        id="wilderness:hunt",
        label="Hunt",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="Actively hunt for larger game.",
        executor=_wilderness_hunt,
    ))

    def _wilderness_end_day(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """End travel day and make camp."""
        result = dm.hex_crawl.end_travel_day()
        return {"success": True, "message": result.get("message", "Ended the travel day.")}

    registry.register(ActionSpec(
        id="wilderness:end_day",
        label="End day / Make camp",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="End the travel day and make camp.",
        executor=_wilderness_end_day,
    ))

    def _wilderness_approach_poi(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Approach a point of interest."""
        hex_id = p.get("hex_id") or dm.hex_crawl.current_hex_id
        poi_index = int(p.get("poi_index", 0))
        result = dm.hex_crawl.approach_poi(hex_id, poi_index)
        return {"success": True, "message": result.get("message", "You approach the location.")}

    registry.register(ActionSpec(
        id="wilderness:approach_poi",
        label="Approach POI",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        params_schema={
            "hex_id": {"type": "string", "required": False},
        },
        help="Cautiously approach a point of interest in the hex.",
        executor=_wilderness_approach_poi,
    ))

    def _wilderness_enter_poi(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Enter a point of interest."""
        hex_id = p.get("hex_id") or dm.hex_crawl.current_hex_id
        result = dm.hex_crawl.enter_poi(hex_id)
        if result.get("requires_entry_check"):
            return {"success": False, "message": result.get("message", "Entry requires conditions.")}
        return {"success": True, "message": result.get("message", "You enter.")}

    registry.register(ActionSpec(
        id="wilderness:enter_poi",
        label="Enter POI",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="Enter a point of interest (settlement, dungeon entrance, etc.).",
        executor=_wilderness_enter_poi,
    ))

    def _wilderness_leave_poi(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Leave the current point of interest."""
        hex_id = p.get("hex_id") or dm.hex_crawl.current_hex_id
        result = dm.hex_crawl.leave_poi(hex_id)
        return {"success": True, "message": result.get("message", "You depart.")}

    registry.register(ActionSpec(
        id="wilderness:leave_poi",
        label="Leave POI",
        category=ActionCategory.WILDERNESS,
        requires_state="wilderness_travel",
        help="Leave the current point of interest.",
        executor=_wilderness_leave_poi,
    ))

    # -------------------------------------------------------------------------
    # Dungeon actions
    # -------------------------------------------------------------------------
    def _make_dungeon_executor(action_type_name: str):
        """Factory for dungeon action executors."""
        def executor(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
            from src.dungeon.dungeon_engine import DungeonActionType
            action = getattr(DungeonActionType, action_type_name)
            turn = dm.dungeon.execute_turn(action, p or None)
            messages = []
            for m in (turn.messages or []):
                messages.append(m)
            for w in (turn.warnings or []):
                messages.append(f"Warning: {w}")
            msg = "\n".join(messages) if messages else turn.action_result.get("message", "Action completed.")
            return {"success": True, "message": msg}
        return executor

    registry.register(ActionSpec(
        id="dungeon:move",
        label="Move",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        params_schema={
            "direction": {"type": "string", "required": False},
            "door_index": {"type": "integer", "required": False},
        },
        help="Move through a door or passage.",
        executor=_make_dungeon_executor("MOVE"),
    ))

    registry.register(ActionSpec(
        id="dungeon:search",
        label="Search the area",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        help="Search the current room for hidden features.",
        executor=_make_dungeon_executor("SEARCH"),
    ))

    registry.register(ActionSpec(
        id="dungeon:listen",
        label="Listen at door",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        params_schema={
            "door_index": {"type": "integer", "required": False},
        },
        help="Listen for sounds beyond a door.",
        executor=_make_dungeon_executor("LISTEN"),
    ))

    registry.register(ActionSpec(
        id="dungeon:open_door",
        label="Open door",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        params_schema={
            "door_index": {"type": "integer", "required": False},
        },
        help="Attempt to open a door.",
        executor=_make_dungeon_executor("OPEN_DOOR"),
    ))

    registry.register(ActionSpec(
        id="dungeon:pick_lock",
        label="Pick lock",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        params_schema={
            "door_index": {"type": "integer", "required": False},
        },
        safe_to_execute=False,
        help="Attempt to pick a lock (requires thief skills).",
        executor=_make_dungeon_executor("PICK_LOCK"),
    ))

    registry.register(ActionSpec(
        id="dungeon:disarm_trap",
        label="Disarm trap",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        safe_to_execute=False,
        help="Attempt to disarm a detected trap.",
        executor=_make_dungeon_executor("DISARM_TRAP"),
    ))

    registry.register(ActionSpec(
        id="dungeon:rest",
        label="Short rest",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        help="Take a short rest to recover.",
        executor=_make_dungeon_executor("REST"),
    ))

    registry.register(ActionSpec(
        id="dungeon:map",
        label="Update map",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        help="Update the party's map with explored areas.",
        executor=_make_dungeon_executor("MAP"),
    ))

    registry.register(ActionSpec(
        id="dungeon:fast_travel",
        label="Fast travel",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        params_schema={
            "room_id": {"type": "string", "required": True},
        },
        help="Quickly travel to a previously explored room.",
        executor=_make_dungeon_executor("FAST_TRAVEL"),
    ))

    def _dungeon_exit(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Exit the dungeon."""
        result = dm.dungeon.exit_dungeon()
        return {"success": True, "message": result.get("message", "Exited dungeon.")}

    registry.register(ActionSpec(
        id="dungeon:exit",
        label="Exit dungeon",
        category=ActionCategory.DUNGEON,
        requires_state="dungeon_exploration",
        executor=_dungeon_exit,
        help="Leave the dungeon and return to wilderness.",
    ))

    # -------------------------------------------------------------------------
    # Encounter actions
    # -------------------------------------------------------------------------
    registry.register(ActionSpec(
        id="encounter:parley",
        label="Attempt to parley",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        help="Try to communicate with the encountered creatures.",
    ))

    registry.register(ActionSpec(
        id="encounter:flee",
        label="Flee",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        safe_to_execute=False,
        help="Attempt to flee from the encounter.",
    ))

    registry.register(ActionSpec(
        id="encounter:attack",
        label="Attack",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        safe_to_execute=False,
        help="Initiate combat with the encountered creatures.",
    ))

    registry.register(ActionSpec(
        id="encounter:wait",
        label="Wait and observe",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        help="Wait and observe the creatures' behavior.",
    ))

    # -------------------------------------------------------------------------
    # Settlement actions
    # -------------------------------------------------------------------------
    registry.register(ActionSpec(
        id="settlement:explore",
        label="Explore the settlement",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Walk around and explore the settlement.",
    ))

    registry.register(ActionSpec(
        id="settlement:visit_inn",
        label="Visit the inn",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Go to the local inn for rest and rumors.",
    ))

    registry.register(ActionSpec(
        id="settlement:visit_market",
        label="Visit the market",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Browse the local market for goods.",
    ))

    registry.register(ActionSpec(
        id="settlement:talk_npc",
        label="Talk to NPC",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        params_schema={
            "npc_id": {"type": "string", "required": False},
        },
        help="Speak with a local NPC.",
    ))

    registry.register(ActionSpec(
        id="settlement:leave",
        label="Leave settlement",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Leave the settlement and return to wilderness.",
    ))

    # -------------------------------------------------------------------------
    # Downtime actions
    # -------------------------------------------------------------------------
    registry.register(ActionSpec(
        id="downtime:rest",
        label="Rest for the day",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="Spend a day resting and recovering.",
    ))

    registry.register(ActionSpec(
        id="downtime:train",
        label="Train / Practice",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="Spend time training skills or practicing.",
    ))

    registry.register(ActionSpec(
        id="downtime:research",
        label="Research",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="Research lore, magic, or local information.",
    ))

    registry.register(ActionSpec(
        id="downtime:craft",
        label="Craft item",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="Spend time crafting an item.",
    ))

    registry.register(ActionSpec(
        id="downtime:end",
        label="End downtime",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="End the downtime period.",
    ))

    return registry


# Global default registry instance
_default_registry: Optional[ActionRegistry] = None


def get_default_registry() -> ActionRegistry:
    """Get the default action registry (singleton)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = _create_default_registry()
    return _default_registry


def reset_registry() -> None:
    """Reset the default registry (mainly for testing)."""
    global _default_registry
    _default_registry = None
