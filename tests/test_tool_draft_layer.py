"""Tests for F007 - Draft-only tool action layer."""

from datetime import UTC, datetime, time

import pytest

from idea_to_action.graph.nodes.tool_draft_generator import (
    ToolDraftError,
    generate_tool_actions,
)
from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tasks import (
    DraftCalendarEvent,
    DraftTask,
    Effort,
    Priority,
)
from idea_to_action.schemas.tool_actions import (
    ActionPlan,
    ActionType,
    ApprovalStatus,
    ToolAction,
)
from idea_to_action.tools.fake_calendar import FakeCalendarTool
from idea_to_action.tools.fake_task_manager import FakeTaskManagerTool
from idea_to_action.tools.registry import ToolRegistry


class TestFakeTaskManager:
    def test_draft_create_task_returns_pending_action(self) -> None:
        tool = FakeTaskManagerTool()
        task = DraftTask(
            title="Buy groceries",
            priority=Priority.MEDIUM,
            effort=Effort.SMALL,
            is_inferred=True,
        )
        action = tool.draft_create_task(task)

        assert isinstance(action, ToolAction)
        assert action.action_type == ActionType.CREATE_TASK
        assert action.approval_required is True
        assert action.approval_status == ApprovalStatus.PENDING
        assert action.action_data["title"] == "Buy groceries"
        assert action.action_data["priority"] == "medium"

    def test_draft_preserves_due_date(self) -> None:
        tool = FakeTaskManagerTool()
        due = datetime(2026, 5, 8, 18, 0, tzinfo=UTC)
        task = DraftTask(
            title="Submit report",
            suggested_due_date=due,
            priority=Priority.HIGH,
            effort=Effort.LARGE,
            is_inferred=False,
        )
        action = tool.draft_create_task(task)
        assert action.action_data["due_date"] is not None

    def test_execute_approved_task_succeeds(self) -> None:
        tool = FakeTaskManagerTool()
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Test task"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        result = tool.execute(action)
        assert result["status"] == "fake_executed"
        assert "no external task" in result["note"].lower()

    def test_execute_unapproved_task_blocked(self) -> None:
        tool = FakeTaskManagerTool()
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Test task"},
            approval_required=True,
            approval_status=ApprovalStatus.PENDING,
        )
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(action)

    def test_execute_wrong_action_type_rejected(self) -> None:
        tool = FakeTaskManagerTool()
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={"title": "Event"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        with pytest.raises(ValueError, match="cannot execute"):
            tool.execute(action)


class TestFakeCalendar:
    def test_draft_create_event_returns_pending_action(self) -> None:
        tool = FakeCalendarTool()
        event = DraftCalendarEvent(
            title="Team sync",
            suggested_date=datetime(2026, 5, 5),
            suggested_time=time(14, 0),
            duration_minutes=30,
        )
        action = tool.draft_create_event(event)

        assert action.action_type == ActionType.CREATE_CALENDAR_EVENT
        assert action.approval_required is True
        assert action.approval_status == ApprovalStatus.PENDING
        assert action.action_data["title"] == "Team sync"

    def test_execute_approved_event_succeeds(self) -> None:
        tool = FakeCalendarTool()
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={"title": "Meeting"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        result = tool.execute(action)
        assert result["status"] == "fake_executed"

    def test_execute_unapproved_event_blocked(self) -> None:
        tool = FakeCalendarTool()
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={"title": "Meeting"},
            approval_required=True,
            approval_status=ApprovalStatus.REJECTED,
        )
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(action)


class TestToolRegistry:
    def test_registry_routes_correctly(self) -> None:
        registry = ToolRegistry()
        action = ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={"title": "Task"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        result = registry.execute(action)
        assert result["status"] == "fake_executed"

    def test_registry_routes_send_email_to_fake_email(self) -> None:
        registry = ToolRegistry()
        action = ToolAction(
            action_type=ActionType.SEND_EMAIL,
            action_data={"to": "test@test.com", "subject": "Hello"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )

        result = registry.execute(action)

        assert result["status"] == "fake_created"
        assert result["email_to"] == "test@test.com"


class TestToolDraftGenerator:
    def test_generates_actions_from_plan(self) -> None:
        plan = PlanResult(
            summary="Two tasks and a meeting.",
            tasks=[
                DraftTask(
                    title="Task A",
                    priority=Priority.HIGH,
                    effort=Effort.SMALL,
                    is_inferred=True,
                ),
                DraftTask(
                    title="Task B",
                    priority=Priority.MEDIUM,
                    effort=Effort.LARGE,
                    is_inferred=True,
                ),
            ],
            calendar_events=[
                DraftCalendarEvent(
                    title="Meeting X",
                    suggested_date=datetime(2026, 5, 6),
                    suggested_time=time(10, 0),
                )
            ],
            missing_context=[],
            is_inferred=True,
        )

        action_plan = generate_tool_actions(plan)

        assert isinstance(action_plan, ActionPlan)
        assert len(action_plan.actions) == 3  # 2 tasks + 1 calendar
        assert action_plan.pending_count == 3
        assert action_plan.approved_count == 0

    def test_all_actions_approval_required(self) -> None:
        plan = PlanResult(
            summary="One task.",
            tasks=[
                DraftTask(
                    title="Task",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    is_inferred=True,
                ),
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        action_plan = generate_tool_actions(plan)

        for action in action_plan.actions:
            assert action.approval_required is True, (
                f"Action '{action.action_type.value}' has approval_required=False"
            )

    def test_all_actions_start_pending(self) -> None:
        plan = PlanResult(
            summary="One task.",
            tasks=[
                DraftTask(
                    title="Task",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    is_inferred=True,
                ),
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        action_plan = generate_tool_actions(plan)

        for action in action_plan.actions:
            assert action.approval_status == ApprovalStatus.PENDING

    def test_empty_plan_raises(self) -> None:
        """A plan with no tasks or events should raise (ActionPlan requires actions)."""
        from pydantic import ValidationError

        plan = PlanResult(
            summary="Nothing to do.",
            tasks=[],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        with pytest.raises(ValidationError):
            generate_tool_actions(plan)

    def test_task_action_has_task_type(self) -> None:
        plan = PlanResult(
            summary="One task.",
            tasks=[
                DraftTask(
                    title="Buy milk",
                    priority=Priority.MEDIUM,
                    effort=Effort.SMALL,
                    is_inferred=True,
                ),
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        action_plan = generate_tool_actions(plan)

        task_actions = [
            a for a in action_plan.actions
            if a.action_type == ActionType.CREATE_TASK
        ]
        assert len(task_actions) == 1

    def test_calendar_action_has_event_type(self) -> None:
        plan = PlanResult(
            summary="One meeting.",
            tasks=[],
            calendar_events=[
                DraftCalendarEvent(
                    title="Sync",
                    suggested_date=datetime(2026, 5, 5),
                    suggested_time=time(14, 0),
                )
            ],
            missing_context=[],
            is_inferred=True,
        )

        action_plan = generate_tool_actions(plan)

        event_actions = [
            a for a in action_plan.actions
            if a.action_type == ActionType.CREATE_CALENDAR_EVENT
        ]
        assert len(event_actions) == 1
