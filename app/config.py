
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "Chinnok Agent Endpoint API"
    log_level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"] = "WARN"
    api_docs_enabled: bool = True
    request_max_bytes: int = 1_048_576

    llm_provider: Literal["azure_openai", "openai", "vertex_ai"] = "azure_openai"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment_name: str = ""
    azure_openai_model_name: str = ""
    azure_openai_temperature: float = 0.0
    azure_openai_timeout_seconds: int = 60
    azure_openai_max_retries: int = 2

    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str | None = None


    postgres_conn_str: SecretStr | None = None
    qdrant_url: SecretStr | None = None
    email_audit_persistence_enabled: bool = True
    email_audit_persistence_timeout_seconds: int = 3
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 5

    sessions_enabled: bool = True
    session_ttl_hours: int = 24

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
