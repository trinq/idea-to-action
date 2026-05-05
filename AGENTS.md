# AGENTS.md
This repository is designed for long-running coding-agent work.
The goal is to leave the repo in a state where the next session can continue without guessing.

## Project
This project is an AI Personal Productivity Agent.
The agent turns rough notes, reminders, meeting notes, and task dumps into organized ideas, actionable plans, draft tool actions, and approved execution steps.
Core workflows:
1. Organize Ideas
2. Develop Action Plans
3. Execute or delegate tasks through approved tools
This is not a fully autonomous assistant.
The LLM may classify, summarize, plan, prioritize, draft, and recommend.
Deterministic rules control schemas, tool permissions, approvals, and execution boundaries.

## MVP Scope
Initial MVP: Idea Organizer + Action Plan Generator.
Input may include raw notes, bullet points, meeting notes, voice transcripts, reminders, project thoughts, learning goals, and follow-up items.
Output must include cleaned summary, categories, actionable tasks, priority, effort estimate, missing context, draft tool actions, and approval requirements.
Out of scope for MVP:
- sending emails automatically
- creating calendar events without approval
- creating or modifying tasks without approval
- deleting user data
- making purchases
- contacting third parties automatically
- background autonomous execution
- multi-agent architecture

## Startup Workflow
Before writing code:
1. Confirm the working directory with `pwd`.
2. Read `AGENTS.md`.
3. Read `claude-progress.md` for latest verified state and next step.
4. Read `feature_list.json` and choose the highest-priority unfinished feature.
5. Review recent commits with `git log --oneline -5`.
6. Run `./init.sh`.
7. Run required verification before starting new work.
If baseline verification is failing, fix that first.
Do not stack new feature work on top of a broken starting state.

## Working Rules
- Work on one feature at a time.
- Keep changes within the selected feature scope.
- Prefer durable repo artifacts over chat summaries.
- Do not mark a feature complete just because code was added.
- Do not silently change verification rules during implementation.
- Do not add multi-agent architecture before single-agent eval quality is measured.
- Use LangGraph for orchestration only. Do not use full LangChain (chains, agents, retrievers).
- If behavior changes, update the matching docs, tests, or evals in the same session.

## Hard Constraints
MUST:
- preserve user intent
- separate user facts from model inference
- validate input and output schemas
- mark missing context explicitly
- mark inferred priority, effort, and dates as inferred
- require approval before writing to external tools
- log tool calls and tool results
- keep MVP execution approval-gated
MUST NOT:
- invent deadlines, meetings, commitments, contacts, or preferences
- create calendar events without approval
- create, update, complete, or delete external tasks without approval
- send emails or messages without approval
- delete or overwrite user notes
- expose private user data in logs
- store secrets, API keys, or tokens in the repo

## Required Artifacts
- `feature_list.json`: source of truth for feature state
- `claude-progress.md`: session log and current verified status
- `init.sh`: standard startup and verification path
- `session-handoff.md`: optional compact handoff for larger sessions

## Definition Of Done
A feature is done only when target behavior is implemented, verification ran, schemas pass, tests or evals pass, evidence is recorded, approval requirements are preserved, and the repo remains restartable from the standard startup path.
If verification was not run, the feature is not done.

## End Of Session
Before ending a session:
1. Update `claude-progress.md`.
2. Update `feature_list.json`.
3. Record changes, verification, risks, blockers, and next action.
4. Commit with a descriptive message once work is safe.
5. Leave the repo clean enough for the next session to run `./init.sh`.

