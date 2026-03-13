# backend/tests/test_critic.py
import pytest
from unittest.mock import MagicMock, patch
from backend.models import (
    CriticReport,
    CriticVerification,
    RawCompanySignal,
    DeepDiveReport,
    DeepDiveSection,
)


def _make_deep_dive_report() -> DeepDiveReport:
    """Helper to create a mock DeepDiveReport for critic tests."""
    section = DeepDiveSection(
        title="Overview",
        content="Acme Corp is an AI company.",
        confidence=0.9,
        source_urls=["https://acme.com"],
        source_count=1,
    )
    return DeepDiveReport(
        query="Acme Corp",
        company_name="Acme Corp",
        overview=section,
        funding=DeepDiveSection(
            title="Funding History",
            content="Raised $10M Series A.",
            confidence=0.8,
            source_urls=["https://crunchbase.com/acme"],
            source_count=1,
        ),
        key_people=DeepDiveSection(
            title="Key People",
            content="CEO: John Doe",
            confidence=0.7,
            source_urls=["https://linkedin.com/johndoe"],
            source_count=1,
        ),
        product_technology=DeepDiveSection(
            title="Product/Technology",
            content="NLP platform for enterprise.",
            confidence=0.85,
            source_urls=["https://acme.com/product"],
            source_count=1,
        ),
        recent_news=DeepDiveSection(
            title="Recent News",
            content="Acme announced new partnership.",
            confidence=0.6,
            source_urls=["https://techcrunch.com/acme"],
            source_count=1,
        ),
        competitors=DeepDiveSection(
            title="Competitors",
            content="Beta Inc, Gamma Ltd.",
            confidence=0.5,
            source_urls=[],
            source_count=0,
        ),
        red_flags=DeepDiveSection(
            title="Red Flags",
            content="Data not available",
            confidence=0.0,
            source_urls=[],
            source_count=0,
        ),
    )


def _make_raw_signals() -> list[RawCompanySignal]:
    """Helper to create mock raw signals."""
    return [
        RawCompanySignal(
            company_name="Acme Corp",
            url="https://acme.com",
            snippet="Acme Corp is an AI company founded in 2020.",
            source="tavily",
        ),
        RawCompanySignal(
            company_name="Acme Corp",
            url="https://crunchbase.com/acme",
            snippet="Acme Corp raised $10M in a Series A round.",
            source="exa",
        ),
        RawCompanySignal(
            company_name="Acme Corp",
            url="https://techcrunch.com/acme",
            snippet="Acme Corp announces new enterprise partnership.",
            source="tavily",
        ),
    ]


