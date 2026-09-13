"""CLI para indexar e consultar a base vetorial fictícia local."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx
from psycopg import Error as PostgresError

from app.core.embeddings import EmbeddingError
from app.tools.docs import ingest_documents, search_documents, setup_documents


async def execute(action: str, query: str | None) -> None:
    async with asyncio.timeout(300):
        if action == "init":
            await setup_documents()
            print("Tabelas knowledge_documents e document_chunks preparadas.")
        elif action == "ingest":
            data = json.loads((Path(__file__).parent / "data/knowledge.json").read_text())
            count = await ingest_documents(data)
            print(f"Indexação concluída: {count} novos trechos vetoriais.")
        else:
            result = await search_documents(query or "")
            if not result["matches"]:
                print("Nenhum trecho atingiu o limiar para este modelo. Confira a indexação.")
            for match in result["matches"]:
                print(f"[{match['source']}#{match['chunk_index']}] score={match['score']:.3f}")
                print(f"{match['title']}\n{match['content']}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init")
    commands.add_parser("ingest", help="Indexar app/data/knowledge.json")
    search = commands.add_parser("search")
    search.add_argument("query")
    args = parser.parse_args(argv)
    try:
        asyncio.run(execute(args.action, getattr(args, "query", None)))
    except PostgresError:
        print(
            "Erro no PostgreSQL. Verifique o banco e execute app.documents init.", file=sys.stderr
        )
        return 1
    except (httpx.HTTPError, ConnectionError, EmbeddingError):
        print(
            "Falha nos embeddings. Verifique o Ollama e o modelo nomic-embed-text:v1.5.",
            file=sys.stderr,
        )
        return 1
    except TimeoutError:
        print("Prazo de 300 segundos excedido; a operação foi cancelada.", file=sys.stderr)
        return 1
    except (ValueError, OSError):
        print(
            "Documento, consulta ou arquivo inválido. Confira os limites da documentação.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("Operação cancelada.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
