from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./finance_sync.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "deepseek"
    llm_endpoint: str = "https://api.deepseek.com"
    llm_deployment: str = "deepseek-chat"
    llm_api_key: str = "test-key"
    llm_timeout_seconds: int | None = 120
    storage_provider: str = "local"
    storage_bucket: str = "finance-sync"
    storage_local_path: str = "./storage"
    watch_directories: str = ""
    watch_poll_interval_seconds: int = 30
    log_level: str = "INFO"
    jwt_secret_key: str = "your-secret-key-change-in-production"
    sqlserver_host: str | None = None
    sqlserver_port: int | None = None
    sqlserver_user: str | None = None
    sqlserver_password: str | None = None
    sqlserver_database: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
