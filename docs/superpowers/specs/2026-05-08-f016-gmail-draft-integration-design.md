# F016 - Gmail Draft Integration Design Spec

**Goal:** Create Gmail draft emails from approved `SEND_EMAIL` tool actions. F016 is tool-only: it does not change planner prompts, planner schemas, or automatic email extraction yet.

**Architecture:** Add a real `GmailDraftTool` that mirrors the existing Google Calendar tool pattern: OAuth2 token loading/refresh, approval-gated execution, Google API error wrapping, and registry auto-detection. Add a fake email fallback so local execution and tests remain safe when Gmail is not configured.

**Safety invariant:** The integration creates Gmail drafts only. It never sends emails automatically.

---

## Scope

### In scope

- Add Gmail OAuth config paths.
- Add `GmailDraftTool` for `ActionType.SEND_EMAIL`.
- Add `FakeEmailTool` fallback.
- Add `scripts/auth_gmail.py` for one-time OAuth.
- Update `ToolRegistry` to route `SEND_EMAIL`.
- Update UI status/result display for Gmail drafts.
- Add focused tests for auth, approval gating, MIME generation, draft creation, registry routing, and fake fallback.
- Update F016 evidence in `feature_list.json` after verification.

### Out of scope

- No `DraftEmail` schema in this version.
- No planner prompt changes.
- No automatic extraction of email actions from notes.
- No sending email.
- No attachment support.
- No threaded replies.

---

## Files

| File | Action |
|---|---|
| `src/idea_to_action/config.py` | Modify — add `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH` |
| `src/idea_to_action/tools/gmail_draft.py` | Create — real Gmail draft tool |
| `src/idea_to_action/tools/fake_email.py` | Create — fake fallback for `SEND_EMAIL` |
| `src/idea_to_action/tools/registry.py` | Modify — route `SEND_EMAIL`, expose Gmail connection status |
| `src/idea_to_action/ui/app.py` | Modify — show Gmail status and draft result |
| `scripts/auth_gmail.py` | Create — one-time OAuth flow |
| `tests/test_gmail_draft.py` | Create — unit tests for Gmail tool |
| `tests/test_tool_draft_layer.py` | Modify — registry/fake email routing tests as needed |
| `tests/test_ui.py` | Modify — status/result tests as needed |
| `feature_list.json` | Modify after verification — mark F016 passing with evidence |
| `docs/using-gmail-integration.md` | Create — setup and usage guide |

---

## Config

Add Gmail-specific credentials paths separate from Calendar:

```python
GMAIL_CREDENTIALS_PATH = os.environ.get(
    "GMAIL_CREDENTIALS_PATH",
    os.path.join(PROJECT_ROOT, "credentials", "gmail_credentials.json"),
)
GMAIL_TOKEN_PATH = os.environ.get(
    "GMAIL_TOKEN_PATH",
    os.path.join(PROJECT_ROOT, "credentials", "gmail_token.json"),
)
```

Use a separate token file because Gmail needs a different OAuth scope from Calendar. This avoids invalidating or confusing the existing Calendar token.

---

## OAuth Scope

Use the narrow compose scope:

```python
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
```

This permits creating and managing drafts without granting broader mailbox access or send permissions beyond what Gmail compose scope allows. The tool still only calls `drafts().create(...)`, never `messages().send(...)`.

---

## Action Payload

F016 consumes manually-created or externally-supplied `ToolAction` objects:

```python
ToolAction(
    action_type=ActionType.SEND_EMAIL,
    action_data={
        "to": "person@example.com",
        "subject": "Subject line",
        "body": "Email body text",
    },
    approval_required=True,
    approval_status=ApprovalStatus.APPROVED,
)
```

Optional fields:

```python
"cc": ["a@example.com"]
"bcc": ["b@example.com"]
```

Validation at the tool boundary:

| Condition | Behavior |
|---|---|
| Wrong action type | `ValueError` |
| Pending/rejected action | `PermissionError` |
| Missing/empty `to` | `GmailDraftError` |
| Missing `subject` | Default to empty string |
| Missing `body` | Default to empty string |

---

## GmailDraftTool

```python
class GmailIntegrationError(Exception):
    """Base error for Gmail integrations."""

class GmailAuthError(GmailIntegrationError):
    """Authentication error — user needs to run auth flow."""

class GmailDraftError(GmailIntegrationError):
    """Error from Gmail draft creation or payload validation."""

class GmailDraftTool:
    name = "gmail_draft"

    def __init__(self, credentials_path: str | None = None, token_path: str | None = None) -> None:
        """Store credential paths and lazily initialize the Gmail service."""

    def _get_credentials(self) -> Credentials:
        """Load, refresh, validate, and return Gmail OAuth credentials."""

    def _save_credentials(self, creds: Credentials) -> None:
        """Persist refreshed credentials to the configured token path."""

    def _get_service(self):
        """Build and cache the authenticated Gmail API service."""

    @staticmethod
    def run_auth_flow(credentials_path: str | None = None, token_path: str | None = None) -> None:
        """Run browser OAuth and save the Gmail token."""

    def execute(self, action: ToolAction) -> dict:
        """Create a Gmail draft from an approved SEND_EMAIL action."""

    def _build_mime_message(self, action_data: dict) -> str:
        """Return a base64url-encoded MIME message for Gmail drafts.create."""
```

