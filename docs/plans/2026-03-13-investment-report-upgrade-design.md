# Investment Report Upgrade — Design Document

**Date:** 2026-03-13
**Status:** Approved

## Problem

The deep dive report lacks critical data needed for investment decisions compared to professional platforms like Crunchbase, PitchBook, and CB Insights. Key gaps: no investment scoring, no valuations per round, no board/advisor data, no M&A history, no partnerships/customers, no patents, no revenue estimates. Additionally, the report is a single scrollable page that becomes unwieldy with more sections.

## Solution

1. Add 8 new data categories to the research pipeline
2. Integrate 2 free APIs (Diffbot, USPTO PatentsView) for structured data
3. Expand web search queries for data not covered by APIs
4. Compute an Investment Readiness Score (0-100, four sub-scores)
5. Reorganize the UI into 6 tabbed sections following an investor workflow

## Data Architecture

### New Pydantic Models (backend/models.py)

```python
# --- Investment Score ---
class InvestmentScore(BaseModel):
    overall: int  # 0-100
    money: int  # 0-25
    market: int  # 0-25
    momentum: int  # 0-25
    management: int  # 0-25
    rationale: str  # Brief explanation

# --- Enhanced FundingRound (add fields to existing) ---
# Add to FundingRound:
#   lead_investor: Optional[str]
#   pre_money_valuation: Optional[str]
#   post_money_valuation: Optional[str]

# --- Board & Advisors ---
class BoardMember(BaseModel):
    name: str
    role: Optional[str]  # "Chair", "Member", "Observer"
    organization: Optional[str]
    background: Optional[str]
    linkedin_url: Optional[str]
    source_url: Optional[str]

class Advisor(BaseModel):
    name: str
    expertise: Optional[str]
    organization: Optional[str]
    linkedin_url: Optional[str]
    source_url: Optional[str]

# --- Partnerships & Customers ---
class Partnership(BaseModel):
    partner_name: str
    type: Optional[str]  # "strategic", "customer", "technology", "distribution"
    description: Optional[str]
    date: Optional[str]
    source_url: Optional[str]

class KeyCustomer(BaseModel):
    name: str
    description: Optional[str]
    source_url: Optional[str]

# --- Acquisitions ---
class Acquisition(BaseModel):
    acquired_company: str
    date: Optional[str]
    amount: Optional[str]
    rationale: Optional[str]
    source_url: Optional[str]

# --- Patents ---
class Patent(BaseModel):
    title: str
    filing_date: Optional[str]
    status: Optional[str]  # "granted", "pending"
    domain: Optional[str]
    patent_number: Optional[str]
    source_url: Optional[str]

# --- Revenue ---
class RevenueEstimate(BaseModel):
    range: Optional[str]  # "$5M-$10M ARR"
    growth_rate: Optional[str]  # "~50% YoY"
    source_url: Optional[str]
    confidence: float = 0.0

# --- Employee History ---
class EmployeeCountPoint(BaseModel):
    date: str  # "2024-01", "2025-06"
    count: int
    source: Optional[str]  # "diffbot", "linkedin", "web"
```

### DeepDiveReport Additions

```python
# New fields on DeepDiveReport:
operating_status: Optional[str]  # "Active", "Acquired", "Closed", "IPO"
total_funding: Optional[str]
investment_score: Optional[InvestmentScore]
revenue_estimate: Optional[RevenueEstimate]
board_members: list[BoardMember]
advisors: list[Advisor]
partnerships: list[Partnership]
key_customers: list[KeyCustomer]
acquisitions: list[Acquisition]
patents: list[Patent]
employee_count_history: list[EmployeeCountPoint]

# New prose sections:
governance: Optional[DeepDiveSection]  # Board & advisors analysis
```

## API Integrations

### Diffbot Knowledge Graph API

**Purpose:** Structured company data (basics, revenue, employee count, tech stack)
**Free tier:** 10,000 credits/month (~400 company lookups)
**Integration point:** New `backend/apis/diffbot.py` module called from profiler node

