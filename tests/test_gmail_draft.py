"""Tests for F016 - Gmail draft integration."""

import base64
from email import message_from_bytes
import importlib
import os
from unittest import mock

import pytest

from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction


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


def _approved_email_action(action_data: dict | None = None) -> ToolAction:
    return ToolAction(
        action_type=ActionType.SEND_EMAIL,
        action_data=action_data or {
            "to": "person@example.com",
            "subject": "Hello",
            "body": "Draft body",
        },
        approval_required=True,
        approval_status=ApprovalStatus.APPROVED,
    )


def _pending_email_action() -> ToolAction:
    return ToolAction(
        action_type=ActionType.SEND_EMAIL,
        action_data={"to": "person@example.com", "subject": "Hello"},
        approval_required=True,
        approval_status=ApprovalStatus.PENDING,
    )


class TestFakeEmailTool:
    def test_fake_email_execute_requires_approval(self) -> None:
        from idea_to_action.tools.fake_email import FakeEmailTool

        tool = FakeEmailTool()

        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(_pending_email_action())

    def test_fake_email_execute_rejects_wrong_action_type(self) -> None:
        from idea_to_action.tools.fake_email import FakeEmailTool

        tool = FakeEmailTool()
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Task"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )

        with pytest.raises(ValueError, match="cannot execute action type"):
            tool.execute(action)

    def test_fake_email_execute_returns_fake_created(self) -> None:
        from idea_to_action.tools.fake_email import FakeEmailTool

        tool = FakeEmailTool()
        result = tool.execute(_approved_email_action())

        assert result == {
            "status": "fake_created",
            "email_to": "person@example.com",
            "email_subject": "Hello",
        }


class TestGmailErrorHierarchy:
    def test_gmail_integration_error_is_base(self) -> None:
        from idea_to_action.tools.gmail_draft import (
            GmailAuthError,
            GmailDraftError,
            GmailIntegrationError,
        )

        assert issubclass(GmailAuthError, GmailIntegrationError)
        assert issubclass(GmailDraftError, GmailIntegrationError)

    def test_errors_are_exceptions(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailIntegrationError

        assert issubclass(GmailIntegrationError, Exception)


class TestGmailDraftToolInit:
    def test_init_with_defaults(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        assert tool.name == "gmail_draft"
        assert tool._credentials_path is not None
        assert tool._token_path is not None

    def test_init_with_custom_paths(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool("/tmp/gmail_creds.json", "/tmp/gmail_token.json")
        assert tool._credentials_path == "/tmp/gmail_creds.json"
        assert tool._token_path == "/tmp/gmail_token.json"


class TestGmailExecuteApprovalGating:
    def test_execute_pending_blocked(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(_pending_email_action())

    def test_execute_rejected_blocked(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        action = _pending_email_action().model_copy(
            update={"approval_status": ApprovalStatus.REJECTED}
        )
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(action)

    def test_execute_wrong_action_type(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Task"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        with pytest.raises(ValueError, match="cannot execute action type"):
            tool.execute(action)


class TestBuildMimeMessage:
    def test_build_mime_message_encodes_headers_and_body(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        raw = tool._build_mime_message({
            "to": ["one@example.com", "two@example.com"],
            "cc": ["cc@example.com"],
            "bcc": ["bcc@example.com"],
            "subject": "Subject line",
            "body": "Hello from the body",
        })

        msg = message_from_bytes(base64.urlsafe_b64decode(raw.encode("utf-8")))
        assert msg["To"] == "one@example.com, two@example.com"
        assert msg["Cc"] == "cc@example.com"
        assert msg["Bcc"] == "bcc@example.com"
        assert msg["Subject"] == "Subject line"
        assert "Hello from the body" in msg.get_payload()

    @pytest.mark.parametrize("to_value", [None, [], ""])
    def test_build_mime_message_requires_recipient(self, to_value) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftError, GmailDraftTool

        tool = GmailDraftTool()
        with pytest.raises(GmailDraftError, match="recipient"):
            tool._build_mime_message({"to": to_value, "subject": "No recipient"})
