# Fase 5 — aprovação humana

O terceiro incremento adiciona PostgreSQL com pgvector e retomada entre processos
pela CLI `app.persistent`. Consulte [postgres-local.md](postgres-local.md).
Os exemplos abaixo documentam os dois primeiros incrementos, com checkpoint em memória.

Os dois primeiros incrementos da v0.5 incluem checkpoint em memória, revisão na CLI e
retomada com aprovação ou rejeição. A ação protegida é **simulada**: copiar a
síntese aprovada para `report` no estado. Não há arquivo, envio ou publicação.

O fluxo optativo é `agent -> tools -> summarize -> review -> release -> END`.
A rejeição segue de `review` para `END`. A orientação direta continua encerrando
no agente, pois não existe relatório a aprovar. Consultas sem logs também passam
pela revisão da resposta determinística.

## Experimento local

Ative a revisão na CLI com o Ollama disponível:

```bash
export INCIDENT_LAB_MODE=ollama
export INCIDENT_LAB_ORDER_ID=123
export INCIDENT_LAB_REQUIRE_APPROVAL=true
python -m app.main
```

A CLI apresenta a síntese como rascunho ainda não liberado. Digite `sim` para
aprovar; qualquer outra resposta rejeita. Espaços nas extremidades são removidos,
mas a comparação diferencia maiúsculas de minúsculas. Aprovação e rejeição
encerram com código 0. EOF ou Ctrl+C durante a revisão cancelam com código 1.
Uma orientação direta não solicita aprovação. Use `false` (padrão) para desativar.
Valores diferentes de `true` e `false`, ou aprovação no modo `demo`, são erros de configuração.

`run_investigation(..., review=callback)` habilita o mesmo fluxo no uso programático.
O callback síncrono recebe o rascunho e deve devolver um booleano. O executor usa
uma thread de investigação nova e um checkpoint em memória por chamada.
Os 300 segundos são compartilhados pela investigação e pela retomada, descontando
somente o tempo de execução do grafo. A espera humana não consome esse orçamento.
O callback bloqueia o chamador durante a leitura; essa interface destina-se à CLI local.

## Experimento com a API do grafo

Com o ambiente instalado e o Ollama disponível, execute o exemplo abaixo em um
arquivo Python na raiz do projeto. Use somente dados fictícios.

```python
import asyncio
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.graph import build_graph
from app.core.model import create_model


graph = build_graph(
    create_model("qwen3:1.7b"),
    require_approval=True,
    checkpointer=InMemorySaver(),
)
config = {"configurable": {"thread_id": str(uuid4())}}


async def invoke(value):
    async with asyncio.timeout(300):
        return await graph.ainvoke(value, config)


paused = asyncio.run(invoke({"request": "Investigue o pedido 123.", "order_id": "123"}))
if paused.get("__interrupt__"):
    print(paused["__interrupt__"][0].value["draft"])
    decision = input("Liberar relatório simulado? Digite sim para aprovar: ") == "sim"
    final = asyncio.run(invoke(Command(resume=decision)))
    print(final["report"] if final["approved"] else "Relatório rejeitado.")
else:
    print(paused["response"])
```

A espera humana acontece fora do prazo de execução. Cada chamada deste exemplo
didático tem seu próprio prazo de 300 segundos. Para compartilhar o orçamento,
use `run_investigation` como a CLI. `build_graph` diretamente não aplica timeout.

## Contrato e limites

- Passe `require_approval=True`, um modelo e um checkpointer para habilitar a revisão.
- Use um `thread_id` novo para cada investigação. Retome com o mesmo grafo,
  checkpointer e configuração, usando `Command(resume=True)` ou `Command(resume=False)`.
- `response` é a síntese disponível para revisão; somente `report` representa a
  liberação simulada. Durante a pausa não há decisão nem relatório liberado.
- Strings, números e objetos não são decisões válidas. Uma decisão inválida gera
  erro e não libera o relatório; este incremento não fornece uma interface de correção.
- O nó de revisão reinicia na retomada, por isso não contém efeitos antes de
  `interrupt`. A liberação ocorre em outro nó e substitui um campo do estado.
- Retomar uma execução concluída não repete consulta, síntese ou liberação.
  Isso não constitui garantia de execução única para futuros efeitos externos.
- O checkpoint é volátil: encerrar o processo perde o estado. Não há retomada
  entre processos, autenticação, autorização por usuário ou controle de concorrência.
- A API do grafo é de uso local confiável: não exponha entrada arbitrária de estado,
  `update_state`, IDs de threads ou comandos como se fossem uma interface autorizada.
- Aprovar significa revisar o conteúdo, sem garantir que a síntese esteja correta.

Os dois primeiros incrementos não adicionaram dependências. A persistência durável
foi implementada na CLI PostgreSQL; efeitos externos com idempotência permanecem
para incrementos futuros. Os testes usam modelo controlado,
grafo real e entradas simuladas de terminal; não validam a qualidade de um LLM real.

A implementação segue os mecanismos oficiais de
[interrupt e Command](https://docs.langchain.com/oss/python/langgraph/interrupts)
e [checkpoint](https://docs.langchain.com/oss/python/langgraph/persistence).
