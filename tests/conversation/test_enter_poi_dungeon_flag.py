"""
Tests for wilderness:enter_poi dungeon flag handling.

Verifies that when HexCrawlEngine.enter_poi returns {"success": False, "is_dungeon": True},
the action registry properly returns {"success": False, ..., "is_dungeon": True} instead
of incorrectly returning {"success": True}.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.conversation.action_registry import get_default_registry, reset_registry
from src.game_state.state_machine import GameState


class MockHexCrawl:
    """Mock HexCrawlEngine for testing enter_poi behavior."""

    def __init__(self, enter_poi_result=None):
        self._enter_poi_result = enter_poi_result or {"success": True, "message": "You enter."}
        self.current_hex_id = "0103"

    def enter_poi(self, hex_id):
        return self._enter_poi_result


class MockVirtualDM:
    """Mock VirtualDM for testing action registry."""

    def __init__(self, hex_crawl=None):
        self.hex_crawl = hex_crawl or MockHexCrawl()
        self.current_state = GameState.WILDERNESS_TRAVEL


class TestEnterPoiDungeonFlag:
    """Tests for dungeon flag handling in wilderness:enter_poi."""

    def test_dungeon_poi_returns_success_false(self):
        """When enter_poi returns is_dungeon=True, action should return success=False."""
        reset_registry()
        registry = get_default_registry()

        # Mock engine returns dungeon flag
        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": False,
            "is_dungeon": True,
            "message": "This is a dungeon entrance. Use enter_dungeon action.",
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        assert result["success"] is False, "enter_poi should return success=False for dungeon POIs"

    def test_dungeon_poi_passes_through_is_dungeon_flag(self):
        """When enter_poi returns is_dungeon=True, action should include is_dungeon in result."""
        reset_registry()
        registry = get_default_registry()

        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": False,
            "is_dungeon": True,
            "message": "This is a dungeon entrance.",
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        assert result.get("is_dungeon") is True, "enter_poi should pass through is_dungeon flag"

    def test_dungeon_poi_preserves_message(self):
        """When enter_poi returns is_dungeon=True, action should preserve the message."""
        reset_registry()
        registry = get_default_registry()

        expected_message = "This is a dungeon entrance. Use wilderness:enter_dungeon."
        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": False,
            "is_dungeon": True,
            "message": expected_message,
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        assert result["message"] == expected_message

    def test_normal_poi_returns_success_true(self):
        """When enter_poi returns success (not dungeon), action should return success=True."""
        reset_registry()
        registry = get_default_registry()

        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": True,
            "message": "You enter the tavern.",
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        assert result["success"] is True

    def test_normal_poi_has_no_dungeon_flag(self):
        """When enter_poi returns success (not dungeon), action should not include is_dungeon."""
        reset_registry()
        registry = get_default_registry()

        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": True,
            "message": "You enter the tavern.",
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        assert "is_dungeon" not in result or result.get("is_dungeon") is False

    def test_requires_entry_check_still_works(self):
        """When enter_poi requires entry check, action should return success=False."""
        reset_registry()
        registry = get_default_registry()

        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": False,
            "requires_entry_check": True,
            "message": "The gate is locked.",
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        assert result["success"] is False
        assert "locked" in result["message"]

    def test_dungeon_check_before_entry_check(self):
        """Dungeon check should be evaluated before entry check."""
        reset_registry()
        registry = get_default_registry()

        # Edge case: both flags set (shouldn't happen, but dungeon takes priority)
        hex_crawl = MockHexCrawl(enter_poi_result={
            "success": False,
            "is_dungeon": True,
            "requires_entry_check": True,
            "message": "This is a dungeon entrance.",
        })
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        result = registry.execute(dm, "wilderness:enter_poi", {})

        # Dungeon flag should be in result (dungeon check runs first)
        assert result.get("is_dungeon") is True


class TestEnterPoiHexIdParam:
    """Tests for hex_id parameter handling."""

    def test_uses_provided_hex_id(self):
        """When hex_id is provided, it should be passed to enter_poi."""
        reset_registry()
        registry = get_default_registry()

        hex_crawl = MockHexCrawl()
        hex_crawl.enter_poi = MagicMock(return_value={"success": True, "message": "Entered."})
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        registry.execute(dm, "wilderness:enter_poi", {"hex_id": "0709"})

        hex_crawl.enter_poi.assert_called_once_with("0709")

    def test_uses_current_hex_if_not_provided(self):
        """When hex_id is not provided, should use current_hex_id."""
        reset_registry()
        registry = get_default_registry()

        hex_crawl = MockHexCrawl()
        hex_crawl.current_hex_id = "0505"
        hex_crawl.enter_poi = MagicMock(return_value={"success": True, "message": "Entered."})
        dm = MockVirtualDM(hex_crawl=hex_crawl)

        registry.execute(dm, "wilderness:enter_poi", {})

        hex_crawl.enter_poi.assert_called_once_with("0505")
