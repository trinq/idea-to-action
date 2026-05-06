# claude-progress.md

This file records the current verified state of the repository.

A fresh agent session should read this file after `AGENTS.md` and before starting new work.

## Current Verified State

Project name:

```text
idea-to-action
```

Project type:

```text
AI Personal Productivity Agent
```

Current phase:

```text
Core pipeline complete with eval suite. Ready for prompt tuning and real LLM testing.
```

Current status:

```text
F001-F009, F011-F013 implemented and passing (12/13 features).
Full pipeline + eval suite + trace logging + API/CLI all green.
```

Highest-priority unfinished feature:

```text
F010 - Simple local UI
```

Standard startup command:

```bash
./init.sh
```

Standard feature tracker:

```text
feature_list.json
```

Current blocker:

```text
None
```

## Existing Harness Files

Created:

- `AGENTS.md`
- `init.sh`
- `feature_list.json`
- `claude-progress.md`
- `ARCHITECTURE.md`
- `README.md`
- `pyproject.toml`
- `src/idea_to_action/` (full package structure)
- `tests/test_input_schema.py`
- `examples/valid_raw_idea.json`
- `examples/invalid_empty_input.json`

Not created yet:

- `CONSTRAINTS.md`
- `docs/`
- `evals/` (populated)
- `scripts/` (populated)

## Session Record

### Session 013 - F012 Implementation

Goal:

```text
Implement F012 - API and CLI interface.
```

Completed:

```text
Created src/idea_to_action/pipeline.py: run_pipeline() orchestrator wiring
input → organizer → planner → tool draft → trace.
PipelineResult and PipelineError dataclasses. Each step wrapped in try/except,
never throws — always returns partial results.
Created src/idea_to_action/api/models.py: Pydantic request/response models.
Created src/idea_to_action/api/app.py: FastAPI create_app() factory with
/health and /submit endpoints. Graceful error handling: 422 for validation,
503 for missing LLM.
Created src/idea_to_action/main.py: CLI with argparse, stdin support,
--json flag, formatted text output.
Created tests/test_pipeline.py: 16 pipeline integration tests.
Created tests/test_api.py: 10 API endpoint tests (TestClient).
Created tests/test_main.py: 10 CLI integration tests (subprocess).
```

Verification run:

```text
init.sh passed. 261/261 tests passing (225 previous + 36 new). 12/12 evals passing.
```

Evidence recorded:

```text
run_pipeline() successfully chains all steps: input validation, organizer, planner,
tool draft generation, trace logging.
Pipeline never crashes — errors are captured per step and returned in result.errors.
Trace file always written (try/finally), even on failures.
API /health returns llm_available status.
API /submit validates input (422 on empty/missing), returns 503 when no LLM.
CLI rejects empty/whitespace input at the CLI level.
CLI --json outputs parseable JSON with full pipeline result.
CLI reads from stdin when --text not provided.
Safe dump uses model_dump(mode='json') to avoid datetime serialization issues.
```

Known risks:

```text
DEEPSEEK_API_KEY not set — pipeline always returns partial results.
Real LLM end-to-end testing needs API key.
FastAPI server not started/tested with uvicorn — only TestClient tests.
```

Next best action:

```text
Start F010 - Simple local UI (last feature).
```

### Session 012 - F009 Implementation

Goal:

```text
Implement F009 - Trace logging.
```

Completed:

```text
Created src/idea_to_action/tracing/trace_logger.py: TraceLogger with JSONL output.
_secret_redaction: sensitive keys (api_key, password, token, secret, authorization),
value patterns (sk-*, Bearer *), nested dicts and lists of dicts.
Created tests/test_trace_logger.py: 22 tests for sanitize + trace logger + full pipeline.
```

Verification run:

```text
init.sh passed. 225/225 tests passing. 12/12 evals passing.
```

Evidence recorded:

```text
TraceLogger.log() records step, timestamp, trace_id, sanitized data.
close() writes JSONL to traces/ directory.
API keys and Bearer tokens redacted in both keys and values.
Nested structures (dicts, lists of dicts) sanitized recursively.
Full pipeline trace: 5 steps (input, organizer, planner, tools, final_output).
Empty trace creates file without content.
Step ordering preserved across 10-entry trace.
```

Known risks:

```text
DEEPSEEK_API_KEY not set — trace logger tested structurally, not via live pipeline.
```

Next best action:

```text
Start F012 - API and CLI interface.
```

### Session 011 - F008 Implementation

Goal:

