# backend/nodes/planner.py
from __future__ import annotations
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import get_llm, invoke_structured
from backend.models import SearchPlan

logger = logging.getLogger(__name__)

EXPLORE_PROMPT = """You are a competitive intelligence research planner.
Given a sector query, generate a search plan to discover 10-20 companies in this space.
Output search terms that will find companies, their funding, and key details.
Include sub-sector categories to organize the landscape."""

DEEP_DIVE_PROMPT = """You are a competitive intelligence research planner for investor due diligence.
Given a company name, generate 8-10 specific search terms to find comprehensive intelligence.
Include the company name in every search term. Cover these categories:

CORE INTELLIGENCE:
- "{company} funding rounds investors valuation"
- "{company} founders leadership team executives"
- "{company} headquarters employees headcount founding date"
- "{company} product technology platform"
- "{company} latest news announcements 2024 2025 2026"

COMPETITOR & MARKET ANALYSIS:
- "{company} competitors alternatives market landscape"
- "{company} market size TAM total addressable market"

DUE DILIGENCE:
- "{company} revenue customers growth traction business model"
- "{company} competitive advantages moat differentiation"
- "{company} regulatory risks concerns controversies"

Replace {company} with the actual company name.
Generate 8-10 search terms. Quality over quantity."""


def plan_search(state: dict) -> dict:
    llm = get_llm()

    query = state["query"]
    mode = state["mode"]
    prompt = EXPLORE_PROMPT if mode == "explore" else DEEP_DIVE_PROMPT

    try:
        plan = invoke_structured(llm, SearchPlan, [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Query: {query}")
        ])
    except Exception as exc:
        logger.error("Planner LLM call failed for query=%s: %s", query, exc)
        raise RuntimeError(f"Planner failed: {exc}") from exc

    return {"search_plan": plan}
