from datetime import datetime
from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, Numeric,
    SmallInteger, String, Text, TIMESTAMP
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Operator(Base):
    __tablename__ = "operators"

    id         = Column(Integer, primary_key=True)
    name       = Column(String(255), nullable=False)
    team       = Column(String(100))
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

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
    processing_status   = Column(String(20), default="pending")   # pending/processing/done/error
    processing_error    = Column(Text)
    created_at          = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

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

    filled_by_ai       = Column(Boolean, default=True)
    corrected_by_human = Column(Boolean, default=False)
    created_at         = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    call = relationship("Call", back_populates="questionnaire")

    @property
    def total_score(self) -> int:
        fields = [
            self.q1_1, self.q1_2, self.q1_3,
            self.q2_1, self.q2_2, self.q2_3,
            self.q3_1, self.q3_2,
            self.q4_1, self.q4_2, self.q4_3, self.q4_4,
            self.q5_1, self.q5_2, self.q5_3,
            self.q6_1, self.q6_2, self.q6_3,
            self.q7_1, self.q7_2, self.q7_3,
            self.q8_1, self.q8_2, self.q8_3,
            self.q9_1, self.q9_2,
            self.q10_1, self.q10_2,
            self.q11_1, self.q11_2, self.q11_3,
            self.q12_1, self.q13_1, self.q14_1,
        ]
        return sum(1 for f in fields if f is True)


class Outcome(Base):
    __tablename__ = "outcomes"

    id         = Column(Integer, primary_key=True)
    order_id   = Column(String(100), nullable=False, unique=True, index=True)
    approved   = Column(Boolean)
    redeemed   = Column(Boolean)
    avg_check  = Column(Numeric(10, 2))
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
