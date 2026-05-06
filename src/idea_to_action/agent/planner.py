"""Action Plan Generator agent.

Converts organized ideas into concrete, actionable plans using an LLM
with structured output. Priorities follow deterministic rules.
Deadlines are never invented.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from idea_to_action.agent.llm_provider import LLMConfigError
from idea_to_action.agent.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_TEMPLATE
from idea_to_action.schemas.ideas import OrganizedIdeaOutput
from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tasks import DraftCalendarEvent, DraftTask


class PlannerError(Exception):
    """Error from the action plan generator."""


def generate_plan(
    organized: OrganizedIdeaOutput,
    llm,
) -> PlanResult:
    """Generate an action plan from organized ideas.

    Args:
        organized: The organized idea output from the Idea Organizer.
        llm: A langchain ChatOpenAI instance (or mock).

    Returns:
        A PlanResult with concrete tasks, calendar events, and summary.

    Raises:
        PlannerError: If the LLM call fails or returns invalid output.
    """
    # Serialize ideas for the prompt
    ideas_json = json.dumps(
        [
            {
                "original_text": idea.original_text,
                "cleaned_text": idea.cleaned_text,
                "category": idea.category,
                "is_actionable": idea.is_actionable,
                "is_inferred": idea.is_inferred,
            }
            for idea in organized.ideas
        ],
        ensure_ascii=False,
        indent=2,
    )

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(
            content=PLANNER_USER_TEMPLATE.format(
                ideas_json=ideas_json,
                categories=", ".join(organized.categories),
                actionable_count=len(organized.actionable_items),
                vague_count=len(organized.vague_items),
            )
        ),
    ]

    try:
        structured_llm = llm.with_structured_output(PlanResult, method="json_mode")
        result = structured_llm.invoke(messages)
    except LLMConfigError:
        raise
    except Exception as e:
        raise PlannerError(
            f"Failed to generate action plan: {e}"
        ) from e

    if not isinstance(result, PlanResult):
        raise PlannerError(
            f"LLM returned unexpected type: {type(result).__name__}. "
            f"Expected PlanResult."
        )

    # Post-validate: ensure no invented deadlines on tasks without evidence
    result = _validate_no_invented_deadlines(result, organized)

    return result


def _validate_no_invented_deadlines(
    plan: PlanResult,
    organized: OrganizedIdeaOutput,
) -> PlanResult:
    """Remove suggested_due_date from tasks where no deadline
    was present in the original organized ideas."""
    # Collect all original text to check for date mentions
    all_text = " ".join(idea.original_text + " " + idea.cleaned_text for idea in organized.ideas).lower()

    cleaned_tasks = []
    for task in plan.tasks:
        if task.suggested_due_date is not None:
            # Only allow due date if the original input mentioned a date
            date_keywords = [
                "thứ", "monday", "tuesday", "wednesday", "thursday", "friday",
                "saturday", "sunday", "tomorrow", "ngày", "deadline", "due",
            ]
            has_date_evidence = any(kw in all_text for kw in date_keywords)
            if not has_date_evidence:
                # Remove invented deadline
                task = task.model_copy(update={"suggested_due_date": None})
        cleaned_tasks.append(task)

    return plan.model_copy(update={"tasks": cleaned_tasks})


def _validate_no_invented_meetings(
    plan: PlanResult,
    organized: OrganizedIdeaOutput,
) -> PlanResult:
    """Remove calendar events where no meeting/time evidence exists
    in the original organized ideas."""
    all_text = " ".join(idea.original_text + " " + idea.cleaned_text for idea in organized.ideas).lower()

    time_keywords = ["gặp", "họp", "meeting", "sync", "call", "gọi", "lúc", "vào lúc"]

    valid_events = []
    for event in plan.calendar_events:
        if event.suggested_date is not None or event.suggested_time is not None:
            has_time_evidence = any(kw in all_text for kw in time_keywords)
            if not has_time_evidence:
                # Remove invented event
                event = DraftCalendarEvent(
                    title=event.title,
                    description=event.description,
                    is_inferred=True,
                    missing_context=["No time or meeting evidence in original input."],
                )
        valid_events.append(event)

    return plan.model_copy(update={"calendar_events": valid_events})
