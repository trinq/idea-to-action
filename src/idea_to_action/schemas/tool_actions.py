"""Tool action schema with approval enforcement.

All write actions must carry an approval status.
No tool action can be executed without explicit approval.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class ActionType(str, Enum):
    CREATE_TASK = "create_task"
    CREATE_CALENDAR_EVENT = "create_calendar_event"
    CREATE_REMINDER = "create_reminder"
    SEND_EMAIL = "send_email"
    SEND_MESSAGE = "send_message"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ToolAction(BaseModel):
    """A single tool action that requires approval before execution.

    Write actions (create, send) MUST have approval_required=True.
    Read actions may set approval_required=False.
    """

    action_type: ActionType = Field(
        ...,
        description="Type of tool action.",
    )
    action_data: dict[str, Any] = Field(
        default_factory=dict,
        description="The payload for the action (task body, calendar fields, etc.).",
    )
    approval_required: bool = Field(
        default=True,
        description="Whether this action requires user approval. Write actions must be True.",
    )
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="Current approval state. Starts as pending.",
    )
    draft_id: Optional[str] = Field(
        default=None,
        description="Reference to the draft object this action was generated from.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this tool action was drafted (UTC).",
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        description="When the action was approved. None if still pending.",
    )
    approved_by: Optional[str] = Field(
        default=None,
        description="Who approved the action (e.g. 'user', 'admin').",
    )

    @model_validator(mode="after")
    def write_actions_must_require_approval(self) -> "ToolAction":
        """Write actions (create_*, send_*) MUST have approval_required=True."""
        write_actions = {
            ActionType.CREATE_TASK,
            ActionType.CREATE_CALENDAR_EVENT,
            ActionType.CREATE_REMINDER,
            ActionType.SEND_EMAIL,
            ActionType.SEND_MESSAGE,
        }
        if self.action_type in write_actions and not self.approval_required:
            raise ValueError(
                f"Write action '{self.action_type.value}' must have approval_required=True"
            )
        return self

    @model_validator(mode="after")
    def approved_at_only_when_approved(self) -> "ToolAction":
        """approved_at should only be set when status is approved."""
        if self.approved_at is not None and self.approval_status != ApprovalStatus.APPROVED:
            raise ValueError(
                "approved_at can only be set when approval_status is 'approved'"
            )
        return self


class ActionPlan(BaseModel):
    """A collection of tool actions generated from organized ideas."""

    actions: list[ToolAction] = Field(
        ...,
        min_length=1,
        description="Draft tool actions ready for approval.",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="Summary of the action plan.",
    )
    pending_count: int = Field(
        default=0,
        description="Number of actions still pending approval.",
    )
    approved_count: int = Field(
        default=0,
        description="Number of actions approved for execution.",
    )
    rejected_count: int = Field(
        default=0,
        description="Number of actions rejected by user.",
    )
