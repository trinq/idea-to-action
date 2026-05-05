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
Core schemas, storage, and rules implemented
```

Current status:

```text
F001, F002, F003, F011, F004 implemented and passing. All core infrastructure ready.
```

Highest-priority unfinished feature:

```text
F013 - LLM provider configuration
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
F013 - LLM provider configuration
```

Expected work:

```text
Implement configurable LLM provider layer with API key management,
model selection, and graceful fallback on failure.
Support DeepSeek (primary) and OpenAI (alternative).
API keys loaded from environment only, never stored in repo.
Graceful error when API key missing or invalid.
Model selection configurable.
Add provider tests.
```

Definition of done for F013:

```text
LLM provider configurable via environment variables.
API key loaded from environment.
Graceful error on missing/invalid key.
Model selection works.
Verification result is recorded here and in feature_list.json.
```
