"""
Monster Data Loader for Dolmenwood Virtual DM.

Loads monster data from JSON files in the data/content/monsters directory
and stores them in both SQLite (structured storage) and ChromaDB (vector search).

JSON File Format:
{
    "_metadata": {
        "source_file": "path/to/source.pdf",
        "pages": [32, 33, 34],
        "content_type": "monsters",
        "item_count": 4
    },
    "items": [
        {
            "name": "Deorling—Doe",
            "monster_id": "deorling_doe",
            "armor_class": 13,
            ...
        }
    ]
}
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.data_models import (
    ContentSource,
    Monster,
    SourceReference,
    SourceType,
)
from src.content_loader.content_pipeline import ContentPipeline, ImportResult
from src.content_loader.content_manager import ContentType


logger = logging.getLogger(__name__)


@dataclass
class MonsterFileMetadata:
    """Metadata from a monster JSON file."""
    source_file: str = ""
    pages: list[int] = field(default_factory=list)
    content_type: str = "monsters"
    item_count: int = 0
    errors: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class MonsterFileLoadResult:
    """Result of loading a single monster JSON file."""
    file_path: Path
    success: bool
    metadata: Optional[MonsterFileMetadata] = None
    monsters_loaded: int = 0
    monsters_failed: int = 0
    errors: list[str] = field(default_factory=list)
    import_results: list[ImportResult] = field(default_factory=list)


@dataclass
class MonsterDirectoryLoadResult:
    """Result of loading all monster files from a directory."""
    directory: Path
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_monsters_loaded: int = 0
    total_monsters_failed: int = 0
    file_results: list[MonsterFileLoadResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MonsterDataLoader:
    """
    Loads monster data from JSON files and stores in ContentPipeline.

    Usage:
        pipeline = ContentPipeline()
        loader = MonsterDataLoader(pipeline)

        # Load all monsters from directory
        result = loader.load_directory(Path("data/content/monsters"))

        # Or load a single file
        result = loader.load_file(Path("data/content/monsters/deorlings.json"))
    """

    # Default source for monster data
    DEFAULT_SOURCE_ID = "dolmenwood_monster_book"
    DEFAULT_BOOK_CODE = "DMB"

    def __init__(
        self,
        pipeline: ContentPipeline,
        default_source_id: Optional[str] = None,
        auto_register_source: bool = True
    ):
        """
        Initialize the monster data loader.

        Args:
            pipeline: ContentPipeline for storage
            default_source_id: Default source ID for imports
            auto_register_source: Automatically register source if not exists
        """
        self.pipeline = pipeline
        self.default_source_id = default_source_id or self.DEFAULT_SOURCE_ID
        self.auto_register_source = auto_register_source

        # Ensure default source is registered
        if self.auto_register_source:
            self._ensure_source_registered()

    def _ensure_source_registered(self) -> None:
        """Ensure the default source is registered."""
        if not self.pipeline.get_source(self.default_source_id):
            source = ContentSource(
                source_id=self.default_source_id,
                source_type=SourceType.CORE_RULEBOOK,
                book_name="Dolmenwood Monster Book",
                book_code=self.DEFAULT_BOOK_CODE,
                version="1.0",
                file_path="",
                imported_at=datetime.now(),
            )
            self.pipeline.register_source(source)
            logger.info(f"Registered default source: {self.default_source_id}")

    def load_directory(
        self,
        directory: Path,
        recursive: bool = False,
        pattern: str = "*.json"
    ) -> MonsterDirectoryLoadResult:
        """
        Load all monster JSON files from a directory.

        Args:
            directory: Path to directory containing monster JSON files
            recursive: Search subdirectories recursively
            pattern: Glob pattern for matching files

        Returns:
            MonsterDirectoryLoadResult with load statistics
        """
        result = MonsterDirectoryLoadResult(directory=directory)

        if not directory.exists():
            result.errors.append(f"Directory not found: {directory}")
            logger.error(f"Monster directory not found: {directory}")
            return result

        if not directory.is_dir():
            result.errors.append(f"Path is not a directory: {directory}")
            logger.error(f"Path is not a directory: {directory}")
            return result

        # Find all JSON files
        if recursive:
            json_files = list(directory.rglob(pattern))
        else:
            json_files = list(directory.glob(pattern))

        logger.info(f"Found {len(json_files)} JSON files in {directory}")

        for json_file in sorted(json_files):
            result.files_processed += 1

            file_result = self.load_file(json_file)
            result.file_results.append(file_result)

            if file_result.success:
                result.files_successful += 1
                result.total_monsters_loaded += file_result.monsters_loaded
                result.total_monsters_failed += file_result.monsters_failed
            else:
                result.files_failed += 1
                result.errors.extend(file_result.errors)

        logger.info(
            f"Loaded {result.total_monsters_loaded} monsters from "
            f"{result.files_successful}/{result.files_processed} files"
        )

        return result

    def load_file(self, file_path: Path) -> MonsterFileLoadResult:
        """
        Load monsters from a single JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            MonsterFileLoadResult with load status
        """
        result = MonsterFileLoadResult(file_path=file_path, success=False)

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid JSON: {e}")
            logger.error(f"Failed to parse {file_path}: {e}")
            return result
        except Exception as e:
            result.errors.append(f"Error reading file: {e}")
            logger.error(f"Error reading {file_path}: {e}")
            return result

        # Parse metadata
        metadata_dict = data.get("_metadata", {})
        result.metadata = MonsterFileMetadata(
            source_file=metadata_dict.get("source_file", ""),
            pages=metadata_dict.get("pages", []),
            content_type=metadata_dict.get("content_type", "monsters"),
            item_count=metadata_dict.get("item_count", 0),
            errors=metadata_dict.get("errors", []),
            note=metadata_dict.get("note", ""),
        )

        # Determine source reference
        source_ref = self._get_source_reference(result.metadata)

        # Load monster items
        items = data.get("items", [])
        if not items:
            result.errors.append("No items found in file")
            return result

        for item in items:
            try:
                monster = self._parse_monster_item(item)
                import_result = self._add_monster_to_pipeline(monster, source_ref)
                result.import_results.append(import_result)

                if import_result.success:
                    result.monsters_loaded += 1
                else:
                    result.monsters_failed += 1
                    if import_result.error:
                        result.errors.append(f"Monster {item.get('name', '?')}: {import_result.error}")

            except Exception as e:
                result.monsters_failed += 1
                result.errors.append(f"Error parsing monster {item.get('name', '?')}: {e}")
                logger.error(f"Error parsing monster from {file_path}: {e}")

        result.success = result.monsters_loaded > 0
        logger.debug(f"Loaded {result.monsters_loaded} monsters from {file_path}")

        return result

    def _get_source_reference(self, metadata: MonsterFileMetadata) -> SourceReference:
        """Get source reference from metadata."""
        # Extract page reference if available
        page_ref = None
        if metadata.pages:
            if len(metadata.pages) == 1:
                page_ref = f"p. {metadata.pages[0]}"
            else:
                page_ref = f"pp. {metadata.pages[0]}-{metadata.pages[-1]}"

        return SourceReference(
            source_id=self.default_source_id,
            book_code=self.DEFAULT_BOOK_CODE,
            page_reference=page_ref,
        )

    def _parse_monster_item(self, item: dict[str, Any]) -> Monster:
        """
        Parse a monster item from JSON into a Monster dataclass.

        Args:
            item: Dictionary from JSON "items" array

        Returns:
            Monster dataclass instance
        """
        return Monster(
            # Core identification
            name=item.get("name", "Unknown Monster"),
            monster_id=item.get("monster_id", item.get("name", "unknown").lower().replace(" ", "_")),

            # Combat statistics
            armor_class=item.get("armor_class", 10),
            hit_dice=item.get("hit_dice", "1d8"),
            hp=item.get("hp", 4),
            level=item.get("level", 1),
            morale=item.get("morale", 7),

            # Movement
            movement=item.get("movement", "40'"),
            speed=item.get("speed", 40),
            burrow_speed=item.get("burrow_speed"),
            fly_speed=item.get("fly_speed"),
            swim_speed=item.get("swim_speed"),

            # Combat
            attacks=item.get("attacks", []),
            damage=item.get("damage", []),

            # Saving throws
            save_doom=item.get("save_doom", 14),
            save_ray=item.get("save_ray", 15),
            save_hold=item.get("save_hold", 16),
            save_blast=item.get("save_blast", 17),
            save_spell=item.get("save_spell", 18),
            saves_as=item.get("saves_as"),

            # Treasure
            treasure_type=item.get("treasure_type"),
            hoard=item.get("hoard"),
            possessions=item.get("possessions"),

            # Classification
            size=item.get("size", "Medium"),
            monster_type=item.get("monster_type", "Mortal"),
            sentience=item.get("sentience", "Sentient"),
            alignment=item.get("alignment", "Neutral"),
            intelligence=item.get("intelligence"),

            # Abilities
            special_abilities=item.get("special_abilities", []),
            immunities=item.get("immunities", []),
            resistances=item.get("resistances", []),
            vulnerabilities=item.get("vulnerabilities", []),

            # Description and behavior
            description=item.get("description"),
            behavior=item.get("behavior"),
            speech=item.get("speech"),
            traits=item.get("traits", []),

            # Encounter information
            number_appearing=item.get("number_appearing"),
            lair_percentage=item.get("lair_percentage"),
            encounter_scenarios=item.get("encounter_scenarios", []),
            lair_descriptions=item.get("lair_descriptions", []),

            # Experience and habitat
            xp_value=item.get("xp_value", 0),
            habitat=item.get("habitat", []),

            # Source tracking
            page_reference=item.get("page_reference", ""),
        )

    def _add_monster_to_pipeline(
        self,
        monster: Monster,
        source: SourceReference
    ) -> ImportResult:
        """
        Add a monster to the ContentPipeline.

        Args:
            monster: Monster dataclass instance
            source: Source reference

        Returns:
            ImportResult with status
        """
        # Convert Monster to dictionary for storage
        data = self._monster_to_dict(monster)

        # Build tags for filtering
        tags = [monster.monster_type.lower(), monster.size.lower()]
        if monster.alignment:
            tags.append(monster.alignment.lower())
        tags.extend([h.lower() for h in monster.habitat])

        return self.pipeline.add_content(
            content_id=monster.monster_id,
            content_type=ContentType.MONSTER,
            data=data,
            source=source,
            tags=tags
        )

    def _monster_to_dict(self, monster: Monster) -> dict[str, Any]:
        """Convert Monster dataclass to dictionary for storage."""
        return {
            # Core identification
            'name': monster.name,
            'monster_id': monster.monster_id,

            # Combat statistics
            'armor_class': monster.armor_class,
            'hit_dice': monster.hit_dice,
            'hp': monster.hp,
            'level': monster.level,
            'morale': monster.morale,

            # Movement
            'movement': monster.movement,
            'speed': monster.speed,
            'burrow_speed': monster.burrow_speed,
            'fly_speed': monster.fly_speed,
            'swim_speed': monster.swim_speed,

            # Combat
            'attacks': monster.attacks,
            'damage': monster.damage,

            # Saving throws
            'save_doom': monster.save_doom,
            'save_ray': monster.save_ray,
            'save_hold': monster.save_hold,
            'save_blast': monster.save_blast,
            'save_spell': monster.save_spell,
            'saves_as': monster.saves_as,

            # Treasure
            'treasure_type': monster.treasure_type,
            'hoard': monster.hoard,
            'possessions': monster.possessions,

            # Classification
            'size': monster.size,
            'monster_type': monster.monster_type,
            'sentience': monster.sentience,
            'alignment': monster.alignment,
            'intelligence': monster.intelligence,

            # Abilities
            'special_abilities': monster.special_abilities,
            'immunities': monster.immunities,
            'resistances': monster.resistances,
            'vulnerabilities': monster.vulnerabilities,

            # Description and behavior
            'description': monster.description,
            'behavior': monster.behavior,
            'speech': monster.speech,
            'traits': monster.traits,

            # Encounter information
            'number_appearing': monster.number_appearing,
            'lair_percentage': monster.lair_percentage,
            'encounter_scenarios': monster.encounter_scenarios,
            'lair_descriptions': monster.lair_descriptions,

            # Experience and habitat
            'xp_value': monster.xp_value,
            'habitat': monster.habitat,

            # Source tracking
            'page_reference': monster.page_reference,
        }

    def scan_directory(self, directory: Path) -> list[Path]:
        """
        Scan directory for monster JSON files without loading them.

        Args:
            directory: Path to scan

        Returns:
            List of JSON file paths found
        """
        if not directory.exists() or not directory.is_dir():
            return []

        return sorted(directory.glob("*.json"))

    def validate_file(self, file_path: Path) -> tuple[bool, list[str]]:
        """
        Validate a monster JSON file without loading it.

        Args:
            file_path: Path to JSON file

        Returns:
            Tuple of (is_valid, list of errors/warnings)
        """
        errors = []

        if not file_path.exists():
            return False, ["File not found"]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"]

        # Check structure
        if "_metadata" not in data:
            errors.append("Missing _metadata section")

        if "items" not in data:
            errors.append("Missing items section")
        elif not isinstance(data["items"], list):
            errors.append("items must be an array")
        elif len(data["items"]) == 0:
            errors.append("items array is empty")
        else:
            # Validate each item
            for i, item in enumerate(data["items"]):
                if "name" not in item:
                    errors.append(f"Item {i}: missing name")
                if "monster_id" not in item:
                    errors.append(f"Item {i}: missing monster_id")
                if "armor_class" not in item:
                    errors.append(f"Item {i}: missing armor_class")
                if "hit_dice" not in item:
                    errors.append(f"Item {i}: missing hit_dice")

        return len(errors) == 0, errors


def load_all_monsters(
    pipeline: ContentPipeline,
    data_dir: Optional[Path] = None
) -> MonsterDirectoryLoadResult:
    """
    Convenience function to load all monsters from the default directory.

    Args:
        pipeline: ContentPipeline for storage
        data_dir: Override default data directory

    Returns:
        MonsterDirectoryLoadResult with load statistics
    """
    if data_dir is None:
        # Default to project data directory
        data_dir = Path(__file__).parent.parent.parent / "data" / "content" / "monsters"

    loader = MonsterDataLoader(pipeline)
    return loader.load_directory(data_dir)
