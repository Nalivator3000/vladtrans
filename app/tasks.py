import asyncio
import logging

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.models import Call, QuestionnaireResponse
from app.services.analyzer import analyze_transcript
from app.services.transcriber import transcribe_audio

log = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_call(self, call_id: int, audio_path: str):
    """
    Основная задача: транскрибирует звонок и заполняет анкету.
    Запускается асинхронно через Celery.
    """
    try:
        asyncio.run(_process_call_async(call_id, audio_path))
    except Exception as exc:
        log.error(f"[call_id={call_id}] Task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


async def _process_call_async(call_id: int, audio_path: str):
    async with AsyncSessionLocal() as db:
        call = await db.get(Call, call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found in DB")

        # --- Шаг 1: Транскрипция ---
        log.info(f"[call_id={call_id}] Starting transcription: {audio_path}")
        call.processing_status = "processing"
        await db.commit()

        try:
            transcript = transcribe_audio(audio_path)
        except Exception as exc:
            error_msg = f"Transcription failed: {exc}"
            log.error(f"[call_id={call_id}] {error_msg}", exc_info=True)
            call.processing_status = "error"
            call.processing_error = error_msg
            await db.commit()
            raise

        if not transcript or not transcript.strip():
            error_msg = "Transcription returned empty result"
            log.warning(f"[call_id={call_id}] {error_msg}")
            call.processing_status = "error"
            call.processing_error = error_msg
            await db.commit()
            raise ValueError(error_msg)

        call.transcript_text = transcript
        log.info(f"[call_id={call_id}] Transcription done, {len(transcript)} chars")

        # --- Шаг 2: Анализ анкеты ---
        log.info(f"[call_id={call_id}] Starting AI analysis")
        try:
            answers = analyze_transcript(transcript)
        except Exception as exc:
            error_msg = f"AI analysis failed: {exc}"
            log.error(f"[call_id={call_id}] {error_msg}", exc_info=True)
            call.processing_status = "error"
            call.processing_error = error_msg
            await db.commit()
            raise

        if not answers:
            error_msg = "AI analysis returned empty result"
            log.warning(f"[call_id={call_id}] {error_msg}")
            call.processing_status = "error"
            call.processing_error = error_msg
            await db.commit()
            raise ValueError(error_msg)

        log.info(f"[call_id={call_id}] AI analysis done, {len(answers)} fields")

        # --- Шаг 3: Сохранение анкеты (idempotent) ---
        existing = await db.scalar(
            select(QuestionnaireResponse).where(QuestionnaireResponse.call_id == call_id)
        )
        if existing:
            for key, val in answers.items():
                setattr(existing, key, val)
        else:
            qr = QuestionnaireResponse(call_id=call_id, filled_by_ai=True, **answers)
            db.add(qr)

        call.processing_status = "done"
        call.processing_error = None
        await db.commit()
        log.info(f"[call_id={call_id}] Processing complete")
