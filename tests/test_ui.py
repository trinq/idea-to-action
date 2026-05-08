"""Tests for F010 - Simple Local UI.

Tests the approval logic, status transitions, execution gating,
and pipeline result structure. The Streamlit UI itself is verified
manually via `streamlit run`.
"""

import pytest

from idea_to_action.pipeline import PipelineError, PipelineResult
from idea_to_action.schemas.tool_actions import (
    ActionPlan,
    ActionType,
    ApprovalStatus,
    ToolAction,
)
from idea_to_action.tools.registry import ToolRegistry


def _make_pending_action(
    action_type: ActionType = ActionType.CREATE_TASK,
    action_data: dict | None = None,
) -> ToolAction:
    """Helper to create a pending tool action for testing."""
    return ToolAction(
        action_type=action_type,
        action_data=action_data or {"title": "Test task", "priority": "high"},
        approval_required=True,
    )


class TestApprovalTransitions:
    """Tests for approve/reject status transitions."""

    def test_approve_action_transitions_to_approved(self) -> None:
        action = _make_pending_action()
        assert action.approval_status == ApprovalStatus.PENDING

        approved = action.model_copy(
            update={"approval_status": ApprovalStatus.APPROVED}
        )
        assert approved.approval_status == ApprovalStatus.APPROVED

    def test_reject_action_transitions_to_rejected(self) -> None:
        action = _make_pending_action()
        assert action.approval_status == ApprovalStatus.PENDING

        rejected = action.model_copy(
            update={"approval_status": ApprovalStatus.REJECTED}
        )
        assert rejected.approval_status == ApprovalStatus.REJECTED

    def test_approved_action_can_be_executed(self) -> None:
        action = _make_pending_action()
        approved = action.model_copy(
            update={"approval_status": ApprovalStatus.APPROVED}
        )

        registry = ToolRegistry()
        result = registry.execute(approved)

        assert result["status"] == "fake_executed"
        assert result["action_type"] == "create_task"
        assert result["data"] == {"title": "Test task", "priority": "high"}

    def test_pending_action_cannot_be_executed(self) -> None:
        action = _make_pending_action()
        assert action.approval_status == ApprovalStatus.PENDING

        registry = ToolRegistry()
        with pytest.raises(PermissionError, match="Cannot execute unapproved action"):
            registry.execute(action)

    def test_rejected_action_cannot_be_executed(self) -> None:
        action = _make_pending_action()
        rejected = action.model_copy(
            update={"approval_status": ApprovalStatus.REJECTED}
        )

        registry = ToolRegistry()
        with pytest.raises(PermissionError, match="Cannot execute unapproved action"):
            registry.execute(rejected)

    def test_execute_approved_calendar_event(self) -> None:
        action = ToolAction(
            action_type=ActionType.CREATE_CALENDAR_EVENT,
            action_data={"title": "Meeting", "date": "2026-05-06"},
            approval_required=True,
        )
        approved = action.model_copy(
            update={"approval_status": ApprovalStatus.APPROVED}
        )

        registry = ToolRegistry()
        result = registry.execute(approved)

        # Registry may use FakeCalendarTool or GoogleCalendarTool depending on config
        assert result["status"] in ("fake_executed", "created")


class TestPipelineResultStructure:
    """Smoke tests for PipelineResult structure."""

    def test_pipeline_result_has_expected_structure(self) -> None:
        """Verify the PipelineResult dataclass has the expected fields."""
        result = PipelineResult(
            input=None,
            organized=None,
            plan=None,
            tool_actions=None,
            errors=[],
            trace_id="abc123",
            trace_file=None,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
        )
        assert result.trace_id == "abc123"
        assert result.input is None
        assert result.organized is None
        assert result.plan is None
        assert result.tool_actions is None
        assert result.errors == []
        assert result.has_errors is False

    def test_pipeline_result_with_errors(self) -> None:
        result = PipelineResult(
            input=None,
            organized=None,
            plan=None,
            tool_actions=None,
            errors=[
                PipelineError(
                    step="organizer",
                    message="LLM not configured",
                    error_type="llm_not_configured",
                ),
            ],
            trace_id="abc123",
            trace_file=None,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
        )
        assert result.has_errors is True
        assert len(result.errors) == 1
        assert result.errors[0].step == "organizer"
        assert result.errors[0].error_type == "llm_not_configured"


class TestUIModuleImports:
    """Verify the UI package is importable."""

    def test_ui_package_imports(self) -> None:
        from idea_to_action.ui import __doc__ as ui_doc
        assert ui_doc is not None

    def test_app_module_imports(self) -> None:
        import idea_to_action.ui.app as app_module
        assert app_module._init_session_state is not None
        assert app_module._approve_action is not None
        assert app_module._reject_action is not None
        assert app_module._render_tool_actions is not None

    def test_format_execution_result_message_for_gmail_draft(self) -> None:
        from idea_to_action.ui.app import _format_execution_result_message

        message = _format_execution_result_message(
            {
                "status": "created",
                "gmail_draft_id": "draft_123",
                "gmail_message_id": "msg_123",
                "email_to": "person@example.com",
                "email_subject": "Hello",
            }
        )

        assert "Gmail draft created" in message
        assert "draft_123" in message
        assert "person@example.com" in message
        assert "Hello" in message
