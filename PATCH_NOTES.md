# Patch Notes: Phases P0-P2 Wiring Gap Fixes

This patch addresses several wiring gaps and improves the overall robustness of the Dolmenwood Virtual DM system.

## Phase 1 (P0): Fix social:oracle_question Runtime Crash

**Problem:** `social:oracle_question` action was crashing at runtime because it tried to import a non-existent function `_mythic_fate_check` from `conversation_facade.py`.

**Fix:** Re-implemented `_social_oracle_question` to use MythicGME directly with DiceRngAdapter for deterministic oracle results.

**New Behavior:**
- Works in both online and offline modes
- Accepts optional `odds` or `likelihood` parameter
- Includes NPC context in oracle questions when available
- Returns structured result with `answer`, `roll`, and `chaos_factor`

## Phase 2 (P1): Freeform Text Routes to social:say

**Problem:** Typing freeform text during SOCIAL_INTERACTION returned "freeform unsupported" error.

**Fix:** Added SOCIAL_INTERACTION branch in `_process_freeform_action()` that routes to `social:say`.

**New Behavior:**
- Typing during social interaction now acts as speaking to the NPC
- No longer returns confusing "unsupported" error

## Phase 3 (P1): social:say Uses Real Narrator Pathway

**Problem:** `social:say` in LLM-enabled mode only returned placeholder text.

**Fix:** Updated `_social_say` to call `dm_agent.generate_simple_npc_dialogue()` when LLM is available.

**New Behavior:**
- LLM-enabled: Calls DmAgent for narration with NPC context
- Offline mode: Provides oracle guidance
- Falls back gracefully on LLM errors
- Respects Python-referee separation (LLM narrates, doesn't decide mechanics)

## Phase 4 (P0/P1): Tighten ActionRegistry vs Legacy

**Problem:** Many suggested action IDs were only handled by legacy if-chains in ConversationFacade.

**Fix:** Registered executors for previously legacy-only actions.

**New Action IDs (registered with executors):**
- `wilderness:resolve_poi_hazard`
- `wilderness:take_item`
- `wilderness:search_location`
- `wilderness:explore_feature`
- `wilderness:enter_poi_with_conditions`
- `wilderness:enter_dungeon`
- `combat:resolve_round`
- `combat:flee`
- `combat:parley`
- `combat:status`
- `combat:end`

**Legacy Whitelist:** Now empty - all suggested actions are registry-registered.

## Phase 5 (P2): Content Load Fails Fast on Empty Hexes

**Problem:** `load_content=True` could silently succeed even if hexes directory was empty.

**Fix:** Added validation in `_load_base_content()` that raises `RuntimeError` if no hexes are loaded.

**New Behavior:**
- Clear error message mentioning hexes and content directory
- Only applies when `load_content=True`
- Does not affect `load_content=False` mode

## Phase 6 (P2): Replace Private Field Reads with Accessors

**Problem:** Some code used `getattr(dm.hex_crawl, "_travel_points_remaining")` instead of public accessors.

**Fix:** Replaced with calls to `get_travel_points_remaining()` and `get_travel_points_total()`.

**Files Changed:**
- `src/conversation/action_registry.py`
- `src/conversation/conversation_facade.py`

---

## Running Tests

```bash
# Run all tests
python -m pytest

# Run specific phase tests
python -m pytest tests/conversation/test_social_oracle_question.py -v
python -m pytest tests/conversation/test_social_freeform_routes_to_social_say.py -v
python -m pytest tests/conversation/test_social_say_llm_enabled_uses_agent.py -v
python -m pytest tests/main/test_load_content_fails_on_empty_hexes.py -v
```

## Test Summary

- All 2905 tests pass
- 6 tests skipped (pre-existing skips)
- New tests added:
  - `tests/conversation/test_social_oracle_question.py` (9 tests)
  - `tests/conversation/test_social_freeform_routes_to_social_say.py` (7 tests)
  - `tests/conversation/test_social_say_llm_enabled_uses_agent.py` (8 tests)
  - `tests/main/test_load_content_fails_on_empty_hexes.py` (3 tests)
