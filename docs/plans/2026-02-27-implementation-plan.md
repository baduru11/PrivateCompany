# Private Company Intelligence Agent — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-stack competitive intelligence web app with LangGraph agent orchestration, anti-hallucination safeguards, and professional Bloomberg-style UI.

**Architecture:** FastAPI backend with two LangGraph subgraphs (Explore + Deep Dive), each flowing through Planner → Searcher → Profiler → Synthesis → Critic nodes. React frontend with shadcn/ui, react-force-graph-2d for landscape visualization, Recharts for data charts. SSE streaming for real-time agent status.

**Tech Stack:** Python, FastAPI, LangGraph, Gemini 2.5 Flash, Tavily, Exa, Crawl4AI, Jina Reader, React, Tailwind CSS, shadcn/ui, react-force-graph-2d, Recharts

**Design Doc:** `docs/plans/2026-02-27-private-company-intel-design.md`

---

## Phase 1: Backend Foundation

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/__init__.py`
- Create: `backend/nodes/__init__.py`
- Create: `backend/fixtures/.gitkeep`

**Step 1: Create backend directory structure**

```bash
mkdir -p backend/nodes backend/fixtures backend/cache/api backend/cache/reports
touch backend/__init__.py backend/nodes/__init__.py backend/fixtures/.gitkeep
```

**Step 2: Write requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sse-starlette==2.1.0
langgraph==0.4.0
langchain-google-genai==2.1.0
langchain-openai==0.3.0
langchain-anthropic==0.3.0
langchain-core==0.3.0
tavily-python==0.5.0
exa-py==1.5.0
crawl4ai==0.8.0
httpx==0.27.0
pydantic==2.10.0
pydantic-settings==2.7.0
python-dotenv==1.0.0
```

**Step 3: Write .env.example**

```
GEMINI_API_KEY=your-key-here
TAVILY_API_KEY=your-key-here
EXA_API_KEY=your-key-here
OPENAI_API_KEY=optional
ANTHROPIC_API_KEY=optional
LLM_PROVIDER=gemini
```

**Step 4: Create virtual environment and install**

```bash
cd backend && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt
```

**Step 5: Commit**

```bash
git add backend/
git commit -m "feat: scaffold backend project with dependencies"
```

---

### Task 2: Pydantic models (models.py)

**Files:**
- Create: `backend/models.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_models.py
import pytest
from pydantic import ValidationError
from backend.models import (
    SearchPlan, RawCompanySignal, CompanyProfile,
    ExploreReport, DeepDiveReport, CriticVerification,
    CriticReport, StatusEvent, AgentState
)

def test_company_profile_requires_source_for_funding():
    """If funding_total is set, funding_source_url must exist."""
    with pytest.raises(ValidationError):
        CompanyProfile(
            name="TestCo",
            funding_total="$10M",
            funding_source_url=None,
            funding_confidence=0.8
        )

def test_company_profile_allows_missing_funding():
    """If funding_total is None, no source needed."""
    profile = CompanyProfile(name="TestCo")
    assert profile.funding_total is None
    assert profile.funding_confidence == 0.0

def test_company_profile_valid_with_source():
    profile = CompanyProfile(
        name="TestCo",
        funding_total="$10M",
        funding_source_url="https://example.com",
        funding_confidence=0.9
    )
    assert profile.name == "TestCo"

def test_confidence_score_bounded():
    with pytest.raises(ValidationError):
        CompanyProfile(name="TestCo", funding_confidence=1.5)

def test_search_plan_structure():
    plan = SearchPlan(
        search_terms=["AI chips", "inference hardware"],
        target_company_count=15,
        sub_sectors=["GPU", "ASIC", "FPGA"]
    )
    assert len(plan.search_terms) == 2

def test_status_event_structure():
    event = StatusEvent(node="searcher", status="running", detail="Searching...")
    assert event.node == "searcher"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL — ImportError

**Step 3: Write models.py**

```python
# backend/models.py
from __future__ import annotations
from typing import Optional, Literal, Union
from pydantic import BaseModel, Field, model_validator


class SearchPlan(BaseModel):
    search_terms: list[str]
    target_company_count: int = 15
    sub_sectors: list[str] = []


class RawCompanySignal(BaseModel):
    company_name: str
    url: str
    snippet: str
    source: Literal["tavily", "exa"]
    metadata: dict = {}


class CompanyProfile(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    funding_total: Optional[str] = None
    funding_source_url: Optional[str] = None
    funding_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    funding_stage: Optional[str] = None
    funding_stage_source_url: Optional[str] = None
    key_investors: list[str] = []
    founding_year: Optional[int] = None
    founding_year_source_url: Optional[str] = None
    headcount_estimate: Optional[str] = None
    headquarters: Optional[str] = None
    core_product: Optional[str] = None
    core_technology: Optional[str] = None
    key_people: list[dict] = []
    recent_news: list[dict] = []
    sub_sector: Optional[str] = None
    raw_sources: list[str] = []

    @model_validator(mode="after")
    def funding_must_have_source(self):
        if self.funding_total and not self.funding_source_url:
            raise ValueError("funding_total set without funding_source_url")
        return self


class ExploreCompany(BaseModel):
    name: str
    sub_sector: str = "Unknown"
    funding_total: Optional[str] = None
    funding_numeric: float = 0.0
    founding_year: Optional[int] = None
    description: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_count: int = 0


class ExploreReport(BaseModel):
    query: str
    sector: str
    companies: list[ExploreCompany]
    sub_sectors: list[str]
    summary: str


class DeepDiveSection(BaseModel):
    title: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_urls: list[str] = []
    source_count: int = 0


class FundingRound(BaseModel):
    date: Optional[str] = None
    stage: Optional[str] = None
    amount: Optional[str] = None
    investors: list[str] = []
    source_url: Optional[str] = None


class NewsItem(BaseModel):
    title: str
    date: Optional[str] = None
    source_url: Optional[str] = None
    snippet: str
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"


class CompetitorEntry(BaseModel):
    name: str
    description: Optional[str] = None
    funding: Optional[str] = None
    differentiator: Optional[str] = None


class DeepDiveReport(BaseModel):
    query: str
    company_name: str
    overview: DeepDiveSection
    funding: DeepDiveSection
    funding_rounds: list[FundingRound] = []
    key_people: DeepDiveSection
    product_technology: DeepDiveSection
    recent_news: DeepDiveSection
    news_items: list[NewsItem] = []
    competitors: DeepDiveSection
    competitor_entries: list[CompetitorEntry] = []
    red_flags: DeepDiveSection


class CriticVerification(BaseModel):
    field: str
    status: Literal["verified", "unverified", "conflicting", "missing"]
    source_url: Optional[str] = None
    note: Optional[str] = None


class CriticReport(BaseModel):
    overall_confidence: float = Field(ge=0.0, le=1.0)
    section_scores: dict[str, float] = {}
    verifications: list[CriticVerification] = []
    gaps: list[str] = []
    should_retry: bool = False
    retry_queries: list[str] = []


class StatusEvent(BaseModel):
    node: str
    status: Literal["running", "complete", "error", "retrying"]
    detail: str
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add backend/models.py backend/tests/
git commit -m "feat: add Pydantic models with source-grounding validators"
```

---

### Task 3: Config and LLM factory (config.py)

**Files:**
- Create: `backend/config.py`
- Create: `backend/tests/test_config.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_config.py
import os
import pytest
from unittest.mock import patch

def test_get_llm_returns_gemini_by_default():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "LLM_PROVIDER": "gemini"}):
        from backend.config import get_llm
        llm = get_llm()
        assert llm is not None

