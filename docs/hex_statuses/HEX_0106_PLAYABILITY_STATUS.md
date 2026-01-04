# Hex 0106 (The Outlook and the Red Monolith) - Playability Status

## Summary

This document tracks what aspects of hex 0106's gameplay are automated vs. require manual DM intervention.

**Date:** 2026-01-03
**Implementation Version:** 2.0 (Core Gaps Fixed)

---

## What's Fully Implemented

### Hex Data Loading
- All hex properties, terrain, coordinates loaded correctly
- Procedural data (lost chance, encounter chance, foraging) parsed
- Night hazards defined in data (2 hazards)

### Points of Interest (2 Total)
- **Granite Crag** - Full description, entering/exploring/leaving, hazards defined
- **The Red Vorpal Monolith** - Full description, seasonal behavior, hazards defined

### Roll Tables
- Crag Base Discoveries (d6, 6 unique entries with `unique_entries: true`)
- Unique entry deduplication supported in `hex_crawl_engine.py:5167-5241`

### Items
- Bone Talisman (magical, +1 vs terror saves)
- Obsidian Shard (magical, doubles shadow/darkness spell duration)

### Test Coverage
- `tests/content_loader/test_hex_0106_loading.py` - 23 tests for content loading
- `tests/test_hex_0106_hazards.py` - 24 tests for hazard mechanics (NEW)

---

## What's NOW Playable (Fixed in v2.0)

### 1. RESTLESS_SLEEP Condition - FIXED
**Previous Gap:** Condition not defined in ConditionType enum

**Solution Implemented:**
- Added `ConditionType.RESTLESS_SLEEP` enum value
- Added to `CONDITION_BLOCKED_ACTIONS` (no blocked actions, informative message)
- Added to `CONDITION_ROLL_MODIFIERS` with `hp_recovery: 0` and `spell_memorization: False`

**Location:** `src/data_models.py`
**Tests:** 2 tests in `tests/test_hex_0106_hazards.py`

---

### 2. TERROR Condition - FIXED
**Previous Gap:** Condition not defined for monolith terror hazard

**Solution Implemented:**
- Added `ConditionType.TERROR` enum value
- Added to `CONDITION_BLOCKED_ACTIONS` (blocks combat, spell, exploration; allows movement for fleeing)
- Added to `CONDITION_ROLL_MODIFIERS` with `climbing_checks: -2` and `forces_flee: True`

**Location:** `src/data_models.py`
**Tests:** 2 tests in `tests/test_hex_0106_hazards.py`

---

### 3. COMPELLED Condition - FIXED
**Previous Gap:** Generic compelled condition not defined (different from COMPELLED_DANCING)

**Solution Implemented:**
- Added `ConditionType.COMPELLED` enum value
- Added to `CONDITION_BLOCKED_ACTIONS` (allows only movement)
- Added to `CONDITION_ROLL_MODIFIERS` with `forces_movement: True`, `can_be_restrained: True`, `removal: time_of_day_dawn`

**Location:** `src/data_models.py`
**Tests:** 2 tests in `tests/test_hex_0106_hazards.py`

---

### 4. Seasonal POI State Checking - FIXED
**Previous Gap:** No engine code to determine active POI effects based on season

**Solution Implemented:**
- Added `get_poi_seasonal_state()` method to HexCrawlEngine
- Added `is_poi_effect_active()` method for effect checking
- Returns current state, active effects, and seasonal metadata

**Location:** `src/hex_crawl/hex_crawl_engine.py`
**Tests:** 3 tests in `tests/test_hex_0106_hazards.py`

---

### 5. Winter Night Trigger Detection - FIXED
**Previous Gap:** "winter_night" triggers were matching generic "night" check

**Solution Implemented:**
- Added `_is_winter()` helper method
- Added explicit "winter_night" trigger type in `process_night_hazards()`
- Excluded "winter_night" from generic night matching

**Location:** `src/hex_crawl/hex_crawl_engine.py`
**Tests:** 4 tests in `tests/test_hex_0106_hazards.py`

---

### 6. Ability Check for Climbing - FIXED
**Previous Gap:** Hazards with `check_type: "dexterity"` not handled

**Solution Implemented:**
- Added `check_type` handling in `_resolve_hazard()`
- Uses OSE ability check rules (roll d20, success if <= ability score)
- Properly routes ability checks separate from saving throws

**Location:** `src/hex_crawl/hex_crawl_engine.py`
**Tests:** 1 test in `tests/test_hex_0106_hazards.py`

