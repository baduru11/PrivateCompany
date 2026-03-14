"""
Pydantic schemas for the Private Company Intelligence Agent.

All models enforce source-grounding validators to prevent hallucination:
if a factual field is populated, a corresponding source URL must be provided.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Lenient validators — LLMs sometimes return out-of-range values.  Clamping
# is better than rejecting the entire object (and losing all structured data).
# ---------------------------------------------------------------------------

def _clamp_unit(v, default: float = 0.0) -> float:
    """Clamp to [0.0, 1.0]."""
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return default


def _clamp_int(v, lo: int, hi: int, default: int = 0) -> int:
    """Clamp integer to [lo, hi]."""
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _normalize_literal(v, valid: set[str], default: str) -> str:
    """Normalize a string to a valid Literal member."""
    if isinstance(v, str):
        low = v.lower().strip()
        if low in valid:
            return low
    return default


class SearchPlan(BaseModel):
    search_terms: list[str]
    target_company_count: int = 15
    sub_sectors: list[str] = []


class RawCompanySignal(BaseModel):
    company_name: str
    url: str
    snippet: str
    source: Literal["tavily", "exa", "serper"]
    metadata: dict = {}


class CompanyProfile(BaseModel):
    name: str = ""
    description: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    crunchbase_url: Optional[str] = None
    funding_total: Optional[str] = None
    funding_source_url: Optional[str] = None
    funding_confidence: float = 0.0
    funding_stage: Optional[str] = None
    funding_stage_source_url: Optional[str] = None
    key_investors: list[str] = []
    founding_year: Optional[int] = None
    founding_month: Optional[str] = None  # e.g. "March", "2023-03"
    founding_year_source_url: Optional[str] = None
    headcount_estimate: Optional[str] = None
    headquarters: Optional[str] = None
    core_product: Optional[str] = None
    core_technology: Optional[str] = None
    key_people: list[dict] = []
    recent_news: list[dict] = []
    sub_sector: Optional[str] = None
    raw_sources: list[str] = []
    # Due diligence enrichment
    market_tam: Optional[str] = None
    market_tam_source_url: Optional[str] = None
    business_model: Optional[str] = None
    revenue_indicators: Optional[str] = None
    customer_signals: Optional[str] = None
    competitive_advantages: Optional[str] = None
    regulatory_environment: Optional[str] = None
    competitors_mentioned: list[dict] = []
    # Investment report upgrade fields
    board_members: list[dict] = []
    advisors: list[dict] = []
    partnerships: list[dict] = []
    key_customers: list[dict] = []
    acquisitions: list[dict] = []
    patents: list[dict] = []
    revenue_estimate: Optional[dict] = None
    employee_count_history: list[dict] = []
    operating_status: Optional[str] = None

    @field_validator("funding_confidence", mode="before")
    @classmethod
    def _clamp_funding_confidence(cls, v):
        return _clamp_unit(v)

    @model_validator(mode="after")
    def funding_must_have_source(self):
        if self.funding_total and not self.funding_source_url:
            # Don't raise — LLMs often omit source URLs. Losing the entire
            # profile over a missing source URL is far worse than having
            # unverified funding data. The critic node will flag it.
            self.funding_confidence = 0.0
        return self


class Citation(BaseModel):
    id: int
    url: str
    snippet: str = ""
    extracted_at: Optional[str] = None


class ExploreCompany(BaseModel):
    name: str
    sub_sector: str = "Unknown"
    website: Optional[str] = None
    funding_total: Optional[str] = None
    funding_numeric: float = 0.0
    funding_stage: Optional[str] = None
    founding_year: Optional[int] = None
    headquarters: Optional[str] = None
    key_investors: list[str] = []
    description: Optional[str] = None
    confidence: float = 0.0
    source_count: int = 0

    @field_validator("founding_year", mode="before")
    @classmethod
    def _coerce_founding_year(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return None

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v)


class ExploreReport(BaseModel):
    query: str
    sector: str
    companies: list[ExploreCompany]
    sub_sectors: list[str]
    summary: str
    citations: list[Citation] = []


class DeepDiveSection(BaseModel):
    title: str
    content: str
    confidence: float = 0.0
    source_urls: list[str] = []
    source_count: int = 0

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v)


class SectionProse(BaseModel):
    """Output schema for a single section's parallel LLM call."""
    content: str
    confidence: float = 0.5
    source_urls: list[str] = []
    source_count: int = 0

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v, 0.5)


class FundingRound(BaseModel):
    date: Optional[str] = None
    stage: Optional[str] = None
    amount: Optional[str] = None
    investors: list[str] = []
    lead_investor: Optional[str] = None
    pre_money_valuation: Optional[str] = None
    post_money_valuation: Optional[str] = None
    source_url: Optional[str] = None


class NewsItem(BaseModel):
    title: str
    date: Optional[str] = None
    source_url: Optional[str] = None
    snippet: str
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"

    @field_validator("sentiment", mode="before")
    @classmethod
    def _normalize_sentiment(cls, v):
        return _normalize_literal(v, {"positive", "neutral", "negative"}, "neutral")


class CompetitorEntry(BaseModel):
    name: str
    description: Optional[str] = None
    funding: Optional[str] = None
    funding_stage: Optional[str] = None
    differentiator: Optional[str] = None
    overlap: Optional[str] = None
    website: Optional[str] = None
    source_url: Optional[str] = None


class PersonEntry(BaseModel):
    name: str
    title: Optional[str] = None
    background: Optional[str] = None
    source_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    prior_exits: list[str] = []
    domain_expertise_years: Optional[int] = None
    notable_affiliations: list[str] = []


