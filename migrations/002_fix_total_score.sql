-- ============================================================
-- 002_fix_total_score.sql
-- Пересоздаём total_score с COALESCE, чтобы NULL в вопросах
-- не обнулял весь балл (NULL + anything = NULL в PostgreSQL).
-- ============================================================

-- View зависит от total_score — дропаем и пересоздаём
DROP VIEW IF EXISTS call_analytics;

ALTER TABLE questionnaire_responses
    DROP COLUMN IF EXISTS total_score;

ALTER TABLE questionnaire_responses
    ADD COLUMN total_score SMALLINT GENERATED ALWAYS AS (
        COALESCE(q1_1::int,0)  + COALESCE(q1_2::int,0)  + COALESCE(q1_3::int,0)  +
        COALESCE(q2_1::int,0)  + COALESCE(q2_2::int,0)  + COALESCE(q2_3::int,0)  +
        COALESCE(q3_1::int,0)  + COALESCE(q3_2::int,0)  +
        COALESCE(q4_1::int,0)  + COALESCE(q4_2::int,0)  + COALESCE(q4_3::int,0)  + COALESCE(q4_4::int,0) +
        COALESCE(q5_1::int,0)  + COALESCE(q5_2::int,0)  + COALESCE(q5_3::int,0)  +
        COALESCE(q6_1::int,0)  + COALESCE(q6_2::int,0)  + COALESCE(q6_3::int,0)  +
        COALESCE(q7_1::int,0)  + COALESCE(q7_2::int,0)  + COALESCE(q7_3::int,0)  +
        COALESCE(q8_1::int,0)  + COALESCE(q8_2::int,0)  + COALESCE(q8_3::int,0)  +
        COALESCE(q9_1::int,0)  + COALESCE(q9_2::int,0)  +
        COALESCE(q10_1::int,0) + COALESCE(q10_2::int,0) +
        COALESCE(q11_1::int,0) + COALESCE(q11_2::int,0) + COALESCE(q11_3::int,0) +
        COALESCE(q12_1::int,0) + COALESCE(q13_1::int,0) + COALESCE(q14_1::int,0)
    ) STORED;

-- Восстанавливаем view
CREATE OR REPLACE VIEW call_analytics AS
SELECT
    c.id            AS call_id,
    c.order_id,
    c.call_date,
    c.duration_sec,
    o.name          AS operator_name,
    o.team          AS operator_team,
    qr.total_score,
    qr.q1_1, qr.q1_2, qr.q1_3,
    qr.q2_1, qr.q2_2, qr.q2_3,
    qr.q3_1, qr.q3_2,
    qr.q4_1, qr.q4_2, qr.q4_3, qr.q4_4,
    qr.q5_1, qr.q5_2, qr.q5_3,
    qr.q6_1, qr.q6_2, qr.q6_3,
    qr.q7_1, qr.q7_2, qr.q7_3,
    qr.q8_1, qr.q8_2, qr.q8_3,
    qr.q9_1, qr.q9_2,
    qr.q10_1, qr.q10_2,
    qr.q11_1, qr.q11_2, qr.q11_3,
    qr.q12_1, qr.q13_1, qr.q14_1,
    qr.filled_by_ai,
    qr.corrected_by_human,
    out.approved,
    out.redeemed,
    out.avg_check
FROM calls c
LEFT JOIN operators               o   ON c.operator_id = o.id
LEFT JOIN questionnaire_responses qr  ON c.id = qr.call_id
LEFT JOIN outcomes                out ON c.order_id = out.order_id;
