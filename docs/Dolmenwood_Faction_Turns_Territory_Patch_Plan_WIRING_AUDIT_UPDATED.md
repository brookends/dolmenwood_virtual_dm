# Dolmenwood Virtual DM — Faction Turns (Territory-Only) Patch Plan

This patch plan integrates **long-term faction play** into the existing Dolmenwood Virtual DM codebase using a lightweight “faction turns” loop:
- Each faction maintains **resources**, **goals**, and **three active actions**.
- On a faction turn, pick one active action (randomly by default), roll **d6**, apply a **±1 modifier** (capped) based on resources / interference, and advance a **progress bar**.
- When an action completes, apply its **territory effects**, replace it, and log the results.

The mechanical core follows the procedure described by Among Cats and Books (ELMC).  
See: “Executing the Faction Turn” (random action selection, d6 roll, ±1 cap, progress advancement, logging).

This implementation is **territory-only**:
- No supply/economy tracking.
- “Resources” are *tags* that (a) justify a +1 to a roll for relevant actions or (b) justify -1 via opposition or interference.

## 1) What’s being added


## 1A) Wiring audit findings (repo-confirmed)

These points were verified by inspecting the current repository (not assumed). They adjust the original plan to match how the Virtual DM actually runs today.

### Day-advance hook and callback signature
- The **day callbacks live on `TimeTracker`**, not `GlobalController`. The method is `TimeTracker.register_day_callback(callback: Callable[[int], None])` in `src/game_state/global_controller.py`.
- Callbacks receive **only** `days_passed: int` (no `new_date` argument). If you need the new in-world date/time, read it from `controller.time_tracker.game_date` / `controller.time_tracker.game_time`.
- Important ordering detail: `TimeTracker` invokes day callbacks *inside* `advance_turn()`, before `GlobalController.advance_time()` copies the new date/time into `world_state.current_date/current_time`.  
  ➜ **Do not** use `controller.world_state.current_date` inside the callback for timestamps; use `controller.time_tracker.game_date` instead.

### Persistence and state export seams
- Persistence is handled through `SessionManager` + `GameSession.custom_data` in `src/game_state/session_manager.py`, and is wired into `VirtualDM.save_game()` / `VirtualDM.load_game()` in `src/main.py`.
- The conversation/UI snapshot uses `export_public_state(dm)` which currently returns `dm.get_full_state()` (`src/conversation/state_export.py`).  
  ➜ The least invasive way to surface faction state is to **merge a `factions` key in `VirtualDM.get_full_state()`** (rather than changing the conversation layer).


### Content placement and filenames
- The repo’s canonical on-disk content root is `data/content/` (loaded when `--load-content` is enabled). There is currently **no** `data/content/factions/` directory, so the patch must create it.
- The uploaded `factions_index.json` lists filenames like `nag_lord.json`, `cold_prince.json`, `drune.json`, but the uploaded example files are named `faction_nag_lord_atanuwe.json`, `faction_cold_prince.json`, `faction_drune.json`.  
  ➜ Decide on **one** convention and make `FactionLoader` tolerant: load via index if present, otherwise glob `*.json` and filter on presence of `faction_id`.

### Conversation/action routing seams
- Clickable action IDs are registered in `src/conversation/action_registry.py` (via `get_default_registry()`), and suggestions are assembled in `src/conversation/suggestion_builder.py`.
- If you want a player-accessible “Faction Status” view, add a `meta:factions` (or `factions:status`) action spec to the registry and a corresponding suggested action in the suggestion builder.

### RNG + observability
- The project already has a singleton `DiceRoller` (`src/data_models.py`) with seeding support and roll logging.
- New faction mechanics should use `controller.dice_roller.roll(...)` (or `DiceRoller.roll(...)`) rather than `random.*`, so faction turns can be deterministic in tests and visible in logs.

### Uploaded skeleton patch mismatches to fix
- The skeleton patch assumes a `GlobalController.register_day_callback` API and a `(days_passed, new_date)` callback signature — neither exists today (see above).
- The skeleton uses `random.choice(...)` for action selection; this should be replaced with a `DiceRoller`-based selection for determinism and auditability.
- Several hunks contain placeholder escape sequences (e.g., `\1`) that will not apply cleanly; treat the skeleton as scaffolding, not a drop-in patch.

### New runtime subsystem: `FactionEngine`
Add a new subsystem that:
- Loads faction definitions from `data/content/factions/`
- Maintains persistent faction state (active actions, progress, territory controlled, relations, logs)
- Advances faction state on a cadence (default weekly)
- Emits narrative-facing “world news” items for the LLM/UI

