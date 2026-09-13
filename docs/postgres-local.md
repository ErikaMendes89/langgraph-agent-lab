# PostgreSQL com pgvector local

O terceiro incremento da fase 5 usa PostgreSQL 17 com pgvector 0.8.6 em Docker.
O banco armazena checkpoints do LangGraph e mantém os dados em um volume nomeado.
A extensão `vector` está habilitada e sua operação de distância foi testada.
O quarto incremento adiciona o catálogo documental, embeddings locais e busca
semântica; os contratos e o pipeline estão descritos em [rag.md](rag.md).

## Preparar e iniciar

Requisitos: Docker com Compose e Python 3.12 ou 3.13 instalado. Na raiz do projeto:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/prepare_local_db.py
docker compose up -d --wait
.venv/bin/python -m app.persistent init
```

O script gera senhas aleatórias diferentes para o administrador e a aplicação.
Não imprime os valores nem substitui credenciais existentes. `.local/` é ignorado
pelo Git e tem permissão 0700; o arquivo `pgpass` tem permissão 0600.
Os arquivos montados como secrets são legíveis pelo processo PostgreSQL no contêiner;
no host, o diretório 0700 restringe o acesso. Não remova `.local/` ao reiniciar o banco:
gerar novas senhas em arquivos não altera as senhas já armazenadas no volume.

O Compose publica somente `127.0.0.1:5433`, para evitar conflito com PostgreSQL na
porta padrão 5432. `db/init.sql` roda apenas no primeiro uso de um volume vazio:
habilita pgvector e cria `incident_lab` sem superuser, criação de bancos ou roles.
O usuário da aplicação pode criar e usar suas tabelas no schema `public`.
`app.persistent init` aplica as migrações oficiais de checkpoint e pode ser repetido.
Não executa remoção de tabelas nem limpeza de registros.

As novas dependências são `langgraph-checkpoint-postgres` (persistência oficial do
LangGraph) e `psycopg[binary]` (driver, sem exigir compilador local). A serialização
restringe a leitura dos checkpoints aos tipos seguros reconhecidos pelo LangGraph.

## Investigar e retomar depois

Com o Ollama local disponível:

```bash
export INCIDENT_LAB_ORDER_ID=123
export INCIDENT_LAB_REQUEST='Investigue o pedido 123.'
.venv/bin/python -m app.persistent start
```

Anote o UUID exibido em `Investigação:`. O programa consulta os logs fictícios,
salva a síntese e encerra aguardando aprovação. Você pode fechar o terminal e depois:

```bash
.venv/bin/python -m app.persistent show UUID_DA_INVESTIGACAO
.venv/bin/python -m app.persistent resume UUID_DA_INVESTIGACAO --approve
# Ou, para rejeitar:
.venv/bin/python -m app.persistent resume UUID_DA_INVESTIGACAO --reject
```

Substitua `UUID_DA_INVESTIGACAO` pelo identificador exibido, sem reutilizá-lo para
iniciar outra investigação. `show` permite rever o conteúdo antes de decidir.
A retomada aprova exatamente o rascunho salvo e não chama o modelo novamente.
Repetir `resume` em uma investigação concluída retorna a decisão original, mesmo
que a nova opção seja diferente. Não é possível aprovar uma investigação que falhou
antes de chegar à revisão. A orientação direta continua terminando sem aprovação.

Esta CLI sempre usa PostgreSQL e exige revisão de relatórios; não depende de
`INCIDENT_LAB_MODE` nem de `INCIDENT_LAB_REQUIRE_APPROVAL`. O comando anterior
`python -m app.main` continua disponível para o experimento em memória.
`INCIDENT_LAB_MODEL`, `INCIDENT_LAB_REQUEST` e `INCIDENT_LAB_ORDER_ID` mantêm seus contratos.
Por padrão, a conexão usa `.local/pgpass` relativo à raiz do projeto. A variável
opcional `INCIDENT_LAB_DATABASE_URL` substitui essa conexão; ao usá-la, configure
também a autenticação correspondente. Arquivos `.env` não são carregados pelo Python.

Cada comando persistente tem prazo próprio de 300 segundos, incluindo conexão,
checkpoint e execução do grafo. O tempo entre comandos não consome esse prazo.
Locks de sessão impedem duas operações simultâneas da CLI na mesma investigação;
a conexão libera o lock ao encerrar, inclusive em erro. Isso não é autenticação
nem impede alterações manuais feitas por quem tem acesso de escrita ao banco.

## Ver no DBeaver

Crie uma conexão do tipo **PostgreSQL** e preencha:

| Campo | Valor |
| --- | --- |
| Host | `127.0.0.1` |
| Porta | `5433` |
| Banco | `incident_lab` |
| Usuário | `incident_lab` |
| Senha | Conteúdo do arquivo local `.local/app_password` |

Abra esse arquivo localmente no editor para preencher a senha; não a publique ou
adicione ao repositório. Teste a conexão e abra **Schemas → public → Tables**.
As tabelas de checkpoint são `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` e
`checkpoint_migrations`. O catálogo RAG também cria `knowledge_documents` e
`document_chunks`, que armazenam as versões ativas dos documentos e seus vetores.
Parte do estado usa JSONB e parte usa serialização binária; para ler o relatório
formatado, use o comando `show`.

Consultas somente leitura para explorar:

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

SELECT thread_id, checkpoint_id, parent_checkpoint_id, metadata
FROM checkpoints
ORDER BY checkpoint_id DESC
LIMIT 20;

SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector AS distancia;
```

## Parar, preservar e verificar

```bash
docker compose stop
docker compose up -d --wait
```

Esses comandos preservam o volume `incident-lab_postgres_data`. Não remova o volume
para atualizar código ou recriar o contêiner. Antes de mudar a versão principal do
PostgreSQL ou executar novas migrações em um banco com dados úteis, faça backup do
banco e preserve as credenciais. Neste incremento não há comando automático de
rollback nem remoção de dados; voltar ao experimento em memória não modifica o banco.

Para executar a suíte com integração real:

```bash
INCIDENT_LAB_TEST_POSTGRES=true .venv/bin/python -m pytest -q -o faulthandler_timeout=15
```

Sem a variável, oito testes de integração são ignorados. Com ela, os testes adicionam
investigações sintéticas com UUIDs novos no banco configurado e preservam os registros.
Não use essa opção em um banco de produção. Foram verificados retomada após saída
de outro processo, aprovação/rejeição, repetição sem efeitos adicionais, bloqueio
concorrente, colisão de IDs, falha anterior à revisão, pgvector e permissões da role.
O modelo é controlado nos testes; não houve validação com Ollama real neste incremento.

O relatório continua simulado no estado, sem arquivo ou publicação externa.
Não há autenticação de usuários, API web, recuperação automática de falhas no modelo,
política de retenção ou estratégia de upgrade de checkpoints entre versões do grafo.

Referências: [pgvector](https://github.com/pgvector/pgvector),
[checkpointer PostgreSQL](https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres)
e [conexão PostgreSQL no DBeaver](https://dbeaver.com/docs/dbeaver/Database-driver-PostgreSQL/).
