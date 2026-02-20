-- ============================================================
-- 001_init.sql — начальная схема БД аналитики звонков
-- ============================================================

CREATE TABLE IF NOT EXISTS operators (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    team        VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calls (
    id              SERIAL PRIMARY KEY,
    order_id        VARCHAR(100) NOT NULL,
    operator_id     INTEGER REFERENCES operators(id),
    call_date       TIMESTAMPTZ NOT NULL,
    duration_sec    INTEGER,
    audio_url       TEXT,
    transcript_text TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calls_order_id    ON calls(order_id);
CREATE INDEX IF NOT EXISTS idx_calls_operator_id ON calls(operator_id);
CREATE INDEX IF NOT EXISTS idx_calls_call_date   ON calls(call_date);

CREATE TABLE IF NOT EXISTS questionnaire_responses (
    id       SERIAL PRIMARY KEY,
    call_id  INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,

    -- 1. Приветствие (макс 3)
    q1_1  BOOLEAN,
    q1_2  BOOLEAN,
    q1_3  BOOLEAN,

    -- 2. Уточнение региона (макс 3)
    q2_1  BOOLEAN,
    q2_2  BOOLEAN,
    q2_3  BOOLEAN,

    -- 3. Выявление потребности (макс 2)
    q3_1  BOOLEAN,
    q3_2  BOOLEAN,

    -- 4. Презентация продукта (макс 4)
    q4_1  BOOLEAN,
    q4_2  BOOLEAN,
    q4_3  BOOLEAN,
    q4_4  BOOLEAN,

    -- 5. Презентация вилки цен 3+2 и 2+2 (макс 3)
    q5_1  BOOLEAN,
    q5_2  BOOLEAN,
    q5_3  BOOLEAN,

    -- 6. Презентация скидки на курс 2+2 (макс 3)
    q6_1  BOOLEAN,
    q6_2  BOOLEAN,
    q6_3  BOOLEAN,

    -- 7. Презентация базового курса 2+1 (макс 3)
    q7_1  BOOLEAN,
    q7_2  BOOLEAN,
    q7_3  BOOLEAN,

    -- 8. Проработка возражения (макс 3)
    q8_1  BOOLEAN,
    q8_2  BOOLEAN,
    q8_3  BOOLEAN,

    -- 9. Корректность данных в CRM (макс 2)
    q9_1  BOOLEAN,
    q9_2  BOOLEAN,

    -- 10. Информация о доставке (макс 2)
    q10_1 BOOLEAN,
    q10_2 BOOLEAN,

    -- 11. Устный договор (макс 3)
    q11_1 BOOLEAN,
    q11_2 BOOLEAN,
    q11_3 BOOLEAN,

    -- 12. Информация о бонусе (макс 1)
    q12_1 BOOLEAN,

    -- 13. Прощание (макс 1)
    q13_1 BOOLEAN,

    -- 14. Перезвон (макс 1)
    q14_1 BOOLEAN,

    filled_by_ai        BOOLEAN DEFAULT TRUE,
    corrected_by_human  BOOLEAN DEFAULT FALSE,

    -- COALESCE чтобы NULL считался как 0, а не обнулял весь score
    total_score SMALLINT GENERATED ALWAYS AS (
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
    ) STORED,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_qr_call_id ON questionnaire_responses(call_id);

CREATE TABLE IF NOT EXISTS outcomes (
    id          SERIAL PRIMARY KEY,
    order_id    VARCHAR(100) NOT NULL UNIQUE,
    approved    BOOLEAN,
    redeemed    BOOLEAN,
    avg_check   NUMERIC(10, 2),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outcomes_order_id ON outcomes(order_id);

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
