# Hex 0108 (The Cabbage Plot) - Playability Status

## Summary

This document tracks the implementation status of hex 0108's features, including NPC intelligence, faction integration, investigation hazards, and evening encounters.

**Date:** 2026-01-04
**Implementation Version:** 1.0 (Full Automation)

---

## Fully Implemented Features

### Core Data Model Extensions (src/data_models.py)

#### HexProcedural
- `encounter_table: Optional[RollTable]` - Embedded hex-specific encounter table
- `investigation_hazard: Optional[dict]` - Triggered when investigating specific features

#### PointOfInterest
- `evening_hazard: Optional[dict]` - Triggered when staying at location during evening

#### HexNPC
- `group_count: Optional[str]` - Dice expression for group size (e.g., "1d4+1d4")
- `group_composition: Optional[dict]` - Breakdown by type (e.g., {"humans": "1d4", "shorthorns": "1d4"})
- `faction_profile: Optional[dict]` - Extended faction role info (role, standing, notes)

---

## Engine Methods (src/hex_crawl/hex_crawl_engine.py)

### check_investigation_hazard(hex_id, trigger)
- Checks if investigation hazard triggers when players investigate something
- Parses "X-in-6" probability strings
- Returns result ID when triggered (e.g., "murkins_soldiers_arrive")

**Example:**
```python
result = engine.check_investigation_hazard("0108", "investigate_cabbages")
# Returns: {triggered: True, description: "...", result: "murkins_soldiers_arrive", chance: "2-in-6"}
```

### check_evening_hazard(hex_id, poi_name)
- Checks if evening hazard triggers when staying at a POI
- Parses "X-in-6" probability strings
- Returns result ID when triggered (e.g., "murkins_soldiers_harassment")

**Example:**
```python
result = engine.check_evening_hazard("0108", "The Crimson Bath")
# Returns: {triggered: True, description: "...", result: "murkins_soldiers_harassment", chance: "3-in-6"}
```

### roll_hex_encounter_table(hex_id)
- Rolls on a hex's custom encounter table if present
- Handles both single rolls and range entries (e.g., "2-6")
- Returns table name, roll value, and result

**Example:**
```python
result = engine.roll_hex_encounter_table("0108")
# Returns: {has_table: True, roll: 1, result: "murkins_soldiers", description: "...", table_name: "Hex 0108 Encounters"}
```

### get_npc_group_size(hex_id, npc_id)
- Rolls for NPC group size when NPC represents multiple individuals
- Handles complex dice expressions like "1d4+1d4"
- Returns total count and composition breakdown

**Example:**
```python
result = engine.get_npc_group_size("0108", "murkins_soldiers")
# Returns: {is_group: True, total_count: 5, composition: {humans: 2, shorthorns: 3}, group_count_expression: "1d4+1d4"}
```

### _serialize_npc_intelligence(npc)
- Serializes a HexNPC's intelligence data for social context
- Extracts known_topics, secret_info, relationships, faction_profile, vulnerabilities
- Used when transitioning to SOCIAL_INTERACTION state

**Example:**
```python
intel = engine._serialize_npc_intelligence(npc)
# Returns: {known_topics: [...], secret_info: [...], faction_profile: {...}, relationships: [...]}
```

## GlobalController Methods (src/game_state/global_controller.py)

### _build_participant_from_intelligence(npc_id, npc_name, npc_intel, context)
- Creates SocialParticipant from serialized NPC intelligence
- Populates known_topics, secret_info, relationships, faction profile
- Stores vulnerabilities as DM hints in secrets list

**Example:**
```python
participant = controller._build_participant_from_intelligence(
    npc_id="timilda_brumble",
    npc_name="Timilda Brumble",
    npc_intel=intel,
    context={"hex_id": "0108", "disposition": 0}
)
# Returns: SocialParticipant with full intelligence
```

---

## Hex 0108 Content

### POI: The Crimson Bath
- **entering**: Details how to find and enter the inn
- **interior**: Description of the common room and atmosphere
- **exploring**: What players find when investigating
- **leaving**: Conditions for departure
- **evening_hazard**: 3-in-6 chance of Murkin's Soldiers visit each evening

### Roll Tables (3)
1. **Current Patrons** (d6) - Who's in the common room
2. **Crimson Bath Rumors** (d6) - Local gossip and leads
3. **Evening Events** (d6) - What happens during stay

### NPCs

