from datetime import datetime, timedelta, timezone

import sentry_sdk
from fastapi import Depends, FastAPI
from sqlalchemy import func, select, text

from app.api import analytics, calls, operators, outcomes
from app.core.auth import verify_api_key
from app.core.config import settings
from app.core.database import get_db
from app.models.models import Call

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

app = FastAPI(title="Vladtrans Call Analytics", version="0.1.0")

# Все роуты защищены API-ключом кроме /health
_auth = [Depends(verify_api_key)]

app.include_router(calls.router,     prefix="/calls",     tags=["calls"],     dependencies=_auth)
app.include_router(operators.router, prefix="/operators", tags=["operators"], dependencies=_auth)
app.include_router(outcomes.router,  prefix="/outcomes",  tags=["outcomes"],  dependencies=_auth)
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"], dependencies=_auth)


@app.get("/health", tags=["system"])
async def health(db=Depends(get_db)):
    db_status = "ok"
    calls_pending = 0
    calls_error_24h = 0
    try:
        calls_pending = await db.scalar(
            select(func.count()).where(Call.processing_status.in_(["pending", "processing"]))
        )
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        calls_error_24h = await db.scalar(
            select(func.count()).where(
                Call.processing_status == "error",
                Call.created_at >= since,
            )
        )
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "calls_pending": calls_pending,
        "calls_error_24h": calls_error_24h,
    }
