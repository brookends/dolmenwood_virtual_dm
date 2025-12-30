"""
Unified Content Pipeline for Dolmenwood Virtual DM.

Integrates ContentManager (structured storage) and RulesRetriever (vector search)
into a single coherent system with automatic indexing and validation.

This is the primary interface for all content operations:
- Extraction from PDFs
- Validation and normalization
- Storage in SQLite
- Indexing in vector store
- Retrieval with context-aware search
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, TypeVar

from src.data_models import (
    ContentSource,
    Feature,
    HexFeature,
    HexLocation,
    HexNPC,
    HexProcedural,
    Lair,
    Landmark,
    NPC,
    PointOfInterest,
    RollTable,
    RollTableEntry,
    Season,
    SourceReference,
    SourceType,
    StatBlock,
)
from src.content_loader.content_manager import ContentManager, ContentType
from src.content_loader.pdf_parser import PDFParser, TextParser
from src.vector_db.rules_retriever import ContentCategory, RulesRetriever, SearchContext, SearchResult
from src.game_state.state_machine import GameState


logger = logging.getLogger(__name__)

T = TypeVar('T')


class ValidationError(Exception):
    """Raised when content fails validation."""
    pass


class ExtractionError(Exception):
    """Raised when content extraction fails."""
    pass


@dataclass
class ValidationResult:
    """Result of content validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_data: Optional[dict[str, Any]] = None


@dataclass
class ImportResult:
    """Result of a content import operation."""
    success: bool
    content_id: str
    content_type: ContentType
    source_id: str
    indexed: bool = False
    validation: Optional[ValidationResult] = None
    error: Optional[str] = None


