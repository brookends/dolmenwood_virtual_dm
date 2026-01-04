# Hex 0109 (Lady Borrid and Murkin's Army) - Playability Status

## Summary

This document tracks the implementation status of hex 0109's features, including NPC intelligence, faction integration, POI roll tables, investigation hazards, and evening hazards.

**Date:** 2026-01-04
**Implementation Version:** 1.0 (Full Automation)

---

## Fully Implemented Features

### Core Data Model Extensions (src/data_models.py)

#### HexProcedural
- `encounter_table: Optional[RollTable]` - Embedded hex-specific encounter table (d6)
- `investigation_hazard: Optional[dict]` - Triggered when investigating the army camp
- `foraging_results: str` - Description of foraging yields
- `foraging_special: list[str]` - Special foraging items (hazelnuts, chestnuts, mushrooms)

#### PointOfInterest
- `evening_hazard: Optional[dict]` - Both POIs have evening hazards
- `roll_tables: list[RollTable]` - Lodge has 2 tables, Camp has 2 tables
- `secrets: list[str]` - Both POIs have secrets

#### HexNPC
- `known_topics: list[KnownTopic]` - Both NPCs have 8+ topics
- `secret_info: list[SecretInfo]` - Both NPCs have 3+ secrets
- `relationships: list[dict]` - Both NPCs have cross-hex relationships
- `faction_profile: Optional[dict]` - Both NPCs have house_murkin profiles
- `vulnerabilities: list[str]` - Both NPCs have vulnerabilities
- `personal_feelings: Optional[str]` - Snidebleat has "loathes employer"

---

## Engine Methods (src/hex_crawl/hex_crawl_engine.py)

### check_investigation_hazard(hex_id, trigger)
- **Status:** Implemented
- Checks if investigation hazard triggers when investigating the camp
- Returns result ID "camp_alarm" when triggered

**Example:**
```python
result = engine.check_investigation_hazard("0109", "investigate_camp")
# Returns: {triggered: True, description: "...", result: "camp_alarm", chance: "3-in-6"}
```

### check_evening_hazard(hex_id, poi_name)
- **Status:** Implemented
- Works for both Lodge (4-in-6 dinner invitation) and Camp (2-in-6 patrol)

**Example:**
```python
result = engine.check_evening_hazard("0109", "Lady Borrid's Hunting Lodge")
# Returns: {triggered: True, result: "dinner_invitation", chance: "4-in-6"}
```

### roll_hex_encounter_table(hex_id)
- **Status:** Implemented
- Rolls on custom d6 table (1=patrol, 2=hunting party, 3-6=standard)

**Example:**
```python
result = engine.roll_hex_encounter_table("0109")
# Returns: {has_table: True, roll: 2, result: "hunting_party", description: "..."}
```

### roll_on_poi_table(hex_id, table_name, poi_name)
- **Status:** Implemented
- Rolls on POI tables like "Hunting Companions Present" or "Camp Activities"
- Supports `unique_entries` for Trophy Room Curiosities

**Example:**
```python
result = engine.roll_on_poi_table("0109", "Camp Activities", "Murkin's Army")
# Returns: {roll: 3, title: "Press-Gang Returns", description: "...", mechanical_effect: "..."}
```

### sleep_at_poi(hex_id, poi_name, character_ids)
- **Status:** Implemented
- Works for staying at the Lodge overnight
- Checks evening hazard, applies rest effects

---

## Hex 0109 Content

### POI: Lady Borrid's Hunting Lodge

| Feature | Status | Notes |
|---------|--------|-------|
| **entering** | Implemented | Moose head alarm described but not automated |
| **interior** | Implemented | Trophy room with Wyrm skull, manticore head |
| **exploring** | Implemented | Three floors, cellars with vault |
| **leaving** | Implemented | Brynne tracking not automated |
| **evening_hazard** | Implemented | 4-in-6 dinner invitation |
| **roll_tables** | Implemented | 2 tables (Companions, Trophies) |
| **secrets** | Implemented | Secret vault, moose head silencing |

### POI: Murkin's Army

| Feature | Status | Notes |
|---------|--------|-------|
| **entering** | Implemented | Sentry challenge described but sneaking not automated |
| **interior** | Implemented | 12 tents, command tent, supply area |
| **exploring** | Implemented | Sneaking, prisoner discovery described |
| **leaving** | Implemented | Escort/pursuit described |
| **evening_hazard** | Implemented | 2-in-6 night patrol |
| **roll_tables** | Implemented | 2 tables (Activities, Morale) |
| **secrets** | Implemented | Desertion potential, Snidebleat's cache |

### Roll Tables (4 total)

1. **Hunting Companions Present** (d6) - Who's at the lodge
2. **Trophy Room Curiosities** (d6, unique) - Notable items to discover
3. **Camp Activities** (d6) - What soldiers are doing
4. **Soldier Morale** (d6) - Current mood of troops

