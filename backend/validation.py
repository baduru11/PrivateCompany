# backend/validation.py
"""Query validation — rule-based and LLM semantic pre-check.

Tier 2 (rule-based) runs instantly with zero cost.
Tier 3 (LLM semantic) uses a single LLM call to check whether the query
is a valid business intelligence request (1 API call vs 20+ for the full pipeline).
"""
from __future__ import annotations

import json
import logging
import re

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class QueryValidation(BaseModel):
    is_valid: bool
    reason: str = ""
    suggestion: str = ""


class QuerySuggestion(BaseModel):
    is_valid: bool
    suggestions: list[str] = []
    original_query: str = ""
    mode: str = ""
    confidence: float = 0.0  # >=0.9 means "skip suggestions, auto-proceed"
    reason: str = ""


# ---------------------------------------------------------------------------
# Tier 2 — Rule-based validation (instant, free)
# ---------------------------------------------------------------------------
_CONSONANTS = set("bcdfghjklmnpqrstvwxz")  # 'y' excluded — acts as vowel in crypto, gym, etc.


def validate_query_rules(query: str) -> QueryValidation:
    """Apply cheap heuristic checks. Returns invalid result on first failure."""
    q = query.strip()

    # Length checks
    if len(q) < 3:
        return QueryValidation(
            is_valid=False,
            reason="Query is too short (minimum 3 characters).",
            suggestion="Try a company name like 'Nvidia' or a sector like 'AI infrastructure'.",
        )
    if len(q) > 200:
        return QueryValidation(
            is_valid=False,
            reason="Query is too long (maximum 200 characters).",
            suggestion="Keep your query concise — e.g. 'digital health SaaS startups'.",
        )

    # Must contain at least one letter or digit
    if not re.search(r"[a-zA-Z0-9]", q):
        return QueryValidation(
            is_valid=False,
            reason="Query must contain letters or numbers.",
            suggestion="Try entering a company or sector name.",
        )

    # Reject 4+ repeated characters ("xxxx", "!!!!")
    if re.search(r"(.)\1{3,}", q):
        return QueryValidation(
            is_valid=False,
            reason="Query contains too many repeated characters.",
            suggestion="Enter a real company or sector name.",
        )

    # Reject keyboard mash: 5+ consecutive consonants ("asdfgh")
    lower = q.lower()
    consec = 0
    for ch in lower:
        if ch in _CONSONANTS:
            consec += 1
            if consec >= 5:
                return QueryValidation(
                    is_valid=False,
                    reason="Query looks like random keyboard input.",
                    suggestion="Try something like 'cloud computing companies' or 'Tesla'.",
                )
        else:
            consec = 0

    # At least 40% alphabetic characters
    alpha_count = sum(1 for ch in q if ch.isalpha())
    if len(q) > 0 and alpha_count / len(q) < 0.4:
        return QueryValidation(
            is_valid=False,
            reason="Query must be mostly text, not numbers or symbols.",
            suggestion="Describe a company or industry in words.",
        )

    return QueryValidation(is_valid=True)


# ---------------------------------------------------------------------------
# Tier 3 — LLM semantic validation (1 API call, fail-closed)
# ---------------------------------------------------------------------------
_SEMANTIC_PROMPT = """\
You are a query validator for a business intelligence tool.
Decide whether the user's query is a valid request to research a company, \
sector, industry, market, or business topic.

VALID examples: "Nvidia", "AI chip startups", "digital health SaaS", \
"Series A fintech companies", "Tesla competitors"
INVALID examples: "recipe for cookies", "tell me a joke", "what is 2+2", \
"write me a poem", "hello how are you"

Respond with EXACTLY one line in this format (no markdown, no extra text):
VALID
or
INVALID|<short reason>|<optional suggestion>

User query: {query}"""


async def validate_query_semantic(query: str) -> QueryValidation:
    """Use a single LLM call to check business relevance. Fail-closed on errors."""
    try:
        from backend.config import get_llm

        llm = get_llm()
        response = await llm.ainvoke(_SEMANTIC_PROMPT.format(query=query))
        text = response.content.strip()

        if text.startswith("VALID"):
            return QueryValidation(is_valid=True)

        parts = text.split("|", 2)
        reason = parts[1].strip() if len(parts) > 1 else "Query doesn't appear to be about a company or sector."
        suggestion = parts[2].strip() if len(parts) > 2 else ""
        return QueryValidation(is_valid=False, reason=reason, suggestion=suggestion)

    except Exception:
        logger.exception("Semantic validation failed — rejecting query")
        return QueryValidation(
            is_valid=False,
            reason="Validation service temporarily unavailable. Please retry in a moment.",
            suggestion="If this persists, check that the backend has a valid OPENROUTER_API_KEY.",
        )


