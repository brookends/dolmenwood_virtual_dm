# Dolmenwood Virtual DM — Fairy Roads Patch Plan (v1)

This patch introduces **fairy roads** as a first-class travel mode: a new `FAIRY_ROAD_TRAVEL` game state, a dedicated engine, content loaders/registry, encounter & time-dilation hooks, and clean integration points from wilderness exploration and special encounters.

It is written to be **directly actionable for an LLM implementing code changes** in the current repo structure (`src/...`).

---

## 0) Goals and scope

### Goals
- Add a new travel mode that follows Dolmenwood fairy road procedures:
  - No getting lost while staying on-road.
  - Up to 3 encounter/location checks per day of travel on the road.
  - Road-specific location table (d8) + shared encounter table (d20).
  - **Don’t stray from the path**: leaving the road causes faintness; persisting results in unconsciousness and waking in a random hex.
  - **Time dilation on return**: on return to the mortal world, roll on the time-passed table (and also support special location-specific dilation).

### Out of scope (but left with hooks)
- “Journeys into Fairy” domain exploration beyond the side-road invitation gate.
- Full bestiary statblocks for all listed creatures (the encounter engine can still reference existing monsters/aliases).
- Visual map rendering / VTT integration.

---

## 1) Content: files, schema, and where to put them

### New content directory
Create:
- `data/content/fairy_roads/`

Place the JSON files (bundle provided in this chat) into that directory:
- `fairy_roads_common.json`
- `fairy_road_*.json`
- `fairy_road_index.json` (optional convenience index)

### Recommended schema expectations (what code should rely on)
Each road JSON contains:
- `id`, `name`, `length_miles`
- `doors[]` entries with `hex_id`, plus `direction` tags (`endpoint`, `entry`, `exit_only`)
- `side_roads[]` with `requires_invitation`
- `tables.locations_d8.entries[]` with `roll`, `summary`, and `effects[]`

`fairy_roads_common.json` contains:
- Shared encounter table: `tables.fairy_road_encounters_d20`
- Shared time-dilation table: `tables.time_passed_in_mortal_world_2d6`
- Core procedural summaries for “don’t stray”, “side-roads”, and travel procedure.

---

## 2) Add a Fairy Road content loader + registry

Mirror the patterns used for spells and monsters.

### 2.1 New files
Create:
- `src/content_loader/fairy_road_loader.py`
- `src/content_loader/fairy_road_registry.py`

### 2.2 Loader responsibilities
`FairyRoadLoader` should:
- Load `data/content/fairy_roads/*.json`
- Parse and validate minimal required keys (fail-fast with clear errors):
  - `id`, `name`, `length_miles`
  - `tables.locations_d8.entries`
- Load and cache the common file once (`fairy_roads_common.json`)
- Provide:
  - `load_all_roads() -> dict[id, FairyRoadDefinition]`
  - `get_common() -> FairyRoadCommon`

You can keep these as plain `dict[str, Any]` for MVP, but define dataclasses if you want static clarity.

### 2.3 Registry responsibilities
`FairyRoadRegistry` should:
- Hold in-memory index of roads by id and by door hex:
  - `roads_by_id: dict[str, FairyRoadDefinition]`
  - `road_door_index: dict[str, list[DoorRef]]` where key is hex_id (e.g. "0602")
- Provide:
  - `get_road(road_id)`
  - `get_roads_at_hex(hex_id) -> list[DoorRef]`
  - `list_roads()`

Add singleton helpers, following the spell registry pattern:
- `get_fairy_road_registry()`
- `reset_fairy_road_registry()`

### 2.4 Export from content_loader
Update:
- `src/content_loader/__init__.py`
to export the new loader/registry symbols.

---

## 3) Add a new game state and state-machine triggers

### 3.1 Add the state
Update `src/game_state/state_machine.py`:
- Add `FAIRY_ROAD_TRAVEL = "fairy_road_travel"` to `GameState`.

