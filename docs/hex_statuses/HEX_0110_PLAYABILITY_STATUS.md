# Hex 0110 (The Shadow of Lord Gnarlgruff) - Playability Status

## Summary

This document tracks the implementation status of hex 0110's features, including NPC intelligence, faction connections, POI roll tables, entry conditions, night hazards, and moon phase mechanics.

**Date:** 2026-01-04
**Implementation Version:** 1.0 (Full Automation)

---

## Fully Implemented Features

### Core Data Model Extensions (src/data_models.py)

#### HexProcedural
- `encounter_chance: str` - "2-in-6" for this hex
- `encounter_modifiers: list[dict]` - Devil goat encounter override
- `night_hazards: list[dict]` - Sleep hazard (devil goats) and full moon hazard
- `foraging_results: str` - Holly berries, hawthorn berries, shadow mushrooms
- `foraging_special: list[str]` - Special foraging items
- `lost_behavior: dict` - Disorienting lost behavior

#### PointOfInterest
- `evening_hazard: Optional[dict]` - 4-in-6 devil goat reinforcements
- `roll_tables: list[RollTable]` - 2 tables (Bone Pile Discoveries, Monolith Events)
- `secrets: list[str]` - POI-level secrets about Gnarlgruff
- `entry_conditions: dict` - Kindred-restricted entry (longhorn breggles only)
- `hazards: list[dict]` - Devil goat attack and charnel stench hazards
- `discovery_hints: dict` - Smell, sound, visual hints

#### HexNPC
- `known_topics: list[KnownTopic]` - Lord Gnarlgruff has 8 topics
- `secret_info: list[SecretInfo]` - Lord Gnarlgruff has 3 secrets
- `relationships: list[dict]` - Cross-hex relationships to Malbleat (0709), Ramius (0410)
- `vulnerabilities: list[str]` - Both NPCs have vulnerabilities
- `is_combatant: bool` - Devil goats are combatants
- `group_count: str` - Devil goats use "2d4" for variable spawns
- `time_presence: dict` - Lord Gnarlgruff only appears on full moon

---

## Engine Methods (src/hex_crawl/hex_crawl_engine.py)

### engage_poi_npc(hex_id, poi_name, npc_id)
- **Status:** Implemented
- Creates combat encounter with correct group size
- Handles `group_count` expressions like "2d4"

**Example:**
```python
result = engine.engage_poi_npc("0110", "Devil Goats' Glade", "devil_goats")
# Returns: {encounter_started: True, combatants: [{name: "Devil Goat", ...}, ...]}
```

### check_evening_hazard(hex_id, poi_name)
- **Status:** Implemented
- 4-in-6 chance of devil goat reinforcements at Devil Goats' Glade

**Example:**
```python
result = engine.check_evening_hazard("0110", "Devil Goats' Glade")
# Returns: {triggered: True, result: "devil_goat_reinforcements", chance: "4-in-6"}
```

### roll_on_poi_table(hex_id, table_name, poi_name)
- **Status:** Implemented
- Rolls on POI tables like "Bone Pile Discoveries" or "Monolith Events"
- Supports `unique_entries` for Bone Pile Discoveries

**Example:**
```python
result = engine.roll_on_poi_table("0110", "Bone Pile Discoveries", "Devil Goats' Glade")
# Returns: {roll: 3, title: "Silver Necklace with Ioun", description: "...", mechanical_effect: {...}}
```

### sleep_at_poi(hex_id, poi_name, character_ids)
- **Status:** Implemented
- Checks night_hazards including "sleep" trigger (3-in-6 devil goat attack)
- Handles "npc_arrival" hazard type

---

## Hex 0110 Content

### POI: Devil Goats' Glade

| Feature | Status | Notes |
|---------|--------|-------|
| **entering** | Implemented | Kindred check for longhorn breggles |
| **interior** | Implemented | 2d4 devil goats, monolith, bone mound |
| **exploring** | Implemented | Bone pile searchable, monolith events |
| **leaving** | Implemented | Peaceful retreat described |
| **evening_hazard** | Implemented | 4-in-6 reinforcements |
| **roll_tables** | Implemented | 2 tables (Bone Pile, Monolith Events) |
| **entry_conditions** | Data Tracked | Kindred checking not automated |
| **hazards** | Partially Implemented | Combat trigger needs manual start |
| **discovery_hints** | Data Tracked | DM narrates smell/sound/visual |

### Roll Tables (2 total)

