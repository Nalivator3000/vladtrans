from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Operator

router = APIRouter()


class OperatorCreate(BaseModel):
    name: str
    team: str | None = None


@router.post("/", status_code=201)
async def create_operator(data: OperatorCreate, db: AsyncSession = Depends(get_db)):
    op = Operator(**data.model_dump())
    db.add(op)
    await db.commit()
    await db.refresh(op)
    return op
