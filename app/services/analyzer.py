import json
import logging
import os

from openai import AuthenticationError, OpenAI, RateLimitError, APIError

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
log = logging.getLogger(__name__)


def _translate_to_russian(transcript: str) -> str:
    """Переводит транскрипт на русский язык для более точного анализа GPT."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты переводчик. Переведи текст на русский язык дословно, "
                        "сохраняя структуру диалога. Не добавляй пояснений."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            temperature=0,
        )
        translated = response.choices[0].message.content
        log.info(f"Translated transcript to Russian ({len(translated)} chars)")
        return translated
    except Exception as e:
        log.warning(f"Translation failed ({e}), using original transcript")
        return transcript

EXPECTED_FIELDS = {
    "q1_1", "q1_2", "q1_3",
    "q2_1", "q2_2", "q2_3",
    "q3_1", "q3_2",
    "q4_1", "q4_2", "q4_3", "q4_4",
    "q5_1", "q5_2", "q5_3",
    "q6_1", "q6_2", "q6_3",
    "q7_1", "q7_2", "q7_3",
    "q8_1", "q8_2", "q8_3",
    "q9_1", "q9_2",
    "q10_1", "q10_2",
    "q11_1", "q11_2", "q11_3",
    "q12_1", "q13_1", "q14_1",
}

SYSTEM_PROMPT = """Ты — аналитик качества звонков грузинского колл-центра.
Тебе дают транскрипт телефонного разговора между оператором и клиентом.
Транскрипт на русском языке (переведён с грузинского автоматически, может содержать неточности).
Оценивай смысл и контекст разговора целиком, не придираясь к точным формулировкам.
Твоя задача — оценить работу оператора по чек-листу и вернуть результат в формате JSON.

Правила:
- true  — критерий выполнен (даже частично / неточно)
- false — критерий явно НЕ выполнен
- null  — критерий не применим к данному звонку

Верни ТОЛЬКО валидный JSON без markdown и пояснений."""

QUESTIONNAIRE_PROMPT = """Оцени звонок по следующим критериям:

1. ПРИВЕТСТВИЕ
  q1_1: Оператор поприветствовал клиента и уточнил его имя
  q1_2: Оператор представил себя и свою позицию
  q1_3: Оператор сообщил причину звонка, уточнил заказ и спросил удобно ли говорить

2. УТОЧНЕНИЕ РЕГИОНА
  q2_1: Оператор уточнил регион/город проживания клиента после приветствия
  q2_2: Уточнение города было сделано ДО выявления потребностей
  q2_3: Оператор НЕ запрашивал полный адрес на этом этапе

3. ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ
  q3_1: Оператор задал клиенту не менее 5 и не более 10 вопросов для выявления потребностей
  q3_2: Оператор узнал потребности клиента для точного предложения продукта

4. ПРЕЗЕНТАЦИЯ ПРОДУКТА
  q4_1: Оператор презентовал продукт с акцентом на ключевые преимущества
  q4_2: Оператор рассказал о поэтапном/постепенном действии продукта
  q4_3: Оператор описал как продукт решает конкретные потребности клиента
  q4_4: Оператор упоминал характеристики продукта БЕЗ озвучивания цены

5. ПРЕЗЕНТАЦИЯ ВИЛКИ ЦЕН (курсы 3+2 и 2+2)
  q5_1: Оператор объяснил почему именно эти курсы необходимы клиенту исходя из его симптомов
  q5_2: Оператор корректно назвал цену и количество упаковок каждого курса
  q5_3: В конце оператор задал вопрос с призывом сделать заказ

6. ПРЕЗЕНТАЦИЯ СКИДКИ НА КУРС 2+2
  q6_1: Оператор объяснил почему компания может сделать скидку
  q6_2: Оператор корректно назвал цену и количество упаковок со скидкой
  q6_3: В конце оператор задал вопрос с призывом оформить заказ со скидкой

