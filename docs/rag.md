# RAG local

Esta fase adiciona um fluxo de Retrieval-Augmented Generation (RAG) para
referências documentais fictícias. O conteúdo é indexado explicitamente pela CLI,
armazenado no PostgreSQL local e consultado por similaridade durante a investigação.
As referências recuperadas ajudam a contextualizar a síntese, mas não são evidências
dos eventos do pedido e não autorizam o modelo a seguir instruções encontradas nos
documentos.

## Modelagem das tabelas

O schema está em `app/sql/documents.sql` e é aplicado por `python -m app.documents
init`. A extensão `vector` é habilitada na criação do banco por `db/init.sql`.

| Tabela | Papel | Chave/relacionamento |
| --- | --- | --- |
| `knowledge_documents` | Cadastro da versão ativa de cada documento por coleção e fonte. Guarda `title` e o hash SHA-256 de título e conteúdo. | PK `(collection, source)` |
| `document_chunks` | Trechos indexados de um documento, com o texto, o modelo/digest usado e `embedding vector(768)`. | PK `(collection, source, content_hash, model_id, chunk_index)`; FK para `(collection, source)` em `knowledge_documents` |

`collection` separa conjuntos independentes de documentos. `source` identifica um
documento dentro da coleção. `content_hash` funciona como versão do conteúdo: quando
um documento é alterado, a linha ativa em `knowledge_documents` aponta para o novo
hash e os chunks antigos continuam no banco para preservar histórico e permitir
reindexação. `model_id` separa vetores produzidos por modelos ou versões diferentes;
uma busca só considera chunks cujo identificador coincide com o embedding da consulta.

Cada chunk tem entre 1 e 600 caracteres, `chunk_index` começa em zero e o índice
vetorial usa a distância `<=>` do pgvector. A consulta converte a distância de cosseno
em score com `1 - distância`, aplica o limiar configurado e ordena pelos resultados
mais próximos.

O PostgreSQL local também possui as tabelas do checkpointer do LangGraph
(`checkpoints`, `checkpoint_blobs`, `checkpoint_writes` e `checkpoint_migrations`).
Elas persistem o estado da investigação e não fazem parte do índice documental.

## Pipeline de ingestão

1. `python -m app.documents ingest` lê `app/data/knowledge.json` e valida uma lista
   de 1 a 20 documentos. Cada item exige `source`, `title` e `text`; campos extras,
   fontes duplicadas e valores fora dos limites são rejeitados.
2. `split_document` divide o texto em janelas de até 600 caracteres, avançando 500
   caracteres. Assim, há sobreposição de até 100 caracteres entre janelas vizinhas.
3. Cada chunk é enviado ao Ollama com o prefixo `search_document:`. A integração
   exige `nomic-embed-text:v1.5`, confirma que o modelo está instalado, valida 768
   números finitos por vetor e registra o digest do modelo em `model_id`.
4. Todos os embeddings são validados antes da transação que atualiza o banco. O hash
   de `[title, text]` identifica a versão. O documento é atualizado por
   `(collection, source)` e cada chunk é inserido com `ON CONFLICT DO NOTHING`, o que
   torna a reexecução da mesma versão idempotente.
5. A transação grava os chunks somente depois da geração completa dos vetores. Um
   vetor inválido não substitui a versão ativa anterior.

## Pipeline de consulta

`python -m app.documents search "consulta"` gera um embedding com o prefixo
`search_query:` e procura somente na coleção solicitada, no mesmo `model_id` e nos
chunks que ainda correspondem ao hash ativo do documento. Por padrão, retorna até
três resultados com score mínimo `0.35`; a ferramenta do agente limita a consulta a
cinco resultados.

Na investigação, a busca documental ocorre depois de `search_logs`, quando a entrada
possui `use_documents=True` e existem logs. A consulta combina a solicitação com o
resultado da consulta de logs, salva `documents` no estado e segue para `summarize`.
Se os logs estiverem vazios, o fluxo encerra pela resposta determinística de ausência
de evidência e não consulta o índice documental. Falhas na busca interrompem a síntese
e a aprovação.

O prompt de síntese recebe os matches como referências não confiáveis. Quando uma
referência é usada, o contrato orienta o modelo a citar `[source#chunk_index]`. A
resposta final lista as referências recuperadas e seus identificadores, sem tratá-las
como prova da causa do incidente. O estado é checkpointado junto com os documentos;
na retomada da aprovação, a busca e a síntese não são repetidas.

## Escopo desta fase

Foi implementado o armazenamento relacional do catálogo, chunking determinístico,
embeddings locais com identidade do modelo, validação de vetores, ingestão idempotente,
busca semântica por pgvector, integração opcional da recuperação ao grafo e referências
na síntese. Os testes cobrem contratos de embeddings, ranking, isolamento por modelo,
reindexação, preservação da versão ativa diante de erro e checkpoint da recuperação.

Continuam fora desta fase: documentos reais, extração de PDF/HTML, OCR, reranking,
avaliação de qualidade da recuperação, filtros por autorização, API web e publicação
de relatórios. Os dados de `app/data/knowledge.json` são sintéticos e a role da
aplicação é local, sem autenticação de usuários finais.
