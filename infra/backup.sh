#!/bin/sh
# Nightly encrypted PostgreSQL backup, kept 30 days locally and copied to a second
# Swiss location with rclone (BACKUP_REMOTE, e.g. "swissbackup:sst-tutor-backups").
# Runs inside the backup container; see docs/runbooks/backups-and-restore.md.
set -eu

STAMP=$(date -u +%Y%m%d-%H%M%S)
OUT_DIR=/backups
FILE="$OUT_DIR/sst-$STAMP.sql.gz"

pg_dump -h postgres -U sst -d sst --no-owner --no-privileges | gzip -9 > "$FILE"

if [ -n "${BACKUP_PASSPHRASE:-}" ]; then
  gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$BACKUP_PASSPHRASE" "$FILE"
  rm -f "$FILE"
  FILE="$FILE.gpg"
else
  echo "WARNING: BACKUP_PASSPHRASE is empty; backup is not encrypted" >&2
fi

# Keep 30 days locally.
find "$OUT_DIR" -type f -name 'sst-*.sql.gz*' -mtime +30 -delete

if [ -n "${BACKUP_REMOTE:-}" ]; then
  rclone copy "$FILE" "$BACKUP_REMOTE/" --quiet
  rclone delete "$BACKUP_REMOTE/" --min-age 30d --quiet || true
fi

echo "backup done: $FILE"
