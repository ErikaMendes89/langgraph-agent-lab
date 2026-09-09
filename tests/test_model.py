import httpx
import pytest

from app.core.model import create_model


def test_model_passes_timeouts_to_http_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def send(self: httpx.Client, request: httpx.Request, **kwargs: object) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("simulated", request=request)

    monkeypatch.setattr(httpx.Client, "send", send)
    with pytest.raises(httpx.ReadTimeout, match="simulated"):
        create_model("qwen3:1.7b").invoke("pedido 123")
    assert len(requests) == 1
    assert requests[0].extensions["timeout"] == {
        "connect": 5.0,
        "read": 120.0,
        "write": 120.0,
        "pool": 120.0,
    }