def test_get_llm_raises_without_key():
    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}, clear=True):
        from backend.config import get_llm
        with pytest.raises(ValueError):
            get_llm()

def test_settings_loads_env():
    with patch.dict(os.environ, {
        "GEMINI_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
    }):
        from backend.config import Settings
        s = Settings()
        assert s.gemini_api_key == "test"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL — ImportError

**Step 3: Write config.py**

```python
# backend/config.py
from __future__ import annotations
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    tavily_api_key: str = ""
    exa_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "gemini"
    cache_dir: str = "cache"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm(provider: str | None = None):
    settings = get_settings()
    provider = provider or settings.llm_provider

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
        )
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=0,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/config.py backend/tests/test_config.py
git commit -m "feat: add LLM factory config with provider switching"
```

---

### Task 4: Two-level cache system (cache.py)

**Files:**
- Create: `backend/cache.py`
- Create: `backend/tests/test_cache.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_cache.py
import json
import tempfile
import os
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
    assert result == report

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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cache.py -v`
Expected: FAIL — ImportError

**Step 3: Write cache.py**

```python
# backend/cache.py
from __future__ import annotations
import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


class CacheManager:
    def __init__(self, base_dir: str = "cache"):
        self.base_dir = Path(base_dir)
        self.api_dir = self.base_dir / "api"
        self.report_dir = self.base_dir / "reports"
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_key(self, key: str) -> str:
        return key.strip().lower()

    def _hash_key(self, *parts: str) -> str:
        combined = "|".join(self._normalize_key(p) for p in parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def get_api(self, provider: str, query: str) -> dict | None:
        path = self.api_dir / f"{provider}_{self._hash_key(provider, query)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def set_api(self, provider: str, query: str, data: dict) -> None:
        path = self.api_dir / f"{provider}_{self._hash_key(provider, query)}.json"
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def get_report(self, mode: str, query: str) -> dict | None:
        path = self.report_dir / f"{mode}_{self._hash_key(mode, query)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def set_report(self, mode: str, query: str, data: dict) -> None:
        meta = {
            **data,
            "_cached_at": datetime.now(timezone.utc).isoformat(),
            "_mode": mode,
            "_query": query,
        }
        path = self.report_dir / f"{mode}_{self._hash_key(mode, query)}.json"
        path.write_text(json.dumps(meta, default=str), encoding="utf-8")

    def list_reports(self) -> list[dict]:
        reports = []
        for path in self.report_dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            reports.append({
                "mode": data.get("_mode", "unknown"),
                "query": data.get("_query", "unknown"),
                "cached_at": data.get("_cached_at", ""),
                "filename": path.name,
            })
        return sorted(reports, key=lambda r: r["cached_at"], reverse=True)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_cache.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add backend/cache.py backend/tests/test_cache.py
git commit -m "feat: add two-level cache system (API + report)"
```

---

## Phase 2: Agent Nodes

### Task 5: Planner node

**Files:**
- Create: `backend/nodes/planner.py`
- Create: `backend/tests/test_planner.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_planner.py
import pytest
from unittest.mock import MagicMock, patch
from backend.models import SearchPlan

def test_planner_explore_returns_search_plan():
    from backend.nodes.planner import plan_search
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=SearchPlan(
            search_terms=["AI inference chips", "custom silicon AI"],
            target_company_count=15,
            sub_sectors=["GPU", "ASIC", "FPGA"]
        ))
    )
    state = {"query": "AI inference chips", "mode": "explore", "retry_count": 0}
    with patch("backend.nodes.planner.get_llm", return_value=mock_llm):
        result = plan_search(state)
    assert "search_plan" in result
    assert len(result["search_plan"].search_terms) > 0

def test_planner_deep_dive_returns_search_plan():
    from backend.nodes.planner import plan_search
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=SearchPlan(
            search_terms=["NVIDIA funding", "NVIDIA investors", "NVIDIA news 2024"],
            target_company_count=1,
            sub_sectors=[]
        ))
    )
    state = {"query": "NVIDIA", "mode": "deep_dive", "retry_count": 0}
    with patch("backend.nodes.planner.get_llm", return_value=mock_llm):
        result = plan_search(state)
    assert result["search_plan"].target_company_count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_planner.py -v`
Expected: FAIL — ImportError

**Step 3: Write planner.py**

```python
# backend/nodes/planner.py
from __future__ import annotations
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import get_llm
from backend.models import SearchPlan

EXPLORE_PROMPT = """You are a competitive intelligence research planner.
Given a sector query, generate a search plan to discover 10-20 companies in this space.
Output search terms that will find companies, their funding, and key details.
Include sub-sector categories to organize the landscape."""

DEEP_DIVE_PROMPT = """You are a competitive intelligence research planner.
Given a company name, generate a search plan to find detailed intelligence:
funding history, key investors, leadership team, product details, recent news, competitors, and red flags.
Output specific search terms for each information category."""


def plan_search(state: dict) -> dict:
    llm = get_llm()
    structured_llm = llm.with_structured_output(SearchPlan)

    query = state["query"]
    mode = state["mode"]
    prompt = EXPLORE_PROMPT if mode == "explore" else DEEP_DIVE_PROMPT

    retry_context = ""
    if state.get("retry_count", 0) > 0 and state.get("critic_report"):
        gaps = state["critic_report"].gaps
        retry_context = f"\n\nPrevious search had gaps: {', '.join(gaps)}. Focus on filling these."

    plan = structured_llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"Query: {query}{retry_context}")
    ])

    return {"search_plan": plan}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_planner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/nodes/planner.py backend/tests/test_planner.py
git commit -m "feat: add Planner node with explore/deep-dive prompts"
```

