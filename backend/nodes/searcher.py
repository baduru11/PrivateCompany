# backend/nodes/searcher.py
from __future__ import annotations
from backend.models import RawCompanySignal, SearchPlan
from backend.config import get_settings
from backend.cache import CacheManager

_cache: CacheManager | None = None


def get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager(get_settings().cache_dir)
    return _cache


def get_exa_client():
    from exa_py import Exa
    return Exa(api_key=get_settings().exa_api_key)


def get_tavily_client():
    from tavily import TavilyClient
    return TavilyClient(api_key=get_settings().tavily_api_key)


def _search_exa(client, query: str, num_results: int, cache: CacheManager) -> list[RawCompanySignal]:
    cached = cache.get_api("exa", query)
    if cached:
        return [RawCompanySignal(**s) for s in cached]

    results = client.search(query, num_results=num_results, type="company")
    signals = [
        RawCompanySignal(
            company_name=r.title or "Unknown",
            url=r.url,
            snippet=r.text or "",
            source="exa",
        )
        for r in results.results
    ]
    cache.set_api("exa", query, [s.model_dump() for s in signals])
    return signals


def _search_tavily(client, query: str, cache: CacheManager) -> list[RawCompanySignal]:
    cached = cache.get_api("tavily", query)
    if cached:
        return [RawCompanySignal(**s) for s in cached]

    response = client.search(query, max_results=10)
    signals = [
        RawCompanySignal(
            company_name=r.get("title", "Unknown"),
            url=r.get("url", ""),
            snippet=r.get("content", ""),
            source="tavily",
        )
        for r in response.get("results", [])
    ]
    cache.set_api("tavily", query, [s.model_dump() for s in signals])
    return signals


def search(state: dict) -> dict:
    plan: SearchPlan = state["search_plan"]
    mode = state["mode"]
    cache = get_cache()
    signals: list[RawCompanySignal] = []

    if mode == "explore":
        exa = get_exa_client()
        tavily = get_tavily_client()
        for term in plan.search_terms:
            signals.extend(_search_exa(exa, term, plan.target_company_count, cache))

        if len(signals) < 5:
            for term in plan.search_terms:
                signals.extend(_search_tavily(tavily, term, cache))
    else:
        tavily = get_tavily_client()
        for term in plan.search_terms:
            signals.extend(_search_tavily(tavily, term, cache))

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique: list[RawCompanySignal] = []
    for s in signals:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            unique.append(s)

    return {"raw_signals": unique}
