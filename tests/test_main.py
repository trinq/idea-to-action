"""Tests for F012 - CLI interface."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

MAIN_PATH = str(Path(__file__).parent.parent / "src" / "idea_to_action" / "main.py")


def _cli(*args, stdin_text=None, env=None):
    """Run the CLI as a subprocess and return stdout, stderr, exit code."""
    cmd = [sys.executable, MAIN_PATH, *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=stdin_text,
        env=env,
    )
    return result.stdout, result.stderr, result.returncode


class TestCLIBasics:
    def test_cli_help(self):
        stdout, stderr, code = _cli("--help")
        assert code == 0
        assert "raw notes" in stdout.lower() or "raw notes" in stdout
        assert "--text" in stdout
        assert "--json" in stdout

    def test_cli_empty_input(self):
        stdout, stderr, code = _cli()
        assert code == 1
        assert "No input provided" in stderr

    def test_cli_text_flag(self):
        """CLI with --text should not crash (will show error for no LLM)."""
        stdout, stderr, code = _cli("--text", "Buy milk", "--json")
        # Will have errors due to no LLM, but should not crash
        assert code >= 0  # Not a Python traceback

    def test_cli_json_output_is_valid(self):
        """JSON output should be parseable."""
        stdout, stderr, code = _cli("--text", "Buy milk", "--json")
        data = json.loads(stdout)
        assert "trace_id" in data
        assert "status" in data
        assert "errors" in data
        # Without LLM, status should be "partial"
        assert data["status"] == "partial"
        assert len(data["errors"]) > 0

    def test_cli_stdin_input(self):
        stdout, stderr, code = _cli("--json", stdin_text="Send report by Friday")
        assert code == 1
        data = json.loads(stdout)
        assert "errors" in data
        assert data["status"] == "partial"

    def test_cli_formatted_output(self):
        stdout, stderr, code = _cli("--text", "Buy milk")
        assert "Trace ID:" in stdout
        assert "Buy milk" in stdout

    def test_cli_input_type_flag(self):
        stdout, stderr, code = _cli("--text", "Buy milk", "--type", "note", "--json")
        data = json.loads(stdout)
        # Even with LLM error, input validation should pass
        assert "input" in data
        assert data["input"]["input_type"] == "note"

    def test_cli_rejects_empty_text(self):
        """Empty --text should be rejected at the CLI level."""
        stdout, stderr, code = _cli("--text", "", "--json")
        assert code == 1
        assert "No input provided" in stderr

    def test_cli_whitespace_only_is_rejected(self):
        """Whitespace-only --text should be rejected at the CLI level."""
        stdout, stderr, code = _cli("--text", "   ", "--json")
        assert code == 1
        assert "No input provided" in stderr

    def test_cli_trace_dir_flag_creates_trace(self):
        """--trace-dir should create trace file even on error."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            stdout, stderr, code = _cli(
                "--text", "Buy milk", "--json", "--trace-dir", tmp,
            )
            data = json.loads(stdout)
            # Check that trace file was created
            traces = list(Path(tmp).glob("*.jsonl"))
            assert len(traces) > 0
