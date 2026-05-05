"""JSONL-based storage manager with checksum integrity verification."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from idea_to_action.config import DATA_DIR


class StorageError(Exception):
    """Base error for storage operations."""


class IntegrityError(StorageError):
    """Data integrity check failed — file may be corrupted or tampered."""


class NotFoundError(StorageError):
    """Record not found."""


class StorageManager:
    """Simple JSONL storage manager.

    Each line is a JSON record: {"id", "type", "checksum", "created_at", "data"}.
    The checksum is SHA-256 of json.dumps(data, sort_keys=True).
    On load, checksum is verified to detect corruption or tampering.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir or DATA_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, record_type: str) -> Path:
        """Get the JSONL file path for a record type."""
        return self.base_dir / f"{record_type}.jsonl"

    @staticmethod
    def _compute_checksum(data: dict[str, Any]) -> str:
        """Compute SHA-256 checksum of JSON-serialized data."""
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _make_record(
        record_id: str,
        record_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a storage record with checksum."""
        return {
            "id": record_id,
            "type": record_type,
            "checksum": StorageManager._compute_checksum(data),
            "created_at": datetime.now(UTC).isoformat(),
            "data": data,
        }

    @staticmethod
    def _verify_record(record: dict[str, Any]) -> None:
        """Verify a loaded record's checksum. Raises IntegrityError on mismatch."""
        expected = record.get("checksum", "")
        actual = StorageManager._compute_checksum(record.get("data", {}))
        if expected != actual:
            raise IntegrityError(
                f"Checksum mismatch for record '{record.get('id', 'unknown')}': "
                f"expected {expected[:16]}..., got {actual[:16]}..."
            )

    def save(self, record_id: str, record_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Save a record to JSONL. Returns the full stored record.

        If a record with the same ID and type exists, it is overwritten.
        """
        record = self._make_record(record_id, record_type, data)
        file_path = self._file_path(record_type)

        # Read all existing records
        records = []
        if file_path.exists():
            records = self._read_all_raw(file_path)
            # Remove existing record with same ID
            records = [r for r in records if r.get("id") != record_id]

        records.append(record)
        self._write_all(file_path, records)
        return record

    def load(self, record_id: str, record_type: str) -> dict[str, Any]:
        """Load a record by ID and type. Raises NotFoundError if missing."""
        file_path = self._file_path(record_type)
        if not file_path.exists():
            raise NotFoundError(
                f"No storage file for type '{record_type}'. "
                f"Record '{record_id}' not found."
            )

        for record in self._read_all_raw(file_path):
            if record.get("id") == record_id:
                self._verify_record(record)
                return record

        raise NotFoundError(
            f"Record '{record_id}' not found in '{record_type}'."
        )

    def list_all(self, record_type: str) -> list[dict[str, Any]]:
        """List all records of a given type, with integrity verification."""
        file_path = self._file_path(record_type)
        if not file_path.exists():
            return []

        records = []
        for record in self._read_all_raw(file_path):
            self._verify_record(record)
            records.append(record)
        return records

    def delete(self, record_id: str, record_type: str) -> bool:
        """Delete a record by ID and type. Returns True if deleted, False if not found."""
        file_path = self._file_path(record_type)
        if not file_path.exists():
            return False

        records = self._read_all_raw(file_path)
        filtered = [r for r in records if r.get("id") != record_id]

        if len(filtered) == len(records):
            return False  # Not found

        self._write_all(file_path, filtered)
        return True

    def exists(self, record_id: str, record_type: str) -> bool:
        """Check if a record exists."""
        try:
            self.load(record_id, record_type)
            return True
        except (NotFoundError, IntegrityError):
            return False

    def _read_all_raw(self, file_path: Path) -> list[dict[str, Any]]:
        """Read all JSONL lines from a file. Skips blank lines."""
        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise StorageError(
                        f"Malformed JSON in {file_path}: {e}"
                    ) from e
        return records

    def _write_all(self, file_path: Path, records: list[dict[str, Any]]) -> None:
        """Write all records to a JSONL file atomically."""
        tmp_path = file_path.with_suffix(".jsonl.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            os.replace(tmp_path, file_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
