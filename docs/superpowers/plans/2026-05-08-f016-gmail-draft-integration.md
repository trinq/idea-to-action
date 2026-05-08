# F016 Gmail Draft Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create Gmail draft emails from approved `SEND_EMAIL` tool actions without ever sending email.

**Architecture:** Add a Gmail draft tool that mirrors the existing Google Calendar OAuth pattern, plus a fake email fallback for unconfigured local use. Register `SEND_EMAIL` in `ToolRegistry`, surface Gmail status/results in the Streamlit UI, and keep F016 tool-only with no planner/schema extraction changes.

**Tech Stack:** Python, pytest, Google OAuth (`google-auth-oauthlib`), Google API client (`google-api-python-client`), stdlib `email.message.EmailMessage`, stdlib `base64`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/idea_to_action/config.py` | Add Gmail credential/token paths using `I2A_GMAIL_CREDENTIALS`, `I2A_GMAIL_TOKEN`, and `DATA_DIR`. |
| `.gitignore` | Explicitly ignore Gmail OAuth artifacts. |
| `src/idea_to_action/tools/fake_email.py` | Safe fake fallback for `SEND_EMAIL`, approval-gated and external-call-free. |
| `src/idea_to_action/tools/gmail_draft.py` | Real Gmail draft integration: OAuth, MIME construction, draft creation, trace logging. |
| `src/idea_to_action/tools/registry.py` | Auto-detect Gmail credentials, route `SEND_EMAIL`, expose `is_gmail_connected`. |
| `scripts/auth_gmail.py` | One-time browser OAuth flow for Gmail compose scope. |
| `src/idea_to_action/ui/app.py` | Show Gmail connection status and draft creation result. |
| `tests/test_gmail_draft.py` | Focused tests for Gmail tool and fake fallback. |
| `tests/test_tool_draft_layer.py` | Registry routing coverage for `SEND_EMAIL`. |
| `tests/test_ui.py` | UI approval/result behavior for Gmail drafts. |
| `docs/using-gmail-integration.md` | User setup guide. |
| `feature_list.json` | Mark F016 passing with evidence after verification. |

---

### Task 1: Config and gitignore

**Files:**
- Modify: `src/idea_to_action/config.py`
- Modify: `.gitignore`
- Test: `tests/test_gmail_draft.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_gmail_draft.py` with:

```python
"""Tests for F016 - Gmail draft integration."""

import os
from unittest import mock


def test_gmail_config_defaults_follow_project_conventions() -> None:
    with mock.patch.dict(os.environ, {}, clear=True):
        import importlib
        import idea_to_action.config as config

        reloaded = importlib.reload(config)

        assert reloaded.GMAIL_CREDENTIALS_PATH.endswith("gmail_client_secret.json")
        assert reloaded.GMAIL_TOKEN_PATH.endswith("data/gmail_token.json")


def test_gmail_config_uses_i2a_env_vars() -> None:
    with mock.patch.dict(
        os.environ,
        {
            "I2A_GMAIL_CREDENTIALS": "/tmp/custom_gmail_creds.json",
            "I2A_GMAIL_TOKEN": "/tmp/custom_gmail_token.json",
        },
        clear=True,
    ):
        import importlib
        import idea_to_action.config as config

        reloaded = importlib.reload(config)

        assert reloaded.GMAIL_CREDENTIALS_PATH == "/tmp/custom_gmail_creds.json"
        assert reloaded.GMAIL_TOKEN_PATH == "/tmp/custom_gmail_token.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_gmail_draft.py -v
