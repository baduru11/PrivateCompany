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
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from backend.cache import CacheManager
from backend.config import get_settings
from backend.graph import build_deep_dive_graph, build_explore_graph
from backend.streaming import format_sse
from backend.validation import QueryValidation, validate_query_rules, validate_query_semantic

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Startup check — log whether API keys are loaded
_s = get_settings()
logger.info("GEMINI_API_KEY loaded: %s", bool(_s.gemini_api_key))
logger.info("TAVILY_API_KEY loaded: %s", bool(_s.tavily_api_key))
logger.info("EXA_API_KEY loaded: %s", bool(_s.exa_api_key))

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


app = FastAPI(
    title="Private Company Intelligence Agent",
    version="0.1.0",
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    # --- Tier 3: LLM semantic validation (runs after cache/fixture) ---------
    semantic = await validate_query_semantic(req.query)
    if not semantic.is_valid:
        raise HTTPException(
            status_code=422,
            detail=semantic.reason + (f" Suggestion: {semantic.suggestion}" if semantic.suggestion else ""),
        )

    # --- Cache miss: stream via SSE ----------------------------------------
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
            # Pick the right graph builder
            if req.mode == "explore":
                graph = build_explore_graph()
            else:
                graph = build_deep_dive_graph()

            # Emit "start" event
            yield ServerSentEvent(
                data=json.dumps({"node": "system", "status": "running", "detail": f"Starting {req.mode} pipeline"}),
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
            ):
                for node_name, output in chunk.items():
                    if node_name == "__start__":
                        continue

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
            }

            # Cache the result
            cache.set_report(req.mode, req.query, final_payload)

            # Emit "complete" event
            yield ServerSentEvent(
                data=json.dumps(final_payload),
                event="complete",
            )
        except Exception as exc:
            logger.exception("Error running %s pipeline", req.mode)
            yield ServerSentEvent(
                data=json.dumps({"error": str(exc)}),
                event="error",
            )

    return EventSourceResponse(event_generator())
