# Dolmenwood Virtual DM — Patch Plan (Blockers + Gaps)

This plan is written to be **directly executable by an LLM with repo access**. It is organized in phases with concrete file targets, implementation notes, and acceptance criteria.

> Guiding principle: **Keep mechanics authoritative in Python.** Narration hooks should only consume resolved results.

---

## Phase 0 — Baseline hygiene (small but important)

### 0.1 Add missing `README.md` (packaging fix)
**Why:** `pyproject.toml` references `README.md` but it is not present at repo root.

- **Create:** `README.md` (short: install, run, test)
- **Acceptance:** `poetry build` (or metadata inspection) no longer warns about missing README.

### 0.2 Add a “content required” warning in CLI
**Why:** Many procedures behave like placeholders unless base content is loaded.

- **Edit:** `src/main.py` CLI start-up: if `--load-content` is false, print a clear warning.
- **Acceptance:** Running without content prints a single, non-spam warning.

---

## Phase 1 — Wire base content into runtime (BLOCKER)

### Problem
The repo contains complete loaders and registries under `src/content_loader/`, but `VirtualDM` does not populate engines/registries at startup. Save/load deltas (`SessionManager`) also assume base content exists.

### Goal
Make `--load-content` (and `GameConfig.load_content`) actually load:
- hexes → `HexCrawlEngine._hex_data`
- monsters → `MonsterRegistry` singleton (for encounter tables/factory)
- spells → `SpellResolver` (for combat spell casting) and/or `SpellRegistry`
- items → `ItemCatalog` (for shopping/inventory validation)

…and ensure `load_game()` loads base content before applying session deltas.

### 1.1 Implement a runtime bootstrapper
**Create:** `src/content_loader/runtime_bootstrap.py`

Suggested API:

```python
@dataclass
class RuntimeContent:
    hexes: dict[str, HexLocation]
    spells: dict[str, SpellData]
    monster_registry: MonsterRegistry
    item_catalog: ItemCatalog
    warnings: list[str]
    stats: dict[str, Any]  # counts, failures
```

```python
def load_runtime_content(
    *,
    content_root: Path,
    controller: GlobalController,
    enable_vector_db: bool,
    mock_embeddings: bool,
    local_embeddings: bool,
    skip_indexing: bool,
) -> RuntimeContent:
    ...
```

Implementation notes:
- Hexes: reuse `HexDataLoader._parse_hex_item()` *or* add a small public helper in `hex_loader.py` (recommended) so runtime code doesn’t call private methods.
- Monsters: call `get_monster_registry().load_from_directory(...)` using `data/content/monsters`.
- Spells: use `SpellDataLoader.load_all_spells()` then build `{spell_id: SpellData}`.
- Items: construct `ItemCatalog(data_dir=...)` and call `load()` once.

Keep it **pure and dependency-light**:
- If vector DB optional deps aren’t installed, return a warning and continue without indexing.
- Avoid writing to SQLite in runtime bootstrap unless you explicitly intend to persist/import (optional).

### 1.2 Wire bootstrap into `VirtualDM.__init__`
**Edit:** `src/main.py`

- After constructing engines, if `self.config.load_content`:
  1. Call `load_runtime_content(...)`
  2. Inject hexes: `for hid, hx in content.hexes.items(): self.hex_crawl.load_hex_data(hid, hx)`
  3. Inject spells: create controller-aware resolver:
     - `spell_resolver = SpellResolver(spell_database=content.spells, controller=self.controller)`
     - pass into `CombatEngine(self.controller, spell_resolver=spell_resolver)`
     - (this requires moving CombatEngine initialization until after content load, or allowing reassignment)
  4. Ensure monster registry is loaded before any encounter rolling.
  5. Store reference: `self.content = content` (optional, for diagnostics)

- **Acceptance:**
  - Starting with `--load-content` populates `HexCrawlEngine.get_hex_data(hex_id)` for known hexes.
  - Combat spell lookup works: `self.combat.spell_resolver.lookup_spell("...")` returns data.
  - Encounters can create real combatants via `MonsterRegistry.create_combatant(...)`.

### 1.3 Fix save/load ordering (session deltas require base content)
**Edit:** `VirtualDM.load_game()` in `src/main.py`

- Ensure base content is loaded **before** `self.session_manager.apply_to_hex_engine(self.hex_crawl)`.
- If content is not loaded and `load_game()` is called, either:
  - auto-load base content (recommended), or
  - raise a clear error that base content is required.

