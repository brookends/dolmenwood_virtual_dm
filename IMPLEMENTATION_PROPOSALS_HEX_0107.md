# Implementation Proposals: Hex 0107 Full Automation

## Overview

This document proposes concrete fixes for the 7 remaining playability gaps in hex 0107 (The Weeping Woman). Each proposal includes:
- Where to implement
- What to change
- Estimated complexity
- Code sketches

---

## 1. Trigger Detection - "I drink the water"

### Problem
The system can't detect when a player describes drinking the Woman's tears.

### Solution
Add POI-aware action patterns and a new `CONSUME` action type.

### Implementation

**File: `src/narrative/intent_parser.py`**

```python
# Add to ActionType enum (around line 50)
class ActionType(str, Enum):
    # ... existing types ...
    CONSUME = "consume"  # Eating/drinking something

# Add to action patterns in narrative_resolver.py
POI_INTERACTION_PATTERNS = [
    (("drink", "sip", "taste", "imbibe"), "poi:consume_water", extract_target, 0.95),
    (("touch", "press", "push"), "poi:touch", extract_target, 0.9),
    (("climb", "scale"), "poi:climb", extract_height, 0.9),
]
```

**File: `src/narrative/narrative_resolver.py`**

```python
def _resolve_poi_action(
    self, parsed: ParsedIntent, character: CharacterState, context: dict
) -> ResolutionResult:
    """Handle POI-specific actions like drinking water at The Weeping Woman."""
    poi_name = context.get("current_poi")
    action_id = parsed.action_id

    if not poi_name:
        return self._resolve_narrative_action(parsed, character, context)

    # Get POI hazards that match the action trigger
    poi_hazards = self._get_poi_hazards_for_trigger(
        hex_id=context.get("hex_id"),
        poi_name=poi_name,
        trigger=action_id  # e.g., "drinking the water"
    )

    if poi_hazards:
        # Resolve hazards in sequence
        results = []
        for hazard in poi_hazards:
            result = self.hazard_resolver.resolve_hazard(
                hazard_type=HazardType.ENCHANTMENT,
                character=character,
                **hazard
            )
            results.append(result)
            if not result.success:
                break  # Stop on failed save

        return self._combine_hazard_results(results)

    return self._resolve_narrative_action(parsed, character, context)
```

**Complexity:** Medium (2-3 hours)

---

## 2. Condition Application - Auto-add to Character State

### Problem
`HazardResult.apply_conditions` is populated but not processed in hex_crawl_engine.

### Solution
Process `apply_conditions` after hazard resolution using existing `GlobalController.apply_condition()`.

### Implementation

**File: `src/hex_crawl/hex_crawl_engine.py`**

```python
def _resolve_hazard(
    self,
    hazard: dict[str, Any],
    character: CharacterState,
) -> HazardResult:
    """Resolve a single hazard check."""
    # ... existing resolution code ...

    result = self.narrative_resolver.hazard_resolver.resolve_hazard(...)

    # NEW: Apply conditions to game state
    self._apply_hazard_effects(result, character)

    return result

def _apply_hazard_effects(self, result: HazardResult, character: CharacterState) -> None:
    """Apply damage and conditions from hazard result to game state."""
    # Apply damage
    for target_id, damage in result.apply_damage:
        self.controller.apply_damage(target_id, damage, result.damage_type or "hazard")

    # Apply conditions with full Condition objects
    for target_id, condition_str in result.apply_conditions:
        # Create rich Condition with enchantment metadata
        condition = self._create_condition_from_hazard(
            condition_str=condition_str,
            hazard_data=result,  # Pass full hazard data for metadata
            source=result.description,
        )
        self.controller.apply_condition(target_id, condition, source=result.description)

def _create_condition_from_hazard(
    self,
    condition_str: str,
    hazard_data: HazardResult,
    source: str,
) -> Condition:
    """Create a rich Condition object from hazard result."""
    from src.data_models import Condition, ConditionType

    # Map string to ConditionType
    condition_type = ConditionType(condition_str)

    # Extract metadata from hazard narrative hints
    ends_at = None
    for hint in hazard_data.narrative_hints:
        if "until dawn" in hint.lower():
            ends_at = "dawn"
            break

    return Condition(
        condition_type=condition_type,
        source=source,
        ends_at_time_of_day=ends_at,
    )
```

**File: `src/game_state/global_controller.py`**

