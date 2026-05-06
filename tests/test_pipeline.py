"""Tests for F012 - Pipeline orchestration."""

import json
import tempfile

import pytest

from idea_to_action.agent.llm_provider import LLMConfigError
from idea_to_action.pipeline import PipelineError, PipelineResult, run_pipeline
from idea_to_action.schemas.ideas import (
    MissingContext,
    OrganizedIdea,
    OrganizedIdeaOutput,
)
from idea_to_action.schemas.input import InputType, RawIdeaInput
from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tasks import DraftTask, Priority, Effort


def make_mock_llm(organized_output, plan_output=None):
    """Create a multi-step mock LLM for pipeline tests.

    First call returns organized_output, second returns plan_output.
    If an output is callable, it's called to produce the value (for
    testing exceptions).
    """
    call_count = [0]

    class MockStructuredLLM:
        def invoke(self, messages):
            nonlocal organized_output, plan_output
            try:
                call_count[0] += 1
                if call_count[0] == 1:
                    # Organizer output
                    if callable(organized_output):
                        return organized_output()
                    return organized_output
                else:
                    # Planner output
                    if callable(plan_output):
                        return plan_output()
                    return plan_output
            except Exception as e:
                # Re-raise the same exception so error handling works
                raise type(e)(str(e)) from None

    class MockLLM:
        def with_structured_output(self, schema, **kwargs):
            return MockStructuredLLM()

    return MockLLM()


def _make_organized_output() -> OrganizedIdeaOutput:
    return OrganizedIdeaOutput(
        cleaned_summary="Buy milk.",
        ideas=[
            OrganizedIdea(
                original_text="Buy milk",
                cleaned_text="Buy milk",
                category="personal",
                is_actionable=True,
                is_inferred=False,
            ),
        ],
        categories=["personal"],
        actionable_items=[],
        vague_items=[],
        missing_context=[],
        confidence=0.9,
        inferred_fields=["confidence"],
    )


def _make_plan_result() -> PlanResult:
    return PlanResult(
        summary="Buy milk.",
        tasks=[
            DraftTask(
                title="Buy milk",
                description="Buy milk from the store",
                priority=Priority.MEDIUM,
                effort=Effort.SMALL,
                is_inferred=True,
            ),
        ],
        calendar_events=[],
        missing_context=[],
        is_inferred=True,
    )


class TestPipelineResult:
    def test_has_errors_false_when_no_errors(self):
        result = PipelineResult(
            input=None, organized=None, plan=None, tool_actions=None,
            errors=[], trace_id="t1", trace_file=None,
            started_at="", finished_at="",
        )
        assert result.has_errors is False

    def test_has_errors_true_when_errors_exist(self):
        result = PipelineResult(
            input=None, organized=None, plan=None, tool_actions=None,
            errors=[PipelineError(step="validation", message="bad", error_type="x")],
            trace_id="t1", trace_file=None,
            started_at="", finished_at="",
        )
        assert result.has_errors is True


class TestFullPipeline:
    def test_full_pipeline_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            assert result.input is not None
            assert result.input.raw_text == "Buy milk"
            assert result.organized is not None
            assert result.organized.cleaned_summary == "Buy milk."
            assert result.plan is not None
            assert len(result.plan.tasks) == 1
            assert result.plan.tasks[0].title == "Buy milk"
            assert result.tool_actions is not None
            assert len(result.tool_actions.actions) == 1
            assert len(result.errors) == 0
            assert result.has_errors is False
            assert result.trace_file is not None
            assert result.trace_file.exists()

    def test_pipeline_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output())
            result = run_pipeline(
                "", llm, trace_dir=tmp,
            )

            assert result.input is None
            assert result.organized is None
            assert result.plan is None
            assert result.tool_actions is None
            assert len(result.errors) == 1
            assert result.errors[0].step == "validation"
            assert result.errors[0].error_type == "validation_error"

    def test_pipeline_trace_written_on_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output())
            result = run_pipeline("", llm, trace_dir=tmp)

            assert result.trace_file is not None
            assert result.trace_file.exists()
            content = result.trace_file.read_text()
            assert "validation_error" in content

    def test_pipeline_organizer_error_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            def raise_error():
                raise Exception("LLM connection failed")

            llm = make_mock_llm(raise_error)
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            assert result.input is not None
            assert result.organized is None
            assert result.plan is None
            assert result.tool_actions is None
            assert len(result.errors) == 1
            assert result.errors[0].step == "organizer"
            assert result.errors[0].error_type == "organizer_error"

    def test_pipeline_planner_error_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            def raise_error():
                raise Exception("LLM timeout")

            llm = make_mock_llm(_make_organized_output(), raise_error)
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            assert result.input is not None
            assert result.organized is not None
            assert result.plan is None
            assert result.tool_actions is None
            assert len(result.errors) == 1
            assert result.errors[0].step == "planner"

    def test_pipeline_organizer_and_planner_both_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            def raise_error():
                raise Exception("fail")

            llm = make_mock_llm(raise_error, raise_error)
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            # Organizer fails first, so planner is never called
            assert result.organized is None
            assert result.plan is None
            assert len(result.errors) == 1
            assert result.errors[0].step == "organizer"

    def test_pipeline_trace_written_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            def raise_error():
                raise Exception("crash")

            llm = make_mock_llm(raise_error)
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            assert result.trace_file is not None
            assert result.trace_file.exists()
            content = result.trace_file.read_text()
            assert "organizer_error" in content
            assert "input_received" in content

    def test_pipeline_result_has_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            assert result.started_at
            assert result.finished_at
            assert result.started_at <= result.finished_at

    def test_pipeline_auto_generates_trace_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            assert result.trace_id
            assert len(result.trace_id) == 12  # uuid hex 12-char

    def test_pipeline_custom_trace_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_id="custom-001", trace_dir=tmp,
            )

            assert result.trace_id == "custom-001"

    def test_pipeline_trace_file_is_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            with open(result.trace_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        assert "trace_id" in record
                        assert "step" in record
                        assert "timestamp" in record
                        assert "data" in record

    def test_pipeline_full_trace_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )

            with open(result.trace_file) as f:
                steps = [json.loads(line)["step"] for line in f if line.strip()]

            assert "input_received" in steps
            assert "organizer_output" in steps
            assert "planner_output" in steps
            assert "tool_actions_drafted" in steps
            assert "final_output" in steps

    def test_pipeline_preserves_input_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Test note",
                llm,
                trace_dir=tmp,
                input_type=InputType.NOTE,
                source="cli",
            )

            assert result.input is not None
            assert result.input.input_type == InputType.NOTE
            assert result.input.source == "cli"

    def test_pipeline_api_key_not_in_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            llm = make_mock_llm(_make_organized_output(), _make_plan_result())
            result = run_pipeline(
                "Buy milk", llm, trace_dir=tmp,
            )
            content = result.trace_file.read_text()
            # TraceLogger._sanitize should already handle this,
            # but verify no raw secrets slip through
            assert "api_key" not in content.lower()
