"""Tests for F011 - Storage layer."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from idea_to_action.storage.manager import (
    IntegrityError,
    NotFoundError,
    StorageError,
    StorageManager,
)


@pytest.fixture
def storage() -> StorageManager:
    """Create a StorageManager with a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield StorageManager(base_dir=tmp)


class TestSaveAndLoad:
    def test_save_and_load_organized_idea(self, storage: StorageManager) -> None:
        data = {
            "cleaned_summary": "Cần chuẩn bị presentation.",
            "categories": ["work"],
            "confidence": 0.9,
        }
        storage.save("idea-001", "organized_ideas", data)
        record = storage.load("idea-001", "organized_ideas")
        assert record["id"] == "idea-001"
        assert record["type"] == "organized_ideas"
        assert record["data"] == data
        assert "checksum" in record
        assert "created_at" in record

    def test_save_and_load_action_plan(self, storage: StorageManager) -> None:
        data = {
            "summary": "Plan for presentation.",
            "actions": [
                {"action_type": "create_task", "title": "Làm slide"}
            ],
        }
        storage.save("plan-001", "action_plans", data)
        record = storage.load("plan-001", "action_plans")
        assert record["data"]["summary"] == "Plan for presentation."
        assert len(record["data"]["actions"]) == 1

    def test_save_overwrites_existing(self, storage: StorageManager) -> None:
        storage.save("idea-001", "organized_ideas", {"version": 1})
        storage.save("idea-001", "organized_ideas", {"version": 2})
        record = storage.load("idea-001", "organized_ideas")
        assert record["data"]["version"] == 2

    def test_load_nonexistent_raises(self, storage: StorageManager) -> None:
        with pytest.raises(NotFoundError):
            storage.load("no-such-id", "organized_ideas")

    def test_load_wrong_type_raises(self, storage: StorageManager) -> None:
        storage.save("idea-001", "organized_ideas", {"data": "x"})
        with pytest.raises(NotFoundError):
            storage.load("idea-001", "action_plans")


class TestListAll:
    def test_list_all_empty(self, storage: StorageManager) -> None:
        assert storage.list_all("organized_ideas") == []

    def test_list_all_returns_all_records(self, storage: StorageManager) -> None:
        storage.save("a", "organized_ideas", {"n": 1})
        storage.save("b", "organized_ideas", {"n": 2})
        storage.save("c", "organized_ideas", {"n": 3})
        results = storage.list_all("organized_ideas")
        assert len(results) == 3
        ids = {r["id"] for r in results}
        assert ids == {"a", "b", "c"}


class TestDelete:
    def test_delete_existing(self, storage: StorageManager) -> None:
        storage.save("idea-001", "organized_ideas", {"data": "x"})
        assert storage.delete("idea-001", "organized_ideas") is True
        with pytest.raises(NotFoundError):
            storage.load("idea-001", "organized_ideas")

    def test_delete_nonexistent_returns_false(self, storage: StorageManager) -> None:
        assert storage.delete("no-such-id", "organized_ideas") is False

    def test_delete_only_removes_target(self, storage: StorageManager) -> None:
        storage.save("a", "organized_ideas", {"n": 1})
        storage.save("b", "organized_ideas", {"n": 2})
        storage.delete("a", "organized_ideas")
        results = storage.list_all("organized_ideas")
        assert len(results) == 1
        assert results[0]["id"] == "b"


class TestExists:
    def test_exists_true(self, storage: StorageManager) -> None:
        storage.save("idea-001", "organized_ideas", {"data": "x"})
        assert storage.exists("idea-001", "organized_ideas") is True

    def test_exists_false(self, storage: StorageManager) -> None:
        assert storage.exists("no-such-id", "organized_ideas") is False


class TestDataIntegrity:
    def test_valid_record_passes_integrity(self, storage: StorageManager) -> None:
        """Normal save/load cycle preserves data integrity."""
        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        storage.save("idea-001", "organized_ideas", data)
        record = storage.load("idea-001", "organized_ideas")
        assert record["data"] == data

    def test_tampered_file_rejected(self, storage: StorageManager) -> None:
        """Directly modifying the JSONL data without updating checksum must be caught."""
        storage.save("idea-001", "organized_ideas", {"approved": False})
        file_path = storage._file_path("organized_ideas")

        # Tamper with the data field without updating the checksum
        lines = file_path.read_text().strip().split("\n")
        record = json.loads(lines[0])
        record["data"]["approved"] = True  # Tampered!
        file_path.write_text(json.dumps(record, ensure_ascii=False) + "\n")

        with pytest.raises(IntegrityError, match="Checksum mismatch"):
            storage.load("idea-001", "organized_ideas")

    def test_list_all_detects_tampered_record(self, storage: StorageManager) -> None:
        storage.save("good", "organized_ideas", {"data": "ok"})
        storage.save("bad", "organized_ideas", {"data": "will be tampered"})

        file_path = storage._file_path("organized_ideas")
        lines = file_path.read_text().strip().split("\n")
        # Find and tamper with the "bad" record
        for i, line in enumerate(lines):
            record = json.loads(line)
            if record["id"] == "bad":
                record["data"]["data"] = "TAMPERED"
                lines[i] = json.dumps(record, ensure_ascii=False)
                break
        file_path.write_text("\n".join(lines) + "\n")

        with pytest.raises(IntegrityError, match="Checksum mismatch"):
            storage.list_all("organized_ideas")

    def test_corrupted_json_rejected(self, storage: StorageManager) -> None:
        storage.save("idea-001", "organized_ideas", {"data": "ok"})
        file_path = storage._file_path("organized_ideas")
        # Write garbage
        file_path.write_text("this is not valid json\n")

        with pytest.raises(StorageError, match="Malformed JSON"):
            storage.load("idea-001", "organized_ideas")

    def test_empty_file_returns_empty_list(self, storage: StorageManager) -> None:
        file_path = storage._file_path("organized_ideas")
        file_path.write_text("")
        assert storage.list_all("organized_ideas") == []


class TestChecksum:
    def test_checksum_is_deterministic(self) -> None:
        a = StorageManager._compute_checksum({"a": 1, "b": 2})
        b = StorageManager._compute_checksum({"b": 2, "a": 1})
        assert a == b  # sort_keys ensures consistency

    def test_different_data_different_checksum(self) -> None:
        a = StorageManager._compute_checksum({"data": 1})
        b = StorageManager._compute_checksum({"data": 2})
        assert a != b


class TestAtomicWrite:
    def test_tmp_file_cleaned_up(self, storage: StorageManager) -> None:
        storage.save("idea-001", "organized_ideas", {"data": "ok"})
        tmp_files = list(storage.base_dir.glob("*.tmp"))
        assert len(tmp_files) == 0
