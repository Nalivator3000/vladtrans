from fastapi import APIRouter, Depends
from pydantic import BaseModel
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_db
from app.models.models import Outcome

router = APIRouter()


class OutcomeUpsert(BaseModel):
    order_id: str
    approved: bool | None = None
    redeemed: bool | None = None
    avg_check: Decimal | None = None


@router.post("/", status_code=200)
async def upsert_outcome(data: OutcomeUpsert, db: AsyncSession = Depends(get_db)):
    """
    Upsert результатов заказа (апрув, выкуп, чек).
    Вызывается из CRM или вручную при обновлении статуса заказа.
    """
    stmt = (
        insert(Outcome)
        .values(**data.model_dump())
        .on_conflict_do_update(
            index_elements=["order_id"],
            set_={k: v for k, v in data.model_dump().items() if k != "order_id"},
        )
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "order_id": data.order_id}
