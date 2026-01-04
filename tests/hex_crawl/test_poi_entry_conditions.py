"""
Tests for POI entry conditions and permission-based entry.

This test suite validates:
- SocialParticipant permission tracking
- enter_poi_with_conditions works with various condition types
- Permission granted in social context enables entry
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_models import (
    SocialParticipant,
    SocialParticipantType,
    PointOfInterest,
    SocialContext,
)
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.game_state.global_controller import GlobalController


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def participant():
    """Create a basic SocialParticipant for testing."""
    return SocialParticipant(
        participant_id="lady_borrid",
        name="Lady Amonie Borrid",
        participant_type=SocialParticipantType.NPC,
    )


@pytest.fixture
def poi_with_permission_required():
    """Create a POI that requires permission to enter."""
    return PointOfInterest(
        name="Lady Borrid's Hunting Lodge",
        poi_type="lodge",
        description="A hunting lodge.",
        entry_conditions={
            "type": "permission_required",
            "description": "Entering without permission triggers the moose head alarm.",
            "check_type": "social",
            "npc_id": "lady_amonie_borrid",
            "outcomes": {
                "success": "Lady Borrid welcomes the visitors",
                "failure": "Visitors are politely asked to leave",
                "hostile": "The giant weasel is commanded to attack",
            },
        },
    )


@pytest.fixture
def poi_with_toll():
    """Create a POI that requires payment to enter."""
    return PointOfInterest(
        name="Toll Bridge",
        poi_type="bridge",
        description="A bridge with a toll.",
        entry_conditions={
            "type": "toll",
            "toll_amount": 5,
            "description": "A 5gp toll is required.",
            "outcomes": {
                "success": "The toll keeper waves you through",
                "failure": "Pay the toll or turn back",
            },
        },
    )


@pytest.fixture
def poi_with_password():
    """Create a POI that requires a password."""
    return PointOfInterest(
        name="Secret Entrance",
        poi_type="entrance",
        description="A hidden door.",
        entry_conditions={
            "type": "password",
            "password": "swordfish",
            "description": "Speak the password to enter.",
            "outcomes": {
                "success": "The door slides open",
                "failure": "The door remains sealed",
            },
        },
    )


@pytest.fixture
def poi_with_interrogation():
    """Create a POI that requires interrogation/social check."""
    return PointOfInterest(
        name="Murkin's Army Camp",
        poi_type="camp",
        description="A military camp.",
        entry_conditions={
            "type": "interrogation",
            "description": "Visitors are questioned by sentries.",
            "check_type": "social",
            "npc_id": "sergeant_snidebleat",
            "outcomes": {
                "success": "You may pass after questioning",
                "failure": "Move along",
                "hostile": "Visitors are arrested",
            },
        },
    )


# =============================================================================
# SOCIAL PARTICIPANT PERMISSION TESTS
# =============================================================================


class TestSocialParticipantPermissions:
    """Test that SocialParticipant permission tracking works."""

    def test_permission_defaults_to_false(self, participant):
        """By default, no permissions are granted."""
        assert participant.has_permission("Lady Borrid's Hunting Lodge") is False

    def test_grant_permission(self, participant):
        """Granting permission sets it to True."""
        participant.grant_permission("Lady Borrid's Hunting Lodge")
        assert participant.has_permission("Lady Borrid's Hunting Lodge") is True

    def test_revoke_permission(self, participant):
        """Revoking permission sets it to False."""
        participant.grant_permission("Lady Borrid's Hunting Lodge")
        participant.revoke_permission("Lady Borrid's Hunting Lodge")
        assert participant.has_permission("Lady Borrid's Hunting Lodge") is False

    def test_multiple_poi_permissions(self, participant):
        """Can track permissions for multiple POIs."""
        participant.grant_permission("Lodge A")
        participant.grant_permission("Lodge B")
        participant.revoke_permission("Lodge A")

        assert participant.has_permission("Lodge A") is False
        assert participant.has_permission("Lodge B") is True
        assert participant.has_permission("Lodge C") is False

    def test_permissions_field_is_dict(self, participant):
        """Permissions field should be a dictionary."""
        assert isinstance(participant.permissions, dict)
        participant.grant_permission("Test POI")
        assert participant.permissions == {"Test POI": True}


# =============================================================================
# POI ENTRY CONDITION TESTS
# =============================================================================


class TestPOIEntryConditions:
    """Test POI check_entry_allowed method."""

    def test_no_conditions_allows_entry(self):
        """POI without entry conditions allows entry."""
        poi = PointOfInterest(
            name="Open Field",
            poi_type="field",
            description="An open field.",
        )
        result = poi.check_entry_allowed()
        assert result["allowed"] is True

    def test_permission_required_with_permission(self, poi_with_permission_required):
        """Entry succeeds when permission is granted."""
        result = poi_with_permission_required.check_entry_allowed(has_permission=True)
        assert result["allowed"] is True
        assert result["outcome"] == "success"
        assert "welcomes" in result["description"]

    def test_permission_required_without_permission(self, poi_with_permission_required):
        """Entry fails without permission and triggers alert."""
        result = poi_with_permission_required.check_entry_allowed(has_permission=False)
        assert result["allowed"] is False
        assert result["outcome"] == "failure"
        assert result.get("triggers_alert") is True

    def test_toll_with_sufficient_payment(self, poi_with_toll):
        """Entry succeeds with sufficient payment."""
        result = poi_with_toll.check_entry_allowed(payment_offered=5)
        assert result["allowed"] is True
        assert result["payment_taken"] == 5

    def test_toll_with_insufficient_payment(self, poi_with_toll):
        """Entry fails with insufficient payment."""
        result = poi_with_toll.check_entry_allowed(payment_offered=3)
        assert result["allowed"] is False
        assert result["outcome"] == "failure"

    def test_password_correct(self, poi_with_password):
        """Entry succeeds with correct password."""
        result = poi_with_password.check_entry_allowed(password_given="swordfish")
        assert result["allowed"] is True

    def test_password_incorrect(self, poi_with_password):
        """Entry fails with incorrect password."""
        result = poi_with_password.check_entry_allowed(password_given="wrongpass")
        assert result["allowed"] is False

    def test_password_case_insensitive(self, poi_with_password):
        """Password check is case insensitive."""
        result = poi_with_password.check_entry_allowed(password_given="SWORDFISH")
        assert result["allowed"] is True

    def test_interrogation_success(self, poi_with_interrogation):
        """Entry succeeds with social success."""
        result = poi_with_interrogation.check_entry_allowed(social_result="success")
        assert result["allowed"] is True
        assert result["outcome"] == "success"

    def test_interrogation_failure(self, poi_with_interrogation):
        """Entry fails with social failure."""
        result = poi_with_interrogation.check_entry_allowed(social_result="failure")
        assert result["allowed"] is False
        assert result["outcome"] == "failure"

    def test_interrogation_hostile(self, poi_with_interrogation):
        """Entry denied and combat triggered with hostile result."""
        result = poi_with_interrogation.check_entry_allowed(social_result="hostile")
        assert result["allowed"] is False
        assert result["outcome"] == "hostile"
        assert result.get("triggers_combat") is True


# =============================================================================
# INTEGRATION: PERMISSION FROM SOCIAL CONTEXT
# =============================================================================


class TestPermissionFromSocialContext:
    """Test that permissions granted in social context enable entry."""

    def test_social_context_participant_grants_permission(self, participant):
        """When participant grants permission, it should be tracked."""
        # Create a social context with the participant
        context = SocialContext(
            context_id="test_context",
            poi_name="Lady Borrid's Hunting Lodge",
            participants=[participant],
        )

        # Participant grants permission
        participant.grant_permission("Lady Borrid's Hunting Lodge")

        # Verify the context's participant has permission
        assert context.participants[0].has_permission("Lady Borrid's Hunting Lodge")

    def test_permission_persists_across_participant_reference(self, participant):
        """Permission should persist when participant is accessed through context."""
        context = SocialContext(
            context_id="test_context",
            poi_name="Lady Borrid's Hunting Lodge",
            participants=[participant],
        )

        # Grant through direct reference
        participant.grant_permission("Lady Borrid's Hunting Lodge")

        # Access through context and verify
        context_participant = context.participants[0]
        assert context_participant.has_permission("Lady Borrid's Hunting Lodge")


# =============================================================================
# ENGINE INTEGRATION TESTS
# =============================================================================


class TestEnterPOIWithConditionsEngine:
    """Test HexCrawlEngine.enter_poi_with_conditions integration."""

    @pytest.fixture
    def engine_with_poi(self, poi_with_permission_required):
        """Create an engine with a POI that requires permission."""
        controller = MagicMock(spec=GlobalController)
        controller.world_state = MagicMock()
        controller.party_state = MagicMock()
        controller.party_state.characters = {}
        controller.social_context = None

        engine = HexCrawlEngine(controller)

        # Mock hex data with the POI
        mock_hex = MagicMock()
        mock_hex.points_of_interest = [poi_with_permission_required]
        engine._hex_data = {"0109": mock_hex}
        engine._current_hex = "0109"
        engine._current_poi = "Lady Borrid's Hunting Lodge"

        return engine

    def test_enter_with_permission_succeeds(self, engine_with_poi):
        """Entry succeeds when has_permission is True."""
        result = engine_with_poi.enter_poi_with_conditions(
            "0109",
            has_permission=True,
        )
        assert result.get("success", True)
        assert result.get("entry_outcome") == "success"

    def test_enter_without_permission_fails(self, engine_with_poi):
        """Entry fails when has_permission is False."""
        result = engine_with_poi.enter_poi_with_conditions(
            "0109",
            has_permission=False,
        )
        assert result.get("allowed") is False
        assert result.get("triggers_alert") is True

    def test_enter_with_no_current_poi_fails(self, engine_with_poi):
        """Entry fails when not at a POI."""
        engine_with_poi._current_poi = None
        result = engine_with_poi.enter_poi_with_conditions("0109")
        assert result.get("success") is False
        assert "Not at any location" in result.get("error", "")