#### Timilda Brumble (Innkeeper)
- 8 known_topics (local area, inn services, cabbage plot, etc.)
- 3 secret_info (cabbage plot conspiracy, Lord Murkin's abuse, escape desires)
- 4 vulnerabilities (Grerg's safety, coin, legal threats, Murkin's soldiers)
- 3 relationships (Grerg, Lord Ramius, Murkin's Soldiers)

#### Grerg Brumble (Husband/Combatant)
- is_combatant: true
- stat_reference: "Fighter 2"
- 4 known_topics (inn life, local defense, Timilda protection)
- 2 secret_info (hidden weapon, escape plan)

#### Murkin's Soldiers (NPC Group)
- faction: "house_murkin"
- group_count: "1d4+1d4"
- group_composition: {"humans": "1d4", "shorthorns": "1d4"}
- faction_profile: {faction_id: "house_murkin", role: "enforcers", standing: "low"}
- 4 known_topics (patrol routes, Lord Murkin orders, local threats)
- 2 secret_info (bribable, supply cache location) - can_be_bribed: true

### Procedural Section
- encounter_table: Custom d6 table (1=Murkin's Soldiers, 2-6=Standard High Wold)
- investigation_hazard: 2-in-6 when investigating cabbage fields

---

## Parser/Serializer Updates

### hex_loader.py
- Parses `encounter_table` from procedural section into RollTable object
- Parses `investigation_hazard` from procedural section
- Parses `evening_hazard` from POI data
- Parses `group_count`, `group_composition`, `faction_profile` from NPC data

### content_pipeline.py (_hex_to_dict)
- Serializes `encounter_table` using `_roll_table_to_dict()`
- Serializes `investigation_hazard` as-is
- Serializes `evening_hazard` as-is
- Serializes NPC group fields

### content_manager.py (_dict_to_hex)
- Deserializes `encounter_table` using `_dict_to_roll_table()`
- Deserializes `investigation_hazard` as-is
- Deserializes `evening_hazard` in `_dict_to_poi()`
- Deserializes NPC group fields

---

## Test Coverage

### tests/test_hex_0108_compat.py (29 tests)
- Hex loading and terrain validation
- POI entering/interior/roll_tables
- NPC known_topics, secret_info, relationships, vulnerabilities
- Faction topics and bribery
- Engine POI and NPC queries

### tests/hex_crawl/test_hex_0108_features.py (33 tests)
- Procedural encounter table parsing (4 tests)
- Investigation hazard parsing and engine method (4+4 tests)
- Evening hazard parsing and engine method (3+3 tests)
- NPC group fields parsing (3 tests)
- NPC group size engine method (5 tests)
- Chance check helper (3 tests)

### tests/hex_crawl/test_hex_0108_actions.py (54 tests)
- Hazard resolution helper (8 tests)
- Integration with hazard checks (2 tests)
- Wilderness investigate action (5 tests)
- Custom encounter table generation (9 tests)
- Multi-actor group encounters (8 tests)
- NPC intelligence serialization (5 tests)
- NPC intelligence in social context (7 tests)
- Roll hex encounter table action (6 tests)
- Roll hex encounter table suggestion (2 tests)

**Total: 116 tests passing**

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

# 1. Party enters hex 0108
engine._current_hex = "0108"

# 2. Party investigates the rotting cabbage fields
result = engine.check_investigation_hazard("0108", "investigate_cabbages")
if result["triggered"]:
    print(f"Murkin's Soldiers arrive! ({result['description']})")
    # Roll group size
    soldiers = engine.get_npc_group_size("0108", "murkins_soldiers")
    print(f"Group: {soldiers['total_count']} soldiers ({soldiers['composition']})")

# 3. Party visits The Crimson Bath for the evening
evening = engine.check_evening_hazard("0108", "The Crimson Bath")
if evening["triggered"]:
    print(f"Evening hazard: {evening['description']}")

# 4. Roll on custom encounter table
encounter = engine.roll_hex_encounter_table("0108")
if encounter["has_table"]:
    print(f"Rolled {encounter['roll']}: {encounter['result']} - {encounter['description']}")
```

---

## Remaining Low-Priority Items

### Combat Encounter Resolution
**Status:** Data tracked, combat not automated
- Murkin's Soldiers have `is_combatant: true` and `stat_reference`
- Combat encounter initiation returns result ID
- **Workaround:** DM receives "murkins_soldiers_arrive" result and runs combat manually

### Faction Reputation Tracking
**Status:** Faction profile stored, no reputation system
- `faction_profile` tracks role and standing
- No automatic reputation changes based on actions
- **Workaround:** DM tracks house_murkin reputation manually

### Bribery Mechanics
**Status:** Data tracked, no negotiation system
- `can_be_bribed: true` and `bribe_amount` stored on secrets
- No automated negotiation or disposition shift
- **Workaround:** DM checks secret_info for bribery options during roleplay
