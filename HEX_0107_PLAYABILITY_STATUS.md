# Hex 0107 (The Weeping Woman) - Playability Status

## Summary

This document tracks what aspects of hex 0107's dance-until-dawn gameplay are automated vs. require manual DM intervention.

**Date:** 2026-01-03
**Implementation Version:** 1.0

---

## What's Now Implemented

### Condition Types (src/data_models.py)
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

### Hex Crawl Engine (src/hex_crawl/hex_crawl_engine.py)
- Routes `save_type="spell"` hazards to enchantment resolver
- Extracts save modifiers, condition info from hazard definitions

---

## What's Still Not Playable (Requires Manual DM)

### 1. Trigger Detection (Action Parsing)
**Gap:** No automated detection of "drink the water" action
- The system cannot recognize when a player describes drinking the Woman's tears
- **Workaround:** DM manually calls hazard resolution when player drinks

### 2. Condition Application to Game State
**Gap:** Hazard resolution returns conditions but doesn't apply them
- `HazardResult.apply_conditions` is populated but not processed
- **Workaround:** DM must manually add conditions to character state

### 3. Action Restrictions
**Gap:** Conditions don't restrict character actions
- `COMPELLED_DANCING` should prevent combat, spellcasting, etc.
- **Workaround:** DM must enforce "you can only dance" narratively

### 4. Roll Table Integration
**Gap:** Fairy Dance Visions table not automatically rolled
- The POI has a d6 table for what dancers perceive
- **Workaround:** DM rolls manually: `1d6` on the vision table

### 5. Time Advancement
**Gap:** No "skip to dawn" functionality
- Dancing lasts until dawn, but time must be manually advanced
- **Workaround:** DM advances time and checks condition expiry

### 6. Condition Transition Automation
**Gap:** Condition chains don't auto-trigger
- `leads_to_condition` is data only; no automation
- **Workaround:** DM manually applies next condition at dawn

### 7. Healing on Wake
**Gap:** `healing_on_end` not processed automatically
- Dawn slumber should heal 1d6 HP if undisturbed
- **Workaround:** DM rolls 1d6 and adds to HP manually

### 8. Protection Effects
**Gap:** `protection_effects` not enforced
- Magical sleep should protect from cold/elements
- **Workaround:** DM ignores weather/cold hazards during sleep

### 9. Long-Term Dream Tracking
**Gap:** 6-month dream duration not tracked
- `FAIRY_MARKED` condition should trigger dream events periodically
- **Workaround:** DM maintains separate tracking for Neveryon dreams

### 10. Full Moon Variation
**Gap:** No moon phase integration
- Full moon should trigger automatic saves for all in hex
- **Workaround:** DM checks moon phase and triggers saves manually

---

## Implementation Priority

To make hex 0107 fully playable without DM intervention:

### High Priority (Core Loop)
1. **Condition Application** - Process `apply_conditions` in game state
2. **Time Skip** - Add "wait until dawn" command
3. **Condition Expiry** - Check `ends_at_time_of_day` on time changes

### Medium Priority (Enhanced Experience)
4. **Roll Table Integration** - Auto-roll vision table on dancing
5. **Condition Transitions** - Auto-chain conditions per `leads_to_condition`
6. **Healing Processing** - Roll `healing_on_end` dice automatically

### Low Priority (Polish)
7. **Action Restrictions** - Block invalid actions during conditions
8. **Protection Effects** - Exempt sleeping characters from hazards
9. **Moon Phase Tracking** - Integrate with calendar system
10. **Long-Term Dreams** - Periodic dream event generation

---

## Test Coverage

New tests in `tests/test_enchantment_hazards.py`:
- 16 tests covering:
  - Enchantment hazard resolution (5 tests)
  - Condition time-of-day expiry (3 tests)
  - New condition types (6 tests)
  - HazardType.ENCHANTMENT registration (2 tests)

All tests pass as of 2026-01-03.
