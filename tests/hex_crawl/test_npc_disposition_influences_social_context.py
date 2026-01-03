"""
Deterministic tests for NPC disposition influence on social context (P9.4).

Verifies that:
1. NPC disposition is computed from get_npc_disposition_to_party
2. NPC default disposition is added to base
3. Computed disposition is included in interact_with_npc result
4. Transition context includes disposition for SocialContext
5. Relationship modifiers affect computed disposition
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.hex_crawl.hex_crawl_engine import (
    HexCrawlEngine,
    POIVisit,
)
from src.data_models import (
    HexLocation,
    PointOfInterest,
    HexNPC,
    FactionState,
)
from src.game_state.global_controller import GlobalController


@pytest.fixture
def mock_controller():
    """Create a mock controller."""
    controller = MagicMock(spec=GlobalController)
    controller.current_state = MagicMock()
    return controller


@pytest.fixture
def npc_with_disposition():
    """Create an NPC with default disposition."""
    npc = HexNPC(
        npc_id="merchant_tobias",
        name="Tobias the Merchant",
        description="A portly merchant with keen eyes",
        demeanor=["friendly", "cautious"],
    )
    # Set default disposition
    npc.disposition = 10  # Slightly positive default
    return npc


@pytest.fixture
def hostile_npc():
    """Create an NPC with negative default disposition."""
    npc = HexNPC(
        npc_id="bandit_leader",
        name="Scar the Bandit",
        description="A scarred ruffian with a cruel smile",
        demeanor=["hostile", "greedy"],
    )
    npc.disposition = -30  # Hostile default
    return npc


@pytest.fixture
def hex_with_npcs(npc_with_disposition, hostile_npc):
    """Create hex data with NPCs at a POI."""
    poi = PointOfInterest(
        name="Market Square",
        poi_type="settlement_feature",
        description="A busy market square",
        inhabitants="Various merchants and travelers",
    )

    hex_data = HexLocation(
        hex_id="0703",
        name="Lankshorn",
        terrain_type="settlement",
        points_of_interest=[poi],
        npcs=[npc_with_disposition, hostile_npc],
    )
    return hex_data


@pytest.fixture
def faction_state_with_reputation():
    """Create faction state with party reputation modifiers."""
    state = FactionState(hex_id="0703")
    # Party has helped the merchant before (+20)
    state.party_reputation = {
        "merchant_tobias": 20,
        "bandit_leader": -40,  # Party has opposed bandits
    }
    return state


@pytest.fixture
def hex_crawl_engine(mock_controller, hex_with_npcs, faction_state_with_reputation):
    """Create hex crawl engine with test data."""
    engine = HexCrawlEngine(controller=mock_controller)
    engine._hex_data["0703"] = hex_with_npcs
    engine._current_poi = "Market Square"

    # Mock get_faction_state to return our test state
    engine.get_faction_state = MagicMock(return_value=faction_state_with_reputation)

    # Mock get_npcs_at_poi to return NPCs
    engine.get_npcs_at_poi = MagicMock(
        return_value=[
            {"npc_id": "merchant_tobias", "name": "Tobias the Merchant"},
            {"npc_id": "bandit_leader", "name": "Scar the Bandit"},
        ]
    )

    return engine


class TestDispositionComputedFromFactionState:
    """Test that disposition is computed from get_npc_disposition_to_party."""

    def test_base_disposition_from_faction_state(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify base disposition comes from faction state."""
        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        assert result["success"] is True
        # Base (20) + NPC default (10) = 30
        assert result["disposition"] == 30

    def test_negative_base_disposition(self, hex_crawl_engine, mock_controller):
        """Verify negative base disposition is computed correctly."""
        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="bandit_leader",
        )

        assert result["success"] is True
        # Base (-40) + NPC default (-30) = -70
        assert result["disposition"] == -70


class TestNPCDefaultDispositionAdded:
    """Test that NPC default disposition is added to base."""

    def test_npc_default_added_to_base(self, hex_crawl_engine, mock_controller):
        """Verify NPC default disposition is added."""
        # Modify faction state to have 0 reputation
        hex_crawl_engine.get_faction_state.return_value.party_reputation = {
            "merchant_tobias": 0,
        }

        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        # Base (0) + NPC default (10) = 10
        assert result["disposition"] == 10


