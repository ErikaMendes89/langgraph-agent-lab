"""Nó determinístico da primeira etapa de aprendizado."""

from typing import TypedDict

from app.agents.state import InvestigationState


class AgentUpdate(TypedDict):
    response: str


def agent(state: InvestigationState) -> AgentUpdate:
    """Valida a solicitação e retorna somente a atualização do estado."""
    request = state.get("request")
    if not isinstance(request, str) or not request.strip():
        raise ValueError("A solicitação deve ser um texto não vazio.")

    return {
        "response": (
            f"Solicitação recebida: {request.strip()}\n"
            "Demonstração educacional v0.1: nenhuma investigação foi realizada. "
            "Este nó não utiliza LLM, ferramentas ou dados reais."
        )
    }