# ---------------------------------------------------------------------------
# Query suggestion — validation + suggestions in one LLM call
# ---------------------------------------------------------------------------
def _quick_web_search(query: str, max_results: int = 5) -> str:
    """Run a fast web search to get real-time context for suggestion grounding.

    Tries Serper (fastest), falls back to Tavily. Returns a formatted string
    of search snippets, or empty string on failure.
    """
    from backend.config import get_settings
    settings = get_settings()

    # Try Serper first (simple HTTP POST, ~200ms)
    if settings.serper_api_key:
        try:
            resp = httpx.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.serper_api_key},
                json={"q": f"{query} company", "num": max_results},
                timeout=5,
            )
            resp.raise_for_status()
            results = resp.json().get("organic", [])[:max_results]
            if results:
                lines = []
                for r in results:
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    lines.append(f"- {title}: {snippet}")
                return "\n".join(lines)
        except Exception as exc:
            logger.debug("Serper quick search failed: %s", exc)

    # Fallback: Tavily
    if settings.tavily_api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.tavily_api_key)
            response = client.search(f"{query} company", max_results=max_results)
            results = response.get("results", [])
            if results:
                lines = []
                for r in results:
                    title = r.get("title", "")
                    content = r.get("content", "")[:200]
                    lines.append(f"- {title}: {content}")
                return "\n".join(lines)
        except Exception as exc:
            logger.debug("Tavily quick search failed: %s", exc)

    return ""


_SUGGEST_PROMPT = """\
You are a query assistant for a business intelligence tool.
The user submitted: "{query}"
Mode: {mode}
{web_context}
Your job:
1. Decide if this is a valid business/company/sector query.
2. If valid, rate your confidence (0.0–1.0) that the query is already \
well-formed and needs no refinement. 1.0 = perfect as-is, 0.5 = could be improved.
3. Suggest 3-5 refined or corrected versions of the query.

IMPORTANT: Use the web search results above to identify the correct company/sector. \
Do NOT rely solely on your training data — the web results are more current.

DEDUPLICATION RULES:
- Each suggestion must be a DIFFERENT company or sector, not a rephrasing of the same one.
- If all web results point to ONE company, set confidence to 0.95 and return just \
that single company as the only suggestion. Do NOT generate 3-5 paraphrases of the same company.
- Only suggest multiple options when there are genuinely DIFFERENT entities that share \
a name (e.g. "Amber" → "Amber Group (crypto)" vs "Amber Beverage Group (spirits)").
- Include the industry/sector in parentheses to disambiguate.

For "deep_dive" mode: suggest corrected/canonical company names with their sector \
(e.g. "nvdia" → "Nvidia (GPU & AI chips)", "amber" → "Amber Group (crypto financial services)", \
"Amber Beverage Group (spirits & beverages)").
For "explore" mode: suggest refined sector phrases \
(e.g. "chips" → "AI Inference Chip Startups", "Semiconductor Companies").

Respond with ONLY valid JSON (no markdown, no extra text):
{{"is_valid": true/false, "confidence": 0.0-1.0, "suggestions": ["..."], "reason": "..."}}

If the query is not about business/companies/sectors, set is_valid=false and \
explain in reason. suggestions can be empty for invalid queries."""


async def suggest_query(query: str, mode: str) -> QuerySuggestion:
    """Combine validation + suggestion generation in a single LLM call.

    Grounded by a quick web search so suggestions reflect real-time data,
    not just the LLM's training cutoff.

    Fail-open: on any error, returns confidence=1.0 so the user proceeds
    with their original query unblocked.
    """
    try:
        from backend.config import get_llm

        # Quick web search for real-time grounding (runs synchronously, ~200ms)
        web_results = _quick_web_search(query)
        web_context = ""
        if web_results:
            web_context = f"\nWeb search results for \"{query}\":\n{web_results}\n"

        llm = get_llm()
        response = await llm.ainvoke(
            _SUGGEST_PROMPT.format(query=query, mode=mode, web_context=web_context)
        )
        text = response.content.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)

        return QuerySuggestion(
            is_valid=data.get("is_valid", True),
            suggestions=data.get("suggestions", [query]),
            original_query=query,
            mode=mode,
            confidence=float(data.get("confidence", 0.5)),
            reason=data.get("reason", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse suggestion LLM response: %s", exc)
        return QuerySuggestion(
            is_valid=True,
            suggestions=[query],
            original_query=query,
            mode=mode,
            confidence=1.0,
            reason="",
        )
    except Exception:
        logger.exception("Suggestion LLM call failed — failing open")
        return QuerySuggestion(
            is_valid=True,
            suggestions=[query],
            original_query=query,
            mode=mode,
            confidence=1.0,
            reason="",
        )