class TestDispositionClampedToValidRange:
    """Test that computed disposition is clamped to -100 to +100."""

    def test_positive_clamped_to_100(self, hex_crawl_engine, mock_controller):
        """Verify extremely positive disposition is clamped to 100."""
        # Set very high reputation
        hex_crawl_engine.get_faction_state.return_value.party_reputation = {
            "merchant_tobias": 200,
        }

        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        # Would be 200 + 10 = 210, clamped to 100
        assert result["disposition"] == 100

    def test_negative_clamped_to_minus_100(self, hex_crawl_engine, mock_controller):
        """Verify extremely negative disposition is clamped to -100."""
        hex_crawl_engine.get_faction_state.return_value.party_reputation = {
            "bandit_leader": -200,
        }

        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="bandit_leader",
        )

        # Would be -200 + -30 = -230, clamped to -100
        assert result["disposition"] == -100


class TestDispositionIncludedInResult:
    """Test that computed disposition is included in result."""

    def test_disposition_in_result(self, hex_crawl_engine, mock_controller):
        """Verify disposition is in the result dictionary."""
        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        assert "disposition" in result
        assert isinstance(result["disposition"], int)


class TestTransitionContextIncludesDisposition:
    """Test that transition context includes disposition for SocialContext."""

    def test_disposition_in_transition_context(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify transition is called with disposition in context."""
        hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        mock_controller.transition.assert_called_once()
        call_args = mock_controller.transition.call_args
        context = call_args[1]["context"]

        assert "disposition" in context
        assert context["disposition"] == 30  # 20 + 10

    def test_base_and_default_disposition_in_context(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify both base and default disposition are in context for debugging."""
        hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        context = mock_controller.transition.call_args[1]["context"]

        assert context["base_disposition"] == 20  # From faction state
        assert context["npc_default_disposition"] == 10  # From NPC definition


class TestRelationshipModifiersAffectDisposition:
    """Test that relationship modifiers affect computed disposition."""

    def test_positive_reputation_increases_disposition(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify positive reputation increases final disposition."""
        # Party has very good reputation with merchant
        hex_crawl_engine.get_faction_state.return_value.party_reputation = {
            "merchant_tobias": 50,
        }

        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        # 50 + 10 = 60
        assert result["disposition"] == 60

    def test_negative_reputation_decreases_disposition(
        self, hex_crawl_engine, mock_controller
    ):
        """Verify negative reputation decreases final disposition."""
        # Party has wronged the merchant
        hex_crawl_engine.get_faction_state.return_value.party_reputation = {
            "merchant_tobias": -30,
        }

        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        # -30 + 10 = -20
        assert result["disposition"] == -20


class TestFirstMeetingTracked:
    """Test that first_meeting flag is still tracked correctly."""

    def test_first_meeting_true_initially(self, hex_crawl_engine, mock_controller):
        """Verify first_meeting is True on first interaction."""
        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        assert result["first_meeting"] is True

    def test_first_meeting_false_on_subsequent(self, hex_crawl_engine, mock_controller):
        """Verify first_meeting is False on subsequent interactions."""
        # First interaction
        hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        # Reset mock to clear first call
        mock_controller.transition.reset_mock()

        # Second interaction
        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="merchant_tobias",
        )

        assert result["first_meeting"] is False


class TestNPCWithoutDispositionField:
    """Test handling of NPCs without explicit disposition field."""

    def test_zero_default_when_no_disposition_field(
        self, hex_crawl_engine, mock_controller, hex_with_npcs
    ):
        """Verify 0 default is used when NPC has no disposition field."""
        # Create NPC without disposition attribute
        neutral_npc = HexNPC(
            npc_id="guard_erik",
            name="Erik the Guard",
            description="A stoic guard",
        )
        hex_with_npcs.npcs.append(neutral_npc)

        hex_crawl_engine.get_npcs_at_poi.return_value.append(
            {"npc_id": "guard_erik", "name": "Erik the Guard"}
        )

        # Set faction state
        hex_crawl_engine.get_faction_state.return_value.party_reputation = {
            "guard_erik": 5,
        }

        result = hex_crawl_engine.interact_with_npc(
            hex_id="0703",
            npc_id="guard_erik",
        )

        # Base (5) + NPC default (0) = 5
        assert result["disposition"] == 5
