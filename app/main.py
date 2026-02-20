from fastapi import FastAPI
from app.api import calls, operators, outcomes

app = FastAPI(title="Vladtrans Call Analytics", version="0.1.0")

app.include_router(calls.router,     prefix="/calls",     tags=["calls"])
app.include_router(operators.router, prefix="/operators", tags=["operators"])
app.include_router(outcomes.router,  prefix="/outcomes",  tags=["outcomes"])


@app.get("/health")
async def health():
    import subprocess
    ffmpeg_ok = subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0
    return {"status": "ok", "ffmpeg": ffmpeg_ok, "build": "e07aa3c"}
