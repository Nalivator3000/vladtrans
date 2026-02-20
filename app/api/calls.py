import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Call, QuestionnaireResponse

router = APIRouter()


class CallCreate(BaseModel):
    order_id: str
    operator_id: int | None = None
    call_date: datetime
    duration_sec: int | None = None
    audio_url: str


# --------------------------------------------------------------------------- #
# POST /calls/  — принять звонок по URL (основной эндпоинт для продакшена)
# --------------------------------------------------------------------------- #
@router.post("/", status_code=202)
async def create_call(data: CallCreate, db: AsyncSession = Depends(get_db)):
    call = Call(**data.model_dump())
    db.add(call)
    await db.commit()
    await db.refresh(call)

    from app.tasks import process_call
    process_call.delay(call.id, data.audio_url)

    return {"call_id": call.id, "status": "queued"}


# --------------------------------------------------------------------------- #
# POST /calls/upload  — загрузить аудио файл напрямую (для тестов)
# --------------------------------------------------------------------------- #
def _process_uploaded_file(call_id: int, tmp_path: str):
    """
    Фоновая задача для обработки загруженного файла.
    Запускается в том же процессе что и API (без Celery) — нужно для тестов
    когда воркер не поднят отдельно.
    """
    import asyncio
    from app.tasks import _process_call_async
    asyncio.run(_process_call_async(call_id, tmp_path))


@router.post("/upload", status_code=202)
async def upload_call(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    order_id: str = Form(...),
    operator_id: int | None = Form(None),
    call_date: datetime = Form(...),
    duration_sec: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Принимает аудио файл напрямую (multipart/form-data).
    Сохраняет во временный файл и обрабатывает в фоне (без Celery).
    Используется для тестов — в продакшене используй POST /calls/ с audio_url.
    """
    suffix = Path(file.filename).suffix or ".mp3"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    finally:
        tmp.close()

    call = Call(
        order_id=order_id,
        operator_id=operator_id,
        call_date=call_date,
        duration_sec=duration_sec,
        audio_url=f"local:{tmp_path}",
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    background_tasks.add_task(_process_uploaded_file, call.id, tmp_path)

    return {"call_id": call.id, "status": "queued", "filename": file.filename}


# --------------------------------------------------------------------------- #
# GET /calls/{call_id}  — базовая информация о звонке
# --------------------------------------------------------------------------- #
@router.get("/{call_id}")
async def get_call(call_id: int, db: AsyncSession = Depends(get_db)):
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "call_id": call.id,
        "order_id": call.order_id,
        "operator_id": call.operator_id,
        "call_date": call.call_date,
        "duration_sec": call.duration_sec,
        "audio_url": call.audio_url,
        "has_transcript": bool(call.transcript_text),
        "created_at": call.created_at,
    }


# --------------------------------------------------------------------------- #
# GET /calls/{call_id}/results  — результаты анализа (анкета + score)
# --------------------------------------------------------------------------- #
@router.get("/{call_id}/results")
async def get_call_results(call_id: int, db: AsyncSession = Depends(get_db)):
    """
    Возвращает результаты AI-анализа звонка: статус обработки, итоговый балл,
    ответы по каждому критерию анкеты и транскрипт.
    """
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    qr_result = await db.execute(
        select(QuestionnaireResponse).where(QuestionnaireResponse.call_id == call_id)
    )
    qr = qr_result.scalar_one_or_none()

    status = call.processing_status or "pending"

    if status in ("pending", "processing"):
        return {"call_id": call_id, "status": status}

    if status == "error":
        return {
            "call_id": call_id,
            "status": "error",
            "error": call.processing_error,
        }

    if qr is None:
        # processing_status=done но анкеты нет — что-то пошло не так
        return {"call_id": call_id, "status": "error", "error": "Questionnaire missing after processing"}

    q_fields = [
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
    ]

    return {
        "call_id": call_id,
        "status": "done",
        "order_id": call.order_id,
        "call_date": call.call_date,
        "duration_sec": call.duration_sec,
        "total_score": qr.total_score,
        "max_score": 34,
        "filled_by_ai": qr.filled_by_ai,
        "corrected_by_human": qr.corrected_by_human,
        "questionnaire": {f: getattr(qr, f) for f in q_fields},
        "transcript": call.transcript_text,
    }
