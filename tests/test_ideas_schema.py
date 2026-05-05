"""Tests for F002 - Organized idea output schema."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from idea_to_action.schemas.ideas import (
    MissingContext,
    OrganizedIdea,
    OrganizedIdeaOutput,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestOrganizedIdea:
    def test_valid_idea(self) -> None:
        idea = OrganizedIdea(
            original_text="Cần làm slide",
            cleaned_text="Làm slide",
            category="work",
            is_actionable=True,
        )
        assert idea.original_text == "Cần làm slide"
        assert idea.cleaned_text == "Làm slide"
        assert idea.category == "work"
        assert idea.is_actionable is True
        assert idea.is_inferred is False

    def test_default_is_inferred_false(self) -> None:
        idea = OrganizedIdea(
            original_text="A task",
            cleaned_text="A task",
            category="other",
        )
        assert idea.is_inferred is False

    def test_is_inferred_can_be_true(self) -> None:
        idea = OrganizedIdea(
            original_text="Something vague about health",
            cleaned_text="Something vague about health",
            category="health",
            is_actionable=False,
            is_inferred=True,
        )
        assert idea.is_inferred is True

    def test_empty_original_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdea(
                original_text="",
                cleaned_text="Valid",
                category="work",
            )

    def test_whitespace_original_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdea(
                original_text="   ",
                cleaned_text="Valid",
                category="work",
            )

    def test_empty_cleaned_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdea(
                original_text="Valid",
                cleaned_text="",
                category="work",
            )

    def test_empty_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdea(
                original_text="Valid",
                cleaned_text="Valid",
                category="",
            )


class TestMissingContext:
    def test_valid_missing_context(self) -> None:
        mc = MissingContext(
            question="Deadline là khi nào?",
            related_to="Làm slide presentation",
        )
        assert mc.question == "Deadline là khi nào?"

    def test_empty_question_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingContext(question="", related_to="Some idea")

    def test_empty_related_to_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingContext(question="A question?", related_to="")


class TestOrganizedIdeaOutput:
    def test_valid_output(self) -> None:
        idea = OrganizedIdea(
            original_text="Cần làm slide",
            cleaned_text="Làm slide",
            category="work",
            is_actionable=True,
        )
        output = OrganizedIdeaOutput(
            cleaned_summary="Cần làm slide cho presentation.",
            ideas=[idea],
            categories=["work"],
            actionable_items=[idea],
            vague_items=[],
            missing_context=[
                MissingContext(
                    question="Presentation ngày nào?",
                    related_to="Làm slide",
                )
            ],
            confidence=0.9,
            inferred_fields=["confidence"],
        )
        assert len(output.categories) == 1
        assert output.categories[0] == "work"
        assert output.confidence == 0.9
        assert "confidence" in output.inferred_fields

    def test_user_facts_separated_from_inferred(self) -> None:
        """User-provided facts (original_text, explicit categories) are
        separate from inferred fields (confidence, inferred categories)."""
        idea = OrganizedIdea(
            original_text="User explicitly said this",
            cleaned_text="User explicitly said this",
            category="work",
            is_actionable=True,
            is_inferred=False,
        )
        output = OrganizedIdeaOutput(
            cleaned_summary="User explicitly said this.",
            ideas=[idea],
            categories=["work"],
            actionable_items=[idea],
            vague_items=[],
            missing_context=[],
            confidence=0.8,
            inferred_fields=["confidence"],
        )
        # User facts: original_text, cleaned_text, category (is_inferred=False)
        assert output.ideas[0].is_inferred is False
        assert output.ideas[0].original_text == "User explicitly said this"
        # Inferred fields are explicitly listed
        assert "confidence" in output.inferred_fields
        # Categories come from ideas, not invented
        assert output.categories == ["work"]

    def test_missing_context_can_be_empty(self) -> None:
        """Missing context list must be present but can be empty."""
        idea = OrganizedIdea(
            original_text="Buy milk",
            cleaned_text="Buy milk",
            category="personal",
            is_actionable=True,
        )
        output = OrganizedIdeaOutput(
            cleaned_summary="Buy milk.",
            ideas=[idea],
            categories=["personal"],
            actionable_items=[idea],
            vague_items=[],
            missing_context=[],
        )
        assert output.missing_context == []

    def test_empty_categories_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdeaOutput(
                cleaned_summary="Summary.",
                ideas=[
                    OrganizedIdea(
                        original_text="Text",
                        cleaned_text="Text",
                        category="work",
                    )
                ],
                categories=[],
            )

    def test_empty_ideas_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdeaOutput(
                cleaned_summary="Summary.",
                ideas=[],
                categories=["work"],
            )

    def test_defaults(self) -> None:
        idea = OrganizedIdea(
            original_text="A thought",
            cleaned_text="A thought",
            category="other",
        )
        output = OrganizedIdeaOutput(
            cleaned_summary="A thought.",
            ideas=[idea],
            categories=["other"],
        )
        assert output.actionable_items == []
        assert output.vague_items == []
        assert output.missing_context == []
        assert output.confidence == 1.0
        assert output.inferred_fields == []

    def test_confidence_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdeaOutput(
                cleaned_summary="S",
                ideas=[
                    OrganizedIdea(
                        original_text="T",
                        cleaned_text="T",
                        category="w",
                    )
                ],
                categories=["w"],
                confidence=-0.1,
            )

    def test_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrganizedIdeaOutput(
                cleaned_summary="S",
                ideas=[
                    OrganizedIdea(
                        original_text="T",
                        cleaned_text="T",
                        category="w",
                    )
                ],
                categories=["w"],
                confidence=1.1,
            )

    def test_vague_items_tracked(self) -> None:
        vague = OrganizedIdea(
            original_text="Should probably do something about health",
            cleaned_text="Do something about health",
            category="health",
            is_actionable=False,
            is_inferred=True,
        )
        actionable = OrganizedIdea(
            original_text="Buy running shoes",
            cleaned_text="Buy running shoes",
            category="health",
            is_actionable=True,
        )
        output = OrganizedIdeaOutput(
            cleaned_summary="Health stuff.",
            ideas=[actionable, vague],
            categories=["health"],
            actionable_items=[actionable],
            vague_items=[vague],
        )
        assert len(output.vague_items) == 1
        assert output.vague_items[0].is_actionable is False
        assert output.vague_items[0].is_inferred is True


class TestValidSampleFile:
    def test_valid_sample_loads(self) -> None:
        path = EXAMPLES_DIR / "valid_organized_output.json"
        data = json.loads(path.read_text())
        output = OrganizedIdeaOutput(**data)
        assert len(output.categories) > 0
        assert len(output.ideas) > 0
        assert len(output.actionable_items) > 0
        assert isinstance(output.missing_context, list)
        assert "confidence" in output.inferred_fields

    def test_valid_sample_has_missing_context_field(self) -> None:
        path = EXAMPLES_DIR / "valid_organized_output.json"
        data = json.loads(path.read_text())
        output = OrganizedIdeaOutput(**data)
        # missing_context must be present (can have entries or be empty)
        assert hasattr(output, "missing_context")


class TestInvalidSampleFile:
    def test_invalid_no_categories_rejected(self) -> None:
        path = EXAMPLES_DIR / "invalid_no_categories.json"
        data = json.loads(path.read_text())
        with pytest.raises(ValidationError):
            OrganizedIdeaOutput(**data)
