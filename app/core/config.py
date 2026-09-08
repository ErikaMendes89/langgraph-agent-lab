"""Configuração via ambiente, usando somente a biblioteca padrão."""

import os

DEFAULT_REQUEST = "Investigue por que o pedido 123 apresentou inconsistência e gere um relatório."


def get_request() -> str:
    request = os.environ.get("INCIDENT_LAB_REQUEST", DEFAULT_REQUEST)
    if not request.strip():
        raise ValueError("INCIDENT_LAB_REQUEST deve conter um texto não vazio.")
    return request.strip()
