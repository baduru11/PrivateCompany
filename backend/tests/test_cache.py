# backend/tests/test_cache.py
import json
import pytest
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
