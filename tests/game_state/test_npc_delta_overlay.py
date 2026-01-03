"""
Deterministic tests for NPC delta overlay (P9.5).

Verifies that:
1. ActiveNPC combines base NPC + delta correctly
2. get_active_npc returns combined view model
3. is_available() reflects dead/removed state
4. get_effective_disposition() derives string from numeric
5. met_before tracking works correctly
6. get_active_npcs_in_hex returns all NPCs
7. get_available_npcs_in_hex filters unavailable NPCs
"""

import pytest
from unittest.mock import MagicMock, PropertyMock

from src.game_state.session_manager import (
    ActiveNPC,
    NPCStateDelta,
    HexStateDelta,
    GameSession,
    SessionManager,
)
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine
from src.data_models import (
    HexLocation,
    HexNPC,
    FactionState,
)
from src.game_state.global_controller import GlobalController


@pytest.fixture
def base_npc():
    """Create a base HexNPC."""
    return HexNPC(
        npc_id="merchant_tobias",
        name="Tobias the Merchant",
        description="A portly merchant with keen eyes",
        kindred="human",
        alignment="Neutral",
        title="Master Merchant",
        demeanor=["friendly", "cautious"],
        speech="Speaks with a slight lisp",
        languages=["Common", "Elvish"],
        desires=["Profit", "Safety"],
        secrets=["Has a hidden cache"],
        possessions=["Lockbox", "Ledger"],
        location="Market stall",
        faction="Merchants Guild",
        loyalty="loyal",
    )


@pytest.fixture
def hostile_npc():
    """Create a hostile base NPC."""
    return HexNPC(
        npc_id="bandit_scar",
        name="Scar the Bandit",
        description="A scarred ruffian",
        kindred="human",
        alignment="Chaotic",
        demeanor=["hostile", "greedy"],
        is_combatant=True,
    )


@pytest.fixture
def hex_with_npcs(base_npc, hostile_npc):
    """Create hex data with NPCs."""
    return HexLocation(
        hex_id="0703",
        name="Market Town",
        terrain_type="settlement",
        npcs=[base_npc, hostile_npc],
    )


@pytest.fixture
def mock_controller():
    """Create a mock controller with session manager."""
    controller = MagicMock(spec=GlobalController)

    # Set up session manager with a session
    session_manager = MagicMock(spec=SessionManager)
    session = MagicMock(spec=GameSession)
    session.hex_deltas = {}
    session_manager.current_session = session
    controller._session_manager = session_manager

    return controller


@pytest.fixture
def hex_crawl_engine(mock_controller, hex_with_npcs):
    """Create hex crawl engine with test data."""
    engine = HexCrawlEngine(controller=mock_controller)
    engine._hex_data["0703"] = hex_with_npcs

    # Set up faction state
    faction_state = FactionState(hex_id="0703")
    faction_state.party_reputation = {
        "merchant_tobias": 30,  # Friendly
        "bandit_scar": -50,  # Hostile
    }
    engine._faction_states = {"0703": faction_state}
    engine.get_faction_state = MagicMock(return_value=faction_state)

    return engine


class TestActiveNPCFromBaseNPC:
    """Test ActiveNPC.from_base_npc() factory method."""

    def test_creates_active_npc_with_base_fields(self, base_npc):
        """Verify base NPC fields are copied correctly."""
        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
        )

        assert active.npc_id == "merchant_tobias"
        assert active.name == "Tobias the Merchant"
        assert active.description == "A portly merchant with keen eyes"
        assert active.kindred == "human"
        assert active.title == "Master Merchant"
        assert active.demeanor == ["friendly", "cautious"]
        assert active.faction == "Merchants Guild"

    def test_disposition_numeric_passed_through(self, base_npc):
        """Verify disposition_numeric is set correctly."""
        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
            disposition_numeric=45,
        )

        assert active.disposition_numeric == 45

    def test_met_before_passed_through(self, base_npc):
        """Verify met_before is set correctly."""
        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
            met_before=True,
        )

        assert active.met_before is True


class TestActiveNPCDeltaOverlay:
    """Test that delta overlay is applied correctly."""

    def test_delta_overrides_disposition(self, base_npc):
        """Verify delta disposition overrides base."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            disposition="hostile",  # Override to hostile
        )

        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
            delta=delta,
        )

        assert active.disposition == "hostile"
        assert active.has_delta is True

    def test_delta_sets_is_dead(self, base_npc):
        """Verify is_dead from delta."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            is_dead=True,
        )

        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
            delta=delta,
        )

        assert active.is_dead is True
        assert active.is_available() is False

    def test_delta_sets_is_removed(self, base_npc):
        """Verify is_removed from delta."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            is_removed=True,
        )

        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
            delta=delta,
        )

        assert active.is_removed is True
        assert active.is_available() is False

    def test_delta_session_tracking_copied(self, base_npc):
        """Verify session tracking fields are copied from delta."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            quests_given=["fetch_herbs"],
            topics_discussed=["weather", "prices"],
            secrets_revealed=["hidden_cache"],
        )

        active = ActiveNPC.from_base_npc(
            base_npc=base_npc,
            hex_id="0703",
            delta=delta,
        )

        assert active.quests_given == ["fetch_herbs"]
        assert active.topics_discussed == ["weather", "prices"]
        assert active.secrets_revealed == ["hidden_cache"]


