"""Grafos de estudo: exemplo básico e uma rodada de tool calling."""

from functools import partial

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agents.nodes import agent
from app.agents.state import InvestigationState
from app.agents.tool_nodes import request_logs, summarize
from app.tools.logs import search_logs


def build_graph(
    model: BaseChatModel | None = None,
) -> CompiledStateGraph[InvestigationState, None, InvestigationState, InvestigationState]:
    builder = StateGraph(InvestigationState)
    if model is None:
        builder.add_node("agent", agent)
        builder.add_edge(START, "agent")
        builder.add_edge("agent", END)
    else:
        builder.add_node("agent", partial(request_logs, model=model.bind_tools([search_logs])))
        builder.add_node("tools", ToolNode([search_logs], handle_tool_errors=False))
        builder.add_node("summarize", partial(summarize, model=model))
        builder.add_edge(START, "agent")
        builder.add_edge("agent", "tools")
        builder.add_edge("tools", "summarize")
        builder.add_edge("summarize", END)
    return builder.compile()
