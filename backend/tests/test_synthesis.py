# backend/tests/test_synthesis.py
import pytest
from unittest.mock import MagicMock, patch, call
from backend.models import (
    CompanyProfile,
    ExploreReport,
    ExploreCompany,
    DeepDiveReport,
    DeepDiveSection,
    SectionProse,
)
from backend.nodes.synthesis import MetadataAndArrays


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
        user_msg = call_args[1].content
        assert "AI startups" in user_msg
        assert "Acme Corp" in user_msg


class TestSynthesisDeepDive:
    """Tests for deep_dive mode synthesis (parallel per-section architecture)."""

    def _mock_invoke_structured(self, llm, schema, messages):
        """Side effect for invoke_structured that returns appropriate mock per schema."""
        if schema is MetadataAndArrays:
            return MetadataAndArrays(company_name="Acme Corp")
        if schema is SectionProse:
            # Extract section hint from the system message
            system_content = messages[0].content if messages else ""
            if "red flags" in system_content.lower():
                return SectionProse(content="Data not available", confidence=0.0)
            return SectionProse(
                content="Acme Corp is an AI company.",
                confidence=0.9,
                source_urls=["https://acme.com"],
                source_count=1,
            )
        # Fallback for ExploreReport etc.
        raise ValueError(f"Unexpected schema: {schema}")

    def test_synthesis_deep_dive_returns_deep_dive_report(self):
        """synthesize() in deep_dive mode returns a DeepDiveReport via parallel calls."""
        from backend.nodes.synthesis import synthesize

        profiles = [
            _make_profile(
                "Acme Corp",
                description="Acme builds NLP tools",
                funding_total="$10M",
                funding_source_url="https://crunchbase.com/acme",
            ),
        ]

        with (
            patch("backend.nodes.synthesis.get_llm", return_value=MagicMock()),
            patch("backend.nodes.synthesis.invoke_structured", side_effect=self._mock_invoke_structured),
        ):
            result = synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        assert "report" in result
        assert isinstance(result["report"], DeepDiveReport)
        assert result["report"].company_name == "Acme Corp"
        assert result["report"].overview.title == "Overview"
        assert result["report"].overview.content == "Acme Corp is an AI company."
        assert result["report"].red_flags.content == "Data not available"

    def test_synthesis_deep_dive_passes_company_data_in_prompt(self):
        """The user messages for deep_dive should contain the company name and profile data."""
        from backend.nodes.synthesis import synthesize

        profiles = [
            _make_profile("Acme Corp", description="Acme builds NLP tools"),
        ]

        invoke_calls = []

        def _capture_invoke(llm, schema, messages):
            invoke_calls.append((schema, messages))
            return self._mock_invoke_structured(llm, schema, messages)

        with (
            patch("backend.nodes.synthesis.get_llm", return_value=MagicMock()),
            patch("backend.nodes.synthesis.invoke_structured", side_effect=_capture_invoke),
        ):
            synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        # At least metadata call + section calls should have been made
        assert len(invoke_calls) >= 2
        # All calls should include company name in user message
        for schema, messages in invoke_calls:
            user_msg = messages[1].content
            assert "Acme Corp" in user_msg

    def test_synthesis_deep_dive_parallel_sections(self):
        """Verify that all 12 section keys produce sections in the report."""
        from backend.nodes.synthesis import synthesize

        profiles = [_make_profile("Acme Corp", description="Acme builds NLP tools")]

        with (
            patch("backend.nodes.synthesis.get_llm", return_value=MagicMock()),
            patch("backend.nodes.synthesis.invoke_structured", side_effect=self._mock_invoke_structured),
        ):
            result = synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        report = result["report"]
        # Required sections should always be present
        assert report.overview is not None
        assert report.funding is not None
        assert report.key_people is not None
        assert report.product_technology is not None
        assert report.recent_news is not None
        assert report.competitors is not None
        assert report.red_flags is not None

    def test_synthesis_deep_dive_metadata_extraction(self):
        """Verify metadata from MetadataAndArrays is populated in report."""
        from backend.nodes.synthesis import synthesize

        profiles = [_make_profile("Acme Corp")]

        def _meta_invoke(llm, schema, messages):
            if schema is MetadataAndArrays:
                return MetadataAndArrays(
                    company_name="Acme Corp",
                    founded="2020",
                    headquarters="NYC",
                    headcount="~50",
                    funding_stage="Series A",
                )
            return SectionProse(content="Test content.", confidence=0.8)

        with (
            patch("backend.nodes.synthesis.get_llm", return_value=MagicMock()),
            patch("backend.nodes.synthesis.invoke_structured", side_effect=_meta_invoke),
        ):
            result = synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        report = result["report"]
        assert report.founded == "2020"
        assert report.headquarters == "NYC"
        assert report.headcount == "~50"
        assert report.funding_stage == "Series A"


