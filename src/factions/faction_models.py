"""
Data models for the Dolmenwood Faction System.

These models represent:
- Static content loaded from JSON (FactionDefinition, Resource, Goal, ActionTemplate)
- Dynamic state persisted in saves (FactionTurnState, ActionInstance, Territory)
- Party-facing state (PartyFactionState, PartyAffiliation)

Naming notes:
- Uses FactionTurnState (not FactionState) to avoid collision with
  src/data_models.py's local FactionState for hex relationships.
- Uses FactionRelationshipMatrix (not FactionRelationship) to avoid collision
  with src/data_models.py's FactionRelationship for local NPC relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


# =============================================================================
# STATIC CONTENT (loaded from JSON, immutable at runtime)
# =============================================================================


@dataclass(frozen=True)
class Resource:
    """A faction resource that can justify +1/-1 modifiers on actions."""
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass(frozen=True)
class Goal:
    """A faction goal that actions work toward."""
    id: str
    name: str
    description: str = ""
    visibility: Literal["landmark", "hidden", "secret"] = "landmark"
    priority: int = 0
    default_scope: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class ActionTarget:
    """Target specification for an action (hex, settlement, faction, etc.)."""
    type: str  # "hex", "settlement", "faction", "stronghold", "region", "site", "domain"
    id: str


@dataclass(frozen=True)
class EffectCommand:
    """An effect command to execute when an action completes."""
    type: str  # "claim_territory", "set_flag", "add_rumor", "apply_modifier_next_turn", etc.
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EffectCommand":
        """Create from JSON dict."""
        effect_type = d.get("type", "unknown")
        # Copy all fields except 'type' into data
        data = {k: v for k, v in d.items() if k != "type"}
        return cls(type=effect_type, data=data)


@dataclass(frozen=True)
class ActionTemplate:
    """Template for a faction action from the action library."""
    action_id: str
    name: str
    scope: Literal["task", "mission", "goal", "operation", "diplomacy"] = "mission"
    description: str = ""
    goal_id: Optional[str] = None
    resource_tags: list[str] = field(default_factory=list)
    targets: list[ActionTarget] = field(default_factory=list)
    segments: Optional[int] = None  # If None, use default from rules based on scope
    on_complete: list[EffectCommand] = field(default_factory=list)


@dataclass(frozen=True)
class Enclave:
    """A faction enclave/stronghold/domain."""
    id: str
    name: str
    hex: str
    type: str  # "stronghold", "settlement_control", "nodal_stone", "region"
    role: str = ""
    status: str = "active"
    summary: str = ""


@dataclass(frozen=True)
class HomeTerritory:
    """Initial territory holdings for a faction."""
    hexes: list[str] = field(default_factory=list)
    settlements: list[str] = field(default_factory=list)
    strongholds: list[dict[str, Any]] = field(default_factory=list)  # [{id, points}]
    domains: list[dict[str, Any]] = field(default_factory=list)  # [{id, points}]


@dataclass(frozen=True)
class FactionDefinition:
    """
    Static definition of a faction loaded from JSON.

    Contains all immutable data: identity, resources, goals, action library.
    Dynamic state is stored separately in FactionTurnState.
    """
    faction_id: str
    name: str
    description: str = ""
    alignment: Optional[str] = None
    faction_type: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    territory_model: str = "territory_only"
    home_territory: Optional[HomeTerritory] = None
    enclaves: list[Enclave] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    action_library: list[ActionTemplate] = field(default_factory=list)
    starting_actions: list[str] = field(default_factory=list)

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Get a goal by ID."""
        for g in self.goals:
            if g.id == goal_id:
                return g
        return None

    def get_action_template(self, action_id: str) -> Optional[ActionTemplate]:
        """Get an action template by ID."""
        for a in self.action_library:
            if a.action_id == action_id:
                return a
        return None

    def has_resource_tag(self, tag: str) -> bool:
        """Check if this faction has a resource with the given tag."""
        for r in self.resources:
            if tag in r.tags:
                return True
        return False


