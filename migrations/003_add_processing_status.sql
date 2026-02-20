-- ============================================================
-- 003_add_processing_status.sql
-- Добавляем статус обработки и поле для ошибки в таблицу calls.
-- Позволяет отслеживать прогресс и сохранять ошибки Whisper/GPT.
-- ============================================================

ALTER TABLE calls
    ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS processing_error  TEXT;
