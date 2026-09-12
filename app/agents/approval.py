"""Revisão humana antes de liberar um relatório simulado no estado."""

from typing import Literal, TypedDict

from langgraph.types import interrupt

from app.agents.state import InvestigationState


class ApprovalUpdate(TypedDict):
    approved: bool


class ReportUpdate(TypedDict):
    report: str


def review_report(state: InvestigationState) -> ApprovalUpdate:
    draft = state.get("response")
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("A revisão exige uma síntese não vazia.")
    # O nó reinicia na retomada: não executar efeitos antes de interrupt.
    decision = interrupt({"action": "release_simulated_report", "draft": draft})
    if type(decision) is not bool:
        raise ValueError("A decisão de aprovação deve ser um booleano.")
    return {"approved": decision}


def route_after_review(state: InvestigationState) -> Literal["release", "done"]:
    return "release" if state.get("approved") is True else "done"


def release_report(state: InvestigationState) -> ReportUpdate:
    if state.get("approved") is not True:
        raise ValueError("A liberação exige aprovação explícita.")
    # Somente estado: não escreve arquivo nem publica em serviço externo.
    return {"report": state["response"]}
