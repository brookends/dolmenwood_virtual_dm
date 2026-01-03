"""
Tests for P1-9: Verify no duplicate method definitions in HexCrawlEngine.

This test ensures that enter_dungeon_from_poi has a single canonical
definition, preventing method shadowing issues.
"""

import pytest
import inspect


class TestNoDuplicateMethods:
    """Verify no duplicate method definitions in HexCrawlEngine."""

    def test_enter_dungeon_from_poi_single_definition(self):
        """enter_dungeon_from_poi should have only one definition."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        # Check that the method exists
        assert hasattr(HexCrawlEngine, "enter_dungeon_from_poi")

        # Get source code and count definition occurrences
        source_file = inspect.getfile(HexCrawlEngine)
        with open(source_file, "r") as f:
            source = f.read()

        # Count occurrences of the method definition
        definition_count = source.count("def enter_dungeon_from_poi(")

        assert definition_count == 1, (
            f"Expected 1 definition of enter_dungeon_from_poi, found {definition_count}"
        )

    def test_hex_crawl_engine_imports_correctly(self):
        """HexCrawlEngine should import without errors."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        # Basic sanity check
        assert HexCrawlEngine is not None

    def test_enter_dungeon_from_poi_signature(self):
        """enter_dungeon_from_poi should have expected signature."""
        from src.hex_crawl.hex_crawl_engine import HexCrawlEngine

        sig = inspect.signature(HexCrawlEngine.enter_dungeon_from_poi)
        param_names = list(sig.parameters.keys())

        # Should have self, hex_id, and optionally poi_name
        assert "self" in param_names
        assert "hex_id" in param_names
        # The canonical version uses poi_name, not dungeon_engine
        assert "dungeon_engine" not in param_names
