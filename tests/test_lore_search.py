"""
Validation tests for LoreSearch interface and implementations.

Tests the optional vector DB integration for lore enrichment,
ensuring graceful degradation when dependencies are unavailable.
"""

import pytest
from typing import Any

from src.ai.lore_search import (
    LoreCategory,
    LoreSearchResult,
    LoreSearchQuery,
    NullLoreSearch,
    MockLoreSearch,
    VectorLoreSearch,
    create_lore_search,
)
from src.ai.dm_agent import DMAgent, DMAgentConfig, LLMProvider


class TestNullLoreSearch:
    """Test NullLoreSearch graceful no-op behavior."""

    def test_null_search_returns_empty(self):
        """NullLoreSearch.search() returns empty list."""
        null_search = NullLoreSearch("Testing")
        query = LoreSearchQuery(query="drune ritual practices")
        results = null_search.search(query)
        assert results == []

    def test_null_search_simple_returns_empty(self):
        """NullLoreSearch.search_simple() returns empty list."""
        null_search = NullLoreSearch("Testing")
        results = null_search.search_simple("fairy creatures")
        assert results == []

    def test_null_is_not_available(self):
        """NullLoreSearch reports not available."""
        null_search = NullLoreSearch("Dependencies missing")
        assert null_search.is_available() is False

    def test_null_status_contains_reason(self):
        """NullLoreSearch status includes the reason."""
        reason = "chromadb not installed"
        null_search = NullLoreSearch(reason)
        status = null_search.get_status()

        assert status["available"] is False
        assert status["reason"] == reason
        assert status["backend"] == "null"
        assert status["document_count"] == 0

    def test_null_handles_complex_queries(self):
        """NullLoreSearch handles complex queries without error."""
        null_search = NullLoreSearch()
        query = LoreSearchQuery(
            query="ancient history of the dolmenwood druids",
            categories=[LoreCategory.HISTORY, LoreCategory.FACTION],
            max_results=10,
            min_relevance=0.8,
            current_hex="0709",
            current_npc="elder_oak",
            tags=["magic", "ritual"],
        )
        results = null_search.search(query)
        assert results == []


class TestMockLoreSearch:
    """Test MockLoreSearch for testing scenarios."""

    def test_mock_returns_configured_results(self):
        """MockLoreSearch returns results for matching patterns."""
        mock = MockLoreSearch()
        mock.add_mock_result(
            "drune",
            "The Drune are sorcerer-priests.",
            "Campaign Book p.12",
            LoreCategory.FACTION,
        )

        results = mock.search_simple("Tell me about the drune")
        assert len(results) == 1
        assert "Drune" in results[0].content
        assert results[0].category == LoreCategory.FACTION

    def test_mock_returns_empty_for_no_match(self):
        """MockLoreSearch returns empty for unmatched queries."""
        mock = MockLoreSearch()
        mock.add_mock_result("drune", "Drune content", "source")

        results = mock.search_simple("completely unrelated query")
        assert results == []

    def test_mock_respects_max_results(self):
        """MockLoreSearch respects max_results limit."""
        mock = MockLoreSearch()
        for i in range(5):
            mock.add_mock_result("test", f"Result {i}", f"Source {i}")

        results = mock.search_simple("test", max_results=2)
        assert len(results) == 2

    def test_mock_is_available(self):
        """MockLoreSearch reports available."""
        mock = MockLoreSearch()
        assert mock.is_available() is True

    def test_mock_status(self):
        """MockLoreSearch reports correct status."""
        mock = MockLoreSearch()
        mock.add_mock_result("a", "Content A", "Source")
        mock.add_mock_result("b", "Content B", "Source")

        status = mock.get_status()
        assert status["available"] is True
        assert status["backend"] == "mock"
        assert status["document_count"] == 2

    def test_mock_default_results(self):
        """MockLoreSearch can return default results."""
        mock = MockLoreSearch()
        default_result = LoreSearchResult(
            content="Default lore content",
            source="Default Source",
            category=LoreCategory.LORE,
        )
        mock.set_default_results([default_result])

        results = mock.search_simple("any query at all")
        assert len(results) == 1
        assert results[0].content == "Default lore content"


