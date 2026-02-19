from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import Call
from app.tasks import process_call

router = APIRouter()


class CallCreate(BaseModel):
    order_id: str
    operator_id: int | None = None
    call_date: datetime
    duration_sec: int | None = None
    audio_url: str


@router.post("/", status_code=202)
async def create_call(data: CallCreate, db: AsyncSession = Depends(get_db)):
    """
    Создаёт запись о звонке и ставит задачу на обработку в очередь.
    audio_url — путь к файлу или URL для скачивания.
    """
    call = Call(**data.model_dump())
    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Запускаем обработку асинхронно
    process_call.delay(call.id, data.audio_url)

    return {"call_id": call.id, "status": "queued"}


@router.get("/{call_id}")
async def get_call(call_id: int, db: AsyncSession = Depends(get_db)):
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call
