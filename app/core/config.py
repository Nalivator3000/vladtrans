from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI (анализ анкеты через GPT)
    openai_api_key: str

    # Groq (транскрипция Whisper large-v3, поддерживает Georgian)
    groq_api_key: str

    # Database — Railway даёт postgresql://, нам нужен asyncpg драйвер
    database_url: str = "postgresql+asyncpg://vladtrans:vladtrans@db:5432/vladtrans"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"

    @property
    def async_database_url(self) -> str:
        """Для SQLAlchemy async engine."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Для psycopg2 (миграции, init_db)."""
        url = self.database_url
        for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
            if url.startswith(prefix):
                return url.replace(prefix, "postgresql://", 1)
        return url


settings = Settings()
