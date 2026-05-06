# F014 - Google Calendar Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `FakeCalendarTool` with `GoogleCalendarTool` that creates real Google Calendar events from approved draft actions via OAuth2 Web Flow.

**Architecture:** One self-contained `GoogleCalendarTool` class in `src/idea_to_action/tools/google_calendar.py` with the same `execute(action)` / `draft_create_event(event)` interface as `FakeCalendarTool`. OAuth2 auth handled by a separate `scripts/auth_google.py` CLI. `ToolRegistry` auto-detects credentials and falls back to `FakeCalendarTool` when Google is not configured. UI updated to show connection status and event links.

**Tech Stack:** `google-auth-oauthlib` (OAuth2 flow + token refresh), `google-api-python-client` (Calendar API), pytest with `unittest.mock` for tests.

---

### Task 1: Config and Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/idea_to_action/config.py`
- Create: `.gitignore`

- [ ] **Step 1: Add google optional deps to pyproject.toml**

Add after the `ui = ["streamlit>=1.40.0"]` line:

```toml
google = [
    "google-auth-oauthlib>=1.0.0",
    "google-api-python-client>=2.0.0",
]
```

Run:
```
python3 -m pip install -e ".[google,dev]"
```

- [ ] **Step 2: Add Google config vars to config.py**

Add after the `# Reports` block (before `ensure_dirs`):

```python
# Project root (used for credentials file default path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Google Calendar
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "I2A_GOOGLE_CREDENTIALS",
    os.path.join(_PROJECT_ROOT, "client_secret.json"),
)
GOOGLE_TOKEN_PATH = os.environ.get(
    "I2A_GOOGLE_TOKEN",
    os.path.join(DATA_DIR, "google_token.json"),
)
TIMEZONE = os.environ.get("I2A_TIMEZONE", "Asia/Ho_Chi_Minh")
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
data/
traces/
reports/
client_secret.json
google_token.json
.env
```

- [ ] **Step 4: Verify config imports**

Run:
```
python3 -c "from idea_to_action.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH, TIMEZONE; print(GOOGLE_CREDENTIALS_PATH); print(GOOGLE_TOKEN_PATH); print(TIMEZONE)"
```

Expected: paths ending in `client_secret.json`, `data/google_token.json`, and `Asia/Ho_Chi_Minh`.

**Commit:**
```bash
git add pyproject.toml src/idea_to_action/config.py .gitignore
git commit -m "feat: add Google Calendar config and dependencies for F014"
```

---

### Task 2: `GoogleCalendarTool` Class

**Files:**
- Create: `src/idea_to_action/tools/google_calendar.py`

- [ ] **Step 1: Write the full GoogleCalendarTool module**