### `execute()` behavior

1. Require `action.action_type == ActionType.SEND_EMAIL`.
2. Require `action.approval_status == ApprovalStatus.APPROVED`.
3. Validate required recipient data.
4. Build MIME email.
5. Base64url encode the MIME bytes.
6. Call:

```python
service.users().drafts().create(
    userId="me",
    body={"message": {"raw": encoded_message}},
).execute()
```

7. Return:

```python
{
    "status": "created",
    "gmail_draft_id": draft.get("id"),
    "gmail_message_id": draft.get("message", {}).get("id"),
    "email_subject": subject,
    "email_to": to,
}
```

### Error handling

- Missing token or invalid credentials → `GmailAuthError` with `python3 scripts/auth_gmail.py` guidance.
- Token refresh failure → `GmailAuthError`.
- Gmail API failure → `GmailDraftError`.
- Quota/rate errors remain wrapped in `GmailDraftError` with the original `HttpError` details.

---

## FakeEmailTool

A fake fallback keeps unconfigured environments safe and testable:

```python
class FakeEmailTool:
    name = "fake_email"
    def execute(self, action: ToolAction) -> dict: ...
```

It enforces the same approval gate and wrong-action guard, then returns:

```python
{
    "status": "fake_created",
    "email_to": action.action_data.get("to"),
    "email_subject": action.action_data.get("subject"),
}
```

It does not call external services.

---

## Registry Wiring

`ToolRegistry.__init__()` adds Gmail routing:

```python
if os.path.exists(GMAIL_CREDENTIALS_PATH):
    self._email = GmailDraftTool(GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH)
else:
    self._email = FakeEmailTool()

self._executors = {
    ActionType.CREATE_TASK: self._task_manager,
    ActionType.CREATE_CALENDAR_EVENT: self._calendar,
    ActionType.SEND_EMAIL: self._email,
}
```

Add:

```python
@property
def is_gmail_connected(self) -> bool:
    return not isinstance(self._email, FakeEmailTool)
```

Credential-file presence mirrors Calendar behavior. Actual token validity is checked lazily during execution.

---

## UI Updates

Add Gmail status near existing tool status indicators:

- Connected: `Gmail: Connected`
- Not configured: `Gmail: Not configured (using fake tool)`

When an approved `SEND_EMAIL` action executes, show:

- `Created Gmail draft`
- Draft ID if present
- Message ID if present
- Recipient/subject summary

No send button is added.

---

## Auth Script

`scripts/auth_gmail.py` mirrors `scripts/auth_google.py`:

```python
#!/usr/bin/env python3
from idea_to_action.tools.gmail_draft import GmailDraftTool

if __name__ == "__main__":
    GmailDraftTool.run_auth_flow()
```

User flow:

1. Enable Gmail API in Google Cloud.
2. Download OAuth client credentials to `credentials/gmail_credentials.json`.
3. Run `python3 scripts/auth_gmail.py`.
4. Approve Gmail compose scope in browser.
5. Token is saved to `credentials/gmail_token.json`.

---

## Tests

`tests/test_gmail_draft.py` covers:

1. Error hierarchy inheritance.
2. Init defaults and custom credential paths.
3. Missing token raises `GmailAuthError`.
4. Expired token refresh saves token.
5. Refresh failure raises `GmailAuthError`.
6. Pending/rejected actions are blocked.
7. Wrong action type raises `ValueError`.
8. Missing recipient raises `GmailDraftError`.
9. MIME message includes To, Cc, Bcc, Subject, and body.
10. MIME message is base64url encoded for Gmail API.
11. `execute()` calls `users().drafts().create(userId="me", body=...)`.
12. API errors wrap as `GmailDraftError`.
13. Fake email fallback is approval-gated and external-call-free.
14. Registry routes `SEND_EMAIL` to Gmail when configured.
15. Registry routes `SEND_EMAIL` to fake fallback when unconfigured.

Target: keep all existing tests passing and add focused F016 coverage.

---

## Verification

Run:

```bash
python3 -m pytest tests/test_gmail_draft.py tests/test_tool_draft_layer.py tests/test_ui.py
python3 -m pytest
python3 scripts/run_evals.py
```

If local environment API keys make unrelated tests environment-sensitive, document the failing tests and run targeted verification with relevant env vars unset.

---

## Future Work

A later feature can add end-to-end email extraction:

- `DraftEmail` schema
- Planner prompt updates
- Email-specific evals
- UI rendering for generated email drafts

That work is intentionally excluded from F016 to keep this integration small and safe.
