"""Contrato de dados compartilhado pelo grafo."""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InvestigationState(TypedDict):
    request: str
    order_id: NotRequired[str]
    response: NotRequired[str]
    approved: NotRequired[bool]
    report: NotRequired[str]
    messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
