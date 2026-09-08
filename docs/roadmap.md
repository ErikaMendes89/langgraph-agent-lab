# Roadmap de aprendizado

As versões representam etapas aproximadas de estudo, sem promessa de prontidão para
produção. A v0.1 é a única implementação atual. A v0.2 aguarda aprovação.

| Versão | Escopo proposto | Critério de conclusão |
| --- | --- | --- |
| v0.1 — Basic LangGraph | `START -> agent -> END`, configuração, testes e documentação | Execução local determinística e verificações de qualidade aprovadas |
| v0.2 — Tool calling | Introduzir LLM e primeira ferramenta com dados sintéticos | Demonstrar chamada de tool com contrato explícito e testes isolados do provedor |
| v0.3 — Conditional routing | Escolher entre ferramenta e resposta final | Testar rotas e término do fluxo |
| v0.4 — Guardrails and execution limits | Allowlist, validação, limites, timeout e retries limitados | Testar rejeição de entradas e encerramento de execuções fora dos limites |
| v0.5 — Human-in-the-loop | Checkpoint e aprovação antes de ações sensíveis | Testar aprovação, rejeição e retomada sem duplicar efeitos |
| v0.6 — Agent evaluations | Dataset sintético e critérios de qualidade | Executar avaliações repetíveis, incluindo falhas e prompt injection |
| v0.7 — Observability and tracing | Traces, latência, tokens e custo | Medir execuções e verificar remoção de dados sensíveis da telemetria |
| v1.0 — Complete incident investigation agent | Integrar investigação e relatório com ferramentas autorizadas | Demonstrar cenário completo com evidências, limites, aprovação e avaliação |

A v1.0 continuará sendo um projeto educacional e de portfólio. Os detalhes de cada
fase serão definidos a partir do aprendizado e da revisão da etapa anterior.

## Revisão antes de avançar

- Entender e explicar o estado e cada transição.
- Executar testes, lint, verificação de formato e checagem de tipos.
- Revisar secrets, `.gitignore`, alterações e documentação antes de qualquer commit.
- Usar dados fictícios e nunca versionar `.env`, tokens ou API keys.
- Aprovar explicitamente o início da v0.2; não fazer push automaticamente.
