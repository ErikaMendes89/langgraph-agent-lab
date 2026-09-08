"""Contrato de dados compartilhado pelo grafo."""

from typing import NotRequired, TypedDict


class InvestigationState(TypedDict):
    request: str
    response: NotRequired[str]
