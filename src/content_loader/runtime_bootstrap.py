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
        item_catalog: The loaded ItemCatalog instance (if items loaded)
        warnings: List of non-fatal warnings during loading
        stats: Load statistics
    """

    hexes: dict[str, HexLocation] = field(default_factory=dict)
    spells: list[Any] = field(default_factory=list)  # SpellData objects
    monsters_loaded: bool = False
    items_loaded: bool = False
    item_catalog: Any = None  # ItemCatalog instance
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
    """
    Load hex data directly from JSON files.

    Uses direct JSON loading rather than ContentPipeline to avoid
    constructor issues and simplify the loading process.
    """
    if not hex_dir.exists():
        result.warnings.append(f"Hex directory not found: {hex_dir}")
        logger.debug(f"Hex directory not found: {hex_dir}")
        return

    try:
        import json

        # Find all JSON files in the hex directory
        json_files = list(hex_dir.glob("*.json"))

        if not json_files:
            logger.debug(f"No JSON files found in {hex_dir}")
            return

        logger.info(f"Found {len(json_files)} hex JSON files in {hex_dir}")

        # Load each hex file directly
        for json_file in sorted(json_files):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check for hex_id at top level (new format)
                if "hex_id" in data:
                    hex_location = _parse_hex_json(data)
                    if hex_location:
                        result.hexes[hex_location.hex_id] = hex_location
                        result.stats.hexes_loaded += 1
                # Check for items array (legacy format)
                elif "items" in data and isinstance(data["items"], list):
                    for item in data["items"]:
                        if "hex_id" in item:
                            hex_location = _parse_hex_json(item)
                            if hex_location:
                                result.hexes[hex_location.hex_id] = hex_location
                                result.stats.hexes_loaded += 1
                else:
                    result.stats.hexes_failed += 1
                    result.warnings.append(f"No hex_id found in {json_file.name}")

            except json.JSONDecodeError as e:
                result.stats.hexes_failed += 1
                result.warnings.append(f"Invalid JSON in {json_file.name}: {e}")
                logger.warning(f"Failed to parse {json_file}: {e}")
            except Exception as e:
                result.stats.hexes_failed += 1
                result.warnings.append(f"Error loading {json_file.name}: {e}")
                logger.warning(f"Error loading {json_file}: {e}")

        logger.info(f"Loaded {result.stats.hexes_loaded} hexes from {hex_dir}")

    except Exception as e:
        result.warnings.append(f"Error loading hexes: {e}")
        logger.error(f"Error loading hexes: {e}", exc_info=True)


def _parse_hex_json(data: dict[str, Any]) -> Optional[HexLocation]:
    """
    Parse a hex JSON dictionary into a HexLocation dataclass.

    Args:
        data: Dictionary from JSON

    Returns:
        HexLocation instance or None on error
    """
    try:
        from src.data_models import (
            HexFeature,
            HexNPC,
            HexProcedural,
            PointOfInterest,
            RollTable,
            RollTableEntry,
        )

        # Parse coordinates
        coords = data.get("coordinates", [0, 0])
        if isinstance(coords, list) and len(coords) >= 2:
            coordinates = (coords[0], coords[1])
        else:
            coordinates = (0, 0)

        # Parse procedural section
        procedural = None
        proc_data = data.get("procedural")
        if proc_data:
            procedural = HexProcedural(
                lost_chance=proc_data.get("lost_chance", "1-in-6"),
                encounter_chance=proc_data.get("encounter_chance", "1-in-6"),
                encounter_notes=proc_data.get("encounter_notes", ""),
                foraging_results=proc_data.get("foraging_results", ""),
                foraging_special=proc_data.get("foraging_special", []),
                encounter_modifiers=proc_data.get("encounter_modifiers", []),
                lost_behavior=proc_data.get("lost_behavior"),
                night_hazards=proc_data.get("night_hazards", []),
            )

        # Parse points of interest
        points_of_interest = []
        for poi_data in data.get("points_of_interest", []):
            poi = _parse_point_of_interest(poi_data)
            points_of_interest.append(poi)

        # Parse hex-level roll tables
        roll_tables = []
        for table_data in data.get("roll_tables", []):
            table = _parse_roll_table(table_data)
            roll_tables.append(table)

        # Parse NPCs
        npcs = []
        for npc_data in data.get("npcs", []):
            npc = _parse_hex_npc(npc_data)
            npcs.append(npc)

        # Parse legacy features if present
        features = []
        for feature_data in data.get("features", []):
            feature = HexFeature(
                name=feature_data.get("name", "Unknown Feature"),
                description=feature_data.get("description", ""),
                feature_type=feature_data.get("feature_type", "general"),
                is_hidden=feature_data.get("is_hidden", False),
                npcs=feature_data.get("npcs", []),
                monsters=feature_data.get("monsters", []),
                treasure=feature_data.get("treasure"),
                hooks=feature_data.get("hooks", []),
            )
            features.append(feature)

        # Build HexLocation
        hex_location = HexLocation(
            hex_id=data.get("hex_id", "0000"),
            coordinates=coordinates,
            name=data.get("name"),
            tagline=data.get("tagline", ""),
            terrain_type=data.get("terrain_type", "forest"),
            terrain_description=data.get("terrain_description", ""),
            terrain_difficulty=data.get("terrain_difficulty", 1),
            region=data.get("region", ""),
            description=data.get("description", ""),
            dm_notes=data.get("dm_notes", ""),
            procedural=procedural,
            points_of_interest=points_of_interest,
            roll_tables=roll_tables,
            npcs=npcs,
            items=data.get("items", []),
            secrets=data.get("secrets", []),
            adjacent_hexes=data.get("adjacent_hexes", []),
            roads=data.get("roads", []),
            page_reference=data.get("page_reference", ""),
            _metadata=data.get("_metadata"),
            # Legacy fields
            terrain=data.get("terrain_type", "forest"),
            flavour_text=data.get("tagline", ""),
            travel_point_cost=data.get("travel_point_cost", data.get("terrain_difficulty", 1)),
            lost_chance=data.get("lost_chance", 1),
            encounter_chance=data.get("encounter_chance", 1),
            special_encounter_chance=data.get("special_encounter_chance", 0),
            encounter_table=data.get("encounter_table"),
            special_encounters=data.get("special_encounters", []),
            features=features,
            ley_lines=data.get("ley_lines"),
            foraging_yields=data.get("foraging_yields", []),
        )

        return hex_location

    except Exception as e:
        logger.error(f"Error parsing hex {data.get('hex_id', '?')}: {e}")
        return None


def _parse_point_of_interest(data: dict[str, Any]) -> Any:
    """Parse a point of interest from JSON."""
    from src.data_models import PointOfInterest

    # Parse roll tables within the POI
    roll_tables = []
    for table_data in data.get("roll_tables", []):
        table = _parse_roll_table(table_data)
        roll_tables.append(table)

    # Detect hidden POIs from entering field
    entering = data.get("entering")
    is_hidden = data.get("hidden", False)
    if not is_hidden and entering and isinstance(entering, str):
        if "hidden" in entering.lower():
            is_hidden = True

    return PointOfInterest(
        name=data.get("name", "Unknown"),
        poi_type=data.get("poi_type", "general"),
        description=data.get("description", ""),
        tagline=data.get("tagline"),
        entering=entering,
        interior=data.get("interior"),
        exploring=data.get("exploring"),
        leaving=data.get("leaving"),
        inhabitants=data.get("inhabitants"),
        roll_tables=roll_tables,
        npcs=data.get("npcs", []),
        special_features=data.get("special_features", []),
        secrets=data.get("secrets", []),
        is_dungeon=data.get("is_dungeon", False),
        dungeon_levels=data.get("dungeon_levels"),
        hidden=is_hidden,
    )


def _parse_roll_table(data: dict[str, Any]) -> Any:
    """Parse a roll table from JSON."""
    from src.data_models import RollTable, RollTableEntry

    entries = []
    for entry_data in data.get("entries", []):
        entry = RollTableEntry(
            roll=entry_data.get("roll", 1),
            description=entry_data.get("description", ""),
            title=entry_data.get("title"),
            monsters=entry_data.get("monsters", []),
            npcs=entry_data.get("npcs", []),
            items=entry_data.get("items", []),
            mechanical_effect=entry_data.get("mechanical_effect"),
            sub_table=entry_data.get("sub_table"),
        )
        entries.append(entry)

    return RollTable(
        name=data.get("name", "Unknown Table"),
        die_type=data.get("die_type", "d6"),
        description=data.get("description", ""),
        entries=entries,
        unique_entries=data.get("unique_entries", False),
    )


def _parse_hex_npc(data: dict[str, Any]) -> Any:
    """Parse an NPC from JSON."""
    from src.data_models import HexNPC

    return HexNPC(
        npc_id=data.get("npc_id", "unknown"),
        name=data.get("name", "Unknown NPC"),
        description=data.get("description", ""),
        kindred=data.get("kindred", "Human"),
        alignment=data.get("alignment", "Neutral"),
        title=data.get("title"),
        demeanor=data.get("demeanor", []),
        speech=data.get("speech", ""),
        languages=data.get("languages", []),
        desires=data.get("desires", []),
        secrets=data.get("secrets", []),
        possessions=data.get("possessions", []),
        location=data.get("location", ""),
        stat_reference=data.get("stat_reference"),
        is_combatant=data.get("is_combatant", False),
        vulnerabilities=data.get("vulnerabilities", []),
        faction=data.get("faction"),
        loyalty=data.get("loyalty", "loyal"),
    )


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
    """
    Load item data into the ItemCatalog.

    Uses ItemCatalog's built-in load() method which recursively loads
    from all subdirectories using rglob.
    """
    if not item_dir.exists():
        result.warnings.append(f"Item directory not found: {item_dir}")
        logger.debug(f"Item directory not found: {item_dir}")
        return

    try:
        from src.items.item_catalog import ItemCatalog

        # Create catalog with the items directory path
        # ItemCatalog.load() uses rglob to find all nested JSON files
        catalog = ItemCatalog(items_path=str(item_dir))
        catalog.load()

        # Get count from the loaded catalog
        items_loaded = len(catalog)

        result.stats.items_loaded = items_loaded
        result.items_loaded = items_loaded > 0

        # Store the catalog for later access
        result.item_catalog = catalog

        logger.info(f"Loaded {items_loaded} items from {item_dir}")

    except ImportError as e:
        result.warnings.append(f"Failed to import item catalog: {e}")
        logger.warning(f"Failed to import item catalog: {e}")
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
