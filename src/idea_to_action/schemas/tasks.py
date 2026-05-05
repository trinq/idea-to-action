"""Task and calendar draft schemas.

Represents draft tasks, reminders, and calendar drafts extracted
from organized ideas. All dates and priorities are drafts until approved.
"""

from datetime import datetime, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Effort(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class DraftTask(BaseModel):
    """A draft task derived from an actionable idea."""

    title: str = Field(
        ...,
        min_length=1,
        description="Short, actionable task title.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional longer description.",
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Suggested priority.",
    )
    effort: Effort = Field(
        default=Effort.MEDIUM,
        description="Estimated effort.",
    )
    suggested_due_date: Optional[datetime] = Field(
        default=None,
        description="Suggested deadline, only if supported by user evidence.",
    )
    is_inferred: bool = Field(
        default=True,
        description="Whether priority, effort, or due date was inferred vs explicitly stated.",
    )
    source_idea_index: Optional[int] = Field(
        default=None,
        description="Index of the source idea in the organized output ideas list.",
    )


class DraftCalendarEvent(BaseModel):
    """A draft calendar event suggested from user input."""

    title: str = Field(
        ...,
        min_length=1,
        description="Calendar event title.",
    )
    suggested_date: Optional[datetime] = Field(
        default=None,
        description="Suggested date. None if not specified by user.",
    )
    suggested_time: Optional[time] = Field(
        default=None,
        description="Suggested start time. None if not specified.",
    )
    duration_minutes: int = Field(
        default=60,
        ge=1,
        description="Estimated duration in minutes. Defaults to 60.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Event description or agenda.",
    )
    is_inferred: bool = Field(
        default=True,
        description="Whether date/time/duration was inferred.",
    )
    missing_context: list[str] = Field(
        default_factory=list,
        description="What's still unknown (e.g. 'exact time not specified').",
    )


class DraftReminder(BaseModel):
    """A draft reminder to notify the user at a suggested time."""

    title: str = Field(
        ...,
        min_length=1,
        description="What to remind the user about.",
    )
    suggested_trigger: Optional[str] = Field(
        default=None,
        description="When to trigger (e.g. '3pm', 'tomorrow morning', 'next Monday').",
    )
    note: Optional[str] = Field(
        default=None,
        description="Additional reminder details.",
    )
    is_inferred: bool = Field(
        default=True,
        description="Whether the trigger time was inferred.",
    )
