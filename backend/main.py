# backend/main.py
"""FastAPI application with SSE streaming for the Private Company Intelligence Agent.

Endpoints:
    GET  /health      - Health check
    GET  /api/history - List cached reports
    POST /api/query   - Run an explore or deep-dive query (SSE stream or cached)
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", message="urllib3.*chardet.*charset_normalizer")

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from backend.cache import CacheManager
from backend.config import get_settings
from backend.graph import build_deep_dive_graph, build_explore_graph
from backend.nodes.chat import ChatRequest, generate_chat_response
from backend.rag import get_indexed_report_count
from backend.validation import QueryValidation, QuerySuggestion, validate_query_rules, validate_query_semantic, suggest_query

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------
# Approximate token costs (USD per 1M tokens) — update when switching models
_MODEL_COSTS = {
    "deepseek/deepseek-v3.2": {"input": 0.26, "output": 0.38},
    "deepseek/deepseek-chat": {"input": 0.32, "output": 0.89},
    "google/gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
}


def _estimate_cost(mode: str, prose_model: str, extraction_model: str) -> float | None:
    """Rough cost estimate based on mode and models. Returns USD."""
    prose = _MODEL_COSTS.get(prose_model)
    extract = _MODEL_COSTS.get(extraction_model)
    if not prose:
        return None
    # Use extraction model costs if available, else fall back to prose model
    ext = extract or prose
    if mode == "explore":
        # Planner + profiler + explore synthesis: extraction model (~10K in, 5K out)
        # Critic: prose model (~15K in, 3K out)
        return round(
            (10_000 / 1_000_000) * ext["input"]
            + (5_000 / 1_000_000) * ext["output"]
            + (15_000 / 1_000_000) * prose["input"]
            + (3_000 / 1_000_000) * prose["output"],
            4,
        )
    else:
        # Extraction stages (planner + profiler + metadata): ~17K in, 9K out
        # Prose stages (13 sections + score + critic): ~125K in, 42K out
        return round(
            (17_000 / 1_000_000) * ext["input"]
            + (9_000 / 1_000_000) * ext["output"]
            + (125_000 / 1_000_000) * prose["input"]
            + (42_000 / 1_000_000) * prose["output"],
            4,
        )


# Startup check — log whether API keys are loaded
_s = get_settings()
logger.info("OPENROUTER_API_KEY loaded: %s", bool(_s.openrouter_api_key))
logger.info("TAVILY_API_KEY loaded: %s", bool(_s.tavily_api_key))
logger.info("EXA_API_KEY loaded: %s", bool(_s.exa_api_key))
logger.info("SERPER_API_KEY loaded: %s", bool(_s.serper_api_key))
logger.info("Models — prose: %s, extraction: %s, chat: %s", _s.llm_model, _s.extraction_model, _s.chat_model)

# ---------------------------------------------------------------------------
# Fixture loading for offline / demo mode
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent / "fixtures"

FIXTURE_MAP: dict[tuple[str, str], str] = {
    ("explore", "ai inference chips"): "explore_ai_inference_chips.json",
    ("explore", "digital health saas"): "explore_digital_health_saas.json",
    ("deep_dive", "nvidia"): "deep_dive_nvidia.json",
    ("deep_dive", "mistral ai"): "deep_dive_mistral_ai.json",
    ("deep_dive", "recursion pharmaceuticals"): "deep_dive_recursion_pharma.json",
}


def get_fixture(mode: str, query: str) -> dict | None:
    """Return fixture data for a known demo query, or None."""
    key = (mode, query.strip().lower())
    filename = FIXTURE_MAP.get(key)
    if filename:
        path = FIXTURES_DIR / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


@asynccontextmanager
async def lifespan(app):
    """Manage app-level resources like the SqliteSaver checkpointer.

    Note: SqliteSaver uses synchronous __enter__/__exit__. This is acceptable
    because SQLite open/close operations are fast (sub-millisecond).
    """
    s = get_settings()
    checkpointer = None
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        cp_path = Path(s.cache_dir) / "checkpoints.db"
        checkpointer = SqliteSaver.from_conn_string(str(cp_path))
        checkpointer.__enter__()
        logger.info("SqliteSaver checkpointer initialized at %s", cp_path)
    except ImportError:
        logger.info("SqliteSaver not available, running without checkpointing")
    except Exception as exc:
        logger.warning("Failed to initialize SqliteSaver: %s", exc)

    app.state.checkpointer = checkpointer
    yield

    if checkpointer is not None:
        try:
            checkpointer.__exit__(None, None, None)
        except Exception:
            pass


app = FastAPI(
    title="Private Company Intelligence Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — restrict to known frontends in production, allow all in development
_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
# Add Vercel deployment URLs from environment
import os as _os
_vercel_url = _os.environ.get("FRONTEND_URL")
if _vercel_url:
    _ALLOWED_ORIGINS.append(_vercel_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS if _os.environ.get("RAILWAY_ENVIRONMENT") else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------------------------------------------------------------------------
# Rate limiting — simple in-memory token bucket per IP
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 10          # max requests per window
_RATE_WINDOW = 60         # window in seconds


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple per-IP rate limiter for mutation endpoints."""
    if request.method in ("GET", "OPTIONS", "HEAD"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Clean old entries
    _rate_buckets[client_ip] = [t for t in _rate_buckets[client_ip] if now - t < _RATE_WINDOW]
    if len(_rate_buckets[client_ip]) >= _RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait a moment and try again."},
        )
    _rate_buckets[client_ip].append(now)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------
