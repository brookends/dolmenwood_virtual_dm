# Dolmenwood Virtual DM — Integrated Faction System Patch Plan (v4)

This document updates and extends the existing **Faction Turns (Territory-Only)** patch plan to incorporate:
- **Inter-faction relationships** (relationship matrix / group rules)
- **Adventurer interaction** rules (affiliation, quests, rewards, trade, risks)
- **Wiring** into the existing Virtual DM engines (downtime/settlement/encounter/hex-crawl) without violating the core philosophy:  
  **Python is the referee; the LLM is the narrator (optional).**

**Primary goals**
1. Maintain the territory-only faction turns loop (weekly cadence, 3 actions, d6 + ±1 modifier, effects interpreter).
2. Add a *mechanized* faction relationship layer and party-facing interaction layer.
3. Keep the system fully playable with LLM disabled.
4. Keep changes incremental, reviewable, and deterministic in tests (seeded dice, no ad-hoc random).

---

## 0) Inputs reviewed

- Existing patch plan: `Dolmenwood_Faction_Turns_Territory_Patch_Plan_WIRING_AUDIT_UPDATED.md`
- Skeleton patch: `dolmenwood_faction_turns_skeleton.patch` (scaffolding, not cleanly applicable)
- Sample faction content: `faction_sample_content.tar.gz` (JSON faction definitions + rules/index/schema stub)
- Relationship + adventurer interaction reference: `output.pdf` (major faction relationships + how factions deal with adventurers)

---

## 1) Scope update: from “territory-only turns” → “integrated faction system”

### 1.1 Must-have (core simulation)
- Weekly (7-day) faction cycle cadence; per-cycle action advancement and completion effects.
- Territory points, level (cap 4), scaling by level.
- Deterministic RNG and logging.

### 1.2 New (relationships + party interaction)
- **Faction Relationship Matrix**
  - Stores attitudes and “soft constraints” between *major factions* (fear/hate/allied/pact/etc).
  - Supports **group-level** rules (e.g., “Human Nobility” applies to all human houses).
- **Party ↔ Faction Standing**
  - Party reputation/standing with factions and/or groups, plus optional affiliation/fealty records.
  - Used to modify outcomes of: reaction rolls, negotiations, faction quests, and faction interference.
- **Faction Jobs / Quests**
  - Mechanized templates for “example quests” (the LLM may narrate the resolved outcome).
  - Hooked into downtime “faction work” and/or settlement patronage.
- **World News**
  - Faction turns + party interactions emit concise “news” items for offline UI and LLM narration.

---

## 2) Naming + collision avoidance

The repo already contains `FactionState` and `FactionRelationship` in `src/data_models.py` for local relationship graphs.
To avoid confusion:

- Use `FactionTurnState` (or `FactionWorldState`) for the new long-term faction-turn system.
- Use `FactionRelationshipMatrix` / `FactionRelations` for global faction-to-faction attitudes.
- Use `PartyFactionState` for party standing/affiliation.

Do **not** introduce a second global `FactionState` class name at the top level.

---

## 3) Content additions (data/content/factions/)

Keep the existing plan’s directory: `data/content/factions/`.

### 3.1 Existing files (from v3 plan)
- `faction_rules.json`
- `faction.schema.json` (optional validation stub)
- `factions_index.json` (optional)
- `faction_*.json` (per faction definition)

### 3.2 New files (relationships + adventurer interaction)
Add:

1) `faction_relationships.json`
- Defines pairwise relationships between faction ids **and** faction “groups” (see below).
- Includes a score (-100..100) and a sentiment tag (fear/hate/allied/etc).

2) `faction_groups.json` (or embed groups inside `faction_relationships.json`)
- Maps group ids to a tag matcher (e.g., `human_nobility` matches any faction with tag `human_nobility`).
- Enables a single relationship statement to apply to multiple house factions.

3) `faction_adventurer_profiles.json`
- Per-faction (or per-group) definitions:
  - join/fealty rules (alignment constraints, “fully initiable” boolean)
  - rewards list
  - quest templates (IDs, tags, mechanical default effects)
  - trade hooks
  - risk notes (e.g., audience danger with Atanuwë)

