"""Central configuration for idea-to-action.

All config values are loaded from environment variables with sensible defaults.
No secrets, API keys, or tokens are stored in this file.
"""

import os

# LLM Provider
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Storage
DATA_DIR = os.environ.get("I2A_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))

# Tracing
TRACES_DIR = os.environ.get("I2A_TRACES_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "traces"))

# Eval
EVALS_DIR = os.environ.get("I2A_EVALS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "evals"))

# Reports
REPORTS_DIR = os.environ.get("I2A_REPORTS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports"))

# Project root (used for credentials file default path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Google Calendar
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "I2A_GOOGLE_CREDENTIALS",
    os.path.join(_PROJECT_ROOT, "client_secret.json"),
)
GOOGLE_TOKEN_PATH = os.environ.get(
    "I2A_GOOGLE_TOKEN",
    os.path.join(DATA_DIR, "google_token.json"),
)
TIMEZONE = os.environ.get("I2A_TIMEZONE", "Asia/Ho_Chi_Minh")


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    for d in (DATA_DIR, TRACES_DIR, EVALS_DIR, REPORTS_DIR):
        os.makedirs(d, exist_ok=True)