```python
"""Google Calendar integration tool.

Creates real Google Calendar events from approved draft actions.
Uses OAuth2 Web Flow for authentication.
Same interface as FakeCalendarTool — approval-gated.
"""

import os
from datetime import UTC, datetime, timedelta, timezone

from google.auth.exceptions import GoogleAuthError as GAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from idea_to_action.config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    TIMEZONE,
)
from idea_to_action.schemas.tasks import DraftCalendarEvent
from idea_to_action.schemas.tool_actions import (
    ActionType,
    ApprovalStatus,
    ToolAction,
)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class GoogleIntegrationError(Exception):
    """Base error for Google integrations."""


class GoogleAuthError(GoogleIntegrationError):
    """Authentication error — user needs to run auth flow."""


class GoogleCalendarError(GoogleIntegrationError):
    """Error from the Google Calendar API."""


class GoogleCalendarTool:
    """Real Google Calendar integration via OAuth2.

    Same interface as FakeCalendarTool:
    - execute(action) -> dict
    - draft_create_event(event) -> ToolAction

    Approval-gated: only executes approved CREATE_CALENDAR_EVENT actions.
    """

    name = "google_calendar"

    def __init__(self, credentials_path: str | None = None, token_path: str | None = None) -> None:
        self._credentials_path = credentials_path or GOOGLE_CREDENTIALS_PATH
        self._token_path = token_path or GOOGLE_TOKEN_PATH
        self._service = None

    def _get_credentials(self) -> Credentials:
        """Load credentials from token file, refreshing if needed.

        Returns valid Credentials or raises GoogleAuthError if auth is needed.
        """
        if not os.path.exists(self._token_path):
            raise GoogleAuthError(
                "Not authenticated. Run: python3 scripts/auth_google.py"
            )

        creds = Credentials.from_authorized_user_file(
            self._token_path, SCOPES
        )

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds)
            except GAuthError as e:
                raise GoogleAuthError(
                    f"Token refresh failed. Re-authenticate: python3 scripts/auth_google.py\n{e}"
                ) from e

        if not creds or not creds.valid:
            raise GoogleAuthError(
                "Not authenticated. Run: python3 scripts/auth_google.py"
            )

        return creds

    def _save_credentials(self, creds: Credentials) -> None:
        """Persist refreshed credentials back to token file."""
        os.makedirs(os.path.dirname(self._token_path), exist_ok=True)
        with open(self._token_path, "w") as f:
            f.write(creds.to_json())

    def _get_service(self):
        """Build and return an authenticated Google Calendar API service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    @staticmethod
    def run_auth_flow(credentials_path: str | None = None, token_path: str | None = None) -> None:
        """Run the browser-based OAuth flow and save the token.

        Call this once from scripts/auth_google.py.
        """
        creds_path = credentials_path or GOOGLE_CREDENTIALS_PATH
        tok_path = token_path or GOOGLE_TOKEN_PATH

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

    def draft_create_event(self, event: DraftCalendarEvent) -> ToolAction:
        """Create a draft tool action for a calendar event (approval-gated)."""
        return ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={
                "title": event.title,
                "description": event.description,
                "date": event.suggested_date.isoformat()
                if event.suggested_date
                else None,
                "time": event.suggested_time.isoformat()
                if event.suggested_time
                else None,
                "duration_minutes": event.duration_minutes,
            },
            approval_required=True,
            approval_status=ApprovalStatus.PENDING,
            created_at=datetime.now(UTC),
        )

    def execute(self, action: ToolAction) -> dict:
        """Create a real Google Calendar event from an approved action.

        Returns:
            dict with keys: status, google_event_id, html_link, event_summary

        Raises:
            ValueError: Wrong action type.
            PermissionError: Action not approved.
            GoogleAuthError: Not authenticated.
            GoogleCalendarError: API call failed.
        """
        if action.action_type != ActionType.CREATE_CALENDAR_EVENT:
            raise ValueError(
                f"GoogleCalendarTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        service = self._get_service()
        event_body = self._build_event_body(action.action_data)

        try:
            created = (
                service.events()
                .insert(calendarId="primary", body=event_body)
                .execute()
            )
        except HttpError as e:
            raise GoogleCalendarError(
                f"Google Calendar API error: {e}"
            ) from e

        return {
            "status": "created",
            "google_event_id": created.get("id"),
            "html_link": created.get("htmlLink"),
            "event_summary": created.get("summary"),
        }

    def _build_event_body(self, action_data: dict) -> dict:
        """Build a Google Calendar event body from action_data.

        Handles both timed events (date + time) and all-day events (date only).
        """
        title = action_data.get("title", "Untitled Event")
        description = action_data.get("description", "")
        date_str = action_data.get("date")
        time_str = action_data.get("time")
        duration = action_data.get("duration_minutes", 60)

        body = {
            "summary": title,
            "description": description or "",
        }

        if date_str:
            if time_str:
                # Timed event: use dateTime with timezone
                start_dt = f"{date_str}T{time_str}:00"
                # Parse to compute end time
                try:
                    start = datetime.fromisoformat(start_dt)
                except ValueError:
                    # Fallback: just pass through
                    body["start"] = {
                        "dateTime": start_dt,
                        "timeZone": TIMEZONE,
                    }
                    body["end"] = {
                        "dateTime": start_dt,
                        "timeZone": TIMEZONE,
                    }
                    return body

                end = start + timedelta(minutes=int(duration))
                body["start"] = {
                    "dateTime": start.isoformat(),
                    "timeZone": TIMEZONE,
                }
                body["end"] = {
                    "dateTime": end.isoformat(),
                    "timeZone": TIMEZONE,
                }
            else:
                # All-day event: use date only (no timezone for all-day)
                body["start"] = {"date": date_str}
                # For all-day events, Google uses the next day as end
                try:
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    next_day = parsed_date + timedelta(days=1)
                    body["end"] = {"date": next_day.isoformat()}
                except ValueError:
                    body["end"] = {"date": date_str}
        else:
            # No date — create a 1-hour event now
            now = datetime.now(timezone.utc)
            body["start"] = {
                "dateTime": now.isoformat(),
                "timeZone": TIMEZONE,
            }
            body["end"] = {
                "dateTime": (now + timedelta(minutes=int(duration))).isoformat(),
                "timeZone": TIMEZONE,
            }

        return body
```

