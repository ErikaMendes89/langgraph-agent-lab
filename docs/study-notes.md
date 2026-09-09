# Notas de estudo — v0.1 ao início da v0.4

As primeiras seções registram o exemplo inicial, preservado no modo `demo`. A seção
da v0.2 registra a primeira rodada de tool calling. Os exemplos dessa seção descrevem
o código daquela versão. As seções da v0.3 e v0.4 explicam o roteamento e o
tratamento de falhas do código atual.

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

## v0.2 — Do pedido de ferramenta à resposta

Nesta etapa, estou praticando a diferença entre o modelo **solicitar** uma ferramenta
e o programa **executá-la**. Em `app/agents/graph.py`:

```python
builder.add_node("agent", partial(request_logs, model=model.bind_tools([search_logs])))
builder.add_node("tools", ToolNode([search_logs], handle_tool_errors=False))
builder.add_node("summarize", partial(summarize, model=model))
```

`bind_tools` informa ao modelo o nome, a descrição e o schema da ferramenta. Isso não
executa `search_logs`. `partial` fixa o argumento `model` da função, deixando o estado
para ser fornecido pelo grafo; não é uma nova camada de serviços.

Uma resposta controlada usada em `tests/test_tool_graph.py` mostra o protocolo:

```python
AIMessage(
    content="",
    tool_calls=[{"name": "search_logs", "args": {"order_id": "123"}, "id": "call-1"}],
)
```

O `ToolNode` executa a ferramenta registrada e produz um `ToolMessage` com
`tool_call_id="call-1"`. Esse identificador liga o resultado à solicitação original.
O teste `test_tool_round_trip_passes_evidence_back_to_model` verifica que o resultado
real da tool, serializado como JSON, chega à segunda chamada do modelo.

## Histórico de mensagens no state

O estado ganhou este campo em `app/agents/state.py`:

```python
messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
```

`add_messages` é um reducer: combina a atualização com o histórico existente em vez
de substituir a lista inteira. Mensagens com o mesmo ID são atualizadas. Neste fluxo,
o histórico acumula mensagem de sistema, solicitação humana, pedido de ferramenta,
resultado da ferramenta e síntese final. `response` continua sendo a saída da CLI.

`summarize` troca a instrução de sistema enviada na segunda chamada para pedir uma
síntese baseada nas evidências. O histórico armazenado mantém a mensagem inicial.
Não existe memória persistente: a próxima chamada com somente `request` começa de novo.

## Schema e erros também fazem parte do aprendizado

`SearchLogsInput`, em `app/tools/logs.py`, usa Pydantic com modo estrito e proíbe campos
extras. `order_id` deve ser uma string de 1 a 12 dígitos. Essa é uma escolha para o
exercício, não uma regra de um sistema real. A consulta retorna dados novos a cada
chamada, impedindo que uma alteração no resultado contamine a próxima execução.

Aprendi também que `ToolNode` encapsula a falha de validação em `ToolInvocationError`,
mantendo `ValidationError` como causa. Com `handle_tool_errors=False`, ela interrompe
o fluxo em vez de virar uma resposta que o modelo poderia tentar corrigir. A CLI
mostra uma mensagem explícita. O teste verifica o erro e sua causa.

O grafo exige exatamente uma chamada válida. Uma resposta sem tool call é um erro
nesta versão, e não uma rota alternativa. Isso mantém o foco na v0.2: escolher entre
ferramenta e resposta final será o exercício de roteamento condicional da v0.3.

## Decisões da v0.2

- **Ollama local:** permite experimentar sem API key; exige servidor e modelo instalados.
- **Modo demo preservado:** posso revisitar a v0.1 sem precisar iniciar um modelo.
- **Logs sintéticos:** pratico o protocolo sem consultar dados pessoais ou sistemas reais.
- **Fluxo fixo:** duas chamadas ao modelo e uma à tool, sem loop de agente ainda.
- **Síntese sem tools:** a segunda chamada usa o modelo original; novas tool calls são rejeitadas.
- **Testes isolados:** respostas controladas substituem apenas o modelo. O grafo e a tool
  continuam reais, mas isso não mede a capacidade do Qwen3 de seguir instruções.
- **Dependências explícitas:** `langchain-ollama` integra o provedor; `langchain-core` e
  `pydantic`, já transitivas, passam a ser declaradas por serem importadas diretamente.

## Experimentos seguintes

Com Ollama instalado, comparar os pedidos `123` e `456`, observando a diferença entre
evidência fictícia e ausência de evidência. Tentar uma solicitação sem ID e observar
se o modelo respeita a instrução de não inventar um pedido. Essa última propriedade
ainda não é garantida pelo código. Registrar falhas, latência e versões do modelo
antes de tirar conclusões sobre sua qualidade.

