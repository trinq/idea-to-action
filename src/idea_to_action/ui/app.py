"""Streamlit UI for idea-to-action.

Paste raw notes, run the pipeline, review organized output,
and approve/reject draft tool actions.
"""

import streamlit as st

from idea_to_action.agent.llm_provider import LLMConfigError, create_llm
from idea_to_action.pipeline import run_pipeline
from idea_to_action.schemas.tool_actions import ActionPlan, ApprovalStatus, ToolAction
from idea_to_action.tools.registry import ToolRegistry


def _init_session_state() -> None:
    """Initialize session state keys if not already set."""
    defaults = {
        "pipeline_result": None,
        "action_states": {},
        "execution_results": {},
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _get_llm():
    """Try to create an LLM instance. Returns None with a warning if unavailable."""
    try:
        return create_llm()
    except LLMConfigError as e:
        st.warning(f"LLM not available: {e}")
        return None


def _render_organized_ideas() -> None:
    """Render the organized ideas section (collapsible)."""
    result = st.session_state.pipeline_result
    organized = result.organized
    if organized is None:
        return

    with st.expander("Organized Ideas", expanded=False):
        st.subheader(f"Summary: {organized.cleaned_summary}")
        st.metric("Confidence", f"{organized.confidence:.0%}")

        st.write("**Categories:**", ", ".join(organized.categories))

        if organized.actionable_items:
            st.write(f"**Actionable ({len(organized.actionable_items)}):**")
            for idea in organized.actionable_items:
                st.markdown(f"- {idea.cleaned_text} _(category: {idea.category})_")

        if organized.vague_items:
            st.write(f"**Vague ({len(organized.vague_items)}):**")
            for idea in organized.vague_items:
                st.markdown(f"- {idea.cleaned_text} _(category: {idea.category})_")

        if organized.missing_context:
            st.write("**Missing Context:**")
            for ctx in organized.missing_context:
                st.markdown(f"- *{ctx.question}* (re: {ctx.related_to})")

        st.caption(f"{len(organized.ideas)} ideas extracted")


def _render_action_plan() -> None:
    """Render the action plan section (collapsible)."""
    result = st.session_state.pipeline_result
    plan = result.plan
    if plan is None:
        return

    with st.expander("Action Plan", expanded=False):
        st.write(f"**Summary:** {plan.summary}")

        if plan.tasks:
            st.write(f"**Tasks ({len(plan.tasks)}):**")
            for task in plan.tasks:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    task.priority.value, ""
                )
                st.markdown(
                    f"- {priority_emoji} **{task.title}** "
                    f"_(priority: {task.priority.value}, effort: {task.effort.value})_"
                )
                if task.description:
                    st.caption(f"  {task.description}")

        if plan.calendar_events:
            st.write(f"**Calendar Events ({len(plan.calendar_events)}):**")
            for event in plan.calendar_events:
                st.markdown(f"- **{event.title}** ({event.duration_minutes} min)")
                if event.suggested_date:
                    st.caption(f"  Date: {event.suggested_date}")

        if plan.missing_context:
            st.write("**Missing Context:**")
            for ctx in plan.missing_context:
                st.markdown(f"- {ctx}")


def _approve_action(idx: int, action: ToolAction) -> None:
    """Approve an action and execute it via the ToolRegistry."""
    approved = action.model_copy(update={
        "approval_status": ApprovalStatus.APPROVED,
        "approved_by": "user",
    })
    st.session_state.action_states[str(idx)] = "approved"

    registry = ToolRegistry()
    try:
        exec_result = registry.execute(approved)
        st.session_state.execution_results[str(idx)] = {
            "success": True,
            "result": exec_result,
        }
    except Exception as e:
        st.session_state.execution_results[str(idx)] = {
            "success": False,
            "error": str(e),
        }


