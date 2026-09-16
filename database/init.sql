-- Script de inicialização do banco de dados (executado automaticamente pelo Docker)
-- Cria a extensão de UUID e a tabela de áudios

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS audios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_name   VARCHAR(255) NOT NULL,
    original_ext    VARCHAR(10)  NOT NULL,
    mime_type       VARCHAR(100) NOT NULL,
    size_bytes      BIGINT       NOT NULL,
    duration_sec    NUMERIC(10, 3) NOT NULL,
    sample_rate     INTEGER,
    channels        INTEGER,
    bitrate         INTEGER,
    processing_type VARCHAR(50)  NOT NULL,
    processing_params JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    path_original   TEXT         NOT NULL,
    path_processed  TEXT         NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audios_created_at ON audios (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audios_processing ON audios (processing_type);
