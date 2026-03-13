# backend/tests/test_validation.py
import pytest
from unittest.mock import patch, AsyncMock
from backend.validation import validate_query_semantic, validate_query_rules, QueryValidation

# get_llm is imported locally inside validate_query_semantic, so we patch at its source
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
