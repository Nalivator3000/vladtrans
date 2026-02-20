-- ============================================================
-- 004_add_language.sql
-- Добавляем поле language в таблицу calls.
-- Используется для настройки транскрипции: 'ka' = Georgian (translate),
-- 'ru', 'en' и др. = транскрипция с явным языком.
-- ============================================================

ALTER TABLE calls
    ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'ka';