# =============================================================================
# RULES CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class FactionRules:
    """Rules configuration loaded from faction_rules.json."""
    schema_version: int
    turn_cadence_days: int = 7
    max_faction_level: int = 4
    actions_per_faction: int = 3
    die: str = "d6"
    roll_mod_cap: int = 1
    advance_on_4_5: int = 1
    advance_on_6_plus: int = 2
    complication_on_rolls: list[int] = field(default_factory=lambda: [1])
    default_segments_task: int = 4
    default_segments_mission: int = 8
    default_segments_goal: int = 12
    territory_points_to_level: dict[int, int] = field(
        default_factory=lambda: {1: 0, 2: 2, 3: 5, 4: 9}
    )
    actions_per_turn_by_level: dict[int, int] = field(
        default_factory=lambda: {1: 1, 2: 1, 3: 2, 4: 2}
    )
    territory_point_values: dict[str, int] = field(
        default_factory=lambda: {"hex": 1, "settlement": 2, "stronghold": 3, "domain": 4}
    )

    def get_default_segments(self, scope: str) -> int:
        """Get default segment count for a scope."""
        if scope == "task":
            return self.default_segments_task
        elif scope == "goal":
            return self.default_segments_goal
        else:  # mission, operation, diplomacy
            return self.default_segments_mission

    def get_level_for_points(self, points: int) -> int:
        """Compute faction level from territory points."""
        level = 1
        for lv in sorted(self.territory_points_to_level.keys()):
            threshold = self.territory_points_to_level[lv]
            if points >= threshold:
                level = lv
        return min(level, self.max_faction_level)


# =============================================================================
# DYNAMIC STATE (persisted in saves)
# =============================================================================