class TestActiveNPCIsAvailable:
    """Test is_available() method."""

    def test_available_by_default(self, base_npc):
        """Verify NPC is available by default."""
        active = ActiveNPC.from_base_npc(base_npc, "0703")
        assert active.is_available() is True

    def test_unavailable_when_dead(self, base_npc):
        """Verify dead NPCs are unavailable."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            is_dead=True,
        )
        active = ActiveNPC.from_base_npc(base_npc, "0703", delta=delta)
        assert active.is_available() is False

    def test_unavailable_when_removed(self, base_npc):
        """Verify removed NPCs are unavailable."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            is_removed=True,
        )
        active = ActiveNPC.from_base_npc(base_npc, "0703", delta=delta)
        assert active.is_available() is False


class TestActiveNPCGetEffectiveDisposition:
    """Test get_effective_disposition() method."""

    def test_returns_delta_disposition_when_set(self, base_npc):
        """Verify explicit disposition is returned."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            disposition="hostile",
        )
        active = ActiveNPC.from_base_npc(base_npc, "0703", delta=delta)
        assert active.get_effective_disposition() == "hostile"

    def test_friendly_from_high_numeric(self, base_npc):
        """Verify 'friendly' derived from high disposition_numeric."""
        active = ActiveNPC.from_base_npc(
            base_npc, "0703", disposition_numeric=50
        )
        assert active.get_effective_disposition() == "friendly"

    def test_hostile_from_low_numeric(self, base_npc):
        """Verify 'hostile' derived from low disposition_numeric."""
        active = ActiveNPC.from_base_npc(
            base_npc, "0703", disposition_numeric=-50
        )
        assert active.get_effective_disposition() == "hostile"

    def test_neutral_from_middle_numeric(self, base_npc):
        """Verify 'neutral' derived from middle disposition_numeric."""
        active = ActiveNPC.from_base_npc(
            base_npc, "0703", disposition_numeric=10
        )
        assert active.get_effective_disposition() == "neutral"

    def test_boundary_at_25(self, base_npc):
        """Verify boundary value 25 is 'friendly'."""
        active = ActiveNPC.from_base_npc(
            base_npc, "0703", disposition_numeric=25
        )
        assert active.get_effective_disposition() == "friendly"

    def test_boundary_at_negative_25(self, base_npc):
        """Verify boundary value -25 is 'hostile'."""
        active = ActiveNPC.from_base_npc(
            base_npc, "0703", disposition_numeric=-25
        )
        assert active.get_effective_disposition() == "hostile"


class TestHexCrawlEngineGetActiveNPC:
    """Test HexCrawlEngine.get_active_npc() helper."""

    def test_returns_active_npc_for_valid_id(self, hex_crawl_engine):
        """Verify get_active_npc returns correct NPC."""
        active = hex_crawl_engine.get_active_npc("0703", "merchant_tobias")

        assert active is not None
        assert active.npc_id == "merchant_tobias"
        assert active.name == "Tobias the Merchant"

    def test_includes_disposition_from_faction_state(self, hex_crawl_engine):
        """Verify disposition_numeric comes from faction state."""
        active = hex_crawl_engine.get_active_npc("0703", "merchant_tobias")

        assert active.disposition_numeric == 30  # From fixture

    def test_returns_none_for_unknown_hex(self, hex_crawl_engine):
        """Verify None returned for unknown hex."""
        active = hex_crawl_engine.get_active_npc("9999", "merchant_tobias")
        assert active is None

    def test_returns_none_for_unknown_npc(self, hex_crawl_engine):
        """Verify None returned for unknown NPC ID."""
        active = hex_crawl_engine.get_active_npc("0703", "unknown_npc")
        assert active is None

    def test_applies_delta_when_present(self, hex_crawl_engine, mock_controller):
        """Verify delta is applied when present in session."""
        # Set up a delta in the session
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            is_hostile=True,
            quests_given=["help_quest"],
        )
        hex_delta = HexStateDelta(hex_id="0703")
        hex_delta.npc_deltas["merchant_tobias"] = delta
        mock_controller._session_manager.current_session.hex_deltas["0703"] = hex_delta

        active = hex_crawl_engine.get_active_npc("0703", "merchant_tobias")

        assert active.is_hostile is True
        assert active.quests_given == ["help_quest"]
        assert active.has_delta is True
        assert active.met_before is True


class TestHexCrawlEngineGetActiveNPCsInHex:
    """Test HexCrawlEngine.get_active_npcs_in_hex() helper."""

    def test_returns_all_npcs_in_hex(self, hex_crawl_engine):
        """Verify all NPCs in hex are returned."""
        npcs = hex_crawl_engine.get_active_npcs_in_hex("0703")

        assert len(npcs) == 2
        npc_ids = {npc.npc_id for npc in npcs}
        assert npc_ids == {"merchant_tobias", "bandit_scar"}

    def test_returns_empty_for_unknown_hex(self, hex_crawl_engine):
        """Verify empty list for unknown hex."""
        npcs = hex_crawl_engine.get_active_npcs_in_hex("9999")
        assert npcs == []

    def test_returns_empty_for_hex_without_npcs(self, hex_crawl_engine):
        """Verify empty list for hex without NPCs."""
        # Add a hex without NPCs
        empty_hex = HexLocation(
            hex_id="0101",
            name="Empty Hex",
            terrain_type="forest",
            npcs=[],
        )
        hex_crawl_engine._hex_data["0101"] = empty_hex

        npcs = hex_crawl_engine.get_active_npcs_in_hex("0101")
        assert npcs == []


class TestHexCrawlEngineGetAvailableNPCs:
    """Test HexCrawlEngine.get_available_npcs_in_hex() helper."""

    def test_filters_dead_npcs(self, hex_crawl_engine, mock_controller):
        """Verify dead NPCs are filtered out."""
        # Mark one NPC as dead
        delta = NPCStateDelta(
            npc_id="bandit_scar",
            hex_id="0703",
            is_dead=True,
        )
        hex_delta = HexStateDelta(hex_id="0703")
        hex_delta.npc_deltas["bandit_scar"] = delta
        mock_controller._session_manager.current_session.hex_deltas["0703"] = hex_delta

        npcs = hex_crawl_engine.get_available_npcs_in_hex("0703")

        assert len(npcs) == 1
        assert npcs[0].npc_id == "merchant_tobias"

    def test_filters_removed_npcs(self, hex_crawl_engine, mock_controller):
        """Verify removed NPCs are filtered out."""
        # Mark one NPC as removed
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            is_removed=True,
        )
        hex_delta = HexStateDelta(hex_id="0703")
        hex_delta.npc_deltas["merchant_tobias"] = delta
        mock_controller._session_manager.current_session.hex_deltas["0703"] = hex_delta

        npcs = hex_crawl_engine.get_available_npcs_in_hex("0703")

        assert len(npcs) == 1
        assert npcs[0].npc_id == "bandit_scar"

    def test_returns_all_when_none_filtered(self, hex_crawl_engine):
        """Verify all NPCs returned when none are dead/removed."""
        npcs = hex_crawl_engine.get_available_npcs_in_hex("0703")
        assert len(npcs) == 2


class TestNoSessionManagerGraceful:
    """Test graceful handling when no session manager."""

    def test_get_active_npc_without_session_manager(self, hex_with_npcs):
        """Verify get_active_npc works without session manager."""
        controller = MagicMock(spec=GlobalController)
        controller._session_manager = None

        engine = HexCrawlEngine(controller=controller)
        engine._hex_data["0703"] = hex_with_npcs

        # Set up faction state
        faction_state = FactionState(hex_id="0703")
        engine.get_faction_state = MagicMock(return_value=faction_state)

        active = engine.get_active_npc("0703", "merchant_tobias")

        assert active is not None
        assert active.npc_id == "merchant_tobias"
        assert active.has_delta is False
        assert active.met_before is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_npc_with_minimal_fields(self, hex_crawl_engine):
        """Verify handling of NPC with only required fields."""
        minimal_npc = HexNPC(
            npc_id="minimal",
            name="Minimal NPC",
            description="A basic NPC",
        )
        hex_data = hex_crawl_engine._hex_data["0703"]
        hex_data.npcs.append(minimal_npc)

        active = hex_crawl_engine.get_active_npc("0703", "minimal")

        assert active is not None
        assert active.kindred == "human"  # Default
        assert active.demeanor == []  # Empty list default

    def test_disposition_numeric_zero_is_neutral(self, base_npc):
        """Verify disposition_numeric of 0 is 'neutral'."""
        active = ActiveNPC.from_base_npc(
            base_npc, "0703", disposition_numeric=0
        )
        assert active.get_effective_disposition() == "neutral"

    def test_lists_are_copies_not_references(self, base_npc):
        """Verify lists are copied, not referenced."""
        delta = NPCStateDelta(
            npc_id="merchant_tobias",
            hex_id="0703",
            quests_given=["quest1"],
        )

        active = ActiveNPC.from_base_npc(base_npc, "0703", delta=delta)

        # Modify the original delta's list
        delta.quests_given.append("quest2")

        # Active NPC's list should not be affected
        assert active.quests_given == ["quest1"]
