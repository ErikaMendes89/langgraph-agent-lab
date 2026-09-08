# Notas de estudo — v0.1

## O que é um StateGraph

`StateGraph` é a estrutura usada para definir um workflow cujos nós compartilham um
contrato de estado. Em `app/agents/graph.py`, construímos o fluxo e depois compilamos
um objeto executável:

```python
builder = StateGraph(InvestigationState)
builder.add_node("agent", agent)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)
return builder.compile()
```

Construir e compilar não executa o nó. A execução começa quando `app/main.py` chama
`build_graph().invoke({"request": request})`.

## State: os dados da execução

O contrato de `app/agents/state.py` é:

```python
class InvestigationState(TypedDict):
    request: str
    response: NotRequired[str]
```

`request` entra com a solicitação. `response` ainda não existe na entrada e é
preenchido pelo nó. `NotRequired` permite a ausência da chave; não significa
que seu valor pode ser `None`. TypedDict ajuda a checagem estática, mas não valida
dados em runtime. Por isso o nó também verifica tipo e conteúdo.

## Nodes: as unidades de trabalho

Um nó é uma função que recebe estado e devolve uma atualização. `agent`, em
`app/agents/nodes.py`, valida `request`, remove espaços das extremidades para exibição
e retorna um `AgentUpdate` contendo somente `response`.

O nome `agent` identifica a etapa no grafo; nesta fase não existe inteligência de
LLM. A resposta é determinística e informa que nenhuma investigação foi realizada.
O nó não altera o dicionário de entrada. Devolver somente os campos produzidos
torna explícito o que cada etapa modifica.

## Edges, START e END

Arestas definem a sequência. `START` é o marcador de entrada e `END` é o marcador de
término; não são funções de negócio. As duas chamadas `add_edge` dizem: execute
`agent` ao iniciar e encerre quando ele terminar. Não há condições, loops ou tools.

## Como o estado percorre o grafo

Para a entrada `{"request": "Investigue o pedido 123."}`:

1. `START` encaminha a execução ao nó `agent`.
2. O nó lê `request` e devolve `{"response": "Solicitação recebida: ..."}`.
3. LangGraph aplica a atualização ao estado, mantendo `request`.
4. `END` encerra a execução e `invoke` entrega o estado resultante.

Não definimos reducers customizados; uma nova atualização de um campo substitui seu
valor. Não há histórico de mensagens nem persistência entre invocações. O teste
`test_graph_preserves_request_and_returns_demo_response` verifica tanto o resultado
quanto a emissão de uma única atualização do nó `agent` por `stream`.
`test_invocations_do_not_share_state` verifica a independência das chamadas.

## Por que LangGraph em vez de simplesmente chamar um LLM

Uma chamada direta é suficiente para muitas tarefas de uma única etapa. Aqui usamos
LangGraph para aprender a coordenar etapas, estado e transições que futuramente
envolverão ferramentas, decisões e aprovação humana. Um LLM poderá ser usado dentro
de um nó; ele não define sozinho esse controle de execução.

Na v0.1, uma função Python comum faria o mesmo trabalho com menos estrutura.
O grafo foi escolhido intencionalmente como exercício, preparando a compreensão das
próximas fases, sem afirmar que todo problema precisa desse mecanismo.

## Decisões arquiteturais desta versão

- **Sem LLM:** aprender fluxo e estado sem credenciais, rede ou custo de tokens.
- **TypedDict:** contrato pequeno, sem criar modelos e dependências de validação extras.
- **Atualização parcial tipada:** `AgentUpdate` descreve apenas o campo produzido.
- **Construção explícita:** `build_graph()` permite testar invocações isoladamente.
- **Configuração na borda:** `get_request()` lê ambiente; o nó recebe dados diretamente.
- **Erros visíveis:** configuração inválida encerra a CLI com código 1; o grafo rejeita
  entrada inválida com `ValueError`, e falhas inesperadas não são escondidas.
- **Ferramentas e avaliações reservadas:** diretórios documentados, sem implementação
  especulativa antes da aprovação da próxima fase.
- **pytest, Ruff e mypy:** comportamento, lint/formatação e contratos estáticos.

## Exercícios sugeridos

Execute o exemplo, altere `INCIDENT_LAB_REQUEST` e observe o resultado. Depois tente
um valor vazio. Leia os testes para comparar erro de configuração e erro no nó.
Explique por que `request` continua no resultado mesmo sem ser retornado por `agent`.

Referência: [Graph API oficial](https://docs.langchain.com/oss/python/langgraph/use-graph-api).
