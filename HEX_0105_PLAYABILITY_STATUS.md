# Hex 0105 (The Demesne of the Frore Gryphus) - Playability Status

## Summary

This document tracks what aspects of hex 0105's gameplay are automated vs. require manual DM intervention.

**Date:** 2026-01-03
**Implementation Version:** 1.0 (Gaps Identified)

---

## What's Fully Implemented

### Hex Data Loading
- All hex properties, terrain, coordinates loaded correctly
- Procedural data (lost chance, encounter chance, foraging) parsed
- Night hazards defined in data

### Points of Interest (3 Total)
- **Frozen Battleground** - Full description, roll table (6 entries), hazard definition
- **Shepherd Encampment** - Full description, quest hook defined, NPCs linked
- **The Nest of the Frore Gryphus** - Hidden POI, treasure hoard, nest encounter table

### NPC Topic Intelligence
- **Aegnyth Cormick**: 6 known topics with keywords, disposition gates, priorities
- **Aegnyth's Secrets**: 2 secrets with trust/disposition requirements
- **Relationships**: Sister in hex 0108, subordinate shepherds
- **Frore Gryphus**: Stats, vulnerabilities, faction connection

### Roll Tables
- Battlefield Discoveries (d6, 6 unique entries)
- Nest Encounters (d6, 3 outcome types)

### Hazard Resolution
- `HazardType.COLD` exists for generic cold damage
- Frost touch hazard defined (Save vs Doom, 1d6 cold)

### Hidden POI Discovery
- System supports discovering hidden POIs through search

---

## What's NOT Playable (Gaps Identified)

### 1. Night Hazard Trigger Detection (CRITICAL)
**Gap:** `process_night_hazards()` only triggers on "full_moon" or "night" keywords

**Hex 0105's triggers:**
- `camp_near_frost_patches` - Save vs Doom or 1d4 cold damage
- `sleep` - Save vs Spell or exhausted (-1 to all rolls until rest elsewhere)

**Impact:** Neither trigger contains "full_moon" or "night", so they never fire
**Location:** `src/hex_crawl/hex_crawl_engine.py:1889-1893`

**Fix Required:** Extend `process_night_hazards()` to handle additional trigger types:
- `camp_near_*` - Check if party is camping near specific feature
- `sleep` - Trigger for all sleeping characters

---

### 2. Silence Effect Not Implemented
**Gap:** Frozen Battleground has "Silence-like effect—no sounds travel more than 30 feet"

**Impact:** No mechanical enforcement of sound distance limitation
- Spells with verbal components should be affected
- Communication over 30ft should be blocked
- Listen checks should be modified

**Fix Required:** Add POI-level area effect system:
```python
class POIAreaEffect:
    effect_type: str  # "silence_30ft", "darkness", "cold_aura"
    radius_feet: int
    mechanical_effects: dict
```

---

### 3. Cold Aura Combat Mechanic Missing
**Gap:** Frore Gryphus has "Cold Aura (creatures within 10 feet take 1 cold damage per round)"

**Impact:** Automatic proximity damage not applied in combat

**Stat Reference from hex data:**
```
Special: Cold Aura (creatures within 10 feet take 1 cold damage per round)
```

**Fix Required:** Combat engine needs per-round aura damage processing:
```python
def process_start_of_round_effects(self):
    for combatant in self.combatants:
        if combatant.has_aura("cold"):
            for target in self.get_combatants_within(combatant, 10):
                self.apply_damage(target, 1, "cold")
```

---

### 4. Nest Encounter Turn Timer
**Gap:** No mechanism for delayed monster arrivals

**From hex data:**
- "Gryphlings Only" (roll 3-4): "Her cries will summon the mother in 1 Turn"
- "Hunting" (roll 5-6): "Roll again each Turn; on 1-3 they return"

**Impact:** DM must manually track turns and roll for arrival

**Fix Required:** Turn-based event timer system:
```python
class PendingEvent:
    trigger_in_turns: int
    event_type: str  # "monster_arrival", "reinforcements"
    check_each_turn: bool
    check_probability: str  # "1-3 on d6"
    monster_id: str
```

---