- **Acceptance:** Loading a save applies explored hexes, scheduled events, and POI/NPC deltas without exceptions.

### 1.4 Tests to add
**Create:** `tests/test_content_bootstrap_runtime.py`
- `test_runtime_bootstrap_loads_hexes_spells_monsters()` (fast: just counts and a couple lookups)
- `test_load_game_applies_session_state_after_content_load()` (create minimal save, load, verify `hex_crawl._explored_hexes` etc)

---

## Phase 2 — Wire encounter tables into hex travel (BLOCKER)

### Problem
`HexCrawlEngine._generate_encounter()` creates a mostly-empty `EncounterState` for “standard encounters”. The repo already contains:
- `EncounterRoller` (table orchestration) in `src/tables/encounter_roller.py`
- `EncounterFactory` (builds `EncounterState` + combatants) in `src/encounter/encounter_factory.py`

…but they are not used from wilderness travel.

### Goal
When wilderness travel triggers an encounter, generate a fully-populated `EncounterState` using encounter tables + monster registry, then hand it to `EncounterEngine`.

### 2.1 Integrate `EncounterRoller` + `EncounterFactory` into `HexCrawlEngine`
**Edit:** `src/hex_crawl/hex_crawl_engine.py`

Recommended approach:
- Keep contextual encounter modifiers logic as “override layer” (it’s already Dolmenwood-native).
- If no contextual modifier triggers, do:

```python
from src.tables.encounter_roller import EncounterRoller, EncounterContext
from src.encounter.encounter_factory import EncounterFactory

context = EncounterContext(
    region=hex_data.region or "...",
    terrain=terrain.value,
    time_of_day=self.controller.world_state.time_of_day.value,
    location_type="wilderness",
    is_aquatic=...,
    active_unseason=self.controller.world_state.active_unseason,
    # any other fields required by EncounterContext
)
rolled = self._encounter_roller.roll_encounter(context, roll_activity=True, check_lair=True)
factory_result = self._encounter_factory.from_rolled(rolled, terrain=terrain.value, ...)
encounter = factory_result.encounter_state
```

- Store additional rolled details on `encounter.contextual_data` if helpful (lair, hoard, NPC lists).
- Ensure `controller.set_encounter(encounter)` is still called.

**Where to instantiate roller/factory:** in `HexCrawlEngine.__init__` as lazily created singletons.

### 2.2 Acceptance criteria
- A travel-triggered encounter has:
  - `encounter.combatants` populated for monster/animal encounters
  - proper `distance` and `surprise_status` from the roller
  - optional `hoard` and `lair_description` when in lair
- `EncounterEngine.start_encounter(encounter, ...)` can run without needing additional scaffolding.

### 2.3 Tests to add
**Create:** `tests/test_hex_travel_encounter_integration.py`
- Force an encounter trigger (monkeypatch `_check_encounter` to True)
- Assert returned `TravelSegmentResult.encounter` has populated fields (`combatants`, `distance`, etc.)

---

## Phase 3 — Unify conversation action routing (high leverage)

### Problem
There are two competing systems:
- `ConversationFacade.handle_action()` has a manual dispatch `if/elif` chain.
- `ActionRegistry` defines canonical actions with schemas and executors.

### Goal
Make `ConversationFacade` use `ActionRegistry.execute(...)` as the single source of truth.

### 3.1 Replace manual dispatch with registry execution
**Edit:** `src/conversation/conversation_facade.py`

- Construct a registry once (probably in `__init__`): `self.registry = create_default_action_registry()`
- In `handle_action(action_id, params)`:
  - call `result = self.registry.execute(self.dm, action_id, params)`
  - convert result into `TurnResponse` messages
  - attach `suggested_actions = build_suggestions(...)`
  - set `public_state = self.dm.get_full_state()` (or current public subset)
- Preserve action IDs already used by `SuggestionBuilder`.

### 3.2 Acceptance criteria
- Existing conversation tests pass.
- New actions can be added by editing `action_registry.py` only (no façade edits).

---

## Phase 4 — Fix explicit TODO mechanics gaps (small, testable)

### 4.1 Encounter evasion speed uses constants
**Edit:** `src/encounter/encounter_engine.py` (TODO near `get_party_movement_rate()`)

