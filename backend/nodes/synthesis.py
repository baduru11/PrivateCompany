# backend/nodes/synthesis.py
from __future__ import annotations
import logging
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.utils import deduplicate_funding_rounds
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import get_llm, invoke_structured
from backend.models import (
    CompanyProfile, ExploreReport, DeepDiveReport, DeepDiveSection,
    SectionProse, FundingRound, PersonEntry, NewsItem, CompetitorEntry,
    RedFlag, RiskEntry, Citation,
)

logger = logging.getLogger(__name__)

EXPLORE_SYSTEM = """You are a competitive intelligence analyst. Given company profiles,
create a structured competitive landscape report.

INPUT FIELD MAPPING — populate each company with:
- name: company name
- sub_sector: specific technology/market niche
- funding_total: string like "$720M", "Public (IPO 1999)"
- funding_numeric: number in millions (0 for public companies)
- funding_stage: e.g. "Seed", "Series A", "Series B", "Series C+", "IPO / Public"
- founding_year: integer year
- headquarters: city, state/country
- key_investors: list of investor names
- description: 2-3 sentence company description
- confidence: 0.0-1.0 based on source coverage
- source_count: number of sources used

CRITICAL: Only include information from the provided data. Write 'Data not available' for missing fields. Never guess.

CITATIONS: For every factual claim, include an inline citation marker like [1], [2], etc.
Populate the 'citations' array with corresponding entries: {id, url, snippet}.
The snippet should be the exact text from the source that supports the claim."""

# Per-section prompts for parallel synthesis
_SECTION_PROMPTS = {
    "overview": """Write a comprehensive overview of this company for investor due diligence.
Cover: what the company does, its mission, market position, and key value proposition.
Write 2-3 substantive paragraphs using markdown formatting (use **bold** for key terms, bullet lists where appropriate).
CRITICAL: Only use information from the provided data. Never guess.""",

    "funding": """Write a detailed funding history analysis for investor due diligence.
Cover: total funding raised, funding trajectory, key investors, and what the funding signals about company health.
Write 2-3 substantive paragraphs using markdown formatting.
CRITICAL: Only use information from the provided data. Never guess.""",

    "key_people": """Write an analysis of the leadership team for investor due diligence.
Cover: key executives, their backgrounds, relevant experience, and team strengths/gaps.
Write 2-3 substantive paragraphs using markdown formatting.
CRITICAL: Only use information from the provided data. Never guess.""",

    "product_technology": """Write a product and technology analysis for investor due diligence.
Cover: core product/platform, technology stack, technical differentiation, and product-market fit signals.
Structure with markdown: use **bold** for key terms, use bullet points for feature lists, use ### subheadings if covering multiple products.
CRITICAL: Only use information from the provided data. Never guess.""",

    "market_opportunity": """Write a market opportunity analysis for investor due diligence.
Cover: TAM/SAM/SOM, market growth trends, market dynamics, and where this company fits.
Structure with markdown: use **bold** for key metrics, bullet points for market drivers.
CRITICAL: Only use information from the provided data. If no market data available, say so.""",

    "business_model": """Write a business model analysis for investor due diligence.
Cover: revenue model, pricing strategy, unit economics signals, and monetization approach.
Structure with markdown: use **bold** for key terms, bullet points for revenue streams.
CRITICAL: Only use information from the provided data. If no business model data available, say so.""",

    "competitive_advantages": """Write a competitive advantages / moat analysis for investor due diligence.
Cover: IP/patents, network effects, switching costs, data advantages, brand, and regulatory moats.
Structure with markdown: use **bold** for moat types, bullet points for each advantage.
CRITICAL: Only use information from the provided data. If no competitive advantage data available, say so.""",

    "traction": """Write a traction analysis for investor due diligence.
Cover: revenue signals, customer growth, key contracts, adoption metrics, and growth trajectory.
Structure with markdown: use **bold** for key metrics, bullet points for traction signals.
CRITICAL: Only use information from the provided data. If no traction data available, say so.""",

    "recent_news": """Write a recent news summary for investor due diligence.
Cover: key announcements, partnerships, product launches, and market developments.
Write 2-3 paragraphs using markdown formatting.
CRITICAL: Only use information from the provided data. Never guess.""",

    "competitors": """Write a competitive landscape analysis for investor due diligence.
Cover: key competitors, how they compare, market positioning, and competitive dynamics.
Write 2-3 substantive paragraphs using markdown formatting.
CRITICAL: Only use information from the provided data. Never guess.""",

    "red_flags": """Write a red flags assessment for investor due diligence.
Cover: any concerns, controversies, legal issues, team risks, or market risks identified.
If no red flags found, state that clearly.
Write using markdown formatting.
CRITICAL: Only use information from the provided data. Never guess.""",

    "risks": """Write a risk assessment for investor due diligence.
Cover: regulatory, market, technology, team, financial, and competitive risks.
Structure with markdown: use ### subheadings per risk category, bullet points for specific risks.
CRITICAL: Only use information from the provided data. If limited risk data available, say so.""",
}

