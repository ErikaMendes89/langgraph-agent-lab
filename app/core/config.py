"""Configuração via ambiente, usando somente a biblioteca padrão."""

import os
import re
from typing import Literal

DEFAULT_REQUEST = "Investigue por que o pedido 123 apresentou inconsistência e gere um relatório."


def get_require_approval() -> bool:
    value = os.environ.get("INCIDENT_LAB_REQUIRE_APPROVAL", "false")
    if value not in ("true", "false"):
        raise ValueError("INCIDENT_LAB_REQUIRE_APPROVAL deve ser true ou false.")
    return value == "true"


def validate_order_id(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,12}", value) is None:
        raise ValueError("INCIDENT_LAB_ORDER_ID deve conter de 1 a 12 dígitos ASCII.")
    return value


def get_order_id() -> str | None:
    value = os.environ.get("INCIDENT_LAB_ORDER_ID")
    return None if value is None else validate_order_id(value)


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