```python
def apply_condition(
    self,
    character_id: str,
    condition: Union[str, Condition],  # Accept both string and Condition
    source: str = ""
) -> dict:
    """Apply a condition to a character."""
    character = self.get_character(character_id)
    if not character:
        return {"success": False, "error": "Character not found"}

    # Convert string to Condition if needed
    if isinstance(condition, str):
        condition = Condition(
            condition_type=ConditionType(condition),
            source=source,
        )

    # Check for duplicates
    for existing in character.conditions:
        if existing.condition_type == condition.condition_type:
            return {"success": False, "error": "Already has condition"}

    character.conditions.append(condition)
    self._log_event("condition_applied", {
        "character_id": character_id,
        "condition": condition.condition_type.value,
        "source": condition.source,
    })

    return {"success": True, "condition": condition}
```

**Complexity:** Low (1-2 hours)

---

## 3. Action Restrictions - Dancing Blocks Other Actions

### Problem
`COMPELLED_DANCING` condition should prevent combat, spellcasting, movement.

### Solution
Add condition-based action validation in the action resolution pipeline.

### Implementation

**File: `src/data_models.py`**

```python
# Add to ConditionType or as separate dict
CONDITION_BLOCKED_ACTIONS = {
    ConditionType.COMPELLED_DANCING: {
        "blocked": [ActionCategory.COMBAT, ActionCategory.SPELL, ActionCategory.MOVEMENT],
        "allowed": [ActionCategory.NARRATIVE],  # Can still perceive/speak
        "message": "You cannot stop dancing!",
    },
    ConditionType.MAGICAL_SLEEP: {
        "blocked": [ActionCategory.COMBAT, ActionCategory.SPELL, ActionCategory.MOVEMENT,
                    ActionCategory.EXPLORATION, ActionCategory.SURVIVAL],
        "allowed": [],
        "message": "You are in an enchanted slumber.",
    },
    ConditionType.PARALYZED: {
        "blocked": [ActionCategory.COMBAT, ActionCategory.MOVEMENT],
        "allowed": [ActionCategory.NARRATIVE],
        "message": "You cannot move!",
    },
}
```

**File: `src/narrative/narrative_resolver.py`**

```python
def resolve_player_input(
    self, player_input: str, character: CharacterState, context: dict
) -> ResolutionResult:
    """Main entry point for action resolution."""
    # Parse intent
    parsed = self._parse_intent(player_input, context)

    # NEW: Check condition restrictions BEFORE routing
    restriction = self._check_condition_restrictions(character, parsed)
    if restriction:
        return ResolutionResult(
            success=False,
            resolution_type=ResolutionType.AUTO_FAIL,
            description=restriction["message"],
            narrative_hints=["struggles against the enchantment"],
        )

    # Continue with normal routing
    return self._route_action(parsed, character, context)

def _check_condition_restrictions(
    self, character: CharacterState, parsed: ParsedIntent
) -> Optional[dict]:
    """Check if any condition blocks the attempted action."""
    from src.data_models import CONDITION_BLOCKED_ACTIONS

    for condition in character.conditions:
        restriction = CONDITION_BLOCKED_ACTIONS.get(condition.condition_type)
        if restriction and parsed.action_category in restriction["blocked"]:
            return restriction

    return None
```

**Complexity:** Low (1 hour)

---

## 4. Roll Table Integration - Auto-Roll Fairy Dance Visions

### Problem
The POI's "Fairy Dance Visions" d6 table isn't rolled when dancing starts.

### Solution
Trigger roll table when applying `COMPELLED_DANCING` condition.

### Implementation

**File: `src/hex_crawl/hex_crawl_engine.py`**

```python
def _apply_hazard_effects(self, result: HazardResult, character: CharacterState) -> None:
    """Apply damage and conditions from hazard result to game state."""
    # ... existing code ...

    for target_id, condition_str in result.apply_conditions:
        condition = self._create_condition_from_hazard(...)
        self.controller.apply_condition(target_id, condition, source=result.description)

        # NEW: Trigger associated roll tables
        if condition_str == "compelled_dancing":
            self._roll_associated_tables(character, "Fairy Dance Visions")

def _roll_associated_tables(self, character: CharacterState, table_name: str) -> dict:
    """Roll on a POI's roll table and store result."""
    if not self._current_poi:
        return {}

    hex_data = self._hex_data.get(self._current_hex)
    if not hex_data:
        return {}

    for poi in hex_data.points_of_interest:
        if poi.name == self._current_poi:
            for table in poi.roll_tables:
                if table.name == table_name:
                    # Roll on the table
                    roll = self.dice.roll(table.die_type, table_name)
                    entry = table.get_entry(roll.total)

                    # Store vision for narration
                    self._store_character_event(character.character_id, {
                        "type": "vision",
                        "table": table_name,
                        "roll": roll.total,
                        "result": entry.title,
                        "description": entry.description,
                    })

                    return {
                        "table": table_name,
                        "roll": roll.total,
                        "entry": entry,
                    }

    return {}
```

