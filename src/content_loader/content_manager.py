"""
Content Manager for Dolmenwood Virtual DM.

Implements the Multi-Source Content Architecture from Section 7 of the specification.
Manages content from multiple sources with automatic conflict resolution based on priority.

Source Types and Priority:
1. CORE_RULEBOOK (Highest) - Player's Book, Campaign Book, Monster Book
2. CAMPAIGN_SETTING - Dolmenwood setting supplements
3. ADVENTURE_MODULE - Published adventures, dungeons
4. HOMEBREW (Lowest) - Custom content, house rules
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic
import logging

from src.data_models import (
    SourceType,
    SourceReference,
    ContentSource,
    HexLocation,
    HexFeature,
    HexNPC,
    HexProcedural,
    NPC,
    Feature,
    Lair,
    Landmark,
    PointOfInterest,
    RollTable,
    RollTableEntry,
    StatBlock,
    Season,
    KnownTopic,
    SecretInfo,
    SecretStatus,
)


logger = logging.getLogger(__name__)

T = TypeVar('T')


class ContentType(str, Enum):
    """Types of content that can be managed."""
    HEX = "hex"
    NPC = "npc"
    MONSTER = "monster"
    SETTLEMENT = "settlement"
    ITEM = "item"
    SPELL = "spell"
    RULE = "rule"
    TABLE = "table"
    ENCOUNTER = "encounter"


@dataclass
class ContentEntry(Generic[T]):
    """A content entry with metadata."""
    content_id: str
    content_type: ContentType
    data: T
    source: SourceReference
    priority: int  # Lower = higher priority
    version: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConflictResolution:
    """Result of resolving a content conflict."""
    winning_source: str
    losing_sources: list[str]
    reason: str
    merged_data: Optional[dict] = None


class ContentManager:
    """
    Manages content from multiple sources with priority-based conflict resolution.

    The ContentManager is the central hub for all game content including:
    - Hex data from the Campaign Book
    - NPC profiles with relationships
    - Monster statistics
    - Settlement information
    - Rules and tables

    Content is stored in SQLite for persistence and indexed for quick retrieval.
    When content conflicts occur (same ID from different sources), the source
    with higher priority wins.
    """

    # Priority mapping (lower number = higher priority)
    SOURCE_PRIORITY = {
        SourceType.CORE_RULEBOOK: 1,
        SourceType.CAMPAIGN_SETTING: 2,
        SourceType.ADVENTURE_MODULE: 3,
        SourceType.HOMEBREW: 4,
    }

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the content manager.

        Args:
            db_path: Path to SQLite database file. If None, uses in-memory database.
        """
        self.db_path = db_path or Path(":memory:")
        self._sources: dict[str, ContentSource] = {}
        self._content_cache: dict[str, dict[str, Any]] = {}

        # Initialize database
        self._init_database()

        logger.info(f"ContentManager initialized with database: {self.db_path}")

    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Content sources table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_sources (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    book_name TEXT NOT NULL,
                    book_code TEXT NOT NULL,
                    version TEXT NOT NULL,
                    file_path TEXT,
                    file_hash TEXT,
                    page_count INTEGER,
                    imported_at TEXT NOT NULL
                )
            """)

            # Content entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_entries (
                    content_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    version TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (content_id, content_type, source_id),
                    FOREIGN KEY (source_id) REFERENCES content_sources(source_id)
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_type
                ON content_entries(content_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_priority
                ON content_entries(priority)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_tags
                ON content_entries(tags)
            """)

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        if str(self.db_path) == ":memory:":
            # For in-memory database, maintain a single connection
            if not hasattr(self, '_memory_conn'):
                self._memory_conn = sqlite3.connect(":memory:")
            return self._memory_conn
        return sqlite3.connect(str(self.db_path))

    # =========================================================================
    # SOURCE MANAGEMENT
    # =========================================================================

    def register_source(self, source: ContentSource) -> None:
        """
        Register a content source.

        Args:
            source: The content source to register
        """
        self._sources[source.source_id] = source

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO content_sources
                (source_id, source_type, book_name, book_code, version,
                 file_path, file_hash, page_count, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source.source_id,
                source.source_type.value,
                source.book_name,
                source.book_code,
                source.version,
                source.file_path,
                source.file_hash,
                source.page_count,
                source.imported_at.isoformat(),
            ))
            conn.commit()

        logger.info(f"Registered source: {source.book_name} ({source.source_id})")

    def get_source(self, source_id: str) -> Optional[ContentSource]:
        """Get a registered source by ID."""
        return self._sources.get(source_id)

    def list_sources(self) -> list[ContentSource]:
        """List all registered sources."""
        return list(self._sources.values())

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file for version tracking."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # =========================================================================
    # CONTENT STORAGE
    # =========================================================================

    def add_content(
        self,
        content_id: str,
        content_type: ContentType,
        data: dict[str, Any],
        source: SourceReference,
        tags: Optional[list[str]] = None,
        version: str = "1.0"
    ) -> bool:
        """
        Add content to the manager.

        If content with the same ID already exists from a different source,
        priority resolution determines which version is the "active" one.

        Args:
            content_id: Unique identifier for the content
            content_type: Type of content
            data: The content data as a dictionary
            source: Reference to the source
            tags: Optional tags for searching
            version: Version string

        Returns:
            True if content was added successfully
        """
        # Get source to determine priority
        source_obj = self._sources.get(source.source_id)
        if not source_obj:
            logger.warning(f"Source {source.source_id} not registered")
            priority = 99  # Low priority for unknown sources
        else:
            priority = self.SOURCE_PRIORITY.get(source_obj.source_type, 99)

        tags = tags or []
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO content_entries
                (content_id, content_type, source_id, priority, version,
                 data_json, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                content_id,
                content_type.value,
                source.source_id,
                priority,
                version,
                json.dumps(data),
                json.dumps(tags),
                now,
                now,
            ))
            conn.commit()

        # Invalidate cache for this content
        cache_key = f"{content_type.value}:{content_id}"
        if cache_key in self._content_cache:
            del self._content_cache[cache_key]

        logger.debug(f"Added content: {content_type.value}/{content_id} from {source.source_id}")
        return True

    def get_content(
        self,
        content_id: str,
        content_type: ContentType
    ) -> Optional[dict[str, Any]]:
        """
        Get content by ID, resolving conflicts by priority.

        Returns the content from the highest-priority source.

        Args:
            content_id: Content identifier
            content_type: Type of content

        Returns:
            Content data dictionary or None if not found
        """
        cache_key = f"{content_type.value}:{content_id}"

        # Check cache first
        if cache_key in self._content_cache:
            return self._content_cache[cache_key]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data_json, source_id, priority
                FROM content_entries
                WHERE content_id = ? AND content_type = ?
                ORDER BY priority ASC
                LIMIT 1
            """, (content_id, content_type.value))

            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                data['_source_id'] = row[1]
                data['_priority'] = row[2]

                # Cache the result
                self._content_cache[cache_key] = data
                return data

        return None

    def get_all_content(
        self,
        content_type: ContentType,
        tags: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """
        Get all content of a specific type.

        For each content_id, only returns the highest-priority version.

        Args:
            content_type: Type of content to retrieve
            tags: Optional tag filter

        Returns:
            List of content dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get highest priority version of each content_id
            cursor.execute("""
                SELECT ce.content_id, ce.data_json, ce.source_id, ce.priority
                FROM content_entries ce
                INNER JOIN (
                    SELECT content_id, MIN(priority) as min_priority
                    FROM content_entries
                    WHERE content_type = ?
                    GROUP BY content_id
                ) grouped
                ON ce.content_id = grouped.content_id
                   AND ce.priority = grouped.min_priority
                WHERE ce.content_type = ?
            """, (content_type.value, content_type.value))

            results = []
            for row in cursor.fetchall():
                data = json.loads(row[1])
                data['_source_id'] = row[2]
                data['_priority'] = row[3]

                # Filter by tags if specified
                if tags:
                    entry_tags = data.get('tags', [])
                    if not any(tag in entry_tags for tag in tags):
                        continue

                results.append(data)

            return results

    def search_content(
        self,
        content_type: ContentType,
        query: str,
        fields: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """
        Search content by text query.

        Args:
            content_type: Type of content to search
            query: Search query string
            fields: Fields to search in (searches all if None)

        Returns:
            List of matching content
        """
        all_content = self.get_all_content(content_type)
        query_lower = query.lower()

        results = []
        for content in all_content:
            # Search in specified fields or all string fields
            search_fields = fields or content.keys()

            for field in search_fields:
                if field.startswith('_'):
                    continue

                value = content.get(field)
                if isinstance(value, str) and query_lower in value.lower():
                    results.append(content)
                    break
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and query_lower in item.lower():
                            results.append(content)
                            break

        return results

    def delete_content(
        self,
        content_id: str,
        content_type: ContentType,
        source_id: Optional[str] = None
    ) -> bool:
        """
        Delete content.

        Args:
            content_id: Content identifier
            content_type: Type of content
            source_id: If specified, only delete from this source

        Returns:
            True if content was deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if source_id:
                cursor.execute("""
                    DELETE FROM content_entries
                    WHERE content_id = ? AND content_type = ? AND source_id = ?
                """, (content_id, content_type.value, source_id))
            else:
                cursor.execute("""
                    DELETE FROM content_entries
                    WHERE content_id = ? AND content_type = ?
                """, (content_id, content_type.value))

            conn.commit()
            deleted = cursor.rowcount > 0

        # Invalidate cache
        cache_key = f"{content_type.value}:{content_id}"
        if cache_key in self._content_cache:
            del self._content_cache[cache_key]

        return deleted

    # =========================================================================
    # CONFLICT RESOLUTION
    # =========================================================================

    def get_content_versions(
        self,
        content_id: str,
        content_type: ContentType
    ) -> list[dict[str, Any]]:
        """
        Get all versions of content from all sources.

        Useful for inspecting conflicts.

        Args:
            content_id: Content identifier
            content_type: Type of content

        Returns:
            List of all versions with source information
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data_json, source_id, priority, version, updated_at
                FROM content_entries
                WHERE content_id = ? AND content_type = ?
                ORDER BY priority ASC
            """, (content_id, content_type.value))

            versions = []
            for row in cursor.fetchall():
                data = json.loads(row[0])
                data['_source_id'] = row[1]
                data['_priority'] = row[2]
                data['_version'] = row[3]
                data['_updated_at'] = row[4]
                versions.append(data)

            return versions

    def resolve_conflict(
        self,
        content_id: str,
        content_type: ContentType
    ) -> Optional[ConflictResolution]:
        """
        Analyze and report on content conflicts.

        Args:
            content_id: Content identifier
            content_type: Type of content

        Returns:
            ConflictResolution describing the resolution, or None if no conflict
        """
        versions = self.get_content_versions(content_id, content_type)

        if len(versions) <= 1:
            return None

        winning = versions[0]
        losing = versions[1:]

        return ConflictResolution(
            winning_source=winning['_source_id'],
            losing_sources=[v['_source_id'] for v in losing],
            reason=f"Priority: {winning['_priority']} < {[v['_priority'] for v in losing]}",
        )

    # =========================================================================
    # HEX DATA MANAGEMENT
    # =========================================================================

    def add_hex(self, hex_data: HexLocation, source: SourceReference) -> bool:
        """
        Add hex location data.

        Args:
            hex_data: HexLocation object
            source: Source reference

        Returns:
            True if added successfully
        """
        data = {
            'hex_id': hex_data.hex_id,
            'terrain': hex_data.terrain,
            'name': hex_data.name,
            'description': hex_data.description,
            'features': [
                {'feature_id': f.feature_id, 'name': f.name, 'description': f.description,
                 'searchable': f.searchable, 'hidden': f.hidden}
                for f in hex_data.features
            ],
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
            'encounter_table': hex_data.encounter_table,
            'adjacent_hexes': hex_data.adjacent_hexes,
            'roads': hex_data.roads,
            'rivers': hex_data.rivers,
        }

        tags = [hex_data.terrain]
        if hex_data.fairy_influence:
            tags.append('fairy')
        if hex_data.drune_presence:
            tags.append('drune')

        return self.add_content(
            hex_data.hex_id,
            ContentType.HEX,
            data,
            source,
            tags=tags
        )

    def get_hex(self, hex_id: str) -> Optional[HexLocation]:
        """
        Get hex location by ID.

        Args:
            hex_id: Hex identifier (e.g., "0709")

        Returns:
            HexLocation object or None
        """
        data = self.get_content(hex_id, ContentType.HEX)
        if not data:
            return None

        return self._dict_to_hex(data)

    def get_hexes_by_terrain(self, terrain: str) -> list[HexLocation]:
        """Get all hexes with a specific terrain type."""
        all_hexes = self.get_all_content(ContentType.HEX, tags=[terrain])
        return [self._dict_to_hex(h) for h in all_hexes]

    def _dict_to_hex(self, data: dict) -> HexLocation:
        """Convert dictionary to HexLocation."""
        # Parse features - handle both new HexFeature and legacy Feature formats
        features = []
        for f in data.get('features', []):
            if 'feature_id' in f:
                # Legacy Feature format - skip or convert
                continue
            else:
                # New HexFeature format
                features.append(HexFeature(
                    name=f.get('name', 'Unknown'),
                    description=f.get('description', ''),
                    feature_type=f.get('feature_type', 'general'),
                    is_hidden=f.get('is_hidden', False),
                    npcs=f.get('npcs', []),
                    monsters=f.get('monsters', []),
                    treasure=f.get('treasure'),
                    hooks=f.get('hooks', []),
                ))

        # Parse coordinates
        coords = data.get('coordinates', [0, 0])
        if isinstance(coords, list) and len(coords) >= 2:
            coordinates = (coords[0], coords[1])
        else:
            coordinates = (0, 0)

        # Parse procedural (new format)
        procedural = None
        proc_data = data.get('procedural')
        if proc_data and isinstance(proc_data, dict):
            procedural = HexProcedural(
                lost_chance=proc_data.get('lost_chance', '1-in-6'),
                encounter_chance=proc_data.get('encounter_chance', '1-in-6'),
                encounter_notes=proc_data.get('encounter_notes', ''),
                foraging_results=proc_data.get('foraging_results', ''),
                foraging_special=proc_data.get('foraging_special', []),
                encounter_modifiers=proc_data.get('encounter_modifiers', []),
                lost_behavior=proc_data.get('lost_behavior'),
                night_hazards=proc_data.get('night_hazards', []),
            )

        # Parse points of interest (new format)
        points_of_interest = []
        for poi_data in data.get('points_of_interest', []):
            if isinstance(poi_data, dict):
                poi = self._dict_to_poi(poi_data)
                points_of_interest.append(poi)

        # Parse roll tables (new format)
        roll_tables = []
        for table_data in data.get('roll_tables', []):
            if isinstance(table_data, dict):
                table = self._dict_to_roll_table(table_data)
                roll_tables.append(table)

        # Parse NPCs - handle both HexNPC format and legacy string format
        npcs = []
        for npc_data in data.get('npcs', []):
            if isinstance(npc_data, dict):
                # Parse known_topics if present
                known_topics = []
                for topic_data in npc_data.get('known_topics', []):
                    known_topics.append(KnownTopic(
                        topic_id=topic_data.get('topic_id', ''),
                        content=topic_data.get('content', ''),
                        keywords=topic_data.get('keywords', []),
                        required_disposition=topic_data.get('required_disposition', -5),
                        category=topic_data.get('category', 'general'),
                        shared=topic_data.get('shared', False),
                        priority=topic_data.get('priority', 0),
                    ))

                # Parse secret_info if present
                secret_info = []
                for secret_data in npc_data.get('secret_info', []):
                    status_str = secret_data.get('status', 'unknown')
                    try:
                        status = SecretStatus(status_str)
                    except ValueError:
                        status = SecretStatus.UNKNOWN
                    secret_info.append(SecretInfo(
                        secret_id=secret_data.get('secret_id', ''),
                        content=secret_data.get('content', ''),
                        hint=secret_data.get('hint', ''),
                        keywords=secret_data.get('keywords', []),
                        required_disposition=secret_data.get('required_disposition', 3),
                        required_trust=secret_data.get('required_trust', 2),
                        can_be_bribed=secret_data.get('can_be_bribed', False),
                        bribe_amount=secret_data.get('bribe_amount', 0),
                        status=status,
                        hint_count=secret_data.get('hint_count', 0),
                    ))

                npc = HexNPC(
                    npc_id=npc_data.get('npc_id', 'unknown'),
                    name=npc_data.get('name', 'Unknown NPC'),
                    description=npc_data.get('description', ''),
                    kindred=npc_data.get('kindred', 'Human'),
                    alignment=npc_data.get('alignment', 'Neutral'),
                    title=npc_data.get('title'),
                    demeanor=npc_data.get('demeanor', []),
                    speech=npc_data.get('speech', ''),
                    languages=npc_data.get('languages', []),
                    desires=npc_data.get('desires', []),
                    secrets=npc_data.get('secrets', []),
                    known_topics=known_topics,
                    secret_info=secret_info,
                    possessions=npc_data.get('possessions', []),
                    location=npc_data.get('location', ''),
                    stat_reference=npc_data.get('stat_reference'),
                    is_combatant=npc_data.get('is_combatant', False),
                    relationships=npc_data.get('relationships', []),
                    faction=npc_data.get('faction'),
                    loyalty=npc_data.get('loyalty', 'loyal'),
                    personal_feelings=npc_data.get('personal_feelings'),
                    binding=npc_data.get('binding'),
                )
                npcs.append(npc)
            else:
                # Legacy format - string, can't convert to HexNPC without more info
                # Store as-is (will remain as string in the list)
                npcs.append(npc_data)

        return HexLocation(
            # Core identification
            hex_id=data['hex_id'],
            coordinates=coordinates,
            name=data.get('name'),
            tagline=data.get('tagline', ''),

            # Terrain and region
            terrain_type=data.get('terrain_type', data.get('terrain', 'forest')),
            terrain_description=data.get('terrain_description', ''),
            terrain_difficulty=data.get('terrain_difficulty', 1),
            region=data.get('region', ''),

            # Descriptions
            description=data.get('description', ''),
            dm_notes=data.get('dm_notes', ''),

            # Procedural rules (new format)
            procedural=procedural,

            # Points of interest (new format)
            points_of_interest=points_of_interest,

            # Roll tables (new format)
            roll_tables=roll_tables,

            # NPCs (new format)
            npcs=npcs,

            # Associated content
            items=data.get('items', []),
            secrets=data.get('secrets', []),

            # Navigation
            adjacent_hexes=data.get('adjacent_hexes', []),
            roads=data.get('roads', []),

            # Source tracking
            page_reference=data.get('page_reference', ''),

            # Legacy fields
            flavour_text=data.get('flavour_text', data.get('tagline', '')),
            travel_point_cost=data.get('travel_point_cost', 1),
            lost_chance=data.get('lost_chance', 1),
            encounter_chance=data.get('encounter_chance', 1),
            special_encounter_chance=data.get('special_encounter_chance', 0),
            encounter_table=data.get('encounter_table'),
            special_encounters=data.get('special_encounters', []),
            features=features,
            ley_lines=data.get('ley_lines'),
            foraging_yields=data.get('foraging_yields', []),
            terrain=data.get('terrain', data.get('terrain_type', 'forest')),
            lairs=[
                Lair(
                    lair_id=l['lair_id'],
                    monster_type=l['monster_type'],
                    monster_count=l.get('monster_count', '1d6'),
                    treasure_type=l.get('treasure_type'),
                )
                for l in data.get('lairs', [])
            ],
            landmarks=[
                Landmark(
                    landmark_id=l['landmark_id'],
                    name=l['name'],
                    description=l.get('description', ''),
                    visible_from_adjacent=l.get('visible_from_adjacent', True),
                )
                for l in data.get('landmarks', [])
            ],
            fairy_influence=data.get('fairy_influence'),
            drune_presence=data.get('drune_presence', False),
            seasonal_variations={
                Season(k): v for k, v in data.get('seasonal_variations', {}).items()
            },
            rivers=data.get('rivers', []),
            source=SourceReference(
                source_id=data.get('_source_id', ''),
                book_code=data.get('_source_id', '').split('_')[0] if data.get('_source_id') else '',
            ),
        )

    def _dict_to_poi(self, data: dict) -> PointOfInterest:
        """Convert dictionary to PointOfInterest."""
        roll_tables = []
        for table_data in data.get('roll_tables', []):
            if isinstance(table_data, dict):
                table = self._dict_to_roll_table(table_data)
                roll_tables.append(table)

        return PointOfInterest(
            name=data.get('name', 'Unknown'),
            poi_type=data.get('poi_type', 'general'),
            description=data.get('description', ''),
            tagline=data.get('tagline'),
            entering=data.get('entering'),
            interior=data.get('interior'),
            exploring=data.get('exploring'),
            leaving=data.get('leaving'),
            inhabitants=data.get('inhabitants'),
            roll_tables=roll_tables,
            npcs=data.get('npcs', []),
            special_features=data.get('special_features', []),
            secrets=data.get('secrets', []),
            is_dungeon=data.get('is_dungeon', False),
            dungeon_levels=data.get('dungeon_levels'),
            quest_hooks=data.get('quest_hooks', []),
            encounter_modifiers=data.get('encounter_modifiers', []),
            item_persistence=data.get('item_persistence'),
            dynamic_layout=data.get('dynamic_layout'),
            availability=data.get('availability'),
        )

    def _dict_to_roll_table(self, data: dict) -> RollTable:
        """Convert dictionary to RollTable."""
        entries = []
        for entry_data in data.get('entries', []):
            if isinstance(entry_data, dict):
                entry = RollTableEntry(
                    roll=entry_data.get('roll', 1),
                    description=entry_data.get('description', ''),
                    title=entry_data.get('title'),
                    monsters=entry_data.get('monsters', []),
                    npcs=entry_data.get('npcs', []),
                    items=entry_data.get('items', []),
                    mechanical_effect=entry_data.get('mechanical_effect'),
                    sub_table=entry_data.get('sub_table'),
                    reaction_conditions=entry_data.get('reaction_conditions'),
                    transportation_effect=entry_data.get('transportation_effect'),
                    time_effect=entry_data.get('time_effect'),
                    quest_hook=entry_data.get('quest_hook'),
                )
                entries.append(entry)

        return RollTable(
            name=data.get('name', 'Unknown Table'),
            die_type=data.get('die_type', 'd6'),
            description=data.get('description', ''),
            entries=entries,
        )

    # =========================================================================
    # NPC DATA MANAGEMENT
    # =========================================================================

    def add_npc(self, npc: NPC, source: SourceReference) -> bool:
        """
        Add NPC data.

        Args:
            npc: NPC object
            source: Source reference

        Returns:
            True if added successfully
        """
        data = {
            'npc_id': npc.npc_id,
            'name': npc.name,
            'title': npc.title,
            'location': npc.location,
            'faction': npc.faction,
            'personality': npc.personality,
            'goals': npc.goals,
            'secrets': npc.secrets,
            'stat_block': self._stat_block_to_dict(npc.stat_block) if npc.stat_block else None,
            'dialogue_hooks': npc.dialogue_hooks,
            'relationships': npc.relationships,
            'disposition': npc.disposition,
        }

        tags = []
        if npc.faction:
            tags.append(npc.faction)
        if npc.location:
            tags.append(npc.location)

        return self.add_content(
            npc.npc_id,
            ContentType.NPC,
            data,
            source,
            tags=tags
        )

    def get_npc(self, npc_id: str) -> Optional[NPC]:
        """Get NPC by ID."""
        data = self.get_content(npc_id, ContentType.NPC)
        if not data:
            return None

        return self._dict_to_npc(data)

    def get_npcs_by_location(self, location: str) -> list[NPC]:
        """Get all NPCs in a location."""
        all_npcs = self.get_all_content(ContentType.NPC, tags=[location])
        return [self._dict_to_npc(n) for n in all_npcs]

    def get_npcs_by_faction(self, faction: str) -> list[NPC]:
        """Get all NPCs in a faction."""
        all_npcs = self.get_all_content(ContentType.NPC, tags=[faction])
        return [self._dict_to_npc(n) for n in all_npcs]

    def _dict_to_npc(self, data: dict) -> NPC:
        """Convert dictionary to NPC."""
        stat_block = None
        if data.get('stat_block'):
            sb = data['stat_block']
            stat_block = StatBlock(
                armor_class=sb['armor_class'],
                hit_dice=sb['hit_dice'],
                hp_current=sb['hp_current'],
                hp_max=sb['hp_max'],
                movement=sb['movement'],
                attacks=sb.get('attacks', []),
                morale=sb.get('morale', 7),
                save_as=sb.get('save_as', ''),
                special_abilities=sb.get('special_abilities', []),
            )

        return NPC(
            npc_id=data['npc_id'],
            name=data['name'],
            title=data.get('title'),
            location=data.get('location', ''),
            faction=data.get('faction'),
            personality=data.get('personality', ''),
            goals=data.get('goals', []),
            secrets=data.get('secrets', []),
            stat_block=stat_block,
            dialogue_hooks=data.get('dialogue_hooks', []),
            relationships=data.get('relationships', {}),
            disposition=data.get('disposition', 0),
            source=SourceReference(
                source_id=data.get('_source_id', ''),
                book_code=data.get('_source_id', '').split('_')[0] if data.get('_source_id') else '',
            ),
        )

    def _stat_block_to_dict(self, sb: StatBlock) -> dict:
        """Convert StatBlock to dictionary."""
        return {
            'armor_class': sb.armor_class,
            'hit_dice': sb.hit_dice,
            'hp_current': sb.hp_current,
            'hp_max': sb.hp_max,
            'movement': sb.movement,
            'attacks': sb.attacks,
            'morale': sb.morale,
            'save_as': sb.save_as,
            'special_abilities': sb.special_abilities,
        }

    # =========================================================================
    # MONSTER DATA MANAGEMENT
    # =========================================================================

    def add_monster(
        self,
        monster_id: str,
        name: str,
        stat_block: StatBlock,
        description: str,
        source: SourceReference,
        habitat: Optional[list[str]] = None,
        treasure_type: Optional[str] = None,
        number_appearing: str = "1d6",
        alignment: str = "neutral",
        tags: Optional[list[str]] = None
    ) -> bool:
        """
        Add monster data.

        Args:
            monster_id: Unique monster identifier
            name: Monster name
            stat_block: Combat statistics
            description: Monster description
            source: Source reference
            habitat: Where monster is found
            treasure_type: Treasure type code
            number_appearing: Dice string for number encountered
            alignment: Monster alignment
            tags: Additional tags

        Returns:
            True if added successfully
        """
        data = {
            'monster_id': monster_id,
            'name': name,
            'stat_block': self._stat_block_to_dict(stat_block),
            'description': description,
            'habitat': habitat or [],
            'treasure_type': treasure_type,
            'number_appearing': number_appearing,
            'alignment': alignment,
        }

        all_tags = tags or []
        if habitat:
            all_tags.extend(habitat)
        all_tags.append(alignment)

        return self.add_content(
            monster_id,
            ContentType.MONSTER,
            data,
            source,
            tags=all_tags
        )

    def get_monster(self, monster_id: str) -> Optional[dict[str, Any]]:
        """Get monster by ID."""
        return self.get_content(monster_id, ContentType.MONSTER)

    def get_monsters_by_habitat(self, habitat: str) -> list[dict[str, Any]]:
        """Get all monsters in a habitat."""
        return self.get_all_content(ContentType.MONSTER, tags=[habitat])

    # =========================================================================
    # IMPORT/EXPORT
    # =========================================================================

    def export_to_json(self, file_path: Path) -> None:
        """
        Export all content to JSON file.

        Args:
            file_path: Output file path
        """
        export_data = {
            'sources': [],
            'content': {},
        }

        # Export sources
        for source in self._sources.values():
            export_data['sources'].append({
                'source_id': source.source_id,
                'source_type': source.source_type.value,
                'book_name': source.book_name,
                'book_code': source.book_code,
                'version': source.version,
                'file_path': source.file_path,
                'file_hash': source.file_hash,
            })

        # Export content by type
        for content_type in ContentType:
            content_list = self.get_all_content(content_type)
            if content_list:
                export_data['content'][content_type.value] = content_list

        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported content to {file_path}")

    def import_from_json(self, file_path: Path) -> int:
        """
        Import content from JSON file.

        Args:
            file_path: Input file path

        Returns:
            Number of content entries imported
        """
        with open(file_path, 'r') as f:
            import_data = json.load(f)

        count = 0

        # Import sources first
        for source_data in import_data.get('sources', []):
            source = ContentSource(
                source_id=source_data['source_id'],
                source_type=SourceType(source_data['source_type']),
                book_name=source_data['book_name'],
                book_code=source_data['book_code'],
                version=source_data['version'],
                file_path=source_data.get('file_path', ''),
                file_hash=source_data.get('file_hash'),
            )
            self.register_source(source)

        # Import content
        for content_type_str, content_list in import_data.get('content', {}).items():
            content_type = ContentType(content_type_str)

            for content in content_list:
                source_id = content.pop('_source_id', 'imported')
                content.pop('_priority', None)
                content_id = content.get(f'{content_type_str}_id') or content.get('hex_id') or content.get('npc_id') or content.get('monster_id')

                if content_id:
                    self.add_content(
                        content_id,
                        content_type,
                        content,
                        SourceReference(source_id=source_id, book_code='imported'),
                    )
                    count += 1

        logger.info(f"Imported {count} content entries from {file_path}")
        return count

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict[str, Any]:
        """Get content statistics."""
        stats = {
            'sources': len(self._sources),
            'content_counts': {},
            'total_entries': 0,
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for content_type in ContentType:
                cursor.execute("""
                    SELECT COUNT(DISTINCT content_id)
                    FROM content_entries
                    WHERE content_type = ?
                """, (content_type.value,))
                count = cursor.fetchone()[0]
                stats['content_counts'][content_type.value] = count
                stats['total_entries'] += count

        return stats
