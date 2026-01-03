# Comprehensive Code Audit: Dolmenwood Virtual DM

**Audit Date**: 2026-01-03
**Commit**: 77fb0d2
**Auditor**: Claude (code inspection only, no external docs)

---

## Executive Summary

This audit was conducted through direct code inspection of the repository. The codebase is a well-structured Python TTRPG referee system with ~145 source files and ~129 test files. The core philosophy of **Python as referee / LLM as narrator** is correctly implemented throughout.

Many issues from the previous AUDIT_REPORT.md have been addressed (marked with checkmarks below). However, several gaps and new opportunities remain.

---

## Repository Architecture Overview

### Runtime Entry & Turn Lifecycle

1. **Entry point**: `dolmenwood-dm` CLI → `src/main.py:main()`
2. **Orchestrator**: `VirtualDM` class coordinates all subsystems
3. **State Machine**: `StateMachine` in `src/game_state/state_machine.py` (8 states, ~50 valid transitions)
4. **Controller**: `GlobalController` owns `world_state`, `party_state`, `characters`, `time_tracker`
5. **Engines**: HexCrawl, Dungeon, Combat, Encounter, Settlement, Downtime, FairyRoad
6. **Conversation Layer**: `ConversationFacade` → `ActionRegistry` → Engine methods
7. **Response**: `TurnResponse` with messages, suggested_actions, public_state

### Dependency Flow (verified by inspection)

```
CLI/UI → ConversationFacade → VirtualDM
                              ├── GlobalController (state, time, characters)
                              │   ├── StateMachine
                              │   ├── TimeTracker
                              │   └── DiceRoller
                              ├── HexCrawlEngine
                              ├── DungeonEngine
                              ├── CombatEngine → SpellResolver
                              ├── EncounterEngine
                              ├── SettlementEngine
                              ├── DowntimeEngine
                              ├── FairyRoadEngine (NOT WIRED - see C2)
                              ├── FactionEngine
                              ├── DMAgent (optional LLM narrator)
                              └── SessionManager (persistence)
```

---

## Issues Resolved Since Last Audit (Verified Fixed ✅)

| ID | Issue | Resolution |
|----|-------|------------|
| 1 | `wilderness:talk_npc` not executable | ✅ Registered in `action_registry.py:506` |
| 2 | Effect commands not wired | ✅ `_execute_damage`, `_execute_heal`, etc. now call controller methods |
| 3 | RunLog not used in core systems | ✅ Now used in 12 files (up from 5) |
| 4 | MythicGME defaults to non-deterministic | ✅ Now defaults to `DiceRngAdapter` |
| 5 | Entity lookup always returns True | ✅ `_entity_exists_with_reason()` does proper lookup (P10.4) |
| 6 | Settlement NPC talk doesn't enter social | ✅ `initiate_conversation()` is now wired |
| 7 | Missing return_to_previous mappings | ✅ Phase 5.1 added nested state returns |

---

## Remaining Issues & Development Opportunities

### CRITICAL (P0) - Blocking Core Gameplay

#### C1. Dungeon Engine Minimal Integration

**Location**: `src/dungeon/dungeon_engine.py`

**Problem**: The dungeon engine is the least integrated of all engines:
- No spell resolver integration (imported but unused)
- `exit_dungeon()` doesn't properly restore party to the hex they entered from
- No hazard resolver integration
- `handle_player_action()` only handles 3 basic actions (search, rest, map)

**Evidence**:
```python
# src/dungeon/dungeon_engine.py - handle_player_action only handles:
# - "search" (line ~320)
# - "rest" (line ~335)
# - "map" (line ~350)
# All other actions return generic "action not recognized"
```

**Fix**: Wire `NarrativeResolver` and `HazardResolver` to DungeonEngine, similar to HexCrawlEngine.

**Estimated Effort**: 4 hours

---

#### C2. Fairy Road Engine Not Wired to VirtualDM

**Location**: `src/main.py`, `src/fairy_roads/fairy_road_engine.py`

**Problem**: Unlike all other engines, FairyRoadEngine is not instantiated in VirtualDM:

