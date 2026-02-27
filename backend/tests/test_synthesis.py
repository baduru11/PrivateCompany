# backend/tests/test_synthesis.py
import pytest
from unittest.mock import MagicMock, patch, call
from backend.models import (
    CompanyProfile,
    ExploreReport,
    ExploreCompany,
    DeepDiveReport,
    DeepDiveSection,
)


def _make_profile(name: str, **kwargs) -> CompanyProfile:
    """Helper to create a CompanyProfile for tests."""
    return CompanyProfile(name=name, **kwargs)


def _make_explore_report(query: str = "AI startups") -> ExploreReport:
    """Helper to create a mock ExploreReport."""
    return ExploreReport(
        query=query,
        sector="Artificial Intelligence",
        companies=[
            ExploreCompany(
                name="Acme Corp",
                sub_sector="NLP",
                funding_total="$10M",
                funding_numeric=10_000_000.0,
                founding_year=2020,
                description="Acme builds NLP tools",
                confidence=0.8,
                source_count=3,
            ),
        ],
        sub_sectors=["NLP", "Computer Vision"],
        summary="The AI startup landscape includes several emerging players.",
    )


def _make_deep_dive_report(query: str = "Acme Corp") -> DeepDiveReport:
    """Helper to create a mock DeepDiveReport."""
    section = DeepDiveSection(
        title="Overview",
        content="Acme Corp is an AI company.",
        confidence=0.9,
        source_urls=["https://acme.com"],
        source_count=1,
    )
    return DeepDiveReport(
        query=query,
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


class TestSynthesisExplore:
    """Tests for explore mode synthesis."""

    def test_synthesis_explore_returns_explore_report(self):
        """synthesize() in explore mode returns an ExploreReport in state['report']."""
        from backend.nodes.synthesis import synthesize

        profiles = [
            _make_profile("Acme Corp", description="Acme builds widgets"),
            _make_profile("Beta Inc", description="Beta does AI things"),
        ]
        expected_report = _make_explore_report("AI startups")

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_report
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            result = synthesize({
                "mode": "explore",
                "query": "AI startups",
                "company_profiles": profiles,
            })

        assert "report" in result
        assert isinstance(result["report"], ExploreReport)
        assert result["report"].query == "AI startups"
        assert len(result["report"].companies) == 1
        assert result["report"].companies[0].name == "Acme Corp"
        # Verify LLM was called with ExploreReport schema
        mock_llm.with_structured_output.assert_called_once_with(ExploreReport)
        mock_structured.invoke.assert_called_once()

    def test_synthesis_explore_passes_profiles_in_prompt(self):
        """The user message sent to the LLM should contain the query and profiles."""
        from backend.nodes.synthesis import synthesize

        profiles = [
            _make_profile("Acme Corp", description="Acme builds widgets"),
        ]
        expected_report = _make_explore_report()

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_report
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            synthesize({
                "mode": "explore",
                "query": "AI startups",
                "company_profiles": profiles,
            })

        # Check that the invoke call includes query and company data
        call_args = mock_structured.invoke.call_args[0][0]
        user_msg = call_args[1]["content"]
        assert "AI startups" in user_msg
        assert "Acme Corp" in user_msg


class TestSynthesisDeepDive:
    """Tests for deep_dive mode synthesis."""

    def test_synthesis_deep_dive_returns_deep_dive_report(self):
        """synthesize() in deep_dive mode returns a DeepDiveReport in state['report']."""
        from backend.nodes.synthesis import synthesize

        profiles = [
            _make_profile(
                "Acme Corp",
                description="Acme builds NLP tools",
                funding_total="$10M",
                funding_source_url="https://crunchbase.com/acme",
            ),
        ]
        expected_report = _make_deep_dive_report("Acme Corp")

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_report
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            result = synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        assert "report" in result
        assert isinstance(result["report"], DeepDiveReport)
        assert result["report"].company_name == "Acme Corp"
        assert result["report"].overview.title == "Overview"
        assert result["report"].red_flags.content == "Data not available"
        # Verify LLM was called with DeepDiveReport schema
        mock_llm.with_structured_output.assert_called_once_with(DeepDiveReport)
        mock_structured.invoke.assert_called_once()

    def test_synthesis_deep_dive_passes_company_data_in_prompt(self):
        """The user message for deep_dive should contain the company name and profile data."""
        from backend.nodes.synthesis import synthesize

        profiles = [
            _make_profile("Acme Corp", description="Acme builds NLP tools"),
        ]
        expected_report = _make_deep_dive_report()

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_report
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        call_args = mock_structured.invoke.call_args[0][0]
        user_msg = call_args[1]["content"]
        assert "Acme Corp" in user_msg
        assert "Acme builds NLP tools" in user_msg


class TestSynthesisAntiHallucination:
    """Tests verifying the anti-hallucination prompts are properly enforced."""

    def test_synthesis_uses_source_grounded_prompt(self):
        """Both EXPLORE_SYSTEM and DEEP_DIVE_SYSTEM prompts contain anti-hallucination instructions."""
        from backend.nodes.synthesis import EXPLORE_SYSTEM, DEEP_DIVE_SYSTEM

        # Both prompts must contain the critical grounding instruction
        for prompt_name, prompt in [("EXPLORE_SYSTEM", EXPLORE_SYSTEM), ("DEEP_DIVE_SYSTEM", DEEP_DIVE_SYSTEM)]:
            assert "Only include information from the provided data" in prompt, (
                f"{prompt_name} is missing the source-grounding instruction"
            )
            assert "Data not available" in prompt, (
                f"{prompt_name} is missing the 'Data not available' fallback instruction"
            )

    def test_synthesis_explore_system_prompt_sent_to_llm(self):
        """The system message sent to the LLM in explore mode is EXPLORE_SYSTEM."""
        from backend.nodes.synthesis import synthesize, EXPLORE_SYSTEM

        profiles = [_make_profile("Acme Corp")]
        expected_report = _make_explore_report()

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_report
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            synthesize({
                "mode": "explore",
                "query": "AI startups",
                "company_profiles": profiles,
            })

        call_args = mock_structured.invoke.call_args[0][0]
        system_msg = call_args[0]["content"]
        assert system_msg == EXPLORE_SYSTEM

    def test_synthesis_deep_dive_system_prompt_sent_to_llm(self):
        """The system message sent to the LLM in deep_dive mode is DEEP_DIVE_SYSTEM."""
        from backend.nodes.synthesis import synthesize, DEEP_DIVE_SYSTEM

        profiles = [_make_profile("Acme Corp")]
        expected_report = _make_deep_dive_report()

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = expected_report
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        call_args = mock_structured.invoke.call_args[0][0]
        system_msg = call_args[0]["content"]
        assert system_msg == DEEP_DIVE_SYSTEM
