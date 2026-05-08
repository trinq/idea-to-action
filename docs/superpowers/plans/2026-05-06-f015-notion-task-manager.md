# F015 - Notion Task Manager Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `FakeTaskManagerTool` with `NotionTaskManagerTool` that creates real tasks in a Notion database from approved draft actions via the `notion-client` SDK.

**Architecture:** Self-contained `NotionTaskManagerTool` class in `src/idea_to_action/tools/notion_task_manager.py` with the same `execute(action)` / `draft_create_task(task)` interface as `FakeTaskManagerTool`. Auth via `NOTION_API_KEY` env var (Bearer token). `ToolRegistry` auto-detects both env vars and falls back to `FakeTaskManagerTool`. Description written as page content blocks. Rate limit errors wrapped cleanly.

**Tech Stack:** `notion-client` (official SDK), pytest with `unittest.mock`.

---

### Task 1: Config and Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/idea_to_action/config.py`

- [ ] **Step 1: Add notion optional dep to pyproject.toml**

Add after the `google = [...]` block:

```toml
notion = ["notion-client>=2.2.0"]
```

Run:
```
python3 -m pip install -e ".[notion,dev]"
```

- [ ] **Step 2: Add Notion config vars to config.py**

Add after the `TIMEZONE` line (before `ensure_dirs`):

```python
# Notion Task Manager
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
```

- [ ] **Step 3: Verify config imports**

Run:
```
python3 -c "from idea_to_action.config import NOTION_API_KEY, NOTION_DATABASE_ID; print('NOTION_API_KEY:', repr(NOTION_API_KEY)); print('NOTION_DATABASE_ID:', repr(NOTION_DATABASE_ID))"
```

Expected: both empty strings (env vars not set).

**Commit:**
```bash
git add pyproject.toml src/idea_to_action/config.py
git commit -m "feat: add Notion config and dependency for F015"
```

---

### Task 2: NotionTaskManagerTool Class

**Files:**
- Create: `src/idea_to_action/tools/notion_task_manager.py`

- [ ] **Step 1: Write the full NotionTaskManagerTool module**

```python
"""Notion task manager integration tool.

Creates real Notion database pages from approved draft task actions.
Uses Notion Integration Token (Bearer auth).
Same interface as FakeTaskManagerTool — approval-gated.
"""

import os
from datetime import UTC, datetime

from notion_client import Client
from notion_client.errors import APIResponseError

from idea_to_action.config import NOTION_API_KEY, NOTION_DATABASE_ID
from idea_to_action.schemas.tasks import DraftTask
from idea_to_action.schemas.tool_actions import (
    ActionType,
    ApprovalStatus,
    ToolAction,
)


class NotionIntegrationError(Exception):
    """Base error for Notion integrations."""


class NotionAuthError(NotionIntegrationError):
    """Authentication error — NOTION_API_KEY missing or invalid."""


class NotionTaskError(NotionIntegrationError):
    """Error from the Notion API (database not found, rate limit, etc.)."""


class NotionTaskManagerTool:
    """Real Notion task manager integration via Integration Token.

    Same interface as FakeTaskManagerTool:
    - execute(action) -> dict
    - draft_create_task(task) -> ToolAction

    Approval-gated: only executes approved CREATE_TASK actions.
    """

    name = "notion_task_manager"

    def __init__(self, api_key: str | None = None, database_id: str | None = None) -> None:
        self._api_key = api_key or NOTION_API_KEY
        self._database_id = database_id or NOTION_DATABASE_ID
        self._client = None

    def _get_client(self) -> Client:
        """Lazy-init the Notion client. Raises NotionAuthError if API key is empty."""
        if self._client is None:
            if not self._api_key:
                raise NotionAuthError(
                    "Notion API key not configured. Set NOTION_API_KEY environment variable."
                )
            self._client = Client(auth=self._api_key)
        return self._client

    def draft_create_task(self, task: DraftTask) -> ToolAction:
        """Create a draft tool action for a Notion task (approval-gated)."""
        return ToolAction(
            action_type=ActionType.CREATE_TASK,
            action_data={
                "title": task.title,
                "description": task.description,
                "priority": task.priority.value,
                "effort": task.effort.value,
                "due_date": task.suggested_due_date.isoformat()
                if task.suggested_due_date
                else None,
            },
            approval_required=True,
            approval_status=ApprovalStatus.PENDING,
            created_at=datetime.now(UTC),
        )

    def execute(self, action: ToolAction) -> dict:
        """Create a real Notion database page from an approved action.

        Returns:
            dict with keys: status, notion_page_id, notion_page_url, task_title

        Raises:
            ValueError: Wrong action type.
            PermissionError: Action not approved.
            NotionAuthError: API key not configured.
            NotionTaskError: API call failed.
        """
        if action.action_type != ActionType.CREATE_TASK:
            raise ValueError(
                f"NotionTaskManagerTool cannot execute action type '{action.action_type.value}'"
            )
        if action.approval_status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"Cannot execute unapproved action. "
                f"Status is '{action.approval_status.value}', requires 'approved'."
            )

        client = self._get_client()
        properties = self._build_page_properties(action.action_data)
        description = action.action_data.get("description")

        try:
            page = client.pages.create(
                parent={"database_id": self._database_id},
                properties=properties,
            )
        except APIResponseError as e:
            if e.status == 429:
                raise NotionTaskError(
                    "Notion rate limit exceeded. Try again in a few seconds."
                ) from e
            raise NotionTaskError(
                f"Notion API error: {e}"
            ) from e

        page_id = page["id"]

        # Write description as page content (paragraph block)
        if description:
            try:
                client.blocks.children.append(
                    block_id=page_id,
                    children=[{
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": description},
                                }
                            ]
                        },
                    }],
                )
            except APIResponseError as e:
                raise NotionTaskError(
                    f"Notion API error while appending description: {e}"
                ) from e

        return {
            "status": "created",
            "notion_page_id": page_id,
            "notion_page_url": page.get("url", ""),
            "task_title": action.action_data.get("title"),
        }

    def _build_page_properties(self, action_data: dict) -> dict:
        """Build Notion page properties from action_data.

        Maps DraftTask fields to Notion convention-based property names:
        - title -> Name (title type)
        - priority -> Priority (select)
        - effort -> Effort (select)
        - due_date -> Due Date (date, optional)
        """
        title = action_data.get("title", "Untitled Task")
        priority = action_data.get("priority", "medium")
        effort = action_data.get("effort", "medium")
        due_date = action_data.get("due_date")

        properties = {
            "Name": {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title},
                    }
                ]
            },
            "Priority": {
                "select": {"name": priority}
            },
            "Effort": {
                "select": {"name": effort}
            },
        }

        if due_date:
            properties["Due Date"] = {
                "date": {"start": due_date}
            }

        return properties
```

