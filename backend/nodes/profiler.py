# backend/nodes/profiler.py
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from langchain_core.messages import SystemMessage, HumanMessage
from backend.models import RawCompanySignal, CompanyProfile
from backend.config import get_llm, get_settings, invoke_structured

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract structured company data from the provided sources.
Only include information explicitly stated in the source text. Never guess or infer.

You MUST attempt to extract ALL of the following fields:

CORE FIELDS:
- name: The company's official name
- description: A 2-3 sentence summary of what the company does
- website: The company's primary website URL
- linkedin_url: The company's LinkedIn profile URL (e.g. "https://linkedin.com/company/...")
  IMPORTANT: Search carefully for LinkedIn URLs in the source text. Look for patterns like
  "linkedin.com/company/" or "linkedin.com/in/".
- crunchbase_url: The company's Crunchbase page URL (e.g. "https://crunchbase.com/organization/...")
- funding_total: Total funding raised (e.g. "$1.2B", "$50M"). Set funding_source_url too.
- funding_stage: Current stage (e.g. "Series B", "IPO / Public", "Seed").
  Set funding_stage_source_url too.
- key_investors: List of investor names (e.g. ["Sequoia Capital", "a16z"])
- founding_year: Year founded as integer (e.g. 2018). Set founding_year_source_url too.
  IMPORTANT: Also look for the month of founding. If found, note it in the description
  or in a format like "Founded in March 2018" somewhere in the data you extract.
- headcount_estimate: Approximate employees as string (e.g. "~500", "200-300")
- headquarters: City and region (e.g. "San Francisco, California")
- core_product: Main product or service (1-2 sentences)
- core_technology: Key technology used or developed (1-2 sentences)
- sub_sector: The company's specific sub-sector within its industry
- raw_sources: List of all source URLs used

PEOPLE (key_people): List of dicts with:
  - "name", "title", "background" (career history, prior roles)
  - "linkedin_url": CRITICAL — always include if found. Look for "linkedin.com/in/" patterns.
  - Prior exits/acquisitions, domain expertise years, and notable affiliations.
  CRITICAL: ONLY include people who are confirmed employees/founders/executives of the TARGET
  company being researched. Do NOT include people from competitor companies, investors, partners,
  or other organizations that appear in the search results. Every person MUST have a title at the
  target company. If you cannot confirm someone works at the target company, omit them.
  Example: [{"name": "Jane Doe", "title": "CEO", "background": "Previously VP at Google",
             "linkedin_url": "https://linkedin.com/in/janedoe"}]

NEWS (recent_news): List of dicts with "title", "date", "snippet"
  IMPORTANT: Use ISO-like date format (YYYY-MM-DD or YYYY-MM). Sort by date descending (newest first).
  Example: [{"title": "Company raises $50M", "date": "2024-03-15", "snippet": "..."}]

COMPETITOR ANALYSIS (competitors_mentioned): List of dicts with:
  - "name": competitor company name
  - "description": what the competitor does (1-2 sentences)
  - "funding": their funding if mentioned — CRITICAL: always include if mentioned in any source
  - "funding_stage": their funding stage if mentioned
  - "differentiator": how they differ from the target company
  - "overlap": where they compete/overlap with the target company
  - "website": competitor's website URL if found
  Example: [{"name": "Rival Inc", "description": "AI chip maker",
             "funding": "$200M Series C", "funding_stage": "Series C",
             "differentiator": "Focused on edge devices", "overlap": "Both target ML inference",
             "website": "https://rival.com"}]

DUE DILIGENCE FIELDS:
- market_tam: Total addressable market size if mentioned (e.g. "$50B by 2030"). Set market_tam_source_url.
- business_model: How the company makes money (e.g. "SaaS subscription", "hardware sales + licensing")
- revenue_indicators: Any revenue signals (ARR, MRR, revenue growth, customer count, contract values)
- customer_signals: Customer names, testimonials, case studies, or adoption metrics mentioned
- competitive_advantages: Moat, IP, patents, network effects, switching costs mentioned
- regulatory_environment: Any regulatory risks, compliance requirements, or legal issues mentioned