### 3.2 Add transitions
Add transitions analogous to wilderness travel:

From **WILDERNESS_TRAVEL**:
- `enter_fairy_road` -> `FAIRY_ROAD_TRAVEL`

From **FAIRY_ROAD_TRAVEL**:
- `exit_fairy_road` -> `WILDERNESS_TRAVEL`
- `encounter_triggered` -> `ENCOUNTER`
- `enter_side_road` -> (for now) either:
  - `ENCOUNTER` (as a “special location” proxy), or
  - `WILDERNESS_TRAVEL` with a flag (if you model fairy domains as wilderness-like),
  - or leave as TODO until fairy domains are implemented.

From **ENCOUNTER** back to fairy road:
- Add `encounter_end_fairy_road` -> `FAIRY_ROAD_TRAVEL`

From **COMBAT** back to fairy road:
- Add `combat_end_fairy_road` -> `FAIRY_ROAD_TRAVEL`

From **SOCIAL_INTERACTION** back to fairy road:
- Add `conversation_end_fairy_road` -> `FAIRY_ROAD_TRAVEL`

Also ensure:
- `valid_triggers` is updated by adding the trigger strings where needed.

---

## 4) GlobalController: store fairy-road context + time anomaly tools

### 4.1 Add a “fairy road context” to PartyState or Controller
Recommended: keep it in `GlobalController` so saving/loading is easier via SessionManager.

Add a small dataclass in `src/game_state/global_controller.py` (or `src/data_models.py`):
```python
@dataclass
class FairyRoadContext:
    road_id: str
    entered_from_hex: str
    intended_exit_hex: str | None
    direction: str  # "A_to_B" or "B_to_A" or "one_way"
    miles_remaining: float
    checks_done_today: int
    subjective_turns_today: int
    mortal_time_accumulator: list[dict[str, str]]  # e.g. [{"time":"3d10 days","source":"Buttercup Lane #8"}]
```

Store:
- `self._fairy_road: Optional[FairyRoadContext]`

### 4.2 Implement mortal-world time passage without ticking party effects
Add a new method on `GlobalController`:
- `apply_mortal_time_passage(time_str: str, source: str) -> dict`

Where:
- `time_str` can be `"1d6 minutes"`, `"2d6 days"`, `"1d6 weeks"`, etc.

Implementation requirement:
- **Advance `self.time_tracker.game_time/game_date` and sync `world_state`**
- **Do NOT** call `advance_time()` (because that ticks spell effects, consumes food/water, etc).

Implementation approach:
- Parse dice expression + unit.
- Roll with your existing dice utility.
- Convert to turns for clock math (minutes/hours/days/weeks).
- Advance the underlying `GameTime` and `GameDate` directly, then update:
  - `world_state.current_time`
  - `world_state.current_date`
  - `world_state.season` (recompute)

Log event:
- `"mortal_time_passed"` with `{source, rolled, unit, new_time}`

### 4.3 Implement “subjective time” advancement for fairy travel
Fairy-road travel must still:
- Deplete light sources
- Tick conditions and spell effects
- Consume resources / spoilage over experienced days

Add method:
- `advance_subjective_time(turns: int) -> dict`

It should:
- Run the same **turn/watch/day effects** as `advance_time()` does,
  but **without changing world_state date/time** (mortal clock).
- Maintain a small counter store on controller, e.g.:
  - `self._subjective_turn_counter`
  - `self._subjective_day_counter`

To minimize blast radius, keep existing “turn/day callbacks” logic and call them explicitly:
- For each turn: `tick_spell_effects("turns")`, `tick_polymorph_effects()`, `tick_location_effects()`, condition ticks
- Every 24*6 turns: call `consume_resources(...)` and `_check_ration_spoilage(current_day=<subjective_day_counter>)`

**Important:** refactor `_check_ration_spoilage` to accept an explicit `current_day` parameter (it currently reads `self.time_tracker.days`).

Log event:
- `"subjective_time_advance"`

