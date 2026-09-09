"""Entrada de linha de comando do laboratório."""

import sys

from httpx import ConnectError, TimeoutException
from langgraph.prebuilt.tool_node import ToolInvocationError

from app.agents.graph import build_graph
from app.agents.tool_nodes import ModelResponseError
from app.core.config import get_mode, get_model_name, get_request
from app.core.model import create_model


def main() -> int:
    try:
        request = get_request()
        mode = get_mode()
        model_name = get_model_name() if mode == "ollama" else None
    except ValueError as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 1

    model = create_model(model_name) if model_name is not None else None
    try:
        result = build_graph(model).invoke({"request": request})
    except (ConnectError, ConnectionError):
        print(
            "Erro de conexão: não foi possível acessar o Ollama em http://localhost:11434. "
            "Execute 'ollama serve' em outro terminal e tente novamente.",
            file=sys.stderr,
        )
        return 1
    except TimeoutException:
        print(
            "Tempo limite de comunicação com o Ollama excedido. "
            "Verifique o servidor e a capacidade do hardware antes de tentar novamente.",
            file=sys.stderr,
        )
        return 1
    except ModelResponseError as exc:
        print(f"Erro na resposta do modelo: {exc}", file=sys.stderr)
        return 1
    except ToolInvocationError:
        print("Erro na ferramenta: o modelo forneceu argumentos inválidos.", file=sys.stderr)
        return 1
    print(result["response"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
