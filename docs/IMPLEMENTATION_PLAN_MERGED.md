# Dolmenwood Virtual DM — Conversation-First Refactor Plan (Final)

**Updated:** 2025-12-31
**Status:** Template code merged; CLI integration remaining

This plan reflects the current state after merging template code from `main` branch.

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

## Remaining Work

### Phase 1: CLI Integration (~50 lines)

**File:** `src/main.py` (modify existing `DolmenwoodCLI`)

#### 1.1 Add imports
```python
from src.conversation.conversation_facade import ConversationFacade
from src.conversation.types import TurnResponse
```

#### 1.2 Modify `DolmenwoodCLI.__init__`
```python
class DolmenwoodCLI:
    def __init__(self, dm: VirtualDM):
        self.dm = dm
        self.conv = ConversationFacade(dm)  # ADD
        self.last_suggestions = []           # ADD
        # ... rest of existing init
```

#### 1.3 Add numeric selection at start of `process_command`
```python
def process_command(self, user_input: str) -> bool:
    # Handle numeric input as suggestion selection
    if user_input.strip().isdigit() and self.last_suggestions:
        idx = int(user_input.strip()) - 1
        if 0 <= idx < len(self.last_suggestions):
            action = self.last_suggestions[idx]
            turn = self.conv.handle_action(action.id, action.params)
            self._render_turn(turn)
            return True

    # ... existing command parsing ...
```

#### 1.4 Replace "Unknown command" with chat handling
```python
    # At end of process_command, where unknown commands are handled:
    turn = self.conv.handle_chat(user_input)
    self._render_turn(turn)
    return True
```

#### 1.5 Add render helpers
```python
def _render_turn(self, turn: TurnResponse) -> None:
    """Render a conversation turn response."""
    for msg in turn.messages:
        if msg.role == "system":
            print(f"[System] {msg.content}")
        elif msg.role == "dm":
            print(f"\n{msg.content}")
        else:
            print(msg.content)

    if turn.requires_clarification and turn.clarification_prompt:
        print(f"\n? {turn.clarification_prompt}")

    self._render_suggestions(turn.suggested_actions)

def _render_suggestions(self, suggestions: list) -> None:
    """Render numbered suggestions."""
    self.last_suggestions = suggestions[:9]  # Max 9 for single-digit

    if not self.last_suggestions:
        return

    print("\n--- Suggested Actions ---")
    for i, action in enumerate(self.last_suggestions, 1):
        safe = "" if action.safe_to_execute else " [!]"
        print(f"  {i}. {action.label}{safe}")
    print()
```

### Phase 2: Verification Testing

#### 2.1 Manual Testing Checklist
```
[ ] Start CLI, verify suggestions appear
[ ] Type "1" to select first suggestion
[ ] Type natural language (e.g., "search the room")
[ ] Verify dungeon actions execute correctly
[ ] Verify wilderness travel works
[ ] Verify oracle actions work
[ ] Test state transitions
```

#### 2.2 Unit Tests to Add

**`tests/test_conversation_types.py`**
```python
def test_turn_response_to_dict():
    """Test TurnResponse serialization."""
    from src.conversation.types import TurnResponse, ChatMessage, SuggestedAction

    response = TurnResponse(
        messages=[ChatMessage("dm", "You search the room.")],
        suggested_actions=[SuggestedAction(id="dungeon:move", label="Go north")],
    )
    d = response.to_dict()
    assert d["messages"][0]["content"] == "You search the room."
    assert d["suggested_actions"][0]["id"] == "dungeon:move"

def test_suggested_action_defaults():
    """Test SuggestedAction default values."""
    from src.conversation.types import SuggestedAction

    action = SuggestedAction(id="test:action", label="Test")
    assert action.safe_to_execute == True
    assert action.params == {}
```

**`tests/test_suggestion_builder.py`**
```python
def test_dungeon_suggestions_include_light_warning():
    """When no light, light suggestion should be top priority."""
    # Setup dungeon state with no light
    # Verify light suggestion has score 100

def test_rest_suggestion_urgent_after_5_turns():
    """Rest becomes urgent after 5 turns without rest."""
    # Setup dungeon with turns_since_rest >= 5
    # Verify rest suggestion is prioritized

def test_poi_workflow_suggestions():
    """At POI, suggestions should focus on POI actions."""
    # Setup hex_crawl with at_poi=True
    # Verify suggestions include enter, talk, take, leave
```

**`tests/test_conversation_facade.py`**
```python
def test_handle_chat_routes_hex_id():
    """Hex IDs in chat should route to travel."""
    # Input: "I want to go to 0710"
    # Verify: wilderness:travel action executed

def test_handle_action_dungeon_search():
    """dungeon:search action should execute correctly."""
    # Setup dungeon state
    # Call handle_action("dungeon:search", {})
    # Verify turn result

def test_oracle_fate_check():
    """Oracle fate check should return result."""
    # Call handle_action("oracle:fate_check", {"question": "Is it true?"})
    # Verify oracle result in messages
```

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

### MVP Complete When:
- [x] `src/conversation/` package implemented
- [ ] CLI integration in `DolmenwoodCLI`
- [ ] User can type natural language
- [ ] System returns narration + numbered suggestions (up to 9)
- [ ] Typing a number executes that suggestion
- [ ] All procedural actions route to correct engine methods
- [ ] Freeform input routes to `handle_player_action()`
- [ ] Manual testing checklist passes

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

## Quick Start (What To Do Now)

1. **Verify the template code was merged:**
   ```bash
   ls -la src/conversation/
   # Should show 5 Python files
   ```

2. **Apply CLI integration** to `src/main.py`:
   - Add imports
   - Modify `__init__`
   - Add numeric selection handling
   - Add render helpers

3. **Test manually:**
   ```bash
   python -m src.main
   # Type: "look around"
   # Type: "1" (to select first suggestion)
   ```

4. **Add unit tests** (optional but recommended)

5. **When stable:** Implement Upgrade A (LLM intent parsing)

---

## File Summary

### Already Implemented (from template)
```
src/conversation/
├── __init__.py           (1 line)
├── types.py              (70 lines)
├── suggestion_builder.py (979 lines)
├── conversation_facade.py (526 lines)
├── state_export.py       (49 lines)
└── action_registry.py    (44 lines)

Total: 1,669 lines
```

### Still To Modify
```
src/main.py               (+50 lines to DolmenwoodCLI)
```

### Tests To Add
```
tests/
├── test_conversation_types.py
├── test_suggestion_builder.py
├── test_conversation_facade.py
└── test_conversation_integration.py
```
