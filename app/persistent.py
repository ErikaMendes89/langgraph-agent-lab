"""CLI local com checkpoints PostgreSQL e aprovação entre processos."""

import argparse
import asyncio
import math
import sys
from collections.abc import Sequence
from typing import Literal
from uuid import UUID, uuid4

from httpx import ConnectError, HTTPStatusError, TimeoutException
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.tool_node import ToolInvocationError
from langgraph.types import Command, StateSnapshot
from psycopg import Error as PostgresError

from app.agents.graph import build_graph
from app.agents.state import InvestigationState
from app.agents.tool_nodes import ModelResponseError
from app.core.config import get_model_name, get_order_id, get_request, validate_order_id
from app.core.database import open_checkpointer
from app.core.embeddings import EmbeddingError
from app.core.execution import ExecutionTimeoutError
from app.core.model import create_model

Action = Literal["init", "start", "show", "resume"]


async def run_persistent(
    action: Action,
    *,
    thread_id: str,
    model: BaseChatModel | None = None,
    request: str | None = None,
    order_id: str | None = None,
    decision: bool | None = None,
    timeout_seconds: float = 300,
    use_documents: bool = False,
) -> StateSnapshot | None:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("O prazo total deve ser positivo e finito.")
    if action not in ("init", "start", "show", "resume"):
        raise ValueError("Ação desconhecida.")
    if action != "init":
        thread_id = str(UUID(thread_id))
        if model is None:
            raise ValueError("O grafo persistente exige um modelo.")
    if action == "resume" and type(decision) is not bool:
        raise ValueError("A retomada exige aprovação ou rejeição explícita.")
    state: InvestigationState = {"request": request or ""}
    if action == "start":
        state["use_documents"] = use_documents
        if not request or not request.strip():
            raise ValueError("A solicitação deve ser um texto não vazio.")
        if order_id is not None:
            state["order_id"] = validate_order_id(order_id)

    deadline = asyncio.timeout(timeout_seconds)
    try:
        async with deadline, open_checkpointer() as (connection, saver):
            # Lock de sessão: liberado ao fechar a conexão, inclusive em erro/cancelamento.
            lock = await connection.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired",
                ("incident-lab:setup" if action == "init" else thread_id,),
            )
            acquired = await lock.fetchone()
            if not acquired or not acquired["acquired"]:
                raise ValueError("Esta investigação ou inicialização já está em execução.")
            if action == "init":
                # Migrações oficiais revisadas: tabelas/índices e alterações não destrutivas.
                await saver.setup()
                return None
            graph = build_graph(model, require_approval=True, checkpointer=saver)
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            snapshot = await graph.aget_state(config)
            if action == "start":
                if snapshot.values:
                    raise ValueError("O identificador já existe; use show ou resume.")
                await graph.ainvoke(state, config, durability="sync")
            else:
                if not snapshot.values:
                    raise ValueError("Investigação não encontrada.")
                if action == "resume":
                    if not snapshot.next:
                        return snapshot
                    if snapshot.next != ("review",) or not any(
                        task.interrupts for task in snapshot.tasks
                    ):
                        raise ValueError("A investigação não está aguardando aprovação.")
                    await graph.ainvoke(Command(resume=decision), config, durability="sync")
            return await graph.aget_state(config)
    except TimeoutError as exc:
        if not deadline.expired():
            raise
        raise ExecutionTimeoutError("Prazo da operação persistente excedido.") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init", help="Criar ou atualizar tabelas de checkpoint")
    start = commands.add_parser("start", help="Investigar e salvar o rascunho para revisão")
    start.add_argument("--with-docs", action="store_true", help="Consultar referências no pgvector")
    show = commands.add_parser("show", help="Consultar o estado salvo")
    show.add_argument("thread_id", type=UUID)
    resume = commands.add_parser("resume", help="Aprovar ou rejeitar o rascunho salvo")
    resume.add_argument("thread_id", type=UUID)
    decision = resume.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", dest="decision", action="store_true")
    decision.add_argument("--reject", dest="decision", action="store_false")
    args = parser.parse_args(argv)
    thread_id = str(args.thread_id) if hasattr(args, "thread_id") else str(uuid4())
    try:
        model = create_model(get_model_name()) if args.action != "init" else None
        if args.action == "start":
            print(f"Investigação: {thread_id}", flush=True)
        snapshot = asyncio.run(
            run_persistent(
                args.action,
                thread_id=thread_id,
                model=model,
                request=get_request() if args.action == "start" else None,
                order_id=get_order_id() if args.action == "start" else None,
                decision=getattr(args, "decision", None),
                use_documents=getattr(args, "with_docs", False),
            )
        )
    except PostgresError:
        print(
            "Erro no PostgreSQL. Verifique o contêiner, as credenciais e execute "
            "'python -m app.persistent init' após preparar o banco.",
            file=sys.stderr,
        )
        return 1
    except (ConnectError, ConnectionError, TimeoutException):
        print("Falha de comunicação com o Ollama local.", file=sys.stderr)
        return 1
    except (EmbeddingError, HTTPStatusError):
        print(
            "Falha nos embeddings locais. Verifique Ollama e app.documents ingest.", file=sys.stderr
        )
        return 1
    except ExecutionTimeoutError:
        print("Prazo de 300 segundos excedido. Consulte o estado com show.", file=sys.stderr)
        return 1
    except (ValueError, ModelResponseError):
        print(
            "Solicitação, estado ou resposta inválida; confira os dados e use show.",
            file=sys.stderr,
        )
        return 1
    except ToolInvocationError:
        print("Argumentos inválidos na consulta aos logs.", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Operação cancelada. Consulte o checkpoint com show.", file=sys.stderr)
        return 1
    if snapshot is None:
        print("Tabelas de checkpoint preparadas.")
    elif snapshot.next == ("review",):
        print(f"Rascunho aguardando aprovação:\n{snapshot.values['response']}")
        print(f"Use: python -m app.persistent resume {thread_id} --approve (ou --reject)")
    elif snapshot.next:
        print("Investigação incompleta; ainda não há rascunho disponível para aprovação.")
    elif snapshot.values.get("approved") is False:
        print("Relatório rejeitado. Nenhum relatório foi liberado.")
    elif snapshot.values.get("approved") is True:
        print(f"Relatório simulado aprovado:\n{snapshot.values['report']}")
    else:
        print(snapshot.values["response"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
