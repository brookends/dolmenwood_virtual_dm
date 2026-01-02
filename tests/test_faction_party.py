"""
Tests for faction_party.py - Party-faction interaction layer.

Tests party standing management, affiliations, job tracking,
and downtime faction work integration.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.factions.faction_party import (
    FactionWorkResult,
    JobCompletionResult,
    FactionPartyManager,
)
from src.factions.faction_models import (
    ActiveJob,
    FactionRules,
    FactionDefinition,
    PartyAffiliation,
    PartyFactionState,
    QuestTemplate,
    QuestEffect,
    AdventurerProfile,
)
from src.factions.faction_engine import FactionEngine


@pytest.fixture
def basic_rules():
    """Create basic faction rules."""
    return FactionRules(
        schema_version=1,
        turn_cadence_days=7,
        actions_per_faction=3,
    )


@pytest.fixture
def basic_faction():
    """Create a basic faction definition."""
    return FactionDefinition(
        faction_id="nag_lord",
        name="Nag-Lord Atanuwe",
        tags=["fey_courts"],
    )


@pytest.fixture
def faction_engine(basic_rules, basic_faction):
    """Create a faction engine with basic setup."""
    engine = FactionEngine(
        rules=basic_rules,
        definitions={"nag_lord": basic_faction},
    )
    engine.set_party_state(PartyFactionState())
    return engine


@pytest.fixture
def party_manager(faction_engine):
    """Create a party manager."""
    return FactionPartyManager(faction_engine)


# =============================================================================
# FactionWorkResult Tests
# =============================================================================


class TestFactionWorkResult:
    """Tests for FactionWorkResult dataclass."""

    def test_default_rewards_list(self):
        """Test that rewards defaults to empty list."""
        result = FactionWorkResult(success=True, faction_id="test")
        assert result.rewards == []

    def test_provided_rewards(self):
        """Test that provided rewards are preserved."""
        rewards = ["gold", "item"]
        result = FactionWorkResult(
            success=True,
            faction_id="test",
            rewards=rewards,
        )
        assert result.rewards == rewards

    def test_all_fields(self):
        """Test all fields are set correctly."""
        result = FactionWorkResult(
            success=True,
            faction_id="nag_lord",
            job_id="job_123",
            standing_before=5,
            standing_after=7,
            standing_delta=2,
            rewards=["gold"],
            message="Test message",
        )
        assert result.success is True
        assert result.faction_id == "nag_lord"
        assert result.job_id == "job_123"
        assert result.standing_before == 5
        assert result.standing_after == 7
        assert result.standing_delta == 2
        assert result.rewards == ["gold"]
        assert result.message == "Test message"


# =============================================================================
# JobCompletionResult Tests
# =============================================================================


class TestJobCompletionResult:
    """Tests for JobCompletionResult dataclass."""

    def test_default_lists(self):
        """Test that rewards and effects_applied default to empty lists."""
        result = JobCompletionResult(
            success=True,
            job_id="job_1",
            faction_id="test",
        )
        assert result.rewards == []
        assert result.effects_applied == []

    def test_all_fields(self):
        """Test all fields are set correctly."""
        result = JobCompletionResult(
            success=True,
            job_id="job_123",
            faction_id="nag_lord",
            standing_delta=2,
            rewards=["gold"],
            effects_applied=["reputation"],
            message="Completed!",
        )
        assert result.success is True
        assert result.job_id == "job_123"
        assert result.faction_id == "nag_lord"
        assert result.standing_delta == 2
        assert result.rewards == ["gold"]
        assert result.effects_applied == ["reputation"]
        assert result.message == "Completed!"


# =============================================================================
# Standing Management Tests
# =============================================================================


class TestStandingManagement:
    """Tests for party standing management."""

    def test_get_standing_default(self, party_manager):
        """Test that default standing is 0."""
        standing = party_manager.get_standing("nag_lord")
        assert standing == 0

    def test_adjust_standing_positive(self, party_manager):
        """Test positive standing adjustment."""
        old, new = party_manager.adjust_standing("nag_lord", 3, "Test reason")
        assert old == 0
        assert new == 3

    def test_adjust_standing_negative(self, party_manager):
        """Test negative standing adjustment."""
        party_manager.adjust_standing("nag_lord", 5)
        old, new = party_manager.adjust_standing("nag_lord", -2, "Bad action")
        assert old == 5
        assert new == 3

    def test_adjust_standing_cumulative(self, party_manager):
        """Test cumulative standing adjustments."""
        party_manager.adjust_standing("nag_lord", 2)
        party_manager.adjust_standing("nag_lord", 3)
        party_manager.adjust_standing("nag_lord", -1)
        assert party_manager.get_standing("nag_lord") == 4

    def test_adjust_standing_multiple_factions(self, party_manager):
        """Test standing with multiple factions."""
        party_manager.adjust_standing("nag_lord", 5)
        party_manager.adjust_standing("other_faction", -2)
        assert party_manager.get_standing("nag_lord") == 5
        assert party_manager.get_standing("other_faction") == -2

    def test_get_standing_label_allied(self, party_manager):
        """Test Allied label for high standing."""
        assert party_manager.get_standing_label(8) == "Allied"
        assert party_manager.get_standing_label(10) == "Allied"

    def test_get_standing_label_friendly(self, party_manager):
        """Test Friendly label."""
        assert party_manager.get_standing_label(5) == "Friendly"
        assert party_manager.get_standing_label(7) == "Friendly"

    def test_get_standing_label_favorable(self, party_manager):
        """Test Favorable label."""
        assert party_manager.get_standing_label(2) == "Favorable"
        assert party_manager.get_standing_label(4) == "Favorable"

    def test_get_standing_label_neutral(self, party_manager):
        """Test Neutral label."""
        assert party_manager.get_standing_label(-1) == "Neutral"
        assert party_manager.get_standing_label(0) == "Neutral"
        assert party_manager.get_standing_label(1) == "Neutral"

    def test_get_standing_label_unfavorable(self, party_manager):
        """Test Unfavorable label."""
        assert party_manager.get_standing_label(-2) == "Unfavorable"
        assert party_manager.get_standing_label(-4) == "Unfavorable"

    def test_get_standing_label_hostile(self, party_manager):
        """Test Hostile label."""
        assert party_manager.get_standing_label(-5) == "Hostile"
        assert party_manager.get_standing_label(-7) == "Hostile"

    def test_get_standing_label_enemy(self, party_manager):
        """Test Enemy label for very low standing."""
        assert party_manager.get_standing_label(-8) == "Enemy"
        assert party_manager.get_standing_label(-10) == "Enemy"


# =============================================================================
# Affiliation Management Tests
# =============================================================================


class TestAffiliationManagement:
    """Tests for party affiliation management."""

    def test_has_affiliation_false(self, party_manager):
        """Test has_affiliation returns False when no affiliation."""
        assert party_manager.has_affiliation("nag_lord") is False

    def test_create_affiliation(self, party_manager):
        """Test creating an affiliation."""
        affiliation = party_manager.create_affiliation(
            "nag_lord",
            kind="ally",
            current_date="1420-05-10",
        )
        assert affiliation.faction_or_group == "nag_lord"
        assert affiliation.kind == "ally"
        assert affiliation.rank == 0
        assert affiliation.since_date == "1420-05-10"

    def test_has_affiliation_true(self, party_manager):
        """Test has_affiliation returns True after creating affiliation."""
        party_manager.create_affiliation("nag_lord")
        assert party_manager.has_affiliation("nag_lord") is True

    def test_get_affiliation(self, party_manager):
        """Test getting an affiliation."""
        party_manager.create_affiliation("nag_lord", kind="working_relationship")
        affiliation = party_manager.get_affiliation("nag_lord")
        assert affiliation is not None
        assert affiliation.kind == "working_relationship"

    def test_get_affiliation_none(self, party_manager):
        """Test getting non-existent affiliation returns None."""
        assert party_manager.get_affiliation("unknown") is None

    def test_advance_affiliation_rank(self, party_manager):
        """Test advancing affiliation rank."""
        party_manager.create_affiliation("nag_lord")
        affiliation = party_manager.advance_affiliation_rank("nag_lord")
        assert affiliation is not None
        assert affiliation.rank == 1

    def test_advance_affiliation_rank_multiple(self, party_manager):
        """Test advancing affiliation rank multiple times."""
        party_manager.create_affiliation("nag_lord")
        party_manager.advance_affiliation_rank("nag_lord")
        party_manager.advance_affiliation_rank("nag_lord")
        affiliation = party_manager.get_affiliation("nag_lord")
        assert affiliation.rank == 2

    def test_advance_affiliation_rank_not_affiliated(self, party_manager):
        """Test advancing rank when not affiliated returns None."""
        result = party_manager.advance_affiliation_rank("unknown")
        assert result is None

    def test_can_affiliate_no_profiles(self, party_manager):
        """Test can_affiliate returns True when no profiles loaded."""
        can, reason = party_manager.can_affiliate("nag_lord")
        assert can is True
        assert reason == "No profile restrictions"


# =============================================================================
# Job Management Tests
# =============================================================================


class TestJobManagement:
    """Tests for job acceptance and tracking."""

    def test_list_available_jobs_no_profiles(self, party_manager):
        """Test list_available_jobs returns empty when no profiles."""
        jobs = party_manager.list_available_jobs("nag_lord")
        assert jobs == []

    def test_accept_job_no_profiles(self, party_manager):
        """Test accept_job returns None when no profiles."""
        job = party_manager.accept_job("nag_lord", "template_1")
        assert job is None

    def test_get_active_jobs_empty(self, party_manager):
        """Test get_active_jobs when no jobs."""
        jobs = party_manager.get_active_jobs()
        assert jobs == []

    def test_complete_job_not_found(self, party_manager):
        """Test completing non-existent job."""
        result = party_manager.complete_job("unknown_job")
        assert result.success is False
        assert result.message == "Job not found"

    def test_abandon_job_not_found(self, party_manager):
        """Test abandoning non-existent job."""
        result = party_manager.abandon_job("unknown_job")
        assert result is False


class TestJobManagementWithProfiles:
    """Tests for job management with mock profiles."""

    @pytest.fixture
    def mock_profiles(self):
        """Create mock profiles with quest templates."""
        profiles = MagicMock()
        profiles.list_quest_templates.return_value = [
            QuestTemplate(
                id="quest_1",
                title="Find the Artifact",
            ),
            QuestTemplate(
                id="quest_2",
                title="Deliver Message",
            ),
        ]
        profiles.get_quest_template.return_value = QuestTemplate(
            id="quest_1",
            title="Find the Artifact",
        )
        profiles.can_affiliate.return_value = True
        return profiles

    @pytest.fixture
    def party_manager_with_profiles(self, faction_engine, mock_profiles):
        """Create party manager with mock profiles."""
        return FactionPartyManager(faction_engine, profiles=mock_profiles)

    def test_list_available_jobs(self, party_manager_with_profiles):
        """Test listing available jobs."""
        jobs = party_manager_with_profiles.list_available_jobs("nag_lord")
        assert len(jobs) == 2
        assert jobs[0].title == "Find the Artifact"

    @patch("src.factions.faction_party.DiceRoller")
    def test_accept_job(self, mock_dice_class, party_manager_with_profiles):
        """Test accepting a job."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        job = party_manager_with_profiles.accept_job(
            "nag_lord",
            "quest_1",
            current_date="1420-05-10",
        )
        assert job is not None
        assert job.faction_id == "nag_lord"
        assert job.template_id == "quest_1"
        assert job.title == "Find the Artifact"
        assert job.status == "active"
        assert job.accepted_on == "1420-05-10"

    @patch("src.factions.faction_party.DiceRoller")
    def test_get_active_jobs(self, mock_dice_class, party_manager_with_profiles):
        """Test getting active jobs."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        party_manager_with_profiles.accept_job("nag_lord", "quest_1")
        jobs = party_manager_with_profiles.get_active_jobs()
        assert len(jobs) == 1

    @patch("src.factions.faction_party.DiceRoller")
    def test_get_active_jobs_filtered(self, mock_dice_class, party_manager_with_profiles):
        """Test getting active jobs filtered by faction."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        party_manager_with_profiles.accept_job("nag_lord", "quest_1")

        # Filter by nag_lord
        jobs = party_manager_with_profiles.get_active_jobs("nag_lord")
        assert len(jobs) == 1

        # Filter by other faction
        jobs = party_manager_with_profiles.get_active_jobs("other")
        assert len(jobs) == 0

    @patch("src.factions.faction_party.DiceRoller")
    def test_complete_job_success(self, mock_dice_class, party_manager_with_profiles):
        """Test completing a job successfully."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        job = party_manager_with_profiles.accept_job("nag_lord", "quest_1")
        result = party_manager_with_profiles.complete_job(job.job_id, success=True)

        assert result.success is True
        assert result.standing_delta == 1
        assert "completed" in result.message.lower()

    @patch("src.factions.faction_party.DiceRoller")
    def test_complete_job_failure(self, mock_dice_class, party_manager_with_profiles):
        """Test failing a job."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        job = party_manager_with_profiles.accept_job("nag_lord", "quest_1")
        result = party_manager_with_profiles.complete_job(job.job_id, success=False)

        assert result.success is False
        assert result.standing_delta == -1
        assert "failed" in result.message.lower()

    @patch("src.factions.faction_party.DiceRoller")
    def test_abandon_job(self, mock_dice_class, party_manager_with_profiles):
        """Test abandoning a job."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        job = party_manager_with_profiles.accept_job("nag_lord", "quest_1")
        standing_before = party_manager_with_profiles.get_standing("nag_lord")

        result = party_manager_with_profiles.abandon_job(job.job_id)

        assert result is True
        standing_after = party_manager_with_profiles.get_standing("nag_lord")
        assert standing_after == standing_before - 1  # -1 penalty

    def test_can_affiliate_allowed(self, party_manager_with_profiles):
        """Test can_affiliate when allowed by profiles."""
        can, reason = party_manager_with_profiles.can_affiliate("nag_lord")
        assert can is True
        assert reason == "Affiliation allowed"

    def test_can_affiliate_blocked(self, party_manager_with_profiles, mock_profiles):
        """Test can_affiliate when blocked by profiles."""
        mock_profiles.can_affiliate.return_value = False
        can, reason = party_manager_with_profiles.can_affiliate("nag_lord")
        assert can is False
        assert "restrictions" in reason.lower()


# =============================================================================
# Downtime Faction Work Tests
# =============================================================================


class TestFactionWork:
    """Tests for faction work during downtime."""

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_success(self, mock_dice_class, party_manager):
        """Test successful faction work."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 8  # Success (>= 7)
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        result = party_manager.perform_faction_work("nag_lord", days=3)

        assert result.success is True
        assert result.faction_id == "nag_lord"
        assert result.standing_delta >= 1
        assert result.standing_after > result.standing_before

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_failure(self, mock_dice_class, party_manager):
        """Test failed faction work."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 5  # Failure (< 7)
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        result = party_manager.perform_faction_work("nag_lord", days=3)

        assert result.success is False
        assert result.faction_id == "nag_lord"

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_failure_with_penalty(self, mock_dice_class, party_manager):
        """Test failed faction work with standing penalty on bad roll."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 3  # Very bad roll (<= 4)
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        result = party_manager.perform_faction_work("nag_lord", days=3)

        assert result.success is False
        assert result.standing_delta == -1

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_bonus_for_good_roll(self, mock_dice_class, party_manager):
        """Test bonus standing for excellent roll."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 11  # Excellent roll (>= 10)
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        result = party_manager.perform_faction_work("nag_lord", days=3)

        assert result.success is True
        assert result.standing_delta >= 2  # Base + bonus

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_more_days_bonus(self, mock_dice_class, party_manager):
        """Test bonus for working 7+ days."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 7  # Just success
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        result = party_manager.perform_faction_work("nag_lord", days=7)

        assert result.success is True
        assert result.standing_delta == 2  # Base gain of 2 for 7+ days

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_easier_with_high_standing(self, mock_dice_class, party_manager):
        """Test that high standing makes work easier."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 6  # Would normally fail (< 7), but succeeds with standing 5+
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        # Set high standing first
        party_manager.adjust_standing("nag_lord", 5)

        result = party_manager.perform_faction_work("nag_lord", days=3)

        assert result.success is True  # Threshold is 6 with standing >= 5

    @patch("src.factions.faction_party.DiceRoller")
    def test_faction_work_harder_with_negative_standing(self, mock_dice_class, party_manager):
        """Test that negative standing makes work harder."""
        mock_dice = MagicMock()
        mock_roll = MagicMock()
        mock_roll.total = 7  # Would normally succeed (>= 7), but fails with standing < 0
        mock_dice.roll_2d6.return_value = mock_roll
        mock_dice_class.return_value = mock_dice

        # Set negative standing first
        party_manager.adjust_standing("nag_lord", -2)

        result = party_manager.perform_faction_work("nag_lord", days=3)

        assert result.success is False  # Threshold is 8 with standing < 0


# =============================================================================
# Status Reporting Tests
# =============================================================================


class TestStatusReporting:
    """Tests for party faction status reporting."""

    def test_get_party_faction_summary_empty(self, party_manager):
        """Test summary with no faction relationships."""
        summary = party_manager.get_party_faction_summary()
        assert "standing" in summary
        assert "affiliations" in summary
        assert "active_jobs" in summary
        assert "completed_jobs" in summary

    def test_get_party_faction_summary_with_standing(self, party_manager):
        """Test summary with faction standing."""
        party_manager.adjust_standing("nag_lord", 5)
        party_manager.adjust_standing("other_faction", -2)

        summary = party_manager.get_party_faction_summary()

        assert "nag_lord" in summary["standing"]
        assert summary["standing"]["nag_lord"]["value"] == 5
        assert summary["standing"]["nag_lord"]["label"] == "Friendly"

    def test_get_party_faction_summary_with_affiliations(self, party_manager):
        """Test summary with affiliations."""
        party_manager.create_affiliation("nag_lord", kind="ally", current_date="1420-05")
        party_manager.advance_affiliation_rank("nag_lord")

        summary = party_manager.get_party_faction_summary()

        assert len(summary["affiliations"]) == 1
        assert summary["affiliations"][0]["faction"] == "nag_lord"
        assert summary["affiliations"][0]["kind"] == "ally"
        assert summary["affiliations"][0]["rank"] == 1

    @patch("src.factions.faction_party.DiceRoller")
    def test_get_party_faction_summary_with_jobs(
        self, mock_dice_class, faction_engine
    ):
        """Test summary with active jobs."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        mock_profiles = MagicMock()
        mock_profiles.get_quest_template.return_value = QuestTemplate(
            id="quest_1",
            title="Test Quest",
        )

        manager = FactionPartyManager(faction_engine, profiles=mock_profiles)
        manager.accept_job("nag_lord", "quest_1")

        summary = manager.get_party_faction_summary()

        assert len(summary["active_jobs"]) == 1
        assert summary["active_jobs"][0]["title"] == "Test Quest"
        assert summary["active_jobs"][0]["status"] == "active"


