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
                mock_build.return_value = mock_service

                # Chain: service.events().insert().execute()
                events_resource = mock.MagicMock()
                mock_service.events.return_value = events_resource

                insert_request = mock.MagicMock()
                events_resource.insert.return_value = insert_request

                insert_request.execute.return_value = {
                    "id": "evt_abc123",
                    "htmlLink": "https://calendar.google.com/event?eid=abc123",
                    "summary": "Team Sync",
                }

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
