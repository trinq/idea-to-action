"""Pipeline orchestration for idea-to-action.

Wires together the full flow:
  input validation → organize → plan → tool draft → trace

Each step is wrapped in try/except so the pipeline never throws —
it always returns a PipelineResult with errors populated for failed steps.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from idea_to_action.agent.llm_provider import LLMConfigError
from idea_to_action.agent.organizer import OrganizerError, organize_ideas
from idea_to_action.agent.planner import PlannerError, generate_plan
from idea_to_action.graph.nodes.tool_draft_generator import (
    ToolDraftError,
    generate_tool_actions,
)
from idea_to_action.schemas.ideas import OrganizedIdeaOutput
from idea_to_action.schemas.input import InputType, RawIdeaInput
from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tool_actions import ActionPlan
from idea_to_action.tracing.trace_logger import TraceLogger


@dataclass
class PipelineError:
    """An error that occurred during a pipeline step."""
    step: str
    message: str
    error_type: str


@dataclass
class PipelineResult:
    """Result of a pipeline run, including partial results if steps failed."""
    input: RawIdeaInput | None
    organized: OrganizedIdeaOutput | None
    plan: PlanResult | None
    tool_actions: ActionPlan | None
    errors: list[PipelineError]
    trace_id: str
    trace_file: Path | None
    started_at: str
    finished_at: str

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def run_pipeline(
    raw_text: str,
    llm,
    *,
    trace_id: str | None = None,
    trace_dir: str | None = None,
    input_type: InputType = InputType.OTHER,
    source: str = "api",
) -> PipelineResult:
    """Run the full idea-to-action pipeline.

    Args:
        raw_text: The raw user notes.
        llm: A langchain ChatOpenAI instance (or None if LLM is unavailable).
        trace_id: Optional trace ID. Auto-generated if not provided.
        trace_dir: Directory for trace files.
        input_type: Type hint for the input.
        source: Source label (e.g. "cli", "api").

    Returns:
        A PipelineResult with all completed steps and any errors.
        Never raises — errors are always captured in the result.
    """
    tid = trace_id or uuid.uuid4().hex[:12]
    started_at = datetime.now(UTC).isoformat()
    errors: list[PipelineError] = []

    tracer = TraceLogger(tid, base_dir=trace_dir)
    trace_file: Path | None = None

    raw_input: RawIdeaInput | None = None
    organized: OrganizedIdeaOutput | None = None
    plan: PlanResult | None = None
    tool_actions: ActionPlan | None = None

    try:
        # Step 1: Validate input
        try:
            raw_input = RawIdeaInput(
                raw_text=raw_text,
                input_type=input_type,
                source=source,
            )
        except ValidationError as e:
            errors.append(PipelineError(
                step="validation",
                message=str(e.errors(include_input=False)),
                error_type="validation_error",
            ))
            tracer.log("validation_error", {"raw_text": raw_text, "errors": str(e)})
            trace_file = tracer.close()
            return PipelineResult(
                input=None, organized=None, plan=None, tool_actions=None,
                errors=errors, trace_id=tid,
                trace_file=trace_file,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
            )

        tracer.log("input_received", {
            "raw_text": raw_text,
            "input_type": input_type.value,
            "source": source,
        })

        # Step 2: Organize ideas (LLM)
        try:
            organized = organize_ideas(raw_input, llm)
            tracer.log("organizer_output", _safe_dump(organized))
        except LLMConfigError as e:
            errors.append(PipelineError(
                step="organizer",
                message=str(e),
                error_type="llm_not_configured",
            ))
            tracer.log("organizer_error", {"message": str(e), "type": "llm_not_configured"})
        except OrganizerError as e:
            errors.append(PipelineError(
                step="organizer",
                message=str(e),
                error_type="organizer_error",
            ))
            tracer.log("organizer_error", {"message": str(e), "type": "organizer_error"})
        except Exception as e:
            errors.append(PipelineError(
                step="organizer",
                message=f"Unexpected error: {e}",
                error_type="organizer_error",
            ))
            tracer.log("organizer_error", {"message": str(e), "type": "unexpected"})

        # Step 3: Generate action plan (LLM) — only if organizer succeeded
        if organized is not None:
            try:
                plan = generate_plan(organized, llm)
                tracer.log("planner_output", _safe_dump(plan))
            except LLMConfigError as e:
                errors.append(PipelineError(
                    step="planner",
                    message=str(e),
                    error_type="llm_not_configured",
                ))
                tracer.log("planner_error", {"message": str(e), "type": "llm_not_configured"})
            except PlannerError as e:
                errors.append(PipelineError(
                    step="planner",
                    message=str(e),
                    error_type="planner_error",
                ))
                tracer.log("planner_error", {"message": str(e), "type": "planner_error"})
            except Exception as e:
                errors.append(PipelineError(
                    step="planner",
                    message=f"Unexpected error: {e}",
                    error_type="planner_error",
                ))
                tracer.log("planner_error", {"message": str(e), "type": "unexpected"})

        # Step 4: Generate tool actions (deterministic, no LLM)
        if plan is not None:
            try:
                tool_actions = generate_tool_actions(plan)
                tracer.log("tool_actions_drafted", _safe_dump(tool_actions))
            except (ToolDraftError, ValidationError) as e:
                errors.append(PipelineError(
                    step="tool_draft",
                    message=str(e),
                    error_type="tool_draft_error",
                ))
                tracer.log("tool_draft_error", {"message": str(e), "type": "tool_draft_error"})

        # Step 5: Final output
        tracer.log("final_output", {
            "total_errors": len(errors),
            "has_input": raw_input is not None,
            "has_organized": organized is not None,
            "has_plan": plan is not None,
            "has_tool_actions": tool_actions is not None,
            "total_actions": len(tool_actions.actions) if tool_actions else 0,
        })

    finally:
        trace_file = tracer.close()

    return PipelineResult(
        input=raw_input,
        organized=organized,
        plan=plan,
        tool_actions=tool_actions,
        errors=errors,
        trace_id=tid,
        trace_file=trace_file,
        started_at=started_at,
        finished_at=datetime.now(UTC).isoformat(),
    )


def _safe_dump(obj) -> dict:
    """Convert a Pydantic model to JSON-safe dict for trace logging."""
    try:
        return obj.model_dump(mode="json")
    except Exception:
        return {"__str__": str(obj)}
