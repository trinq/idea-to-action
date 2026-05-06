# F014 - Google Calendar Integration Design

## Summary

Replace `FakeCalendarTool` with `GoogleCalendarTool` that creates real Google Calendar events from approved draft actions. Uses OAuth2 Web Flow for authentication. Same `execute(action)` interface — approval-gated, returns structured results.

## Files

### New Files

| File | Purpose |
|---|---|
| `src/idea_to_action/tools/google_calendar.py` | `GoogleCalendarTool` class + OAuth2 auth logic |
| `scripts/auth_google.py` | One-time CLI to run browser OAuth flow and save token |
| `tests/test_google_calendar.py` | Tests — unit with mocked Google API + approval gating |

### Modified Files

| File | Change |
|---|---|
| `pyproject.toml` | Add `google = ["google-auth-oauthlib>=1.0.0", "google-api-python-client>=2.0.0"]` optional deps |
| `src/idea_to_action/tools/registry.py` | Import `GoogleCalendarTool`, use it when credentials exist, fallback to `FakeCalendarTool` |
| `src/idea_to_action/config.py` | Add `GOOGLE_CREDENTIALS_PATH` and `GOOGLE_TOKEN_PATH` env vars with defaults |

## `GoogleCalendarTool` Class

Same interface as `FakeCalendarTool`:

```python
class GoogleCalendarTool:
    name = "google_calendar"

    def __init__(self, credentials_path, token_path): ...

    def execute(self, action: ToolAction) -> dict:
        # 1. Verify action_type == CREATE_CALENDAR_EVENT (else ValueError)
        # 2. Verify approval_status == APPROVED (else PermissionError)
        # 3. Build Google Calendar event body from action.action_data
        # 4. Call events.insert() via google-api-python-client
        # 5. Return {"status": "created", "google_event_id": "...", "html_link": "..."}
        ...

    def draft_create_event(self, event: DraftCalendarEvent) -> ToolAction:
        # Same as FakeCalendarTool — returns draft for approval gate
        ...
```

### Event Mapping

| `action_data` key | Google Calendar field |
|---|---|
| `title` | `summary` |
| `description` | `description` |
| `date` + `time` | `start.dateTime` (ISO 8601 with timezone) |
| `date` + `time` + `duration_minutes` | `end.dateTime` (ISO 8601 with timezone) |
| `date` only (no `time`) | `start.date` / `end.date` (all-day event, YYYY-MM-DD format) |
| — | `timeZone` from `I2A_TIMEZONE` config |

All-day events use `start.date` and `end.date` (date strings without time). Timed events use `start.dateTime` and `end.dateTime` (full ISO 8601 with timezone offset).

### Error Handling

| Condition | Exception | Message |
|---|---|---|
| Wrong action type | `ValueError` | "Cannot execute action type '...' " |
| Not approved | `PermissionError` | "Cannot execute unapproved action. Status is '...', requires 'approved'." |
| Not authenticated | `GoogleAuthError` | "Not authenticated. Run: python3 scripts/auth_google.py" |
| API failure (network, quota, etc.) | `GoogleCalendarError` | Wraps original error message |

`GoogleAuthError` and `GoogleCalendarError` inherit from `GoogleIntegrationError(Exception)`.

## Auth Flow

### One-time Setup

```
python3 scripts/auth_google.py
```

1. Reads `client_secret.json` from project root (`I2A_GOOGLE_CREDENTIALS` env var override)
2. Opens browser for OAuth consent screen
3. Requests scope: `https://www.googleapis.com/auth/calendar.events`
4. Receives refresh token, saves to `data/google_token.json` (`I2A_GOOGLE_TOKEN` env var override)
5. Prints success

### Token Lifecycle

- `google-auth-oauthlib` auto-refreshes access tokens via the refresh token
- If token file is missing or unrecoverable, `GoogleAuthError` raised
- Token file added to `.gitignore`
- Token file permissions should be `600` (owner read/write only) — set after OAuth flow completes

### Config (`config.py`)

```python
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "I2A_GOOGLE_CREDENTIALS",
    os.path.join(PROJECT_ROOT, "client_secret.json")
)
GOOGLE_TOKEN_PATH = os.environ.get(
    "I2A_GOOGLE_TOKEN",
    os.path.join(DATA_DIR, "google_token.json")
)
GOOGLE_CALENDAR_ID = os.environ.get(
    "I2A_GOOGLE_CALENDAR_ID",
    "primary"
)
TIMEZONE = os.environ.get(
    "I2A_TIMEZONE",
    "Asia/Ho_Chi_Minh"
)
```

## Registry Wiring

```python
class ToolRegistry:
    def __init__(self):
        self._task_manager = FakeTaskManagerTool()

        if os.path.exists(GOOGLE_CREDENTIALS_PATH):
            self._calendar = GoogleCalendarTool(GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH)
        else:
            self._calendar = FakeCalendarTool()

        self._executors = {
            ActionType.CREATE_TASK: self._task_manager,
            ActionType.CREATE_CALENDAR_EVENT: self._calendar,
        }
```

When Google is not configured, `FakeCalendarTool` is used — no breaking change.

## Dependencies

```toml
[project.optional-dependencies]
google = [
    "google-auth-oauthlib>=1.0.0",
    "google-api-python-client>=2.0.0",
]
```

Install: `pip install -e ".[google,dev]"`

## Tests (`tests/test_google_calendar.py`)

Test approach: mock `googleapiclient.discovery.build` to avoid real API calls.

| Test | What it verifies |
|---|---|
| `test_execute_approved_creates_event` | `execute()` with APPROVED status calls `events().insert()` and returns event metadata |
| `test_execute_pending_blocked` | `PermissionError` for PENDING action |
| `test_execute_rejected_blocked` | `PermissionError` for REJECTED action |
| `test_execute_wrong_action_type` | `ValueError` for non-CREATE_CALENDAR_EVENT |
| `test_execute_without_auth_raises` | `GoogleAuthError` when no valid token |
| `test_execute_api_error_wrapped` | `GoogleCalendarError` when API call fails |
| `test_draft_create_event` | Returns PENDING ToolAction with correct fields |
| `test_event_body_mapping` | action_data fields map correctly to Google event body |
| `test_allday_event_mapping` | date-only action creates all-day event (start.date, not start.dateTime) |
| `test_timezone_applied` | Event body includes correct timeZone from config |

## Trace Logging

`GoogleCalendarTool.execute()` must log via `TraceLogger` when creating real events:

```python
trace_logger.log("google_calendar_execute", {
    "action_type": action.action_type.value,
    "event_title": action.action_data.get("title"),
    "approval_status": action.approval_status.value,
    "google_event_id": result.get("google_event_id"),
    "html_link": result.get("html_link"),
})
```

This provides an audit trail for all real calendar writes.

## UI Updates

The Streamlit UI (`src/idea_to_action/ui/app.py`) should be updated to:

1. Show whether Google Calendar is connected (green badge) or using fake tool (gray badge)
2. Display `html_link` as a clickable link to the created Google Calendar event after execution
3. Show `google_event_id` in the execution result details
