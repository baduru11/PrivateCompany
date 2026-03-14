# backend/nodes/critic.py
from __future__ import annotations
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import get_llm, invoke_structured
from backend.models import CriticReport

logger = logging.getLogger(__name__)

CRITIC_SYSTEM = """You are a rigorous fact-checker for investor due diligence reports.
You receive a synthesized report AND the raw source data (URL + content snippet) it was built from.

Your job:
1. Cross-check every claim in the report against the raw source snippets provided.
   If a claim's content appears in or is reasonably supported by a source snippet, mark it 'verified'.
2. Flag claims that don't appear in ANY source snippet as 'unverified'.
3. Flag contradictory data from different sources as 'conflicting'.
4. Score each section's confidence (0.0-1.0) based on how well its claims are supported
   by the source snippets. Use this scale:
   - 0.8-1.0: Most claims directly supported by source snippets
   - 0.6-0.8: Key claims supported, some minor details unverifiable
   - 0.4-0.6: Mix of supported and unsupported claims
   - 0.2-0.4: Most claims lack source support
   - 0.0-0.2: No source support or section is empty/stub
   Score ALL sections: overview, funding, key_people, product_technology,
   recent_news, competitors, red_flags, market_opportunity, business_model,
   competitive_advantages, traction, risks, governance.
5. List specific data gaps — missing competitor data, missing LinkedIn/Crunchbase
   links, missing market size, missing revenue/traction signals.
6. If more than 3 major sections have confidence < 0.4, recommend retry with specific queries.

IMPORTANT: A section that has substantial content derived from source snippets should score
at least 0.5. Do NOT give low confidence (< 0.3) to sections that clearly contain
source-backed information. Reserve very low scores for sections with fabricated or
completely unsupported content.

7. Verify that each citation [N] maps to a valid source URL in the raw data.
8. Check competitor_entries: flag if fewer than 3 competitors as a gap.
9. Check people_entries: flag missing LinkedIn URLs or background info as gaps."""


def critique(state: dict) -> dict:
    llm = get_llm()

    report = state["report"]
    raw_signals = state.get("raw_signals", [])

    report_text = report.model_dump_json(indent=2) if hasattr(report, "model_dump_json") else str(report)
    # Include truncated snippets so the critic can verify claims against actual content.
    # Cap at 60 signals with 500-char snippets to stay within token budget (~30k tokens).
    raw_text = "\n\n".join(
        f"[{s.source}] {s.url}\n{s.snippet[:600]}"
        for s in raw_signals[:60]
    ) if raw_signals else "No raw signals available"

    try:
        critic_report = invoke_structured(llm, CriticReport, [
            SystemMessage(content=CRITIC_SYSTEM),
            HumanMessage(content=f"Report:\n{report_text}\n\nRaw sources:\n{raw_text}")
        ])
    except Exception as exc:
        logger.error("Critic LLM call failed: %s", exc)
        # Degrade gracefully — the report is already complete from synthesis.
        # Losing the critic is far better than losing the entire pipeline result.
        critic_report = CriticReport(overall_confidence=0.0)

    # Derive low_confidence_sections from section_scores if the LLM didn't populate it
    if not critic_report.low_confidence_sections and critic_report.section_scores:
        critic_report.low_confidence_sections = [
            section for section, score in critic_report.section_scores.items()
            if score < 0.4
        ]

    # Pipeline is linear — never retry.
    critic_report.should_retry = False

    return {"critic_report": critic_report}
