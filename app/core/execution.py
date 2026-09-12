"""Execução assíncrona com prazo compartilhado por todos os nós e retries."""

import asyncio
import math
from collections.abc import Callable
from typing import cast
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.graph import build_graph
from app.agents.state import InvestigationState
from app.core.config import validate_order_id


class ExecutionTimeoutError(TimeoutError):
    """O prazo total da investigação expirou."""


async def run_investigation(
    model: BaseChatModel,
    request: str,
    *,
    timeout_seconds: float = 300.0,
    order_id: str | None = None,
    review: Callable[[str], bool] | None = None,
) -> InvestigationState:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("O prazo total deve ser positivo e finito.")
    state: InvestigationState = {"request": request}
    if order_id is not None:
        state["order_id"] = validate_order_id(order_id)
    graph = build_graph(
        model,
        require_approval=review is not None,
        checkpointer=InMemorySaver() if review is not None else None,
    )
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid4())}}
    remaining = timeout_seconds

    async def invoke(value: InvestigationState | Command[bool]) -> InvestigationState:
        nonlocal remaining
        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline = asyncio.timeout(remaining)
        try:
            async with deadline:
                # ainvoke não preserva o TypedDict na anotação de retorno do LangGraph.
                return cast(InvestigationState, await graph.ainvoke(value, config))
        except TimeoutError as exc:
            if not deadline.expired():
                raise
            raise ExecutionTimeoutError("Prazo total da investigação excedido.") from exc
        finally:
            remaining -= loop.time() - started

    result = await invoke(state)
    if review is not None and result.get("__interrupt__"):
        # CLI local: espera humana fora do prazo e sem chamada de modelo em andamento.
        decision = review(result["response"])
        if type(decision) is not bool:
            raise ValueError("A decisão de aprovação deve ser um booleano.")
        result = await invoke(Command(resume=decision))
    return result