```text
Implement F008 - Initial eval suite with 12 cases and pass/fail reporting.
```

Completed:

```text
Created evals/scoring.py: 12 check functions for organizer/planner/tool outputs.
Created evals/runner.py: load_eval_cases, run_all_evals, print_report.
Created evals/initial_cases.json: 12 eval cases covering organizer, planner, tool safety.
Created scripts/run_evals.py: CLI entry point.
Created tests/test_evals.py: 26 tests for eval infrastructure.
```

Verification run:

```text
init.sh passed. 203/203 tests passing. 12/12 evals passing.
```

Evidence recorded:

```text
Eval areas: idea_organization (6 cases), action_planning (3 cases), tool_safety (3 cases).
Checks: categories, actionable/vague separation, missing context, confidence range,
original text preservation, no invented deadlines, approval_required, pending status.
All 12 evals pass. Eval script returns exit 0.
```

Known risks:

```text
DEEPSEEK_API_KEY not set — evals test schema rules, not LLM quality.
Real LLM eval tuning needs API key (can be done after F013 is live-tested).
```

Next best action:

```text
Start F009 - Trace logging.
```

### Session 010 - F007 Implementation

Goal:

```text
Implement F007 - Draft-only tool action layer with fake tools.
```

Completed:

```text
Created tools/fake_task_manager.py: draft_create_task() + execute() with approval check.
Created tools/fake_calendar.py: draft_create_event() + execute() with approval check.
Created tools/registry.py: ToolRegistry mapping action types to fake tools.
Created graph/nodes/tool_draft_generator.py: PlanResult → ActionPlan.
All write actions approval_required=True, start pending.
Fake execute() only works when approved; blocked otherwise.
No external APIs are called — all fake.
16 tests in tests/test_tool_draft_layer.py.
```

Verification run:

```text
init.sh passed. 177/177 tests passing (161 previous + 16 new).
```

Evidence recorded:

```text
FakeTaskManager/FakeCalendar draft actions with correct action_type.
All write actions have approval_required=True, approval_status=pending.
Unapproved execute() raises PermissionError.
Registry routes correctly; unknown action types raise ValueError.
ToolDraftGenerator converts PlanResult → ActionPlan with 100% pending actions.
Empty plan rejected at schema level.
```

Known risks:

```text
DEEPSEEK_API_KEY not set — fake tools tested without real APIs.
SEND_EMAIL and SEND_MESSAGE not yet implemented (out of MVP scope).
```

Next best action:

```text
Start F008 - Initial eval suite.
```

### Session 009 - F006 Implementation

Goal:

```text
Implement F006 - Action plan generator agent.
```

Completed:

```text
Created schemas/plan.py: PlanResult schema (tasks, calendar_events, missing_context).
Created agent/planner.py: generate_plan() with structured LLM output.
Added PLANNER_SYSTEM_PROMPT and PLANNER_USER_TEMPLATE to prompts.py.
Post-validation: invented deadlines removed when no evidence in original text.
Only actionable items become tasks; vague items skipped.
11 tests in tests/test_planner.py with mock LLM.
```

Verification run:

```text
init.sh passed. 161/161 tests passing (150 previous + 11 new).
```

Evidence recorded:

```text
generate_plan() accepts OrganizedIdeaOutput, returns PlanResult.
Actionable ideas → concrete tasks with priority and effort.
Vague items skipped — no tasks generated for non-actionable ideas.
Invented deadlines stripped when original text lacks date keywords.
Legitimate deadlines preserved when evidence exists.
No calendar events generated without meeting evidence.
Missing context reported by LLM.
Priorities follow evidence (HIGH for urgent, MEDIUM default).
```

Known risks:

```text
DEEPSEEK_API_KEY not set — tested with mock LLM only.
Planner prompt needs eval tuning (F008).
Post-validation rules are heuristic; evals will measure precision.
```

Next best action:

```text
Start F007 - Draft-only tool action layer.
```

### Session 008 - F005 Implementation

Goal:

```text
Implement F005 - Single idea organizer agent.
```

Completed:

```text
Created agent/organizer.py: organize_ideas() with structured LLM output.
Created agent/prompts.py: ORGANIZER_SYSTEM_PROMPT and ORGANIZER_USER_TEMPLATE.
Uses with_structured_output(OrganizedIdeaOutput) for schema-validated output.
Error handling wraps LLM failures in OrganizerError.
Prompt templates enforce: preserve original text, mark inferred, report missing context, never invent.
10 tests in tests/test_organizer.py with mock LLM.
```