---

### 7. Arcane Caster Save Modifier - FIXED
**Previous Gap:** `modifier_arcane_casters` not applied

**Solution Implemented:**
- Added class-based modifier detection in `_resolve_hazard()`
- Checks for arcane classes (magic-user, elf, mage, wizard, sorcerer)
- Applies bonus to save modifier

**Location:** `src/hex_crawl/hex_crawl_engine.py`
**Tests:** 2 tests in `tests/test_hex_0106_hazards.py`

---

### 8. Sleep Near Monolith Trigger - FIXED
**Previous Gap:** "sleep_near_monolith" trigger pattern not detected

**Solution Implemented:**
- Added `sleep_near_*` trigger pattern in `process_night_hazards()`
- Uses `_hex_has_feature()` to check for matching POI

**Location:** `src/hex_crawl/hex_crawl_engine.py`
**Tests:** 1 test in `tests/test_hex_0106_hazards.py`

---

## What's NOT Playable (Remaining Gaps)

### 1. Lost Behavior with POI Attraction
**Gap:** Lost characters should have 2-in-6 chance per watch of stumbling upon Granite Crag.

**Impact:**
- Special lost behavior unique to this hex
- Characters drawn to the crag by subtle monolith influence

**Priority:** Medium (enhanced mechanics)

---

### 2. Spell Permanence Effect
**Gap:** Shadow/darkness spells cast while touching winter monolith should become permanent.

**Impact:**
- Powerful gameplay mechanic not enforced
- Dispel rules (only dispelled by touching monolith again in winter) not tracked

**Priority:** Low (complex spell modification system)

---

## Implementation Priority

### Completed (v2.0)
1. **RESTLESS_SLEEP Condition** - No HP recovery, no spell memorization
2. **TERROR Condition** - Flee behavior and climbing penalty
3. **COMPELLED Condition** - Movement forcing mechanic
4. **Seasonal POI State Check** - Determine active effects by season
5. **Winter Night Trigger** - Season-aware hazard triggers
6. **Ability Check Resolution** - DEX checks for climbing
7. **Arcane Caster Save Modifier** - Class-based save bonuses
8. **Sleep Near POI Trigger** - POI-proximity trigger detection

### Low Priority (Polish/Optional)
1. **Lost Behavior POI Attraction** - Special lost mechanic
2. **Spell Permanence** - Complex spell modification system

---

## Test Coverage

**New tests added in v2.0:**
- `tests/test_hex_0106_hazards.py` - 24 tests for:
  - Condition types (6 tests)
  - Condition roll modifiers (6 tests)
  - Seasonal POI state (3 tests)
  - Winter night triggers (2 tests)
  - Sleep near monolith (1 test)
  - Ability checks (1 test)
  - Arcane caster modifiers (2 tests)
  - `_is_winter()` helper (3 tests)

Existing tests in `tests/content_loader/test_hex_0106_loading.py`:
- 23 tests covering hex data loading, POIs, items, hazards, seasonal behavior

**Total Test Count:** 3683 tests passing

---

## Comparison to Other Hexes

| Feature | Hex 0107 | Hex 0105 | Hex 0106 |
|---------|----------|----------|----------|
| Enchantment conditions | Implemented | N/A | N/A |
| Time-of-day triggers | Implemented | Implemented | **Implemented** |
| Condition chains | Implemented | N/A | N/A |
| Night hazards | Partial | Implemented | **Implemented** |
| Monster special abilities | N/A | Implemented | N/A |
| Quest hooks | N/A | Implemented | N/A |
| Turn timers | N/A | Implemented | N/A |
| Seasonal POI behavior | N/A | N/A | **Implemented** |
| Ability checks | N/A | N/A | **Implemented** |
| Class-based modifiers | N/A | N/A | **Implemented** |

---

## Files Modified

**Data:**
- `/home/user/dolmenwood_virtual_dm/data/content/hexes/0106_the_outlook_and_the_red_monolith.json`

**Implementation:**
- `src/data_models.py` - Added RESTLESS_SLEEP, TERROR, COMPELLED conditions
- `src/hex_crawl/hex_crawl_engine.py` - Seasonal POI state, winter trigger detection, ability checks, class modifiers

**Tests:**
- `tests/content_loader/test_hex_0106_loading.py` - 23 tests (existing)
- `tests/test_hex_0106_hazards.py` - 24 tests (new)