BOARD & GOVERNANCE (board_members): List of dicts with:
  - "name", "role" ("Chair", "Member", "Observer"), "organization", "background", "linkedin_url"
  Look for: "board of directors", "advisory board", "board member", "chairperson"
  Example: [{"name": "John Smith", "role": "Chair", "organization": "Sequoia Capital",
             "background": "Former CEO of Acme Corp"}]

ADVISORS (advisors): List of dicts with:
  - "name", "expertise", "organization", "linkedin_url"
  Look for: "advisor", "advisory board", "strategic advisor"

PARTNERSHIPS & CUSTOMERS:
- partnerships: List of dicts with "partner_name", "type" ("strategic"/"customer"/"technology"/"distribution"),
  "description", "date"
  Look for: "partnership", "strategic alliance", "teamed up with", "integrated with"
- key_customers: List of dicts with "name", "description"
  Look for: "customer", "client", "used by", "deployed at", "case study"

ACQUISITIONS (acquisitions): List of dicts with:
  - "acquired_company", "date", "amount", "rationale"
  Look for: "acquired", "acquisition", "merger", "M&A", "bought"

PATENTS (patents): List of dicts with:
  - "title", "filing_date", "status" ("granted"/"pending"), "domain", "patent_number"
  Look for: "patent", "intellectual property", "IP portfolio", "patent filed"

REVENUE ESTIMATE (revenue_estimate): Dict with:
  - "range": revenue range string (e.g. "$5M-$10M ARR", "$50M+ revenue")
  - "growth_rate": growth rate if mentioned (e.g. "~50% YoY", "3x in 2 years")

EMPLOYEE HISTORY (employee_count_history): List of dicts with:
  - "date" (e.g. "2024-01", "2025"), "count" (integer)
  Extract any historical headcount mentions with approximate dates.
  Look for: "employees", "team of", "headcount grew to", "workforce of"

OPERATING STATUS (operating_status):
  One of: "Active", "Acquired", "Closed", "IPO"
  Default to "Active" if no evidence of shutdown, acquisition, or IPO.

TRACTION / USER METRICS:
- app_store_rating: App Store or Google Play rating as float (e.g. 4.5, 4.8)
  Look for: "★", "stars", "rating", "4.5/5", "rated 4.8"
- app_store_reviews: Number of reviews as string (e.g. "12K reviews", "5,000+ reviews")
  Look for: "reviews", "ratings count"
- app_downloads: Download count as string (e.g. "1M+", "500K+ downloads", "100K installs")
  Look for: "downloads", "installs", "downloaded by"
- user_count: Active user count as string (e.g. "2M MAU", "50K active users", "500K registered")
  Look for: "users", "MAU", "DAU", "active users", "registered users", "user base"
- product_hunt_upvotes: Product Hunt upvote count as integer
  Look for: "Product Hunt", "upvotes", "hunted"

