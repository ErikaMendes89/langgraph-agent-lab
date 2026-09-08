"""Integração com o servidor Ollama local."""

from langchain_ollama import ChatOllama


def create_model(name: str) -> ChatOllama:
    return ChatOllama(
        model=name,
        base_url="http://localhost:11434",
        temperature=0,
        num_ctx=4096,
        reasoning=False,
    )
