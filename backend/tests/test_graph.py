# backend/tests/test_graph.py
"""Tests for LangGraph state graph definitions."""
import pytest
from unittest.mock import MagicMock, patch
from backend.graph import (
    build_explore_graph,
    build_deep_dive_graph,
    should_retry,
    AgentState,
    _build_graph,
)
from backend.models import CriticReport


# ---------------------------------------------------------------------------
# Graph compilation tests
# ---------------------------------------------------------------------------

class TestGraphCompilation:
    """Verify that both graph builders produce valid compiled graphs."""

    def test_explore_graph_compiles(self):
        graph = build_explore_graph()
        assert graph is not None

    def test_deep_dive_graph_compiles(self):
        graph = build_deep_dive_graph()
        assert graph is not None

    def test_explore_graph_has_correct_nodes(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        node_names = set(graph_view.nodes.keys())
        expected = {"planner", "searcher", "profiler", "synthesis", "critic"}
        # __start__ and __end__ are also present
        assert expected.issubset(node_names)

    def test_deep_dive_graph_has_correct_nodes(self):
        graph = build_deep_dive_graph()
        graph_view = graph.get_graph()
        node_names = set(graph_view.nodes.keys())
        expected = {"planner", "searcher", "profiler", "synthesis", "critic"}
        assert expected.issubset(node_names)

    def test_explore_graph_has_start_and_end(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        node_names = set(graph_view.nodes.keys())
        assert "__start__" in node_names
        assert "__end__" in node_names

    def test_deep_dive_graph_has_start_and_end(self):
        graph = build_deep_dive_graph()
        graph_view = graph.get_graph()
        node_names = set(graph_view.nodes.keys())
        assert "__start__" in node_names
        assert "__end__" in node_names


# ---------------------------------------------------------------------------
# Edge structure tests
# ---------------------------------------------------------------------------

class TestGraphEdges:
    """Verify that edges connect nodes in the expected order."""

    def test_graph_has_edge_from_start_to_planner(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        edges = graph_view.edges
        # edges is a list of Edge objects; check __start__ -> planner
        start_targets = [e.target for e in edges if e.source == "__start__"]
        assert "planner" in start_targets

    def test_graph_has_edge_planner_to_searcher(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        edges = graph_view.edges
        planner_targets = [e.target for e in edges if e.source == "planner"]
        assert "searcher" in planner_targets

    def test_graph_has_edge_searcher_to_profiler(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        edges = graph_view.edges
        searcher_targets = [e.target for e in edges if e.source == "searcher"]
        assert "profiler" in searcher_targets

    def test_graph_has_edge_profiler_to_synthesis(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        edges = graph_view.edges
        profiler_targets = [e.target for e in edges if e.source == "profiler"]
        assert "synthesis" in profiler_targets

    def test_graph_has_edge_synthesis_to_critic(self):
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        edges = graph_view.edges
        synthesis_targets = [e.target for e in edges if e.source == "synthesis"]
        assert "critic" in synthesis_targets

    def test_critic_has_conditional_edges(self):
        """Critic node should have edges to both planner (retry) and __end__."""
        graph = build_explore_graph()
        graph_view = graph.get_graph()
        edges = graph_view.edges
        critic_targets = {e.target for e in edges if e.source == "critic"}
        assert "planner" in critic_targets
        assert "__end__" in critic_targets


# ---------------------------------------------------------------------------
# should_retry conditional routing tests
# ---------------------------------------------------------------------------

class TestShouldRetry:
    """Test the should_retry conditional edge function."""

    def test_returns_end_when_no_critic_report(self):
        state: AgentState = {}  # type: ignore[typeddict-item]
        assert should_retry(state) == "end"

    def test_returns_end_when_should_retry_false(self):
        critic = CriticReport(
            overall_confidence=0.8,
            should_retry=False,
        )
        state: AgentState = {"critic_report": critic}  # type: ignore[typeddict-item]
        assert should_retry(state) == "end"

    def test_returns_planner_when_should_retry_true(self):
        critic = CriticReport(
            overall_confidence=0.2,
            should_retry=True,
            retry_queries=["more data"],
        )
        state: AgentState = {"critic_report": critic}  # type: ignore[typeddict-item]
        assert should_retry(state) == "planner"


# ---------------------------------------------------------------------------
# AgentState typing tests
# ---------------------------------------------------------------------------

class TestAgentState:
    """Verify AgentState TypedDict has the expected keys."""

    def test_agent_state_has_required_keys(self):
        expected_keys = {
            "query", "mode", "search_plan", "raw_signals",
            "company_profiles", "report", "critic_report",
            "retry_count", "retry_targets", "status_events",
        }
        assert expected_keys == set(AgentState.__annotations__.keys())

    def test_agent_state_total_false(self):
        """AgentState should be total=False (all keys optional)."""
        assert AgentState.__total__ is False


# ---------------------------------------------------------------------------
# GraphState accumulation contract tests
# ---------------------------------------------------------------------------

class TestGraphStateAccumulation:
    """Document and verify the accumulation contract for AgentState fields.

    - status_events uses Annotated[list, operator.add] so events merge across nodes.
    - raw_signals is a plain list that replaces on write (fresh results on retry).
    """

    def test_status_events_accumulate_across_nodes(self):
        """status_events should use operator.add to merge, not replace."""
        import operator
        import typing

        hints = typing.get_type_hints(AgentState, include_extras=True)
        status_hint = hints.get("status_events")
        # Verify it has Annotated metadata with operator.add
        assert hasattr(status_hint, "__metadata__"), "status_events should be Annotated"
        assert status_hint.__metadata__[0] is operator.add, (
            "status_events should accumulate with operator.add"
        )

    def test_raw_signals_replaces_on_retry(self):
        """raw_signals should NOT accumulate — on retry we want fresh results."""
        import operator
        import typing

        hints = typing.get_type_hints(AgentState, include_extras=True)
        raw_hint = hints.get("raw_signals")
        # Should NOT have Annotated metadata (plain list, replaces on write)
        has_metadata = hasattr(raw_hint, "__metadata__")
        if has_metadata:
            assert raw_hint.__metadata__[0] is not operator.add, (
                "raw_signals should replace, not accumulate"
            )


class TestTargetedRetry:
    def test_should_retry_uses_low_confidence_sections(self):
        """should_retry returns 'planner' when low_confidence_sections is non-empty."""
        from backend.graph import should_retry
        mock_critic = MagicMock()
        mock_critic.should_retry = True
        mock_critic.low_confidence_sections = ["funding", "key_people"]
        state = {"critic_report": mock_critic, "retry_count": 0}
        assert should_retry(state) == "planner"

    def test_should_retry_ends_when_no_low_confidence(self):
        """should_retry returns 'end' when low_confidence_sections is empty."""
        from backend.graph import should_retry
        mock_critic = MagicMock()
        mock_critic.should_retry = False
        mock_critic.low_confidence_sections = []
        state = {"critic_report": mock_critic, "retry_count": 0}
        assert should_retry(state) == "end"


class TestCheckpointing:
    def test_graph_compiles_with_checkpointer(self):
        """Graph should compile successfully with SqliteSaver checkpointer."""
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError:
            pytest.skip("langgraph-checkpoint-sqlite not installed")

        from backend.graph import _build_graph
        graph = _build_graph()
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            compiled = graph.compile(checkpointer=checkpointer)
            assert compiled is not None
