-- ============================================================
-- 001_init.sql — начальная схема БД аналитики звонков
-- ============================================================

-- Операторы
CREATE TABLE operators (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    team        VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Звонки
CREATE TABLE calls (
    id              SERIAL PRIMARY KEY,
    order_id        VARCHAR(100) NOT NULL,
    operator_id     INTEGER REFERENCES operators(id),
    call_date       TIMESTAMPTZ NOT NULL,
    duration_sec    INTEGER,
    audio_url       TEXT,
    transcript_text TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calls_order_id    ON calls(order_id);
CREATE INDEX idx_calls_operator_id ON calls(operator_id);
CREATE INDEX idx_calls_call_date   ON calls(call_date);

-- Анкеты (1 балл за каждый подпункт, итого макс 34)
CREATE TABLE questionnaire_responses (
    id       SERIAL PRIMARY KEY,
    call_id  INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,

    -- 1. Приветствие (макс 3)
    q1_1  BOOLEAN,  -- Приветствие клиента, уточнение имени
    q1_2  BOOLEAN,  -- Представить себя и свою позицию
    q1_3  BOOLEAN,  -- Сообщить причину звонка, уточнение заказа и удобно ли говорить

    -- 2. Уточнение региона (макс 3)
    q2_1  BOOLEAN,  -- Уточнение региона/города после приветствия
    q2_2  BOOLEAN,  -- Уточнение города до выявления потребностей
    q2_3  BOOLEAN,  -- Не запрашивать полный адрес на этом этапе

    -- 3. Выявление потребности (макс 2)
    q3_1  BOOLEAN,  -- Задать клиенту не менее 5, но не более 10 вопросов
    q3_2  BOOLEAN,  -- Узнать потребности клиента для точного предложения

    -- 4. Презентация продукта (макс 4)
    q4_1  BOOLEAN,  -- Презентовать продукт с акцентом на ключевые преимущества
    q4_2  BOOLEAN,  -- Рассказать о поэтапном действии продукта
    q4_3  BOOLEAN,  -- Описать как продукт решает потребности клиента
    q4_4  BOOLEAN,  -- Упоминание характеристик продукта без озвучивания цены

    -- 5. Презентация вилки цен 3+2 и 2+2 (макс 3)
    q5_1  BOOLEAN,  -- Объяснить почему именно эти курсы необходимы клиенту
    q5_2  BOOLEAN,  -- Назвать корректно цену и количество упаковок каждого курса
    q5_3  BOOLEAN,  -- Задать вопрос в конце с призывом сделать заказ

    -- 6. Презентация скидки на курс 2+2 (макс 3)
    q6_1  BOOLEAN,  -- Объяснить почему можем сделать скидку
    q6_2  BOOLEAN,  -- Назвать корректно цену и количество упаковок
    q6_3  BOOLEAN,  -- Задать вопрос в конце с призывом сделать заказ

    -- 7. Презентация базового курса 2+1 (макс 3)
    q7_1  BOOLEAN,  -- Объяснить почему именно этот курс необходим клиенту
    q7_2  BOOLEAN,  -- Назвать корректно цену и количество упаковок
    q7_3  BOOLEAN,  -- Задать вопрос в конце с призывом сделать заказ

    -- 8. Проработка возражения (макс 3)
    q8_1  BOOLEAN,  -- Принятие позиции клиента
    q8_2  BOOLEAN,  -- Аргументация с использованием потребности клиента
    q8_3  BOOLEAN,  -- Вопрос в конце с призывом оформить курс

    -- 9. Корректность данных в CRM (макс 2)
    q9_1  BOOLEAN,  -- Записать ФИО клиента и корректный адрес
    q9_2  BOOLEAN,  -- Указать верное количество упаковок и цену

    -- 10. Информация о доставке (макс 2)
    q10_1 BOOLEAN,  -- Назвать актуальную информацию о сроках доставки
    q10_2 BOOLEAN,  -- Выбрать и предложить самый быстрый способ доставки

    -- 11. Устный договор (макс 3)
    q11_1 BOOLEAN,  -- Проинформировать о заключении УД по регламенту
    q11_2 BOOLEAN,  -- Озвучить обязательства компании и клиента
    q11_3 BOOLEAN,  -- Задать вопрос в конце "вы согласны?"

    -- 12. Информация о бонусе (макс 1)
    q12_1 BOOLEAN,  -- Оператор озвучил о бонусе/подарке

    -- 13. Прощание (макс 1)
    q13_1 BOOLEAN,  -- Оператор вежливо попрощался

    -- 14. Перезвон (макс 1)
    q14_1 BOOLEAN,  -- Оператор сделал попытку перезвонить (если была необходимость)

    -- Метаданные заполнения
    filled_by_ai        BOOLEAN DEFAULT TRUE,
    corrected_by_human  BOOLEAN DEFAULT FALSE,
    total_score         SMALLINT GENERATED ALWAYS AS (
        (q1_1::int  + q1_2::int  + q1_3::int) +
        (q2_1::int  + q2_2::int  + q2_3::int) +
        (q3_1::int  + q3_2::int) +
        (q4_1::int  + q4_2::int  + q4_3::int  + q4_4::int) +
        (q5_1::int  + q5_2::int  + q5_3::int) +
        (q6_1::int  + q6_2::int  + q6_3::int) +
        (q7_1::int  + q7_2::int  + q7_3::int) +
        (q8_1::int  + q8_2::int  + q8_3::int) +
        (q9_1::int  + q9_2::int) +
        (q10_1::int + q10_2::int) +
        (q11_1::int + q11_2::int + q11_3::int) +
        q12_1::int  + q13_1::int + q14_1::int
    ) STORED,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_qr_call_id ON questionnaire_responses(call_id);

-- Результаты заказов (для корреляций)
CREATE TABLE outcomes (
    id          SERIAL PRIMARY KEY,
    order_id    VARCHAR(100) NOT NULL UNIQUE,
    approved    BOOLEAN,
    redeemed    BOOLEAN,
    avg_check   NUMERIC(10, 2),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outcomes_order_id ON outcomes(order_id);

-- View для аналитики: всё в одном запросе
CREATE VIEW call_analytics AS
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
LEFT JOIN operators             o   ON c.operator_id = o.id
LEFT JOIN questionnaire_responses qr ON c.id = qr.call_id
LEFT JOIN outcomes              out ON c.order_id = out.order_id;
