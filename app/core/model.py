"""Integração com o servidor Ollama local."""

from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import Timeout

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama


def create_model(name: str) -> ChatOllama:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=name,
        base_url="http://localhost:11434",
        temperature=0,
        num_ctx=4096,
        reasoning=False,
        client_kwargs={"timeout": Timeout(120.0, connect=5.0)},
    )
