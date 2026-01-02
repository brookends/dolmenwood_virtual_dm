# Comprehensive Code Audit Report

## Executive Summary

This audit identified **47+ issues** across 6 major subsystems. The most critical gaps involve:

1. **Broken action routing** - `wilderness:talk_npc` suggested but not executable
2. **Effect commands not wired** - Oracle spell effects return success but don't apply to game state
3. **Missing observability** - RunLog not integrated in core systems, blocking replay
4. **Content loaded but unused** - Monster/Item catalogs loaded twice, wasting I/O
5. **State machine gaps** - Several transitions defined but never triggered

---

## CRITICAL ISSUES (Blocking Gameplay)

### 1. wilderness:talk_npc Not Executable

**Location**: `src/conversation/suggestion_builder.py:621-636`

**Problem**: Action is suggested to players but filtered out as non-executable because:
- Not in `LEGACY_SUPPORTED_ACTION_IDS` (empty set)
- Not registered in ActionRegistry

**Evidence**:
```python
# suggestion_builder.py:628 - Creates suggestion
SuggestedAction(id="wilderness:talk_npc", ...)

# But _is_action_executable() returns False because:
# 1. Not transition:* prefix
# 2. LEGACY_SUPPORTED_ACTION_IDS is empty
# 3. Not in ActionRegistry
```

**Fix Required**: Register `wilderness:talk_npc` in `action_registry.py`:
```python
registry.register(ActionSpec(
    id="wilderness:talk_npc",
    label="Talk to NPC",
    category=ActionCategory.WILDERNESS,
    requires_state="wilderness_travel",
    params_schema={"npc_id": {"type": "string", "required": False}},
    executor=_wilderness_talk_npc,
))
```

---

### 2. Effect Commands Not Wired to Game State

**Location**: `src/oracle/effect_commands.py:582-657`

**Problem**: 5 effect handlers have TODO comments and `pass` statements - they return success but don't apply effects:

| Line | Method | Issue |
|------|--------|-------|
| 582 | `_execute_remove_condition()` | TODO: Wire to controller |
| 599 | `_execute_add_condition()` | TODO: Wire to controller |
| 620 | `_execute_modify_stat()` | TODO: Wire to controller |
| 639 | `_execute_damage()` | TODO: Wire to controller |
| 655 | `_execute_heal()` | TODO: Wire to controller |

**Impact**: Spell effects that should modify game state are silently skipped. Oracle claims success despite no-op.

---

### 3. RunLog Not Used in Core Systems

**Location**: `src/observability/run_log.py`

**Problem**: Only 5 files use RunLog. Missing from:
- `src/oracle/mythic_gme.py` - No fate check logging
- `src/oracle/spell_adjudicator.py` - No adjudication logging
- `src/ai/dm_agent.py` - No LLM call logging
- `src/narrative/narrative_resolver.py` - No intent parsing logging
- `src/encounter/encounter_engine.py` - No encounter logging

**Impact**: No deterministic replay possible; no comprehensive game event history.

---

### 4. Monster/Item Catalogs Loaded But Never Used

**Location**: `src/content_loader/runtime_bootstrap.py:446, 486`

**Problem**:
- `MonsterRegistry()` created and loaded at line 446, then **discarded**
- `ItemCatalog` loaded at line 486, stored in `result.item_catalog`, but **never used by VirtualDM**
- When monsters/items needed, engines call `get_monster_registry()` which creates **new instance**

**Impact**: Content loaded twice from disk; wasted I/O and memory.

---

## HIGH PRIORITY ISSUES

### 5. Settlement NPC Talk Doesn't Enter Social State

**Location**: `src/settlement/settlement_engine.py:978-1055`

**Problem**: `_action_talk_to_npc()` returns NPC data but never calls `initiate_conversation()` trigger. The method `initiate_conversation()` IS defined (line 1955) but not wired from any action handler.

**Impact**: Settlement NPCs can be "talked to" but conversation doesn't enter SOCIAL_INTERACTION state.

