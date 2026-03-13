# Free APIs for Private Company Intelligence Data

**Research Date:** 2026-03-13
**Status:** Current as of March 2026

---

## Table of Contents

1. [Tier 1: Fully Free / Government Open Data APIs](#tier-1-fully-free--government-open-data-apis)
2. [Tier 2: Generous Free Tiers (Usable Without Paying)](#tier-2-generous-free-tiers)
3. [Tier 3: Limited Free Tiers (Evaluation/Light Use Only)](#tier-3-limited-free-tiers)
4. [Tier 4: No Meaningful Free Tier (Paid Only)](#tier-4-no-meaningful-free-tier)
5. [Coverage Matrix](#coverage-matrix)
6. [Recommended Stack](#recommended-stack)

---

## Tier 1: Fully Free / Government Open Data APIs

These APIs are completely free with no payment required, backed by governments or open-data orgs.

---

### 1. SEC EDGAR APIs (USA)

| Field | Details |
|---|---|
| **URL** | https://www.sec.gov/search-filings/edgar-application-programming-interfaces |
| **Data endpoint** | `https://data.sec.gov/` |
| **Data provided** | Company filings (10-K, 10-Q, 8-K, etc.), XBRL financial data, company facts, officer/director data (from filings), M&A disclosures, insider transactions |
| **Free tier** | **Completely free, no API key required** |
| **Rate limit** | 10 requests/second |
| **Auth** | None. Must declare User-Agent header: `"Company Name contact@email.com"` |
| **Private companies** | Limited -- only companies that file with the SEC (public + some large private filers) |
| **Format** | REST, JSON |
| **Restrictions** | Must identify yourself via User-Agent. Fair-use rate limiting |

**Key endpoints:**
- Submissions API: `https://data.sec.gov/submissions/CIK{cik}.json`
- Company Facts: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
- Company Concept: `https://data.sec.gov/api/xbrl/companyconcept/...`
- Full-Text Search (EFTS): `https://efts.sec.gov/LATEST/search-index?q=...`

**Best for:** Financials, officer data, M&A filings for SEC-reporting companies.

---

### 2. Companies House API (UK)

| Field | Details |
|---|---|
| **URL** | https://developer.company-information.service.gov.uk/ |
| **Data provided** | Company registration, officers/directors, filing history, financial statements (iXBRL), registered address, SIC codes, company status, charges, persons with significant control (PSC/beneficial ownership) |
| **Free tier** | **Completely free** |
| **Rate limit** | 600 requests per 5 minutes (120 req/min) |
| **Auth** | Free API key (register for account) |
| **Private companies** | **Yes -- all UK registered companies, including private Ltd companies** |
| **Format** | REST, JSON |
| **Restrictions** | UK companies only. Data is Crown Copyright under Open Government Licence |

**Best for:** UK private company basics, officers, financial filings, beneficial ownership.

---

### 3. USPTO PatentsView / Open Data Portal (USA)

| Field | Details |
|---|---|
| **URL** | https://patentsview.org/ and https://developer.uspto.gov/api-catalog |
| **Data provided** | Patent metadata, inventors, assignees (companies), patent classifications (CPC/USPC), citations, full text, patent families |
| **Free tier** | **Completely free** |
| **Rate limit** | 45 requests/minute per API key |
| **Auth** | API key required (free registration) |
| **Private companies** | **Yes -- patents are filed by both public and private companies** |
| **Format** | REST, JSON |
| **Restrictions** | US patents only. Legacy API discontinued May 2025; use new PatentSearch API |

**Key API:** PatentSearch API at `https://search.patentsview.org/`

**Best for:** Patent/IP analysis, identifying R&D activity, inventor-company relationships.

---

### 4. Wikidata SPARQL API

| Field | Details |
|---|---|
| **URL** | https://query.wikidata.org/ |
| **Data provided** | Company founding dates (P571), headquarters location (P159), industry (P452), number of employees (P1128), subsidiaries (P355), parent org (P749), CEO (P169), founders (P112), official website (P856), revenue (P2139), stock exchange (P414), legal form (P1454) |
| **Free tier** | **Completely free, no key required** |
| **Rate limit** | Queries limited to 60 seconds execution time. Concurrent query limits per IP |
| **Auth** | None |
| **Private companies** | **Yes -- notable private companies are in Wikidata (e.g., SpaceX, Stripe)** |
| **Format** | SPARQL endpoint returning JSON, XML, or CSV |
| **Restrictions** | CC0 license. Coverage is community-maintained, so varies by company notability. Data may be incomplete or outdated for smaller companies |

**Example SPARQL query for company data:**
```sparql
SELECT ?company ?companyLabel ?founded ?hqLabel ?employees WHERE {
  ?company wdt:P31/wdt:P279* wd:Q4830453 .  # instance of business
  ?company wdt:P571 ?founded .                # founding date
  OPTIONAL { ?company wdt:P159 ?hq . }
  OPTIONAL { ?company wdt:P1128 ?employees . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
} LIMIT 100
```

**Best for:** Basic company facts for well-known companies (both public and private).

---

### 5. GLEIF API (Global LEI Data)

| Field | Details |
|---|---|
| **URL** | https://api.gleif.org/api/v1/ |
| **Documentation** | https://www.gleif.org/en/lei-data/gleif-api |
| **Data provided** | Legal entity name, registered address, headquarters address, legal form, registration authority, entity status (active/inactive), parent/child relationships (direct & ultimate), LEI-to-BIC/ISIN mappings |
| **Free tier** | **Completely free** |
| **Rate limit** | 60 requests/minute per user |
| **Auth** | None required |
| **Private companies** | **Yes -- any entity with a Legal Entity Identifier, including many private companies** |
| **Format** | REST, JSON (JSON:API spec) |
| **Restrictions** | CC0 license. Only covers entities that have obtained an LEI (~2.5M entities globally). Bulk downloads also available free |

**Best for:** Entity verification, corporate hierarchy/ownership chains, legal entity relationships.

---

### 6. BRREG (Norway Business Register)

| Field | Details |
|---|---|
| **URL** | https://data.brreg.no/ |
| **Data provided** | All registered Norwegian organizations: name, org number, address, industry codes (NACE), number of employees, founding date, organizational form, roles (board members, CEO) |
| **Free tier** | **Completely free** |
| **Rate limit** | Not explicitly documented; reasonable use expected |
| **Auth** | None |
| **Private companies** | **Yes -- all Norwegian registered entities** |
| **Format** | REST, JSON |
| **Restrictions** | Norwegian Open Government Licence (NLOD). Norwegian companies only |

**Best for:** Norwegian private company data with employee counts and officer info.

---

### 7. OpenSanctions API

| Field | Details |
|---|---|
| **URL** | https://www.opensanctions.org/api/ |
| **Data provided** | Sanctions lists, politically exposed persons (PEPs), entities of criminal interest. Includes company names, aliases, jurisdictions, sanctions designations |
| **Free tier** | **Free for non-commercial use** |
| **Rate limit** | Self-hosted version has no limits; hosted API has metered access |
| **Auth** | API key for hosted version |
| **Private companies** | **Yes -- includes sanctioned companies and their associates** |
| **Format** | REST, JSON (Follow the Money schema) |
| **Restrictions** | Non-commercial use free. Commercial use requires data license or API subscription |

**Best for:** Risk screening, sanctions/PEP checks, compliance data.

---

### 8. Google Patents Public Datasets (via BigQuery)

| Field | Details |
|---|---|
| **URL** | https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data |
| **Data provided** | Worldwide patent publications, patent classifications, citations, inventors, assignees, chemical compounds, patent litigation, standards-essential patents. 19 different datasets |
| **Free tier** | **1 TB of BigQuery queries free per month** (then $5/TB) |
| **Rate limit** | Standard BigQuery limits |
| **Auth** | Google Cloud account required |
| **Private companies** | **Yes -- patent assignees include private companies globally** |
| **Format** | SQL queries via BigQuery; REST API available |
| **Restrictions** | Requires Google Cloud account. Data is public domain but platform has usage limits |

**Best for:** Large-scale patent analytics, worldwide patent data, cross-referencing inventors and assignees.

---

## Tier 2: Generous Free Tiers

These have meaningful free tiers that allow real usage without paying.

---

### 9. OpenCorporates API

| Field | Details |
|---|---|
| **URL** | https://api.opencorporates.com/ |
| **Documentation** | https://api.opencorporates.com/documentation/API-Reference |
| **Data provided** | Company name, registration number, status, incorporation date, registered address, officers/directors, filings, corporate network/relationships, industry classifications. 200M+ companies across 140+ jurisdictions |
| **Free tier** | **Free for open-data projects** (share-alike license). 200 requests/month, 50/day for basic use |
| **Rate limit** | Throttled per IP address |
| **Auth** | API token (free registration for open-data use) |
| **Private companies** | **Yes -- covers private companies from government registries worldwide** |
| **Format** | REST, JSON |
| **Restrictions** | Free tier requires open-data share-alike license. Paid plans remove share-alike restriction. Commercial use requires paid plan |

**Best for:** Global company registry data, corporate officer lookups, entity verification.

---

### 10. Diffbot Knowledge Graph API

| Field | Details |
|---|---|
| **URL** | https://www.diffbot.com/products/knowledge-graph/ |
| **Data provided** | Organizations (246M+), people (1.6B), company descriptions, employee count, location, industry, revenue estimates, technologies used, social profiles, news mentions, executive bios. 10B+ entities total |
| **Free tier** | **10,000 credits/month** (perpetual, no credit card). 1 entity export = 25 credits = ~400 company lookups/month |
| **Rate limit** | Limited calls/second on free plan |
| **Auth** | API token (free account) |
| **Private companies** | **Yes -- extensive private company coverage** |
| **Format** | REST, JSON (DQL query language) |
| **Restrictions** | Free plan is limited in credits. No SLA. Commercial use allowed |

**Best for:** Company enrichment, employee data, tech stack detection, competitive intelligence.

---

### 11. Financial Modeling Prep (FMP) API

| Field | Details |
|---|---|
| **URL** | https://site.financialmodelingprep.com/developer/docs |
| **Data provided** | Company profiles, financial statements (income/balance/cash flow), ratios, employee counts (historical), M&A data, SEC filings, stock data, ESG scores |
| **Free tier** | **250 requests/day** |
| **Rate limit** | 250 requests/day, resets daily |
| **Auth** | API key (free registration) |
| **Private companies** | Limited -- primarily SEC-filing companies, but employee count and M&A data may reference private targets |
| **Format** | REST, JSON |
| **Restrictions** | Free plan has reduced coverage and delayed data for some endpoints |

**Best for:** Financial data, employee count trends, M&A transaction data.

---

### 12. Finnhub API

| Field | Details |
|---|---|
| **URL** | https://finnhub.io/ |
| **Data provided** | Company profiles, financial statements, earnings, insider transactions, ESG scores, congressional trading, SEC filings, news sentiment, earnings call transcripts, FDA calendar, lobbying data. 60+ global exchanges |
| **Free tier** | **60 API calls/minute** |
| **Rate limit** | 60 calls/minute |
| **Auth** | API key (free registration) |
| **Private companies** | **No -- primarily public company data** |
| **Format** | REST, JSON; WebSocket for real-time |
| **Restrictions** | "Financials As Reported" endpoint not available on free tier. Public companies focus |

**Best for:** Public company fundamentals, alternative data (ESG, lobbying, sentiment).

---

### 13. OpenAlex API

| Field | Details |
|---|---|
| **URL** | https://docs.openalex.org/ |
| **Data provided** | Research institutions/organizations (~109K), scholarly works (250M+), author affiliations, citation networks. Useful for identifying companies involved in academic research and R&D partnerships |
| **Free tier** | **100,000 requests/day** (transitioning to API key system as of 2025) |
| **Rate limit** | 100,000/day; "polite pool" for faster responses |
| **Auth** | API key (free, being rolled out 2025-2026) |
| **Private companies** | **Partially -- R&D-active companies that publish or fund research** |
| **Format** | REST, JSON |
| **Restrictions** | CC0 license. Data focuses on scholarly/research ecosystem |

**Best for:** Identifying corporate R&D activity, research partnerships, academic affiliations.

---

### 14. Lens.org Patent & Scholar API

| Field | Details |
|---|---|
| **URL** | https://www.lens.org/ |
| **API docs** | https://docs.api.lens.org/ |
| **Data provided** | Global patent data (100M+ records from 100+ jurisdictions), scholarly works (200M+), patent-to-paper citations, biological sequences in patents |
| **Free tier** | **Free for non-commercial/academic use** (trial access available for API) |
| **Rate limit** | Not publicly documented for API; web exports up to 50K records per download |
| **Auth** | Account registration; API access by request |
| **Private companies** | **Yes -- patent assignees include private companies globally** |
| **Format** | REST, JSON |
| **Restrictions** | API trial for non-commercial use. Commercial/production use requires paid plan |

**Best for:** Global patent analysis, patent-scholar linkage, biological patent sequences.

---

### 15. PQAI (Patent Quality AI) API

| Field | Details |
|---|---|
| **URL** | https://projectpq.ai/api/ |
| **Data provided** | Semantic patent search, CPC classification prediction, concept extraction. 11M+ US patents and 11.5M research papers |
| **Free tier** | **Free for individual use** (unlimited web searches; API has limits) |
| **Rate limit** | Not publicly documented for free tier |
| **Auth** | API key |
| **Private companies** | **Yes -- patent assignee data includes private companies** |
| **Format** | REST, JSON |
| **Restrictions** | Open-source, non-profit project by AT&T. Enterprise API is $700/month |

**Best for:** AI-powered semantic patent search, prior art analysis.

---

### 16. BuiltWith Free API

| Field | Details |
|---|---|
| **URL** | https://api.builtwith.com/free-api |
| **Data provided** | Technology groups and categories used by any website (CMS, analytics, CDN, frameworks, payment processors, etc.) |
| **Free tier** | **Free tier available** (limited to technology group counts and last-updated timestamps) |
| **Rate limit** | 1 request/second |
| **Auth** | API key (free) |
| **Private companies** | **Yes -- any company with a website** |
| **Format** | REST, JSON |
| **Restrictions** | Free tier provides limited data (counts only, not full tech details). Full API starts at $250/month |

**Best for:** Technology stack detection, competitive tech analysis.

---

### 17. Hunter.io API

| Field | Details |
|---|---|
| **URL** | https://hunter.io/api |
| **Data provided** | Email addresses associated with a domain, email verification, domain search (people at a company), company name from domain |
| **Free tier** | **25 searches + 50 verifications/month** |
| **Rate limit** | 15 requests/second, 500/minute |
| **Auth** | API key (free registration) |
| **Private companies** | **Yes -- works for any domain** |
| **Format** | REST, JSON |
| **Restrictions** | Very limited free tier. Email data focus, not comprehensive company data |

**Best for:** Finding contacts at companies, email verification.

---

## Tier 3: Limited Free Tiers

Evaluation-grade free access. Good for testing, not for production.

---

### 18. People Data Labs (PDL) API

| Field | Details |
|---|---|
| **URL** | https://www.peopledatalabs.com/ |
| **Data provided** | Person profiles (1.5B+), company profiles (millions), job titles, skills, education, company size, industry, location, funding info, technologies |
| **Free tier** | **100 person/company lookups per month + 25 IP lookups** (basic fields only) |
| **Rate limit** | Limited on free plan |
| **Auth** | API key (free registration) |
| **Private companies** | **Yes -- extensive private company coverage** |
| **Format** | REST, JSON |
| **Restrictions** | Free plan limited to basic fields. Premium fields require paid plan ($98+/month) |

**Best for:** People data enrichment, company firmographics (with paid plan).

---

### 19. Apollo.io API

| Field | Details |
|---|---|
| **URL** | https://docs.apollo.io/ |
| **Data provided** | Company profiles, employee data, email addresses, phone numbers, company news, technology stack, org charts |
| **Free tier** | **100 credits total** (not monthly). Up to 10,000 email credits/month with verified corporate domain |
| **Rate limit** | Varies by plan |
| **Auth** | API key (free account) |
| **Private companies** | **Yes** |
| **Format** | REST, JSON |
| **Restrictions** | 100 credits is very limited. CRM enrichment limited to 100 records/30 days on free plan |

**Best for:** Sales intelligence, contact finding (primarily with paid plan).

---

### 20. Coresignal API

| Field | Details |
|---|---|
| **URL** | https://coresignal.com/ |
| **Data provided** | Company data, employee data, historical headcount (9 years), job postings, company tech stack, employee reviews. Data sourced from public professional profiles |
| **Free tier** | **200 free credits** + 14-day trial (no credit card) |
| **Rate limit** | Trial-level limits |
| **Auth** | API key (free trial registration) |
| **Private companies** | **Yes -- extensive private company coverage** |
| **Format** | REST, JSON |
| **Restrictions** | Trial only. Production plans are paid (custom pricing) |

**Best for:** Employee headcount trends, growth signals, workforce analytics.

---

### 21. SimilarWeb API

| Field | Details |
|---|---|
| **URL** | https://developers.similarweb.com/ |
| **Data provided** | Website traffic estimates, bounce rate, visit duration, traffic sources, geographic distribution, competitor analysis, digital rankings |
| **Free tier** | **100 data credits/month** via DigitalRank API. API Lite being deprecated June 30, 2026 |
| **Rate limit** | Limited on free tier |
| **Auth** | API key |
| **Private companies** | **Yes -- any company with a website** |
| **Format** | REST, JSON |
| **Restrictions** | Free tier is very limited and shrinking. API Lite deprecating mid-2026. Full API requires enterprise sales contact |

**Best for:** Web traffic estimates, digital presence analysis (primarily with paid plan).

---

### 22. Abstract API (Company Enrichment)

| Field | Details |
|---|---|
| **URL** | https://www.abstractapi.com/api/company-enrichment |
| **Data provided** | Company name, domain, year founded, industry, employee count, locality, country, LinkedIn URL, logo |
| **Free tier** | **Free tier available** (generous allowance for testing; exact monthly limit unclear -- likely ~100 requests) |
| **Rate limit** | 1 request/second on free plan |
| **Auth** | API key (free registration) |
| **Private companies** | **Yes -- enrichment from LinkedIn, SEC, government databases** |
| **Format** | REST, JSON |
| **Restrictions** | Credit-based. Each request costs a credit whether or not data is found |

**Best for:** Quick company enrichment by domain or name.

---

### 23. The Companies API

| Field | Details |
|---|---|
| **URL** | https://www.thecompaniesapi.com/ |
| **Data provided** | 300+ data points per company: name, domain, description, industry, employee count, location, social profiles, technologies, funding info. 50M+ companies |
| **Free tier** | **500 free credits** (one-time, not monthly) at $0.00119/credit after |
| **Rate limit** | Standard API limits |
| **Auth** | API key (free registration) |
| **Private companies** | **Yes** |
| **Format** | REST, JSON |
| **Restrictions** | 500 credits is one-time. Real-time data refresh costs 10 credits/request |

**Best for:** Company enrichment with broad data points.

---

### 24. Proxycurl API

| Field | Details |
|---|---|
| **URL** | https://nubela.co/proxycurl/ |
| **Data provided** | LinkedIn profile data for people and companies, employee lists, job postings, company updates |
| **Free tier** | **100 free credits** (one-time trial) |
| **Rate limit** | Varies by plan |
| **Auth** | API key |
| **Private companies** | **Yes** |
| **Format** | REST, JSON |
| **Restrictions** | LinkedIn sent cease-and-desist in Jan 2025. Service may be at legal risk. Starts at $49/month |

**Best for:** LinkedIn data extraction (use with caution due to legal status).

---

## Tier 4: No Meaningful Free Tier

For reference only. These require payment for any API access.

---

### 25. Crunchbase API

| Field | Details |
|---|---|
| **URL** | https://www.crunchbase.com/ |
| **Data provided** | Startup/company profiles, funding rounds, investors, valuations, acquisitions, IPOs, board members, key people, company news |
| **Free tier** | **No free API access.** Free web account gives limited browsing only. API requires Enterprise plan ($50,000+/year) |
| **Private companies** | Yes -- the gold standard for startup/VC data |
| **Format** | REST, JSON |

---

### 26. Clearbit / HubSpot Breeze Intelligence

| Field | Details |
|---|---|
| **URL** | https://www.hubspot.com/products/artificial-intelligence/breeze-intelligence |
| **Data provided** | Company enrichment (industry, size, tech stack, social profiles), person enrichment |
| **Free tier** | **All free Clearbit tools shut down April 30, 2026.** Now HubSpot Breeze Intelligence starting at $45/month for 100 credits |
| **Private companies** | Yes |
| **Format** | REST, JSON (via HubSpot) |

---

### 27. LinkedIn Company API

| Field | Details |
|---|---|
| **URL** | https://developer.linkedin.com/ |
| **Data provided** | Company profiles, employee data, job postings |
| **Free tier** | **No public API access.** Requires LinkedIn Partner Program (incorporated companies only). Custom pricing |
| **Private companies** | Yes |
| **Format** | REST, JSON |

---

### 28. Glassdoor API

| Field | Details |
|---|---|
| **URL** | N/A (no official public API) |
| **Data provided** | Company reviews, ratings, salary data, CEO approval, benefits |
| **Free tier** | **No official API.** Third-party scrapers (Piloterr: 50 free credits; OpenWeb Ninja: free tier on RapidAPI) |
| **Private companies** | Yes (any company with reviews) |

---

### 29. PitchBook

| Field | Details |
|---|---|
| **URL** | https://pitchbook.com/ |
| **Data provided** | Comprehensive private company data, PE/VC deals, valuations, M&A |
| **Free tier** | **None. $12,000-$15,000/user/year** |
| **Private companies** | Yes -- premium private market data |

---

## Coverage Matrix

| Data Category | Best Free APIs | Coverage Quality |
|---|---|---|
| **Company basics** (founding, HQ, employees, status) | Companies House, BRREG, OpenCorporates, Wikidata, GLEIF, SEC EDGAR | HIGH for registered companies |
| **Funding data** (rounds, amounts, investors) | Wikidata (limited), FMP (public M&A) | LOW -- Crunchbase is pay-only |
| **People** (executives, board, advisors) | Companies House (officers), SEC EDGAR (proxy filings), OpenCorporates, Wikidata | MEDIUM for directors; LOW for advisors |
| **Financials** (revenue, metrics) | SEC EDGAR (SEC filers), Companies House (UK filings), FMP, Finnhub | HIGH for public; MEDIUM for UK private |
| **Patents/IP** | USPTO PatentsView, Google Patents BigQuery, Lens.org, PQAI | HIGH |
| **M&A/Acquisitions** | SEC EDGAR (filings), FMP, Wikidata | MEDIUM for public deals; LOW for private |
| **Growth signals** (employee trends, traffic) | Coresignal (trial), SimilarWeb (limited), FMP (employee counts) | LOW on free tiers |
| **Business relationships** | GLEIF (ownership), OpenCorporates (corporate network), Diffbot | MEDIUM |

---

## Recommended Stack for Maximum Free Coverage

### Core (Always Free)

1. **SEC EDGAR** -- US financials, filings, officer data (unlimited free)
2. **Companies House** -- UK company data, officers, financials (unlimited free)
3. **USPTO PatentsView** -- US patent data (unlimited free)
4. **Wikidata SPARQL** -- Global company basics for notable companies (unlimited free)
5. **GLEIF** -- Legal entity verification, corporate hierarchy (unlimited free)

### Supplementary (Free Tier)

6. **OpenCorporates** -- Global company registry data (200 req/month free for open-data projects)
7. **Diffbot Knowledge Graph** -- Company enrichment, tech stack, news (~400 company lookups/month free)
8. **Financial Modeling Prep** -- Financials, employee counts, M&A (250 req/day)
9. **Google Patents BigQuery** -- Global patent analytics (1 TB/month free)

### Growth Signals (Trial/Limited)

10. **Coresignal** -- Employee headcount trends (200 credits trial)
11. **BuiltWith** -- Technology detection (free tier, limited data)
12. **SimilarWeb** -- Web traffic estimates (100 credits/month, deprecating)

### People/Contact Data (Very Limited)

13. **Hunter.io** -- Email finding (25 searches/month)
14. **People Data Labs** -- Person/company enrichment (100 lookups/month)
15. **Apollo.io** -- Contact data (100 credits one-time)

---

## API Authentication Summary

| API | Auth Type | Registration Required |
|---|---|---|
| SEC EDGAR | User-Agent header only | No |
| Companies House | API key | Yes (free) |
| USPTO PatentsView | API key | Yes (free) |
| Wikidata | None | No |
| GLEIF | None | No |
| BRREG | None | No |
| OpenCorporates | API token | Yes (free for open data) |
| Diffbot | API token | Yes (free account) |
| FMP | API key | Yes (free) |
| Finnhub | API key | Yes (free) |
| OpenAlex | API key (transitioning) | Yes (free) |
| BuiltWith | API key | Yes (free) |
| Hunter.io | API key | Yes (free) |
| PDL | API key | Yes (free) |
| Apollo.io | API key | Yes (free) |

---

## Key Gaps in Free Coverage

1. **Funding data** -- The biggest gap. Crunchbase, PitchBook, and Dealroom all require paid plans. Wikidata has some funding data for major startups but is incomplete. No truly free API covers startup funding rounds comprehensively.

2. **Revenue estimates for private companies** -- Essentially unavailable for free. Diffbot's free tier provides some estimates. UK Companies House filings contain actual financials for UK private companies.

3. **Employee growth trends** -- Coresignal provides historical headcount but only as a trial. No free API offers ongoing employee trend data.

4. **Business relationships/partnerships** -- Extremely sparse in free APIs. Diffbot and OpenCorporates provide some relationship data. Press release mining via SEC EDGAR full-text search is one workaround.

5. **Web traffic data** -- SimilarWeb is deprecating its free tier. No good free alternative exists.

---

## Sources

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Companies House API](https://developer.company-information.service.gov.uk/)
- [USPTO PatentsView](https://patentsview.org/)
- [USPTO Open Data Portal](https://developer.uspto.gov/api-catalog)
- [Wikidata SPARQL](https://query.wikidata.org/)
- [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api)
- [BRREG Datasets](https://www.brreg.no/en/use-of-data-from-the-bronnoysund-register-centre/datasets-and-api/)
- [OpenCorporates API](https://api.opencorporates.com/)
- [Diffbot Pricing](https://www.diffbot.com/pricing/)
- [Diffbot Credits](https://docs.diffbot.com/docs/how-credits-work)
- [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs)
- [Finnhub API](https://finnhub.io/docs/api)
- [OpenAlex API](https://docs.openalex.org/)
- [Lens.org](https://about.lens.org/)
- [PQAI API](https://projectpq.ai/api/)
- [BuiltWith Free API](https://api.builtwith.com/free-api)
- [Hunter.io API](https://hunter.io/api)
- [People Data Labs Pricing](https://www.peopledatalabs.com/pricing/company)
- [Apollo.io API Pricing](https://docs.apollo.io/docs/api-pricing)
- [Coresignal](https://coresignal.com/)
- [SimilarWeb API](https://developers.similarweb.com/)
- [Abstract API](https://www.abstractapi.com/api/company-enrichment)
- [The Companies API](https://www.thecompaniesapi.com/)
- [OpenSanctions](https://www.opensanctions.org/api/)
- [Google Patents BigQuery](https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data)
- [Crunchbase Pricing](https://support.crunchbase.com/hc/en-us/articles/360062989313)
- [Clearbit/Breeze Intelligence](https://www.warmly.ai/p/blog/clearbit-pricing)
- [Proxycurl](https://nubela.co/proxycurl/)
- [Zephira.ai](https://zephira.ai/api/)
