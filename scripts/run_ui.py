#!/usr/bin/env python3
"""Convenience launcher for the idea-to-action Streamlit UI."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    app_path = Path(__file__).parent.parent / "src" / "idea_to_action" / "ui" / "app.py"
    if not app_path.exists():
        print(f"Error: App not found at {app_path}", file=sys.stderr)
        sys.exit(1)

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        check=False,
    )


if __name__ == "__main__":
    main()