### 5. Quest Hook Trigger Mechanism
**Gap:** Quest defined but no activation/tracking/completion system

**Quest: hunt_frore_gryphus**
- Giver: Aegnyth Cormick
- Objective: Slay or banish the frore gryphus
- Reward: 50gp + 1gp per sheep carcass + gratitude

**Missing:**
- Quest acceptance detection from NPC conversation
- Quest state tracking (accepted, in_progress, completed, failed)
- Completion detection (gryphus killed or fled hex)
- Reward distribution

**Fix Required:** Quest state machine:
```python
class QuestState(Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

### 6. Gryphling Training Mechanics
**Gap:** Mentioned in secrets but no implementation

**From secrets:**
> "If the gryphlings are captured young, they can potentially be trained—though this would require fairy magic or the aid of someone who knows the Cold Prince's ways"

**Missing:**
- Gryphling capture mechanics
- Training skill check system
- Required knowledge check (fairy beasts / Cold Prince)
- Training outcome effects

**Priority:** Low (aspirational feature)

---

### 7. Cold Prince Consequence Trigger
**Gap:** DM notes mention consequence but no event system

**From DM notes:**
> "Consider having the Cold Prince's agents appear in later sessions if the gryphus is slain, as a consequence."

**Missing:**
- Death event trigger for frore gryphus
- Delayed consequence scheduling
- Cold Prince agent encounter generation

**Fix Required:** World event consequence system:
```python
class WorldConsequence:
    trigger_event: str  # "monster_death:frore_gryphus"
    consequence_type: str  # "faction_agent_appearance"
    delay_days: int
    faction: str  # "cold_prince"
```

---

### 8. Cross-Hex NPC Linkage
**Gap:** Aegnyth references sister Marged in hex 0108, but no reciprocal data

**From relationships:**
```json
{
  "npc_id": "marged_cormick",
  "relationship_type": "family",
  "hex_id": "0108",
  "notes": "Marged owes money to House Mulbreck"
}
```

**Impact:** If players visit hex 0108, there's no Marged NPC defined

**Fix Required:** Add Marged Cormick NPC to hex 0108 with reciprocal relationship

---

## Implementation Priority

### High Priority (Core Gameplay)
1. **Night Hazard Triggers** - Extend trigger detection for camp/sleep hazards
2. **Quest State Tracking** - Basic quest acceptance and completion detection

### Medium Priority (Enhanced Experience)
3. **Nest Turn Timer** - Delayed monster arrival mechanic
4. **Cold Aura Combat** - Per-round proximity damage in combat

### Low Priority (Polish/Optional)
5. **Silence Effect** - POI area effect system
6. **Cross-Hex NPCs** - Add Marged to hex 0108
7. **Cold Prince Consequences** - World event system
8. **Gryphling Training** - Aspirational feature

---

## Test Coverage

Existing tests in `tests/content_loader/test_hex_0105_loading.py`:
- 32 assertions covering hex data loading
- NPC topic parsing
- POI structure validation
- Roll table entries
- Relationship networks

**Missing Tests:**
- Night hazard trigger activation
- Quest state transitions
- Combat aura damage
- Turn timer events

---

## Comparison to Hex 0107

| Feature | Hex 0107 | Hex 0105 |
|---------|----------|----------|
| Enchantment conditions | Implemented | N/A |
| Time-of-day triggers | Implemented | Missing (sleep trigger) |
| Condition chains | Implemented | N/A |
| Night hazards | Partial | Missing (camp trigger) |
| Monster special abilities | N/A | Missing (cold aura) |
| Quest hooks | N/A | Missing (no trigger) |
| Turn timers | N/A | Missing (nest arrival) |

---

## Files Involved

**Data:**
- `/home/user/dolmenwood_virtual_dm/data/content/hexes/0105_the_demesne_of_the_frore_gryphus.json`

**Implementation (needs updates):**
- `src/hex_crawl/hex_crawl_engine.py` - Night hazard triggers
- `src/combat/combat_engine.py` - Aura damage
- `src/game_state/global_controller.py` - Quest state, turn timers

**Tests:**
- `tests/content_loader/test_hex_0105_loading.py`
