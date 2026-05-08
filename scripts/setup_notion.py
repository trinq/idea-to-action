#!/usr/bin/env python3
"""One-time Notion setup for idea-to-action.

Walks you through configuring the Notion task manager integration.
Run once:
    python3 scripts/setup_notion.py
"""

import os
import re
import sys


def _extract_database_id(raw: str) -> str | None:
    """Extract a 32-char hex database ID from various input formats.

    Handles:
    - Full URL: https://www.notion.so/workspace/Title-264c3e246e0c44fb91987c8948bd0ec4?v=...
    - URL with &t= params: 264c3e246e0c44fb91987c8948bd0ec4&t=359b01bf...
    - Raw hex: 264c3e246e0c44fb91987c8948bd0ec4
    - UUID with dashes: 264c3e24-6e0c-44fb-9198-7c8948bd0ec4

    Returns the ID in UUID format with dashes, or None if not found.
    """
    # Strip URL parameters (?v=... and &t=...)
    raw = raw.split("?")[0].split("&")[0].strip().rstrip("/")

    # If it's a URL, extract the last path segment
    if "/" in raw:
        raw = raw.split("/")[-1]

    # If there's a title prefix (e.g. "My-Tasks-264c3e24..."), take the last 32 hex chars
    hex_match = re.search(r"([0-9a-f]{32})$", raw.replace("-", ""), re.IGNORECASE)
    if hex_match:
        hex_id = hex_match.group(1)
        # Format as UUID with dashes: 8-4-4-4-12
        return f"{hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}"

    # Try if it's already a valid UUID with dashes
    uuid_match = re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        raw,
        re.IGNORECASE,
    )
    if uuid_match:
        return raw

    return None


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
    print("  Option A: Paste the FULL URL of your Notion database")
    print("  Option B: Paste just the database ID (32 hex characters)\n")
    print("  Example URL: https://www.notion.so/workspace/My-Tasks-264c3e246e0c44fb91987c8948bd0ec4?v=...\n")
    raw_input = input("Paste URL or database ID here: ").strip()
    if not raw_input:
        print("No database ID provided. Aborting.", file=sys.stderr)
        sys.exit(1)

    database_id = _extract_database_id(raw_input)
    if not database_id:
        print(f"Could not extract a valid database ID from: {raw_input}", file=sys.stderr)
        print("Expected: 32 hex characters (e.g. 264c3e246e0c44fb91987c8948bd0ec4)", file=sys.stderr)
        sys.exit(1)

    print(f"  Extracted database ID: {database_id}")

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
        db_title = db.get('title', [{}])[0].get('plain_text', 'Untitled')
        print(f"  Connected to database: {db_title}")
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
    data_sources = db.get("data_sources") or []
    if data_sources:
        schema_target = client.data_sources
        schema_id = data_sources[0]["id"]
        schema = client.data_sources.retrieve(data_source_id=schema_id)
    else:
        schema_target = client.databases
        schema_id = database_id
        schema = db

    existing_props = schema.get("properties", {})
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
                if data_sources:
                    schema_target.update(
                        data_source_id=schema_id,
                        properties={prop_name: prop_config},
                    )
                else:
                    schema_target.update(
                        database_id=schema_id,
                        properties={prop_name: prop_config},
                    )
                print(f"  Added '{prop_name}' property")
            except APIResponseError as e:
                print(f"  Error: Could not add '{prop_name}': {e}", file=sys.stderr)
                print("  Check that this is a Notion database and that your integration has edit access.", file=sys.stderr)
                sys.exit(1)
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
