"""Tests for F001 - Raw idea input schema."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from idea_to_action.schemas.input import InputType, RawIdeaInput

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestRawIdeaInput:
    """Schema validation tests for RawIdeaInput."""

    def test_valid_note_input(self) -> None:
        inp = RawIdeaInput(
            raw_text="Cần làm slide cho buổi presentation.",
            input_type=InputType.NOTE,
        )
        assert inp.raw_text == "Cần làm slide cho buổi presentation."
        assert inp.input_type == InputType.NOTE

    def test_valid_reminder_input(self) -> None:
        inp = RawIdeaInput(
            raw_text="Gọi điện cho khách hàng lúc 3h chiều.",
            input_type=InputType.REMINDER,
        )
        assert inp.input_type == InputType.REMINDER

    def test_valid_bullet_points_input(self) -> None:
        inp = RawIdeaInput(
            raw_text="- Mua sữa\n- Đổ xăng\n- Gọi bác sĩ",
            input_type=InputType.BULLET_POINTS,
        )
        assert inp.input_type == InputType.BULLET_POINTS

    def test_defaults_to_other(self) -> None:
        inp = RawIdeaInput(raw_text="Some random thought.")
        assert inp.input_type == InputType.OTHER

    def test_original_text_preserved(self) -> None:
        text = "  Gặp team lúc 2h  "
        inp = RawIdeaInput(raw_text=text)
        # Original text is preserved exactly, including surrounding whitespace
        assert inp.raw_text == text

    def test_empty_raw_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RawIdeaInput(raw_text="")

    def test_whitespace_only_raw_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RawIdeaInput(raw_text="   ")

    def test_source_is_optional(self) -> None:
        inp = RawIdeaInput(raw_text="A note without source.")
        assert inp.source is None

    def test_source_can_be_set(self) -> None:
        inp = RawIdeaInput(raw_text="Note from telegram.", source="telegram")
        assert inp.source == "telegram"

    def test_created_at_is_set_automatically(self) -> None:
        inp = RawIdeaInput(raw_text="Auto timestamp.")
        assert inp.created_at is not None


class TestValidSampleFile:
    """Ensure the valid sample JSON file passes schema validation."""

    def test_valid_sample_loads(self) -> None:
        path = EXAMPLES_DIR / "valid_raw_idea.json"
        data = json.loads(path.read_text())
        inp = RawIdeaInput(**data)
        assert inp.raw_text is not None
        assert len(inp.raw_text.strip()) > 0

    def test_valid_sample_has_expected_type(self) -> None:
        path = EXAMPLES_DIR / "valid_raw_idea.json"
        data = json.loads(path.read_text())
        inp = RawIdeaInput(**data)
        assert inp.input_type == InputType.NOTE


class TestInvalidSampleFile:
    """Ensure the invalid sample JSON file fails schema validation."""

    def test_invalid_sample_rejected(self) -> None:
        path = EXAMPLES_DIR / "invalid_empty_input.json"
        data = json.loads(path.read_text())
        with pytest.raises(ValidationError):
            RawIdeaInput(**data)


class TestImmutable:
    """RawIdeaInput is frozen to prevent accidental modification."""

    def test_frozen_model_cannot_be_mutated(self) -> None:
        inp = RawIdeaInput(raw_text="Original text.")
        with pytest.raises(ValidationError):
            inp.raw_text = "Modified text."
