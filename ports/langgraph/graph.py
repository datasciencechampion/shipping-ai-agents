"""LangGraph port: the graph orchestrates MedGuard; the veto is not a model node.

Install: ``pip install -e ".[langgraph]"``

``review()`` always works offline (no LangGraph import). ``build_graph()`` is
the real StateGraph and requires the extra. After ``invoke``, callers still
run ``apply_independent_veto`` so a graph refactor cannot swallow the guardrail.
"""

from __future__ import annotations

from typing import Any, TypedDict

from ports.slice import apply_independent_veto, run_medguard_core
from medguard.types import Review


class GraphState(TypedDict, total=False):
    case: dict
    core_review: Any


def medguard_core_node(state: GraphState) -> GraphState:
    """One graph node: tools + decide. No dose-ceiling here."""
    return {"core_review": run_medguard_core(state["case"])}


def review(case: dict) -> Review:
    """Same v4.1 slice, with the veto applied outside the graph."""
    inner = run_medguard_core(case)
    return apply_independent_veto(inner, case)


def build_graph():
    """Compile a one-node graph. Veto is *not* inside the graph."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            'Install the LangGraph extra: pip install -e ".[langgraph]"'
        ) from exc

    graph = StateGraph(GraphState)
    graph.add_node("medguard_core", medguard_core_node)
    graph.add_edge(START, "medguard_core")
    graph.add_edge("medguard_core", END)
    return graph.compile()


def review_via_langgraph(case: dict, *, recursion_limit: int = 8) -> Review:
    """Invoke the compiled graph, then apply the independent veto."""
    app = build_graph()
    out = app.invoke({"case": case}, config={"recursion_limit": recursion_limit})
    return apply_independent_veto(out["core_review"], case)
