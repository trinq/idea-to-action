"""Tests for F016 - Gmail draft integration."""

import importlib
import os
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def restore_config_from_real_environment():
    yield

    import idea_to_action.config as config

    importlib.reload(config)


def test_gmail_config_defaults_follow_project_conventions() -> None:
    with mock.patch.dict(os.environ, {}, clear=True):
        import idea_to_action.config as config

        reloaded = importlib.reload(config)

        assert reloaded.GMAIL_CREDENTIALS_PATH.endswith("gmail_client_secret.json")
        assert reloaded.GMAIL_TOKEN_PATH.endswith(
            os.path.join("data", "gmail_token.json")
        )


def test_gmail_config_uses_i2a_env_vars() -> None:
    with mock.patch.dict(
        os.environ,
        {
            "I2A_GMAIL_CREDENTIALS": "/tmp/custom_gmail_creds.json",
            "I2A_GMAIL_TOKEN": "/tmp/custom_gmail_token.json",
        },
        clear=True,
    ):
        import idea_to_action.config as config

        reloaded = importlib.reload(config)

        assert reloaded.GMAIL_CREDENTIALS_PATH == "/tmp/custom_gmail_creds.json"
        assert reloaded.GMAIL_TOKEN_PATH == "/tmp/custom_gmail_token.json"
