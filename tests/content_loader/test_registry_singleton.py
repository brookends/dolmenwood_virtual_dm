"""
Tests for registry singleton behavior on VirtualDM.

Phase 7.1: Verify that content registries are stored on VirtualDM
and accessible for reuse rather than being discarded after loading.
"""

import pytest
from pathlib import Path
import tempfile
import json

from src.main import VirtualDM, GameConfig
from src.data_models import GameDate, GameTime
from src.game_state.state_machine import GameState


@pytest.fixture
def temp_content_dir():
    """Create temporary content directory with sample data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = Path(tmpdir)

        # Create subdirectories
        (content_dir / "hexes").mkdir()
        (content_dir / "monsters").mkdir()
        (content_dir / "items").mkdir()
        (content_dir / "spells").mkdir()

        # Create sample hex
        hex_data = {
            "hex_id": "1001",
            "name": "Test Forest",
            "terrain_type": "forest",
            "coordinates": [10, 1],
            "description": "A test forest hex.",
        }
        with open(content_dir / "hexes" / "test_hex.json", "w") as f:
            json.dump(hex_data, f)

        # Create sample monster
        monster_data = {
            "monsters": [
                {
                    "name": "Test Goblin",
                    "hd": "1",
                    "ac": 7,
                    "attacks": [{"name": "club", "damage": "1d6"}],
                    "movement": 30,
                    "morale": 7,
                    "alignment": "Chaotic",
                    "xp": 10,
                }
            ]
        }
        with open(content_dir / "monsters" / "test_monster.json", "w") as f:
            json.dump(monster_data, f)

        # Create sample item
        item_data = {
            "items": [
                {
                    "name": "Test Sword",
                    "type": "weapon",
                    "weight": 3,
                    "cost": 10,
                    "damage": "1d8",
                }
            ]
        }
        with open(content_dir / "items" / "test_item.json", "w") as f:
            json.dump(item_data, f)

        yield content_dir


class TestRegistryStorageOnVirtualDM:
    """Test that registries are stored on VirtualDM."""

    def test_monster_registry_stored(self, temp_content_dir):
        """VirtualDM should store the monster_registry after loading."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # monster_registry should be stored (not None)
        assert dm.monster_registry is not None, (
            "monster_registry should be stored on VirtualDM"
        )

    def test_item_catalog_stored(self, temp_content_dir):
        """VirtualDM should store the item_catalog after loading."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # item_catalog should be stored
        assert dm.item_catalog is not None, (
            "item_catalog should be stored on VirtualDM"
        )

    def test_spell_data_stored(self, temp_content_dir):
        """VirtualDM should store spell_data list after loading."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # spell_data should be a list (may be empty if no spells loaded)
        assert isinstance(dm.spell_data, list), (
            "spell_data should be a list on VirtualDM"
        )


class TestRegistryReuse:
    """Test that stored registries can be reused."""

    def test_monster_registry_is_usable(self, temp_content_dir):
        """Stored monster_registry should be usable for lookups."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # Should be able to use the registry for lookups
        if dm.monster_registry is not None:
            # Registry should have methods
            assert hasattr(dm.monster_registry, "get_monster") or hasattr(
                dm.monster_registry, "lookup"
            ), "monster_registry should have lookup methods"

    def test_item_catalog_is_usable(self, temp_content_dir):
        """Stored item_catalog should be usable for lookups."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=True,
            content_dir=temp_content_dir,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        # Should be able to use the catalog
        if dm.item_catalog is not None:
            # Catalog should be iterable or have lookup methods
            assert hasattr(dm.item_catalog, "__len__") or hasattr(
                dm.item_catalog, "get"
            ), "item_catalog should have lookup capabilities"


class TestRuntimeContentStoresRegistry:
    """Test that RuntimeContent properly stores monster_registry."""

    def test_runtime_content_has_monster_registry_field(self):
        """RuntimeContent should have monster_registry field."""
        from src.content_loader.runtime_bootstrap import RuntimeContent

        content = RuntimeContent()

        assert hasattr(content, "monster_registry"), (
            "RuntimeContent should have monster_registry field"
        )
        assert content.monster_registry is None, (
            "monster_registry should default to None"
        )

    def test_runtime_content_has_errors_field(self):
        """RuntimeContent should have errors field for Phase 7.2."""
        from src.content_loader.runtime_bootstrap import RuntimeContent

        content = RuntimeContent()

        assert hasattr(content, "errors"), (
            "RuntimeContent should have errors field"
        )
        assert content.errors == [], (
            "errors should default to empty list"
        )

    def test_load_monsters_stores_registry(self, temp_content_dir):
        """_load_monsters should store registry in RuntimeContent."""
        from src.content_loader.runtime_bootstrap import (
            load_runtime_content,
        )

        content = load_runtime_content(
            content_root=temp_content_dir,
            load_hexes=True,
            load_spells=False,
            load_monsters=True,
            load_items=False,
        )

        # Should store the registry instance
        assert content.monster_registry is not None, (
            "monster_registry should be stored in RuntimeContent"
        )


class TestNoContentLoadingStoresNone:
    """Test behavior when content loading is disabled."""

    def test_registries_none_when_not_loading(self):
        """Registries should be None when load_content=False."""
        config = GameConfig(
            llm_provider="mock",
            enable_narration=False,
            load_content=False,
        )

        dm = VirtualDM(
            config=config,
            initial_state=GameState.WILDERNESS_TRAVEL,
            game_date=GameDate(year=1, month=6, day=15),
            game_time=GameTime(hour=10, minute=0),
        )

        assert dm.monster_registry is None
        assert dm.item_catalog is None
        assert dm.spell_data == []
