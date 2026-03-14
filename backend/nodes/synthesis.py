# backend/nodes/synthesis.py
from __future__ import annotations
import logging
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.utils import deduplicate_funding_rounds
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import get_llm, get_settings, invoke_structured
from backend.models import (
    CompanyProfile, ExploreCompany, ExploreReport, DeepDiveReport, DeepDiveSection,
    SectionProse, FundingRound, PersonEntry, NewsItem, CompetitorEntry,
    RedFlag, RiskEntry, Citation, InvestmentScore,
    BoardMember, Advisor, Partnership, KeyCustomer, Acquisition,
    Patent, RevenueEstimate, EmployeeCountPoint,
)

logger = logging.getLogger(__name__)

EXPLORE_SYSTEM = """You are a competitive intelligence analyst. Given company profiles,
create a structured competitive landscape report.

STRICT RULES:
1. RELEVANCE: Only include companies that are DIRECTLY relevant to the query.
   - Exclude generic tech giants (Microsoft, Google, Amazon, Apple) unless they have a
     dedicated product specifically in this space.
   - Exclude YouTube videos, blog posts, listicles, or non-companies.
   - Exclude tiny hobby projects, personal tools, or single-developer side projects with
     no evidence of being a real business (no team, no funding, no product traction).
2. QUALITY: Prioritize by business maturity. List the most significant first:
   - Tier 1: Funded startups or established companies with teams, investors, press coverage
   - Tier 2: Apps/products with real users, reviews, or meaningful traction (app store presence,
     user testimonials, active community) — these are valid even without traditional funding
   - Exclude: Hobby projects, demo apps, or tools with no evidence of real usage
3. DEDUPLICATION: Never include the same company twice. If a company appears multiple times
   in the source data, merge the information into a single entry.
4. LIMIT: Include at most 20 companies. Quality over quantity — 10 well-documented companies
   is better than 20 sparse ones.
5. CONFIDENCE: Set confidence based on actual data quality:
   - 0.8-1.0: Multiple sources confirm key facts (funding, founding year, etc.)
   - 0.5-0.7: Some data available but gaps exist
   - 0.2-0.4: Very sparse data, mostly just a name and description

INPUT FIELD MAPPING — populate each company with:
- name: company name (official name, not a product feature description)
- sub_sector: specific technology/market niche within the queried sector
- website: company website URL (e.g. "https://dishgen.com"). Extract from source data.
- funding_total: string like "$720M", "Public (IPO 1999)". Use null if unknown.
- funding_numeric: number in millions (0 if unknown or public)
- funding_stage: e.g. "Seed", "Series A", "Series B", "Series C+", "IPO / Public". Use null if unknown.
- founding_year: integer year. Use null if unknown (do NOT write "Data not available").
- headquarters: city, state/country. Use null if unknown.
- key_investors: list of investor names. Use empty list [] if unknown.
- description: 2-3 sentence company description focused on what makes them relevant to the query
- confidence: 0.0-1.0 based on the rules above
- source_count: number of distinct sources used for this company
- app_store_rating: float rating (e.g. 4.5) from App Store or Google Play. Use null if not found.
- app_store_reviews: review count as string (e.g. "12K reviews"). Use null if not found.
- app_downloads: download count as string (e.g. "1M+"). Use null if not found.
- user_count: user/MAU count as string (e.g. "500K users"). Use null if not found.

CRITICAL SOURCING RULES:
- Only include information explicitly found in the provided source data.
- Do NOT use your pretrained knowledge to fill in company details. If a fact is not in the
  sources, use null. Every data point must come from the provided text.
- Do NOT write string values like "Data not available" — use null instead.
- Do NOT invent or guess website URLs, funding amounts, or founding years.

CITATIONS: For every factual claim, include an inline citation marker like [1], [2], etc.
Populate the 'citations' array with corresponding entries: {id, url, snippet}.
The snippet should be the exact text from the source that supports the claim."""


