"""
Lore Search Interface for Dolmenwood Virtual DM.

Provides optional integration with the vector database for retrieving
game lore, rules, and content to enrich LLM-generated narratives.

Architecture:
- LoreSearchInterface: Abstract protocol for lore retrieval
- VectorLoreSearch: Implementation using RulesRetriever (ChromaDB)
- NullLoreSearch: No-op implementation for when vector DB is disabled
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable
import logging

logger = logging.getLogger(__name__)


class LoreCategory(str, Enum):
    """Categories of lore content for search filtering."""

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
    HISTORY = "history"
    RELIGION = "religion"
    GEOGRAPHY = "geography"


@dataclass
class LoreSearchResult:
    """A single lore search result with source citation."""

    content: str
    source: str  # e.g., "Campaign Book p.42" or "hex_0709.json"
    category: LoreCategory
    relevance: float = 1.0  # 0.0 to 1.0 relevance score
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_citation(self) -> str:
        """Format as a citation string."""
        return f"[{self.source}]"

    def to_enrichment(self) -> str:
        """Format for inclusion in prompts."""
        return f"{self.content} ({self.source})"


@dataclass
class LoreSearchQuery:
    """Query for lore search with optional filters."""

    query: str
    categories: list[LoreCategory] = field(default_factory=list)
    max_results: int = 3
    min_relevance: float = 0.5

    # Context hints for relevance boosting
    current_hex: Optional[str] = None
    current_npc: Optional[str] = None
    current_faction: Optional[str] = None
    tags: list[str] = field(default_factory=list)


@runtime_checkable
class LoreSearchInterface(Protocol):
    """
    Protocol for lore search implementations.

    This allows DMAgent to work with different backends:
    - VectorLoreSearch for full vector DB integration
    - NullLoreSearch for disabled/missing vector DB
    - MockLoreSearch for testing
    """

    def search(self, query: LoreSearchQuery) -> list[LoreSearchResult]:
        """
        Search for lore matching the query.

        Args:
            query: Search query with filters

        Returns:
            List of matching lore results, sorted by relevance
        """
        ...

    def search_simple(
        self,
        query_text: str,
        category: Optional[LoreCategory] = None,
        max_results: int = 3,
    ) -> list[LoreSearchResult]:
        """
        Simplified search interface for common use cases.

        Args:
            query_text: Natural language query
            category: Optional category filter
            max_results: Maximum results to return

        Returns:
            List of matching lore results
        """
        ...

    def is_available(self) -> bool:
        """Check if lore search is functional."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Get status information about the lore search backend."""
        ...


class NullLoreSearch:
    """
    No-op implementation for when vector DB is disabled or unavailable.

    Always returns empty results gracefully.
    """

    def __init__(self, reason: str = "Vector DB disabled"):
        """
        Initialize null lore search.

        Args:
            reason: Why lore search is unavailable
        """
        self._reason = reason
        logger.info(f"NullLoreSearch initialized: {reason}")

    def search(self, query: LoreSearchQuery) -> list[LoreSearchResult]:
        """Return empty results."""
        return []

    def search_simple(
        self,
        query_text: str,
        category: Optional[LoreCategory] = None,
        max_results: int = 3,
    ) -> list[LoreSearchResult]:
        """Return empty results."""
        return []

    def is_available(self) -> bool:
        """Always returns False."""
        return False

    def get_status(self) -> dict[str, Any]:
        """Return status with reason for unavailability."""
        return {
            "available": False,
            "reason": self._reason,
            "backend": "null",
            "document_count": 0,
        }


class VectorLoreSearch:
    """
    Vector database implementation using RulesRetriever.

    Wraps the existing ChromaDB-based RulesRetriever to provide
    lore search functionality to the DM Agent.
    """

    def __init__(self, retriever: Any):
        """
        Initialize with a RulesRetriever instance.

        Args:
            retriever: RulesRetriever from src.vector_db
        """
        self._retriever = retriever
        self._available = retriever is not None
        logger.info(f"VectorLoreSearch initialized, available: {self._available}")

    def search(self, query: LoreSearchQuery) -> list[LoreSearchResult]:
        """
        Search for lore using the vector database.

        Args:
            query: Search query with filters

        Returns:
            List of matching lore results
        """
        if not self._available:
            return []

        try:
            # Build search context for the retriever
            from src.vector_db.rules_retriever import SearchContext, ContentCategory

            # Map LoreCategory to ContentCategory
            category_map = {
                LoreCategory.RULES: ContentCategory.RULES,
                LoreCategory.LORE: ContentCategory.LORE,
                LoreCategory.HEX: ContentCategory.HEX,
                LoreCategory.NPC: ContentCategory.NPC,
                LoreCategory.MONSTER: ContentCategory.MONSTER,
                LoreCategory.SPELL: ContentCategory.SPELL,
                LoreCategory.ITEM: ContentCategory.ITEM,
                LoreCategory.FACTION: ContentCategory.FACTION,
                LoreCategory.SETTLEMENT: ContentCategory.SETTLEMENT,
                LoreCategory.DUNGEON: ContentCategory.DUNGEON,
                LoreCategory.ENCOUNTER: ContentCategory.ENCOUNTER,
            }

            # Build context
            context = SearchContext(
                current_hex=query.current_hex,
                current_npc=query.current_npc,
                current_faction=query.current_faction,
                tags=query.tags,
            )

            # Determine categories to search
            categories = None
            if query.categories:
                categories = [
                    category_map.get(cat, ContentCategory.LORE)
                    for cat in query.categories
                    if cat in category_map
                ]

            # Execute search
            if categories:
                # Filter by categories
                results = self._retriever.search(
                    query=query.query,
                    n_results=query.max_results,
                    categories=categories,
                )
            else:
                # Use contextual search
                results = self._retriever.search_contextual(
                    query=query.query,
                    context=context,
                    n_results=query.max_results,
                )

            # Convert to LoreSearchResult
            lore_results = []
            for result in results:
                # Map ContentCategory back to LoreCategory
                reverse_map = {v: k for k, v in category_map.items()}
                category = reverse_map.get(result.category, LoreCategory.LORE)

                # Build source citation
                source = result.metadata.get("source", "unknown")
                if "page" in result.metadata:
                    source = f"{source} p.{result.metadata['page']}"

                if result.score >= query.min_relevance:
                    lore_results.append(
                        LoreSearchResult(
                            content=result.text,
                            source=source,
                            category=category,
                            relevance=result.score,
                            metadata=result.metadata,
                        )
                    )

            return lore_results

        except Exception as e:
            logger.warning(f"Lore search failed: {e}")
            return []

    def search_simple(
        self,
        query_text: str,
        category: Optional[LoreCategory] = None,
        max_results: int = 3,
    ) -> list[LoreSearchResult]:
        """
        Simplified search interface.

        Args:
            query_text: Natural language query
            category: Optional category filter
            max_results: Maximum results to return

        Returns:
            List of matching lore results
        """
        query = LoreSearchQuery(
            query=query_text,
            categories=[category] if category else [],
            max_results=max_results,
        )
        return self.search(query)

    def is_available(self) -> bool:
        """Check if vector DB is functional."""
        return self._available

    def get_status(self) -> dict[str, Any]:
        """Get status information."""
        if not self._available:
            return {
                "available": False,
                "reason": "Retriever not initialized",
                "backend": "vector",
                "document_count": 0,
            }

        try:
            # Get document count from retriever if available
            doc_count = 0
            if hasattr(self._retriever, "get_document_count"):
                doc_count = self._retriever.get_document_count()

            return {
                "available": True,
                "backend": "chromadb",
                "document_count": doc_count,
                "embedding_model": getattr(self._retriever, "_embedding_model", "unknown"),
            }
        except Exception as e:
            return {
                "available": False,
                "reason": str(e),
                "backend": "vector",
            }