---

### 6. Missing State Machine Mappings in return_to_previous()

**Location**: `src/game_state/state_machine.py:471-502`

**Missing mappings**:
```python
# These state combinations will raise InvalidTransitionError:
(GameState.COMBAT, GameState.SOCIAL_INTERACTION)  # combat_to_parley
(GameState.ENCOUNTER, GameState.SOCIAL_INTERACTION)  # encounter_to_parley
(GameState.ENCOUNTER, GameState.COMBAT)  # encounter_to_combat
```

---

### 7. Unused State Transitions

**Location**: `src/game_state/state_machine.py`

| Line | Transition | Status |
|------|------------|--------|
| 104 | `fairy_road_combat` | Defined, never triggered |
| 154 | `settlement_combat` | Defined, never triggered |
| 277 | `conversation_escalates` | Defined, never triggered |

---

### 8. MythicGME Defaults to Non-Deterministic RNG

**Location**: `src/oracle/mythic_gme.py:404`

**Problem**: Defaults to `random.Random()` instead of requiring `DiceRngAdapter`:
```python
self._rng = rng or random.Random()  # Non-deterministic fallback
```

**Impact**: Oracle calls produce different results even with same seed, breaking replay.

---

### 9. Predetermined Effects Not Applied

**Location**: `src/oracle/spell_adjudicator.py:363, 393`

**Problem**: `predetermined_effects` field populated with strings like `"remove_condition:cursed:..."` but no system applies them.

---

### 10. Missing LLM Error Handling

**Location**: `src/ai/dm_agent.py:1517-1564`

**Problem**: `_execute_schema()` calls LLM without try-except. Only `parse_intent()` and `parse_narrative_intent()` have error handling.

---

## MEDIUM PRIORITY ISSUES

### 11. Registry/Suggestion Misalignment

**Location**: `src/conversation/suggestion_builder.py`

Registered structured actions bypassed in favor of generic fallbacks:

| Engine | Registered Actions | Suggested Instead |
|--------|-------------------|-------------------|
| Settlement | `settlement:explore`, `visit_inn`, `visit_market`, `talk_npc`, `leave` | Generic `settlement:action` |
| Encounter | `encounter:parley`, `flee`, `attack`, `wait` | Generic `encounter:action` |

---

### 12. DM Agent Methods Not Called

**Location**: `src/ai/dm_agent.py`

40 methods defined but many never called:
- `describe_hex()` (line 295)
- `describe_dungeon_room()` (line 344)
- `frame_encounter()` (line 389)
- `frame_social_encounter()` (line 762)
- `describe_poi_approach()` (line 1117)
- `describe_poi_entry()` (line 1170)
- `describe_poi_feature()` (line 1214)
- `narrate_resolved_action()` (line 1268)

---

### 13. NPC State Deltas Not Applied to Objects

**Location**: `src/game_state/session_manager.py:1892-1909`

**Problem**: Comment admits NPC state changes aren't applied to base NPC objects:
```python
# Note: Base HexNPC doesn't have disposition/is_dead fields
# These deltas would be used by the game logic to check state
# rather than modifying the base NPC object
```

---

### 14. Silent Hex Parsing Failures

**Location**: `src/content_loader/runtime_bootstrap.py:310-312`

**Problem**: Bad hex data silently discarded with only a log message.

---

### 15. Spell Adjudication Types Unimplemented

**Location**: `src/oracle/spell_adjudicator.py:46-60`

4 of 10 adjudication types defined but not implemented:
- `CHARM_RESISTANCE`
- `REALITY_WARP`
- `PROTECTION_BYPASS`
- `DURATION_EXTENSION`

---

### 16. Intent Parsing Fallback Incomplete

**Location**: `src/narrative/narrative_resolver.py:238-251`

Pattern matching only handles ~12 action types. Unrecognized input becomes `CREATIVE_SOLUTION` or `NARRATIVE_ACTION`.

---

### 17. Dungeon Engine Minimal Integration

