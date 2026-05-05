"""Tool registry — maps action types to tools.

Used by the Tool Draft Generator and Tool Executor nodes.
All tools in MVP are fake tools.
"""

from idea_to_action.schemas.tool_actions import ActionType, ToolAction
from idea_to_action.tools.fake_calendar import FakeCalendarTool
from idea_to_action.tools.fake_task_manager import FakeTaskManagerTool


class ToolRegistry:
    """Registry that maps action types to tool instances.

    All tools are fake in MVP. Real tools are added later behind the same interface.
    """

    def __init__(self) -> None:
        self._calendar = FakeCalendarTool()
        self._task_manager = FakeTaskManagerTool()

        self._executors = {
            ActionType.CREATE_TASK: self._task_manager,
            ActionType.CREATE_CALENDAR_EVENT: self._calendar,
        }

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
