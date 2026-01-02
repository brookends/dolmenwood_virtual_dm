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
    SOCIAL = "social"
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

    def is_registered(self, action_id: str) -> bool:
        """
        Check if an action ID is registered and has an executor.

        Returns True if the action exists and can be executed.
        """
        spec = self.get(action_id)
        return spec is not None and spec.executor is not None

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

        from src.oracle.dice_rng_adapter import DiceRngAdapter
        mythic = MythicGME(rng=DiceRngAdapter("OracleFateCheck"))
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
        from src.oracle.dice_rng_adapter import DiceRngAdapter

        mythic = MythicGME(rng=DiceRngAdapter("OracleRandomEvent"))
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
        from src.oracle.dice_rng_adapter import DiceRngAdapter

        mythic = MythicGME(rng=DiceRngAdapter("OracleDetailCheck"))
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
    def _make_encounter_executor(action_name: str):
        """Factory for encounter action executors."""
        def executor(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
            from src.encounter.encounter_engine import EncounterAction
            try:
                action = EncounterAction(action_name)
            except ValueError:
                return {"success": False, "message": f"Unknown encounter action: {action_name}"}
            actor = p.get("actor", "party")
            result = dm.encounter.execute_action(action, actor=actor)
            messages = [m for m in (result.messages or [])]
            return {
                "success": True,
                "message": "\n".join(messages) if messages else f"Executed {action_name}.",
            }
        return executor

    registry.register(ActionSpec(
        id="encounter:parley",
        label="Attempt to parley",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        help="Try to communicate with the encountered creatures.",
        executor=_make_encounter_executor("parley"),
    ))

    registry.register(ActionSpec(
        id="encounter:flee",
        label="Flee",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        safe_to_execute=False,
        help="Attempt to flee from the encounter.",
        executor=_make_encounter_executor("evasion"),
    ))

    registry.register(ActionSpec(
        id="encounter:attack",
        label="Attack",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        safe_to_execute=False,
        help="Initiate combat with the encountered creatures.",
        executor=_make_encounter_executor("attack"),
    ))

    registry.register(ActionSpec(
        id="encounter:wait",
        label="Wait and observe",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        help="Wait and observe the creatures' behavior.",
        executor=_make_encounter_executor("wait"),
    ))

    # -------------------------------------------------------------------------
    # Settlement actions
    # -------------------------------------------------------------------------
    def _settlement_explore(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """List locations and overview of settlement."""
        result = dm.settlement.execute_action("settlement:list_locations", {})
        return result

    def _settlement_visit_inn(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Visit the inn."""
        result = dm.settlement.handle_player_action("visit inn")
        if isinstance(result, dict):
            return result
        return {"success": True, "message": "Visited the inn."}

    def _settlement_visit_market(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Visit the market."""
        result = dm.settlement.execute_action("settlement:list_services", {})
        return result

    def _settlement_talk_npc(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """
        Talk to an NPC - transitions to SOCIAL_INTERACTION state.

        This uses the same SOCIAL_INTERACTION system as hex NPC conversations,
        ensuring a unified conversation pathway.
        """
        npc_query = p.get("npc_id") or p.get("npc_name", "")
        if not npc_query:
            # List available NPCs
            result = dm.settlement.execute_action("settlement:list_npcs", {})
            return result

        # Get NPC info from settlement engine
        result = dm.settlement.execute_action(
            "settlement:talk",
            {"npc_name": npc_query}
        )

        if not result.get("success"):
            return result

        # Extract NPC information
        npc_info = result.get("npc", {})
        npc_id = npc_info.get("npc_id", npc_query)
        npc_name = npc_info.get("name", npc_query)

        # Get current settlement context
        settlement = dm.settlement.get_active_settlement()
        settlement_id = settlement.settlement_id if settlement else "unknown"
        settlement_name = settlement.name if settlement else "Unknown Settlement"

        # Transition to SOCIAL_INTERACTION state
        dm.controller.transition(
            "initiate_conversation",
            context={
                "npc_id": npc_id,
                "npc_name": npc_name,
                "settlement_id": settlement_id,
                "settlement_name": settlement_name,
                "return_to": "settlement",
                "first_meeting": True,  # TODO: track met NPCs in settlement
                "npc_info": npc_info,
            },
        )

        return {
            "success": True,
            "message": f"You begin a conversation with {npc_name}.",
            "action": "settlement:talk_npc",
            "npc_id": npc_id,
            "npc_name": npc_name,
            "state": "social_interaction",
        }

    def _settlement_leave(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Leave the settlement."""
        result = dm.settlement.execute_action("settlement:leave", {})
        return result

    registry.register(ActionSpec(
        id="settlement:explore",
        label="Explore the settlement",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Walk around and explore the settlement.",
        executor=_settlement_explore,
    ))

    registry.register(ActionSpec(
        id="settlement:visit_inn",
        label="Visit the inn",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Go to the local inn for rest and rumors.",
        executor=_settlement_visit_inn,
    ))

    registry.register(ActionSpec(
        id="settlement:visit_market",
        label="Visit the market",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Browse the local market for goods.",
        executor=_settlement_visit_market,
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
        executor=_settlement_talk_npc,
    ))

    registry.register(ActionSpec(
        id="settlement:leave",
        label="Leave settlement",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        help="Leave the settlement and return to wilderness.",
        executor=_settlement_leave,
    ))

    # -------------------------------------------------------------------------
    # Downtime actions
    # -------------------------------------------------------------------------
    def _downtime_rest(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Rest and recover."""
        result = dm.downtime.handle_player_action("rest")
        if hasattr(result, 'events') and result.events:
            return {"success": result.success, "message": "\n".join(result.events)}
        return {"success": True, "message": "Rested for the day."}

    def _downtime_train(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Train a skill."""
        skill = p.get("skill", "combat")
        result = dm.downtime.handle_player_action(f"train {skill}")
        if hasattr(result, 'events') and result.events:
            return {"success": result.success, "message": "\n".join(result.events)}
        return {"success": True, "message": f"Trained {skill}."}

    def _downtime_research(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Research a topic."""
        topic = p.get("topic", "local lore")
        result = dm.downtime.handle_player_action(f"research {topic}")
        if hasattr(result, 'events') and result.events:
            return {"success": result.success, "message": "\n".join(result.events)}
        return {"success": True, "message": f"Researched {topic}."}

    def _downtime_craft(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Craft an item."""
        # Crafting not fully implemented, return placeholder
        return {
            "success": True,
            "message": "Crafting is not yet fully implemented. Use the oracle to adjudicate outcomes.",
        }

    def _downtime_end(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """End downtime period."""
        result = dm.downtime.end_downtime()
        if isinstance(result, dict) and result.get("error"):
            return {"success": False, "message": result["error"]}
        return {"success": True, "message": "Downtime ended. Returning to exploration."}

    registry.register(ActionSpec(
        id="downtime:rest",
        label="Rest for the day",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="Spend a day resting and recovering.",
        executor=_downtime_rest,
    ))

    registry.register(ActionSpec(
        id="downtime:train",
        label="Train / Practice",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        params_schema={
            "skill": {"type": "string", "required": False},
        },
        help="Spend time training skills or practicing.",
        executor=_downtime_train,
    ))

    registry.register(ActionSpec(
        id="downtime:research",
        label="Research",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        params_schema={
            "topic": {"type": "string", "required": False},
        },
        help="Research lore, magic, or local information.",
        executor=_downtime_research,
    ))

    registry.register(ActionSpec(
        id="downtime:craft",
        label="Craft item",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="Spend time crafting an item.",
        executor=_downtime_craft,
    ))

    registry.register(ActionSpec(
        id="downtime:end",
        label="End downtime",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        help="End the downtime period.",
        executor=_downtime_end,
    ))

    # -------------------------------------------------------------------------
    # Social Interaction actions
    # -------------------------------------------------------------------------
    def _social_say(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Say something to the NPC in conversation."""
        text = p.get("text", "")
        if not text:
            return {
                "success": False,
                "message": "What do you want to say? Provide text parameter.",
            }

        # Check if LLM is available
        if hasattr(dm, 'dm_agent') and dm.dm_agent:
            # LLM can generate dialogue response
            try:
                # Get social context
                context = dm.controller.get_social_context() if hasattr(dm.controller, 'get_social_context') else {}
                npc_name = context.get("npc_name", "the NPC")
                response = f"[LLM would generate {npc_name}'s response to: '{text}']"
                return {"success": True, "message": response}
            except Exception as e:
                return {"success": True, "message": f"Error: {e}. Use oracle to determine NPC response."}
        else:
            # Offline mode - direct to oracle
            return {
                "success": True,
                "message": (
                    f"[Offline mode] You say: '{text}'\n"
                    "Use oracle:fate_check to determine NPC reaction, or "
                    "oracle:detail_check for their response theme."
                ),
            }

    def _social_end(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """End the conversation and return to previous state."""
        prev_state = dm.controller.state_machine.previous_state
        if not prev_state:
            return {"success": False, "message": "No previous state to return to."}

        from src.game_state.state_machine import GameState

        # Determine correct trigger based on return state
        trigger_map = {
            GameState.WILDERNESS_TRAVEL: "conversation_end_wilderness",
            GameState.SETTLEMENT_EXPLORATION: "conversation_end_settlement",
            GameState.DUNGEON_EXPLORATION: "conversation_end_dungeon",
            GameState.FAIRY_ROAD_TRAVEL: "conversation_end_fairy_road",
            GameState.ENCOUNTER: "conversation_end_wilderness",  # fallback
        }

        trigger = trigger_map.get(prev_state, "conversation_end_wilderness")

        try:
            dm.controller.transition(trigger)
            return {
                "success": True,
                "message": f"Conversation ended. Returned to {prev_state.value}.",
            }
        except Exception as e:
            return {"success": False, "message": f"Could not end conversation: {e}"}

    def _social_oracle_question(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Ask the oracle about the NPC's response or attitude."""
        question = p.get("question", "How does the NPC react?")
        # Route to oracle fate check
        from src.conversation.conversation_facade import _mythic_fate_check
        return _mythic_fate_check(dm, {"question": question, "modifier": 0})

    registry.register(ActionSpec(
        id="social:say",
        label="Say something",
        category=ActionCategory.SOCIAL,
        requires_state="social_interaction",
        params_schema={
            "text": {"type": "string", "required": True},
        },
        help="Say something to the NPC you're conversing with.",
        executor=_social_say,
    ))

    registry.register(ActionSpec(
        id="social:end",
        label="End conversation",
        category=ActionCategory.SOCIAL,
        requires_state="social_interaction",
        help="End the conversation and return to previous activity.",
        executor=_social_end,
    ))

    registry.register(ActionSpec(
        id="social:oracle_question",
        label="Ask oracle about NPC",
        category=ActionCategory.SOCIAL,
        requires_state="social_interaction",
        params_schema={
            "question": {"type": "string", "required": False},
        },
        help="Use the oracle to determine NPC reactions or responses.",
        executor=_social_oracle_question,
    ))

    # -------------------------------------------------------------------------
    # Meta: Factions
    # -------------------------------------------------------------------------
    def _meta_factions(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Get faction status summary."""
        if not hasattr(dm, "factions") or not dm.factions:
            return {"success": True, "message": "Faction system not initialized."}
        from src.factions import get_factions_summary
        summary = get_factions_summary(dm.factions)
        return {"success": True, "message": summary}

    registry.register(ActionSpec(
        id="meta:factions",
        label="Show faction status",
        category=ActionCategory.META,
        help="Display faction levels, territory, active actions, and news.",
        executor=_meta_factions,
    ))

    # -------------------------------------------------------------------------
    # Meta: Roll Log / Observability
    # -------------------------------------------------------------------------
    def _meta_roll_log(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Get recent dice roll events."""
        from src.data_models import DiceRoller
        dice = DiceRoller()
        log = dice.get_roll_log()

        # Get last N entries
        limit = p.get("limit", 20)
        recent = log[-limit:] if len(log) > limit else log

        if not recent:
            return {
                "success": True,
                "message": "No dice rolls recorded yet.",
            }

        # Format the output - DiceResult is a dataclass
        lines = ["Recent Dice Rolls:", ""]
        for entry in recent:
            reason = getattr(entry, 'reason', 'Unknown')
            notation = getattr(entry, 'notation', '?')
            total = getattr(entry, 'total', '?')
            lines.append(f"  {reason}: {notation} = {total}")

        return {
            "success": True,
            "message": "\n".join(lines),
            "roll_log": [
                {
                    "reason": getattr(e, 'reason', ''),
                    "notation": getattr(e, 'notation', ''),
                    "rolls": getattr(e, 'rolls', []),
                    "total": getattr(e, 'total', 0),
                }
                for e in recent
            ],
        }

    def _meta_export_run_log(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Export the full run log to JSON."""
        import json
        import os
        from datetime import datetime
        from src.data_models import DiceRoller

        dice = DiceRoller()
        log = dice.get_roll_log()

        # Create export directory if needed
        save_dir = p.get("save_dir", "saves")
        os.makedirs(save_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"run_log_{timestamp}.json"
        filepath = os.path.join(save_dir, filename)

        # Convert DiceResult objects to dicts
        log_dicts = [
            {
                "reason": getattr(e, 'reason', ''),
                "notation": getattr(e, 'notation', ''),
                "rolls": getattr(e, 'rolls', []),
                "total": getattr(e, 'total', 0),
                "timestamp": str(getattr(e, 'timestamp', '')),
            }
            for e in log
        ]

        # Prepare export data
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "total_rolls": len(log),
            "roll_log": log_dicts,
        }

        # Write to file
        try:
            with open(filepath, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            return {
                "success": True,
                "message": f"Run log exported to: {filepath}",
                "filepath": filepath,
                "total_rolls": len(log),
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to export run log: {e}",
            }

    registry.register(ActionSpec(
        id="meta:roll_log",
        label="Show recent dice rolls",
        category=ActionCategory.META,
        params_schema={
            "limit": {"type": "integer", "required": False, "default": 20},
        },
        help="Display recent dice roll events for observability.",
        executor=_meta_roll_log,
    ))

    # Note: _meta_export_run_log actually exports the DiceRoller roll log
    # Register it as meta:export_roll_log for correct naming
    registry.register(ActionSpec(
        id="meta:export_roll_log",
        label="Export dice roll log",
        category=ActionCategory.META,
        params_schema={
            "save_dir": {"type": "string", "required": False, "default": "saves"},
        },
        help="Export the dice roll log to a JSON file.",
        executor=_meta_export_run_log,
    ))

    # -------------------------------------------------------------------------
    # Meta: RunLog (full event log) - Phase 5
    # -------------------------------------------------------------------------
    def _meta_run_log(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Show formatted RunLog events."""
        from src.observability.run_log import get_run_log

        run_log = get_run_log()
        limit = p.get("limit", 50)

        if run_log.get_event_count() == 0:
            return {
                "success": True,
                "message": "No events recorded in RunLog yet.",
            }

        formatted = run_log.format_log(max_events=limit)
        return {
            "success": True,
            "message": formatted,
            "event_count": run_log.get_event_count(),
        }

    def _meta_export_actual_run_log(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Export the actual RunLog (full event log) to JSON."""
        import os
        from datetime import datetime
        from src.observability.run_log import get_run_log

        run_log = get_run_log()

        # Create export directory if needed
        save_dir = p.get("save_dir", "saves")
        os.makedirs(save_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"run_log_{timestamp}.json"
        filepath = os.path.join(save_dir, filename)

        try:
            run_log.save(filepath)
            summary = run_log.get_summary()
            return {
                "success": True,
                "message": f"RunLog exported to: {filepath}",
                "filepath": filepath,
                "summary": summary,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to export RunLog: {e}",
            }

    registry.register(ActionSpec(
        id="meta:run_log",
        label="Show event log (RunLog)",
        category=ActionCategory.META,
        params_schema={
            "limit": {"type": "integer", "required": False, "default": 50},
        },
        help="Display recent events from the RunLog (transitions, rolls, time steps).",
        executor=_meta_run_log,
    ))

    registry.register(ActionSpec(
        id="meta:export_run_log",
        label="Export full RunLog",
        category=ActionCategory.META,
        params_schema={
            "save_dir": {"type": "string", "required": False, "default": "saves"},
        },
        help="Export the complete RunLog (all events) to a JSON file.",
        executor=_meta_export_actual_run_log,
    ))

    # -------------------------------------------------------------------------
    # Meta: Replay status - Phase 5.3
    # -------------------------------------------------------------------------
    def _meta_replay_status(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Show current replay mode status."""
        from src.data_models import DiceRoller

        # Check if DiceRoller is in replay mode
        if hasattr(DiceRoller, '_replay_session') and DiceRoller._replay_session is not None:
            return {
                "success": True,
                "message": "Replay mode: ACTIVE - DiceRoller is using recorded roll sequence.",
                "replay_active": True,
            }
        else:
            return {
                "success": True,
                "message": (
                    "Replay mode: NOT IMPLEMENTED\n"
                    "Replay functionality is not yet fully implemented.\n"
                    "RunLog can record events but replay requires additional work."
                ),
                "replay_active": False,
            }

    registry.register(ActionSpec(
        id="meta:replay_status",
        label="Check replay mode status",
        category=ActionCategory.META,
        help="Check if replay mode is active and what state it's in.",
        executor=_meta_replay_status,
    ))

    # -------------------------------------------------------------------------
    # Legacy aliases: encounter:action, settlement:action, downtime:action
    # These forward to existing engine methods for backward compatibility
    # -------------------------------------------------------------------------
    def _encounter_action(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Execute a generic encounter action."""
        from src.encounter.encounter_engine import EncounterAction

        action_str = p.get("action", "")
        actor = p.get("actor", "party")

        if not action_str:
            return {"success": False, "message": "No action specified for encounter."}

        try:
            action = EncounterAction(action_str)
        except ValueError:
            return {"success": False, "message": f"Unknown encounter action: {action_str}"}

        result = dm.encounter.execute_action(action, actor=actor)
        messages = [m for m in (result.messages or [])]
        return {
            "success": True,
            "message": "\n".join(messages) if messages else f"Executed {action_str}.",
        }

    def _settlement_action(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Execute a generic settlement action."""
        text = p.get("text", "")
        character_id = p.get("character_id", "party")

        if not text:
            return {"success": False, "message": "No action text specified."}

        rr = dm.settlement.handle_player_action(text, character_id)
        if isinstance(rr, dict):
            return {"success": True, "message": rr.get("message", "Action resolved.")}
        if hasattr(rr, 'narration') and rr.narration:
            return {"success": True, "message": rr.narration}
        return {"success": True, "message": "Resolved."}

    def _downtime_action(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Execute a generic downtime action."""
        text = p.get("text", "")
        character_id = p.get("character_id", "party")

        if not text:
            return {"success": False, "message": "No action text specified."}

        rr = dm.downtime.handle_player_action(text, character_id)
        if hasattr(rr, 'events') and rr.events:
            return {"success": True, "message": "\n".join(rr.events)}
        return {"success": True, "message": "Resolved."}

    registry.register(ActionSpec(
        id="encounter:action",
        label="Encounter action",
        category=ActionCategory.ENCOUNTER,
        requires_state="encounter",
        params_schema={
            "action": {"type": "string", "required": True},
            "actor": {"type": "string", "required": False},
        },
        help="Execute a generic encounter action (parley, evasion, attack, wait).",
        executor=_encounter_action,
    ))

    registry.register(ActionSpec(
        id="settlement:action",
        label="Settlement action",
        category=ActionCategory.SETTLEMENT,
        requires_state="settlement_exploration",
        params_schema={
            "text": {"type": "string", "required": True},
            "character_id": {"type": "string", "required": False},
        },
        help="Execute a freeform settlement action.",
        executor=_settlement_action,
    ))

    registry.register(ActionSpec(
        id="downtime:action",
        label="Downtime action",
        category=ActionCategory.DOWNTIME,
        requires_state="downtime",
        params_schema={
            "text": {"type": "string", "required": True},
            "character_id": {"type": "string", "required": False},
        },
        help="Execute a freeform downtime action.",
        executor=_downtime_action,
    ))

    # -------------------------------------------------------------------------
    # Fairy Road actions - Phase 4: Register executors
    # -------------------------------------------------------------------------
    def _fairy_road_enter(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Enter a fairy road."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        road_id = p.get("road_id", "")
        hex_id = p.get("hex_id") or dm.controller.party_state.location.location_id
        destination = p.get("destination_hex_id")

        result = engine.enter_fairy_road(road_id, hex_id, destination)
        return {
            "success": result.success,
            "message": "\n".join(result.messages),
        }

    def _fairy_road_travel_segment(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Travel one segment on the fairy road."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        if not engine.is_active():
            return {"success": False, "message": "Not on a fairy road."}

        result = engine.travel_segment()
        msg = "\n".join(result.messages)
        if result.encounter_triggered:
            msg += "\nAn encounter awaits! Choose to face it or try to evade."
        return {"success": True, "message": msg}

    def _fairy_road_resolve_encounter(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Resolve a fairy road encounter."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        if not engine.is_active():
            return {"success": False, "message": "Not on a fairy road."}

        result = engine.trigger_encounter_transition()
        return {
            "success": result.get("success", False),
            "message": result.get("message", "Encounter begins!"),
        }

    def _fairy_road_flee_encounter(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Flee from a fairy road encounter."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        if not engine.is_active():
            return {"success": False, "message": "Not on a fairy road."}

        result = engine.resume_after_encounter()
        messages = ["You evade the encounter and continue on the road..."]
        messages.extend(result.messages)
        return {"success": True, "message": "\n".join(messages)}

    def _fairy_road_explore_location(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Explore a location on the fairy road."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        if not engine.is_active():
            return {"success": False, "message": "Not on a fairy road."}

        state = engine.get_travel_state()
        if state and state.last_location_entry:
            return {"success": True, "message": f"Location: {state.last_location_entry.summary}"}
        return {"success": False, "message": "No location to explore."}

    def _fairy_road_continue_past(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Continue past a location on the fairy road."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        if not engine.is_active():
            return {"success": False, "message": "Not on a fairy road."}

        result = engine.resume_after_location()
        return {"success": True, "message": "\n".join(result.messages)}

    def _fairy_road_exit(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Exit the fairy road."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        if not engine.is_active():
            return {"success": False, "message": "Not on a fairy road."}

        exit_hex = p.get("exit_hex_id")
        result = engine.exit_fairy_road(exit_hex)

        msg = "\n".join(result.messages)
        if result.success and result.mortal_time_passed:
            msg += f"\nTime passed in mortal world: {result.mortal_time_passed}"
        return {"success": result.success, "message": msg}

    def _fairy_road_stray(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Intentionally stray from the fairy road path."""
        return {
            "success": True,
            "message": (
                "You intentionally leave the path...\n"
                "This is dangerous and not yet fully implemented."
            ),
        }

    def _fairy_road_status(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Show fairy road travel status."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        summary = engine.get_travel_summary()
        if not summary.get("active"):
            return {"success": True, "message": "Not currently on a fairy road."}

        lines = [
            f"Road: {summary.get('road_name', 'Unknown')}",
            f"Phase: {summary.get('phase', 'unknown')}",
            f"Segment: {summary.get('segment', 0)}/{summary.get('total_segments', 0)}",
            f"Entry: {summary.get('entry_door', 'Unknown')}",
        ]
        if summary.get("destination_door"):
            lines.append(f"Destination: {summary.get('destination_door')}")
        lines.append(f"Subjective time: {summary.get('subjective_turns', 0)} turns")
        lines.append(f"Encounters: {summary.get('encounters_triggered', 0)}")

        return {"success": True, "message": "\n".join(lines)}

    def _fairy_road_find_door(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Find fairy doors in the current hex."""
        from src.fairy_roads.fairy_road_engine import get_fairy_road_engine
        engine = get_fairy_road_engine(dm.controller)

        hex_id = dm.controller.party_state.location.location_id
        doors = engine.can_enter_from_hex(hex_id)

        if not doors:
            return {"success": True, "message": f"No fairy doors found in hex {hex_id}."}

        lines = [f"Fairy doors in hex {hex_id}:"]
        for door in doors:
            lines.append(f"  - {door.get('door_name')} → {door.get('road_name')}")

        return {"success": True, "message": "\n".join(lines)}

    registry.register(ActionSpec(
        id="fairy_road:enter",
        label="Enter fairy road",
        category=ActionCategory.TRANSITION,
        params_schema={
            "road_id": {"type": "string", "required": True},
            "hex_id": {"type": "string", "required": False},
            "destination_hex_id": {"type": "string", "required": False},
        },
        help="Enter a fairy road from the current hex.",
        executor=_fairy_road_enter,
    ))

    registry.register(ActionSpec(
        id="fairy_road:travel_segment",
        label="Travel one segment",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        help="Travel one segment along the fairy road.",
        executor=_fairy_road_travel_segment,
    ))

    registry.register(ActionSpec(
        id="fairy_road:resolve_encounter",
        label="Face encounter",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        help="Face the encounter on the fairy road.",
        executor=_fairy_road_resolve_encounter,
    ))

    registry.register(ActionSpec(
        id="fairy_road:flee_encounter",
        label="Evade encounter",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        help="Try to evade the encounter on the fairy road.",
        executor=_fairy_road_flee_encounter,
    ))

    registry.register(ActionSpec(
        id="fairy_road:explore_location",
        label="Explore location",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        help="Explore a discovered location on the fairy road.",
        executor=_fairy_road_explore_location,
    ))

    registry.register(ActionSpec(
        id="fairy_road:continue_past",
        label="Continue past location",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        help="Leave the location and continue traveling.",
        executor=_fairy_road_continue_past,
    ))

    registry.register(ActionSpec(
        id="fairy_road:exit",
        label="Exit fairy road",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        params_schema={
            "exit_hex_id": {"type": "string", "required": False},
        },
        help="Exit the fairy road.",
        executor=_fairy_road_exit,
    ))

    registry.register(ActionSpec(
        id="fairy_road:stray",
        label="Stray from path",
        category=ActionCategory.TRANSITION,
        requires_state="fairy_road_travel",
        safe_to_execute=False,
        help="Intentionally leave the fairy road path (dangerous).",
        executor=_fairy_road_stray,
    ))

    registry.register(ActionSpec(
        id="fairy_road:status",
        label="Show travel status",
        category=ActionCategory.META,
        help="Show current fairy road travel status.",
        executor=_fairy_road_status,
    ))

    registry.register(ActionSpec(
        id="fairy_road:find_door",
        label="Find fairy doors",
        category=ActionCategory.META,
        help="Search for fairy doors in the current hex.",
        executor=_fairy_road_find_door,
    ))

    # -------------------------------------------------------------------------
    # Combat legacy actions - Phase 4
    # -------------------------------------------------------------------------
    def _combat_cast_spell(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Cast a spell during combat."""
        character_id = p.get("character_id", "")
        spell_name = p.get("spell_name", "")
        target = p.get("target")

        if not spell_name:
            return {"success": False, "message": "No spell specified."}

        # Placeholder - spell casting requires more infrastructure
        return {
            "success": True,
            "message": (
                f"Spell casting: {spell_name}\n"
                "Full spell resolution is not yet implemented in combat."
            ),
        }

    registry.register(ActionSpec(
        id="combat:cast_spell",
        label="Cast spell",
        category=ActionCategory.ENCOUNTER,
        requires_state="combat",
        params_schema={
            "character_id": {"type": "string", "required": False},
            "spell_name": {"type": "string", "required": True},
            "target": {"type": "string", "required": False},
        },
        safe_to_execute=False,
        help="Cast a prepared spell during combat.",
        executor=_combat_cast_spell,
    ))

    # -------------------------------------------------------------------------
    # Party utilities - Phase 4
    # -------------------------------------------------------------------------
    def _party_light(dm: "VirtualDM", p: dict[str, Any]) -> dict[str, Any]:
        """Activate a light source."""
        from src.data_models import LightSourceType

        raw = (p.get("light_source") or "torch").lower()
        ls = {
            "torch": LightSourceType.TORCH,
            "lantern": LightSourceType.LANTERN,
        }.get(raw, LightSourceType.TORCH)

        try:
            dm.controller.activate_light_source(ls)
            ps = dm.controller.party_state
            return {
                "success": True,
                "message": f"Light source set to {ls.value} (remaining turns: {ps.light_remaining_turns}).",
            }
        except Exception as e:
            return {"success": False, "message": f"Couldn't set light source: {e}"}

    registry.register(ActionSpec(
        id="party:light",
        label="Light source",
        category=ActionCategory.META,
        params_schema={
            "light_source": {"type": "string", "required": False},
        },
        help="Activate a torch or lantern.",
        executor=_party_light,
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
