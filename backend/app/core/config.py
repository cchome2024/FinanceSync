from __future__ import annotations

from functools import lru_cache

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field(..., env="REDIS_URL")
    llm_provider: str = Field("azure_openai", env="LLM_PROVIDER")
    llm_endpoint: str = Field(..., env="LLM_ENDPOINT")
    llm_deployment: str = Field(..., env="LLM_DEPLOYMENT")
    llm_api_key: str = Field(..., env="LLM_API_KEY")
    storage_provider: str = Field("local", env="STORAGE_PROVIDER")
    storage_bucket: str = Field("finance-sync", env="STORAGE_BUCKET")
    storage_local_path: str = Field("./storage", env="STORAGE_LOCAL_PATH")
    watch_directories: str = Field("", env="WATCH_DIRECTORIES")
    watch_poll_interval_seconds: int = Field(30, env="WATCH_POLL_INTERVAL_SECONDS")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
