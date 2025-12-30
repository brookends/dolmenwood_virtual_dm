# Dolmenwood Virtual DM - Narration Gap Assessment

## Overview

This document tracks LLM narration coverage across all game engines and states. Use this to identify and implement missing narration hooks.

**Architecture Pattern**: All narration follows the advisory-only pattern:
1. Python resolves mechanics (dice, damage, success/failure)
2. `NarrationContext` packages results
3. DMAgent generates descriptive text via prompt schemas
4. VirtualDM wrapper methods provide the public API

---

## Current Narration Coverage

### Implemented Methods (VirtualDM)

| Method | Schema | Purpose |
|--------|--------|---------|
| `_narrate_hex_arrival()` | `ExplorationDescriptionSchema` | Hex arrival description |
| `narrate_encounter_start()` | `EncounterFramingSchema` | Encounter framing |
| `narrate_combat_round()` | `CombatNarrationSchema` | Combat round description |
| `narrate_failure()` | `FailureConsequenceSchema` | Failed action consequences |
| `narrate_combat_end()` | `CombatConclusionSchema` | Combat aftermath |
| `narrate_dungeon_event()` | `DungeonEventSchema` | Traps, discoveries, hazards |
| `narrate_rest()` | `RestExperienceSchema` | Rest/camping scenes |
| `narrate_poi_approach()` | `POIApproachSchema` | POI approach description |
| `narrate_poi_entry()` | `POIEntrySchema` | POI entry description |
| `narrate_poi_feature()` | `POIFeatureSchema` | POI feature exploration |
| `narrate_resolved_action()` | `ResolvedActionSchema` | Generic resolved action |

---

## Narration Gaps by Engine

### 1. HexCrawlEngine (`src/hex_crawl/hex_crawl_engine.py`)

| Method | Has Narration | Gap Description | Priority |
|--------|---------------|-----------------|----------|
| `travel_to_hex()` | ✅ Yes | Wired via VirtualDM | - |
| `search_hex()` | ❌ No | Feature discovery narration | Medium |
| `approach_poi()` | ❌ No | POI approach (schema exists) | High |
| `enter_poi()` | ❌ No | POI entry (schema exists) | High |
| `explore_poi_feature()` | ❌ No | Feature interaction (schema exists) | High |
| `discover_poi()` | ❌ No | Hidden POI discovery | Medium |
| `describe_sensory_hints()` | ❌ No | Atmospheric clues (returns Python text) | Low |

**Implementation Notes**:
- POI schemas exist but aren't wired to engine methods
- Need to call `VirtualDM.narrate_poi_*()` after mechanical resolution
- `search_hex()` could use `narrate_resolved_action()` via callback

---

### 2. DungeonEngine (`src/dungeon/dungeon_engine.py`)

| Method | Has Narration | Gap Description | Priority |
|--------|---------------|-----------------|----------|
| `enter_dungeon()` | ❌ No | Dungeon entry atmosphere | High |
| `move_to_room()` | ❌ No | Room transition description | High |
| `execute_turn()` | Partial | Trap events have schema, room entry missing | Medium |
| `search_room()` | ❌ No | Search action narration | Medium |
| `listen_at_door()` | ❌ No | Listen action narration | Low |
| `force_door()` | ❌ No | Door forcing narration | Low |

**Implementation Notes**:
- `narrate_dungeon_event()` exists for traps/discoveries
- Missing: room entry/transition narration
- Consider adding `describe_dungeon_room()` wrapper in VirtualDM

---

### 3. CombatEngine (`src/combat/combat_engine.py`)

| Method | Has Narration | Gap Description | Priority |
|--------|---------------|-----------------|----------|
| `start_combat()` | ❌ No | Combat initiation scene | Medium |
| `execute_round()` | ✅ Yes | Via `narrate_combat_round()` | - |
| `end_combat()` | ✅ Yes | Via `narrate_combat_end()` | - |
| `resolve_attack()` | ❌ No | Individual attack narration | Low |
| `check_morale()` | ❌ No | Morale break narration | Medium |
| `process_fleeing()` | ❌ No | Pursuit/escape narration | Medium |

**Implementation Notes**:
- Round-level narration exists
- Individual action narration could use `narrate_resolved_action()`
- Consider morale-specific schema for dramatic breaks

---

### 4. SettlementEngine (`src/settlement/settlement_engine.py`)

| Method | Has Narration | Gap Description | Priority |
|--------|---------------|-----------------|----------|
| `enter_settlement()` | ❌ No | Settlement arrival | **Critical** |
| `visit_building()` | ❌ No | Building entry | **Critical** |
| `initiate_conversation()` | ❌ No | NPC meeting (schema exists) | High |
| `browse_goods()` | ❌ No | Shop interior | Medium |
| `seek_lodging()` | ❌ No | Inn atmosphere | Medium |
| `visit_temple()` | ❌ No | Temple atmosphere | Medium |

**Implementation Notes**:
- No settlement narration exists currently
- Need new schemas: `SettlementArrivalSchema`, `BuildingInteriorSchema`
- `NPCDialogueSchema` exists but not wired to engine

---

### 5. EncounterEngine (`src/encounter/encounter_engine.py`)

| Method | Has Narration | Gap Description | Priority |
|--------|---------------|-----------------|----------|
| `start_encounter()` | ✅ Yes | Via `narrate_encounter_start()` | - |
| `resolve_reaction()` | ❌ No | Reaction roll outcome | Medium |
| `attempt_parley()` | ❌ No | Social interaction attempt | Medium |
| `attempt_evasion()` | ❌ No | Evasion attempt narration | Low |

