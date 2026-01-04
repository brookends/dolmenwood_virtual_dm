# Hex 0107 (The Weeping Woman) - Playability Status

## Summary

This document tracks what aspects of hex 0107's dance-until-dawn gameplay are automated vs. require manual DM intervention.

**Date:** 2026-01-03
**Implementation Version:** 2.0 (Full Automation)

---

## Fully Implemented Features

### Core Condition Types (src/data_models.py)
- `ENCHANTED_HEARING` - Hearing magical music (triggers dancing)
- `COMPELLED_DANCING` - Must dance, cannot take other actions
- `MAGICAL_SLEEP` - Enchanted slumber, protected from elements
- `FAIRY_MARKED` - Long-term fairy attention (dreams, omens)

### Condition Features
- `ends_at_time_of_day` - Conditions can end at specific times (e.g., "dawn")
- `protection_effects` - Track elemental/damage protections during condition
- `healing_on_end` - Dice formula for healing when condition ends
- `leads_to_condition` - Chain to next condition when this one ends
- `should_end_at_time(TimeOfDay)` - Method to check if condition expires

### Hazard Resolution (src/narrative/hazard_resolver.py)
- `HazardType.ENCHANTMENT` - New hazard type for fairy magic
- `_resolve_enchantment()` - Handles spell saves with modifiers
- Automatic effect handling (no save required)
- Condition application on failed saves

---

## Implementation Status - All 7 Gaps Resolved

### 1. Trigger Detection - IMPLEMENTED
**Location:** `src/hex_crawl/hex_crawl_engine.py:370-430`
- `POI_ACTION_PATTERNS` - Dictionary of trigger phrases (consume, touch, enter, examine)
- `detect_poi_action()` - Parses player input for POI interactions
- `get_matching_poi_hazards()` - Matches actions to hex POI definitions
- `resolve_poi_action()` - Complete pipeline from input to hazard resolution

**Example:** "I drink the water" → detects "consume" → matches Woman's tears POI → triggers enchantment hazard

### 2. Condition Application - IMPLEMENTED
**Location:** `src/game_state/global_controller.py:180-220`
- `apply_condition()` - Updated to accept both string and Condition objects
- `_apply_hazard_effects()` in hex_crawl_engine - Applies damage and conditions from HazardResult
- `_create_condition_from_hazard()` - Creates rich Condition with all fields populated

**Flow:** HazardResult → _apply_hazard_effects → GlobalController.apply_condition → character state updated

### 3. Action Restrictions - IMPLEMENTED
**Location:** `src/data_models.py:90-130`, `src/narrative/narrative_resolver.py:50-90`
- `CONDITION_BLOCKED_ACTIONS` - Dictionary mapping conditions to blocked/allowed actions
- `_check_condition_restrictions()` - Checks character conditions before action routing
- Returns restriction message if action is blocked

**Restrictions:**
- `compelled_dancing`: Blocks combat, spell, movement, exploration, survival, hazard
- `magical_sleep`: Blocks all actions (combat, spell, movement, exploration, survival, hazard, social, inventory, creative)

### 4. Roll Table Integration - IMPLEMENTED
**Location:** `src/hex_crawl/hex_crawl_engine.py:300-340`
- `_roll_associated_tables()` - Rolls tables when conditions are applied
- Integrates with existing roll table system
- Triggered automatically during `_apply_hazard_effects()`

**Example:** When COMPELLED_DANCING applied → auto-rolls "Fairy Dance Visions" d6 table

### 5. Time Advancement - IMPLEMENTED
**Location:** `src/game_state/global_controller.py:230-290`
- `advance_to_time_of_day()` - Skips time to specified TimeOfDay (dawn, midnight, etc.)
- Advances hour by hour, calling `_check_time_of_day_expirations()` each step
- Returns summary of time passed and conditions expired

**Example:** `controller.advance_to_time_of_day(TimeOfDay.DAWN, "waiting out the dance")`

### 6. Condition Transitions - IMPLEMENTED
**Location:** `src/game_state/global_controller.py:290-370`
- `_check_time_of_day_expirations()` - Expires conditions when time matches `ends_at_time_of_day`
- `_apply_condition_end_healing()` - Rolls healing dice when condition ends (if undisturbed)
- `_create_chained_condition()` - Creates next condition in chain from `leads_to_condition`

**Example Chain:** COMPELLED_DANCING (ends at dawn) → MAGICAL_SLEEP (8 hours) → FAIRY_MARKED (6 months)

### 7. Full Moon Variation - IMPLEMENTED
**Location:** `src/hex_crawl/hex_crawl_engine.py:440-510`
- `_is_full_moon()` - Checks current moon phase from game state
- `process_night_hazards()` - Processes hex-specific night hazards with moon modifiers
- `check_hex_night_entry()` - Checks for automatic enchantments when entering hex at night

**Full Moon Effect:** -4 penalty to enchantment saves for all characters in hex

---

## Remaining Low-Priority Items

### Protection Effects Enforcement
**Status:** Data tracked, not enforced
- `protection_effects` field is populated on conditions
- Weather/damage hazards don't yet check for protection
- **Workaround:** DM can query character conditions before applying environmental damage

### Long-Term Dream Tracking (6 months)
**Status:** Data tracked, no periodic events
- `FAIRY_MARKED` condition tracks duration in months
- No automatic dream event generation system yet
- **Workaround:** DM can check for fairy_marked condition and generate dreams narratively

---

## Test Coverage

Tests in `tests/test_enchantment_hazards.py`:
- 34 tests covering:
  - Enchantment hazard resolution (5 tests)
  - Condition time-of-day expiry (3 tests)
  - New condition types (6 tests)
  - HazardType.ENCHANTMENT registration (2 tests)
  - Condition-blocked actions (6 tests)
  - Narrative resolver restrictions (3 tests)
  - Time advancement methods (3 tests)
  - POI trigger detection (4 tests)
  - Full moon variation (3 tests)

All 3590 tests pass as of 2026-01-03.

---

## How to Test the Full Loop

```python
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.game_state.global_controller import GlobalController
from src.data_models import TimeOfDay

# Setup
engine = HexCrawlEngine(global_controller)
controller = GlobalController()

# 1. Player enters hex 0107 at night
result = engine.check_hex_night_entry("0107", "player_1")

# 2. Player drinks the water
result = engine.resolve_poi_action("I drink the water", "player_1", "0107")
# → Triggers enchantment save, applies ENCHANTED_HEARING on fail

# 3. Character starts dancing (automatic if hearing music)
# → Applies COMPELLED_DANCING, rolls Fairy Dance Visions table

# 4. Try to attack while dancing
from src.narrative.narrative_resolver import NarrativeResolver
resolver = NarrativeResolver()
# → Returns blocked_by_condition with message about dancing

# 5. Wait until dawn
result = controller.advance_to_time_of_day(TimeOfDay.DAWN, "dancing through the night")
# → COMPELLED_DANCING expires, MAGICAL_SLEEP applied, healing rolled

# 6. Sleep ends after 8 hours
# → MAGICAL_SLEEP expires, FAIRY_MARKED applied

# Character wakes healed, marked by the fae for 6 months
```
