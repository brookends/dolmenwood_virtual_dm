"""
Hex Data Loader for Dolmenwood Virtual DM.

Loads hex data from JSON files in the data/content/hexes directory
and stores them in both SQLite (structured storage) and ChromaDB (vector search).

JSON File Format (single hex per file):
{
    "hex_id": "0101",
    "coordinates": [1, 1],
    "name": "The Spectral Manse",
    "tagline": "A barren expanse...",
    "region": "Northern Scratch",
    "terrain_type": "bog",
    "terrain_difficulty": 3,
    "procedural": { ... },
    "points_of_interest": [ ... ],
    "npcs": [ ... ],
    "_metadata": { ... }
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
    HexFeature,
    HexLocation,
    HexNPC,
    HexProcedural,
    PointOfInterest,
    RollTable,
    RollTableEntry,
    SourceReference,
    SourceType,
)
from src.content_loader.content_pipeline import ContentPipeline, ImportResult, BatchImportResult
from src.content_loader.content_manager import ContentType


logger = logging.getLogger(__name__)


@dataclass
class HexFileMetadata:
    """Metadata from a hex JSON file."""

    source_file: str = ""
    pages: list[int] = field(default_factory=list)
    content_type: str = "hexes"
    item_count: int = 0
    errors: list[str] = field(default_factory=list)
    note: str = ""
    extraction_note: str = ""


@dataclass
class HexFileLoadResult:
    """Result of loading a single hex JSON file."""

    file_path: Path
    success: bool
    metadata: Optional[HexFileMetadata] = None
    hexes_loaded: int = 0
    hexes_failed: int = 0
    errors: list[str] = field(default_factory=list)
    import_results: list[ImportResult] = field(default_factory=list)


@dataclass
class HexDirectoryLoadResult:
    """Result of loading all hex files from a directory."""

    directory: Path
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    total_hexes_loaded: int = 0
    total_hexes_failed: int = 0
    file_results: list[HexFileLoadResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class HexDataLoader:
    """
    Loads hex data from JSON files and stores in ContentPipeline.

    Usage:
        pipeline = ContentPipeline()
        loader = HexDataLoader(pipeline)

        # Load all hexes from directory
        result = loader.load_directory(Path("data/content/hexes"))

        # Or load a single file
        result = loader.load_file(Path("data/content/hexes/hex_0101.json"))
    """

    # Default source for hex data
    DEFAULT_SOURCE_ID = "dolmenwood_campaign_book"
    DEFAULT_BOOK_CODE = "DCB"

    def __init__(
        self,
        pipeline: ContentPipeline,
        default_source_id: Optional[str] = None,
        auto_register_source: bool = True,
    ):
        """
        Initialize the hex data loader.

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
                source_type=SourceType.CAMPAIGN_SETTING,
                book_name="Dolmenwood Campaign Book",
                book_code=self.DEFAULT_BOOK_CODE,
                version="1.0",
                file_path="",
                imported_at=datetime.now(),
            )
            self.pipeline.register_source(source)
            logger.info(f"Registered default source: {self.default_source_id}")

    def load_directory(
        self, directory: Path, recursive: bool = False, pattern: str = "*.json"
    ) -> HexDirectoryLoadResult:
        """
        Load all hex JSON files from a directory.

        Args:
            directory: Path to directory containing hex JSON files
            recursive: Search subdirectories recursively
            pattern: Glob pattern for matching files

        Returns:
            HexDirectoryLoadResult with load statistics
        """
        result = HexDirectoryLoadResult(directory=directory)

        if not directory.exists():
            result.errors.append(f"Directory not found: {directory}")
            logger.error(f"Hex directory not found: {directory}")
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
                result.total_hexes_loaded += file_result.hexes_loaded
                result.total_hexes_failed += file_result.hexes_failed
            else:
                result.files_failed += 1
                result.errors.extend(file_result.errors)

        logger.info(
            f"Loaded {result.total_hexes_loaded} hexes from "
            f"{result.files_successful}/{result.files_processed} files"
        )

        return result

    def load_file(self, file_path: Path) -> HexFileLoadResult:
        """
        Load a hex from a single JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            HexFileLoadResult with load status
        """
        result = HexFileLoadResult(file_path=file_path, success=False)

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid JSON: {e}")
            logger.error(f"Failed to parse {file_path}: {e}")
            return result
        except Exception as e:
            result.errors.append(f"Error reading file: {e}")
            logger.error(f"Error reading {file_path}: {e}")
            return result

        # Parse metadata (now at top level of hex)
        metadata_dict = data.get("_metadata", {})
        result.metadata = HexFileMetadata(
            source_file=metadata_dict.get("source_file", ""),
            pages=metadata_dict.get("pages", []),
            content_type=metadata_dict.get("content_type", "hexes"),
            item_count=metadata_dict.get("item_count", 1),
            errors=metadata_dict.get("errors", []),
            note=metadata_dict.get("note", ""),
            extraction_note=metadata_dict.get("extraction_note", ""),
        )

        # Determine source reference
        source_ref = self._get_source_reference(result.metadata)

        # Check if this is a single hex file (new format) or items array (legacy)
        # New format: hex_id at top level, items is just a field for hex items
        # Legacy format: items is an array of hex objects (each with hex_id)
        if "hex_id" in data:
            # New format - single hex per file (items field is for hex items, not hex data)
            self._load_hex_item(data, source_ref, result)
        elif "items" in data and isinstance(data["items"], list):
            # Legacy format - check if items contains hex objects
            items = data.get("items", [])
            if items and isinstance(items[0], dict) and "hex_id" in items[0]:
                # Items array contains hex data
                for item in items:
                    self._load_hex_item(item, source_ref, result)
            else:
                result.errors.append("Items array does not contain hex data")
                return result
        else:
            result.errors.append("No hex_id or items found in file")
            return result

        result.success = result.hexes_loaded > 0
        logger.debug(f"Loaded {result.hexes_loaded} hexes from {file_path}")

        return result

    def _load_hex_item(
        self, item: dict[str, Any], source_ref: SourceReference, result: HexFileLoadResult
    ) -> None:
        """Load a single hex item and add to pipeline."""
        try:
            hex_location = self._parse_hex_item(item)
            import_result = self.pipeline.add_hex(hex_location, source_ref)
            result.import_results.append(import_result)

            if import_result.success:
                result.hexes_loaded += 1
            else:
                result.hexes_failed += 1
                if import_result.error:
                    result.errors.append(f"Hex {item.get('hex_id', '?')}: {import_result.error}")

        except Exception as e:
            result.hexes_failed += 1
            result.errors.append(f"Error parsing hex {item.get('hex_id', '?')}: {e}")
            logger.error(f"Error parsing hex: {e}")

    def _get_source_reference(self, metadata: HexFileMetadata) -> SourceReference:
        """Get source reference from metadata."""
        # Extract page reference if available
        page_ref = None
        if metadata.pages:
            page_ref = f"p. {metadata.pages[0]}"

        return SourceReference(
            source_id=self.default_source_id,
            book_code=self.DEFAULT_BOOK_CODE,
            page_reference=page_ref,
        )

    def _parse_hex_item(self, item: dict[str, Any]) -> HexLocation:
        """
        Parse a hex item from JSON into a HexLocation dataclass.

        Args:
            item: Dictionary from JSON

        Returns:
            HexLocation dataclass instance
        """
        # Parse coordinates
        coords = item.get("coordinates", [0, 0])
        if isinstance(coords, list) and len(coords) >= 2:
            coordinates = (coords[0], coords[1])
        else:
            coordinates = (0, 0)

        # Parse procedural section
        procedural = None
        proc_data = item.get("procedural")
        if proc_data:
            procedural = HexProcedural(
                lost_chance=proc_data.get("lost_chance", "1-in-6"),
                encounter_chance=proc_data.get("encounter_chance", "1-in-6"),
                encounter_notes=proc_data.get("encounter_notes", ""),
                foraging_results=proc_data.get("foraging_results", ""),
                foraging_special=proc_data.get("foraging_special", []),
            )

        # Parse points of interest
        points_of_interest = []
        for poi_data in item.get("points_of_interest", []):
            poi = self._parse_point_of_interest(poi_data)
            points_of_interest.append(poi)

        # Parse hex-level roll tables
        roll_tables = []
        for table_data in item.get("roll_tables", []):
            table = self._parse_roll_table(table_data)
            roll_tables.append(table)

        # Parse NPCs
        npcs = []
        for npc_data in item.get("npcs", []):
            npc = self._parse_hex_npc(npc_data)
            npcs.append(npc)

        # Parse legacy features if present (backward compatibility)
        features = []
        for feature_data in item.get("features", []):
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
            hex_id=item.get("hex_id", "0000"),
            coordinates=coordinates,
            name=item.get("name"),
            tagline=item.get("tagline", ""),
            terrain_type=item.get("terrain_type", "forest"),
            terrain_description=item.get("terrain_description", ""),
            terrain_difficulty=item.get("terrain_difficulty", 1),
            region=item.get("region", ""),
            description=item.get("description", ""),
            dm_notes=item.get("dm_notes", ""),
            procedural=procedural,
            points_of_interest=points_of_interest,
            roll_tables=roll_tables,
            npcs=npcs,
            items=item.get("items", []),
            secrets=item.get("secrets", []),
            adjacent_hexes=item.get("adjacent_hexes", []),
            roads=item.get("roads", []),
            page_reference=item.get("page_reference", ""),
            _metadata=item.get("_metadata"),
            # Legacy fields
            terrain=item.get("terrain_type", "forest"),
            flavour_text=item.get("tagline", ""),
            travel_point_cost=item.get("travel_point_cost", item.get("terrain_difficulty", 1)),
            lost_chance=item.get("lost_chance", 1),
            encounter_chance=item.get("encounter_chance", 1),
            special_encounter_chance=item.get("special_encounter_chance", 0),
            encounter_table=item.get("encounter_table"),
            special_encounters=item.get("special_encounters", []),
            features=features,
            ley_lines=item.get("ley_lines"),
            foraging_yields=item.get("foraging_yields", []),
        )

        return hex_location

    def _parse_point_of_interest(self, data: dict[str, Any]) -> PointOfInterest:
        """Parse a point of interest from JSON."""
        # Parse roll tables within the POI
        roll_tables = []
        for table_data in data.get("roll_tables", []):
            table = self._parse_roll_table(table_data)
            roll_tables.append(table)

        return PointOfInterest(
            name=data.get("name", "Unknown"),
            poi_type=data.get("poi_type", "general"),
            description=data.get("description", ""),
            tagline=data.get("tagline"),
            entering=data.get("entering"),
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
        )

    def _parse_roll_table(self, data: dict[str, Any]) -> RollTable:
        """Parse a roll table from JSON."""
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
        )

    def _parse_hex_npc(self, data: dict[str, Any]) -> HexNPC:
        """Parse an NPC from JSON."""
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
        )

    def scan_directory(self, directory: Path) -> list[Path]:
        """
        Scan directory for hex JSON files without loading them.

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
        Validate a hex JSON file without loading it.

        Args:
            file_path: Path to JSON file

        Returns:
            Tuple of (is_valid, list of errors/warnings)
        """
        errors = []

        if not file_path.exists():
            return False, ["File not found"]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"]

        # Check for hex_id (new format) or items (legacy format)
        if "hex_id" not in data and "items" not in data:
            errors.append("Missing hex_id or items section")

        if "hex_id" in data:
            # New single-hex format
            if "terrain_type" not in data:
                errors.append("Missing terrain_type")
        elif "items" in data:
            # Legacy format
            if not isinstance(data["items"], list):
                errors.append("items must be an array")
            elif len(data["items"]) == 0:
                errors.append("items array is empty")
            else:
                for i, item in enumerate(data["items"]):
                    if "hex_id" not in item:
                        errors.append(f"Item {i}: missing hex_id")
                    if "terrain_type" not in item:
                        errors.append(f"Item {i}: missing terrain_type")

        return len(errors) == 0, errors


