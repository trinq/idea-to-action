# Gmail Draft Integration — Setup & Usage Guide

The Gmail Draft Integration (F016) lets idea-to-action create **draft emails** in your Gmail account from approved `SEND_EMAIL` actions. Drafts appear in your Gmail Drafts folder — you review, edit, and send them yourself.

> **Safety invariant:** This integration creates Gmail drafts only. It **never** sends emails automatically.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step 1 — Enable the Gmail API in Google Cloud](#step-1--enable-the-gmail-api-in-google-cloud)
4. [Step 2 — Create OAuth 2.0 Credentials](#step-2--create-oauth-20-credentials)
5. [Step 3 — Install Dependencies](#step-3--install-dependencies)
6. [Step 4 — Authenticate with Gmail](#step-4--authenticate-with-gmail)
7. [Step 5 — Verify the Connection](#step-5--verify-the-connection)
8. [Environment Variables Reference](#environment-variables-reference)
9. [Usage — Via the UI](#usage--via-the-ui)
10. [Usage — Via Python](#usage--via-python)
11. [How Email Actions Map to Gmail Drafts](#how-email-actions-map-to-gmail-drafts)
12. [Architecture](#architecture)
13. [Safety Guarantees](#safety-guarantees)
14. [Troubleshooting](#troubleshooting)
15. [Without Gmail Configured](#without-gmail-configured)

---

## Overview

When the agent processes your notes and identifies an email-related action, it generates a `SEND_EMAIL` tool action containing the recipient, subject, and body. After you explicitly **approve** the action, the system creates a draft in your Gmail. You then open Gmail to review, edit, or send the draft at your discretion.

The integration uses Google's OAuth 2.0 flow with the narrowest possible scope (`gmail.compose`) and stores credentials locally on your machine.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Google account** | The Gmail account where drafts will be created |
| **Google Cloud project** | Free tier is sufficient — no billing required for the Gmail API |
| **Python** | 3.11 or later |
| **idea-to-action** | Installed with the `google` optional dependency group |

---

## Step 1 — Enable the Gmail API in Google Cloud

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Select an existing project or create a new one:
   - Click the project dropdown at the top → **New Project**.
   - Name it (e.g. `idea-to-action`) and click **Create**.
3. Navigate to **APIs & Services → Library** (or search for "Gmail API").
4. Search for **Gmail API** and click on it.
5. Click **Enable**.

> **Note:** If you already have a Google Cloud project with the Calendar API enabled (from the Google Calendar integration), you can reuse the same project. Just enable the Gmail API in addition to the Calendar API.

---

## Step 2 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials** in Google Cloud Console.
2. Click **+ CREATE CREDENTIALS → OAuth client ID**.
3. If prompted to configure the OAuth consent screen:
   - Choose **External** (or **Internal** if you have a Workspace org).
   - Fill in the required fields: App name (e.g. `idea-to-action`), user support email, and developer contact email.
   - On the **Scopes** step, no scopes need to be added here — they are requested at runtime.
   - On the **Test users** step, add your Gmail address.
   - Click **Save and Continue** through each step.
4. Back on the credentials page, click **+ CREATE CREDENTIALS → OAuth client ID**.
5. Select **Desktop app** as the application type.
6. Name it (e.g. `idea-to-action Gmail`).
7. Click **Create**.
8. Click **Download JSON** to download the client secret file.
9. Save the downloaded file as `gmail_client_secret.json` in the **project root directory** (same directory as `pyproject.toml`).

> **Important:** The file `gmail_client_secret.json` is already in `.gitignore`. Never commit this file to version control.

> **Tip:** If you already have a `client_secret.json` for the Calendar integration, the Gmail integration uses a **separate** credentials file (`gmail_client_secret.json`) because it requires a different OAuth scope. You can create both from the same Google Cloud project.

---

## Step 3 — Install Dependencies

The Gmail integration uses the same Google client libraries as the Calendar integration. Install the `google` optional dependency group:

```bash
python3 -m pip install -e '.[google]'
```

This installs:
- `google-auth-oauthlib>=1.0.0` — OAuth 2.0 flow
- `google-api-python-client>=2.0.0` — Gmail API client

If you already installed these for the Calendar integration, no additional packages are needed.

---

## Step 4 — Authenticate with Gmail

Run the one-time browser-based OAuth flow:

```bash
python3 scripts/auth_gmail.py
```

This will:
1. Open your default browser to Google's consent screen.
2. Ask you to sign in and grant the **"Compose, send and read email"** permission (this is the `gmail.compose` scope — despite the label, idea-to-action only creates drafts).
3. Save the resulting refresh token to `data/gmail_token.json`.

Expected output:

```
Gmail authentication successful. Token saved to /path/to/idea-to-action/data/gmail_token.json
```

> **Note:** If your app is in "Testing" mode on Google Cloud, only users listed as test users can complete the OAuth flow. You may see a "Google hasn't verified this app" warning — click **Continue** to proceed.

---

## Step 5 — Verify the Connection

Run this quick check to confirm the registry detects your Gmail credentials:

```bash
python3 -c "
from idea_to_action.tools.registry import ToolRegistry
registry = ToolRegistry()
print('Gmail connected:', registry.is_gmail_connected)
"
```

Expected output:

```
Gmail connected: True
```

If it shows `False`, check that `gmail_client_secret.json` exists in the project root (or that `I2A_GMAIL_CREDENTIALS` points to the correct file).

---

## Environment Variables Reference

All Gmail-related settings can be customized via environment variables. Default values work out of the box for most setups.

| Variable | Default | Description |
|---|---|---|
| `I2A_GMAIL_CREDENTIALS` | `<project_root>/gmail_client_secret.json` | Path to the OAuth client secret JSON file downloaded from Google Cloud |
| `I2A_GMAIL_TOKEN` | `<DATA_DIR>/gmail_token.json` | Path to the saved OAuth refresh token (created by `auth_gmail.py`) |
| `I2A_DATA_DIR` | `<project_root>/data/` | Base directory for data files including tokens |

### Example: Custom credential paths

```bash
export I2A_GMAIL_CREDENTIALS="/path/to/my-gmail-credentials.json"
export I2A_GMAIL_TOKEN="/path/to/my-gmail-token.json"
python3 scripts/auth_gmail.py
```

> **Important:** If you set custom paths for authentication, you must use the **same environment variables** when running the app, so the registry can find the credentials and token files.

---

## Usage — Via the UI

1. Start the Streamlit UI:

   ```bash
   streamlit run src/idea_to_action/ui/app.py
   ```

2. Paste notes that mention sending an email, for example:

   ```
   Need to email john@example.com about the project deadline extension.
   Subject should be "Project Deadline Update".
   ```

3. Click **Process**.

4. The **Draft Tool Actions** section shows:
   - **Gmail: Connected** (green status indicator) — confirms the real Gmail tool is active.
   - A `send_email` action with the extracted recipient, subject, and body.

5. Click **Approve** — a draft is created in your Gmail.

6. The UI displays:
   - `Gmail draft created: Project Deadline Update to john@example.com`
   - The Draft ID for reference.

7. Open Gmail → **Drafts** to review, edit, or send.

---

## Usage — Via Python

```python
from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction
from idea_to_action.tools.registry import ToolRegistry

action = ToolAction(
    action_type=ActionType.SEND_EMAIL,
    action_data={
        "to": "recipient@example.com",
        "subject": "Follow-up from planning notes",
        "body": "Hi,\n\nHere is the follow-up we discussed.\n\nBest regards",
        "cc": ["colleague@example.com"],       # optional
        "bcc": ["manager@example.com"],         # optional
    },
    approval_required=True,
    approval_status=ApprovalStatus.APPROVED,
)

result = ToolRegistry().execute(action)
print(result)
# {
#     "status": "created",
#     "gmail_draft_id": "r-123456789",
#     "gmail_message_id": "msg-987654321",
#     "email_subject": "Follow-up from planning notes",
#     "email_to": "recipient@example.com",
# }
```

---

## How Email Actions Map to Gmail Drafts

| `action_data` field | Gmail draft field | Required | Default |
|---|---|---|---|
| `to` | To recipient(s) | **Yes** | — |
| `subject` | Subject line | No | Empty string |
| `body` | Email body (plain text) | No | Empty string |
| `cc` | CC recipients (string or list) | No | Not included |
| `bcc` | BCC recipients (string or list) | No | Not included |

### Input validation

| Condition | Behavior |
|---|---|
| Missing or empty `to` | Raises `GmailDraftError` — draft is not created |
| Missing `subject` | Defaults to empty subject |
| Missing `body` | Defaults to empty body |
| Wrong action type (not `SEND_EMAIL`) | Raises `ValueError` |
| Unapproved action | Raises `PermissionError` — no API call is made |

---

## Architecture

```
┌─────────────────┐
│   User Notes    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Pipeline     │  Organizer → Planner → Tool Draft Generator
└────────┬────────┘
         │  Generates SEND_EMAIL ToolAction (pending)
         ▼
┌─────────────────┐
│  Approval Gate  │  User reviews and approves/rejects
└────────┬────────┘
         │  If approved
         ▼
┌─────────────────┐
│  ToolRegistry   │  Routes SEND_EMAIL → GmailDraftTool (or FakeEmailTool)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GmailDraftTool  │  Builds MIME message → Gmail API drafts.create()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Gmail Drafts   │  Draft appears in user's Gmail
└─────────────────┘
```

### Key components

| Component | File | Role |
|---|---|---|
| `GmailDraftTool` | `src/idea_to_action/tools/gmail_draft.py` | OAuth2 auth, MIME building, Gmail API draft creation |
| `FakeEmailTool` | `src/idea_to_action/tools/fake_email.py` | Safe fallback when Gmail is not configured |
| `ToolRegistry` | `src/idea_to_action/tools/registry.py` | Auto-detects credentials and routes to real or fake tool |
| `auth_gmail.py` | `scripts/auth_gmail.py` | One-time OAuth flow script |
| Config | `src/idea_to_action/config.py` | `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH` |

### Auto-detection logic

The `ToolRegistry` checks whether the Gmail client secret file exists at startup:

- **File exists** → Uses `GmailDraftTool` (real Gmail integration)
- **File missing** → Uses `FakeEmailTool` (returns `{"status": "fake_created", ...}`)

Token validity is checked **lazily** when `execute()` is called — not at startup.

---

## Safety Guarantees

| Guarantee | How it is enforced |
|---|---|
| **Drafts only, never sends** | Code only calls `users().drafts().create()`. No send endpoint (`messages().send()`, `drafts().send()`) is ever called. Tests verify this. |
| **Approval-gated** | `execute()` checks `approval_status == APPROVED` before any API call. Pending and rejected actions raise `PermissionError`. |
| **Narrowest scope** | OAuth scope is `gmail.compose` — the narrowest Gmail scope that supports draft creation. |
| **No secrets in logs** | Trace logging records draft ID, recipient, and subject but never logs email body, access tokens, refresh tokens, or credential file contents. |
| **Credentials not in repo** | `gmail_client_secret.json` and `gmail_token.json` are in `.gitignore`. |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'google...'` | Google dependencies not installed | Run `python3 -m pip install -e '.[google]'` |
| `Gmail client secret file not found` | No OAuth client JSON at expected path | Save it as `gmail_client_secret.json` in the project root, or set `I2A_GMAIL_CREDENTIALS` |
| Browser auth fails or reports "API not enabled" | Gmail API is not enabled in Google Cloud project | Enable Gmail API in Cloud Console → APIs & Services → Library |
| `Google hasn't verified this app` warning | App is in testing mode (normal for development) | Click **Continue** → **Continue** to proceed |
| `Not authenticated. Run: python3 scripts/auth_gmail.py` | Token file is missing or invalid | Run `python3 scripts/auth_gmail.py` |
| `Token refresh failed` | Saved token expired or was revoked | Delete the token file (`data/gmail_token.json`) and rerun `python3 scripts/auth_gmail.py` |
| `Gmail connected: False` | Registry cannot find the credentials file | Check `gmail_client_secret.json` location or `I2A_GMAIL_CREDENTIALS`; restart Python process after changing env vars |
| `Cannot execute unapproved action` | The action was not approved before execution | Set `approval_status=ApprovalStatus.APPROVED` only after user approval |
| `Email draft requires at least one recipient` | `to` field is missing or empty in action data | Add a non-empty `to` field |
| `Gmail API error: <HttpError 403 ...>` | Insufficient permissions or quota exceeded | Check Gmail API quota in Cloud Console; verify the OAuth scope was granted |
| `Gmail API error: <HttpError 429 ...>` | Rate limit exceeded | Wait a few seconds and retry |
| Auth flow hangs or fails to open browser | Running on a headless server | Copy the authorization URL and open it on a machine with a browser; paste the code back |

---

## Without Gmail Configured

If `gmail_client_secret.json` is not present and `I2A_GMAIL_CREDENTIALS` is not set, the system falls back to `FakeEmailTool`:

- The UI shows: **Gmail: Not configured (using fake tool)**
- Approved `SEND_EMAIL` actions return `{"status": "fake_created", ...}` — no real draft is created
- No external API calls are made
- All tests pass without Gmail credentials

This is the default behavior for local development and CI environments.
