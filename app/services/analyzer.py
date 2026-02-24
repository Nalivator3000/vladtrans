import json
import logging
import os

from openai import AuthenticationError, OpenAI, RateLimitError, APIError

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
log = logging.getLogger(__name__)


def _translate_to_english(transcript: str) -> str:
    """
    Переводит транскрипт на английский язык для более точного анализа GPT.
    Использует gpt-4o — он лучше восстанавливает смысл из корявой автотранскрипции.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a translator. This is an automatic transcription of a call center "
                        "phone conversation in Georgian. The text may contain recognition errors. "
                        "Translate to English as accurately as possible, restoring the meaning. "
                        "Preserve the dialogue structure. Do not add explanations."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            temperature=0,
        )
        translated = response.choices[0].message.content
        log.info(f"Translated transcript to English ({len(translated)} chars)")
        return translated
    except Exception as e:
        log.warning(f"Translation failed ({e}), using original transcript")
        return transcript


# Все поля, которые мы ожидаем в ответе GPT
EXPECTED_FIELDS = {
    # Блоки 1-4
    "q1_1", "q1_2", "q1_3",
    "q2_1", "q2_2", "q2_3",
    "q3_1", "q3_2",
    "q4_1", "q4_2", "q4_3", "q4_4",
    # Блоки 5/6/7 (один из трёх)
    "q5_1", "q5_2", "q5_3",
    "q6_1", "q6_2", "q6_3",
    "q7_1", "q7_2", "q7_3",
    # Блоки 8-14
    "q8_1", "q8_2", "q8_3",
    "q9_1", "q9_2",
    "q10_1", "q10_2",
    "q11_1", "q11_2", "q11_3",
    "q12_1", "q13_1", "q14_1",
    # Мета-поля
    "price_block_used",   # integer: 5, 6, 7, или null
    "call_type",          # "standard" | "short" | "complaint" | "other"
    "call_notes",         # free-form GPT notes (required for non-standard, optional for standard)
    # Триггеры (нарушения)
    "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8",
}

SYSTEM_PROMPT = """You are a quality analyst for a Georgian call center.
You are given an English transcript (automatically translated from Georgian — may contain translation errors).
Your task: evaluate the operator's work using the checklist and return a JSON result.

Rules:
- true  — criterion is met (even partially or imprecisely)
- false — criterion is clearly NOT met
- null  — criterion is not applicable to this call

Return ONLY valid JSON without markdown or explanations."""

QUESTIONNAIRE_PROMPT = """First, determine the call type:
- "standard": full sales call (greeting → needs identification → product presentation → price → CRM → closing)
- "short": brief call (callback scheduling, address clarification, call lasted < 2 minutes with no full script)
- "complaint": the client is making a complaint, not a sales call
- "other": anything else not fitting above categories (strange/suspicious call, wrong number, silent call, etc.)

CALL_NOTES RULES (field "call_notes"):
- For "short" calls: briefly describe what the call was about (e.g. "Client called to clarify delivery address. Operator confirmed address and said goodbye.")
- For "complaint" calls: describe the complaint topic, how the operator handled it, and the outcome.
- For "other" / suspicious calls: describe what was strange or suspicious (e.g. "Silent call, no speech detected", "Client was abusive and hung up", "Possible test call", "Wrong number").
- For "standard" calls: fill call_notes ONLY if there is something notable (unusual objection, suspicious behavior, script deviation worth flagging). Otherwise set to null.

For "short", "complaint", and "other" calls: set all questionnaire fields to null EXCEPT those sections that clearly apply. Always fill call_type.

---

BLOCKS 1–4 (apply to all standard calls):

1. GREETING
  q1_1: Operator greeted the client and clarified their name
  q1_2: Operator introduced themselves and their role
  q1_3: Operator stated the reason for the call, clarified the order, and asked if it's convenient to talk

2. REGION CLARIFICATION
  q2_1: Operator clarified the client's region/city after the greeting
  q2_2: City was clarified BEFORE identifying needs
  q2_3: Operator did NOT ask for the full address at this stage

3. NEEDS IDENTIFICATION
  q3_1: Operator asked the client at least 5 and no more than 10 questions to identify needs [WORTH 2 POINTS]
  q3_2: Operator identified the client's needs to make an accurate product offer

4. PRODUCT PRESENTATION
  q4_1: Operator presented the product emphasizing key benefits
  q4_2: Operator explained the gradual/staged effect of the product
  q4_3: Operator described how the product solves the client's specific needs
  q4_4: Operator mentioned product characteristics WITHOUT stating the price

---

BLOCKS 5, 6, 7 — MUTUALLY EXCLUSIVE (choose ONE that matches the call):