class TestLoreSearchResult:
    """Test LoreSearchResult dataclass."""

    def test_result_to_citation(self):
        """LoreSearchResult.to_citation() formats correctly."""
        result = LoreSearchResult(
            content="Content here",
            source="Campaign Book p.42",
            category=LoreCategory.RULES,
        )
        assert result.to_citation() == "[Campaign Book p.42]"

    def test_result_to_enrichment(self):
        """LoreSearchResult.to_enrichment() formats correctly."""
        result = LoreSearchResult(
            content="The Drune rule through fear.",
            source="CB p.12",
            category=LoreCategory.FACTION,
        )
        enrichment = result.to_enrichment()
        assert "The Drune rule through fear." in enrichment
        assert "(CB p.12)" in enrichment


class TestCreateLoreSearch:
    """Test the create_lore_search factory function."""

    def test_disabled_returns_null(self):
        """create_lore_search with use_vector_db=False returns NullLoreSearch."""
        lore_search = create_lore_search(use_vector_db=False)
        assert isinstance(lore_search, NullLoreSearch)
        assert lore_search.is_available() is False

    def test_mock_embeddings_returns_mock(self):
        """create_lore_search with mock_embeddings=True returns MockLoreSearch."""
        lore_search = create_lore_search(
            use_vector_db=True,
            mock_embeddings=True,
        )
        assert isinstance(lore_search, MockLoreSearch)
        assert lore_search.is_available() is True

    def test_mock_has_default_data(self):
        """MockLoreSearch from factory has default test data."""
        lore_search = create_lore_search(
            use_vector_db=True,
            mock_embeddings=True,
        )
        # Factory adds "drune" and "fairy" mock data
        drune_results = lore_search.search_simple("drune")
        assert len(drune_results) >= 1
        assert "Drune" in drune_results[0].content

    def test_without_chromadb_returns_null(self):
        """create_lore_search gracefully falls back when chromadb missing."""
        # Without a retriever and with vector DB enabled, it will try to
        # import RulesRetriever which may fail if chromadb not installed
        lore_search = create_lore_search(use_vector_db=True)
        # Should either work or return NullLoreSearch gracefully
        assert hasattr(lore_search, "search")
        assert hasattr(lore_search, "is_available")
        # Should not raise an exception
        status = lore_search.get_status()
        assert "available" in status


class TestVectorLoreSearch:
    """Test VectorLoreSearch with mock retriever."""

    def test_none_retriever_is_unavailable(self):
        """VectorLoreSearch with None retriever is unavailable."""
        vector_search = VectorLoreSearch(retriever=None)
        assert vector_search.is_available() is False

    def test_none_retriever_returns_empty(self):
        """VectorLoreSearch with None retriever returns empty results."""
        vector_search = VectorLoreSearch(retriever=None)
        results = vector_search.search_simple("any query")
        assert results == []

    def test_none_retriever_status(self):
        """VectorLoreSearch with None retriever has correct status."""
        vector_search = VectorLoreSearch(retriever=None)
        status = vector_search.get_status()
        assert status["available"] is False
        assert status["backend"] == "vector"