```python
# VirtualDM.__init__() creates these engines:
self.hex_crawl = HexCrawlEngine(self.controller)
self.dungeon = DungeonEngine(self.controller)
self.combat = CombatEngine(self.controller)
self.settlement = SettlementEngine(self.controller)
self.downtime = DowntimeEngine(self.controller)
self.encounter = EncounterEngine(self.controller)
# But NO fairy_road!
```

The FairyRoadEngine exists and is well-implemented, but it's never instantiated in VirtualDM. Actions like `fairy_road:travel`, `fairy_road:enter` are registered in ActionRegistry but will fail because there's no `dm.fairy_road` attribute.

**Fix**: Add `self.fairy_road = FairyRoadEngine(self.controller)` to VirtualDM.__init__()

**Estimated Effort**: 1 hour

---

#### C3. DOWNTIME State Transitions Don't Work

**Location**: `src/downtime/downtime_engine.py:188-220`

**Problem**: The DowntimeEngine doesn't call `controller.transition()` when starting or ending downtime. It manages internal state but doesn't integrate with the state machine:

```python
# Missing controller.transition("begin_downtime") on rest start
# Missing controller.transition("downtime_end_*") on rest completion
```

**Impact**: Party can be "resting" but state machine still shows WILDERNESS_TRAVEL.

**Estimated Effort**: 2 hours

---

### HIGH PRIORITY (P1) - Feature Gaps

#### H1. Combat Spell Resolution Path Incomplete

**Location**: `src/combat/combat_engine.py:650-720`

**Problem**: Combat spell casting via `CAST_SPELL` action type resolves spells through `SpellResolver`, but several spell effect types don't affect combat state:

- Mirror Image spell creates images but `_combat_state` doesn't track them
- Haste spell grants extra actions but initiative tracking doesn't account for it
- Confusion spell should cause random behavior but no behavior table integration

**Evidence**: `MechanicalEffect` has flags like `creates_mirror_images`, `is_haste_effect`, `is_confusion_effect` but CombatEngine doesn't check these.

**Estimated Effort**: 4 hours

---

#### H2. Condition Duration Tracking Incomplete

**Location**: `src/game_state/global_controller.py`, `src/data_models.py`

**Problem**: `Condition` dataclass has duration fields:
```python
@dataclass
class Condition:
    condition_type: ConditionType
    duration_remaining: int = 0
    duration_type: str = "rounds"
```

But `TimeTracker` callbacks don't decrement condition durations. Conditions persist until manually removed.

**Fix**: Register a turn/round callback in GlobalController to decrement condition durations.

**Estimated Effort**: 2 hours

---

#### H3. Polymorph Overlay Not Applied

**Location**: `src/data_models.py:1650-1690`, `src/combat/combat_engine.py`

**Problem**: `PolymorphOverlay` dataclass exists to track polymorphed character stats, but:
- No method to apply polymorph overlay to combat stats
- No restoration when polymorph ends
- Spell resolver can set polymorph but combat doesn't use it

**Estimated Effort**: 3 hours

---

#### H4. Weather Effects Not Applied to Gameplay

**Location**: `src/weather/weather_types.py`, `src/hex_crawl/hex_crawl_engine.py`

**Problem**: Weather system is well-implemented with `WeatherEffect` enums and rules, but effects aren't applied:
- `VISIBILITY_REDUCED` doesn't affect encounter distance
- `TRAVEL_DIFFICULT` doesn't modify travel point costs
- `MISSILE_PENALTY` doesn't affect combat missile attack rolls

**Evidence**: `roll_dolmenwood_weather()` returns `WeatherResult` with effects, but HexCrawlEngine only logs it.

**Estimated Effort**: 3 hours

---

#### H5. XP Awards Not Automatically Calculated

**Location**: `src/advancement/xp_manager.py`

**Problem**: XPManager has methods for XP calculation but they're not called:
- `calculate_combat_xp()` exists but not called after combat ends
- `calculate_treasure_xp()` exists but not called after treasure acquisition
- Level-up detection exists but not triggered automatically

**Fix**: Wire XP calculation into CombatEngine's `_end_combat()` and treasure acquisition flows.

**Estimated Effort**: 2 hours

---

### MEDIUM PRIORITY (P2) - Incomplete Features

#### M1. Replay Infrastructure Not Connected

