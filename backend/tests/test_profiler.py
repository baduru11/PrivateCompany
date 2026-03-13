# backend/tests/test_profiler.py
import pytest
from unittest.mock import MagicMock, patch, call
from backend.models import RawCompanySignal, CompanyProfile


def _make_signal(company_name: str, url: str, snippet: str = "snippet") -> RawCompanySignal:
    """Helper to create a RawCompanySignal for tests."""
    return RawCompanySignal(
        company_name=company_name,
        url=url,
        snippet=snippet,
        source="tavily",
    )


def _make_profile(name: str, **kwargs) -> CompanyProfile:
    """Helper to create a CompanyProfile for tests."""
    return CompanyProfile(name=name, **kwargs)


def test_profiler_explore_uses_snippets_only():
    """In explore mode, crawl_page should NOT be called."""
    from backend.nodes.profiler import profile

    signals = [
        _make_signal("Acme Corp", "https://acme.com", "Acme builds widgets"),
        _make_signal("Acme Corp", "https://crunchbase.com/acme", "Acme raised $10M"),
    ]

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = _make_profile(
        "Acme Corp",
        description="Acme builds widgets",
        raw_sources=["https://acme.com", "https://crunchbase.com/acme"],
    )
    mock_llm.with_structured_output.return_value = mock_structured

    with (
        patch("backend.nodes.profiler.get_llm", return_value=mock_llm),
        patch("backend.nodes.profiler.crawl_page") as mock_crawl,
    ):
        result = profile({"mode": "explore", "raw_signals": signals})

    # crawl_page must NOT be called in explore mode
    mock_crawl.assert_not_called()
    # LLM should still be called for extraction
    mock_structured.invoke.assert_called_once()
    assert len(result["company_profiles"]) == 1
    assert result["company_profiles"][0].name == "Acme Corp"


def test_profiler_deep_dive_uses_crawl4ai():
    """In deep_dive mode, crawl_page IS called for each unique URL."""
    from backend.nodes.profiler import profile

    signals = [
        _make_signal("Acme Corp", "https://acme.com", "Acme builds widgets"),
        _make_signal("Acme Corp", "https://crunchbase.com/acme", "Acme raised $10M"),
    ]

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = _make_profile(
        "Acme Corp",
        description="Acme builds widgets",
        funding_total="$10M",
        funding_source_url="https://crunchbase.com/acme",
        raw_sources=["https://acme.com", "https://crunchbase.com/acme"],
    )
    mock_llm.with_structured_output.return_value = mock_structured

    with (
        patch("backend.nodes.profiler.get_llm", return_value=mock_llm),
        patch("backend.nodes.profiler.crawl_page", return_value="Full page content here") as mock_crawl,
    ):
        result = profile({"mode": "deep_dive", "raw_signals": signals})

    # crawl_page MUST be called in deep_dive mode (once per unique URL)
    assert mock_crawl.call_count == 2
    mock_crawl.assert_any_call("https://acme.com")
    mock_crawl.assert_any_call("https://crunchbase.com/acme")
    assert len(result["company_profiles"]) == 1


def test_profiler_returns_profiles():
    """Result contains company_profiles list with correct structure."""
    from backend.nodes.profiler import profile

    signals = [
        _make_signal("Acme Corp", "https://acme.com", "Acme builds widgets"),
        _make_signal("Beta Inc", "https://beta.io", "Beta does AI things"),
    ]

    mock_llm = MagicMock()
    mock_structured = MagicMock()

    # Return different profiles for each company
    mock_structured.invoke.side_effect = [
        _make_profile("Acme Corp", description="Acme builds widgets"),
        _make_profile("Beta Inc", description="Beta does AI things"),
    ]
    mock_llm.with_structured_output.return_value = mock_structured

    with (
        patch("backend.nodes.profiler.get_llm", return_value=mock_llm),
        patch("backend.nodes.profiler.crawl_page"),
    ):
        result = profile({"mode": "explore", "raw_signals": signals})

    assert "company_profiles" in result
    assert isinstance(result["company_profiles"], list)
    assert len(result["company_profiles"]) == 2
    names = {p.name for p in result["company_profiles"]}
    assert "Acme Corp" in names
    assert "Beta Inc" in names


def test_profiler_handles_extraction_failure():
    """If LLM fails, still returns a basic profile with just the name."""
    from backend.nodes.profiler import profile

    signals = [
        _make_signal("Failing Corp", "https://failing.com", "Some snippet"),
    ]

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = Exception("LLM extraction failed")
    mock_llm.with_structured_output.return_value = mock_structured

    with (
        patch("backend.nodes.profiler.get_llm", return_value=mock_llm),
        patch("backend.nodes.profiler.crawl_page"),
    ):
        result = profile({"mode": "explore", "raw_signals": signals})

    assert len(result["company_profiles"]) == 1
    fallback = result["company_profiles"][0]
    assert fallback.name == "Failing Corp"
    assert "https://failing.com" in fallback.raw_sources


def test_profiler_groups_signals_by_company_name():
    """Signals for the same company (case-insensitive) are grouped together."""
    from backend.nodes.profiler import _group_signals_by_company

    signals = [
        _make_signal("Acme Corp", "https://a.com"),
        _make_signal("acme corp", "https://b.com"),
        _make_signal("ACME CORP", "https://c.com"),
        _make_signal("Beta Inc", "https://d.com"),
    ]

    groups = _group_signals_by_company(signals)
    assert len(groups) == 2
    assert len(groups["acme corp"]) == 3
    assert len(groups["beta inc"]) == 1


def test_profiler_deep_dive_limits_urls_to_five():
    """In deep_dive mode, at most 5 URLs are crawled per company."""
    from backend.nodes.profiler import profile

    signals = [
        _make_signal("Acme Corp", f"https://acme.com/{i}", f"snippet {i}")
        for i in range(8)
    ]

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = _make_profile("Acme Corp")
    mock_llm.with_structured_output.return_value = mock_structured

    with (
        patch("backend.nodes.profiler.get_llm", return_value=mock_llm),
        patch("backend.nodes.profiler.crawl_page", return_value="page content") as mock_crawl,
    ):
        result = profile({"mode": "deep_dive", "raw_signals": signals})

    # Should crawl at most 5 URLs even though 8 signals exist
    assert mock_crawl.call_count <= 5


class TestProfilerErrorHandling:
    def test_logs_warning_on_llm_failure(self):
        """Profiler should log a warning (not crash silently) when LLM extraction fails."""
        from backend.nodes.profiler import profile

        signals = [_make_signal("Acme Corp", "https://acme.com", "Acme builds widgets")]

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.side_effect = Exception("Parse error")
        mock_llm.with_structured_output.return_value = mock_structured

        with (
            patch("backend.nodes.profiler.get_llm", return_value=mock_llm),
            patch("backend.nodes.profiler.logger") as mock_logger,
        ):
            result = profile({"mode": "explore", "raw_signals": signals})

        # Should still return a stub profile (existing behavior)
        assert len(result["company_profiles"]) == 1
        assert result["company_profiles"][0].name == "Acme Corp"
        # But NOW it should also log a warning
        mock_logger.warning.assert_called_once()
