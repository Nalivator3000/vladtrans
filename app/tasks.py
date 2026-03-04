import asyncio
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.celery_app import celery_app
from app.models.models import Call, QuestionnaireResponse
from app.services.analyzer import analyze_transcript
from app.services.transcriber import transcribe_audio

log = logging.getLogger(__name__)


def _make_session():
    """Создаёт свежий async engine и сессию — нужно для Celery fork-воркеров.
    Каждый воркер должен иметь свой engine, не унаследованный от родительского процесса."""
    from app.core.config import settings
    engine = create_async_engine(settings.async_database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3)
def process_call(self, call_id: int, audio_path: str, language: str = "ka"):
    """
    Основная задача: транскрибирует звонок и заполняет анкету.
    Запускается асинхронно через Celery.
    """
    try:
        asyncio.run(_process_call_async(call_id, audio_path, language))
    except Exception as exc:
        log.error(f"[call_id={call_id}] Task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


async def _process_call_async(call_id: int, audio_path: str, language: str = "ka"):
    AsyncSessionLocal = _make_session()
    async with AsyncSessionLocal() as db:
        call = await db.get(Call, call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found in DB")

        # --- Шаг 1: Транскрипция ---
        log.info(f"[call_id={call_id}] Starting transcription: {audio_path}")
        call.processing_status = "processing"
        await db.commit()

        try:
            result = await asyncio.to_thread(transcribe_audio, audio_path, language)
        except Exception as exc:
            error_msg = f"Transcription failed: {exc}"
            log.error(f"[call_id={call_id}] {error_msg}", exc_info=True)
            call.processing_status = "error"
            call.processing_error = error_msg
            await db.commit()
            raise

        transcript = result["text"]
        duration_sec = result["duration_sec"]

        if not transcript or not transcript.strip():
            error_msg = "Transcription returned empty result"
            log.warning(f"[call_id={call_id}] {error_msg}")
            call.processing_status = "error"
            call.processing_error = error_msg
            await db.commit()
            raise ValueError(error_msg)

        # Маскируем последовательности из 5+ цифр (телефоны, номера счетов)
        transcript = re.sub(r'\d{5,}', 'xxxx', transcript)

        call.transcript_text = transcript
        # Обновляем duration_sec из реального аудио если не передан при создании
        if not call.duration_sec and duration_sec:
            call.duration_sec = duration_sec
        # ElevenLabs Scribe: $0.40/hour
        actual_duration = call.duration_sec or duration_sec
        call.transcription_cost_usd = round(actual_duration / 3600 * 0.40, 6)
        call.transcription_provider = "elevenlabs"
        log.info(f"[call_id={call_id}] Transcription done, {len(transcript)} chars, {actual_duration}s, cost=${call.transcription_cost_usd}")

        # --- Шаг 2: Анализ анкеты ---
        log.info(f"[call_id={call_id}] Starting AI analysis")
        try:
            answers = await asyncio.to_thread(analyze_transcript, transcript, language)
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
        # Извлекаем мета-поля из ответа и сохраняем в calls, а не в questionnaire_responses
        call_type = answers.pop("call_type", "standard") or "standard"
        call.call_type = call_type
        call.call_notes = answers.pop("call_notes", None)  # GPT notes for non-standard calls
        log.info(f"[call_id={call_id}] call_type={call_type}, notes={'yes' if call.call_notes else 'none'}")

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
