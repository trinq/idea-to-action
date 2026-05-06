"""Idea Organizer agent.

Converts raw user notes into organized, categorized ideas using an LLM
with structured output. This is a single-agent node — no multi-agent architecture.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from idea_to_action.agent.llm_provider import LLMConfigError
from idea_to_action.agent.prompts import ORGANIZER_SYSTEM_PROMPT, ORGANIZER_USER_TEMPLATE
from idea_to_action.schemas.ideas import OrganizedIdeaOutput
from idea_to_action.schemas.input import RawIdeaInput


class OrganizerError(Exception):
    """Error from the idea organizer agent."""


def organize_ideas(
    raw_input: RawIdeaInput,
    llm,
) -> OrganizedIdeaOutput:
    """Convert a raw idea input into organized, categorized output.

    Args:
        raw_input: The validated raw user input.
        llm: A langchain ChatOpenAI instance (or mock).

    Returns:
        An OrganizedIdeaOutput with cleaned summary, categorized ideas,
        actionable/vague classification, missing context, and confidence.

    Raises:
        OrganizerError: If the LLM call fails or returns invalid output.
    """
    messages = [
        SystemMessage(content=ORGANIZER_SYSTEM_PROMPT),
        HumanMessage(
            content=ORGANIZER_USER_TEMPLATE.format(
                input_type=raw_input.input_type.value,
                source=raw_input.source or "unknown",
                raw_text=raw_input.raw_text,
            )
        ),
    ]

    try:
        structured_llm = llm.with_structured_output(OrganizedIdeaOutput, method="json_mode")
        result = structured_llm.invoke(messages)
    except LLMConfigError:
        raise
    except Exception as e:
        raise OrganizerError(
            f"Failed to organize ideas: {e}"
        ) from e

    if not isinstance(result, OrganizedIdeaOutput):
        raise OrganizerError(
            f"LLM returned unexpected type: {type(result).__name__}. "
            f"Expected OrganizedIdeaOutput."
        )

    return result
