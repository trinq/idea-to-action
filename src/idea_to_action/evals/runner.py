"""Eval runner. Loads cases, runs them through the pipeline, reports pass/fail.

Uses mock LLM outputs for now. Designed to be swappable with real LLM later.
"""

import json
import sys
from pathlib import Path
from typing import Any

from idea_to_action.evals.scoring import (
    CheckResult,
    EvalReport,
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
from idea_to_action.schemas.ideas import OrganizedIdeaOutput
from idea_to_action.schemas.input import RawIdeaInput
from idea_to_action.schemas.plan import PlanResult
from idea_to_action.schemas.tool_actions import ActionPlan


DEFAULT_EVALS_PATH = Path(__file__).parent.parent.parent.parent / "evals" / "initial_cases.json"


def load_eval_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """Load eval cases from JSON file."""
    file_path = path or DEFAULT_EVALS_PATH
    if not file_path.exists():
        raise FileNotFoundError(f"Eval cases file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_organizer_checks(case: dict, output: dict) -> list[CheckResult]:
    """Run all organizer-level checks on output."""
    results: list[CheckResult] = []
    results.append(check_has_categories(output))
    results.append(check_no_empty_ideas(output))
    results.append(check_summary_not_empty(output))
    results.append(check_has_missing_context_field(output))
    results.append(check_confidence_in_range(output))
    results.append(check_actionable_items_not_vague(output))
    results.append(check_vague_items_not_actionable(output))
    results.append(check_inferred_fields_present(output))
    raw_text = case.get("input", {}).get("raw_text", "")
    results.append(check_original_text_preserved(raw_text, output))
    return results


def run_planner_checks(case: dict, plan: dict) -> list[CheckResult]:
    """Run planner-level checks on plan output."""
    results: list[CheckResult] = []
    tasks = plan.get("tasks", [])

    # Check task count if expected_task_count is specified
    expected_count = case.get("expected_task_count")
    if expected_count is not None:
        results.append(CheckResult(
            check_name="expected_task_count",
            passed=len(tasks) == expected_count,
            reason=f"Expected {expected_count} tasks, got {len(tasks)}",
        ))
    else:
        results.append(CheckResult(
            check_name="has_tasks",
            passed=len(tasks) > 0,
            reason=f"Found {len(tasks)} tasks" if tasks else "No tasks in plan",
        ))

    # Check no invented deadlines for cases without date evidence
    if not case.get("has_date_evidence", False):
        has_invented = any(t.get("suggested_due_date") is not None for t in tasks)
        results.append(CheckResult(
            check_name="no_invented_deadlines",
            passed=not has_invented,
            reason="No invented deadlines" if not has_invented else "Found invented deadline without evidence",
        ))
    return results


def run_tool_checks(case: dict, action_plan: dict) -> list[CheckResult]:
    """Run tool-level checks on action plan output."""
    results: list[CheckResult] = []
    actions = action_plan.get("actions", [])
    results.append(check_tool_actions_approval_required(actions))
    results.append(check_tool_actions_start_pending(actions))
    results.append(CheckResult(
        check_name="action_plan_has_summary",
        passed=len(action_plan.get("summary", "")) > 0,
        reason="Summary present" if action_plan.get("summary") else "Summary missing",
    ))
    return results


def run_single_eval(case: dict) -> EvalReport:
    """Run a single eval case through all checks and return a report."""
    report = EvalReport(
        eval_id=case["id"],
        area=case["area"],
        description=case["description"],
        passed=True,
    )

    # Run organizer checks on expected output
    if "expected_output" in case:
        report.checks.extend(run_organizer_checks(case, case["expected_output"]))

    # Run planner checks if expected plan exists
    if "expected_plan" in case:
        report.checks.extend(run_planner_checks(case, case["expected_plan"]))

    # Run tool checks if expected actions exist
    if "expected_actions" in case:
        report.checks.extend(run_tool_checks(case, case["expected_actions"]))

    # Overall pass/fail
    report.passed = all(c.passed for c in report.checks)
    return report


def run_all_evals(cases: list[dict] | None = None, path: Path | None = None) -> list[EvalReport]:
    """Run all eval cases and return reports."""
    if cases is None:
        cases = load_eval_cases(path)

    reports = []
    for case in cases:
        report = run_single_eval(case)
        reports.append(report)
    return reports


def print_report(reports: list[EvalReport], stream: Any = None) -> tuple[int, int]:
    """Print eval reports and return (passed_count, failed_count)."""
    out = stream or sys.stdout
    total = len(reports)
    passed = sum(1 for r in reports if r.passed)
    failed = total - passed

    for report in reports:
        status = "PASS" if report.passed else "FAIL"
        print(f"[{status}] {report.eval_id} — {report.description}", file=out)
        for check in report.checks:
            icon = "+" if check.passed else "x"
            print(f"  {icon} {check.check_name}: {check.reason}", file=out)

    print(f"\n---", file=out)
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}", file=out)

    return passed, failed