**Primary integration point:** `TimeTracker` day callbacks via `VirtualDM.controller.time_tracker` (day advance).  
The engine should run on a week boundary or when N days have elapsed.

### New data content
Create `data/content/factions/` JSON content:
- `faction_rules.json` — cadence and core rules
- `<faction_id>.json` — faction definitions (resources/goals/action library)
- `factions_index.json` — optional index listing faction files
- `faction.schema.json` — schema stub (validation)

A sample content pack is provided separately (zip).

## 2) Data model

### 2.1 Static data (loaded from JSON)
**FactionDefinition**
- `faction_id`, `name`, `description`
- `resources[]` with `tags[]`
- `goals[]` with visibility tiers (landmark/hidden/secret)
- `action_library[]` with:
  - `scope`: task/mission/goal (drives default segment counts)
  - `resource_tags`: which resource tags can justify +1
  - `targets`: hex/settlement/faction/etc.
  - `segments`: progress bar length
  - `on_complete`: effect list (claim/contest/fortify territory, set flags, add rumors, apply modifiers)

The sample definitions for Nag-Lord, Cold Prince, Drune, and House Brackenwold were drafted from ELMC’s Dolmenwood faction writeups:

### 2.2 Dynamic state (persisted in saves)
**FactionState**
- `territory`: sets of controlled `hexes`, `settlements`, `strongholds/domains`
- `level`: 1..4 (derived from territory points; cap at 4)
- `active_actions`: exactly 3 action instances, each:
  - `action_id`, `progress`, `segments`, `started_on`, `notes`
- `relations`: simple affinity map by faction_id (optional)
- `log`: list of entries:
  - date, chosen action, die roll, modifier, progress delta, completion, effects applied, narrative notes

Store this under `session.custom_data["faction_state"]` to avoid disrupting immutable base content.

## 3) Engine behavior

### 3.1 Turn cadence
Default: **every 7 in-world days**.
- Register a day callback with `self.controller.time_tracker.register_day_callback(callback)` (callback signature: `callback(days_passed: int)`).
- Accumulate days; when >= cadence, trigger a “faction cycle” and reset accumulator.

Optional: allow other triggers to force a cycle:
- Long settlement downtime
- Major travel time-skips (wilderness, fairy roads, etc.)

### 3.2 Selecting an action
Baseline:
- Randomly select 1 of the 3 active actions for the faction.
Extensions (toggle):
- “Focused drive”: choose the action closest to completion
- “Player pressure”: choose an action that threatens the party’s current region

### 3.3 Rolling and advancement
Baseline:
- Roll d6.
- Determine modifier:
  - +1 if at least one matching resource tag plausibly benefits the action
  - -1 if an opposing faction/resource or registered interference applies
  - cap modifier to ±1
- If result is 4–5: progress +1 segment
- If result is 6+: progress +2 segments
- On roll of 1: trigger a “complication” (optional rule) using Mythic meaning tables for a short narrative tag.
  - **Determinism note:** prefer driving the complication with `DiceRoller` (e.g., percentile rolls + table lookup) rather than creating a new unseeded `random.Random()`.

### 3.4 Completion and replacement
When progress reaches segments:
- Apply `on_complete` effects (territory changes, flags, rumors, scheduled events).
- Create a log entry including the date, action, die result, and completion.
- Replace the completed action with a new one:
  - Default: pick a new action from the library that supports an unfulfilled goal
  - Ensure the 3 actions map to **different goals** as recommended.

## 4) Territory-only rules (Level 1–4)

### 4.1 Territory representation
Territory items:
- `hex` (1 point)
- `settlement` (2 points)
- `stronghold` (3 points)
- `domain` (4 points)

Territory is kept in `FactionState` (not in hex base data).

### 4.2 Level calculation (cap 4)
Compute `territory_points = sum(points)` then:
- Level 1: 0+
- Level 2: 2+
- Level 3: 5+
- Level 4: 9+
(Thresholds are in `faction_rules.json`.)

**Per-turn scaling by level** (recommended to avoid snowballing):
- Levels 1–2: 1 action roll per faction cycle
- Levels 3–4: 2 action rolls per faction cycle

## 5) Effects system

Implement a small “effects interpreter” so JSON can drive world changes without hand-coded branching.