```
GET https://kg.diffbot.com/kg/v3/dql?query=type:Organization name:"<company>"
Returns: revenue, employees, location, founded, description, categories, techStack
```

**Data mapping:**
- `nbEmployees` → current employee count + history point
- `revenue` → revenue_estimate.range
- `location` → headquarters (enrichment/verification)
- `foundedDate` → founding_year (enrichment/verification)
- `categories` → sub_sector verification
- `techStack` → mentioned in product_technology section

### Patents

No patent API — USPTO PatentsView API key grants are temporarily suspended. Patent data comes from web search + LLM extraction using the query `"{company} patents intellectual property filings"`. This is sufficient for identifying notable patents from press releases, Google Patents listings, and company websites.

### Integration Strategy

Diffbot is called in the **profiler node** in parallel with web crawling. Results are merged into the CompanyProfile before synthesis. If the API fails or returns empty, the pipeline continues with web-search-only data (graceful degradation).

## Search Strategy

### New Planner Queries (6 additions to DEEP_DIVE_PROMPT)

Add to the DUE DILIGENCE section of the planner prompt:

```
GOVERNANCE & PEOPLE:
- "{company} board of directors advisors board members governance"

CORPORATE ACTIVITY:
- "{company} acquisitions acquired companies M&A mergers"
- "{company} partnerships strategic partners customers clients key accounts"

INTELLECTUAL PROPERTY:
- "{company} patents intellectual property filings inventions"

FINANCIAL ESTIMATES:
- "{company} revenue ARR annual revenue estimate valuation fundraise"

WORKFORCE:
- "{company} employee count headcount growth hiring linkedin"
```

### Profiler Extraction Additions

Expand EXTRACTION_PROMPT with new sections:

```
BOARD & GOVERNANCE (board_members):
- Extract board member names, roles (Chair/Member/Observer), org affiliation
- Look for "board of directors", "advisory board", "board member"

ADVISORS (advisors):
- Extract advisor names, expertise areas, organizations
- Look for "advisor", "advisory board", "strategic advisor"

PARTNERSHIPS & CUSTOMERS (partnerships, key_customers):
- Extract partner names, partnership types, key customer names
- Look for "partnership", "strategic alliance", "customer", "client"

ACQUISITIONS (acquisitions):
- Extract acquired company names, dates, amounts, rationale
- Look for "acquired", "acquisition", "merger", "M&A"

REVENUE SIGNALS (revenue_estimate):
- Extract revenue ranges, ARR/MRR, growth rates
- Look for "revenue", "ARR", "MRR", "annual recurring"

EMPLOYEE HISTORY (employee_count_history):
- Extract any historical headcount mentions with dates
- Look for "employees", "team of", "headcount", "grew to"

OPERATING STATUS:
- Determine if company is Active, Acquired, Closed, or IPO
```

## Investment Score Computation

Computed in **synthesis node** after all data is gathered. Four sub-scores (0-25 each):

### Money Score (0-25)
- Funding recency (recent round = higher)
- Round progression (Seed → A → B = healthy trajectory)
- Investor quality (well-known VCs = higher)
- Total funding amount relative to stage
- Revenue signals present

### Market Score (0-25)
- TAM mentioned and sized
- Market growth signals
- Clear market positioning
- Business model clarity
- Low regulatory risk

### Momentum Score (0-25)
- Recent news (positive sentiment = higher)
- Hiring/employee growth
- Partnership activity
- Recent funding round
- Product launches or milestones

### Management Score (0-25)
- Team prior exits
- Domain expertise years
- Board quality (known investors/operators)
- Advisor strength
- Complete leadership (CEO + CTO + key roles filled)

**Implementation:** Single LLM call in synthesis with all profile data as context, outputting `InvestmentScore` structured output. The LLM evaluates signals and assigns scores with rationale.

## UI Design

### Tab Structure

Replace single-scroll layout with 6 horizontal tabs. Each tab is internally scrollable with optional sub-navigation.

```
[Overview] [Financials] [Team] [Product & Market] [Traction] [Risk]
```

