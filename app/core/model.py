"""Integração com o servidor Ollama local."""

from httpx import Timeout
from langchain_ollama import ChatOllama


def create_model(name: str) -> ChatOllama:
    return ChatOllama(
        model=name,
        base_url="http://localhost:11434",
        temperature=0,
        num_ctx=4096,
        reasoning=False,
        client_kwargs={"timeout": Timeout(120.0, connect=5.0)},
    )