Verification run:

```text
init.sh passed. 150/150 tests passing (140 previous + 10 new).
```

Evidence recorded:

```text
organize_ideas() accepts RawIdeaInput, returns OrganizedIdeaOutput.
Vague items correctly classified as non-actionable.
Missing context reported for incomplete notes.
Original text preserved verbatim.
Multiple categories handled correctly.
inferred_fields populated appropriately.
Prompt templates include all required rules.
LLM errors wrapped gracefully.
```

Known risks:

```text
DEEPSEEK_API_KEY not set — tested with mock LLM only.
No live LLM end-to-end test yet.
Prompt tuning not done — needs eval suite (F008).
```

Next best action:

```text
Start F006 - Action plan generator.
```

### Session 007 - F013 Implementation

Goal:

```text
Implement F013 - Configurable LLM provider layer.
```

Completed:

```text
Created agent/llm_provider.py with provider-agnostic factory.
Supports DeepSeek (primary) and OpenAI (alternative).
Both via langchain-openai ChatOpenAI (DeepSeek is OpenAI-compatible).
API keys from environment only (DEEPSEEK_API_KEY, OPENAI_API_KEY).
Graceful LLMConfigError on missing/invalid keys.
Configurable model selection via env vars.
get_default_provider() auto-detects available provider.
24 tests in tests/test_llm_provider.py.
```

Verification run:

```text
init.sh passed. 140/140 tests passing.
```

Evidence recorded:

```text
API keys loaded from env only, never hardcoded or read from files.
create_llm() returns ChatOpenAI with correct model, base_url, temperature.
Missing key raises LLMConfigError with clear message.
Model defaults: deepseek-chat / gpt-4o-mini, overridable via env.
API key excluded from str/repr output.
Provider priority: DeepSeek first, then OpenAI fallback.
```

Known risks:

```text
DEEPSEEK_API_KEY not set in current environment.
No actual API call is made in tests — provider is validated structurally.
```

Next best action:

```text
Start F005 - Single idea organizer agent.
```

### Session 006 - F004 Implementation

Goal:

```text
Implement F004 - Deterministic priority and effort rules.
```

Completed:

```text
Created rules/priority.py: assign_priority() with explicit deadline patterns,
vague/someday patterns, urgency keywords (Vietnamese + English).
Created rules/effort.py: estimate_effort() with small/large keyword detection.
All rules are pure Python, no LLM.
Missing context reported when deadline is uncertain.
All estimates marked is_inferred unless explicitly stated by user.
28 tests in tests/test_priority_rules.py.
```

Verification run:

```text
init.sh passed. 116/116 tests passing.
```

Evidence recorded:

```text
Explicit deadline → HIGH (not inferred).
Vague someday → LOW (not inferred).
Default actionable → MEDIUM (inferred).
Non-actionable → LOW (not inferred).
Small effort keywords → SMALL (inferred).
Large effort keywords → LARGE (inferred).
Default → MEDIUM (inferred).
Missing context detected for uncertain deadlines.
No urgency invented.
```

Known risks:

```text
DEEPSEEK_API_KEY not set. LLM features will not work.
Keyword-based rules are heuristic — evals will measure precision later.
```

Next best action:

```text
Start F013 - LLM provider configuration.
```

### Session 005 - F011 Implementation

Goal:

```text
Implement F011 - Local JSONL storage layer with checksum integrity verification.
```

Completed:

```text
Created StorageManager with JSONL backend (storage/manager.py).
save/load/list/delete/exists operations for any record type.
SHA-256 checksum per record, verified on load and list_all.
Atomic writes via tmp file + os.replace.
Corrupted JSON and tampered data rejected with clear errors.
15 tests in tests/test_storage.py.
```

Verification run:

```text
init.sh passed. 88/88 tests passing (14+22+32+5 F001-F003 + 15 F011).
```

Evidence recorded:

```text
All tests pass. Save/load round-trip preserves data integrity.
Tampered files detected via checksum mismatch.
Corrupted JSON raises StorageError.
Atomic writes prevent partial file corruption.
```

Known risks:

```text
DEEPSEEK_API_KEY not set.
```

Next best action:

```text
Start F004 - Priority and effort rules.
```

### Session 004 - F003 Implementation

Goal:

```text
Implement F003 - Task and tool-action schema with approval enforcement.
```

Completed:

