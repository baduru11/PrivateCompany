"""
Pydantic schemas for the Private Company Intelligence Agent.

All models enforce source-grounding validators to prevent hallucination:
if a factual field is populated, a corresponding source URL must be provided.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class SearchPlan(BaseModel):
    search_terms: list[str]
    target_company_count: int = 15
    sub_sectors: list[str] = []


class RawCompanySignal(BaseModel):
    company_name: str
    url: str
    snippet: str
    source: Literal["tavily", "exa"]
    metadata: dict = {}


class CompanyProfile(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    funding_total: Optional[str] = None
    funding_source_url: Optional[str] = None
    funding_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    funding_stage: Optional[str] = None
    funding_stage_source_url: Optional[str] = None
    key_investors: list[str] = []
    founding_year: Optional[int] = None
    founding_year_source_url: Optional[str] = None
    headcount_estimate: Optional[str] = None
    headquarters: Optional[str] = None
    core_product: Optional[str] = None
    core_technology: Optional[str] = None
    key_people: list[dict] = []
    recent_news: list[dict] = []
    sub_sector: Optional[str] = None
    raw_sources: list[str] = []

    @model_validator(mode="after")
    def funding_must_have_source(self):
        if self.funding_total and not self.funding_source_url:
            raise ValueError("funding_total set without funding_source_url")
        return self


class ExploreCompany(BaseModel):
    name: str
    sub_sector: str = "Unknown"
    funding_total: Optional[str] = None
    funding_numeric: float = 0.0
    founding_year: Optional[int] = None
    description: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_count: int = 0


class ExploreReport(BaseModel):
    query: str
    sector: str
    companies: list[ExploreCompany]
    sub_sectors: list[str]
    summary: str


class DeepDiveSection(BaseModel):
    title: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_urls: list[str] = []
    source_count: int = 0


class FundingRound(BaseModel):
    date: Optional[str] = None
    stage: Optional[str] = None
    amount: Optional[str] = None
    investors: list[str] = []
    source_url: Optional[str] = None


class NewsItem(BaseModel):
    title: str
    date: Optional[str] = None
    source_url: Optional[str] = None
    snippet: str
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"


class CompetitorEntry(BaseModel):
    name: str
    description: Optional[str] = None
    funding: Optional[str] = None
    differentiator: Optional[str] = None


class DeepDiveReport(BaseModel):
    query: str
    company_name: str
    overview: DeepDiveSection
    funding: DeepDiveSection
    funding_rounds: list[FundingRound] = []
    key_people: DeepDiveSection
    product_technology: DeepDiveSection
    recent_news: DeepDiveSection
    news_items: list[NewsItem] = []
    competitors: DeepDiveSection
    competitor_entries: list[CompetitorEntry] = []
    red_flags: DeepDiveSection


class CriticVerification(BaseModel):
    field: str
    status: Literal["verified", "unverified", "conflicting", "missing"]
    source_url: Optional[str] = None
    note: Optional[str] = None


class CriticReport(BaseModel):
    overall_confidence: float = Field(ge=0.0, le=1.0)
    section_scores: dict[str, float] = {}
    verifications: list[CriticVerification] = []
    gaps: list[str] = []
    should_retry: bool = False
    retry_queries: list[str] = []


class StatusEvent(BaseModel):
    node: str
    status: Literal["running", "complete", "error", "retrying"]
    detail: str
