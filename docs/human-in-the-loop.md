# Fase 5 — aprovação humana

Primeiro incremento da v0.5: checkpoint em memória, interrupção para revisão e
retomada com aprovação ou rejeição. A ação protegida é **simulada**: copiar a
síntese aprovada para `report` no estado. Não há arquivo, envio ou publicação.

O fluxo optativo é `agent -> tools -> summarize -> review -> release -> END`.
A rejeição segue de `review` para `END`. A orientação direta continua encerrando
no agente, pois não existe relatório a aprovar. Consultas sem logs também passam
pela revisão da resposta determinística.

## Experimento local

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

A espera humana acontece fora do prazo de execução. Cada chamada do exemplo tem
seu próprio prazo de 300 segundos. A CLI `python -m app.main` e
`run_investigation` continuam no fluxo anterior, sem aprovação. `build_graph`
diretamente não aplica timeout; o exemplo o adiciona explicitamente.

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

Não foram adicionadas dependências. Persistência durável, interface integrada à CLI
 e efeitos externos com idempotência permanecem para incrementos futuros.

A implementação segue os mecanismos oficiais de
[interrupt e Command](https://docs.langchain.com/oss/python/langgraph/interrupts)
e [checkpoint](https://docs.langchain.com/oss/python/langgraph/persistence).
