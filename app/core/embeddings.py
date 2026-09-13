"""Embeddings locais com identidade do modelo e validação do contrato vetorial."""

import math
from dataclasses import dataclass

import httpx

EMBEDDING_MODEL = "nomic-embed-text:v1.5"
EMBEDDING_DIMENSIONS = 768


class EmbeddingError(RuntimeError):
    """O provedor local não entregou embeddings compatíveis."""


@dataclass(frozen=True)
class EmbeddingBatch:
    model_id: str
    vectors: list[list[float]]


def validate_vectors(value: object, count: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != count:
        raise EmbeddingError("Quantidade inválida de embeddings.")
    result: list[list[float]] = []
    for vector in value:
        if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError("Dimensão incompatível com a coluna vector(768).")
        if any(
            type(number) not in (int, float) or not math.isfinite(number) or abs(number) > 3e38
            for number in vector
        ):
            raise EmbeddingError("O embedding contém números inválidos.")
        converted = [float(number) for number in vector]
        if not any(converted):
            raise EmbeddingError("Vetor nulo não permite similaridade por cosseno.")
        result.append(converted)
    return result


async def embed_texts(texts: list[str]) -> EmbeddingBatch:
    if not texts or len(texts) > 128 or any(not text.strip() or len(text) > 1600 for text in texts):
        raise ValueError("Embeddings exigem de 1 a 128 textos não vazios de até 1600 caracteres.")
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:11434", timeout=httpx.Timeout(120, connect=5)
    ) as client:

        async def model_digest() -> str:
            response = await client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("models"), list):
                for model in payload["models"]:
                    if isinstance(model, dict) and model.get("name") == EMBEDDING_MODEL:
                        digest = model.get("digest")
                        if isinstance(digest, str) and digest.strip():
                            return digest
            raise EmbeddingError(f"Modelo ausente. Execute ollama pull {EMBEDDING_MODEL}.")

        digest = await model_digest()
        response = await client.post(
            "/api/embed",
            json={"model": EMBEDDING_MODEL, "input": texts, "truncate": False},
        )
        response.raise_for_status()
        payload = response.json()
        vectors = validate_vectors(
            payload.get("embeddings") if isinstance(payload, dict) else None, len(texts)
        )
        if await model_digest() != digest:
            raise EmbeddingError("O modelo mudou durante a geração; repita a operação.")
        return EmbeddingBatch(f"{EMBEDDING_MODEL}@{digest}:retrieval-v1", vectors)