### NPCs

#### Lady Amonie Borrid (Level 9 Hunter)
- **is_combatant:** true
- **stat_reference:** "Level 9 Hunter"
- **known_topics:** 10 topics (welcome, hunt, wyrm, Murkin, war, Ramius, woods, Brynne, cheese monstrosity, politics)
- **secret_info:** 4 secrets (rebellion sympathy, Timilda messages, peacemaker plan, vault documents)
- **relationships:** 4 (Lord Murkin, Timilda Brumble, Snidebleat, Lord Ramius)
- **faction_profile:** house_murkin (role: "dissident_family", standing: "high")
- **vulnerabilities:** 4 (mention of cousin, war casualties, legendary beasts, threat to common folk)

#### Sergeant Crewwin Snidebleat (Level 4 Knight)
- **is_combatant:** true
- **stat_reference:** "Level 4 Knight"
- **faction:** "house_murkin"
- **loyalty:** "bought"
- **personal_feelings:** "loathes employer"
- **known_topics:** 9 topics (challenge, orders, troops, Murkin plans, Nodlock war, Horns of Kolstoke, ambition, Lady Borrid, Red Gwen)
- **secret_info:** 5 secrets (loathes Murkin, bribable for passage, Red Gwen alliance, troop morale, hidden wealth)
- **relationships:** 4 (Lord Murkin, Red Gwen, Lady Borrid, soldiers)
- **faction_profile:** house_murkin (role: "knight", standing: "medium")
- **vulnerabilities:** 5 (bribery, glory, Red Gwen mention, Murkin insult, wealth threat)

### Procedural Section
- **encounter_table:** Custom d6 (1=patrol, 2=hunting party, 3-6=standard High Wold)
- **investigation_hazard:** 3-in-6 when investigating camp (triggers "camp_alarm")
- **foraging_results:** Hazelnuts, chestnuts, mushrooms (some hallucinogenic)

### Items (6)
1. Horn of Blasting (5,000gp, magical, hidden in trophies)
2. Fairy Shortbow (3,000gp, magical, in vault)
3. Fairy Arrows - Breggle Bane x12 (1,200gp, magical, in vault)
4. Vault Chalices and Jewels (8,000gp, in vault)
5. Snidebleat's Onyxes (1,000gp, buried under tent)
6. Ring of Energy Resistance - Fire (2,500gp, worn by Snidebleat)

---

## Test Coverage

### tests/hex_crawl/test_hex_0109_features.py (37 tests)
- Hex loading (5 tests)
- Lady Borrid NPC intelligence (7 tests)
- Sergeant Snidebleat NPC intelligence (7 tests)
- POI evening hazards (3 tests)
- Investigation hazard (2 tests)
- Roll tables (3 tests)
- Encounter table (2 tests)
- Items (3 tests)
- Secrets (2 tests)
- Runtime bootstrap parser (3 tests)

### tests/hex_crawl/test_poi_entry_conditions.py (21 tests)
- SocialParticipant permissions (5 tests)
- POI entry conditions (12 tests)
- Permission from social context (2 tests)
- Engine integration (2 tests)

### tests/hex_crawl/test_poi_alarm_system.py (23 tests)
- POIVisit alarm tracking (2 tests)
- Unauthorized entry alerts (4 tests)
- Silence alarm (5 tests)
- Stealth entry (4 tests)
- Get POI info (4 tests)
- Camp sentry alarm (4 tests)

### tests/hex_crawl/test_poi_secret_discovery.py (19 tests)
- Concealed items with reveals_secret (2 tests)
- Hidden POI visibility (3 tests)
- Search reveals secret (6 tests)
- Navigation to discovered POI (4 tests)
- Discovered secrets tracking (3 tests)
- Integration flow (1 test)

### tests/hex_crawl/test_poi_buried_treasure.py (13 tests)
- Buried coffer data (2 tests)
- Search reveals items (4 tests)
- Take item after discovery (4 tests)
- Integration flow (1 test)
- Item persistence (2 tests)

### tests/hex_crawl/test_stealth_camp_entry.py (24 tests)
- Method exists (2 tests)
- Stealth success (4 tests)
- Stealth failure (4 tests)
- Sentry count difficulty (4 tests)
- Stealth modifier (2 tests)
- Error handling (3 tests)
- Action registry (2 tests)
- Murkin's Army integration (3 tests)

**Total: 137 tests passing**

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

# 1. Party enters hex 0109
engine._current_hex = "0109"

# 2. Party approaches Murkin's Army camp (investigation hazard)
result = engine.check_investigation_hazard("0109", "investigate_camp")
if result["triggered"]:
    print(f"ALARM! Sentries spotted the party: {result['description']}")

# 3. Roll on encounter table
encounter = engine.roll_hex_encounter_table("0109")
if encounter["has_table"]:
    print(f"Rolled {encounter['roll']}: {encounter['result']} - {encounter['description']}")

