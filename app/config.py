
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

    llm_provider: Literal["azure_openai", "openai", "anthropic", "google_genai", "vertex_ai"] = "google_genai"
    llm_model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_MODEL", "GEMINI_MODEL", "llm_model", "gemini_model"),
    )
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    llm_max_tokens: int = 4096

    # API Keys & Credentials
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    google_cloud_project: str | None = None

    # Azure-specific settings (if using azure_openai)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment_name: str = ""
    azure_openai_model_name: str = ""

    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str | None = None


    database_url: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_CONN_STR", "database_url", "postgres_conn_str"),
    )
    postgres_conn_str: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_CONN_STR", "database_url", "postgres_conn_str"),
    )
    qdrant_url: SecretStr | None = None
    email_audit_persistence_enabled: bool = True
    email_audit_persistence_timeout_seconds: int = 3
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 5
    postgres_timeout_seconds: int = 5
    max_result_rows: int = 200

    sql_agent_max_queries: int = 3
    sql_agent_recursion_limit: int = 25

    sessions_enabled: bool = True
    session_ttl_hours: int = 24

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
