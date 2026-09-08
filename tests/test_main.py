import pytest

from app.core.config import DEFAULT_REQUEST, get_request
from app.main import main


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
