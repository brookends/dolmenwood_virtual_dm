"""
Rules Retriever for Dolmenwood Virtual DM.

Implements ChromaDB vector storage with context-aware retrieval from Section 7.5.
Provides semantic search over game content (rules, lore, NPCs, locations).

The retriever searches different content based on game state:
- In combat -> search combat rules + monster stats
- In hex -> search hex data + relevant encounters
- Talking to NPC -> search NPC profile + faction lore
- In adventure -> prioritize adventure-specific content
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import logging

from src.game_state.state_machine import GameState
from src.data_models import (
    SourceType,
    SourceReference,
)


logger = logging.getLogger(__name__)


class ContentCategory(str, Enum):
    """Categories for content indexing."""

    RULES = "rules"
    LORE = "lore"
    HEX = "hex"
    NPC = "npc"
    MONSTER = "monster"
    SPELL = "spell"
    ITEM = "item"
    FACTION = "faction"
    SETTLEMENT = "settlement"
    DUNGEON = "dungeon"
    ENCOUNTER = "encounter"


@dataclass
class SearchResult:
    """A search result with metadata."""

    content_id: str
    category: ContentCategory
    text: str
    metadata: dict[str, Any]
    score: float  # Similarity score (higher = more relevant)
    source: Optional[SourceReference] = None


@dataclass
class SearchContext:
    """Context for search to enable context-aware retrieval."""

    game_state: GameState
    current_hex: Optional[str] = None
    current_npc: Optional[str] = None
    current_monster: Optional[str] = None
    active_faction: Optional[str] = None
    current_dungeon: Optional[str] = None
    tags: list[str] = field(default_factory=list)


@dataclass
class IndexedDocument:
    """A document indexed in the vector store."""

    doc_id: str
    category: ContentCategory
    text: str
    metadata: dict[str, Any]
    embedding: Optional[list[float]] = None


class RulesRetriever:
    """
    Context-aware retrieval system for game content.

    Uses ChromaDB for vector storage and semantic search.
    Automatically adjusts search based on current game state
    to return the most relevant content.

    When ChromaDB is not available, falls back to simple
    keyword-based search.
    """

    # Category weights by game state (higher = more relevant)
    STATE_CATEGORY_WEIGHTS = {
        GameState.WILDERNESS_TRAVEL: {
            ContentCategory.HEX: 2.0,
            ContentCategory.ENCOUNTER: 1.5,
            ContentCategory.MONSTER: 1.2,
            ContentCategory.RULES: 1.0,
        },
        GameState.ENCOUNTER: {
            ContentCategory.MONSTER: 2.0,
            ContentCategory.ENCOUNTER: 1.8,
            ContentCategory.RULES: 1.5,
        },
        GameState.DUNGEON_EXPLORATION: {
            ContentCategory.DUNGEON: 2.0,
            ContentCategory.MONSTER: 1.5,
            ContentCategory.RULES: 1.2,
        },
        GameState.COMBAT: {
            ContentCategory.RULES: 2.0,
            ContentCategory.MONSTER: 1.8,
            ContentCategory.SPELL: 1.5,
        },
        GameState.SETTLEMENT_EXPLORATION: {
            ContentCategory.SETTLEMENT: 2.0,
            ContentCategory.NPC: 1.8,
            ContentCategory.FACTION: 1.5,
        },
        GameState.SOCIAL_INTERACTION: {
            ContentCategory.NPC: 2.0,
            ContentCategory.FACTION: 1.8,
            ContentCategory.LORE: 1.5,
        },
        GameState.DOWNTIME: {
            ContentCategory.RULES: 1.5,
            ContentCategory.SETTLEMENT: 1.2,
            ContentCategory.FACTION: 1.0,
        },
    }

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: str = "dolmenwood_content",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize the rules retriever.

        Args:
            persist_directory: Directory for ChromaDB persistence
            collection_name: Name of the ChromaDB collection
            embedding_model: Sentence transformer model for embeddings
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        self._chroma_available = False
        self._client = None
        self._collection = None
        self._embedding_function = None

        # Fallback storage for when ChromaDB is not available
        self._fallback_documents: dict[str, IndexedDocument] = {}

        # Try to initialize ChromaDB
        self._init_chromadb()

        logger.info(f"RulesRetriever initialized (ChromaDB available: {self._chroma_available})")

    def _init_chromadb(self) -> None:
        """Initialize ChromaDB if available."""
        try:
            import chromadb
            from chromadb.config import Settings

            # Create client
            if self.persist_directory:
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_directory), settings=Settings(anonymized_telemetry=False)
                )
            else:
                self._client = chromadb.Client(Settings(anonymized_telemetry=False))

            # Try to use sentence transformers for embeddings
            try:
                from chromadb.utils import embedding_functions

                self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.embedding_model
                )
            except ImportError:
                logger.warning("sentence-transformers not available, using default embeddings")
                self._embedding_function = None

            # Get or create collection
            if self._embedding_function:
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=self._embedding_function,
                    metadata={"hnsw:space": "cosine"},
                )
            else:
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name, metadata={"hnsw:space": "cosine"}
                )

            self._chroma_available = True
            logger.info("ChromaDB initialized successfully")

        except ImportError:
            logger.warning("ChromaDB not available, using fallback storage")
            self._chroma_available = False

        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            self._chroma_available = False

    # =========================================================================
    # INDEXING
    # =========================================================================

    def index_document(
        self,
        doc_id: str,
        category: ContentCategory,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Index a document for retrieval.

        Args:
            doc_id: Unique document identifier
            category: Content category
            text: Document text content
            metadata: Additional metadata

        Returns:
            True if indexed successfully
        """
        metadata = metadata or {}
        metadata["category"] = category.value
        metadata["indexed_at"] = datetime.now().isoformat()

        if self._chroma_available and self._collection:
            try:
                self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
                return True
            except Exception as e:
                logger.error(f"Error indexing document: {e}")
                return False
        else:
            # Fallback storage
            self._fallback_documents[doc_id] = IndexedDocument(
                doc_id=doc_id,
                category=category,
                text=text,
                metadata=metadata,
            )
            return True

    def index_hex(self, hex_id: str, hex_data: dict[str, Any]) -> bool:
        """Index hex location data."""
        text_parts = [
            f"Hex {hex_id}",
            hex_data.get("name", ""),
            f"Terrain: {hex_data.get('terrain', 'unknown')}",
            hex_data.get("description", ""),
        ]

        # Add features
        for feature in hex_data.get("features", []):
            text_parts.append(feature.get("name", ""))
            text_parts.append(feature.get("description", ""))

        # Add landmarks
        for landmark in hex_data.get("landmarks", []):
            text_parts.append(landmark.get("name", ""))
            text_parts.append(landmark.get("description", ""))

        text = " ".join(filter(None, text_parts))

        metadata = {
            "hex_id": hex_id,
            "terrain": hex_data.get("terrain", ""),
            "name": hex_data.get("name", ""),
            "has_fairy": bool(hex_data.get("fairy_influence")),
            "has_drune": hex_data.get("drune_presence", False),
        }

        return self.index_document(f"hex_{hex_id}", ContentCategory.HEX, text, metadata)

    def index_npc(self, npc_id: str, npc_data: dict[str, Any]) -> bool:
        """Index NPC data."""
        text_parts = [
            npc_data.get("name", ""),
            npc_data.get("title", ""),
            f"Location: {npc_data.get('location', '')}",
            f"Faction: {npc_data.get('faction', '')}",
            f"Personality: {npc_data.get('personality', '')}",
        ]

        # Add goals
        for goal in npc_data.get("goals", []):
            text_parts.append(f"Goal: {goal}")

        # Add dialogue hooks
        for hook in npc_data.get("dialogue_hooks", []):
            text_parts.append(hook)

        text = " ".join(filter(None, text_parts))

        metadata = {
            "npc_id": npc_id,
            "name": npc_data.get("name", ""),
            "location": npc_data.get("location", ""),
            "faction": npc_data.get("faction", ""),
        }

        return self.index_document(f"npc_{npc_id}", ContentCategory.NPC, text, metadata)

    def index_monster(self, monster_id: str, monster_data: dict[str, Any]) -> bool:
        """Index monster data."""
        text_parts = [
            monster_data.get("name", ""),
            monster_data.get("description", ""),
        ]

        # Add habitat info
        for habitat in monster_data.get("habitat", []):
            text_parts.append(f"Found in: {habitat}")

        # Add stat summary
        stat_block = monster_data.get("stat_block", {})
        if stat_block:
            text_parts.append(f"HD: {stat_block.get('hit_dice', '')}")
            text_parts.append(f"AC: {stat_block.get('armor_class', '')}")

        text = " ".join(filter(None, text_parts))

        metadata = {
            "monster_id": monster_id,
            "name": monster_data.get("name", ""),
            "habitat": monster_data.get("habitat", []),
        }

        return self.index_document(f"monster_{monster_id}", ContentCategory.MONSTER, text, metadata)

    def index_rule(self, rule_id: str, rule_text: str, rule_category: str = "general") -> bool:
        """Index a game rule."""
        metadata = {
            "rule_id": rule_id,
            "rule_category": rule_category,
        }
        return self.index_document(f"rule_{rule_id}", ContentCategory.RULES, rule_text, metadata)

    def index_lore(self, lore_id: str, lore_text: str, topic: str = "general") -> bool:
        """Index lore/background information."""
        metadata = {
            "lore_id": lore_id,
            "topic": topic,
        }
        return self.index_document(f"lore_{lore_id}", ContentCategory.LORE, lore_text, metadata)

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search(
        self,
        query: str,
        context: Optional[SearchContext] = None,
        n_results: int = 5,
        categories: Optional[list[ContentCategory]] = None,
    ) -> list[SearchResult]:
        """
        Search for relevant content.

        Args:
            query: Search query
            context: Optional search context for state-aware retrieval
            n_results: Maximum number of results
            categories: Limit search to specific categories

        Returns:
            List of SearchResult ordered by relevance
        """
        if self._chroma_available and self._collection:
            return self._search_chromadb(query, context, n_results, categories)
        else:
            return self._search_fallback(query, context, n_results, categories)

    def _search_chromadb(
        self,
        query: str,
        context: Optional[SearchContext],
        n_results: int,
        categories: Optional[list[ContentCategory]],
    ) -> list[SearchResult]:
        """Search using ChromaDB."""
        # Build where clause for category filtering
        where = None
        if categories:
            if len(categories) == 1:
                where = {"category": categories[0].value}
            else:
                where = {"category": {"$in": [c.value for c in categories]}}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results * 2,  # Get more results for re-ranking
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            search_results = []
            if results and results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    text = results["documents"][0][i] if results["documents"] else ""
                    distance = results["distances"][0][i] if results["distances"] else 1.0

                    # Convert distance to similarity score (ChromaDB uses L2 distance)
                    score = 1.0 / (1.0 + distance)

                    # Apply context-based re-ranking
                    if context:
                        score = self._rerank_by_context(score, metadata, context)

                    category = ContentCategory(metadata.get("category", "rules"))

                    search_results.append(
                        SearchResult(
                            content_id=doc_id,
                            category=category,
                            text=text,
                            metadata=metadata,
                            score=score,
                        )
                    )

            # Sort by score and limit results
            search_results.sort(key=lambda x: x.score, reverse=True)
            return search_results[:n_results]

        except Exception as e:
            logger.error(f"ChromaDB search error: {e}")
            return []

    def _search_fallback(
        self,
        query: str,
        context: Optional[SearchContext],
        n_results: int,
        categories: Optional[list[ContentCategory]],
    ) -> list[SearchResult]:
        """Simple keyword-based fallback search."""
        query_lower = query.lower()
        query_terms = query_lower.split()

        results = []

        for doc_id, doc in self._fallback_documents.items():
            # Filter by category
            if categories and doc.category not in categories:
                continue

            # Simple keyword matching
            text_lower = doc.text.lower()
            score = 0.0

            for term in query_terms:
                if term in text_lower:
                    # Count occurrences
                    count = text_lower.count(term)
                    score += count * 0.1

            if score > 0:
                # Apply context-based re-ranking
                if context:
                    score = self._rerank_by_context(score, doc.metadata, context)

                results.append(
                    SearchResult(
                        content_id=doc_id,
                        category=doc.category,
                        text=doc.text,
                        metadata=doc.metadata,
                        score=score,
                    )
                )

        # Sort by score and limit results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:n_results]

    def _rerank_by_context(
        self, base_score: float, metadata: dict[str, Any], context: SearchContext
    ) -> float:
        """Adjust score based on game context."""
        score = base_score

        # Apply state-based category weights
        category_str = metadata.get("category", "")
        try:
            category = ContentCategory(category_str)
            weights = self.STATE_CATEGORY_WEIGHTS.get(context.game_state, {})
            weight = weights.get(category, 1.0)
            score *= weight
        except ValueError:
            pass

        # Boost if matching current context
        if context.current_hex and metadata.get("hex_id") == context.current_hex:
            score *= 2.0

        if context.current_npc and metadata.get("npc_id") == context.current_npc:
            score *= 2.0

        if context.active_faction and metadata.get("faction") == context.active_faction:
            score *= 1.5

        if context.current_dungeon and metadata.get("dungeon_id") == context.current_dungeon:
            score *= 1.8

        # Check tag matches
        doc_tags = metadata.get("tags", [])
        if isinstance(doc_tags, str):
            doc_tags = [doc_tags]
        for tag in context.tags:
            if tag in doc_tags:
                score *= 1.2

        return score

    def search_contextual(
        self, query: str, game_state: GameState, **context_kwargs
    ) -> list[SearchResult]:
        """
        Context-aware search based on game state.

        This is the main entry point for the retriever during gameplay.
        It automatically adjusts search parameters based on the current
        game state.

        Args:
            query: Search query
            game_state: Current game state
            **context_kwargs: Additional context (current_hex, current_npc, etc.)

        Returns:
            List of relevant SearchResults
        """
        context = SearchContext(game_state=game_state, **context_kwargs)

        # Determine which categories to prioritize
        weights = self.STATE_CATEGORY_WEIGHTS.get(game_state, {})
        if weights:
            # Get categories with weight > 1.0
            priority_categories = [cat for cat, weight in weights.items() if weight > 1.0]
        else:
            priority_categories = None

        return self.search(query, context, categories=priority_categories)

    # =========================================================================
    # SPECIALIZED QUERIES
    # =========================================================================

    def get_combat_rules(self, query: str) -> list[SearchResult]:
        """Get combat-related rules."""
        context = SearchContext(game_state=GameState.COMBAT)
        return self.search(query, context, categories=[ContentCategory.RULES])

    def get_hex_info(self, hex_id: str) -> list[SearchResult]:
        """Get information about a specific hex."""
        return self.search(f"hex {hex_id}", categories=[ContentCategory.HEX])

    def get_npc_info(self, npc_name: str) -> list[SearchResult]:
        """Get information about an NPC."""
        return self.search(npc_name, categories=[ContentCategory.NPC])

    def get_monster_info(self, monster_name: str) -> list[SearchResult]:
        """Get information about a monster."""
        return self.search(monster_name, categories=[ContentCategory.MONSTER])

    def get_faction_info(self, faction_name: str) -> list[SearchResult]:
        """Get information about a faction."""
        return self.search(faction_name, categories=[ContentCategory.FACTION, ContentCategory.LORE])

    # =========================================================================
    # MANAGEMENT
    # =========================================================================

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the index."""
        if self._chroma_available and self._collection:
            try:
                self._collection.delete(ids=[doc_id])
                return True
            except Exception as e:
                logger.error(f"Error deleting document: {e}")
                return False
        else:
            if doc_id in self._fallback_documents:
                del self._fallback_documents[doc_id]
                return True
            return False

    def clear_all(self) -> bool:
        """Clear all indexed documents."""
        if self._chroma_available and self._client:
            try:
                self._client.delete_collection(self.collection_name)
                self._init_chromadb()
                return True
            except Exception as e:
                logger.error(f"Error clearing index: {e}")
                return False
        else:
            self._fallback_documents.clear()
            return True

    def get_statistics(self) -> dict[str, Any]:
        """Get index statistics."""
        if self._chroma_available and self._collection:
            try:
                count = self._collection.count()
                return {
                    "backend": "chromadb",
                    "total_documents": count,
                    "collection_name": self.collection_name,
                }
            except Exception:
                pass

        return {
            "backend": "fallback",
            "total_documents": len(self._fallback_documents),
        }

    def export_index(self, file_path: Path) -> None:
        """Export index to JSON file."""
        if self._chroma_available and self._collection:
            # Get all documents from ChromaDB
            try:
                results = self._collection.get(include=["documents", "metadatas"])
                documents = []
                for i, doc_id in enumerate(results["ids"]):
                    documents.append(
                        {
                            "doc_id": doc_id,
                            "text": results["documents"][i] if results["documents"] else "",
                            "metadata": results["metadatas"][i] if results["metadatas"] else {},
                        }
                    )
            except Exception as e:
                logger.error(f"Error exporting from ChromaDB: {e}")
                documents = []
        else:
            documents = [
                {
                    "doc_id": doc.doc_id,
                    "category": doc.category.value,
                    "text": doc.text,
                    "metadata": doc.metadata,
                }
                for doc in self._fallback_documents.values()
            ]

        with open(file_path, "w") as f:
            json.dump({"documents": documents}, f, indent=2)

        logger.info(f"Exported {len(documents)} documents to {file_path}")

    def import_index(self, file_path: Path) -> int:
        """Import index from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)

        count = 0
        for doc in data.get("documents", []):
            category = ContentCategory(
                doc.get("category", doc.get("metadata", {}).get("category", "rules"))
            )
            if self.index_document(doc["doc_id"], category, doc["text"], doc.get("metadata", {})):
                count += 1

        logger.info(f"Imported {count} documents from {file_path}")
        return count
