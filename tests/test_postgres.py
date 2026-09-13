"""Integração optativa: banco local preparado; somente dados sintéticos são adicionados."""

import asyncio
import os
import subprocess
import sys
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.core.database import open_checkpointer
from app.persistent import run_persistent

pytestmark = pytest.mark.skipif(
    os.environ.get("INCIDENT_LAB_TEST_POSTGRES") != "true",
    reason="Requer PostgreSQL local e INCIDENT_LAB_TEST_POSTGRES=true",
)

START_PROCESS = """
import asyncio
import sys
from unittest.mock import AsyncMock, Mock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from app.persistent import run_persistent
model = Mock(spec=BaseChatModel)
model.bind_tools.return_value = model
model.ainvoke = AsyncMock(side_effect=[
    AIMessage(content='', tool_calls=[
        {'name': 'search_logs', 'args': {'order_id': sys.argv[2]}, 'id': 'persist-test'}
    ]),
    AIMessage(content='Falha simulada na atualização.'),
])
result = asyncio.run(run_persistent(
    'start', thread_id=sys.argv[1], model=model,
    request='Investigue o pedido fictício.', order_id=sys.argv[2],
))
assert result.next == ('review',)
assert 'report' not in result.values
"""


def unavailable_model() -> Mock:
    model = Mock(spec=BaseChatModel)
    model.bind_tools.return_value = model
    model.ainvoke = AsyncMock(side_effect=AssertionError("Não deve chamar o modelo na retomada"))
    return model


@pytest.mark.parametrize("approved", [True, False])
@pytest.mark.parametrize("order_id", ["123", "456"])
def test_resume_after_process_exit_does_not_repeat_work(approved: bool, order_id: str) -> None:
    thread_id = str(uuid4())
    subprocess.run(
        [sys.executable, "-c", START_PROCESS, thread_id, order_id], check=True, timeout=30
    )
    displayed = subprocess.run(
        [sys.executable, "-m", "app.persistent", "show", thread_id],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "Rascunho aguardando aprovação" in displayed.stdout
    model = unavailable_model()

    async def scenario() -> None:
        paused = await run_persistent("show", thread_id=thread_id, model=model)
        assert paused is not None
        assert paused.next == ("review",)
        assert "report" not in paused.values
        result = await run_persistent("resume", thread_id=thread_id, model=model, decision=approved)
        assert result is not None
        assert result.next == ()
        assert result.values["approved"] is approved
        assert ("report" in result.values) is approved
        if approved:
            assert result.values["report"] == paused.values["response"]
        repeated = await run_persistent(
            "resume", thread_id=thread_id, model=model, decision=not approved
        )
        assert repeated is not None
        assert repeated.config == result.config
        assert repeated.values == result.values
        assert len(result.values["messages"]) == len(paused.values["messages"])

    asyncio.run(scenario())
    model.ainvoke.assert_not_called()


def test_pgvector_and_application_role() -> None:
    async def scenario() -> None:
        async with open_checkpointer() as (connection, _):
            cursor = await connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            assert await cursor.fetchone()
            cursor = await connection.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector AS d")
            assert await cursor.fetchone() == {"d": 1.0}
            cursor = await connection.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
                "WHERE rolname = current_user"
            )
            assert await cursor.fetchone() == {
                "rolsuper": False,
                "rolcreatedb": False,
                "rolcreaterole": False,
            }

    asyncio.run(scenario())


def test_concurrent_operation_is_rejected() -> None:
    async def scenario() -> None:
        thread_id = str(uuid4())
        async with open_checkpointer() as (connection, _):
            await connection.execute(
                "SELECT pg_advisory_lock(hashtextextended(%s, 0))", (thread_id,)
            )
            with pytest.raises(ValueError, match="já está em execução"):
                await run_persistent("show", thread_id=thread_id, model=unavailable_model())
        with pytest.raises(ValueError, match="não encontrada"):
            await run_persistent("show", thread_id=thread_id, model=unavailable_model())

    asyncio.run(scenario())


def test_existing_thread_cannot_be_overwritten() -> None:
    thread_id = str(uuid4())
    subprocess.run([sys.executable, "-c", START_PROCESS, thread_id, "456"], check=True, timeout=30)
    with pytest.raises(ValueError, match="já existe"):
        asyncio.run(
            run_persistent(
                "start", thread_id=thread_id, model=unavailable_model(), request="Outro pedido"
            )
        )


def test_failed_investigation_cannot_be_approved() -> None:
    thread_id = str(uuid4())
    model = unavailable_model()
    model.ainvoke = AsyncMock(return_value=AIMessage(content="Consulta omitida"))
    from app.agents.tool_nodes import ModelResponseError

    with pytest.raises(ModelResponseError):
        asyncio.run(
            run_persistent(
                "start",
                thread_id=thread_id,
                model=cast(BaseChatModel, model),
                request="Pedido 123",
                order_id="123",
            )
        )
    with pytest.raises(ValueError, match="não está aguardando aprovação"):
        asyncio.run(
            run_persistent(
                "resume",
                thread_id=thread_id,
                model=unavailable_model(),
                decision=True,
            )
        )