1. **Bone Pile Discoveries** (d6, unique) - Treasures and danger in bone pile
2. **Monolith Events** (d4) - Events when examining monolith

### NPCs

#### Devil Goats (Demon, Chaotic)
- **is_combatant:** true
- **stat_reference:** "Devil Goat (DMB)"
- **group_count:** "2d4"
- **vulnerabilities:** 3 (holy_symbols, blessed_weapons, holy_water)
- **known_topics:** 0 (minimal intelligence)
- **relationships:** 1 (lord_gnarlgruff_spirit as former master)

#### Lord Gnarlgruff (Spirit, Chaotic)
- **is_combatant:** false
- **stat_reference:** null (cannot be fought normally)
- **time_presence:** moon_phase = "full" (only appears on full moon)
- **vulnerabilities:** 3 (cold_iron, dispel_magic, exorcism)
- **known_topics:** 8 topics:
  - identity, malbleat_connection, ramius_connection, resurrection_desire
  - book_of_foul_wonders, devil_goats, monolith_purpose, laboratory_destruction
- **secret_info:** 3 secrets:
  - remains_location (trust 1): Bones beneath Shadholme
  - book_thief_identity (trust 2): Yrzanthruul stole the Book
  - resurrection_ritual (trust 2): Three requirements for resurrection
- **relationships:** 3:
  - lord_malbleat (0709) - descendant, potential resurrector
  - lord_ramius (0410) - descendant, rejected heritage
  - devil_goats (0110) - former master
- **binding:** Self-bound to monolith, cannot leave glade

### Procedural Section
- **encounter_chance:** 2-in-6
- **encounter_modifiers:** 2-in-6 chance replaces encounter with 1d3 devil goats
- **night_hazards:** 2 hazards (sleep trigger, full_moon trigger)
- **foraging_special:** Holly berries, hawthorn berries, shadow mushrooms (5gp each)
- **lost_behavior:** Disorienting, paths seem to shift

### Items (4)
1. Silver Dagger (30gp, not magical, in bone pile)
2. Silver Necklace with Grey Ioun (250gp, magical, in bone pile)
3. Gold Ring with Red Garnet (400gp, not magical, in bone pile)
4. Hip Flask with Philtre of Wondrous Vitality (magical, in bone pile)

---

## Test Coverage

### tests/hex_crawl/test_hex_0110.py (38 tests)
- Hex loading (5 tests)
- Devil Goats' Glade POI (10 tests)
- Devil Goats NPC (5 tests)
- Lord Gnarlgruff Spirit NPC (11 tests)
- Items (3 tests)
- Secrets (2 tests)
- Roll table resolution (2 tests)
- Integration tests (2 tests)

**Total: 38 tests passing**

---

## How to Test the Full Loop

```python
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.game_state.global_controller import GlobalController
from src.data_models import GameDate

# Setup
controller = GlobalController()
controller.world_state.current_date = GameDate(year=1, month=3, day=15)
engine = HexCrawlEngine(controller)

# 1. Party enters hex 0110
engine._current_hex = "0110"

# 2. Check for encounters (2-in-6, may be devil goats)
encounter = engine.check_encounter("0110")
if encounter.get("encounter_triggered"):
    print(f"Encounter: {encounter.get('description')}")

# 3. Approach Devil Goats' Glade - party is NOT longhorn breggles
# Entry conditions would trigger combat (not automated, DM handles)
poi = engine.get_hex_data("0110").points_of_interest[0]
print(f"Entry condition: {poi.entry_conditions}")

# 4. Roll on Bone Pile Discoveries
bone_result = engine.roll_on_poi_table("0110", "Bone Pile Discoveries", "Devil Goats' Glade")
print(f"Found: {bone_result['title']} - {bone_result['description']}")

# 5. Touch the monolith
monolith_result = engine.roll_on_poi_table("0110", "Monolith Events", "Devil Goats' Glade")
print(f"Monolith event: {monolith_result['title']}")

# 6. Stay overnight (evening hazard + night hazard)
rest_result = engine.sleep_at_poi("0110", "Devil Goats' Glade")
if rest_result.get("evening_hazard", {}).get("triggered"):
    print("Evening: More devil goats arrive!")
print(f"Rest result: {rest_result['message']}")

# 7. Engage NPC for combat
combat_result = engine.engage_poi_npc("0110", "Devil Goats' Glade", "devil_goats")
print(f"Combat started with {len(combat_result.get('combatants', []))} devil goats")
```

---

