# Investment Report Upgrade — Implementation Plan

**Date:** 2026-03-13
**Design Doc:** `2026-03-13-investment-report-upgrade-design.md`

## Task Overview

Upgrade the deep dive research report to match professional investment platforms (Crunchbase, PitchBook, CB Insights). Adds 8 new data categories, Diffbot API integration, investment scoring, and reorganizes UI into 6 tabbed sections.

---

## Task 1: New Pydantic Models

**Files:** `backend/models.py`

**Changes:**
1. Add new model classes:
   - `InvestmentScore` (overall, money, market, momentum, management, rationale)
   - `BoardMember` (name, role, organization, background, linkedin_url, source_url)
   - `Advisor` (name, expertise, organization, linkedin_url, source_url)
   - `Partnership` (partner_name, type, description, date, source_url)
   - `KeyCustomer` (name, description, source_url)
   - `Acquisition` (acquired_company, date, amount, rationale, source_url)
   - `Patent` (title, filing_date, status, domain, patent_number, source_url)
   - `RevenueEstimate` (range, growth_rate, source_url, confidence)
   - `EmployeeCountPoint` (date, count, source)

2. Extend `FundingRound`:
   - Add `lead_investor: Optional[str]`
   - Add `pre_money_valuation: Optional[str]`
   - Add `post_money_valuation: Optional[str]`

3. Extend `DeepDiveReport`:
   - Add `operating_status: Optional[str]`
   - Add `total_funding: Optional[str]`
   - Add `investment_score: Optional[InvestmentScore]`
   - Add `revenue_estimate: Optional[RevenueEstimate]`
   - Add `board_members: list[BoardMember]` (default_factory=list)
   - Add `advisors: list[Advisor]` (default_factory=list)
   - Add `partnerships: list[Partnership]` (default_factory=list)
   - Add `key_customers: list[KeyCustomer]` (default_factory=list)
   - Add `acquisitions: list[Acquisition]` (default_factory=list)
   - Add `patents: list[Patent]` (default_factory=list)
   - Add `employee_count_history: list[EmployeeCountPoint]` (default_factory=list)
   - Add `governance: Optional[DeepDiveSection]`

4. Extend `MetadataAndArrays` (in synthesis.py):
   - Add `operating_status: Optional[str]`
   - Add `total_funding: Optional[str]`
   - Add all new structured arrays

5. Extend `CompanyProfile`:
   - Add `board_members: list[dict]` (default_factory=list)
   - Add `advisors: list[dict]` (default_factory=list)
   - Add `partnerships: list[dict]` (default_factory=list)
   - Add `key_customers: list[dict]` (default_factory=list)
   - Add `acquisitions: list[dict]` (default_factory=list)
   - Add `patents: list[dict]` (default_factory=list)
   - Add `revenue_estimate: Optional[dict]`
   - Add `employee_count_history: list[dict]` (default_factory=list)
   - Add `operating_status: Optional[str]`

**Review checkpoint:** Verify models are importable, no circular deps, existing tests still pass.

---

## Task 2: Diffbot API Integration

**Files:** `backend/apis/__init__.py` (new), `backend/apis/diffbot.py` (new), `backend/config.py`, `backend/requirements.txt`

**Changes:**
1. Create `backend/apis/` directory with `__init__.py`
2. Create `backend/apis/diffbot.py`:
   - `async def lookup_company(company_name: str) -> dict | None`
   - Calls `https://kg.diffbot.com/kg/v3/dql` with DQL query: `type:Organization name:"<company>"`
   - Maps response fields to CompanyProfile-compatible dict
   - Returns None on error/empty (graceful degradation)
   - Respects rate limits, 30s timeout
3. Add `DIFFBOT_API_KEY` to `Settings` in `config.py`
4. Add `httpx` to requirements.txt (async HTTP client for API calls)

**Data mapping logic in diffbot.py:**
```
response.nbEmployees → headcount_estimate, employee_count_history[0]
response.revenue → revenue_estimate
response.location → headquarters (verify/enrich)
response.foundedDate → founding_year (verify/enrich)
response.categories → sub_sector (verify)
response.description → description (verify/enrich)
response.stock → operating_status (if IPO info present)
```

**Review checkpoint:** Test with a known company name, verify response mapping.

---

## Task 3: Expand Planner Search Queries

**Files:** `backend/nodes/planner.py`

**Changes:**
1. Update `DEEP_DIVE_PROMPT` to add 6 new query categories:

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