def _parse_funding_numeric(funding_str: str | None) -> float:
    """Extract a numeric funding value (in millions) from a string like '$720M'."""
    if not funding_str:
        return 0.0
    m = re.search(r'\$\s*([\d.]+)\s*([BMK])?', funding_str, re.IGNORECASE)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = (m.group(2) or '').upper()
    if unit == 'B':
        val *= 1000
    elif unit == 'K':
        val /= 1000
    return val


_SECTION_FORMAT_RULES = """
FORMAT RULES (apply to every section):
- Do NOT start with a title, heading, or section name — the UI already displays the section title.
- Do NOT write an "Executive Summary" or opening preamble like "Based on the provided data...".
- Do NOT end with a disclaimer, caveat, or "Note:" paragraph about data limitations or due diligence.
- Jump straight into the substance on the first line. End with the last substantive point.
- Use markdown: **bold** for key terms, bullet lists, ### subheadings for sub-topics.
- INLINE CITATIONS: For every factual claim, add an inline citation marker like [1], [2], etc.
  referring to the source URL where you found the information. These markers must correspond to
  entries in the citations array extracted separately.
- CRITICAL: Only use information from the provided data. Never guess or infer."""

# Per-section prompts for parallel synthesis
_SECTION_PROMPTS = {
    "overview": f"""Write a comprehensive overview of this company for investor due diligence.
Cover: what the company does, its mission, market position, and key value proposition.
Write 2-3 substantive paragraphs.
{_SECTION_FORMAT_RULES}""",

    "funding": f"""Write a detailed funding history analysis for investor due diligence.
Cover: total funding raised, funding trajectory, key investors, and what the funding signals about company health.
Write 2-3 substantive paragraphs.
{_SECTION_FORMAT_RULES}""",

    "key_people": f"""Write an analysis of the leadership team for investor due diligence.
Cover: key executives, their backgrounds, relevant experience, and team strengths/gaps.
Write 2-3 substantive paragraphs.
{_SECTION_FORMAT_RULES}""",

    "product_technology": f"""Write a product and technology analysis for investor due diligence.
Cover: core product/platform, technology stack, technical differentiation, and product-market fit signals.
Use ### subheadings if covering multiple products.
{_SECTION_FORMAT_RULES}""",

    "market_opportunity": f"""Write a market opportunity analysis for investor due diligence.
Cover: TAM/SAM/SOM, market growth trends, market dynamics, and where this company fits.
If no market data available, say so briefly.
{_SECTION_FORMAT_RULES}""",

    "business_model": f"""Write a business model analysis for investor due diligence.
Cover: revenue model, pricing strategy, unit economics signals, and monetization approach.
If no business model data available, say so briefly.
{_SECTION_FORMAT_RULES}""",

    "competitive_advantages": f"""Write a competitive advantages / moat analysis for investor due diligence.
Cover: IP/patents, network effects, switching costs, data advantages, brand, and regulatory moats.
If no competitive advantage data available, say so briefly.
{_SECTION_FORMAT_RULES}""",

    "traction": f"""Write a traction analysis for investor due diligence.
Cover: revenue signals, customer growth, key contracts, adoption metrics, and growth trajectory.
If no traction data available, say so briefly.
{_SECTION_FORMAT_RULES}""",

    "recent_news": f"""Write a recent news summary for investor due diligence.
Cover: key announcements, partnerships, product launches, and market developments.
Write 2-3 paragraphs.
{_SECTION_FORMAT_RULES}""",

    "competitors": f"""Write a competitive landscape analysis for investor due diligence.
Cover: key competitors, how they compare, market positioning, and competitive dynamics.
Write 2-3 substantive paragraphs.
{_SECTION_FORMAT_RULES}""",

    "red_flags": f"""Write a red flags assessment for investor due diligence.
Cover: any concerns, controversies, legal issues, team risks, or market risks identified.
If no red flags found, state that clearly in one sentence — do not pad with generic risk language.
{_SECTION_FORMAT_RULES}""",

    "risks": f"""Write a risk assessment for investor due diligence.
Cover: regulatory, market, technology, team, financial, and competitive risks.
Use ### subheadings per risk category.
{_SECTION_FORMAT_RULES}""",

    "governance": f"""Write a governance analysis for investor due diligence.
Cover: board composition and quality, advisor network, governance structure, and what it signals about company maturity.
Highlight notable board members' backgrounds, investor representation on the board, and advisor expertise areas.
{_SECTION_FORMAT_RULES}""",
}

