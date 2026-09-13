"""Conexão local PostgreSQL e serialização restrita dos checkpoints."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row


def database_conninfo() -> str:
    configured = os.environ.get("INCIDENT_LAB_DATABASE_URL")
    if configured is not None:
        if not configured.strip():
            raise ValueError("INCIDENT_LAB_DATABASE_URL não pode ser vazia.")
        return make_conninfo(configured, connect_timeout=5)
    return make_conninfo(
        host="127.0.0.1",
        port=5433,
        dbname="incident_lab",
        user="incident_lab",
        passfile=str(Path(".local/pgpass").resolve()),
        connect_timeout=5,
        options="-c statement_timeout=30000",
    )


@asynccontextmanager
async def open_database() -> AsyncIterator[AsyncConnection[DictRow]]:
    async with await AsyncConnection.connect(
        database_conninfo(), autocommit=True, row_factory=dict_row
    ) as connection:
        yield connection


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[tuple[AsyncConnection[DictRow], AsyncPostgresSaver]]:
    async with open_database() as connection:
        saver = AsyncPostgresSaver(
            connection, serde=JsonPlusSerializer(allowed_msgpack_modules=None)
        )
        yield connection, saver