settings = get_settings()
cache = CacheManager(base_dir=settings.cache_dir)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: Literal["explore", "deep_dive"]

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        v = v.strip()
        # Tier 2: rule-based validation (defense in depth)
        result = validate_query_rules(v)
        if not result.is_valid:
            raise ValueError(result.reason)
        return v


class CachedResponse(BaseModel):
    cached: bool = True
    data: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/history")
async def history():
    """Return a list of all cached reports, newest first."""
    return cache.list_reports()


@app.get("/api/report/{filename}")
async def get_report(filename: str):
    """Return the full cached report data by filename."""
    data = cache.get_report_by_filename(filename)
    if data is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return data


@app.delete("/api/report/{filename}")
async def delete_report(filename: str):
    """Delete a cached report by filename."""
    deleted = cache.delete_report(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": filename}


class ValidateRequest(BaseModel):
    query: str = Field(..., min_length=1)

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class SuggestRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: Literal["explore", "deep_dive"]

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


@app.post("/api/validate")
async def validate(req: ValidateRequest):
    """Quick pre-flight validation: rule-based + LLM semantic check."""
    # Tier 2: rule-based
    rules_result = validate_query_rules(req.query)
    if not rules_result.is_valid:
        return rules_result

    # Tier 3: LLM semantic
    semantic_result = await validate_query_semantic(req.query)
    return semantic_result


@app.post("/api/suggest")
async def suggest(req: SuggestRequest):
    """Validate + suggest refined queries in one step."""
    # Tier 2: rule-based (instant)
    rules_result = validate_query_rules(req.query)
    if not rules_result.is_valid:
        return QuerySuggestion(
            is_valid=False,
            original_query=req.query,
            mode=req.mode,
            reason=rules_result.reason,
        )

    # Skip suggestions for fixture/cached queries
    if get_fixture(req.mode, req.query) or cache.get_report(req.mode, req.query):
        return QuerySuggestion(
            is_valid=True,
            confidence=1.0,
            suggestions=[req.query],
            original_query=req.query,
            mode=req.mode,
        )

    # LLM: validate + suggest in one call
    return await suggest_query(req.query, req.mode)


@app.post("/api/query")
async def query(req: QueryRequest):
    """Run an explore or deep-dive query.

    If the result is already cached, return it as a plain JSON response.
    Otherwise stream SSE events while the LangGraph agent runs.
    """
    # --- Fixture hit (offline / demo mode) ---------------------------------
    fixture = get_fixture(req.mode, req.query)
    if fixture is not None:
        return CachedResponse(data=fixture)

    # --- Cache hit ----------------------------------------------------------
    cached = cache.get_report(req.mode, req.query)
    if cached is not None:
        return CachedResponse(data=cached)

    # --- Cache miss: stream via SSE ----------------------------------------
    # Note: Tier 3 semantic validation removed — /api/suggest already validates
    # with web-search grounding. Tier 2 rule-based validation still runs in
    # QueryRequest.query_not_blank. Keeping Tier 3 here was blocking valid
    # queries for companies the LLM doesn't know about.
    NODE_DETAILS = {
        "planner": "Planning search strategy...",
        "searcher": "Searching for company data...",
        "profiler": "Building company profiles...",
        "synthesis": "Synthesizing report...",
        "critic": "Reviewing and scoring report...",
    }
    NODE_ORDER = ["planner", "searcher", "profiler", "synthesis", "critic"]

    async def event_generator():
        try:
            checkpointer = app.state.checkpointer

            # Pick the right graph builder
            if req.mode == "explore":
                graph = build_explore_graph(checkpointer=checkpointer)
            else:
                graph = build_deep_dive_graph(checkpointer=checkpointer)

            thread_id = str(uuid.uuid4())

            # Emit "start" event
            yield ServerSentEvent(
                data=json.dumps({"node": "system", "status": "running", "detail": f"Starting {req.mode} pipeline", "thread_id": thread_id}),
                event="status",
            )

            # Emit "running" for the first node
            yield ServerSentEvent(
                data=json.dumps({"node": "planner", "status": "running", "detail": NODE_DETAILS["planner"]}),
                event="status",
            )

            # Stream the graph node-by-node via astream so we can emit
            # SSE events as each node completes, rather than waiting for
            # the entire pipeline to finish.
            final_state = {}
            async for chunk in graph.astream(
                {"query": req.query, "mode": req.mode},
                stream_mode="updates",
                config={
                    "configurable": {"thread_id": thread_id},
                    "metadata": {
                        "mode": req.mode,
                        "query": req.query,
                    },
                },
            ):
                for node_name, output in chunk.items():
                    if node_name == "__start__":
                        continue

                    # Stream report sections BEFORE emitting "complete" for synthesis,
                    # so the frontend receives section data before it thinks synthesis is done.
                    if node_name == "synthesis" and isinstance(output, dict) and "report" in output:
                        report_obj = output["report"]
                        if hasattr(report_obj, "model_dump"):
                            report_dict = report_obj.model_dump()
                            for key in ["overview", "funding", "key_people", "product_technology", "recent_news", "competitors", "red_flags", "market_opportunity", "business_model", "competitive_advantages", "traction", "risks", "governance"]:
                                if key in report_dict and report_dict[key]:
                                    yield ServerSentEvent(
                                        data=json.dumps({"section": key, "content": report_dict[key]}),
                                        event="section",
                                    )

                    # Emit "complete" for the node that just finished
                    yield ServerSentEvent(
                        data=json.dumps({"node": node_name, "status": "complete", "detail": f"{node_name.title()} complete"}),
                        event="status",
                    )

                    # Emit "running" for the next node in the pipeline
                    try:
                        idx = NODE_ORDER.index(node_name)
                        if idx + 1 < len(NODE_ORDER):
                            next_node = NODE_ORDER[idx + 1]
                            yield ServerSentEvent(
                                data=json.dumps({"node": next_node, "status": "running", "detail": NODE_DETAILS[next_node]}),
                                event="status",
                            )
                    except ValueError:
                        pass

                    # Accumulate outputs for final payload
                    if isinstance(output, dict):
                        final_state.update(output)

            # Build the final payload
            report = final_state.get("report")
            report_data = report.model_dump() if hasattr(report, "model_dump") else (report or {})
            critic = final_state.get("critic_report")
            critic_data = critic.model_dump() if hasattr(critic, "model_dump") else (critic or {})

            final_payload = {
                "report": report_data,
                "critic": critic_data,
                "query": req.query,
                "mode": req.mode,
                "report_id": final_state.get("report_id", ""),
                "estimated_cost_usd": _estimate_cost(req.mode, settings.llm_model, settings.extraction_model),
            }

            # Cache the result
            cache.set_report(req.mode, req.query, final_payload)

            # Emit "complete" event
            yield ServerSentEvent(
                data=json.dumps(final_payload),
                event="complete",
            )
        except asyncio.CancelledError:
            # Client disconnected (e.g. user clicked Stop) — exit silently
            logger.info("Client disconnected during %s pipeline for query=%s", req.mode, req.query)
            return
        except GeneratorExit:
            # Generator was closed by the framework — exit silently
            logger.info("SSE generator closed for %s query=%s", req.mode, req.query)
            return
        except Exception as exc:
            logger.exception("Error running %s pipeline", req.mode)
            with suppress(Exception):
                yield ServerSentEvent(
                    data=json.dumps({"error": str(exc)}),
                    event="error",
                )

    return EventSourceResponse(event_generator())


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat with research data via RAG + LLM streaming."""
    async def event_generator():
        async for event in generate_chat_response(req):
            yield ServerSentEvent(
                event=event["type"],
                data=json.dumps(event),
            )
    return EventSourceResponse(event_generator())


@app.get("/api/chat/status")
async def chat_status():
    """Return count of indexed reports for the scope toggle UI."""
    return {"indexed_reports": get_indexed_report_count()}
