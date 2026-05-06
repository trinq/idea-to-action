#!/usr/bin/env python3
"""Idea-to-Action CLI — submit raw notes, get organized output.

Usage:
    python -m idea_to_action.main --text "Buy milk and send report"
    echo "Buy milk" | python -m idea_to_action.main
    python -m idea_to_action.main --text "Send report" --json
"""

import argparse
import json
import sys
from pathlib import Path

from idea_to_action.agent.llm_provider import LLMConfigError, create_llm
from idea_to_action.pipeline import PipelineResult, run_pipeline
from idea_to_action.schemas.input import InputType


def format_text_output(result: PipelineResult) -> str:
    """Pretty-print pipeline result as human-readable text."""
    lines = []
    lines.append("=" * 50)
    lines.append(f"Trace ID: {result.trace_id}")
    lines.append("=" * 50)

    if result.errors:
        for e in result.errors:
            lines.append(f"  [{e.error_type}] {e.step}: {e.message}")
        lines.append("")

    if result.input:
        lines.append(f"Input: {result.input.raw_text}")
        lines.append("")

    if result.organized:
        lines.append("== Organized Ideas ==")
        lines.append(f"Summary: {result.organized.cleaned_summary}")
        lines.append(f"Categories: {', '.join(result.organized.categories)}")
        lines.append(f"Confidence: {result.organized.confidence}")
        lines.append(f"Ideas ({len(result.organized.ideas)}):")
        for idea in result.organized.ideas:
            actionable = "✓" if idea.is_actionable else "~"
            inferred = "(inferred)" if idea.is_inferred else ""
            lines.append(f"  [{idea.category}] {actionable} {idea.cleaned_text} {inferred}")
        if result.organized.missing_context:
            lines.append("Missing context:")
            for mc in result.organized.missing_context:
                lines.append(f"  ? {mc.question}")
        lines.append("")

    if result.plan:
        lines.append("== Action Plan ==")
        lines.append(f"Summary: {result.plan.summary}")
        if result.plan.tasks:
            lines.append(f"Tasks ({len(result.plan.tasks)}):")
            for task in result.plan.tasks:
                priority = task.priority.value if task.priority else "?"
                effort = task.effort.value if task.effort else "?"
                due = f" (due: {task.suggested_due_date})" if task.suggested_due_date else ""
                lines.append(f"  [{priority}/{effort}] {task.title}{due}")
        if result.plan.calendar_events:
            lines.append(f"Calendar events ({len(result.plan.calendar_events)}):")
            for ev in result.plan.calendar_events:
                lines.append(f"  {ev.title}")
        lines.append("")

    if result.tool_actions:
        lines.append("== Draft Actions ==")
        lines.append(f"Total: {len(result.tool_actions.actions)} "
                     f"(pending: {result.tool_actions.pending_count}, "
                     f"approved: {result.tool_actions.approved_count}, "
                     f"rejected: {result.tool_actions.rejected_count})")
        for action in result.tool_actions.actions:
            status = action.approval_status.value
            req = "approval required" if action.approval_required else "no approval"
            lines.append(f"  [{status}] {action.action_type.value} ({req})")
        lines.append("")

    if result.trace_file:
        lines.append(f"Trace: {result.trace_file}")

    lines.append("=" * 50)
    return "\n".join(lines)


def format_json_output(result: PipelineResult) -> str:
    """Serialize pipeline result as JSON."""
    output = {
        "trace_id": result.trace_id,
        "status": "success" if not result.errors else "partial",
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "errors": [{"step": e.step, "message": e.message, "error_type": e.error_type}
                    for e in result.errors],
    }
    if result.input:
        output["input"] = result.input.model_dump(mode="json")
    if result.organized:
        output["organized"] = result.organized.model_dump(mode="json")
    if result.plan:
        output["plan"] = result.plan.model_dump(mode="json")
    if result.tool_actions:
        output["tool_actions"] = result.tool_actions.model_dump(mode="json")
    return json.dumps(output, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="idea-to-action",
        description="Convert rough notes into organized ideas and action plans.",
    )
    parser.add_argument(
        "--text", default=None,
        help="Raw notes to process (reads from stdin if omitted).",
    )
    parser.add_argument(
        "--type", default="other",
        choices=[t.value for t in InputType],
        help="Input type hint (default: other).",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output structured JSON instead of formatted text.",
    )
    parser.add_argument(
        "--trace-dir", default=None,
        help="Directory for trace files (default: traces/).",
    )
    args = parser.parse_args()

    # Get raw text from --text or stdin
    raw_text = args.text
    if raw_text is None:
        if not sys.stdin.isatty():
            raw_text = sys.stdin.read().strip()
        else:
            print("Enter your raw notes (Ctrl+D when done):", file=sys.stderr)
            raw_text = sys.stdin.read().strip()
    else:
        raw_text = raw_text.strip()

    if not raw_text:
        print("Error: No input provided. Use --text or pipe input via stdin.", file=sys.stderr)
        return 1

    # Try to create LLM
    llm = None
    try:
        llm = create_llm()
    except LLMConfigError as e:
        # Will be caught by pipeline as organizer error
        pass

    result = run_pipeline(
        raw_text=raw_text,
        llm=llm,
        input_type=InputType(args.type),
        source="cli",
        trace_dir=args.trace_dir,
    )

    if args.json:
        print(format_json_output(result))
    else:
        print(format_text_output(result))

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
