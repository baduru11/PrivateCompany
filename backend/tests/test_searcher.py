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


def test_searcher_explore_uses_all_three_providers():
    """In explore mode, all 3 providers run in parallel."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["AI chips"],
        target_company_count=15,
        sub_sectors=["GPU"],
    )

    mock_exa = MagicMock()
    mock_exa.search.return_value = MagicMock(results=[
        _make_exa_result("CompanyA", "https://a.com"),
    ])

    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [
            _make_tavily_result("CompanyB", "https://b.com"),
        ]
    }

    mock_serper_response = MagicMock()
    mock_serper_response.status_code = 200
    mock_serper_response.raise_for_status = MagicMock()
    mock_serper_response.json.return_value = {
        "organic": [
            {"title": "CompanyC", "link": "https://c.com", "snippet": "snippet"},
        ]
    }

    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    with (
        patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_settings") as mock_settings,
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
        patch("httpx.post", return_value=mock_serper_response),
    ):
        mock_settings.return_value = MagicMock(
            exa_api_key="test-exa-key",
            tavily_api_key="test-tavily-key",
            serper_api_key="test-serper-key",
            cache_dir="cache",
        )
        result = search({"search_plan": plan, "mode": "explore"})

    assert "raw_signals" in result
    assert len(result["raw_signals"]) == 3
    sources = {s.source for s in result["raw_signals"]}
    assert sources == {"exa", "tavily", "serper"}
    mock_exa.search.assert_called_once()
    mock_tavily.search.assert_called_once()


def test_searcher_deep_dive_uses_all_three_providers():
    """In deep_dive mode, all 3 providers run in parallel."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["NVIDIA funding", "NVIDIA investors"],
        target_company_count=1,
        sub_sectors=[],
    )

    mock_exa = MagicMock()
    mock_exa.search.return_value = MagicMock(results=[
        _make_exa_result("NVIDIA Exa", "https://nvidia.com/exa"),
    ])

    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [
            _make_tavily_result("NVIDIA Fund", "https://nvidia.com/funding"),
        ]
    }

    mock_serper_response = MagicMock()
    mock_serper_response.status_code = 200
    mock_serper_response.raise_for_status = MagicMock()
    mock_serper_response.json.return_value = {
        "organic": [
            {"title": "NVIDIA Google", "link": "https://nvidia.com/google", "snippet": "from serper"},
        ]
    }

    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    with (
        patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_settings") as mock_settings,
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
        patch("httpx.post", return_value=mock_serper_response),
    ):
        mock_settings.return_value = MagicMock(
            exa_api_key="test-exa-key",
            tavily_api_key="test-tavily-key",
            serper_api_key="test-serper-key",
            cache_dir="cache",
        )
        result = search({"search_plan": plan, "mode": "deep_dive"})

    assert "raw_signals" in result
    # Tavily called once per search term
    assert mock_tavily.search.call_count == 2
    # Exa called once per search term
    assert mock_exa.search.call_count == 2
    # All 3 sources present
    sources = {s.source for s in result["raw_signals"]}
    assert sources == {"exa", "tavily", "serper"}


def test_searcher_deduplicates_by_url():
    """Same URL from different sources appears only once in results."""
    from backend.nodes.searcher import search

    plan = SearchPlan(
        search_terms=["AI chips"],
        target_company_count=15,
        sub_sectors=[],
    )

    shared_url = "https://duplicate.com"

    mock_exa = MagicMock()
    mock_exa.search.return_value = MagicMock(results=[
        _make_exa_result("Duplicate Co", shared_url),
    ])

    # Tavily returns nothing for this test
    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {"results": []}

    # Serper also returns the same URL plus a unique one
    mock_serper_response = MagicMock()
    mock_serper_response.status_code = 200
    mock_serper_response.raise_for_status = MagicMock()
    mock_serper_response.json.return_value = {
        "organic": [
            {"title": "Duplicate Co", "link": shared_url, "snippet": "dup"},
            {"title": "UniqueCompany", "link": "https://unique.com", "snippet": "unique"},
        ]
    }

    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    with (
        patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_settings") as mock_settings,
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
        patch("httpx.post", return_value=mock_serper_response),
    ):
        mock_settings.return_value = MagicMock(
            exa_api_key="test-exa-key",
            tavily_api_key="test-tavily-key",
            serper_api_key="test-serper-key",
            cache_dir="cache",
        )
        result = search({"search_plan": plan, "mode": "explore"})

    urls = [s.url for s in result["raw_signals"]]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in results"
    assert shared_url in urls
    assert "https://unique.com" in urls
    assert len(result["raw_signals"]) == 2