---

### Task 6: Searcher node

**Files:**
- Create: `backend/nodes/searcher.py`
- Create: `backend/tests/test_searcher.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_searcher.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.models import SearchPlan, RawCompanySignal

def test_searcher_explore_uses_exa_and_tavily():
    from backend.nodes.searcher import search
    mock_exa = MagicMock()
    mock_exa.search.return_value = MagicMock(results=[
        MagicMock(title="Cerebras Systems", url="https://cerebras.net", text="AI chip company"),
        MagicMock(title="Groq Inc", url="https://groq.com", text="LPU inference"),
    ])
    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {"results": [
        {"title": "Groq raises $640M", "url": "https://news.com/groq", "content": "Groq funding news"}
    ]}
    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    state = {
        "query": "AI inference chips",
        "mode": "explore",
        "search_plan": SearchPlan(
            search_terms=["AI inference chips"],
            target_company_count=15,
            sub_sectors=["GPU", "ASIC"]
        ),
        "retry_count": 0,
    }

    with patch("backend.nodes.searcher.get_exa_client", return_value=mock_exa), \
         patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily), \
         patch("backend.nodes.searcher.get_cache", return_value=mock_cache):
        result = search(state)

    assert "raw_signals" in result
    assert len(result["raw_signals"]) > 0

def test_searcher_deep_dive_uses_tavily():
    from backend.nodes.searcher import search
    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {"results": [
        {"title": "NVIDIA Q4 earnings", "url": "https://news.com/nvidia", "content": "NVIDIA posted..."}
    ]}
    mock_cache = MagicMock()
    mock_cache.get_api.return_value = None

    state = {
        "query": "NVIDIA",
        "mode": "deep_dive",
        "search_plan": SearchPlan(
            search_terms=["NVIDIA funding", "NVIDIA leadership"],
            target_company_count=1,
            sub_sectors=[]
        ),
        "retry_count": 0,
    }

    with patch("backend.nodes.searcher.get_tavily_client", return_value=mock_tavily), \
         patch("backend.nodes.searcher.get_cache", return_value=mock_cache):
        result = search(state)

    assert "raw_signals" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_searcher.py -v`
Expected: FAIL — ImportError

**Step 3: Write searcher.py**

```python
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
    seen_urls = set()
    unique = []
    for s in signals:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            unique.append(s)

    return {"raw_signals": unique}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_searcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/nodes/searcher.py backend/tests/test_searcher.py
git commit -m "feat: add Searcher node with Exa + Tavily + caching"
```

---

### Task 7: Profiler node

**Files:**
- Create: `backend/nodes/profiler.py`
- Create: `backend/tests/test_profiler.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_profiler.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.models import RawCompanySignal, SearchPlan

def test_profiler_explore_uses_snippets_only():
    """Explore mode should NOT call Crawl4AI — lightweight profiling."""
    from backend.nodes.profiler import profile

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=MagicMock(
            model_dump=MagicMock(return_value={
                "name": "Cerebras",
                "funding_total": "$720M",
                "funding_source_url": "https://news.com/cerebras",
                "funding_confidence": 0.8,
            })
        ))
    )

    state = {
        "query": "AI inference chips",
        "mode": "explore",
        "search_plan": SearchPlan(search_terms=["AI chips"], target_company_count=15, sub_sectors=[]),
        "raw_signals": [
            RawCompanySignal(company_name="Cerebras", url="https://cerebras.net", snippet="AI chip company raised $720M", source="exa"),
        ],
        "retry_count": 0,
    }

    with patch("backend.nodes.profiler.get_llm", return_value=mock_llm), \
         patch("backend.nodes.profiler.crawl_page") as mock_crawl:
        result = profile(state)

    mock_crawl.assert_not_called()
    assert "company_profiles" in result
    assert len(result["company_profiles"]) > 0

def test_profiler_deep_dive_uses_crawl4ai():
    """Deep Dive mode should call Crawl4AI for full extraction."""
    from backend.nodes.profiler import profile

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=MagicMock(
            model_dump=MagicMock(return_value={
                "name": "NVIDIA",
                "funding_total": None,
                "funding_confidence": 0.0,
            })
        ))
    )

    state = {
        "query": "NVIDIA",
        "mode": "deep_dive",
        "search_plan": SearchPlan(search_terms=["NVIDIA"], target_company_count=1, sub_sectors=[]),
        "raw_signals": [
            RawCompanySignal(company_name="NVIDIA", url="https://nvidia.com", snippet="GPU company", source="tavily"),
        ],
        "retry_count": 0,
    }

    with patch("backend.nodes.profiler.get_llm", return_value=mock_llm), \
         patch("backend.nodes.profiler.crawl_page", return_value="NVIDIA is a leading GPU manufacturer..."):
        result = profile(state)

    assert "company_profiles" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_profiler.py -v`
Expected: FAIL — ImportError

**Step 3: Write profiler.py**

