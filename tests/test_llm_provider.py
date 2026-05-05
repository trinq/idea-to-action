"""Tests for F013 - LLM provider configuration."""

import os
from unittest import mock

import pytest
from langchain_openai import ChatOpenAI

from idea_to_action.agent.llm_provider import (
    LLMConfigError,
    ProviderType,
    create_llm,
    get_api_key,
    get_base_url,
    get_default_provider,
    get_model,
    validate_provider,
)


class TestGetApiKey:
    def test_returns_key_from_env(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test-123"}, clear=True):
            assert get_api_key(ProviderType.DEEPSEEK) == "sk-test-123"

    def test_raises_when_key_missing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigError, match="DEEPSEEK_API_KEY"):
                get_api_key(ProviderType.DEEPSEEK)

    def test_raises_when_key_empty(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=True):
            with pytest.raises(LLMConfigError, match="DEEPSEEK_API_KEY"):
                get_api_key(ProviderType.DEEPSEEK)

    def test_openai_key_from_env(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-456"}, clear=True):
            assert get_api_key(ProviderType.OPENAI) == "sk-openai-456"

    def test_openai_raises_when_missing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigError, match="OPENAI_API_KEY"):
                get_api_key(ProviderType.OPENAI)


class TestGetModel:
    def test_returns_default_model_deepseek(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_model(ProviderType.DEEPSEEK) == "deepseek-chat"

    def test_returns_default_model_openai(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_model(ProviderType.OPENAI) == "gpt-4o-mini"

    def test_returns_override_from_env(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_MODEL": "deepseek-reasoner"}, clear=True):
            assert get_model(ProviderType.DEEPSEEK) == "deepseek-reasoner"


class TestGetBaseUrl:
    def test_deepseek_default_base_url(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_base_url(ProviderType.DEEPSEEK) == "https://api.deepseek.com"

    def test_openai_default_none(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_base_url(ProviderType.OPENAI) is None

    def test_custom_base_url_from_env(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_BASE_URL": "https://custom.api.com"}, clear=True):
            assert get_base_url(ProviderType.DEEPSEEK) == "https://custom.api.com"


class TestValidateProvider:
    def test_passes_when_key_set(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            validate_provider(ProviderType.DEEPSEEK)  # no raise

    def test_raises_when_key_missing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigError):
                validate_provider(ProviderType.DEEPSEEK)


class TestCreateLlm:
    def test_creates_chat_openai_instance(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            llm = create_llm(ProviderType.DEEPSEEK)
            assert isinstance(llm, ChatOpenAI)
            assert llm.model_name == "deepseek-chat"
            assert llm.openai_api_base == "https://api.deepseek.com"

    def test_creates_with_custom_model(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            llm = create_llm(ProviderType.DEEPSEEK, model="deepseek-reasoner")
            assert llm.model_name == "deepseek-reasoner"

    def test_creates_with_temperature(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            llm = create_llm(ProviderType.DEEPSEEK, temperature=0.7)
            assert llm.temperature == 0.7

    def test_default_temperature_is_zero(self) -> None:
        """Default temperature is 0.0 for deterministic outputs."""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            llm = create_llm(ProviderType.DEEPSEEK)
            assert llm.temperature == 0.0

    def test_raises_when_key_missing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigError, match="DEEPSEEK_API_KEY"):
                create_llm(ProviderType.DEEPSEEK)

    def test_creates_openai_instance(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai"}, clear=True):
            llm = create_llm(ProviderType.OPENAI)
            assert isinstance(llm, ChatOpenAI)
            assert llm.model_name == "gpt-4o-mini"

    def test_api_key_not_exposed_in_repr(self) -> None:
        """API key must not appear in string representation."""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-secret-key-12345"}, clear=True):
            llm = create_llm(ProviderType.DEEPSEEK)
            s = str(llm)
            assert "sk-secret-key-12345" not in s


class TestGetDefaultProvider:
    def test_returns_deepseek_when_key_set(self) -> None:
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=True):
            assert get_default_provider() == ProviderType.DEEPSEEK

    def test_returns_openai_when_only_openai_set(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            assert get_default_provider() == ProviderType.OPENAI

    def test_prefers_deepseek_over_openai(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "sk-ds", "OPENAI_API_KEY": "sk-oai"},
            clear=True,
        ):
            assert get_default_provider() == ProviderType.DEEPSEEK

    def test_raises_when_no_keys_set(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMConfigError, match="No LLM provider configured"):
                get_default_provider()
