# Arquitetura

## Aprovação humana na v0.5

`build_graph(model, require_approval=True, checkpointer=...)` acrescenta os nós
`review` e `release` depois da síntese. `review` usa `interrupt` para apresentar
o rascunho e recebe um booleano por `Command(resume=...)`. Apenas a aprovação
encaminha para `release`, que copia a síntese para `report` no estado. A rejeição
encerra o fluxo. O contrato adiciona `approved` e `report` como campos opcionais.
Não há efeito externo nem nova dependência. A CLI habilita a revisão com
`INCIDENT_LAB_REQUIRE_APPROVAL=true` no modo Ollama. O executor recebe um callback
`review`, cria um checkpoint em memória e um `thread_id` novo e retoma o mesmo grafo
com a decisão. O orçamento de 300 segundos é compartilhado pelas chamadas do grafo;
a espera humana fica fora dele. EOF e Ctrl+C cancelam a CLI com código 1, enquanto
a rejeição encerra normalmente com código 0. Sem a opção, o fluxo anterior permanece.
O exemplo, o contrato de threads e os limites
do checkpoint em memória estão em [human-in-the-loop.md](human-in-the-loop.md).

## Escopo atual — v0.3 e incrementos da v0.4

Laboratório educacional, sem alegação de experiência profissional ou uso em produção.
O modo `demo` preserva `START -> agent -> END`, determinístico e sem LLM.
O modo `ollama` usa uma aresta condicional após `agent`: uma tool call leva a
`tools -> summarize -> END`; uma resposta direta leva a `END`. Não há loops.

| Arquivo/diretório | Responsabilidade |
| --- | --- |
| `app/main.py` | Entrada CLI, configuração, invocação e saída |
| `app/core/config.py` | Ler solicitação, modo e nome do modelo do ambiente |
| `app/core/model.py` | Configurar ChatOllama no servidor local |
| `app/core/execution.py` | Executar o grafo assíncrono com prazo total e cancelamento |
| `app/agents/state.py` | Contrato tipado `InvestigationState` |
| `app/agents/nodes.py` | Validar solicitação e retornar `AgentUpdate` |
| `app/agents/tool_nodes.py` | Chamar o modelo, escolher a rota e formatar a saída |
| `app/agents/graph.py` | Construir e compilar o grafo |
| `app/tools/logs.py` | Schema estrito e consulta somente leitura a logs fictícios |
| `tests/` | Testes determinísticos de comportamento |
| `evals/` | Reserva para avaliações futuras |

## Contratos e fluxo

1. A CLI lê `INCIDENT_LAB_REQUEST`, `INCIDENT_LAB_MODE` e, no modo Ollama,
   `INCIDENT_LAB_MODEL` e o opcional `INCIDENT_LAB_ORDER_ID`. O padrão é `demo`, sem chamada externa.
2. `build_graph(model)` registra `search_logs` com `bind_tools`. Sem modelo,
   `build_graph()` monta o exemplo básico da v0.1.
3. A CLI usa `asyncio.run(run_investigation(model, request))` no modo Ollama, com
   `ainvoke` dentro de `asyncio.timeout(300)`. O modo demo continua síncrono.
4. `call_agent` valida a solicitação e envia mensagens ao modelo. Aceita uma chamada
   a `search_logs`, com identificador não vazio, ou uma resposta textual não vazia.
   `invalid_tool_calls` e múltiplas chamadas interrompem a execução. Com `order_id`
   no estado, a chamada deve existir e apontar para o mesmo ID. Sem ID e sem tool call,
   o texto livre é substituído por uma orientação fixa de escopo e configuração.
5. `route_after_agent` lê a última `AIMessage`. Com tool call, retorna `tools`;
   sem tool call, retorna `done`, mapeado a `END` em `add_conditional_edges`.
6. Na rota de consulta, `ToolNode` valida os argumentos com `SearchLogsInput`, executa
   a ferramenta e devolve um `ToolMessage`. `summarize` envia o histórico com as
   evidências ao modelo sem tools vinculadas.
7. `format_response` aplica às duas rotas o contrato de texto não vazio sem novas
   chamadas de ferramenta. A CLI imprime a saída com aviso de dados fictícios e retorna 0.

A resposta direta já preenche `response` em `call_agent`; não há segunda chamada
ao modelo nem execução de tool nessa rota. O roteador apenas escolhe o caminho,
sem alterar estado ou executar ações. Uma tool call válida acompanhada de texto
continua na rota de consulta, pois o conteúdo textual não substitui a chamada estruturada.

`response` e `messages` são opcionais na entrada. `request` e `response` usam
substituição de valor; `messages` usa o reducer `add_messages`, que acumula mensagens
e substitui mensagens com o mesmo ID. O histórico pertence apenas à invocação atual,
sem checkpoint ou memória entre chamadas. A entrada da CLI contém somente `request`.

