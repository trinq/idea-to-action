#!/usr/bin/env python3
"""One-time Google OAuth2 authentication for idea-to-action.

Run this once to authorize Google Calendar access:
    python3 scripts/auth_google.py

Prerequisites:
    - client_secret.json in the project root (download from Google Cloud Console)
    - Google Calendar API enabled in your GCP project
"""

import sys

from idea_to_action.tools.google_calendar import GoogleCalendarTool


def main() -> None:
    try:
        GoogleCalendarTool.run_auth_flow()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "\nTo get a client_secret.json file:\n"
            "1. Go to https://console.cloud.google.com/apis/credentials\n"
            "2. Create an OAuth 2.0 Client ID (Desktop application)\n"
            "3. Download the JSON and save it as 'client_secret.json' in the project root",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
