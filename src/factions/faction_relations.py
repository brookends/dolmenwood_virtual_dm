"""
Faction relationship matrix loader and resolver.

Loads and resolves inter-faction relationships from faction_relationships.json.
Supports:
- Direct faction-to-faction relationships
- Group-based relationships (e.g., "human_nobility" applies to all matching factions)
- Score lookup with fallback (exact pair > group pair > default 0)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.factions.faction_models import (
    FactionDefinition,
    GroupRule,
    Relation,
)

logger = logging.getLogger(__name__)


@dataclass
class RelationsLoadResult:
    """Result of loading relationships."""
    success: bool
    relation_count: int = 0
    group_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class FactionRelations:
    """
    Manages inter-faction relationships.

    Supports:
    - Direct faction pairs (e.g., "drune" <-> "pluritine_church")
    - Group rules (e.g., "human_nobility" matches factions with that tag)
    - Score resolution with priority: exact pair > group pair > default 0
    """

    def __init__(
        self,
        relations: list[Relation],
        groups: dict[str, GroupRule],
        faction_defs: Optional[dict[str, FactionDefinition]] = None,
    ):
        """
        Initialize the relations manager.

        Args:
            relations: List of Relation objects (pairwise relationships)
            groups: Dict of group_id -> GroupRule
            faction_defs: Optional dict of faction definitions for tag matching
        """
        self._relations = relations
        self._groups = groups
        self._faction_defs = faction_defs or {}

        # Build lookup indices
        self._pair_index: dict[tuple[str, str], Relation] = {}
        for rel in relations:
            # Store both directions for symmetric lookup
            self._pair_index[(rel.a, rel.b)] = rel
            self._pair_index[(rel.b, rel.a)] = rel

        # Build reverse index: tag -> group_ids
        self._tag_to_groups: dict[str, set[str]] = {}
        for group_id, rule in groups.items():
            for tag in rule.match_tags_any:
                if tag not in self._tag_to_groups:
                    self._tag_to_groups[tag] = set()
                self._tag_to_groups[tag].add(group_id)

    @property
    def relations(self) -> list[Relation]:
        """Get all relations."""
        return self._relations

    @property
    def groups(self) -> dict[str, GroupRule]:
        """Get all group rules."""
        return self._groups

    def set_faction_defs(self, faction_defs: dict[str, FactionDefinition]) -> None:
        """Set faction definitions for tag matching."""
        self._faction_defs = faction_defs

    def resolve_ids(self, faction_id: str) -> list[str]:
        """
        Resolve a faction ID to a list of applicable IDs.

        Returns [faction_id] + any group_ids matched by the faction's tags.

        Args:
            faction_id: The faction ID to resolve

        Returns:
            List starting with the faction_id, followed by matching group_ids
        """
        result = [faction_id]

        # If it's already a group, just return it
        if faction_id in self._groups:
            return result

        # Get faction definition to check tags
        faction_def = self._faction_defs.get(faction_id)
        if faction_def:
            # Find all groups this faction belongs to
            matched_groups = set()
            for tag in faction_def.tags:
                if tag in self._tag_to_groups:
                    matched_groups.update(self._tag_to_groups[tag])
            result.extend(sorted(matched_groups))

        return result

    def get_score(self, a_id: str, b_id: str) -> int:
        """
        Get the relationship score between two factions or groups.

        Resolution order:
        1. Exact faction pair
        2. Faction-to-group pair
        3. Group-to-group pair
        4. Default 0 (neutral)

        Args:
            a_id: First faction or group ID
            b_id: Second faction or group ID

        Returns:
            Relationship score (-100 to 100)
        """
        rel = self.get_relation(a_id, b_id)
        return rel.score if rel else 0

    def get_sentiment(self, a_id: str, b_id: str) -> str:
        """
        Get the relationship sentiment between two factions or groups.

        Args:
            a_id: First faction or group ID
            b_id: Second faction or group ID

        Returns:
            Sentiment string (e.g., "allied", "hate", "neutral")
        """
        rel = self.get_relation(a_id, b_id)
        return rel.sentiment if rel else "neutral"

    def get_relation(self, a_id: str, b_id: str) -> Optional[Relation]:
        """
        Get the relationship between two factions or groups.

        Tries exact match first, then expands to group matches.

        Args:
            a_id: First faction or group ID
            b_id: Second faction or group ID

        Returns:
            Relation object or None if no relationship found
        """
        # 1. Try exact pair lookup
        if (a_id, b_id) in self._pair_index:
            return self._pair_index[(a_id, b_id)]

        # 2. Expand both IDs to include group matches
        a_ids = self.resolve_ids(a_id)
        b_ids = self.resolve_ids(b_id)

        # 3. Search for any pair among expanded sets
        # Prioritize: exact faction > faction-group > group-group
        best_rel: Optional[Relation] = None
        best_priority = -1

        for i, a in enumerate(a_ids):
            for j, b in enumerate(b_ids):
                if (a, b) in self._pair_index:
                    rel = self._pair_index[(a, b)]
                    # Priority: lower i and j means more specific match
                    priority = 100 - i - j
                    if abs(rel.score) > 0:  # Prefer non-zero scores
                        priority += 10
                    if priority > best_priority:
                        best_priority = priority
                        best_rel = rel

        return best_rel

    def get_all_relations_for(self, faction_id: str) -> list[Relation]:
        """
        Get all relations involving a faction (directly or via groups).

        Args:
            faction_id: The faction ID

        Returns:
            List of Relation objects
        """
        ids = self.resolve_ids(faction_id)
        result = []
        seen = set()

        for fid in ids:
            for (a, b), rel in self._pair_index.items():
                if a == fid and rel not in seen:
                    result.append(rel)
                    seen.add(rel)

        return result

    def is_hostile(self, a_id: str, b_id: str, threshold: int = -25) -> bool:
        """Check if two factions are hostile (score below threshold)."""
        return self.get_score(a_id, b_id) <= threshold

    def is_friendly(self, a_id: str, b_id: str, threshold: int = 25) -> bool:
        """Check if two factions are friendly (score above threshold)."""
        return self.get_score(a_id, b_id) >= threshold


def _parse_group_rule(group_id: str, data: dict[str, Any]) -> GroupRule:
    """Parse a group rule from JSON."""
    return GroupRule(
        group_id=group_id,
        match_tags_any=data.get("match_tags_any", []),
        description=data.get("description", ""),
    )


def _parse_relation(data: dict[str, Any]) -> Relation:
    """Parse a relation from JSON."""
    return Relation(
        a=data.get("a", ""),
        b=data.get("b", ""),
        score=data.get("score", 0),
        sentiment=data.get("sentiment", "neutral"),
        notes=data.get("notes", ""),
    )


class FactionRelationsLoader:
    """
    Loads faction relationships from faction_relationships.json.
    """

    def __init__(self, content_root: Path):
        """
        Initialize the loader.

        Args:
            content_root: Path to the content directory
        """
        self.content_root = Path(content_root)
        self.factions_dir = self.content_root / "factions"
        self._relations: Optional[FactionRelations] = None
        self._load_result: Optional[RelationsLoadResult] = None

    @property
    def relations(self) -> Optional[FactionRelations]:
        """Get loaded relations (call load first)."""
        return self._relations

    @property
    def load_result(self) -> Optional[RelationsLoadResult]:
        """Get the result of the last load operation."""
        return self._load_result

    def load(
        self,
        faction_defs: Optional[dict[str, FactionDefinition]] = None,
    ) -> FactionRelations:
        """
        Load relationships from faction_relationships.json.

        Args:
            faction_defs: Optional faction definitions for tag matching

        Returns:
            FactionRelations instance
        """
        result = RelationsLoadResult(success=True)
        relations: list[Relation] = []
        groups: dict[str, GroupRule] = {}

        rel_path = self.factions_dir / "faction_relationships.json"

        if not rel_path.exists():
            result.success = False
            result.errors.append(f"Relationships file not found: {rel_path}")
            self._load_result = result
            self._relations = FactionRelations([], {}, faction_defs)
            return self._relations

        try:
            with open(rel_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate schema version
            schema_version = data.get("schema_version", 1)
            if schema_version != 1:
                result.warnings.append(f"Unknown schema_version: {schema_version}")

            # Parse groups
            groups_data = data.get("groups", {})
            for group_id, group_data in groups_data.items():
                groups[group_id] = _parse_group_rule(group_id, group_data)

            result.group_count = len(groups)

            # Parse pairs
            pairs_data = data.get("pairs", [])
            for pair_data in pairs_data:
                rel = _parse_relation(pair_data)

                # Validate score range
                score_range = data.get("score_range", [-100, 100])
                if rel.score < score_range[0] or rel.score > score_range[1]:
                    result.warnings.append(
                        f"Score {rel.score} for {rel.a}-{rel.b} outside range {score_range}"
                    )

                relations.append(rel)

            result.relation_count = len(relations)

        except json.JSONDecodeError as e:
            result.success = False
            result.errors.append(f"JSON parse error: {e}")
        except Exception as e:
            result.success = False
            result.errors.append(f"Error loading relationships: {e}")

        self._load_result = result
        self._relations = FactionRelations(relations, groups, faction_defs)
        return self._relations

    def validate(self, faction_defs: dict[str, FactionDefinition]) -> list[str]:
        """
        Validate relationships against loaded faction definitions.

        Returns:
            List of validation warnings
        """
        warnings = []

        if not self._relations:
            return ["Relations not loaded"]

        known_ids = set(faction_defs.keys())
        known_groups = set(self._relations.groups.keys())
        all_known = known_ids | known_groups

        for rel in self._relations.relations:
            if rel.a not in all_known:
                warnings.append(f"Unknown faction/group in relation: {rel.a}")
            if rel.b not in all_known:
                warnings.append(f"Unknown faction/group in relation: {rel.b}")

        return warnings
