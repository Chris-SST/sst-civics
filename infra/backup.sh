#!/bin/sh
# Nightly encrypted PostgreSQL backup, kept 30 days locally and copied to a second
# Swiss location with rclone (BACKUP_REMOTE, e.g. "swissbackup:civics-backups").
# Runs inside the backup container; see docs/runbooks/backups-and-restore.md.
set -eu

STAMP=$(date -u +%Y%m%d-%H%M%S)
OUT_DIR=/backups
# Dump every application database that exists (civics, and umami once analytics is set up).
FILES=""
for DB in civics umami; do
  if ! psql -h postgres -U civics -lqt | cut -d '|' -f 1 | grep -qw "$DB"; then
    continue
  fi
  FILE="$OUT_DIR/$DB-$STAMP.sql.gz"
  pg_dump -h postgres -U civics -d "$DB" --no-owner --no-privileges | gzip -9 > "$FILE"
  if [ -n "${BACKUP_PASSPHRASE:-}" ]; then
    gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$BACKUP_PASSPHRASE" "$FILE"
    rm -f "$FILE"
    FILE="$FILE.gpg"
  else
    echo "WARNING: BACKUP_PASSPHRASE is empty; backup is not encrypted" >&2
  fi
  FILES="$FILES $FILE"
done

# Keep 30 days locally.
find "$OUT_DIR" -type f \( -name 'civics-*.sql.gz*' -o -name 'umami-*.sql.gz*' \) -mtime +30 -delete

if [ -n "${BACKUP_REMOTE:-}" ]; then
  for FILE in $FILES; do rclone copy "$FILE" "$BACKUP_REMOTE/" --quiet; done
  rclone delete "$BACKUP_REMOTE/" --min-age 30d --quiet || true
fi

echo "backup done: $FILE"