**Location**: `src/observability/replay.py`

**Problem**: Replay system exists (P10.3 implementation) with `ReplaySession` and `ReplayDiceRoller`, but:
- No CLI flag to enable replay mode
- RunLog snapshots not auto-persisted (only manual)
- No load/resume functionality exposed in VirtualDM

**Partial Solution Exists**: `GameConfig.auto_persist_run_log` and `run_log_persist_dir` are defined but not used.

**Estimated Effort**: 4 hours

---

#### M2. Vector DB Lore Search Not Indexed at Runtime

**Location**: `src/ai/lore_search.py`, `src/vector_db/rules_retriever.py`

**Problem**: Vector DB infrastructure exists but:
- `create_lore_search()` creates an empty index
- Hex descriptions, monster lore, spell text never indexed
- `search_lore()` returns empty results in most cases

**Config Exists**: `use_vector_db`, `skip_indexing` options defined but indexing never triggered.

**Estimated Effort**: 4 hours

---

#### M3. PDF Ingestion Completely Stub

**Location**: `src/content_loader/pdf_parser.py`, `src/main.py:2926`

**Problem**: `--ingest-pdf` CLI flag accepted but:
```python
# main.py line ~2926
if args.ingest_pdf:
    # TODO: Implement PDF ingestion
    print("PDF ingestion not yet implemented")
```

The `pdf_parser.py` module has classes but they're never called.

**Estimated Effort**: 6 hours

---

#### M4. Glyph System Partial

**Location**: `src/data_models.py:2200-2300`, `src/game_state/global_controller.py`

**Problem**: `Glyph` and `GlyphType` dataclasses defined, controller has `_glyphs` dict, but:
- No method to create glyphs from spell effects
- No method to check glyph triggers (door opened, word read)
- Knock spell effect doesn't interact with Glyph of Locking

**Estimated Effort**: 4 hours

---

#### M5. Social Interaction Engine Missing

**Location**: `src/game_state/state_machine.py` (SOCIAL_INTERACTION state)

**Problem**: The game has 8 states including SOCIAL_INTERACTION, but:
- No dedicated `SocialInteractionEngine` class
- `social:*` actions handled inline in ActionRegistry
- No formal conversation tree or negotiation mechanics
- Reaction rolls and disposition don't affect outcomes mechanically

**Current Behavior**: Social state is entered but all logic is ad-hoc.

**Estimated Effort**: 8 hours

---

#### M6. Monster Catalog Not Used for Encounter Generation

**Location**: `src/content_loader/monster_registry.py`, `src/encounter/encounter_factory.py`

**Problem**: `MonsterRegistry` loads monster stats but:
- `EncounterFactory.create_wilderness_encounter()` uses hardcoded creature lists
- Hex encounter tables reference monster names but don't fetch stats
- Combatant stat blocks often left empty

**Evidence**: `Combatant` objects created with `stat_block=None` throughout.

**Estimated Effort**: 3 hours

---

### LOW PRIORITY (P3) - Polish & Cleanup

#### L1. Dead Code in Suggestion Builder

**Location**: `src/conversation/suggestion_builder.py`

The `LEGACY_SUPPORTED_ACTION_IDS` set is now empty but the check remains. Can be removed.

**Estimated Effort**: 15 minutes

---

#### L2. Unused Config Options

**Location**: `src/main.py:121-128`

```python
local_embeddings: bool = False  # Never used
skip_indexing: bool = False  # Never used
```

**Estimated Effort**: 15 minutes

---

#### L3. Inconsistent Type Hints in Mypy-Ignored Modules

**Location**: `pyproject.toml` lists 38 modules with `ignore_errors = true`

Many modules have partial type hints that trigger errors. Should be gradually fixed to enable strict typing.

**Estimated Effort**: Ongoing

---

#### L4. Test Coverage Gaps for New Features

Based on file dates, some newer features lack comprehensive tests:
- `src/factions/faction_oracle.py` - minimal test coverage
- `src/fairy_roads/fairy_road_engine.py` - action registry handlers untested
- `src/settlement/settlement_encounter_adapter.py` - no dedicated tests

**Estimated Effort**: 4 hours

---

