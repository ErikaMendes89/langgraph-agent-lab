# Arquitetura

## Escopo da v0.1

Laboratório educacional, sem alegação de experiência profissional ou uso em produção.
O caminho implementado é `START -> agent -> END`. A execução é síncrona, local e
determinística; não exige um provedor de LLM.

| Arquivo/diretório | Responsabilidade |
| --- | --- |
| `app/main.py` | Entrada CLI, configuração, invocação e saída |
| `app/core/config.py` | Ler `INCIDENT_LAB_REQUEST` e validar configuração |
| `app/agents/state.py` | Contrato tipado `InvestigationState` |
| `app/agents/nodes.py` | Validar solicitação e retornar `AgentUpdate` |
| `app/agents/graph.py` | Construir e compilar o grafo |
| `app/tools/` | Reserva para ferramentas futuras |
| `tests/` | Testes determinísticos de comportamento |
| `evals/` | Reserva para avaliações futuras |

## Contratos e fluxo

1. A CLI lê a variável de ambiente ou usa a solicitação de exemplo.
2. `build_graph()` cria um grafo independente, sem instância global.
3. `invoke({"request": request})` inicia o estado.
4. `agent` verifica se `request` é um texto não vazio e retorna apenas `response`.
5. LangGraph aplica a atualização, preservando `request`, e chega a `END`.
6. A CLI imprime a resposta e retorna código 0.

`response` é opcional no estado inicial. Não há reducers customizados: a atualização
substitui o valor do campo correspondente. O nó não modifica o dicionário recebido.
O estado não persiste após a execução e não existe memória compartilhada entre chamadas.

## Erros e segurança atual

Configuração vazia recebe mensagem em stderr e código 1. Entrada direta inválida no
grafo gera `ValueError`. Erros inesperados são propagados, preservando o diagnóstico;
não são convertidos em uma falsa resposta de sucesso.

Não há credenciais ou integrações externas no código da aplicação. `.gitignore`
exclui ambientes virtuais, caches e `.env`, preservando `.env.example`.
A resposta ecoa a solicitação no terminal, por isso os exemplos devem ser sintéticos.
Não existem ainda controles completos para dados sensíveis ou exposição como serviço.

## Evolução planejada

O nó poderá usar um LLM e solicitar tools. `search_logs`, `get_customer`, `search_docs`
e `create_report` são candidatas, sem APIs ou regras de negócio definidas nesta fase.
Primeiro usaremos cenários e dados sintéticos. As versões seguintes estudarão
roteamento, validação, orçamento de execução, aprovação humana, avaliação e tracing.
Persistência e efeitos externos exigirão decisões sobre autorização, idempotência,
retenção e recuperação de falhas antes de sua implementação.

Não foram adicionados servidor web, banco, camada de serviços, fábrica de provedores
ou framework de configuração. A separação atual é suficiente para entender o fluxo
e evoluir responsabilidades sem abstrações prematuras.
