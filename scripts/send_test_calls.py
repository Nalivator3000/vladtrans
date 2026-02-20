#!/usr/bin/env python3
"""
Тестовый отправщик звонков.

Использование:
    python scripts/send_test_calls.py

Кладёшь аудио файлы (.mp3 / .wav / .ogg / .m4a) в папку test_audio/,
запускаешь скрипт — он отправляет каждый файл на POST /calls/upload
и сохраняет результат в test_audio/sent_calls.json.

Настройки — переменные окружения или .env:
    API_URL  — базовый URL API  (по умолчанию http://localhost:8000)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")
AUDIO_DIR = Path(__file__).resolve().parent.parent / "test_audio"
SENT_LOG = AUDIO_DIR / "sent_calls.json"

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".webm"}


def load_sent() -> dict:
    if SENT_LOG.exists():
        return json.loads(SENT_LOG.read_text())
    return {}


def save_sent(data: dict):
    SENT_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def send_file(path: Path, operator_id: int | None = None) -> dict:
    with open(path, "rb") as f:
        response = httpx.post(
            f"{API_URL}/calls/upload",
            files={"file": (path.name, f, "audio/mpeg")},
            data={
                "order_id": path.stem,                         # имя файла как order_id
                "call_date": datetime.now(timezone.utc).isoformat(),
                **({"operator_id": str(operator_id)} if operator_id else {}),
            },
            timeout=60,
        )
    response.raise_for_status()
    return response.json()


def main():
    if not AUDIO_DIR.exists():
        print(f"Папка {AUDIO_DIR} не найдена. Создайте её и положите в неё аудио файлы.")
        sys.exit(1)

    audio_files = [
        p for p in sorted(AUDIO_DIR.iterdir())
        if p.suffix.lower() in AUDIO_EXTENSIONS
    ]

    if not audio_files:
        print(f"В папке {AUDIO_DIR} нет аудио файлов ({', '.join(AUDIO_EXTENSIONS)}).")
        sys.exit(0)

    sent = load_sent()
    new_count = 0

    for path in audio_files:
        key = path.name
        if key in sent:
            print(f"  SKIP  {key}  (уже отправлен, call_id={sent[key]['call_id']})")
            continue

        print(f"  SEND  {key} ...", end=" ", flush=True)
        try:
            result = send_file(path)
            sent[key] = {
                "call_id": result["call_id"],
                "status": result["status"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
            save_sent(sent)
            print(f"OK  call_id={result['call_id']}")
            new_count += 1
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nОтправлено: {new_count} новых файлов. Лог: {SENT_LOG}")
    print(f"Проверить результаты: python scripts/check_results.py")


if __name__ == "__main__":
    main()
