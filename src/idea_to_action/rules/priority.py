"""Deterministic priority assignment rules.

Pure Python, no LLM. Rules are based on explicit evidence in the text.
Never invents urgency. Missing deadlines are reported as missing context.
"""

import re
from dataclasses import dataclass, field

from idea_to_action.schemas.ideas import OrganizedIdea
from idea_to_action.schemas.tasks import Priority


# Patterns indicating an explicit deadline (high priority)
EXPLICIT_DEADLINE_PATTERNS: list[str] = [
    # Vietnamese
    r"(thứ\s*[2-7]|thứ\s*hai|thứ\s*ba|thứ\s*tư|thứ\s*năm|thứ\s*sáu|thứ\s*bảy|chủ\s*nhật)",
    r"(ngày|hạn|deadline|hạn\s*chót)[:\s]+\d{1,2}[/-]\d{1,2}",
    r"\d{1,2}/\d{1,2}/\d{2,4}",
    r"ngày\s+\d{1,2}\s+tháng\s+\d{1,2}",
    # English
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(tomorrow|tonight|today)\b",
    r"\bby\s+\d{1,2}[/-]\d{1,2}\b",
    r"\bdue\s+(on|by|date)",
    r"\bdeadline\b",
    r"\b(asap|urgent|gấp|ngay|lập\s+tức)\b",
]

# Patterns indicating a vague/someday item (low priority)
SOMEDAY_PATTERNS: list[str] = [
    r"\b(someday|sometime|eventually|one\s+day|maybe|later|whenever)\b",
    r"\b(khi\s+nào|để\s+sau|lúc\s+nào\s+đó|sẽ\s+làm|tạm\s+thời)\b",
    r"\b(không\s+gấp|không\s+cần\s+gấp)\b",
    r"\b(có\s+thể|ý\s+tưởng|nghĩ\s+về)\b",
]

# Patterns for schedule-related words that suggest a need for context
SCHEDULE_UNCERTAINTY_PATTERNS: list[str] = [
    r"\b(khoảng|around|about|maybe|chắc|lúc\s+nào\s+đó)\b.*\d{1,2}",
    r"\d{1,2}.*\b(khoảng|around|maybe|ish)\b",
]


@dataclass
class PriorityResult:
    """Result of priority assignment."""

    priority: Priority
    is_inferred: bool
    missing_context: list[str] = field(default_factory=list)


def assign_priority(idea: OrganizedIdea) -> PriorityResult:
    """Assign priority to an organized idea based on evidence in the text.

    Rules (in priority order):
    1. Explicit deadline/urgency patterns → HIGH (not inferred)
    2. Vague/someday patterns → LOW (not inferred)
    3. Non-actionable items → LOW (not inferred)
    4. Default → MEDIUM (inferred)

    Returns PriorityResult with the assigned priority and whether it was inferred.
    Missing context is reported when a deadline is mentioned but unclear.
    """
    text = idea.cleaned_text.lower()
    original = idea.original_text.lower()

    combined = f"{text} {original}"

    # Rule 1: Explicit deadline → HIGH
    for pattern in EXPLICIT_DEADLINE_PATTERNS:
        if re.search(pattern, combined):
            missing = _check_schedule_uncertainty(combined)
            return PriorityResult(
                priority=Priority.HIGH,
                is_inferred=False,
                missing_context=missing,
            )

    # Rule 2: Vague/someday → LOW
    for pattern in SOMEDAY_PATTERNS:
        if re.search(pattern, combined):
            return PriorityResult(
                priority=Priority.LOW,
                is_inferred=False,
            )

    # Rule 3: Non-actionable → LOW
    if not idea.is_actionable:
        return PriorityResult(
            priority=Priority.LOW,
            is_inferred=False,
        )

    # Rule 4: Default → MEDIUM (inferred)
    return PriorityResult(
        priority=Priority.MEDIUM,
        is_inferred=True,
    )


def _check_schedule_uncertainty(text: str) -> list[str]:
    """Check if a deadline has uncertainty that should be flagged as missing context."""
    missing = []
    for pattern in SCHEDULE_UNCERTAINTY_PATTERNS:
        if re.search(pattern, text):
            missing.append("Exact deadline is uncertain — confirm with user.")
            break
    return missing
