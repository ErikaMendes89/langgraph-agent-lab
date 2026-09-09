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
| v0.5 — Human-in-the-loop | Checkpoint e aprovação antes de ações sensíveis | Testar aprovação, rejeição e retomada sem duplicar efeitos |
| v0.6 — Agent evaluations | Dataset sintético e critérios de qualidade | Executar avaliações repetíveis, incluindo falhas e prompt injection |
| v0.7 — Observability and tracing | Traces, latência, tokens e custo | Medir execuções e verificar remoção de dados sensíveis da telemetria |
| v1.0 — Complete incident investigation agent | Integrar investigação e relatório com ferramentas autorizadas | Demonstrar cenário completo com evidências, limites, aprovação e avaliação |

A v1.0 continuará sendo um projeto educacional e de portfólio. Os detalhes de cada
fase serão definidos a partir do aprendizado e da revisão da etapa anterior.

## Revisão antes de avançar

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
