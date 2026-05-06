"""JSONL trace logger for debugging and auditing.

Records each pipeline step: input, organize, plan, draft_tools, approvals, errors.
Traces are written as JSONL files in the traces/ directory.
Secrets and API keys are automatically sanitized.
"""

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from idea_to_action.config import TRACES_DIR


class TraceLogger:
    """Records pipeline execution traces as JSONL.

    Usage:
        tracer = TraceLogger("run-001")
        tracer.log("input_received", {"raw_text": "..."})
        tracer.log("organizer_output", {"categories": ["work"]})
        tracer.log("error", {"message": "..."})
        tracer.close()  # writes the trace file
    """

    def __init__(
        self,
        trace_id: str,
        base_dir: Optional[str] = None,
    ) -> None:
        self.trace_id = trace_id
        self.base_dir = Path(base_dir or TRACES_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        self._started_at = datetime.now(UTC)

    def log(self, step: str, data: dict[str, Any]) -> None:
        """Record a pipeline step.

        Data is sanitized to remove secrets before writing.
        """
        entry = {
            "trace_id": self.trace_id,
            "step": step,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": _sanitize(data),
        }
        self._entries.append(entry)

    def close(self) -> Path:
        """Write all entries to the trace file and return the file path."""
        file_path = self.base_dir / f"{self.trace_id}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return file_path

    def get_entries(self) -> list[dict[str, Any]]:
        """Return in-memory entries (for testing)."""
        return list(self._entries)

    @property
    def step_count(self) -> int:
        return len(self._entries)


# Patterns for secret detection in trace data
_SECRET_KEY_PATTERNS: list[str] = [
    r"sk-[a-zA-Z0-9]{16,}",
    r"Bearer\s+[a-zA-Z0-9\-_\.]+",
    r"api_key",
    r"api[-_]?key",
    r"secret",
    r"password",
    r"token",
]

_SENSITIVE_KEYS: set[str] = {
    "api_key", "apikey", "api_secret", "secret", "password",
    "token", "access_token", "auth", "authorization", "credential",
}


def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
    """Remove or mask sensitive values from trace data.

    - Keys matching sensitive patterns are replaced with "[REDACTED]"
    - Values containing API key patterns are masked
    """
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        # Redact sensitive keys
        if key.lower() in _SENSITIVE_KEYS:
            sanitized[key] = "[REDACTED]"
            continue

        # Check string values for secret patterns
        if isinstance(value, str):
            for pattern in _SECRET_KEY_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    value = "[REDACTED]"
                    break
            sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = _sanitize(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            sanitized[key] = value
    return sanitized