class TestSynthesisAntiHallucination:
    """Tests verifying the anti-hallucination prompts are properly enforced."""

    def test_synthesis_explore_prompt_has_grounding_instructions(self):
        """EXPLORE_SYSTEM prompt contains anti-hallucination instructions."""
        from backend.nodes.synthesis import EXPLORE_SYSTEM

        assert "ONLY use company names from the AVAILABLE COMPANIES list" in EXPLORE_SYSTEM, (
            "EXPLORE_SYSTEM is missing the available-companies-only instruction"
        )
        assert "Do NOT invent" in EXPLORE_SYSTEM, (
            "EXPLORE_SYSTEM is missing the anti-hallucination instruction"
        )

    def test_synthesis_section_prompts_have_grounding_instructions(self):
        """All per-section prompts contain anti-hallucination instructions."""
        from backend.nodes.synthesis import _SECTION_PROMPTS

        for key, prompt in _SECTION_PROMPTS.items():
            assert "Only use information from the provided data" in prompt, (
                f"Section prompt '{key}' is missing the source-grounding instruction"
            )

    def test_synthesis_metadata_prompt_has_grounding_instructions(self):
        """_METADATA_PROMPT contains anti-hallucination instructions."""
        from backend.nodes.synthesis import _METADATA_PROMPT

        assert "Only include information from the provided data" in _METADATA_PROMPT, (
            "_METADATA_PROMPT is missing the source-grounding instruction"
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
        system_msg = call_args[0].content
        assert system_msg == EXPLORE_SYSTEM

    def test_synthesis_deep_dive_uses_per_section_prompts(self):
        """Deep dive mode uses per-section prompts (not a single DEEP_DIVE_SYSTEM prompt)."""
        from backend.nodes.synthesis import synthesize, _SECTION_PROMPTS, _METADATA_PROMPT

        profiles = [_make_profile("Acme Corp")]
        invoke_calls = []

        def _capture_invoke(llm, schema, messages):
            invoke_calls.append((schema, messages))
            if schema is MetadataAndArrays:
                return MetadataAndArrays(company_name="Acme Corp")
            return SectionProse(content="Test content.", confidence=0.8)

        with (
            patch("backend.nodes.synthesis.get_llm", return_value=MagicMock()),
            patch("backend.nodes.synthesis.invoke_structured", side_effect=_capture_invoke),
        ):
            synthesize({
                "mode": "deep_dive",
                "query": "Acme Corp",
                "company_profiles": profiles,
            })

        # Should have 1 metadata call + 12 section calls = 13 total
        assert len(invoke_calls) == 13
        # First call should be metadata extraction
        meta_call_schema, meta_call_messages = invoke_calls[0]
        assert meta_call_schema is MetadataAndArrays
        assert meta_call_messages[0].content == _METADATA_PROMPT


class TestSynthesisErrorHandling:
    def test_raises_descriptive_error_on_llm_failure(self):
        """Synthesis should raise a clear error when LLM fails."""
        from backend.nodes.synthesis import synthesize

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.side_effect = Exception("API timeout")
        mock_llm.with_structured_output.return_value = mock_structured

        profiles = [_make_profile("Acme Corp")]

        with patch("backend.nodes.synthesis.get_llm", return_value=mock_llm):
            with pytest.raises(RuntimeError, match="Synthesis failed"):
                synthesize({"query": "AI chips", "mode": "explore", "company_profiles": profiles})
