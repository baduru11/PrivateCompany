# backend/tests/test_searcher.py
import pytest
from unittest.mock import MagicMock, patch
from backend.models import SearchPlan, RawCompanySignal


def _make_exa_result(title, url, text="snippet"):
    """Helper to create a mock Exa search result object."""
    r = MagicMock()
    r.title = title
    r.url = url
    r.text = text
    return r


def _make_tavily_result(title, url, content="snippet"):
    """Helper to create a Tavily-style result dict."""
    return {"title": title, "url": url, "content": content}


def test_searcher_explore_uses_exa_and_tavily():
    """In explore mode, Exa is called first. If < 5 results, Tavily supplements."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["AI chips"],
        target_company_count=15,
        sub_sectors=["GPU"],
    )

    # Exa returns only 2 results (below threshold of 5), so Tavily will also be called
    mock_exa = MagicMock()
    mock_exa.search.return_value = MagicMock(results=[
        _make_exa_result("CompanyA", "https://a.com"),
        _make_exa_result("CompanyB", "https://b.com"),
    ])

    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [
            _make_tavily_result("CompanyC", "https://c.com"),
        ]
    }

    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None  # No cache hits

    with (
        patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
    ):
        result = search({"search_plan": plan, "mode": "explore"})

    assert "raw_signals" in result
    assert len(result["raw_signals"]) == 3
    sources = {s.source for s in result["raw_signals"]}
    assert "exa" in sources
    assert "tavily" in sources
    mock_exa.search.assert_called_once()
    mock_tavily.search.assert_called_once()


def test_searcher_deep_dive_uses_tavily():
    """In deep_dive mode, only Tavily is used (no Exa)."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["NVIDIA funding", "NVIDIA investors"],
        target_company_count=1,
        sub_sectors=[],
    )

    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [
            _make_tavily_result("NVIDIA Fund", "https://nvidia.com/funding"),
        ]
    }

    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    with (
        patch("backend.nodes.searcher.get_exa_client") as mock_exa_factory,
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
    ):
        result = search({"search_plan": plan, "mode": "deep_dive"})

    assert "raw_signals" in result
    # Tavily called once per search term
    assert mock_tavily.search.call_count == 2
    # Exa client should never have been created
    mock_exa_factory.assert_not_called()
    # All signals should be from tavily
    for signal in result["raw_signals"]:
        assert signal.source == "tavily"


def test_searcher_deduplicates_by_url():
    """Same URL from different sources appears only once in results."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["AI chips"],
        target_company_count=15,
        sub_sectors=[],
    )

    shared_url = "https://duplicate.com"

    # Exa returns 1 result with shared_url (below 5, so Tavily also fires)
    mock_exa = MagicMock()
    mock_exa.search.return_value = MagicMock(results=[
        _make_exa_result("Duplicate Co", shared_url),
    ])

    # Tavily also returns the same URL
    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [
            _make_tavily_result("Duplicate Co", shared_url),
            _make_tavily_result("UniqueCompany", "https://unique.com"),
        ]
    }

    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    with (
        patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
    ):
        result = search({"search_plan": plan, "mode": "explore"})

    urls = [s.url for s in result["raw_signals"]]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in results"
    assert shared_url in urls
    assert "https://unique.com" in urls
    assert len(result["raw_signals"]) == 2


def test_searcher_uses_cache():
    """If cache has data, the API client is not called."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["cached query"],
        target_company_count=1,
        sub_sectors=[],
    )

    cached_data = [
        RawCompanySignal(
            company_name="CachedCo",
            url="https://cached.com",
            snippet="from cache",
            source="tavily",
        ).model_dump()
    ]

    mock_tavily = MagicMock()
    mock_cache = MagicMock()
    # Cache returns data for tavily queries
    mock_cache.get_api.return_value = cached_data

    with (
        patch("backend.nodes.searcher.get_exa_client") as mock_exa_factory,
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
    ):
        result = search({"search_plan": plan, "mode": "deep_dive"})

    assert len(result["raw_signals"]) == 1
    assert result["raw_signals"][0].company_name == "CachedCo"
    # The actual API should NOT have been called since cache was hit
    mock_tavily.search.assert_not_called()
    mock_exa_factory.assert_not_called()
