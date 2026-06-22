from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "Smart Metrics Platform"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "metrics"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""  # Set in production; leave empty for no-auth

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD}"
                f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Celery (defaults to REDIS_URL if not set)
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_CONCURRENCY: int = 4  # Number of Celery worker processes

    # API Authentication
    API_KEY: str = "dev-api-key-please-change-in-production"

    # CORS — set to a comma-separated list of allowed origins in production,
    # e.g. "https://dashboard.example.com,https://admin.example.com"
    # The special value "*" allows all origins (only safe in development).
    CORS_ORIGINS: list[str] = ["*"]

    # Server workers (Gunicorn) — recommended: 2 × CPU_COUNT + 1
    WORKERS: int = 2

    # Log format: "json" (production) | "text" (development / human-readable)
    LOG_FORMAT: str = "json"

    # Cache TTL (seconds)
    CACHE_TTL_STATS: int = 300
    CACHE_TTL_ANOMALIES: int = 60
    CACHE_TTL_MA: int = 600


settings = Settings()
