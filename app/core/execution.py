"""Execução assíncrona com prazo compartilhado por todos os nós e retries."""

import asyncio
import math
from typing import cast

from langchain_core.language_models import BaseChatModel

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
) -> InvestigationState:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("O prazo total deve ser positivo e finito.")
    deadline = asyncio.timeout(timeout_seconds)
    state: InvestigationState = {"request": request}
    if order_id is not None:
        state["order_id"] = validate_order_id(order_id)
    try:
        async with deadline:
            # ainvoke não preserva o TypedDict na anotação de retorno do LangGraph.
            return cast(InvestigationState, await build_graph(model).ainvoke(state))
    except TimeoutError as exc:
        if not deadline.expired():
            raise
        raise ExecutionTimeoutError("Prazo total da investigação excedido.") from exc
