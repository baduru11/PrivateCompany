<p align="center">
  <h1 align="center">CompanyIntel</h1>
  <p align="center">
    <strong>AI-powered competitive intelligence on private companies and sectors</strong>
  </p>
  <p align="center">
    <a href="#features">Features</a> &bull;
    <a href="#demo">Demo</a> &bull;
    <a href="#architecture">Architecture</a> &bull;
    <a href="#getting-started">Getting Started</a> &bull;
    <a href="#deployment">Deployment</a> &bull;
    <a href="#api-reference">API</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12" />
    <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/LangGraph-0.4-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph" />
    <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React 19" />
    <img src="https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS 4" />
    <img src="https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white" alt="Vite 7" />
  </p>
</p>

---

CompanyIntel is a full-stack competitive intelligence platform that uses a LangGraph-orchestrated AI agent pipeline to research private companies and market sectors. It surfaces sourced, confidence-scored intelligence through a Bloomberg Terminal-inspired dark UI with interactive visualizations, scroll-spy investment reports, and RAG-powered chat.

## Features

**Explore Mode** — Enter a sector (e.g. *"AI inference chips"*) and get back 10-30 companies mapped on an interactive force-directed graph with funding stages, sub-sectors, and sortable metrics.

**Deep Dive Mode** — Enter a company name and receive a comprehensive investment report on a single scrollable page with a scroll-spy sidebar: Overview (investment score gauge + key metrics), Financials (funding chart + revenue estimate), Team (key people + board & advisors), Product & Market (technology analysis + patent portfolio), Traction (employee growth + partnerships + acquisitions + news), and Risk (competitor landscape + red flags).

**Research Chat (RAG)** — Ask follow-up questions about any report via a context-aware chat panel. Research data is automatically chunked and indexed into ChromaDB (with `all-MiniLM-L6-v2` embeddings) during the search phase. At chat time, relevant chunks are retrieved via cosine similarity (distance threshold 0.7), injected into the LLM context, and the response streams back via SSE. If RAG retrieval is weak (< 3 good results above threshold), the chat agent falls back to live web search via an LLM tool-calling loop (Serper first, then Tavily). Scope to the current report or search across all indexed reports.

**History Dashboard** — Browse, revisit, and manage all past research from the landing page. Export any deep dive report to PDF with one click.

### Highlights

- **Real-time streaming** — Watch the agent work step-by-step via Server-Sent Events with a live progress bar and collapsible agent log
- **Investment Score** — 4-axis framework (Money / Market / Momentum / Management, 0-25 each) producing a 0-100 overall investment readiness score with animated SVG gauge
- **Three-layer anti-hallucination defense** — Source-grounded synthesis prompts + Pydantic validators + independent Critic node that fact-checks every claim against raw sources
- **Confidence scoring** — Every data point carries a green/yellow/red confidence badge (0.0-1.0) so you know what's verified vs. uncertain
- **Two-phase query validation** — Rule-based heuristics (length, composition, keyboard-mash detection) + LLM semantic check with smart query suggestions before committing API credits
- **Offline demo mode** — 5 pre-built fixture datasets work instantly with zero API keys
- **Two-level caching** — API call cache + report cache (7-day TTL) eliminates redundant requests and serves repeat queries instantly
- **Multi-model LLM architecture** — Three specialized model roles routed through OpenRouter: a prose/reasoning model (DeepSeek v3.2), an extraction model (Gemini 3 Flash Preview with `:online` web grounding), and a chat model (Gemini 3 Flash Preview `:online`) — each configurable independently
- **Real-time web grounding** — The extraction and chat models use OpenRouter's `:online` suffix, enabling the LLM to search Google during every structured extraction call for up-to-date funding, traction, and news data
- **LangGraph retry loop** — Critic-driven quality gate with up to 2 search iterations for both explore and deep dive modes
- **Cost estimation** — Every query response includes an estimated USD cost based on model-specific token pricing
- **PDF export** — Client-side report export via html2pdf.js
- **Diffbot enrichment** — Optional Diffbot Knowledge Graph integration fills data gaps (headcount, revenue, founding year, operating status)
- **Funding round deduplication** — Fuzzy matching prevents duplicate funding entries across sources

## Demo

Try these queries with no API keys required:

