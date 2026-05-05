"""Organized idea output schema.

The output of the Idea Organizer node.
Separates user-provided facts from model-inferred fields.
"""

from pydantic import BaseModel, Field, field_validator


class OrganizedIdea(BaseModel):
    """A single idea extracted, cleaned, and categorized from raw input."""

    original_text: str = Field(
        ...,
        min_length=1,
        description="The user's original words, preserved verbatim.",
    )
    cleaned_text: str = Field(
        ...,
        min_length=1,
        description="Cleaned version of the idea, typos fixed, clarified.",
    )
    category: str = Field(
        ...,
        min_length=1,
        description="Assigned category (e.g. 'work', 'personal', 'health', 'learning').",
    )
    is_actionable: bool = Field(
        default=False,
        description="Whether this idea can be turned into a concrete action.",
    )
    is_inferred: bool = Field(
        default=False,
        description="True if the category or actionability was inferred, not explicitly stated by user.",
    )

    @field_validator("original_text")
    @classmethod
    def original_text_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("original_text must not be empty or whitespace-only")
        return v

    @field_validator("cleaned_text")
    @classmethod
    def cleaned_text_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("cleaned_text must not be empty or whitespace-only")
        return v


class MissingContext(BaseModel):
    """Information the user didn't provide that would improve planning."""

    question: str = Field(
        ...,
        min_length=1,
        description="A specific question for the user to clarify.",
    )
    related_to: str = Field(
        ...,
        min_length=1,
        description="Which idea or category this missing context relates to.",
    )


class OrganizedIdeaOutput(BaseModel):
    """Full output from the Idea Organizer.

    Separates user facts (original_text in each idea) from model inferences
    (categories, is_actionable when is_inferred=True, confidence, inferred_fields).
    """

    cleaned_summary: str = Field(
        ...,
        min_length=1,
        description="A cleaned overall summary of the raw input.",
    )
    ideas: list[OrganizedIdea] = Field(
        ...,
        min_length=1,
        description="All extracted ideas, each with original and cleaned text.",
    )
    categories: list[str] = Field(
        ...,
        min_length=1,
        description="Distinct categories assigned across all ideas. Must not be empty.",
    )
    actionable_items: list[OrganizedIdea] = Field(
        default_factory=list,
        description="Ideas marked as actionable.",
    )
    vague_items: list[OrganizedIdea] = Field(
        default_factory=list,
        description="Ideas that are too vague to act on directly.",
    )
    missing_context: list[MissingContext] = Field(
        default_factory=list,
        description="Missing information that would help planning. Can be empty but must be present.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence in the organization result. 1.0 = highest.",
    )
    inferred_fields: list[str] = Field(
        default_factory=list,
        description="Names of top-level fields that were inferred by the model, not directly stated by the user.",
    )

    @field_validator("categories")
    @classmethod
    def categories_must_not_be_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("categories must not be empty")
        return v
