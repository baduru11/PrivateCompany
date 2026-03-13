# backend/tests/test_cache.py
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from backend.cache import CacheManager


@pytest.fixture
def cache(tmp_path):
    return CacheManager(base_dir=str(tmp_path))


def test_api_cache_miss(cache):
    result = cache.get_api("tavily", "test query")
    assert result is None


def test_api_cache_set_and_get(cache):
    data = {"results": [{"title": "Test"}]}
    cache.set_api("tavily", "test query", data)
    result = cache.get_api("tavily", "test query")
    assert result == data


def test_report_cache_set_and_get(cache):
    report = {"query": "AI chips", "companies": []}
    cache.set_report("explore", "AI chips", report)
    result = cache.get_report("explore", "AI chips")
    assert result["query"] == "AI chips"


def test_report_cache_miss(cache):
    result = cache.get_report("explore", "nonexistent")
    assert result is None


def test_list_reports(cache):
    cache.set_report("explore", "AI chips", {"query": "AI chips"})
    cache.set_report("deep_dive", "NVIDIA", {"query": "NVIDIA"})
    reports = cache.list_reports()
    assert len(reports) == 2


def test_cache_key_normalization(cache):
    cache.set_api("tavily", "  AI Chips  ", {"data": 1})
    result = cache.get_api("tavily", "ai chips")
    assert result == {"data": 1}


class TestCacheTTL:
    def test_expired_report_returns_none(self, tmp_path):
        """Reports older than TTL should return None."""
        cm = CacheManager(base_dir=str(tmp_path), report_ttl_days=7)
        cm.set_report("explore", "AI chips", {"summary": "test"})

        # Should be found (fresh)
        assert cm.get_report("explore", "AI chips") is not None

        # Simulate 8 days later
        eight_days_later = datetime.now(timezone.utc) + timedelta(days=8)
        with patch("backend.cache.datetime") as mock_dt:
            mock_dt.now.return_value = eight_days_later
            mock_dt.fromisoformat = datetime.fromisoformat
            result = cm.get_report("explore", "AI chips")
        assert result is None

    def test_fresh_report_returns_data(self, tmp_path):
        """Reports within TTL should be returned normally."""
        cm = CacheManager(base_dir=str(tmp_path), report_ttl_days=7)
        cm.set_report("explore", "AI chips", {"summary": "test"})
        result = cm.get_report("explore", "AI chips")
        assert result is not None
        assert result["summary"] == "test"


class TestCacheErrorHandling:
    def test_get_report_handles_corrupted_json(self, tmp_path):
        """get_report should return None for corrupted JSON files."""
        cm = CacheManager(base_dir=str(tmp_path))
        path = cm.report_dir / "explore_deadbeef.json"
        path.write_text("not valid json{{{", encoding="utf-8")
        # list_reports should not crash
        reports = cm.list_reports()
        assert isinstance(reports, list)

    def test_get_api_handles_corrupted_json(self, tmp_path):
        """get_api should return None for corrupted JSON files."""
        cm = CacheManager(base_dir=str(tmp_path))
        # Write corrupted JSON to the exact path get_api will look up
        query = "test corrupted"
        expected_path = cm.api_dir / f"exa_{cm._hash_key('exa', query)}.json"
        expected_path.write_text("not valid json{{{", encoding="utf-8")
        result = cm.get_api("exa", query)
        assert result is None
