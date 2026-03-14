# backend/nodes/searcher.py
from __future__ import annotations
import logging
from backend.models import RawCompanySignal, SearchPlan
from backend.rag import store_research, make_report_id
from backend.config import get_settings
from backend.cache import CacheManager

logger = logging.getLogger(__name__)

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


def _search_serper(query: str, num_results: int, cache: CacheManager) -> list[RawCompanySignal]:
    cached = cache.get_api("serper", query)
    if cached:
        return [RawCompanySignal(**s) for s in cached]

    import httpx

    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().serper_api_key},
            json={"q": query, "num": num_results},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("organic", [])[:num_results]
        signals = [
            RawCompanySignal(
                company_name=r.get("title", "Unknown"),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                source="serper",
            )
            for r in results
        ]
        cache.set_api("serper", query, [s.model_dump() for s in signals])
        return signals
    except Exception as exc:
        logger.warning("Serper search failed for query=%s: %s", query, exc)
        return []


def _search_exa(client, query: str, num_results: int, cache: CacheManager) -> list[RawCompanySignal]:
    cached = cache.get_api("exa", query)
    if cached:
        return [RawCompanySignal(**s) for s in cached]

    try:
        results = client.search(query, num_results=num_results, type="auto")
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
    except Exception as exc:
        logger.warning("Exa search failed for query=%s: %s", query, exc)
        return []


def _search_tavily(client, query: str, num_results: int, cache: CacheManager) -> list[RawCompanySignal]:
    cached = cache.get_api("tavily", query)
    if cached:
        return [RawCompanySignal(**s) for s in cached]

    try:
        response = client.search(query, max_results=num_results)
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
    except Exception as exc:
        logger.warning("Tavily search failed for query=%s: %s", query, exc)
        return []


def _search_patents(company_name: str, cache: CacheManager) -> list[RawCompanySignal]:
    """Search Google Patents via Serper for patents assigned to a company."""
    settings = get_settings()
    if not settings.serper_api_key:
        return []

    query = f'site:patents.google.com "{company_name}" patent'
    cached = cache.get_api("serper_patents", query)
    if cached:
        return [RawCompanySignal(**s) for s in cached]

    import httpx

    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.serper_api_key},
            json={"q": query, "num": 10},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("organic", [])[:10]
        signals = [
            RawCompanySignal(
                company_name=company_name,
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                source="google_patents",
            )
            for r in results
        ]
        cache.set_api("serper_patents", query, [s.model_dump() for s in signals])
        logger.info("Google Patents search found %d results for %s", len(signals), company_name)
        return signals
    except Exception as exc:
        logger.warning("Google Patents search failed for %s: %s", company_name, exc)
        return []


def search(state: dict) -> dict:
    plan: SearchPlan = state["search_plan"]
    mode = state["mode"]
    cache = get_cache()
    signals: list[RawCompanySignal] = []

    # Initialize all available clients
    exa = None
    try:
        exa = get_exa_client()
    except Exception as exc:
        logger.warning("Failed to create Exa client: %s", exc)

    tavily = None
    try:
        tavily = get_tavily_client()
    except Exception as exc:
        logger.warning("Failed to create Tavily client: %s", exc)

    has_serper = bool(get_settings().serper_api_key)
    num_results = plan.target_company_count if mode == "explore" else 10

    # Run all providers concurrently (+ patent search for deep_dive)
    from concurrent.futures import ThreadPoolExecutor

    def _run_exa():
        results = []
        if exa is not None:
            for term in plan.search_terms:
                results.extend(_search_exa(exa, term, num_results, cache))
        return results

    def _run_tavily():
        results = []
        if tavily is not None:
            for term in plan.search_terms:
                results.extend(_search_tavily(tavily, term, num_results, cache))
        return results

    def _run_serper():
        results = []
        if has_serper:
            for term in plan.search_terms:
                results.extend(_search_serper(term, num_results, cache))
        return results

    def _run_patents():
        if mode == "deep_dive":
            return _search_patents(state["query"].strip(), cache)
        return []

    with ThreadPoolExecutor(max_workers=4) as pool:
        exa_future = pool.submit(_run_exa)
        tavily_future = pool.submit(_run_tavily)
        serper_future = pool.submit(_run_serper)
        patent_future = pool.submit(_run_patents)

        exa_results = exa_future.result()
        tavily_results = tavily_future.result()
        serper_results = serper_future.result()
        patent_results = patent_future.result()

    # Interleave results from all providers (round-robin) so the signal
    # list has provider diversity instead of being dominated by whichever
    # provider's results are concatenated first.
    all_results = [exa_results, tavily_results, serper_results]
    max_len = max((len(r) for r in all_results), default=0)
    for i in range(max_len):
        for results in all_results:
            if i < len(results):
                signals.append(results[i])

    # Append patent results (supplementary, after main interleaved results)
    if patent_results:
        signals.extend(patent_results)

    if not signals:
        raise RuntimeError("Search failed: no results found from any provider")

    # In deep-dive mode, all signals belong to the target company — normalize
    # company_name so the profiler groups them into a single profile instead of
    # fragmenting by page title.
    if mode == "deep_dive":
        target_name = state["query"].strip()
        for s in signals:
            s.company_name = target_name

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique: list[RawCompanySignal] = []
    for s in signals:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            unique.append(s)

    # Cap results — deep-dive needs more signals (50) to cover all
    # sections (governance, patents, partnerships, etc.) since the planner
    # generates 14-16 diverse search terms plus dedicated patent search.
    max_signals = plan.target_company_count * 2 if mode == "explore" else 50
    signals = unique[:max_signals]

    # RAG ingestion — synchronous so chat is available immediately after report
    report_id = make_report_id(state["query"])
    company_name = state["query"].strip()

    try:
        store_research(report_id, company_name, signals)
    except Exception as e:
        logger.warning("RAG ingestion failed for report_id=%s: %s", report_id, e)

    return {"raw_signals": signals, "report_id": report_id}
