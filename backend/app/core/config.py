from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; secrets are injected instead of committed."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI-CodeReview"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://ai_codereview:ai_codereview@postgres:5432/ai_codereview"
    artifact_root: str = "/artifacts"
    jwt_secret: str = Field(min_length=32)
    jwt_access_ttl_seconds: int = Field(default=3600, ge=300, le=86_400)
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    worker_id: str = "worker-1"
    job_lease_seconds: int = Field(default=60, ge=15, le=300)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    gemini_api_key: str | None = None
    gemini_generation_model: str = "gemini-2.5-flash"
    embedding_model: str = "text-embedding-004"


@lru_cache
def get_settings() -> Settings:
    return Settings()