_METADATA_PROMPT = """Extract metadata and structured arrays from the company profile data.

METADATA:
- company_name: string
- founded: string (e.g. "March 2023", "2018") — include month if available
- headquarters: string
- headcount: string (e.g. "~500", "200-300")
- funding_stage: string
- linkedin_url: string or null
- crunchbase_url: string or null

STRUCTURED ARRAYS (extract directly from profile data):
- funding_rounds: [{date, stage, amount, investors: [string], source_url}]
  IMPORTANT: Deduplicate funding rounds. If two rounds have the same amount and overlapping investors,
  keep only the one with the more specific date. Never list the same round twice.
- people_entries: [{name, title, background, source_url, linkedin_url, prior_exits: [string], domain_expertise_years: int, notable_affiliations: [string]}]
  IMPORTANT: Always include linkedin_url if found in sources. Search for "linkedin.com/in/" patterns.
- news_items: [{title, date, source_url, snippet, sentiment: "positive"|"neutral"|"negative"}]
  IMPORTANT: Sort by date descending (most recent first). Use ISO-like date format (YYYY-MM-DD or YYYY-MM).
- competitor_entries: [{name, description, funding, funding_stage, differentiator, overlap, website, source_url}]
  IMPORTANT: Include funding amount for each competitor if mentioned in sources.
- red_flag_entries: [{content, severity: "low"|"medium"|"high", confidence: 0.0-1.0, source_urls: [string]}]
- risk_entries: [{category: "regulatory"|"market"|"technology"|"team"|"financial"|"competitive", content, severity, confidence, source_urls}]
- citations: [{id: int, url: string, snippet: string}]

CRITICAL: Only include information from the provided data. Never guess.
Deduplicate all arrays — same person, same funding round, same news item should appear only once."""


class MetadataAndArrays(BaseModel):
    """Schema for metadata + structured arrays extraction."""
    company_name: str = ""
    founded: Optional[str] = None
    headquarters: Optional[str] = None
    headcount: Optional[str] = None
    funding_stage: Optional[str] = None
    linkedin_url: Optional[str] = None
    crunchbase_url: Optional[str] = None
    funding_rounds: list[FundingRound] = []
    people_entries: list[PersonEntry] = []
    news_items: list[NewsItem] = []
    competitor_entries: list[CompetitorEntry] = []
    red_flag_entries: list[RedFlag] = []
    risk_entries: list[RiskEntry] = []
    citations: list[Citation] = []


def _generate_section(llm, section_key: str, profiles_text: str, company_name: str) -> tuple[str, SectionProse]:
    """Generate a single section's prose via LLM. Returns (section_key, SectionProse)."""
    prompt = _SECTION_PROMPTS.get(section_key, "")
    if not prompt:
        return section_key, SectionProse(content="No data available.", confidence=0.0)

    try:
        result = invoke_structured(llm, SectionProse, [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Company: {company_name}\n\nCollected data:\n{profiles_text}")
        ])
        return section_key, result
    except Exception as exc:
        logger.warning("Section %s generation failed: %s", section_key, exc)
        return section_key, SectionProse(content="Data not available due to processing error.", confidence=0.0)


