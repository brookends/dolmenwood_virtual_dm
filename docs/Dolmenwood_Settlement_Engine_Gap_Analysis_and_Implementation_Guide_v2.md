# Dolmenwood Settlement Engine — Gap Analysis & Implementation Guide (v2)

This document is a *compatibility-updated* version of the original settlement expansion guide.
It keeps the same overall approach (JSON-authored settlements + location-centric interaction),
but corrects integration assumptions to match the current repo’s actual APIs.

## Why a v2?
The repo’s conversation layer currently expects **freeform settlement actions** via:
- `ConversationFacade.handle_action(... action_id == "settlement:action" ...)`
- which calls `SettlementEngine.handle_player_action(text, character_id)`

The original skeleton/plan focused on a structured `execute_action(...)` router and UI suggestions.
That is still the right end state — but we need a **bridge** so the existing UI keeps working
while the structured action API is introduced.

Additionally:
- dice rolling in the repo uses `DiceRoller.roll(...)` (not `roll_dice`)
- time-of-day is granular (`TimeOfDay.DAWN/MORNING/...`) but settlement encounter tables are day/night

---

## 1) Current SettlementEngine (repo reality check)

### What is implemented today
`src/settlement/settlement_engine.py` currently provides:
- “enter/exit settlement” state transitions and party-location updates
- a **procedural** “building/shop” model (`Settlement`, `Building`, `Shop`) used for basic services
- a few atmosphere/rumor hooks (lightweight)
- time advancement hooks via the WorldState / TimeTracker

### What is missing (core gaps)
- No loader/registry for JSON-authored settlement packs
- No location-centric browsing (“list locations / visit location / details”)
- No service execution based on authored “services[]”
- No authored NPC rosters tied to locations
- No authored encounter tables (day/night)
- No stable UI/export seam for settlement state

---

## 2) What the settlement JSON pack demands (engine capability inventory)

The JSON pack implies these minimum interactive capabilities:

### P0 (must-have)
1. **List locations**
2. **Visit a location** (show description; enforce locks)
3. **List/use services** in a location (preserve cost text; best-effort coin parsing)
4. **List NPCs in location** and basic “talk” scaffolding (narration-only initially)

### P1 (next)
5. **Rumors + settlement events** (tie into knowledge/notes)
6. **Day/Night encounter tables** with deterministic dice logging

### P2 (later)
7. **Equipment availability rules** (price modifiers, category gating, special items)
8. **Roads/connections** (asking directions, routing to wilderness travel)
9. **Deep services** (spellcasting, hiring, faction play, legal trouble, etc.)

---

## 3) Updated architecture (recommended)

### 3.1 Content loading
Add new modules (shipped in skeleton v2):
- `src/content_loader/settlement_loader.py`
- `src/settlement/settlement_registry.py`
- `src/settlement/settlement_content_models.py`

Loader supports:
- single-record JSON files
- wrapper format `{ "_metadata": ..., "items": [...] }` (mirrors spell loader style)

### 3.2 Runtime state vs content state
**Content state**: immutable `SettlementData` from JSON pack  
**Runtime state**: mutable “what the party has done here”:
- current settlement id
- current location number (or None)
- visited locations set
- discovered rumors / discovered NPC facts
- last encounter timestamp, etc.

Recommendation: introduce a small `SettlementRuntimeState` owned by `SettlementEngine`
(do not mutate `SettlementData` itself).

### 3.3 Interaction surface (bridge first, then structured actions)

**Bridge (required now):**
- Implement `SettlementEngine.handle_player_action(text, character_id)` as a conservative shim:
  - detect a few obvious intents
  - otherwise return a friendly “unimplemented” message
  - internally call `execute_action(...)` when possible

**Structured actions (target end state):**
- `SettlementEngine.execute_action(action_id: str, params: dict) -> dict`
- `SettlementEngine.get_suggested_actions(character_id) -> list[dict]`

Once structured actions exist, the UI can graduate from:
- one generic `settlement:action`
to:
- specific actions like `settlement:list_locations`, `settlement:visit_location`, etc.

