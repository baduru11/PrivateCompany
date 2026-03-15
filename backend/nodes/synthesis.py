# backend/nodes/synthesis.py
from __future__ import annotations
import logging
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
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


def _normalize_linkedin_url(url: str | None) -> str | None:
    """Ensure LinkedIn URLs include 'www.' — LinkedIn requires it.

    Converts ``https://linkedin.com/...`` to ``https://www.linkedin.com/...``.
    """
    if not url:
        return url
    # Match http(s)://linkedin.com/... (missing www.)
    return re.sub(r"^(https?://)(?:(?!www\.))(linkedin\.com)", r"\1www.\2", url)


EXPLORE_SYSTEM = """You are a competitive intelligence analyst selecting companies from search results.

CRITICAL RULES (MUST follow):
- NEVER attribute a parent company's funding to a product. Claude Code is NOT a $7B+ company —
  it's a product of Anthropic. GitHub Copilot is NOT a $100M+ funded startup — it's a Microsoft product.
  If a product doesn't have its OWN independent funding, leave funding_total EMPTY.
- NEVER list the same company/product twice under different names. If "Cursor" and "Anysphere"
  both appear, keep ONLY "Cursor" (the product name users know).

COMPANY SELECTION RULES:
1. FIRST: List the most important, well-known companies/products in this sector FROM YOUR KNOWLEDGE.
   You already know the major players — list them even if they don't appear in the search results.
   The search results are often incomplete. Your knowledge is the primary source for DISCOVERY.
2. THEN: Check the AVAILABLE COMPANIES list for additional relevant companies you missed.
   Copy names character-for-character when matching.
3. For each company, fill in ALL fields you know (funding, year, HQ, investors, website, description).
   Use both search data AND your knowledge.
4. Target 10-12 companies that CLEARLY belong. Do NOT pad — quality over quantity.
5. Use the PRODUCT name users know, not the corporate/parent name
   (e.g., "Cursor" not "Anysphere", "Devin" not "Cognition Labs", "GitHub Copilot" not "GitHub").

SELECTION CRITERIA — for each company in the list, ask TWO questions:
1. "Is this an actual company/startup (not a category, article, or generic term)?"
2. "Does this company's CORE product directly serve the queried sector?"
Both must be YES. If either is NO or UNCLEAR → exclude it.

RELEVANCE TEST — be strict about relevance:
- A company must BUILD/SELL a product in the queried sector, not just be tangentially related
- A company that merely USES tools in this sector does NOT belong
- Infrastructure providers (cloud, GPU) do NOT belong unless they have a dedicated product in this sector
- General consulting/outsourcing/services companies do NOT belong
- Companies from adjacent but DIFFERENT sectors do NOT belong (e.g., AI writing tools ≠ AI coding assistants)
- Code security/scanning/testing tools are a DIFFERENT sector from coding assistants unless they have AI code generation features

STRICTLY EXCLUDE even if in the list:
- Generic category terms that are NOT real companies (e.g. "AI Code Assistants", "Best Coding Tools 2024", "Top AI Startups")
- Articles, listicles, blogs, review sites, publications, newsletters (e.g. Stackademic, G2, TechCrunch, Gartner)
- VCs, accelerators, investment firms, consulting firms
- AI models, APIs, or open-source projects that are NOT standalone companies/products (e.g., Codex, Qwen3, LLaMA, StarCoder are models, not companies)
- General-purpose AI tools (ChatGPT, Gemini, Claude) unless they have a DEDICATED product in the sector
- Big tech parent companies (Microsoft, Google, Amazon, Apple, Samsung) — but their standalone dedicated products/subsidiaries ARE allowed
- Hobby projects or tools with no evidence of real users, funding, or team
- Duplicates — if two entries refer to the same product/company, keep only ONE — the product name users know.
  Examples: keep "Cursor" not "Anysphere", keep "Devin" not "Cognition", keep "Cody" not "Sourcegraph",
  keep "Windsurf" not "Codeium", keep "Ghostwriter" not "Replit" (unless Replit itself is the product)
- If a name looks like a generic keyword phrase rather than a company name, EXCLUDE it

RANK by: funded companies first (most funding → top), then most traction data, then others.
TARGET: Select 10-12 companies that CLEARLY belong. Fewer is better than padding with unknowns.
Do NOT pad the list to hit a target — only include companies you're confident about.
If you only have 6 good candidates, return 6. Quality always beats quantity.

For each selected company, populate AS MANY FIELDS AS POSSIBLE:
- name: copy EXACTLY from the AVAILABLE COMPANIES list (character-for-character)
- sub_sector: specific niche within the sector — use CONSISTENT singular naming
- description: 2-3 sentences about what the company does
- funding_total: total funding raised (e.g. "$252M", "$3.4B") — use data from sources OR your knowledge.
  If a product is part of a larger company (e.g., Claude Code → Anthropic, GitHub Copilot → Microsoft),
  do NOT list the parent's total funding as the product's funding. Leave funding_total empty if the
  product doesn't have independent funding.
- funding_stage: latest known stage (e.g. "Series D", "Series B")
- founding_year: year founded (integer, e.g. 2022)
- headquarters: city and state/country (e.g. "San Francisco, CA")
- key_investors: list of major investors (e.g. ["Sequoia Capital", "a16z"])
- website: company website URL if known
- user_count: number of users/developers (e.g. "1.3M+ paid subscribers", "20M+ users", "500K+ developers")
  This is CRITICAL — fill in user/developer counts from your knowledge for EVERY company where known.

IMPORTANT: Fill in ALL fields from your knowledge — especially user_count, funding, founding year,
headquarters, and key investors. It's better to provide known data than leave fields empty.
The critic node will verify claims later.

SUB-SECTOR RULES:
- Use singular form consistently (e.g. "AI Coding Assistant" not "AI Coding Assistants")
- Aim for 3-6 distinct sub-sectors — group similar companies together

Also provide:
- sector: short name for the overall sector
- sub_sectors: list of sub-sector categories you used (singular form, 3-6 categories)
- summary: 2-3 sentence landscape overview with total market funding mentioned if known"""