_METADATA_PROMPT = """Extract metadata and structured arrays for the TARGET COMPANY ONLY.

You will receive structured profile data AND raw source snippets. Use BOTH to extract
the most complete and accurate information possible. The raw snippets contain the original
source text — use them to verify and enrich the structured data.

CRITICAL SCOPING RULE: Only extract people, board members, advisors, and other entries that
belong to the TARGET company (specified in "Company: ..." below). Do NOT include executives,
board members, or employees of competitor companies, investors, or partner organizations.
If a person's affiliation is unclear, omit them.

METADATA:
- company_name: string
- founded: string (e.g. "March 2023", "2018") — include month if available
- headquarters: string
- headcount: string (e.g. "~500", "200-300")
- funding_stage: string
- linkedin_url: string or null
- crunchbase_url: string or null
- operating_status: "Active" | "Acquired" | "Closed" | "IPO" (default "Active" if unclear)
- total_funding: string (e.g. "$1.2B", "$50M") — total capital raised across all rounds

STRUCTURED ARRAYS (extract directly from profile data AND raw source snippets):
- funding_rounds: [{date, stage, amount, investors: [string], lead_investor: string or null, pre_money_valuation: string or null, post_money_valuation: string or null, source_url}]
  CRITICAL DEDUP: Multiple sources often report the SAME round with slightly different amounts
  (e.g. $3.4M vs $3.5M vs $3.9M) or with different subsets of investors. These are ONE round.
  If amounts are within 30% of each other AND the investor lists overlap, it is the SAME round.
  Output it only ONCE with the most specific date and the most complete investor list.
  Include lead_investor separately from the investors list. Include valuations if mentioned.
- people_entries: [{name, title, background, source_url, linkedin_url, prior_exits: [string], domain_expertise_years: int, notable_affiliations: [string]}]
  IMPORTANT: Only include people who WORK AT the target company (founders, executives, employees).
  Do NOT include investors, competitor executives, or people from other organizations.
  Always include linkedin_url if found in sources. Search for "linkedin.com/in/" patterns.
  Verify each person's title and background against the raw source snippets.
- news_items: [{title, date, source_url, snippet, sentiment: "positive"|"neutral"|"negative"}]
  IMPORTANT: Sort by date descending (most recent first). Use ISO-like date format (YYYY-MM-DD or YYYY-MM).
- competitor_entries: [{name, description, funding, funding_stage, differentiator, overlap, website, source_url}]
  IMPORTANT: Include funding amount for each competitor if mentioned in sources.
- red_flag_entries: [{content, severity: "low"|"medium"|"high", confidence: 0.0-1.0, source_urls: [string]}]
- risk_entries: [{category: "regulatory"|"market"|"technology"|"team"|"financial"|"competitive", content, severity, confidence, source_urls}]
- board_members: [{name, role: "Chair"|"Member"|"Observer", organization, background, linkedin_url, source_url}]
  IMPORTANT: Only include board members OF the target company. Investor partners who sit on the board
  should be listed with their VC firm as "organization", but they must actually serve on THIS company's board.
- advisors: [{name, expertise, organization, linkedin_url, source_url}]
  IMPORTANT: Only include advisors TO the target company.
- partnerships: [{partner_name, type: "strategic"|"customer"|"technology"|"distribution", description, date, source_url}]
- key_customers: [{name, description, source_url}]
- acquisitions: [{acquired_company, date, amount, rationale, source_url}]
- patents: [{title, filing_date, status: "granted"|"pending", domain, patent_number, source_url}]
- revenue_estimate: {range: string, growth_rate: string, source_url: string, confidence: 0.0-1.0} or null
- employee_count_history: [{date: string, count: int, source: string}]
- citations: [{id: int, url: string, snippet: string}]

CRITICAL: Only include information from the provided data. Never guess.
Deduplicate all arrays — same person, same funding round, same news item should appear only once."""