@dataclass
class ActionInstance:
    """An active action instance being worked on by a faction."""
    action_id: str
    goal_id: Optional[str]
    progress: int
    segments: int
    started_on: str  # ISO date string (e.g., "1-3-15" for Year 1, Month 3, Day 15)
    notes: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if this action has reached its segment target."""
        return self.progress >= self.segments

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "action_id": self.action_id,
            "goal_id": self.goal_id,
            "progress": self.progress,
            "segments": self.segments,
            "started_on": self.started_on,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionInstance":
        """Deserialize from dict."""
        return cls(
            action_id=d["action_id"],
            goal_id=d.get("goal_id"),
            progress=d.get("progress", 0),
            segments=d.get("segments", 8),
            started_on=d.get("started_on", ""),
            notes=d.get("notes", ""),
        )


@dataclass
class Territory:
    """Dynamic territory holdings for a faction."""
    hexes: set[str] = field(default_factory=set)
    settlements: set[str] = field(default_factory=set)
    strongholds: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    # Custom point values for non-standard holdings
    custom_points: dict[str, int] = field(default_factory=dict)

    def compute_points(self, point_values: dict[str, int]) -> int:
        """Compute total territory points."""
        total = 0
        total += len(self.hexes) * point_values.get("hex", 1)
        total += len(self.settlements) * point_values.get("settlement", 2)
        total += len(self.strongholds) * point_values.get("stronghold", 3)
        total += len(self.domains) * point_values.get("domain", 4)
        # Add custom points
        total += sum(self.custom_points.values())
        return total

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "hexes": sorted(self.hexes),
            "settlements": sorted(self.settlements),
            "strongholds": sorted(self.strongholds),
            "domains": sorted(self.domains),
            "custom_points": self.custom_points,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Territory":
        """Deserialize from dict."""
        return cls(
            hexes=set(d.get("hexes", [])),
            settlements=set(d.get("settlements", [])),
            strongholds=set(d.get("strongholds", [])),
            domains=set(d.get("domains", [])),
            custom_points=d.get("custom_points", {}),
        )

    @classmethod
    def from_home_territory(cls, ht: HomeTerritory) -> "Territory":
        """Create Territory from HomeTerritory definition."""
        territory = cls(
            hexes=set(ht.hexes),
            settlements=set(ht.settlements),
        )
        # Add strongholds and domains, storing custom points if specified
        for sh in ht.strongholds:
            if isinstance(sh, dict):
                sh_id = sh.get("id", "")
                territory.strongholds.add(sh_id)
                if "points" in sh and sh["points"] != 3:
                    territory.custom_points[sh_id] = sh["points"]
            else:
                territory.strongholds.add(str(sh))

        for dm in ht.domains:
            if isinstance(dm, dict):
                dm_id = dm.get("id", "")
                territory.domains.add(dm_id)
                if "points" in dm and dm["points"] != 4:
                    territory.custom_points[dm_id] = dm["points"]
            else:
                territory.domains.add(str(dm))

        return territory


@dataclass
class FactionLogEntry:
    """A log entry for faction activity."""
    date: str
    action_id: str
    roll: int
    modifier: int
    delta: int
    completed: bool
    effects_applied: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "date": self.date,
            "action_id": self.action_id,
            "roll": self.roll,
            "modifier": self.modifier,
            "delta": self.delta,
            "completed": self.completed,
            "effects_applied": self.effects_applied,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FactionLogEntry":
        """Deserialize from dict."""
        return cls(
            date=d.get("date", ""),
            action_id=d.get("action_id", ""),
            roll=d.get("roll", 0),
            modifier=d.get("modifier", 0),
            delta=d.get("delta", 0),
            completed=d.get("completed", False),
            effects_applied=d.get("effects_applied", []),
            notes=d.get("notes", ""),
        )


@dataclass
class FactionTurnState:
    """
    Dynamic state for a faction during play.

    Named FactionTurnState to avoid collision with data_models.FactionState.
    """
    faction_id: str
    territory: Territory = field(default_factory=Territory)
    active_actions: list[ActionInstance] = field(default_factory=list)  # Exactly 3
    modifiers_next_cycle: list[dict[str, Any]] = field(default_factory=list)
    log: list[FactionLogEntry] = field(default_factory=list)
    news: list[str] = field(default_factory=list)  # Recent news items

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "faction_id": self.faction_id,
            "territory": self.territory.to_dict(),
            "active_actions": [a.to_dict() for a in self.active_actions],
            "modifiers_next_cycle": self.modifiers_next_cycle,
            "log": [e.to_dict() for e in self.log],
            "news": self.news,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FactionTurnState":
        """Deserialize from dict."""
        return cls(
            faction_id=d["faction_id"],
            territory=Territory.from_dict(d.get("territory", {})),
            active_actions=[
                ActionInstance.from_dict(a) for a in d.get("active_actions", [])
            ],
            modifiers_next_cycle=d.get("modifiers_next_cycle", []),
            log=[FactionLogEntry.from_dict(e) for e in d.get("log", [])],
            news=d.get("news", []),
        )


# =============================================================================
# PARTY-FACING STATE
# =============================================================================


@dataclass
class PartyAffiliation:
    """Record of party affiliation with a faction or group."""
    faction_or_group: str
    kind: Literal["fealty", "oath", "working_relationship", "cult_blessing"] = "working_relationship"
    rank: int = 0
    since_date: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "faction_or_group": self.faction_or_group,
            "kind": self.kind,
            "rank": self.rank,
            "since_date": self.since_date,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PartyAffiliation":
        """Deserialize from dict."""
        return cls(
            faction_or_group=d["faction_or_group"],
            kind=d.get("kind", "working_relationship"),
            rank=d.get("rank", 0),
            since_date=d.get("since_date"),
        )


@dataclass
class ActiveJob:
    """An active job/quest the party has accepted from a faction."""
    job_id: str
    faction_id: str
    template_id: str
    title: str
    accepted_on: str
    status: Literal["active", "completed", "failed", "abandoned"] = "active"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "job_id": self.job_id,
            "faction_id": self.faction_id,
            "template_id": self.template_id,
            "title": self.title,
            "accepted_on": self.accepted_on,
            "status": self.status,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActiveJob":
        """Deserialize from dict."""
        return cls(
            job_id=d["job_id"],
            faction_id=d["faction_id"],
            template_id=d["template_id"],
            title=d["title"],
            accepted_on=d["accepted_on"],
            status=d.get("status", "active"),
            notes=d.get("notes", ""),
        )


@dataclass
class PartyFactionState:
    """
    Party's relationship state with all factions.

    Stores standing (reputation), affiliations, and active jobs.
    """
    standing_by_id: dict[str, int] = field(default_factory=dict)  # faction_id or group_id -> standing
    affiliations: list[PartyAffiliation] = field(default_factory=list)
    active_jobs: dict[str, ActiveJob] = field(default_factory=dict)  # job_id -> job
    completed_job_ids: list[str] = field(default_factory=list)

    def get_standing(self, faction_or_group: str) -> int:
        """Get party standing with a faction or group (default 0)."""
        return self.standing_by_id.get(faction_or_group, 0)

    def adjust_standing(self, faction_or_group: str, delta: int, *, clamp: tuple[int, int] = (-10, 10)) -> int:
        """
        Adjust standing with a faction or group.

        Returns the new standing value.
        """
        current = self.get_standing(faction_or_group)
        new_value = max(clamp[0], min(clamp[1], current + delta))
        self.standing_by_id[faction_or_group] = new_value
        return new_value

    def has_affiliation(self, faction_or_group: str) -> bool:
        """Check if party has any affiliation with a faction or group."""
        for aff in self.affiliations:
            if aff.faction_or_group == faction_or_group:
                return True
        return False

    def get_affiliation(self, faction_or_group: str) -> Optional[PartyAffiliation]:
        """Get party's affiliation with a faction or group."""
        for aff in self.affiliations:
            if aff.faction_or_group == faction_or_group:
                return aff
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "standing_by_id": self.standing_by_id,
            "affiliations": [a.to_dict() for a in self.affiliations],
            "active_jobs": {k: v.to_dict() for k, v in self.active_jobs.items()},
            "completed_job_ids": self.completed_job_ids,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PartyFactionState":
        """Deserialize from dict."""
        return cls(
            standing_by_id=d.get("standing_by_id", {}),
            affiliations=[
                PartyAffiliation.from_dict(a) for a in d.get("affiliations", [])
            ],
            active_jobs={
                k: ActiveJob.from_dict(v) for k, v in d.get("active_jobs", {}).items()
            },
            completed_job_ids=d.get("completed_job_ids", []),
        )