class TestCriticHappyPath:
    """Tests for the basic critic functionality."""

    def test_critic_returns_report_with_confidence(self):
        """critique() returns a CriticReport with confidence scores in state['critic_report']."""
        from backend.nodes.critic import critique

        report = _make_deep_dive_report()
        raw_signals = _make_raw_signals()

        expected_critic = CriticReport(
            overall_confidence=0.75,
            section_scores={
                "overview": 0.9,
                "funding": 0.8,
                "key_people": 0.7,
                "product_technology": 0.85,
                "recent_news": 0.6,
                "competitors": 0.3,
                "red_flags": 0.0,
            },
            verifications=[
                CriticVerification(
                    field="overview",
                    status="verified",
                    source_url="https://acme.com",
                    note="Matches raw source",
                ),
            ],
            gaps=["No competitor funding data"],
            should_retry=False,
            retry_queries=[],
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            result = critique({
                "report": report,
                "raw_signals": raw_signals,
                "company_profiles": [],
            })

        assert "critic_report" in result
        assert isinstance(result["critic_report"], CriticReport)
        assert result["critic_report"].overall_confidence == 0.75
        assert result["critic_report"].section_scores["overview"] == 0.9
        assert result["critic_report"].should_retry is False
        # No retry keys in result (pipeline is linear)
        assert "retry_count" not in result
        assert "retry_targets" not in result
        # Verify LLM was called with CriticReport schema
        mock_llm.with_structured_output.assert_called_once_with(CriticReport)
        mock_structured.invoke.assert_called_once()

    def test_critic_passes_report_and_sources_in_prompt(self):
        """The prompt sent to the LLM contains both the report and raw source data."""
        from backend.nodes.critic import critique

        report = _make_deep_dive_report()
        raw_signals = _make_raw_signals()

        expected_critic = CriticReport(
            overall_confidence=0.75,
            section_scores={},
            verifications=[],
            gaps=[],
            should_retry=False,
            retry_queries=[],
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            critique({
                "report": report,
                "raw_signals": raw_signals,
                "company_profiles": [],
            })

        call_args = mock_structured.invoke.call_args[0][0]
        user_msg = call_args[1].content
        # Report content should be in the prompt
        assert "Acme Corp" in user_msg
        # Raw source URLs should be in the prompt (snippets are no longer sent)
        assert "https://acme.com" in user_msg

    def test_critic_uses_system_prompt(self):
        """The system message sent to the LLM is CRITIC_SYSTEM."""
        from backend.nodes.critic import critique, CRITIC_SYSTEM

        report = _make_deep_dive_report()

        expected_critic = CriticReport(
            overall_confidence=0.5,
            section_scores={},
            should_retry=False,
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            critique({
                "report": report,
                "raw_signals": [],
            })

        call_args = mock_structured.invoke.call_args[0][0]
        system_msg = call_args[0].content
        assert system_msg == CRITIC_SYSTEM


class TestCriticNoRetry:
    """Tests that the critic never requests a retry (pipeline is linear)."""

    def test_critic_forces_should_retry_false_even_when_llm_says_true(self):
        """should_retry is always forced to False regardless of LLM output."""
        from backend.nodes.critic import critique

        report = _make_deep_dive_report()
        raw_signals = _make_raw_signals()

        # LLM identifies critical gaps and recommends retry
        gap_critic = CriticReport(
            overall_confidence=0.25,
            section_scores={
                "overview": 0.3,
                "funding": 0.2,
                "key_people": 0.1,
                "product_technology": 0.3,
                "recent_news": 0.2,
                "competitors": 0.1,
                "red_flags": 0.0,
            },
            verifications=[
                CriticVerification(
                    field="funding",
                    status="unverified",
                    note="Funding amount not found in any raw source",
                ),
            ],
            gaps=[
                "No verified funding data",
                "Key people section entirely unsourced",
                "Product details missing from raw sources",
                "Competitor data fabricated",
            ],
            should_retry=True,
            retry_queries=[
                "Acme Corp funding rounds 2024",
                "Acme Corp leadership team",
            ],
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = gap_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            result = critique({
                "report": report,
                "raw_signals": raw_signals,
                "company_profiles": [],
            })

        # should_retry is always forced to False (linear pipeline)
        assert result["critic_report"].should_retry is False
        # Gaps and queries are preserved for informational purposes
        assert len(result["critic_report"].gaps) == 4
        # No retry_count or retry_targets in result
        assert "retry_count" not in result
        assert "retry_targets" not in result


class TestCriticEdgeCases:
    """Tests for edge cases in the critic node."""

    def test_critic_handles_no_raw_signals(self):
        """critique() works when raw_signals is empty or missing."""
        from backend.nodes.critic import critique

        report = _make_deep_dive_report()

        expected_critic = CriticReport(
            overall_confidence=0.3,
            section_scores={},
            gaps=["No raw sources to verify against"],
            should_retry=False,
            retry_queries=["Acme Corp"],
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            result = critique({
                "report": report,
            })

        # Should still produce a valid critic report
        assert "critic_report" in result
        assert isinstance(result["critic_report"], CriticReport)
        # The "No raw signals available" fallback should appear in the prompt
        call_args = mock_structured.invoke.call_args[0][0]
        user_msg = call_args[1].content
        assert "No raw signals available" in user_msg

    def test_critic_handles_string_report(self):
        """critique() works when report is a plain string instead of a Pydantic model."""
        from backend.nodes.critic import critique

        expected_critic = CriticReport(
            overall_confidence=0.5,
            section_scores={},
            should_retry=False,
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            result = critique({
                "report": "This is a plain text report about Acme Corp.",
                "raw_signals": [],
            })

        assert "critic_report" in result
        call_args = mock_structured.invoke.call_args[0][0]
        user_msg = call_args[1].content
        assert "This is a plain text report about Acme Corp." in user_msg

    def test_critic_returns_only_critic_report_key(self):
        """critique() should return only the critic_report key, no retry state."""
        from backend.nodes.critic import critique

        report = _make_deep_dive_report()

        expected_critic = CriticReport(
            overall_confidence=0.8,
            section_scores={},
            should_retry=False,
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_critic
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            result = critique({
                "report": report,
            })

        assert set(result.keys()) == {"critic_report"}


class TestCriticErrorHandling:
    def test_raises_descriptive_error_on_llm_failure(self):
        """Critic should raise a clear error when LLM fails."""
        from backend.nodes.critic import critique

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.side_effect = Exception("API timeout")
        mock_llm.with_structured_output.return_value = mock_structured

        report = _make_deep_dive_report()

        with patch("backend.nodes.critic.get_llm", return_value=mock_llm):
            with pytest.raises(RuntimeError, match="Critic failed"):
                critique({"report": report})


class TestCriticTargetedRetry:
    def test_populates_low_confidence_sections(self):
        """Critic should list sections with confidence < 0.4."""
        from backend.models import CriticReport
        critic_report = CriticReport(
            overall_confidence=0.5,
            section_scores={
                "overview": 0.8,
                "funding": 0.3,
                "key_people": 0.2,
                "product_technology": 0.7,
                "recent_news": 0.6,
                "competitors": 0.35,
                "red_flags": 0.5,
            },
            verifications=[],
            gaps=["funding details", "leadership team"],
            should_retry=False,
            low_confidence_sections=["funding", "key_people", "competitors"],
        )
        assert critic_report.low_confidence_sections == ["funding", "key_people", "competitors"]

    def test_should_retry_true_when_low_confidence_sections_exist(self):
        """should_retry should be True when 3+ sections are below 0.4."""
        from backend.models import CriticReport
        report = CriticReport(
            overall_confidence=0.4,
            section_scores={
                "overview": 0.8,
                "funding": 0.2,
                "key_people": 0.3,
                "product_technology": 0.3,
                "recent_news": 0.6,
                "competitors": 0.5,
                "red_flags": 0.5,
            },
            low_confidence_sections=["funding", "key_people", "product_technology"],
            should_retry=True,
        )
        assert report.should_retry is True
        assert len(report.low_confidence_sections) == 3