_INVESTMENT_SCORE_PROMPT = """You are an investment analyst scoring a private company's investment readiness.
Based on the provided research data, assign four sub-scores (0-25 each) and an overall score (0-100).

MONEY (0-25): Evaluate financial health signals.
- Recent funding round (within 18 months = higher)
- Healthy round progression (Seed → A → B = good trajectory)
- Reputable investors (well-known VCs = higher)
- Total funding appropriate for stage
- Revenue signals present (ARR, growth rate)

MARKET (0-25): Evaluate market positioning.
- TAM mentioned and sized (larger = higher, but must be credible)
- Market growth signals present
- Clear market positioning and differentiation
- Business model clarity
- Low regulatory risk

MOMENTUM (0-25): Evaluate growth signals.
- Positive recent news (partnerships, launches, awards)
- Hiring / employee growth
- Partnership activity
- Recent funding round
- Customer wins and traction signals

MANAGEMENT (0-25): Evaluate team quality.
- Founder/executive prior exits
- Domain expertise (years in industry)
- Board quality (reputable investors/operators)
- Advisor network strength
- Complete leadership (CEO + CTO + key roles filled)

Output:
- overall: sum of four sub-scores (0-100)
- money, market, momentum, management: individual scores (0-25 each)
- rationale: 2-3 sentences explaining the score, highlighting strongest and weakest areas

CRITICAL: Only use information from the provided data. Score conservatively — missing data should lower scores."""


class MetadataAndArrays(BaseModel):
    """Schema for metadata + structured arrays extraction."""
    company_name: str = ""
    founded: Optional[str] = None
    headquarters: Optional[str] = None
    headcount: Optional[str] = None
    funding_stage: Optional[str] = None
    linkedin_url: Optional[str] = None
    crunchbase_url: Optional[str] = None
    operating_status: Optional[str] = None
    total_funding: Optional[str] = None
    funding_rounds: list[FundingRound] = []
    people_entries: list[PersonEntry] = []
    news_items: list[NewsItem] = []
    competitor_entries: list[CompetitorEntry] = []
    red_flag_entries: list[RedFlag] = []
    risk_entries: list[RiskEntry] = []
    citations: list[Citation] = []
    board_members: list[BoardMember] = []
    advisors: list[Advisor] = []
    partnerships: list[Partnership] = []
    key_customers: list[KeyCustomer] = []
    acquisitions: list[Acquisition] = []
    patents: list[Patent] = []
    revenue_estimate: Optional[RevenueEstimate] = None
    employee_count_history: list[EmployeeCountPoint] = []


