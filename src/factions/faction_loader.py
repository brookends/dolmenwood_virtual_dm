"""
Faction definition loader for Dolmenwood Virtual DM.

Loads faction definitions and rules from JSON files in data/content/factions/.
Supports both index-based loading (factions_index.json) and glob-based fallback.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.factions.faction_models import (
    ActionTarget,
    ActionTemplate,
    EffectCommand,
    Enclave,
    FactionDefinition,
    FactionRules,
    Goal,
    HomeTerritory,
    Resource,
)

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Result of a loading operation."""
    success: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_resource(d: dict[str, Any]) -> Resource:
    """Parse a resource from JSON dict."""
    return Resource(
        id=d.get("id", ""),
        name=d.get("name", ""),
        tags=d.get("tags", []),
        description=d.get("description"),
    )


def _parse_goal(d: dict[str, Any]) -> Goal:
    """Parse a goal from JSON dict."""
    return Goal(
        id=d.get("id", ""),
        name=d.get("name", ""),
        description=d.get("description", ""),
        visibility=d.get("visibility", "landmark"),
        priority=d.get("priority", 0),
        default_scope=d.get("default_scope"),
        notes=d.get("notes"),
    )


def _parse_action_target(d: dict[str, Any]) -> ActionTarget:
    """Parse an action target from JSON dict."""
    return ActionTarget(
        type=d.get("type", ""),
        id=d.get("id", ""),
    )


def _parse_action_template(d: dict[str, Any]) -> ActionTemplate:
    """Parse an action template from JSON dict."""
    targets = [_parse_action_target(t) for t in d.get("targets", [])]
    on_complete = [EffectCommand.from_dict(e) for e in d.get("on_complete", [])]

    return ActionTemplate(
        action_id=d.get("id", d.get("action_id", "")),
        name=d.get("name", ""),
        scope=d.get("scope", "mission"),
        description=d.get("description", ""),
        goal_id=d.get("goal_id"),
        resource_tags=d.get("resource_tags", []),
        targets=targets,
        segments=d.get("segments"),
        on_complete=on_complete,
    )


def _parse_enclave(d: dict[str, Any]) -> Enclave:
    """Parse an enclave from JSON dict."""
    return Enclave(
        id=d.get("id", ""),
        name=d.get("name", ""),
        hex=d.get("hex", ""),
        type=d.get("type", ""),
        role=d.get("role", ""),
        status=d.get("status", "active"),
        summary=d.get("summary", ""),
    )


def _parse_home_territory(d: dict[str, Any]) -> HomeTerritory:
    """Parse home territory from JSON dict."""
    return HomeTerritory(
        hexes=d.get("hexes", []),
        settlements=d.get("settlements", []),
        strongholds=d.get("strongholds", []),
        domains=d.get("domains", []),
    )