### 3.3 Data hygiene tasks (recommended)
- Ensure all noble houses carry unambiguous tags:
  - Human houses already use `human_nobility`.
  - Add `longhorn_nobility` to all High Wold longhorn houses (some sample files only have `high_wold` or `nobility`).
- Resolve the index filename mismatch:
  - If `factions_index.json` exists, loader should tolerate both `nag_lord.json` and `faction_nag_lord_atanuwe.json` style names (or regenerate the index).

Companion examples are provided as:
- `faction_relationships.example.json`
- `faction_adventurer_profiles.example.json`

---

## 4) Runtime architecture (updated)

### 4.1 Core subsystem: `FactionEngine`
Responsibilities:
- Load faction definitions + relationships + adventurer profiles.
- Maintain:
  - `FactionTurnState` per faction (territory, level, actions, logs, modifiers)
  - `PartyFactionState` (standing, affiliations, active faction jobs)
- Run cycles on cadence (default weekly), using existing `TimeTracker.register_day_callback(days_passed:int)` seam.
- Emit “news” items for UI/LLM.

### 4.2 Supporting services (keep small + testable)
- `FactionLoader` (definitions)
- `FactionRelationsLoader` (relationships + group matcher)
- `FactionAdventurerProfileLoader` (adventurer interaction affordances)
- `FactionEffectsInterpreter` (existing plan)
- `FactionInteractionResolver` (party-facing: seek work, accept/complete jobs, compute reaction modifiers)

> Keep the referee/narrator split: **All rolls and state updates happen in Python.**  
> The LLM (if enabled) receives the resolved outcomes and may narrate them.

---

## 5) Wiring plan (repo-integrated)

### 5.1 VirtualDM wiring (`src/main.py`)
Follow v3 wiring seams and extend them:

1) **Initialize** after `GlobalController` is constructed:
- `self.faction_engine = FactionEngine(controller=self.controller, content_root=config.content_dir, ...)`
- `self.faction_engine.initialize()`

2) **Register day callback**:
- `self.controller.time_tracker.register_day_callback(self.faction_engine.on_days_advanced)`

3) **Save/Load**:
- In `save_game()`: `session.custom_data["faction_state"] = self.faction_engine.serialize_state()`
- In `load_game()`: if present, `self.faction_engine.deserialize_state(session.custom_data["faction_state"])`

4) **State export**:
- In `get_full_state()`: merge
  - `{"factions": self.faction_engine.get_public_state()}`
  - `{"faction_party": self.faction_engine.get_party_public_state()}` (or a combined shape)

### 5.2 Conversation / UI actions
Add minimal offline-visible actions:

- `meta:factions` → show overall faction status + recent news
- `factions:relations` → show relation between two faction ids (or a faction and the party)
- `factions:seek_work` → generate faction job offers (by faction id or by current settlement)
- `factions:accept_job`, `factions:complete_job` (optional; can be subsumed by downtime “faction work”)

Implementation seams:
- `src/conversation/action_registry.py` (register ActionSpec → handler)
- `src/conversation/suggestion_builder.py` (low priority “Faction status” suggestion)

### 5.3 Downtime “Faction Work” integration (`src/downtime/downtime_engine.py`)
The repo already contains a `FACTION_WORK` downtime activity and a rudimentary faction relation model.

Update plan:
- Route downtime `FACTION_WORK` through `FactionInteractionResolver`:
  - If the player chooses a target faction/group, generate a job offer.
  - Resolve success/failure with **controller.dice_roller** (no new DiceRoller instances).
  - Apply:
    - party standing changes
    - registered “interference” / consequences in `FactionEngine`
    - world news log entry

Also: persist the party’s faction standing in `FactionEngine` (not only in downtime engine ephemeral state).

### 5.4 Settlement conversation hooks (`src/settlement/settlement_engine.py`)
NPCs and settlements already have a `faction` field.