def _merge_profiles_into_meta(meta: MetadataAndArrays, profiles: list[CompanyProfile], company_name: str) -> None:
    """Fill MetadataAndArrays gaps from already-structured CompanyProfile fields.

    The LLM re-extraction sometimes drops basic info that the profiler already captured.
    This ensures trivial fields like founded year, headcount, and headquarters survive.
    Only merges from profiles that match the target company name to avoid cross-contamination.
    """
    target = company_name.strip().lower()
    target_words = set(target.split())
    for p in profiles:
        # Skip profiles that don't match the target company.
        # Use both substring and word-overlap checks to handle variations
        # like "Apple" vs "Apple Inc." or "Mistral AI" vs "Mistral AI SAS".
        if p.name:
            pname = p.name.strip().lower()
            is_substring = target in pname or pname in target
            pname_words = set(pname.split())
            word_overlap = len(target_words & pname_words) / max(len(target_words), 1)
            if not is_substring and word_overlap < 0.5:
                continue
        # Basic metadata — fill only if LLM left it empty
        if not meta.founded and p.founding_year:
            month_part = f"{p.founding_month} " if getattr(p, "founding_month", None) else ""
            meta.founded = f"{month_part}{p.founding_year}"
        if not meta.headquarters and p.headquarters:
            meta.headquarters = p.headquarters
        if not meta.headcount and p.headcount_estimate:
            meta.headcount = p.headcount_estimate
        if not meta.funding_stage and p.funding_stage:
            meta.funding_stage = p.funding_stage
        if not meta.linkedin_url and p.linkedin_url:
            meta.linkedin_url = p.linkedin_url
        if not meta.crunchbase_url and p.crunchbase_url:
            meta.crunchbase_url = p.crunchbase_url
        if not meta.total_funding and p.funding_total:
            meta.total_funding = p.funding_total
        if not meta.operating_status and getattr(p, "operating_status", None):
            meta.operating_status = p.operating_status
        if not meta.company_name or meta.company_name == company_name:
            if p.name and p.name.strip():
                meta.company_name = p.name

        # People — merge any profiler-extracted people the LLM missed
        # Only merge people who have a title (people without titles are likely
        # from other companies that appeared in search results)
        existing_people = {pe.name.lower().strip() for pe in meta.people_entries}
        for person in p.key_people:
            name = person.get("name", "")
            title = person.get("title")
            if name and name.lower().strip() not in existing_people and title:
                meta.people_entries.append(PersonEntry(
                    name=name,
                    title=title,
                    background=person.get("background"),
                    linkedin_url=person.get("linkedin_url"),
                    source_url=person.get("source_url"),
                ))
                existing_people.add(name.lower().strip())

        # Competitors — merge profiler-extracted competitors the LLM missed
        existing_competitors = {ce.name.lower().strip() for ce in meta.competitor_entries}
        for comp in p.competitors_mentioned:
            name = comp.get("name", "")
            if name and name.lower().strip() not in existing_competitors:
                meta.competitor_entries.append(CompetitorEntry(
                    name=name,
                    description=comp.get("description"),
                    funding=comp.get("funding"),
                    funding_stage=comp.get("funding_stage"),
                    differentiator=comp.get("differentiator"),
                    overlap=comp.get("overlap"),
                    website=comp.get("website"),
                    source_url=comp.get("source_url"),
                ))
                existing_competitors.add(name.lower().strip())

        # Board members — merge
        existing_board = {bm.name.lower().strip() for bm in meta.board_members}
        for bm in p.board_members:
            name = bm.get("name", "")
            if name and name.lower().strip() not in existing_board:
                meta.board_members.append(BoardMember(
                    name=name,
                    role=bm.get("role"),
                    organization=bm.get("organization"),
                    background=bm.get("background"),
                    linkedin_url=bm.get("linkedin_url"),
                    source_url=bm.get("source_url"),
                ))
                existing_board.add(name.lower().strip())

        # Advisors — merge
        existing_advisors = {a.name.lower().strip() for a in meta.advisors}
        for adv in p.advisors:
            name = adv.get("name", "")
            if name and name.lower().strip() not in existing_advisors:
                meta.advisors.append(Advisor(
                    name=name,
                    expertise=adv.get("expertise"),
                    organization=adv.get("organization"),
                    linkedin_url=adv.get("linkedin_url"),
                    source_url=adv.get("source_url"),
                ))
                existing_advisors.add(name.lower().strip())

        # Partnerships — merge
        existing_partnerships = {pa.partner_name.lower().strip() for pa in meta.partnerships}
        for part in p.partnerships:
            name = part.get("partner_name", "")
            if name and name.lower().strip() not in existing_partnerships:
                meta.partnerships.append(Partnership(
                    partner_name=name,
                    type=part.get("type"),
                    description=part.get("description"),
                    date=part.get("date"),
                    source_url=part.get("source_url"),
                ))
                existing_partnerships.add(name.lower().strip())

        # Acquisitions — merge
        existing_acquisitions = {a.acquired_company.lower().strip() for a in meta.acquisitions}
        for acq in p.acquisitions:
            name = acq.get("acquired_company", "")
            if name and name.lower().strip() not in existing_acquisitions:
                meta.acquisitions.append(Acquisition(
                    acquired_company=name,
                    date=acq.get("date"),
                    amount=acq.get("amount"),
                    rationale=acq.get("rationale"),
                    source_url=acq.get("source_url"),
                ))
                existing_acquisitions.add(name.lower().strip())

        # Key customers — merge
        existing_customers = {kc.name.lower().strip() for kc in meta.key_customers}
        for cust in p.key_customers:
            name = cust.get("name", "")
            if name and name.lower().strip() not in existing_customers:
                meta.key_customers.append(KeyCustomer(
                    name=name,
                    description=cust.get("description"),
                    source_url=cust.get("source_url"),
                ))
                existing_customers.add(name.lower().strip())

        # Patents — merge
        existing_patents = {pt.title.lower().strip() for pt in meta.patents}
        for pat in p.patents:
            title = pat.get("title", "")
            if title and title.lower().strip() not in existing_patents:
                meta.patents.append(Patent(
                    title=title,
                    filing_date=pat.get("filing_date"),
                    status=pat.get("status"),
                    domain=pat.get("domain"),
                    patent_number=pat.get("patent_number"),
                    source_url=pat.get("source_url"),
                ))
                existing_patents.add(title.lower().strip())


