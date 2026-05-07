#!/usr/bin/env python3
"""One-time Notion setup for idea-to-action.

Walks you through configuring the Notion task manager integration.
Run once:
    python3 scripts/setup_notion.py
"""

import os
import sys


def main() -> None:
    print("=== Notion Setup for idea-to-action ===\n")

    # Step 1: API Key
    print("Step 1: Create a Notion integration")
    print("  1. Open https://www.notion.so/my-integrations")
    print("  2. Click 'New integration', name it, submit")
    print("  3. Copy the Internal Integration Secret\n")
    api_key = input("Paste your secret here: ").strip()
    if not api_key:
        print("No key provided. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Database ID
    print("\nStep 2: Get your database ID")
    print("  Open your Notion database in a browser. The URL looks like:")
    print("  https://www.notion.so/workspace/1a2b3c4d5e6f?v=...")
    print("  Copy the part before ?v= (e.g. 1a2b3c4d5e6f)\n")
    database_id = input("Paste your database ID here: ").strip()
    if not database_id:
        print("No database ID provided. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Step 3: Share database
    print("\nStep 3: Share the database with your integration")
    print("  Open your Notion database, click ... > Connections > Add connections")
    print(f"  Find your integration and add it.\n")
    input("Press Enter once you've done this...")

    # Step 4: Auto-setup database properties
    print("\nStep 4: Setting up database properties...")
    os.environ["NOTION_API_KEY"] = api_key
    os.environ["NOTION_DATABASE_ID"] = database_id

    from notion_client import Client
    from notion_client.errors import APIResponseError

    client = Client(auth=api_key)

    # Verify connection
    try:
        db = client.databases.retrieve(database_id=database_id)
        print(f"  Connected to database: {db.get('title', [{}])[0].get('plain_text', 'Untitled')}")
    except APIResponseError as e:
        if e.status == 401:
            print("  Error: Invalid API key.", file=sys.stderr)
            sys.exit(1)
        elif e.status == 404:
            print("  Error: Database not found. Check the ID and that you shared it with the integration.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"  Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Add required properties if missing
    existing_props = db.get("properties", {})
    needed = {
        "Priority": {"select": {"options": [
            {"name": "high", "color": "red"},
            {"name": "medium", "color": "yellow"},
            {"name": "low", "color": "green"},
        ]}},
        "Effort": {"select": {"options": [
            {"name": "small", "color": "green"},
            {"name": "medium", "color": "yellow"},
            {"name": "large", "color": "red"},
        ]}},
        "Due Date": {"date": {}},
    }

    for prop_name, prop_config in needed.items():
        if prop_name not in existing_props:
            try:
                client.databases.update(
                    database_id=database_id,
                    properties={prop_name: prop_config},
                )
                print(f"  Added '{prop_name}' property")
            except APIResponseError as e:
                print(f"  Warning: Could not add '{prop_name}': {e}")
        else:
            print(f"  '{prop_name}' already exists")

    # Step 5: Save to .env
    print("\nStep 5: Saving environment variables...")
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    env_lines = []
    if os.path.exists(env_file):
        with open(env_file) as f:
            env_lines = f.read().splitlines()

    # Update or add NOTION vars
    updated_key = False
    updated_db = False
    for i, line in enumerate(env_lines):
        if line.startswith("NOTION_API_KEY="):
            env_lines[i] = f"NOTION_API_KEY={api_key}"
            updated_key = True
        elif line.startswith("NOTION_DATABASE_ID="):
            env_lines[i] = f"NOTION_DATABASE_ID={database_id}"
            updated_db = True

    if not updated_key:
        env_lines.append(f"NOTION_API_KEY={api_key}")
    if not updated_db:
        env_lines.append(f"NOTION_DATABASE_ID={database_id}")

    with open(env_file, "w") as f:
        f.write("\n".join(env_lines) + "\n")

    print(f"  Saved to {env_file}")
    print(f"  Run: source {env_file}  (or restart your terminal)")

    # Done
    print("\n=== Setup complete ===")
    print("Run: streamlit run src/idea_to_action/ui/app.py")
    print("Approve a task action and it'll land in your Notion database.")


if __name__ == "__main__":
    main()
