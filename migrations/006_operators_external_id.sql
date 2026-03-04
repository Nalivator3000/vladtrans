-- ============================================================
-- 006_operators_external_id.sql
-- Добавляем external_id в операторов — ATS-идентификатор
-- ============================================================

ALTER TABLE operators
    ADD COLUMN IF NOT EXISTS external_id VARCHAR(100);

CREATE UNIQUE INDEX IF NOT EXISTS idx_operators_external_id
    ON operators(external_id)
    WHERE external_id IS NOT NULL;