```

Expected: FAIL because `GMAIL_CREDENTIALS_PATH` and `GMAIL_TOKEN_PATH` are not defined.

- [ ] **Step 3: Implement config values**

In `src/idea_to_action/config.py`, add after the Google Calendar config and before `TIMEZONE`:

```python
# Gmail Drafts
GMAIL_CREDENTIALS_PATH = os.environ.get(
    "I2A_GMAIL_CREDENTIALS",
    os.path.join(_PROJECT_ROOT, "gmail_client_secret.json"),
)
GMAIL_TOKEN_PATH = os.environ.get(
    "I2A_GMAIL_TOKEN",
    os.path.join(DATA_DIR, "gmail_token.json"),
)
```

- [ ] **Step 4: Update `.gitignore`**

Append these lines to `.gitignore`:

```gitignore
gmail_client_secret.json
gmail_token.json
```

- [ ] **Step 5: Run config tests**

Run:

```bash
python3 -m pytest tests/test_gmail_draft.py -v
```

Expected: PASS for both config tests.

- [ ] **Step 6: Commit**

```bash
git add src/idea_to_action/config.py .gitignore tests/test_gmail_draft.py
git commit -m "feat: add Gmail draft config"
```

---

### Task 2: FakeEmailTool fallback

**Files:**
- Create: `src/idea_to_action/tools/fake_email.py`
- Modify: `tests/test_gmail_draft.py`

- [ ] **Step 1: Add failing fake email tests**

Append to `tests/test_gmail_draft.py`:

```python
import pytest

from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction


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
```

- [ ] **Step 2: Run fake tests to verify they fail**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestFakeEmailTool -v
```

Expected: FAIL because `idea_to_action.tools.fake_email` does not exist.

- [ ] **Step 3: Create fake email tool**

Create `src/idea_to_action/tools/fake_email.py`:

```python
"""Fake email tool for safe local execution.

Prepares fake results for approved SEND_EMAIL actions without calling Gmail.
"""

from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction


class FakeEmailTool:
    """Safe fake fallback for email draft execution."""

    name = "fake_email"

    def execute(self, action: ToolAction) -> dict:
        """Return a fake email draft result for an approved SEND_EMAIL action."""
        if action.action_type != ActionType.SEND_EMAIL:
            raise ValueError(
                f"FakeEmailTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        return {
            "status": "fake_created",
            "email_to": action.action_data.get("to"),
            "email_subject": action.action_data.get("subject"),
        }
```

- [ ] **Step 4: Run fake tests**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestFakeEmailTool -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/idea_to_action/tools/fake_email.py tests/test_gmail_draft.py
git commit -m "feat: add fake email draft tool"
```

---

### Task 3: GmailDraftTool core behavior

**Files:**
- Create: `src/idea_to_action/tools/gmail_draft.py`
- Modify: `tests/test_gmail_draft.py`

- [ ] **Step 1: Add failing Gmail tool tests**

Append to `tests/test_gmail_draft.py`:

```python
import base64
from email import message_from_bytes
from unittest import mock


class TestGmailErrorHierarchy:
    def test_gmail_errors_inherit_from_base(self) -> None:
        from idea_to_action.tools.gmail_draft import (
            GmailAuthError,
            GmailDraftError,
            GmailIntegrationError,
        )

        assert issubclass(GmailAuthError, GmailIntegrationError)
        assert issubclass(GmailDraftError, GmailIntegrationError)
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