## Features NOT Yet Automated (Priority Levels)

### Moon Phase Tracking
**Status:** Data Tracked, Not Automated
- `time_presence.moon_phase = "full"` for Lord Gnarlgruff
- Spirit can only manifest on full moon nights
- **Workaround:** DM manually checks if current date is full moon
- **Priority:** Medium - Would enhance NPC availability

### Kindred-Restricted Entry
**Status:** Data Tracked, Not Automated
- `entry_conditions.type = "kindred_restricted"`
- Only longhorn breggles can enter without triggering combat
- **Workaround:** DM checks party composition manually
- **Priority:** Medium - Would automate entry restrictions

### POI Hazard Combat Triggers
**Status:** Partially Automated
- `hazards[0].effect = "combat"` for devil_goat_attack
- Combat encounter not auto-started on entry
- **Workaround:** DM initiates combat via `engage_poi_npc`
- **Priority:** Low - Minor convenience

### Charnel Stench Save
**Status:** Data Tracked, Not Automated
- `hazards[1].save_type = "death"` for charnel stench
- -1 to attacks/saves while in glade on failed save
- **Workaround:** DM calls for save manually
- **Priority:** Low - Standard hazard handling

### Binding Field Parsing
**Status:** Data Tracked, Not Used
- `binding.bound_to`, `binding.release_condition`, etc.
- Spirit cannot leave glade, bound to monolith
- **Workaround:** DM references binding data for narrative
- **Priority:** Low - Narrative flavor

### Full Moon Night Hazard
**Status:** Data Tracked, Not Automated
- `night_hazards[1].trigger = "full_moon"`
- Characters drawn to monolith in dreamlike trance (Save vs Spell)
- **Workaround:** DM triggers on full moon nights
- **Priority:** Medium - Ties to moon phase system

### Discovery Hints
**Status:** Data Tracked, DM Narrates
- `discovery_hints.smell`, `.sound`, `.visual`
- Charnel stench detectable from 1 mile away
- **Workaround:** DM uses hints for atmosphere
- **Priority:** Low - Narrative flavor

### mechanical_effect Application
**Status:** Data Tracked, Effects Not Automated
- Roll table entries have `mechanical_effect` like treasure values
- **Workaround:** DM applies effects manually
- **Priority:** Low - Standard table handling

### Cross-Hex Relationship Following
**Status:** Data Tracked, No Navigation Automation
- Lord Gnarlgruff has relationships to NPCs in hexes 0709, 0410
- **Workaround:** DM uses relationship data to guide storylines
- **Implemented:** Travel suggestions via `get_relationship_travel_suggestions`
- **Priority:** Low - Already has workaround

---

## Summary of Implementation Gaps

| Feature | Priority | Effort | Notes |
|---------|----------|--------|-------|
| Moon phase tracking | Medium | Medium | Would enhance NPC availability system |
| Kindred-restricted entry | Medium | Medium | Party composition checking |
| POI hazard auto-combat | Low | Low | Minor convenience improvement |
| Save hazards (charnel stench) | Low | Medium | Part of broader save system |
| Full moon night hazard | Medium | Medium | Requires moon phase + save system |
| Binding field usage | Low | Low | Narrative only |
| Discovery hints automation | Low | Low | Narrative only |
| mechanical_effect automation | Low | Medium | Would enhance table results |

---

## Cross-Hex Connections

| From NPC | Relationship | To NPC | Hex |
|----------|--------------|--------|-----|
| Lord Gnarlgruff | descendant | Lord Malbleat | 0709 |
| Lord Gnarlgruff | descendant | Lord Ramius | 0410 |

These relationships connect to the larger Longhorn nobility storyline:
- **Lord Malbleat (0709)**: Potential resurrector, occupies manor above Gnarlgruff's remains
- **Lord Ramius (0410)**: Rejected the necromantic heritage, would not aid resurrection
- **Book of Foul Wonders**: Quest hook leading eastward beyond Dolmenwood

---

## Narrative Hooks

1. **Resurrection Quest**: Retrieve Gnarlgruff's remains from Shadholme (0709) + Book of Foul Wonders from eastern sorcerer
2. **Faction Intrigue**: Malbleat vs Ramius, both descendants with different views on the ancestor
3. **Devil Goat Threat**: Hostile to all non-longhorns, dangerous night encounters
4. **Full Moon Mystery**: Spirit communication only on specific nights
5. **Treasure Hunting**: Bone pile contains valuable items (up to 400gp + magical items)