def load_all_hexes(
    pipeline: ContentPipeline, data_dir: Optional[Path] = None
) -> HexDirectoryLoadResult:
    """
    Convenience function to load all hexes from the default directory.

    Args:
        pipeline: ContentPipeline for storage
        data_dir: Override default data directory

    Returns:
        HexDirectoryLoadResult with load statistics
    """
    if data_dir is None:
        # Default to project data directory
        data_dir = Path(__file__).parent.parent.parent / "data" / "content" / "hexes"

    loader = HexDataLoader(pipeline)
    return loader.load_directory(data_dir)


def create_sample_hex_json(output_path: Path) -> None:
    """
    Create a sample hex JSON file for testing.

    Args:
        output_path: Path to write sample file
    """
    sample_data = {
        "hex_id": "0101",
        "coordinates": [1, 1],
        "name": "The Spectral Manse",
        "tagline": "A barren expanse of stagnant pools. The keening wind carries strains of distant violin music.",
        "region": "Northern Scratch",
        "terrain_type": "bog",
        "terrain_description": "Bog (3), Northern Scratch",
        "terrain_difficulty": 3,
        "procedural": {
            "lost_chance": "2-in-6",
            "encounter_chance": "2-in-6",
            "encounter_notes": "Encounters are 2-in-6 likely to be with a bewildered banshee heading to a ball at the Spectral Manse",
            "foraging_results": "Successful foraging yields 1d2 portions of Bosun's Balm, in addition to the normal results",
            "foraging_special": ["Bosun's Balm (1d2 portions)"],
        },
        "description": "A barren expanse of stagnant pools. The keening wind carries strains of distant violin music.",
        "points_of_interest": [
            {
                "name": "The Spectral Manse",
                "poi_type": "manse",
                "description": "A thicket of twisted blackthorns stands amid a treacherous region of rivulets and sodden moss carpets.",
                "tagline": None,
                "entering": "The front door opens freely, or a window can be forced.",
                "interior": "The manor exists in an odd dimension, halfway between Fairy and the mortal world.",
                "exploring": "Roll on the Rooms and Encounters tables for each room entered.",
                "leaving": "With the exception of any of Lord Hobbled-and-Blackened's possessions, items from the manse evaporate into mist when taken into the real world.",
                "inhabitants": "Lord Hobbled-and-Blackened is imprisoned in the manse with a number of spectral guests.",
                "roll_tables": [],
                "npcs": ["lord_hobbled_and_blackened"],
                "special_features": [],
                "secrets": [],
                "is_dungeon": True,
                "dungeon_levels": None,
            }
        ],
        "roll_tables": [],
        "npcs": [
            {
                "npc_id": "lord_hobbled_and_blackened",
                "name": "Lord Hobbled-and-Blackened",
                "title": None,
                "description": "A gaunt, icicle-thin frost elf courtier dressed in flamboyant white lace and a ruff of hoarfrost.",
                "kindred": "Frost Elf",
                "alignment": "Neutral",
                "demeanor": ["Manic", "twitchy fingers"],
                "speech": "Rapid babbling, laughing",
                "languages": ["Woldish", "High Elfish"],
                "desires": ["Freedom from the manse", "To see Ygraine once more"],
                "secrets": [
                    "Once a court musician to Prince Mallowheart",
                    "Imprisoned here for falling in love with Ygraine Mordlin",
                ],
                "possessions": [
                    "Magical violin, which when played skilfully can cast the arcane spell Dominate once a week (worth 10,000gp)"
                ],
                "location": "The Spectral Manse",
                "stat_reference": "frost elf courtier (DMB)",
                "is_combatant": True,
            }
        ],
        "items": [],
        "secrets": [],
        "dm_notes": "",
        "adjacent_hexes": [],
        "roads": [],
        "_metadata": {
            "source_file": "../data/pdfs/core/Dolmenwood_Campaign_Book.pdf",
            "pages": [192],
            "extraction_note": "Review and correct this data before importing",
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)

    logger.info(f"Created sample hex JSON at {output_path}")