# 4. Visit Lady Borrid's Lodge - roll for who's present
companions = engine.roll_on_poi_table("0109", "Hunting Companions Present", "Lady Borrid's Hunting Lodge")
print(f"At the lodge: {companions['title']} - {companions['description']}")

# 5. Explore trophy room
trophy = engine.roll_on_poi_table("0109", "Trophy Room Curiosities", "Lady Borrid's Hunting Lodge")
print(f"Found: {trophy['title']} - {trophy['description']}")

# 6. Stay overnight (evening hazard + rest)
rest_result = engine.sleep_at_poi("0109", "Lady Borrid's Hunting Lodge")
if rest_result.get("evening_hazard", {}).get("triggered"):
    print("Evening event: Dinner invitation from Lady Borrid!")
print(f"Rest result: {rest_result['message']}")
```

---

## Features NOT Yet Automated (Low Priority)

### Moose Head Alarm System
**Status:** Implemented
- Alarm triggers on unauthorized entry via `enter_poi_with_conditions`
- Can be silenced with acorns via `silence_poi_alarm` method
- Stealth entry available via `enter_poi_stealth` method

### Secret Door / Vault Discovery
**Status:** Implemented
- `search_poi_location("cellars")` can find the Secret Vault Door
- Finding it reveals "hidden_vault" secret via `reveals_secret` field
- Lady Borrid's Hidden Vault POI becomes visible after discovery
- Navigate to vault via `navigate_to_child_poi`

### Snidebleat's Buried Treasure
**Status:** Implemented
- `search_poi_location("command tent")` can find the Buried Coffer (DC 5)
- Finding coffer makes onyxes takeable via `take_item`
- Items properly tracked in POI state

### Press-Gang Rescue Mechanics
**Status:** Described in Camp Activities table, no automation
- "Press-Gang Returns" entry notes "Potential rescue opportunity"
- **Workaround:** DM handles as roleplay/combat scenario

### Stealth/Sneaking Into Camp
**Status:** Implemented
- `sneak_into_poi` engine method uses skill_resolver for d6 stealth check
- Sentry count (2d4) affects difficulty: 0-2 sentries = DC 4, 3-4 = DC 5, 5+ = DC 6
- Success: enter POI undetected, no hazards triggered
- Failure: triggers investigation hazard (camp_alarm)
- Player action: `wilderness:sneak_into_poi`

### Animal Companion Tracking (Brynne)
**Status:** Described in `leaving`, no automation
- Giant weasel may track those who leave by stealth
- **Workaround:** DM narrates pursuit if players sneak out

### mechanical_effect Application
**Status:** Data tracked, effects not automated
- Roll table entries have `mechanical_effect` like "+1 to reaction rolls"
- **Workaround:** DM applies modifiers manually during play

### Foraging Mushroom Hallucination
**Status:** Described in foraging_results, no automation
- "1-in-6 chance of mild hallucination if not properly prepared"
- **Workaround:** DM rolls for hallucination effect separately

### Cross-Hex Relationship Following
**Status:** Data tracked, no navigation automation
- NPCs have relationships to NPCs in hexes 0108, 0208, 0311
- **Workaround:** DM uses relationship data to guide narrative connections

### Bribery Resolution
**Status:** Data tracked (can_be_bribed, bribe_amount), no negotiation system
- Snidebleat's secrets have bribe amounts (50gp, 100gp, 200gp)
- **Workaround:** DM checks secret_info during roleplay

### Combat Encounter Resolution
**Status:** NPCs have stat_reference, combat not automated
- Lady Borrid: "Level 9 Hunter"
- Snidebleat: "Level 4 Knight"
- Soldiers: "Level 1 fighters"
- **Workaround:** DM runs combat manually using stats

---

## Summary of Implementation Gaps

| Feature | Priority | Effort | Notes |
|---------|----------|--------|-------|
| mechanical_effect automation | Medium | Medium | Would enhance POI table results |
| Stealth system for camp infiltration | Low | High | Complex system needed |
| Alarm/trap triggers | Low | Medium | General POI alarm system |
| Secret door discovery | Low | Medium | Part of broader search system |
| Bribery negotiation | Low | Medium | Social interaction enhancement |
| Combat encounter initiation | Low | High | Full combat system integration |

---

## Cross-Hex Connections

| From NPC | Relationship | To NPC | Hex |
|----------|--------------|--------|-----|
| Lady Borrid | family (cousin) | Lord Murkin | 0208 |
| Lady Borrid | secret_ally | Timilda Brumble | 0108 |
| Lady Borrid | hopeful_ally | Lord Ramius | - |
| Snidebleat | employer | Lord Murkin | 0208 |
| Snidebleat | secret_correspondent | Red Gwen | 0311 |

These relationships enable faction-spanning storylines connecting the Cabbage Plot rebellion (0108), Kolstoke Keep (0208), and the bandit queen (0311).
