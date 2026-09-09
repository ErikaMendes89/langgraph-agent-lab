from unittest.mock import Mock

import pytest
from httpx import ConnectError, ConnectTimeout, ReadTimeout
from langchain_core.messages import AIMessage

from app.core.config import DEFAULT_REQUEST, get_mode, get_model_name, get_request
from app.main import main


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("INCIDENT_LAB_MODE", "INCIDENT_LAB_MODEL", "INCIDENT_LAB_REQUEST"):
        monkeypatch.delenv(name, raising=False)


def test_default_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INCIDENT_LAB_REQUEST", raising=False)
    assert get_request() == DEFAULT_REQUEST


def test_main_uses_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("INCIDENT_LAB_REQUEST", "  pedido de teste  ")
    assert main() == 0
    captured = capsys.readouterr()
    assert "Solicitação recebida: pedido de teste\n" in captured.out
    assert captured.err == ""


def test_main_reports_configuration_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("INCIDENT_LAB_REQUEST", "  ")
    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Erro de configuração" in captured.err


def test_default_mode_does_not_require_ollama() -> None:
    assert get_mode() == "demo"
    assert get_model_name() == "qwen3:1.7b"


def test_invalid_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INCIDENT_LAB_MODE", "unknown")
    with pytest.raises(ValueError, match="INCIDENT_LAB_MODE"):
        get_mode()


def test_empty_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INCIDENT_LAB_MODEL", " ")
    with pytest.raises(ValueError, match="INCIDENT_LAB_MODEL"):
        get_model_name()


def test_cli_runs_tool_graph_without_real_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model = Mock()
    model.bind_tools.return_value = model
    model.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_logs", "args": {"order_id": "123"}, "id": "cli-1"}],
        ),
        AIMessage(content="Há uma falha simulada de atualização."),
    ]
    factory = Mock(return_value=model)
    monkeypatch.setattr("app.main.create_model", factory)
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    monkeypatch.setenv("INCIDENT_LAB_MODEL", "modelo-local")
    assert main() == 0
    factory.assert_called_once_with("modelo-local")
    captured = capsys.readouterr()
    assert "dados inteiramente fictícios" in captured.out
    assert "falha simulada" in captured.out
    assert captured.err == ""


@pytest.mark.parametrize(
    "reply, expected_error",
    [
        (AIMessage(content="  "), "Erro na resposta do modelo"),
        (
            AIMessage(
                content="",
                tool_calls=[{"name": "search_logs", "args": {"order_id": "bad"}, "id": "1"}],
            ),
            "Erro na ferramenta",
        ),
    ],
)
def test_cli_reports_model_errors_without_success_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reply: AIMessage,
    expected_error: str,
) -> None:
    model = Mock()
    model.bind_tools.return_value = model
    model.invoke.return_value = reply
    monkeypatch.setattr("app.main.create_model", Mock(return_value=model))
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert expected_error in captured.err


def test_cli_prints_direct_answer_without_running_a_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model = Mock()
    model.bind_tools.return_value = model
    model.invoke.return_value = AIMessage(content="Qual é o ID do pedido?")
    monkeypatch.setattr("app.main.create_model", Mock(return_value=model))
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    monkeypatch.setenv("INCIDENT_LAB_REQUEST", "Investigue uma inconsistência.")
    assert main() == 0
    captured = capsys.readouterr()
    assert captured.out.endswith("Qual é o ID do pedido?\n")
    assert captured.err == ""
    assert model.invoke.call_count == 1


@pytest.mark.parametrize("stage", ["agent", "summarize"])
@pytest.mark.parametrize(
    "error, message",
    [
        (ConnectionError("private detail"), "Erro de conexão"),
        (ConnectError("private detail"), "Erro de conexão"),
        (ConnectTimeout("private detail"), "Tempo limite"),
        (ReadTimeout("private detail"), "Tempo limite"),
    ],
)
def test_cli_reports_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    error: Exception,
    message: str,
) -> None:
    model = Mock()
    model.bind_tools.return_value = model
    replies: list[AIMessage | Exception] = []
    if stage == "summarize":
        replies.append(
            AIMessage(
                content="",
                tool_calls=[{"name": "search_logs", "args": {"order_id": "123"}, "id": "1"}],
            )
        )
    replies.append(error)
    model.invoke.side_effect = replies
    monkeypatch.setattr("app.main.create_model", Mock(return_value=model))
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err
    assert "private detail" not in captured.err
    assert model.invoke.call_count == len(replies)


def test_cli_does_not_hide_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    model = Mock()
    model.bind_tools.return_value = model
    model.invoke.side_effect = RuntimeError("unexpected")
    monkeypatch.setattr("app.main.create_model", Mock(return_value=model))
    monkeypatch.setenv("INCIDENT_LAB_MODE", "ollama")
    with pytest.raises(RuntimeError, match="unexpected"):
        main()