7. ПРЕЗЕНТАЦИЯ БАЗОВОГО КУРСА (2+1)
  q7_1: Оператор объяснил почему именно этот курс необходим клиенту
  q7_2: Оператор корректно назвал цену и количество упаковок
  q7_3: В конце оператор задал вопрос с призывом сделать заказ

8. ПРОРАБОТКА ВОЗРАЖЕНИЯ (после базового курса)
  q8_1: Оператор принял позицию клиента (не спорил)
  q8_2: Оператор аргументировал с использованием выявленных потребностей клиента
  q8_3: В конце оператор задал вопрос с призывом оформить курс

9. КОРРЕКТНОСТЬ ДАННЫХ В CRM
  q9_1: Оператор записал ФИО клиента и корректный адрес
  q9_2: Оператор указал верное количество упаковок и цену

10. ИНФОРМАЦИЯ О ДОСТАВКЕ
  q10_1: Оператор назвал актуальную информацию о сроках доставки
  q10_2: Оператор выбрал и предложил самый быстрый способ доставки

11. УСТНЫЙ ДОГОВОР
  q11_1: Оператор проинформировал о заключении устного договора по регламенту компании
  q11_2: Оператор озвучил обязательства компании (отправить товар) и клиента (выкупить)
  q11_3: Оператор задал вопрос "вы согласны?" в конце

12. ИНФОРМАЦИЯ О БОНУСЕ
  q12_1: Оператор сообщил клиенту о бонусе/подарке

13. ПРОЩАНИЕ
  q13_1: Оператор вежливо попрощался с клиентом

14. ПЕРЕЗВОН
  q14_1: Оператор сделал попытку перезвонить клиенту (если была необходимость, иначе null)

Верни JSON строго в таком формате:
{
  "q1_1": true, "q1_2": true, "q1_3": false,
  "q2_1": true, "q2_2": true, "q2_3": true,
  "q3_1": false, "q3_2": true,
  "q4_1": true, "q4_2": false, "q4_3": true, "q4_4": true,
  "q5_1": true, "q5_2": true, "q5_3": false,
  "q6_1": true, "q6_2": true, "q6_3": true,
  "q7_1": false, "q7_2": false, "q7_3": false,
  "q8_1": true, "q8_2": true, "q8_3": false,
  "q9_1": true, "q9_2": true,
  "q10_1": true, "q10_2": false,
  "q11_1": true, "q11_2": true, "q11_3": true,
  "q12_1": true,
  "q13_1": true,
  "q14_1": null
}"""


def analyze_transcript(transcript: str, language: str = "ka") -> dict:
    """
    Анализирует транскрипт звонка и возвращает заполненную анкету.
    Если язык не русский/английский — переводит транскрипт на русский перед анализом.
    Бросает RuntimeError при ошибках API (нет токенов, auth, quota и т.д.).
    """
    analysis_text = transcript
    if language not in ("ru", "en"):
        log.info(f"Translating transcript from '{language}' to Russian for analysis")
        analysis_text = _translate_to_russian(transcript)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{QUESTIONNAIRE_PROMPT}\n\nТРАНСКРИПТ ЗВОНКА:\n{analysis_text}"},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except AuthenticationError as e:
        raise RuntimeError(f"OpenAI auth error (проверь OPENAI_API_KEY): {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"OpenAI rate limit / quota exceeded: {e}") from e
    except APIError as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e

    raw = response.choices[0].message.content
    log.debug(f"GPT raw response: {raw[:200]}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GPT returned invalid JSON: {e}\nRaw: {raw[:500]}") from e

    # Если GPT пропустил поля — заполняем None и логируем предупреждение
    missing = EXPECTED_FIELDS - set(data.keys())
    if missing:
        log.warning(f"GPT response missing fields: {missing} — filling with None")
        for field in missing:
            data[field] = None

    # Возвращаем только известные поля (защита от мусора в ответе)
    return {k: v for k, v in data.items() if k in EXPECTED_FIELDS}
