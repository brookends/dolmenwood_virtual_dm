"""
Tests for content loading failure on empty hexes.

Phase 5 (P2): Verify that VirtualDM fails fast with a clear error message
when load_content=True but no hexes are loaded.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.main import VirtualDM, GameConfig
from src.data_models import DiceRoller
from src.game_state.state_machine import GameState


@pytest.fixture
def seeded_dice():
    """Provide deterministic dice for reproducible tests."""
    DiceRoller.clear_roll_log()
    DiceRoller.set_seed(42)
    yield
    DiceRoller.clear_roll_log()


@pytest.fixture
def empty_content_dir():
    """Create a temporary content directory with structure but no hex data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = Path(tmpdir)

        # Create required directory structure but with no hex files
        (content_dir / "hexes").mkdir()
        (content_dir / "items").mkdir()
        (content_dir / "items" / "equipment").mkdir()
        (content_dir / "monsters").mkdir()
        (content_dir / "spells").mkdir()
        (content_dir / "settlements").mkdir()

        # Create a minimal item file (not a hex)
        item_file = content_dir / "items" / "equipment" / "torch.json"
        item_file.write_text('{"id": "torch", "name": "Torch", "weight": 1}')

        yield content_dir


class TestLoadContentFailsOnEmptyHexes:
    """Test that content loading fails clearly when hexes are empty."""

    def test_fails_with_clear_error_on_empty_hexes(self, seeded_dice, empty_content_dir):
        """VirtualDM should raise a clear error when no hexes are loaded."""
        from src.conversation.action_registry import reset_registry
        reset_registry()

        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=empty_content_dir,
        )

        with pytest.raises(RuntimeError) as exc_info:
            VirtualDM(
                config=config,
                initial_state=GameState.WILDERNESS_TRAVEL,
            )

        # Error message should be clear and helpful
        error_msg = str(exc_info.value)
        assert "hex" in error_msg.lower()
        assert "content" in error_msg.lower() or "load" in error_msg.lower()

    def test_does_not_fail_without_load_content(self, seeded_dice, empty_content_dir):
        """When load_content=False, empty hexes should not cause failure."""
        from src.conversation.action_registry import reset_registry
        reset_registry()

        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=False,  # Not loading content
            content_dir=empty_content_dir,
        )

        # Should not raise
        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
        )

        assert dm is not None
        assert dm.current_state == GameState.WILDERNESS_TRAVEL


class TestLoadContentSucceedsWithValidHexes:
    """Test that content loading succeeds when hexes are present."""

    def test_succeeds_with_valid_hex_data(self, seeded_dice):
        """Content loading should succeed when hex data is present."""
        from src.conversation.action_registry import reset_registry
        reset_registry()

        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)

            # Create required directory structure
            (content_dir / "hexes").mkdir()
            (content_dir / "items").mkdir()
            (content_dir / "monsters").mkdir()
            (content_dir / "spells").mkdir()
            (content_dir / "settlements").mkdir()

            # Create a valid hex file
            hex_file = content_dir / "hexes" / "hex_0101.json"
            hex_file.write_text('''{
                "hex_id": "0101",
                "name": "Test Hex",
                "terrain": "forest",
                "description": "A test hex for validation"
            }''')

            config = GameConfig(
                llm_provider="mock",
                enable_narration=False,
                load_content=True,
                content_dir=content_dir,
            )

            # Should not raise
            dm = VirtualDM(
                config=config,
                initial_state=GameState.WILDERNESS_TRAVEL,
            )

            assert dm is not None
            assert dm._content_loaded is True
