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
]