class MockLoreSearch:
    """
    Mock implementation for testing.

    Returns predefined results for specific queries.
    """

    def __init__(self):
        """Initialize with sample lore data."""
        self._mock_data: dict[str, list[LoreSearchResult]] = {}
        self._default_results: list[LoreSearchResult] = []

    def add_mock_result(
        self,
        query_pattern: str,
        content: str,
        source: str = "Mock Source",
        category: LoreCategory = LoreCategory.LORE,
    ) -> None:
        """Add a mock result for a query pattern."""
        if query_pattern not in self._mock_data:
            self._mock_data[query_pattern] = []
        self._mock_data[query_pattern].append(
            LoreSearchResult(
                content=content,
                source=source,
                category=category,
                relevance=0.9,
            )
        )

    def set_default_results(self, results: list[LoreSearchResult]) -> None:
        """Set default results when no pattern matches."""
        self._default_results = results

    def search(self, query: LoreSearchQuery) -> list[LoreSearchResult]:
        """Search mock data."""
        query_lower = query.query.lower()

        # Check for pattern matches
        for pattern, results in self._mock_data.items():
            if pattern.lower() in query_lower:
                return results[: query.max_results]

        return self._default_results[: query.max_results]

    def search_simple(
        self,
        query_text: str,
        category: Optional[LoreCategory] = None,
        max_results: int = 3,
    ) -> list[LoreSearchResult]:
        """Simplified search."""
        query = LoreSearchQuery(
            query=query_text,
            categories=[category] if category else [],
            max_results=max_results,
        )
        return self.search(query)

    def is_available(self) -> bool:
        """Always returns True for mock."""
        return True

    def get_status(self) -> dict[str, Any]:
        """Return mock status."""
        return {
            "available": True,
            "backend": "mock",
            "document_count": sum(len(r) for r in self._mock_data.values()),
        }


def create_lore_search(
    use_vector_db: bool = True,
    mock_embeddings: bool = False,
    retriever: Optional[Any] = None,
) -> LoreSearchInterface:
    """
    Factory function to create the appropriate LoreSearch implementation.

    Args:
        use_vector_db: Whether to use vector DB
        mock_embeddings: Whether to use mock embeddings (testing)
        retriever: Optional pre-configured retriever

    Returns:
        Appropriate LoreSearchInterface implementation
    """
    if not use_vector_db:
        return NullLoreSearch("Vector DB disabled by configuration")

    if mock_embeddings:
        mock = MockLoreSearch()
        # Add some default mock data for testing
        mock.add_mock_result(
            "drune",
            "The Drune are an ancient order of sorcerer-priests who rule the "
            "forest through fear and dark magic.",
            "Campaign Book p.12",
            LoreCategory.FACTION,
        )
        mock.add_mock_result(
            "fairy",
            "Fairy creatures are beings of glamour and caprice, native to the "
            "Otherworld that bleeds into Dolmenwood.",
            "Campaign Book p.8",
            LoreCategory.LORE,
        )
        return mock

    if retriever is not None:
        return VectorLoreSearch(retriever)

    # Try to create a retriever
    try:
        from src.vector_db.rules_retriever import RulesRetriever

        retriever = RulesRetriever()
        return VectorLoreSearch(retriever)
    except ImportError as e:
        logger.info(f"Vector DB not available (missing dependencies): {e}")
        return NullLoreSearch("chromadb or sentence-transformers not installed")
    except Exception as e:
        logger.warning(f"Failed to initialize vector DB: {e}")
        return NullLoreSearch(f"Initialization failed: {e}")