def test_searcher_uses_cache():
    """If cache has data, the actual API search methods are not called."""
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

    mock_exa = MagicMock()
    mock_tavily = MagicMock()
    mock_cache = MagicMock()
    # Cache returns data for all providers
    mock_cache.get_api.return_value = cached_data

    with (
        patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
        patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
        patch("backend.nodes.searcher.get_settings") as mock_settings,
        patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
        patch("httpx.post") as mock_httpx,
    ):
        mock_settings.return_value = MagicMock(
            exa_api_key="test-exa-key",
            tavily_api_key="test-tavily-key",
            serper_api_key="test-serper-key",
            cache_dir="cache",
        )
        result = search({"search_plan": plan, "mode": "deep_dive"})

    # Cache was hit, so actual search APIs should NOT have been called
    mock_exa.search.assert_not_called()
    mock_tavily.search.assert_not_called()
    mock_httpx.assert_not_called()
    # Deduplicated: all 3 providers return same URL, so only 1 result
    assert len(result["raw_signals"]) == 1
    assert result["raw_signals"][0].company_name == "CachedCo"


class TestSearcherTimeoutHandling:
    """Verify API timeouts are handled gracefully (return empty, don't crash)."""

    def test_exa_timeout_returns_empty(self):
        from backend.nodes.searcher import _search_exa

        mock_exa = MagicMock()
        mock_exa.search.side_effect = TimeoutError("Exa timed out")
        mock_cache = MagicMock()
        mock_cache.get_api.return_value = None

        result = _search_exa(mock_exa, "AI chips", 10, mock_cache)
        assert result == []

    def test_tavily_timeout_returns_empty(self):
        from backend.nodes.searcher import _search_tavily

        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = TimeoutError("Tavily timed out")
        mock_cache = MagicMock()
        mock_cache.get_api.return_value = None

        result = _search_tavily(mock_tavily, "AI chips", mock_cache)
        assert result == []

    def test_serper_timeout_returns_empty(self):
        from backend.nodes.searcher import _search_serper

        mock_cache = MagicMock()
        mock_cache.get_api.return_value = None

        with (
            patch("httpx.post", side_effect=TimeoutError("Serper timed out")),
            patch("backend.nodes.searcher.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(serper_api_key="test-key")
            result = _search_serper("AI chips", 10, mock_cache)
        assert result == []

    def test_search_raises_when_all_providers_fail(self):
        from backend.nodes.searcher import search

        plan = SearchPlan(search_terms=["test"], target_company_count=10)
        mock_exa = MagicMock()
        mock_exa.search.side_effect = TimeoutError("down")
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = TimeoutError("down")
        mock_cache = MagicMock()
        mock_cache.get_api.return_value = None

        with (
            patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa),
            patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily),
            patch("backend.nodes.searcher.get_settings") as mock_settings,
            patch("backend.nodes.searcher.get_cache", return_value=mock_cache),
            patch("httpx.post", side_effect=TimeoutError("down")),
        ):
            mock_settings.return_value = MagicMock(
                exa_api_key="test-exa-key",
                tavily_api_key="test-tavily-key",
                serper_api_key="test-serper-key",
                cache_dir="cache",
            )
            with pytest.raises(RuntimeError, match="no results found"):
                search({"search_plan": plan, "mode": "explore"})
