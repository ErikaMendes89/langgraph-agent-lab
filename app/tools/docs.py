"""Indexação explícita e busca somente leitura de documentos fictícios no pgvector."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import TypedDict

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.core.database import open_database
from app.core.embeddings import EmbeddingError, embed_texts, validate_vectors


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    source: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=4000)


class SearchDocsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=3, ge=1, le=5)
    min_score: float = Field(default=0.35, ge=-1, le=1, allow_inf_nan=False)


class DocumentMatch(TypedDict):
    source: str
    title: str
    chunk_index: int
    content: str
    score: float


class SearchDocsResult(TypedDict):
    synthetic: bool
    model_id: str
    matches: list[DocumentMatch]


def split_document(text: str) -> list[str]:
    """Trechos de até 600 caracteres, com até 100 caracteres de sobreposição."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + 600].strip()
        if chunk:
            chunks.append(chunk)
        if start + 600 >= len(text):
            break
        start += 500
    return chunks


async def setup_documents() -> None:
    schema = (Path(__file__).resolve().parents[1] / "sql/documents.sql").read_text()
    async with open_database() as connection, connection.transaction():
        await connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("docs:init",)
        )
        await connection.execute(schema)


async def ingest_documents(value: object, *, collection: str = "lab") -> int:
    documents = TypeAdapter(list[DocumentInput]).validate_python(value)
    if not 1 <= len(documents) <= 20:
        raise ValueError("A indexação aceita de 1 a 20 documentos por operação.")
    if len({document.source for document in documents}) != len(documents):
        raise ValueError("As fontes devem ser únicas na operação.")
    chunks = [split_document(document.text) for document in documents]
    batch = await embed_texts(
        [
            f"search_document: {document.title}\n{chunk}"
            for document, parts in zip(documents, chunks, strict=True)
            for chunk in parts
        ]
    )
    vectors = iter(validate_vectors(batch.vectors, sum(map(len, chunks))))
    inserted = 0
    # Gera e valida todos os vetores antes de modificar as versões ativas no banco.
    async with open_database() as connection, connection.transaction():
        for document, parts in zip(documents, chunks, strict=True):
            version = hashlib.sha256(
                json.dumps([document.title, document.text], ensure_ascii=False).encode()
            ).hexdigest()
            await connection.execute(
                "INSERT INTO knowledge_documents (collection, source, title, content_hash) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (collection, source) DO UPDATE "
                "SET title = EXCLUDED.title, content_hash = EXCLUDED.content_hash",
                (collection, document.source, document.title, version),
            )
            for index, chunk in enumerate(parts):
                cursor = await connection.execute(
                    "INSERT INTO document_chunks "
                    "(collection, source, content_hash, chunk_index, content, model_id, embedding) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::vector) ON CONFLICT DO NOTHING",
                    (
                        collection,
                        document.source,
                        version,
                        index,
                        chunk,
                        batch.model_id,
                        json.dumps(next(vectors)),
                    ),
                )
                inserted += cursor.rowcount
    return inserted


async def search_documents(
    query: str, *, limit: int = 3, min_score: float = 0.35, collection: str = "lab"
) -> SearchDocsResult:
    args = SearchDocsInput(query=query, limit=limit, min_score=min_score)
    batch = await embed_texts([f"search_query: {args.query}"])
    vector = json.dumps(validate_vectors(batch.vectors, 1)[0])
    async with open_database() as connection:
        cursor = await connection.execute(
            "SELECT c.source, d.title, c.chunk_index, c.content, "
            "1 - (c.embedding <=> %s::vector) AS score "
            "FROM document_chunks c JOIN knowledge_documents d "
            "ON d.collection = c.collection AND d.source = c.source "
            "AND d.content_hash = c.content_hash "
            "WHERE c.collection = %s AND c.model_id = %s "
            "AND 1 - (c.embedding <=> %s::vector) >= %s "
            "ORDER BY c.embedding <=> %s::vector, c.source, c.chunk_index LIMIT %s",
            (vector, collection, batch.model_id, vector, args.min_score, vector, args.limit),
        )
        matches: list[DocumentMatch] = [
            {
                "source": row["source"],
                "title": row["title"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "score": row["score"],
            }
            for row in await cursor.fetchall()
        ]
    return {"synthetic": True, "model_id": batch.model_id, "matches": matches}


@tool(args_schema=SearchDocsInput)
async def search_docs(query: str, limit: int = 3, min_score: float = 0.35) -> SearchDocsResult:
    """Busca referências fictícias por similaridade; não comprova eventos de um pedido."""
    deadline = asyncio.timeout(180)
    try:
        async with deadline:
            return await search_documents(query, limit=limit, min_score=min_score)
    except TimeoutError as exc:
        if not deadline.expired():
            raise
        raise EmbeddingError("Prazo da busca documental excedido.") from exc
