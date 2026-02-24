-- Migration: Scoring system v2
-- - Adds call_type to calls table
-- - Adds price_block_used, t1-t8 trigger fields to questionnaire_responses
-- Run: psql $DATABASE_URL -f scripts/migrate_scoring_v2.sql

-- 1. Add call_type to calls
ALTER TABLE calls
    ADD COLUMN IF NOT EXISTS call_type VARCHAR(20) DEFAULT 'standard';

COMMENT ON COLUMN calls.call_type IS
    'standard | short | complaint | other — тип звонка для выбора системы оценки';

-- 2. Add price_block_used to questionnaire_responses
ALTER TABLE questionnaire_responses
    ADD COLUMN IF NOT EXISTS price_block_used SMALLINT;

COMMENT ON COLUMN questionnaire_responses.price_block_used IS
    '5 = вилка цен (3+2 / 2+2), 6 = скидка на курс (2+2), 7 = базовый курс (2+1), NULL = не применимо';

-- 3. Add trigger fields (нарушения — при true балл НЕ начисляется за этот критерий)
ALTER TABLE questionnaire_responses
    ADD COLUMN IF NOT EXISTS t1 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t2 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t3 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t4 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t5 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t6 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t7 BOOLEAN,
    ADD COLUMN IF NOT EXISTS t8 BOOLEAN;

COMMENT ON COLUMN questionnaire_responses.t1 IS 'Триггер 1: грубость / оскорбление клиента';
COMMENT ON COLUMN questionnaire_responses.t2 IS 'Триггер 2: обман клиента относительно продукта/цены';
COMMENT ON COLUMN questionnaire_responses.t3 IS 'Триггер 3: давление / агрессивные продажи';
COMMENT ON COLUMN questionnaire_responses.t4 IS 'Триггер 4: некорректное завершение звонка';
COMMENT ON COLUMN questionnaire_responses.t5 IS 'Триггер 5: нарушение скрипта (критическое)';
COMMENT ON COLUMN questionnaire_responses.t6 IS 'Триггер 6: разглашение конфиденциальной информации';
COMMENT ON COLUMN questionnaire_responses.t7 IS 'Триггер 7: обсуждение конкурентов негативно';
COMMENT ON COLUMN questionnaire_responses.t8 IS 'Триггер 8: прочее критическое нарушение';

-- Verify
SELECT
    column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name IN ('calls', 'questionnaire_responses')
  AND column_name IN (
      'call_type', 'price_block_used',
      't1','t2','t3','t4','t5','t6','t7','t8'
  )
ORDER BY table_name, column_name;
