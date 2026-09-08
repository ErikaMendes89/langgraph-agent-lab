import json
from typing import cast
from unittest.mock import Mock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolInvocationError
from pydantic import ValidationError

from app.agents.graph import build_graph
from app.agents.tool_nodes import ModelResponseError
from app.tools.logs import search_logs


def tool_reply(order_id: str = "123") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "search_logs", "args": {"order_id": order_id}, "id": "call-1"}],
    )


def scripted_model(*replies: AIMessage | Exception) -> Mock:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.invoke.side_effect = replies
    return model


def test_tool_round_trip_passes_evidence_back_to_model() -> None:
    model = scripted_model(tool_reply(), AIMessage(content="Falha simulada na atualização."))
    result = build_graph(cast(BaseChatModel, model)).invoke({"request": "Investigue o pedido 123."})
    model.bind_tools.assert_called_once_with([search_logs])
    assert model.invoke.call_count == 2
    messages = model.invoke.call_args_list[1].args[0]
    evidence = messages[-1]
    assert isinstance(evidence, ToolMessage)
    assert evidence.tool_call_id == "call-1"
    payload = json.loads(str(evidence.content))
    assert payload["synthetic"] is True
    assert payload["order_id"] == "123"
    assert len(payload["logs"]) == 2
    assert result["request"] == "Investigue o pedido 123."
    assert len(result["messages"]) == 5
    assert result["response"].endswith("Falha simulada na atualização.")
    assert "dados inteiramente fictícios" in result["response"]


def test_unknown_order_passes_empty_evidence_to_model() -> None:
    model = scripted_model(tool_reply("456"), AIMessage(content="Sem evidências disponíveis."))
    build_graph(cast(BaseChatModel, model)).invoke({"request": "Investigue o pedido 456."})
    evidence = model.invoke.call_args_list[1].args[0][-1]
    assert json.loads(evidence.content)["logs"] == []


@pytest.mark.parametrize(
    "reply",
    [
        AIMessage(content="Não chamarei ferramentas."),
        AIMessage(content="", tool_calls=tool_reply().tool_calls * 2),
        AIMessage(content="", tool_calls=[{"name": "shell", "args": {}, "id": "call-1"}]),
        AIMessage(content="", tool_calls=[{"name": "search_logs", "args": {}, "id": ""}]),
        AIMessage(
            content="",
            invalid_tool_calls=[{"name": "search_logs", "args": "{", "id": "bad"}],
        ),
    ],
)
def test_invalid_tool_protocol_stops_before_summary(reply: AIMessage) -> None:
    model = scripted_model(reply)
    with pytest.raises(ModelResponseError):
        build_graph(cast(BaseChatModel, model)).invoke({"request": "pedido 123"})
    assert model.invoke.call_count == 1


def test_invalid_tool_arguments_propagate_validation_error() -> None:
    model = scripted_model(tool_reply("../123"))
    with pytest.raises(ToolInvocationError) as error:
        build_graph(cast(BaseChatModel, model)).invoke({"request": "pedido 123"})
    assert isinstance(error.value.__cause__, ValidationError)
    assert model.invoke.call_count == 1


@pytest.mark.parametrize("reply", [AIMessage(content="  "), tool_reply()])
def test_summary_rejects_empty_text_or_further_tools(reply: AIMessage) -> None:
    model = scripted_model(tool_reply(), reply)
    with pytest.raises(ModelResponseError):
        build_graph(cast(BaseChatModel, model)).invoke({"request": "pedido 123"})
    assert model.invoke.call_count == 2


def test_provider_failure_is_not_hidden() -> None:
    model = scripted_model(ConnectionError("Servidor indisponível"))
    with pytest.raises(ConnectionError, match="Servidor indisponível"):
        build_graph(cast(BaseChatModel, model)).invoke({"request": "pedido 123"})


def test_invalid_request_does_not_call_model() -> None:
    model = scripted_model()
    with pytest.raises(ValueError, match="texto não vazio"):
        build_graph(cast(BaseChatModel, model)).invoke({"request": " "})
    model.invoke.assert_not_called()


def test_tool_graph_does_not_keep_history_between_invocations() -> None:
    model = scripted_model(
        tool_reply(),
        AIMessage(content="Primeira síntese."),
        tool_reply("456"),
        AIMessage(content="Segunda síntese."),
    )
    graph = build_graph(cast(BaseChatModel, model))
    graph.invoke({"request": "pedido 123"})
    result = graph.invoke({"request": "pedido 456"})
    assert len(result["messages"]) == 5
    assert "123" not in str(model.invoke.call_args_list[2].args[0])
