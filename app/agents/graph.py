"""Grafos de estudo: exemplo básico e uma rodada de tool calling."""

from functools import partial

from httpx import ConnectError, TimeoutException
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import RetryPolicy

from app.agents.nodes import agent
from app.agents.state import InvestigationState
from app.agents.tool_nodes import acall_agent, asummarize, call_agent, route_after_agent, summarize
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
        model_retry = RetryPolicy(
            max_attempts=2,
            initial_interval=0.5,
            jitter=False,
            retry_on=(ConnectError, ConnectionError, TimeoutException),
        )
        bound_model = model.bind_tools([search_logs])
        builder.add_node(
            "agent",
            RunnableLambda(
                partial(call_agent, model=bound_model),
                afunc=partial(acall_agent, model=bound_model),
            ),
            retry_policy=model_retry,
        )
        builder.add_node("tools", ToolNode([search_logs], handle_tool_errors=False))
        builder.add_node(
            "summarize",
            RunnableLambda(partial(summarize, model=model), afunc=partial(asummarize, model=model)),
            retry_policy=model_retry,
        )
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "done": END})
        builder.add_edge("tools", "summarize")
        builder.add_edge("summarize", END)
    return builder.compile()
