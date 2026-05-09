"""Tests for F016 - Gmail draft integration."""

import base64
from email import message_from_bytes
import importlib
import os
from pathlib import Path
import runpy
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


def test_auth_gmail_import_does_not_run_auth_flow() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "auth_gmail.py"

    with mock.patch(
        "idea_to_action.tools.gmail_draft.GmailDraftTool.run_auth_flow"
    ) as run_auth_flow:
        namespace = runpy.run_path(str(script_path), run_name="auth_gmail_import_test")

    run_auth_flow.assert_not_called()
    assert callable(namespace["main"])


def test_auth_gmail_main_delegates_to_gmail_auth_flow() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "auth_gmail.py"

    with mock.patch(
        "idea_to_action.tools.gmail_draft.GmailDraftTool.run_auth_flow"
    ) as run_auth_flow:
        runpy.run_path(str(script_path), run_name="__main__")

    run_auth_flow.assert_called_once_with()


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


class TestGmailAuth:
    def test_execute_without_auth_raises_when_token_missing(self, tmp_path) -> None:
        from idea_to_action.tools.gmail_draft import GmailAuthError, GmailDraftTool

        token_path = tmp_path / "missing_token.json"
        tool = GmailDraftTool(token_path=str(token_path))

        with pytest.raises(GmailAuthError, match="Not authenticated"):
            tool.execute(_approved_email_action())

    def test_expired_token_with_refresh_token_refreshes_and_saves_credentials(
        self, tmp_path
    ) -> None:
        from idea_to_action.tools import gmail_draft
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        token_path = tmp_path / "gmail_token.json"
        token_path.write_text("{}")
        creds = mock.Mock()
        creds.expired = True
        creds.refresh_token = "refresh-token"
        creds.valid = True
        creds.to_json.return_value = '{"token": "refreshed"}'

        with mock.patch.object(
            gmail_draft.Credentials,
            "from_authorized_user_file",
            return_value=creds,
        ), mock.patch.object(gmail_draft, "Request", return_value="request"):
            result = GmailDraftTool(token_path=str(token_path))._get_credentials()

        assert result is creds
        creds.refresh.assert_called_once_with("request")
        assert token_path.read_text() == '{"token": "refreshed"}'


class TestGmailExecuteWithMockedAPI:
    def test_execute_approved_action_creates_draft_and_returns_ids(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        service = mock.Mock()
        create_result = {
            "id": "draft-123",
            "message": {"id": "message-456"},
        }
        service.users.return_value.drafts.return_value.create.return_value.execute.return_value = create_result

        with mock.patch.object(tool, "_get_service", return_value=service), mock.patch.object(
            tool, "_build_mime_message", return_value="encoded-message"
        ), mock.patch("idea_to_action.tools.gmail_draft.TraceLogger"):
            result = tool.execute(_approved_email_action())

        service.users.return_value.drafts.return_value.create.assert_called_once_with(
            userId="me", body={"message": {"raw": "encoded-message"}}
        )
        service.users.return_value.drafts.return_value.create.return_value.execute.assert_called_once_with()
        assert result == {
            "status": "created",
            "gmail_draft_id": "draft-123",
            "gmail_message_id": "message-456",
            "email_subject": "Hello",
            "email_to": "person@example.com",
        }

    def test_execute_does_not_call_send_endpoint(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        service = mock.Mock()
        service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
            "id": "draft-123",
            "message": {"id": "message-456"},
        }

        with mock.patch.object(tool, "_get_service", return_value=service), mock.patch.object(
            tool, "_build_mime_message", return_value="encoded-message"
        ), mock.patch("idea_to_action.tools.gmail_draft.TraceLogger"):
            tool.execute(_approved_email_action())

        assert not service.users.return_value.messages.return_value.send.called
        assert not service.users.return_value.drafts.return_value.send.called

    def test_http_error_from_drafts_create_wraps_as_gmail_draft_error(self) -> None:
        from googleapiclient.errors import HttpError

        from idea_to_action.tools.gmail_draft import GmailDraftError, GmailDraftTool

        tool = GmailDraftTool()
        service = mock.Mock()
        response = mock.Mock(status=500, reason="Server Error")
        service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
            response, b'{"error": {"message": "boom"}}'
        )

        with mock.patch.object(tool, "_get_service", return_value=service), mock.patch.object(
            tool, "_build_mime_message", return_value="encoded-message"
        ):
            with pytest.raises(GmailDraftError, match="Gmail API error"):
                tool.execute(_approved_email_action())


class TestRegistryWithGmail:
    def test_registry_uses_fake_email_when_credentials_missing(self, tmp_path) -> None:
        import idea_to_action.tools.registry as registry_module
        from idea_to_action.tools.fake_email import FakeEmailTool

        with mock.patch.object(
            registry_module, "GMAIL_CREDENTIALS_PATH", str(tmp_path / "missing.json")
        ):
            registry = registry_module.ToolRegistry()

        assert registry.is_gmail_connected is False
        assert isinstance(registry._email, FakeEmailTool)

    def test_registry_execute_send_email_uses_fake_when_unconfigured(self, tmp_path) -> None:
        import idea_to_action.tools.registry as registry_module
        from idea_to_action.tools.fake_email import FakeEmailTool

        def fail_on_gmail_draft_import(name, *args, **kwargs):
            if name == "idea_to_action.tools.gmail_draft":
                raise ImportError("gmail_draft should not be imported")
            return real_import(name, *args, **kwargs)

        real_import = __import__
        with mock.patch.object(
            registry_module, "GMAIL_CREDENTIALS_PATH", str(tmp_path / "missing.json")
        ), mock.patch("builtins.__import__", side_effect=fail_on_gmail_draft_import):
            registry = registry_module.ToolRegistry()

        result = registry.execute(_approved_email_action())

        assert isinstance(registry._email, FakeEmailTool)
        assert result == {
            "status": "fake_created",
            "email_to": "person@example.com",
            "email_subject": "Hello",
        }

    def test_registry_uses_gmail_draft_when_credentials_exist_without_auth(
        self, tmp_path
    ) -> None:
        import idea_to_action.tools.registry as registry_module
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        credentials_path = tmp_path / "gmail_client_secret.json"
        token_path = tmp_path / "gmail_token.json"
        credentials_path.write_text("{}")

        with mock.patch.object(
            registry_module, "GMAIL_CREDENTIALS_PATH", str(credentials_path)
        ), mock.patch.object(
            registry_module, "GMAIL_TOKEN_PATH", str(token_path)
        ):
            registry = registry_module.ToolRegistry()

        assert registry.is_gmail_connected is True
        assert isinstance(registry._email, GmailDraftTool)
        assert registry._email._credentials_path == str(credentials_path)
        assert registry._email._token_path == str(token_path)
