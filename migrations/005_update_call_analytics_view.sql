-- ============================================================
-- 005_update_call_analytics_view.sql
-- Обновляем VIEW call_analytics:
--   + call_type, call_notes, language, processing_status
--   + transcription_provider, transcription_cost_usd
--   + price_block_used, t1-t8 (триггеры)
--   + total_score_correct — правильный подсчёт (q3_1=2б, блоки 5/6/7 взаимоисключающие)
--   + triggers_count — число сработавших триггеров
-- ============================================================

DROP VIEW IF EXISTS call_analytics;

CREATE VIEW call_analytics AS
SELECT
    -- Основная информация о звонке
    c.id                        AS call_id,
    c.order_id,
    c.call_date,
    c.duration_sec,
    c.language,
    c.call_type,
    c.call_notes,
    c.processing_status,
    c.transcription_provider,
    c.transcription_cost_usd,

    -- Оператор
    o.name                      AS operator_name,
    o.team                      AS operator_team,

    -- Скоринг: правильный подсчёт
    --   q3_1 = 2 балла, блоки 5/6/7 взаимоисключающие по price_block_used
    qr.price_block_used,
    (
        -- Блок 1: Приветствие (макс 3)
        COALESCE(qr.q1_1::int,0) + COALESCE(qr.q1_2::int,0) + COALESCE(qr.q1_3::int,0) +
        -- Блок 2: Уточнение региона (макс 3)
        COALESCE(qr.q2_1::int,0) + COALESCE(qr.q2_2::int,0) + COALESCE(qr.q2_3::int,0) +
        -- Блок 3: Выявление потребности (q3_1=2б, q3_2=1б, макс 3)
        COALESCE(qr.q3_1::int,0) * 2 + COALESCE(qr.q3_2::int,0) +
        -- Блок 4: Презентация продукта (макс 4)
        COALESCE(qr.q4_1::int,0) + COALESCE(qr.q4_2::int,0) + COALESCE(qr.q4_3::int,0) + COALESCE(qr.q4_4::int,0) +
        -- Блоки 5/6/7: только активный (макс 3)
        CASE
            WHEN qr.price_block_used = 5 THEN
                COALESCE(qr.q5_1::int,0) + COALESCE(qr.q5_2::int,0) + COALESCE(qr.q5_3::int,0)
            WHEN qr.price_block_used = 6 THEN
                COALESCE(qr.q6_1::int,0) + COALESCE(qr.q6_2::int,0) + COALESCE(qr.q6_3::int,0)
            WHEN qr.price_block_used = 7 THEN
                COALESCE(qr.q7_1::int,0) + COALESCE(qr.q7_2::int,0) + COALESCE(qr.q7_3::int,0)
            ELSE GREATEST(
                COALESCE(qr.q5_1::int,0) + COALESCE(qr.q5_2::int,0) + COALESCE(qr.q5_3::int,0),
                COALESCE(qr.q6_1::int,0) + COALESCE(qr.q6_2::int,0) + COALESCE(qr.q6_3::int,0),
                COALESCE(qr.q7_1::int,0) + COALESCE(qr.q7_2::int,0) + COALESCE(qr.q7_3::int,0)
            )
        END +
        -- Блок 8: Возражения (макс 3)
        COALESCE(qr.q8_1::int,0) + COALESCE(qr.q8_2::int,0) + COALESCE(qr.q8_3::int,0) +
        -- Блок 9: CRM (макс 2)
        COALESCE(qr.q9_1::int,0) + COALESCE(qr.q9_2::int,0) +
        -- Блок 10: Доставка (макс 2)
        COALESCE(qr.q10_1::int,0) + COALESCE(qr.q10_2::int,0) +
        -- Блок 11: Устный договор (макс 3)
        COALESCE(qr.q11_1::int,0) + COALESCE(qr.q11_2::int,0) + COALESCE(qr.q11_3::int,0) +
        -- Блок 12: Бонус (макс 1)
        COALESCE(qr.q12_1::int,0) +
        -- Блок 13: Прощание (макс 1)
        COALESCE(qr.q13_1::int,0) +
        -- Блок 14: Перезвон (макс 1)
        COALESCE(qr.q14_1::int,0)
    )                           AS total_score,

    -- Детали скоринга по блокам
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

    -- Триггеры (критические нарушения)
    qr.t1, qr.t2, qr.t3, qr.t4, qr.t5, qr.t6, qr.t7, qr.t8,
    (
        COALESCE(qr.t1::int,0) + COALESCE(qr.t2::int,0) + COALESCE(qr.t3::int,0) +
        COALESCE(qr.t4::int,0) + COALESCE(qr.t5::int,0) + COALESCE(qr.t6::int,0) +
        COALESCE(qr.t7::int,0) + COALESCE(qr.t8::int,0)
    )                           AS triggers_count,

    -- Мета
    qr.filled_by_ai,
    qr.corrected_by_human,

    -- Итоги продажи
    out.approved,
    out.redeemed,
    out.avg_check

FROM calls c
LEFT JOIN operators               o   ON c.operator_id = o.id
LEFT JOIN questionnaire_responses qr  ON c.id = qr.call_id
LEFT JOIN outcomes                out ON c.order_id = out.order_id;
