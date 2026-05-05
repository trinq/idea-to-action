"""LLM provider configuration and factory.

Supports DeepSeek (primary) and OpenAI (alternative).
Both use langchain-openai's ChatOpenAI since DeepSeek is OpenAI-compatible.
API keys are loaded from environment variables only — never stored in the repo.
"""

import os
from enum import Enum
from typing import Optional

from langchain_openai import ChatOpenAI

from idea_to_action.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)


class ProviderType(str, Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"


class LLMConfigError(Exception):
    """Configuration error — missing or invalid LLM settings."""


class LLMConnectionError(Exception):
    """Connection or authentication error with the LLM provider."""


# Default models
_DEFAULT_MODELS: dict[ProviderType, str] = {
    ProviderType.DEEPSEEK: "deepseek-chat",
    ProviderType.OPENAI: "gpt-4o-mini",
}

# Environment variable keys
_API_KEY_ENVVARS: dict[ProviderType, str] = {
    ProviderType.DEEPSEEK: "DEEPSEEK_API_KEY",
    ProviderType.OPENAI: "OPENAI_API_KEY",
}

_MODEL_ENVVARS: dict[ProviderType, str] = {
    ProviderType.DEEPSEEK: "DEEPSEEK_MODEL",
    ProviderType.OPENAI: "OPENAI_MODEL",
}

_BASE_URL_ENVVARS: dict[ProviderType, str] = {
    ProviderType.DEEPSEEK: "DEEPSEEK_BASE_URL",
    ProviderType.OPENAI: "OPENAI_BASE_URL",
}

_DEFAULT_BASE_URLS: dict[ProviderType, Optional[str]] = {
    ProviderType.DEEPSEEK: "https://api.deepseek.com",
    ProviderType.OPENAI: None,  # langchain-openai uses default OpenAI base URL
}


def get_api_key(provider: ProviderType) -> str:
    """Get API key from environment for a provider.

    Never reads from files, config, or hardcoded values.
    """
    env_var = _API_KEY_ENVVARS[provider]
    key = os.environ.get(env_var, "")
    if not key:
        raise LLMConfigError(
            f"{env_var} is not set. "
            f"Set it in your environment to use the {provider.value} provider."
        )
    return key


def get_model(provider: ProviderType) -> str:
    """Get the configured model name for a provider."""
    env_var = _MODEL_ENVVARS[provider]
    return os.environ.get(env_var, _DEFAULT_MODELS[provider])


def get_base_url(provider: ProviderType) -> Optional[str]:
    """Get the API base URL for a provider."""
    env_var = _BASE_URL_ENVVARS[provider]
    default = _DEFAULT_BASE_URLS[provider]
    return os.environ.get(env_var, default)


def validate_provider(provider: ProviderType) -> None:
    """Validate that a provider can be used without making an API call.

    Checks that the API key exists (non-empty).
    Does NOT validate the key against the remote API.
    """
    get_api_key(provider)  # raises LLMConfigError if missing


def create_llm(
    provider: ProviderType = ProviderType.DEEPSEEK,
    *,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatOpenAI:
    """Create a configured ChatOpenAI instance for the given provider.

    Args:
        provider: Which provider to use (deepseek or openai).
        temperature: Model temperature. Default 0.0 for deterministic outputs.
        max_tokens: Max output tokens. None uses provider default.
        model: Override the configured model name.

    Returns:
        A langchain ChatOpenAI instance ready to use.

    Raises:
        LLMConfigError: If the API key is not set.
    """
    api_key = get_api_key(provider)
    base_url = get_base_url(provider)
    selected_model = model or get_model(provider)

    kwargs: dict = {
        "model": selected_model,
        "api_key": api_key,
        "temperature": temperature,
    }
    if base_url is not None:
        kwargs["base_url"] = base_url
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    return ChatOpenAI(**kwargs)


def get_default_provider() -> ProviderType:
    """Determine the default provider based on available API keys.

    Priority: DeepSeek first, then OpenAI.
    """
    try:
        get_api_key(ProviderType.DEEPSEEK)
        return ProviderType.DEEPSEEK
    except LLMConfigError:
        pass

    try:
        get_api_key(ProviderType.OPENAI)
        return ProviderType.OPENAI
    except LLMConfigError:
        pass

    raise LLMConfigError(
        "No LLM provider configured. "
        "Set DEEPSEEK_API_KEY or OPENAI_API_KEY in your environment."
    )