# =============================================================================
# Party State Initialization Tests
# =============================================================================


class TestPartyStateInitialization:
    """Tests for party state initialization."""

    def test_party_state_created_if_missing(self, basic_rules, basic_faction):
        """Test that party state is created if missing."""
        engine = FactionEngine(
            rules=basic_rules,
            definitions={"nag_lord": basic_faction},
        )
        # Don't set party state

        manager = FactionPartyManager(engine)

        # Accessing party_state should create one
        state = manager.party_state
        assert state is not None
        assert isinstance(state, PartyFactionState)

    def test_party_state_preserved_if_exists(self, faction_engine):
        """Test that existing party state is preserved."""
        # Set up some state
        faction_engine.party_state.adjust_standing("nag_lord", 5)

        manager = FactionPartyManager(faction_engine)

        assert manager.get_standing("nag_lord") == 5


# =============================================================================
# Quest Effects Tests
# =============================================================================


class TestQuestEffects:
    """Tests for quest effect application on job completion."""

    @pytest.fixture
    def mock_profiles_with_effects(self):
        """Create mock profiles with quest effects."""
        profiles = MagicMock()
        profiles.get_quest_template.return_value = QuestTemplate(
            id="quest_1",
            title="Diplomatic Mission",
            default_effects=[
                QuestEffect(
                    type="party_reputation",
                    delta=2,
                    faction="allied_faction",
                ),
                QuestEffect(
                    type="party_reputation",
                    delta=-1,
                    faction="enemy_faction",
                ),
            ],
        )
        return profiles

    @patch("src.factions.faction_party.DiceRoller")
    def test_quest_effects_applied_on_success(
        self, mock_dice_class, faction_engine, mock_profiles_with_effects
    ):
        """Test that quest effects are applied on successful completion."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        manager = FactionPartyManager(faction_engine, profiles=mock_profiles_with_effects)

        job = manager.accept_job("nag_lord", "quest_1")
        result = manager.complete_job(job.job_id, success=True)

        assert result.success is True
        assert len(result.effects_applied) == 2

        # Check that standing was adjusted for affected factions
        assert manager.get_standing("allied_faction") == 2
        assert manager.get_standing("enemy_faction") == -1

    @patch("src.factions.faction_party.DiceRoller")
    def test_quest_effects_not_applied_on_failure(
        self, mock_dice_class, faction_engine, mock_profiles_with_effects
    ):
        """Test that quest effects are NOT applied on failure."""
        mock_dice = MagicMock()
        mock_dice.randint.return_value = 1234
        mock_dice_class.return_value = mock_dice

        manager = FactionPartyManager(faction_engine, profiles=mock_profiles_with_effects)

        job = manager.accept_job("nag_lord", "quest_1")
        result = manager.complete_job(job.job_id, success=False)

        assert result.success is False
        assert len(result.effects_applied) == 0

        # Standing should not be adjusted for quest effects
        assert manager.get_standing("allied_faction") == 0
        assert manager.get_standing("enemy_faction") == 0
