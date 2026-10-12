"""
Provider-agnostic LLM factory. The rest of the app only calls get_llm().
"""

from functools import lru_cache
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.config import Settings, get_settings

DEFAULT_MODELS = {
    "google_genai": "gemini-3.8-flash",
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o-mini",
    "azure_openai": "gpt-4o-mini",
    "vertex_ai": "gemini-2.5-flash",
}

_NO_TEMPERATURE_PREFIXES = ("o1", "o3", "o4", "gpt-5")


class LLMConfigError(RuntimeError):
    pass


def _secret(value: SecretStr | None, env_name: str) -> str:
    if not value:
        raise LLMConfigError(f"{env_name} is not set in .env")
    return value.get_secret_value()


def _temp(s: Settings, model: str) -> dict[str, Any]:
    return {} if model.lower().startswith(_NO_TEMPERATURE_PREFIXES) else {"temperature": s.llm_temperature}


def _gemini(s: Settings, model: str) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=model,
        api_key=_secret(s.google_api_key, "GOOGLE_API_KEY"),
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
        **_temp(s, model),
    )


def _anthropic(s: Settings, model: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=model,
        api_key=_secret(s.anthropic_api_key, "ANTHROPIC_API_KEY"),
        max_tokens=s.llm_max_tokens,
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
        **_temp(s, model),
    )


def _openai(s: Settings, model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        api_key=_secret(s.openai_api_key, "OPENAI_API_KEY"),
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
        **_temp(s, model),
    )


def _azure(s: Settings, model: str) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI
    deployment = model or s.azure_openai_deployment_name
    if not deployment or not s.azure_openai_endpoint:
        raise LLMConfigError("AZURE_OPENAI_ENDPOINT and deployment name are required.")
    return AzureChatOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        azure_deployment=deployment,
        api_version=s.azure_openai_api_version,
        api_key=_secret(s.azure_openai_api_key, "AZURE_OPENAI_API_KEY"),
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
        **_temp(s, s.azure_openai_model_name or deployment),
    )


def _vertex(s: Settings, model: str) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI
    if not s.google_cloud_project:
        raise LLMConfigError("GOOGLE_CLOUD_PROJECT is required for vertex_ai.")
    return ChatGoogleGenerativeAI(
        model=model,
        vertexai=True,
        project=s.google_cloud_project,
        timeout=s.llm_timeout_seconds,
        max_retries=s.llm_max_retries,
        **_temp(s, model),
    )


_BUILDERS: dict[str, Callable[[Settings, str], BaseChatModel]] = {
    "google_genai": _gemini,
    "anthropic": _anthropic,
    "openai": _openai,
    "azure_openai": _azure,
    "vertex_ai": _vertex,
}


@lru_cache(maxsize=8)
def _cached_llm(provider: str, model: str) -> BaseChatModel:
    builder = _BUILDERS.get(provider)
    if builder is None:
        raise LLMConfigError(f"Unknown provider '{provider}'. Allowed: {sorted(_BUILDERS)}")
    return builder(get_settings(), model)


def get_llm(provider: str | None = None, model: str | None = None) -> BaseChatModel:
    s = get_settings()
    p = provider or s.llm_provider
    m = model or s.llm_model or DEFAULT_MODELS.get(p, "")
    return _cached_llm(p, m)


def message_text(content: Any) -> str:
    """Normalizes response content from strings, content lists, or thinking blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b if isinstance(b, str)
            else b.get("text", "") if isinstance(b, dict) and b.get("type") == "text"
            else ""
            for b in content
        )
    return str(content)