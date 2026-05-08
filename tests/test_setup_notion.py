import builtins
import os
import runpy
import sys
import types
from pathlib import Path


def test_setup_accepts_database_response_with_data_sources(monkeypatch, tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "setup_notion.py"
    env_path = Path(__file__).resolve().parents[1] / ".env"
    original_env = env_path.read_text() if env_path.exists() else None
    original_notion_key = os.environ.get("NOTION_API_KEY")
    original_notion_db = os.environ.get("NOTION_DATABASE_ID")

    calls = []

    class FakeDatabases:
        def retrieve(self, database_id):
            return {
                "title": [{"plain_text": "New database"}],
                "properties": {},
                "data_sources": [{"id": "source-id"}],
            }

        def update(self, database_id, properties):
            calls.append(("database", database_id, properties))
            return {}

    class FakeDataSources:
        def retrieve(self, data_source_id):
            return {"properties": {"Name": {"type": "title"}}}

        def update(self, data_source_id, properties):
            calls.append(("data_source", data_source_id, properties))
            return {}

    class FakeClient:
        def __init__(self, auth):
            self.databases = FakeDatabases()
            self.data_sources = FakeDataSources()

    fake_errors = types.ModuleType("notion_client.errors")
    fake_errors.APIResponseError = type("APIResponseError", (Exception,), {})
    fake_notion = types.ModuleType("notion_client")
    fake_notion.Client = FakeClient

    monkeypatch.setitem(sys.modules, "notion_client", fake_notion)
    monkeypatch.setitem(sys.modules, "notion_client.errors", fake_errors)
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": {
            "Paste your secret here: ": "secret",
            "Paste URL or database ID here: ": "264c3e246e0c44fb91987c8948bd0ec4",
            "Press Enter once you've done this...": "",
        }[prompt],
    )
    monkeypatch.chdir(script_path.parents[1])

    try:
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        if original_env is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(original_env)

        if original_notion_key is None:
            os.environ.pop("NOTION_API_KEY", None)
        else:
            os.environ["NOTION_API_KEY"] = original_notion_key

        if original_notion_db is None:
            os.environ.pop("NOTION_DATABASE_ID", None)
        else:
            os.environ["NOTION_DATABASE_ID"] = original_notion_db

    assert [call[0] for call in calls] == ["data_source", "data_source", "data_source"]
    assert all(call[1] == "source-id" for call in calls)
    assert env_path.read_text() == original_env
