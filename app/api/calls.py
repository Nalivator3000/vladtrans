import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Call, Operator, QuestionnaireResponse

router = APIRouter()


# --------------------------------------------------------------------------- #
# GET /calls/  — список звонков с фильтрами и пагинацией
# --------------------------------------------------------------------------- #
@router.get("/")
async def list_calls(
    db: AsyncSession = Depends(get_db),
    operator_id: Optional[str] = Query(None, description="external_id оператора в ATS"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None, description="pending/processing/done/error"),
    call_type: Optional[str] = Query(None, description="standard/short/complaint/other"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    # Базовый запрос с LEFT JOIN на анкету и оператора
    base = (
        select(
            Call.id, Call.order_id, Call.operator_id, Call.call_date,
            Call.duration_sec, Call.processing_status, Call.call_type,
            Call.created_at,
            QuestionnaireResponse.total_score if hasattr(QuestionnaireResponse, 'total_score') else None,
        )
        .outerjoin(QuestionnaireResponse, QuestionnaireResponse.call_id == Call.id)
    )

    if operator_id:
        base = base.join(Operator, Operator.id == Call.operator_id).where(
            Operator.external_id == operator_id
        )
    if date_from:
        base = base.where(Call.call_date >= date_from)
    if date_to:
        base = base.where(Call.call_date <= date_to)
    if status:
        base = base.where(Call.processing_status == status)
    if call_type:
        base = base.where(Call.call_type == call_type)

    total = await db.scalar(select(func.count()).select_from(base.subquery()))

    rows = await db.execute(
        base.order_by(Call.call_date.desc()).limit(limit).offset(offset)
    )
    items = []
    for row in rows:
        call = await db.get(Call, row[0])
        qr_result = await db.execute(
            select(QuestionnaireResponse).where(QuestionnaireResponse.call_id == call.id)
        )
        qr = qr_result.scalar_one_or_none()
        items.append({
            "call_id": call.id,
            "order_id": call.order_id,
            "operator_id": call.operator_id,
            "call_date": call.call_date,
            "duration_sec": call.duration_sec,
            "processing_status": call.processing_status,
            "call_type": call.call_type,
            "total_score": qr.total_score if qr else None,
            "created_at": call.created_at,
        })

    return {"total": total, "items": items}


class CallCreate(BaseModel):
    order_id: str
    operator_id: str | None = None  # ATS-идентификатор оператора (любая строка/число)
    call_date: datetime
    duration_sec: int | None = None
    audio_url: str
    language: str = "ka"   # ISO-639-1, default грузинский


# --------------------------------------------------------------------------- #
# POST /calls/  — принять звонок по URL (основной эндпоинт для продакшена)
# --------------------------------------------------------------------------- #
@router.post("/", status_code=202)
async def create_call(
    data: CallCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Авто-создание оператора по external_id если не существует
    internal_operator_id = None
    if data.operator_id:
        operator = await db.scalar(
            select(Operator).where(Operator.external_id == data.operator_id)
        )
        if not operator:
            operator = Operator(external_id=data.operator_id, name=data.operator_id)
            db.add(operator)
            await db.flush()
        internal_operator_id = operator.id

    call_data = data.model_dump()
    call_data["operator_id"] = internal_operator_id
    call = Call(**call_data)
    db.add(call)
    await db.commit()
    await db.refresh(call)

    from app.tasks import _process_call_async
    background_tasks.add_task(_process_call_async, call.id, data.audio_url, data.language)

    return {"call_id": call.id, "status": "queued", "language": data.language}


# --------------------------------------------------------------------------- #
# POST /calls/upload  — загрузить аудио файл напрямую (для тестов)
# --------------------------------------------------------------------------- #
async def _process_uploaded_file(call_id: int, tmp_path: str, language: str):
    """
    Фоновая задача для обработки загруженного файла.
    Async — FastAPI awaits её после отправки ответа, в том же event loop.
    """
    from app.tasks import _process_call_async
    await _process_call_async(call_id, tmp_path, language)


@router.post("/upload", status_code=202)
async def upload_call(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    order_id: str = Form(...),
    operator_id: int | None = Form(None),
    call_date: datetime = Form(...),
    duration_sec: int | None = Form(None),
    language: str = Form("ka"),
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
        language=language,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    background_tasks.add_task(_process_uploaded_file, call.id, tmp_path, language)

    return {"call_id": call.id, "status": "queued", "filename": file.filename, "language": language}


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


# --------------------------------------------------------------------------- #
# POST /calls/{call_id}/reprocess  — переобработать звонок заново
# --------------------------------------------------------------------------- #
@router.post("/{call_id}/reprocess", status_code=202)
async def reprocess_call(
    call_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not call.audio_url:
        raise HTTPException(status_code=400, detail="Call has no audio_url to reprocess")

    call.processing_status = "pending"
    call.processing_error = None
    await db.commit()

    from app.tasks import _process_call_async
    background_tasks.add_task(_process_call_async, call.id, call.audio_url, call.language or "ka")

    return {"call_id": call_id, "status": "queued"}

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
    t_fields = ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"]

    # max_score: 29 для стандартного звонка (3+3+3+4+3+3+2+2+3+1+1+1)
    # q3_1 = 2б, один из блоков 5/6/7 = 3б
    max_score = 29 if call.call_type == "standard" else None

    return {
        "call_id": call_id,
        "status": "done",
        "call_type": call.call_type,
        "call_notes": call.call_notes,
        "order_id": call.order_id,
        "call_date": call.call_date,
        "duration_sec": call.duration_sec,
        "total_score": qr.total_score,
        "max_score": max_score,
        "price_block_used": qr.price_block_used,
        "triggers": {f: getattr(qr, f) for f in t_fields},
        "triggers_fired": qr.triggers_fired,
        "filled_by_ai": qr.filled_by_ai,
        "corrected_by_human": qr.corrected_by_human,
        "questionnaire": {f: getattr(qr, f) for f in q_fields},
        "transcript": call.transcript_text,
    }
