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
