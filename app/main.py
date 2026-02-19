import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api import calls, operators, outcomes


async def run_migrations():
    """Запускает миграции в фоне — не блокирует старт приложения."""
    await asyncio.sleep(2)  # даём БД секунду подняться
    try:
        import subprocess, sys
        subprocess.run([sys.executable, "scripts/init_db.py"], check=True)
        print("Migrations applied.")
    except Exception as e:
        print(f"Migration warning (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_migrations())
    yield


app = FastAPI(title="Vladtrans Call Analytics", version="0.1.0", lifespan=lifespan)

app.include_router(calls.router,     prefix="/calls",     tags=["calls"])
app.include_router(operators.router, prefix="/operators", tags=["operators"])
app.include_router(outcomes.router,  prefix="/outcomes",  tags=["outcomes"])


@app.get("/health")
async def health():
    return {"status": "ok"}
