"""Consulta somente leitura a um cenário inteiramente fictício."""

from typing import TypedDict

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field


class SearchLogsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    order_id: str = Field(pattern=r"^[0-9]{1,12}$", description="ID numérico do pedido fictício")


class LogEntry(TypedDict):
    event: str
    detail: str


class SearchLogsResult(TypedDict):
    order_id: str
    synthetic: bool
    logs: list[LogEntry]


@tool(args_schema=SearchLogsInput)
def search_logs(order_id: str) -> SearchLogsResult:
    """Consulta logs fictícios de um pedido. Apenas o pedido 123 tem dados neste laboratório."""
    logs: list[LogEntry] = []
    if order_id == "123":
        logs = [
            {"event": "payment_approved", "detail": "Pagamento aprovado no cenário fictício."},
            {
                "event": "order_update_failed",
                "detail": "Falha simulada ao atualizar o status do pedido após o pagamento.",
            },
        ]
    return {"order_id": order_id, "synthetic": True, "logs": logs}
