"""Tests for backend.core.backup_manager — SQLite backup management."""

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.backup_manager import BackupManager, BackupResult


def _create_test_db(path: Path, table: str = "items") -> None:
    """Create a minimal SQLite database with one table and sample row."""
    conn = sqlite3.connect(str(path))
    conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute(f"INSERT INTO {table} (value) VALUES ('hello')")
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# backup_database — single DB backup
# ------------------------------------------------------------------


class TestBackupDatabase:
    def test_creates_backup_file(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        result = mgr.backup_database(db_path)

        assert isinstance(result, BackupResult)
        assert result.backup_path.exists()
        assert result.db_name == "test"
        assert result.integrity_ok is True
        assert result.size_bytes > 0
        assert result.duration_ms >= 0

    def test_backup_is_valid_sqlite(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        result = mgr.backup_database(db_path)

        # The backup should contain the same data as the original
        conn = sqlite3.connect(str(result.backup_path))
        rows = conn.execute("SELECT value FROM items").fetchall()
        conn.close()
        assert rows == [("hello",)]

    def test_nonexistent_db_raises_file_not_found(self, tmp_path: Path):
        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        with pytest.raises(FileNotFoundError, match="Database not found"):
            mgr.backup_database(tmp_path / "no_such.db")

    def test_backup_result_is_immutable(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        result = mgr.backup_database(db_path)

        with pytest.raises(AttributeError):
            result.db_name = "other"


# ------------------------------------------------------------------
# backup_all — bulk backup
# ------------------------------------------------------------------


class TestBackupAll:
    def test_backs_up_multiple_dbs(self, tmp_path: Path):
        _create_test_db(tmp_path / "alpha.db")
        _create_test_db(tmp_path / "beta.db")

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        results = mgr.backup_all()

        assert len(results) == 2
        names = {r.db_name for r in results}
        assert names == {"alpha", "beta"}
        assert all(r.integrity_ok for r in results)

    def test_no_db_files_returns_empty(self, tmp_path: Path):
        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        results = mgr.backup_all()
        assert results == []

    def test_continues_on_failure(self, tmp_path: Path):
        _create_test_db(tmp_path / "good.db")
        # Create a non-db file with .db extension to cause error
        bad_path = tmp_path / "bad.db"
        bad_path.write_text("not a database")

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        results = mgr.backup_all()

        # "bad.db" may still produce a result (sqlite3 copies bytes regardless)
        # but good.db should always succeed
        good_results = [r for r in results if r.db_name == "good"]
        assert len(good_results) == 1
        assert good_results[0].integrity_ok is True


# ------------------------------------------------------------------
# list_backups
# ------------------------------------------------------------------


class TestListBackups:
    def test_lists_backup_files_with_metadata(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        mgr.backup_database(db_path)

        backups = mgr.list_backups()
        assert len(backups) == 1
        entry = backups[0]
        assert "filename" in entry
        assert "path" in entry
        assert "size_bytes" in entry
        assert "modified" in entry
        assert entry["filename"].startswith("test_")
        assert entry["size_bytes"] > 0

    def test_empty_when_no_backups(self, tmp_path: Path):
        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        assert mgr.list_backups() == []


# ------------------------------------------------------------------
# restore
# ------------------------------------------------------------------


class TestRestore:
    def test_restore_creates_working_copy(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        result = mgr.backup_database(db_path)

        restore_target = tmp_path / "restored.db"
        ok = mgr.restore(result.backup_path, restore_target)

        assert ok is True
        assert restore_target.exists()

        conn = sqlite3.connect(str(restore_target))
        rows = conn.execute("SELECT value FROM items").fetchall()
        conn.close()
        assert rows == [("hello",)]

    def test_restore_nonexistent_backup_raises(self, tmp_path: Path):
        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        with pytest.raises(FileNotFoundError, match="Backup not found"):
            mgr.restore(tmp_path / "nope.db", tmp_path / "out.db")

    def test_restore_creates_parent_directories(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        result = mgr.backup_database(db_path)

        deep_target = tmp_path / "sub" / "dir" / "restored.db"
        ok = mgr.restore(result.backup_path, deep_target)

        assert ok is True
        assert deep_target.exists()

    def test_restore_fails_on_corrupt_backup(self, tmp_path: Path):
        corrupt = tmp_path / "backups" / "corrupt.db"
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_text("not a real database")

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        ok = mgr.restore(corrupt, tmp_path / "out.db")
        assert ok is False


# ------------------------------------------------------------------
# cleanup_old_backups
# ------------------------------------------------------------------


class TestCleanupOldBackups:
    def test_keeps_only_max_backups(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=2)
        backup_dir = tmp_path / "backups"

        # Create 4 backups manually with distinct names
        for i in range(4):
            p = backup_dir / f"test_2024010{i}_000000.db"
            _create_test_db(p)

        mgr.cleanup_old_backups("test")

        backups = list(backup_dir.glob("test_*.db"))
        assert len(backups) == 2

    def test_returns_removed_count(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=2)

        # Create 4 backups manually in the backup dir
        backup_dir = tmp_path / "backups"
        for i in range(4):
            p = backup_dir / f"test_2024010{i}_000000.db"
            _create_test_db(p)
            time.sleep(0.05)

        removed = mgr.cleanup_old_backups("test")
        assert removed == 2

    def test_no_removal_when_under_limit(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _create_test_db(db_path)

        mgr = BackupManager(data_dir=tmp_path, max_backups=5)
        mgr.backup_database(db_path)

        removed = mgr.cleanup_old_backups("test")
        assert removed == 0


# ------------------------------------------------------------------
# Backup directory creation
# ------------------------------------------------------------------


class TestBackupDirSetup:
    def test_default_backup_dir(self, tmp_path: Path):
        mgr = BackupManager(data_dir=tmp_path)
        assert mgr._backup_dir == tmp_path / "backups"
        assert mgr._backup_dir.exists()

    def test_custom_backup_dir(self, tmp_path: Path):
        custom = tmp_path / "my_backups"
        mgr = BackupManager(data_dir=tmp_path, backup_dir=custom)
        assert mgr._backup_dir == custom
        assert custom.exists()
