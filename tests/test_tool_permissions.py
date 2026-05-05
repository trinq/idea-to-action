"""Tests for F003 - Tool action schema with approval enforcement."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from idea_to_action.schemas.tool_actions import (
    ActionPlan,
    ActionType,
    ApprovalStatus,
    ToolAction,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestToolAction:
    def test_valid_create_task_action(self) -> None:
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Buy milk", "priority": "high"},
            approval_required=True,
        )
        assert action.action_type == ActionType.CREATE_TASK
        assert action.approval_required is True
        assert action.approval_status == ApprovalStatus.PENDING

    def test_valid_create_calendar_action(self) -> None:
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={"title": "Meeting", "date": "2026-05-06"},
            approval_required=True,
        )
        assert action.action_type == ActionType.CREATE_CALENDAR_EVENT

    def test_valid_create_reminder_action(self) -> None:
        action = ToolAction(
            action_type=ActionType.CREATE_REMINDER,
            action_data={"title": "Call back", "trigger": "2pm"},
            approval_required=True,
        )
        assert action.action_type == ActionType.CREATE_REMINDER

    def test_write_action_without_approval_rejected(self) -> None:
        """Create task without approval_required must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ToolAction(
                action_type=ActionType.CREATE_TASK,
                action_data={"title": "Task"},
                approval_required=False,
            )
        assert "approval_required=True" in str(exc_info.value)

    def test_create_calendar_without_approval_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ToolAction(
                action_type=ActionType.CREATE_CALENDAR_EVENT,
                action_data={"title": "Event"},
                approval_required=False,
            )
        assert "approval_required=True" in str(exc_info.value)

    def test_create_reminder_without_approval_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ToolAction(
                action_type=ActionType.CREATE_REMINDER,
                action_data={"title": "Reminder"},
                approval_required=False,
            )
        assert "approval_required=True" in str(exc_info.value)

    def test_send_email_without_approval_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ToolAction(
                action_type=ActionType.SEND_EMAIL,
                action_data={"to": "test@test.com", "body": "Hello"},
                approval_required=False,
            )
        assert "approval_required=True" in str(exc_info.value)

    def test_send_message_without_approval_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ToolAction(
                action_type=ActionType.SEND_MESSAGE,
                action_data={"to": "someone", "body": "Hi"},
                approval_required=False,
            )
        assert "approval_required=True" in str(exc_info.value)

    def test_approval_status_transitions(self) -> None:
        """Actions start pending, can be approved or rejected."""
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Task"},
            approval_required=True,
        )
        assert action.approval_status == ApprovalStatus.PENDING

        approved = action.model_copy(
            update={"approval_status": ApprovalStatus.APPROVED}
        )
        assert approved.approval_status == ApprovalStatus.APPROVED

    def test_approved_at_requires_approved_status(self) -> None:
        """approved_at should only be set when status is approved."""
        from datetime import datetime

        with pytest.raises(ValidationError) as exc_info:
            ToolAction(
                action_type=ActionType.CREATE_TASK,
                action_data={"title": "Task"},
                approval_required=True,
                approval_status=ApprovalStatus.PENDING,
                approved_at=datetime.now(),
            )
        assert "approved_at" in str(exc_info.value)

    def test_draft_id_is_optional(self) -> None:
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Task"},
            approval_required=True,
        )
        assert action.draft_id is None

    def test_action_data_is_flexible(self) -> None:
        """action_data can hold arbitrary payloads for different action types."""
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={
                "title": "Meeting",
                "date": "2026-05-06",
                "time": "14:00",
                "location": "Room A",
                "attendees": ["alice", "bob"],
            },
            approval_required=True,
        )
        assert action.action_data["location"] == "Room A"
        assert len(action.action_data["attendees"]) == 2


class TestActionPlan:
    def test_valid_action_plan(self) -> None:
        actions = [
            ToolAction(
                action_type=ActionType.CREATE_TASK,
                action_data={"title": "Task 1"},
                approval_required=True,
            ),
            ToolAction(
                action_type=ActionType.CREATE_TASK,
                action_data={"title": "Task 2"},
                approval_required=True,
                approval_status=ApprovalStatus.REJECTED,
            ),
        ]
        plan = ActionPlan(
            actions=actions,
            summary="Two tasks from the idea.",
            pending_count=1,
            rejected_count=1,
        )
        assert len(plan.actions) == 2
        assert plan.pending_count == 1
        assert plan.rejected_count == 1

    def test_empty_actions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ActionPlan(actions=[], summary="Empty plan")

    def test_empty_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ActionPlan(
                actions=[
                    ToolAction(
                        action_type=ActionType.CREATE_TASK,
                        action_data={"title": "T"},
                        approval_required=True,
                    )
                ],
                summary="",
            )


class TestSampleFiles:
    def test_valid_action_plan_loads(self) -> None:
        data = json.loads((EXAMPLES_DIR / "valid_action_plan.json").read_text())
        actions = [ToolAction(**item) for item in data]
        assert len(actions) == 2
        assert all(a.approval_required for a in actions)
        assert all(a.approval_status == ApprovalStatus.PENDING for a in actions)

    def test_invalid_write_without_approval_rejected(self) -> None:
        data = json.loads(
            (EXAMPLES_DIR / "invalid_write_without_approval.json").read_text()
        )
        with pytest.raises(ValidationError):
            ToolAction(**data)