| Mode | Query | What you'll see |
|------|-------|-----------------|
| Explore | `AI inference chips` | ~15 companies on a force-directed graph |
| Explore | `digital health saas` | Healthcare SaaS landscape with funding data |
| Deep Dive | `nvidia` | Full report — founded 1993, ~30k employees, funding history |
| Deep Dive | `mistral ai` | AI startup report — founded April 2023, key people, competitors |
| Deep Dive | `recursion pharmaceuticals` | Biotech report — founded 2013, drug pipeline, red flags |

## Architecture

### Agent Pipeline

Both modes use the same 5-node LangGraph pipeline with a critic-driven retry loop:

```
START → Planner → Searcher → Profiler → Synthesis → Critic → END
                                                       ↓ (if should_retry && iteration < 2)
                                                   retry_gate → Planner (with new search terms)
```

| Node | Responsibility |
|------|---------------|
| **Planner** | Generates a structured `SearchPlan` — 14-16 search terms covering funding, governance, patents, partnerships, revenue, workforce. Uses the extraction model. |
| **Searcher** | Parallel search across Exa (semantic discovery) + Tavily (web search) + Serper (Google search), deduplicated. Async RAG ingest into ChromaDB for chat. |
| **Profiler** | Explore: extraction model parses company data from snippets. Deep Dive: httpx full-page fetch → Crawl4AI → Jina Reader fallback + optional Diffbot KG enrichment. |
| **Synthesis** | Explore: produces an `ExploreReport` with companies list, sub-sectors, and summary. Deep Dive: parallel per-section prose generation (13 sections) + structured array extraction (funding rounds, board members, patents, acquisitions, etc.) + Investment Score (4-axis). |
| **Critic** | Fact-checks claims against raw source snippets, assigns per-section confidence scores (0.0-1.0). Evaluates quality and triggers retry if data is insufficient (< 8 companies in explore, or 3+ low-confidence sections in deep dive). Degrades gracefully on failure. |

### Deep Dive Report Sections

The deep dive produces 13 prose sections, each with confidence scores and source URLs:

Overview · Funding · Key People · Product & Technology · Market Opportunity · Business Model · Competitive Advantages · Traction · Competitors · Red Flags · Risks · Governance · Recent News

Plus structured data arrays: funding rounds, people entries, news items, competitor entries, board members, advisors, partnerships, key customers, acquisitions, patents, employee count history, revenue estimates, red flags, and risk entries.

### Tech Stack

```
┌─────────────────────────────────────────────────────────┐
│  Frontend                                               │
│  React 19 · Tailwind CSS 4 · Radix UI · Vite 7         │
│  react-force-graph-2d · Recharts · react-markdown       │
│  html2pdf.js · Lucide React                             │
├─────────────────────────────────────────────────────────┤
│  Backend                                                │
│  Python 3.12 · FastAPI · LangGraph 0.4                  │
│  SSE streaming · Pydantic v2                            │
├─────────────────────────────────────────────────────────┤
│  Search & Extraction                                    │
│  Tavily (web search) · Exa (semantic discovery)         │
│  Serper (Google search) · Crawl4AI (page extraction)    │
│  Jina Reader (fallback) · Diffbot KG (enrichment)       │
├─────────────────────────────────────────────────────────┤
│  RAG & Chat                                             │
│  ChromaDB (vector store) · SentenceTransformers         │
│  (all-MiniLM-L6-v2 embeddings)                          │
│  LLM tool-calling with web search fallback              │
├─────────────────────────────────────────────────────────┤
│  LLM (via OpenRouter)                                   │
│  Prose/reasoning: DeepSeek v3.2                         │
│  Extraction: Gemini 3 Flash Preview :online             │
│  Chat: Gemini 3 Flash Preview :online                   │
├─────────────────────────────────────────────────────────┤
│  Deploy                                                 │
│  Frontend → Vercel · Backend → Railway (Docker)         │
└─────────────────────────────────────────────────────────┘
```

### Query Validation

Two-phase validation prevents wasted API calls:

