"""Fake email tool for safe local execution.

Prepares fake results for approved SEND_EMAIL actions without calling Gmail.
"""

from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction


class FakeEmailTool:
    """Safe fake fallback for email draft execution."""

    name = "fake_email"

    def execute(self, action: ToolAction) -> dict:
        """Return a fake email draft result for an approved SEND_EMAIL action."""
        if action.action_type != ActionType.SEND_EMAIL:
            raise ValueError(
                f"FakeEmailTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        return {
            "status": "fake_created",
            "email_to": action.action_data.get("to"),
            "email_subject": action.action_data.get("subject"),
        }
