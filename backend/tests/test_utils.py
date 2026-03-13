from backend.models import FundingRound
from backend.utils import deduplicate_funding_rounds


def test_deduplicate_removes_same_amount_and_stage():
    rounds = [
        FundingRound(date="2025-06", stage="Seed", amount="$15M", investors=["Investor A"]),
        FundingRound(date="2025-06-23", stage="Seed", amount="$15M", investors=["Investor A", "Investor B"]),
    ]
    result = deduplicate_funding_rounds(rounds)
    assert len(result) == 1
    assert result[0].date == "2025-06-23"  # more specific date kept


def test_deduplicate_keeps_different_stages():
    rounds = [
        FundingRound(date="2024-01", stage="Seed", amount="$5M", investors=[]),
        FundingRound(date="2024-06", stage="Series A", amount="$20M", investors=[]),
    ]
    result = deduplicate_funding_rounds(rounds)
    assert len(result) == 2


def test_deduplicate_empty_list():
    assert deduplicate_funding_rounds([]) == []
