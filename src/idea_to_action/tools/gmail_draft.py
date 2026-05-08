"""Gmail draft integration tool.

Creates Gmail drafts from approved draft actions.
Uses OAuth2 Web Flow for authentication.
"""

import base64
import os
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from google.auth.exceptions import GoogleAuthError as GAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from idea_to_action.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction
from idea_to_action.tracing.trace_logger import TraceLogger

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailIntegrationError(Exception):
    """Base error for Gmail integrations."""


class GmailAuthError(GmailIntegrationError):
    """Authentication error — user needs to run auth flow."""


class GmailDraftError(GmailIntegrationError):
    """Error from Gmail draft creation or message construction."""


class GmailDraftTool:
    """Real Gmail draft integration via OAuth2.

    Approval-gated: only creates drafts for approved SEND_EMAIL actions.
    This tool never calls Gmail send endpoints.
    """

    name = "gmail_draft"

    def __init__(self, credentials_path: str | None = None, token_path: str | None = None) -> None:
        self._credentials_path = credentials_path or GMAIL_CREDENTIALS_PATH
        self._token_path = token_path or GMAIL_TOKEN_PATH
        self._service = None

    def _get_credentials(self) -> Credentials:
        """Load credentials from token file, refreshing if needed."""
        if not os.path.exists(self._token_path):
            raise GmailAuthError(
                "Not authenticated. Run: python3 scripts/auth_gmail.py"
            )

        creds = Credentials.from_authorized_user_file(self._token_path, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds)
            except GAuthError as e:
                raise GmailAuthError(
                    "Token refresh failed. Re-authenticate: "
                    f"python3 scripts/auth_gmail.py\n{e}"
                ) from e

        if not creds or not creds.valid:
            raise GmailAuthError(
                "Not authenticated. Run: python3 scripts/auth_gmail.py"
            )

        return creds

    def _save_credentials(self, creds: Credentials) -> None:
        """Persist refreshed credentials back to token file."""
        os.makedirs(os.path.dirname(self._token_path), exist_ok=True)
        with open(self._token_path, "w") as f:
            f.write(creds.to_json())

    def _get_service(self):
        """Build and return an authenticated Gmail API service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    @staticmethod
    def run_auth_flow(credentials_path: str | None = None, token_path: str | None = None) -> None:
        """Run the browser-based OAuth flow and save the Gmail token."""
        creds_path = credentials_path or GMAIL_CREDENTIALS_PATH
        tok_path = token_path or GMAIL_TOKEN_PATH

        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Gmail client secret file not found at {creds_path}. "
                "Download it from Google Cloud Console."
            )

        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(tok_path), exist_ok=True)
        with open(tok_path, "w") as f:
            f.write(creds.to_json())

        print(f"Gmail authentication successful. Token saved to {tok_path}")

    def execute(self, action: ToolAction) -> dict[str, Any]:
        """Create a Gmail draft from an approved action.

        Raises:
            ValueError: Wrong action type.
            PermissionError: Action not approved.
            GmailAuthError: Not authenticated.
            GmailDraftError: API call failed or message data is invalid.
        """
        if action.action_type != ActionType.SEND_EMAIL:
            raise ValueError(
                f"GmailDraftTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                "Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        service = self._get_service()
        raw_message = self._build_mime_message(action.action_data)

        try:
            created = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw_message}})
                .execute()
            )
        except HttpError as e:
            raise GmailDraftError(f"Gmail Draft API error: {e}") from e

        result = {
            "status": "created",
            "gmail_draft_id": created.get("id"),
            "message_id": created.get("message", {}).get("id"),
        }

        tracer = TraceLogger(f"gmail-draft-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}")
        tracer.log(
            "gmail_draft_created",
            {
                "draft_id": result["gmail_draft_id"],
                "message_id": result["message_id"],
                "to": action.action_data.get("to"),
                "subject": action.action_data.get("subject", ""),
            },
        )
        tracer.close()

        return result

    def _build_mime_message(self, action_data: dict[str, Any]) -> str:
        """Build a base64url-encoded MIME message from action data."""
        recipients = action_data.get("to")
        if not recipients:
            raise GmailDraftError("Email draft requires at least one recipient")

        msg = EmailMessage()
        msg["To"] = self._join_recipients(recipients)
        if not msg["To"]:
            raise GmailDraftError("Email draft requires at least one recipient")

        cc = action_data.get("cc")
        if cc:
            msg["Cc"] = self._join_recipients(cc)

        bcc = action_data.get("bcc")
        if bcc:
            msg["Bcc"] = self._join_recipients(bcc)

        msg["Subject"] = action_data.get("subject", "") or ""
        msg.set_content(action_data.get("body", "") or "")

        return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    @staticmethod
    def _join_recipients(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        return ", ".join(str(item).strip() for item in value if str(item).strip())
