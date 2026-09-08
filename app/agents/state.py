"""Contrato de dados compartilhado pelo grafo."""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InvestigationState(TypedDict):
    request: str
    response: NotRequired[str]
    messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