class RiskEntry(BaseModel):
    category: Literal["regulatory", "market", "technology", "team", "financial", "competitive"] = "market"
    content: str
    severity: Literal["low", "medium", "high"] = "medium"
    confidence: float = 0.5
    source_urls: list[str] = []

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, v):
        return _normalize_literal(
            v, {"regulatory", "market", "technology", "team", "financial", "competitive"}, "market"
        )

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v):
        return _normalize_literal(v, {"low", "medium", "high"}, "medium")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v, 0.5)


class RedFlag(BaseModel):
    content: str
    severity: Literal["low", "medium", "high"] = "medium"
    confidence: float = 0.5
    source_urls: list[str] = []

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v):
        return _normalize_literal(v, {"low", "medium", "high"}, "medium")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v, 0.5)


class InvestmentScore(BaseModel):
    overall: int = 0
    money: int = 0
    market: int = 0
    momentum: int = 0
    management: int = 0
    rationale: str = ""

    @field_validator("money", "market", "momentum", "management", mode="before")
    @classmethod
    def _clamp_sub_scores(cls, v):
        return _clamp_int(v, 0, 25)

    @field_validator("overall", mode="before")
    @classmethod
    def _clamp_overall(cls, v):
        return _clamp_int(v, 0, 100)

    @model_validator(mode="after")
    def enforce_overall_sum(self) -> "InvestmentScore":
        """Ensure overall == sum of sub-scores. LLMs sometimes get arithmetic wrong."""
        self.overall = self.money + self.market + self.momentum + self.management
        return self


class BoardMember(BaseModel):
    name: str
    role: Optional[str] = None  # "Chair", "Member", "Observer"
    organization: Optional[str] = None
    background: Optional[str] = None
    linkedin_url: Optional[str] = None
    source_url: Optional[str] = None


class Advisor(BaseModel):
    name: str
    expertise: Optional[str] = None
    organization: Optional[str] = None
    linkedin_url: Optional[str] = None
    source_url: Optional[str] = None


class Partnership(BaseModel):
    partner_name: str
    type: Optional[str] = None  # "strategic", "customer", "technology", "distribution"
    description: Optional[str] = None
    date: Optional[str] = None
    source_url: Optional[str] = None


class KeyCustomer(BaseModel):
    name: str
    description: Optional[str] = None
    source_url: Optional[str] = None


class Acquisition(BaseModel):
    acquired_company: str
    date: Optional[str] = None
    amount: Optional[str] = None
    rationale: Optional[str] = None
    source_url: Optional[str] = None


class Patent(BaseModel):
    title: str
    filing_date: Optional[str] = None
    status: Optional[str] = None  # "granted", "pending"
    domain: Optional[str] = None
    patent_number: Optional[str] = None
    source_url: Optional[str] = None


class RevenueEstimate(BaseModel):
    range: Optional[str] = None  # "$5M-$10M ARR"
    growth_rate: Optional[str] = None  # "~50% YoY"
    source_url: Optional[str] = None
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v)


class EmployeeCountPoint(BaseModel):
    date: str  # "2024-01", "2025-06"
    count: int
    source: Optional[str] = None  # "diffbot", "linkedin", "web"


class DeepDiveReport(BaseModel):
    query: str
    company_name: str
    founded: Optional[str] = None
    headquarters: Optional[str] = None
    headcount: Optional[str] = None
    funding_stage: Optional[str] = None
    linkedin_url: Optional[str] = None
    crunchbase_url: Optional[str] = None
    logo_url: Optional[str] = None
    operating_status: Optional[str] = None  # "Active", "Acquired", "Closed", "IPO"
    total_funding: Optional[str] = None
    investment_score: Optional[InvestmentScore] = None
    revenue_estimate: Optional[RevenueEstimate] = None
    overview: DeepDiveSection
    funding: DeepDiveSection
    funding_rounds: list[FundingRound] = []
    key_people: DeepDiveSection
    people_entries: list[PersonEntry] = []
    product_technology: DeepDiveSection
    recent_news: DeepDiveSection
    news_items: list[NewsItem] = []
    competitors: DeepDiveSection
    competitor_entries: list[CompetitorEntry] = []
    red_flags: DeepDiveSection
    red_flag_entries: list[RedFlag] = []
    # Governance
    governance: Optional[DeepDiveSection] = None
    board_members: list[BoardMember] = []
    advisors: list[Advisor] = []
    # Traction & activity
    partnerships: list[Partnership] = []
    key_customers: list[KeyCustomer] = []
    acquisitions: list[Acquisition] = []
    patents: list[Patent] = []
    employee_count_history: list[EmployeeCountPoint] = []
    # Due diligence sections
    market_opportunity: Optional[DeepDiveSection] = None
    business_model: Optional[DeepDiveSection] = None
    competitive_advantages: Optional[DeepDiveSection] = None
    traction: Optional[DeepDiveSection] = None
    risks: Optional[DeepDiveSection] = None
    risk_entries: list[RiskEntry] = []
    citations: list[Citation] = []


class CriticVerification(BaseModel):
    field: str
    status: Literal["verified", "unverified", "conflicting", "missing"] = "unverified"
    source_url: Optional[str] = None
    note: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v):
        return _normalize_literal(
            v, {"verified", "unverified", "conflicting", "missing"}, "unverified"
        )


class CriticReport(BaseModel):
    overall_confidence: float = 0.0
    section_scores: dict[str, float] = {}
    verifications: list[CriticVerification] = []
    gaps: list[str] = []
    should_retry: bool = False
    retry_queries: list[str] = []
    low_confidence_sections: list[str] = []

    @field_validator("overall_confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        return _clamp_unit(v)


class StatusEvent(BaseModel):
    node: str
    status: Literal["running", "complete", "error", "retrying"]
    detail: str