If a field's data is not in the sources, leave it null or empty. For each factual field
you populate, set the corresponding source_url field to where you found it."""


def crawl_page(url: str, timeout: float = 30.0) -> str | None:
    """Extract page content using Crawl4AI, fallback to Jina Reader."""
    try:
        from crawl4ai import WebCrawler
        crawler = WebCrawler()
        result = crawler.run(url=url)
        if result and result.markdown:
            return result.markdown
    except ImportError:
        logger.debug("Crawl4AI not installed, falling back to Jina Reader")
    except Exception as exc:
        logger.debug("Crawl4AI failed for %s: %s, falling back to Jina Reader", url, exc)

    # Fallback: Jina Reader
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp = httpx.get(jina_url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 100:
            return resp.text
    except Exception:
        pass

    return None


def _group_signals_by_company(signals: list[RawCompanySignal]) -> dict[str, list[RawCompanySignal]]:
    """Group raw signals by normalized company name (case-insensitive, stripped)."""
    groups: dict[str, list[RawCompanySignal]] = {}
    for s in signals:
        key = s.company_name.strip().lower()
        groups.setdefault(key, []).append(s)
    return groups


def _profile_one_company(
    company_key: str,
    company_signals: list[RawCompanySignal],
    mode: str,
) -> CompanyProfile:
    """Profile a single company. Thread-safe — creates its own LLM instance."""
    if not company_signals:
        logger.warning("Empty signal list for company_key=%s", company_key)
        return CompanyProfile(name=company_key)

    llm = get_llm(get_settings().extraction_model)

    snippets = "\n\n".join(
        f"Source: {s.url}\n{s.snippet}" for s in company_signals
    )

    extra_content = ""
    diffbot_data: dict | None = None
    if mode == "deep_dive":
        urls = list({s.url for s in company_signals})[:5]

        with ThreadPoolExecutor(max_workers=5) as pool:
            future_to_url = {pool.submit(crawl_page, url): url for url in urls}
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page = future.result()
                    if page:
                        extra_content += f"\n\n--- Full page: {url} ---\n{page[:3000]}"
                except Exception as exc:
                    logger.warning("Crawl failed for %s: %s", url, exc)

        # Diffbot enrichment
        try:
            from backend.apis.diffbot import lookup_company_sync
            diffbot_data = lookup_company_sync(company_signals[0].company_name)
        except Exception as exc:
            logger.warning("Diffbot lookup failed for %s: %s", company_key, exc)

    combined = f"{snippets}{extra_content}"

    try:
        result = invoke_structured(llm, CompanyProfile, [
            SystemMessage(content=EXTRACTION_PROMPT),
            HumanMessage(content=f"Extract company profile from:\n\n{combined}")
        ])
        if not result.name:
            result.name = company_signals[0].company_name

        if diffbot_data:
            _merge_diffbot(result, diffbot_data)

        return result
    except Exception as exc:
        logger.warning("LLM extraction failed for company=%s: %s", company_key, exc)
        return CompanyProfile(
            name=company_signals[0].company_name,
            raw_sources=[s.url for s in company_signals],
        )


def profile(state: dict) -> dict:
    """Profile node: extract structured CompanyProfile objects from raw signals.

    Companies are profiled in parallel using a thread pool.
    - Explore mode: Lightweight profiling using Tavily snippets only (no Crawl4AI).
    - Deep Dive mode: Full extraction using Crawl4AI (primary) -> Jina Reader (fallback)
      -> Tavily snippets (last resort).
    """
    mode = state["mode"]
    signals = state["raw_signals"]

    grouped = _group_signals_by_company(signals)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_profile_one_company, key, sigs, mode): key
            for key, sigs in grouped.items()
        }
        profiles: list[CompanyProfile] = []
        for future in as_completed(futures):
            company_key = futures[future]
            try:
                profiles.append(future.result())
            except Exception as exc:
                logger.error("Profiler thread failed for %s: %s", company_key, exc)

    return {"company_profiles": profiles}


def _merge_diffbot(profile: CompanyProfile, diffbot: dict) -> None:
    """Merge Diffbot data into a CompanyProfile, filling gaps only."""
    if not profile.description and diffbot.get("description"):
        profile.description = diffbot["description"]
    if not profile.headquarters and diffbot.get("headquarters"):
        profile.headquarters = diffbot["headquarters"]
    if not profile.website and diffbot.get("website"):
        profile.website = diffbot["website"]
    if not profile.founding_year and diffbot.get("founding_year"):
        profile.founding_year = diffbot["founding_year"]
    if not profile.headcount_estimate and diffbot.get("headcount_estimate"):
        profile.headcount_estimate = diffbot["headcount_estimate"]
    if not profile.operating_status and diffbot.get("operating_status"):
        profile.operating_status = diffbot["operating_status"]
    if not profile.sub_sector and diffbot.get("sub_sector"):
        profile.sub_sector = diffbot["sub_sector"]
    if not profile.linkedin_url and diffbot.get("linkedin_url"):
        profile.linkedin_url = diffbot["linkedin_url"]
    if not profile.crunchbase_url and diffbot.get("crunchbase_url"):
        profile.crunchbase_url = diffbot["crunchbase_url"]
    # Always merge employee history and revenue (additive data)
    if diffbot.get("employee_count_history"):
        profile.employee_count_history.extend(diffbot["employee_count_history"])
    if not profile.revenue_estimate and diffbot.get("revenue_estimate"):
        profile.revenue_estimate = diffbot["revenue_estimate"]
