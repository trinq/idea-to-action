"""Tests for F006 - Action plan generator."""

from datetime import datetime, time

import pytest

from idea_to_action.agent.planner import PlannerError, generate_plan
from idea_to_action.schemas.ideas import OrganizedIdea, OrganizedIdeaOutput
from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tasks import DraftCalendarEvent, DraftTask, Effort, Priority


def make_mock_llm(return_value):
    class MockStructuredLLM:
        def invoke(self, messages):
            return return_value

    class MockLLM:
        def with_structured_output(self, schema, **kwargs):
            return MockStructuredLLM()

    return MockLLM()


def make_organized_output(
    ideas: list[OrganizedIdea],
    actionable: list[OrganizedIdea] | None = None,
    vague: list[OrganizedIdea] | None = None,
) -> OrganizedIdeaOutput:
    categories = list({i.category for i in ideas})
    return OrganizedIdeaOutput(
        cleaned_summary="Test summary.",
        ideas=ideas,
        categories=categories,
        actionable_items=actionable or [i for i in ideas if i.is_actionable],
        vague_items=vague or [i for i in ideas if not i.is_actionable],
        missing_context=[],
        confidence=0.9,
        inferred_fields=["confidence"],
    )


class TestGeneratePlan:
    def test_generates_plan_from_actionable_ideas(self) -> None:
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Chuẩn bị slide presentation thứ 6",
                cleaned_text="Chuẩn bị slide presentation thứ 6",
                category="work",
                is_actionable=True,
            ),
            OrganizedIdea(
                original_text="Gặp team lúc 2h",
                cleaned_text="Họp team lúc 2h",
                category="work",
                is_actionable=True,
            ),
        ])

        expected = PlanResult(
            summary="Chuẩn bị presentation và họp team.",
            tasks=[
                DraftTask(
                    title="Chuẩn bị slide presentation",
                    priority=Priority.HIGH,
                    effort=Effort.LARGE,
                    suggested_due_date=datetime(2026, 5, 8, 18, 0),
                    is_inferred=True,
                ),
                DraftTask(
                    title="Họp sync team",
                    priority=Priority.MEDIUM,
                    effort=Effort.SMALL,
                    is_inferred=True,
                ),
            ],
            calendar_events=[
                DraftCalendarEvent(
                    title="Sync team",
                    suggested_date=datetime(2026, 5, 5),
                    suggested_time=time(14, 0),
                    duration_minutes=30,
                    is_inferred=False,
                )
            ],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(expected)
        result = generate_plan(organized, llm)

        assert isinstance(result, PlanResult)
        assert len(result.tasks) == 2
        assert result.tasks[0].title == "Chuẩn bị slide presentation"

    def test_skips_vague_items(self) -> None:
        """Only actionable items become tasks. Vague items are skipped."""
        organized = make_organized_output(
            ideas=[
                OrganizedIdea(
                    original_text="Send email",
                    cleaned_text="Send email",
                    category="work",
                    is_actionable=True,
                ),
                OrganizedIdea(
                    original_text="Someday learn guitar",
                    cleaned_text="Learn guitar someday",
                    category="learning",
                    is_actionable=False,
                ),
            ],
            actionable=[
                OrganizedIdea(
                    original_text="Send email",
                    cleaned_text="Send email",
                    category="work",
                    is_actionable=True,
                ),
            ],
            vague=[
                OrganizedIdea(
                    original_text="Someday learn guitar",
                    cleaned_text="Learn guitar someday",
                    category="learning",
                    is_actionable=False,
                ),
            ],
        )

        expected = PlanResult(
            summary="Send the email.",
            tasks=[
                DraftTask(
                    title="Send email",
                    priority=Priority.MEDIUM,
                    effort=Effort.SMALL,
                    is_inferred=True,
                )
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(expected)
        result = generate_plan(organized, llm)

        assert len(result.tasks) == 1

    def test_priorities_follow_evidence(self) -> None:
        """Tasks with deadlines should get higher priority."""
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Fix production bug ASAP",
                cleaned_text="Fix production bug urgently",
                category="work",
                is_actionable=True,
            ),
        ])

        expected = PlanResult(
            summary="Fix the production bug.",
            tasks=[
                DraftTask(
                    title="Fix production bug",
                    priority=Priority.HIGH,
                    effort=Effort.MEDIUM,
                    is_inferred=True,
                )
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(expected)
        result = generate_plan(organized, llm)

        assert result.tasks[0].priority == Priority.HIGH

    def test_invented_deadline_removed(self) -> None:
        """If the LLM invents a deadline without evidence, it should be removed."""
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Cập nhật documentation",
                cleaned_text="Cập nhật documentation",
                category="work",
                is_actionable=True,
            ),
        ])

        # LLM invents a deadline that wasn't in the original
        with_invented_deadline = PlanResult(
            summary="Cập nhật documentation.",
            tasks=[
                DraftTask(
                    title="Cập nhật documentation",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    suggested_due_date=datetime(2026, 5, 10),
                    is_inferred=True,
                )
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(with_invented_deadline)
        result = generate_plan(organized, llm)

        # The invented deadline should be stripped
        assert result.tasks[0].suggested_due_date is None

    def test_legitimate_deadline_preserved(self) -> None:
        """A deadline supported by original text evidence should be kept."""
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Nộp báo cáo trước thứ 6 tuần này",
                cleaned_text="Nộp báo cáo trước thứ 6",
                category="work",
                is_actionable=True,
            ),
        ])

        with_legit_deadline = PlanResult(
            summary="Nộp báo cáo trước thứ 6.",
            tasks=[
                DraftTask(
                    title="Nộp báo cáo",
                    priority=Priority.HIGH,
                    effort=Effort.MEDIUM,
                    suggested_due_date=datetime(2026, 5, 8, 18, 0),
                    is_inferred=False,
                )
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(with_legit_deadline)
        result = generate_plan(organized, llm)

        # "thứ" keyword is in original text, so deadline is preserved
        assert result.tasks[0].suggested_due_date is not None

    def test_no_calendar_events_without_evidence(self) -> None:
        """Calendar events without meeting evidence should not be created."""
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Mua sữa",
                cleaned_text="Mua sữa",
                category="personal",
                is_actionable=True,
            ),
        ])

        expected = PlanResult(
            summary="Mua sữa.",
            tasks=[
                DraftTask(
                    title="Mua sữa",
                    priority=Priority.MEDIUM,
                    effort=Effort.SMALL,
                    is_inferred=True,
                )
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(expected)
        result = generate_plan(organized, llm)

        assert len(result.calendar_events) == 0

    def test_missing_context_reported(self) -> None:
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Send the thing to that person",
                cleaned_text="Send something to someone",
                category="other",
                is_actionable=True,
                is_inferred=True,
            ),
        ])

        expected = PlanResult(
            summary="Send something to someone.",
            tasks=[
                DraftTask(
                    title="Send the thing",
                    priority=Priority.MEDIUM,
                    effort=Effort.SMALL,
                    is_inferred=True,
                )
            ],
            calendar_events=[],
            missing_context=[
                "What needs to be sent?",
                "Who is the recipient?",
            ],
            is_inferred=True,
        )

        llm = make_mock_llm(expected)
        result = generate_plan(organized, llm)

        assert len(result.missing_context) > 0

    def test_llm_error_wrapped(self) -> None:
        class FailingLLM:
            def with_structured_output(self, schema, **kwargs):
                raise RuntimeError("API timeout")

        organized = make_organized_output([
            OrganizedIdea(
                original_text="Task",
                cleaned_text="Task",
                category="work",
                is_actionable=True,
            ),
        ])

        with pytest.raises(PlannerError, match="Failed to generate action plan"):
            generate_plan(organized, FailingLLM())

    def test_plan_is_inferred_by_default(self) -> None:
        organized = make_organized_output([
            OrganizedIdea(
                original_text="Buy groceries",
                cleaned_text="Buy groceries",
                category="personal",
                is_actionable=True,
            ),
        ])

        expected = PlanResult(
            summary="Buy groceries.",
            tasks=[
                DraftTask(
                    title="Buy groceries",
                    priority=Priority.MEDIUM,
                    effort=Effort.SMALL,
                    is_inferred=True,
                )
            ],
            calendar_events=[],
            missing_context=[],
            is_inferred=True,
        )

        llm = make_mock_llm(expected)
        result = generate_plan(organized, llm)

        assert result.is_inferred is True


class TestPlannerPromptTemplate:
    def test_system_prompt_includes_rules(self) -> None:
        from idea_to_action.agent.prompts import PLANNER_SYSTEM_PROMPT

        assert "actionable" in PLANNER_SYSTEM_PROMPT.lower()
        assert "priority" in PLANNER_SYSTEM_PROMPT.lower()
        assert "deadline" in PLANNER_SYSTEM_PROMPT.lower()
        assert "never invent" in PLANNER_SYSTEM_PROMPT.lower()
        assert "concrete" in PLANNER_SYSTEM_PROMPT.lower()

    def test_user_template_includes_ideas(self) -> None:
        from idea_to_action.agent.prompts import PLANNER_USER_TEMPLATE

        assert "{ideas_json}" in PLANNER_USER_TEMPLATE
        assert "{categories}" in PLANNER_USER_TEMPLATE
        assert "{actionable_count}" in PLANNER_USER_TEMPLATE
