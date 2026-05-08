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

Create a database (or use an existing one). The setup script can add the required properties automatically:

| Property Name | Type | Options |
|---|---|---|
| `Name` | Title | (default — created automatically) |
| `Priority` | Select | `high`, `medium`, `low` |
| `Effort` | Select | `small`, `medium`, `large` |
| `Due Date` | Date | (no options needed) |

The property names are **case-sensitive** — they must match exactly.

Notion's newer API exposes database columns through a nested **data source** schema. The setup script handles both older database schemas and newer data source schemas.

## Step 3: Give Your Integration Access

1. Open the Notion database page
2. Click **...** (top-right menu) → **Connections** → **Add connections**
3. Find your integration (e.g. "idea-to-action") and click it
4. Confirm the access dialog

## Step 4: Run the Setup Script

Run:

```bash
python3 scripts/setup_notion.py
```

The script asks for:

1. Your Notion integration secret
2. The full Notion database URL or database ID
3. Confirmation that the database has been shared with the integration

It then:

- Extracts and normalizes the database ID
- Verifies the database is visible to the integration
- Adds `Priority`, `Effort`, and `Due Date` properties if missing
- Saves `NOTION_API_KEY` and `NOTION_DATABASE_ID` to `.env`

Example accepted URL:

```text
https://www.notion.so/workspace/My-Tasks-264c3e246e0c44fb91987c8948bd0ec4?v=...
```

## Step 5: Load Environment Variables

The Streamlit UI auto-loads `.env`. For terminal commands, either restart your terminal or run the command printed by the setup script:

```bash
source /path/to/idea-to-action/.env
```

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
| Properties not visible after setup | Script says properties added but UI does not show them | Re-run setup with the current script; it updates Notion data source schemas correctly |
| Rate limit (429) | `Notion rate limit exceeded` | Wait a few seconds, try again |
| Description append fails | Task still created, warning shown | Task exists in Notion but without description |

## Without Notion Configured

If `NOTION_API_KEY` or `NOTION_DATABASE_ID` is not set, the system falls back to `FakeTaskManagerTool` — no real pages are created. The UI shows "Notion: Not configured (using fake tool)".
