# ARCHITECTURE.md

This file is the system map for the `idea-to-action` project.

It records the technology stack, major components, data flow, folder structure, and architectural constraints.

## Project Name

```text
idea-to-action
```

## Product Type

```text
AI Personal Productivity Agent
```

The system converts rough user thoughts into organized ideas, action plans, and approval-gated tool actions.

## Technology Stack

### Language

```text
Python 3.11+
```

Reason:

- simple backend implementation
- strong ecosystem for AI tooling
- good support for schema validation, testing, CLI, and APIs

### Backend Framework

```text
FastAPI
```

Used later for:

- API endpoints
- UI/backend separation
- tool integration endpoints
- future external integrations

MVP may start without FastAPI if CLI is enough.

### Schema Validation

```text
Pydantic v2
```

Used for:

- raw idea input schema
- organized idea output schema
- task schema
- tool action schema
- approval state validation

All agent input and output must be schema-validated.

### Agent Orchestration

```text
LangGraph
```

Used for:

- state machine workflow (input → organize → plan → draft → approve → execute)
- conditional routing between nodes
- human-in-the-loop interrupts at approval gate
- checkpointing and state persistence
- streaming intermediate results

Reason:

- the workflow is a natural directed graph with clear nodes and edges
- approval gate requires interrupt/resume — LangGraph supports this natively
- checkpointing replaces custom state persistence code
- state typing integrates well with Pydantic schemas

Constraints:

- use LangGraph only, not full LangChain
- keep each node simple and testable in isolation
- do not use LangChain agents, chains, or retrievers
- business logic stays in pure Python, LangGraph handles orchestration only

### LangGraph Workflow Design

```text
                    ┌──────────────┐
                    │  Raw Input   │
                    └──────┬───────┘
                           ↓
                ┌──────────────────┐
                │ Input Validator  │
                └──────┬───────────┘
                       ↓
              ┌────────────────────┐
              │  Idea Organizer    │
              └────────┬───────────┘
                       ↓
              ┌────────────────────┐
              │  Action Planner    │
              └────────┬───────────┘
                       ↓
            ┌──────────────────────┐
            │ Tool Draft Generator │
            └──────────┬───────────┘
                       ↓
            ┌──────────────────────┐
            │   Approval Gate      │ ← human interrupt
            └──────────┬───────────┘
                       ↓
            ┌──────────────────────┐
            │  Tool Execution      │
            └──────────┬───────────┘
                       ↓
            ┌──────────────────────┐
            │  Trace & Report      │
            └──────────────────────┘
```

Each node is a Python function that:

- receives typed state (Pydantic model)
- performs one focused task
- returns updated state
- can be tested independently without LangGraph

### LLM Layer

```text
DeepSeek API via langchain-openai (OpenAI-compatible)
```

Primary provider: **DeepSeek** (`https://api.deepseek.com`)

DeepSeek API is OpenAI-compatible, so it works through `langchain-openai` with custom `base_url`:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=os.environ["DEEPSEEK_API_KEY"],
)
```

Configuration:

- `DEEPSEEK_API_KEY` loaded from environment variable
- `DEEPSEEK_MODEL` defaults to `deepseek-chat` (configurable)
- structured JSON output via `.with_structured_output()`
- prompt templates kept separate from business rules
- architecture remains provider-agnostic — switching provider only requires changing config

### Storage

MVP:

```text
Local JSON / JSONL files
```

Used for:

- sample inputs
- traces
- eval results
- local reports

Later:

```text
SQLite or PostgreSQL
```

Use database storage only after schemas, evals, and traces are stable.

### Testing

```text
pytest
```

Used for:

- schema validation tests
- rule tests
- tool permission tests
- eval runner tests

### Evaluation

```text
Custom eval runner
```

Initial evals should test:

- idea categorization
- action plan quality
- missing context detection
- hallucinated deadline detection
- approval requirement preservation
- schema validity

### Logging / Tracing

```text
JSONL trace files
```

Trace records should include:

- input ID
- normalized input
- model output
- tool draft actions
- approval state
- errors
- final output

Traces must not store secrets or unnecessary private data.

### UI

MVP:

```text
CLI
```

Later:

```text
Streamlit or simple web UI
```

Do not build UI before schemas, agent workflow, and evals exist.

### Tool Integrations

MVP:

```text
Fake tools only
```

Planned tool categories:

- notes app
- task manager
- calendar
- reminders
- email draft
- project management system

All write actions must be approval-gated.

## Core Components

```text
Raw Input
  ↓
