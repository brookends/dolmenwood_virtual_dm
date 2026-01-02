# Dolmenwood Virtual DM — Faction System Implementation Schematics (v4)

This is an implementation-oriented companion to the v4 patch plan. It provides module layouts, class outlines, method signatures, and deterministic resolution guidance.

---

## 1) New modules

Create:

- `src/factions/__init__.py`
- `src/factions/faction_models.py`
- `src/factions/faction_loader.py`
- `src/factions/faction_relations.py`
- `src/factions/faction_adventurers.py`
- `src/factions/faction_effects.py`
- `src/factions/faction_engine.py`
- `src/factions/faction_interactions.py` (party-facing, optional but recommended)

> Note: avoid naming collisions with `src/data_models.py` (which already contains `FactionState` and `FactionRelationship`).

---

## 2) Data model outlines (Python)

### 2.1 Static content

```python
@dataclass(frozen=True)
class Resource:
    id: str
    name: str
    tags: list[str]
    description: str | None = None

@dataclass(frozen=True)
class Goal:
    id: str
    name: str
    description: str
    visibility: Literal["landmark","hidden","secret"]
    priority: int = 0

@dataclass(frozen=True)
class ActionTemplate:
    action_id: str
    name: str
    scope: Literal["task","mission","goal"]
    description: str
    resource_tags: list[str]
    targets: list[dict]  # hex/settlement/faction/etc
    segments: int | None = None
    on_complete: list[dict] = field(default_factory=list)

@dataclass(frozen=True)
class FactionDefinition:
    faction_id: str
    name: str
    description: str
    alignment: str | None = None
    type: str | None = None
    tags: list[str] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    action_library: list[ActionTemplate] = field(default_factory=list)
```

### 2.2 Dynamic state (persisted)

```python
@dataclass
class ActionInstance:
    action_id: str
    goal_id: str | None
    progress: int
    segments: int
    started_on: str  # ISO date
    notes: str = ""

@dataclass
class Territory:
    hexes: set[str] = field(default_factory=set)
    settlements: set[str] = field(default_factory=set)
    strongholds: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)

@dataclass
class FactionTurnState:
    faction_id: str
    territory: Territory = field(default_factory=Territory)
    active_actions: list[ActionInstance] = field(default_factory=list)  # exactly 3
    modifiers_next_cycle: list[dict] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)  # compact log entries
```

### 2.3 Party state (persisted)

```python
@dataclass
class PartyAffiliation:
    faction_or_group: str
    kind: Literal["fealty","oath","working_relationship","cult_blessing"]
    rank: int = 0
    since_date: str | None = None

@dataclass
class PartyFactionState:
    standing_by_id: dict[str, int] = field(default_factory=dict)   # faction_id or group_id -> standing
    affiliations: list[PartyAffiliation] = field(default_factory=list)
    active_jobs: dict[str, dict] = field(default_factory=dict)     # job_id -> job record
```

---

## 3) Loaders

### 3.1 FactionLoader
Responsibilities:
- Read JSON from `data/content/factions/`
- If `factions_index.json` exists: load listed files, tolerating mismatched names
- Else: glob `*.json`, filter those containing `faction_id`

API:

```python
class FactionLoader:
    def __init__(self, content_root: Path): ...
    def load_rules(self) -> dict: ...
    def load_definitions(self) -> dict[str, FactionDefinition]: ...
```

### 3.2 Relations loader + matcher

```python
@dataclass(frozen=True)
class Relation:
    a: str
    b: str
    score: int  # -100..100
    sentiment: str
    notes: str

@dataclass(frozen=True)
class GroupRule:
    group_id: str
    match_tags_any: list[str]

class FactionRelations:
    def __init__(self, relations: list[Relation], groups: dict[str, GroupRule], defs: dict[str,FactionDefinition]): ...

    def resolve_ids(self, faction_id: str) -> list[str]:
        # return [faction_id] + group_ids matched by tags

    def get_score(self, a_id: str, b_id: str) -> int:
        # exact pair > group pair > 0

    def get_relation(self, a_id: str, b_id: str) -> Relation | None: ...
```