class TestGmailApprovalGating:
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
    def test_build_mime_message_encodes_email_fields(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        encoded = tool._build_mime_message({
            "to": "person@example.com",
            "cc": ["cc@example.com"],
            "bcc": ["bcc@example.com"],
            "subject": "Hello",
            "body": "Draft body",
        })

        decoded = base64.urlsafe_b64decode(encoded.encode("utf-8"))
        msg = message_from_bytes(decoded)

        assert msg["To"] == "person@example.com"
        assert msg["Cc"] == "cc@example.com"
        assert msg["Bcc"] == "bcc@example.com"
        assert msg["Subject"] == "Hello"
        assert msg.get_payload() == "Draft body\n"

    def test_build_mime_message_requires_recipient(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftError, GmailDraftTool

        tool = GmailDraftTool()

        with pytest.raises(GmailDraftError, match="recipient"):
            tool._build_mime_message({"subject": "Hello", "body": "Body"})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestGmailErrorHierarchy tests/test_gmail_draft.py::TestGmailDraftToolInit tests/test_gmail_draft.py::TestGmailApprovalGating tests/test_gmail_draft.py::TestBuildMimeMessage -v
```

Expected: FAIL because `gmail_draft.py` does not exist.

- [ ] **Step 3: Implement GmailDraftTool core**

Create `src/idea_to_action/tools/gmail_draft.py`:

```python
"""Gmail draft integration tool.

Creates Gmail drafts from approved SEND_EMAIL actions. Never sends email.
"""

import base64
import os
from email.message import EmailMessage

from google.auth.exceptions import GoogleAuthError as GAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from idea_to_action.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction
from idea_to_action.tracing import TraceLogger

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailIntegrationError(Exception):
    """Base error for Gmail integrations."""


class GmailAuthError(GmailIntegrationError):
    """Authentication error — user needs to run auth flow."""


class GmailDraftError(GmailIntegrationError):
    """Error from Gmail draft creation or payload validation."""


class GmailDraftTool:
    """Real Gmail draft integration via OAuth2."""

    name = "gmail_draft"

    def __init__(self, credentials_path: str | None = None, token_path: str | None = None) -> None:
        self._credentials_path = credentials_path or GMAIL_CREDENTIALS_PATH
        self._token_path = token_path or GMAIL_TOKEN_PATH
        self._service = None

    def _get_credentials(self) -> Credentials:
        if not os.path.exists(self._token_path):
            raise GmailAuthError("Not authenticated. Run: python3 scripts/auth_gmail.py")

        creds = Credentials.from_authorized_user_file(self._token_path, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds)
            except GAuthError as e:
                raise GmailAuthError(
                    f"Token refresh failed. Re-authenticate: python3 scripts/auth_gmail.py\n{e}"
                ) from e

        if not creds or not creds.valid:
            raise GmailAuthError("Not authenticated. Run: python3 scripts/auth_gmail.py")

        return creds

    def _save_credentials(self, creds: Credentials) -> None:
        os.makedirs(os.path.dirname(self._token_path), exist_ok=True)
        with open(self._token_path, "w") as f:
            f.write(creds.to_json())

    def _get_service(self):
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    @staticmethod
    def run_auth_flow(credentials_path: str | None = None, token_path: str | None = None) -> None:
        creds_path = credentials_path or GMAIL_CREDENTIALS_PATH
        tok_path = token_path or GMAIL_TOKEN_PATH

        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Client secret file not found at {creds_path}. "
                "Download it from Google Cloud Console."
            )

        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(tok_path), exist_ok=True)
        with open(tok_path, "w") as f:
            f.write(creds.to_json())

        print(f"Authentication successful. Token saved to {tok_path}")

    def execute(self, action: ToolAction) -> dict:
        if action.action_type != ActionType.SEND_EMAIL:
            raise ValueError(
                f"GmailDraftTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        service = self._get_service()
        encoded_message = self._build_mime_message(action.action_data)

        try:
            draft = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": encoded_message}})
                .execute()
            )
        except HttpError as e:
            raise GmailDraftError(f"Gmail API error: {e}") from e

        result = {
            "status": "created",
            "gmail_draft_id": draft.get("id"),
            "gmail_message_id": draft.get("message", {}).get("id"),
            "email_subject": action.action_data.get("subject", ""),
            "email_to": action.action_data.get("to"),
        }
        TraceLogger().log("gmail_draft_execute", {
            "action_type": action.action_type.value,
            "approval_status": action.approval_status.value,
            "email_to": action.action_data.get("to"),
            "email_subject": action.action_data.get("subject"),
            "gmail_draft_id": result.get("gmail_draft_id"),
            "gmail_message_id": result.get("gmail_message_id"),
        })
        return result

    def _build_mime_message(self, action_data: dict) -> str:
        to = action_data.get("to")
        if not to:
            raise GmailDraftError("Email recipient is required in action_data['to']")

        msg = EmailMessage()
        msg["To"] = to
        if action_data.get("cc"):
            msg["Cc"] = ", ".join(action_data["cc"])
        if action_data.get("bcc"):
            msg["Bcc"] = ", ".join(action_data["bcc"])
        msg["Subject"] = action_data.get("subject", "")
        msg.set_content(action_data.get("body", ""))

        raw = msg.as_bytes()
        return base64.urlsafe_b64encode(raw).decode("utf-8")
