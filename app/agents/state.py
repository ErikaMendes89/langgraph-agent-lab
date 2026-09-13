"""Contrato de dados compartilhado pelo grafo."""

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.tools.docs import SearchDocsResult


class InvestigationState(TypedDict):
    request: str
    order_id: NotRequired[str]
    response: NotRequired[str]
    approved: NotRequired[bool]
    report: NotRequired[str]
    use_documents: NotRequired[bool]
    documents: NotRequired[SearchDocsResult]
    messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