Suggested effect types:
- `claim_territory` {territory:{type,id}}
- `lose_territory`
- `contest_territory` {territory, against:faction_id}
- `fortify_territory`
- `set_flag` {key, delta}
- `add_rumor` {text}
- `apply_modifier_next_turn` {target_faction, modifier, reason}
- `add_relation` {with, delta}

Store global knobs (e.g., `church_faith_crisis`) in `controller.world_state.global_flags`.

## 6) Code changes (repo-oriented)

### 6.1 New modules
Add:
- `src/factions/faction_models.py`
  - dataclasses for FactionDefinition, Resource, Goal, ActionTemplate, ActionInstance, FactionState, LogEntry
- `src/factions/faction_loader.py`
  - loads JSON from `data/content/factions/`
  - validates minimally (schema_version, required keys)
- `src/factions/faction_engine.py`
  - owns all FactionState
  - `initialize()`, `run_cycle(days_passed:int)`, `serialize_state()`, `deserialize_state()`
  - `get_public_state()` for LLM-visible summaries
- `src/factions/faction_effects.py`
  - interprets `on_complete` effect lists and mutates faction/world state

### 6.2 VirtualDM wiring
In `src/main.py`:
- Initialize `FactionEngine` after `GlobalController` is created.
- Register the engine with `self.controller.time_tracker.register_day_callback(...)` (see Wiring Audit section for callback signature and date/time ordering).

In `save_game()`:
- `session.custom_data["faction_state"] = faction_engine.serialize_state()`

In `load_game()`:
- If present, call `faction_engine.deserialize_state(session.custom_data["faction_state"])`

In `get_full_state()`:
- Merge `{"factions": faction_engine.get_public_state()}` into the returned dict so the LLM/UI can reflect ongoing faction events.

### 6.3 LLM prompt surface
Ensure the “public state” includes:
- each faction’s current level and territory points
- the three active actions with progress (and whether they are landmark/hidden/secret goals)
- last N log entries (N=5)

This supports emergent narrative play without needing to expose internal implementation.


### 6.4 Conversation/UI integration (recommended)

Add a minimal player-facing surface so faction play is inspectable and debuggable without the LLM:

- `src/conversation/action_registry.py`
  - Add an action spec like `meta:factions` (or `factions:status`) that returns a `TurnResponse` containing:
    - a short, human-readable status summary (system message), and
    - `public_state["factions"]` populated from `faction_engine.get_public_state()`.
  - (Optional) Add a debug-only `factions:run_cycle` action gated behind `safe_to_execute=False` unless a `--debug` flag exists.

- `src/conversation/suggestion_builder.py`
  - Add a low-priority always-available suggested action: “Faction status”.

This keeps the system playable in offline/mock LLM mode and makes regression testing easier.

## 7) Testing checklist

Add unit tests (even lightweight):
- action selection + roll modifier capping (±1 cap)
- progress advancement logic (4–5 => +1, 6+ => +2)
- completion triggers effects + replacement (new action instance chosen)
- save/load round trip preserving faction state (via `session.custom_data["faction_state"]`)
- cadence trigger: advancing time by 7 days calls exactly one cycle
  - in tests, trigger via `controller.advance_time(7 * 144, reason="test")` (144 turns per day)
- determinism: use the existing `seeded_dice` fixture (`DiceRoller.set_seed(...)`) and avoid `random.Random()` inside faction code


## 8) Rollout steps

1. Add the new `src/factions/` modules and wire initialization + save/load.
2. Drop in the sample content pack into `data/content/factions/`.
3. Start a new session; verify the engine runs after 7 days.
4. Expand faction JSON to cover all desired factions.
5. Add “player interference” hooks:
   - when PCs complete quests, clear locations, or make alliances, call `faction_engine.register_interference(...)`.

---
## Appendix: Example “public state” shape (for LLM)

```json
{
  "cycle_cadence_days": 7,
  "last_cycle_date": "Year 1, Month 2, Day 7",
  "factions": [
    {
      "faction_id": "cold_prince",
      "level": 2,
      "territory_points": 3,
      "active_actions": [
        {"id":"secure_gate","progress":3,"segments":8},
        {"id":"parley_fairy_noble","progress":1,"segments":8},
        {"id":"scout_chell_stones","progress":4,"segments":4,"complete":true}
      ],
      "recent_log": [
        {"date":"Y1-M2-D7","action":"scout_chell_stones","roll":5,"mod":0,"delta":1}
      ]
    }
  ],
  "news": [
    "A thundercrack in clear skies—one of the standing stones has fallen."
  ]
}
```
