# Roadmap de aprendizado

As versões representam etapas aproximadas de estudo, sem promessa de prontidão para
produção. A v0.1 está preservada no modo `demo`; a v0.2 introduziu tool calling com
Ollama e logs fictícios. A v0.3 adiciona a escolha entre consulta e resposta direta,
com testes de ambas as rotas. A execução local com Ollama produziu um relatório,
conforme observado pela autora. A comparação dos três cenários com o modelo real
está registrada em [validation-v0.4.md](validation-v0.4.md): o pedido 456 revelou
uma afirmação sem consulta. Os testes automatizados usam respostas controladas.

| Versão | Escopo proposto | Critério de conclusão |
| --- | --- | --- |
| v0.1 — Basic LangGraph | `START -> agent -> END`, configuração, testes e documentação | Execução local determinística e verificações de qualidade aprovadas |
| v0.2 — Tool calling | Introduzir LLM e primeira ferramenta com dados sintéticos | Demonstrar chamada de tool com contrato explícito e testes isolados do provedor |
| v0.3 — Conditional routing | Escolher entre ferramenta e resposta final | Testar rotas e término do fluxo |
| v0.4 — Guardrails and execution limits | Allowlist, validação, limites, timeout e retries limitados | Testar rejeição de entradas e encerramento de execuções fora dos limites |
| v0.5 — Human-in-the-loop | Checkpoint, aprovação, PostgreSQL/pgvector e RAG local | Concluída: aprovação, rejeição, retomada entre processos e integrações locais verificadas |
| v0.6 — Agent evaluations | Dataset sintético e critérios de qualidade | Executar avaliações repetíveis, incluindo falhas e prompt injection |
| v0.7 — Observability and tracing | Traces, latência, tokens e custo | Medir execuções e verificar remoção de dados sensíveis da telemetria |
| v1.0 — Complete incident investigation agent | Integrar investigação e relatório com ferramentas autorizadas | Demonstrar cenário completo com evidências, limites, aprovação e avaliação |

A v1.0 continuará sendo um projeto educacional e de portfólio. Os detalhes de cada
fase serão definidos a partir do aprendizado e da revisão da etapa anterior.

## Revisão antes de avançar

### Fase 5 concluída

O primeiro incremento adiciona revisão humana optativa na API do grafo, com
checkpoint em memória e liberação simulada de relatório no estado. Os testes
cobrem aprovação, rejeição, decisão inválida e retomadas repetidas, sem repetir
consulta ou síntese. O segundo incremento integra a revisão à CLI por
`INCIDENT_LAB_REQUIRE_APPROVAL=true`, preservando o orçamento de execução entre
investigação e retomada e excluindo a espera humana. Os testes cobrem também
rejeição, EOF, Ctrl+C, configuração inválida e prazo restante na retomada.
O terceiro incremento usa PostgreSQL local com pgvector e permite retomar aprovações
entre processos pela CLI `app.persistent`. O quarto incremento adiciona catálogo
documental, chunking, embeddings locais, ingestão idempotente e busca semântica
integrada opcionalmente ao grafo. Os testes cobrem persistência, locks, idempotência
da decisão, permissões da role e o índice vetorial. Efeitos externos, autenticação de
usuários, avaliações e observabilidade continuam
pendentes para fases posteriores; veja [rag.md](rag.md), [postgres-local.md](postgres-local.md) e
[human-in-the-loop.md](human-in-the-loop.md).

### Validação da v0.5 em Python 3.13

Foi usado um Python 3.13.15 isolado, sem substituir o Python do sistema. A suíte
de PostgreSQL/pgvector passou com 8 testes. A ingestão real com
`nomic-embed-text:v1.5` foi idempotente (0 novos trechos na execução repetida) e a
busca semântica retornou três resultados. A CLI também foi validada com
`qwen3:1.7b`, incluindo a pausa de aprovação, retomada aprovada e retomada
rejeitada.

A suíte determinística em memória passou após a correção mínima de dois fixtures
que substituíam `StructuredTool.func` por `Mock`. A versão atual de
`langgraph-prebuilt` faz introspecção de tipos nessa função; os fixtures passaram
a usar funções reais tipadas, sem alterar a implementação do grafo. Com Python
3.13.15, timeout individual de 20 segundos e PostgreSQL habilitado, a suíte
completa terminou com 152 testes aprovados. Não foi necessário pin adicional de
LangGraph/LangChain nem alteração em `ToolNode`, `interrupt`, `resume` ou
`InMemorySaver`.

Os travamentos observados anteriormente foram, portanto, consequência dos
fixtures inválidos, não uma limitação confirmada das APIs nem um defeito do grafo
de produção. O fluxo real com Ollama e os fluxos persistentes com PostgreSQL
também passam. A execução final desta auditoria habilitou PostgreSQL/pgvector e
terminou com 152 testes aprovados; Ruff, formatação e mypy também passaram.

### Histórico da fase 4

Primeiro incremento da v0.4: timeout de comunicação com o Ollama e mensagens de
conexão indisponível/timeout na CLI, com saída 1 e sem relatório parcial. Os testes
simulam falhas tanto no agente quanto na síntese. O segundo incremento adiciona
no máximo duas tentativas por nó do modelo para falhas de conexão ou timeout,
sem repetir ferramentas. O terceiro incremento aplica prazo total de 300 segundos
na CLI, com cancelamento assíncrono e testes de expiração no agente, na síntese
e durante retries. A revisão confirmou cobertura dos controles de execução, mas
o teste real encontrou uma lacuna de evidência na rota direta. O quarto incremento
introduz ID estruturado com consulta obrigatória e substitui respostas sem ferramenta
por orientação fixa quando o ID não é configurado. O quinto incremento responde
de forma determinística quando a consulta não retorna logs, evitando hipóteses
sem evidência e dispensando a segunda chamada ao modelo.

- Entender e explicar o estado e cada transição.
- Executar testes, lint, verificação de formato e checagem de tipos.
- Revisar secrets, `.gitignore`, alterações e documentação antes de qualquer commit.
- Usar dados fictícios e nunca versionar `.env`, tokens ou API keys.
- Revisar o contrato de ID explícito e a validação da correção antes da v0.5.