```python
# backend/nodes/profiler.py
from __future__ import annotations
import httpx
from backend.models import RawCompanySignal, CompanyProfile
from backend.config import get_llm

EXTRACTION_PROMPT = """Extract structured company data from these sources.
Only include information explicitly present in the source text.
If data is missing, leave the field as null. Never guess or infer.
For each field you populate, set the corresponding source_url to where you found it."""


def crawl_page(url: str, timeout: float = 30.0) -> str | None:
    """Extract page content using Crawl4AI, fallback to Jina Reader."""
    try:
        from crawl4ai import WebCrawler
        crawler = WebCrawler()
        result = crawler.run(url=url)
        if result and result.markdown:
            return result.markdown
    except Exception:
        pass

    # Fallback: Jina Reader
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp = httpx.get(jina_url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 100:
            return resp.text
    except Exception:
        pass

    return None


def _group_signals_by_company(signals: list[RawCompanySignal]) -> dict[str, list[RawCompanySignal]]:
    groups: dict[str, list[RawCompanySignal]] = {}
    for s in signals:
        key = s.company_name.strip().lower()
        groups.setdefault(key, []).append(s)
    return groups


def profile(state: dict) -> dict:
    mode = state["mode"]
    signals = state["raw_signals"]
    llm = get_llm()
    structured_llm = llm.with_structured_output(CompanyProfile)

    grouped = _group_signals_by_company(signals)
    profiles: list[CompanyProfile] = []

    for company_key, company_signals in grouped.items():
        snippets = "\n\n".join(
            f"Source: {s.url}\n{s.snippet}" for s in company_signals
        )

        extra_content = ""
        if mode == "deep_dive":
            urls = list({s.url for s in company_signals})[:3]
            for url in urls:
                page = crawl_page(url)
                if page:
                    extra_content += f"\n\n--- Full page: {url} ---\n{page[:3000]}"

        combined = f"{snippets}{extra_content}"

        try:
            result = structured_llm.invoke([
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"Extract company profile from:\n\n{combined}"}
            ])
            profiles.append(result)
        except Exception:
            profiles.append(CompanyProfile(
                name=company_signals[0].company_name,
                raw_sources=[s.url for s in company_signals],
            ))

    return {"company_profiles": profiles}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_profiler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/nodes/profiler.py backend/tests/test_profiler.py
git commit -m "feat: add Profiler node with Crawl4AI + Jina fallback"
```

---

### Task 8: Synthesis node

**Files:**
- Create: `backend/nodes/synthesis.py`
- Create: `backend/tests/test_synthesis.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_synthesis.py
import pytest
from unittest.mock import MagicMock, patch
from backend.models import CompanyProfile, ExploreReport, DeepDiveReport

def test_synthesis_explore_returns_explore_report():
    from backend.nodes.synthesis import synthesize
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=ExploreReport(
            query="AI chips",
            sector="AI Inference Hardware",
            companies=[],
            sub_sectors=["GPU", "ASIC"],
            summary="The AI chip landscape..."
        ))
    )
    state = {
        "query": "AI chips",
        "mode": "explore",
        "company_profiles": [
            CompanyProfile(name="Cerebras"),
            CompanyProfile(name="Groq"),
        ],
        "retry_count": 0,
    }
    with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
        result = synthesize(state)
    assert "report" in result
    assert isinstance(result["report"], ExploreReport)

def test_synthesis_deep_dive_returns_deep_dive_report():
    from backend.nodes.synthesis import synthesize
    mock_report = DeepDiveReport(
        query="NVIDIA",
        company_name="NVIDIA",
        overview=MagicMock(title="Overview", content="...", confidence=0.9, source_urls=[], source_count=0),
        funding=MagicMock(title="Funding", content="...", confidence=0.5, source_urls=[], source_count=0),
        key_people=MagicMock(title="Key People", content="...", confidence=0.7, source_urls=[], source_count=0),
        product_technology=MagicMock(title="Product", content="...", confidence=0.8, source_urls=[], source_count=0),
        recent_news=MagicMock(title="News", content="...", confidence=0.6, source_urls=[], source_count=0),
        competitors=MagicMock(title="Competitors", content="...", confidence=0.7, source_urls=[], source_count=0),
        red_flags=MagicMock(title="Red Flags", content="...", confidence=0.4, source_urls=[], source_count=0),
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=mock_report)
    )
    state = {
        "query": "NVIDIA",
        "mode": "deep_dive",
        "company_profiles": [CompanyProfile(name="NVIDIA")],
        "retry_count": 0,
    }
    with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
        result = synthesize(state)
    assert "report" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_synthesis.py -v`
Expected: FAIL — ImportError

**Step 3: Write synthesis.py**

```python
# backend/nodes/synthesis.py
from __future__ import annotations
from backend.config import get_llm
from backend.models import CompanyProfile, ExploreReport, DeepDiveReport

EXPLORE_SYSTEM = """You are a competitive intelligence analyst. Given company profiles,
create a structured competitive landscape report.
CRITICAL: Only include information from the provided data. Write 'Data not available' for missing fields. Never guess."""

DEEP_DIVE_SYSTEM = """You are a competitive intelligence analyst. Given company data,
create a detailed intelligence report with these sections: Overview, Funding History,
Key People, Product/Technology, Recent News, Competitors, Red Flags.
CRITICAL: Only include information from the provided data. If data is missing, explicitly
state 'Data not available' in that section. Never infer, guess, or use your own knowledge.
For each section, set confidence based on how much source data supports it."""


def synthesize(state: dict) -> dict:
    llm = get_llm()
    mode = state["mode"]
    profiles = state["company_profiles"]

    profiles_text = "\n\n".join(
        p.model_dump_json(indent=2) if hasattr(p, "model_dump_json")
        else str(p)
        for p in profiles
    )

    if mode == "explore":
        structured_llm = llm.with_structured_output(ExploreReport)
        report = structured_llm.invoke([
            {"role": "system", "content": EXPLORE_SYSTEM},
            {"role": "user", "content": f"Query: {state['query']}\n\nCompany profiles:\n{profiles_text}"}
        ])
    else:
        structured_llm = llm.with_structured_output(DeepDiveReport)
        report = structured_llm.invoke([
            {"role": "system", "content": DEEP_DIVE_SYSTEM},
            {"role": "user", "content": f"Company: {state['query']}\n\nCollected data:\n{profiles_text}"}
        ])

    return {"report": report}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_synthesis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/nodes/synthesis.py backend/tests/test_synthesis.py
git commit -m "feat: add Synthesis node with source-grounded prompts"
```

---

### Task 9: Critic node

