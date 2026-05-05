"""Tests for F008 - Eval suite infrastructure."""

import json
from pathlib import Path
from unittest import mock

import pytest

from idea_to_action.evals.runner import (
    EvalReport,
    load_eval_cases,
    run_all_evals,
    run_organizer_checks,
    run_single_eval,
)
from idea_to_action.evals.scoring import (
    CheckResult,
    check_actionable_items_not_vague,
    check_confidence_in_range,
    check_has_categories,
    check_has_missing_context_field,
    check_inferred_fields_present,
    check_no_empty_ideas,
    check_original_text_preserved,
    check_summary_not_empty,
    check_tool_actions_approval_required,
    check_tool_actions_start_pending,
    check_vague_items_not_actionable,
)


class TestCheckFunctions:
    def test_has_categories_pass(self) -> None:
        result = check_has_categories({"categories": ["work", "personal"]})
        assert result.passed is True

    def test_has_categories_fail(self) -> None:
        result = check_has_categories({"categories": []})
        assert result.passed is False

    def test_confidence_in_range_pass(self) -> None:
        assert check_confidence_in_range({"confidence": 0.5}).passed is True
        assert check_confidence_in_range({"confidence": 0.0}).passed is True
        assert check_confidence_in_range({"confidence": 1.0}).passed is True

    def test_confidence_in_range_fail(self) -> None:
        assert check_confidence_in_range({"confidence": -0.1}).passed is False
        assert check_confidence_in_range({"confidence": 1.1}).passed is False

    def test_actionable_not_vague_pass(self) -> None:
        result = check_actionable_items_not_vague({
            "actionable_items": [
                {"original_text": "Task", "is_actionable": True}
            ]
        })
        assert result.passed is True

    def test_actionable_not_vague_fail(self) -> None:
        result = check_actionable_items_not_vague({
            "actionable_items": [
                {"original_text": "Vague", "is_actionable": False}
            ]
        })
        assert result.passed is False

    def test_vague_not_actionable_pass(self) -> None:
        result = check_vague_items_not_actionable({
            "vague_items": [
                {"original_text": "Someday", "is_actionable": False}
            ]
        })
        assert result.passed is True

    def test_vague_not_actionable_fail(self) -> None:
        result = check_vague_items_not_actionable({
            "vague_items": [
                {"original_text": "Task", "is_actionable": True}
            ]
        })
        assert result.passed is False

    def test_approval_required_all_true(self) -> None:
        result = check_tool_actions_approval_required([
            {"approval_required": True},
            {"approval_required": True},
        ])
        assert result.passed is True

    def test_approval_required_one_false(self) -> None:
        result = check_tool_actions_approval_required([
            {"approval_required": True},
            {"approval_required": False},
        ])
        assert result.passed is False

    def test_tool_actions_start_pending(self) -> None:
        result = check_tool_actions_start_pending([
            {"approval_status": "pending"},
            {"approval_status": "pending"},
        ])
        assert result.passed is True

    def test_tool_actions_one_approved(self) -> None:
        result = check_tool_actions_start_pending([
            {"approval_status": "pending"},
            {"approval_status": "approved"},
        ])
        assert result.passed is False

    def test_original_text_preserved(self) -> None:
        result = check_original_text_preserved(
            "Buy milk today",
            {"ideas": [{"original_text": "Buy milk today"}]},
        )
        assert result.passed is True

    def test_original_text_not_preserved(self) -> None:
        result = check_original_text_preserved(
            "Buy milk today",
            {"ideas": [{"original_text": "Something else entirely"}]},
        )
        assert result.passed is False

    def test_summary_not_empty(self) -> None:
        assert check_summary_not_empty({"cleaned_summary": "OK"}).passed is True
        assert check_summary_not_empty({"cleaned_summary": ""}).passed is False

    def test_has_missing_context_field(self) -> None:
        assert check_has_missing_context_field({"missing_context": []}).passed is True
        assert check_has_missing_context_field({}).passed is False

    def test_no_empty_ideas(self) -> None:
        idea = {"original_text": "A", "cleaned_text": "A", "category": "w"}
        assert check_no_empty_ideas({"ideas": [idea]}).passed is True
        assert check_no_empty_ideas({"ideas": []}).passed is False

    def test_inferred_fields_present(self) -> None:
        assert check_inferred_fields_present({"inferred_fields": []}).passed is True
        assert check_inferred_fields_present({}).passed is False


class TestEvalReport:
    def test_report_counts(self) -> None:
        report = EvalReport(
            eval_id="test-1",
            area="test",
            description="A test",
            passed=True,
            checks=[
                CheckResult("a", True, "ok"),
                CheckResult("b", False, "fail"),
                CheckResult("c", True, "ok"),
            ],
        )
        assert report.passed_count == 2
        assert report.failed_count == 1

    def test_report_passed_property(self) -> None:
        report = EvalReport(
            eval_id="test-1",
            area="test",
            description="Test",
            passed=True,
            checks=[CheckResult("a", False, "fail")],
        )
        assert report.passed is True  # Explicitly set
        # When computed from checks:
        report2 = run_single_eval({
            "id": "eval-001",
            "area": "idea_organization",
            "description": "Test",
            "input": {"raw_text": "Buy milk"},
            "expected_output": {
                "cleaned_summary": "OK",
                "ideas": [
                    {"original_text": "Buy milk", "cleaned_text": "Buy milk", "category": "personal", "is_actionable": True}
                ],
                "categories": ["personal"],
                "actionable_items": [],
                "vague_items": [],
                "missing_context": [],
                "confidence": 0.8,
                "inferred_fields": ["confidence"],
            },
        })
        assert report2.passed is True


class TestLoadEvalCases:
    def test_loads_default_cases(self) -> None:
        cases = load_eval_cases()
        assert len(cases) >= 12
        assert all("id" in c for c in cases)
        assert all("area" in c for c in cases)

    def test_loads_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_eval_cases(Path("/nonexistent/evals.json"))


class TestRunAllEvals:
    def test_all_default_evals_pass(self) -> None:
        """All built-in eval cases must pass."""
        reports = run_all_evals()
        assert len(reports) >= 12, f"Expected 12+ evals, got {len(reports)}"
        for report in reports:
            assert report.passed, (
                f"Eval '{report.eval_id}' failed: "
                f"{[c for c in report.checks if not c.passed]}"
            )

    def test_run_organizer_checks_basic(self) -> None:
        case = {
            "id": "test",
            "input": {"raw_text": "Buy milk"},
        }
        output = {
            "cleaned_summary": "Buy milk.",
            "ideas": [
                {"original_text": "Buy milk", "cleaned_text": "Buy milk", "category": "personal", "is_actionable": True}
            ],
            "categories": ["personal"],
            "actionable_items": [
                {"original_text": "Buy milk", "is_actionable": True}
            ],
            "vague_items": [],
            "missing_context": [],
            "confidence": 0.9,
            "inferred_fields": ["confidence"],
        }
        results = run_organizer_checks(case, output)
        assert all(r.passed for r in results), [r for r in results if not r.passed]


class TestEvalScript:
    def test_script_exists(self) -> None:
        path = Path(__file__).parent.parent / "scripts" / "run_evals.py"
        assert path.exists(), f"Script not found at {path}"

    def test_script_runnable(self) -> None:
        """The eval script should run and return 0."""
        import subprocess
        import sys

        script_path = Path(__file__).parent.parent / "scripts" / "run_evals.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Eval script failed with code {result.returncode}:\n{result.stdout}\n{result.stderr}"
        )
        assert "All evals passed" in result.stdout