- [ ] **Step 2: Verify module imports**

Run:
```
python3 -c "from idea_to_action.tools.google_calendar import GoogleCalendarTool, GoogleIntegrationError, GoogleAuthError, GoogleCalendarError; print('OK')"
```

Expected: `OK`

**Commit:**
```bash
git add src/idea_to_action/tools/google_calendar.py
git commit -m "feat: add GoogleCalendarTool with OAuth2 and approval-gated execute"
```

---

### Task 3: Auth Script

**Files:**
- Create: `scripts/auth_google.py`

- [ ] **Step 1: Write auth_google.py**

```python
#!/usr/bin/env python3
"""One-time Google OAuth2 authentication for idea-to-action.

Run this once to authorize Google Calendar access:
    python3 scripts/auth_google.py

Prerequisites:
    - client_secret.json in the project root (download from Google Cloud Console)
    - Google Calendar API enabled in your GCP project
"""

import sys

from idea_to_action.tools.google_calendar import GoogleCalendarTool


def main() -> None:
    try:
        GoogleCalendarTool.run_auth_flow()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "\nTo get a client_secret.json file:\n"
            "1. Go to https://console.cloud.google.com/apis/credentials\n"
            "2. Create an OAuth 2.0 Client ID (Desktop application)\n"
            "3. Download the JSON and save it as 'client_secret.json' in the project root",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable and verify syntax**

Run:
```
chmod +x scripts/auth_google.py
python3 -c "import py_compile; py_compile.compile('scripts/auth_google.py', doraise=True); print('OK')"
```

Expected: `OK`

**Commit:**
```bash
git add scripts/auth_google.py
git commit -m "feat: add Google OAuth2 auth script"
```

---

### Task 4: Registry Wiring

**Files:**
- Modify: `src/idea_to_action/tools/registry.py`

- [ ] **Step 1: Update ToolRegistry to auto-detect Google Calendar**

Replace the entire file content:

```python
"""Tool registry — maps action types to tools.

Used by the Tool Draft Generator and Tool Executor nodes.
Auto-detects Google Calendar when credentials are configured,
falls back to FakeCalendarTool otherwise.
"""

import os

from idea_to_action.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH
from idea_to_action.schemas.tool_actions import ActionType, ToolAction
from idea_to_action.tools.fake_calendar import FakeCalendarTool
from idea_to_action.tools.fake_task_manager import FakeTaskManagerTool


class ToolRegistry:
    """Registry that maps action types to tool instances.

    Uses GoogleCalendarTool when Google credentials are available,
    falls back to FakeCalendarTool when they are not.
    """

    def __init__(self) -> None:
        self._task_manager = FakeTaskManagerTool()

        if os.path.exists(GOOGLE_CREDENTIALS_PATH):
            from idea_to_action.tools.google_calendar import GoogleCalendarTool
            self._calendar = GoogleCalendarTool(
                GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH
            )
        else:
            self._calendar = FakeCalendarTool()

        self._executors = {
            ActionType.CREATE_TASK: self._task_manager,
            ActionType.CREATE_CALENDAR_EVENT: self._calendar,
        }

    @property
    def is_google_calendar_connected(self) -> bool:
        """Whether Google Calendar (real) is configured, not fake."""
        return not isinstance(self._calendar, FakeCalendarTool)

    def execute(self, action: ToolAction) -> dict:
        """Route an approved action to the correct tool for execution.

        Raises:
            ValueError: If no tool is registered for this action type.
        """
        tool = self._executors.get(action.action_type)
        if tool is None:
            raise ValueError(
                f"No tool registered for action type '{action.action_type.value}'"
            )
        return tool.execute(action)
