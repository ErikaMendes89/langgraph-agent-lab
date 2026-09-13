import asyncio
from typing import Any

import httpx
import pytest

from app.core.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingError,
    embed_texts,
    validate_vectors,
)


def vector() -> list[float]:
    return [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


@pytest.mark.parametrize(
    "value",
    [
        [],
        [[1.0]],
        [[0.0] * 768],
        [[float("nan")] * 768],
        [[float("inf")] * 768],
        [[True] * 768],
        [[1e39] * 768],
    ],
)
def test_invalid_vectors_are_rejected(value: object) -> None:
    with pytest.raises(EmbeddingError):
        validate_vectors(value, 1)


@pytest.mark.parametrize("changed", [True, False])
def test_real_http_payload_and_model_identity(
    monkeypatch: pytest.MonkeyPatch, changed: bool
) -> None:
    tags = 0

    async def send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        nonlocal tags
        if request.url.path == "/api/tags":
            tags += 1
            digest = "changed" if changed and tags == 2 else "original"
            return httpx.Response(
                200, request=request, json={"models": [{"name": EMBEDDING_MODEL, "digest": digest}]}
            )
        import json

        payload = json.loads(request.content)
        assert payload == {"model": EMBEDDING_MODEL, "input": ["consulta"], "truncate": False}
        return httpx.Response(200, request=request, json={"embeddings": [vector()]})

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    if changed:
        with pytest.raises(EmbeddingError, match="mudou"):
            asyncio.run(embed_texts(["consulta"]))
    else:
        result = asyncio.run(embed_texts(["consulta"]))
        assert "@original:retrieval-v1" in result.model_id
        assert result.vectors == [vector()]


def test_missing_model_does_not_call_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, request=request, json={"models": []})

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    with pytest.raises(EmbeddingError, match="Modelo ausente"):
        asyncio.run(embed_texts(["consulta"]))
