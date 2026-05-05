"""Eval scoring functions.

Each check is a pure function that inspects pipeline output and returns
a pass/fail result with a reason. Checks are schema-based, not LLM-based,
so they can run without an API key.
"""

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    reason: str


@dataclass
class EvalReport:
    eval_id: str
    area: str
    description: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


def check_has_categories(output: dict) -> CheckResult:
    """Output must have at least one category."""
    cats = output.get("categories", [])
    passed = len(cats) > 0
    return CheckResult(
        check_name="has_categories",
        passed=passed,
        reason=f"Found {len(cats)} categories" if passed else "No categories found",
    )


def check_has_missing_context_field(output: dict) -> CheckResult:
    """Output must have the missing_context field (can be empty)."""
    has_field = "missing_context" in output
    value = output.get("missing_context", "FIELD_NOT_PRESENT")
    return CheckResult(
        check_name="has_missing_context_field",
        passed=has_field,
        reason="Field present" if has_field else "missing_context field missing",
    )


def check_actionable_items_not_vague(output: dict) -> CheckResult:
    """Actionable items should have is_actionable=True, not False."""
    actionable = output.get("actionable_items", [])
    for item in actionable:
        if not item.get("is_actionable", True):
            return CheckResult(
                check_name="actionable_items_not_vague",
                passed=False,
                reason=f"Found non-actionable item in actionable_items: {item.get('original_text', '')[:50]}",
            )
    return CheckResult(
        check_name="actionable_items_not_vague",
        passed=True,
        reason=f"All {len(actionable)} actionable items are marked actionable",
    )


def check_vague_items_not_actionable(output: dict) -> CheckResult:
    """Vague items should have is_actionable=False."""
    vague = output.get("vague_items", [])
    for item in vague:
        if item.get("is_actionable", False):
            return CheckResult(
                check_name="vague_items_not_actionable",
                passed=False,
                reason=f"Found actionable item in vague_items: {item.get('original_text', '')[:50]}",
            )
    return CheckResult(
        check_name="vague_items_not_actionable",
        passed=True,
        reason=f"All {len(vague)} vague items are not actionable",
    )


def check_original_text_preserved(input_raw_text: str, output: dict) -> CheckResult:
    """At least one idea's original_text must match the raw input."""
    ideas = output.get("ideas", [])
    for idea in ideas:
        if idea.get("original_text", "") in input_raw_text:
            return CheckResult(
                check_name="original_text_preserved",
                passed=True,
                reason="Original user text found in output ideas",
            )
    return CheckResult(
        check_name="original_text_preserved",
        passed=False,
        reason="Original user text not preserved in any idea",
    )


def check_confidence_in_range(output: dict) -> CheckResult:
    """Confidence must be between 0.0 and 1.0."""
    confidence = output.get("confidence", -1)
    passed = 0.0 <= confidence <= 1.0
    return CheckResult(
        check_name="confidence_in_range",
        passed=passed,
        reason=f"Confidence is {confidence}" if passed else f"Confidence {confidence} out of range",
    )


def check_tool_actions_approval_required(actions: list[dict]) -> CheckResult:
    """All tool actions must have approval_required=True."""
    for i, action in enumerate(actions):
        if not action.get("approval_required", False):
            return CheckResult(
                check_name="tool_actions_approval_required",
                passed=False,
                reason=f"Action {i} has approval_required=False",
            )
    return CheckResult(
        check_name="tool_actions_approval_required",
        passed=True,
        reason=f"All {len(actions)} actions have approval_required=True",
    )


def check_tool_actions_start_pending(actions: list[dict]) -> CheckResult:
    """All tool actions should start with approval_status=pending."""
    for i, action in enumerate(actions):
        if action.get("approval_status") != "pending":
            return CheckResult(
                check_name="tool_actions_start_pending",
                passed=False,
                reason=f"Action {i} has status '{action.get('approval_status')}' instead of 'pending'",
            )
    return CheckResult(
        check_name="tool_actions_start_pending",
        passed=True,
        reason=f"All {len(actions)} actions start as pending",
    )


def check_no_empty_ideas(output: dict) -> CheckResult:
    """Output must have at least one idea."""
    ideas = output.get("ideas", [])
    passed = len(ideas) > 0
    return CheckResult(
        check_name="no_empty_ideas",
        passed=passed,
        reason=f"Found {len(ideas)} ideas" if passed else "No ideas in output",
    )


def check_summary_not_empty(output: dict) -> CheckResult:
    """cleaned_summary must not be empty."""
    summary = output.get("cleaned_summary", "")
    passed = len(summary.strip()) > 0
    return CheckResult(
        check_name="summary_not_empty",
        passed=passed,
        reason="Summary present" if passed else "Summary is empty",
    )


def check_inferred_fields_present(output: dict) -> CheckResult:
    """inferred_fields must be present in output."""
    has_field = "inferred_fields" in output
    return CheckResult(
        check_name="inferred_fields_present",
        passed=has_field,
        reason="inferred_fields present" if has_field else "inferred_fields missing",
    )