1. **Rule-based (instant)** — Length (3-200 chars), character composition, keyboard-mash heuristics (repeated chars, consecutive consonant runs), runs on both client and server
2. **LLM semantic (~1s)** — Single LLM call via `/api/suggest` verifies business relevance and returns refined query suggestions; fail-open on errors. Auto-proceeds if confidence >= 0.9.

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- (Optional) API keys for live queries — see [Environment Variables](#environment-variables)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # macOS/Linux
source venv/Scripts/activate    # Windows (Git Bash)

pip install -r requirements.txt

# Install Playwright for Crawl4AI page extraction
playwright install --with-deps chromium

# Configure environment
cp .env.example .env
# Edit .env with your API keys (optional for demo mode)

# Start the server
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env
# Default: VITE_API_URL=http://localhost:8000

# Start dev server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and try any of the demo queries above.

### Environment Variables

#### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | For live queries | — | OpenRouter API key (provides access to DeepSeek, Gemini, GPT-4o, Claude, etc.) |
| `LLM_MODEL` | No | `deepseek/deepseek-v3.2` | OpenRouter model ID for prose/reasoning (section writing, critic) |
| `EXTRACTION_MODEL` | No | `google/gemini-3-flash-preview:online` | OpenRouter model ID for structured JSON extraction with web grounding (planner, profiler, synthesis) |
| `CHAT_MODEL` | No | `google/gemini-3-flash-preview:online` | OpenRouter model ID for RAG chat with web grounding |
| `TAVILY_API_KEY` | For live queries | — | Tavily web search API key |
| `EXA_API_KEY` | For live queries | — | Exa semantic search API key |
| `SERPER_API_KEY` | For live queries | — | Serper Google search API key |
| `DIFFBOT_API_KEY` | No | — | Diffbot Knowledge Graph API key (optional enrichment) |
| `CACHE_DIR` | No | `cache` | Path to cache directory |
| `LANGCHAIN_TRACING_V2` | No | `false` | Enable LangSmith observability |

#### Frontend (`frontend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | No | `http://localhost:8000` | Backend API base URL |

> **Demo mode:** No API keys needed. Queries matching the 5 fixture names (exact, case-insensitive) return pre-built results instantly.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/query` | Run explore or deep dive — returns JSON (cached) or SSE stream (live) |
| `POST` | `/api/validate` | Pre-flight query validation (rule-based + LLM semantic) |
| `POST` | `/api/suggest` | Validate + suggest refined queries in one step |
| `GET` | `/api/history` | List all cached reports (newest first) |
| `GET` | `/api/report/{filename}` | Retrieve a specific cached report |
| `DELETE` | `/api/report/{filename}` | Delete a cached report |
| `POST` | `/api/chat` | RAG-powered chat over research data (SSE stream) |
| `GET` | `/api/chat/status` | Count of indexed reports for scope toggle UI |

### Query Request

```json
POST /api/query
{
  "query": "AI inference chips",
  "mode": "explore"           // "explore" or "deep_dive"
}
```

### Chat Request

```json
POST /api/chat
{
  "message": "What is their main competitive advantage?",
  "report_id": "abc123",
  "company_name": "Nvidia",
  "scope": "current"          // "current" or "all"
}
```

### SSE Events

| Event | Payload | Description |
|-------|---------|-------------|
| `status` | `{"node": "searcher", "status": "running", "detail": "...", "thread_id": "..."}` | Pipeline node progress |
| `section` | `{"section": "funding", "content": {...}}` | Deep dive report section as it completes |
| `complete` | `{"report": {...}, "critic": {...}, "query": "...", "mode": "...", "estimated_cost_usd": 0.005}` | Final result with cost estimate |
| `error` | `{"error": "..."}` | Error message |

## Deployment

### Backend — Railway

The backend deploys as a Docker container on Railway.

```bash
# railway.toml is pre-configured
# Set environment variables in the Railway dashboard
# Deploy via Railway CLI or GitHub integration
```

The Dockerfile installs Playwright + Chromium for Crawl4AI page extraction.

### Frontend — Vercel

```bash
# vercel.json is pre-configured
# Set VITE_API_URL to your Railway backend URL
# Deploy via Vercel CLI or GitHub integration
```

## Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI app — endpoints + SSE streaming + cost estimation
│   ├── models.py               # Pydantic schemas (reports, profiles, scores)
│   ├── config.py               # Settings + LLM provider factory + structured output helpers
│   ├── graph.py                # LangGraph state graph definitions
│   ├── cache.py                # Two-level caching (API calls + reports, 7-day TTL)
│   ├── validation.py           # Query validation (rule-based + LLM semantic + suggestions)
│   ├── rag.py                  # ChromaDB RAG — indexing + retrieval for chat
│   ├── utils.py                # Funding round deduplication (fuzzy matching)
│   ├── streaming.py            # SSE streaming utilities
│   ├── nodes/
│   │   ├── planner.py          # Search plan generation
│   │   ├── searcher.py         # Exa + Tavily + Serper parallel search
│   │   ├── profiler.py         # httpx + Crawl4AI + Jina + Diffbot extraction
│   │   ├── synthesis.py        # Parallel section synthesis + investment scoring
│   │   ├── critic.py           # Fact-checking + confidence scoring
│   │   └── chat.py             # RAG chat response generation with web search fallback
│   ├── apis/
│   │   └── diffbot.py          # Diffbot Knowledge Graph API client
│   ├── fixtures/               # 5 demo datasets (no API keys needed)
│   ├── tests/                  # pytest suite — 15 test files (unit + integration)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Root shell + view routing
│   │   ├── components/
│   │   │   ├── layout/         # TopBar, ProgressBar, StepIndicator, AgentLog, SuggestionPanel
│   │   │   ├── explore/        # ExploreView, ForceGraph, CompanySidebar, FilterChips
│   │   │   ├── deep-dive/      # Single-page scroll-spy report + 14 sub-components
│   │   │   │   ├── DeepDiveView.jsx        # Scroll-spy report shell + sidebar nav
│   │   │   │   ├── SectionNav.jsx          # Sidebar navigation
│   │   │   │   ├── InvestmentScoreCard.jsx # SVG gauge + 4-axis bars
│   │   │   │   ├── FundingChart.jsx        # Area chart + rounds table
│   │   │   │   ├── RevenueCard.jsx         # Revenue estimate + growth
│   │   │   │   ├── BoardCard.jsx           # Board members + advisors
│   │   │   │   ├── EmployeeChart.jsx       # Headcount line chart
│   │   │   │   ├── PartnershipCard.jsx     # Partnership cards
│   │   │   │   ├── AcquisitionCard.jsx     # M&A timeline
│   │   │   │   ├── PatentTable.jsx         # Patent portfolio table
│   │   │   │   ├── CompetitorTable.jsx     # Competitor matrix
│   │   │   │   ├── RedFlagCard.jsx         # Risk severity cards
│   │   │   │   ├── NewsCard.jsx            # News + sentiment
│   │   │   │   └── ReportSection.jsx       # Markdown section wrapper
│   │   │   ├── chat/           # ChatPanel, ChatInput, ChatMessage, ScopeToggle
│   │   │   ├── history/        # HistoryGrid, HistoryCard
│   │   │   ├── shared/         # CitationText, ConfidenceBadge, SourcePopover, MarkdownProse,
│   │   │   │                   #   SentimentBadge, LinkedInIcon, PDFExport
│   │   │   └── ui/             # Radix-based primitives (badge, button, card, input, popover,
│   │   │                       #   scroll-area, tabs, tooltip)
│   │   ├── hooks/              # useAgentQuery (two-phase SSE), useChatStream
│   │   └── lib/                # api.js, exportPdf.js, utils.js
│   ├── vercel.json
│   └── package.json
├── docs/plans/                 # Design documents + implementation plans
└── railway.toml
```

## Testing

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_integration.py -v    # End-to-end fixture tests
pytest tests/test_models.py -v         # Pydantic schema validation
pytest tests/test_main.py -v           # API endpoint tests
pytest tests/test_synthesis.py -v      # Synthesis node tests
pytest tests/test_config.py -v         # Config + structured output tests
pytest tests/test_validation.py -v     # Query validation tests
```

185 tests pass offline — no external API calls. Fixtures and mocks are used throughout. 15 test files covering cache, config, critic, eval, graph, integration, main, models, planner, profiler, searcher, SSE, synthesis, utils, and validation.

## API Credit Economics

| Query Type | Tavily | Exa | Serper | Estimated Cost |
|------------|--------|-----|--------|----------------|
| Explore (15 companies) | ~15 credits | 1 credit | ~15 credits | ~31 credits |
| Deep Dive (1 company) | ~5 credits | 0 | ~5 credits | ~10 credits |

**LLM costs** (via OpenRouter, default models):

| Model | Role | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|------|---------------------|----------------------|
| DeepSeek v3.2 | Prose / reasoning | $0.26 | $0.38 |
| Gemini 3 Flash Preview :online | Extraction + Chat | $0.15 | $0.60 |

The `:online` web grounding adds ~$0.02 per request (Exa search via OpenRouter). An explore query costs ~$0.30; a deep dive ~$0.50. Caching reduces repeat queries to zero cost.

## License

This project is proprietary software. All rights reserved.
