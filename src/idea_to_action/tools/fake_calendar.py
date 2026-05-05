"""Fake calendar tool for MVP.

Drafts calendar event actions without executing them.
All write actions require approval.
No external APIs are called.
"""

from datetime import UTC, datetime

from idea_to_action.schemas.tasks import DraftCalendarEvent
from idea_to_action.schemas.tool_actions import (
    ActionType,
    ApprovalStatus,
    ToolAction,
)


class FakeCalendarTool:
    """Fake calendar that only drafts actions, never creates real events."""

    name = "fake_calendar"

    def draft_create_event(self, event: DraftCalendarEvent) -> ToolAction:
        """Create a draft tool action for a calendar event.

        The action is NOT executed — it must go through the approval gate first.
        """
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
        """FAKE execution — does NOT call any external API.

        Only logs what would have happened.
        Requires approval_status=APPROVED.
        """
        if action.action_type != ActionType.CREATE_CALENDAR_EVENT:
            raise ValueError(
                f"FakeCalendarTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        return {
            "status": "fake_executed",
            "action_type": action.action_type.value,
            "data": action.action_data,
            "note": "This is a fake tool. No external calendar event was actually created.",
        }
