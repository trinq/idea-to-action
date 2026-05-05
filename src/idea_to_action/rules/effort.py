"""Deterministic effort estimation rules.

Pure Python, no LLM. Effort is estimated based on keywords in the idea text.
All estimates are inferred by default unless explicit effort is stated.
"""

import re
from dataclasses import dataclass

from idea_to_action.schemas.ideas import OrganizedIdea
from idea_to_action.schemas.tasks import Effort


# Indicators of small effort
SMALL_PATTERNS: list[str] = [
    r"\b(nhanh|quick|fast|simple|dễ|đơn\s*giản|small|minor)\b",
    r"\b(chỉ\s*cần|làm\s*nhanh|nhỏ|vài\s*phút)\b",
    r"\b\d{1,2}\s*(min|phút|minute)\b",
    r"\bjust\s+(do|send|call|check|ask|reply)\b",
    r"\b(send|reply|call|check)\s+(an?\s+)?(email|message|text)\b",
]

# Indicators of large effort
LARGE_PATTERNS: list[str] = [
    r"\b(lớn|big|large|complex|phức\s*tạp|major|huge|nhiều|dài)\b",
    r"\b(research|nghiên\s*cứu|investigate|phân\s*tích|analysis)\b",
    r"\b(build|create|develop|implement|xây\s*dựng|phát\s*triển|thiết\s*kế)\b",
    r"\b(many|several|multiple|nhiều|vài)\s+(hours|days|weeks|giờ|ngày|tuần)\b",
    r"\b(presentation|deck|report|báo\s*cáo|tài\s*liệu|slide|plan|kế\s*hoạch)\b",
]


@dataclass
class EffortResult:
    """Result of effort estimation."""

    effort: Effort
    is_inferred: bool


def estimate_effort(idea: OrganizedIdea) -> EffortResult:
    """Estimate effort for an organized idea based on keywords in the text.

    Rules:
    1. Small keywords → SMALL (inferred)
    2. Large keywords → LARGE (inferred)
    3. Default → MEDIUM (inferred)

    All estimates are inferred unless the user explicitly stated the effort level.
    """
    text = idea.cleaned_text.lower()
    original = idea.original_text.lower()
    combined = f"{text} {original}"

    # Rule 1: Small indicators → SMALL
    for pattern in SMALL_PATTERNS:
        if re.search(pattern, combined):
            return EffortResult(effort=Effort.SMALL, is_inferred=True)

    # Rule 2: Large indicators → LARGE
    for pattern in LARGE_PATTERNS:
        if re.search(pattern, combined):
            return EffortResult(effort=Effort.LARGE, is_inferred=True)

    # Rule 3: Default → MEDIUM
    return EffortResult(effort=Effort.MEDIUM, is_inferred=True)