def _parse_faction_definition(data: dict[str, Any]) -> FactionDefinition:
    """Parse a faction definition from JSON dict."""
    resources = [_parse_resource(r) for r in data.get("resources", [])]
    goals = [_parse_goal(g) for g in data.get("goals", [])]
    action_library = [_parse_action_template(a) for a in data.get("action_library", [])]
    enclaves = [_parse_enclave(e) for e in data.get("enclaves", [])]

    home_territory = None
    if "home_territory" in data:
        home_territory = _parse_home_territory(data["home_territory"])

    return FactionDefinition(
        faction_id=data.get("faction_id", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        alignment=data.get("alignment"),
        faction_type=data.get("type"),
        tags=data.get("tags", []),
        territory_model=data.get("territory_model", "territory_only"),
        home_territory=home_territory,
        enclaves=enclaves,
        resources=resources,
        goals=goals,
        action_library=action_library,
        starting_actions=data.get("starting_actions", []),
    )


class FactionLoader:
    """
    Loads faction definitions and rules from JSON files.

    Supports:
    - Index-based loading via factions_index.json
    - Glob-based fallback when index is missing or incomplete
    - Tolerant filename matching (nag_lord.json vs faction_nag_lord_atanuwe.json)
    """

    def __init__(self, content_root: Path):
        """
        Initialize the loader.

        Args:
            content_root: Path to the content directory (e.g., data/content)
        """
        self.content_root = Path(content_root)
        self.factions_dir = self.content_root / "factions"
        self._rules: Optional[FactionRules] = None
        self._definitions: dict[str, FactionDefinition] = {}
        self._load_result: Optional[LoadResult] = None

    @property
    def rules(self) -> Optional[FactionRules]:
        """Get loaded rules (call load_rules first)."""
        return self._rules

    @property
    def definitions(self) -> dict[str, FactionDefinition]:
        """Get loaded definitions (call load_definitions first)."""
        return self._definitions

    @property
    def load_result(self) -> Optional[LoadResult]:
        """Get the result of the last load operation."""
        return self._load_result

    def load_rules(self) -> FactionRules:
        """
        Load faction rules from faction_rules.json.

        Returns:
            FactionRules instance with defaults if file not found.
        """
        rules_path = self.factions_dir / "faction_rules.json"
        if not rules_path.exists():
            logger.warning(f"Faction rules not found at {rules_path}, using defaults")
            self._rules = FactionRules(schema_version=1)
            return self._rules

        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse progression rules
            advance_on = data.get("progression", {}).get("advance_on_roll", {})
            advance_4_5 = advance_on.get("4-5", 1)
            advance_6_plus = advance_on.get("6+", 2)

            complication_rolls = data.get("progression", {}).get("complication_on_roll", [1])

            # Parse default segments
            default_segments = data.get("default_progress_segments", {})

            # Parse leveling
            leveling = data.get("leveling", {})
            tp_to_level_raw = leveling.get("territory_points_to_level", {})
            # Convert string keys to int
            tp_to_level = {int(k): v for k, v in tp_to_level_raw.items()}

            actions_by_level_raw = leveling.get("actions_per_turn_by_level", {})
            actions_by_level = {int(k): v for k, v in actions_by_level_raw.items()}

            self._rules = FactionRules(
                schema_version=data.get("schema_version", 1),
                turn_cadence_days=data.get("turn_cadence_days", 7),
                max_faction_level=data.get("max_faction_level", 4),
                actions_per_faction=data.get("actions_per_faction", 3),
                die=data.get("die", "d6"),
                roll_mod_cap=data.get("roll_mod_cap", 1),
                advance_on_4_5=advance_4_5,
                advance_on_6_plus=advance_6_plus,
                complication_on_rolls=complication_rolls,
                default_segments_task=default_segments.get("task", 4),
                default_segments_mission=default_segments.get("mission", 8),
                default_segments_goal=default_segments.get("goal", 12),
                territory_points_to_level=tp_to_level if tp_to_level else {1: 0, 2: 2, 3: 5, 4: 9},
                actions_per_turn_by_level=actions_by_level if actions_by_level else {1: 1, 2: 1, 3: 2, 4: 2},
                territory_point_values=data.get("territory_points", {"hex": 1, "settlement": 2, "stronghold": 3, "domain": 4}),
            )
            return self._rules

        except Exception as e:
            logger.error(f"Error loading faction rules: {e}")
            self._rules = FactionRules(schema_version=1)
            return self._rules

    def load_definitions(self) -> dict[str, FactionDefinition]:
        """
        Load all faction definitions.

        Tries index-based loading first, falls back to glob.

        Returns:
            Dict of faction_id -> FactionDefinition
        """
        result = LoadResult(success=True)
        self._definitions = {}

        if not self.factions_dir.exists():
            result.success = False
            result.errors.append(f"Factions directory not found: {self.factions_dir}")
            self._load_result = result
            return self._definitions

        # Try to load via index
        index_path = self.factions_dir / "factions_index.json"
        loaded_from_index = set()

        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)

                for entry in index_data.get("factions", []):
                    faction_id = entry.get("faction_id", "")
                    filename = entry.get("file", "")

                    if not faction_id or not filename:
                        result.warnings.append(f"Index entry missing faction_id or file: {entry}")
                        continue

                    # Try exact filename first
                    file_path = self.factions_dir / filename
                    if not file_path.exists():
                        # Try with faction_ prefix
                        prefixed_name = f"faction_{filename}"
                        file_path = self.factions_dir / prefixed_name
                    if not file_path.exists():
                        # Try faction_<faction_id>.json
                        alt_name = f"faction_{faction_id}.json"
                        file_path = self.factions_dir / alt_name

                    if file_path.exists():
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            definition = _parse_faction_definition(data)
                            self._definitions[definition.faction_id] = definition
                            loaded_from_index.add(file_path.name)
                        except Exception as e:
                            result.warnings.append(f"Error loading {file_path}: {e}")
                    else:
                        result.warnings.append(f"Faction file not found for {faction_id}: tried {filename}")

            except Exception as e:
                result.warnings.append(f"Error reading index file: {e}")

        # Glob for any faction files not loaded via index
        for json_file in self.factions_dir.glob("*.json"):
            if json_file.name in loaded_from_index:
                continue

            # Skip non-faction files
            if json_file.name in (
                "faction_rules.json",
                "factions_index.json",
                "faction.schema.json",
                "faction_relationships.json",
                "faction_adventurer_profiles.json",
            ):
                continue

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Only load if it has a faction_id field
                if "faction_id" in data:
                    definition = _parse_faction_definition(data)
                    if definition.faction_id not in self._definitions:
                        self._definitions[definition.faction_id] = definition

            except Exception as e:
                result.warnings.append(f"Error loading {json_file}: {e}")

        if not self._definitions:
            result.warnings.append("No faction definitions loaded")

        self._load_result = result
        return self._definitions

    def load_all(self) -> LoadResult:
        """
        Load rules and all definitions.

        Returns:
            LoadResult with success status and any errors/warnings.
        """
        result = LoadResult(success=True)

        try:
            self.load_rules()
        except Exception as e:
            result.errors.append(f"Failed to load rules: {e}")
            result.success = False

        try:
            self.load_definitions()
            if self._load_result:
                result.warnings.extend(self._load_result.warnings)
                result.errors.extend(self._load_result.errors)
        except Exception as e:
            result.errors.append(f"Failed to load definitions: {e}")
            result.success = False

        self._load_result = result
        return result

    def get_definition(self, faction_id: str) -> Optional[FactionDefinition]:
        """Get a faction definition by ID."""
        return self._definitions.get(faction_id)

    def list_faction_ids(self) -> list[str]:
        """List all loaded faction IDs."""
        return list(self._definitions.keys())

    def validate_definitions(self) -> list[str]:
        """
        Validate loaded definitions for required fields.

        Returns:
            List of validation error messages.
        """
        errors = []
        for faction_id, defn in self._definitions.items():
            if not defn.faction_id:
                errors.append(f"Faction missing faction_id")
            if not defn.name:
                errors.append(f"Faction {faction_id} missing name")
            # Validate action references
            for action_id in defn.starting_actions:
                if not defn.get_action_template(action_id):
                    errors.append(
                        f"Faction {faction_id} starting_action '{action_id}' "
                        f"not found in action_library"
                    )
        return errors