**Complexity:** Low (1 hour)

---

## 5. Time Advancement - "Wait Until Dawn" Command

### Problem
No way to skip time to a specific TimeOfDay.

### Solution
Add `advance_to_time_of_day()` method and action.

### Implementation

**File: `src/game_state/global_controller.py`**

```python
def advance_to_time_of_day(
    self,
    target_time: TimeOfDay,
    reason: str = "waiting"
) -> dict:
    """
    Advance time until reaching the target time of day.

    Args:
        target_time: TimeOfDay to advance to (e.g., DAWN)
        reason: Reason for time advancement

    Returns:
        Dict with hours_passed, conditions_expired, etc.
    """
    current_time = self.world_state.current_time
    hours_passed = 0
    max_hours = 24  # Safety limit

    while current_time.get_time_of_day() != target_time and hours_passed < max_hours:
        result = self.advance_time(turns=6, reason=reason)  # 1 hour = 6 turns
        hours_passed += 1
        current_time = self.world_state.current_time

        # Check for condition expirations
        self._check_time_of_day_expirations(target_time)

    return {
        "success": True,
        "hours_passed": hours_passed,
        "new_time": current_time,
        "time_of_day": target_time.value,
    }

def _check_time_of_day_expirations(self, current_time: TimeOfDay) -> list[dict]:
    """Check and expire conditions that end at current time of day."""
    expired = []

    for character in self._get_all_characters():
        for condition in character.conditions[:]:  # Copy list for safe removal
            if condition.should_end_at_time(current_time):
                # Process transition before removal
                transition = condition.get_end_transition()

                # Apply healing if specified
                if transition["healing"]:
                    self._apply_condition_end_healing(character, transition["healing"])

                # Apply next condition if chained
                if transition["next_condition"]:
                    next_cond = self._create_chained_condition(transition["next_condition"])
                    character.conditions.append(next_cond)

                # Remove expired condition
                character.conditions.remove(condition)
                expired.append({
                    "character_id": character.character_id,
                    "condition": condition.condition_type.value,
                    "healing_applied": transition["healing"],
                    "chained_to": transition["next_condition"],
                })

    return expired
```

**File: `src/conversation/action_registry.py`**

```python
# Add new action
WILDERNESS_ACTIONS.append({
    "action_id": "wilderness:wait_until",
    "label": "Wait until...",
    "state": "wilderness",
    "params": ["time_of_day"],  # dawn, dusk, midnight, etc.
    "function": lambda ctx, time: ctx.hex_crawl.wait_until_time(time),
})
```

**Complexity:** Medium (2-3 hours)

---

## 6. Condition Transitions - Auto-Chain Conditions

### Problem
`leads_to_condition` is data only; transitions don't auto-trigger.

### Solution
Already included in #5 above - `_check_time_of_day_expirations()` handles chaining.

### Additional Implementation

**File: `src/game_state/global_controller.py`**

```python
def _create_chained_condition(self, chain_data: dict) -> Condition:
    """Create the next condition in a chain."""
    condition_type_str = chain_data.get("condition_type")
    source = chain_data.get("source", "condition_chain")

    # Look up condition metadata from a registry
    metadata = CONDITION_CHAIN_METADATA.get(condition_type_str, {})

    return Condition(
        condition_type=ConditionType(condition_type_str),
        source=source,
        duration_days=metadata.get("duration_days"),
        ends_at_time_of_day=metadata.get("ends_at"),
        healing_on_end=metadata.get("healing"),
        leads_to_condition=metadata.get("next"),
    )

# Condition chain registry
CONDITION_CHAIN_METADATA = {
    "magical_sleep": {
        "duration_days": None,  # Ends at time of day instead
        "ends_at": None,  # Sleep ends when disturbed or after 8 hours
        "healing": {"dice": "1d6", "condition": "undisturbed"},
        "next": {"condition_type": "fairy_marked", "source": "neveryon_dreams"},
    },
    "fairy_marked": {
        "duration_days": 180,  # 6 months
        "ends_at": None,
        "healing": None,
        "next": None,  # End of chain
    },
}
```