This keeps:
- Party effects aligned with experienced time
- World clock isolated, so return-time dilation is rules-correct

---

## 5) Implement `FairyRoadEngine`

### 5.1 New module
Create:
- `src/fairy_roads/fairy_road_engine.py`
- `src/fairy_roads/__init__.py`

### 5.2 Engine responsibilities
The engine is responsible for:
- Entering a fairy road via a door in the current hex
- Advancing along the road (turns/watches/days)
- Rolling encounter/location checks (per procedure)
- Resolving location table effects
- Handling “stray from the path”
- Exiting via the far door (or one-way ejection)
- Applying mortal time passage on return

### 5.3 Public API (match other engines)
Provide:
- `enter_fairy_road(road_id: str, *, from_hex: str, via_door_hex: str | None = None) -> dict`
- `travel(turns: int | None = None, watches: int | None = 1) -> dict`
- `exit_fairy_road(*, forced_to_hex: str | None = None) -> dict`
- `handle_player_action(text: str, character_id: str) -> ResolutionResult` (freeform support)
- `get_context() -> Optional[FairyRoadContext]`

### 5.4 Travel procedure implementation
When traveling:
- Convert road length to travel time using your existing overland travel rules.
- Each “travel segment” should advance subjective time (not mortal time):
  - Use `controller.advance_subjective_time(...)`
- Each (subjective) day of travel:
  - Allow up to 3 checks:
    - Roll 1d6:
      - 1–2: monster encounter (d20)
      - 3–4: location encountered (d8 road table)
      - 5–6: no event
- When monster encountered:
  - Call existing `EncounterEngine` entrypoint with origin = FAIRY_ROAD and
    set up encounter actors as usual.
  - Trigger state transition: `controller.transition("encounter_triggered")`
- When location encountered:
  - Resolve effect atoms from JSON:
    - `heal`, `damage`, `save`, `chance`, `toll`, `rest_site`, `forced_exit`, `stray_from_path`,
      `modify_effective_length`, `mortal_time_delta`, etc.
  - For any `mortal_time_delta`, append into `context.mortal_time_accumulator`.

### 5.5 Exiting and time dilation
On exit:
- Choose exit hex:
  - Normal road: the opposite door hex in the road file
  - One-way road: fixed ejection hex (Prince’s Road)
  - Forced exit location: explicit `forced_to_hex`
