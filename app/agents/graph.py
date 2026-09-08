"""Construção explícita de START -> agent -> END."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.nodes import agent
from app.agents.state import InvestigationState


def build_graph() -> CompiledStateGraph[
    InvestigationState, None, InvestigationState, InvestigationState
]:
    builder = StateGraph(InvestigationState)
    builder.add_node("agent", agent)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile()
