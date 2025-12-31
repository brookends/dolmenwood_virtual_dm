"""src.conversation.suggestion_builder

Build a ranked list of UI-clickable suggestions that feel *Dolmenwood-native*.

The ranking heuristics are intentionally simple and transparent:
- **Urgent constraints** first (no light, rest due, traps detected, no travel points).
- Then **high-frequency procedures** (move/search/listen/approach POI/parley).
- Then **nice-to-have** utilities (map, oracle, state transitions).

This module is UI-agnostic:
- CLI renders as a numbered list
- Foundry later renders as buttons

Important: These suggestions are meant to *help the player*; they are not an
exhaustive action list and they should avoid spoilers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.main import VirtualDM

from src.game_state.state_machine import GameState
from src.dungeon.dungeon_engine import DungeonActionType, DoorState
from src.encounter.encounter_engine import EncounterAction

from src.conversation.types import SuggestedAction


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------

@dataclass
class _Candidate:
    action: SuggestedAction
    score: float


def _clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def _default_character_id(dm: VirtualDM) -> str:
    chars = dm.controller.get_active_characters()
    if chars:
        return chars[0].character_id
    all_chars = dm.controller.get_all_characters()
    return all_chars[0].character_id if all_chars else "party"


def _current_hex_id(dm: VirtualDM) -> str:
    return dm.controller.party_state.location.location_id


def _has_light(dm: VirtualDM) -> bool:
    ps = dm.controller.party_state
    return bool(ps.active_light_source) and ps.light_remaining_turns > 0


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def build_suggestions(dm: VirtualDM, *, character_id: Optional[str] = None, limit: int = 9) -> list[SuggestedAction]:
    """Return ranked suggestions for the current state."""

    cid = character_id or _default_character_id(dm)
    state = dm.current_state

    candidates: list[_Candidate] = []

    # Always-available utility: save/status (low priority; not state-advancing)
    candidates.append(
        _Candidate(
            SuggestedAction(
                id="meta:status",
                label="Show status / summary",
                safe_to_execute=True,
                help="Print a compact summary of current mode, time, and party state.",
            ),
            score=5,
        )
    )

    # ------------------------------------------------------------------
    # Mode-specific suggestions
    # ------------------------------------------------------------------

    if state == GameState.DUNGEON_EXPLORATION:
        candidates.extend(_dungeon_suggestions(dm, cid))

    elif state == GameState.WILDERNESS_TRAVEL:
        candidates.extend(_wilderness_suggestions(dm, cid))

    elif state == GameState.ENCOUNTER:
        candidates.extend(_encounter_suggestions(dm))

    elif state == GameState.SETTLEMENT_EXPLORATION:
        candidates.extend(_settlement_suggestions(dm, cid))

    elif state == GameState.DOWNTIME:
        candidates.extend(_downtime_suggestions(dm, cid))

    # ------------------------------------------------------------------
    # Cross-cutting: Mythic oracle (kept visible but not dominant)
    # ------------------------------------------------------------------

    candidates.extend(_oracle_suggestions())

    # ------------------------------------------------------------------
    # Optional: state machine triggers (developer/debug oriented)
    # ------------------------------------------------------------------

    try:
        triggers = dm.get_valid_actions()
    except Exception:
        triggers = []

    for t in triggers:
        candidates.append(
            _Candidate(
                SuggestedAction(
                    id=f"transition:{t}",
                    label=f"Transition: {t}",
                    safe_to_execute=False,
                    help="State machine trigger (debug/tooling).",
                ),
                score=1,
            )
        )

    # Sort + dedupe by id (keep best score)
    best: dict[str, _Candidate] = {}
    for c in candidates:
        prev = best.get(c.action.id)
        if not prev or c.score > prev.score:
            best[c.action.id] = c

    ranked = sorted(best.values(), key=lambda c: c.score, reverse=True)
    return [c.action for c in ranked[: _clamp(limit, 3, 20)]]


# -----------------------------------------------------------------------------
# Dungeon suggestions
# -----------------------------------------------------------------------------


def _dungeon_suggestions(dm: VirtualDM, cid: str) -> list[_Candidate]:
    out: list[_Candidate] = []
    ps = dm.controller.party_state
    ds = dm.dungeon.get_dungeon_state()
    room = dm.dungeon.get_current_room()

    # Light is existential in a dungeon
    if not _has_light(dm):
        out.append(
            _Candidate(
                SuggestedAction(
                    id="party:light",
                    label="Light a torch / lantern (keep the darkness back)",
                    params_schema={
                        "type": "object",
                        "properties": {
                            "light_source": {"type": "string", "enum": ["torch", "lantern"]}
                        },
                        "required": ["light_source"],
                    },
                    params={"light_source": "torch"},
                    safe_to_execute=True,
                    help="Dungeon exploration assumes a lit light source. This sets party_state.active_light_source.",
                ),
                score=100,
            )
        )
    else:
        # If the light is about to die, warn early
        if ps.light_remaining_turns <= 2:
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="party:light",
                        label=f"Refresh light source (only {ps.light_remaining_turns} Turn(s) left)",
                        params_schema={
                            "type": "object",
                            "properties": {
                                "light_source": {"type": "string", "enum": ["torch", "lantern"]}
                            },
                            "required": ["light_source"],
                        },
                        params={"light_source": "torch"},
                        safe_to_execute=False,
                        help="If you have spare torches/lantern oil, swap now to avoid fighting in darkness.",
                    ),
                    score=86,
                )
            )

    # Mandatory rest every 5 Turns (engine tracks it)
    try:
        summary = dm.dungeon.get_exploration_summary()
        needs_rest = bool(summary.get("needs_rest"))
        turns_since_rest = int(summary.get("turns_since_rest", 0))
    except Exception:
        needs_rest = False
        turns_since_rest = 0

    if needs_rest:
        out.append(
            _Candidate(
                SuggestedAction(
                    id="dungeon:rest",
                    label="Spend 1 Turn resting (required after 5 Turns)",
                    safe_to_execute=True,
                    help="Resets the dungeon rest clock; still consumes a Turn and can trigger encounters.",
                ),
                score=95,
            )
        )
    else:
        # Keep visible but lower
        out.append(
            _Candidate(
                SuggestedAction(
                    id="dungeon:rest",
                    label=f"Rest (turns since rest: {turns_since_rest}/5)",
                    safe_to_execute=True,
                    help="Sometimes worth it to reduce risk of exhaustion if you’re pushing your luck.",
                ),
                score=35,
            )
        )

    # Traps: if detected, disarm becomes high priority
    if room and getattr(room, "hazards", None):
        detected = [h for h in room.hazards if getattr(h, "detected", False) and not getattr(h, "disarmed", False)]
        for h in detected[:3]:
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="dungeon:disarm_trap",
                        label=f"Disarm trap: {h.name}",
                        params_schema={
                            "type": "object",
                            "properties": {
                                "hazard_id": {"type": "string"},
                                "character_id": {"type": "string"},
                            },
                            "required": ["hazard_id", "character_id"],
                        },
                        params={"hazard_id": h.hazard_id, "character_id": cid},
                        safe_to_execute=True,
                        help="Spends a Turn attempting to disarm the detected hazard.",
                    ),
                    score=92,
                )
            )

    # Core loop actions: move / listen / open doors / search / map
    if ds and room:
        # Movement: generate one candidate per exit
        for direction, target_room in (room.exits or {}).items():
            door_id = f"{ds.current_room}_{direction}"
            door_state = (room.doors or {}).get(door_id)

            # If door is locked/stuck/barred, suggest opening/picking first
            if door_state in (DoorState.LOCKED, DoorState.STUCK, DoorState.BARRED):
                label_state = door_state.value
                out.append(
                    _Candidate(
                        SuggestedAction(
                            id="dungeon:open_door",
                            label=f"Open/force door {direction.upper()} ({label_state})",
                            params={"direction": direction},
                            safe_to_execute=True,
                            help="Attempts to open/force a blocked door; may create noise.",
                        ),
                        score=84,
                    )
                )
                if door_state == DoorState.LOCKED:
                    out.append(
                        _Candidate(
                            SuggestedAction(
                                id="dungeon:pick_lock",
                                label=f"Pick lock {direction.upper()} (thief tools)",
                                params_schema={
                                    "type": "object",
                                    "properties": {
                                        "door_id": {"type": "string"},
                                        "character_id": {"type": "string"},
                                    },
                                    "required": ["door_id", "character_id"],
                                },
                                params={"door_id": door_id, "character_id": cid},
                                safe_to_execute=True,
                                help="Requires a character; success depends on their abilities.",
                            ),
                            score=80,
                        )
                    )

                # Listening is still useful when blocked
                out.append(
                    _Candidate(
                        SuggestedAction(
                            id="dungeon:listen",
                            label=f"Listen at door {direction.upper()} (1-in-6)",
                            params={"door_id": door_id},
                            safe_to_execute=True,
                            help="Spend 1 Turn listening; may reveal danger beyond.",
                        ),
                        score=72,
                    )
                )
                continue

            # Closed door: suggest opening + listening; moving is possible, but we prioritize door interaction
            if door_state == DoorState.CLOSED:
                out.append(
                    _Candidate(
                        SuggestedAction(
                            id="dungeon:open_door",
                            label=f"Open door {direction.upper()} (quietly if possible)",
                            params={"direction": direction},
                            safe_to_execute=True,
                            help="Opening a door is a classic risk moment; consider listening first.",
                        ),
                        score=78,
                    )
                )
                out.append(
                    _Candidate(
                        SuggestedAction(
                            id="dungeon:listen",
                            label=f"Listen at door {direction.upper()} (1-in-6)",
                            params={"door_id": door_id},
                            safe_to_execute=True,
                            help="Spends 1 Turn; helps avoid walking into trouble.",
                        ),
                        score=74,
                    )
                )

            # Standard move (open passage or already-open door)
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="dungeon:move",
                        label=f"Spend 1 Turn: Move {direction.upper()}",
                        params={"direction": direction},
                        safe_to_execute=True,
                        help="Advances time, consumes light, and can trigger wandering monster checks.",
                    ),
                    score=76,
                )
            )

        # Search is high value if the room hasn’t been searched
        if not getattr(room, "searched", False):
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="dungeon:search",
                        label="Spend 1 Turn: Search for traps/secret doors (2-in-6)",
                        safe_to_execute=True,
                        help="Marks room as searched; may detect hazards and secret doors.",
                    ),
                    score=74,
                )
            )
        else:
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="dungeon:search",
                        label="Search again (slow, but sometimes worth it)",
                        safe_to_execute=True,
                        help="Re-searching is costly; consider only if you have a strong hunch.",
                    ),
                    score=28,
                )
            )

        # Mapping is useful for escape bonuses; bump if no map yet
        if not getattr(ds, "has_map", False):
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="dungeon:map",
                        label="Spend 1 Turn: Map this area (+2 to escape)",
                        safe_to_execute=True,
                        help="Sets has_map=True; improves escape odds later.",
                    ),
                    score=60,
                )
            )

        # Fast travel if known safe path
        if getattr(ds, "known_exit_path", False) and getattr(ds, "safe_path_to_exit", None):
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="dungeon:fast_travel",
                        label="Fast travel along known safe path (accelerate turns)",
                        params={"route": ds.safe_path_to_exit},
                        safe_to_execute=True,
                        help="Consumes multiple Turns quickly; still checks wandering monsters.",
                    ),
                    score=52,
                )
            )

        # Exit dungeon (only sensible if you believe you can reach an exit)
        out.append(
            _Candidate(
                SuggestedAction(
                    id="dungeon:exit",
                    label="Leave the dungeon (return to wilderness)",
                    safe_to_execute=False,
                    help="This should be used when you’re at an exit/entrance; engine currently does not enforce position.",
                ),
                score=12,
            )
        )

    return out


# -----------------------------------------------------------------------------
# Wilderness suggestions
# -----------------------------------------------------------------------------



def _wilderness_suggestions(dm: VirtualDM, cid: str) -> list[_Candidate]:
    out: list[_Candidate] = []
    hex_id = _current_hex_id(dm)

    # Travel points are private in the engine; we read them for UX only.
    tp_remaining = int(getattr(dm.hex_crawl, "_travel_points_remaining", 0) or 0)
    tp_total = int(getattr(dm.hex_crawl, "_travel_points_total", 0) or 0)

    # Are we currently focused on a POI?
    try:
        poi_state = dm.hex_crawl.get_current_poi_state()
    except Exception:
        poi_state = {}

    at_poi = bool(poi_state.get("at_poi"))
    poi_name = poi_state.get("poi_name")
    can_enter = bool(poi_state.get("can_enter"))
    requires_hazard = bool(poi_state.get("requires_hazard_resolution"))

    # ------------------------------------------------------------------
    # If at a POI, prioritize POI-native actions (hazards, enter, talk, loot)
    # ------------------------------------------------------------------
    if at_poi and poi_name:
        # Resolve hazards first (approach challenges)
        if requires_hazard:
            try:
                hazards = dm.hex_crawl.get_poi_hazards(hex_id)
            except Exception:
                hazards = []

            for i, h in enumerate(hazards[:3]):
                h_name = h.get("name", f"hazard {i+1}")
                out.append(
                    _Candidate(
                        SuggestedAction(
                            id="wilderness:resolve_poi_hazard",
                            label=f"Overcome hazard: {h_name}",
                            params_schema={
                                "type": "object",
                                "properties": {
                                    "hex_id": {"type": "string"},
                                    "hazard_index": {"type": "integer"},
                                    "character_id": {"type": "string"},
                                    "approach_method": {"type": "string"},
                                },
                                "required": ["hex_id", "hazard_index", "character_id"],
                            },
                            params={
                                "hex_id": hex_id,
                                "hazard_index": i,
                                "character_id": cid,
                                "approach_method": "careful",
                            },
                            safe_to_execute=True,
                            help="Runs HexCrawlEngine.resolve_poi_hazard; success may unlock entry.",
                        ),
                        score=96,
                    )
                )

        # Enter the location
        if can_enter:
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="wilderness:enter_poi",
                        label=f"Enter {poi_name}",
                        params={"hex_id": hex_id},
                        safe_to_execute=True,
                        help="Runs HexCrawlEngine.enter_poi; may reveal sub-locations, NPCs, and items.",
                    ),
                    score=92,
                )
            )
        else:
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="wilderness:enter_poi_with_conditions",
                        label=f"Enter {poi_name} (provide entry conditions)",
                        params_schema={
                            "type": "object",
                            "properties": {
                                "hex_id": {"type": "string"},
                                "payment": {"type": "string"},
                                "password": {"type": "string"},
                                "approach": {"type": "string"},
                            },
                            "required": ["hex_id"],
                        },
                        params={"hex_id": hex_id, "payment": "", "password": "", "approach": "respectful"},
                        safe_to_execute=False,
                        help="Use when the location demands a toll, password, invitation, etc.",
                    ),
                    score=55,
                )
            )

        # Talk to present NPCs
        try:
            npcs = dm.hex_crawl.get_npcs_at_poi(hex_id)
        except Exception:
            npcs = []
        for npc in npcs[:3]:
            npc_id = npc.get("id") or npc.get("npc_id") or npc.get("name", "")
            npc_name = npc.get("name", "someone")
            if npc_id:
                out.append(
                    _Candidate(
                        SuggestedAction(
                            id="wilderness:talk_npc",
                            label=f"Talk to: {npc_name}",
                            params={"hex_id": hex_id, "npc_id": npc_id},
                            safe_to_execute=True,
                            help="Runs HexCrawlEngine.interact_with_npc; may trigger Social Interaction state.",
                        ),
                        score=82,
                    )
                )

        # Take items that are present
        try:
            items = dm.hex_crawl.get_items_at_poi(hex_id)
        except Exception:
            items = []
        for it in items[:2]:
            name = it.get("name", "item")
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="wilderness:take_item",
                        label=f"Take: {name}",
                        params_schema={
                            "type": "object",
                            "properties": {
                                "hex_id": {"type": "string"},
                                "item_name": {"type": "string"},
                                "character_id": {"type": "string"},
                            },
                            "required": ["hex_id", "item_name", "character_id"],
                        },
                        params={"hex_id": hex_id, "item_name": name, "character_id": cid},
                        safe_to_execute=True,
                        help="Runs HexCrawlEngine.take_item; item becomes unavailable thereafter.",
                    ),
                    score=58,
                )
            )

        # Dungeon access from this POI
        try:
            access = dm.hex_crawl.get_dungeon_access_info(hex_id)
        except Exception:
            access = []
        for a in access:
            if not a.get("is_accessible"):
                continue
            if a.get("poi_name") != poi_name:
                continue
            out.append(
                _Candidate(
                    SuggestedAction(
                        id="wilderness:enter_dungeon",
                        label=f"Enter dungeon (via {poi_name})",
                        params={
                            "hex_id": hex_id,
                            "dungeon_id": a.get("dungeon_id", poi_name),
                            "entrance_room": a.get("entrance_room", "entrance"),
                        },
                        safe_to_execute=True,
                        help="Transitions into Dungeon Exploration using POI-provided tables/config.",
                    ),
                    score=94,
                )
            )

        # Generic exploratory prompts at a site
        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:search_location",
                    label="Search this location (choose where/how)",
                    params_schema={
                        "type": "object",
                        "properties": {
                            "hex_id": {"type": "string"},
                            "search_location": {"type": "string"},
                            "thorough": {"type": "boolean"},
                        },
                        "required": ["hex_id", "search_location"],
                    },
                    params={
                        "hex_id": hex_id,
                        "search_location": "around the obvious hiding places",
                        "thorough": False,
                    },
                    safe_to_execute=True,
                    help="Runs HexCrawlEngine.search_poi_location; may find hidden items/paths.",
                ),
                score=54,
            )
        )

        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:explore_feature",
                    label="Examine a notable feature (describe it)",
                    params_schema={
                        "type": "object",
                        "properties": {
                            "hex_id": {"type": "string"},
                            "feature_description": {"type": "string"},
                        },
                        "required": ["hex_id", "feature_description"],
                    },
                    params={"hex_id": hex_id, "feature_description": "the most prominent feature here"},
                    safe_to_execute=True,
                    help="Runs HexCrawlEngine.explore_poi_feature (NarrativeResolver adjudicates outcomes).",
                ),
                score=50,
            )
        )

        # Leave the location
        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:leave_poi",
                    label=f"Leave {poi_name} (return to hex travel)",
                    params={"hex_id": hex_id},
                    safe_to_execute=True,
                ),
                score=60,
            )
        )

        return out

    # ------------------------------------------------------------------
    # Hex-level travel suggestions (not currently focused on a POI)
    # ------------------------------------------------------------------

    # If you’re out of travel points, "end day" becomes urgent.
    if tp_total and tp_remaining <= 0:
        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:end_day",
                    label="Make camp / End travel day (reset Travel Points)",
                    safe_to_execute=True,
                    help="Advances time ~12 hours and resets daily travel flags.",
                ),
                score=92,
            )
        )

    out.append(
        _Candidate(
            SuggestedAction(
                id="wilderness:look_around",
                label="Look around (sensory hints + visible landmarks)",
                params={"hex_id": hex_id},
                safe_to_execute=True,
                help="Returns player-facing hints without spending Travel Points.",
            ),
            score=75,
        )
    )

    visible = dm.hex_crawl.get_visible_pois(hex_id)
    for idx, poi in enumerate(visible[:4]):
        poi_type = poi.get("type", "location")
        brief = poi.get("brief") or ""
        label = f"Approach {poi_type}" + (f": {brief}" if brief else "")
        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:approach_poi",
                    label=label,
                    params={"hex_id": hex_id, "poi_index": idx},
                    safe_to_execute=True,
                    help="Moves from hex-level travel into a specific point of interest.",
                ),
                score=82,
            )
        )

    # Travel to adjacent hexes
    try:
        hex_data = dm.hex_crawl.get_hex_data(hex_id)
        adjacent = list(getattr(hex_data, "adjacent_hexes", []))
    except Exception:
        adjacent = []

    for a in adjacent[:6]:
        score = 80 if (tp_remaining > 0) else 30
        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:travel",
                    label=f"Travel to {a}",
                    params={"hex_id": a},
                    safe_to_execute=True,
                    help="Spends Travel Points based on terrain, weather, and route type.",
                ),
                score=score,
            )
        )

    if tp_remaining > 0:
        out.append(
            _Candidate(
                SuggestedAction(
                    id="wilderness:search_hex",
                    label="Search the hex (costs Travel Points; may reveal hidden sites)",
                    params={"hex_id": hex_id},
                    safe_to_execute=True,
                    help="Runs a search procedure; can discover hidden POIs.",
                ),
                score=58,
            )
        )

    # Generic survival actions (freeform)
    out.append(
        _Candidate(
            SuggestedAction(
                id="wilderness:forage",
                label="Forage for food/water (freeform resolution)",
                params={"character_id": cid},
                safe_to_execute=True,
                help="Delegates to HexCrawlEngine.handle_player_action('forage', ...).",
            ),
            score=36,
        )
    )
    out.append(
        _Candidate(
            SuggestedAction(
                id="wilderness:hunt",
                label="Hunt (freeform resolution)",
                params={"character_id": cid},
                safe_to_execute=True,
                help="Delegates to HexCrawlEngine.handle_player_action('hunt', ...).",
            ),
            score=33,
        )
    )

    return out



# -----------------------------------------------------------------------------
# Encounter suggestions
# -----------------------------------------------------------------------------


def _encounter_suggestions(dm: VirtualDM) -> list[_Candidate]:
    out: list[_Candidate] = []

    # Try to bias based on reaction roll if it exists
    try:
        summary = dm.encounter.get_encounter_summary()
        reaction = summary.get("reaction")
    except Exception:
        reaction = None

    # Default ordering: parley > evade > attack > wait.
    base = {
        EncounterAction.PARLEY: 85,
        EncounterAction.EVASION: 80,
        EncounterAction.ATTACK: 72,
        EncounterAction.WAIT: 55,
    }

    # If reaction is hostile, bump evasion/attack; if friendly, bump parley.
    if reaction:
        if reaction in ("hostile", "aggressive"):
            base[EncounterAction.EVASION] += 10
            base[EncounterAction.ATTACK] += 6
            base[EncounterAction.PARLEY] -= 10
        if reaction in ("friendly", "helpful"):
            base[EncounterAction.PARLEY] += 10
            base[EncounterAction.ATTACK] -= 8

    for a, score in sorted(base.items(), key=lambda kv: kv[1], reverse=True):
        out.append(
            _Candidate(
                SuggestedAction(
                    id="encounter:action",
                    label=f"Encounter: {a.value}",
                    params={"action": a.value, "actor": "party"},
                    safe_to_execute=True,
                    help="Runs EncounterEngine.execute_action for the party.",
                ),
                score=score,
            )
        )

    return out


# -----------------------------------------------------------------------------
# Settlement / Downtime suggestions
# -----------------------------------------------------------------------------


def _settlement_suggestions(dm: VirtualDM, cid: str) -> list[_Candidate]:
    # These are intentionally phrased in Dolmenwood-ish terms.
    # They route to SettlementEngine.handle_player_action() for now.
    return [
        _Candidate(
            SuggestedAction(
                id="settlement:action",
                label="Find an inn and rest",
                params={"text": "find an inn and rest", "character_id": cid},
                safe_to_execute=True,
                help="Freeform settlement action; later can map to a hard-coded procedure.",
            ),
            score=70,
        ),
        _Candidate(
            SuggestedAction(
                id="settlement:action",
                label="Gather rumors (tavern talk)",
                params={"text": "gather rumors", "character_id": cid},
                safe_to_execute=True,
            ),
            score=65,
        ),
        _Candidate(
            SuggestedAction(
                id="settlement:action",
                label="Visit the market (buy/sell)",
                params={"text": "visit the market", "character_id": cid},
                safe_to_execute=True,
            ),
            score=55,
        ),
        _Candidate(
            SuggestedAction(
                id="settlement:action",
                label="Seek work / hirelings",
                params={"text": "seek work or hirelings", "character_id": cid},
                safe_to_execute=True,
            ),
            score=45,
        ),
    ]


def _downtime_suggestions(dm: VirtualDM, cid: str) -> list[_Candidate]:
    return [
        _Candidate(
            SuggestedAction(
                id="downtime:action",
                label="Rest and recover",
                params={"text": "rest and recover", "character_id": cid},
                safe_to_execute=True,
            ),
            score=70,
        ),
        _Candidate(
            SuggestedAction(
                id="downtime:action",
                label="Train / improve a skill",
                params={"text": "train", "character_id": cid},
                safe_to_execute=True,
            ),
            score=50,
        ),
        _Candidate(
            SuggestedAction(
                id="downtime:action",
                label="Craft / tinker",
                params={"text": "craft", "character_id": cid},
                safe_to_execute=True,
            ),
            score=45,
        ),
    ]


# -----------------------------------------------------------------------------
# Oracle suggestions
# -----------------------------------------------------------------------------


def _oracle_suggestions() -> list[_Candidate]:
    return [
        _Candidate(
            SuggestedAction(
                id="oracle:fate_check",
                label="Ask the Oracle (yes/no)",
                params_schema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "likelihood": {
                            "type": "string",
                            "enum": [
                                "impossible",
                                "very_unlikely",
                                "unlikely",
                                "fifty_fifty",
                                "likely",
                                "very_likely",
                                "near_sure_thing",
                                "a_sure_thing",
                                "has_to_be",
                            ],
                        },
                    },
                    "required": ["question"],
                },
                params={"question": "", "likelihood": "fifty_fifty"},
                safe_to_execute=False,
                help="Mythic GME 2e Fate Check; use when the fiction is uncertain.",
            ),
            score=22,
        ),
        _Candidate(
            SuggestedAction(
                id="oracle:random_event",
                label="Mythic: Random Event",
                safe_to_execute=True,
                help="Generates a focus + meaning pair; use on doubles/interrupts or when stuck.",
            ),
            score=18,
        ),
        _Candidate(
            SuggestedAction(
                id="oracle:detail_check",
                label="Mythic: Detail Check (meaning table)",
                safe_to_execute=True,
                help="Generates a meaning pair; use to answer 'what kind?' or 'how?'.",
            ),
            score=16,
        ),
    ]