```text
Created DraftTask, DraftCalendarEvent, DraftReminder schemas (tasks.py).
Created ToolAction, ActionPlan schemas with approval_required enforcement (tool_actions.py).
Write actions (create_*, send_*) MUST have approval_required=True.
All actions start with approval_status=pending.
Valid samples: valid_draft_task.json, valid_calendar_draft.json, valid_action_plan.json.
Invalid sample: invalid_write_without_approval.json.
Added 32 tests (10 task schema + 22 tool permissions).
```

Verification run:

```text
init.sh passed. 68/68 tests passing (14 F001 + 22 F002 + 32 F003).
No deprecation warnings.
```

Evidence recorded:

```text
All tests pass. Write actions rejected without approval_required=True.
approval_status transitions: pending → approved/rejected.
approved_at only settable when status is approved.
```

Known risks:

```text
DEEPSEEK_API_KEY not set.
```

Next best action:

```text
Start F011 - Storage layer.
```

### Session 003 - F002 Implementation

Goal:

```text
Implement F002 - Organized idea output schema with user fact vs inference separation.
```

Completed:

```text
Created OrganizedIdea, MissingContext, and OrganizedIdeaOutput schemas.
Separates user facts (original_text, explicit categories) from inferred fields.
Added valid sample: examples/valid_organized_output.json.
Added invalid sample: examples/invalid_no_categories.json.
Added 22 tests in tests/test_ideas_schema.py.
```

Verification run:

```text
init.sh passed. 36/36 tests passing (14 F001 + 22 F002).
```

Evidence recorded:

```text
All tests pass. Output schema validates correctly. Categories required.
Missing context field required (can be empty). User facts and inferred fields separated.
Confidence bounded 0.0-1.0.
```

Known risks:

```text
DEEPSEEK_API_KEY not set.
```

Next best action:

```text
Start F003 - Task and tool-action schema.
```

### Session 002 - Project Scaffolding + F001 Implementation

Goal:

```text
Create project skeleton (pyproject.toml, folder structure, __init__.py, config.py).
Implement F001 - Raw idea input schema with validation and tests.
```

Completed:

```text
Created pyproject.toml with langgraph, langchain-openai, pydantic, pytest.
Created full folder structure per ARCHITECTURE.md.
Created src/idea_to_action/__init__.py and config.py.
Created F001 schema: RawIdeaInput (raw_text, input_type, source, created_at).
Created valid sample: examples/valid_raw_idea.json.
Created invalid sample: examples/invalid_empty_input.json.
Created 14 tests in tests/test_input_schema.py.
```

Verification run:

```text
init.sh passed. 14/14 tests passing. No deprecation warnings.
```

Evidence recorded:

```text
All tests pass. Schema validates correctly, rejects empty/whitespace,
preserves original text, and is immutable.
```

Known risks:

```text
DEEPSEEK_API_KEY not set.
No git repo yet.
```

Next best action:

```text
Start F002 - Organized idea output schema.
```

### Session 001 - Minimal Harness Bootstrap

Goal:

```text
Create the minimal repository harness files based on the WalkingLabs template approach.
```

Completed:

```text
Created AGENTS.md for the AI Personal Productivity Agent.
Created init.sh as the standard startup and verification entrypoint.
Created feature_list.json with the initial feature roadmap.
Created claude-progress.md to track current state and handoff.
```

Verification run:

```text
init.sh passed. 14/14 tests passing. No deprecation warnings.
```

Evidence recorded:

```text
- pyproject.toml with langgraph, langchain-openai, pydantic, pytest
- Full package structure per ARCHITECTURE.md
- F001 schema: RawIdeaInput with raw_text, input_type, source, created_at
- Valid sample: examples/valid_raw_idea.json
- Invalid sample: examples/invalid_empty_input.json
- 14 tests covering: valid inputs, empty rejection, whitespace rejection,
  text preservation, immutability, sample file validation
```

Known risks:

```text
- DEEPSEEK_API_KEY not set. LLM features will not work.
- No eval suite exists yet.
- No runnable example script exists yet.
```

Next best action:

```text
Start F003 - Task and tool-action schema.
```

## Next Implementation Target

Feature:

```text
F010 - Simple local UI
```

Expected work:

```text
Build a simple local UI (Streamlit or simple web UI) where the user
can paste rough notes and receive organized ideas, action plan, and
draft actions. All actions remain approval-gated — no execution
without explicit user approval.
```

Definition of done for F010:

```text
Open local UI.
Submit sample notes.
View structured output.
Confirm no action executes without approval.
Verification result is recorded here and in feature_list.json.
```