**Implementation Notes**:
- Encounter framing exists
- Reaction/parley could use `NPCDialogueSchema`

---

### 6. DowntimeEngine (`src/downtime/downtime_engine.py`)

| Method | Has Narration | Gap Description | Priority |
|--------|---------------|-----------------|----------|
| `rest()` | ✅ Yes | Via `narrate_rest()` | - |
| `train_skill()` | ❌ No | Training montage | Low |
| `craft_item()` | ❌ No | Crafting narration | Low |
| `research()` | ❌ No | Research narration | Low |

**Implementation Notes**:
- Rest is covered
- Downtime activities could use `DowntimeSummarySchema`

---

### 7. NarrativeResolver (`src/narrative/narrative_resolver.py`)

| Resolver | Has Narration | Gap Description | Priority |
|----------|---------------|-----------------|----------|
| `resolve_player_input()` | ✅ Yes | Callback wired | - |
| `SpellResolver` | ✅ Partial | Via callback | - |
| `HazardResolver` | ✅ Partial | Via callback | - |
| `CreativeSolutionResolver` | ✅ Partial | Via callback | - |

**Implementation Notes**:
- Callback mechanism implemented
- All resolved actions get narration automatically

---

## Priority Implementation Order

### Phase 1: Critical Gaps (Settlement)
```
1. Add SettlementArrivalSchema to prompt_schemas.py
2. Add BuildingInteriorSchema to prompt_schemas.py
3. Add DMAgent.describe_settlement_arrival()
4. Add DMAgent.describe_building_interior()
5. Add VirtualDM.narrate_settlement_arrival()
6. Add VirtualDM.narrate_building_interior()
7. Wire to SettlementEngine methods
```

### Phase 2: High Priority (POI Wiring + Dungeon Rooms)
```
1. Wire narrate_poi_approach() to HexCrawlEngine.approach_poi()
2. Wire narrate_poi_entry() to HexCrawlEngine.enter_poi()
3. Wire narrate_poi_feature() to HexCrawlEngine.explore_poi_feature()
4. Add DungeonRoomEntrySchema to prompt_schemas.py
5. Add DMAgent.describe_dungeon_room_entry()
6. Add VirtualDM.narrate_room_entry()
7. Wire to DungeonEngine.move_to_room()
```

### Phase 3: Medium Priority (Combat/Encounter Polish)
```
1. Add CombatInitiationSchema for combat start
2. Add MoraleBreakSchema for dramatic morale failures
3. Wire reaction roll outcomes to NPCDialogueSchema
4. Add search action narration hooks
```

### Phase 4: Low Priority (Polish)
```
1. Individual attack narration
2. Door forcing/listening narration
3. Downtime activity narration
4. Pursuit/evasion narration
```

---

## Implementation Template

For each gap, follow this pattern:

### 1. Add Schema (prompt_schemas.py)
```python
@dataclass
class NewFeatureInputs:
    """Inputs for new feature narration."""
    required_field: str
    optional_field: str = ""
    list_field: list[str] = field(default_factory=list)

@dataclass
class NewFeatureSchema(PromptSchema):
    def __init__(self, inputs: NewFeatureInputs):
        super().__init__(
            schema_type=PromptSchemaType.NEW_FEATURE,
            inputs=vars(inputs)
        )
        self.typed_inputs = inputs

    def build_prompt(self) -> str:
        # Build prompt from inputs
        pass
```

### 2. Add DMAgent Method (dm_agent.py)
```python
def describe_new_feature(
    self,
    required_field: str,
    optional_field: str = "",
) -> DescriptionResult:
    inputs = NewFeatureInputs(
        required_field=required_field,
        optional_field=optional_field,
    )
    schema = NewFeatureSchema(inputs)
    return self._execute_schema(schema)
```

### 3. Add VirtualDM Wrapper (main.py)
```python
def narrate_new_feature(
    self,
    *,
    required_field: str,
    optional_field: str = "",
) -> Optional[str]:
    if not self._dm_agent or not self.config.enable_narration:
        return None
    try:
        result = self._dm_agent.describe_new_feature(
            required_field=required_field,
            optional_field=optional_field,
        )
        return result.content if result.success else None
    except Exception as e:
        logger.warning(f"Error generating narration: {e}")
        return None
```

### 4. Wire to Engine
```python
# In the engine method, after mechanical resolution:
result = self._resolve_mechanics()
if hasattr(self.controller, 'virtual_dm'):
    narration = self.controller.virtual_dm.narrate_new_feature(...)
    result['narration'] = narration
return result
```

---

## Files to Modify

| File | Purpose |
|------|---------|
| `src/ai/prompt_schemas.py` | Add new schema classes |
| `src/ai/dm_agent.py` | Add DMAgent methods |
| `src/main.py` | Add VirtualDM wrapper methods |
| `src/hex_crawl/hex_crawl_engine.py` | Wire POI narration |
| `src/dungeon/dungeon_engine.py` | Wire room narration |
| `src/settlement/settlement_engine.py` | Wire settlement narration |
| `src/combat/combat_engine.py` | Wire combat start/morale |
| `tests/test_integration.py` | Add narration tests |

---

## Testing Pattern

```python
def test_new_feature_narration_method(self, virtual_dm_with_narration):
    """Test narrate_new_feature method."""
    narration = virtual_dm_with_narration.narrate_new_feature(
        required_field="test value",
        optional_field="optional value",
    )
    assert narration is not None
    assert isinstance(narration, str)

def test_new_feature_narration_disabled(self, virtual_dm_no_narration):
    """Test narrate_new_feature returns None when disabled."""
    result = virtual_dm_no_narration.narrate_new_feature(
        required_field="test",
    )
    assert result is None
```