# =============================================================================
# RELATIONSHIP MODELS
# =============================================================================


@dataclass(frozen=True)
class Relation:
    """A relationship between two factions or groups."""
    a: str
    b: str
    score: int  # -100..100
    sentiment: str
    notes: str = ""


@dataclass(frozen=True)
class GroupRule:
    """A rule for matching factions to a group by tags."""
    group_id: str
    match_tags_any: list[str] = field(default_factory=list)
    description: str = ""


# =============================================================================
# ADVENTURER PROFILE MODELS
# =============================================================================


@dataclass(frozen=True)
class PCJoinPolicy:
    """Policy for PCs joining a faction."""
    allow_affiliation: bool = True
    fully_initiable: bool = False
    allowed_alignments: list[str] = field(default_factory=list)
    join_summary: str = ""


@dataclass(frozen=True)
class QuestEffect:
    """An effect applied when a quest is completed."""
    type: str  # "party_reputation", etc.
    faction: Optional[str] = None
    faction_group: Optional[str] = None
    delta: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "QuestEffect":
        """Create from dict."""
        return cls(
            type=d.get("type", "unknown"),
            faction=d.get("faction"),
            faction_group=d.get("faction_group"),
            delta=d.get("delta", 0),
        )


@dataclass(frozen=True)
class QuestTemplate:
    """A template for a faction quest/job."""
    id: str
    title: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    default_effects: list[QuestEffect] = field(default_factory=list)


@dataclass(frozen=True)
class AdventurerProfile:
    """Profile defining how a faction interacts with adventurers."""
    faction_or_group_id: str
    pc_join_policy: PCJoinPolicy = field(default_factory=PCJoinPolicy)
    rewards: list[str] = field(default_factory=list)
    quest_templates: list[QuestTemplate] = field(default_factory=list)
    trade: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    inherits_from: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    interaction_risk: Optional[dict[str, str]] = None