```

- [ ] **Step 2: Verify registry with and without credentials**

Run (credentials file doesn't exist — should use fake):
```
python3 -c "
from idea_to_action.tools.registry import ToolRegistry
r = ToolRegistry()
print('Google connected:', r.is_google_calendar_connected)
"
```

Expected: `Google connected: False`

- [ ] **Step 3: Run existing tests to confirm no regression**

Run:
```
python3 -m pytest tests/test_tool_draft_layer.py -v
```

Expected: all 16 tests pass.

**Commit:**
```bash
git add src/idea_to_action/tools/registry.py
git commit -m "feat: wire GoogleCalendarTool into registry with auto-detect"
```

---

### Task 5: Tests

**Files:**
- Create: `tests/test_google_calendar.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for F014 - Google Calendar integration."""

import json
from datetime import UTC, datetime, time, timezone
from unittest import mock

import pytest

from idea_to_action.schemas.tasks import DraftCalendarEvent
from idea_to_action.schemas.tool_actions import (
    ActionType,
    ApprovalStatus,
    ToolAction,
)
from idea_to_action.tools.google_calendar import (
    GoogleAuthError,
    GoogleCalendarError,
    GoogleCalendarTool,
    GoogleIntegrationError,
)


def _make_approved_calendar_action(
    action_data: dict | None = None,
) -> ToolAction:
    return ToolAction(
        action_type=ActionType.CREATE_CALENDAR_EVENT,
        action_data=action_data or {
            "title": "Team Sync",
            "description": "Weekly sync",
            "date": "2026-05-07",
            "time": "14:00",
            "duration_minutes": 30,
        },
        approval_required=True,
        approval_status=ApprovalStatus.APPROVED,
    )


def _make_pending_calendar_action() -> ToolAction:
    return ToolAction(
        action_type=ActionType.CREATE_CALENDAR_EVENT,
        action_data={"title": "Test"},
        approval_required=True,
        approval_status=ApprovalStatus.PENDING,
    )


class TestErrorHierarchy:
    def test_google_integration_error_is_base(self) -> None:
        assert issubclass(GoogleAuthError, GoogleIntegrationError)
        assert issubclass(GoogleCalendarError, GoogleIntegrationError)

    def test_errors_are_exceptions(self) -> None:
        assert issubclass(GoogleIntegrationError, Exception)


class TestGoogleCalendarToolInit:
    def test_init_with_defaults(self) -> None:
        tool = GoogleCalendarTool()
        assert tool.name == "google_calendar"
        assert tool._credentials_path is not None
        assert tool._token_path is not None

    def test_init_with_custom_paths(self) -> None:
        tool = GoogleCalendarTool("/tmp/creds.json", "/tmp/token.json")
        assert tool._credentials_path == "/tmp/creds.json"
        assert tool._token_path == "/tmp/token.json"


class TestExecuteApprovalGating:
    def test_execute_pending_blocked(self) -> None:
        tool = GoogleCalendarTool()
        action = _make_pending_calendar_action()
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(action)

    def test_execute_rejected_blocked(self) -> None:
        tool = GoogleCalendarTool()
        action = _make_pending_calendar_action()
        rejected = action.model_copy(
            update={"approval_status": ApprovalStatus.REJECTED}
        )
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(rejected)

    def test_execute_wrong_action_type(self) -> None:
        tool = GoogleCalendarTool()
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Task"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        with pytest.raises(ValueError, match="cannot execute action type"):
            tool.execute(action)


class TestBuildEventBody:
    def test_event_body_mapping_timed(self) -> None:
        tool = GoogleCalendarTool()
        body = tool._build_event_body({
            "title": "Meeting",
            "description": "Discuss Q2",
            "date": "2026-05-07",
            "time": "14:00",
            "duration_minutes": 45,
        })

        assert body["summary"] == "Meeting"
        assert body["description"] == "Discuss Q2"
        assert "dateTime" in body["start"]
        assert body["start"]["dateTime"].startswith("2026-05-07T14:00")
        assert "dateTime" in body["end"]
        assert "timeZone" in body["start"]

    def test_event_body_mapping_allday(self) -> None:
        tool = GoogleCalendarTool()
        body = tool._build_event_body({
            "title": "Holiday",
            "description": None,
            "date": "2026-05-07",
            "time": None,
            "duration_minutes": 60,
        })

        assert body["summary"] == "Holiday"
        assert "date" in body["start"]
        assert body["start"]["date"] == "2026-05-07"
        assert body["end"]["date"] == "2026-05-08"
        # All-day events should NOT have dateTime
        assert "dateTime" not in body["start"]

    def test_event_body_no_date(self) -> None:
        tool = GoogleCalendarTool()
        body = tool._build_event_body({
            "title": "Now",
            "description": "",
            "date": None,
            "time": None,
            "duration_minutes": 30,
        })

        assert body["summary"] == "Now"
        assert "dateTime" in body["start"]
        assert "timeZone" in body["start"]


class TestDraftCreateEvent:
    def test_draft_create_event(self) -> None:
        tool = GoogleCalendarTool()
        event = DraftCalendarEvent(
            title="Team sync",
            suggested_date=datetime(2026, 5, 7),
            suggested_time=time(14, 0),
            duration_minutes=30,
        )
        action = tool.draft_create_event(event)

        assert action.action_type == ActionType.CREATE_CALENDAR_EVENT
        assert action.approval_required is True
        assert action.approval_status == ApprovalStatus.PENDING
        assert action.action_data["title"] == "Team sync"
        assert action.action_data["date"] is not None
        assert action.action_data["time"] is not None
        assert action.action_data["duration_minutes"] == 30


class TestExecuteWithMockedAPI:
    def test_execute_approved_creates_event(self) -> None:
        """execute() with APPROVED status calls the API and returns event metadata."""
        tool = GoogleCalendarTool()
        action = _make_approved_calendar_action()

        # Mock _get_credentials to return a fake valid cred
        fake_creds = mock.MagicMock()
        fake_creds.valid = True
        fake_creds.expired = False

        with mock.patch.object(tool, "_get_credentials", return_value=fake_creds):
            with mock.patch("idea_to_action.tools.google_calendar.build") as mock_build:
                mock_service = mock.MagicMock()
                mock_events = mock.MagicMock()
                mock_insert = mock.MagicMock()
                mock_execute = mock.MagicMock(return_value={
                    "id": "evt_abc123",
                    "htmlLink": "https://calendar.google.com/event?eid=abc123",
                    "summary": "Team Sync",
                })

                mock_insert.return_value.execute = mock_execute
                mock_events.return_value.insert.return_value = mock_insert
                mock_service.events.return_value = mock_events
                mock_build.return_value = mock_service

                result = tool.execute(action)

        assert result["status"] == "created"
        assert result["google_event_id"] == "evt_abc123"
        assert "calendar.google.com" in result["html_link"]

    def test_execute_without_auth_raises(self) -> None:
        """When no token file exists, raises GoogleAuthError."""
        tool = GoogleCalendarTool("/nonexistent/creds.json", "/nonexistent/token.json")
        action = _make_approved_calendar_action()

        with pytest.raises(GoogleAuthError, match="Not authenticated"):
            tool.execute(action)

    def test_execute_api_error_wrapped(self) -> None:
        """When the API returns an error, wraps it in GoogleCalendarError."""
        tool = GoogleCalendarTool()
        action = _make_approved_calendar_action()

        fake_creds = mock.MagicMock()
        fake_creds.valid = True
        fake_creds.expired = False

        with mock.patch.object(tool, "_get_credentials", return_value=fake_creds):
            with mock.patch("idea_to_action.tools.google_calendar.build") as mock_build:
                from googleapiclient.errors import HttpError

                mock_service = mock.MagicMock()
                mock_service.events.return_value.insert.return_value.execute.side_effect = (
                    HttpError(
                        mock.MagicMock(status=500),
                        b'{"error": {"message": "Internal error"}}',
                    )
                )
                mock_build.return_value = mock_service

                with pytest.raises(GoogleCalendarError, match="Google Calendar API error"):
                    tool.execute(action)


class TestRegistryWithGoogle:
    def test_registry_is_not_connected_when_no_creds(self) -> None:
        """When no credentials file, is_google_calendar_connected is False."""
        from idea_to_action.tools.registry import ToolRegistry

        with mock.patch(
            "idea_to_action.tools.registry.GOOGLE_CREDENTIALS_PATH",
            "/nonexistent/creds.json",
        ):
            registry = ToolRegistry()
            assert registry.is_google_calendar_connected is False

    def test_registry_execute_still_works_with_fake(self) -> None:
        """Even without Google, registry.execute() still works via FakeCalendarTool."""
        from idea_to_action.tools.registry import ToolRegistry

        with mock.patch(
            "idea_to_action.tools.registry.GOOGLE_CREDENTIALS_PATH",
            "/nonexistent/creds.json",
        ):
            registry = ToolRegistry()
            action = _make_approved_calendar_action()
            result = registry.execute(action)
            assert result["status"] == "fake_executed"
```

- [ ] **Step 2: Run the tests**

Run:
```
python3 -m pytest tests/test_google_calendar.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 3: Run full test suite to confirm no regressions**

Run:
```
python3 -m pytest tests/ -v
```

Expected: all tests pass (271 old + 14 new = 285).

**Commit:**
```bash
git add tests/test_google_calendar.py
git commit -m "test: add Google Calendar integration tests"
```

---

### Task 6: UI Updates

**Files:**
- Modify: `src/idea_to_action/ui/app.py`

- [ ] **Step 1: Update _render_tool_actions to show connection status and event links**

Replace the `_render_tool_actions` function:

```python
def _render_tool_actions() -> None:
    """Render the draft tool actions with approve/reject buttons."""
    result = st.session_state.pipeline_result
    tool_actions = result.tool_actions
    if tool_actions is None or not tool_actions.actions:
        return

    st.subheader("Draft Tool Actions")

    # Show Google Calendar connection status
    registry = ToolRegistry()
    if registry.is_google_calendar_connected:
        st.success("Google Calendar: Connected")
    else:
        st.caption("Google Calendar: Not configured (using fake tool)")

    st.write(f"{len(tool_actions.actions)} action(s) pending approval.")

    for idx, action in enumerate(tool_actions.actions):
        state_key = str(idx)
        current_state = st.session_state.action_states.get(state_key, "pending")

        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.write(f"**{action.action_type.value}**")
                st.json(action.action_data)
                st.caption(
                    f"Drafted: {action.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
                    if action.created_at else ""
                )

            with col2:
                if current_state == "pending":
                    st.button(
                        "Approve",
                        key=f"approve_{idx}",
                        type="primary",
                        on_click=_approve_action,
                        args=(idx, action),
                    )

            with col3:
                if current_state == "pending":
                    st.button(
                        "Reject",
                        key=f"reject_{idx}",
                        on_click=_reject_action,
                        args=(idx, action),
                    )

            if current_state != "pending":
                st.info(f"Status: **{current_state}**")

            exec_result = st.session_state.execution_results.get(state_key)
            if exec_result:
                if exec_result["success"]:
                    result_data = exec_result["result"]
                    # Show Google Calendar event link if available
                    if result_data.get("html_link"):
                        st.success(
                            f"Event created: [{result_data['event_summary']}]({result_data['html_link']}) "
                            f"(ID: `{result_data['google_event_id']}`)"
                        )
                    else:
                        st.success(f"Execution result: {result_data}")
                else:
                    st.error(f"Execution failed: {exec_result['error']}")
```

- [ ] **Step 2: Verify UI module imports**

Run:
```
python3 -c "import idea_to_action.ui.app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run UI tests**

Run:
```
python3 -m pytest tests/test_ui.py -v
```

Expected: all 10 tests pass.

**Commit:**
```bash
git add src/idea_to_action/ui/app.py
git commit -m "feat: show Google Calendar connection status and event links in UI"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run full test suite**

```
python3 -m pytest tests/ -v
```

Expected: 285 tests pass (271 old + 14 new).

- [ ] **Step 2: Run init.sh**

```
bash init.sh
```

Expected: all tests pass, all evals pass.

- [ ] **Step 3: Run evals**

```
python3 scripts/run_evals.py
```

Expected: 12/12 evals pass.

- [ ] **Step 4: Update feature_list.json**

Set F014 status to "passing" with evidence.

**Commit:**
```bash
git add feature_list.json
git commit -m "feat: mark F014 Google Calendar as passing"
```
