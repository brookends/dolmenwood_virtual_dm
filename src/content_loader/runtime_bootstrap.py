"""
Runtime Content Bootstrapper for Dolmenwood Virtual DM.

Loads base content from disk and provides runtime-ready data structures
for use by VirtualDM and its engines.

This module wraps the existing content loaders (HexDataLoader, SpellDataLoader,
MonsterDataLoader) and extracts data suitable for runtime use.

Usage:
    from src.content_loader.runtime_bootstrap import load_runtime_content

    content = load_runtime_content(Path("data/content"))
    for hex_id, hex_loc in content.hexes.items():
        hex_crawl_engine.load_hex_data(hex_id, hex_loc)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.data_models import HexLocation

logger = logging.getLogger(__name__)


@dataclass
class RuntimeContentStats:
    """Statistics about loaded content."""

    hexes_loaded: int = 0
    hexes_failed: int = 0
    spells_loaded: int = 0
    spells_failed: int = 0
    monsters_loaded: int = 0
    monsters_failed: int = 0
    items_loaded: int = 0


@dataclass
class RuntimeContent:
    """
    Runtime-ready content data.

    Contains all content loaded from disk, ready for use by engines.

    Attributes:
        hexes: Dictionary of hex_id -> HexLocation objects
        spells: List of SpellData objects (for SpellResolver registration)
        monsters_loaded: Whether monsters were loaded into the registry
        items_loaded: Whether items were loaded into the catalog
        warnings: List of non-fatal warnings during loading
        stats: Load statistics
    """

    hexes: dict[str, HexLocation] = field(default_factory=dict)
    spells: list[Any] = field(default_factory=list)  # SpellData objects
    monsters_loaded: bool = False
    items_loaded: bool = False
    warnings: list[str] = field(default_factory=list)
    stats: RuntimeContentStats = field(default_factory=RuntimeContentStats)


def load_runtime_content(
    content_root: Optional[Path] = None,
    load_hexes: bool = True,
    load_spells: bool = True,
    load_monsters: bool = True,
    load_items: bool = True,
    enable_vector_db: bool = False,
) -> RuntimeContent:
    """
    Load all runtime content from disk.

    Uses existing content loaders to load data, then extracts runtime-ready
    structures for use by VirtualDM and its engines.

    Args:
        content_root: Root directory for content files.
            Defaults to data/content relative to project root.
        load_hexes: Whether to load hex data
        load_spells: Whether to load spell data
        load_monsters: Whether to load monster data
        load_items: Whether to load item data
        enable_vector_db: Whether to enable vector DB for lore search
            (requires chromadb dependencies)

    Returns:
        RuntimeContent with all loaded data
    """
    result = RuntimeContent()

    if content_root is None:
        # Default to project's data directory
        content_root = Path(__file__).parent.parent.parent / "data" / "content"

    if not content_root.exists():
        result.warnings.append(f"Content directory not found: {content_root}")
        logger.warning(f"Content directory not found: {content_root}")
        return result

    logger.info(f"Loading runtime content from: {content_root}")

    # Load hexes
    if load_hexes:
        _load_hexes(content_root / "hexes", result, enable_vector_db)

    # Load spells
    if load_spells:
        _load_spells(content_root / "spells", result)

    # Load monsters
    if load_monsters:
        _load_monsters(content_root / "monsters", result)

    # Load items
    if load_items:
        _load_items(content_root / "items", result)

    # Summary
    logger.info(
        f"Content loaded: {result.stats.hexes_loaded} hexes, "
        f"{result.stats.spells_loaded} spells, "
        f"{result.stats.monsters_loaded} monsters"
    )

    return result


def _load_hexes(hex_dir: Path, result: RuntimeContent, enable_vector_db: bool) -> None:
    """Load hex data using HexDataLoader."""
    if not hex_dir.exists():
        result.warnings.append(f"Hex directory not found: {hex_dir}")
        logger.debug(f"Hex directory not found: {hex_dir}")
        return

    try:
        from src.content_loader.content_pipeline import ContentPipeline
        from src.content_loader.hex_loader import HexDataLoader
        from src.content_loader.content_manager import ContentType

        # Create pipeline for loading
        pipeline = ContentPipeline(use_vector_db=enable_vector_db)
        loader = HexDataLoader(pipeline)

        # Load all hexes
        load_result = loader.load_directory(hex_dir)

        result.stats.hexes_loaded = load_result.total_hexes_loaded
        result.stats.hexes_failed = load_result.total_hexes_failed

        if load_result.errors:
            result.warnings.extend(load_result.errors[:10])  # Cap at 10

        # Extract HexLocation objects from the pipeline's content manager
        all_hex_dicts = pipeline.content_manager.get_all_content(ContentType.HEX)
        for hex_dict in all_hex_dicts:
            hex_id = hex_dict.get("hex_id")
            if hex_id:
                hex_loc = pipeline.content_manager._dict_to_hex(hex_dict)
                result.hexes[hex_id] = hex_loc

        logger.info(f"Loaded {len(result.hexes)} hexes from {hex_dir}")

    except ImportError as e:
        result.warnings.append(f"Failed to import hex loader: {e}")
        logger.warning(f"Failed to import hex loader: {e}")
    except Exception as e:
        result.warnings.append(f"Error loading hexes: {e}")
        logger.error(f"Error loading hexes: {e}", exc_info=True)


def _load_spells(spell_dir: Path, result: RuntimeContent) -> None:
    """Load spell data using SpellDataLoader."""
    if not spell_dir.exists():
        result.warnings.append(f"Spell directory not found: {spell_dir}")
        logger.debug(f"Spell directory not found: {spell_dir}")
        return

    try:
        from src.content_loader.spell_loader import SpellDataLoader

        loader = SpellDataLoader()
        load_result = loader.load_directory(spell_dir)

        result.stats.spells_loaded = load_result.total_spells_loaded
        result.stats.spells_failed = load_result.total_spells_failed
        result.spells = load_result.all_spells

        if load_result.errors:
            result.warnings.extend(load_result.errors[:10])

        logger.info(f"Loaded {len(result.spells)} spells from {spell_dir}")

    except ImportError as e:
        result.warnings.append(f"Failed to import spell loader: {e}")
        logger.warning(f"Failed to import spell loader: {e}")
    except Exception as e:
        result.warnings.append(f"Error loading spells: {e}")
        logger.error(f"Error loading spells: {e}", exc_info=True)


def _load_monsters(monster_dir: Path, result: RuntimeContent) -> None:
    """Load monster data into the MonsterRegistry."""
    if not monster_dir.exists():
        result.warnings.append(f"Monster directory not found: {monster_dir}")
        logger.debug(f"Monster directory not found: {monster_dir}")
        return

    try:
        from src.content_loader.monster_registry import MonsterRegistry

        # Create registry and load monsters
        registry = MonsterRegistry()
        load_stats = registry.load_from_directory(monster_dir)

        result.stats.monsters_loaded = load_stats.get("monsters_loaded", 0)
        result.monsters_loaded = result.stats.monsters_loaded > 0

        if load_stats.get("errors"):
            result.warnings.extend(load_stats["errors"][:10])

        logger.info(f"Loaded {result.stats.monsters_loaded} monsters from {monster_dir}")

    except ImportError as e:
        result.warnings.append(f"Failed to import monster registry: {e}")
        logger.warning(f"Failed to import monster registry: {e}")
    except Exception as e:
        result.warnings.append(f"Error loading monsters: {e}")
        logger.error(f"Error loading monsters: {e}", exc_info=True)


def _load_items(item_dir: Path, result: RuntimeContent) -> None:
    """Load item data into the ItemCatalog."""
    if not item_dir.exists():
        result.warnings.append(f"Item directory not found: {item_dir}")
        logger.debug(f"Item directory not found: {item_dir}")
        return

    try:
        from src.items.item_catalog import ItemCatalog

        catalog = ItemCatalog()

        # Check for JSON files in the directory
        json_files = list(item_dir.glob("*.json"))
        if not json_files:
            result.warnings.append(f"No item JSON files found in: {item_dir}")
            return

        # Load each file
        items_loaded = 0
        for json_file in json_files:
            try:
                count = catalog.load_from_file(json_file)
                items_loaded += count
            except Exception as e:
                result.warnings.append(f"Error loading {json_file.name}: {e}")

        result.stats.items_loaded = items_loaded
        result.items_loaded = items_loaded > 0

        logger.info(f"Loaded {items_loaded} items from {item_dir}")

    except ImportError as e:
        result.warnings.append(f"Failed to import item catalog: {e}")
        logger.warning(f"Failed to import item catalog: {e}")
    except AttributeError:
        # ItemCatalog may not have load_from_file method yet
        result.warnings.append("ItemCatalog.load_from_file not implemented")
        logger.debug("ItemCatalog.load_from_file not implemented")
    except Exception as e:
        result.warnings.append(f"Error loading items: {e}")
        logger.error(f"Error loading items: {e}", exc_info=True)


def register_spells_with_combat(
    spells: list[Any],
    combat_engine: Any,
) -> int:
    """
    Register loaded spells with a CombatEngine's SpellResolver.

    Args:
        spells: List of SpellData objects from RuntimeContent.spells
        combat_engine: CombatEngine instance with spell_resolver attribute

    Returns:
        Number of spells registered
    """
    if not spells:
        return 0

    if not hasattr(combat_engine, "spell_resolver") or combat_engine.spell_resolver is None:
        logger.warning("CombatEngine has no spell_resolver, skipping spell registration")
        return 0

    try:
        from src.content_loader.spell_loader import register_spells_with_resolver

        count = register_spells_with_resolver(spells, combat_engine.spell_resolver)
        logger.info(f"Registered {count} spells with combat engine")
        return count
    except Exception as e:
        logger.error(f"Error registering spells: {e}")
        return 0
