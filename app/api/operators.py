from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Operator

router = APIRouter()


class OperatorCreate(BaseModel):
    name: str
    team: str | None = None


class OperatorUpdate(BaseModel):
    name: str | None = None
    team: str | None = None


def _fmt(o: Operator) -> dict:
    return {
        "id": o.id,
        "external_id": o.external_id,
        "name": o.name,
        "team": o.team,
        "created_at": o.created_at,
    }


@router.post("/", status_code=201)
async def create_operator(data: OperatorCreate, db: AsyncSession = Depends(get_db)):
    op = Operator(**data.model_dump())
    db.add(op)
    await db.commit()
    await db.refresh(op)
    return _fmt(op)


@router.get("/")
async def list_operators(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Operator).order_by(Operator.name))
    return [_fmt(o) for o in result.scalars().all()]


@router.get("/{external_id}")
async def get_operator(external_id: str, db: AsyncSession = Depends(get_db)):
    op = await db.scalar(select(Operator).where(Operator.external_id == external_id))
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    return _fmt(op)


@router.patch("/{external_id}")
async def update_operator(
    external_id: str,
    data: OperatorUpdate,
    db: AsyncSession = Depends(get_db),
):
    op = await db.scalar(select(Operator).where(Operator.external_id == external_id))
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    if data.name is not None:
        op.name = data.name
    if data.team is not None:
        op.team = data.team
    await db.commit()
    await db.refresh(op)
    return _fmt(op)
