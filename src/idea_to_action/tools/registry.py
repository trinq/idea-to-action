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
