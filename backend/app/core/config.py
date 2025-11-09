from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./finance_sync.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "azure_openai"
    llm_endpoint: str = "https://example.openai.azure.com"
    llm_deployment: str = "gpt-4o"
    llm_api_key: str = "test-key"
    llm_timeout_seconds: int | None = 120
    storage_provider: str = "local"
    storage_bucket: str = "finance-sync"
    storage_local_path: str = "./storage"
    watch_directories: str = ""
    watch_poll_interval_seconds: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
