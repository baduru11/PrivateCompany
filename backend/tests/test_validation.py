# backend/tests/test_validation.py
import json
import pytest
from unittest.mock import patch, AsyncMock
from backend.validation import validate_query_semantic, validate_query_rules, suggest_query, QueryValidation, QuerySuggestion

# get_llm is imported locally inside validate_query_semantic / suggest_query,
# so we patch at its source
_GET_LLM = "backend.config.get_llm"


class TestValidateQueryRules:
    def test_rejects_short_query(self):
        result = validate_query_rules("ab")
        assert not result.is_valid
        assert "too short" in result.reason

    def test_rejects_long_query(self):
        result = validate_query_rules("x" * 201)
        assert not result.is_valid
        assert "too long" in result.reason

    def test_accepts_valid_query(self):
        result = validate_query_rules("AI infrastructure startups")
        assert result.is_valid


class TestValidateQuerySemantic:
    @pytest.mark.asyncio
    async def test_returns_valid_for_valid_response(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(content="VALID")

        with patch(_GET_LLM, return_value=mock_llm):
            result = await validate_query_semantic("Nvidia")
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_returns_invalid_for_invalid_response(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content="INVALID|Not a business query|Try a company name"
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await validate_query_semantic("recipe for cookies")
        assert not result.is_valid
        assert "Not a business query" in result.reason
        assert "Try a company name" in result.suggestion

    @pytest.mark.asyncio
    async def test_fails_closed_on_llm_error(self):
        """When the LLM call fails, validation should reject the query."""
        with patch(_GET_LLM, side_effect=Exception("LLM down")):
            result = await validate_query_semantic("test query")
        assert not result.is_valid
        assert "unavailable" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_pipe_parts(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content="INVALID | has spaces | suggestion here "
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await validate_query_semantic("hello")
        assert not result.is_valid
        assert result.reason == "has spaces"
        assert result.suggestion == "suggestion here"


class TestSuggestQuery:
    @pytest.mark.asyncio
    async def test_returns_suggestions_for_typo(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content=json.dumps({
                "is_valid": True,
                "confidence": 0.6,
                "suggestions": ["Nvidia", "NVIDIA Corporation", "Nvidia Corp"],
                "reason": "Looks like a typo for Nvidia",
            })
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await suggest_query("nvdia", "deep_dive")
        assert result.is_valid
        assert result.confidence == 0.6
        assert "Nvidia" in result.suggestions
        assert result.original_query == "nvdia"
        assert result.mode == "deep_dive"

    @pytest.mark.asyncio
    async def test_returns_high_confidence_for_correct_query(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content=json.dumps({
                "is_valid": True,
                "confidence": 0.95,
                "suggestions": ["Nvidia"],
                "reason": "Query is already well-formed",
            })
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await suggest_query("Nvidia", "deep_dive")
        assert result.is_valid
        assert result.confidence >= 0.9
        assert "Nvidia" in result.suggestions

    @pytest.mark.asyncio
    async def test_malformed_json_fails_open(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content="this is not json at all"
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await suggest_query("nvdia", "deep_dive")
        assert result.is_valid
        assert result.confidence == 1.0
        assert result.suggestions == ["nvdia"]

    @pytest.mark.asyncio
    async def test_llm_exception_fails_open(self):
        with patch(_GET_LLM, side_effect=Exception("LLM down")):
            result = await suggest_query("nvdia", "deep_dive")
        assert result.is_valid
        assert result.confidence == 1.0
        assert result.suggestions == ["nvdia"]

    @pytest.mark.asyncio
    async def test_invalid_query_from_llm(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content=json.dumps({
                "is_valid": False,
                "confidence": 0.0,
                "suggestions": [],
                "reason": "Not a business query",
            })
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await suggest_query("recipe for cookies", "explore")
        assert not result.is_valid
        assert "Not a business query" in result.reason

    @pytest.mark.asyncio
    async def test_strips_markdown_fences_from_response(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = AsyncMock(
            content='```json\n{"is_valid": true, "confidence": 0.7, "suggestions": ["Nvidia"], "reason": ""}\n```'
        )

        with patch(_GET_LLM, return_value=mock_llm):
            result = await suggest_query("nvdia", "deep_dive")
        assert result.is_valid
        assert "Nvidia" in result.suggestions