- [ ] **Step 2: Verify module imports**

Run:
```
python3 -c "from idea_to_action.tools.notion_task_manager import NotionTaskManagerTool, NotionIntegrationError, NotionAuthError, NotionTaskError; print('OK')"
```

Expected: `OK`

**Commit:**
```bash
git add src/idea_to_action/tools/notion_task_manager.py
git commit -m "feat: add NotionTaskManagerTool with integration token auth and approval-gated execute"
```

---

### Task 3: Registry Wiring

**Files:**
- Modify: `src/idea_to_action/tools/registry.py`

- [ ] **Step 1: Update ToolRegistry to auto-detect Notion**

Replace the entire file:

```python
"""Tool registry — maps action types to tools.

Used by the Tool Draft Generator and Tool Executor nodes.
Auto-detects Google Calendar and Notion when credentials are configured,
falls back to fake tools otherwise.
"""

import os

from idea_to_action.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH
from idea_to_action.schemas.tool_actions import ActionType, ToolAction
from idea_to_action.tools.fake_calendar import FakeCalendarTool
from idea_to_action.tools.fake_task_manager import FakeTaskManagerTool


class ToolRegistry:
    """Registry that maps action types to tool instances.

    Uses real tools when credentials are available,
    falls back to fake tools when they are not.
    """

    def __init__(self) -> None:
        # Notion: auto-detect based on env vars
        if os.environ.get("NOTION_API_KEY") and os.environ.get("NOTION_DATABASE_ID"):
            from idea_to_action.tools.notion_task_manager import NotionTaskManagerTool
            self._task_manager = NotionTaskManagerTool()
        else:
            self._task_manager = FakeTaskManagerTool()

        # Google Calendar: auto-detect based on credentials file
        if os.path.exists(GOOGLE_CREDENTIALS_PATH):
            from idea_to_action.tools.google_calendar import GoogleCalendarTool
            self._calendar = GoogleCalendarTool(
                GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH
            )
        else:
            self._calendar = FakeCalendarTool()

        self._executors = {
            ActionType.CREATE_TASK: self._task_manager,
            ActionType.CREATE_CALENDAR_EVENT: self._calendar,
        }

    @property
    def is_google_calendar_connected(self) -> bool:
        """Whether Google Calendar (real) is configured, not fake."""
        return not isinstance(self._calendar, FakeCalendarTool)

    @property
    def is_notion_task_manager_connected(self) -> bool:
        """Whether Notion task manager (real) is configured, not fake."""
        return not isinstance(self._task_manager, FakeTaskManagerTool)

    def execute(self, action: ToolAction) -> dict:
        """Route an approved action to the correct tool for execution.

        Raises:
            ValueError: If no tool is registered for this action type.
        """
        tool = self._executors.get(action.action_type)
        if tool is None:
            raise ValueError(
                f"No tool registered for action type '{action.action_type.value}'"
            )
        return tool.execute(action)
```