```

- [ ] **Step 4: Run Gmail core tests**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestGmailErrorHierarchy tests/test_gmail_draft.py::TestGmailDraftToolInit tests/test_gmail_draft.py::TestGmailApprovalGating tests/test_gmail_draft.py::TestBuildMimeMessage -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/idea_to_action/tools/gmail_draft.py tests/test_gmail_draft.py
git commit -m "feat: add Gmail draft tool core"
```

---

### Task 4: Gmail API execution and auth tests

**Files:**
- Modify: `tests/test_gmail_draft.py`
- Modify: `src/idea_to_action/tools/gmail_draft.py` if tests reveal gaps

- [ ] **Step 1: Add failing execution/auth tests**

Append to `tests/test_gmail_draft.py`:

```python

class TestGmailAuth:
    def test_execute_without_auth_raises(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailAuthError, GmailDraftTool

        tool = GmailDraftTool("/nonexistent/gmail_creds.json", "/nonexistent/gmail_token.json")

        with pytest.raises(GmailAuthError, match="Not authenticated"):
            tool.execute(_approved_email_action())

    def test_refresh_expired_token_saves_credentials(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool("/tmp/gmail_creds.json", "/tmp/gmail_token.json")
        fake_creds = mock.MagicMock()
        fake_creds.expired = True
        fake_creds.refresh_token = "refresh"
        fake_creds.valid = True
        fake_creds.to_json.return_value = "{}"

        with mock.patch("idea_to_action.tools.gmail_draft.os.path.exists", return_value=True):
            with mock.patch("idea_to_action.tools.gmail_draft.Credentials.from_authorized_user_file", return_value=fake_creds):
                with mock.patch.object(tool, "_save_credentials") as save:
                    result = tool._get_credentials()

        assert result is fake_creds
        fake_creds.refresh.assert_called_once()
        save.assert_called_once_with(fake_creds)


class TestGmailExecuteWithMockedAPI:
    def test_execute_approved_creates_draft_only(self) -> None:
        from idea_to_action.tools.gmail_draft import GmailDraftTool

        tool = GmailDraftTool()
        action = _approved_email_action()
        fake_creds = mock.MagicMock()
        fake_creds.valid = True
        fake_creds.expired = False

        with mock.patch.object(tool, "_get_credentials", return_value=fake_creds):
            with mock.patch("idea_to_action.tools.gmail_draft.build") as mock_build:
                with mock.patch("idea_to_action.tools.gmail_draft.TraceLogger"):
                    mock_service = mock.MagicMock()
                    mock_build.return_value = mock_service
                    drafts_resource = mock.MagicMock()
                    mock_service.users.return_value.drafts.return_value = drafts_resource
                    create_request = mock.MagicMock()
                    drafts_resource.create.return_value = create_request
                    create_request.execute.return_value = {
                        "id": "draft_123",
                        "message": {"id": "msg_123"},
                    }

                    result = tool.execute(action)

        drafts_resource.create.assert_called_once()
        kwargs = drafts_resource.create.call_args.kwargs
        assert kwargs["userId"] == "me"
        assert "raw" in kwargs["body"]["message"]
        assert result["status"] == "created"
        assert result["gmail_draft_id"] == "draft_123"
        assert result["gmail_message_id"] == "msg_123"
        assert not mock_service.users.return_value.messages.return_value.send.called

    def test_execute_api_error_wrapped(self) -> None:
        from googleapiclient.errors import HttpError
        from idea_to_action.tools.gmail_draft import GmailDraftError, GmailDraftTool

        tool = GmailDraftTool()
        fake_creds = mock.MagicMock()
        fake_creds.valid = True
        fake_creds.expired = False

        with mock.patch.object(tool, "_get_credentials", return_value=fake_creds):
            with mock.patch("idea_to_action.tools.gmail_draft.build") as mock_build:
                mock_service = mock.MagicMock()
                mock_service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
                    mock.MagicMock(status=500),
                    b'{"error": {"message": "Internal error"}}',
                )
                mock_build.return_value = mock_service

                with pytest.raises(GmailDraftError, match="Gmail API error"):
                    tool.execute(_approved_email_action())
```

