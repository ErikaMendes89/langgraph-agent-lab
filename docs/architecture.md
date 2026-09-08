# Arquitetura

## Escopo atual — v0.2

Laboratório educacional, sem alegação de experiência profissional ou uso em produção.
O modo `demo` preserva `START -> agent -> END`, determinístico e sem LLM.
O modo `ollama` usa `START -> agent -> tools -> summarize -> END`, com uma rodada
de tool calling e um modelo servido localmente. Ainda não há roteamento condicional.

| Arquivo/diretório | Responsabilidade |
| --- | --- |
| `app/main.py` | Entrada CLI, configuração, invocação e saída |
| `app/core/config.py` | Ler solicitação, modo e nome do modelo do ambiente |
| `app/core/model.py` | Configurar ChatOllama no servidor local |
| `app/agents/state.py` | Contrato tipado `InvestigationState` |
| `app/agents/nodes.py` | Validar solicitação e retornar `AgentUpdate` |
| `app/agents/tool_nodes.py` | Solicitar uma tool e sintetizar seu resultado |
| `app/agents/graph.py` | Construir e compilar o grafo |
| `app/tools/logs.py` | Schema estrito e consulta somente leitura a logs fictícios |
| `tests/` | Testes determinísticos de comportamento |
| `evals/` | Reserva para avaliações futuras |

## Contratos e fluxo

1. A CLI lê `INCIDENT_LAB_REQUEST`, `INCIDENT_LAB_MODE` e, no modo Ollama,
   `INCIDENT_LAB_MODEL`. O padrão é `demo`, sem chamada externa.
2. `build_graph(model)` registra `search_logs` com `bind_tools`. Sem modelo,
   `build_graph()` monta o exemplo básico da v0.1.
3. `invoke({"request": request})` inicia uma execução independente.
4. `request_logs` valida a solicitação, envia mensagens ao modelo e exige exatamente
   uma chamada a `search_logs`, com identificador não vazio.
5. `ToolNode` valida os argumentos com `SearchLogsInput`, executa a consulta e devolve
   um `ToolMessage` associado ao ID da chamada.
6. `summarize` envia o histórico com as evidências ao modelo sem tools vinculadas.
   Exige texto não vazio e rejeita novas chamadas de ferramentas.
7. A CLI imprime a síntese com um aviso de dados fictícios e retorna código 0.

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
Falhas inesperadas, inclusive indisponibilidade do provedor, são propagadas para diagnóstico.
Não há fallback silencioso para demo quando o modo Ollama falha.

O modelo usa `http://localhost:11434`, sem API key. `.gitignore`
exclui ambientes virtuais, caches e `.env`, preservando `.env.example`.
A solicitação e as evidências são enviadas ao servidor local. Os exemplos devem ser
sintéticos. Instruções nos prompts para não obedecer aos logs não constituem proteção
completa contra prompt injection. Não existem controles para exposição como serviço.

Há duas chamadas ao modelo em uma execução bem-sucedida, com somente uma consulta à
tool. Não há política própria de retry, timeout, orçamento de tokens ou custo nesta fase.
O contexto está configurado em 4096 tokens para o experimento local; isso não substitui
limites de execução. O resumo não passa por validação semântica de evidências.

## Evolução planejada

`get_customer`, `search_docs` e `create_report` continuam planejadas, sem APIs ou
regras de negócio definidas. As versões seguintes estudarão
roteamento, validação, orçamento de execução, aprovação humana, avaliação e tracing.
Persistência e efeitos externos exigirão decisões sobre autorização, idempotência,
retenção e recuperação de falhas antes de sua implementação.

Não foram adicionados servidor web, banco, camada de serviços, fábrica de provedores
ou framework de configuração. O modelo é recebido como `BaseChatModel`, permitindo
substituí-lo por respostas controladas nos testes. A separação atual permite entender o fluxo
e evoluir responsabilidades sem abstrações prematuras.