- [ ] **Step 2: Verify registry with and without Notion credentials**

Run (no Notion env vars set — should use fake):
```
python3 -c "
from idea_to_action.tools.registry import ToolRegistry
r = ToolRegistry()
print('Notion connected:', r.is_notion_task_manager_connected)
print('Google connected:', r.is_google_calendar_connected)
"
```

Expected: `Notion connected: False`, `Google connected: False`

- [ ] **Step 3: Run existing tests to confirm no regression**

Run:
```
python3 -m pytest tests/test_tool_draft_layer.py -v
```

Expected: all 16 tests pass.

**Commit:**
```bash
git add src/idea_to_action/tools/registry.py
git commit -m "feat: wire NotionTaskManagerTool into registry with auto-detect"
```

---

### Task 4: Tests

**Files:**
- Create: `tests/test_notion_task_manager.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for F015 - Notion task manager integration."""

from datetime import UTC, datetime
from unittest import mock

import pytest

from idea_to_action.schemas.tasks import DraftTask, Effort, Priority
from idea_to_action.schemas.tool_actions import (
    ActionType,
    ApprovalStatus,
    ToolAction,
)
from idea_to_action.tools.notion_task_manager import (
    NotionAuthError,
    NotionIntegrationError,
    NotionTaskError,
    NotionTaskManagerTool,
)


def _make_approved_task_action(
    action_data: dict | None = None,
) -> ToolAction:
    return ToolAction(
        action_type=ActionType.CREATE_TASK,
        action_data=action_data or {
            "title": "Buy groceries",
            "description": "Milk, eggs, bread",
            "priority": "high",
            "effort": "small",
            "due_date": "2026-05-07",
        },
        approval_required=True,
        approval_status=ApprovalStatus.APPROVED,
    )


def _make_pending_task_action() -> ToolAction:
    return ToolAction(
        action_type=ActionType.CREATE_TASK,
        action_data={"title": "Test"},
        approval_required=True,
        approval_status=ApprovalStatus.PENDING,
    )


class TestErrorHierarchy:
    def test_notion_integration_error_is_base(self) -> None:
        assert issubclass(NotionAuthError, NotionIntegrationError)
        assert issubclass(NotionTaskError, NotionIntegrationError)

    def test_errors_are_exceptions(self) -> None:
        assert issubclass(NotionIntegrationError, Exception)


class TestNotionTaskManagerToolInit:
    def test_init_with_defaults(self) -> None:
        tool = NotionTaskManagerTool()
        assert tool.name == "notion_task_manager"
        assert tool._api_key == ""
        assert tool._database_id == ""

    def test_init_with_custom_params(self) -> None:
        tool = NotionTaskManagerTool(
            api_key="secret_abc",
            database_id="db_xyz",
        )
        assert tool._api_key == "secret_abc"
        assert tool._database_id == "db_xyz"


class TestExecuteApprovalGating:
    def test_execute_pending_blocked(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        action = _make_pending_task_action()
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(action)

    def test_execute_rejected_blocked(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        action = _make_pending_task_action()
        rejected = action.model_copy(
            update={"approval_status": ApprovalStatus.REJECTED}
        )
        with pytest.raises(PermissionError, match="Cannot execute unapproved"):
            tool.execute(rejected)

    def test_execute_wrong_action_type(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={"title": "Event"},
            approval_required=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        with pytest.raises(ValueError, match="cannot execute action type"):
            tool.execute(action)

    def test_execute_without_api_key_raises_auth_error(self) -> None:
        """When api_key is empty, raises NotionAuthError."""
        tool = NotionTaskManagerTool(api_key="", database_id="dummy")
        action = _make_approved_task_action()
        with pytest.raises(NotionAuthError, match="API key not configured"):
            tool.execute(action)


class TestBuildPageProperties:
    def test_full_mapping(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        props = tool._build_page_properties({
            "title": "Buy groceries",
            "priority": "high",
            "effort": "small",
            "due_date": "2026-05-07",
        })

        assert props["Name"]["title"][0]["text"]["content"] == "Buy groceries"
        assert props["Priority"]["select"]["name"] == "high"
        assert props["Effort"]["select"]["name"] == "small"
        assert props["Due Date"]["date"]["start"] == "2026-05-07"

    def test_no_due_date(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        props = tool._build_page_properties({
            "title": "Task",
            "priority": "medium",
            "effort": "medium",
            "due_date": None,
        })

        assert "Due Date" not in props
        assert props["Name"]["title"][0]["text"]["content"] == "Task"

    def test_default_title_when_missing(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        props = tool._build_page_properties({})

        assert props["Name"]["title"][0]["text"]["content"] == "Untitled Task"
        assert props["Priority"]["select"]["name"] == "medium"


class TestDraftCreateTask:
    def test_draft_create_task(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        task = DraftTask(
            title="Review PR",
            description="Check the auth module",
            priority=Priority.HIGH,
            effort=Effort.SMALL,
            suggested_due_date=datetime(2026, 5, 10),
        )
        action = tool.draft_create_task(task)

        assert action.action_type == ActionType.CREATE_TASK
        assert action.approval_required is True
        assert action.approval_status == ApprovalStatus.PENDING
        assert action.action_data["title"] == "Review PR"
        assert action.action_data["description"] == "Check the auth module"
        assert action.action_data["priority"] == "high"
        assert action.action_data["effort"] == "small"
        assert action.action_data["due_date"] is not None


class TestExecuteWithMockedAPI:
    def test_execute_approved_creates_page(self) -> None:
        """execute() with APPROVED status calls the Notion API and returns page metadata."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch("idea_to_action.tools.notion_task_manager.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/buy-groceries-page_abc123",
            }

            result = tool.execute(_make_approved_task_action())

        assert result["status"] == "created"
        assert result["notion_page_id"] == "page_abc123"
        assert "notion.so" in result["notion_page_url"]
        assert result["task_title"] == "Buy groceries"

        # Verify pages.create was called with correct args
        mock_client.pages.create.assert_called_once()
        call_kwargs = mock_client.pages.create.call_args.kwargs
        assert call_kwargs["parent"] == {"database_id": "db_xyz"}
        assert "properties" in call_kwargs

    def test_execute_appends_description_as_content(self) -> None:
        """When description is present, it's appended as a paragraph block."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch("idea_to_action.tools.notion_task_manager.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/test",
            }

            tool.execute(_make_approved_task_action())

        # Should append description as children block
        mock_client.blocks.children.append.assert_called_once()
        call_kwargs = mock_client.blocks.children.append.call_args.kwargs
        assert call_kwargs["block_id"] == "page_abc123"
        assert len(call_kwargs["children"]) == 1
        block = call_kwargs["children"][0]
        assert block["paragraph"]["rich_text"][0]["text"]["content"] == "Milk, eggs, bread"

    def test_execute_skips_description_when_none(self) -> None:
        """When description is None, no children block is appended."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")
        action = _make_approved_task_action({
            "title": "Simple task",
            "description": None,
            "priority": "medium",
            "effort": "medium",
            "due_date": None,
        })

        with mock.patch("idea_to_action.tools.notion_task_manager.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/test",
            }

            tool.execute(action)

        mock_client.blocks.children.append.assert_not_called()

    def test_execute_api_error_wrapped(self) -> None:
        """When the API returns an error, wraps it in NotionTaskError."""
        from notion_client.errors import APIResponseError

        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch("idea_to_action.tools.notion_task_manager.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.side_effect = APIResponseError(
                response=mock.MagicMock(status_code=404),
                body='{"message": "Database not found"}',
            )

            with pytest.raises(NotionTaskError, match="Notion API error"):
                tool.execute(_make_approved_task_action())

    def test_execute_rate_limit_wrapped(self) -> None:
        """Rate limit (429) errors get a specific message."""
        from notion_client.errors import APIResponseError

        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch("idea_to_action.tools.notion_task_manager.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.side_effect = APIResponseError(
                response=mock.MagicMock(status_code=429),
                body='{"message": "Rate limited"}',
            )

            with pytest.raises(NotionTaskError, match="rate limit exceeded"):
                tool.execute(_make_approved_task_action())


class TestRegistryWithNotion:
    def test_registry_not_connected_when_no_env_vars(self) -> None:
        """When NOTION_API_KEY is not set, is_notion_task_manager_connected is False."""
        from idea_to_action.tools.registry import ToolRegistry

        with mock.patch.dict("os.environ", {}, clear=True):
            registry = ToolRegistry()
            assert registry.is_notion_task_manager_connected is False

    def test_registry_execute_still_works_with_fake(self) -> None:
        """Even without Notion, registry.execute() still works via FakeTaskManagerTool."""
        from idea_to_action.tools.registry import ToolRegistry

        with mock.patch.dict("os.environ", {}, clear=True):
            registry = ToolRegistry()
            action = _make_approved_task_action()
            result = registry.execute(action)
            assert result["status"] == "fake_executed"
```