- [ ] **Step 2: Run execution/auth tests**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestGmailAuth tests/test_gmail_draft.py::TestGmailExecuteWithMockedAPI -v
```

Expected: PASS if Task 3 implementation is complete; otherwise fix only the failing behavior described by pytest.

- [ ] **Step 3: Run all Gmail tests**

```bash
python3 -m pytest tests/test_gmail_draft.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/idea_to_action/tools/gmail_draft.py tests/test_gmail_draft.py
git commit -m "test: cover Gmail draft execution"
```

---

### Task 5: Registry routing

**Files:**
- Modify: `src/idea_to_action/tools/registry.py`
- Modify: `tests/test_tool_draft_layer.py`
- Modify: `tests/test_gmail_draft.py`

- [ ] **Step 1: Add failing registry tests**

Append to `tests/test_gmail_draft.py`:

```python

class TestRegistryWithGmail:
    def test_registry_is_not_connected_when_no_gmail_creds(self) -> None:
        from idea_to_action.tools.fake_email import FakeEmailTool
        from idea_to_action.tools.registry import ToolRegistry

        with mock.patch("idea_to_action.tools.registry.GMAIL_CREDENTIALS_PATH", "/nonexistent/gmail_creds.json"):
            registry = ToolRegistry()

        assert registry.is_gmail_connected is False
        assert isinstance(registry._email, FakeEmailTool)

    def test_registry_execute_send_email_uses_fake_when_unconfigured(self) -> None:
        from idea_to_action.tools.registry import ToolRegistry

        with mock.patch("idea_to_action.tools.registry.GMAIL_CREDENTIALS_PATH", "/nonexistent/gmail_creds.json"):
            registry = ToolRegistry()
            result = registry.execute(_approved_email_action())

        assert result["status"] == "fake_created"
        assert result["email_to"] == "person@example.com"
```

- [ ] **Step 2: Run registry tests to verify they fail**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestRegistryWithGmail -v
```

Expected: FAIL because registry does not import Gmail config or route `SEND_EMAIL`.

- [ ] **Step 3: Update registry imports**

In `src/idea_to_action/tools/registry.py`, change:

```python
from idea_to_action.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH
```

to:

```python
from idea_to_action.config import (
    GMAIL_CREDENTIALS_PATH,
    GMAIL_TOKEN_PATH,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
)
```

Add:

```python
from idea_to_action.tools.fake_email import FakeEmailTool
```

- [ ] **Step 4: Add Gmail setup in `ToolRegistry.__init__`**

After Calendar setup, add:

```python
        # Gmail: auto-detect based on credentials file
        if os.path.exists(GMAIL_CREDENTIALS_PATH):
            from idea_to_action.tools.gmail_draft import GmailDraftTool
            self._email = GmailDraftTool(GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH)
        else:
            self._email = FakeEmailTool()
```

Change `_executors` to:

```python
        self._executors = {
            ActionType.CREATE_TASK: self._task_manager,
            ActionType.CREATE_CALENDAR_EVENT: self._calendar,
            ActionType.SEND_EMAIL: self._email,
        }
```

- [ ] **Step 5: Add Gmail connection property**

Add below `is_notion_task_manager_connected`:

```python
    @property
    def is_gmail_connected(self) -> bool:
        """Whether Gmail draft integration (real) is configured, not fake."""
        return not isinstance(self._email, FakeEmailTool)
```

- [ ] **Step 6: Run registry tests**

```bash
python3 -m pytest tests/test_gmail_draft.py::TestRegistryWithGmail tests/test_tool_draft_layer.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/idea_to_action/tools/registry.py tests/test_gmail_draft.py tests/test_tool_draft_layer.py
git commit -m "feat: route email actions through Gmail registry"
```

---

### Task 6: Auth script

**Files:**
- Create: `scripts/auth_gmail.py`
- Modify: `tests/test_gmail_draft.py`

- [ ] **Step 1: Add failing auth script test**