def synthesize(state: dict) -> dict:
    llm = get_llm()
    mode = state["mode"]
    profiles = state["company_profiles"]

    profiles_text = "\n\n".join(
        p.model_dump_json(indent=2) if hasattr(p, "model_dump_json")
        else str(p)
        for p in profiles
    )

    if mode == "explore":
        try:
            report = invoke_structured(llm, ExploreReport, [
                SystemMessage(content=EXPLORE_SYSTEM),
                HumanMessage(content=f"Query: {state['query']}\n\nCompany profiles:\n{profiles_text}")
            ])
        except Exception as exc:
            logger.error("Synthesis LLM call failed for query=%s mode=%s: %s", state['query'], mode, exc)
            raise RuntimeError(f"Synthesis failed: {exc}") from exc
        return {"report": report}

    # --- Deep-dive: parallel synthesis ---
    company_name = state["query"]

    # 1. Extract metadata + structured arrays (one LLM call)
    try:
        meta = invoke_structured(llm, MetadataAndArrays, [
            SystemMessage(content=_METADATA_PROMPT),
            HumanMessage(content=f"Company: {company_name}\n\nCollected data:\n{profiles_text}")
        ])
    except Exception as exc:
        logger.error("Metadata extraction failed: %s", exc)
        meta = MetadataAndArrays(company_name=company_name)

    meta.funding_rounds = deduplicate_funding_rounds(meta.funding_rounds)

    # 2. Generate logo URL from company website
    logo_url = None
    for p in profiles:
        if hasattr(p, 'website') and p.website:
            domain_match = re.match(r'https?://(?:www\.)?([^/]+)', p.website)
            if domain_match:
                domain = domain_match.group(1)
                logo_url = f"https://logo.clearbit.com/{domain}"
            break

    # 3. Generate all prose sections in parallel
    section_keys = [
        "overview", "funding", "key_people", "product_technology",
        "market_opportunity", "business_model", "competitive_advantages",
        "traction", "recent_news", "competitors", "red_flags", "risks",
    ]

    section_results: dict[str, SectionProse] = {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_generate_section, llm, key, profiles_text, company_name): key
            for key in section_keys
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                _, prose = future.result()
                section_results[key] = prose
            except Exception as exc:
                logger.warning("Section %s failed: %s", key, exc)
                section_results[key] = SectionProse(content="Data not available.", confidence=0.0)

    # 4. Assemble DeepDiveReport
    def _to_section(key: str) -> DeepDiveSection:
        prose = section_results.get(key, SectionProse(content="No data available.", confidence=0.0))
        return DeepDiveSection(
            title=key.replace("_", " ").title(),
            confidence=prose.confidence,
            content=prose.content,
            source_urls=prose.source_urls,
            source_count=prose.source_count,
        )

    def _to_optional_section(key: str):
        prose = section_results.get(key)
        if not prose or not prose.content or prose.content.strip().lower() in ("", "data not available.", "no data available.", "data not available due to processing error."):
            return None
        return _to_section(key)

    report = DeepDiveReport(
        query=state["query"],
        company_name=meta.company_name or company_name,
        founded=meta.founded,
        headquarters=meta.headquarters,
        headcount=meta.headcount,
        funding_stage=meta.funding_stage,
        linkedin_url=meta.linkedin_url,
        crunchbase_url=meta.crunchbase_url,
        logo_url=logo_url,
        overview=_to_section("overview"),
        funding=_to_section("funding"),
        funding_rounds=meta.funding_rounds,
        key_people=_to_section("key_people"),
        people_entries=meta.people_entries,
        product_technology=_to_section("product_technology"),
        recent_news=_to_section("recent_news"),
        news_items=meta.news_items,
        competitors=_to_section("competitors"),
        competitor_entries=meta.competitor_entries,
        red_flags=_to_section("red_flags"),
        red_flag_entries=meta.red_flag_entries,
        market_opportunity=_to_optional_section("market_opportunity"),
        business_model=_to_optional_section("business_model"),
        competitive_advantages=_to_optional_section("competitive_advantages"),
        traction=_to_optional_section("traction"),
        risks=_to_optional_section("risks"),
        risk_entries=meta.risk_entries,
        citations=meta.citations,
    )

    return {"report": report}
