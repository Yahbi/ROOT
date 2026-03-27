#!/bin/bash
# ROOT — Daily database backup script
# Add to crontab: 0 3 * * * /home/ubuntu/ROOT/deploy/backup.sh
set -euo pipefail

BACKUP_DIR="/home/ubuntu/ROOT/backups"
DATA_DIR="/home/ubuntu/ROOT/data"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/root_data_${TIMESTAMP}.tar.gz"

# Backup all SQLite databases + skill files
tar -czf "$BACKUP_FILE" -C "$DATA_DIR" \
  --exclude='*.db-wal' --exclude='*.db-shm' \
  . 2>/dev/null || true

# Remove backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "root_data_*.tar.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

SIZE=$(du -sh "$BACKUP_FILE" 2>/dev/null | cut -f1)
echo "[$(date)] Backup created: $BACKUP_FILE ($SIZE)"
