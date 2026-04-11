#!/bin/bash
# ROOT — Daily SQLite database backup script
# Uses SQLite's online backup API via Python for safe, consistent backups.
#
# Add to crontab: 0 3 * * * /home/user/ROOT/deploy/backup.sh
#
# Features:
#   - SQLite backup API (not file copy — safe even while ROOT is running)
#   - PRAGMA integrity_check on every backup
#   - Timestamped per-database backup files
#   - Retains last 7 daily backups, prunes older ones
#   - Full logging to backups/backup.log
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
ROOT_DIR="/home/user/ROOT"
DATA_DIR="${ROOT_DIR}/data"
BACKUP_DIR="${ROOT_DIR}/backups/daily"
LOG_FILE="${ROOT_DIR}/backups/backup.log"
KEEP_DAYS=7

# ─── Setup ───────────────────────────────────────────────────────────────────
mkdir -p "${BACKUP_DIR}"
mkdir -p "$(dirname "${LOG_FILE}")"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_TAG=$(date +%Y-%m-%d)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log "=========================================="
log "ROOT backup started — timestamp ${TIMESTAMP}"
log "=========================================="

# ─── Discover all .db files ──────────────────────────────────────────────────
DB_FILES=$(find "${DATA_DIR}" -maxdepth 1 -name "*.db" -type f | sort)
DB_COUNT=$(echo "${DB_FILES}" | wc -l)
log "Found ${DB_COUNT} databases to back up"

TOTAL_OK=0
TOTAL_FAIL=0

# ─── Backup each database using SQLite's backup API ─────────────────────────
for DB_PATH in ${DB_FILES}; do
    DB_NAME=$(basename "${DB_PATH}" .db)
    BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.db"

    log "  Backing up: ${DB_NAME}.db"

    # Use Python's sqlite3 module which wraps SQLite's backup API.
    # This is safe to run while the database is in use (WAL mode or not).
    BACKUP_RESULT=$(python3 -c "
import sqlite3, sys

src = None
dst = None
try:
    src = sqlite3.connect('${DB_PATH}')
    dst = sqlite3.connect('${BACKUP_FILE}')
    src.backup(dst)
    dst.close()
    dst = None
    src.close()
    src = None
    print('OK')
except Exception as e:
    print(f'BACKUP_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
finally:
    if dst:
        dst.close()
    if src:
        src.close()
" 2>&1) || true

    if echo "${BACKUP_RESULT}" | grep -q "BACKUP_ERROR"; then
        log "    FAILED backup for ${DB_NAME}: ${BACKUP_RESULT}"
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
        continue
    fi

    # Run integrity check on the backup (not the live database)
    INTEGRITY=$(python3 -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('${BACKUP_FILE}')
    result = conn.execute('PRAGMA integrity_check').fetchone()[0]
    conn.close()
    print(result)
except Exception as e:
    print(f'INTEGRITY_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1) || true

    if [ "${INTEGRITY}" = "ok" ]; then
        SIZE=$(du -sh "${BACKUP_FILE}" 2>/dev/null | cut -f1)
        log "    OK — ${SIZE}, integrity_check passed"
        TOTAL_OK=$((TOTAL_OK + 1))
    else
        log "    WARNING — backup created but integrity_check failed: ${INTEGRITY}"
        log "    Removing corrupt backup: ${BACKUP_FILE}"
        rm -f "${BACKUP_FILE}"
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi
done

# ─── Prune old backups ───────────────────────────────────────────────────────
log "Pruning backups older than ${KEEP_DAYS} days..."
PRUNED=$(find "${BACKUP_DIR}" -name "*.db" -type f -mtime +${KEEP_DAYS} -print -delete 2>/dev/null | wc -l)
log "  Pruned ${PRUNED} old backup files"

# ─── Summary ─────────────────────────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)
log "=========================================="
log "Backup complete: ${TOTAL_OK} succeeded, ${TOTAL_FAIL} failed"
log "Backup directory size: ${TOTAL_SIZE}"
log "=========================================="

if [ "${TOTAL_FAIL}" -gt 0 ]; then
    log "WARNING: ${TOTAL_FAIL} database(s) failed backup — review log above"
    exit 1
fi

exit 0
