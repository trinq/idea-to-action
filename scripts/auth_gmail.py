#!/usr/bin/env python3
"""One-time Gmail OAuth setup for idea-to-action."""

from idea_to_action.tools.gmail_draft import GmailDraftTool


if __name__ == "__main__":
    GmailDraftTool.run_auth_flow()