def _parse_funding_numeric(funding_str: str | None) -> float:
    """Extract a numeric funding value (in actual USD) from a string like '$720M'.

    Returns the value in actual dollars so the frontend can format it directly
    (e.g. '$720M' → 720_000_000, '$1.5B' → 1_500_000_000).
    """
    if not funding_str:
        return 0.0
    m = re.search(r'\$\s*([\d.]+)\s*([BMK])?', funding_str, re.IGNORECASE)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = (m.group(2) or '').upper()
    if unit == 'B':
        val *= 1_000_000_000
    elif unit == 'M':
        val *= 1_000_000
    elif unit == 'K':
        val *= 1_000
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
- Use the provided data as your primary source, but supplement with well-known facts from your
  knowledge when the data is incomplete. The critic node will verify claims later."""

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
- linkedin_url: string or null — ONLY include if found in the provided search data. Do NOT guess LinkedIn URLs.
- crunchbase_url: string or null — ONLY include if found in the provided search data. Do NOT guess.
- operating_status: "Active" | "Acquired" | "Closed" | "IPO" (default "Active" if unclear)
- total_funding: string (e.g. "$1.2B", "$50M") — total capital raised across all rounds

STRUCTURED ARRAYS (extract directly from profile data AND raw source snippets):
- funding_rounds: [{date, stage, amount, investors: [string], lead_investor: string or null, pre_money_valuation: string or null, post_money_valuation: string or null, source_url}]
  Extract EVERY distinct funding round mentioned. Include Seed, Series A, B, C, D, etc.
  Each round with a DIFFERENT stage name (Seed, Series A, Series B, etc.) is a SEPARATE round — include all of them.
  Only deduplicate when the SAME round appears multiple times with slightly different amounts.
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

CRITICAL: Build the MOST COMPLETE picture possible. Use BOTH the provided data AND your knowledge.

The search data is often incomplete. You MUST supplement with facts from your training data:
- funding_rounds: Include ALL known rounds (Seed, Series A, B, C, D, etc.) — not just the latest
- people_entries: Include ALL known executives, not just those in search results
- competitor_entries: Include ALL major competitors (aim for 5-8), with their funding if known
- news_items: Include 5+ recent news items from your knowledge if search results are sparse
- board_members: Include investor board seats if known (e.g., a16z partner on the board)
- partnerships: Include known integrations, strategic partnerships
- citations: Include source URLs from the search results for every factual claim

It's FAR better to include well-known facts than leave arrays empty.
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


_SKIP_DOMAINS = (
    "google.", "bing.", "youtube.", "twitter.", "linkedin.", "crunchbase.",
    "techcrunch.", "forbes.", "bloomberg.", "reddit.", "wikipedia.",
    "apps.apple.com", "sensortower.", "appannie.", "similarweb.",
    "g2.com", "capterra.", "trustpilot.", "appfigures.",
    "medium.com", "gartner.", "startus-insights.", "ventureradar.",
    "datacamp.", "brightseotools.", "strategydriven.", "spacelift.",
    "ycombinator.", "producthunt.", "pitchbook.", "tracxn.",
    "stackshare.", "alternativeto.", "slant.co", "saasworthy.",
    "sourceforge.", "stackademic.", "towardsdatascience.",
    "hackernoon.", "dev.to", "substack.", "beehiiv.",
    "marketplace.visualstudio.", "chrome.google.",
    # VC / investor sites
    "sequoiacap.", "a16z.", "accel.", "indexventures.", "andreessen",
    "kpcb.", "greylock.", "benchmark.", "lightspeed.", "thrive.",
    # Article / review aggregators
    "aitoolsbusiness.", "aitools.", "futurepedia.", "theresanaiforthat.",
    "toolify.", "topai.", "aixploria.", "aicollection.",
    "clickup.", "zapier.", "notion.", "hubspot.",
)


def _is_non_company(name: str, website: str | None) -> bool:
    """Check if an entry is likely NOT a real company (generic term, article site, etc.)."""
    name_lower = name.lower().strip()

    # Generic terms that are not companies
    generic_terms = {
        "ai agents", "ai coding assistants", "ai code assistants",
        "ai coding assistant", "ai code assistant",
        "ai tools", "best ai tools", "top ai startups", "coding tools",
        "ai solutions", "ai code", "code generation", "ai development",
        "ai startups", "ai companies", "ai software", "ai platform",
        "ai assistant", "ai assistants", "code assistant", "code assistants",
        "copilot",  # generic term (GitHub Copilot should be listed as "GitHub Copilot")
    }
    if name_lower in generic_terms:
        return True

    # Names that look like article titles (contain too many words)
    if len(name_lower.split()) > 4:
        return True

    # Names that are just generic phrases starting with common prefixes
    generic_prefixes = ("best ", "top ", "list of ", "how to ", "what is ")
    if any(name_lower.startswith(p) for p in generic_prefixes):
        return True

    # Website is a known non-company domain
    if website:
        for skip in _SKIP_DOMAINS:
            if skip in website.lower():
                return True

    return False


def _extract_from_snippets(company: ExploreCompany, signals: list) -> ExploreCompany:
    """Extract data from raw search snippets that the profiler may have missed."""
    company_name_lower = company.name.lower().replace(" ", "")

    # First pass: find the company's own website (prefer URLs whose domain contains the company name)
    candidate_websites: list[str] = []
    for sig in signals:
        url = sig.url or ""
        if not url:
            continue
        parts = url.split("/")
        domain = parts[2] if len(parts) > 2 else ""
        if not domain or any(sk in domain for sk in _SKIP_DOMAINS):
            continue
        # Check if the domain looks like it belongs to this company
        domain_clean = domain.lower().replace("www.", "").replace("-", "").replace(".", "")
        # Strong match: company name (stripped) appears in domain
        name_parts = company_name_lower.replace(".", "").replace(" ", "")
        # Try several matching strategies
        domain_base = domain_clean.split("com")[0].split("io")[0].split("ai")[0].split("app")[0].split("co")[0]
        if (name_parts in domain_clean
            or domain_base and len(domain_base) > 2 and domain_base in name_parts
            or name_parts and len(name_parts) > 2 and name_parts in domain_base):
            if not company.website:
                company.website = f"https://{domain}"
            break
        candidate_websites.append(f"https://{domain}")

    # Also try to extract website URLs mentioned in snippet text
    if not company.website:
        for sig in signals:
            text = sig.snippet or ""
            url_m = re.search(
                r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|io|app|co|org|net|ai|cc|dev|sh)(?:\.[a-z]{2})?)',
                text,
            )
            if url_m:
                found_domain = url_m.group(1).lower()
                if not any(sk in found_domain for sk in _SKIP_DOMAINS):
                    domain_clean = found_domain.replace(".", "").replace("-", "")
                    name_parts = company_name_lower.replace(".", "").replace(" ", "")
                    if name_parts in domain_clean or domain_clean.split("com")[0] in name_parts:
                        company.website = f"https://{found_domain}"
                        break

    # No fallback: if we couldn't match the company name to a domain,
    # leave website empty. The verification step's LLM can fill it in.

    for sig in signals:
        text = sig.snippet or ""

        # Extract ratings from snippet text
        if company.app_store_rating is None:
            m = re.search(r'(\d\.\d)\s*(?:out of 5|/5|stars?|★|rating)', text, re.IGNORECASE)
            if m:
                try:
                    company.app_store_rating = float(m.group(1))
                except ValueError:
                    pass

        # Extract download counts — only if company name is mentioned in context
        if not company.app_downloads and company.name.lower() in text.lower():
            m = re.search(r'(\d[\d,.]*[MKB]?\+?)\s*(?:downloads?|installs?)', text, re.IGNORECASE)
            if m:
                company.app_downloads = m.group(1)

        # Extract user counts — ONLY if the company name appears near the number
        # to avoid picking up random numbers from listicle articles
        if not company.user_count:
            # Pattern: "CompanyName ... X users" or "X users ... CompanyName" within ~100 chars
            name_lower = company.name.lower()
            text_lower = text.lower()
            if name_lower in text_lower:
                # Find user count mentions with larger numbers (>1000 to skip noise)
                for um in re.finditer(r'(\d[\d,.]*[MKB]?\+?)\s*(?:users?|customers?|students?|learners?|subscribers?|developers?|MAU|DAU)', text, re.IGNORECASE):
                    count_str = um.group(1).replace(",", "")
                    # Check if it's a meaningful count (not tiny noise like "5 users")
                    try:
                        raw_num = float(re.sub(r'[MKB+]', '', count_str))
                        has_suffix = bool(re.search(r'[MKB]', um.group(1), re.IGNORECASE))
                        if raw_num < 100 and not has_suffix:
                            continue  # Skip small numbers like "5 users"
                    except ValueError:
                        pass
                    # Check proximity: company name within 150 chars of the number
                    name_pos = text_lower.find(name_lower)
                    num_pos = um.start()
                    if abs(name_pos - num_pos) < 150:
                        company.user_count = um.group(1) + " " + um.group(0).split()[-1]
                        break

        # Extract review counts — only if company name is mentioned in context
        if not company.app_store_reviews and company.name.lower() in text.lower():
            m = re.search(r'(\d[\d,.]*[KM]?\+?)\s*(?:reviews?|ratings?)', text, re.IGNORECASE)
            if m:
                company.app_store_reviews = m.group(1) + " reviews"

        # Extract FUNDING amounts (NOT valuations) — only from snippets mentioning this company
        if not company.funding_total and company.name.lower() in text.lower():
            funding_patterns = [
                r'(?:total\s+)?(?:funding|raised|capital)(?:\s+(?:of|to\s+date|total))?\s*[:=]?\s*\$\s*([\d,.]+)\s*([BMK])',
                r'(?:raised|secured|closed|received)\s+\$\s*([\d,.]+)\s*([BMK])',
                r'\$\s*([\d,.]+)\s*([BMK])\s*(?:in\s+)?(?:funding|raised|investment|round|series|seed)',
            ]
            best_amount = 0.0
            best_str = ""
            for pattern in funding_patterns:
                for fm in re.finditer(pattern, text, re.IGNORECASE):
                    # Skip if this is actually a valuation
                    start = max(0, fm.start() - 30)
                    context = text[start:fm.end() + 10].lower()
                    if 'valuat' in context or 'valued at' in context or 'worth' in context:
                        continue
                    amount = fm.group(1).replace(",", "")
                    unit_raw = fm.group(2).strip().upper()
                    if unit_raw.startswith("BILLION"):
                        unit = "B"
                    elif unit_raw.startswith("MILLION"):
                        unit = "M"
                    else:
                        unit = unit_raw[0]
                    candidate = f"${amount}{unit}"
                    candidate_val = _parse_funding_numeric(candidate)
                    if candidate_val > best_amount:
                        best_amount = candidate_val
                        best_str = candidate
            if best_str:
                company.funding_total = best_str
                company.funding_numeric = best_amount

        # Extract funding stage — only from snippets mentioning this company
        if not company.funding_stage and company.name.lower() in text.lower():
            m = re.search(r'((?:Pre-)?Seed|Series\s+[A-Z]\+?|Angel)\s*(?:round|funding|stage)?', text, re.IGNORECASE)
            if m:
                company.funding_stage = m.group(1).strip()

        # Extract founding year — only from snippets mentioning this company
        if not company.founding_year and company.name.lower() in text.lower():
            m = re.search(r'(?:founded|established|launched|started)\s+(?:in\s+)?(\d{4})', text, re.IGNORECASE)
            if m:
                yr = int(m.group(1))
                if 1990 <= yr <= 2026:
                    company.founding_year = yr

        # Extract headquarters — only from snippets mentioning this company
        if not company.headquarters and company.name.lower() in text.lower():
            m = re.search(r'(?:based in|headquartered in|headquarters?\s+(?:in|:))\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,?\s+(?:the|a|and|with|is|has|was|that|which)|\s*$)', text)
            if m:
                hq = m.group(1).strip().rstrip(",")
                if len(hq) < 60:
                    company.headquarters = hq

    # Extend source URLs from signals (don't overwrite existing)
    existing_urls = set(company.source_urls)
    for sig in signals:
        if sig.url and sig.url not in existing_urls:
            company.source_urls.append(sig.url)
            existing_urls.add(sig.url)
    company.source_urls = company.source_urls[:10]
    company.source_count = len(company.source_urls)

    return company


def _enrich_from_profile(company: ExploreCompany, profile: CompanyProfile) -> ExploreCompany:
    """Enrich an LLM-selected ExploreCompany with data from its CompanyProfile."""
    company.website = company.website or profile.website
    company.funding_total = company.funding_total or profile.funding_total
    company.funding_numeric = _parse_funding_numeric(company.funding_total or profile.funding_total)
    company.funding_stage = company.funding_stage or profile.funding_stage
    company.founding_year = company.founding_year or profile.founding_year
    company.headquarters = company.headquarters or profile.headquarters
    company.key_investors = company.key_investors or profile.key_investors or []
    company.description = company.description or profile.description or profile.core_product
    company.source_count = max(company.source_count, len(profile.raw_sources) if profile.raw_sources else 0)
    company.source_urls = company.source_urls or profile.raw_sources or []
    company.app_store_rating = company.app_store_rating or profile.app_store_rating
    company.app_store_reviews = company.app_store_reviews or profile.app_store_reviews
    company.app_downloads = company.app_downloads or profile.app_downloads
    company.user_count = company.user_count or profile.user_count
    return company


def _compute_confidence(c: ExploreCompany) -> float:
    """Compute confidence from data completeness and quality.

    Tiered scoring: a company with solid core data (name, description, funding)
    starts at a high baseline. Additional fields boost further.
    """
    # Baseline: every company with a name and description starts at 0.30
    score = 0.30 if (c.description and len(c.description) > 20) else 0.15

    # Tier 1 — core data (each adds significant confidence)
    if c.funding_total:
        score += 0.20
    if c.website:
        score += 0.10
    if c.funding_stage:
        score += 0.08

    # Tier 2 — important context
    if c.founding_year:
        score += 0.08
    if c.headquarters:
        score += 0.05
    if c.key_investors:
        score += 0.05

    # Tier 3 — traction & sources (bonus)
    if c.app_store_rating is not None or c.app_downloads or c.user_count:
        score += 0.07
    if c.source_count >= 2:
        score += 0.04
    if c.source_count >= 4:
        score += 0.03

    return round(min(score, 1.0), 2)


def _quick_web_search(query: str, num: int = 5) -> list[dict]:
    """Fast web search via Serper for secondary enrichment."""
    settings = get_settings()
    if not settings.serper_api_key:
        return []
    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.serper_api_key},
            json={"q": query, "num": num},
            timeout=8,
        )
        resp.raise_for_status()
        return [
            {"url": r.get("link", ""), "snippet": f"{r.get('title', '')}. {r.get('snippet', '')}"}
            for r in resp.json().get("organic", [])[:num]
        ]
    except Exception as exc:
        logger.debug("Quick search failed for '%s': %s", query, exc)
        return []


def _verify_and_supplement_companies(companies: list[ExploreCompany], query: str, llm) -> list[ExploreCompany]:
    """Use multiple web searches + LLM to build a comprehensive, relevant company list.

    This is the PRIMARY quality gate — it searches for curated company lists
    in this sector, then uses the LLM to merge with existing data, remove
    irrelevant entries, add missing major players, and deduplicate.
    """
    # Step 1: Multiple web searches — keep the FULL sector phrase to avoid noise
    # Include list queries, competitor queries, and sub-niche queries
    top_company = companies[0].name if companies else ""
    search_queries = [
        f"top {query} companies startups 2025 2026",
        f"best {query} tools comparison ranked",
        f"{query} competitors alternatives list",
    ]
    # Add competitor query using a well-known company in the list
    if top_company and len(top_company) > 2:
        search_queries.append(f"{top_company} competitors alternatives vs 2025")
    all_snippets = []
    for sq in search_queries:
        results = _quick_web_search(sq, num=6)
        for r in results:
            snippet = r.get("snippet", "")
            if snippet:
                all_snippets.append(snippet)

    if not all_snippets:
        return companies

    verification_text = "\n".join(f"- {s}" for s in all_snippets)
    existing_names = [c.name for c in companies]

    # Step 2: LLM evaluates everything — adds missing, removes irrelevant, deduplicates
    try:
        class CompanyVerification(BaseModel):
            missing_companies: list[ExploreCompany] = Field(
                default_factory=list,
                description="Companies to ADD — only ones you're HIGHLY confident belong"
            )
            irrelevant_names: list[str] = Field(
                default_factory=list,
                description="Names of existing companies to REMOVE"
            )
            duplicate_pairs: list[str] = Field(
                default_factory=list,
                description="Names to remove because they duplicate another entry "
                            "(e.g., remove 'Anysphere' because 'Cursor' is already listed)"
            )

        result = invoke_structured(llm, CompanyVerification, [
            SystemMessage(content=(
                f"You are building the definitive list of companies/products in a SPECIFIC sector.\n\n"
                f"You have an EXISTING list and FRESH web search results about '{query}'.\n\n"
                f"THREE tasks:\n\n"
                f"1. MISSING (up to 8): Add companies/products that CLEARLY belong in '{query}'. "
                f"ONLY add if you can describe what their product does in this sector. "
                f"Think about sub-niches: AI code editors, AI code completion, AI code review, "
                f"AI app builders, AI coding agents, AI test generation. Cover ALL sub-niches.\n"
                f"Do NOT add:\n"
                f"   - AI models or open-source projects (Codex, Qwen, LLaMA, StarCoder = models, not companies)\n"
                f"   - Companies from OTHER AI sectors (legal AI, security AI, enterprise search, AGI research)\n"
                f"   - CI/CD, DevOps, or infrastructure platforms unless they have a dedicated AI coding feature\n"
                f"   - Companies you're unsure about — when in doubt, leave them out\n"
                f"Use the PRODUCT name users know, not the parent company. "
                f"Only list funding the product/startup INDEPENDENTLY raised — never parent company funding. "
                f"Fill in: name, sub_sector, description, funding_total, funding_stage, founding_year, "
                f"headquarters, key_investors, website, user_count (e.g. '1M+ developers').\n\n"
                f"2. IRRELEVANT: Remove companies whose CORE product is NOT in '{query}':\n"
                f"   - Wrong sector entirely (legal AI, security AI, enterprise search, etc.)\n"
                f"   - Code security/scanning/testing tools (Snyk, Veracode) ≠ coding assistants\n"
                f"   - CI/CD platforms (Harness, CircleCI) ≠ coding assistants\n"
                f"   - Generic AI platforms or AI research labs without a shipped product in this sector\n"
                f"   - Parent company when the specific product is a better entry\n"
                f"   Be aggressive — remove anything that doesn't CLEARLY belong.\n\n"
                f"3. DUPLICATES: Remove the less-known name when two entries are the same:\n"
                f"   - Parent + product (Anysphere → keep Cursor)\n"
                f"   - Rebrand (Codeium → keep Windsurf)\n"
                f"   - Same product, different names"
            )),
            HumanMessage(content=(
                f"Sector: {query}\n\n"
                f"EXISTING companies:\n{chr(10).join(f'  - {n}' for n in existing_names)}\n\n"
                f"FRESH WEB SEARCH RESULTS:\n{verification_text}\n\n"
                f"Build the best possible list for '{query}'. Quality over quantity."
            ))
        ])

        # Remove irrelevant + duplicates
        to_remove = set()
        if result.irrelevant_names:
            to_remove.update(n.lower().strip() for n in result.irrelevant_names)
        if result.duplicate_pairs:
            to_remove.update(n.lower().strip() for n in result.duplicate_pairs)
        if to_remove:
            before = len(companies)
            companies = [c for c in companies if c.name.lower().strip() not in to_remove]
            removed = before - len(companies)
            if removed:
                logger.info("Removed %d companies (irrelevant/duplicate): %s", removed, to_remove)
            existing_names = [c.name for c in companies]

        # Add missing companies — only if the LLM provided a description
        # (no description = the LLM isn't confident enough to explain what this company does)
        if result.missing_companies:
            added = 0
            for c in result.missing_companies:
                if added >= 8:
                    break
                # Skip if no description — LLM must be able to explain relevance
                if not c.description or len(c.description.strip()) < 20:
                    logger.debug("Skipping verification add %s — no description", c.name)
                    continue
                # Skip if already exists (fuzzy match)
                c_lower = c.name.lower().strip()
                if any(c_lower == n.lower().strip() or c_lower in n.lower() or n.lower().strip() in c_lower
                       for n in existing_names if len(n) > 3):
                    continue
                _normalize_funding_str(c)
                c.confidence = _compute_confidence(c)
                companies.append(c)
                existing_names.append(c.name)
                added += 1
                logger.info("Added missing company: %s (funding=%s)", c.name, c.funding_total)

    except Exception as exc:
        logger.warning("Company verification failed: %s", exc)

    return companies


def _name_in_text(name: str, text: str) -> bool:
    """Check if a company name (or any significant word from it) appears in text.

    Lenient matching for names like 'Bolt.new', 'v0 by Vercel', etc.
    """
    text_lower = text.lower()
    name_lower = name.lower().strip()
    if name_lower in text_lower:
        return True
    # Check if any significant word (>2 chars) from the name appears
    words = [w.replace(".", "") for w in name_lower.split() if len(w.replace(".", "")) > 2]
    # Exclude generic words that would cause false matches
    skip = {"the", "and", "for", "inc", "ltd", "llc", "corp", "company", "new"}
    words = [w for w in words if w not in skip]
    return any(w in text_lower for w in words)


def _secondary_enrich(company: ExploreCompany) -> ExploreCompany:
    """Targeted search to fill missing funding/website/founding/traction data for a single company."""
    needs_data = (not company.funding_total or not company.website
                  or not company.founding_year or not company.user_count)
    if not needs_data:
        return company

    results = _quick_web_search(f"{company.name} company funding raised founded users crunchbase", num=5)
    if not results:
        return company

    for r in results:
        text = r.get("snippet", "")
        url = r.get("url", "")

        # Extract website from search result URLs
        if not company.website and url:
            parts = url.split("/")
            domain = parts[2] if len(parts) > 2 else ""
            if domain and not any(sk in domain for sk in _SKIP_DOMAINS):
                domain_clean = domain.lower().replace("www.", "").replace("-", "").replace(".", "")
                name_parts = company.name.lower().replace(".", "").replace(" ", "")
                if name_parts in domain_clean or (len(name_parts) > 3 and domain_clean.startswith(name_parts[:4])):
                    company.website = f"https://{domain}"

        # Extract FUNDING from search snippets (NOT valuations)
        # Only from snippets that mention this company to avoid cross-contamination
        if not company.funding_total and _name_in_text(company.name, text):
            # Patterns that specifically match FUNDING (not valuation)
            funding_patterns = [
                r'(?:total\s+)?(?:funding|raised|capital)(?:\s+(?:of|to\s+date|total))?\s*[:=]?\s*\$\s*([\d,.]+)\s*([BMK])',
                r'(?:raised|secured|closed|received)\s+\$\s*([\d,.]+)\s*([BMK])',
                r'\$\s*([\d,.]+)\s*([BMK])\s*(?:in\s+)?(?:funding|raised|investment|round|series|seed)',
            ]
            # Pattern to DETECT valuations (so we can skip them)
            valuation_pattern = r'(?:valued?\s+at|valuation\s+(?:of)?|worth)\s+\$\s*([\d,.]+)\s*([BMK])'

            best_amount = 0.0
            best_str = ""
            for pattern in funding_patterns:
                for fm in re.finditer(pattern, text, re.IGNORECASE):
                    # Check if this match is actually a valuation in context
                    start = max(0, fm.start() - 30)
                    context = text[start:fm.end() + 10].lower()
                    if 'valuat' in context or 'valued at' in context or 'worth' in context:
                        continue  # Skip valuations
                    amount = fm.group(1).replace(",", "")
                    unit_raw = fm.group(2).strip().upper()
                    if unit_raw.startswith("BILLION"):
                        unit = "B"
                    elif unit_raw.startswith("MILLION"):
                        unit = "M"
                    else:
                        unit = unit_raw[0]
                    candidate = f"${amount}{unit}"
                    candidate_val = _parse_funding_numeric(candidate)
                    if candidate_val > best_amount:
                        best_amount = candidate_val
                        best_str = candidate
            if best_str:
                if best_amount > (company.funding_numeric or 0):
                    company.funding_total = best_str
                    company.funding_numeric = best_amount

        # Extract funding stage
        if not company.funding_stage:
            m = re.search(r'((?:Pre-)?Seed|Series\s+[A-Z]\+?|Angel)\s*(?:round|funding|stage)?', text, re.IGNORECASE)
            if m:
                company.funding_stage = m.group(1).strip()

        # Extract founding year
        if not company.founding_year:
            m = re.search(r'(?:founded|established|launched|started)\s+(?:in\s+)?(\d{4})', text, re.IGNORECASE)
            if m:
                yr = int(m.group(1))
                if 1990 <= yr <= 2026:
                    company.founding_year = yr

        # Extract user/developer count — only from snippets mentioning this company
        if not company.user_count and _name_in_text(company.name, text):
            user_patterns = [
                r'(\d[\d,.]*[MKB]?\+?)\s*(?:users?|developers?|customers?|subscribers?|MAU)',
                r'(?:over|more than|~)\s*(\d[\d,.]*[MKB]?\+?)\s*(?:users?|developers?|customers?)',
            ]
            for pattern in user_patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    count = m.group(1)
                    # Skip tiny numbers
                    try:
                        raw = float(re.sub(r'[MKB+,]', '', count))
                        if raw < 100 and not re.search(r'[MKB]', count, re.IGNORECASE):
                            continue
                    except ValueError:
                        pass
                    company.user_count = count + " users"
                    break

    return company


def _secondary_enrich_batch(companies: list[ExploreCompany]) -> list[ExploreCompany]:
    """Run secondary enrichment for companies missing key data, in parallel."""
    needs_enrichment = [c for c in companies
                        if not c.funding_total or not c.website
                        or not c.founding_year or not c.user_count]
    if not needs_enrichment:
        return companies

    logger.info("Secondary enrichment: %d/%d companies need data", len(needs_enrichment), len(companies))

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_secondary_enrich, c): c for c in needs_enrichment[:12]}
        for future in as_completed(futures, timeout=30):
            try:
                future.result(timeout=10)
            except Exception as exc:
                logger.debug("Secondary enrichment failed: %s", exc)

    # Recompute confidence after enrichment
    for c in companies:
        c.confidence = _compute_confidence(c)

    return companies


def _merge_company_data(target: ExploreCompany, source: ExploreCompany) -> None:
    """Copy missing fields from source into target (target takes precedence)."""
    if not target.funding_total and source.funding_total:
        target.funding_total = source.funding_total
        target.funding_numeric = source.funding_numeric
    if not target.funding_stage and source.funding_stage:
        target.funding_stage = source.funding_stage
    if not target.website and source.website:
        target.website = source.website
    if not target.founding_year and source.founding_year:
        target.founding_year = source.founding_year
    if not target.headquarters and source.headquarters:
        target.headquarters = source.headquarters
    if not target.key_investors and source.key_investors:
        target.key_investors = source.key_investors
    if not target.description and source.description:
        target.description = source.description
    if not target.user_count and source.user_count:
        target.user_count = source.user_count
    if not target.app_store_rating and source.app_store_rating:
        target.app_store_rating = source.app_store_rating
    if not target.app_downloads and source.app_downloads:
        target.app_downloads = source.app_downloads
    if not target.app_store_reviews and source.app_store_reviews:
        target.app_store_reviews = source.app_store_reviews
    target.source_count = max(target.source_count or 0, source.source_count or 0)
    existing = set(target.source_urls)
    for url in source.source_urls:
        if url not in existing:
            target.source_urls.append(url)
            existing.add(url)


def _extract_domain(url: str | None) -> str:
    """Extract base domain from URL for comparison."""
    if not url:
        return ""
    m = re.match(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1).lower() if m else ""


def _deduplicate_companies(companies: list[ExploreCompany]) -> list[ExploreCompany]:
    """Remove duplicate companies by name containment OR matching website domain."""
    if len(companies) < 2:
        return companies

    to_remove: set[int] = set()
    for i, a in enumerate(companies):
        if i in to_remove:
            continue
        a_lower = a.name.lower().strip()
        a_domain = _extract_domain(a.website)
        for j in range(i + 1, len(companies)):
            if j in to_remove:
                continue
            b = companies[j]
            b_lower = b.name.lower().strip()

            # Both names must be meaningful length
            if len(a_lower) < 4 or len(b_lower) < 4:
                continue

            # Check: name containment, same website domain, or description mentions the other
            is_name_dup = a_lower in b_lower or b_lower in a_lower
            b_domain = _extract_domain(b.website)
            is_domain_dup = a_domain and b_domain and a_domain == b_domain
            # If one company's description mentions the other's name, they're likely the same
            a_desc = (a.description or "").lower()
            b_desc = (b.description or "").lower()
            is_desc_dup = (a_lower in b_desc) or (b_lower in a_desc)
            if not is_name_dup and not is_domain_dup and not is_desc_dup:
                continue

            # Keep the one with more data, merge from the other
            a_score = (a.confidence or 0) + (0.5 if a.funding_total else 0)
            b_score = (b.confidence or 0) + (0.5 if b.funding_total else 0)

            if a_score >= b_score:
                _merge_company_data(a, b)
                to_remove.add(j)
                logger.info("Dedup: merged '%s' into '%s'", b.name, a.name)
            else:
                _merge_company_data(b, a)
                to_remove.add(i)
                logger.info("Dedup: merged '%s' into '%s'", a.name, b.name)
                break  # a is removed, stop checking

    return [c for i, c in enumerate(companies) if i not in to_remove]


def _normalize_funding_str(company: ExploreCompany) -> None:
    """Normalize funding_total to compact format: '$1 billion' → '$1B', '$100 million' → '$100M'."""
    ft = company.funding_total
    if not ft:
        return
    ft_lower = ft.lower().strip()
    m = re.search(r'\$\s*([\d,.]+)\s*(billion|million|thousand)', ft_lower)
    if m:
        amount = m.group(1)
        unit_map = {"billion": "B", "million": "M", "thousand": "K"}
        unit = unit_map.get(m.group(2), "")
        company.funding_total = f"${amount}{unit}"
    # Also ensure funding_numeric is set
    if company.funding_total and not company.funding_numeric:
        company.funding_numeric = _parse_funding_numeric(company.funding_total)


def _normalize_sub_sectors(companies: list[ExploreCompany]) -> list[ExploreCompany]:
    """Normalize sub-sector names: deduplicate singular/plural forms and near-duplicates."""
    # Count occurrences of each sub-sector (case-insensitive)
    counts: dict[str, int] = {}
    canonical: dict[str, str] = {}
    for c in companies:
        s = (c.sub_sector or "Unknown").strip()
        key = s.lower().rstrip("s")  # strip trailing 's' for singular/plural matching
        if key not in counts:
            counts[key] = 0
            canonical[key] = s
        counts[key] += 1
        # Prefer the shorter (singular) form, or the one that appears first
        if len(s) < len(canonical[key]):
            canonical[key] = s

    # Apply normalized names
    for c in companies:
        s = (c.sub_sector or "Unknown").strip()
        key = s.lower().rstrip("s")
        c.sub_sector = canonical.get(key, s)

    return companies


def _synthesize_explore(state: dict, profiles: list, profiles_text: str, llm) -> ExploreReport:
    """Two-step explore synthesis: LLM picks relevant companies, code enriches them."""
    query = state["query"]
    raw_signals = state.get("raw_signals", [])

    # Build a name→profile lookup for enrichment (keyed by extracted company name)
    profile_map: dict[str, CompanyProfile] = {}
    for p in profiles:
        key = (p.name or "").strip().lower()
        if key and key != "unknown":
            # Keep the profile with the most data
            if key not in profile_map or len(p.raw_sources) > len(profile_map[key].raw_sources):
                profile_map[key] = p

    # Build name→raw snippets lookup so we can re-extract data missed by the profiler
    signal_map: dict[str, list] = {}
    for s in raw_signals:
        key = s.company_name.strip().lower()
        signal_map.setdefault(key, []).append(s)

    # Build a rich summary of each profile — include ALL available data so the LLM
    # can make informed relevance decisions
    profile_summaries = []
    for key, p in profile_map.items():
        parts = [f"Company: {p.name}"]
        if p.description:
            parts.append(f"Description: {p.description[:300]}")
        if p.core_product:
            parts.append(f"Product: {p.core_product[:200]}")
        if p.core_technology:
            parts.append(f"Technology: {p.core_technology[:150]}")
        if p.sub_sector:
            parts.append(f"Sub-sector: {p.sub_sector}")
        if p.website:
            parts.append(f"Website: {p.website}")
        if p.funding_total:
            parts.append(f"Funding: {p.funding_total}")
        if p.funding_stage:
            parts.append(f"Stage: {p.funding_stage}")
        if p.key_investors:
            parts.append(f"Investors: {', '.join(p.key_investors[:5])}")
        if p.founding_year:
            yr = str(p.founding_year)
            if p.founding_month:
                yr = f"{p.founding_month} {yr}"
            parts.append(f"Founded: {yr}")
        if p.headquarters:
            parts.append(f"HQ: {p.headquarters}")
        if p.headcount_estimate:
            parts.append(f"Team: {p.headcount_estimate}")
        if p.business_model:
            parts.append(f"Business model: {p.business_model[:100]}")
        if p.revenue_indicators:
            parts.append(f"Revenue: {p.revenue_indicators[:100]}")
        if p.app_store_rating is not None:
            rating_str = f"{p.app_store_rating}★"
            if p.app_store_reviews:
                rating_str += f" ({p.app_store_reviews})"
            parts.append(f"Rating: {rating_str}")
        if p.app_downloads:
            parts.append(f"Downloads: {p.app_downloads}")
        if p.user_count:
            parts.append(f"Users: {p.user_count}")
        if p.customer_signals:
            parts.append(f"Customers: {p.customer_signals[:150]}")
        if p.key_people:
            people = [f"{kp.get('name', '?')} ({kp.get('title', '?')})" for kp in p.key_people[:3]]
            parts.append(f"Key people: {', '.join(people)}")
        if p.recent_news:
            news = [n.get("title", "") for n in p.recent_news[:2] if n.get("title")]
            if news:
                parts.append(f"Recent news: {'; '.join(news)}")
        if p.operating_status and p.operating_status != "Active":
            parts.append(f"Status: {p.operating_status}")
        parts.append(f"Sources: {len(p.raw_sources)} source(s)")
        profile_summaries.append("\n".join(parts))

    concise_profiles = "\n\n---\n\n".join(profile_summaries)

    # Build explicit list of available company names to prevent hallucination
    available_names = sorted({p.name for p in profiles if p.name and p.name.strip().lower() != "unknown"})
    names_list = "\n".join(f"  - {name}" for name in available_names)

    # Build raw snippet context — these comparison articles contain the real company lists
    raw_snippet_text = ""
    if raw_signals:
        seen_snippets = set()
        snippets = []
        for s in raw_signals[:30]:
            snip = (s.snippet or "")[:400].strip()
            if snip and snip not in seen_snippets:
                seen_snippets.add(snip)
                snippets.append(snip)
        raw_snippet_text = "\n\n".join(snippets[:15])

    try:
        # Step 1: LLM reads raw search snippets + profiled data to select companies.
        # The raw snippets from comparison articles are the BEST source for discovering
        # all companies in a sector ("Top 17 AI Coding Assistants: Copilot, Cursor, ...")
        report = invoke_structured(llm, ExploreReport, [
            SystemMessage(content=EXPLORE_SYSTEM),
            HumanMessage(content=(
                f"Query: {query}\n\n"
                f"RAW SEARCH RESULTS (read these carefully — they list companies in this sector):\n"
                f"{raw_snippet_text}\n\n"
                f"STRUCTURED PROFILES (enrichment data for companies found in search):\n"
                f"{concise_profiles}"
            ))
        ])

        # Step 1b: Validate — match LLM-selected names to profiles where possible,
        # but accept ALL companies the LLM selected (knowledge-first approach).
        available_lower = {n.lower() for n in available_names}
        validated = []
        for c in report.companies:
            cname = c.name.strip().lower()
            # Try to match to available profile name for data enrichment later
            if cname in available_lower:
                validated.append(c)
                continue
            # Fuzzy: check if name is contained in or contains an available name
            for avail in available_lower:
                if cname in avail or avail in cname:
                    c.name = next(n for n in available_names if n.lower() == avail)
                    break
            # Accept ALL LLM-selected companies — the LLM's knowledge IS the discovery source
            validated.append(c)
        report.companies = validated

        # Step 2: Code-driven enrichment — match each company to its profile
        enriched = []
        seen = set()
        for c in report.companies:
            name_key = c.name.strip().lower()
            if name_key in seen:
                continue
            seen.add(name_key)

            # Fuzzy match: try exact, then substring, then profile name field
            profile = profile_map.get(name_key)
            if not profile:
                for pkey, p in profile_map.items():
                    if name_key in pkey or pkey in name_key:
                        profile = p
                        break
            if not profile:
                for _pkey, p in profile_map.items():
                    if name_key in (p.name or "").lower():
                        profile = p
                        break

            if profile:
                c = _enrich_from_profile(c, profile)

            # Also extract from raw snippets (catches data profiler missed)
            signals = signal_map.get(name_key, [])
            if not signals:
                # Fuzzy match signals by key name
                for skey, sigs in signal_map.items():
                    if name_key in skey or skey in name_key:
                        signals = sigs
                        break
            if not signals:
                # Search ALL signal snippets for mentions of this company
                # (catches data from listicle/comparison articles)
                for _skey, sigs in signal_map.items():
                    for sig in sigs:
                        if name_key in (sig.snippet or "").lower():
                            signals.append(sig)
            if signals:
                c = _extract_from_snippets(c, signals)

            # Step 3: Normalize and compute confidence
            _normalize_funding_str(c)
            c.confidence = _compute_confidence(c)
            enriched.append(c)

        # If too few companies enriched, fill from profiles
        enriched_names = {c.name.strip().lower() for c in enriched}
        if len(enriched) < 5:
            for key, p in profile_map.items():
                if key in enriched_names or key == "unknown":
                    continue
                c = ExploreCompany(
                    name=p.name or "Unknown",
                    sub_sector=p.sub_sector or "Unknown",
                )
                c = _enrich_from_profile(c, p)
                sigs = signal_map.get(key, [])
                if not sigs:
                    for skey, s_list in signal_map.items():
                        if key in skey or skey in key:
                            sigs = s_list
                            break
                if not sigs:
                    for _skey, s_list in signal_map.items():
                        for sig in s_list:
                            if key in (sig.snippet or "").lower():
                                sigs.append(sig)
                if sigs:
                    c = _extract_from_snippets(c, sigs)
                c.confidence = _compute_confidence(c)
                enriched.append(c)
                enriched_names.add(key)
                if len(enriched) >= 15:
                    break

        # Post-processing: filter out non-companies (generic terms, article sites)
        enriched = [c for c in enriched if not _is_non_company(c.name, c.website)]
        # NOTE: Sector-relevance filtering is handled by the LLM verification step,
        # not by keyword overlap. A company tagged "Developer Tool" IS relevant
        # to "AI coding assistants" — don't remove it based on sub_sector wording.

        # Deduplicate near-identical names (e.g., "GitHub" + "GitHub Copilot")
        enriched = _deduplicate_companies(enriched)

        # Verify against live web: add missing major companies AND remove irrelevant ones.
        # Runs BEFORE secondary enrichment so newly added companies also get enriched.
        enriched = _verify_and_supplement_companies(enriched, query, llm)
        enriched = [c for c in enriched if not _is_non_company(c.name, c.website)]
        # Run dedup again after verification (verification may have added duplicates)
        enriched = _deduplicate_companies(enriched)

        # Secondary enrichment: targeted web searches for companies missing key data.
        # Now covers both original AND verification-added companies.
        enriched = _secondary_enrich_batch(enriched)
        # Re-filter after enrichment (wrong websites may now be detected)
        enriched = [c for c in enriched if not _is_non_company(c.name, c.website)]

        # Clear funding that's obviously from a parent company.
        # Generic check: if funding > $1B AND the company name doesn't match its website domain,
        # the funding likely belongs to the parent company, not this product.
        for c in enriched:
            if c.funding_numeric and c.funding_numeric >= 1_000_000_000 and c.website:
                domain = _extract_domain(c.website).replace("www.", "")
                name_words = [w.lower().replace(".", "") for w in c.name.split() if len(w) > 2]
                # Check if ANY significant word from the company name appears in the domain
                name_in_domain = any(w in domain for w in name_words)
                if not name_in_domain:
                    logger.info("Clearing likely parent-company funding for %s ($%.0fB, domain=%s doesn't match name)",
                                c.name, c.funding_numeric / 1e9, domain)
                    c.funding_total = None
                    c.funding_numeric = 0.0

        enriched = _normalize_sub_sectors(enriched)
        # Re-sort by funding (descending) then confidence
        enriched.sort(key=lambda c: (c.funding_numeric or 0, c.confidence or 0), reverse=True)
        report.companies = enriched[:12]
        # Update report sub_sectors to match normalized companies
        report.sub_sectors = list({c.sub_sector for c in report.companies if c.sub_sector and c.sub_sector != "Unknown"})
    except Exception as exc:
        logger.error("Explore synthesis failed for query=%s: %s — building from profiles", query, exc)
        # Fallback: build directly from profiles
        enriched = []
        seen = set()
        for key, p in profile_map.items():
            if key in seen:
                continue
            seen.add(key)
            c = ExploreCompany(
                name=p.name or "Unknown",
                sub_sector=p.sub_sector or "Unknown",
            )
            c = _enrich_from_profile(c, p)
            signals = signal_map.get(key, [])
            if not signals:
                for skey, sigs in signal_map.items():
                    if key in skey or skey in key:
                        signals = sigs
                        break
            if not signals:
                for _skey, sigs in signal_map.items():
                    for sig in sigs:
                        if key in (sig.snippet or "").lower():
                            signals.append(sig)
            if signals:
                c = _extract_from_snippets(c, signals)
            c.confidence = _compute_confidence(c)
            enriched.append(c)
        enriched.sort(key=lambda x: x.confidence, reverse=True)
        enriched = enriched[:12]
        sub_sectors = list({c.sub_sector for c in enriched if c.sub_sector and c.sub_sector != "Unknown"})
        report = ExploreReport(
            query=query,
            sector=query,
            companies=enriched,
            sub_sectors=sub_sectors,
            summary="Report generated from raw profile data (LLM synthesis unavailable).",
            citations=[],
        )

    return report


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
        report = _synthesize_explore(state, profiles, profiles_text, llm_extraction)
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

    # 1d. Gap-fill: if structured arrays are thin, do a targeted LLM call to supplement
    gaps = []
    if len(meta.funding_rounds) < 2:
        gaps.append("funding_rounds (include ALL known rounds: Seed, Series A, B, C, D etc.)")
    if len(meta.competitor_entries) < 5:
        gaps.append("competitor_entries (include 5-8 major competitors with funding amounts)")
    if len(meta.news_items) < 3:
        gaps.append("news_items (include 5+ recent news items)")
    if len(meta.board_members) < 1:
        gaps.append("board_members (include investor board seats if known)")
    if len(meta.citations) < 5:
        gaps.append("citations (include source URLs for factual claims)")

    if gaps:
        logger.info("Gap-filling %d thin arrays for %s: %s", len(gaps), company_name, [g.split(" (")[0] for g in gaps])
        gap_prompt = (
            f"The following structured arrays for {company_name} are incomplete. "
            f"Fill them from your knowledge. Return ONLY the requested arrays.\n\n"
            f"Include ALL funding rounds — Seed through latest. Do not skip earlier rounds.\n"
            f"Do NOT fill linkedin_url or crunchbase_url — leave them null.\n\n"
            f"Thin arrays to fill:\n" + "\n".join(f"- {g}" for g in gaps)
        )
        try:
            gap_fill = invoke_structured(llm_extraction, MetadataAndArrays, [
                SystemMessage(content=gap_prompt),
                HumanMessage(content=f"Company: {company_name}\n\nExisting data:\n{profiles_text[:3000]}")
            ])
            # Merge gap-filled data (only add, never overwrite)
            if len(meta.funding_rounds) < 2 and gap_fill.funding_rounds:
                existing_stages = {(r.stage or "").lower() for r in meta.funding_rounds}
                for r in gap_fill.funding_rounds:
                    if (r.stage or "").lower() not in existing_stages:
                        meta.funding_rounds.append(r)
                meta.funding_rounds = deduplicate_funding_rounds(meta.funding_rounds)
            if len(meta.competitor_entries) < 5 and gap_fill.competitor_entries:
                existing_names = {c.name.lower() for c in meta.competitor_entries}
                for c in gap_fill.competitor_entries:
                    if c.name.lower() not in existing_names:
                        meta.competitor_entries.append(c)
            if len(meta.news_items) < 3 and gap_fill.news_items:
                existing_titles = {n.title.lower() for n in meta.news_items}
                for n in gap_fill.news_items:
                    if n.title.lower() not in existing_titles:
                        meta.news_items.append(n)
                meta.news_items.sort(key=lambda n: n.date or "0000-00-00", reverse=True)
            if len(meta.board_members) < 1 and gap_fill.board_members:
                meta.board_members = gap_fill.board_members
            if len(meta.citations) < 5 and gap_fill.citations:
                existing_urls = {c.url for c in meta.citations}
                for c in gap_fill.citations:
                    if c.url not in existing_urls:
                        meta.citations.append(c)
                for i, cit in enumerate(meta.citations, 1):
                    cit.id = i
            logger.info("Gap-fill complete: rounds=%d, competitors=%d, news=%d, board=%d, citations=%d",
                        len(meta.funding_rounds), len(meta.competitor_entries),
                        len(meta.news_items), len(meta.board_members), len(meta.citations))
        except Exception as exc:
            logger.warning("Gap-fill failed: %s", exc)

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

    # Normalize LinkedIn URLs (LinkedIn requires www.)
    meta.linkedin_url = _normalize_linkedin_url(meta.linkedin_url)
    for pe in meta.people_entries:
        pe.linkedin_url = _normalize_linkedin_url(pe.linkedin_url)
    for bm in meta.board_members:
        bm.linkedin_url = _normalize_linkedin_url(bm.linkedin_url)
    for adv in meta.advisors:
        adv.linkedin_url = _normalize_linkedin_url(adv.linkedin_url)

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
