"""Tests for F009 - Trace logging."""

import json
import tempfile
from pathlib import Path

import pytest

from idea_to_action.tracing.trace_logger import TraceLogger, _sanitize


@pytest.fixture
def tracer() -> TraceLogger:
    with tempfile.TemporaryDirectory() as tmp:
        yield TraceLogger(trace_id="test-run-001", base_dir=tmp)


class TestSanitize:
    def test_sensitive_key_redacted(self) -> None:
        result = _sanitize({"api_key": "sk-secret-value-123"})
        assert result["api_key"] == "[REDACTED]"

    def test_normal_keys_preserved(self) -> None:
        result = _sanitize({"raw_text": "Buy milk", "category": "personal"})
        assert result["raw_text"] == "Buy milk"
        assert result["category"] == "personal"

    def test_api_key_in_value_redacted(self) -> None:
        result = _sanitize({"config": "using api_key=sk-abcdef1234567890"})
        assert result["config"] == "[REDACTED]"

    def test_token_redacted(self) -> None:
        result = _sanitize({"token": "my-secret-token"})
        assert result["token"] == "[REDACTED]"

    def test_password_redacted(self) -> None:
        result = _sanitize({"password": "super-secret"})
        assert result["password"] == "[REDACTED]"

    def test_secret_redacted(self) -> None:
        result = _sanitize({"api_secret": "sssh"})
        assert result["api_secret"] == "[REDACTED]"

    def test_authorization_redacted(self) -> None:
        result = _sanitize({"Authorization": "Bearer xyz"})
        assert result["Authorization"] == "[REDACTED]"

    def test_nested_dict_sanitized(self) -> None:
        result = _sanitize({"llm_config": {"api_key": "sk-nested"}})
        assert result["llm_config"]["api_key"] == "[REDACTED]"

    def test_list_of_dicts_sanitized(self) -> None:
        result = _sanitize({
            "actions": [
                {"name": "ok", "api_key": "sk-1"},
                {"name": "also ok", "api_key": "sk-2"},
            ]
        })
        assert result["actions"][0]["api_key"] == "[REDACTED]"
        assert result["actions"][1]["api_key"] == "[REDACTED]"
        assert result["actions"][0]["name"] == "ok"

    def test_bearer_token_redacted(self) -> None:
        result = _sanitize({"header": "Bearer sk-abcdef1234567890abcdef"})
        assert result["header"] == "[REDACTED]"

    def test_normal_text_not_redacted(self) -> None:
        """Don't redact normal text that happens to contain 'key'."""
        result = _sanitize({"title": "Key results for Q1"})
        assert result["title"] == "Key results for Q1"


class TestTraceLogger:
    def test_log_step(self, tracer: TraceLogger) -> None:
        tracer.log("input_received", {"raw_text": "Buy milk"})
        assert tracer.step_count == 1
        entry = tracer.get_entries()[0]
        assert entry["trace_id"] == "test-run-001"
        assert entry["step"] == "input_received"
        assert entry["data"]["raw_text"] == "Buy milk"
        assert "timestamp" in entry

    def test_multiple_steps(self, tracer: TraceLogger) -> None:
        tracer.log("input_received", {"raw_text": "Task"})
        tracer.log("organizer_output", {"categories": ["work"]})
        tracer.log("planner_output", {"tasks": [{"title": "Task"}]})
        tracer.log("tool_actions_drafted", {"actions": [{"type": "create_task"}]})

        assert tracer.step_count == 4
        entries = tracer.get_entries()
        assert entries[0]["step"] == "input_received"
        assert entries[1]["step"] == "organizer_output"
        assert entries[2]["step"] == "planner_output"
        assert entries[3]["step"] == "tool_actions_drafted"

    def test_creates_trace_file(self, tracer: TraceLogger) -> None:
        tracer.log("input_received", {"raw_text": "Test"})
        path = tracer.close()

        assert path.exists()
        content = path.read_text().strip()
        assert "input_received" in content
        assert "Test" in content

    def test_trace_file_is_valid_jsonl(self, tracer: TraceLogger) -> None:
        tracer.log("step_1", {"data": "a"})
        tracer.log("step_2", {"data": "b"})
        path = tracer.close()

        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    assert "trace_id" in record
                    assert "step" in record
                    assert "timestamp" in record
                    assert "data" in record

    def test_api_key_not_in_trace_file(self, tracer: TraceLogger) -> None:
        tracer.log("config", {"api_key": "sk-secret-1234567890"})
        path = tracer.close()

        content = path.read_text()
        assert "sk-secret-1234567890" not in content
        assert "[REDACTED]" in content

    def test_step_ordering_preserved(self, tracer: TraceLogger) -> None:
        for i in range(10):
            tracer.log(f"step_{i}", {"index": i})
        path = tracer.close()

        entries = []
        with open(path) as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))

        assert len(entries) == 10
        for i, entry in enumerate(entries):
            assert entry["data"]["index"] == i

    def test_empty_trace_close(self, tracer: TraceLogger) -> None:
        """Closing with no entries should create empty file."""
        path = tracer.close()
        assert path.exists()
        assert path.read_text().strip() == ""

    def test_tool_action_decision_logged(self, tracer: TraceLogger) -> None:
        """Tool action approvals/rejections must be traceable."""
        tracer.log("approval_decision", {
            "action_type": "create_task",
            "decision": "approved",
            "action_data": {"title": "Task"},
        })
        assert tracer.step_count == 1
        entry = tracer.get_entries()[0]
        assert entry["data"]["decision"] == "approved"
        assert entry["data"]["action_type"] == "create_task"

    def test_error_logged(self, tracer: TraceLogger) -> None:
        tracer.log("error", {"message": "LLM connection failed", "code": "TIMEOUT"})
        entry = tracer.get_entries()[0]
        assert entry["data"]["message"] == "LLM connection failed"
        assert entry["data"]["code"] == "TIMEOUT"

    def test_final_output_logged(self, tracer: TraceLogger) -> None:
        tracer.log("final_output", {
            "summary": "Plan completed.",
            "pending_actions": 3,
            "approved_actions": 0,
        })
        entry = tracer.get_entries()[0]
        assert entry["data"]["pending_actions"] == 3


class TestFullPipelineTrace:
    def test_full_pipeline_trace(self, tracer: TraceLogger) -> None:
        """Simulate a full pipeline run and verify trace completeness."""
        tracer.log("input_received", {
            "raw_text": "Cần làm slide thứ 6.",
            "input_type": "note",
            "source": "cli",
        })
        tracer.log("organizer_output", {
            "categories": ["work"],
            "actionable_count": 1,
            "vague_count": 0,
        })
        tracer.log("planner_output", {
            "tasks": [{"title": "Làm slide", "priority": "high"}],
        })
        tracer.log("tool_actions_drafted", {
            "actions": [
                {"action_type": "create_task", "approval_required": True, "approval_status": "pending"}
            ],
        })
        tracer.log("final_output", {
            "total_actions": 1,
            "pending": 1,
            "approved": 0,
            "rejected": 0,
        })
        path = tracer.close()

        assert tracer.step_count == 5
        assert path.exists()

        # Read back and verify all steps
        with open(path) as f:
            steps = [json.loads(line)["step"] for line in f if line.strip()]

        assert steps == [
            "input_received",
            "organizer_output",
            "planner_output",
            "tool_actions_drafted",
            "final_output",
        ]
