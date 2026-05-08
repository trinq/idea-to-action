#!/usr/bin/env python3
"""One-time Gmail OAuth2 authentication for idea-to-action.

Run this once to authorize Gmail draft access:
    python3 scripts/auth_gmail.py

Prerequisites:
    - gmail_client_secret.json in the project root (download from Google Cloud Console)
    - Gmail API enabled in your GCP project
"""

import sys

from idea_to_action.tools.gmail_draft import GmailDraftTool


def main() -> None:
    try:
        GmailDraftTool.run_auth_flow()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "\nTo get a gmail_client_secret.json file:\n"
            "1. Go to https://console.cloud.google.com/apis/credentials\n"
            "2. Create an OAuth 2.0 Client ID (Desktop application)\n"
            "3. Download the JSON and save it as 'gmail_client_secret.json' in the project root\n"
            "4. Make sure the Gmail API is enabled in your GCP project",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
