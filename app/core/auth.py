from fastapi import Header, HTTPException
from app.core.config import settings


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """FastAPI dependency — проверяет X-API-Key header."""
    if not settings.api_key:
        return  # auth отключён если ключ не задан в env
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
