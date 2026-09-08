"""Configuração via ambiente, usando somente a biblioteca padrão."""

import os
from typing import Literal

DEFAULT_REQUEST = "Investigue por que o pedido 123 apresentou inconsistência e gere um relatório."


def get_request() -> str:
    request = os.environ.get("INCIDENT_LAB_REQUEST", DEFAULT_REQUEST)
    if not request.strip():
        raise ValueError("INCIDENT_LAB_REQUEST deve conter um texto não vazio.")
    return request.strip()


def get_mode() -> Literal["demo", "ollama"]:
    mode = os.environ.get("INCIDENT_LAB_MODE", "demo")
    if mode == "demo":
        return "demo"
    if mode == "ollama":
        return "ollama"
    raise ValueError("INCIDENT_LAB_MODE deve ser demo ou ollama.")


def get_model_name() -> str:
    name = os.environ.get("INCIDENT_LAB_MODEL", "qwen3:1.7b").strip()
    if not name:
        raise ValueError("INCIDENT_LAB_MODEL deve conter o nome de um modelo instalado no Ollama.")
    return name
