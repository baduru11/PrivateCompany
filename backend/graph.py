# backend/graph.py
"""LangGraph state graph definitions for explore and deep-dive pipelines.

Both graphs share the same topology:
    Planner -> Searcher -> Profiler -> Synthesis -> Critic
with a conditional edge from Critic back to Searcher when should_retry=True,
capped at 1 retry by the Critic node itself.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, Union

from langgraph.graph import END, START, StateGraph

from backend.models import (
    CompanyProfile,
    CriticReport,
    DeepDiveReport,
    ExploreReport,
    RawCompanySignal,
    SearchPlan,
    StatusEvent,
)
from backend.nodes.critic import critique
from backend.nodes.planner import plan_search
from backend.nodes.profiler import profile
from backend.nodes.searcher import search
from backend.nodes.synthesis import synthesize

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """Shared state flowing through every node in the graph."""

    query: str
    mode: str
    search_plan: SearchPlan
    raw_signals: list[RawCompanySignal]
    company_profiles: list[CompanyProfile]
    report: Union[ExploreReport, DeepDiveReport]
    critic_report: CriticReport
    retry_count: int
    retry_targets: list[str]
    status_events: Annotated[list[StatusEvent], operator.add]


def should_retry(state: AgentState) -> Literal["planner", "end"]:
    """Conditional edge: route back to planner on retry, otherwise finish."""
    critic = state.get("critic_report")
    if critic and critic.should_retry:
        return "planner"
    return "end"


def _build_graph() -> StateGraph:
    """Construct (but do not compile) the shared 5-node state graph."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", plan_search)
    graph.add_node("searcher", search)
    graph.add_node("profiler", profile)
    graph.add_node("synthesis", synthesize)
    graph.add_node("critic", critique)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "searcher")
    graph.add_edge("searcher", "profiler")
    graph.add_edge("profiler", "synthesis")
    graph.add_edge("synthesis", "critic")
    graph.add_conditional_edges(
        "critic",
        should_retry,
        {
            "planner": "planner",
            "end": END,
        },
    )

    return graph


def build_explore_graph(checkpointer=None):
    """Compile the explore-mode graph.

    Usage::

        graph = build_explore_graph()
        result = graph.invoke({"query": "AI healthcare startups", "mode": "explore"})
    """
    graph = _build_graph()
    return graph.compile(checkpointer=checkpointer)


def build_deep_dive_graph(checkpointer=None):
    """Compile the deep-dive-mode graph.

    Usage::

        graph = build_deep_dive_graph()
        result = graph.invoke({"query": "Acme Corp", "mode": "deep_dive"})
    """
    graph = _build_graph()
    return graph.compile(checkpointer=checkpointer)
