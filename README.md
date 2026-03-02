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

CompanyIntel is a full-stack competitive intelligence platform that uses a LangGraph-orchestrated AI agent pipeline to research private companies and market sectors. It surfaces sourced, confidence-scored intelligence through a Bloomberg Terminal-inspired dark UI with interactive visualizations.

## Features

**Explore Mode** — Enter a sector (e.g. *"AI inference chips"*) and get back 10-20 companies mapped on an interactive force-directed graph with funding stages, sub-sectors, and sortable metrics.

**Deep Dive Mode** — Enter a company name and receive a comprehensive intelligence report: funding history, key people, recent news with sentiment analysis, competitor landscape, red flags, and per-section confidence scores.

**History Dashboard** — Browse, revisit, and manage all past research from the landing page. Export any deep dive report to PDF with one click.

### Highlights

- **Real-time streaming** — Watch the agent work step-by-step via Server-Sent Events with a live progress bar and collapsible agent log
- **Three-layer anti-hallucination defense** — Source-grounded synthesis prompts + Pydantic validators + independent Critic node that fact-checks every claim against raw sources
- **Confidence scoring** — Every data point carries a green/yellow/red confidence badge (0.0–1.0) so you know what's verified vs. uncertain
- **Offline demo mode** — 5 pre-built fixture datasets work instantly with zero API keys
- **Two-level caching** — API call cache + report cache eliminates redundant requests and serves repeat queries instantly
- **Multi-LLM support** — Switch between Gemini, GPT-4o, Claude, or DeepSeek with a single environment variable
- **PDF export** — Client-side report export via html2pdf.js

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

Both modes use the same 5-node LangGraph topology:

```
START → Planner → Searcher → Profiler → Synthesis → Critic → END
                     ↑                                  |
                     └──────── (max 1 retry) ───────────┘
```

| Node | Responsibility |
|------|---------------|
| **Planner** | Generates a structured `SearchPlan` — search terms, target company count, sub-sector breakdown |
| **Searcher** | Explore: Exa semantic discovery + Tavily fallback. Deep Dive: Tavily news/funding/press search |
| **Profiler** | Explore: LLM extraction from snippets. Deep Dive: Crawl4AI → Jina Reader → snippet fallback |
| **Synthesis** | Source-grounded LLM report generation with Pydantic structured output |
| **Critic** | Fact-checks claims against raw sources, assigns per-section confidence scores, triggers retry if needed |

### Tech Stack

```
┌─────────────────────────────────────────────────────────┐
│  Frontend                                               │
│  React 19 · Tailwind CSS 4 · shadcn/ui · Vite 7        │
│  react-force-graph-2d · Recharts · html2pdf.js          │
├─────────────────────────────────────────────────────────┤
│  Backend                                                │
│  Python 3.12 · FastAPI · LangGraph 0.4                  │
│  SSE streaming · Pydantic v2                            │
├─────────────────────────────────────────────────────────┤
│  Search & Extraction                                    │
│  Tavily (web search) · Exa (semantic discovery)         │
│  Crawl4AI (page extraction) · Jina Reader (fallback)    │
├─────────────────────────────────────────────────────────┤
│  LLM Providers                                          │
│  Gemini 2.5 Flash (default) · GPT-4o-mini · Claude      │
│  DeepSeek via OpenRouter                                │
├─────────────────────────────────────────────────────────┤
│  Deploy                                                 │
│  Frontend → Vercel · Backend → Railway (Docker)         │
└─────────────────────────────────────────────────────────┘
```

### Query Validation

Three-tier validation prevents wasted API calls:

1. **Client-side (instant)** — Length, character, and keyboard-mash heuristics
2. **Server-side (instant)** — Same rule-based checks in the API layer
3. **LLM semantic (~1s)** — Single LLM call verifies business relevance; fail-open on errors

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
uvicorn main:app --reload --port 8000
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
| `GEMINI_API_KEY` | For live queries | — | Google Gemini API key |
| `TAVILY_API_KEY` | For live queries | — | Tavily web search API key |
| `EXA_API_KEY` | For live queries | — | Exa semantic search API key |
| `OPENAI_API_KEY` | No | — | OpenAI API key (alternative LLM) |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (alternative LLM) |
| `OPENROUTER_API_KEY` | No | — | OpenRouter API key (DeepSeek, etc.) |
| `LLM_PROVIDER` | No | `gemini` | LLM provider: `gemini` / `openai` / `anthropic` / `openrouter` |
| `CACHE_DIR` | No | `cache` | Path to cache directory |

#### Frontend (`frontend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | No | `http://localhost:8000` | Backend API base URL |

> **Demo mode:** No API keys needed. Queries matching the 5 fixture names return pre-built results instantly.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/query` | Run explore or deep dive — returns JSON (cached) or SSE stream (live) |
| `POST` | `/api/validate` | Pre-flight query validation (rule-based + LLM semantic) |
| `GET` | `/api/history` | List all cached reports (newest first) |
| `GET` | `/api/report/{filename}` | Retrieve a specific cached report |
| `DELETE` | `/api/report/{filename}` | Delete a cached report |

### Query Request

```json
POST /api/query
{
  "query": "AI inference chips",
  "mode": "explore"           // "explore" or "deep_dive"
}
```

### SSE Events

| Event | Payload | Description |
|-------|---------|-------------|
| `status` | `{"node": "searcher", "status": "running", "detail": "..."}` | Pipeline node progress |
| `complete` | `{"report": {...}, "critic": {...}, "query": "...", "mode": "..."}` | Final result |
| `error` | `{"error": "..."}` | Error message |
| `heartbeat` | — | Keep-alive ping (every 15s) |

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
│   ├── main.py                 # FastAPI app — endpoints + SSE streaming
│   ├── models.py               # Pydantic schemas (reports, profiles, plans)
│   ├── config.py               # Settings + LLM provider factory
│   ├── graph.py                # LangGraph state graph definitions
│   ├── cache.py                # Two-level caching (API calls + reports)
│   ├── streaming.py            # SSE helpers + heartbeat
│   ├── validation.py           # Three-tier query validation
│   ├── nodes/
│   │   ├── planner.py          # Search plan generation
│   │   ├── searcher.py         # Exa + Tavily web search
│   │   ├── profiler.py         # Crawl4AI + Jina page extraction
│   │   ├── synthesis.py        # Source-grounded report generation
│   │   └── critic.py           # Fact-checking + confidence scoring
│   ├── fixtures/               # 5 demo datasets (no API keys needed)
│   ├── tests/                  # pytest suite (unit + integration)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Root shell + view routing
│   │   ├── components/
│   │   │   ├── layout/         # TopBar, ProgressBar, StepIndicator, AgentLog
│   │   │   ├── explore/        # ForceGraph, CompanySidebar, FilterChips
│   │   │   ├── deep-dive/      # DeepDiveView, SectionNav, FundingChart, ...
│   │   │   ├── history/        # HistoryGrid, HistoryCard
│   │   │   └── shared/         # PDFExport, SourcePopover, badges
│   │   ├── hooks/              # useAgentQuery, useSSE
│   │   └── lib/                # API client, utilities
│   ├── vercel.json
│   └── package.json
├── docs/plans/                 # Design document + implementation plan
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
```

All tests run offline — no external API calls. Fixtures and mocks are used throughout.

## API Credit Economics

| Query Type | Tavily | Exa | Estimated Cost |
|------------|--------|-----|----------------|
| Explore (15 companies) | ~15 credits | 1 credit | ~16 credits |
| Deep Dive (1 company) | ~5 credits | 0 | ~5 credits |

With 1,000 Tavily credits/month (free tier): ~50 explore queries or ~200 deep dives. Caching reduces repeat queries to zero cost. Crawl4AI and Jina Reader are free and unlimited.

## License

This project is proprietary software. All rights reserved.
