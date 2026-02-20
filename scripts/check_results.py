#!/usr/bin/env python3
"""
Тестовый приёмщик результатов.

Использование:
    python scripts/check_results.py

Читает test_audio/sent_calls.json (создаётся send_test_calls.py),
опрашивает GET /calls/{id}/results для каждого отправленного звонка
и выводит сводную таблицу с результатами.

Настройки:
    API_URL  — базовый URL API  (по умолчанию http://localhost:8000)
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")
AUDIO_DIR = Path(__file__).resolve().parent.parent / "test_audio"
SENT_LOG = AUDIO_DIR / "sent_calls.json"

# Группировка вопросов для читаемого вывода
SECTIONS = {
    "1. Приветствие":        ["q1_1", "q1_2", "q1_3"],
    "2. Регион":             ["q2_1", "q2_2", "q2_3"],
    "3. Потребность":        ["q3_1", "q3_2"],
    "4. Продукт":            ["q4_1", "q4_2", "q4_3", "q4_4"],
    "5. Вилка цен":          ["q5_1", "q5_2", "q5_3"],
    "6. Скидка 2+2":         ["q6_1", "q6_2", "q6_3"],
    "7. Базовый курс":       ["q7_1", "q7_2", "q7_3"],
    "8. Возражение":         ["q8_1", "q8_2", "q8_3"],
    "9. Данные CRM":         ["q9_1", "q9_2"],
    "10. Доставка":          ["q10_1", "q10_2"],
    "11. Устный договор":    ["q11_1", "q11_2", "q11_3"],
    "12. Бонус":             ["q12_1"],
    "13. Прощание":          ["q13_1"],
    "14. Перезвон":          ["q14_1"],
}


def bool_icon(val: bool | None) -> str:
    if val is True:
        return "✓"
    if val is False:
        return "✗"
    return "—"  # null = не применимо


def fetch_results(call_id: int) -> dict:
    r = httpx.get(f"{API_URL}/calls/{call_id}/results", timeout=15)
    r.raise_for_status()
    return r.json()


def print_call_result(filename: str, call_id: int, data: dict):
    status = data.get("status")
    print(f"\n{'=' * 60}")
    print(f"Файл:    {filename}")
    print(f"call_id: {call_id}  |  order_id: {data.get('order_id', '—')}")
    print(f"Статус:  {status}")

    if status != "done":
        return

    score = data.get("total_score", 0)
    max_score = data.get("max_score", 34)
    pct = round(score / max_score * 100) if max_score else 0
    print(f"Балл:    {score}/{max_score}  ({pct}%)")
    print(f"AI:      {'да' if data.get('filled_by_ai') else 'нет'}  |  "
          f"Скорректировано: {'да' if data.get('corrected_by_human') else 'нет'}")

    questionnaire = data.get("questionnaire", {})
    print()
    for section, fields in SECTIONS.items():
        icons = "  ".join(f"{f}={bool_icon(questionnaire.get(f))}" for f in fields)
        print(f"  {section:<22} {icons}")

    transcript = data.get("transcript", "")
    if transcript:
        print(f"\nТранскрипт (первые 300 символов):")
        print(f"  {transcript[:300]}{'...' if len(transcript) > 300 else ''}")


def main():
    if not SENT_LOG.exists():
        print(f"Лог {SENT_LOG} не найден. Сначала запустите send_test_calls.py.")
        sys.exit(1)

    sent = json.loads(SENT_LOG.read_text())
    if not sent:
        print("Нет отправленных звонков.")
        sys.exit(0)

    summary = []

    for filename, info in sent.items():
        call_id = info["call_id"]
        try:
            data = fetch_results(call_id)
            print_call_result(filename, call_id, data)
            summary.append((filename, call_id, data.get("status"), data.get("total_score")))
        except Exception as e:
            print(f"\n[ERROR] {filename} (call_id={call_id}): {e}")
            summary.append((filename, call_id, "error", None))

    # Итоговая сводка
    print(f"\n{'=' * 60}")
    print(f"{'СВОДКА':^60}")
    print(f"{'=' * 60}")
    print(f"{'Файл':<35} {'ID':>5} {'Статус':<12} {'Балл':>5}")
    print(f"{'-' * 60}")
    for fname, cid, st, sc in summary:
        score_str = str(sc) if sc is not None else "—"
        print(f"{fname:<35} {cid:>5} {st:<12} {score_str:>5}")


if __name__ == "__main__":
    main()
