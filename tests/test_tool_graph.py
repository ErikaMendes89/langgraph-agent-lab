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
        AIMessage(content="  "),
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


@pytest.mark.parametrize(
    "prompt, answer",
    [
        ("Investigue uma inconsistência.", "Qual é o ID do pedido que você quer consultar?"),
        ("O que você pode fazer?", "Posso consultar logs fictícios de pedidos neste laboratório."),
    ],
)
def test_direct_response_ends_without_tool_or_second_model_call(prompt: str, answer: str) -> None:
    model = scripted_model(AIMessage(content=answer))
    updates = list(
        build_graph(cast(BaseChatModel, model)).stream({"request": prompt}, stream_mode="updates")
    )
    assert [list(update) for update in updates] == [["agent"]]
    output = updates[0]["agent"]
    assert output["response"].endswith(answer)
    assert "dados inteiramente fictícios" in output["response"]
    assert len(output["messages"]) == 3
    assert not any(isinstance(message, ToolMessage) for message in output["messages"])
    assert model.invoke.call_count == 1


def test_tool_call_with_text_takes_tool_route_and_finishes() -> None:
    reply = tool_reply()
    reply.content = "Vou consultar os logs fictícios."
    model = scripted_model(reply, AIMessage(content="Síntese das evidências fictícias."))
    updates = list(
        build_graph(cast(BaseChatModel, model)).stream(
            {"request": "Investigue o pedido 123."}, stream_mode="updates"
        )
    )
    assert [list(update) for update in updates] == [["agent"], ["tools"], ["summarize"]]
    assert "response" not in updates[0]["agent"]
    assert updates[-1]["summarize"]["response"].endswith("Síntese das evidências fictícias.")
    assert model.invoke.call_count == 2


def test_route_is_recomputed_for_each_invocation() -> None:
    model = scripted_model(
        tool_reply(),
        AIMessage(content="Primeira síntese."),
        AIMessage(content="Qual pedido?"),
        tool_reply("456"),
        AIMessage(content="Sem evidências para o segundo pedido."),
    )
    graph = build_graph(cast(BaseChatModel, model))
    graph.invoke({"request": "pedido 123"})
    direct = graph.invoke({"request": "Investigue uma inconsistência."})
    assert len(direct["messages"]) == 3
    assert direct["response"].endswith("Qual pedido?")
    final = graph.invoke({"request": "pedido 456"})
    assert len(final["messages"]) == 5
    assert final["response"].endswith("Sem evidências para o segundo pedido.")
    assert "Primeira síntese" not in str(final["messages"])
    assert model.invoke.call_count == 5


def test_malformed_tool_call_with_text_is_not_treated_as_direct_response() -> None:
    reply = AIMessage(
        content="Resposta aparentemente válida.",
        invalid_tool_calls=[{"name": "search_logs", "args": "{", "id": "bad"}],
    )
    model = scripted_model(reply)
    with pytest.raises(ModelResponseError):
        build_graph(cast(BaseChatModel, model)).invoke({"request": "pedido 123"})
    assert model.invoke.call_count == 1
