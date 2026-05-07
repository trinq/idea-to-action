# Using the Notion Task Manager Integration (F015)

The system creates real tasks in your Notion database when you approve draft task actions.

## Prerequisites

1. A [Notion integration](https://www.notion.so/my-integrations) (free)
2. A Notion database with the correct properties
3. Python dependencies installed

## Step 1: Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **New integration**
3. Name it (e.g. "idea-to-action")
4. Select the workspace where your database lives
5. Click **Submit**
6. Copy the **Internal Integration Secret** — it starts with `ntn_` or `secret_`

## Step 2: Set Up Your Notion Database

Create a database (or use an existing one) with these properties:

| Property Name | Type | Options |
|---|---|---|
| `Name` | Title | (default — created automatically) |
| `Priority` | Select | `high`, `medium`, `low` |
| `Effort` | Select | `small`, `medium`, `large` |
| `Due Date` | Date | (no options needed) |

The property names are **case-sensitive** — they must match exactly.

## Step 3: Give Your Integration Access

1. Open the Notion database page
2. Click **...** (top-right menu) → **Connections** → **Add connections**
3. Find your integration (e.g. "idea-to-action") and click it
4. Confirm the access dialog

## Step 4: Copy Your Database ID

Open your Notion database in a browser. The URL looks like:

```
https://www.notion.so/workspace/1a2b3c4d5e6f?v=...
```

The database ID is the part before `?v=` — in this example, `1a2b3c4d5e6f`.

## Step 5: Configure Environment Variables

```bash
export NOTION_API_KEY="ntn_your_integration_secret"
export NOTION_DATABASE_ID="1a2b3c4d5e6f"
```

Add these to your shell profile (`~/.zshrc`, `~/.bashrc`) for persistence.

## Step 6: Verify It's Connected

```bash
python3 -c "
from idea_to_action.tools.registry import ToolRegistry
r = ToolRegistry()
print('Notion connected:', r.is_notion_task_manager_connected)
"
```

Expected: `Notion connected: True`

## Step 7: Use It

### Via the UI

```bash
streamlit run src/idea_to_action/ui/app.py
```

1. Paste some notes mentioning tasks (e.g. "Need to review the Q2 budget by Friday — high priority")
2. Click **Process**
3. In the Draft Tool Actions section, you'll see a `create_task` action
4. Notion connection status appears at the top (green "Notion: Connected")
5. Click **Approve** — the task is created in your Notion database
6. A link to the new Notion page appears

### Via Python

```python
from idea_to_action.tools.notion_task_manager import NotionTaskManagerTool
from idea_to_action.schemas.tool_actions import ActionType, ApprovalStatus, ToolAction

tool = NotionTaskManagerTool()

action = ToolAction(
    action_type=ActionType.CREATE_TASK,
    action_data={
        "title": "Review Q2 budget",
        "description": "Check line items against forecasts",
        "priority": "high",
        "effort": "medium",
        "due_date": "2026-05-15",
    },
    approval_required=True,
    approval_status=ApprovalStatus.APPROVED,
)

result = tool.execute(action)
print(result["notion_page_url"])
# → https://www.notion.so/review-q2-budget-page_abc123
```

## How Tasks Map to Notion

| DraftTask field | Notion property | Where |
|---|---|---|
| `title` | `Name` | Page title |
| `priority` | `Priority` | Select property |
| `effort` | `Effort` | Select property |
| `due_date` | `Due Date` | Date property |
| `description` | — | Page content (paragraph block) |

## Error Handling

| Error | Message | What to do |
|---|---|---|
| No API key | `Notion API key not configured` | Set `NOTION_API_KEY` |
| No database ID | `Notion database ID not configured` | Set `NOTION_DATABASE_ID` |
| Invalid API key (401) | `Notion API key is invalid` | Check key in Notion integrations page |
| Database not found (404) | `Notion API error: ...` | Check database ID, verify integration has access |
| Rate limit (429) | `Notion rate limit exceeded` | Wait a few seconds, try again |
| Description append fails | Task still created, warning shown | Task exists in Notion but without description |

## Without Notion Configured

If `NOTION_API_KEY` or `NOTION_DATABASE_ID` is not set, the system falls back to `FakeTaskManagerTool` — no real pages are created. The UI shows "Notion: Not configured (using fake tool)".
