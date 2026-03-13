# backend/tests/test_eval.py
"""LangSmith-compatible evaluation harness using fixture datasets.

Runs structured assertions against the 5 pre-built fixture datasets to catch
regressions in report quality, confidence scoring, and data completeness.
"""
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    assert path.exists(), f"Fixture not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


class TestExploreFixtureQuality:
    """Validate explore fixture data meets minimum quality bar."""

    @pytest.mark.parametrize("fixture_file", [
        "explore_ai_inference_chips.json",
        "explore_digital_health_saas.json",
    ])
    def test_has_minimum_companies(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        companies = report.get("companies", [])
        assert len(companies) >= 5, f"Expected at least 5 companies, got {len(companies)}"

    @pytest.mark.parametrize("fixture_file", [
        "explore_ai_inference_chips.json",
        "explore_digital_health_saas.json",
    ])
    def test_companies_have_required_fields(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        for company in report.get("companies", []):
            assert company.get("name"), "Company missing name"
            assert company.get("sub_sector"), "Company missing sub_sector"
            assert company.get("description"), "Company missing description"

    @pytest.mark.parametrize("fixture_file", [
        "explore_ai_inference_chips.json",
        "explore_digital_health_saas.json",
    ])
    def test_has_summary(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        summary = report.get("summary", "")
        assert len(summary) > 50, f"Summary too short: {len(summary)} chars"

    @pytest.mark.parametrize("fixture_file", [
        "explore_ai_inference_chips.json",
        "explore_digital_health_saas.json",
    ])
    def test_companies_have_confidence_scores(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        for company in report.get("companies", []):
            score = company.get("confidence")
            assert score is not None, f"Company {company['name']} missing confidence"
            assert 0.0 <= score <= 1.0, (
                f"Confidence out of range for {company['name']}: {score}"
            )

    @pytest.mark.parametrize("fixture_file", [
        "explore_ai_inference_chips.json",
        "explore_digital_health_saas.json",
    ])
    def test_has_sub_sectors(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        sub_sectors = report.get("sub_sectors", [])
        assert len(sub_sectors) >= 3, (
            f"Expected at least 3 sub_sectors, got {len(sub_sectors)}"
        )


class TestDeepDiveFixtureQuality:
    """Validate deep dive fixture data meets minimum quality bar."""

    @pytest.mark.parametrize("fixture_file", [
        "deep_dive_nvidia.json",
        "deep_dive_mistral_ai.json",
        "deep_dive_recursion_pharma.json",
    ])
    def test_has_all_sections(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        required = ["overview", "funding", "key_people", "product_technology",
                     "recent_news", "competitors", "red_flags"]
        for section in required:
            assert section in report, f"Missing section: {section}"
            section_data = report[section]
            if isinstance(section_data, dict):
                assert section_data.get("content"), f"Section {section} has no content"

    @pytest.mark.parametrize("fixture_file", [
        "deep_dive_nvidia.json",
        "deep_dive_mistral_ai.json",
        "deep_dive_recursion_pharma.json",
    ])
    def test_has_metadata(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        assert report.get("company_name"), "Missing company_name"

    @pytest.mark.parametrize("fixture_file", [
        "deep_dive_nvidia.json",
        "deep_dive_mistral_ai.json",
        "deep_dive_recursion_pharma.json",
    ])
    def test_confidence_scores_reasonable(self, fixture_file):
        data = _load_fixture(fixture_file)
        critic = data.get("critic", data.get("critic_report", {}))
        if not critic or not critic.get("section_scores"):
            pytest.skip("No critic scores in fixture")
        scores = critic["section_scores"]
        for section, score in scores.items():
            assert 0.0 <= score <= 1.0, f"Score out of range for {section}: {score}"
        avg = sum(scores.values()) / len(scores)
        assert avg >= 0.3, f"Average confidence too low: {avg:.2f}"

    @pytest.mark.parametrize("fixture_file", [
        "deep_dive_nvidia.json",
        "deep_dive_mistral_ai.json",
        "deep_dive_recursion_pharma.json",
    ])
    def test_sections_have_source_urls(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        sections_with_sources = [
            "overview", "funding", "key_people", "product_technology",
            "recent_news", "competitors", "red_flags",
        ]
        for section in sections_with_sources:
            section_data = report.get(section, {})
            if isinstance(section_data, dict):
                urls = section_data.get("source_urls", [])
                assert len(urls) >= 1, (
                    f"Section {section} has no source_urls"
                )

    @pytest.mark.parametrize("fixture_file", [
        "deep_dive_nvidia.json",
        "deep_dive_mistral_ai.json",
        "deep_dive_recursion_pharma.json",
    ])
    def test_has_people_entries(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        people = report.get("people_entries", [])
        assert len(people) >= 2, f"Expected at least 2 people_entries, got {len(people)}"
        for person in people:
            assert person.get("name"), "Person missing name"
            assert person.get("title"), "Person missing title"

    @pytest.mark.parametrize("fixture_file", [
        "deep_dive_nvidia.json",
        "deep_dive_mistral_ai.json",
        "deep_dive_recursion_pharma.json",
    ])
    def test_has_competitor_entries(self, fixture_file):
        data = _load_fixture(fixture_file)
        report = data.get("report", data)
        competitors = report.get("competitor_entries", [])
        assert len(competitors) >= 3, (
            f"Expected at least 3 competitor_entries, got {len(competitors)}"
        )
        for comp in competitors:
            assert comp.get("name"), "Competitor missing name"
            assert comp.get("description"), "Competitor missing description"


class TestFixtureDataIntegrity:
    """Cross-cutting data integrity checks."""

    @pytest.mark.parametrize("fixture_file,mode", [
        ("explore_ai_inference_chips.json", "explore"),
        ("explore_digital_health_saas.json", "explore"),
        ("deep_dive_nvidia.json", "deep_dive"),
        ("deep_dive_mistral_ai.json", "deep_dive"),
        ("deep_dive_recursion_pharma.json", "deep_dive"),
    ])
    def test_fixture_is_valid_json(self, fixture_file, mode):
        data = _load_fixture(fixture_file)
        assert isinstance(data, dict)
        # Should have either report key or be the report itself
        report = data.get("report", data)
        assert isinstance(report, dict)

    @pytest.mark.parametrize("fixture_file,mode", [
        ("explore_ai_inference_chips.json", "explore"),
        ("explore_digital_health_saas.json", "explore"),
        ("deep_dive_nvidia.json", "deep_dive"),
        ("deep_dive_mistral_ai.json", "deep_dive"),
        ("deep_dive_recursion_pharma.json", "deep_dive"),
    ])
    def test_critic_section_present(self, fixture_file, mode):
        data = _load_fixture(fixture_file)
        critic = data.get("critic", {})
        assert isinstance(critic, dict), "Missing or invalid critic section"
        assert critic.get("overall_confidence") is not None, "Missing overall_confidence"
        assert 0.0 <= critic["overall_confidence"] <= 1.0, (
            f"overall_confidence out of range: {critic['overall_confidence']}"
        )

    @pytest.mark.parametrize("fixture_file,mode", [
        ("explore_ai_inference_chips.json", "explore"),
        ("explore_digital_health_saas.json", "explore"),
        ("deep_dive_nvidia.json", "deep_dive"),
        ("deep_dive_mistral_ai.json", "deep_dive"),
        ("deep_dive_recursion_pharma.json", "deep_dive"),
    ])
    def test_critic_has_verifications(self, fixture_file, mode):
        data = _load_fixture(fixture_file)
        critic = data.get("critic", {})
        verifications = critic.get("verifications", [])
        assert len(verifications) >= 1, "Critic has no verifications"
        for v in verifications:
            assert v.get("field"), "Verification missing field"
            assert v.get("status") in ("verified", "unverified"), (
                f"Unexpected verification status: {v.get('status')}"
            )
