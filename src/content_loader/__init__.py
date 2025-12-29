"""Content loading and management module."""

from src.content_loader.content_manager import ContentManager, ContentType, ContentEntry
from src.content_loader.content_pipeline import (
    ContentPipeline,
    DefaultValidator,
    ValidationResult,
    ImportResult,
    BatchImportResult,
    ValidationError,
    ExtractionError,
)
from src.content_loader.pdf_parser import PDFParser, TextParser
from src.content_loader.hex_loader import (
    HexDataLoader,
    HexFileLoadResult,
    HexDirectoryLoadResult,
    HexFileMetadata,
    load_all_hexes,
    create_sample_hex_json,
)
from src.content_loader.monster_loader import (
    MonsterDataLoader,
    MonsterFileLoadResult,
    MonsterDirectoryLoadResult,
    MonsterFileMetadata,
    load_all_monsters,
)
from src.content_loader.monster_registry import (
    MonsterRegistry,
    MonsterLookupResult,
    StatBlockResult,
    NPCStatRequest,
    get_monster_registry,
    reset_monster_registry,
)

__all__ = [
    # Core manager
    "ContentManager",
    "ContentType",
    "ContentEntry",
    # Unified pipeline
    "ContentPipeline",
    "DefaultValidator",
    "ValidationResult",
    "ImportResult",
    "BatchImportResult",
    "ValidationError",
    "ExtractionError",
    # Parsers
    "PDFParser",
    "TextParser",
    # Hex loader
    "HexDataLoader",
    "HexFileLoadResult",
    "HexDirectoryLoadResult",
    "HexFileMetadata",
    "load_all_hexes",
    "create_sample_hex_json",
    # Monster loader
    "MonsterDataLoader",
    "MonsterFileLoadResult",
    "MonsterDirectoryLoadResult",
    "MonsterFileMetadata",
    "load_all_monsters",
    # Monster registry
    "MonsterRegistry",
    "MonsterLookupResult",
    "StatBlockResult",
    "NPCStatRequest",
    "get_monster_registry",
    "reset_monster_registry",
]
