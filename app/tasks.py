import asyncio
from pathlib import Path

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.models import Call, QuestionnaireResponse
from app.services.transcriber import transcribe_audio
from app.services.analyzer import analyze_transcript
from sqlalchemy import select


@celery_app.task(bind=True, max_retries=3)
def process_call(self, call_id: int, audio_path: str):
    """
    Основная задача: транскрибирует звонок и заполняет анкету.
    Запускается асинхронно после получения аудио файла.
    """
    try:
        asyncio.run(_process_call_async(call_id, audio_path))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


async def _process_call_async(call_id: int, audio_path: str):
    async with AsyncSessionLocal() as db:
        call = await db.get(Call, call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")

        # 1. Транскрипция
        transcript = transcribe_audio(audio_path)
        call.transcript_text = transcript
        await db.flush()

        # 2. Анализ анкеты
        answers = analyze_transcript(transcript)

        # 3. Проверяем нет ли уже анкеты (idempotency)
        existing = await db.scalar(
            select(QuestionnaireResponse).where(QuestionnaireResponse.call_id == call_id)
        )
        if existing:
            for key, val in answers.items():
                setattr(existing, key, val)
        else:
            qr = QuestionnaireResponse(call_id=call_id, filled_by_ai=True, **answers)
            db.add(qr)

        await db.commit()
