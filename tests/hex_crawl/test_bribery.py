"""
Tests for bribery mechanics (social:offer_bribe action).

This test suite validates:
- Party gold storage in PartyState
- Session persistence of gold
- social:offer_bribe action registration
- Bribe success/failure conditions
- Gold deduction on successful bribe
- Secret reveal on successful bribe
"""

import pytest
from unittest.mock import MagicMock, PropertyMock, patch

from src.data_models import (
    PartyState,
    PartyResources,
    Location,
    LocationType,
    SecretInfo,
    SecretStatus,
)
from src.game_state.session_manager import (
    SessionManager,
    SerializablePartyState,
)


# =============================================================================
# PARTY GOLD TESTS
# =============================================================================


class TestPartyGoldStorage:
    """Test gold storage in PartyState."""

    def test_party_state_has_gold_gp_field(self):
        """PartyState should have gold_gp field."""
        party = PartyState(
            location=Location(LocationType.HEX, "0109"),
        )
        assert hasattr(party, "gold_gp")
        assert party.gold_gp == 0

    def test_party_state_gold_gp_default(self):
        """gold_gp should default to 0."""
        party = PartyState(
            location=Location(LocationType.HEX, "0109"),
        )
        assert party.gold_gp == 0

    def test_party_state_gold_gp_can_be_set(self):
        """gold_gp should be settable."""
        party = PartyState(
            location=Location(LocationType.HEX, "0109"),
            gold_gp=100,
        )
        assert party.gold_gp == 100

    def test_party_state_gold_gp_can_be_modified(self):
        """gold_gp should be modifiable."""
        party = PartyState(
            location=Location(LocationType.HEX, "0109"),
            gold_gp=50,
        )
        party.gold_gp += 25
        assert party.gold_gp == 75

        party.gold_gp -= 30
        assert party.gold_gp == 45


# =============================================================================
# SERIALIZATION TESTS
# =============================================================================


class TestGoldPersistence:
    """Test gold persistence in session manager."""

    def test_serializable_party_state_has_gold_gp(self):
        """SerializablePartyState should have gold_gp field."""
        sps = SerializablePartyState(
            location_type="wilderness",
            location_id="0109",
            gold_gp=250,
        )
        assert sps.gold_gp == 250

    def test_serializable_party_state_to_dict(self):
        """gold_gp should be included in to_dict()."""
        sps = SerializablePartyState(
            location_type="wilderness",
            location_id="0109",
            gold_gp=100,
        )
        data = sps.to_dict()
        assert "gold_gp" in data
        assert data["gold_gp"] == 100

    def test_serializable_party_state_from_dict(self):
        """gold_gp should be restored from dict."""
        data = {
            "location_type": "wilderness",
            "location_id": "0109",
            "gold_gp": 500,
        }
        sps = SerializablePartyState.from_dict(data)
        assert sps.gold_gp == 500

    def test_serializable_party_state_from_dict_missing_gold(self):
        """Missing gold_gp should default to 0."""
        data = {
            "location_type": "wilderness",
            "location_id": "0109",
        }
        sps = SerializablePartyState.from_dict(data)
        assert sps.gold_gp == 0


class TestSessionManagerGoldExtraction:
    """Test session manager extraction and application of gold."""

    def test_extract_party_state_includes_gold(self):
        """extract_party_state should include gold_gp."""
        manager = SessionManager()
        manager.new_session("Test")

        party = PartyState(
            location=Location(LocationType.HEX, "0109"),
            resources=PartyResources(),
            gold_gp=150,
        )

        serialized = manager.extract_party_state(party)
        assert serialized.gold_gp == 150

    def test_apply_party_state_restores_gold(self):
        """apply_party_state should restore gold_gp."""
        manager = SessionManager()
        session = manager.new_session("Test")
        session.party_state = SerializablePartyState(
            location_type="hex",
            location_id="0109",
            gold_gp=200,
        )

        party = PartyState(
            location=Location(LocationType.HEX, "0109"),
            resources=PartyResources(),
        )
        assert party.gold_gp == 0

        manager.apply_party_state(party)
        assert party.gold_gp == 200


# =============================================================================
# ACTION REGISTRATION TESTS
# =============================================================================