def _reject_action(idx: int, action: ToolAction) -> None:
    """Reject an action — no execution."""
    st.session_state.action_states[str(idx)] = "rejected"
    st.session_state.execution_results[str(idx)] = {
        "success": True,
        "result": {"status": "rejected", "action_type": action.action_type.value},
    }


def _render_tool_actions() -> None:
    """Render the draft tool actions with approve/reject buttons."""
    result = st.session_state.pipeline_result
    tool_actions = result.tool_actions
    if tool_actions is None or not tool_actions.actions:
        return

    st.subheader("Draft Tool Actions")

    # Show Google Calendar connection status
    registry = ToolRegistry()
    if registry.is_google_calendar_connected:
        st.success("Google Calendar: Connected")
    else:
        st.caption("Google Calendar: Not configured (using fake tool)")

    if registry.is_notion_task_manager_connected:
        st.success("Notion: Connected")
    else:
        st.caption("Notion: Not configured (using fake tool)")

    st.write(f"{len(tool_actions.actions)} action(s) pending approval.")

    for idx, action in enumerate(tool_actions.actions):
        state_key = str(idx)
        current_state = st.session_state.action_states.get(state_key, "pending")

        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.write(f"**{action.action_type.value}**")
                st.json(action.action_data)
                st.caption(
                    f"Drafted: {action.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
                    if action.created_at else ""
                )

            with col2:
                if current_state == "pending":
                    st.button(
                        "Approve",
                        key=f"approve_{idx}",
                        type="primary",
                        on_click=_approve_action,
                        args=(idx, action),
                    )

            with col3:
                if current_state == "pending":
                    st.button(
                        "Reject",
                        key=f"reject_{idx}",
                        on_click=_reject_action,
                        args=(idx, action),
                    )

            if current_state != "pending":
                st.info(f"Status: **{current_state}**")

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


def _render_trace_info() -> None:
    """Render trace ID and file path."""
    result = st.session_state.pipeline_result
    st.divider()
    st.caption(f"Trace ID: `{result.trace_id}`")
    if result.trace_file:
        st.caption(f"Trace file: `{result.trace_file}`")


def main() -> None:
    """Main Streamlit app entry point."""
    st.set_page_config(page_title="Idea to Action", page_icon="", layout="wide")
    st.title("Idea to Action")
    st.write("Paste your raw notes below and click **Process** to organize them into actionable plans.")

    _init_session_state()

    # Step 1: Input area
    raw_text = st.text_area(
        "Raw Notes",
        placeholder="Paste your notes, bullet points, reminders, or meeting notes here...",
        height=200,
    )
    process_clicked = st.button("Process", type="primary")

    if process_clicked and raw_text.strip():
        with st.spinner("Running pipeline..."):
            llm = _get_llm()
            result = run_pipeline(raw_text, llm, source="ui")
            st.session_state.pipeline_result = result
            st.session_state.action_states = {}
            st.session_state.execution_results = {}
    elif process_clicked and not raw_text.strip():
        st.error("Please enter some text before processing.")

    result = st.session_state.pipeline_result
    if result is None:
        return

    # Step 2: Status / Errors
    if result.has_errors:
        st.divider()
        for err in result.errors:
            if err.error_type == "llm_not_configured":
                st.warning(
                    f"LLM not available — **{err.step}** step skipped. "
                    "Set DEEPSEEK_API_KEY in your environment to enable LLM features."
                )
            else:
                st.error(f"**{err.step}** error: {err.message}")

    if result.errors and all(e.error_type == "llm_not_configured" for e in result.errors):
        st.info(
            "The pipeline completed input validation and tool drafting "
            "(deterministic steps) but skipped LLM-dependent steps. "
            "Set DEEPSEEK_API_KEY to get full results."
        )

    # Step 3: Organized Ideas
    _render_organized_ideas()

    # Step 4: Action Plan
    _render_action_plan()

    # Step 5: Draft Tool Actions (approval gate)
    _render_tool_actions()

    # Step 6: Trace info
    _render_trace_info()


if __name__ == "__main__":
    main()