### 3.4 Encounters: day/night mapping
Ship and use `SettlementEncounterTables`:
- converts granular `TimeOfDay` into `day` vs `night`
- rolls via `DiceRoller.roll("1d6")` so rolls are replay/loggable
- optionally logs `RunLog.log_table_lookup(...)`

---

## 4) Data model notes (robust import)

The v2 content models accept common schema drift:
- location key: `location_type` OR `type` OR `category`
- location id: `number` OR `id`
- encounter entries may omit `roll` (fallback assigns 1..N)
- governance/religion may be dicts OR strings

This keeps the loader resilient and pushes “strictness” into validation later.

---

## 5) Procedure triggers (how to wire to the rest of the game)

These are the recommended “procedure seams” between settlement play and the wider engine:

### 5.1 Enter settlement
Inputs:
- `settlement_id` (from hex feature, user selection, or narrative travel outcome)

Effects:
- set active settlement runtime state
- update party location
- generate narration: arrival + atmosphere + notable hooks

### 5.2 Visit location
Inputs:
- `location_number`

Effects:
- enforce lock rules (`is_locked`, `key_holder`)
- set current location
- narrate exterior/interior + relevant NPCs/services

### 5.3 Use service
Inputs:
- `location_number`, `service_name`, optional params

Effects:
- return structured `ServiceUseResult` (cost text, best-effort coin parse)
- optional downstream hooks:
  - rest healing (lodging)
  - bless/curse resolution (prayer)
  - cure wounds/conditions (healer)
  - purchases (later)

### 5.4 Talk to NPC
Inputs:
- `npc_id`, `topic`, `approach`

Effects:
- narration only initially
- later: knowledge/rumor updates, reaction rolls, faction relation changes

### 5.5 Encounter check
Trigger:
- time advances OR location change OR “loiter” action

Effects:
- roll using day/night table
- on certain outcomes: transition to ENCOUNTER state and pass context

---

## 6) Observability & export (Foundry-ready seam)

Prefer the existing `RunLog` infrastructure rather than adding a second event buffer.

When something notable happens:
- `get_run_log().log_custom("settlement_event", {...})`

And for UI snapshotting:
- add a `settlement_pack` section to `SettlementEngine.get_full_state()` containing:
  - active settlement id/name/hex
  - current location summary
  - visited locations
  - unlocked locations
  - last rolled encounter (optional)

This dovetails with the existing `conversation/state_export.py` and `EventStream`.

---

## 7) Testing strategy (fast feedback)

Shipped tests in skeleton v2:
- loader test (fixture-based)
- encounter test (deterministic roll with `DiceRoller.set_seed`)

Add in-repo tests next:
- `test_settlement_enter_and_list_locations` (engine-level smoke test)
- `test_settlement_visit_locked_location_requires_key` (rule enforcement)
- `test_settlement_service_cost_parsing_is_nonfatal` (robustness)

---

## 8) Implementation checklist (LLM-friendly)

### Phase 0 — plumbing (P0)
- [ ] Add `data/content/settlements/` and at least 1 JSON
- [ ] Copy v2 skeleton modules into repo
- [ ] Load registry in `VirtualDM.__init__` and attach to `self.settlement`
- [ ] Add `SettlementEngine.set_registry(...)`

### Phase 1 — bridge + basic navigation (P0)
- [ ] Implement `handle_player_action` shim
- [ ] Implement `execute_action("settlement:list_locations")`
- [ ] Implement `execute_action("settlement:visit_location")`

### Phase 2 — services + NPC listing (P0 → P1)
- [ ] `execute_action("settlement:list_services")`
- [ ] `execute_action("settlement:use_service")` using `SettlementServiceExecutor`
- [ ] `execute_action("settlement:list_npcs")`
- [ ] `execute_action("settlement:talk_to_npc")` narration-only

### Phase 3 — encounters + events (P1)
- [ ] integrate `SettlementEncounterTables`
- [ ] log table lookups + custom settlement events in `RunLog`

### Phase 4 — upgrade UI actions (P2)
- [ ] teach `suggestion_builder` to query `dm.settlement.get_suggested_actions(...)`
- [ ] teach `ConversationFacade.handle_action` to route specific settlement action ids
- [ ] keep `settlement:action` freeform as a fallback path
