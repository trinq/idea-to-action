"""Raw idea input schema.

Accepts rough notes, bullet points, reminders, meeting notes, and task dumps.
Preserves original user text and validates basic structure.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InputType(str, Enum):
    NOTE = "note"
    REMINDER = "reminder"
    MEETING_NOTES = "meeting_notes"
    TASK_DUMP = "task_dump"
    BULLET_POINTS = "bullet_points"
    OTHER = "other"


class RawIdeaInput(BaseModel):
    """A single raw idea input from the user.

    raw_text is the original user text and is always preserved.
    input_type helps the organizer node choose the right classification strategy.
    """

    raw_text: str = Field(
        ...,
        min_length=1,
        description="Original user text, preserved verbatim.",
    )
    input_type: InputType = Field(
        default=InputType.OTHER,
        description="Type hint for the raw input.",
    )
    source: Optional[str] = Field(
        default=None,
        description="Where this input came from (e.g. 'telegram', 'cli', 'voice').",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the input was received (UTC).",
    )

    @field_validator("raw_text")
    @classmethod
    def raw_text_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("raw_text must not be empty or whitespace-only")
        return v

    model_config = ConfigDict(frozen=True)
