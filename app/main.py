"""Entrada de linha de comando do laboratório."""

import sys

from app.agents.graph import build_graph
from app.core.config import get_request


def main() -> int:
    try:
        request = get_request()
    except ValueError as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 1

    result = build_graph().invoke({"request": request})
    print(result["response"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
