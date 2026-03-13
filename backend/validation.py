# backend/validation.py
"""Query validation — rule-based and LLM semantic pre-check.

Tier 2 (rule-based) runs instantly with zero cost.
Tier 3 (LLM semantic) uses a single LLM call to check whether the query
is a valid business intelligence request (1 API call vs 20+ for the full pipeline).
"""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------
class QueryValidation(BaseModel):
    is_valid: bool
    reason: str = ""
    suggestion: str = ""


# ---------------------------------------------------------------------------
# Tier 2 — Rule-based validation (instant, free)
# ---------------------------------------------------------------------------
_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


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