- Apply **mortal** time passage:
  - Start with the base “Time Passed in the Mortal World” roll (2d6 table).
  - Add any accumulated deltas from locations (e.g., Buttercup Lane #8, White Way plaza if desired).
  - Call `controller.apply_mortal_time_passage(...)` for each delta entry in order.
- Update party location to the exit hex via existing hex crawl move helpers.
- Transition: `controller.transition("exit_fairy_road")`

### 5.6 Straying off the path
If `stray_from_path` triggers:
- Immediately run:
  - `controller.advance_subjective_time(1)` (the “within 1 turn” faint threshold)
- Then “wake in random hex”:
  - Use hex registry or hex crawl engine to pick a random valid Dolmenwood hex id
  - Set party location to that hex
  - Apply mortal time passage roll (2d6 table)
  - Transition out to wilderness travel

Log:
- `"fairy_road_stray"`

---

## 6) Encounter system integration

### 6.1 Add encounter origin
Update `src/encounter/encounter_engine.py`:
- Extend `EncounterOrigin` with `FAIRY_ROAD = "fairy_road"`

Update all places that return to origin:
- Add logic mirroring wilderness/dungeon/settlement:
  - On end: `controller.transition("encounter_end_fairy_road")`

### 6.2 Transportation effects (special encounters)
The encounter engine already supports `transportation_effect`. Add a convention:
- destination strings like:
  - `"fairy_road:buttercup_lane"`
  - `"fairy_road:the_princes_road"`

When `resolve_transportation_save()` returns transported=True:
- The caller (conversation facade / orchestrator) should interpret that destination
  and call `dm.fairy_roads.enter_fairy_road(...)`.

Implement a small dispatcher helper:
- `src/encounter/transport_dispatch.py` or place in `VirtualDM`

---

## 7) VirtualDM wiring

Update `src/main.py`:
- Instantiate the new engine:
  - `self.fairy_roads = FairyRoadEngine(self.controller)`

Update any exported interfaces if needed.

---

## 8) Conversation facade + suggestions

### 8.1 Freeform routing
Update `src/conversation/conversation_facade.py`:
- In `_process_freeform_action`, add:
  - `if state == GameState.FAIRY_ROAD_TRAVEL: rr = self.dm.fairy_roads.handle_player_action(...)`

### 8.2 Action ids (optional but recommended)
Add explicit actions similar to dungeon/encounter:
- `fairy_road:travel_watch` (default)
- `fairy_road:exit` (if at endpoint / forced exit)
- `fairy_road:turn_back`
- `fairy_road:status`

Update `handle_turn()` to route those actions.

### 8.3 Suggestion builder
Update `src/conversation/suggestion_builder.py`:
- Add a new branch:
  - `elif state == GameState.FAIRY_ROAD_TRAVEL: candidates.extend(_fairy_road_suggestions(...))`

Suggested actions:
- Travel 1 watch
- Exit (if exit is available)
- Turn back
- Check status

Also update `_status_summary()` to show:
- Current mode
- **Mortal world date/time** (world_state)
- Fairy road id + miles remaining (if in fairy road)
- Subjective time counters if you expose them (optional)

---

## 9) Save/Load support

Update `src/game_state/session_manager.py`:
- Ensure fairy road context is saved as part of the session state deltas:
  - Add `fairy_road_context` to the saved controller/party snapshot.
- On load:
  - If fairy road context exists, restore it and set current state accordingly.

Minimal approach:
- Store it inside `PartyState.custom_state["fairy_road"]` (if you already have custom_state).
If not present, add a `custom_state: dict[str, Any]` to PartyState.

---

## 10) Tests and acceptance criteria

### 10.1 Unit tests (suggested)
Create `tests/test_fairy_roads.py` covering:
- Registry loads all roads and indexes doors correctly
- Entering a road sets context + state
- Travel triggers encounter rolls and location rolls
- Stray causes relocation + mortal time roll
- Exit applies mortal time passage without consuming extra resources
- One-way exit (Prince’s Road) behaves correctly

### 10.2 Acceptance checklist
- [ ] From wilderness at a door hex, player can enter a fairy road.
- [ ] Travel progresses; encounter checks happen up to 3/day; no “lost” checks while on-road.
- [ ] Location results apply their mechanical effects (heals, damage, conditions, forced exits).
- [ ] Straying relocates the party and applies time-passed roll.
- [ ] Exiting returns to correct mortal hex and applies time-passed roll.
- [ ] Time-passed effects do **not** tick party spell durations/resources twice.
- [ ] Encounters triggered on fairy roads return to fairy-road mode after resolution.
- [ ] Saves and loads preserve fairy-road context.

---

## 11) Implementation order (recommended)

1. Content directory + loader + registry
2. Add `GameState.FAIRY_ROAD_TRAVEL` and state-machine triggers
3. Add controller helpers:
   - `advance_subjective_time`
   - `apply_mortal_time_passage`
4. Implement FairyRoadEngine core loop:
   - enter / travel / exit
5. Integrate encounter origin + return triggers
6. Wire into VirtualDM + conversation facade + suggestions
7. Save/load
8. Tests

---

## 12) Notes on “invitation-only” side-roads (future-safe hook)

For now:
- If a location effect is `side_road` and party lacks an invitation token:
  - Trigger `stray_from_path` (per rules)
- Add future extension:
  - `PartyState.fairy_invitations: set[str]` holding domain ids
  - A later “fairy domain” engine can consume that and allow entry.

---

*End of patch plan.*