- Replace hard-coded `30`/`60` with:
  - `party_speed = self.controller.get_party_movement_rate()` (or compute from `PartyState`)
  - `enemy_speed = max(combatant.speed for combatant in encounter.combatants if combatant.is_active)`
- Ensure `enemy_speed` handles missing speed (fallback to table default by monster size/type).

### 4.2 Dungeon item consumption not wired
**Edit:** `src/dungeon/dungeon_engine.py` at TODO “Wire to inventory system”
- When an action consumes an item:
  - call `character.consume(item_id, quantity=1, ...)` (or controller helper if preferred)
  - then `self.controller.update_party_encumbrance()`

### 4.3 Thief lock-picking check stub
**Edit:** `src/narrative/hazard_resolver.py` TODO: implement thief lock-pick logic
- Integrate a Dex check + thief skill bonus if class matches (or consult `classes` subsystem).
- Add deterministic tests for success/failure paths.

---

## Phase 5 — Condition enforcement alignment (quality + correctness)

The repo includes a condition reference document: `docs/CONDITIONS.md`. Conditions marked **Partial**/**Pending** should either be:
- fully enforced in mechanics, or
- explicitly treated as narrative-only until implemented.

### 5.1 Implement a centralized “condition effects” layer
**Target:** a single place combat/encounter/dungeon consult for modifiers:
- attack penalties
- movement penalties
- action restrictions
- perception penalties, etc.

Suggested location:
- `src/game_state/condition_effects.py` (new) or extend `GlobalController` helpers.

### 5.2 Prioritize conditions (from `docs/CONDITIONS.md`)
**Pending:** CHARMED, DEAFENED, DREAMLESS, INCAPACITATED, INVISIBLE, PETRIFIED
**Partial:** BLINDED, CURSED, DEHYDRATED, DISEASED, FRIGHTENED, LOST, PARALYZED, PRONE, RESTRAINED, STUNNED

Acceptance:
- Combat and encounter checks consistently call the same modifier hooks.

---

## Phase 6 — Narration hook completion (coverage)

There is a detailed checklist in `docs/NARRATION_GAP_ASSESSMENT.md`. Missing hooks currently include:

### Critical
- `enter_settlement()` — Settlement arrival
- `visit_building()` — Building entry

### High
- `approach_poi()` — POI approach (schema exists)
- `enter_poi()` — POI entry (schema exists)
- `explore_poi_feature()` — Feature interaction (schema exists)
- `enter_dungeon()` — Dungeon entry atmosphere
- `move_to_room()` — Room transition description
- `initiate_conversation()` — NPC meeting (schema exists)

### Medium
- `search_hex()` — Feature discovery narration
- `discover_poi()` — Hidden POI discovery
- `search_room()` — Search action narration
- `start_combat()` — Combat initiation scene
- `check_morale()` — Morale break narration
- `process_fleeing()` — Pursuit/escape narration
- `browse_goods()` — Shop interior
- `seek_lodging()` — Inn atmosphere
- `visit_temple()` — Temple atmosphere
- `resolve_reaction()` — Reaction roll outcome
- `attempt_parley()` — Social interaction attempt

### Low
- `describe_sensory_hints()` — Atmospheric clues (returns Python text)
- `listen_at_door()` — Listen action narration
- `force_door()` — Door forcing narration
- `resolve_attack()` — Individual attack narration
- `attempt_evasion()` — Evasion attempt narration
- `train_skill()` — Training montage
- `craft_item()` — Crafting narration
- `research()` — Research narration

Implementation pattern:
- Engines produce a `NarrationContext` (resolved facts only)
- `VirtualDM.narrate_*` calls `DMAgent.describe(context)`
- No mutation, no dice, no state changes in narration

Add tests following existing narration patterns in `tests/test_narration_*.py`.

---

## Phase 7 — Optional improvements (defer until blockers done)

- DB-backed table loading: replace hard-coded tables with JSON/SQLite loaders where it adds value.
- Foundry bridge: wire `integrations/foundry/foundry_bridge.py` into a socket/export loop.
- Lore search: enable vector DB retrieval for narration enrichment once content indexing is stable.

---

## Suggested execution order (if you want “playable” fastest)

1. Phase 1 (content bootstrap)  
2. Phase 2 (encounter tables wired into travel)  
3. Phase 3 (action routing unification)  
4. Phase 4 (TODO mechanics)  
5. Phase 6 (narration gaps)  
6. Phase 5 (conditions)  
7. Phase 7 (optional)