Update plan:
- When generating conversation content for topic “FACTION”:
  - Pull faction definition summary (name/description/known territory)
  - Include party standing/fealty status (if any)
  - Include 1–2 relevant recent “news” items
  - Provide a deterministic “patronage hook” (suggest `factions:seek_work` if appropriate)

### 5.5 Encounter reaction modifiers (optional but recommended)
Add a small modifier function:
- Inputs: encountered NPC faction (if any), party standing, party affiliations, and global relations.
- Output: integer modifier to reaction roll (cap to ±2, default ±1).
- Used by `EncounterEngine.interpret_reaction(...)` or wherever reaction is rolled.

### 5.6 Hex-crawl/local reputation integration
The repo already has a local `FactionState` relationship graph in `src/data_models.py` used by hex-crawl.

Do **not** replace it initially.
Instead:
- If an entity references a known global faction id, the local graph can consult the global relationship matrix for defaults.
- Party standing with major factions should be sourced from `FactionEngine` when available, with local deltas layered on top.

---

## 6) Updated mechanics: relationships + adventurer interactions

### 6.1 Relationship scores (mechanized)
Store relationships as:
- `score`: -100..100 (mechanical)
- `sentiment`: string tag (narrative)
- `notes`: source justification / reminder

Use score only for:
- computing reaction modifiers
- generating “news framing”
- selecting likely conflict/aid between factions (optional extension)

### 6.2 Party standing
Store party standing as an int (e.g., -10..+10) per faction id and per group id.
- Joining/fealty creates an “affiliation” record with ranks.
- Standing modifies:
  - job access (minimum standing)
  - reaction rolls
  - faction interference modifiers

### 6.3 Adventurer profile rules
Encode:
- alignment constraints
- “fully initiable” boolean (Drune and Witches are NPC-only factions for full initiation)
- rewards list
- quest templates list

Quest templates produce:
- deterministic mechanical effects on completion/failure
- optional follow-up hooks (e.g., “spawn rumor”, “apply_modifier_next_turn”)

---

## 7) Implementation steps (safe order)

1) **Content**: create `data/content/factions/` + drop in rules + definitions + new relationship/profile json files.
2) **Core modules**: implement loaders + models + engine + effects interpreter (territory-only, as in v3 plan).
3) **VirtualDM wiring**: init/save/load/get_full_state + TimeTracker callback.
4) **UI surface**: `meta:factions` action returning deterministic status + public_state.
5) **Party standing storage**: introduce `PartyFactionState` persisted in the same save blob.
6) **Downtime integration**: route `FACTION_WORK` through faction interaction layer.
7) **Settlement integration**: conversation topic “FACTION” uses faction engine for info.
8) **(Optional) Encounter mods + deeper engine hooks**.

Each step must keep tests green and be reviewable in isolation.

---

## 8) Tests (deterministic)

Add/extend tests:
- Loader tests:
  - loads definitions, relationships, profiles; tolerant of index mismatch
- Cycle tests:
  - cadence trigger (advance 7 days → exactly one cycle)
  - action selection + modifier cap
  - progress advancement rules (4–5 => +1, 6+ => +2)
  - completion applies effects and replaces action
- Persistence:
  - save/load roundtrip preserves faction + party state
- Interaction:
  - downtime faction work generates job, rolls deterministically, applies standing and news

All tests must seed dice (`DiceRoller.set_seed(...)` or existing fixtures).

---

## 9) Acceptance criteria (definition of “done”)

Minimum ship criteria:
- New faction system runs automatically on week boundaries.
- `meta:factions` shows status in offline mode.
- Save/load roundtrip works.
- Relationships and party standing are present in public state.
- Downtime faction work can change party standing and produces a news entry.

---

## 10) Recovery prompt (if session is restarted)

If you need to continue work in a fresh session, use this prompt:

> “Open the repo zip and the four uploaded files. Read:
> - `Dolmenwood_Faction_System_Integrated_Patch_Plan_v4.md`
> - `Dolmenwood_Faction_System_Implementation_Schematics_v4.md`
> - `faction_relationships.example.json`
> - `faction_adventurer_profiles.example.json`
> Then implement the patch plan step-by-step, keeping changes incremental and tests deterministic.”

