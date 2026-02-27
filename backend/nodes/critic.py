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
