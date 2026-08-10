from functools import lru_cache

from typing import Literal

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
    generation_provider: Literal["fake", "gemini", "deepseek"] = "fake"
    embedding_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: str | None = None
    gemini_generation_model: str = "gemini-2.5-flash"
    deepseek_api_key: str | None = None
    deepseek_generation_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    agent_tool_allowed_hosts: list[str] = Field(default_factory=list)
    agent_tool_timeout_seconds: int = Field(default=10, ge=1, le=30)
    agent_tool_response_limit_bytes: int = Field(default=262_144, ge=4_096, le=1_048_576)
    embedding_model: str = "text-embedding-004"

    @property
    def generation_model_name(self) -> str:
        if self.generation_provider == "gemini":
            return self.gemini_generation_model
        if self.generation_provider == "deepseek":
            return self.deepseek_generation_model
        return "fake-model-v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
