-- Migração aditiva. Mantém versões antigas para não apagar dados na reindexação.
CREATE TABLE IF NOT EXISTS knowledge_documents (
    collection TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (collection, source)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    collection TEXT NOT NULL,
    source TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 600),
    model_id TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    PRIMARY KEY (collection, source, content_hash, model_id, chunk_index),
    FOREIGN KEY (collection, source) REFERENCES knowledge_documents (collection, source)
);