2. Update target from "8-10 search terms" to "12-16 search terms" in the prompt

**Review checkpoint:** Run planner on a test company, verify new queries appear.

---

## Task 4: Expand Profiler Extraction

**Files:** `backend/nodes/profiler.py`

**Changes:**
1. Update `EXTRACTION_PROMPT` to add new extraction sections:
   - `board_members`: list of {name, role, organization, background, linkedin_url}
   - `advisors`: list of {name, expertise, organization, linkedin_url}
   - `partnerships`: list of {partner_name, type, description, date}
   - `key_customers`: list of {name, description}
   - `acquisitions`: list of {acquired_company, date, amount, rationale}
   - `patents`: list of {title, filing_date, status, domain, patent_number}
   - `revenue_estimate`: {range, growth_rate}
   - `employee_count_history`: list of {date, count}
   - `operating_status`: "Active" | "Acquired" | "Closed" | "IPO"

2. Integrate Diffbot call in `profile()` function:
   - For deep_dive mode, call `diffbot.lookup_company()` in parallel with web crawling
   - Merge Diffbot structured data into the CompanyProfile
   - Diffbot data used as verification/enrichment (doesn't override web-extracted data, fills gaps)

3. Update `CompanyProfile` field extraction to include new fields

**Review checkpoint:** Run profiler on a test company, verify new fields are populated.

---

## Task 5: Expand Synthesis & Investment Score

**Files:** `backend/nodes/synthesis.py`

**Changes:**
1. Add new section prompt to `_SECTION_PROMPTS`:
   - `"governance"`: Board composition, advisor quality, governance structure analysis

2. Add `_INVESTMENT_SCORE_PROMPT`:
   - System prompt that evaluates all gathered data
   - Outputs InvestmentScore with four sub-scores and rationale
   - Scores based on signals: funding trajectory, team quality, market size, news sentiment, hiring, partnerships, revenue signals

3. Update `MetadataAndArrays` extraction:
   - Add `operating_status`, `total_funding` to metadata prompt
   - Add `board_members`, `advisors`, `partnerships`, `key_customers`, `acquisitions`, `patents`, `employee_count_history`, `revenue_estimate` to structured arrays

4. Update `synthesize()` function:
   - Add governance to parallel section generation
   - Add investment score LLM call (can run in parallel with sections)
   - Add enhanced FundingRound fields (lead_investor, pre/post valuations) to metadata extraction
   - Wire new arrays into DeepDiveReport

**Review checkpoint:** Run full pipeline on a test company, verify all new sections and score populate.

---

## Task 6: Frontend — Tab System & Overview Tab

**Files:**
- `frontend/src/components/deep-dive/DeepDiveView.jsx` (major refactor)
- `frontend/src/components/deep-dive/InvestmentScoreCard.jsx` (new)
- `frontend/src/components/deep-dive/TabNav.jsx` (new)

**Changes:**
1. Refactor `DeepDiveView.jsx`:
   - Replace single-scroll layout with `<Tabs>` from `ui/tabs.jsx`
   - 6 tabs: Overview, Financials, Team, Product & Market, Traction, Risk
   - Tab bar: sticky below TopBar with icons (Lucide)
   - Each tab is a `<TabsContent>` with internal scroll
   - Move `SectionNav` inside each tab as sub-navigation

2. Create `InvestmentScoreCard.jsx`:
   - Circular gauge SVG (0-100) with gradient stroke (red→amber→green)
   - Four horizontal mini progress bars for sub-scores
   - Rationale text below
   - Animate on mount

3. Overview tab content:
   - InvestmentScoreCard
   - 6 MetricCards: Founded, HQ, Employees, Stage, Status, Total Funding
   - Overview prose section

**Use `ui-ux-pro-max` skill for visual design of all new components.**

**Review checkpoint:** Visual review — tab switching works, overview tab looks professional.

---

## Task 7: Frontend — Financials Tab

**Files:**
- `frontend/src/components/deep-dive/DeepDiveView.jsx`
- `frontend/src/components/deep-dive/FundingChart.jsx` (enhance)
- `frontend/src/components/deep-dive/RevenueCard.jsx` (new)

**Changes:**
1. Create `RevenueCard.jsx`:
   - Revenue range display (large text)
   - Growth rate badge
   - Confidence indicator
   - Source link

2. Enhance `FundingChart.jsx`:
   - Add valuation line overlay (dual Y-axis) if valuation data exists
   - Add columns to table: Lead Investor, Pre-Money, Post-Money

3. Financials tab content:
   - RevenueCard (if revenue_estimate exists)
   - Enhanced FundingChart
   - Funding prose section

**Review checkpoint:** Chart renders correctly with new columns, revenue card displays properly.

---

## Task 8: Frontend — Team Tab

**Files:**
- `frontend/src/components/deep-dive/DeepDiveView.jsx`
- `frontend/src/components/deep-dive/BoardCard.jsx` (new)

**Changes:**
1. Create `BoardCard.jsx`:
   - Reuse similar layout to person cards
   - Role badge (Chair/Member/Observer/Advisor)
   - Organization affiliation
   - LinkedIn link

2. Team tab content:
   - Key Executives — existing person card grid
   - Board Members — BoardCard grid (if board_members exists)
   - Advisors — BoardCard grid with expertise badges (if advisors exists)
   - Governance prose section (if exists)

**Review checkpoint:** Cards render, role badges display correctly.

---

## Task 9: Frontend — Product & Market Tab

**Files:**
- `frontend/src/components/deep-dive/DeepDiveView.jsx`
- `frontend/src/components/deep-dive/PatentTable.jsx` (new)

**Changes:**
1. Create `PatentTable.jsx`:
   - Table: Title, Filing Date, Status (Granted●/Pending○ badge), Domain
   - Similar style to CompetitorTable

2. Product & Market tab content (with sub-nav):
   - Product/Technology prose
   - Patents table (if patents exist)
   - Market Opportunity prose (if exists)
   - Competitive Advantages prose (if exists)
   - Business Model prose (if exists)

**Review checkpoint:** Table renders, sub-nav works within tab.

---

## Task 10: Frontend — Traction Tab

**Files:**
- `frontend/src/components/deep-dive/DeepDiveView.jsx`
- `frontend/src/components/deep-dive/EmployeeChart.jsx` (new)
- `frontend/src/components/deep-dive/PartnershipCard.jsx` (new)
- `frontend/src/components/deep-dive/AcquisitionCard.jsx` (new)

**Changes:**
1. Create `EmployeeChart.jsx`:
   - Recharts LineChart from employee_count_history
   - X-axis: dates, Y-axis: count
   - Tooltip with date + count
   - Gradient fill under line

2. Create `PartnershipCard.jsx`:
   - Partner name, type badge (Strategic/Customer/Tech/Distribution), description
   - Date and source link

3. Create `AcquisitionCard.jsx`:
   - Timeline-style: acquired company name, date, amount, rationale
   - Source link

4. Traction tab content:
   - Employee growth chart (if history exists)
   - Partnerships card grid (if partnerships exist)
   - Key Customers list (if key_customers exist)
   - Acquisitions timeline (if acquisitions exist)
   - Traction prose (if exists)
   - Recent News — NewsCard grid (moved from standalone section)

**Review checkpoint:** Charts and cards render, conditional sections hide when empty.

---

## Task 11: Frontend — Risk Tab

**Files:**
- `frontend/src/components/deep-dive/DeepDiveView.jsx`

**Changes:**
1. Risk tab content (reuses existing components):
   - Competitors prose + CompetitorTable
   - Red Flags — RedFlagCard grid
   - Risk entries with category/severity cards
   - Risks prose (if exists)

**Review checkpoint:** All existing components render correctly in new tab context.

---

## Task 12: Integration Testing & Polish

**Files:** Multiple

**Changes:**
1. Run full pipeline end-to-end on 2-3 test companies
2. Verify all tabs populate correctly
3. Verify conditional rendering (empty sections hidden gracefully)
4. Verify chat panel still works with new tab layout
5. Verify PDF export works with tab content
6. Verify confidence badges on tabs show worst section confidence
7. Fix any visual issues, spacing, responsive behavior
8. Update existing tests if needed (model changes may break some)

**Review checkpoint:** Full visual + functional review.

---

## Execution Order

Tasks 1-5 (backend) can be partially parallelized:
- Task 1 (models) must go first
- Tasks 2, 3 can run in parallel after Task 1
- Task 4 depends on Task 1 + Task 2
- Task 5 depends on Task 1 + Task 4

Tasks 6-11 (frontend) can be partially parallelized:
- Task 6 (tab system + overview) must go first
- Tasks 7, 8, 9, 10, 11 can run in parallel after Task 6

Task 12 runs last.

## Dependencies

- `httpx` — async HTTP client for Diffbot API calls
- No other new dependencies (Recharts, Radix Tabs already installed)
