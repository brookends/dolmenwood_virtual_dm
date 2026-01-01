# Dolmenwood Settlement Engine — Patch Plan (v2)

This patch plan is aligned to the current repo’s actual integration points:
- `ConversationFacade` calls `SettlementEngine.handle_player_action(...)` for `settlement:action`
- dice uses `DiceRoller.roll(...)`
- encounter tables are authored as day/night but game time is `TimeOfDay` (granular)

The goal is to introduce the settlement JSON pack **without breaking existing settlement gameplay**.

---

## Guiding principles
1. **Bridge first, then refactor**: add a small shim so the current UI continues working.
2. **Data-first settlement interaction**: location browsing, services, NPCs, encounter tables.
3. **Deterministic & observable**: all random rolls go through `DiceRoller`, all major actions log to `RunLog`.

---

## Phase 0 — Content plumbing (P0, low risk)

### Tasks
1) **Add loader + models**
- Copy v2 skeleton modules into repo:
  - `src/content_loader/settlement_loader.py`
  - `src/settlement/settlement_content_models.py`
  - `src/settlement/settlement_registry.py`
  - `src/settlement/settlement_encounters.py`
  - `src/settlement/settlement_services.py`

2) **Add settlement content directory**
- Create: `data/content/settlements/`
- Add at least one settlement JSON file (minimal viable is fine).

3) **Load registry at startup**
- In `src/main.py` inside `VirtualDM.__init__`:
  - instantiate `SettlementLoader(Path("data/content/settlements"))`
  - call `load_registry_with_report()`
  - attach via `self.settlement.set_registry(registry)`

4) **Add `set_registry`**
- In `src/settlement/settlement_engine.py` add:
  - `self._registry: Optional[SettlementRegistry]`
  - `def set_registry(self, registry: SettlementRegistry) -> None: ...`

### Acceptance criteria
- Game launches
- Settlement registry loads (even if empty) with no crash
- Unit tests in skeleton pass when copied into repo

---

## Phase 1 — Bridge API + core navigation (P0)

### Tasks
1) **Implement `handle_player_action` shim**
- File: `src/settlement/settlement_engine.py`
- Add `handle_player_action(text, character_id)`:
  - conservative keyword routing (list locations / visit X / services / talk to)
  - fallback returns a friendly “unimplemented” message, not an exception
  - when intent is recognized, call `execute_action(...)`

2) **Add structured router**
- Add: `execute_action(action_id: str, params: dict) -> dict`
- Implement minimum actions:
  - `settlement:list_locations`
  - `settlement:visit_location`

3) **Runtime state**
- Add minimal runtime fields:
  - active settlement id
  - current location number
  - visited locations set

### Acceptance criteria
- In settlement state, freeform input:
  - “list locations” returns a list
  - “visit 1” returns location text
- No code path requires the old procedural Building/Shop model for these actions

---

## Phase 2 — Services + NPC listing (P0 → P1)

### Tasks
1) **Services**
- Implement:
  - `settlement:list_services` (for current or specified location)
  - `settlement:use_service` (dispatch through `SettlementServiceExecutor`)
- Preserve cost text and parse simple coins best-effort (non-fatal on failure)

2) **NPCs**
- Implement:
  - `settlement:list_npcs` (current location default)
  - `settlement:talk_to_npc` (narration-only placeholder)
- Lookup NPCs via:
  - `locations[].npcs[]` and/or `npcs[].location_id`

3) **Logging**
- Use `RunLog.log_custom("settlement_event", ...)` for:
  - visit location
  - service used
  - talk to NPC

### Acceptance criteria
- “services” lists services in current location
- “use lodging” returns structured result (cost text + notes)
- “list npcs” returns NPCs present
- No crashes if a location has no services or no NPCs

---

## Phase 3 — Encounter tables + time advancement hooks (P1)

### Tasks
1) **Encounter table integration**
- On time-advancing actions (rest, long convo, etc), call:
  - `SettlementEncounterTables(settlement_data).roll(DiceRoller, current_time_of_day)`
- Ensure day/night mapping works.

2) **Escalation rules**
- Start simple:
  - If the table returns a result, narrate it and log it
- Later:
  - Add a probability gate (e.g., 2-in-6 day, 1-in-6 night) before consulting the table
  - For “combat-ish” results, transition into EncounterEngine/CombatEngine

3) **Observability**
- The helper already logs a table lookup; keep that or log a custom event.

### Acceptance criteria
- Deterministic encounter roll in unit test with `DiceRoller.set_seed`
- Encounter results appear in narration and/or log

---

## Phase 4 — Locks, equipment availability, roads (P2)

### Tasks
1) **Locked locations**
- Enforce `is_locked` + `key_holder`:
  - block entering unless party has key or special permission
  - optionally allow “knock / bribe / break in” actions later

2) **Equipment availability**
- Add a query action:
  - `settlement:equipment_availability`
- Integrate into shop/trade later:
  - apply `price_modifier`
  - filter `available/unavailable_categories`
  - expose `special_items`

3) **Roads/connections**
- Add:
  - `settlement:ask_directions` (returns roads + destinations)
- Later: connect to HexEngine and travel procedures.

### Acceptance criteria
- Attempting to visit locked location produces an informative refusal
- Equipment availability can be queried from settlement state
- Directions list is available when data exists

---

## Phase 5 — UI actions upgrade (optional but recommended)

### Tasks
1) **Expose suggested actions**
- Implement `get_suggested_actions(character_id)` returning a list of:
  - `{"action_id": "...", "label": "...", "params": {...}}`

2) **Use suggestions in `suggestion_builder`**
- If `dm.settlement.get_suggested_actions` exists, prefer those over the generic
  `"settlement:action"` suggestion.

3) **Route structured action ids in `ConversationFacade`**
- For action ids like `settlement:visit_location`, call `execute_action` directly.

### Acceptance criteria
- UI shows stable clickable actions for settlement play
- Freeform fallback remains available

---

## Smoke test script (manual)
1. Start game
2. Travel to a settlement (enter settlement state)
3. Type:
   - “list locations”
   - “visit 1”
   - “services”
   - “use lodging”
   - “list npcs”
4. Advance time (rest) and confirm encounter check can run