def _generate_section(section_key: str, profiles_text: str, raw_snippets: str, company_name: str) -> tuple[str, SectionProse]:
    """Generate a single section's prose via LLM. Returns (section_key, SectionProse).

    Creates its own LLM instance per thread to avoid shared-state issues.
    """
    prompt = _SECTION_PROMPTS.get(section_key, "")
    if not prompt:
        return section_key, SectionProse(content="No data available.", confidence=0.0)

    context = f"Company: {company_name}\n\nStructured profile data:\n{profiles_text}"
    if raw_snippets:
        context += f"\n\nRaw source snippets:\n{raw_snippets}"

    llm = get_llm()
    try:
        result = invoke_structured(llm, SectionProse, [
            SystemMessage(content=prompt),
            HumanMessage(content=context)
        ])
        return section_key, result
    except Exception as exc:
        logger.warning("Section %s generation failed: %s", section_key, exc)
        return section_key, SectionProse(content="Data not available due to processing error.", confidence=0.0)


def synthesize(state: dict) -> dict:
    settings = get_settings()
    llm_extraction = get_llm(settings.extraction_model)
    llm_prose = get_llm()  # default = prose/reasoning model
    mode = state["mode"]
    profiles = state["company_profiles"]

    profiles_text = "\n\n".join(
        p.model_dump_json(indent=2) if hasattr(p, "model_dump_json")
        else str(p)
        for p in profiles
    )

    if mode == "explore":
        try:
            report = invoke_structured(llm_extraction, ExploreReport, [
                SystemMessage(content=EXPLORE_SYSTEM),
                HumanMessage(content=f"Query: {state['query']}\n\nCompany profiles:\n{profiles_text}")
            ])
            # Post-process: deduplicate and limit
            seen = set()
            deduped = []
            for c in report.companies:
                key = c.name.strip().lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(c)
            report.companies = deduped[:20]
        except Exception as exc:
            logger.error("Synthesis LLM call failed for query=%s mode=%s: %s — building fallback report from profiles", state['query'], mode, exc)
            # Graceful degradation: build a minimal ExploreReport from raw profiles
            fallback_companies = []
            seen_names = set()
            for p in profiles:
                name = (p.name or "Unknown").strip()
                name_lower = name.lower()
                if name_lower in seen_names or name_lower == "unknown":
                    continue
                seen_names.add(name_lower)
                fallback_companies.append(ExploreCompany(
                    name=name,
                    sub_sector=p.sub_sector or "Unknown",
                    website=p.website,
                    funding_total=p.funding_total,
                    funding_numeric=_parse_funding_numeric(p.funding_total),
                    funding_stage=p.funding_stage,
                    founding_year=p.founding_year,
                    headquarters=p.headquarters,
                    key_investors=p.key_investors or [],
                    description=p.description or p.core_product,
                    confidence=p.funding_confidence if p.funding_confidence else 0.2,
                    source_count=len(p.raw_sources) if p.raw_sources else 0,
                    app_store_rating=p.app_store_rating,
                    app_store_reviews=p.app_store_reviews,
                    app_downloads=p.app_downloads,
                    user_count=p.user_count,
                ))
            fallback_companies = fallback_companies[:20]
            sub_sectors = list({c.sub_sector for c in fallback_companies if c.sub_sector and c.sub_sector != "Unknown"})
            report = ExploreReport(
                query=state["query"],
                sector=state["query"],
                companies=fallback_companies,
                sub_sectors=sub_sectors,
                summary="Report generated from raw profile data (LLM synthesis unavailable).",
                citations=[],
            )
        return {"report": report}

    # --- Deep-dive: parallel synthesis ---
    company_name = state["query"]

    # Build raw snippets from searcher signals so LLMs have original source text.
    raw_signals = state.get("raw_signals", [])

    # Full snippets for metadata extraction (needs all data to extract arrays)
    raw_snippets_full = "\n\n".join(
        f"[{s.source}] {s.url}\n{s.snippet[:600]}"
        for s in raw_signals[:40]
    ) if raw_signals else ""

    # Shorter snippets for per-section prose and investment score (supplementary context)
    raw_snippets_short = "\n\n".join(
        f"[{s.source}] {s.url}\n{s.snippet[:400]}"
        for s in raw_signals[:30]
    ) if raw_signals else ""

    # 1. Extract metadata + structured arrays (one LLM call)
    meta_context = f"Company: {company_name}\n\nStructured profile data:\n{profiles_text}"
    if raw_snippets_full:
        meta_context += f"\n\nRaw source snippets:\n{raw_snippets_full}"
    try:
        meta = invoke_structured(llm_extraction, MetadataAndArrays, [
            SystemMessage(content=_METADATA_PROMPT),
            HumanMessage(content=meta_context)
        ])
    except Exception as exc:
        logger.error("Metadata extraction failed: %s", exc)
        meta = MetadataAndArrays(company_name=company_name)

    meta.funding_rounds = deduplicate_funding_rounds(meta.funding_rounds)

    # Recompute total_funding from actual deduplicated rounds so it matches
    # the funding history table. The LLM's total_funding is often inconsistent
    # with the individual rounds it extracted.
    if meta.funding_rounds:
        from backend.utils import _parse_amount
        computed_total = sum(_parse_amount(r.amount) for r in meta.funding_rounds)
        if computed_total > 0:
            if computed_total >= 1_000_000_000:
                meta.total_funding = f"${computed_total / 1_000_000_000:.1f}B"
            elif computed_total >= 1_000_000:
                meta.total_funding = f"${computed_total / 1_000_000:.1f}M"
            elif computed_total >= 1_000:
                meta.total_funding = f"${computed_total / 1_000:.0f}K"
            else:
                meta.total_funding = f"${computed_total:,.0f}"

    # Assign sequential citation IDs (LLM may return inconsistent IDs)
    for i, cit in enumerate(meta.citations, 1):
        cit.id = i

    # Sort news by date descending (LLM is instructed to, but enforce it)
    if meta.news_items:
        meta.news_items.sort(key=lambda n: n.date or "0000-00-00", reverse=True)

    # 1b. Fill metadata gaps from already-structured profile fields.
    # The LLM re-extraction sometimes misses basic info that the profiler already captured.
    _merge_profiles_into_meta(meta, profiles, company_name)

    # 1c. Filter out people without titles — these are almost always from other
    # companies that appeared in search results (hallucinated affiliations).
    if meta.people_entries:
        before = len(meta.people_entries)
        meta.people_entries = [
            pe for pe in meta.people_entries
            if pe.title and pe.title.strip().lower() not in ("", "none", "n/a", "unknown")
        ]
        removed = before - len(meta.people_entries)
        if removed:
            logger.info("Filtered %d people without valid titles", removed)

    # 2. Generate logo URL from company website
    logo_url = None
    for p in profiles:
        if hasattr(p, 'website') and p.website:
            domain_match = re.match(r'https?://(?:www\.)?([^/]+)', p.website)
            if domain_match:
                domain = domain_match.group(1)
                logo_url = f"https://logo.clearbit.com/{domain}"
            break

    # 3. Compute investment score (single call, can use full context)
    score_context = f"Company: {company_name}\n\nStructured profile data:\n{profiles_text}"
    if raw_snippets_full:
        score_context += f"\n\nRaw source snippets:\n{raw_snippets_full}"
    investment_score = None
    try:
        investment_score = invoke_structured(llm_prose, InvestmentScore, [
            SystemMessage(content=_INVESTMENT_SCORE_PROMPT),
            HumanMessage(content=score_context)
        ])
    except Exception as exc:
        logger.warning("Investment score computation failed: %s", exc)

    # Merge Diffbot employee history from profiles into metadata
    for p in profiles:
        if hasattr(p, 'employee_count_history') and p.employee_count_history:
            for pt in p.employee_count_history:
                try:
                    if isinstance(pt, EmployeeCountPoint):
                        meta.employee_count_history.append(pt)
                    elif isinstance(pt, dict):
                        meta.employee_count_history.append(
                            EmployeeCountPoint(**pt)
                        )
                except Exception as exc:
                    logger.debug("Skipping employee_count_history entry: %s", exc)
        if hasattr(p, 'revenue_estimate') and p.revenue_estimate and not meta.revenue_estimate:
            try:
                if isinstance(p.revenue_estimate, RevenueEstimate):
                    meta.revenue_estimate = p.revenue_estimate
                elif isinstance(p.revenue_estimate, dict):
                    meta.revenue_estimate = RevenueEstimate(**p.revenue_estimate)
            except Exception as exc:
                logger.debug("Skipping revenue_estimate: %s", exc)
        if hasattr(p, 'operating_status') and p.operating_status and not meta.operating_status:
            meta.operating_status = p.operating_status

    # 4. Generate all prose sections in parallel
    section_keys = [
        "overview", "funding", "key_people", "product_technology",
        "market_opportunity", "business_model", "competitive_advantages",
        "traction", "recent_news", "competitors", "red_flags", "risks",
        "governance",
    ]

    section_results: dict[str, SectionProse] = {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_generate_section, key, profiles_text, raw_snippets_short, company_name): key
            for key in section_keys
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                _, prose = future.result()
                section_results[key] = prose
            except Exception as exc:
                logger.warning("Section %s failed: %s", key, exc)
                section_results[key] = SectionProse(content="Data not available due to processing error.", confidence=0.0)

    # 4. Assemble DeepDiveReport
    def _to_section(key: str) -> DeepDiveSection:
        prose = section_results.get(key, SectionProse(content="", confidence=0.0))
        return DeepDiveSection(
            title=key.replace("_", " ").title(),
            confidence=prose.confidence,
            content=prose.content if prose.content else "",
            source_urls=prose.source_urls,
            source_count=prose.source_count,
        )

    def _to_optional_section(key: str):
        prose = section_results.get(key)
        if not prose or not prose.content:
            return None
        cleaned = prose.content.strip().lower()
        if not cleaned or "data not available" in cleaned or "no data available" in cleaned or "processing error" in cleaned:
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
        operating_status=meta.operating_status,
        total_funding=meta.total_funding,
        investment_score=investment_score,
        revenue_estimate=meta.revenue_estimate,
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
        governance=_to_optional_section("governance"),
        board_members=meta.board_members,
        advisors=meta.advisors,
        partnerships=meta.partnerships,
        key_customers=meta.key_customers,
        acquisitions=meta.acquisitions,
        patents=meta.patents,
        employee_count_history=meta.employee_count_history,
        market_opportunity=_to_optional_section("market_opportunity"),
        business_model=_to_optional_section("business_model"),
        competitive_advantages=_to_optional_section("competitive_advantages"),
        traction=_to_optional_section("traction"),
        risks=_to_optional_section("risks"),
        risk_entries=meta.risk_entries,
        citations=meta.citations,
    )

    return {"report": report}