`search_logs` recebe uma string de 1 a 12 dígitos, sem campos extras. A saída contém
`order_id`, `synthetic: true` e `logs`, uma lista de eventos com `event` e `detail`.
Somente `123` possui eventos sintéticos; outros IDs retornam uma lista vazia.
Não há acesso ao sistema de arquivos, banco, rede ou dados de clientes nessa ferramenta.

## Erros e segurança atual

Configuração inválida recebe mensagem em stderr e código 1. Entrada direta inválida no
grafo gera `ValueError`. Violações do protocolo geram `ModelResponseError`.
Argumentos inválidos na tool geram `ValidationError`, encapsulado pelo `ToolNode` em
`ToolInvocationError`. A CLI apresenta uma mensagem sem ecoar os argumentos e retorna 1.
Falhas de conexão (`ConnectError` ou `ConnectionError`) e timeout (`TimeoutException`)
recebem mensagens específicas na CLI, com código 1 e sem relatório parcial. Falhas
inesperadas continuam sendo propagadas para diagnóstico.
Não há fallback silencioso para demo quando o modo Ollama falha.

O modelo usa `http://localhost:11434`, sem API key. `.gitignore`
exclui ambientes virtuais, caches e `.env`, preservando `.env.example`.
A solicitação e as evidências são enviadas ao servidor local. Os exemplos devem ser
sintéticos. Instruções nos prompts para não obedecer aos logs não constituem proteção
completa contra prompt injection. Não existem controles para exposição como serviço.

Sem falhas, há uma chamada ao modelo na rota direta ou duas na rota de consulta, com no máximo
uma execução de tool. O cliente HTTP tem timeout de 5 segundos para conectar e
120 segundos para leitura, escrita e espera por conexão disponível. O limite de
leitura vale para a espera entre blocos, não para a duração total do grafo.
`agent` e `summarize` usam `RetryPolicy(max_attempts=2)` apenas para `ConnectError`,
`ConnectionError` e `TimeoutException`, com intervalo de 0,5 segundo e sem jitter.
São no máximo quatro tentativas de modelo na rota de consulta. `tools` não tem retry;
repetir a síntese não repete a consulta. Erros de protocolo e validação não têm retry.
A CLI aplica prazo total de 300 segundos, compartilhado por nós e retries, via
`run_investigation`. `ExecutionTimeoutError` informa a expiração; não é elegível
a retry. A CLI retorna 1 e não imprime relatório parcial. Chamadas diretas ao
grafo não têm esse prazo. Ainda não há orçamento de tokens ou custo.

Os nós do modelo usam `RunnableLambda` com implementações síncronas e assíncronas,
compartilhando prompts e validações. Na CLI, `ainvoke` chega ao cliente HTTP
assíncrono do ChatOllama, permitindo cancelar a operação sem uma thread de inferência.
O cancelamento é cooperativo e aguarda a limpeza da chamada. Não garante parada
imediata no servidor nem interrompe código síncrono bloqueante. A ferramenta atual
é uma consulta curta em memória; futuras integrações precisarão rever essa condição.
O contexto está configurado em 4096 tokens para o experimento local; isso não substitui
limites de execução. A resposta não passa por validação semântica de evidências;
o modelo pode escolher a rota inadequada ou fazer afirmações incorretas.
O ID estruturado tem validação de 1 a 12 dígitos ASCII antes da chamada ao modelo.
Sem ele, o tool calling por texto continua experimental; nenhuma resposta livre
sem ferramenta é apresentada como investigação. O campo estruturado é a fonte
de verdade quando houver divergência com o texto. A correspondência do ID e a
consulta obrigatória não garantem correção semântica da síntese.

## Evolução planejada

`get_customer`, `search_docs` e `create_report` continuam planejadas, sem APIs ou
regras de negócio definidas. As versões seguintes estudarão
validação, orçamento de execução, aprovação humana, avaliação e tracing.
Persistência e efeitos externos exigirão decisões sobre autorização, idempotência,
retenção e recuperação de falhas antes de sua implementação.

Não foram adicionados servidor web, banco, camada de serviços, fábrica de provedores
ou framework de configuração. O modelo é recebido como `BaseChatModel`, permitindo
substituí-lo por respostas controladas nos testes. A separação atual permite entender o fluxo
e evoluir responsabilidades sem abstrações prematuras.

## Resposta quando não há logs

Quando `search_logs` retorna uma lista vazia, o nó `summarize` encerra com uma
resposta determinística, sem nova chamada ao modelo: não há registros para
determinar causa ou status, e ausência de logs não comprova inexistência do pedido.
A consulta continua sendo obrigatória para o ID configurado. Resultado ausente,
JSON inválido, campo `logs` inválido ou erro da ferramenta não viram sucesso.

Nesse caminho há uma chamada ao modelo para solicitar a consulta (até duas
tentativas com retry) e uma consulta à ferramenta. Com logs, a síntese continua
usando o modelo e mantém os riscos de interpretação já documentados.
