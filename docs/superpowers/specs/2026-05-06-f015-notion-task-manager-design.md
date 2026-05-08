# F015 - Notion Task Manager Integration Design Spec

**Goal:** Replace `FakeTaskManagerTool` with a real `NotionTaskManagerTool` that creates tasks in a Notion database from approved draft actions, following the same architecture as F014 Google Calendar integration.

**Architecture:** Self-contained `NotionTaskManagerTool` class with `execute(action)` / `draft_create_task(task)` interface matching `FakeTaskManagerTool`. Auth via `NOTION_API_KEY` env var (Bearer token). Uses `notion-client` SDK. `ToolRegistry` auto-detects credentials and falls back to `FakeTaskManagerTool`.

**Tech Stack:** `notion-client` (official Notion Python SDK), `httpx` (transitive dep for HTTP), pytest with `unittest.mock`.

---

## Files

| File | Action |
|---|---|
| `src/idea_to_action/tools/notion_task_manager.py` | Create — `NotionTaskManagerTool` class |
| `tests/test_notion_task_manager.py` | Create — ~14 tests |
| `src/idea_to_action/config.py` | Modify — add `NOTION_API_KEY`, `NOTION_DATABASE_ID` |
| `src/idea_to_action/tools/registry.py` | Modify — auto-detect Notion, add property |
| `src/idea_to_action/ui/app.py` | Modify — show Notion connection status and page links |
| `pyproject.toml` | Modify — add `notion` optional deps |
| `feature_list.json` | Modify — F015 to `passing` |

---

## Error Hierarchy

```
NotionIntegrationError(Exception) ← base
├── NotionAuthError — NOTION_API_KEY missing or invalid
└── NotionTaskError — API call failed (database not found, rate limit, etc.)
```

---

## Config

```python
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
```

Both must be set for real Notion integration — unlike F014 which checks for a file.

---

## Notion Database Convention

The Notion database must have these properties (names are convention-based, not configurable):

| DraftTask field | Notion property name | Notion type |
|---|---|---|
| `title` | `Name` | title (the default title property) |
| `priority` | `Priority` | select (options: "high", "medium", "low") |
| `effort` | `Effort` | select (options: "small", "medium", "large") |
| `suggested_due_date` | `Due Date` | date (optional, omitted when None) |

---

## NotionTaskManagerTool

```python
class NotionTaskManagerTool:
    name = "notion_task_manager"

    def __init__(self, api_key=None, database_id=None):
        # Default from env vars NOTION_API_KEY, NOTION_DATABASE_ID

    def _get_client(self):
        # Lazy-init notion_client.Client
        # Raises NotionAuthError if api_key is empty

    def draft_create_task(self, task: DraftTask) -> ToolAction:
        # Mirrors FakeTaskManagerTool — returns PENDING ToolAction

    def execute(self, action: ToolAction) -> dict:
        # 1. Guard: action_type == CREATE_TASK else ValueError
        # 2. Guard: approval_status == APPROVED else PermissionError
        # 3. _build_page_properties(action_data)
        # 4. client.pages.create(parent={database_id}, properties=...)
        # 5. Wrap APIErrorResponse -> NotionTaskError
        # 6. Return {status, notion_page_id, notion_page_url, task_title}

    def _build_page_properties(self, action_data: dict) -> dict:
        # Maps action_data to Notion page properties schema
```

### execute() return shape

```python
{
    "status": "created",
    "notion_page_id": "uuid-string",
    "notion_page_url": "https://notion.so/task-title-uuid",
    "task_title": "Task title",
}
```

### _build_page_properties mapping

```python
# Input action_data (from draft_create_task):
# {"title": "...", "description": "...", "priority": "high", "effort": "small", "due_date": "2026-05-07"}

# Output Notion properties:
{
    "Name": {"title": [{"text": {"content": title}}]},
    "Priority": {"select": {"name": priority}},
    "Effort": {"select": {"name": effort}},
    "Due Date": {"date": {"start": due_date}},  # only if due_date not None
}
```

---

## Registry Wiring

```python
class ToolRegistry:
    def __init__(self):
        # Notion: auto-detect based on env vars
        if os.environ.get("NOTION_API_KEY") and os.environ.get("NOTION_DATABASE_ID"):
            from idea_to_action.tools.notion_task_manager import NotionTaskManagerTool
            self._task_manager = NotionTaskManagerTool()
        else:
            self._task_manager = FakeTaskManagerTool()

        # Google Calendar: auto-detect based on credentials file (existing)
        ...

    @property
    def is_notion_task_manager_connected(self) -> bool:
        return not isinstance(self._task_manager, FakeTaskManagerTool)
```

---

## UI Updates

Same pattern as F014: `_render_tool_actions()` already handles task actions. Add:
- Connection status: `"Notion: Connected"` (green) or `"Notion: Not configured (using fake tool)"` (caption)
- On successful task creation, show `notion_page_url` as a clickable link

---

## Tests (~14 tests)

Mirroring F014's test structure:

1. **TestErrorHierarchy** — 2 tests (inheritance chain, Exception subclass)
2. **TestNotionTaskManagerToolInit** — 2 tests (defaults from env, custom params)
3. **TestExecuteApprovalGating** — 3 tests (pending blocked, rejected blocked, wrong action type)
4. **TestBuildPageProperties** — 3 tests (full mapping, no due date, no description)
5. **TestDraftCreateTask** — 1 test (returns PENDING ToolAction with correct fields)
6. **TestExecuteWithMockedAPI** — 3 tests (creates page via mocked Client, auth error on empty key, API error wrapping)
7. **TestRegistryWithNotion** — 2 tests (not connected without key, fake fallback works)

---

## Dependencies

Add to `pyproject.toml`:
```toml
notion = ["notion-client>=2.2.0"]
```

---

## Description Handling

`description` from `action_data` is written as the **page content** (not a property), using a paragraph block:

```python
# In execute(), after pages.create():
if description:
    client.blocks.children.append(
        block_id=page_id,
        children=[{
            "paragraph": {
                "rich_text": [{"text": {"content": description}}]
            }
        }]
    )
```

This keeps the Notion database clean (properties for structured data, content for details).

---

## Trace Logging

`NotionTaskManagerTool.execute()` must log via `TraceLogger` when creating real tasks:

```python
trace_logger.log("notion_task_execute", {
    "action_type": action.action_type.value,
    "task_title": action.action_data.get("title"),
    "approval_status": action.approval_status.value,
    "notion_page_id": result.get("notion_page_id"),
    "notion_page_url": result.get("notion_page_url"),
})
```

This provides an audit trail for all real Notion writes.

---

## Rate Limit Handling

Notion API has a rate limit of **3 requests/second**. Handle `APIResponseError` with status 429:

- Log a warning
- Wrap in `NotionTaskError` with a clear message: `"Notion rate limit exceeded. Try again in a few seconds."`
- Do NOT auto-retry in MVP — keep it simple, let the user retry via UI

