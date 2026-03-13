# backend/nodes/critic.py
from __future__ import annotations
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import get_llm, invoke_structured
from backend.models import CriticReport

logger = logging.getLogger(__name__)

CRITIC_SYSTEM = """You are a rigorous fact-checker for investor due diligence reports.
You receive a synthesized report AND the raw source data it was built from.

Your job:
1. Cross-check every claim in the report against the raw sources
2. Flag claims that don't appear in any source as 'unverified'
3. Flag contradictory data from different sources as 'conflicting'
4. Score each section's confidence (0.0-1.0) based on source coverage.
   Score ALL sections including: overview, funding, key_people, product_technology,
   recent_news, competitors, red_flags, market_opportunity, business_model,
   competitive_advantages, traction, risks.
5. List specific data gaps — especially missing competitor data, missing LinkedIn/Crunchbase
   links, missing market size, missing revenue/traction signals
6. If more than 3 major sections have confidence < 0.4, recommend a retry with specific search queries

Be strict. An unverified claim is worse than 'Data not available'.

7. Verify that each citation [N] in the report maps to a valid source URL in the raw data.
   Flag citations that reference URLs not present in the source pool as 'unverified'.
8. Check competitor_entries: flag if fewer than 3 competitors are listed as a gap.
9. Check people_entries: flag missing LinkedIn URLs or background info as gaps."""


def critique(state: dict) -> dict:
    llm = get_llm()

    report = state["report"]
    raw_signals = state.get("raw_signals", [])

    report_text = report.model_dump_json(indent=2) if hasattr(report, "model_dump_json") else str(report)
    # Send only source+URL (no snippets) for the first 100 signals to reduce token waste
    raw_text = "\n".join(
        f"[{s.source}] {s.url}"
        for s in raw_signals[:100]
    ) if raw_signals else "No raw signals available"

    try:
        critic_report = invoke_structured(llm, CriticReport, [
            SystemMessage(content=CRITIC_SYSTEM),
            HumanMessage(content=f"Report:\n{report_text}\n\nRaw sources:\n{raw_text}")
        ])
    except Exception as exc:
        logger.error("Critic LLM call failed: %s", exc)
        raise RuntimeError(f"Critic failed: {exc}") from exc

    # Derive low_confidence_sections from section_scores if the LLM didn't populate it
    if not critic_report.low_confidence_sections and critic_report.section_scores:
        critic_report.low_confidence_sections = [
            section for section, score in critic_report.section_scores.items()
            if score < 0.4
        ]

    # Pipeline is linear — never retry.
    critic_report.should_retry = False

    return {"critic_report": critic_report}
