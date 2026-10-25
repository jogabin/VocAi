-- Cloud SQL 전용: pgvector 확장 + RAG 임베딩 테이블
-- Cloud SQL Studio(콘솔) 에서 01_schema.sql, 02_seed.sql 다음에 실행하세요.
-- (로컬에서는 scripts/init_db.py 가 자동으로 만들어 주므로 실행하지 않아도 됩니다)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incident_embedding (
    incident_id   BIGINT PRIMARY KEY REFERENCES incident_alert(incident_id) ON DELETE CASCADE,
    model         VARCHAR(100) NOT NULL,
    content       TEXT         NOT NULL,
    content_hash  VARCHAR(40)  NOT NULL,
    embedding     vector       NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
