"""Tests for F005 - Idea organizer agent."""

from unittest import mock

import pytest

from idea_to_action.agent.organizer import OrganizerError, organize_ideas
from idea_to_action.schemas.ideas import (
    MissingContext,
    OrganizedIdea,
    OrganizedIdeaOutput,
)
from idea_to_action.schemas.input import InputType, RawIdeaInput


def make_mock_llm(return_value: OrganizedIdeaOutput):
    """Create a mock LLM that returns structured output directly."""

    class MockStructuredLLM:
        def invoke(self, messages):
            return return_value

    class MockLLM:
        def with_structured_output(self, schema, **kwargs):
            return MockStructuredLLM()

    return MockLLM()


class TestOrganizeIdeas:
    def test_organizes_simple_note(self) -> None:
        raw = RawIdeaInput(
            raw_text="Cần chuẩn bị slide cho presentation thứ 6. Gặp team lúc 2h.",
            input_type=InputType.NOTE,
        )
        expected = OrganizedIdeaOutput(
            cleaned_summary="Cần chuẩn bị slide presentation thứ 6 và họp team lúc 2h.",
            ideas=[
                OrganizedIdea(
                    original_text="Cần chuẩn bị slide cho presentation thứ 6",
                    cleaned_text="Chuẩn bị slide cho presentation thứ 6",
                    category="work",
                    is_actionable=True,
                    is_inferred=False,
                ),
                OrganizedIdea(
                    original_text="Gặp team lúc 2h",
                    cleaned_text="Họp team lúc 2h",
                    category="work",
                    is_actionable=True,
                    is_inferred=False,
                ),
            ],
            categories=["work"],
            actionable_items=[
                OrganizedIdea(
                    original_text="Cần chuẩn bị slide cho presentation thứ 6",
                    cleaned_text="Chuẩn bị slide cho presentation thứ 6",
                    category="work",
                    is_actionable=True,
                ),
                OrganizedIdea(
                    original_text="Gặp team lúc 2h",
                    cleaned_text="Họp team lúc 2h",
                    category="work",
                    is_actionable=True,
                ),
            ],
            vague_items=[],
            missing_context=[
                MissingContext(
                    question="Presentation thứ 6 lúc mấy giờ?",
                    related_to="Chuẩn bị slide cho presentation thứ 6",
                )
            ],
            confidence=0.9,
            inferred_fields=["confidence"],
        )

        llm = make_mock_llm(expected)
        result = organize_ideas(raw, llm)

        assert isinstance(result, OrganizedIdeaOutput)
        assert len(result.categories) == 1
        assert result.categories[0] == "work"
        assert len(result.ideas) == 2
        assert len(result.actionable_items) == 2
        assert len(result.vague_items) == 0
        assert len(result.missing_context) == 1

    def test_vague_ideas_not_forced_into_actions(self) -> None:
        """Vague items should not be marked as actionable."""
        raw = RawIdeaInput(raw_text="Maybe I should learn something new someday.")
        expected = OrganizedIdeaOutput(
            cleaned_summary="User is considering learning something new.",
            ideas=[
                OrganizedIdea(
                    original_text="Maybe I should learn something new someday.",
                    cleaned_text="Learn something new someday.",
                    category="learning",
                    is_actionable=False,
                    is_inferred=True,
                )
            ],
            categories=["learning"],
            actionable_items=[],
            vague_items=[
                OrganizedIdea(
                    original_text="Maybe I should learn something new someday.",
                    cleaned_text="Learn something new someday.",
                    category="learning",
                    is_actionable=False,
                    is_inferred=True,
                )
            ],
            missing_context=[
                MissingContext(
                    question="What specific topic or skill?",
                    related_to="Learn something new someday.",
                )
            ],
            confidence=0.4,
            inferred_fields=["confidence"],
        )

        llm = make_mock_llm(expected)
        result = organize_ideas(raw, llm)

        assert len(result.actionable_items) == 0
        assert len(result.vague_items) == 1
        assert result.vague_items[0].is_actionable is False

    def test_missing_context_reported(self) -> None:
        """Missing context should be reported for incomplete notes."""
        raw = RawIdeaInput(raw_text="Send the report.")
        expected = OrganizedIdeaOutput(
            cleaned_summary="Send the report.",
            ideas=[
                OrganizedIdea(
                    original_text="Send the report.",
                    cleaned_text="Send the report.",
                    category="work",
                    is_actionable=True,
                    is_inferred=False,
                )
            ],
            categories=["work"],
            actionable_items=[
                OrganizedIdea(
                    original_text="Send the report.",
                    cleaned_text="Send the report.",
                    category="work",
                    is_actionable=True,
                    is_inferred=False,
                )
            ],
            vague_items=[],
            missing_context=[
                MissingContext(
                    question="Which report? To whom?",
                    related_to="Send the report.",
                ),
                MissingContext(
                    question="Deadline?",
                    related_to="Send the report.",
                ),
            ],
            confidence=0.5,
            inferred_fields=["confidence"],
        )

        llm = make_mock_llm(expected)
        result = organize_ideas(raw, llm)

        assert len(result.missing_context) == 2

    def test_multiple_categories(self) -> None:
        """Input spanning multiple categories should produce multiple categories."""
        raw = RawIdeaInput(
            raw_text="Cần đi gym và gửi báo cáo cho sếp. Cũng cần mua sữa."
        )
        expected = OrganizedIdeaOutput(
            cleaned_summary="Cần đi gym, gửi báo cáo, và mua sữa.",
            ideas=[
                OrganizedIdea(
                    original_text="Cần đi gym",
                    cleaned_text="Đi gym",
                    category="health",
                    is_actionable=True,
                    is_inferred=False,
                ),
                OrganizedIdea(
                    original_text="gửi báo cáo cho sếp",
                    cleaned_text="Gửi báo cáo cho sếp",
                    category="work",
                    is_actionable=True,
                    is_inferred=False,
                ),
                OrganizedIdea(
                    original_text="Cần mua sữa",
                    cleaned_text="Mua sữa",
                    category="personal",
                    is_actionable=True,
                    is_inferred=False,
                ),
            ],
            categories=["health", "work", "personal"],
            actionable_items=[
                OrganizedIdea(
                    original_text="Cần đi gym",
                    cleaned_text="Đi gym",
                    category="health",
                    is_actionable=True,
                ),
                OrganizedIdea(
                    original_text="gửi báo cáo cho sếp",
                    cleaned_text="Gửi báo cáo cho sếp",
                    category="work",
                    is_actionable=True,
                ),
                OrganizedIdea(
                    original_text="Cần mua sữa",
                    cleaned_text="Mua sữa",
                    category="personal",
                    is_actionable=True,
                ),
            ],
            vague_items=[],
            missing_context=[],
            confidence=1.0,
            inferred_fields=["confidence"],
        )

        llm = make_mock_llm(expected)
        result = organize_ideas(raw, llm)

        assert len(result.categories) == 3
        assert set(result.categories) == {"health", "work", "personal"}

    def test_preserves_original_text(self) -> None:
        """Original user text must be preserved verbatim in output."""
        original_text = "gặp team lúc 2h để sync  lại   progress"
        raw = RawIdeaInput(raw_text=original_text)
        expected = OrganizedIdeaOutput(
            cleaned_summary="Họp team lúc 2h để sync progress.",
            ideas=[
                OrganizedIdea(
                    original_text=original_text,  # exactly preserved
                    cleaned_text="Họp team lúc 2h để sync progress",
                    category="work",
                    is_actionable=True,
                    is_inferred=False,
                )
            ],
            categories=["work"],
            actionable_items=[
                OrganizedIdea(
                    original_text=original_text,
                    cleaned_text="Họp team lúc 2h để sync progress",
                    category="work",
                    is_actionable=True,
                )
            ],
            vague_items=[],
            missing_context=[],
            confidence=0.95,
            inferred_fields=["confidence"],
        )

        llm = make_mock_llm(expected)
        result = organize_ideas(raw, llm)

        assert result.ideas[0].original_text == original_text

    def test_inferred_fields_listed(self) -> None:
        """inferred_fields must list what was inferred."""
        raw = RawIdeaInput(raw_text="A task")
        expected = OrganizedIdeaOutput(
            cleaned_summary="A task.",
            ideas=[
                OrganizedIdea(
                    original_text="A task",
                    cleaned_text="A task",
                    category="other",
                    is_actionable=True,
                    is_inferred=True,
                )
            ],
            categories=["other"],
            actionable_items=[
                OrganizedIdea(
                    original_text="A task",
                    cleaned_text="A task",
                    category="other",
                    is_actionable=True,
                    is_inferred=True,
                )
            ],
            vague_items=[],
            missing_context=[
                MissingContext(
                    question="What is the task about?",
                    related_to="A task",
                )
            ],
            confidence=0.2,
            inferred_fields=["confidence", "categories", "is_actionable"],
        )

        llm = make_mock_llm(expected)
        result = organize_ideas(raw, llm)

        assert "confidence" in result.inferred_fields
        assert "categories" in result.inferred_fields

    def test_llm_error_wrapped(self) -> None:
        """LLM failures should be wrapped in OrganizerError."""

        class FailingLLM:
            def with_structured_output(self, schema, **kwargs):
                raise RuntimeError("API connection failed")

        raw = RawIdeaInput(raw_text="Some text")

        with pytest.raises(OrganizerError, match="Failed to organize ideas"):
            organize_ideas(raw, FailingLLM())

    def test_empty_input_handled(self) -> None:
        """Empty input should fail at schema level before reaching LLM."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RawIdeaInput(raw_text="")


class TestOrganizerPromptTemplate:
    """Verify prompt templates are well-formed and include expected instructions."""

    def test_system_prompt_includes_key_rules(self) -> None:
        from idea_to_action.agent.prompts import ORGANIZER_SYSTEM_PROMPT

        assert "preserve" in ORGANIZER_SYSTEM_PROMPT.lower()
        assert "clean" in ORGANIZER_SYSTEM_PROMPT.lower()
        assert "category" in ORGANIZER_SYSTEM_PROMPT.lower()
        assert "actionable" in ORGANIZER_SYSTEM_PROMPT.lower()
        assert "is_inferred" in ORGANIZER_SYSTEM_PROMPT.lower()
        assert "missing context" in ORGANIZER_SYSTEM_PROMPT.lower()
        assert "never invent" in ORGANIZER_SYSTEM_PROMPT.lower()

    def test_user_template_contains_input_fields(self) -> None:
        from idea_to_action.agent.prompts import ORGANIZER_USER_TEMPLATE

        assert "{raw_text}" in ORGANIZER_USER_TEMPLATE
        assert "{input_type}" in ORGANIZER_USER_TEMPLATE
        assert "{source}" in ORGANIZER_USER_TEMPLATE