**Complexity:** Low (included in #5)

---

## 7. Full Moon Variation - Moon Phase Triggers

### Problem
Full moon should trigger automatic saves for all characters in hex.

### Solution
Add moon-phase-aware hazard checking in the hex crawl night phase.

### Implementation

**File: `src/hex_crawl/hex_crawl_engine.py`**

```python
def _process_night_phase(self, hex_id: str) -> list[dict]:
    """Process night-specific effects including moon phase hazards."""
    results = []
    hex_data = self._hex_data.get(hex_id)
    if not hex_data or not hex_data.procedural:
        return results

    # Check moon phase
    is_full_moon = self.controller.current_date.is_full_moon()

    # Get night hazards from hex procedural data
    night_hazards = hex_data.procedural.night_hazards or []

    for hazard in night_hazards:
        trigger = hazard.get("trigger", "")

        # Check if this hazard applies
        should_trigger = False
        if "full_moon" in trigger and is_full_moon:
            should_trigger = True
        elif "night" in trigger and not is_full_moon:
            should_trigger = True

        if should_trigger:
            # Apply to all party members
            for character in self._get_party_in_hex(hex_id):
                result = self._resolve_hazard(hazard, character)
                results.append({
                    "character_id": character.character_id,
                    "hazard": hazard.get("name", trigger),
                    "result": result,
                })

    return results

def advance_to_night(self, hex_id: str) -> dict:
    """Advance time to night and process night hazards."""
    # Advance to evening/night
    self.controller.advance_to_time_of_day(TimeOfDay.EVENING, "traveling")

    # Process night phase hazards
    night_results = self._process_night_phase(hex_id)

    return {
        "time": TimeOfDay.EVENING.value,
        "night_hazards": night_results,
        "is_full_moon": self.controller.current_date.is_full_moon(),
    }
```

**File: `src/hex_crawl/hex_crawl_engine.py`** (time advancement hook)

```python
def _on_time_advanced(self, turns: int, new_time: GameTime) -> None:
    """Hook called when time advances - check for time-based triggers."""
    time_of_day = new_time.get_time_of_day()

    # Entering night triggers night hazard check
    if time_of_day == TimeOfDay.DUSK:
        current_hex = self._current_hex
        if current_hex:
            self._process_night_phase(current_hex)
```

**Complexity:** Medium (2-3 hours)

---

## Implementation Priority

| Priority | Fix | Complexity | Dependencies |
|----------|-----|------------|--------------|
| 1 | Condition Application (#2) | Low | None |
| 2 | Action Restrictions (#3) | Low | #2 |
| 3 | Time Advancement (#5) | Medium | None |
| 4 | Condition Transitions (#6) | Low | #5 |
| 5 | Roll Table Integration (#4) | Low | #2 |
| 6 | Full Moon Variation (#7) | Medium | #5 |
| 7 | Trigger Detection (#1) | Medium | #2 |

**Recommended Order:** 2 → 3 → 5 → 6 → 4 → 7 → 1

**Total Estimated Time:** 10-14 hours

---

## Testing Strategy

Each fix should include:
1. Unit tests for the new methods
2. Integration test with hex 0107 data
3. End-to-end test of the full dance sequence

**Example Test:**

```python
def test_full_dance_sequence():
    """Test complete hex 0107 dance-until-dawn flow."""
    # Setup
    engine = HexCrawlEngine(...)
    character = create_test_character()
    engine.enter_hex("0107")
    engine.enter_poi("The Weeping Woman")

    # 1. Drink the water
    result = engine.handle_player_action("I drink the water", character.id, {})

    # 2. Check condition applied
    assert character.has_condition(ConditionType.ENCHANTED_HEARING)

    # 3. Advance to dawn
    engine.controller.advance_to_time_of_day(TimeOfDay.DAWN, "dancing")

    # 4. Check condition transitioned
    assert not character.has_condition(ConditionType.COMPELLED_DANCING)
    assert character.has_condition(ConditionType.MAGICAL_SLEEP)

    # 5. Check vision was rolled
    events = engine.get_character_events(character.id)
    assert any(e["type"] == "vision" for e in events)
```