Append to `tests/test_gmail_draft.py`:

```python

def test_auth_gmail_script_exists() -> None:
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "auth_gmail.py"

    assert script.exists()
    assert "GmailDraftTool.run_auth_flow()" in script.read_text()
```

- [ ] **Step 2: Run auth script test to verify it fails**

```bash
python3 -m pytest tests/test_gmail_draft.py::test_auth_gmail_script_exists -v
```

Expected: FAIL because `scripts/auth_gmail.py` does not exist.

- [ ] **Step 3: Create auth script**

Create `scripts/auth_gmail.py`:

```python
#!/usr/bin/env python3
"""One-time Gmail OAuth setup for idea-to-action."""

from idea_to_action.tools.gmail_draft import GmailDraftTool


if __name__ == "__main__":
    GmailDraftTool.run_auth_flow()
```

- [ ] **Step 4: Run auth script test**

```bash
python3 -m pytest tests/test_gmail_draft.py::test_auth_gmail_script_exists -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/auth_gmail.py tests/test_gmail_draft.py
git commit -m "feat: add Gmail auth script"
```

---

### Task 7: UI status and Gmail draft result rendering

**Files:**
- Modify: `src/idea_to_action/ui/app.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Add failing UI unit test for Gmail result text helper**

If `tests/test_ui.py` does not already expose a result formatting helper, first add one through this test by importing `_format_execution_result_message` after implementation. Append:

```python

def test_format_execution_result_message_for_gmail_draft() -> None:
    from idea_to_action.ui.app import _format_execution_result_message

    message = _format_execution_result_message({
        "status": "created",
        "gmail_draft_id": "draft_123",
        "gmail_message_id": "msg_123",
        "email_to": "person@example.com",
        "email_subject": "Hello",
    })

    assert "Gmail draft created" in message
    assert "draft_123" in message
    assert "person@example.com" in message
    assert "Hello" in message
```

- [ ] **Step 2: Run UI test to verify it fails**

```bash
python3 -m pytest tests/test_ui.py::test_format_execution_result_message_for_gmail_draft -v
```

Expected: FAIL because `_format_execution_result_message` does not exist.

- [ ] **Step 3: Add result formatting helper**

In `src/idea_to_action/ui/app.py`, above `_render_tool_actions`, add:

```python
def _format_execution_result_message(result_data: dict) -> str:
    """Return a human-readable execution result message."""
    if result_data.get("gmail_draft_id"):
        return (
            f"Gmail draft created: {result_data.get('email_subject', '')} "
            f"to {result_data.get('email_to', '')} "
            f"(Draft ID: `{result_data['gmail_draft_id']}`)"
        )
    return f"Execution result: {result_data}"
```

- [ ] **Step 4: Use helper in `_render_tool_actions`**

In `src/idea_to_action/ui/app.py`, after the Notion branch and before the generic branch, add:

```python
                    elif result_data.get("gmail_draft_id"):
                        st.success(_format_execution_result_message(result_data))
```

Also add Gmail status after Notion status:

```python
    if registry.is_gmail_connected:
        st.success("Gmail: Connected")
    else:
        st.caption("Gmail: Not configured (using fake tool)")
```

- [ ] **Step 5: Run UI tests**

```bash
python3 -m pytest tests/test_ui.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/idea_to_action/ui/app.py tests/test_ui.py
git commit -m "feat: show Gmail draft status in UI"
```

---

### Task 8: Docs and feature evidence

**Files:**
- Create: `docs/using-gmail-integration.md`
- Modify: `feature_list.json`

- [ ] **Step 1: Create Gmail usage guide**

Create `docs/using-gmail-integration.md`:

```markdown
# Using the Gmail Draft Integration (F016)

The system creates Gmail draft emails when you approve `send_email` tool actions. It never sends email automatically.

## Prerequisites

1. Google Cloud project with Gmail API enabled
2. OAuth client secret JSON downloaded to `gmail_client_secret.json`, or `I2A_GMAIL_CREDENTIALS` set to its path
3. Python dependencies installed with the Google optional extras

## Step 1: Authenticate Gmail