Determine which price presentation block was used in this call:
- Block 5 (price_block_used=5): operator presented TWO course options (3+2 and 2+2) as a "price fork"
- Block 6 (price_block_used=6): operator presented a DISCOUNT on the 2+2 course (after block 5 was rejected)
- Block 7 (price_block_used=7): operator presented the BASIC course (2+1, cheapest option)
- null (price_block_used=null): no price presentation occurred (short call, complaint, etc.)

Set the questions of the TWO unused blocks to null.

5. PRICE FORK PRESENTATION (courses 3+2 and 2+2) — only if price_block_used=5
  q5_1: Operator explained why exactly these courses are needed based on the client's symptoms
  q5_2: Operator correctly stated the price and number of packages for each course
  q5_3: Operator ended with a closing question prompting an order

6. DISCOUNT PRESENTATION (discounted 2+2 course) — only if price_block_used=6
  q6_1: Operator explained why the company can offer a discount
  q6_2: Operator correctly stated the discounted price and number of packages
  q6_3: Operator ended with a closing question prompting an order at the discounted price

7. BASIC COURSE PRESENTATION (2+1) — only if price_block_used=7
  q7_1: Operator explained why exactly this course is needed for the client
  q7_2: Operator correctly stated the price and number of packages
  q7_3: Operator ended with a closing question prompting an order

---

BLOCKS 8–14 (apply to standard calls; set null if not applicable):

8. OBJECTION HANDLING (after basic course)
  q8_1: Operator accepted the client's position (did not argue)
  q8_2: Operator argued using the client's previously identified needs
  q8_3: Operator ended with a closing question prompting the client to place the order

9. CRM DATA ACCURACY
  q9_1: Operator recorded the client's full name and correct address
  q9_2: Operator specified the correct number of packages and price

10. DELIVERY INFORMATION
  q10_1: Operator provided up-to-date information about delivery timeframes
  q10_2: Operator selected and offered the fastest delivery method

11. VERBAL AGREEMENT
  q11_1: Operator informed the client about the verbal agreement per company regulations
  q11_2: Operator stated the company's obligations (ship goods) and client's obligations (accept/pay)
  q11_3: Operator asked "do you agree?" at the end

12. BONUS INFORMATION
  q12_1: Operator informed the client about a bonus/gift

13. FAREWELL
  q13_1: Operator said a polite farewell

14. CALLBACK
  q14_1: Operator made an attempt to call back the client (if necessary; otherwise null)

---

TRIGGERS — critical violations (true = violation detected, false = no violation):
  t1: Rudeness / insult toward the client
  t2: Deception of the client (product properties or price)
  t3: Pressure / aggressive sales tactics
  t4: Improper call termination (hung up abruptly, was rude at end)
  t5: Critical script violation (skipped mandatory section without reason)
  t6: Disclosure of confidential information
  t7: Negative discussion of competitors by name
  t8: Other critical violation not covered above

---

Return JSON in exactly this format:
{
  "call_type": "standard",
  "call_notes": null,
  "price_block_used": 5,
  "q1_1": true, "q1_2": true, "q1_3": false,
  "q2_1": true, "q2_2": true, "q2_3": true,
  "q3_1": false, "q3_2": true,
  "q4_1": true, "q4_2": false, "q4_3": true, "q4_4": true,
  "q5_1": true, "q5_2": true, "q5_3": false,
  "q6_1": null, "q6_2": null, "q6_3": null,
  "q7_1": null, "q7_2": null, "q7_3": null,
  "q8_1": true, "q8_2": true, "q8_3": false,
  "q9_1": true, "q9_2": true,
  "q10_1": true, "q10_2": false,
  "q11_1": true, "q11_2": true, "q11_3": true,
  "q12_1": true,
  "q13_1": true,
  "q14_1": null,
  "t1": false, "t2": false, "t3": false, "t4": false,
  "t5": false, "t6": false, "t7": false, "t8": false
}"""


# Поля анкеты (без мета-полей call_type, price_block_used, триггеров)
QUESTIONNAIRE_FIELDS = {
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
TRIGGER_FIELDS = {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"}
META_FIELDS = {"price_block_used", "call_type", "call_notes"}


def analyze_transcript(transcript: str, language: str = "ka") -> dict:
    """
    Анализирует транскрипт звонка и возвращает заполненную анкету.
    Если язык не русский/английский — переводит транскрипт на английский перед анализом.
    Бросает RuntimeError при ошибках API.
    """
    analysis_text = transcript
    if language not in ("ru", "en"):
        log.info(f"Translating transcript from '{language}' to English for analysis")
        analysis_text = _translate_to_english(transcript)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{QUESTIONNAIRE_PROMPT}\n\nCALL TRANSCRIPT:\n{analysis_text}"},
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
    log.debug(f"GPT raw response: {raw[:300]}")

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