Referências: [tools e ToolNode](https://docs.langchain.com/oss/python/langchain/tools)
e [ChatOllama](https://docs.langchain.com/oss/python/integrations/chat/ollama).

## v0.3 — Escolhendo o próximo passo

Na v0.2, toda execução com modelo precisava de uma ferramenta. Agora estou praticando
uma alternativa: o modelo pode responder diretamente, inclusive pedindo informações
que faltam. Em `app/agents/graph.py`, substituí a aresta fixa após `agent` por:

```python
builder.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "done": END})
```

`route_after_agent`, em `app/agents/tool_nodes.py`, recebe o estado atualizado pelo
nó e examina a última `AIMessage`. Se houver `tool_calls`, retorna `tools`; caso
contrário, retorna `done`. O dicionário mapeia esse resultado para o próximo destino.
O retorno está tipado como `Literal["tools", "done"]` para explicitar as opções.

O roteador não é outro LLM e não executa a ferramenta. Ele toma uma decisão
determinística sobre a estrutura da resposta produzida pelo modelo. Não procura
palavras como “pedido” no texto do usuário para escolher a rota.

| Resposta do modelo | Caminho | Chamadas ao modelo | Consultas à tool |
| --- | --- | --- | --- |
| Texto sem tool call | `agent -> END` | 1 | 0 |
| Uma tool call válida | `agent -> tools -> summarize -> END` | 2 | 1 |
| Tool call malformada ou múltipla | Erro antes do roteamento | 1 | 0 |

## O que mudou nos nós

`request_logs` passou a se chamar `call_agent`, pois agora também recebe respostas
sem consulta. `AgentDecisionUpdate` contém as mensagens e um campo `response`
opcional: a resposta direta preenche esse campo; a rota de tool deixa a síntese
preenchê-lo depois.

`format_response` reúne a validação final que as duas rotas compartilham: o texto
deve ser não vazio e não pode pedir novas ferramentas. Ela também acrescenta o
aviso de laboratório com dados fictícios. Isso evita duplicar o contrato de saída.

Uma resposta que contém texto **e** uma tool call segue para a ferramenta. Já uma
chamada em `invalid_tool_calls` é rejeitada por `call_agent`, mesmo que exista texto
aparentemente válido. Não quero transformar uma falha de protocolo em sucesso.

## Como verifiquei as rotas

Em `tests/test_tool_graph.py`, os testes usam `stream(..., stream_mode="updates")`
para observar quais nós realmente executaram:

- `test_direct_response_ends_without_tool_or_second_model_call` verifica somente
  `agent`, uma chamada ao modelo e a resposta final disponível.
- `test_tool_call_with_text_takes_tool_route_and_finishes` verifica `agent`, `tools`
  e `summarize`, com duas chamadas ao modelo.
- `test_route_is_recomputed_for_each_invocation` alterna entre consulta, resposta
  direta e outra consulta no mesmo grafo, sem reaproveitar histórico ou resposta anterior.

Os testes anteriores de argumentos inválidos, ferramenta desconhecida, síntese vazia
e falha do provedor continuam verificando regressões.

## Limites do que aprendi nesta etapa

A rota direta permite ao modelo perguntar “Qual é o ID do pedido?”, mas os testes
usam essa resposta pronta. Eles provam o caminho executado a partir dela, não que um
LLM real fará a pergunta correta. O modelo ainda pode escolher mal ou inventar fatos.

As duas rotas terminam sem loops. Não adicionei conversa persistente: após um pedido
de esclarecimento, a próxima execução precisa receber novamente a solicitação completa.
Políticas de limite, timeout, retry e validações adicionais ficam para a v0.4.

Referência: [arestas condicionais na Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).

## v0.4 — Primeiro incremento: comunicação com o Ollama

Durante a execução local, a conexão foi recusada porque o servidor não estava
disponível em `localhost:11434`. Iniciar `ollama serve` em outro terminal e baixar
o modelo permitiu obter o relatório. Isso mostrou a diferença entre instalar a
integração Python e manter o servidor do modelo em execução.

`create_model` agora passa `Timeout(120.0, connect=5.0)` por `client_kwargs`.
São 5 segundos para conectar e 120 segundos para as demais operações de rede.
O timeout de leitura mede a espera entre blocos recebidos; uma resposta que continua
enviando blocos pode durar mais de 120 segundos. Ainda não há prazo total do grafo.

A CLI trata conexão recusada e timeout com mensagem em stderr e código 1, sem
imprimir relatório parcial ou repetir a chamada. Outros erros inesperados continuam
visíveis. HTTPX já era transitivo e passou a ser dependência direta por ser importado.

Os testes simulam falhas no agente e na síntese, verificando que não há saída de
sucesso nem chamadas extras. Um teste usa o ChatOllama real com envio HTTP substituído
para verificar os timeouts na requisição sem acessar a rede. Esses testes não
comprovam o desempenho do modelo real nem simulam a passagem de 120 segundos.

Validação deste incremento: 57 testes aprovados, Ruff (lint e formato), mypy e
`git diff --check` sem problemas. Retries limitados e prazo total continuam pendentes.

Referências: [timeouts do HTTPX](https://www.python-httpx.org/advanced/timeouts/) e
[client_kwargs do ChatOllama](https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama/client_kwargs).
