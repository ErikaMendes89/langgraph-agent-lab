from typing import cast

import pytest

from app.agents.graph import build_graph
from app.agents.nodes import agent
from app.agents.state import InvestigationState


def test_graph_preserves_request_and_returns_demo_response() -> None:
    graph = build_graph()
    request = "Investigue o pedido 123."
    result = graph.invoke({"request": request})
    assert result["request"] == request
    assert request in result["response"]
    assert "nenhuma investigação foi realizada" in result["response"]
    assert list(graph.stream({"request": request}, stream_mode="updates")) == [
        {"agent": {"response": result["response"]}}
    ]


@pytest.mark.parametrize("invalid_request", ["", "   ", "\n", None, 123])
def test_graph_rejects_invalid_input(invalid_request: object) -> None:
    with pytest.raises(ValueError, match="texto não vazio"):
        build_graph().invoke(cast(InvestigationState, {"request": invalid_request}))


def test_graph_rejects_missing_request() -> None:
    with pytest.raises(ValueError, match="texto não vazio"):
        build_graph().invoke(cast(InvestigationState, {}))


def test_node_does_not_mutate_input() -> None:
    state: InvestigationState = {"request": "  pedido 123  "}
    update = agent(state)
    assert state == {"request": "  pedido 123  "}
    assert "Solicitação recebida: pedido 123\n" in update["response"]


def test_invocations_do_not_share_state() -> None:
    graph = build_graph()
    graph.invoke({"request": "pedido anterior"})
    result = graph.invoke({"request": "pedido atual"})
    assert "pedido anterior" not in result["response"]
    assert "pedido atual" in result["response"]
