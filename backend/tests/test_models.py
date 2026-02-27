# backend/tests/test_models.py
import pytest
from pydantic import ValidationError
from backend.models import (
    SearchPlan, RawCompanySignal, CompanyProfile,
    ExploreReport, DeepDiveReport, CriticVerification,
    CriticReport, StatusEvent, ExploreCompany,
    DeepDiveSection, FundingRound, NewsItem, CompetitorEntry
)

def test_company_profile_requires_source_for_funding():
    """If funding_total is set, funding_source_url must exist."""
    with pytest.raises(ValidationError):
        CompanyProfile(
            name="TestCo",
            funding_total="$10M",
            funding_source_url=None,
            funding_confidence=0.8
        )

def test_company_profile_allows_missing_funding():
    """If funding_total is None, no source needed."""
    profile = CompanyProfile(name="TestCo")
    assert profile.funding_total is None
    assert profile.funding_confidence == 0.0

def test_company_profile_valid_with_source():
    profile = CompanyProfile(
        name="TestCo",
        funding_total="$10M",
        funding_source_url="https://example.com",
        funding_confidence=0.9
    )
    assert profile.name == "TestCo"

def test_confidence_score_bounded():
    with pytest.raises(ValidationError):
        CompanyProfile(name="TestCo", funding_confidence=1.5)

def test_search_plan_structure():
    plan = SearchPlan(
        search_terms=["AI chips", "inference hardware"],
        target_company_count=15,
        sub_sectors=["GPU", "ASIC", "FPGA"]
    )
    assert len(plan.search_terms) == 2

def test_status_event_structure():
    event = StatusEvent(node="searcher", status="running", detail="Searching...")
    assert event.node == "searcher"

def test_explore_company():
    c = ExploreCompany(name="TestCo", sub_sector="GPU", funding_numeric=10.0)
    assert c.confidence == 0.0

def test_deep_dive_section():
    s = DeepDiveSection(title="Overview", content="Test", confidence=0.8, source_urls=["https://x.com"])
    assert s.source_count == 0  # default

def test_funding_round():
    r = FundingRound(stage="Series A", amount="$10M", investors=["a16z"])
    assert len(r.investors) == 1

def test_news_item_sentiment():
    n = NewsItem(title="Good news", snippet="Things are good", sentiment="positive")
    assert n.sentiment == "positive"

def test_critic_report():
    c = CriticReport(overall_confidence=0.75, gaps=["missing headcount"])
    assert c.should_retry is False

def test_raw_company_signal():
    s = RawCompanySignal(company_name="Test", url="https://test.com", snippet="desc", source="tavily")
    assert s.source == "tavily"
