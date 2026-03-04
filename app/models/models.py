from datetime import datetime
from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, Numeric,
    SmallInteger, String, Text, TIMESTAMP
)
from sqlalchemy.orm import DeclarativeBase, relationship

# Максимальный балл для каждого блока (вилка / скидка / базовый одинаковы = 3)
MAX_SCORE_BY_BLOCK = {
    "standard": 29,   # 3+3+3+4+3+3+2+2+3+1+1+1 (один из блоков 5/6/7)
    "short":    None,  # определяется по ненулевым полям
    "complaint": None,
    "other":    None,
}


class Base(DeclarativeBase):
    pass


class Operator(Base):
    __tablename__ = "operators"

    id          = Column(Integer, primary_key=True)
    external_id = Column(String(100), unique=True, index=True)  # ATS-идентификатор
    name        = Column(String(255), nullable=False)
    team        = Column(String(100))
    created_at  = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    calls = relationship("Call", back_populates="operator")


class Call(Base):
    __tablename__ = "calls"

    id              = Column(Integer, primary_key=True)
    order_id        = Column(String(100), nullable=False, index=True)
    operator_id     = Column(Integer, ForeignKey("operators.id"))
    call_date       = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    duration_sec    = Column(Integer)
    audio_url           = Column(Text)
    language            = Column(String(10), default="ka")        # ISO-639-1 язык звонка
    transcript_text     = Column(Text)
    call_type               = Column(String(20), default="standard")  # standard/short/complaint/other
    call_notes              = Column(Text)    # GPT-generated notes (required for non-standard calls)
    transcription_provider  = Column(String(20), default="elevenlabs")
    transcription_cost_usd  = Column(Numeric(10, 6))
    processing_status       = Column(String(20), default="pending")   # pending/processing/done/error
    processing_error        = Column(Text)
    created_at              = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    operator             = relationship("Operator", back_populates="calls")
    questionnaire        = relationship("QuestionnaireResponse", back_populates="call", uselist=False)


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id      = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True)

    # 1. Приветствие (макс 3)
    q1_1 = Column(Boolean)  # Приветствие клиента, уточнение имени
    q1_2 = Column(Boolean)  # Представить себя и свою позицию
    q1_3 = Column(Boolean)  # Сообщить причину звонка, уточнение заказа, удобно ли говорить

    # 2. Уточнение региона (макс 3)
    q2_1 = Column(Boolean)  # Уточнение региона/города после приветствия
    q2_2 = Column(Boolean)  # Уточнение города до выявления потребностей
    q2_3 = Column(Boolean)  # Не запрашивать полный адрес на этом этапе

    # 3. Выявление потребности (макс 2)
    q3_1 = Column(Boolean)  # Задать клиенту 5-10 вопросов
    q3_2 = Column(Boolean)  # Узнать потребности для точного предложения

    # 4. Презентация продукта (макс 4)
    q4_1 = Column(Boolean)  # Презентовать с акцентом на ключевые преимущества
    q4_2 = Column(Boolean)  # Рассказать о поэтапном действии продукта
    q4_3 = Column(Boolean)  # Описать как продукт решает потребности клиента
    q4_4 = Column(Boolean)  # Упоминание характеристик без озвучивания цены

    # 5. Презентация вилки цен 3+2 и 2+2 (макс 3)
    q5_1 = Column(Boolean)  # Объяснить почему эти курсы необходимы клиенту
    q5_2 = Column(Boolean)  # Назвать корректно цену и количество упаковок каждого курса
    q5_3 = Column(Boolean)  # Задать вопрос с призывом сделать заказ

    # 6. Презентация скидки на курс 2+2 (макс 3)
    q6_1 = Column(Boolean)  # Объяснить почему можем сделать скидку
    q6_2 = Column(Boolean)  # Назвать корректно цену и количество упаковок
    q6_3 = Column(Boolean)  # Задать вопрос с призывом сделать заказ

    # 7. Презентация базового курса 2+1 (макс 3)
    q7_1 = Column(Boolean)  # Объяснить почему этот курс необходим клиенту
    q7_2 = Column(Boolean)  # Назвать корректно цену и количество упаковок
    q7_3 = Column(Boolean)  # Задать вопрос с призывом сделать заказ

    # 8. Проработка возражения (макс 3)
    q8_1 = Column(Boolean)  # Принятие позиции клиента
    q8_2 = Column(Boolean)  # Аргументация с использованием потребности клиента
    q8_3 = Column(Boolean)  # Вопрос в конце с призывом оформить курс

    # 9. Корректность данных в CRM (макс 2)
    q9_1 = Column(Boolean)  # Записать ФИО клиента и корректный адрес
    q9_2 = Column(Boolean)  # Указать верное количество упаковок и цену

    # 10. Информация о доставке (макс 2)
    q10_1 = Column(Boolean)  # Назвать актуальную информацию о сроках доставки
    q10_2 = Column(Boolean)  # Предложить самый быстрый способ доставки

    # 11. Устный договор (макс 3)
    q11_1 = Column(Boolean)  # Проинформировать о заключении УД по регламенту
    q11_2 = Column(Boolean)  # Озвучить обязательства компании и клиента
    q11_3 = Column(Boolean)  # Задать вопрос "вы согласны?"

    # 12. Информация о бонусе (макс 1)
    q12_1 = Column(Boolean)  # Озвучил о бонусе/подарке

    # 13. Прощание (макс 1)
    q13_1 = Column(Boolean)  # Вежливо попрощался

    # 14. Перезвон (макс 1)
    q14_1 = Column(Boolean)  # Сделал попытку перезвонить

    # Блок цен: какой вариант использовался в звонке (5=вилка, 6=скидка, 7=базовый)
    price_block_used = Column(SmallInteger)  # 5 | 6 | 7 | NULL

    # Триггеры — критические нарушения (true = нарушение зафиксировано)
    t1 = Column(Boolean)  # Грубость / оскорбление клиента
    t2 = Column(Boolean)  # Обман клиента (продукт / цена)
    t3 = Column(Boolean)  # Давление / агрессивные продажи
    t4 = Column(Boolean)  # Некорректное завершение звонка
    t5 = Column(Boolean)  # Критическое нарушение скрипта
    t6 = Column(Boolean)  # Разглашение конфиденциальной информации
    t7 = Column(Boolean)  # Негативное обсуждение конкурентов
    t8 = Column(Boolean)  # Прочее критическое нарушение

    filled_by_ai       = Column(Boolean, default=True)
    corrected_by_human = Column(Boolean, default=False)
    created_at         = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    call = relationship("Call", back_populates="questionnaire")

    @property
    def total_score(self) -> int:
        """
        Подсчёт баллов:
        - q3_1 стоит 2 балла (остальные — 1)
        - блоки 5, 6, 7 — взаимоисключающие (учитывается только тот, что в price_block_used)
        - триггеры не добавляют и не вычитают баллы (хранятся отдельно)
        """
        score = 0

        # Блоки 1-4 (1б каждый)
        for f in [self.q1_1, self.q1_2, self.q1_3,
                  self.q2_1, self.q2_2, self.q2_3,
                  self.q3_2,
                  self.q4_1, self.q4_2, self.q4_3, self.q4_4]:
            if f is True:
                score += 1

        # q3_1 стоит 2 балла
        if self.q3_1 is True:
            score += 2

        # Блок 5, 6 или 7 (зависит от price_block_used)
        if self.price_block_used == 5:
            for f in [self.q5_1, self.q5_2, self.q5_3]:
                if f is True:
                    score += 1
        elif self.price_block_used == 6:
            for f in [self.q6_1, self.q6_2, self.q6_3]:
                if f is True:
                    score += 1
        elif self.price_block_used == 7:
            for f in [self.q7_1, self.q7_2, self.q7_3]:
                if f is True:
                    score += 1
        else:
            # price_block_used не определён — считаем лучший из трёх блоков
            b5 = sum(1 for f in [self.q5_1, self.q5_2, self.q5_3] if f is True)
            b6 = sum(1 for f in [self.q6_1, self.q6_2, self.q6_3] if f is True)
            b7 = sum(1 for f in [self.q7_1, self.q7_2, self.q7_3] if f is True)
            score += max(b5, b6, b7)

        # Блоки 8-14 (1б каждый)
        for f in [self.q8_1, self.q8_2, self.q8_3,
                  self.q9_1, self.q9_2,
                  self.q10_1, self.q10_2,
                  self.q11_1, self.q11_2, self.q11_3,
                  self.q12_1, self.q13_1, self.q14_1]:
            if f is True:
                score += 1

        return score

    @property
    def triggers_fired(self) -> list[str]:
        """Список триггеров, которые сработали (true)."""
        result = []
        for i, t in enumerate([self.t1, self.t2, self.t3, self.t4,
                                self.t5, self.t6, self.t7, self.t8], start=1):
            if t is True:
                result.append(f"t{i}")
        return result


class Outcome(Base):
    __tablename__ = "outcomes"

    id         = Column(Integer, primary_key=True)
    order_id   = Column(String(100), nullable=False, unique=True, index=True)
    approved   = Column(Boolean)
    redeemed   = Column(Boolean)
    avg_check  = Column(Numeric(10, 2))
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
