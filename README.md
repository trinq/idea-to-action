<div align="center">

<!-- Hero Section -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d1117,50:161b22,100:1f6feb&height=220&section=header&text=idea-to-action&fontSize=52&fontColor=f0f6fc&fontAlignY=35&desc=AI%20Personal%20Productivity%20Agent&descSize=18&descAlignY=55&descColor=8b949e&animation=fadeIn" width="100%" alt="idea-to-action" />

<br/>

**Turn rough notes, reminders, and task dumps into organized ideas, actionable plans, and approval-gated tool actions — powered by AI.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-f5c542?style=for-the-badge)](LICENSE)

<br/>

[![Tests](https://img.shields.io/badge/tests-340%20passed-2ea043?style=flat-square&logo=pytest&logoColor=white)](#-testing)
[![Evals](https://img.shields.io/badge/evals-12%2F12%20passed-2ea043?style=flat-square)](#-evaluation-suite)
[![Code](https://img.shields.io/badge/source-3.6k%20lines-blue?style=flat-square)](#-project-structure)

<br/>

[Features](#-features) · [Quick Start](#-quick-start) · [Architecture](#-architecture) · [Integrations](#-integrations) · [Docs](#-documentation)

</div>

<br/>

---

<br/>

## 🎯 What is idea-to-action?

**idea-to-action** is an AI-powered personal productivity agent that bridges the gap between *thinking* and *doing*. Paste your messy notes, bullet-point brain dumps, or meeting transcripts — and get back structured ideas, concrete action plans, and ready-to-approve tool actions.

> 💡 **The key principle:** The AI classifies, summarizes, plans, and drafts — but **you** always approve before anything is executed. No surprises, no autonomous actions.

<br/>

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🧠 Smart Idea Organization
Messy notes go in → organized, categorized ideas come out. Separates actionable items from vague thoughts. Detects missing context and flags it.

</td>
<td width="50%" valign="top">

### 📋 Action Plan Generation
Turns organized ideas into concrete tasks with priorities, effort estimates, and suggested deadlines — all evidence-based, never hallucinated.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🔐 Approval-Gated Execution
Every write action (tasks, calendar events, email drafts) requires explicit user approval. Nothing executes without your say-so.

</td>
<td width="50%" valign="top">

### 📅 Google Calendar Integration
Creates real calendar events from approved drafts via OAuth2. Auto-detects credentials and falls back to safe fake tools.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📝 Notion Task Manager
Pushes approved tasks directly to your Notion database with full property mapping — priority, effort, due dates, and descriptions.

</td>
<td width="50%" valign="top">

### ✉️ Gmail Draft Integration
Creates Gmail drafts from approved email actions. **Never sends automatically** — drafts sit in Gmail for your review.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🔍 Trace Logging & Eval Suite
Full JSONL tracing with secret redaction. 12 eval cases covering organization, planning, and tool safety. Built for iteration.

</td>
<td width="50%" valign="top">

### 🖥️ Multi-Interface
Streamlit UI for visual interaction, REST API for integration, and CLI for scripting — all sharing the same pipeline.

</td>
</tr>
</table>

<br/>

## 🏗️ Architecture

```
                    ┌──────────────┐
                    │  Raw Input   │   Notes, bullet points, meeting transcripts
                    └──────┬───────┘
                           │
                ┌──────────▼──────────┐
                │  Input Validator    │   Schema validation, text preservation
                └──────────┬──────────┘
                           │
               ┌───────────▼───────────┐
               │   Idea Organizer  🧠  │   LLM-powered categorization
               └───────────┬───────────┘
                           │
               ┌───────────▼───────────┐
               │  Action Planner  📋   │   LLM-powered task breakdown
               └───────────┬───────────┘
                           │
            ┌──────────────▼──────────────┐
            │  Tool Draft Generator  🔧   │   Creates approval-gated drafts
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────┐
            │    Approval Gate  🔐        │   ← Human-in-the-loop
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────┐
            │   Tool Execution  🚀        │   Google Calendar / Notion / Gmail
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────┐
            │   Trace & Report  📊        │   JSONL traces, secret redaction
            └─────────────────────────────┘
```

<br/>

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Language** | Python 3.11+ | Core runtime |
| **Orchestration** | LangGraph | State machine workflow with human-in-the-loop |
| **LLM** | DeepSeek / OpenAI | Idea organization & action planning |
| **Schemas** | Pydantic v2 | Input/output validation, type safety |
| **API** | FastAPI | REST endpoints |
| **UI** | Streamlit | Interactive local interface |
| **Testing** | pytest | 340 tests across 21 test files |
| **Integrations** | Google Calendar, Notion, Gmail | Real tool execution (approval-gated) |
| **Storage** | JSONL + SHA-256 checksums | Local persistence with integrity verification |
| **Tracing** | Custom JSONL logger | Full pipeline tracing with secret redaction |

<br/>

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- A **DeepSeek** or **OpenAI** API key (for LLM features)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/idea-to-action.git
cd idea-to-action

# Install core dependencies
python3 -m pip install -e .

# Install optional dependencies (pick what you need)
python3 -m pip install -e '.[dev]'       # pytest
python3 -m pip install -e '.[ui]'        # Streamlit UI
python3 -m pip install -e '.[api]'       # FastAPI server
python3 -m pip install -e '.[google]'    # Google Calendar + Gmail
python3 -m pip install -e '.[notion]'    # Notion integration

# Or install everything at once
python3 -m pip install -e '.[dev,ui,api,google,notion]'
```

### Configure LLM

```bash
# Option A: DeepSeek (recommended — affordable and capable)
export DEEPSEEK_API_KEY="your-deepseek-api-key"

# Option B: OpenAI
export OPENAI_API_KEY="your-openai-api-key"
```

### Run

<table>
<tr>
<td width="33%">

**🖥️ Streamlit UI**
```bash
streamlit run \
  src/idea_to_action/ui/app.py
```

</td>
<td width="33%">

**⌨️ CLI**
```bash
python3 -m idea_to_action \
  --text "Your notes here"
```

</td>
<td width="34%">

**🌐 API Server**
```bash
uvicorn \
  idea_to_action.api.app:app
```

</td>
</tr>
</table>

<br/>

## 📖 Usage

### Via the Streamlit UI

1. Start the UI: `streamlit run src/idea_to_action/ui/app.py`
2. Paste your raw notes into the text area
3. Click **Process**
4. Review organized ideas and action plan
5. **Approve** or **Reject** each draft tool action
6. Approved actions execute immediately (calendar events, Notion tasks, Gmail drafts)

### Via CLI

```bash
# From text argument
python3 -m idea_to_action --text "Need to email John about the project deadline by Friday. Also schedule a team sync next week."

# From stdin
echo "Buy groceries, call dentist, review Q2 budget — high priority" | python3 -m idea_to_action

# JSON output
python3 -m idea_to_action --text "Your notes" --json
```

### Via Python

```python
from idea_to_action.pipeline import run_pipeline
from idea_to_action.agent.llm_provider import create_llm

llm = create_llm()
result = run_pipeline(
    "Need to review Q2 budget by Friday — high priority. "
    "Also, email Sarah the meeting notes.",
    llm=llm,
)

# Organized ideas
print(result.organized.cleaned_summary)
print(result.organized.actionable_items)

# Action plan
print(result.plan.tasks)

# Draft tool actions (pending approval)
for action in result.tool_actions.actions:
    print(f"{action.action_type.value}: {action.action_data}")
```

<br/>

## 🔌 Integrations

<table>
<tr>
<td width="33%" align="center">

### 📅 Google Calendar
Create real calendar events from approved drafts.

[Architecture →](ARCHITECTURE.md)

</td>
<td width="33%" align="center">

### 📝 Notion
Push tasks to your Notion database with priority, effort, and due dates.

[Setup Guide →](docs/using-notion-integration.md)

</td>
<td width="34%" align="center">

### ✉️ Gmail
Create email drafts — never sends automatically.

[Setup Guide →](docs/using-gmail-integration.md)

</td>
</tr>
</table>

All integrations share the same pattern:
- **Auto-detection:** Real tool is used when credentials are found; safe fake tool otherwise
- **Approval-gated:** Nothing executes without explicit user approval
- **Graceful fallback:** The system works without any integration configured

<br/>

## 📁 Project Structure

```
idea-to-action/
├── src/idea_to_action/
│   ├── agent/               # LLM logic (organizer, planner, prompts)
│   ├── api/                 # FastAPI REST endpoints
│   ├── evals/               # Scoring functions & eval runner
│   ├── graph/               # LangGraph workflow & nodes
│   ├── rules/               # Deterministic priority & effort rules
│   ├── schemas/             # Pydantic models (input, ideas, tasks, actions)
│   ├── storage/             # JSONL persistence with checksums
│   ├── tools/               # Tool integrations (Calendar, Notion, Gmail, fakes)
│   ├── tracing/             # JSONL trace logger with secret redaction
│   ├── ui/                  # Streamlit interactive UI
│   ├── config.py            # Environment-based configuration
│   ├── main.py              # CLI entry point
│   └── pipeline.py          # Pipeline orchestrator
│
├── tests/                   # 340 tests across 21 files
├── evals/                   # 12 eval cases (organization, planning, safety)
├── scripts/                 # Auth & utility scripts
├── examples/                # Sample input/output JSON files
├── docs/                    # Integration setup guides
└── traces/                  # Pipeline trace output (gitignored)
```

<br/>

## 🧪 Testing

```bash
# Run all tests
python3 -m pytest

# Run with verbose output
python3 -m pytest -v

# Run specific test file
python3 -m pytest tests/test_gmail_draft.py
```

**Current status: 340 tests passing across 21 test files.**

<br/>

## 📊 Evaluation Suite

```bash
# Run all evals
python3 scripts/run_evals.py
```

12 eval cases covering three areas:

| Area | Cases | What it checks |
|:---|:---:|:---|
| **Idea Organization** | 6 | Categories, actionable vs. vague, missing context, text preservation |
| **Action Planning** | 3 | Task quality, no invented deadlines, evidence-based priorities |
| **Tool Safety** | 3 | Approval requirements, pending status, no unauthorized execution |

<br/>

## ⚙️ Configuration

All configuration is via environment variables — no secrets stored in the repo.

| Variable | Required | Description |
|:---|:---:|:---|
| `DEEPSEEK_API_KEY` | Yes* | DeepSeek API key for LLM features |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (alternative to DeepSeek) |
| `DEEPSEEK_MODEL` | No | Model name (default: `deepseek-chat`) |
| `I2A_DATA_DIR` | No | Data directory (default: `./data/`) |
| `I2A_TRACES_DIR` | No | Traces directory (default: `./traces/`) |
| `I2A_TIMEZONE` | No | Timezone (default: `Asia/Ho_Chi_Minh`) |
| `I2A_GMAIL_CREDENTIALS` | No | Gmail OAuth client secret path |
| `I2A_GMAIL_TOKEN` | No | Gmail OAuth token path |
| `I2A_GOOGLE_CREDENTIALS` | No | Google Calendar OAuth client secret path |
| `I2A_GOOGLE_TOKEN` | No | Google Calendar OAuth token path |
| `NOTION_API_KEY` | No | Notion integration secret |
| `NOTION_DATABASE_ID` | No | Notion database ID |

<sub>* At least one LLM API key is required for AI features. The system works without one (deterministic steps only).</sub>

<br/>

## 📚 Documentation

| Document | Description |
|:---|:---|
| [Gmail Integration Guide](docs/using-gmail-integration.md) | Full setup for Gmail draft creation |
| [Notion Integration Guide](docs/using-notion-integration.md) | Full setup for Notion task management |
| [Architecture](ARCHITECTURE.md) | System design, data flow, and constraints |

<br/>

## 🛡️ Safety Principles

This project follows strict safety-by-design principles:

- **🔐 Approval-gated execution** — All write operations (tasks, events, emails) require explicit user approval
- **🚫 No autonomous actions** — The AI recommends; the human decides
- **📝 Drafts only** — Gmail creates drafts, never sends. Calendar creates events only when approved
- **🔒 Secret redaction** — Traces never log API keys, tokens, or email body content
- **✅ Schema validation** — All inputs and outputs are validated against strict Pydantic schemas
- **📊 Inference marking** — AI-inferred priorities, dates, and efforts are explicitly marked as inferred

<br/>

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/my-feature`
3. **Run** the test suite before committing: `python3 -m pytest`
4. **Run** the eval suite: `python3 scripts/run_evals.py`
5. **Commit** with a descriptive message
6. **Push** and open a Pull Request

Please ensure all tests and evals pass before submitting.

<br/>

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

<br/>

---

<div align="center">

<br/>

**Built with ❤️ for people who think faster than they can organize.**

<br/>

<sub>Made with Python · LangGraph · Pydantic · FastAPI · Streamlit</sub>

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d1117,50:161b22,100:1f6feb&height=100&section=footer" width="100%" />

</div>
