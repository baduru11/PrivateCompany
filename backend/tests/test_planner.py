# backend/tests/test_planner.py
import pytest
from unittest.mock import MagicMock, patch
from backend.models import SearchPlan


def test_planner_explore_returns_search_plan():
    from backend.nodes.planner import plan_search
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=SearchPlan(
            search_terms=["AI inference chips", "custom silicon AI"],
            target_company_count=15,
            sub_sectors=["GPU", "ASIC", "FPGA"]
        ))
    )
    state = {"query": "AI inference chips", "mode": "explore"}
    with patch("backend.nodes.planner.get_llm", return_value=mock_llm):
        result = plan_search(state)
    assert "search_plan" in result
    assert len(result["search_plan"].search_terms) > 0


def test_planner_deep_dive_returns_search_plan():
    from backend.nodes.planner import plan_search
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = MagicMock(
        invoke=MagicMock(return_value=SearchPlan(
            search_terms=["NVIDIA funding", "NVIDIA investors", "NVIDIA news 2024"],
            target_company_count=1,
            sub_sectors=[]
        ))
    )
    state = {"query": "NVIDIA", "mode": "deep_dive"}
    with patch("backend.nodes.planner.get_llm", return_value=mock_llm):
        result = plan_search(state)
    assert result["search_plan"].target_company_count == 1


def test_planner_does_not_include_retry_context():
    """Planner should not include any retry context (pipeline is linear)."""
    from backend.nodes.planner import plan_search

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SearchPlan(
        search_terms=["NVIDIA headcount", "NVIDIA employees"],
        target_company_count=1,
        sub_sectors=[]
    )
    mock_llm.with_structured_output.return_value = mock_structured
    state = {"query": "NVIDIA", "mode": "deep_dive"}
    with patch("backend.nodes.planner.get_llm", return_value=mock_llm):
        result = plan_search(state)
    assert "search_plan" in result
    # Verify the prompt does not contain retry context
    call_args = mock_structured.invoke.call_args[0][0]
    user_msg = call_args[1].content
    assert "retry" not in user_msg.lower()
    assert "gap" not in user_msg.lower()
    assert user_msg == "Query: NVIDIA"


class TestPlannerErrorHandling:
    def test_raises_descriptive_error_on_llm_failure(self):
        """Planner should raise a clear error when LLM fails, not a raw exception."""
        from backend.nodes.planner import plan_search

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.side_effect = Exception("API timeout")
        mock_llm.with_structured_output.return_value = mock_structured

        with patch("backend.nodes.planner.get_llm", return_value=mock_llm):
            with pytest.raises(RuntimeError, match="Planner failed"):
                plan_search({"query": "AI chips", "mode": "explore"})