@dataclass
class BatchImportResult:
    """Result of a batch import operation."""
    total: int
    successful: int
    failed: int
    results: list[ImportResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successful / self.total if self.total > 0 else 0.0


class ContentValidator(Protocol):
    """Protocol for content validators."""
    def validate(self, data: dict[str, Any], content_type: ContentType) -> ValidationResult:
        ...


class DefaultValidator:
    """Default content validator with basic checks."""

    # Required fields by content type
    REQUIRED_FIELDS = {
        ContentType.HEX: ['hex_id'],
        ContentType.NPC: ['npc_id', 'name'],
        ContentType.MONSTER: ['monster_id', 'name'],  # Stats validated separately
        ContentType.SETTLEMENT: ['settlement_id', 'name'],
        ContentType.ITEM: ['item_id', 'name'],
        ContentType.SPELL: ['spell_id', 'name', 'level'],
        ContentType.RULE: ['rule_id', 'text'],
        ContentType.TABLE: ['table_id', 'entries'],
        ContentType.ENCOUNTER: ['encounter_id'],
    }

    # Valid terrain types for Dolmenwood
    VALID_TERRAINS = {
        'forest', 'deep_forest', 'river', 'lake', 'swamp', 'marsh', 'bog',
        'hills', 'mountains', 'plains', 'farmland', 'moor', 'ruins',
        'settlement', 'road', 'trail', 'grassland', 'woodland'
    }

    def validate(self, data: dict[str, Any], content_type: ContentType) -> ValidationResult:
        """Validate content data."""
        errors = []
        warnings = []
        normalized = dict(data)

        # Check required fields
        required = self.REQUIRED_FIELDS.get(content_type, [])
        for field_name in required:
            if field_name not in data or data[field_name] is None:
                errors.append(f"Missing required field: {field_name}")

        # Type-specific validation
        if content_type == ContentType.HEX:
            normalized, type_errors, type_warnings = self._validate_hex(data)
            errors.extend(type_errors)
            warnings.extend(type_warnings)
        elif content_type == ContentType.NPC:
            normalized, type_errors, type_warnings = self._validate_npc(data)
            errors.extend(type_errors)
            warnings.extend(type_warnings)
        elif content_type == ContentType.MONSTER:
            normalized, type_errors, type_warnings = self._validate_monster(data)
            errors.extend(type_errors)
            warnings.extend(type_warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_data=normalized if len(errors) == 0 else None
        )

    def _validate_hex(self, data: dict) -> tuple[dict, list[str], list[str]]:
        """Validate hex-specific data."""
        errors = []
        warnings = []
        normalized = dict(data)

        # Normalize hex_id format (should be 4 digits like "0709")
        hex_id = data.get('hex_id', '')
        if hex_id:
            # Remove any non-numeric characters and pad
            clean_id = ''.join(c for c in str(hex_id) if c.isdigit())
            if len(clean_id) < 4:
                clean_id = clean_id.zfill(4)
            elif len(clean_id) > 4:
                warnings.append(f"Hex ID '{hex_id}' has more than 4 digits")
            normalized['hex_id'] = clean_id

        # Validate terrain - check terrain_type first, then fallback to terrain
        terrain = data.get('terrain_type', data.get('terrain', '')).lower().replace(' ', '_')
        if terrain and terrain not in self.VALID_TERRAINS:
            warnings.append(f"Unknown terrain type: {terrain}")
        normalized['terrain'] = terrain
        normalized['terrain_type'] = terrain

        # Validate terrain_difficulty (should be 1-4)
        terrain_difficulty = data.get('terrain_difficulty', 1)
        if isinstance(terrain_difficulty, int) and not (1 <= terrain_difficulty <= 4):
            warnings.append(f"Terrain difficulty {terrain_difficulty} outside expected range 1-4")
        normalized['terrain_difficulty'] = terrain_difficulty

        # Ensure new format lists exist
        normalized.setdefault('points_of_interest', [])
        normalized.setdefault('roll_tables', [])
        normalized.setdefault('npcs', [])
        normalized.setdefault('items', [])
        normalized.setdefault('secrets', [])
        normalized.setdefault('adjacent_hexes', [])
        normalized.setdefault('roads', [])

        # Ensure legacy lists exist
        normalized.setdefault('features', [])
        normalized.setdefault('lairs', [])
        normalized.setdefault('landmarks', [])
        normalized.setdefault('rivers', [])
        normalized.setdefault('seasonal_variations', {})
        normalized.setdefault('foraging_yields', [])
        normalized.setdefault('special_encounters', [])

        return normalized, errors, warnings

    def _validate_npc(self, data: dict) -> tuple[dict, list[str], list[str]]:
        """Validate NPC-specific data."""
        errors = []
        warnings = []
        normalized = dict(data)

        # Ensure name is not empty
        if not data.get('name', '').strip():
            errors.append("NPC name cannot be empty")

        # Normalize disposition to integer range (-100 to 100)
        disposition = data.get('disposition', 0)
        if isinstance(disposition, str):
            try:
                disposition = int(disposition)
            except ValueError:
                disposition = 0
                warnings.append("Could not parse disposition, defaulting to 0")
        disposition = max(-100, min(100, disposition))
        normalized['disposition'] = disposition

        # Ensure lists exist
        normalized.setdefault('goals', [])
        normalized.setdefault('secrets', [])
        normalized.setdefault('dialogue_hooks', [])
        normalized.setdefault('relationships', {})

        return normalized, errors, warnings

    def _validate_monster(self, data: dict) -> tuple[dict, list[str], list[str]]:
        """Validate monster-specific data."""
        errors = []
        warnings = []
        normalized = dict(data)

        # Check for required fields - support both new format and legacy stat_block format
        has_new_format = 'armor_class' in data or 'hit_dice' in data
        has_legacy_format = 'stat_block' in data and data['stat_block']

        if has_new_format:
            # New format with top-level stats
            if 'armor_class' not in data:
                warnings.append("Missing armor_class, defaulting to 10")
                normalized['armor_class'] = 10
            else:
                # Normalize AC to integer
                ac = data.get('armor_class')
                if isinstance(ac, str):
                    try:
                        ac = int(ac.split()[0])
                    except (ValueError, IndexError):
                        ac = 10
                        warnings.append("Could not parse AC, defaulting to 10")
                normalized['armor_class'] = ac

            if 'hit_dice' not in data:
                warnings.append("Missing hit_dice, defaulting to 1d8")
                normalized['hit_dice'] = "1d8"

        elif has_legacy_format:
            # Legacy stat_block format
            stat_block = data['stat_block']
            if 'armor_class' not in stat_block:
                warnings.append("Monster stat_block missing armor_class")
            if 'hit_dice' not in stat_block:
                warnings.append("Monster stat_block missing hit_dice")

            # Normalize AC to integer
            ac = stat_block.get('armor_class')
            if isinstance(ac, str):
                try:
                    ac = int(ac.split()[0])
                except (ValueError, IndexError):
                    ac = 10
                    warnings.append("Could not parse AC, defaulting to 10")
            stat_block['armor_class'] = ac
            normalized['stat_block'] = stat_block
        else:
            warnings.append("No stats found, using defaults")
            normalized['armor_class'] = 10
            normalized['hit_dice'] = "1d8"

        # Ensure lists exist
        normalized.setdefault('habitat', [])
        normalized.setdefault('attacks', [])
        normalized.setdefault('damage', [])
        normalized.setdefault('special_abilities', [])
        normalized.setdefault('immunities', [])
        normalized.setdefault('resistances', [])
        normalized.setdefault('vulnerabilities', [])
        normalized.setdefault('traits', [])
        normalized.setdefault('encounter_scenarios', [])
        normalized.setdefault('lair_descriptions', [])

        return normalized, errors, warnings


class ContentPipeline:
    """
    Unified content pipeline integrating storage and search.

    This class provides a single interface for:
    - Importing content from PDFs or JSON
    - Validating and normalizing content
    - Storing in SQLite (via ContentManager)
    - Indexing for search (via RulesRetriever)
    - Retrieving with context-aware search

    Usage:
        pipeline = ContentPipeline()
        pipeline.register_source(source)

        # Import from PDF
        results = pipeline.import_from_pdf(pdf_path, source_ref)

        # Or add content directly
        pipeline.add_hex(hex_data, source_ref)

        # Search with game context
        results = pipeline.search("goblin lair", game_state=GameState.WILDERNESS_TRAVEL)
    """

    # Mapping from ContentType to ContentCategory for indexing
    TYPE_TO_CATEGORY = {
        ContentType.HEX: ContentCategory.HEX,
        ContentType.NPC: ContentCategory.NPC,
        ContentType.MONSTER: ContentCategory.MONSTER,
        ContentType.SETTLEMENT: ContentCategory.SETTLEMENT,
        ContentType.ITEM: ContentCategory.ITEM,
        ContentType.SPELL: ContentCategory.SPELL,
        ContentType.RULE: ContentCategory.RULES,
        ContentType.TABLE: ContentCategory.RULES,
        ContentType.ENCOUNTER: ContentCategory.ENCOUNTER,
    }

    def __init__(
        self,
        db_path: Optional[Path] = None,
        vector_path: Optional[Path] = None,
        validator: Optional[ContentValidator] = None,
        auto_index: bool = True
    ):
        """
        Initialize the content pipeline.

        Args:
            db_path: Path for SQLite database (None for in-memory)
            vector_path: Path for ChromaDB persistence (None for in-memory)
            validator: Custom content validator (uses DefaultValidator if None)
            auto_index: Automatically index content for search when added
        """
        self.content_manager = ContentManager(db_path)
        self.retriever = RulesRetriever(persist_directory=vector_path)
        self.validator = validator or DefaultValidator()
        self.auto_index = auto_index

        # Track import callbacks for extensibility
        self._post_import_callbacks: list[Callable[[ImportResult], None]] = []

        logger.info(f"ContentPipeline initialized (auto_index={auto_index})")

    # =========================================================================
    # SOURCE MANAGEMENT
    # =========================================================================

    def register_source(self, source: ContentSource) -> None:
        """Register a content source."""
        self.content_manager.register_source(source)

    def get_source(self, source_id: str) -> Optional[ContentSource]:
        """Get a registered source."""
        return self.content_manager.get_source(source_id)

    def list_sources(self) -> list[ContentSource]:
        """List all registered sources."""
        return self.content_manager.list_sources()

    # =========================================================================
    # CONTENT ADDITION (with auto-indexing)
    # =========================================================================

    def add_content(
        self,
        content_id: str,
        content_type: ContentType,
        data: dict[str, Any],
        source: SourceReference,
        tags: Optional[list[str]] = None,
        skip_validation: bool = False,
        skip_indexing: bool = False
    ) -> ImportResult:
        """
        Add content with validation and automatic indexing.

        Args:
            content_id: Unique identifier
            content_type: Type of content
            data: Content data dictionary
            source: Source reference
            tags: Optional tags for filtering
            skip_validation: Skip validation step
            skip_indexing: Skip vector indexing

        Returns:
            ImportResult with status and any errors
        """
        # Validate
        validation = None
        if not skip_validation:
            validation = self.validator.validate(data, content_type)
            if not validation.is_valid:
                return ImportResult(
                    success=False,
                    content_id=content_id,
                    content_type=content_type,
                    source_id=source.source_id,
                    validation=validation,
                    error=f"Validation failed: {'; '.join(validation.errors)}"
                )
            # Use normalized data
            if validation.normalized_data:
                data = validation.normalized_data

        # Store in ContentManager
        try:
            self.content_manager.add_content(
                content_id=content_id,
                content_type=content_type,
                data=data,
                source=source,
                tags=tags
            )
        except Exception as e:
            logger.error(f"Failed to store content {content_id}: {e}")
            return ImportResult(
                success=False,
                content_id=content_id,
                content_type=content_type,
                source_id=source.source_id,
                validation=validation,
                error=str(e)
            )

        # Index for search
        indexed = False
        if self.auto_index and not skip_indexing:
            indexed = self._index_content(content_id, content_type, data, source)

        result = ImportResult(
            success=True,
            content_id=content_id,
            content_type=content_type,
            source_id=source.source_id,
            indexed=indexed,
            validation=validation
        )

        # Run post-import callbacks
        for callback in self._post_import_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.warning(f"Post-import callback failed: {e}")

        return result

    def _index_content(
        self,
        content_id: str,
        content_type: ContentType,
        data: dict[str, Any],
        source: SourceReference
    ) -> bool:
        """Index content in the vector store."""
        category = self.TYPE_TO_CATEGORY.get(content_type, ContentCategory.RULES)

        # Build searchable text based on content type
        text = self._build_searchable_text(content_type, data)

        # Build metadata
        metadata = {
            'content_id': content_id,
            'content_type': content_type.value,
            'source_id': source.source_id,
        }

        # Add type-specific metadata
        if content_type == ContentType.HEX:
            metadata['hex_id'] = data.get('hex_id', content_id)
            metadata['terrain'] = data.get('terrain', '')
            metadata['name'] = data.get('name', '')
        elif content_type == ContentType.NPC:
            metadata['npc_id'] = data.get('npc_id', content_id)
            metadata['name'] = data.get('name', '')
            metadata['location'] = data.get('location', '')
            metadata['faction'] = data.get('faction', '')
        elif content_type == ContentType.MONSTER:
            metadata['monster_id'] = data.get('monster_id', content_id)
            metadata['name'] = data.get('name', '')
            metadata['habitat'] = data.get('habitat', [])

        doc_id = f"{content_type.value}_{content_id}"
        return self.retriever.index_document(doc_id, category, text, metadata)

    def _build_searchable_text(self, content_type: ContentType, data: dict) -> str:
        """Build searchable text from content data."""
        parts = []

        if content_type == ContentType.HEX:
            parts.append(f"Hex {data.get('hex_id', '')}")
            parts.append(data.get('name', ''))
            parts.append(data.get('tagline', ''))
            parts.append(f"Terrain: {data.get('terrain_type', data.get('terrain', ''))}")
            parts.append(f"Region: {data.get('region', '')}")
            parts.append(data.get('flavour_text', ''))
            parts.append(data.get('description', ''))

            # Procedural section (new format)
            procedural = data.get('procedural')
            if procedural and isinstance(procedural, dict):
                parts.append(procedural.get('encounter_notes', ''))
                parts.append(procedural.get('foraging_results', ''))
                for forage_special in procedural.get('foraging_special', []):
                    parts.append(f"Foraging: {forage_special}")

            # Points of interest (new format)
            for poi in data.get('points_of_interest', []):
                if isinstance(poi, dict):
                    parts.append(poi.get('name', ''))
                    parts.append(poi.get('description', ''))
                    parts.append(poi.get('tagline', ''))
                    parts.append(f"Type: {poi.get('poi_type', '')}")
                    parts.append(poi.get('entering', ''))
                    parts.append(poi.get('interior', ''))
                    parts.append(poi.get('exploring', ''))
                    parts.append(poi.get('leaving', ''))
                    parts.append(poi.get('inhabitants', ''))
                    # NPCs in POI
                    for npc_id in poi.get('npcs', []):
                        parts.append(f"NPC: {npc_id}")
                    # Secrets in POI
                    for secret in poi.get('secrets', []):
                        parts.append(f"Secret: {secret}")
                    # Roll tables in POI
                    for table in poi.get('roll_tables', []):
                        if isinstance(table, dict):
                            parts.append(f"Table: {table.get('name', '')}")
                            for entry in table.get('entries', []):
                                if isinstance(entry, dict):
                                    parts.append(entry.get('description', ''))
                                    if entry.get('mechanical_effect'):
                                        parts.append(f"Effect: {entry.get('mechanical_effect')}")

            # Hex-level NPCs (new format with full data)
            for npc in data.get('npcs', []):
                if isinstance(npc, dict):
                    parts.append(f"NPC: {npc.get('name', '')}")
                    parts.append(npc.get('description', ''))
                    parts.append(f"Kindred: {npc.get('kindred', '')}")
                    parts.append(npc.get('speech', ''))
                    for desire in npc.get('desires', []):
                        parts.append(f"Desire: {desire}")
                    for secret in npc.get('secrets', []):
                        parts.append(f"Secret: {secret}")
                    for possession in npc.get('possessions', []):
                        parts.append(f"Possession: {possession}")
                else:
                    # Legacy format - just a string
                    parts.append(f"NPC: {npc}")

            # Hex-level roll tables (new format)
            for table in data.get('roll_tables', []):
                if isinstance(table, dict):
                    parts.append(f"Table: {table.get('name', '')}")
                    for entry in table.get('entries', []):
                        if isinstance(entry, dict):
                            parts.append(entry.get('description', ''))

            # Legacy features with expanded data
            for feature in data.get('features', []):
                if isinstance(feature, dict):
                    parts.append(feature.get('name', ''))
                    parts.append(feature.get('description', ''))
                    parts.append(f"Type: {feature.get('feature_type', '')}")
                    # Include NPCs and monsters in features
                    for npc in feature.get('npcs', []):
                        parts.append(f"NPC: {npc}")
                    for monster in feature.get('monsters', []):
                        parts.append(f"Monster: {monster}")
                    if feature.get('treasure'):
                        parts.append(f"Treasure: {feature.get('treasure')}")
                    for hook in feature.get('hooks', []):
                        parts.append(f"Hook: {hook}")

            # Special encounters
            for enc in data.get('special_encounters', []):
                parts.append(f"Special encounter: {enc}")

            # Secrets (for DM search)
            for secret in data.get('secrets', []):
                parts.append(f"Secret: {secret}")

            # Legacy foraging
            for forage in data.get('foraging_yields', []):
                parts.append(f"Foraging: {forage}")

            # Legacy landmarks
            for landmark in data.get('landmarks', []):
                if isinstance(landmark, dict):
                    parts.append(landmark.get('name', ''))
                    parts.append(landmark.get('description', ''))

        elif content_type == ContentType.NPC:
            parts.append(data.get('name', ''))
            parts.append(data.get('title', ''))
            parts.append(f"Location: {data.get('location', '')}")
            parts.append(f"Faction: {data.get('faction', '')}")
            parts.append(data.get('personality', ''))
            for goal in data.get('goals', []):
                parts.append(f"Goal: {goal}")
            for hook in data.get('dialogue_hooks', []):
                parts.append(hook)

        elif content_type == ContentType.MONSTER:
            # Core info
            parts.append(data.get('name', ''))
            parts.append(data.get('description', ''))
            parts.append(data.get('behavior', ''))

            # Classification
            parts.append(f"Type: {data.get('monster_type', '')}")
            parts.append(f"Size: {data.get('size', '')}")
            parts.append(f"Alignment: {data.get('alignment', '')}")
            parts.append(f"Sentience: {data.get('sentience', '')}")

            # Stats for quick reference
            parts.append(f"HD: {data.get('hit_dice', '')}")
            parts.append(f"AC: {data.get('armor_class', '')}")
            parts.append(f"Morale: {data.get('morale', '')}")

            # Attacks
            for attack in data.get('attacks', []):
                parts.append(f"Attack: {attack}")

            # Special abilities (important for search)
            for ability in data.get('special_abilities', []):
                parts.append(f"Ability: {ability}")

            # Immunities/resistances/vulnerabilities
            for immunity in data.get('immunities', []):
                parts.append(f"Immune: {immunity}")
            for resistance in data.get('resistances', []):
                parts.append(f"Resistant: {resistance}")
            for vulnerability in data.get('vulnerabilities', []):
                parts.append(f"Vulnerable: {vulnerability}")

            # Habitat
            for habitat in data.get('habitat', []):
                parts.append(f"Found in: {habitat}")

            # Encounter scenarios (useful for DM search)
            for scenario in data.get('encounter_scenarios', []):
                parts.append(f"Encounter: {scenario}")

            # Traits
            for trait in data.get('traits', []):
                parts.append(f"Trait: {trait}")

            # Legacy stat_block format support
            stat_block = data.get('stat_block', {})
            if stat_block:
                parts.append(f"HD: {stat_block.get('hit_dice', '')}")
                parts.append(f"AC: {stat_block.get('armor_class', '')}")

        elif content_type == ContentType.RULE:
            parts.append(data.get('title', ''))
            parts.append(data.get('text', ''))

        elif content_type == ContentType.SETTLEMENT:
            parts.append(data.get('name', ''))
            parts.append(data.get('description', ''))
            parts.append(f"Population: {data.get('population', '')}")

        else:
            # Generic: include name, title, description, text
            for key in ['name', 'title', 'description', 'text']:
                if key in data:
                    parts.append(str(data[key]))

        return ' '.join(filter(None, parts))

    # =========================================================================
    # TYPED CONTENT ADDITION
    # =========================================================================

    def add_hex(self, hex_data: HexLocation, source: SourceReference) -> ImportResult:
        """Add a hex location."""
        data = self._hex_to_dict(hex_data)
        return self.add_content(
            content_id=hex_data.hex_id,
            content_type=ContentType.HEX,
            data=data,
            source=source,
            tags=[hex_data.terrain] + (['fairy'] if hex_data.fairy_influence else [])
        )

    def add_npc(self, npc: NPC, source: SourceReference) -> ImportResult:
        """Add an NPC."""
        data = self._npc_to_dict(npc)
        tags = []
        if npc.faction:
            tags.append(npc.faction)
        if npc.location:
            tags.append(npc.location)
        return self.add_content(
            content_id=npc.npc_id,
            content_type=ContentType.NPC,
            data=data,
            source=source,
            tags=tags
        )

    def add_monster(
        self,
        monster_id: str,
        name: str,
        stat_block: StatBlock,
        description: str,
        source: SourceReference,
        habitat: Optional[list[str]] = None,
        treasure_type: Optional[str] = None,
        number_appearing: str = "1d6"
    ) -> ImportResult:
        """Add a monster."""
        data = {
            'monster_id': monster_id,
            'name': name,
            'stat_block': {
                'armor_class': stat_block.armor_class,
                'hit_dice': stat_block.hit_dice,
                'hp_current': stat_block.hp_current,
                'hp_max': stat_block.hp_max,
                'movement': stat_block.movement,
                'attacks': stat_block.attacks,
                'morale': stat_block.morale,
                'save_as': stat_block.save_as,
                'special_abilities': stat_block.special_abilities,
            },
            'description': description,
            'habitat': habitat or [],
            'treasure_type': treasure_type,
            'number_appearing': number_appearing,
        }
        return self.add_content(
            content_id=monster_id,
            content_type=ContentType.MONSTER,
            data=data,
            source=source,
            tags=habitat or []
        )

    def add_rule(
        self,
        rule_id: str,
        title: str,
        text: str,
        source: SourceReference,
        category: str = "general"
    ) -> ImportResult:
        """Add a game rule."""
        data = {
            'rule_id': rule_id,
            'title': title,
            'text': text,
            'category': category,
        }
        return self.add_content(
            content_id=rule_id,
            content_type=ContentType.RULE,
            data=data,
            source=source,
            tags=[category]
        )

    # =========================================================================
    # CONTENT RETRIEVAL
    # =========================================================================

    def get_content(self, content_id: str, content_type: ContentType) -> Optional[dict]:
        """Get content by ID (from structured storage)."""
        return self.content_manager.get_content(content_id, content_type)

    def get_hex(self, hex_id: str) -> Optional[HexLocation]:
        """Get a hex location."""
        return self.content_manager.get_hex(hex_id)

    def get_npc(self, npc_id: str) -> Optional[NPC]:
        """Get an NPC."""
        return self.content_manager.get_npc(npc_id)

    def get_monster(self, monster_id: str) -> Optional[dict]:
        """Get a monster."""
        return self.content_manager.get_monster(monster_id)

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search(
        self,
        query: str,
        game_state: Optional[GameState] = None,
        content_types: Optional[list[ContentType]] = None,
        n_results: int = 5,
        **context_kwargs
    ) -> list[SearchResult]:
        """
        Search for content with optional game state context.

        Args:
            query: Search query
            game_state: Current game state for context-aware ranking
            content_types: Limit to specific content types
            n_results: Maximum results to return
            **context_kwargs: Additional context (current_hex, current_npc, etc.)

        Returns:
            List of SearchResult ordered by relevance
        """
        # Convert content types to categories
        categories = None
        if content_types:
            categories = [
                self.TYPE_TO_CATEGORY.get(ct, ContentCategory.RULES)
                for ct in content_types
            ]

        if game_state:
            context = SearchContext(game_state=game_state, **context_kwargs)
            return self.retriever.search(query, context, n_results, categories)
        else:
            return self.retriever.search(query, None, n_results, categories)

    def search_contextual(
        self,
        query: str,
        game_state: GameState,
        **context_kwargs
    ) -> list[SearchResult]:
        """Context-aware search based on game state."""
        return self.retriever.search_contextual(query, game_state, **context_kwargs)

    # =========================================================================
    # IMPORT FROM SOURCES
    # =========================================================================

    def import_from_pdf(
        self,
        pdf_path: Path,
        source: SourceReference,
        content_types: Optional[list[ContentType]] = None
    ) -> BatchImportResult:
        """
        Import content from a PDF file.

        Args:
            pdf_path: Path to PDF file
            source: Source reference
            content_types: Types to extract (None for all)

        Returns:
            BatchImportResult with import statistics
        """
        results = []

        try:
            parser = PDFParser(pdf_path)
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path}: {e}")
            return BatchImportResult(total=0, successful=0, failed=1, results=[
                ImportResult(
                    success=False,
                    content_id="",
                    content_type=ContentType.HEX,
                    source_id=source.source_id,
                    error=f"Failed to open PDF: {e}"
                )
            ])

        # Extract and import hexes
        if content_types is None or ContentType.HEX in content_types:
            hexes = parser.extract_hexes()
            for hex_data in hexes:
                result = self.add_hex(hex_data, source)
                results.append(result)

        # Extract and import NPCs
        if content_types is None or ContentType.NPC in content_types:
            npcs = parser.extract_npcs()
            for npc in npcs:
                result = self.add_npc(npc, source)
                results.append(result)

        # Extract and import monsters
        if content_types is None or ContentType.MONSTER in content_types:
            monsters = parser.extract_monsters()
            for name, stat_block in monsters:
                monster_id = name.lower().replace(' ', '_').replace("'", '')
                result = self.add_monster(
                    monster_id=monster_id,
                    name=name,
                    stat_block=stat_block,
                    description="",
                    source=source
                )
                results.append(result)

        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return BatchImportResult(
            total=len(results),
            successful=successful,
            failed=failed,
            results=results
        )

    def import_from_json(
        self,
        json_path: Path,
        source: SourceReference,
        content_types: Optional[list[ContentType]] = None
    ) -> BatchImportResult:
        """
        Import content from a JSON file.

        Args:
            json_path: Path to JSON file
            source: Source reference
            content_types: Types to extract (None for all)

        Returns:
            BatchImportResult with import statistics
        """
        results = []

        try:
            parser = TextParser(json_path)
        except Exception as e:
            logger.error(f"Failed to open JSON {json_path}: {e}")
            return BatchImportResult(total=0, successful=0, failed=1, results=[
                ImportResult(
                    success=False,
                    content_id="",
                    content_type=ContentType.HEX,
                    source_id=source.source_id,
                    error=f"Failed to open JSON: {e}"
                )
            ])

        # Extract and import hexes
        if content_types is None or ContentType.HEX in content_types:
            hexes = parser.extract_hexes()
            for hex_data in hexes:
                result = self.add_hex(hex_data, source)
                results.append(result)

        # Extract and import NPCs
        if content_types is None or ContentType.NPC in content_types:
            npcs = parser.extract_npcs()
            for npc in npcs:
                result = self.add_npc(npc, source)
                results.append(result)

        # Extract and import monsters
        if content_types is None or ContentType.MONSTER in content_types:
            monsters = parser.extract_monsters()
            for name, stat_block in monsters:
                monster_id = name.lower().replace(' ', '_').replace("'", '')
                result = self.add_monster(
                    monster_id=monster_id,
                    name=name,
                    stat_block=stat_block,
                    description="",
                    source=source
                )
                results.append(result)

        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return BatchImportResult(
            total=len(results),
            successful=successful,
            failed=failed,
            results=results
        )

    # =========================================================================
    # RE-INDEXING
    # =========================================================================

    def reindex_all(self) -> int:
        """
        Re-index all content in the vector store.

        Useful after changing indexing logic or recovering from corruption.

        Returns:
            Number of documents indexed
        """
        self.retriever.clear_all()
        count = 0

        for content_type in ContentType:
            all_content = self.content_manager.get_all_content(content_type)
            for data in all_content:
                content_id = data.get(f'{content_type.value}_id') or data.get('hex_id') or data.get('npc_id') or data.get('monster_id')
                if content_id:
                    source_id = data.get('_source_id', 'unknown')
                    source = SourceReference(source_id=source_id, book_code='')
                    if self._index_content(content_id, content_type, data, source):
                        count += 1

        logger.info(f"Re-indexed {count} documents")
        return count

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def add_post_import_callback(self, callback: Callable[[ImportResult], None]) -> None:
        """Add a callback to run after each content import."""
        self._post_import_callbacks.append(callback)

    def remove_post_import_callback(self, callback: Callable[[ImportResult], None]) -> None:
        """Remove a post-import callback."""
        if callback in self._post_import_callbacks:
            self._post_import_callbacks.remove(callback)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """Get combined statistics from both storage systems."""
        cm_stats = self.content_manager.get_statistics()
        rr_stats = self.retriever.get_statistics()

        return {
            'structured_storage': cm_stats,
            'vector_storage': rr_stats,
            'auto_index_enabled': self.auto_index,
        }

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_all(self, output_dir: Path) -> None:
        """Export all content to files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export structured content
        self.content_manager.export_to_json(output_dir / 'content.json')

        # Export vector index
        self.retriever.export_index(output_dir / 'index.json')

        logger.info(f"Exported all content to {output_dir}")

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _hex_to_dict(self, hex_data: HexLocation) -> dict:
        """Convert HexLocation to dictionary."""
        # Convert features - handle both HexFeature and legacy Feature types
        features_list = []
        for f in hex_data.features:
            if isinstance(f, HexFeature):
                features_list.append({
                    'name': f.name,
                    'description': f.description,
                    'feature_type': f.feature_type,
                    'is_hidden': f.is_hidden,
                    'npcs': f.npcs,
                    'monsters': f.monsters,
                    'treasure': f.treasure,
                    'hooks': f.hooks,
                })
            else:
                # Legacy Feature format
                features_list.append({
                    'name': f.name,
                    'description': f.description,
                    'feature_type': 'general',
                    'is_hidden': getattr(f, 'hidden', False),
                    'npcs': [],
                    'monsters': [],
                    'treasure': None,
                    'hooks': [],
                })

        # Convert procedural
        procedural_dict = None
        if hex_data.procedural:
            procedural_dict = {
                'lost_chance': hex_data.procedural.lost_chance,
                'encounter_chance': hex_data.procedural.encounter_chance,
                'encounter_notes': hex_data.procedural.encounter_notes,
                'foraging_results': hex_data.procedural.foraging_results,
                'foraging_special': hex_data.procedural.foraging_special,
            }

        # Convert points of interest
        poi_list = []
        for poi in hex_data.points_of_interest:
            poi_dict = {
                'name': poi.name,
                'poi_type': poi.poi_type,
                'description': poi.description,
                'tagline': poi.tagline,
                'entering': poi.entering,
                'interior': poi.interior,
                'exploring': poi.exploring,
                'leaving': poi.leaving,
                'inhabitants': poi.inhabitants,
                'npcs': poi.npcs,
                'special_features': poi.special_features,
                'secrets': poi.secrets,
                'is_dungeon': poi.is_dungeon,
                'dungeon_levels': poi.dungeon_levels,
                'roll_tables': [self._roll_table_to_dict(t) for t in poi.roll_tables],
            }
            poi_list.append(poi_dict)

        # Convert roll tables
        roll_tables_list = [self._roll_table_to_dict(t) for t in hex_data.roll_tables]

        # Convert NPCs - handle both HexNPC objects and legacy string format
        npcs_list = []
        for npc in hex_data.npcs:
            if isinstance(npc, HexNPC):
                # Serialize known_topics
                known_topics_list = []
                for topic in npc.known_topics:
                    known_topics_list.append({
                        'topic_id': topic.topic_id,
                        'content': topic.content,
                        'keywords': topic.keywords,
                        'required_disposition': topic.required_disposition,
                        'category': topic.category,
                        'shared': topic.shared,
                        'priority': topic.priority,
                    })

                # Serialize secret_info
                secret_info_list = []
                for secret in npc.secret_info:
                    secret_info_list.append({
                        'secret_id': secret.secret_id,
                        'content': secret.content,
                        'hint': secret.hint,
                        'keywords': secret.keywords,
                        'required_disposition': secret.required_disposition,
                        'required_trust': secret.required_trust,
                        'can_be_bribed': secret.can_be_bribed,
                        'bribe_amount': secret.bribe_amount,
                        'status': secret.status.value,
                        'hint_count': secret.hint_count,
                    })

                npc_dict = {
                    'npc_id': npc.npc_id,
                    'name': npc.name,
                    'description': npc.description,
                    'kindred': npc.kindred,
                    'alignment': npc.alignment,
                    'title': npc.title,
                    'demeanor': npc.demeanor,
                    'speech': npc.speech,
                    'languages': npc.languages,
                    'desires': npc.desires,
                    'secrets': npc.secrets,
                    'possessions': npc.possessions,
                    'location': npc.location,
                    'stat_reference': npc.stat_reference,
                    'is_combatant': npc.is_combatant,
                    'relationships': npc.relationships,
                    'faction': npc.faction,
                    'loyalty': npc.loyalty,
                    'personal_feelings': npc.personal_feelings,
                    'binding': npc.binding,
                }
                # Only include enhanced fields if they have data
                if known_topics_list:
                    npc_dict['known_topics'] = known_topics_list
                if secret_info_list:
                    npc_dict['secret_info'] = secret_info_list
                npcs_list.append(npc_dict)
            else:
                # Legacy format - just a string
                npcs_list.append(npc)

        return {
            # Core identification
            'hex_id': hex_data.hex_id,
            'coordinates': list(hex_data.coordinates) if hex_data.coordinates else [0, 0],
            'name': hex_data.name,
            'tagline': hex_data.tagline,

            # Terrain and region
            'terrain_type': hex_data.terrain_type or hex_data.terrain,
            'terrain_description': hex_data.terrain_description,
            'terrain_difficulty': hex_data.terrain_difficulty,
            'region': hex_data.region,

            # Descriptions
            'flavour_text': hex_data.flavour_text,
            'description': hex_data.description,
            'dm_notes': hex_data.dm_notes,

            # Procedural rules (new format)
            'procedural': procedural_dict,

            # Points of interest (new format)
            'points_of_interest': poi_list,

            # Roll tables (new format)
            'roll_tables': roll_tables_list,

            # Travel mechanics (legacy)
            'travel_point_cost': hex_data.travel_point_cost,
            'lost_chance': hex_data.lost_chance,
            'encounter_chance': hex_data.encounter_chance,
            'special_encounter_chance': hex_data.special_encounter_chance,

            # Encounters (legacy)
            'encounter_table': hex_data.encounter_table,
            'special_encounters': hex_data.special_encounters,

            # Features (legacy)
            'features': features_list,

            # Associated content
            'npcs': npcs_list,
            'items': hex_data.items,
            'secrets': hex_data.secrets,

            # Special properties
            'ley_lines': hex_data.ley_lines,
            'foraging_yields': hex_data.foraging_yields,

            # Source tracking
            'page_reference': hex_data.page_reference,

            # Navigation
            'adjacent_hexes': hex_data.adjacent_hexes,
            'roads': hex_data.roads,

            # Legacy fields (for backward compatibility)
            'terrain': hex_data.terrain or hex_data.terrain_type,
            'lairs': [
                {'lair_id': l.lair_id, 'monster_type': l.monster_type,
                 'monster_count': l.monster_count, 'treasure_type': l.treasure_type}
                for l in hex_data.lairs
            ],
            'landmarks': [
                {'landmark_id': l.landmark_id, 'name': l.name, 'description': l.description,
                 'visible_from_adjacent': l.visible_from_adjacent}
                for l in hex_data.landmarks
            ],
            'fairy_influence': hex_data.fairy_influence,
            'drune_presence': hex_data.drune_presence,
            'seasonal_variations': {
                s.value: v for s, v in hex_data.seasonal_variations.items()
            },
            'rivers': hex_data.rivers,
        }

    def _roll_table_to_dict(self, table: RollTable) -> dict:
        """Convert RollTable to dictionary."""
        entries = []
        for entry in table.entries:
            entries.append({
                'roll': entry.roll,
                'description': entry.description,
                'title': entry.title,
                'monsters': entry.monsters,
                'npcs': entry.npcs,
                'items': entry.items,
                'mechanical_effect': entry.mechanical_effect,
                'sub_table': entry.sub_table,
            })
        return {
            'name': table.name,
            'die_type': table.die_type,
            'description': table.description,
            'entries': entries,
        }

    def _npc_to_dict(self, npc: NPC) -> dict:
        """Convert NPC to dictionary."""
        stat_block_dict = None
        if npc.stat_block:
            stat_block_dict = {
                'armor_class': npc.stat_block.armor_class,
                'hit_dice': npc.stat_block.hit_dice,
                'hp_current': npc.stat_block.hp_current,
                'hp_max': npc.stat_block.hp_max,
                'movement': npc.stat_block.movement,
                'attacks': npc.stat_block.attacks,
                'morale': npc.stat_block.morale,
                'save_as': npc.stat_block.save_as,
                'special_abilities': npc.stat_block.special_abilities,
            }

        return {
            'npc_id': npc.npc_id,
            'name': npc.name,
            'title': npc.title,
            'location': npc.location,
            'faction': npc.faction,
            'personality': npc.personality,
            'goals': npc.goals,
            'secrets': npc.secrets,
            'stat_block': stat_block_dict,
            'dialogue_hooks': npc.dialogue_hooks,
            'relationships': npc.relationships,
            'disposition': npc.disposition,
        }