Input Validator
  ↓
Idea Organizer
  ↓
Action Planner
  ↓
Task / Tool Action Generator
  ↓
Approval Gate
  ↓
Tool Execution Layer
  ↓
Trace + Report
```

### Input Validator

Validates raw user input.

Owns:

- required fields
- empty input rejection
- original text preservation
- metadata validation

### Idea Organizer

Converts rough notes into organized categories.

Owns:

- idea cleanup
- category assignment
- actionable vs vague classification
- missing context detection

### Action Planner

Turns organized ideas into practical next steps.

Owns:

- task decomposition
- priority suggestion
- effort estimate
- suggested due date when supported by evidence

### Tool Action Generator

Prepares tool-ready draft actions.

Owns:

- draft task object
- draft calendar event
- draft reminder
- draft email/message
- approval status

### Approval Gate

Prevents unsafe or unauthorized execution.

Owns:

- approval_required flag
- approved action list
- blocked action list
- execution permission state

### Tool Execution Layer

Executes only approved actions.

MVP uses fake tools only.

### Eval Layer

Measures output quality and safety.

Owns:

- eval cases
- scoring
- regression tracking
- eval reports

### Trace Layer

Records what happened.

Owns:

- inputs
- outputs
- tool calls
- approval decisions
- errors

## Initial Folder Structure

```text
idea-to-action/
├── AGENTS.md
├── ARCHITECTURE.md
├── init.sh
├── claude-progress.md
├── feature_list.json
├── pyproject.toml
├── README.md
│
├── src/
│   └── idea_to_action/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── input.py
│       │   ├── ideas.py
│       │   ├── tasks.py
│       │   ├── tool_actions.py
│       │   └── state.py          # LangGraph state definition
│       │
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── workflow.py        # main LangGraph graph definition
│       │   ├── nodes/
│       │   │   ├── __init__.py
│       │   │   ├── input_validator.py
│       │   │   ├── idea_organizer.py
│       │   │   ├── action_planner.py
│       │   │   ├── tool_draft_generator.py
│       │   │   ├── approval_gate.py
│       │   │   ├── tool_executor.py
│       │   │   └── trace_reporter.py
│       │   └── edges.py           # conditional edge logic
│       │
│       ├── rules/
│       │   ├── __init__.py
│       │   ├── priority.py
│       │   ├── effort.py
│       │   └── permissions.py
│       │
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── organizer.py       # LLM logic for idea organization
│       │   ├── planner.py         # LLM logic for action planning
│       │   └── prompts.py
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── fake_calendar.py
│       │   ├── fake_task_manager.py
│       │   └── registry.py
│       │
│       ├── evals/
│       │   ├── __init__.py
│       │   ├── scoring.py
│       │   └── runner.py
│       │
│       └── tracing/
│           ├── __init__.py
│           └── trace_logger.py
│
├── examples/
│   ├── valid_raw_idea.json
│   └── invalid_empty_input.json
│
├── evals/
│   └── initial_cases.json
│
├── tests/
│   ├── test_input_schema.py
│   ├── test_task_schema.py
│   ├── test_priority_rules.py
│   ├── test_tool_permissions.py
│   └── test_graph_workflow.py     # LangGraph integration tests
│
├── scripts/
│   ├── run_example.py
│   └── run_evals.py
│
├── traces/
│   └── .gitkeep
│
└── reports/
    └── .gitkeep
```

## Architectural Constraints

MUST:

- validate all input and output with schemas
- keep tool writes approval-gated
- start with fake tools
- keep prompts separate from deterministic rules
- keep evals before serious prompt tuning
- keep traces free of secrets

MUST NOT:

- build multi-agent architecture in MVP
- connect real tools before fake tools and evals work
- allow calendar/task/email writes without approval
- store API keys in the repository
- use full LangChain (chains, agents, retrievers) — only LangGraph + langchain-core
- put business logic inside graph nodes — nodes should delegate to pure Python functions
