-- =============================================================================
-- DDL: Modelo Relacional Normalizado (3NF) - Consulta de Acordos Jurídicos
-- Hierarquia: Autor (1) -> (N) Acordos (1) -> (N) Documentos
-- =============================================================================

CREATE TABLE IF NOT EXISTS autores (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    telefone VARCHAR(100) NOT NULL,
    endereco VARCHAR(500) NOT NULL,
    empresa_nome VARCHAR(255) NOT NULL,
    empresa_segmento VARCHAR(255) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acordos (
    id INTEGER PRIMARY KEY,
    autor_id INTEGER NOT NULL,
    titulo VARCHAR(500) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_acordos_autor
        FOREIGN KEY (autor_id)
        REFERENCES autores (id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY,
    acordo_id INTEGER NOT NULL,
    titulo VARCHAR(500) NOT NULL,
    url VARCHAR(1000) NOT NULL,
    thumbnail_url VARCHAR(1000) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_documentos_acordo
        FOREIGN KEY (acordo_id)
        REFERENCES acordos (id)
        ON DELETE CASCADE
);

-- Índices de performance para consultas relacionais, filtros e joins
CREATE INDEX IF NOT EXISTS idx_autores_nome ON autores (nome);
CREATE INDEX IF NOT EXISTS idx_autores_email ON autores (email);
CREATE INDEX IF NOT EXISTS idx_autores_empresa_segmento ON autores (empresa_segmento);
CREATE INDEX IF NOT EXISTS idx_acordos_autor_id ON acordos (autor_id);
CREATE INDEX IF NOT EXISTS idx_documentos_acordo_id ON documentos (acordo_id);

-- Trigger para atualizar automaticamente a coluna atualizado_em
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_timestamp_autores ON autores;
CREATE TRIGGER set_timestamp_autores
BEFORE UPDATE ON autores
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

DROP TRIGGER IF EXISTS set_timestamp_acordos ON acordos;
CREATE TRIGGER set_timestamp_acordos
BEFORE UPDATE ON acordos
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

DROP TRIGGER IF EXISTS set_timestamp_documentos ON documentos;
CREATE TRIGGER set_timestamp_documentos
BEFORE UPDATE ON documentos
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();