## Development Paths Forward

### Path A: Complete Core Gameplay Loop
**Priority**: Immediate

1. **Wire FairyRoadEngine** to VirtualDM (C2 - 1 hour)
2. **Complete DungeonEngine** with narrative/hazard resolvers (C1 - 4 hours)
3. **Fix DowntimeEngine** state transitions (C3 - 2 hours)
4. **Wire condition duration** decrementing (H2 - 2 hours)
5. **Wire weather effects** to gameplay (H4 - 3 hours)

**Total**: ~12 hours

### Path B: Combat Completeness
**Priority**: High

1. **Track combat spell effects** (mirror image, haste, confusion) (H1 - 4 hours)
2. **Apply polymorph overlays** to combat stats (H3 - 3 hours)
3. **Auto-calculate XP** after combat (H5 - 2 hours)
4. **Use MonsterRegistry** for stat blocks (M6 - 3 hours)

**Total**: ~12 hours

### Path C: Observability & Replay
**Priority**: Medium

1. **Wire auto-persist** for RunLog (M1 - 2 hours)
2. **Add replay CLI flag** and session loader (M1 - 4 hours)
3. **Index content** in vector DB at startup (M2 - 4 hours)

**Total**: ~10 hours

### Path D: Advanced Features
**Priority**: Lower

1. **Create SocialInteractionEngine** with conversation mechanics (M5 - 8 hours)
2. **Implement glyph triggers** for spells (M4 - 4 hours)
3. **PDF ingestion pipeline** (M3 - 6 hours)

**Total**: ~18 hours

---

## Files Requiring Most Attention

| Priority | File | Issues |
|----------|------|--------|
| Critical | `src/main.py` | C2 (FairyRoadEngine not created) |
| Critical | `src/dungeon/dungeon_engine.py` | C1 (minimal integration) |
| Critical | `src/downtime/downtime_engine.py` | C3 (no state transitions) |
| High | `src/combat/combat_engine.py` | H1, H3 (spell effects, polymorph) |
| High | `src/game_state/global_controller.py` | H2 (condition durations) |
| High | `src/hex_crawl/hex_crawl_engine.py` | H4 (weather effects) |
| Medium | `src/observability/replay.py` | M1 (not connected) |
| Medium | `src/encounter/encounter_factory.py` | M6 (monster registry) |

---

## Verification Commands

To verify this audit, run:

```bash
# Check FairyRoadEngine not in VirtualDM
grep -n "fairy_road" src/main.py

# Check DungeonEngine action handling
grep -n "handle_player_action" src/dungeon/dungeon_engine.py

# Check condition duration tracking
grep -n "duration_remaining" src/game_state/global_controller.py

# Check weather effect application
grep -n "WeatherEffect" src/hex_crawl/hex_crawl_engine.py

# Check XP manager usage
grep -rn "calculate_combat_xp\|calculate_treasure_xp" src/

# Check polymorph overlay usage
grep -rn "PolymorphOverlay" src/
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Critical Issues (P0) | 3 |
| High Priority Issues (P1) | 5 |
| Medium Priority Issues (P2) | 6 |
| Low Priority Issues (P3) | 4 |
| **Total Issues** | **18** |
| Issues Fixed Since Last Audit | 7 |

---

## Conclusion

The Dolmenwood Virtual DM codebase is architecturally sound with clear separation between:
- **Python referee** (all dice, rules, state in Python)
- **LLM narrator** (optional, advisory only)

The previous audit identified issues that have been substantially addressed. The remaining gaps are primarily about **completing integration** rather than architectural fixes. The 3 critical issues (C1-C3) are all about wiring existing code together, not writing new systems.

The test infrastructure is excellent with seeded dice, mock LLM, and comprehensive fixtures. Any changes should follow the established patterns and maintain test coverage.

### Key Principle to Maintain

> **Python is the referee; the LLM is the narrator.**
> - Python must own: game state, rules resolution, dice, timekeeping, resources, conditions, state transitions, persistence.
> - The LLM must NOT invent mechanics or new world facts. It may narrate outcomes already determined by code, summarize, and suggest options.
> - If a situation cannot be mechanized safely, route it to the oracle/adjudication pathway instead of guessing.
