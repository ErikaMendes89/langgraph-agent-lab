import asyncio
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage

from app.agents.state import InvestigationState
from app.agents.tool_nodes import ModelResponseError, asummarize, summarize


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("content", ["{}", '{"logs": null}', '{"logs": ""}', "not json", "[]"])
def test_invalid_result_is_not_treated_as_empty_logs(content: str, asynchronous: bool) -> None:
    model = Mock(spec=BaseChatModel)
    model.ainvoke = AsyncMock()
    state: InvestigationState = {
        "request": "pedido 456",
        "messages": [ToolMessage(content=content, tool_call_id="1")],
    }
    with pytest.raises(ModelResponseError):
        if asynchronous:
            asyncio.run(asummarize(state, model=cast(BaseChatModel, model)))
        else:
            summarize(state, model=cast(BaseChatModel, model))
    model.invoke.assert_not_called()
    model.ainvoke.assert_not_called()


def test_missing_result_is_not_treated_as_empty_logs() -> None:
    model = Mock(spec=BaseChatModel)
    with pytest.raises(ModelResponseError, match="exige o resultado"):
        summarize({"request": "pedido 456"}, model=cast(BaseChatModel, model))
    model.invoke.assert_not_called()


def test_tool_error_is_not_treated_as_empty_logs() -> None:
    model = Mock(spec=BaseChatModel)
    with pytest.raises(ModelResponseError, match="resultado válido"):
        summarize(
            {
                "request": "pedido 456",
                "messages": [ToolMessage(content='{"logs": []}', tool_call_id="1", status="error")],
            },
            model=cast(BaseChatModel, model),
        )
    model.invoke.assert_not_called()
