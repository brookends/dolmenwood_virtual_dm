# Dolmenwood Virtual DM — Conversation-First Refactor Plan (Final)

**Updated:** 2025-12-31
**Status:** ✅ MVP Complete - CLI integration and tests done

This plan reflects the current state after implementing the conversation-first interface.

---

## Current Status

### ✅ Completed: `src/conversation/` Package (1,669 lines)

The conversation orchestration layer is **fully implemented**:

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `types.py` | 70 | ✅ Done | ChatMessage, SuggestedAction, TurnResponse |
| `suggestion_builder.py` | 979 | ✅ Done | Context-aware, scored, Dolmenwood-native suggestions |
| `conversation_facade.py` | 526 | ✅ Done | Full action routing for all game states |
| `state_export.py` | 49 | ✅ Done | Versioned state export + EventStream |
| `action_registry.py` | 44 | ✅ Done | Skeleton for Upgrade B |

### ✅ Completed: CLI Integration

| File | Changes | Status | Description |
|------|---------|--------|-------------|
| `src/main.py` | +73 lines | ✅ Done | ConversationFacade integration, numbered selection, render helpers |

### ✅ Completed: Unit Tests (57 tests)

| File | Tests | Status | Description |
|------|-------|--------|-------------|
| `tests/test_conversation_types.py` | 11 | ✅ Done | ChatMessage, SuggestedAction, TurnResponse tests |
| `tests/test_suggestion_builder.py` | 19 | ✅ Done | Suggestion building and helper function tests |
| `tests/test_conversation_facade.py` | 27 | ✅ Done | Facade routing, oracle, dungeon, wilderness tests |

### ✅ Bug Fixes Applied

- Fixed `WorldState.time_of_day` → `WorldState.current_time.get_time_of_day()` in hex_crawl_engine.py
- Fixed `FateCheckResult.answer` → `FateCheckResult.result` in conversation_facade.py
- Fixed `RandomEvent.meaning.action` → `RandomEvent.action` in conversation_facade.py
- Fixed circular imports using `TYPE_CHECKING` pattern

### Key Features Already Implemented

**Suggestion Builder (Dolmenwood-native, ranked by urgency):**
- **Urgent constraints first**: No light, rest due (5 turns), traps detected, no travel points
- **High-frequency procedures**: Move, search, listen, approach POI, parley
- **Nice-to-have utilities**: Map, oracle, state transitions
- **POI-focused workflow**: When at POI, suggestions shift to hazard resolution → enter → talk → take items → enter dungeon → explore → leave
- **Scoring system**: Each candidate gets a score (1-100) based on context signals

**Conversation Facade (complete action routing):**
- **Wilderness**: travel, look_around, search_hex, end_day, approach_poi, resolve_poi_hazard, enter_poi, enter_poi_with_conditions, leave_poi, talk_npc, take_item, search_location, explore_feature, forage, hunt, enter_dungeon
- **Dungeon**: move, search, listen, open_door, pick_lock, disarm_trap, rest, map, fast_travel, exit
- **Encounter**: action routing to EncounterEngine
- **Settlement/Downtime**: freeform delegation to handle_player_action()
- **Meta**: status summary
- **Oracle**: fate_check, random_event, detail_check (Mythic GME fully integrated)

**State Export:**
- Versioned schema (version 1)
- EventStream wraps RunLog for UI consumption

---

## ✅ Completed Work

### Phase 1: CLI Integration ✅ DONE

All CLI integration changes have been applied to `src/main.py`:
- Import of `ConversationFacade`, `TurnResponse`, `SuggestedAction`
- `DolmenwoodCLI.__init__` modified with `self.conv` and `self.last_suggestions`
- Numeric selection handling in `process_command`
- Natural language fallback routing to `handle_chat`
- `_render_turn()` and `_render_suggestions()` helpers added
- Initial suggestions shown on startup via `_show_initial_suggestions()`

### Phase 2: Verification Testing ✅ DONE

#### 2.1 Manual Testing Checklist
```
[x] Start CLI, verify suggestions appear
[x] Type "1" to select first suggestion
[x] Type natural language (e.g., "search the room")
[x] Verify dungeon actions execute correctly (via unit tests)
[x] Verify wilderness travel works (via unit tests)
[x] Verify oracle actions work (via unit tests)
[x] Test state transitions (via unit tests)
```

#### 2.2 Unit Tests ✅ DONE (57 tests)

All suggested tests have been implemented and are passing:
- `tests/test_conversation_types.py` - 11 tests
- `tests/test_suggestion_builder.py` - 19 tests
- `tests/test_conversation_facade.py` - 27 tests

---

## Upgrade Path (Post-MVP)

### Upgrade A: LLM-Driven Intent Parsing

**When:** Pattern matching in ConversationFacade feels limiting

**Goal:** Replace pattern matching with LLM-based intent parsing for higher accuracy.

**Implementation:**

