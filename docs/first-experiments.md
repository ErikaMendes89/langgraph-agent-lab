# Primeiros experimentos com LangGraph

[Voltar ao projeto](../README.md) · [Índice da documentação](README.md)

Acompanhe um pedido fictício do primeiro nó até a decisão de liberar um relatório.
Os exercícios usam o modo demo e testes com um modelo simulado.

## Preparar o ambiente

Na raiz do clone, use Python 3.12 ou 3.13. Os comandos abaixo assumem Bash.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## 1. Modo demo

```bash
INCIDENT_LAB_MODE=demo INCIDENT_LAB_REQUIRE_APPROVAL=false \
  INCIDENT_LAB_REQUEST="Investigue o pedido 123." python -m app.main
```

O terminal deve mostrar a solicitação e a mensagem do nó demo.

```text
Solicitação recebida: Investigue o pedido 123.
Demonstração educacional v0.1: nenhuma investigação foi realizada. Este nó não utiliza LLM, ferramentas ou dados reais.
```

Em [`nodes.py`](../app/agents/nodes.py), veja como `agent` recebe `request` e
devolve `response`. Em [`graph.py`](../app/agents/graph.py), siga o caminho
`START → agent → END` usado por `build_graph()`.

**Experimente** trocar o texto de `INCIDENT_LAB_REQUEST`. A primeira linha da
resposta acompanha o texto que você enviou.

## 2. Consulta de logs

Rode os dois casos já cobertos por [`test_tool_graph.py`](../tests/test_tool_graph.py).

```bash
python -m pytest -q \
  tests/test_tool_graph.py::test_tool_round_trip_passes_evidence_back_to_model \
  tests/test_tool_graph.py::test_unknown_order_returns_no_evidence_without_second_model_call
```

O resultado esperado é `2 passed`. Cada teste confere um caminho do grafo.

| Pedido fictício | `search_logs` retorna | Próximo passo |
| --- | --- | --- |
| `123` | Pagamento aprovado e falha simulada ao atualizar o pedido | O grafo envia a evidência ao modelo simulado para formar a síntese. |
| `456` | Lista vazia | O grafo informa que não encontrou registros e termina após a primeira chamada ao modelo. |

Em [`logs.py`](../app/tools/logs.py), confira os dados do exercício. Em
[`tool_nodes.py`](../app/agents/tool_nodes.py), localize a mensagem que diz que a
consulta não retornou registros. Ela deixa em aberto a causa e o estado do pedido.

## 3. Pausa para revisar

```bash
python -m pytest -q tests/test_approval.py::test_review_resume_does_not_repeat_investigation
```

O resultado esperado é `4 passed`, com aprovação e rejeição nas execuções
síncrona e assíncrona. Abra [`test_approval.py`](../tests/test_approval.py) e
acompanhe o rascunho em `__interrupt__`. O estado só ganha o campo `report`
após aprovar. O teste também verifica que retomar o fluxo reaproveita a consulta
já feita.

Para aprovar ou rejeitar pelo terminal com o Ollama, siga
[revisão humana com um modelo local](human-in-the-loop.md#experimento-local).