**Files:**
- Create: `backend/nodes/critic.py`
- Create: `backend/tests/test_critic.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_critic.py
import pytest
from unittest.mock import MagicMock, patch
from backend.models import CriticReport

def test_critic_returns_report_with_confidence():
    from backend.nodes.critic import critique
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=CriticReport(
            overall_confidence=0.75,
            section_scores={"overview": 0.9, "funding": 0.6},
            verifications=[],
            gaps=["headcount data missing"],
            should_retry=False,
            retry_queries=[]
        ))
    )

    state = {
        "query": "NVIDIA",
        "mode": "deep_dive",
        "raw_signals": [],
        "company_profiles": [],
        "report": MagicMock(),
        "retry_count": 0,
    }

    with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
        result = critique(state)

    assert "critic_report" in result
    assert result["critic_report"].overall_confidence == 0.75

def test_critic_requests_retry_on_major_gaps():
    from backend.nodes.critic import critique
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=CriticReport(
            overall_confidence=0.3,
            section_scores={},
            verifications=[],
            gaps=["no funding data", "no product info", "no news found"],
            should_retry=True,
            retry_queries=["NVIDIA funding history", "NVIDIA product lineup"]
        ))
    )

    state = {
        "query": "NVIDIA",
        "mode": "deep_dive",
        "raw_signals": [],
        "company_profiles": [],
        "report": MagicMock(),
        "retry_count": 0,
    }

    with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
        result = critique(state)

    assert result["critic_report"].should_retry is True

def test_critic_does_not_retry_on_second_pass():
    from backend.nodes.critic import critique
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=CriticReport(
            overall_confidence=0.4,
            section_scores={},
            verifications=[],
            gaps=["still missing data"],
            should_retry=True,
            retry_queries=["more queries"]
        ))
    )

    state = {
        "query": "NVIDIA",
        "mode": "deep_dive",
        "raw_signals": [],
        "company_profiles": [],
        "report": MagicMock(),
        "retry_count": 1,  # Already retried once
    }

    with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
        result = critique(state)

    # should_retry forced to False because retry_count >= 1
    assert result["critic_report"].should_retry is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_critic.py -v`
Expected: FAIL — ImportError

**Step 3: Write critic.py**

```python
# backend/nodes/critic.py
from __future__ import annotations
from backend.config import get_llm
from backend.models import CriticReport

CRITIC_SYSTEM = """You are a rigorous fact-checker for competitive intelligence reports.
You receive a synthesized report AND the raw source data it was built from.

Your job:
1. Cross-check every claim in the report against the raw sources
2. Flag claims that don't appear in any source as 'unverified'
3. Flag contradictory data from different sources as 'conflicting'
4. Score each section's confidence (0.0-1.0) based on source coverage
5. List specific data gaps
6. If more than 3 major sections have confidence < 0.4, recommend a retry with specific search queries

Be strict. An unverified claim is worse than 'Data not available'."""


def critique(state: dict) -> dict:
    llm = get_llm()
    structured_llm = llm.with_structured_output(CriticReport)

    report = state["report"]
    raw_signals = state.get("raw_signals", [])
    profiles = state.get("company_profiles", [])
    retry_count = state.get("retry_count", 0)

    report_text = report.model_dump_json(indent=2) if hasattr(report, "model_dump_json") else str(report)
    raw_text = "\n".join(
        f"[{s.source}] {s.url}: {s.snippet[:500]}"
        for s in raw_signals
    ) if raw_signals else "No raw signals available"

    critic_report = structured_llm.invoke([
        {"role": "system", "content": CRITIC_SYSTEM},
        {"role": "user", "content": f"Report:\n{report_text}\n\nRaw sources:\n{raw_text}"}
    ])

    # Enforce max 1 retry
    if retry_count >= 1:
        critic_report.should_retry = False

    return {
        "critic_report": critic_report,
        "retry_count": retry_count + (1 if critic_report.should_retry else 0),
    }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_critic.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/nodes/critic.py backend/tests/test_critic.py
git commit -m "feat: add Critic node with citation verification + retry cap"
```

---

## Phase 3: LangGraph Graphs

### Task 10: Graph definitions (graph.py)

**Files:**
- Create: `backend/graph.py`
- Create: `backend/tests/test_graph.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_graph.py
import pytest
from backend.graph import build_explore_graph, build_deep_dive_graph

def test_explore_graph_compiles():
    graph = build_explore_graph()
    assert graph is not None

def test_deep_dive_graph_compiles():
    graph = build_deep_dive_graph()
    assert graph is not None

def test_explore_graph_has_correct_nodes():
    graph = build_explore_graph()
    node_names = set(graph.nodes.keys())
    assert "planner" in node_names
    assert "searcher" in node_names
    assert "profiler" in node_names
    assert "synthesis" in node_names
    assert "critic" in node_names

def test_deep_dive_graph_has_correct_nodes():
    graph = build_deep_dive_graph()
    node_names = set(graph.nodes.keys())
    assert "planner" in node_names
    assert "searcher" in node_names
    assert "profiler" in node_names
    assert "synthesis" in node_names
    assert "critic" in node_names
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph.py -v`
Expected: FAIL — ImportError

**Step 3: Write graph.py**

```python
# backend/graph.py
from __future__ import annotations
from typing import Literal, Union, Optional
from langgraph.graph import StateGraph, END
from backend.models import (
    SearchPlan, RawCompanySignal, CompanyProfile,
    ExploreReport, DeepDiveReport, CriticReport, StatusEvent
)
from backend.nodes.planner import plan_search
from backend.nodes.searcher import search
from backend.nodes.profiler import profile
from backend.nodes.synthesis import synthesize
from backend.nodes.critic import critique
from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict, total=False):
    query: str
    mode: str
    search_plan: SearchPlan
    raw_signals: list[RawCompanySignal]
    company_profiles: list[CompanyProfile]
    report: Union[ExploreReport, DeepDiveReport]
    critic_report: CriticReport
    retry_count: int
    status_events: Annotated[list[StatusEvent], operator.add]


def should_retry(state: AgentState) -> Literal["searcher", "end"]:
    critic = state.get("critic_report")
    if critic and critic.should_retry:
        return "searcher"
    return "end"


def _build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("planner", plan_search)
    graph.add_node("searcher", search)
    graph.add_node("profiler", profile)
    graph.add_node("synthesis", synthesize)
    graph.add_node("critic", critique)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "searcher")
    graph.add_edge("searcher", "profiler")
    graph.add_edge("profiler", "synthesis")
    graph.add_edge("synthesis", "critic")
    graph.add_conditional_edges("critic", should_retry, {
        "searcher": "searcher",
        "end": END,
    })

    return graph


def build_explore_graph():
    graph = _build_graph()
    return graph.compile()


def build_deep_dive_graph():
    graph = _build_graph()
    return graph.compile()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/graph.py backend/tests/test_graph.py
git commit -m "feat: add LangGraph explore + deep-dive graphs with retry logic"
```

---

## Phase 4: FastAPI + SSE

### Task 11: FastAPI app with SSE streaming (main.py + streaming.py)

**Files:**
- Create: `backend/streaming.py`
- Create: `backend/main.py`
- Create: `backend/tests/test_main.py`

**Step 1: Write streaming.py**

