import asyncio
from functools import wraps
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.approval import release_report
from app.agents.graph import build_graph
from app.agents.state import InvestigationState
from app.tools.logs import SearchLogsResult, search_logs


def model_for_review(order_id: str = "123") -> Mock:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    replies = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_logs", "args": {"order_id": order_id}, "id": "1"}],
        ),
        AIMessage(content="Falha simulada na atualização."),
    ]
    model.invoke.side_effect = replies
    model.ainvoke = AsyncMock(side_effect=replies)
    return model


@pytest.mark.parametrize("approved", [True, False])
@pytest.mark.parametrize("asynchronous", [True, False])
def test_review_resume_does_not_repeat_investigation(
    approved: bool, asynchronous: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    query_calls = 0
    original_query = cast(StructuredTool, search_logs).func
    if not callable(original_query):
        raise AssertionError("search_logs.func precisa ser chamável")

    @wraps(original_query)
    def query(order_id: str) -> SearchLogsResult:
        nonlocal query_calls
        query_calls += 1
        return cast(SearchLogsResult, original_query(order_id))

    monkeypatch.setattr(search_logs, "func", query)
    model = model_for_review()
    graph = build_graph(
        cast(BaseChatModel, model), require_approval=True, checkpointer=InMemorySaver()
    )
    config: RunnableConfig = {"configurable": {"thread_id": "review-1"}}

    async def scenario() -> None:
        initial: InvestigationState = {"request": "pedido 123", "order_id": "123"}
        paused = (
            await graph.ainvoke(initial, config) if asynchronous else graph.invoke(initial, config)
        )
        assert "report" not in paused
        assert "approved" not in paused
        assert paused["__interrupt__"][0].value["draft"] == paused["response"]
        for _ in range(2):
            result = (
                await graph.ainvoke(Command(resume=approved), config)
                if asynchronous
                else graph.invoke(Command(resume=approved), config)
            )
            assert result["approved"] is approved
            assert ("report" in result) is approved
            if approved:
                assert result["report"] == paused["response"]
        assert graph.get_state(config).next == ()

    asyncio.run(scenario())
    assert query_calls == 1
    assert (model.ainvoke if asynchronous else model.invoke).call_count == 2


@pytest.mark.parametrize("decision", ["true", "false", 1, 0, {"approved": True}])
def test_invalid_decision_cannot_release_report(decision: object) -> None:
    graph = build_graph(
        cast(BaseChatModel, model_for_review()),
        require_approval=True,
        checkpointer=InMemorySaver(),
    )
    config: RunnableConfig = {"configurable": {"thread_id": "invalid"}}
    graph.invoke({"request": "pedido 123"}, config)
    with pytest.raises(ValueError, match="booleano"):
        graph.invoke(Command(resume=decision), config)
    assert "report" not in graph.get_state(config).values


def test_direct_guidance_does_not_request_approval() -> None:
    model = model_for_review()
    model.invoke.side_effect = [AIMessage(content="Qual pedido?")]
    graph = build_graph(
        cast(BaseChatModel, model), require_approval=True, checkpointer=InMemorySaver()
    )
    result = graph.invoke({"request": "Investigue"}, {"configurable": {"thread_id": "direct"}})
    assert "__interrupt__" not in result
    assert "report" not in result


def test_empty_evidence_still_requires_review() -> None:
    model = model_for_review("456")
    graph = build_graph(
        cast(BaseChatModel, model), require_approval=True, checkpointer=InMemorySaver()
    )
    result = graph.invoke(
        {"request": "pedido 456", "order_id": "456"},
        {"configurable": {"thread_id": "empty"}},
    )
    assert "não retornou registros" in result["__interrupt__"][0].value["draft"]
    assert "report" not in result
    assert model.invoke.call_count == 1


def test_approval_requires_checkpoint_and_model() -> None:
    with pytest.raises(ValueError, match="modelo e checkpointer"):
        build_graph(cast(BaseChatModel, model_for_review()), require_approval=True)
    with pytest.raises(ValueError, match="modelo e checkpointer"):
        build_graph(require_approval=True, checkpointer=InMemorySaver())


def test_release_rejects_missing_approval() -> None:
    with pytest.raises(ValueError, match="aprovação explícita"):
        release_report({"request": "pedido 123", "response": "Síntese"})