- [ ] **Step 2: Run the tests**

Run:
```
python3 -m pytest tests/test_notion_task_manager.py -v
```

Expected: all 16 tests pass.

- [ ] **Step 3: Run full test suite to confirm no regressions**

Run:
```
python3 -m pytest tests/ -v
```

Expected: all tests pass (287 old + 16 new = 303).

**Commit:**
```bash
git add tests/test_notion_task_manager.py
git commit -m "test: add Notion task manager integration tests"
```

---

### Task 5: UI Updates

**Files:**
- Modify: `src/idea_to_action/ui/app.py`

- [ ] **Step 1: Update _render_tool_actions to show Notion connection status and page links**

Replace the connection status block (lines 143-148) with both Google and Notion status:

```python
    # Show connection status for both integrations
    registry = ToolRegistry()
    if registry.is_google_calendar_connected:
        st.success("Google Calendar: Connected")
    else:
        st.caption("Google Calendar: Not configured (using fake tool)")

    if registry.is_notion_task_manager_connected:
        st.success("Notion: Connected")
    else:
        st.caption("Notion: Not configured (using fake tool)")
```

Replace the execution result display block (lines 189-202) to also handle Notion page links:

```python
            exec_result = st.session_state.execution_results.get(state_key)
            if exec_result:
                if exec_result["success"]:
                    result_data = exec_result["result"]
                    # Show Google Calendar event link if available
                    if result_data.get("html_link"):
                        st.success(
                            f"Event created: [{result_data['event_summary']}]({result_data['html_link']}) "
                            f"(ID: `{result_data['google_event_id']}`)"
                        )
                    # Show Notion page link if available
                    elif result_data.get("notion_page_url"):
                        st.success(
                            f"Task created: [{result_data['task_title']}]({result_data['notion_page_url']}) "
                            f"(ID: `{result_data['notion_page_id']}`)"
                        )
                    else:
                        st.success(f"Execution result: {result_data}")
                else:
                    st.error(f"Execution failed: {exec_result['error']}")
```