```python
# backend/streaming.py
from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator
from backend.models import StatusEvent


async def heartbeat_generator(interval: float = 15.0) -> AsyncGenerator[str, None]:
    while True:
        await asyncio.sleep(interval)
        yield f"event: heartbeat\ndata: {{}}\n\n"


def format_sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
```

**Step 2: Write the failing test for main.py**

```python
# backend/tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_history_endpoint_empty():
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_query_endpoint_rejects_empty():
    resp = client.post("/api/query", json={"query": "", "mode": "explore"})
    assert resp.status_code == 422 or resp.status_code == 400
```

**Step 3: Write main.py**

```python
# backend/main.py
from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from backend.cache import CacheManager
from backend.config import get_settings
from backend.graph import build_explore_graph, build_deep_dive_graph
from backend.streaming import format_sse

cache: CacheManager | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache
    cache = CacheManager(get_settings().cache_dir)
    yield

app = FastAPI(title="CompanyIntel API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: str = Field(pattern="^(explore|deep_dive)$")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/history")
def get_history():
    return cache.list_reports() if cache else []


@app.post("/api/query")
async def run_query(req: QueryRequest):
    # Check report cache first
    if cache:
        cached = cache.get_report(req.mode, req.query)
        if cached:
            return {"cached": True, "result": cached}

    async def event_stream():
        try:
            graph = build_explore_graph() if req.mode == "explore" else build_deep_dive_graph()
            initial_state = {
                "query": req.query,
                "mode": req.mode,
                "retry_count": 0,
            }

            yield format_sse("status", {"node": "planner", "status": "running", "detail": f"Planning search for: {req.query}"})

            result = await asyncio.to_thread(graph.invoke, initial_state)

            report = result.get("report")
            critic = result.get("critic_report")

            if report and cache:
                report_data = report.model_dump() if hasattr(report, "model_dump") else report
                if critic:
                    report_data["_critic"] = critic.model_dump() if hasattr(critic, "model_dump") else critic
                cache.set_report(req.mode, req.query, report_data)

            yield format_sse("complete", {
                "report": report.model_dump() if hasattr(report, "model_dump") else {},
                "critic": critic.model_dump() if hasattr(critic, "model_dump") else {},
            })
        except Exception as e:
            yield format_sse("error", {"message": str(e)})

    return EventSourceResponse(event_stream())
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_main.py -v`
Expected: PASS (at least health + history tests)

**Step 5: Commit**

```bash
git add backend/main.py backend/streaming.py backend/tests/test_main.py
git commit -m "feat: add FastAPI app with SSE streaming + history endpoint"
```

---

## Phase 5: Frontend Foundation

### Task 12: React project scaffolding

**Step 1: Create React app with Vite**

```bash
cd /c/Users/badur/baduru/02_Projects/PrivateCompany
npm create vite@latest frontend -- --template react
cd frontend && npm install
```

**Step 2: Install dependencies**

```bash
cd frontend
npm install tailwindcss @tailwindcss/vite
npm install react-force-graph-2d recharts html2pdf.js
npm install lucide-react class-variance-authority clsx tailwind-merge
npm install @radix-ui/react-slot @radix-ui/react-dialog @radix-ui/react-popover @radix-ui/react-tabs @radix-ui/react-toggle @radix-ui/react-toggle-group @radix-ui/react-tooltip @radix-ui/react-scroll-area
```

**Step 3: Configure Tailwind (update `src/index.css`)**

```css
@import "tailwindcss";
```

Update `vite.config.js`:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

**Step 4: Create directory structure**

```bash
mkdir -p src/components/{layout,explore,deep-dive,history,shared}
mkdir -p src/hooks src/lib
```

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with Tailwind + shadcn deps"
```

---

### Task 13: shadcn/ui setup and shared utilities

**Files:**
- Create: `frontend/src/lib/utils.js`
- Create: `frontend/src/lib/api.js`
- Create: `frontend/src/components/ui/card.jsx`
- Create: `frontend/src/components/ui/badge.jsx`
- Create: `frontend/src/components/ui/button.jsx`
- Create: `frontend/src/components/ui/input.jsx`
- Create: `frontend/src/components/ui/tabs.jsx`
- Create: `frontend/src/components/ui/scroll-area.jsx`
- Create: `frontend/src/components/ui/tooltip.jsx`
- Create: `frontend/src/components/ui/popover.jsx`

**Step 1: Write utils.js**

```javascript
// frontend/src/lib/utils.js
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

**Step 2: Write api.js**

```javascript
// frontend/src/lib/api.js
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getApiUrl(path) {
  return `${API_BASE}${path}`;
}

export async function fetchHistory() {
  const resp = await fetch(getApiUrl("/api/history"));
  if (!resp.ok) throw new Error("Failed to fetch history");
  return resp.json();
}
```

**Step 3: Create shadcn/ui components**

Use `npx shadcn@latest init` or manually create the component files following shadcn/ui patterns. The key components needed are: Card, Badge, Button, Input, Tabs, ScrollArea, Tooltip, Popover.

Run: `cd frontend && npx shadcn@latest init -d && npx shadcn@latest add card badge button input tabs scroll-area tooltip popover`

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add shadcn/ui components + API client + utilities"
```

---

### Task 14: SSE hook and query hook

**Files:**
- Create: `frontend/src/hooks/useSSE.js`
- Create: `frontend/src/hooks/useAgentQuery.js`

**Step 1: Write useSSE.js**

```javascript
// frontend/src/hooks/useSSE.js
import { useState, useEffect, useRef, useCallback } from "react";

