"""Entrada de linha de comando do laboratório."""

import asyncio
import sys

from httpx import ConnectError, TimeoutException
from langgraph.prebuilt.tool_node import ToolInvocationError

from app.agents.graph import build_graph
from app.agents.tool_nodes import ModelResponseError
from app.core.config import (
    get_mode,
    get_model_name,
    get_order_id,
    get_request,
    get_require_approval,
)
from app.core.execution import ExecutionTimeoutError, run_investigation
from app.core.model import create_model


def review_report(draft: str) -> bool:
    print(f"Rascunho para revisão (ainda não liberado):\n{draft}")
    return (
        input("Liberar relatório simulado? Digite sim; outra resposta rejeita: ").strip() == "sim"
    )


def main() -> int:
    try:
        request = get_request()
        mode = get_mode()
        model_name = get_model_name() if mode == "ollama" else None
        order_id = get_order_id() if mode == "ollama" else None
        require_approval = get_require_approval()
        if require_approval and mode != "ollama":
            raise ValueError("A aprovação humana exige INCIDENT_LAB_MODE=ollama.")
    except ValueError as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 1

    model = create_model(model_name) if model_name is not None else None
    try:
        result = (
            asyncio.run(
                run_investigation(
                    model,
                    request,
                    order_id=order_id,
                    review=review_report if require_approval else None,
                )
            )
            if model is not None
            else build_graph().invoke({"request": request})
        )
    except (EOFError, KeyboardInterrupt):
        print("Execução cancelada. Nenhum relatório foi liberado.", file=sys.stderr)
        return 1
    except ExecutionTimeoutError:
        print(
            "Prazo total da investigação excedido (300 segundos). Execução cancelada.",
            file=sys.stderr,
        )
        return 1
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
    if result.get("approved") is False:
        print("Relatório rejeitado. Nenhum relatório foi liberado.")
    elif result.get("approved") is True:
        print(f"Relatório simulado aprovado:\n{result['report']}")
    else:
        print(result["response"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