class TestDMAgentLoreIntegration:
    """Test DMAgent integration with LoreSearch."""

    def test_agent_with_null_lore_search(self):
        """DMAgent works with NullLoreSearch."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        null_search = NullLoreSearch("Testing")
        agent = DMAgent(config, lore_search=null_search)

        assert agent.lore_search_available is False
        results = agent.retrieve_lore("drune")
        assert results == []

    def test_agent_with_mock_lore_search(self):
        """DMAgent works with MockLoreSearch."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        mock_search = MockLoreSearch()
        mock_search.add_mock_result(
            "drune",
            "The Drune are ancient sorcerers.",
            "CB p.12",
            LoreCategory.FACTION,
        )
        agent = DMAgent(config, lore_search=mock_search)

        assert agent.lore_search_available is True
        results = agent.retrieve_lore("drune")
        assert len(results) == 1
        assert "sorcerers" in results[0].content

    def test_agent_default_has_null_search(self):
        """DMAgent defaults to NullLoreSearch when not provided."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        agent = DMAgent(config)

        # Should have a lore search interface (NullLoreSearch)
        assert agent.lore_search_available is False
        results = agent.retrieve_lore("anything")
        assert results == []

    def test_agent_lore_enrichment(self):
        """DMAgent.get_lore_enrichment() formats results for prompts."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        mock_search = MockLoreSearch()
        mock_search.add_mock_result(
            "history",
            "Long ago, the forest was ruled by fey.",
            "Lore p.5",
            LoreCategory.HISTORY,
        )
        agent = DMAgent(config, lore_search=mock_search)

        enrichment = agent.get_lore_enrichment("history of the forest")
        assert "Long ago" in enrichment
        assert "Lore p.5" in enrichment

    def test_agent_lore_status(self):
        """DMAgent.get_lore_status() returns backend status."""
        config = DMAgentConfig(llm_provider=LLMProvider.MOCK)
        mock_search = MockLoreSearch()
        agent = DMAgent(config, lore_search=mock_search)

        status = agent.get_lore_status()
        assert status["available"] is True
        assert status["backend"] == "mock"


class TestVirtualDMLoreIntegration:
    """Test VirtualDM integration with LoreSearch via config."""

    def test_virtual_dm_with_vector_db_disabled(self):
        """VirtualDM with --no-vector-db uses NullLoreSearch."""
        from src.main import VirtualDM, GameConfig

        config = GameConfig(
            use_vector_db=False,
            enable_narration=True,
        )
        dm = VirtualDM(config=config)

        # DM Agent should have lore search disabled
        if dm.dm_agent:
            assert dm.dm_agent.lore_search_available is False

    def test_virtual_dm_with_mock_embeddings(self):
        """VirtualDM with --mock-embeddings uses MockLoreSearch."""
        from src.main import VirtualDM, GameConfig

        config = GameConfig(
            use_vector_db=True,
            mock_embeddings=True,
            enable_narration=True,
        )
        dm = VirtualDM(config=config)

        # DM Agent should have mock lore search available
        if dm.dm_agent:
            assert dm.dm_agent.lore_search_available is True
            # Should have default mock data
            results = dm.dm_agent.retrieve_lore("drune")
            assert len(results) >= 1


class TestGracefulDegradation:
    """Test that the system degrades gracefully without vector DB."""

    def test_no_hard_failures_without_vector_db(self):
        """System works without vector DB dependencies."""
        from src.main import VirtualDM, GameConfig, create_demo_session

        config = GameConfig(
            use_vector_db=False,
            enable_narration=True,
            llm_provider="mock",
        )

        # Should not raise any exceptions
        dm = create_demo_session(config)

        # Should be able to use all features
        assert dm.current_state is not None
        assert dm.get_party() is not None
        assert dm.status() is not None

        # Narration should still work (just without lore enrichment)
        if dm.dm_agent:
            result = dm.dm_agent.describe_hex(
                hex_id="0709",
                terrain="forest",
            )
            assert result is not None

    def test_lore_search_protocol_compliance(self):
        """All implementations satisfy LoreSearchInterface protocol."""
        from src.ai.lore_search import LoreSearchInterface

        # All should have required methods
        implementations = [
            NullLoreSearch(),
            MockLoreSearch(),
            VectorLoreSearch(None),
        ]

        for impl in implementations:
            # Check required methods exist and are callable
            assert callable(getattr(impl, "search", None))
            assert callable(getattr(impl, "search_simple", None))
            assert callable(getattr(impl, "is_available", None))
            assert callable(getattr(impl, "get_status", None))

            # Check runtime_checkable protocol
            assert isinstance(impl, LoreSearchInterface)
