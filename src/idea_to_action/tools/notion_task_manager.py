"""Notion task manager integration tool.

Creates real Notion database pages from approved draft task actions.
Uses Notion Integration Token (Bearer auth).
Same interface as FakeTaskManagerTool — approval-gated.
"""

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

        if not self._database_id:
            raise NotionAuthError(
                "Notion database ID not configured. Set NOTION_DATABASE_ID environment variable."
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
            if e.status == 401:
                raise NotionAuthError(
                    "Notion API key is invalid. Check your NOTION_API_KEY environment variable."
                ) from e
            if e.status == 429:
                raise NotionTaskError(
                    "Notion rate limit exceeded. Try again in a few seconds."
                ) from e
            raise NotionTaskError(
                f"Notion API error: {e}"
            ) from e

        page_id = page["id"]

        result = {
            "status": "created",
            "notion_page_id": page_id,
            "notion_page_url": page.get("url", ""),
            "task_title": action.action_data.get("title"),
        }

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
                result["warning"] = f"Task created but description could not be added: {e}"

        return result

    def _build_page_properties(self, action_data: dict) -> dict:
        """Build Notion page properties from action_data.

        Maps DraftTask fields to Notion convention-based property names:
        - title -> Name (title type)
        - priority -> Priority (select)
        - effort -> Effort (select)
        - due_date -> Due Date (date, optional)
        """
        title = action_data.get("title") or "Untitled Task"
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
            date_only = due_date.split("T")[0] if "T" in due_date else due_date
            properties["Due Date"] = {
                "date": {"start": date_only}
            }

        return properties
