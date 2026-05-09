# Using the Gmail Draft Integration (F016)

The Gmail integration creates Gmail drafts from approved email actions. It creates drafts only and never sends email automatically.

## Prerequisites

1. Enable the Gmail API in your Google Cloud project.
2. Create an OAuth client secret for an installed/desktop application.
3. Save the downloaded OAuth client JSON at the project root as `gmail_client_secret.json`, or set `I2A_GMAIL_CREDENTIALS` to the absolute path of that file.
4. Install the Google optional dependencies:

```bash
python3 -m pip install -e '.[google]'
```

## Authenticate Gmail

Run the browser-based OAuth flow:

```bash
python3 scripts/auth_gmail.py
```

The flow requests Gmail compose scope and saves the resulting token to `DATA_DIR/gmail_token.json` by default, where `DATA_DIR` is `I2A_DATA_DIR` or the project `data/` directory. To use a different token path, set `I2A_GMAIL_TOKEN` before running the auth script and before starting the app.

## Verify the Registry Connection

`ToolRegistry` uses the real Gmail draft tool when the Gmail client secret file exists at `gmail_client_secret.json` or `I2A_GMAIL_CREDENTIALS`.

```bash
python3 -c "
from idea_to_action.tools.registry import ToolRegistry
registry = ToolRegistry()
print('Gmail connected:', registry.is_gmail_connected)
"
```

Expected after credentials are configured: `Gmail connected: True`.

## Create a Draft from an Approved Action

Gmail draft execution is approval-gated. Use an approved `SEND_EMAIL` `ToolAction` and execute it through the registry:

```python
from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction
from idea_to_action.tools.registry import ToolRegistry

action = ToolAction(
    action_type=ActionType.SEND_EMAIL,
    action_data={
        "to": "recipient@example.com",
        "subject": "Follow-up from planning notes",
        "body": "Hi,\n\nHere is the follow-up we discussed.\n",
    },
    approval_required=True,
    approval_status=ApprovalStatus.APPROVED,
)

result = ToolRegistry().execute(action)
print(result["gmail_draft_id"])
```

The result identifies the created Gmail draft. Open Gmail Drafts to review, edit, or send it manually.

## Safety Guarantees

- The integration creates drafts only; it never sends messages.
- The Gmail OAuth scope is `https://www.googleapis.com/auth/gmail.compose`.
- The Gmail tool calls `users().drafts().create(...)` only.
- It does not call Gmail send endpoints such as `users().messages().send(...)` or `users().drafts().send(...)`.
- Unapproved `SEND_EMAIL` actions are rejected before any Gmail API call.

## Troubleshooting

| Problem | Likely cause | What to do |
|---|---|---|
| `ModuleNotFoundError: No module named 'google...'` | Google optional dependencies are not installed. | Run `python3 -m pip install -e '.[google]'`. |
| `Gmail client secret file not found` | No OAuth client JSON at the configured credentials path. | Save it as `gmail_client_secret.json` in the project root, or set `I2A_GMAIL_CREDENTIALS` to the file path. |
| Browser auth fails or reports API disabled | Gmail API is not enabled for the Google Cloud project. | Enable Gmail API, then run `python3 scripts/auth_gmail.py` again. |
| `Not authenticated. Run: python3 scripts/auth_gmail.py` | Token file is missing or invalid. | Run `python3 scripts/auth_gmail.py`; if using a custom path, ensure `I2A_GMAIL_TOKEN` is set consistently. |
| `Token refresh failed` | Saved token expired or was revoked. | Delete the token file and rerun `python3 scripts/auth_gmail.py`. |
| `Gmail connected: False` | The registry cannot see the Gmail credentials file. | Check `gmail_client_secret.json` location or `I2A_GMAIL_CREDENTIALS`; restart the Python process after changing environment variables. |
| `Cannot execute unapproved action` | The action was not approved. | Set `approval_status=ApprovalStatus.APPROVED` only after explicit user approval. |
| `Email draft requires at least one recipient` | The action data has no `to` recipient. | Add a non-empty `to` field before executing. |
| `Gmail API error: ...` | Gmail rejected the draft create request, or there is a network/quota issue. | Check the error details, network connectivity, Gmail API quota, and account permissions, then retry. |
