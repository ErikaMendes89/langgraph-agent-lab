import asyncio
from typing import cast
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.core.execution import ExecutionTimeoutError, run_investigation
from app.core.model import create_model


@pytest.mark.parametrize("stage", ["agent", "summarize"])
def test_deadline_cancels_active_model_call(stage: str) -> None:
    cancelled = False
    calls = 0

    async def reply(*args: object, **kwargs: object) -> AIMessage:
        nonlocal cancelled, calls
        calls += 1
        if stage == "summarize" and calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": "search_logs", "args": {"order_id": "123"}, "id": "1"}],
            )
        try:
            await asyncio.Event().wait()
        finally:
            cancelled = True
        raise AssertionError("unreachable")

    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(side_effect=reply)
    with pytest.raises(ExecutionTimeoutError):
        asyncio.run(
            run_investigation(cast(BaseChatModel, model), "pedido 123", timeout_seconds=0.1)
        )
    assert cancelled
    assert calls == (1 if stage == "agent" else 2)
    model.invoke.assert_not_called()


def test_deadline_includes_retry_delay() -> None:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(side_effect=httpx.ConnectError("offline"))
    with pytest.raises(ExecutionTimeoutError):
        asyncio.run(
            run_investigation(cast(BaseChatModel, model), "pedido 123", timeout_seconds=0.1)
        )
    assert model.ainvoke.call_count == 1


def test_real_ollama_client_uses_cancellable_async_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = False

    async def send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        nonlocal cancelled
        try:
            await asyncio.Event().wait()
        finally:
            cancelled = True
        raise AssertionError("unreachable")

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    model = create_model("qwen3:1.7b")
    with pytest.raises(ExecutionTimeoutError):
        asyncio.run(run_investigation(model, "pedido 123", timeout_seconds=0.1))
    assert cancelled


def test_unrelated_timeout_is_not_reported_as_deadline() -> None:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(side_effect=TimeoutError("unrelated"))
    with pytest.raises(TimeoutError, match="unrelated") as error:
        asyncio.run(run_investigation(cast(BaseChatModel, model), "pedido 123"))
    assert not isinstance(error.value, ExecutionTimeoutError)
    assert model.ainvoke.call_count == 1


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_deadline_is_rejected(timeout: float) -> None:
    model = Mock(spec=BaseChatModel)
    with pytest.raises(ValueError, match="positivo e finito"):
        asyncio.run(
            run_investigation(cast(BaseChatModel, model), "pedido 123", timeout_seconds=timeout)
        )
    model.bind_tools.assert_not_called()


def test_human_wait_is_outside_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(
        return_value=AIMessage(
            content="",
            tool_calls=[{"name": "search_logs", "args": {"order_id": "456"}, "id": "wait"}],
        )
    )
    timeout = Mock(wraps=asyncio.timeout)
    monkeypatch.setattr("app.core.execution.asyncio.timeout", timeout)

    def review(draft: str) -> bool:
        assert "não retornou registros" in draft
        time.sleep(0.2)
        return True

    result = asyncio.run(
        run_investigation(
            cast(BaseChatModel, model), "pedido 456", timeout_seconds=0.1, review=review
        )
    )
    assert result["approved"] is True
    assert result["report"] == result["response"]
    assert model.ainvoke.call_count == 1
    assert timeout.call_count == 2
    assert 0 < timeout.call_args_list[1].args[0] < 0.1


def test_resume_uses_remaining_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.state import InvestigationState

    async def reply(*args: object, **kwargs: object) -> AIMessage:
        await asyncio.sleep(0.15)
        return AIMessage(
            content="",
            tool_calls=[{"name": "search_logs", "args": {"order_id": "456"}, "id": "budget"}],
        )

    async def slow_release(state: InvestigationState) -> dict[str, str]:
        await asyncio.sleep(0.15)
        return {"report": state["response"]}

    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(side_effect=reply)
    monkeypatch.setattr("app.agents.graph.release_report", slow_release)
    review = Mock(return_value=True)
    with pytest.raises(ExecutionTimeoutError):
        asyncio.run(
            run_investigation(
                cast(BaseChatModel, model), "pedido 456", timeout_seconds=0.25, review=review
            )
        )
    review.assert_called_once()
    assert model.ainvoke.call_count == 1


def test_review_is_not_called_after_investigation_failure() -> None:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(side_effect=RuntimeError("unexpected"))
    review = Mock(return_value=True)
    with pytest.raises(RuntimeError, match="unexpected"):
        asyncio.run(run_investigation(cast(BaseChatModel, model), "pedido 123", review=review))
    review.assert_not_called()