export function useSSE(url, { enabled = false, onEvent, onComplete, onError } = {}) {
  const [status, setStatus] = useState("idle"); // idle | connecting | connected | error
  const [events, setEvents] = useState([]);
  const sourceRef = useRef(null);
  const timeoutRef = useRef(null);

  const connect = useCallback(() => {
    if (!url || !enabled) return;
    setStatus("connecting");

    const source = new EventSource(url);
    sourceRef.current = source;

    const resetTimeout = () => {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => {
        setStatus("error");
        source.close();
        onError?.("Agent may be stalled — no events for 60 seconds");
      }, 60000);
    };

    source.onopen = () => {
      setStatus("connected");
      resetTimeout();
    };

    source.addEventListener("status", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, data]);
      onEvent?.(data);
      resetTimeout();
    });

    source.addEventListener("complete", (e) => {
      const data = JSON.parse(e.data);
      setStatus("idle");
      clearTimeout(timeoutRef.current);
      source.close();
      onComplete?.(data);
    });

    source.addEventListener("error", (e) => {
      if (e.data) {
        const data = JSON.parse(e.data);
        onError?.(data.message);
      }
      setStatus("error");
      clearTimeout(timeoutRef.current);
      source.close();
    });

    source.addEventListener("heartbeat", () => resetTimeout());

    source.onerror = () => {
      setStatus("error");
      clearTimeout(timeoutRef.current);
      source.close();
    };
  }, [url, enabled]);

  useEffect(() => {
    connect();
    return () => {
      sourceRef.current?.close();
      clearTimeout(timeoutRef.current);
    };
  }, [connect]);

  const reset = useCallback(() => {
    setEvents([]);
    setStatus("idle");
  }, []);

  return { status, events, reset };
}
```

**Step 2: Write useAgentQuery.js**

```javascript
// frontend/src/hooks/useAgentQuery.js
import { useState, useCallback } from "react";
import { getApiUrl } from "../lib/api";
import { useSSE } from "./useSSE";

export function useAgentQuery() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("explore");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [sseUrl, setSseUrl] = useState(null);

  const { status: sseStatus, events, reset: resetSSE } = useSSE(sseUrl, {
    enabled: !!sseUrl,
    onComplete: (data) => {
      setResult(data);
      setIsLoading(false);
      setSseUrl(null);
    },
    onError: (msg) => {
      setError(msg);
      setIsLoading(false);
      setSseUrl(null);
    },
  });

  const submit = useCallback(async (q, m) => {
    setQuery(q);
    setMode(m);
    setResult(null);
    setError(null);
    setIsLoading(true);
    resetSSE();

    const url = getApiUrl(`/api/query?query=${encodeURIComponent(q)}&mode=${m}`);
    setSseUrl(url);
  }, [resetSSE]);

  return {
    query, mode, result, error, isLoading,
    sseStatus, events, submit,
  };
}
```

**Step 3: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat: add useSSE + useAgentQuery hooks with auto-reconnect"
```

---

## Phase 6: Frontend — Layout + Explore Mode

### Task 15: Layout components (TopBar, ProgressBar, StepIndicator, AgentLog)

**Files:**
- Create: `frontend/src/components/layout/TopBar.jsx`
- Create: `frontend/src/components/layout/ProgressBar.jsx`
- Create: `frontend/src/components/layout/StepIndicator.jsx`
- Create: `frontend/src/components/layout/AgentLog.jsx`

Implement per the design doc: compact search bar top-left, thin GitHub-style progress bar, step indicators for Planner → Searcher → Profiler → Synthesis → Critic, collapsible agent log drawer.

**Step 1: Build all four layout components**

Reference design doc Section "UI/UX Design Principles" for layout wireframe. Key details:
- TopBar: logo left, search input center, mode toggle (Explore/Deep Dive) as shadcn Tabs, submit button
- ProgressBar: position fixed top, thin 3px bar, animate width based on current step (5 steps = 20% each)
- StepIndicator: horizontal list of 5 nodes, active one highlighted with accent color, completed ones with check
- AgentLog: fixed bottom, collapsible via click, shows list of SSE events in reverse chronological order

**Step 2: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat: add layout components (TopBar, ProgressBar, StepIndicator, AgentLog)"
```

---

### Task 16: Explore Mode components

**Files:**
- Create: `frontend/src/components/explore/ExploreView.jsx`
- Create: `frontend/src/components/explore/ForceGraph.jsx`
- Create: `frontend/src/components/explore/CompanySidebar.jsx`
- Create: `frontend/src/components/explore/FilterChips.jsx`

**Step 1: Build ForceGraph.jsx**

Key implementation details:
- Import `ForceGraph2D` from `react-force-graph-2d`
- Custom `nodeCanvasObject` renderer: draw circle sized by `funding_numeric`, fill color by `sub_sector`, draw company initial text in center
- `onNodeHover`: show tooltip with name, funding, year
- `onNodeClick`: set selected company, open sidebar
- Node data shape: `{ id, name, sub_sector, funding_numeric, founding_year, val (= funding_numeric for sizing) }`
- Link data: connect companies in same sub_sector with faint lines

**Step 2: Build CompanySidebar.jsx**

- Slide-in panel from right, 30% width
- Shows: company name, description, funding, stage, year, HQ
- "Deep Dive" button at bottom that triggers mode switch + query

**Step 3: Build FilterChips.jsx**

- Row of toggle buttons: funding stages (Seed, Series A, B, C+), sub-sectors (from data), year ranges
- Filters update ForceGraph node visibility

**Step 4: Build ExploreView.jsx**

- Composes: context bar ("AI Inference Chips — 16 companies found") + ForceGraph (70%) + CompanySidebar (30% when open) + FilterChips below graph

**Step 5: Commit**

```bash
git add frontend/src/components/explore/
git commit -m "feat: add Explore Mode with force graph + sidebar + filters"
```

---

## Phase 7: Frontend — Deep Dive Mode

### Task 17: Deep Dive components

**Files:**
- Create: `frontend/src/components/deep-dive/DeepDiveView.jsx`
- Create: `frontend/src/components/deep-dive/SectionNav.jsx`
- Create: `frontend/src/components/deep-dive/ReportSection.jsx`
- Create: `frontend/src/components/deep-dive/FundingChart.jsx`
- Create: `frontend/src/components/deep-dive/NewsCard.jsx`
- Create: `frontend/src/components/deep-dive/CompetitorTable.jsx`
- Create: `frontend/src/components/deep-dive/RedFlagCard.jsx`
- Create: `frontend/src/components/shared/ConfidenceBadge.jsx`
- Create: `frontend/src/components/shared/SentimentBadge.jsx`
- Create: `frontend/src/components/shared/SourcePopover.jsx`

**Step 1: Build shared components first**

- ConfidenceBadge: green (>= 0.7), yellow (>= 0.4), red (< 0.4). Shows score + "N sources" text. Clickable.
- SentimentBadge: positive (green), neutral (gray), negative (red). Small pill.
- SourcePopover: on click, shows raw source snippet in a popover.

**Step 2: Build ReportSection.jsx**

- shadcn Card wrapper with: title, ConfidenceBadge in top-right, source count, content area, SourcePopover trigger

**Step 3: Build specialized sections**

- FundingChart: Recharts AreaChart showing funding rounds over time. X-axis = date, Y-axis = cumulative funding. Dots for each round with tooltip showing stage + investors.
- NewsCard: Card with colored left border (green/yellow/red by sentiment), title, date, snippet, source link.
- CompetitorTable: simple table with columns: Name, Description, Funding, Differentiator.
- RedFlagCard: amber/red background Card with warning icon from lucide-react, text, confidence badge.

**Step 4: Build SectionNav.jsx**

- Sticky left sidebar, list of section links: Overview, Funding, People, Product, News, Competitors, Red Flags
- Highlight active section based on scroll position (IntersectionObserver)

**Step 5: Build DeepDiveView.jsx**

- Layout: SectionNav (fixed left, 200px) + scrollable content area with all ReportSections stacked
- PDF download button in top-right

**Step 6: Commit**

```bash
git add frontend/src/components/deep-dive/ frontend/src/components/shared/
git commit -m "feat: add Deep Dive Mode with report sections + charts"
```

---

## Phase 8: Frontend — History + PDF + App Shell

### Task 18: History dashboard (landing page)

**Files:**
- Create: `frontend/src/components/history/HistoryGrid.jsx`
- Create: `frontend/src/components/history/HistoryCard.jsx`

**Step 1: Build HistoryCard.jsx**

- Card showing: query name, mode badge (Explore = blue, Deep Dive = purple), date, thumbnail area

**Step 2: Build HistoryGrid.jsx**

- Fetches `/api/history` on mount
- Renders grid of HistoryCards (CSS grid, responsive: 1 col mobile, 2 col tablet, 3 col desktop)
- Search/filter bar at top
- Click card → load cached result into main view

**Step 3: Commit**

```bash
git add frontend/src/components/history/
git commit -m "feat: add Results History dashboard as landing page"
```

---

### Task 19: PDF Export

**Files:**
- Create: `frontend/src/components/shared/PDFExport.jsx`

**Step 1: Build PDFExport.jsx**

- Button component that captures the Deep Dive report DOM and converts to PDF via html2pdf.js
- Styled output: header with "CompanyIntel Report", company name, date
- Confidence badges preserved as colored text
- Footer: "Sources verified as of [date]"

**Step 2: Commit**

```bash
git add frontend/src/components/shared/PDFExport.jsx
git commit -m "feat: add PDF export for Deep Dive reports"
```

---

### Task 20: App.jsx — wire everything together

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: Build App.jsx**

- State management: current view (history | explore | deep_dive), query results
- Layout: TopBar (always visible) + ProgressBar + StepIndicator + main content area + AgentLog
- Routing: no react-router needed — simple state-based view switching
- On submit: call useAgentQuery.submit(), show ProgressBar + StepIndicator, render ExploreView or DeepDiveView on complete
- On logo click: return to HistoryGrid

**Step 2: Update index.css with dark theme variables**

Set up CSS variables for shadcn dark theme: background, foreground, card, popover, primary, secondary, muted, accent, destructive colors.

**Step 3: Run dev server and verify**

```bash
cd frontend && npm run dev
```

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: wire App shell with view routing + dark theme"
```