1. Add schema to `src/ai/prompt_schemas.py`:
```python
class IntentParseSchema(PromptSchema):
    """Parse player input into structured action."""
    # Output: action_id, params, confidence, requires_clarification
```

2. Add to `DMAgent`:
```python
def parse_intent(self, player_input: str, context: dict) -> dict:
    """Parse player intent using LLM."""
```

3. Wire in `ConversationFacade.handle_chat`:
```python
# Try LLM parsing first if available
if self._intent_parser and intent.confidence > 0.7:
    return self.handle_action(intent['action_id'], intent.get('params'))
# Fall back to pattern matching
```

### Upgrade B: Canonical ActionRegistry

**When:** Action routing becomes complex or you want tool-guided workflows

**Goal:** Make ActionRegistry authoritative for all actions.

The skeleton is already in `action_registry.py`. To activate:

1. Register all actions with specs:
```python
registry.register(ActionSpec(
    id="dungeon:search",
    label="Search the area",
    params_schema={...},
    executor=lambda dm, p: dm.dungeon.execute_turn(DungeonActionType.SEARCH, p),
))
```

2. Route ConversationFacade.handle_action through registry:
```python
def handle_action(self, action_id: str, params: dict) -> TurnResponse:
    return self.registry.execute(self.dm, action_id, params)
```

### Upgrade C: Foundry VTT Seam

**When:** Ready to add visual representation

**Goal:** Export state deltas and events in Foundry-compatible format.

**Implementation:**

1. Create `src/integrations/foundry/foundry_bridge.py`
2. Support two modes:
   - Snapshot mode: Full state each turn
   - Delta mode: Only state changes
3. Translate events to Foundry socket messages

### Upgrade D: Enhanced Oracle Integration

**When:** Want oracle-based adjudication for ambiguous situations

The template already integrates Mythic GME with:
- `oracle:fate_check` - Yes/No questions with likelihood
- `oracle:random_event` - Random event generation
- `oracle:detail_check` - Meaning word pairs

To enhance for freeform resolution:
1. Detect ambiguous player input in `_handle_freeform`
2. Offer oracle options when `ParsedIntent.requires_clarification`
3. Wire `MythicSpellAdjudicator` for Tier-4 spells in `SpellResolver`

---

## Definition of Done

### ✅ MVP Complete:
- [x] `src/conversation/` package implemented
- [x] CLI integration in `DolmenwoodCLI`
- [x] User can type natural language
- [x] System returns narration + numbered suggestions (up to 9)
- [x] Typing a number executes that suggestion
- [x] All procedural actions route to correct engine methods
- [x] Freeform input routes to `handle_player_action()`
- [x] Manual testing checklist passes
- [x] Unit tests added (57 tests, all passing)
- [x] All 937 tests in suite passing

### Upgrade A Complete When:
- [ ] LLM parses intent with >70% accuracy
- [ ] Graceful fallback to pattern matching

### Upgrade B Complete When:
- [ ] All actions registered in ActionRegistry
- [ ] Parameter validation enforced
- [ ] State validation enforced

### Upgrade C Complete When:
- [ ] State exports in versioned schema
- [ ] Event stream consumable by Foundry
- [ ] Delta mode working for efficiency

### Upgrade D Complete When:
- [ ] Oracle offered for ambiguous inputs
- [ ] Tier-4 spells adjudicated via Mythic

---

## Quick Start (Using the Conversation-First Interface)

The conversation-first interface is now complete. To use it:

1. **Run the CLI:**
   ```bash
   python -m src.main
   ```

2. **Interact with suggestions:**
   - Numbered suggestions appear after each action
   - Type a number (1-9) to execute that suggestion
   - Type natural language to perform freeform actions

3. **Example session:**
   ```
   [wilderness_travel]> look around
   [dm] You survey your surroundings in the forest...

   --- Suggested Actions ---
     1. Travel to hex 0710
     2. Forage for food/water
     3. Ask the Oracle (yes/no)

   [wilderness_travel]> 1
   [System] Traveled to hex 0710...
   ```

4. **Run tests:**
   ```bash
   python -m pytest tests/test_conversation*.py -v
   ```

5. **Next steps:** Consider implementing Upgrade A (LLM intent parsing) for smarter natural language handling

---

## File Summary

### Conversation Package (Complete)
```
src/conversation/
├── __init__.py             (17 lines - exports)
├── types.py                (70 lines)
├── suggestion_builder.py   (979 lines)
├── conversation_facade.py  (526 lines)
├── state_export.py         (49 lines)
└── action_registry.py      (44 lines)

Total: ~1,685 lines
```

### Modified Files
```
src/main.py                (+73 lines - CLI integration)
src/hex_crawl/hex_crawl_engine.py  (bug fix)
```

### Tests Added
```
tests/
├── test_conversation_types.py     (11 tests)
├── test_suggestion_builder.py     (19 tests)
└── test_conversation_facade.py    (27 tests)

Total: 57 new tests (937 total in suite)
```
