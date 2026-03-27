"""
SQLite backup manager — automated backups with integrity verification.

Creates online backups using the sqlite3 backup API, verifies integrity,
and manages retention (keeping only the most recent N backups per database).
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import DATA_DIR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackupResult:
    """Immutable record of a completed backup operation."""

    db_name: str
    backup_path: Path
    size_bytes: int
    duration_ms: float
    integrity_ok: bool
    timestamp: str


class BackupManager:
    """Manage automated SQLite database backups.

    Parameters
    ----------
    data_dir:
        Directory containing the SQLite database files.
    backup_dir:
        Directory for storing backups. Defaults to ``data_dir / "backups"``.
    max_backups:
        Maximum number of backup files to retain per database.
    """

    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        backup_dir: Optional[Path] = None,
        max_backups: int = 5,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._backup_dir = Path(backup_dir) if backup_dir else self._data_dir / "backups"
        self._max_backups = max_backups
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def backup_database(self, db_path: Path) -> BackupResult:
        """Create a backup of a single SQLite database.

        Uses ``sqlite3.Connection.backup()`` for a safe online backup,
        then runs ``PRAGMA integrity_check`` on the copy.

        Raises
        ------
        FileNotFoundError
            If *db_path* does not exist.
        sqlite3.Error
            If the backup or integrity check fails at the SQLite level.
        """
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        db_name = db_path.stem
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{db_name}_{ts}.db"
        backup_path = self._backup_dir / backup_filename

        start = time.monotonic()

        try:
            source = sqlite3.connect(str(db_path))
            dest = sqlite3.connect(str(backup_path))
            try:
                source.backup(dest)
            finally:
                dest.close()
                source.close()
        except sqlite3.Error:
            # Clean up partial backup file on failure.
            if backup_path.exists():
                backup_path.unlink()
            raise

        duration_ms = (time.monotonic() - start) * 1000
        size_bytes = backup_path.stat().st_size
        integrity_ok = self._check_integrity(backup_path)

        if not integrity_ok:
            logger.warning(
                "Backup integrity check failed for %s at %s",
                db_name,
                backup_path,
            )

        result = BackupResult(
            db_name=db_name,
            backup_path=backup_path,
            size_bytes=size_bytes,
            duration_ms=round(duration_ms, 2),
            integrity_ok=integrity_ok,
            timestamp=ts,
        )

        self.cleanup_old_backups(db_name)

        logger.info(
            "Backup complete: %s (%.1f KB, %.0f ms, integrity=%s)",
            backup_path.name,
            size_bytes / 1024,
            duration_ms,
            integrity_ok,
        )
        return result

    def backup_all(self) -> list[BackupResult]:
        """Back up every ``.db`` file found in *data_dir*."""
        results: list[BackupResult] = []
        db_files = sorted(self._data_dir.glob("*.db"))

        if not db_files:
            logger.info("No .db files found in %s", self._data_dir)
            return results

        for db_path in db_files:
            try:
                result = self.backup_database(db_path)
                results.append(result)
            except Exception:
                logger.exception("Failed to backup %s", db_path.name)

        return results

    def list_backups(self) -> list[dict[str, object]]:
        """List existing backup files with metadata."""
        backups: list[dict[str, object]] = []
        for path in sorted(self._backup_dir.glob("*.db")):
            stat = path.stat()
            backups.append({
                "filename": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        return backups

    def restore(self, backup_path: Path, target_path: Path) -> bool:
        """Restore a database from a backup file.

        Validates backup integrity before copying. Returns ``True`` on
        success, ``False`` if the backup fails the integrity check.

        Raises
        ------
        FileNotFoundError
            If *backup_path* does not exist.
        """
        backup_path = Path(backup_path)
        target_path = Path(target_path)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        if not self._check_integrity(backup_path):
            logger.error(
                "Restore aborted — backup failed integrity check: %s",
                backup_path,
            )
            return False

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(backup_path), str(target_path))

        logger.info("Restored %s -> %s", backup_path.name, target_path)
        return True

    def cleanup_old_backups(self, db_name: str) -> int:
        """Remove old backups for *db_name*, keeping only *max_backups*.

        Returns the number of backups removed.
        """
        pattern = f"{db_name}_*.db"
        existing = sorted(
            self._backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        to_remove = existing[self._max_backups:]
        for path in to_remove:
            path.unlink()
            logger.debug("Removed old backup: %s", path.name)

        return len(to_remove)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_integrity(db_path: Path) -> bool:
        """Run ``PRAGMA integrity_check`` and return ``True`` if it passes."""
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                return result is not None and result[0] == "ok"
            finally:
                conn.close()
        except sqlite3.Error:
            logger.exception("Integrity check error for %s", db_path)
            return False
