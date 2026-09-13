import asyncio
import os
from uuid import uuid4

import pytest

from app.core.database import open_database
from app.core.embeddings import EmbeddingBatch, EmbeddingError
from app.tools.docs import ingest_documents, search_documents, setup_documents

pytestmark = pytest.mark.skipif(
    os.environ.get("INCIDENT_LAB_TEST_POSTGRES") != "true", reason="Requer PostgreSQL local"
)


def test_real_vector_ranking_versions_and_model_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = "test-" + str(uuid4())
    model_id = "fake-v1"

    async def embed(texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            model_id,
            [([1.0, 0.0] if "pagamento" in text else [0.0, 1.0]) + [0.0] * 766 for text in texts],
        )

    monkeypatch.setattr("app.tools.docs.embed_texts", embed)

    async def scenario() -> None:
        nonlocal model_id
        await setup_documents()
        docs = [
            {"source": "pagamento", "title": "pagamento", "text": "pagamento aprovado " * 45},
            {"source": "outro", "title": "Outro tema", "text": "Revisão de documentos"},
        ]
        assert await ingest_documents(docs, collection=collection) == 3
        assert await ingest_documents(docs, collection=collection) == 0
        result = await search_documents("pagamento", min_score=0.99, collection=collection)
        assert len(result["matches"]) == 2
        assert all(match["source"] == "pagamento" for match in result["matches"])
        assert result["matches"][0]["score"] == pytest.approx(1)
        docs[0]["text"] = "pagamento em uma versão curta"
        assert await ingest_documents(docs[:1], collection=collection) == 1
        result = await search_documents("pagamento", min_score=0.99, collection=collection)
        assert len(result["matches"]) == 1
        assert result["matches"][0]["content"] == docs[0]["text"]
        async with open_database() as connection:
            cursor = await connection.execute(
                "SELECT count(*) AS n FROM document_chunks WHERE collection = %s", (collection,)
            )
            assert await cursor.fetchone() == {"n": 4}
        model_id = "fake-v2"
        assert (await search_documents("pagamento", collection=collection))["matches"] == []
        assert await ingest_documents(docs, collection=collection) == 2
        assert len((await search_documents("pagamento", collection=collection))["matches"]) == 1

    asyncio.run(scenario())


def test_invalid_embedding_does_not_change_active_document(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = "test-" + str(uuid4())
    invalid = False

    async def embed(texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            "fake", [[0.0] * 768 if invalid else [1.0] + [0.0] * 767 for _ in texts]
        )

    monkeypatch.setattr("app.tools.docs.embed_texts", embed)

    async def scenario() -> None:
        nonlocal invalid
        await setup_documents()
        original = [{"source": "manual", "title": "Manual", "text": "Conteúdo original"}]
        await ingest_documents(original, collection=collection)
        invalid = True
        with pytest.raises(EmbeddingError):
            await ingest_documents(
                [{"source": "manual", "title": "Manual", "text": "Texto alterado"}],
                collection=collection,
            )
        invalid = False
        result = await search_documents("consulta", collection=collection)
        assert result["matches"][0]["content"] == "Conteúdo original"

    asyncio.run(scenario())