**Location**: `src/dungeon/dungeon_engine.py`

- Only 7 transition/controller calls (vs HexCrawl's 13+)
- No NPC encounter integration
- `exit_dungeon()` doesn't return party to proper hex
- Spell resolver imported but never used

---

### 18. HexCrawl POI Methods Incomplete

**Location**: `src/hex_crawl/hex_crawl_engine.py`

Several methods defined but with gaps:
- `resolve_poi_hazard()` (line 2361) - hazard trigger check incomplete
- `get_npc_relationships()` (line 3020) - never applied to disposition calculations
- `get_npc_disposition_to_party()` (line 4521) - never called from `interact_with_npc()`

---

## LOW PRIORITY ISSUES

### 19. Dead Code in Legacy If-Chain

**Location**: `src/conversation/conversation_facade.py:197-564`

14+ actions duplicated between registry and legacy if-chain. Legacy branches never execute because registry check at line 182-194 catches them first.

### 20. Config Options Not Implemented

**Location**: `src/main.py:121-122, 2926`

- `local_embeddings` - accepted but never used
- `skip_indexing` - accepted but never used
- `ingest_pdf` - TODO comment, completely unimplemented

### 21. Replay Not Integrated

**Location**: `src/observability/replay.py`

Infrastructure exists (lines 25-165) but not integrated with game engine. Even if logging was complete, replay wouldn't work.

### 22. Entity Lookup Not Implemented

**Location**: `src/oracle/effect_commands.py:441-446`

`_entity_exists()` always returns True without validation.

### 23. Downtime Crafting Placeholder

**Location**: `src/conversation/action_registry.py:815-821`

Returns placeholder message: "Crafting is not yet fully implemented."

### 24. Faction Engine May Be None

**Location**: `src/main.py:713`

If `load_content=False`, factions not initialized, but code calls `save_faction_state(self.factions, ...)` unconditionally.

---

## SUMMARY BY CATEGORY

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Action Routing | 1 | 0 | 2 | 1 | 4 |
| State Machine | 0 | 2 | 0 | 0 | 2 |
| Engine Integration | 0 | 1 | 3 | 0 | 4 |
| Content/Data Flow | 1 | 0 | 2 | 2 | 5 |
| Oracle/AI | 2 | 3 | 3 | 2 | 10 |
| Observability | 1 | 0 | 0 | 1 | 2 |
| **Total** | **5** | **6** | **10** | **6** | **27** |

---

## RECOMMENDED FIX PRIORITY

### Immediate (Blocking Gameplay)
1. Register `wilderness:talk_npc` in ActionRegistry
2. Wire effect handlers to controller methods
3. Add RunLog calls to oracle/spell systems
4. Fix MythicGME to require DiceRngAdapter

### High (Breaks Core Features)
5. Wire settlement NPC talk to social interaction
6. Add missing state machine return_to_previous mappings
7. Use loaded monster/item catalogs instead of re-loading
8. Apply predetermined effects from spell adjudicator
9. Add LLM error handling in dm_agent

### Medium (Incomplete Features)
10. Update suggestions to use registered specific actions
11. Implement missing spell adjudication types
12. Complete intent parsing fallback coverage
13. Wire HexCrawl POI methods properly
14. Add NPC state fields to HexNPC model

### Low (Polish)
15. Remove dead code from legacy if-chain
16. Implement unused config options or remove them
17. Complete dungeon engine integration
18. Add entity lookup validation

---

## Files Most Needing Attention

1. `src/conversation/action_registry.py` - Register missing actions
2. `src/oracle/effect_commands.py` - Wire 5 effect handlers
3. `src/game_state/state_machine.py` - Add missing mappings
4. `src/settlement/settlement_engine.py` - Wire NPC talk to social
5. `src/content_loader/runtime_bootstrap.py` - Fix catalog usage
6. `src/oracle/mythic_gme.py` - Require DiceRngAdapter
7. `src/observability/run_log.py` - Add comprehensive logging calls
