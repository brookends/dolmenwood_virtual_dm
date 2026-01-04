"""
Tests for POI secret discovery system including vault secret door.

This test suite validates:
- Searching locations can reveal secrets
- reveals_secret adds to _discovered_secrets
- Hidden POIs become visible after secret discovery
- Navigation to child POIs after discovery
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_loader.content_pipeline import ContentPipeline
from src.content_loader.hex_loader import HexDataLoader
from src.data_models import DiceRoller, GameDate, PointOfInterest
from src.game_state.global_controller import GlobalController
from src.hex_crawl.hex_crawl_engine import HexCrawlEngine


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pipeline():
    """Create a content pipeline with hex 0109 loaded."""
    pipeline = ContentPipeline()
    loader = HexDataLoader(pipeline)
    result = loader.load_file(
        Path("data/content/hexes/0109_lady_borrid_and_murkins_army.json")
    )
    assert result.success, f"Failed to load hex 0109: {result.errors}"
    return pipeline


@pytest.fixture
def controller():
    """Create a GlobalController."""
    controller = GlobalController()
    controller.world_state.current_date = GameDate(year=1, month=3, day=15)
    return controller


@pytest.fixture
def engine(controller, pipeline):
    """Create a HexCrawlEngine with hex 0109 loaded."""
    engine = HexCrawlEngine(controller)
    engine._hex_data["0109"] = pipeline.get_hex("0109")
    engine._current_hex = "0109"
    return engine


@pytest.fixture
def engine_at_lodge(engine):
    """Engine positioned at Lady Borrid's Hunting Lodge."""
    engine._current_poi = "Lady Borrid's Hunting Lodge"
    return engine


# =============================================================================
# CONCEALED ITEM DATA TESTS
# =============================================================================


class TestConcealedItemWithRevealsSecret:
    """Test that concealed items can have reveals_secret field."""

    def test_vault_door_exists_in_concealed_items(self, pipeline):
        """Lodge should have vault door in concealed items."""
        hex_data = pipeline.get_hex("0109")
        lodge = next(
            p for p in hex_data.points_of_interest
            if p.name == "Lady Borrid's Hunting Lodge"
        )

        vault_door = None
        for item in lodge.concealed_items:
            if item.get("name") == "Secret Vault Door":
                vault_door = item
                break

        assert vault_door is not None, "Vault door should exist in concealed items"
        assert vault_door.get("reveals_secret") == "hidden_vault"
        assert vault_door.get("hidden_in") == "cellars"

    def test_hidden_vault_poi_exists(self, pipeline):
        """Hidden Vault POI should exist with requires_discovery."""
        hex_data = pipeline.get_hex("0109")
        vault = None
        for poi in hex_data.points_of_interest:
            if poi.name == "Lady Borrid's Hidden Vault":
                vault = poi
                break

        assert vault is not None, "Hidden Vault POI should exist"
        assert vault.requires_discovery == "hidden_vault"
        assert vault.parent_poi == "Lady Borrid's Hunting Lodge"


# =============================================================================
# POI VISIBILITY TESTS
# =============================================================================


class TestHiddenPOIVisibility:
    """Test that POIs with requires_discovery are hidden until secret found."""

    def test_vault_not_visible_before_discovery(self, engine):
        """Hidden Vault should not be visible before secret discovered."""
        hex_data = engine._hex_data["0109"]

        for poi in hex_data.points_of_interest:
            if poi.name == "Lady Borrid's Hidden Vault":
                assert not poi.is_visible(engine._discovered_secrets)
                return

        pytest.fail("Hidden Vault POI not found")

    def test_vault_visible_after_discovery(self, engine):
        """Hidden Vault should be visible after secret discovered."""
        engine._discovered_secrets.add("hidden_vault")
        hex_data = engine._hex_data["0109"]

        for poi in hex_data.points_of_interest:
            if poi.name == "Lady Borrid's Hidden Vault":
                assert poi.is_visible(engine._discovered_secrets)
                return

        pytest.fail("Hidden Vault POI not found")

    def test_other_pois_always_visible(self, engine):
        """Lodge and Camp should be visible without any secrets."""
        hex_data = engine._hex_data["0109"]

        lodge = next(
            p for p in hex_data.points_of_interest
            if p.name == "Lady Borrid's Hunting Lodge"
        )
        camp = next(
            p for p in hex_data.points_of_interest
            if p.name == "Murkin's Army"
        )

        assert lodge.is_visible(engine._discovered_secrets)
        assert camp.is_visible(engine._discovered_secrets)


# =============================================================================
# SEARCH AND SECRET DISCOVERY TESTS
# =============================================================================