class TestBribeActionRegistration:
    """Test that the bribe action is properly registered."""

    def test_action_registered(self):
        """social:offer_bribe should be registered."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        assert spec is not None
        assert spec.executor is not None

    def test_action_has_correct_params(self):
        """Action should have correct parameter schema."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        assert "secret_id" in spec.params_schema
        assert spec.params_schema["secret_id"]["required"] is True
        assert "gold_amount" in spec.params_schema
        assert spec.params_schema["gold_amount"]["required"] is False

    def test_action_requires_social_interaction(self):
        """Action should require social_interaction state."""
        from src.conversation.action_registry import get_default_registry

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        assert spec.requires_state == "social_interaction"


# =============================================================================
# SECRET INFO BRIBERY TESTS
# =============================================================================


class TestSecretInfoBribery:
    """Test SecretInfo bribery support."""

    def test_secret_info_has_bribe_fields(self):
        """SecretInfo should have can_be_bribed and bribe_amount fields."""
        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            can_be_bribed=True,
            bribe_amount=50,
        )
        assert secret.can_be_bribed is True
        assert secret.bribe_amount == 50

    def test_can_reveal_with_sufficient_bribe(self):
        """can_reveal should return True when bribe is sufficient."""
        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            can_be_bribed=True,
            bribe_amount=50,
            required_disposition=5,  # High disposition required
            required_trust=3,  # High trust required
        )

        # Without bribe, should fail (disposition 0, trust 0)
        assert secret.can_reveal(0, 0, 0) is False

        # With sufficient bribe, should succeed
        assert secret.can_reveal(0, 0, 50) is True

    def test_can_reveal_with_insufficient_bribe(self):
        """can_reveal should return False when bribe is insufficient."""
        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            can_be_bribed=True,
            bribe_amount=50,
            required_disposition=5,
            required_trust=3,
        )

        # Insufficient bribe
        assert secret.can_reveal(0, 0, 25) is False

    def test_can_reveal_non_bribeable(self):
        """can_reveal should ignore bribe for non-bribeable secrets."""
        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            can_be_bribed=False,
            bribe_amount=50,
            required_disposition=3,
            required_trust=2,
        )

        # Even large bribe shouldn't work
        assert secret.can_reveal(0, 0, 1000) is False

        # But meeting disposition/trust should work
        assert secret.can_reveal(3, 2, 0) is True


# =============================================================================
# BRIBE ACTION EXECUTION TESTS
# =============================================================================


