"""Tool Draft Generator node.

Converts an action plan (PlanResult) into approval-gated ToolAction objects.
All write actions are draft-only — no external execution without approval.
"""

from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tool_actions import ActionPlan, ToolAction
from idea_to_action.tools.fake_calendar import FakeCalendarTool
from idea_to_action.tools.fake_task_manager import FakeTaskManagerTool


class ToolDraftError(Exception):
    """Error during tool draft generation."""


def generate_tool_actions(plan: PlanResult) -> ActionPlan:
    """Convert a PlanResult into an ActionPlan with approval-gated tool actions.

    Each task becomes a CREATE_TASK tool action.
    Each calendar event becomes a CREATE_CALENDAR_EVENT tool action.
    ALL write actions have approval_required=True and start as pending.

    No external tools are called — this is draft-only.
    """
    task_manager = FakeTaskManagerTool()
    calendar = FakeCalendarTool()
    actions: list[ToolAction] = []

    # Tasks → tool actions
    for task in plan.tasks:
        action = task_manager.draft_create_task(task)
        actions.append(action)

    # Calendar events → tool actions
    for event in plan.calendar_events:
        action = calendar.draft_create_event(event)
        actions.append(action)

    # Verify all write actions are approval_required
    for action in actions:
        if action.approval_required is not True:
            raise ToolDraftError(
                f"Action '{action.action_type.value}' must have approval_required=True. "
                f"Got approval_required={action.approval_required}."
            )

    return ActionPlan(
        actions=actions,
        summary=plan.summary,
        pending_count=len(actions),
        approved_count=0,
        rejected_count=0,
    )