---

## Phase 9: Integration + Fixtures

### Task 21: Fixture data for offline demo

**Files:**
- Create: `backend/fixtures/explore_ai_inference_chips.json`
- Create: `backend/fixtures/explore_digital_health_saas.json`
- Create: `backend/fixtures/deep_dive_nvidia.json`
- Create: `backend/fixtures/deep_dive_mistral_ai.json`
- Create: `backend/fixtures/deep_dive_recursion_pharma.json`

**Step 1: Generate fixture data**

Run the actual agent for each of the 5 demo queries and save the full output (report + critic report) as JSON fixtures. If API keys aren't available, manually construct realistic fixture data matching the Pydantic model schemas.

**Step 2: Add fixture loading to main.py**

Modify `/api/query` endpoint: before running the graph, check if query matches a fixture filename. If so, return fixture data directly.

**Step 3: Commit**

```bash
git add backend/fixtures/ backend/main.py
git commit -m "feat: add 5 demo fixtures for offline mode"
```

---

### Task 22: End-to-end integration test

**Files:**
- Create: `backend/tests/test_integration.py`

**Step 1: Write integration test using fixtures**

```python
# backend/tests/test_integration.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_explore_fixture_returns_result():
    resp = client.post("/api/query", json={"query": "AI inference chips", "mode": "explore"})
    assert resp.status_code == 200

def test_deep_dive_fixture_returns_result():
    resp = client.post("/api/query", json={"query": "NVIDIA", "mode": "deep_dive"})
    assert resp.status_code == 200

def test_history_returns_cached_reports():
    # After running queries, history should have entries
    resp = client.get("/api/history")
    assert resp.status_code == 200
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_integration.py -v`

**Step 3: Commit**

```bash
git add backend/tests/test_integration.py
git commit -m "test: add end-to-end integration tests with fixtures"
```

---

## Phase 10: Deployment Config

### Task 23: Backend Dockerfile + Railway config

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/railway.toml`

**Step 1: Write Dockerfile (includes Playwright for Crawl4AI)**

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y wget gnupg && \
    pip install playwright && playwright install --with-deps chromium && \
    apt-get clean
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Write railway.toml**

```toml
[build]
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
```

**Step 3: Commit**

```bash
git add backend/Dockerfile backend/railway.toml
git commit -m "feat: add Dockerfile + Railway deployment config"
```

---

### Task 24: Frontend Vercel config

**Files:**
- Create: `frontend/.env.example`
- Create: `frontend/vercel.json`

**Step 1: Write configs**

`.env.example`:
```
VITE_API_URL=http://localhost:8000
```

`vercel.json`:
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

**Step 2: Commit**

```bash
git add frontend/.env.example frontend/vercel.json
git commit -m "feat: add Vercel deployment config"
```

---

## Total: 24 Tasks across 10 Phases

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-4 | Backend foundation (scaffolding, models, config, cache) |
| 2 | 5-9 | Agent nodes (planner, searcher, profiler, synthesis, critic) |
| 3 | 10 | LangGraph graph definitions |
| 4 | 11 | FastAPI + SSE streaming |
| 5 | 12-14 | Frontend foundation (React, shadcn/ui, hooks) |
| 6 | 15-16 | Explore Mode UI |
| 7 | 17 | Deep Dive Mode UI |
| 8 | 18-20 | History, PDF export, App shell |
| 9 | 21-22 | Fixtures + integration tests |
| 10 | 23-24 | Deployment config |
