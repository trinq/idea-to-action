"""Tests for F003 - Task, calendar draft, and reminder schemas."""

import json
from datetime import datetime, time
from pathlib import Path

import pytest
from pydantic import ValidationError

from idea_to_action.schemas.tasks import (
    DraftCalendarEvent,
    DraftReminder,
    DraftTask,
    Effort,
    Priority,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestDraftTask:
    def test_valid_task(self) -> None:
        task = DraftTask(
            title="Chuẩn bị slide",
            description="Tạo slide deck.",
            priority=Priority.HIGH,
            effort=Effort.LARGE,
            is_inferred=False,
        )
        assert task.title == "Chuẩn bị slide"
        assert task.priority == Priority.HIGH
        assert task.effort == Effort.LARGE
        assert task.is_inferred is False

    def test_defaults(self) -> None:
        task = DraftTask(title="A task")
        assert task.priority == Priority.MEDIUM
        assert task.effort == Effort.MEDIUM
        assert task.is_inferred is True
        assert task.description is None
        assert task.suggested_due_date is None

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DraftTask(title="")

    def test_with_due_date(self) -> None:
        due = datetime(2026, 5, 8, 18, 0, 0)
        task = DraftTask(
            title="Task with deadline",
            suggested_due_date=due,
            is_inferred=False,
        )
        assert task.suggested_due_date == due

    def test_is_inferred_true_by_default(self) -> None:
        """Priority, effort, dates are inferred by default."""
        task = DraftTask(title="A task")
        assert task.is_inferred is True


class TestDraftCalendarEvent:
    def test_valid_calendar_event(self) -> None:
        event = DraftCalendarEvent(
            title="Team sync",
            suggested_date=datetime(2026, 5, 5),
            suggested_time=time(14, 0),
            duration_minutes=30,
        )
        assert event.title == "Team sync"
        assert event.suggested_time == time(14, 0)
        assert event.duration_minutes == 30

    def test_defaults(self) -> None:
        event = DraftCalendarEvent(title="Meeting")
        assert event.duration_minutes == 60
        assert event.is_inferred is True
        assert event.suggested_date is None
        assert event.suggested_time is None
        assert event.missing_context == []

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DraftCalendarEvent(title="")

    def test_missing_context_tracks_unknowns(self) -> None:
        event = DraftCalendarEvent(
            title="Meeting",
            missing_context=["exact time not specified", "location unknown"],
        )
        assert len(event.missing_context) == 2

    def test_duration_minimum_one_minute(self) -> None:
        with pytest.raises(ValidationError):
            DraftCalendarEvent(title="Meeting", duration_minutes=0)


class TestDraftReminder:
    def test_valid_reminder(self) -> None:
        reminder = DraftReminder(
            title="Gọi điện cho khách hàng",
            suggested_trigger="3pm",
            note="Xác nhận lại yêu cầu dự án",
        )
        assert reminder.title == "Gọi điện cho khách hàng"
        assert reminder.suggested_trigger == "3pm"

    def test_defaults(self) -> None:
        reminder = DraftReminder(title="A reminder")
        assert reminder.is_inferred is True
        assert reminder.suggested_trigger is None
        assert reminder.note is None

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DraftReminder(title="")


class TestSampleFiles:
    def test_valid_draft_task_loads(self) -> None:
        data = json.loads((EXAMPLES_DIR / "valid_draft_task.json").read_text())
        task = DraftTask(**data)
        assert task.priority == Priority.HIGH
        assert task.suggested_due_date is not None

    def test_valid_calendar_draft_loads(self) -> None:
        data = json.loads((EXAMPLES_DIR / "valid_calendar_draft.json").read_text())
        event = DraftCalendarEvent(**data)
        assert event.suggested_time is not None
        assert event.duration_minutes == 30
