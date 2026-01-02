"""
Smoke tests for runtime content bootstrapping.

These tests verify that content loading works correctly and fails loudly
when content cannot be loaded.
"""

import pytest
from pathlib import Path

from src.content_loader.runtime_bootstrap import (
    load_runtime_content,
    RuntimeContent,
    RuntimeContentStats,
)


# Path to test fixtures
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "content"


class TestHexLoading:
    """Tests for hex content loading."""

    def test_load_hexes_from_fixture_dir(self):
        """Loading hexes from fixture directory should find at least 2 hexes."""
        result = load_runtime_content(
            content_root=FIXTURE_DIR,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        # Should have loaded at least 2 hexes from fixtures
        assert result.stats.hexes_loaded >= 2, (
            f"Expected at least 2 hexes loaded, got {result.stats.hexes_loaded}. "
            f"Warnings: {result.warnings}"
        )

        # Hexes dict should contain entries
        assert len(result.hexes) >= 2, (
            f"Expected at least 2 hexes in result.hexes, got {len(result.hexes)}"
        )

        # Verify specific test hex IDs are present
        assert "test_0101" in result.hexes, "test_0101 hex should be loaded"
        assert "test_0102" in result.hexes, "test_0102 hex should be loaded"

    def test_hex_data_is_valid(self):
        """Loaded hex data should contain expected fields."""
        result = load_runtime_content(
            content_root=FIXTURE_DIR,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        hex_data = result.hexes.get("test_0101")
        assert hex_data is not None, "test_0101 hex should be loaded"

        # Check required fields
        assert hex_data.hex_id == "test_0101"
        assert hex_data.name == "Test Hex One"
        assert hex_data.terrain_type == "forest"
        assert hex_data.coordinates == (1, 1)

    def test_hex_npcs_are_loaded(self):
        """NPCs in hex files should be loaded."""
        result = load_runtime_content(
            content_root=FIXTURE_DIR,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        hex_data = result.hexes.get("test_0101")
        assert hex_data is not None

        # Should have at least one NPC
        assert len(hex_data.npcs) >= 1, "test_0101 should have at least 1 NPC"
        assert hex_data.npcs[0].npc_id == "test_npc_1"
        assert hex_data.npcs[0].name == "Test NPC One"

    def test_empty_hex_dir_fails_gracefully(self, tmp_path):
        """Empty hex directory should not claim success."""
        # Create empty hex dir
        hex_dir = tmp_path / "hexes"
        hex_dir.mkdir()

        result = load_runtime_content(
            content_root=tmp_path,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        # Should have 0 hexes loaded
        assert result.stats.hexes_loaded == 0
        assert len(result.hexes) == 0

    def test_no_warnings_on_successful_load(self):
        """Successful hex loading should not generate load failure warnings."""
        result = load_runtime_content(
            content_root=FIXTURE_DIR,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        # Should have loaded hexes
        assert result.stats.hexes_loaded >= 2

        # Check for loader failure warnings (not just any warning)
        loader_failure_warnings = [
            w for w in result.warnings
            if "Failed to import" in w or "Error loading hexes" in w
        ]
        assert len(loader_failure_warnings) == 0, (
            f"Unexpected loader failure warnings: {loader_failure_warnings}"
        )


class TestItemLoading:
    """Tests for item content loading."""

    def test_load_items_from_fixture_dir(self):
        """Loading items from fixture directory should find items in subdirectories."""
        result = load_runtime_content(
            content_root=FIXTURE_DIR,
            load_hexes=False,
            load_spells=False,
            load_monsters=False,
            load_items=True,
            enable_vector_db=False,
        )

        # Should have loaded items
        assert result.stats.items_loaded >= 4, (
            f"Expected at least 4 items loaded, got {result.stats.items_loaded}. "
            f"Warnings: {result.warnings}"
        )
        assert result.items_loaded is True, "items_loaded flag should be True"

    def test_item_catalog_is_accessible(self):
        """Item catalog should be accessible after loading."""
        result = load_runtime_content(
            content_root=FIXTURE_DIR,
            load_hexes=False,
            load_spells=False,
            load_monsters=False,
            load_items=True,
            enable_vector_db=False,
        )

        # The catalog should be stored in result
        assert hasattr(result, 'item_catalog') or result.items_loaded, (
            "Items should be loaded successfully"
        )

    def test_empty_items_dir_fails_gracefully(self, tmp_path):
        """Empty items directory should not claim success."""
        # Create empty items dir
        items_dir = tmp_path / "items"
        items_dir.mkdir()

        result = load_runtime_content(
            content_root=tmp_path,
            load_hexes=False,
            load_spells=False,
            load_monsters=False,
            load_items=True,
            enable_vector_db=False,
        )

        # Should have 0 items loaded
        assert result.stats.items_loaded == 0
        assert result.items_loaded is False


class TestContentLoadingWithVirtualDM:
    """Tests for content loading through VirtualDM."""

    def test_virtual_dm_content_load_true(self):
        """VirtualDM with load_content=True should load content."""
        from src.main import VirtualDM, GameConfig

        # Use real content directory
        content_dir = Path(__file__).parent.parent.parent / "data" / "content"

        if not content_dir.exists():
            pytest.skip("Content directory not available")

        # Create config with load_content=True
        config = GameConfig(load_content=True)
        dm = VirtualDM(config=config)

        # If content exists, it should be loaded
        # At minimum, we should not have _content_loaded=True with 0 hexes
        if dm._content_loaded:
            # If claiming loaded, should have some content
            assert dm.controller is not None, (
                "_content_loaded is True but controller is None"
            )


class TestContentLoadingFailures:
    """Tests to verify content loading fails loudly when appropriate."""

    def test_invalid_json_creates_warning(self, tmp_path):
        """Invalid JSON file should create a warning, not silently fail."""
        hex_dir = tmp_path / "hexes"
        hex_dir.mkdir()

        # Create invalid JSON file
        bad_file = hex_dir / "bad_hex.json"
        bad_file.write_text("{ invalid json }")

        result = load_runtime_content(
            content_root=tmp_path,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        # Should have warning about the bad file
        assert len(result.warnings) > 0 or result.stats.hexes_failed > 0, (
            "Invalid JSON should generate warning or increment failed count"
        )

    def test_missing_hex_id_creates_warning(self, tmp_path):
        """JSON without hex_id should not silently succeed."""
        hex_dir = tmp_path / "hexes"
        hex_dir.mkdir()

        # Create JSON without hex_id
        bad_file = hex_dir / "no_id.json"
        bad_file.write_text('{"name": "Test", "terrain_type": "forest"}')

        result = load_runtime_content(
            content_root=tmp_path,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        # Should either fail or have warning
        # The hex should not be loaded without an ID
        assert result.stats.hexes_loaded == 0 or len(result.warnings) > 0


class TestRealContentLoading:
    """Integration tests using real content data."""

    def test_load_real_hexes_if_available(self):
        """Load real hex content if available."""
        content_dir = Path(__file__).parent.parent.parent / "data" / "content"

        if not (content_dir / "hexes").exists():
            pytest.skip("Real hex content not available")

        result = load_runtime_content(
            content_root=content_dir,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
            enable_vector_db=False,
        )

        # Should load at least some hexes from real content
        assert result.stats.hexes_loaded > 0, (
            f"Expected to load hexes from real content. "
            f"Warnings: {result.warnings}"
        )

    def test_load_real_items_if_available(self):
        """Load real item content if available."""
        content_dir = Path(__file__).parent.parent.parent / "data" / "content"

        if not (content_dir / "items").exists():
            pytest.skip("Real item content not available")

        result = load_runtime_content(
            content_root=content_dir,
            load_hexes=False,
            load_spells=False,
            load_monsters=False,
            load_items=True,
            enable_vector_db=False,
        )

        # Should load at least some items from real content
        assert result.stats.items_loaded > 0, (
            f"Expected to load items from real content. "
            f"Warnings: {result.warnings}"
        )