class TestBribeActionExecution:
    """Test bribe action execution."""

    def _create_mock_dm(self, party_gold: int = 100):
        """Create a mock VirtualDM with social context."""
        dm = MagicMock()

        # Create a bribeable secret
        secret = SecretInfo(
            secret_id="murkin_location",
            content="Murkin hides treasure under the old oak.",
            hint="Something about treasure...",
            can_be_bribed=True,
            bribe_amount=25,
            status=SecretStatus.UNKNOWN,
        )

        # Create participant with the secret
        participant = MagicMock()
        participant.name = "Shifty Sam"
        participant.secret_info = [secret]
        participant.conversation = MagicMock()
        participant.conversation.disposition_numeric = 0
        participant.conversation.trust_level = 0

        # Set up social context
        social_context = MagicMock()
        social_context.participants = [participant]

        # Set up controller
        controller = MagicMock()
        type(controller).social_context = PropertyMock(return_value=social_context)
        controller.party_state = MagicMock()
        controller.party_state.gold_gp = party_gold

        dm.controller = controller

        return dm, participant, secret

    def test_bribe_success_deducts_gold(self):
        """Successful bribe should deduct gold from party."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 25,
        })

        assert result["success"] is True
        assert dm.controller.party_state.gold_gp == 75

    def test_bribe_success_reveals_secret(self):
        """Successful bribe should reveal the secret."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 25,
        })

        assert result["success"] is True
        assert secret.status == SecretStatus.REVEALED
        assert "secret_revealed" in result
        assert result["secret_revealed"]["content"] == "Murkin hides treasure under the old oak."

    def test_bribe_insufficient_gold_fails(self):
        """Bribe should fail if party has insufficient gold."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=10)

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 25,
        })

        assert result["success"] is False
        assert "error" in result
        assert "Insufficient funds" in result["error"]

    def test_bribe_insufficient_offer_fails(self):
        """Bribe should fail if offer is less than required."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 10,  # Less than required 25
        })

        assert result["success"] is False
        assert "required_amount" in result
        assert result["required_amount"] == 25

    def test_bribe_unknown_secret_fails(self):
        """Bribe should fail for unknown secret ID."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "nonexistent_secret",
            "gold_amount": 25,
        })

        assert result["success"] is False
        assert "error" in result

    def test_bribe_already_revealed_fails(self):
        """Bribe should fail if secret already revealed."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)
        secret.status = SecretStatus.REVEALED

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 25,
        })

        assert result["success"] is False
        assert "already been revealed" in result["error"]

    def test_bribe_non_bribeable_fails(self):
        """Bribe should fail for non-bribeable secrets."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)
        secret.can_be_bribed = False

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 25,
        })

        assert result["success"] is False
        assert "cannot be bribed" in result["message"]

    def test_bribe_no_social_context_fails(self):
        """Bribe should fail when not in social interaction."""
        from src.conversation.action_registry import get_default_registry

        dm = MagicMock()
        dm.controller.social_context = None

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            "gold_amount": 25,
        })

        assert result["success"] is False
        assert "Not in a conversation" in result["error"]

    def test_bribe_defaults_to_required_amount(self):
        """Bribe should default to required amount if not specified."""
        from src.conversation.action_registry import get_default_registry

        dm, participant, secret = self._create_mock_dm(party_gold=100)

        registry = get_default_registry()
        spec = registry.get("social:offer_bribe")

        result = spec.executor(dm, {
            "secret_id": "murkin_location",
            # No gold_amount specified
        })

        assert result["success"] is True
        assert result["gold_spent"] == 25
        assert dm.controller.party_state.gold_gp == 75


# =============================================================================
# SUGGESTION BUILDER TESTS
# =============================================================================


class TestBribeSuggestion:
    """Test bribe suggestion in suggestion builder."""

    def test_suggestion_shown_when_bribeable_secret_exists(self):
        """Bribe suggestion should appear when NPC has bribeable secret."""
        from src.conversation.suggestion_builder import _social_suggestions

        # Create mock DM
        dm = MagicMock()

        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            hint="Something secret...",
            can_be_bribed=True,
            bribe_amount=50,
            status=SecretStatus.UNKNOWN,
        )

        participant = MagicMock()
        participant.name = "Informant"
        participant.secret_info = [secret]

        social_context = MagicMock()
        social_context.participants = [participant]

        type(dm.controller).social_context = PropertyMock(return_value=social_context)
        dm.controller.party_state = MagicMock()
        dm.controller.party_state.gold_gp = 100

        suggestions = _social_suggestions(dm, "char_1")

        bribe_suggestions = [s for s in suggestions if s.action.id == "social:offer_bribe"]
        assert len(bribe_suggestions) == 1
        assert bribe_suggestions[0].action.params["gold_amount"] == 50

    def test_no_suggestion_when_insufficient_gold(self):
        """No bribe suggestion when party lacks gold."""
        from src.conversation.suggestion_builder import _social_suggestions

        dm = MagicMock()

        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            can_be_bribed=True,
            bribe_amount=50,
            status=SecretStatus.UNKNOWN,
        )

        participant = MagicMock()
        participant.name = "Informant"
        participant.secret_info = [secret]

        social_context = MagicMock()
        social_context.participants = [participant]

        type(dm.controller).social_context = PropertyMock(return_value=social_context)
        dm.controller.party_state = MagicMock()
        dm.controller.party_state.gold_gp = 25  # Less than required

        suggestions = _social_suggestions(dm, "char_1")

        bribe_suggestions = [s for s in suggestions if s.action.id == "social:offer_bribe"]
        assert len(bribe_suggestions) == 0

    def test_no_suggestion_when_secret_already_revealed(self):
        """No bribe suggestion for already revealed secrets."""
        from src.conversation.suggestion_builder import _social_suggestions

        dm = MagicMock()

        secret = SecretInfo(
            secret_id="test_secret",
            content="A hidden truth",
            can_be_bribed=True,
            bribe_amount=50,
            status=SecretStatus.REVEALED,  # Already revealed
        )

        participant = MagicMock()
        participant.name = "Informant"
        participant.secret_info = [secret]

        social_context = MagicMock()
        social_context.participants = [participant]

        type(dm.controller).social_context = PropertyMock(return_value=social_context)
        dm.controller.party_state = MagicMock()
        dm.controller.party_state.gold_gp = 100

        suggestions = _social_suggestions(dm, "char_1")

        bribe_suggestions = [s for s in suggestions if s.action.id == "social:offer_bribe"]
        assert len(bribe_suggestions) == 0