- [ ] **Step 2: Verify UI module imports**

Run:
```
python3 -c "import idea_to_action.ui.app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run UI tests**

Run:
```
python3 -m pytest tests/test_ui.py -v
```

Expected: all 10 tests pass.

**Commit:**
```bash
git add src/idea_to_action/ui/app.py
git commit -m "feat: show Notion connection status and page links in UI"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run full test suite**

```
python3 -m pytest tests/ -v
```

Expected: 303 tests pass (287 old + 16 new).

- [ ] **Step 2: Run init.sh**

```
bash init.sh
```

Expected: all tests pass, all evals pass.

- [ ] **Step 3: Run evals**

```
python3 scripts/run_evals.py
```

Expected: 12/12 evals pass.

- [ ] **Step 4: Update feature_list.json**

Set F015 status to `"passing"` with evidence:

```json
{
    "id": "F015",
    "priority": 15,
    "area": "integration",
    "title": "Notion task manager integration",
    "user_visible_behavior": "The system creates real tasks in a Notion database from approved draft task actions.",
    "status": "passing",
    "verification": [...],
    "evidence": [
        "16/16 tests passing in tests/test_notion_task_manager.py",
        "NotionTaskManagerTool: Bearer token auth, approval-gated execute()",
        "ToolRegistry auto-detects NOTION_API_KEY + NOTION_DATABASE_ID → NotionTaskManagerTool, else FakeTaskManagerTool",
        "Page properties mapping: Name (title), Priority (select), Effort (select), Due Date (date)",
        "Description written as page content (paragraph block)",
        "Rate limit (429) wrapped in NotionTaskError with clear message",
        "UI shows Notion connection status and page links",
        "Error hierarchy: NotionIntegrationError ← NotionAuthError, NotionTaskError"
    ],
    "notes": "Requires Notion integration with database. Set NOTION_API_KEY and NOTION_DATABASE_ID env vars. Database must have Name, Priority, Effort, Due Date properties."
}
```

**Commit:**
```bash
git add feature_list.json
git commit -m "feat: mark F015 Notion task manager as passing"
```
