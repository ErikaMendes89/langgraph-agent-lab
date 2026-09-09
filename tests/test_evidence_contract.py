import asyncio
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.graph import build_graph
from app.agents.tool_nodes import DIRECT_GUIDANCE, ModelResponseError
from app.core.config import get_order_id
from app.core.execution import run_investigation
from app.main import main


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "wrong_reply",
    [
        AIMessage(content="O pedido não foi encontrado nos logs."),
        AIMessage(
            content="", tool_calls=[{"name": "search_logs", "args": {"order_id": "123"}, "id": "1"}]
        ),
    ],
)
def test_explicit_order_rejects_missing_or_wrong_evidence(
    asynchronous: bool,
    wrong_reply: AIMessage,
) -> None:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.invoke.return_value = wrong_reply
    model.ainvoke = AsyncMock(return_value=wrong_reply)
    with pytest.raises(ModelResponseError):
        if asynchronous:
            asyncio.run(run_investigation(cast(BaseChatModel, model), "Investigue", order_id="456"))
        else:
            build_graph(cast(BaseChatModel, model)).invoke(
                {"request": "Investigue", "order_id": "456"}
            )
    assert model.invoke.call_count + model.ainvoke.call_count == 1


@pytest.mark.parametrize("order_id", ["123", "456"])
def test_explicit_order_consults_matching_tool(order_id: str) -> None:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(
                content="",
                tool_calls=[{"name": "search_logs", "args": {"order_id": order_id}, "id": "1"}],
            ),
            AIMessage(content="Síntese das evidências."),
        ]
    )
    result = asyncio.run(
        run_investigation(cast(BaseChatModel, model), "Investigue", order_id=order_id)
    )
    tools = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tools) == 1
    assert order_id in str(tools[0].content)
    if order_id == "123":
        assert result["response"].endswith("Síntese das evidências.")
        assert model.ainvoke.call_count == 2
    else:
        assert "não retornou registros" in result["response"]
        assert model.ainvoke.call_count == 1


def test_original_false_claim_is_not_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    monkeypatch.setenv("INCIDENT_LAB_REQUEST", "Investigue o pedido 456.")
    monkeypatch.delenv("INCIDENT_LAB_ORDER_ID", raising=False)
    model = Mock()
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(
        return_value=AIMessage(content="O pedido 456 não foi encontrado nos logs disponíveis.")
    )
    monkeypatch.setattr("app.main.create_model", Mock(return_value=model))
    assert main() == 0
    output = capsys.readouterr()
    assert DIRECT_GUIDANCE in output.out
    assert "não foi encontrado" not in output.out


@pytest.mark.parametrize("value", ["", " 123", "123\n", "١٢٣", "1" * 13, "../123"])
def test_invalid_configured_order_is_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("INCIDENT_LAB_ORDER_ID", value)
    with pytest.raises(ValueError, match="INCIDENT_LAB_ORDER_ID"):
        get_order_id()


def test_cli_passes_explicit_order_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    monkeypatch.setenv("INCIDENT_LAB_ORDER_ID", "456")
    model = Mock()
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(return_value=AIMessage(content="Sem logs."))
    monkeypatch.setattr("app.main.create_model", Mock(return_value=model))
    assert main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "exige uma consulta" in output.err
    model.ainvoke.assert_awaited_once()
