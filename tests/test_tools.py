import pytest
from pydantic import ValidationError

from app.tools.logs import search_logs


def test_search_logs_returns_synthetic_evidence() -> None:
    result = search_logs.invoke({"order_id": "123"})
    assert result["synthetic"] is True
    assert result["order_id"] == "123"
    assert [entry["event"] for entry in result["logs"]] == [
        "payment_approved",
        "order_update_failed",
    ]


def test_unknown_order_has_no_fabricated_logs() -> None:
    assert search_logs.invoke({"order_id": "456"})["logs"] == []


@pytest.mark.parametrize("order_id", [123, True, "", "../123", "123\n", "1" * 13])
def test_search_logs_rejects_invalid_id(order_id: object) -> None:
    with pytest.raises(ValidationError):
        search_logs.invoke({"order_id": order_id})


def test_search_logs_rejects_extra_arguments() -> None:
    with pytest.raises(ValidationError):
        search_logs.invoke({"order_id": "123", "path": "/tmp/logs"})


def test_search_logs_returns_fresh_data() -> None:
    result = search_logs.invoke({"order_id": "123"})
    result["logs"].clear()
    assert len(search_logs.invoke({"order_id": "123"})["logs"]) == 2