### 3.3 Adventurer profiles loader

```python
class FactionAdventurerProfiles:
    def get_profile(self, faction_or_group_id: str) -> dict | None: ...
    def list_job_templates(self, faction_or_group_id: str) -> list[dict]: ...
```

---

## 4) Engine design

### 4.1 FactionEngine public API

```python
class FactionEngine:
    def __init__(self, controller: GlobalController, content_root: Path, *, enabled: bool = True): ...

    def initialize(self) -> None:
        self.rules = ...
        self.defs = ...
        self.relations = ...
        self.profiles = ...
        self.state = ...        # faction_id -> FactionTurnState
        self.party = ...        # PartyFactionState

    def on_days_advanced(self, days_passed: int) -> None:
        # accumulate; when >= cadence => run_cycle()

    def run_cycle(self, *, reason: str = "weekly") -> list[dict]:
        # returns news items (also stored)

    def serialize_state(self) -> dict: ...
    def deserialize_state(self, blob: dict) -> None: ...

    def get_public_state(self) -> dict: ...
    def get_party_public_state(self) -> dict: ...

    # Party interaction helpers
    def adjust_party_standing(self, faction_or_group: str, delta: int, *, reason: str) -> None: ...
    def register_interference(self, faction_id: str, *, kind: str, magnitude: int, reason: str) -> None: ...
```

### 4.2 Deterministic action selection (no random.choice)

Use `controller.dice_roller`:
- If you need a uniform selection from N items: roll `dN` and index.
- Log the roll into the faction log entry.

### 4.3 Progress advancement
Exactly as v3 plan:
- Roll d6
- Mod: +1 if matching resource tags; -1 if interference/opposition; cap ±1
- 4–5: +1; 6+ => +2; 1: optional complication tag (oracle table), deterministic

### 4.4 News generation
Each cycle should produce compact structured “news” entries:

```json
{"date":"1023-03-10","faction":"witches","type":"action_progress","action_id":"witch_fetch_herbs","delta":1,"completed":false}
```

Narration can be generated from this in offline or LLM mode.

---

## 5) Party interaction resolver (recommended)

### 5.1 Job lifecycle
- `seek_work(faction_or_group_id, context)` returns a list of offers (templates + rolled details).
- `accept_job(job_id)` stores into `PartyFactionState.active_jobs`.
- `resolve_job(job_id, outcome)` applies standing changes + interference + news.

### 5.2 Reaction modifier helper
Provide a helper used by Encounter/Settlement:

```python
def compute_reaction_modifier(npc_faction_id: str | None, party: PartyFactionState, relations: FactionRelations) -> int:
    # Start with standing thresholds (e.g. >= +3 => +1; <= -3 => -1)
    # Add “affiliation friction”: if party affiliated with church and NPC is witches, apply -1 etc.
    # Cap to ±2.
```

---

## 6) Wiring checklists (per file)

### 6.1 `src/main.py` (VirtualDM)
- Create `self.faction_engine`
- Register day callback
- Save/load `session.custom_data["faction_state"]`
- Merge into `get_full_state()`

### 6.2 `src/conversation/action_registry.py`
- Add ActionSpec for `meta:factions` (offline inspectability)
- Optional: actions for relations and seek_work

### 6.3 `src/downtime/downtime_engine.py`
- Route FACTION_WORK through faction interaction resolver
- Remove local ad-hoc DiceRoller instance; use `self.controller.dice_roller`

### 6.4 `src/settlement/settlement_engine.py`
- When NPC has `faction`, query engine for public info + party standing.
- Suggest faction work/patronage.

---

## 7) Minimal deterministic tests

- `test_faction_cycle_weekly_trigger()`
- `test_action_progress_rules()`
- `test_state_roundtrip()`
- `test_meta_factions_action_offline()`
- `test_downtime_faction_work_applies_standing()`

---

## 8) Resume prompt

If interrupted, reload the v4 patch plan + this schematics doc, then implement steps 1→8 in order, keeping each PR-sized and fully tested.

