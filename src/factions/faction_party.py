"""
Party-faction interaction layer.

Bridges the FactionEngine and DowntimeEngine to provide:
- Faction job acceptance and tracking
- Standing adjustments based on actions
- Quest completion rewards

This module integrates with the existing DowntimeEngine.faction_work
while adding support for the global faction system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from src.data_models import DiceRoller

if TYPE_CHECKING:
    from src.factions.faction_engine import FactionEngine
    from src.factions.faction_adventurers import FactionAdventurerProfiles
    from src.factions.faction_relations import FactionRelations

from src.factions.faction_models import (
    ActiveJob,
    PartyAffiliation,
    PartyFactionState,
    QuestTemplate,
)

logger = logging.getLogger(__name__)


@dataclass
class FactionWorkResult:
    """Result of faction work during downtime."""
    success: bool
    faction_id: str
    job_id: Optional[str] = None
    standing_before: int = 0
    standing_after: int = 0
    standing_delta: int = 0
    rewards: list[str] = None
    message: str = ""
    roll_total: int = 0  # The 2d6 roll total
    oracle_twist: Optional[Any] = None  # OracleEvent for extreme rolls

    def __post_init__(self):
        if self.rewards is None:
            self.rewards = []


@dataclass
class JobCompletionResult:
    """Result of completing a faction job."""
    success: bool
    job_id: str
    faction_id: str
    standing_delta: int = 0
    rewards: list[str] = None
    effects_applied: list[str] = None
    message: str = ""

    def __post_init__(self):
        if self.rewards is None:
            self.rewards = []
        if self.effects_applied is None:
            self.effects_applied = []


class FactionPartyManager:
    """
    Manages party-faction interactions.

    Provides methods for:
    - Accepting and tracking faction jobs
    - Performing faction work during downtime
    - Adjusting standing based on actions
    - Checking affiliation requirements
    """

    def __init__(
        self,
        engine: "FactionEngine",
        profiles: Optional["FactionAdventurerProfiles"] = None,
    ):
        """
        Initialize the party manager.

        Args:
            engine: The FactionEngine instance
            profiles: Optional adventurer profiles for job templates
        """
        self._engine = engine
        self._profiles = profiles

    @property
    def party_state(self) -> PartyFactionState:
        """Get the party faction state."""
        if not self._engine.party_state:
            self._engine.set_party_state(PartyFactionState())
        return self._engine.party_state

    # =========================================================================
    # STANDING MANAGEMENT
    # =========================================================================

    def get_standing(self, faction_id: str) -> int:
        """Get party standing with a faction."""
        return self.party_state.get_standing(faction_id)

    def adjust_standing(
        self,
        faction_id: str,
        delta: int,
        reason: str = "",
    ) -> tuple[int, int]:
        """
        Adjust party standing with a faction.

        Args:
            faction_id: The faction ID
            delta: Change in standing
            reason: Reason for adjustment (for logging)

        Returns:
            Tuple of (old_standing, new_standing)
        """
        old_standing = self.party_state.get_standing(faction_id)
        new_standing = self.party_state.adjust_standing(faction_id, delta)

        if reason:
            logger.info(
                f"Standing with {faction_id}: {old_standing} -> {new_standing} ({reason})"
            )

        return old_standing, new_standing

    def get_standing_label(self, standing: int) -> str:
        """Get a human-readable label for standing value."""
        if standing >= 8:
            return "Allied"
        elif standing >= 5:
            return "Friendly"
        elif standing >= 2:
            return "Favorable"
        elif standing >= -1:
            return "Neutral"
        elif standing >= -4:
            return "Unfavorable"
        elif standing >= -7:
            return "Hostile"
        else:
            return "Enemy"

    # =========================================================================
    # AFFILIATION MANAGEMENT
    # =========================================================================

    def can_affiliate(
        self,
        faction_id: str,
        alignment: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Check if party can affiliate with a faction.

        Args:
            faction_id: The faction ID
            alignment: Optional party alignment to check

        Returns:
            Tuple of (can_affiliate, reason)
        """
        if not self._profiles:
            return True, "No profile restrictions"

        if not self._profiles.can_affiliate(faction_id, alignment):
            return False, "Alignment or policy restrictions"

        return True, "Affiliation allowed"

    def create_affiliation(
        self,
        faction_id: str,
        kind: str = "working_relationship",
        current_date: str = "",
    ) -> PartyAffiliation:
        """
        Create an affiliation with a faction.

        Args:
            faction_id: The faction ID
            kind: Type of affiliation
            current_date: Current game date

        Returns:
            The created PartyAffiliation
        """
        affiliation = PartyAffiliation(
            faction_or_group=faction_id,
            kind=kind,
            rank=0,
            since_date=current_date,
        )
        self.party_state.affiliations.append(affiliation)
        return affiliation

    def has_affiliation(self, faction_id: str) -> bool:
        """Check if party has any affiliation with a faction."""
        return self.party_state.has_affiliation(faction_id)

    def get_affiliation(self, faction_id: str) -> Optional[PartyAffiliation]:
        """Get party's affiliation with a faction."""
        return self.party_state.get_affiliation(faction_id)

    def advance_affiliation_rank(self, faction_id: str) -> Optional[PartyAffiliation]:
        """
        Advance rank in an affiliation.

        Args:
            faction_id: The faction ID

        Returns:
            Updated PartyAffiliation or None if not affiliated
        """
        affiliation = self.get_affiliation(faction_id)
        if affiliation:
            affiliation.rank += 1
        return affiliation

    # =========================================================================
    # JOB MANAGEMENT
    # =========================================================================

    def list_available_jobs(
        self,
        faction_id: str,
    ) -> list[QuestTemplate]:
        """
        List available jobs from a faction.

        Args:
            faction_id: The faction ID

        Returns:
            List of available quest templates
        """
        if not self._profiles:
            return []

        return self._profiles.list_quest_templates(faction_id)

    def accept_job(
        self,
        faction_id: str,
        template_id: str,
        current_date: str = "",
    ) -> Optional[ActiveJob]:
        """
        Accept a job from a faction.

        Args:
            faction_id: The faction ID
            template_id: The quest template ID
            current_date: Current game date

        Returns:
            ActiveJob if accepted, None if template not found
        """
        if not self._profiles:
            logger.warning("No profiles available for job acceptance")
            return None

        template = self._profiles.get_quest_template(faction_id, template_id)
        if not template:
            logger.warning(f"Quest template {template_id} not found for {faction_id}")
            return None

        # Generate unique job ID
        dice = DiceRoller()
        job_id = f"{faction_id}_{template_id}_{dice.randint(1000, 9999, 'job_id')}"

        job = ActiveJob(
            job_id=job_id,
            faction_id=faction_id,
            template_id=template_id,
            title=template.title,
            accepted_on=current_date,
            status="active",
        )

        self.party_state.active_jobs[job_id] = job
        return job

    def complete_job(
        self,
        job_id: str,
        success: bool = True,
    ) -> JobCompletionResult:
        """
        Complete or fail a job.

        Args:
            job_id: The job ID
            success: Whether the job was successful

        Returns:
            JobCompletionResult with effects applied
        """
        job = self.party_state.active_jobs.get(job_id)
        if not job:
            return JobCompletionResult(
                success=False,
                job_id=job_id,
                faction_id="",
                message="Job not found",
            )

        result = JobCompletionResult(
            success=success,
            job_id=job_id,
            faction_id=job.faction_id,
        )

        # Update job status
        job.status = "completed" if success else "failed"

        # Apply standing change
        if success:
            delta = 1  # Base standing gain
            _, new_standing = self.adjust_standing(
                job.faction_id, delta, f"Completed job: {job.title}"
            )
            result.standing_delta = delta
            result.message = f"Job completed! Standing improved to {new_standing}"
        else:
            delta = -1  # Standing penalty for failure
            _, new_standing = self.adjust_standing(
                job.faction_id, delta, f"Failed job: {job.title}"
            )
            result.standing_delta = delta
            result.message = f"Job failed. Standing reduced to {new_standing}"

        # Apply quest effects if available
        if self._profiles and success:
            template = self._profiles.get_quest_template(job.faction_id, job.template_id)
            if template and template.default_effects:
                for effect in template.default_effects:
                    if effect.type == "party_reputation":
                        target = effect.faction or effect.faction_group or job.faction_id
                        self.adjust_standing(
                            target, effect.delta, f"Quest effect: {effect.type}"
                        )
                        result.effects_applied.append(
                            f"Standing with {target} adjusted by {effect.delta}"
                        )

        # Move to completed list
        self.party_state.completed_job_ids.append(job_id)
        del self.party_state.active_jobs[job_id]

        return result

    def abandon_job(self, job_id: str) -> bool:
        """
        Abandon an active job.

        Args:
            job_id: The job ID

        Returns:
            True if job was abandoned
        """
        job = self.party_state.active_jobs.get(job_id)
        if not job:
            return False

        job.status = "abandoned"

        # Small standing penalty for abandonment
        self.adjust_standing(job.faction_id, -1, f"Abandoned job: {job.title}")

        del self.party_state.active_jobs[job_id]
        return True

    def get_active_jobs(self, faction_id: Optional[str] = None) -> list[ActiveJob]:
        """
        Get active jobs, optionally filtered by faction.

        Args:
            faction_id: Optional faction filter

        Returns:
            List of active jobs
        """
        jobs = list(self.party_state.active_jobs.values())
        if faction_id:
            jobs = [j for j in jobs if j.faction_id == faction_id]
        return jobs

    # =========================================================================
    # DOWNTIME FACTION WORK
    # =========================================================================

    def perform_faction_work(
        self,
        faction_id: str,
        days: int,
        task_type: str = "general",
        current_date: str = "",
    ) -> FactionWorkResult:
        """
        Perform faction work during downtime.

        This integrates with the DowntimeEngine's faction_work method
        but uses the global faction system for standing.

        Extreme rolls (2 or 12) trigger oracle detail checks for twists:
        - Roll of 2: Catastrophic failure with narrative twist
        - Roll of 12: Exceptional success with narrative twist

        Args:
            faction_id: The faction to work for
            days: Number of days worked
            task_type: Type of work performed
            current_date: Current game date for oracle events

        Returns:
            FactionWorkResult with outcomes
        """
        dice = DiceRoller()

        standing_before = self.get_standing(faction_id)

        # Roll for work success (2d6)
        roll = dice.roll_2d6(f"faction work for {faction_id}")
        roll_total = roll.total

        # Check for extreme rolls and generate oracle twist if enabled
        oracle_twist = None
        is_extreme_roll = roll_total in (2, 12)
        if is_extreme_roll and self._engine.oracle:
            oracle = self._engine.oracle
            if oracle.config.enabled and oracle.config.party_work_twists_enabled:
                if oracle.config.party_work_twist_on_extremes:
                    tag = "party_work_exceptional" if roll_total == 12 else "party_work_catastrophe"
                    oracle_twist = oracle.detail_check(
                        date=current_date,
                        faction_id=faction_id,
                        tag=tag,
                    )

        # Determine success threshold based on standing
        # Better standing = easier tasks
        threshold = 7
        if standing_before >= 5:
            threshold = 6
        elif standing_before >= 2:
            threshold = 7
        elif standing_before < 0:
            threshold = 8

        success = roll_total >= threshold

        if success:
            # Calculate standing gain
            # More days = more potential gain, but diminishing returns
            base_gain = 1
            if days >= 7:
                base_gain = 2
            elif days >= 3:
                base_gain = 1

            # Bonus for good roll
            if roll_total >= 10:
                base_gain += 1

            # Extra bonus for natural 12
            if roll_total == 12:
                base_gain += 1

            _, standing_after = self.adjust_standing(
                faction_id, base_gain, f"Faction work ({days} days)"
            )

            twist_msg = ""
            if oracle_twist:
                twist_msg = f" Twist: {oracle_twist.meaning_pair}"

            return FactionWorkResult(
                success=True,
                faction_id=faction_id,
                standing_before=standing_before,
                standing_after=standing_after,
                standing_delta=base_gain,
                message=f"Successfully completed {task_type} work for {faction_id}.{twist_msg}",
                roll_total=roll_total,
                oracle_twist=oracle_twist,
            )
        else:
            # Failure - possible standing loss on bad roll
            delta = 0
            if roll_total <= 4:
                delta = -1
                self.adjust_standing(faction_id, delta, "Failed faction work")

            # Extra penalty for natural 2
            if roll_total == 2:
                delta -= 1
                self.adjust_standing(faction_id, -1, "Catastrophic faction work failure")

            twist_msg = ""
            if oracle_twist:
                twist_msg = f" Twist: {oracle_twist.meaning_pair}"

            return FactionWorkResult(
                success=False,
                faction_id=faction_id,
                standing_before=standing_before,
                standing_after=standing_before + delta,
                standing_delta=delta,
                message=f"Failed to complete {task_type} work for {faction_id}.{twist_msg}",
                roll_total=roll_total,
                oracle_twist=oracle_twist,
            )

    # =========================================================================
    # STATUS REPORTING
    # =========================================================================

    def get_party_faction_summary(self) -> dict[str, Any]:
        """
        Get a summary of party faction relationships.

        Returns:
            Dict with standing, affiliations, and jobs
        """
        return {
            "standing": {
                faction_id: {
                    "value": standing,
                    "label": self.get_standing_label(standing),
                }
                for faction_id, standing in self.party_state.standing_by_id.items()
            },
            "affiliations": [
                {
                    "faction": aff.faction_or_group,
                    "kind": aff.kind,
                    "rank": aff.rank,
                    "since": aff.since_date,
                }
                for aff in self.party_state.affiliations
            ],
            "active_jobs": [
                {
                    "job_id": job.job_id,
                    "faction": job.faction_id,
                    "title": job.title,
                    "status": job.status,
                }
                for job in self.party_state.active_jobs.values()
            ],
            "completed_jobs": len(self.party_state.completed_job_ids),
        }
