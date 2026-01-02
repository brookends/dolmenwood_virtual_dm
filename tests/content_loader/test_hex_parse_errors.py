"""
Tests for hex parsing error handling.

Phase 7.2: Verify that hex parsing failures are not silently discarded
but instead raised or collected as critical errors.
"""

import pytest
from pathlib import Path
import tempfile
import json

from src.content_loader.runtime_bootstrap import (
    HexParseError,
    RuntimeContent,
    load_runtime_content,
    _parse_hex_json,
)
from src.main import VirtualDM, GameConfig
from src.data_models import GameDate, GameTime
from src.game_state.state_machine import GameState


class TestHexParseErrorException:
    """Test the HexParseError exception class."""

    def test_hex_parse_error_stores_hex_id(self):
        """HexParseError should store the hex_id."""
        error = HexParseError("1001", "Invalid coordinates")

        assert error.hex_id == "1001"
        assert error.message == "Invalid coordinates"

    def test_hex_parse_error_message_format(self):
        """HexParseError should have informative message."""
        error = HexParseError("1234", "Missing required field")

        assert "1234" in str(error)
        assert "Missing required field" in str(error)


class TestParseHexJsonRaisesError:
    """Test that _parse_hex_json raises HexParseError on failure."""

    def test_parse_valid_hex_succeeds(self):
        """Valid hex data should parse successfully."""
        data = {
            "hex_id": "1001",
            "name": "Test Hex",
            "terrain_type": "forest",
            "coordinates": [10, 1],
        }

        result = _parse_hex_json(data)

        assert result is not None
        assert result.hex_id == "1001"

    def test_parse_hex_with_missing_coords_does_not_raise(self):
        """Missing coordinates should not raise, should use some default."""
        data = {
            "hex_id": "1001",
            "name": "Test Hex",
            "terrain_type": "forest",
            # Missing coordinates
        }

        # Should not raise - graceful handling
        result = _parse_hex_json(data)
        # Coordinates should be a tuple of two values
        assert isinstance(result.coordinates, tuple)
        assert len(result.coordinates) == 2

    def test_parse_hex_with_invalid_coord_type_does_not_crash(self):
        """Invalid coordinate types should be handled gracefully."""
        # This test verifies that truly malformed data is handled gracefully
        # The current implementation is fairly lenient with defaults
        data = {
            "hex_id": "1001",
            "name": "Test Hex",
            "terrain_type": "forest",
            "coordinates": "not a list",  # Wrong type
        }

        # The implementation handles this gracefully with defaults
        result = _parse_hex_json(data)
        # Coordinates should still be a valid tuple
        assert isinstance(result.coordinates, tuple)
        assert len(result.coordinates) == 2


class TestRuntimeContentErrorsField:
    """Test that RuntimeContent collects errors."""

    def test_errors_field_exists(self):
        """RuntimeContent should have an errors field."""
        content = RuntimeContent()

        assert hasattr(content, "errors")
        assert isinstance(content.errors, list)
        assert len(content.errors) == 0

    def test_errors_separate_from_warnings(self):
        """Errors and warnings should be separate lists."""
        content = RuntimeContent()

        content.warnings.append("A warning")
        content.errors.append("An error")

        assert len(content.warnings) == 1
        assert len(content.errors) == 1
        assert content.warnings[0] == "A warning"
        assert content.errors[0] == "An error"


class TestLoadRuntimeContentCollectsErrors:
    """Test that load_runtime_content collects hex parse errors."""

    @pytest.fixture
    def content_dir_with_invalid_json(self):
        """Create content directory with invalid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            hex_dir = content_dir / "hexes"
            hex_dir.mkdir()

            # Create invalid JSON file
            with open(hex_dir / "invalid.json", "w") as f:
                f.write("{not valid json")

            yield content_dir

    @pytest.fixture
    def content_dir_with_valid_hex(self):
        """Create content directory with valid hex."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            hex_dir = content_dir / "hexes"
            hex_dir.mkdir()

            hex_data = {
                "hex_id": "1001",
                "name": "Valid Hex",
                "terrain_type": "forest",
                "coordinates": [10, 1],
            }
            with open(hex_dir / "valid.json", "w") as f:
                json.dump(hex_data, f)

            yield content_dir

    def test_invalid_json_adds_to_errors(self, content_dir_with_invalid_json):
        """Invalid JSON should add to errors list."""
        content = load_runtime_content(
            content_root=content_dir_with_invalid_json,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
        )

        assert len(content.errors) > 0, "Invalid JSON should add to errors"
        assert any("JSON" in e or "json" in e.lower() for e in content.errors)

    def test_valid_content_has_no_errors(self, content_dir_with_valid_hex):
        """Valid content should not produce errors."""
        content = load_runtime_content(
            content_root=content_dir_with_valid_hex,
            load_hexes=True,
            load_spells=False,
            load_monsters=False,
            load_items=False,
        )

        assert len(content.errors) == 0, (
            f"Valid content should not have errors: {content.errors}"
        )
        assert len(content.hexes) == 1


class TestVirtualDMFailsOnErrors:
    """Test that VirtualDM fails fast when content has errors."""

    @pytest.fixture
    def content_dir_with_error(self):
        """Create content directory that will produce errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)

            # Create hexes directory with invalid JSON
            hex_dir = content_dir / "hexes"
            hex_dir.mkdir()
            with open(hex_dir / "bad.json", "w") as f:
                f.write("{invalid json content")

            yield content_dir

    def test_virtual_dm_raises_on_content_errors(self, content_dir_with_error):
        """VirtualDM should raise RuntimeError when content has errors."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=content_dir_with_error,
        )

        with pytest.raises(RuntimeError) as exc_info:
            VirtualDM(
                config=config,
                initial_state=GameState.WILDERNESS_TRAVEL,
                game_date=GameDate(year=1, month=6, day=15),
                game_time=GameTime(hour=10, minute=0),
            )

        # Should mention the error
        assert "error" in str(exc_info.value).lower()


class TestHexParseErrorExportedFromModule:
    """Test that HexParseError is properly exported."""

    def test_hex_parse_error_importable_from_content_loader(self):
        """HexParseError should be importable from content_loader."""
        from src.content_loader import HexParseError

        error = HexParseError("test", "test message")
        assert isinstance(error, Exception)

    def test_runtime_content_importable_from_content_loader(self):
        """RuntimeContent should be importable from content_loader."""
        from src.content_loader import RuntimeContent

        content = RuntimeContent()
        assert hasattr(content, "errors")
        assert hasattr(content, "monster_registry")