class TestSearchRevealsSecret:
    """Test that searching can reveal secrets."""

    def test_search_cellars_with_high_roll_finds_vault(self, engine_at_lodge):
        """Searching cellars with high roll should find vault door."""
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6  # High roll ensures success
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            assert result.get("success") is True
            assert result.get("found_count", 0) > 0

            # Check that vault door was found
            found_names = [item.get("name") for item in result.get("items_found", [])]
            assert "Secret Vault Door" in found_names

    def test_finding_vault_door_reveals_secret(self, engine_at_lodge):
        """Finding vault door should add to discovered secrets."""
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6  # High roll ensures success
            mock_roll.return_value = mock_result

            # Before search
            assert "hidden_vault" not in engine_at_lodge._discovered_secrets

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            # After search (if vault door found)
            if any(item.get("name") == "Secret Vault Door" for item in result.get("items_found", [])):
                assert "hidden_vault" in engine_at_lodge._discovered_secrets

    def test_secrets_revealed_in_result(self, engine_at_lodge):
        """Result should include secrets_revealed field."""
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            if any(item.get("reveals_secret") for item in result.get("items_found", [])):
                assert "secrets_revealed" in result
                assert "hidden_vault" in result["secrets_revealed"]

    def test_newly_accessible_locations_in_result(self, engine_at_lodge):
        """Result should include newly accessible locations."""
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            if "hidden_vault" in result.get("secrets_revealed", []):
                assert "newly_accessible_locations" in result
                new_locs = result["newly_accessible_locations"]
                assert any(loc["name"] == "Lady Borrid's Hidden Vault" for loc in new_locs)

    def test_search_message_mentions_hidden_location(self, engine_at_lodge):
        """Message should mention hidden location when secret revealed."""
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            if "secrets_revealed" in result:
                assert "hidden location" in result.get("message", "").lower()

    def test_low_roll_does_not_find_vault(self, engine_at_lodge):
        """Low search roll should not find vault door."""
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 1  # Low roll
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            found_names = [item.get("name") for item in result.get("items_found", [])]
            assert "Secret Vault Door" not in found_names
            assert "hidden_vault" not in engine_at_lodge._discovered_secrets


# =============================================================================
# NAVIGATION TESTS
# =============================================================================


class TestNavigationToDiscoveredPOI:
    """Test navigating to POIs after discovery."""

    def test_vault_not_in_accessible_before_discovery(self, engine_at_lodge):
        """Hidden Vault should not appear in accessible POIs before discovery."""
        accessible = engine_at_lodge.get_accessible_pois("0109")

        accessible_names = [poi.get("name") for poi in accessible]
        assert "Lady Borrid's Hidden Vault" not in accessible_names

    def test_vault_in_accessible_after_discovery(self, engine_at_lodge):
        """Hidden Vault should appear in accessible POIs after discovery."""
        engine_at_lodge._discovered_secrets.add("hidden_vault")

        accessible = engine_at_lodge.get_accessible_pois("0109")

        accessible_names = [poi.get("name") for poi in accessible]
        assert "Lady Borrid's Hidden Vault" in accessible_names

    def test_can_enter_vault_after_discovery(self, engine_at_lodge):
        """Should be able to enter vault after discovery."""
        engine_at_lodge._discovered_secrets.add("hidden_vault")

        result = engine_at_lodge.navigate_to_child_poi(
            "0109",
            "Lady Borrid's Hidden Vault",
        )

        assert result.get("success") is True
        assert engine_at_lodge._current_poi == "Lady Borrid's Hidden Vault"

    def test_cannot_enter_vault_before_discovery(self, engine_at_lodge):
        """Should not be able to enter vault before discovery."""
        result = engine_at_lodge.navigate_to_child_poi(
            "0109",
            "Lady Borrid's Hidden Vault",
        )

        assert result.get("success") is False
        assert "cannot find" in result.get("error", "").lower()


# =============================================================================
# DISCOVERED SECRETS TRACKING TESTS
# =============================================================================


class TestDiscoveredSecretsTracking:
    """Test that discovered secrets are properly tracked."""

    def test_get_discovered_secrets(self, engine):
        """get_discovered_secrets should return copy of secrets."""
        engine._discovered_secrets.add("test_secret")

        secrets = engine.get_discovered_secrets()
        assert "test_secret" in secrets

        # Modifying returned set should not affect internal state
        secrets.add("another_secret")
        assert "another_secret" not in engine._discovered_secrets

    def test_has_discovered_secret(self, engine):
        """has_discovered_secret should check correctly."""
        assert not engine.has_discovered_secret("hidden_vault")

        engine._discovered_secrets.add("hidden_vault")

        assert engine.has_discovered_secret("hidden_vault")

    def test_secret_not_re_added(self, engine_at_lodge):
        """Discovering same secret twice should not create duplicates."""
        engine_at_lodge._discovered_secrets.add("hidden_vault")

        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location(
                "0109",
                search_location="cellars",
            )

            # Should not duplicate
            assert engine_at_lodge._discovered_secrets.count("hidden_vault") if hasattr(
                engine_at_lodge._discovered_secrets, "count"
            ) else list(engine_at_lodge._discovered_secrets).count("hidden_vault") == 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestVaultDiscoveryIntegration:
    """Integration tests for the full vault discovery flow."""

    def test_full_vault_discovery_flow(self, engine_at_lodge):
        """Test complete flow: search -> discover -> navigate -> get items."""
        # Step 1: Vault is not visible
        hex_data = engine_at_lodge._hex_data["0109"]
        vault = next(
            (p for p in hex_data.points_of_interest
             if p.name == "Lady Borrid's Hidden Vault"),
            None
        )
        assert vault is not None
        assert not vault.is_visible(engine_at_lodge._discovered_secrets)

        # Step 2: Search cellars with high roll
        with patch.object(engine_at_lodge.dice, "roll") as mock_roll:
            mock_result = MagicMock()
            mock_result.total = 6
            mock_roll.return_value = mock_result

            result = engine_at_lodge.search_poi_location("0109", "cellars")

        # Step 3: Verify secret discovered
        assert "hidden_vault" in engine_at_lodge._discovered_secrets

        # Step 4: Vault is now visible
        assert vault.is_visible(engine_at_lodge._discovered_secrets)

        # Step 5: Can navigate to vault
        enter_result = engine_at_lodge.navigate_to_child_poi(
            "0109",
            "Lady Borrid's Hidden Vault",
        )
        assert enter_result.get("success") is True
        assert engine_at_lodge._current_poi == "Lady Borrid's Hidden Vault"