Run:

```bash
python3 scripts/auth_gmail.py
```

Approve the Gmail compose scope in the browser. The token is saved to `data/gmail_token.json` by default, or to `I2A_GMAIL_TOKEN` if set.

## Step 2: Verify Registry Connection

```bash
python3 -c "from idea_to_action.tools.registry import ToolRegistry; print(ToolRegistry().is_gmail_connected)"
```

Expected: `True` when `gmail_client_secret.json` exists.

## Step 3: Execute an Approved Email Action

```python
from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction
from idea_to_action.tools.registry import ToolRegistry

 action = ToolAction(
    action_type=ActionType.SEND_EMAIL,
    action_data={
        "to": "person@example.com",
        "subject": "Hello",
        "body": "Draft body",
    },
    approval_required=True,
    approval_status=ApprovalStatus.APPROVED,
)

result = ToolRegistry().execute(action)
print(result)
```

The draft appears in Gmail Drafts.

## Safety

F016 only calls Gmail `drafts.create`. It never calls Gmail send endpoints.

## Troubleshooting

| Error | What to do |
|---|---|
| `Not authenticated` | Run `python3 scripts/auth_gmail.py` |
| Client secret missing | Download OAuth client JSON and save it as `gmail_client_secret.json` |
| Gmail API error | Confirm Gmail API is enabled and OAuth scope was approved |
```

Fix the accidental leading space before `action = ToolAction` after writing the file.

- [ ] **Step 2: Update F016 in `feature_list.json`**

Change F016 status to `passing` only after verification in Task 9. For now, leave it `not_started` or set to `in_progress` if implementation has begun. Add evidence in Task 9 after tests pass.

- [ ] **Step 3: Commit docs**

```bash
git add docs/using-gmail-integration.md feature_list.json
git commit -m "docs: add Gmail draft integration guide"
```

---

### Task 9: Verification and final feature_list update

**Files:**
- Modify: `feature_list.json`

- [ ] **Step 1: Run targeted tests**

```bash
python3 -m pytest tests/test_gmail_draft.py tests/test_tool_draft_layer.py tests/test_ui.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

```bash
python3 -m pytest
```

Expected: PASS, unless local API keys make pre-existing tests environment-sensitive. If failures are unrelated to F016 and caused by local env, record exact failing tests in the final response and run targeted tests with relevant env vars unset.

- [ ] **Step 3: Run evals**

```bash
python3 scripts/run_evals.py
```

Expected: all evals pass.

- [ ] **Step 4: Update F016 evidence**

In `feature_list.json`, update F016:

```json
"status": "passing",
"evidence": [
  "tests/test_gmail_draft.py passing",
  "GmailDraftTool: OAuth2 compose scope, approval-gated execute()",
  "ToolRegistry routes SEND_EMAIL to GmailDraftTool when configured, else FakeEmailTool",
  "Draft creation uses users().drafts().create only; no send endpoint is called",
  "UI shows Gmail connection status and draft IDs",
  "scripts/auth_gmail.py for one-time OAuth2 browser flow"
],
"notes": "Creates Gmail drafts only, never sends automatically. Requires Gmail API enabled and OAuth credentials via I2A_GMAIL_CREDENTIALS or gmail_client_secret.json. All writes approval-gated."
```

- [ ] **Step 5: Validate JSON**

```bash
python3 -m json.tool feature_list.json >/dev/null
```

Expected: exit code 0.

- [ ] **Step 6: Commit final evidence**

```bash
git add feature_list.json
git commit -m "feat: mark F016 Gmail draft integration as passing"
```

---

## Self-Review

- Spec coverage: config, gitignore, Gmail tool, fake fallback, registry, auth script, UI, docs, trace logging, safety invariant, tests, and feature evidence are all mapped to tasks.
- Placeholder scan: no TBD/TODO placeholders. Each implementation step includes concrete code or exact commands.
- Type consistency: tool names, config names, action type `ActionType.SEND_EMAIL`, result keys, and env vars match the approved spec.
- Scope check: no planner/schema extraction changes, no sending, no attachments, no threaded replies.
