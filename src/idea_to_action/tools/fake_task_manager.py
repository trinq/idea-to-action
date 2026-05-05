"""Fake task manager tool for MVP.

Drafts task actions without executing them.
All write actions require approval.
No external APIs are called.
"""

from datetime import UTC, datetime

from idea_to_action.schemas.tasks import DraftTask
from idea_to_action.schemas.tool_actions import (
    ActionType,
    ApprovalStatus,
    ToolAction,
)


class FakeTaskManagerTool:
    """Fake task manager that only drafts actions, never executes."""

    name = "fake_task_manager"

    def draft_create_task(self, task: DraftTask) -> ToolAction:
        """Create a draft tool action for creating a task.

        The action is NOT executed — it must go through the approval gate first.
        """
        return ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={
                "title": task.title,
                "description": task.description,
                "priority": task.priority.value,
                "effort": task.effort.value,
                "due_date": task.suggested_due_date.isoformat()
                if task.suggested_due_date
                else None,
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
        if action.action_type != ActionType.CREATE_TASK:
            raise ValueError(
                f"FakeTaskManagerTool cannot execute action type '{action.action_type.value}'"
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
            "note": "This is a fake tool. No external task was actually created.",
        }