Tab bar: sticky below TopBar. Uses existing Radix `<Tabs>` component from `ui/tabs.jsx`.

### Tab 1: Overview
- **Investment Score Card** — circular gauge (0-100), four mini progress bars (Money/Market/Momentum/Management), rationale text
- **Metric Cards** — 6-column grid: Founded | HQ | Employees | Stage | Status | Total Funding
- **Overview Prose** — existing overview DeepDiveSection

### Tab 2: Financials
- **Revenue Estimate Card** — range display, growth rate badge, confidence indicator
- **Funding Chart** — enhanced existing FundingChart with valuation line overlay (dual Y-axis)
- **Funding Table** — existing table + 3 new columns: Lead Investor, Pre-Money, Post-Money
- **Funding Prose** — existing funding DeepDiveSection

### Tab 3: Team
- **Key Executives** — existing person cards (2-col grid)
- **Board Members** — new card grid with role badges (Chair/Member/Observer)
- **Advisors** — new card grid with expertise badges
- **Governance Prose** — new prose section on board/management quality

### Tab 4: Product & Market
- **Product/Technology Prose** — existing section
- **Patents Table** — new: title, filing date, status badge (Granted ●/Pending ○), domain
- **Market Opportunity Prose** — existing (was conditional due diligence)
- **Competitive Advantages Prose** — existing
- **Business Model Prose** — existing
- Left sub-nav for jumping between sub-sections

### Tab 5: Traction
- **Employee Growth Chart** — line chart (Recharts) from employee_count_history
- **Key Partnerships** — card grid: partner name, type badge, description
- **Key Customers** — list with names and context
- **Acquisitions Timeline** — cards: acquired company, date, amount, rationale
- **Traction Prose** — existing section
- **Recent News** — existing NewsCard grid (moved here)

### Tab 6: Risk
- **Competitors Table** — existing (moved here as competitive risk)
- **Competitors Prose** — existing
- **Red Flags** — existing RedFlagCard components
- **Risk Entries** — existing risk cards with category/severity
- **Risks Prose** — existing

### Navigation Behavior
- Tab state stored in component state (not URL, to keep it simple)
- SectionNav sidebar repurposed as **in-tab sub-navigation** for tabs with multiple sub-sections
- IntersectionObserver still tracks active sub-section within current tab
- Tab defaults to Overview on report load
- Confidence badges shown on tab triggers (worst confidence of contained sections)

### Visual Design
- Use `ui-ux-pro-max` skill during implementation for professional styling
- Maintain existing design tokens (HSL variables, glass morphism, animations)
- New components follow existing patterns (rounded-xl, confidence borders, staggered animations)
- Investment score gauge: custom SVG with gradient stroke (red → amber → green)

## Compatibility

### RAG System
No changes needed. RAG ingestion happens at Searcher stage (before profiling). More search queries = richer RAG context. Chat can now answer questions about board, patents, valuations, etc.

### Caching
No changes needed. Report cache stores the full DeepDiveReport object. New fields are simply additional data in the cached object.

### Critic Node
No changes needed. The critic evaluates sections by key name. New sections (governance) will be evaluated automatically. New structured arrays don't affect the critic flow.

### Chat System
No changes needed. The chat endpoint reads from RAG (raw search content) and the report object. New fields in the report are accessible to chat responses.

## Out of Scope
- No paid API integrations (Crunchbase API $50K+, PitchBook $12K+)
- No real-time financial data feeds
- No cap table modeling
- No company comparison side-by-side view
- No changes to explore mode or history views
- No changes to RAG/chat system
- No changes to caching or critic nodes

## Risk Mitigation
- Some data (exact valuations, revenue, patents) may not be findable via web search + free APIs. The confidence system handles this — sections render conditionally, low-confidence warnings surface gaps.
- Diffbot free tier (400 lookups/month) may be insufficient for heavy usage. Fallback: web-search-only mode if quota exhausted.
- USPTO only covers US patents. International patents come from web search extraction.
