"""Recupera referências após os logs; consulta vazia não vira evidência."""

import asyncio
from typing import Literal, TypedDict

from app.agents.state import InvestigationState
from app.agents.tool_nodes import empty_logs_response
from app.tools.docs import SearchDocsResult, search_docs


class DocumentsUpdate(TypedDict):
    documents: SearchDocsResult


def route_after_tools(state: InvestigationState) -> Literal["documents", "summarize"]:
    if state.get("use_documents") is True and empty_logs_response(state) is None:
        return "documents"
    return "summarize"


async def aretrieve_documents(state: InvestigationState) -> DocumentsUpdate:
    # O conteúdo da ferramenta é a consulta de logs validada pela rota anterior.
    query = f"{state['request'][:500]}\n{str(state['messages'][-1].content)[:499]}"
    return {"documents": await search_docs.ainvoke({"query": query})}


def retrieve_documents(state: InvestigationState) -> DocumentsUpdate:
    return asyncio.run(aretrieve_documents(state))
