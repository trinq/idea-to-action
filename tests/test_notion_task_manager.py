"""Tests for F015 - Notion task manager integration."""

from datetime import UTC, datetime
from unittest import mock

import pytest
from notion_client.errors import APIErrorCode, APIResponseError

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


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------
class TestErrorHierarchy:
    def test_notion_integration_error_is_base(self) -> None:
        assert issubclass(NotionAuthError, NotionIntegrationError)
        assert issubclass(NotionTaskError, NotionIntegrationError)

    def test_errors_are_exceptions(self) -> None:
        assert issubclass(NotionIntegrationError, Exception)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Approval gating
# ---------------------------------------------------------------------------
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

    def test_execute_without_database_id_raises_auth_error(self) -> None:
        """When database_id is empty, raises NotionAuthError."""
        tool = NotionTaskManagerTool(api_key="dummy", database_id="")
        action = _make_approved_task_action()
        with pytest.raises(NotionAuthError, match="database ID not configured"):
            tool.execute(action)


# ---------------------------------------------------------------------------
# _build_page_properties
# ---------------------------------------------------------------------------
class TestBuildPageProperties:
    def test_full_mapping(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        props = tool._build_page_properties({
            "title": "Buy groceries",
            "priority": "high",
            "effort": "small",
            "due_date": "2026-05-07T00:00:00+00:00",
        })

        assert props["Name"]["title"][0]["text"]["content"] == "Buy groceries"
        assert props["Priority"]["select"]["name"] == "high"
        assert props["Effort"]["select"]["name"] == "small"
        assert props["Due Date"]["date"]["start"] == "2026-05-07"

    def test_date_only_string_preserved(self) -> None:
        """Due dates without time component are passed through as-is."""
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        props = tool._build_page_properties({
            "title": "Task",
            "priority": "medium",
            "effort": "medium",
            "due_date": "2026-05-07",
        })
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

    def test_empty_title_falls_back(self) -> None:
        tool = NotionTaskManagerTool(api_key="dummy", database_id="dummy")
        props = tool._build_page_properties({"title": ""})

        assert props["Name"]["title"][0]["text"]["content"] == "Untitled Task"


# ---------------------------------------------------------------------------
# draft_create_task
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# execute with mocked Notion API
# ---------------------------------------------------------------------------
class TestExecuteWithMockedAPI:
    def test_execute_approved_creates_page(self) -> None:
        """execute() with APPROVED status calls the Notion API and returns page metadata."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
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

        mock_client.pages.create.assert_called_once()
        call_kwargs = mock_client.pages.create.call_args.kwargs
        assert call_kwargs["parent"] == {"database_id": "db_xyz"}
        assert "properties" in call_kwargs

    def test_execute_appends_description_as_content(self) -> None:
        """When description is present, it's appended as a paragraph block."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/test",
            }

            tool.execute(_make_approved_task_action())

        mock_client.blocks.children.append.assert_called_once()
        call_kwargs = mock_client.blocks.children.append.call_args.kwargs
        assert call_kwargs["block_id"] == "page_abc123"
        assert len(call_kwargs["children"]) == 1
        block = call_kwargs["children"][0]
        assert (
            block["paragraph"]["rich_text"][0]["text"]["content"]
            == "Milk, eggs, bread"
        )

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

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/test",
            }

            tool.execute(action)

        mock_client.blocks.children.append.assert_not_called()

    def test_execute_description_append_failure_returns_warning(self) -> None:
        """When description append fails, result still returns success with warning."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/test",
            }
            mock_client.blocks.children.append.side_effect = APIResponseError(
                code=APIErrorCode.InternalServerError,
                status=500,
                message="Server error",
                headers={},
                raw_body_text='{"message": "Server error"}',
            )

            result = tool.execute(_make_approved_task_action())

        assert result["status"] == "created"
        assert result["notion_page_id"] == "page_abc123"
        assert "warning" in result
        assert "description could not be added" in result["warning"]

    def test_execute_api_error_wrapped(self) -> None:
        """When the API returns an error, wraps it in NotionTaskError."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.side_effect = APIResponseError(
                code=APIErrorCode.ObjectNotFound,
                status=404,
                message="Database not found",
                headers={},
                raw_body_text='{"message": "Database not found"}',
            )

            with pytest.raises(NotionTaskError, match="Notion API error"):
                tool.execute(_make_approved_task_action())

    def test_execute_rate_limit_wrapped(self) -> None:
        """Rate limit (429) errors get a specific message."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.side_effect = APIResponseError(
                code=APIErrorCode.RateLimited,
                status=429,
                message="Rate limited",
                headers={},
                raw_body_text='{"message": "Rate limited"}',
            )

            with pytest.raises(NotionTaskError, match="rate limit exceeded"):
                tool.execute(_make_approved_task_action())

    def test_execute_unauthorized_wraps_as_auth_error(self) -> None:
        """401 errors are raised as NotionAuthError, not NotionTaskError."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.side_effect = APIResponseError(
                code=APIErrorCode.Unauthorized,
                status=401,
                message="Unauthorized",
                headers={},
                raw_body_text='{"message": "Unauthorized"}',
            )

            with pytest.raises(NotionAuthError, match="API key is invalid"):
                tool.execute(_make_approved_task_action())

    def test_execute_empty_title_task(self) -> None:
        """Task with empty title still creates with fallback title."""
        tool = NotionTaskManagerTool(api_key="secret_abc", database_id="db_xyz")
        action = _make_approved_task_action({
            "title": "",
            "description": None,
            "priority": "medium",
            "effort": "medium",
            "due_date": None,
        })

        with mock.patch(
            "idea_to_action.tools.notion_task_manager.Client"
        ) as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value = mock_client

            mock_client.pages.create.return_value = {
                "id": "page_abc123",
                "url": "https://notion.so/test",
            }

            result = tool.execute(action)

        assert result["task_title"] == "Untitled Task"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------
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
