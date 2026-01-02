"""
Faction adventurer profiles loader.

Loads adventurer interaction profiles from faction_adventurer_profiles.json.
Supports:
- Per-faction profiles defining join policies, rewards, quest templates
- Profile inheritance (e.g., house_brackenwold inherits from human_nobility)
- Quest template loading with deterministic effect definitions
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.factions.faction_models import (
    AdventurerProfile,
    PCJoinPolicy,
    QuestEffect,
    QuestTemplate,
)

logger = logging.getLogger(__name__)


@dataclass
class ProfilesLoadResult:
    """Result of loading adventurer profiles."""
    success: bool
    profile_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_pc_join_policy(data: dict[str, Any]) -> PCJoinPolicy:
    """Parse PC join policy from JSON."""
    return PCJoinPolicy(
        allow_affiliation=data.get("allow_affiliation", True),
        fully_initiable=data.get("fully_initiable", False),
        allowed_alignments=data.get("allowed_alignments", []),
        join_summary=data.get("join_summary", ""),
    )


def _parse_quest_effect(data: dict[str, Any]) -> QuestEffect:
    """Parse a quest effect from JSON."""
    return QuestEffect.from_dict(data)


def _parse_quest_template(data: dict[str, Any]) -> QuestTemplate:
    """Parse a quest template from JSON."""
    effects = [_parse_quest_effect(e) for e in data.get("default_effects", [])]

    return QuestTemplate(
        id=data.get("id", ""),
        title=data.get("title", ""),
        tags=data.get("tags", []),
        summary=data.get("summary", ""),
        default_effects=effects,
    )


def _parse_profile(faction_or_group_id: str, data: dict[str, Any]) -> AdventurerProfile:
    """Parse an adventurer profile from JSON."""
    pc_join_policy = PCJoinPolicy()
    if "pc_join_policy" in data:
        pc_join_policy = _parse_pc_join_policy(data["pc_join_policy"])

    quest_templates = [
        _parse_quest_template(t) for t in data.get("quest_templates", [])
    ]

    return AdventurerProfile(
        faction_or_group_id=faction_or_group_id,
        pc_join_policy=pc_join_policy,
        rewards=data.get("rewards", []),
        quest_templates=quest_templates,
        trade=data.get("trade", []),
        warnings=data.get("warnings", []),
        services=data.get("services", []),
        inherits_from=data.get("inherits_from"),
        notes=data.get("notes", []),
        interaction_risk=data.get("interaction_risk"),
    )


class FactionAdventurerProfiles:
    """
    Manages faction adventurer interaction profiles.

    Supports:
    - Profile lookup by faction or group ID
    - Profile inheritance resolution
    - Quest template listing and lookup
    """

    def __init__(self, profiles: dict[str, AdventurerProfile]):
        """
        Initialize with loaded profiles.

        Args:
            profiles: Dict of faction_or_group_id -> AdventurerProfile
        """
        self._profiles = profiles
        self._resolved_cache: dict[str, AdventurerProfile] = {}

    @property
    def profiles(self) -> dict[str, AdventurerProfile]:
        """Get all profiles."""
        return self._profiles

    def get_profile(self, faction_or_group_id: str) -> Optional[AdventurerProfile]:
        """
        Get a profile by faction or group ID.

        If the profile inherits from another, returns the resolved profile
        with inherited values filled in.

        Args:
            faction_or_group_id: The faction or group ID

        Returns:
            AdventurerProfile or None if not found
        """
        if faction_or_group_id not in self._profiles:
            return None

        # Check cache first
        if faction_or_group_id in self._resolved_cache:
            return self._resolved_cache[faction_or_group_id]

        profile = self._profiles[faction_or_group_id]

        # If no inheritance, return as-is
        if not profile.inherits_from:
            self._resolved_cache[faction_or_group_id] = profile
            return profile

        # Resolve inheritance
        parent = self.get_profile(profile.inherits_from)
        if not parent:
            logger.warning(
                f"Profile {faction_or_group_id} inherits from "
                f"unknown profile {profile.inherits_from}"
            )
            self._resolved_cache[faction_or_group_id] = profile
            return profile

        # Merge: child values override parent, lists are combined
        resolved = AdventurerProfile(
            faction_or_group_id=profile.faction_or_group_id,
            pc_join_policy=profile.pc_join_policy if profile.pc_join_policy.allowed_alignments else parent.pc_join_policy,
            rewards=profile.rewards if profile.rewards else parent.rewards,
            quest_templates=profile.quest_templates if profile.quest_templates else parent.quest_templates,
            trade=profile.trade if profile.trade else parent.trade,
            warnings=profile.warnings + parent.warnings,
            services=profile.services if profile.services else parent.services,
            inherits_from=profile.inherits_from,
            notes=profile.notes + parent.notes,
            interaction_risk=profile.interaction_risk or parent.interaction_risk,
        )

        self._resolved_cache[faction_or_group_id] = resolved
        return resolved

    def list_faction_ids(self) -> list[str]:
        """List all faction/group IDs with profiles."""
        return list(self._profiles.keys())

    def list_quest_templates(
        self,
        faction_or_group_id: str,
    ) -> list[QuestTemplate]:
        """
        List quest templates for a faction or group.

        Args:
            faction_or_group_id: The faction or group ID

        Returns:
            List of QuestTemplate objects
        """
        profile = self.get_profile(faction_or_group_id)
        if not profile:
            return []
        return list(profile.quest_templates)

    def get_quest_template(
        self,
        faction_or_group_id: str,
        template_id: str,
    ) -> Optional[QuestTemplate]:
        """
        Get a specific quest template.

        Args:
            faction_or_group_id: The faction or group ID
            template_id: The quest template ID

        Returns:
            QuestTemplate or None
        """
        templates = self.list_quest_templates(faction_or_group_id)
        for t in templates:
            if t.id == template_id:
                return t
        return None

    def can_affiliate(
        self,
        faction_or_group_id: str,
        alignment: Optional[str] = None,
    ) -> bool:
        """
        Check if adventurers can affiliate with a faction.

        Args:
            faction_or_group_id: The faction or group ID
            alignment: Optional alignment to check

        Returns:
            True if affiliation is allowed
        """
        profile = self.get_profile(faction_or_group_id)
        if not profile:
            return False

        if not profile.pc_join_policy.allow_affiliation:
            return False

        if alignment and profile.pc_join_policy.allowed_alignments:
            return alignment in profile.pc_join_policy.allowed_alignments

        return True

    def is_fully_initiable(self, faction_or_group_id: str) -> bool:
        """
        Check if adventurers can be fully initiated into a faction.

        Some factions (Drune, Witches) allow working relationships
        but not full PC membership.

        Args:
            faction_or_group_id: The faction or group ID

        Returns:
            True if full initiation is possible
        """
        profile = self.get_profile(faction_or_group_id)
        if not profile:
            return False
        return profile.pc_join_policy.fully_initiable


class FactionAdventurerProfilesLoader:
    """
    Loads adventurer profiles from faction_adventurer_profiles.json.
    """

    def __init__(self, content_root: Path):
        """
        Initialize the loader.

        Args:
            content_root: Path to the content directory
        """
        self.content_root = Path(content_root)
        self.factions_dir = self.content_root / "factions"
        self._profiles: Optional[FactionAdventurerProfiles] = None
        self._load_result: Optional[ProfilesLoadResult] = None

    @property
    def profiles(self) -> Optional[FactionAdventurerProfiles]:
        """Get loaded profiles (call load first)."""
        return self._profiles

    @property
    def load_result(self) -> Optional[ProfilesLoadResult]:
        """Get the result of the last load operation."""
        return self._load_result

    def load(self) -> FactionAdventurerProfiles:
        """
        Load adventurer profiles from JSON.

        Returns:
            FactionAdventurerProfiles instance
        """
        result = ProfilesLoadResult(success=True)
        profiles: dict[str, AdventurerProfile] = {}

        profiles_path = self.factions_dir / "faction_adventurer_profiles.json"

        if not profiles_path.exists():
            result.success = False
            result.errors.append(f"Profiles file not found: {profiles_path}")
            self._load_result = result
            self._profiles = FactionAdventurerProfiles({})
            return self._profiles

        try:
            with open(profiles_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate schema version
            schema_version = data.get("schema_version", 1)
            if schema_version != 1:
                result.warnings.append(f"Unknown schema_version: {schema_version}")

            # Parse profiles
            profiles_data = data.get("profiles", {})
            for faction_or_group_id, profile_data in profiles_data.items():
                profile = _parse_profile(faction_or_group_id, profile_data)
                profiles[faction_or_group_id] = profile

            result.profile_count = len(profiles)

        except json.JSONDecodeError as e:
            result.success = False
            result.errors.append(f"JSON parse error: {e}")
        except Exception as e:
            result.success = False
            result.errors.append(f"Error loading profiles: {e}")

        self._load_result = result
        self._profiles = FactionAdventurerProfiles(profiles)
        return self._profiles

    def validate(self) -> list[str]:
        """
        Validate loaded profiles.

        Returns:
            List of validation warnings
        """
        warnings = []

        if not self._profiles:
            return ["Profiles not loaded"]

        for faction_id, profile in self._profiles.profiles.items():
            # Check inheritance references
            if profile.inherits_from:
                if profile.inherits_from not in self._profiles.profiles:
                    warnings.append(
                        f"Profile {faction_id} inherits from "
                        f"unknown profile {profile.inherits_from}"
                    )

            # Check quest template IDs are unique
            seen_ids = set()
            for template in profile.quest_templates:
                if template.id in seen_ids:
                    warnings.append(
                        f"Duplicate quest template ID {template.id} in {faction_id}"
                    )
                seen_ids.add(template.id)

        return warnings
