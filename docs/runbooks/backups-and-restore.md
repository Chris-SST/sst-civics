# Backups and restore

## What runs

The `backup` container in `infra/docker-compose.yml` runs `infra/backup.sh` once a day:

1. `pg_dump` of the `sst` database, gzip-compressed.
2. Symmetric encryption with GPG (AES-256) using `BACKUP_PASSPHRASE`.
3. Local copy in the `backups` Docker volume, kept 30 days.
4. If `BACKUP_REMOTE` is set, `rclone copy` to a second Swiss location, also pruned at 30 days.

Photos (Phase 1) live in Swiss object storage with their own 30-day lifecycle and are not part of this backup.

## Second location

Use a storage bucket at a different Swiss provider from the server, for example Infomaniak Swiss Backup (OpenStack Swift or S3) when hosting at Exoscale, or Exoscale SOS when hosting at Infomaniak. Configure rclone on the host once:

```bash
docker run --rm -it -v sst_rclone:/config/rclone rclone/rclone config
# create a remote named "swissbackup", then set BACKUP_REMOTE=swissbackup:sst-tutor-backups in .env
```

Mount the rclone config into the backup container by adding `- sst_rclone:/root/.config/rclone:ro` to its volumes.

## Check a backup exists

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec backup ls -la /backups
docker compose -f infra/docker-compose.yml --env-file .env logs --tail 20 backup
```

## Restore (also the quarterly restore test)

Do the test on the staging server, never on production, unless recovering production.

```bash
cd /opt/sst-tutor
docker compose -f infra/docker-compose.yml --env-file .env stop api worker
docker compose -f infra/docker-compose.yml --env-file .env exec backup sh -c \
  'gpg --batch --passphrase "$BACKUP_PASSPHRASE" -d /backups/sst-<stamp>.sql.gz.gpg | gunzip > /tmp/restore.sql'
docker compose -f infra/docker-compose.yml --env-file .env exec -T postgres psql -U sst -d postgres -c "DROP DATABASE sst;" -c "CREATE DATABASE sst OWNER sst;"
docker compose -f infra/docker-compose.yml --env-file .env exec backup cat /tmp/restore.sql | \
  docker compose -f infra/docker-compose.yml --env-file .env exec -T postgres psql -U sst -d sst
docker compose -f infra/docker-compose.yml --env-file .env start api worker
```

Then log in as admin and confirm families and users are present. Record the date and outcome of each restore test in `docs/PROGRESS.md`.

## Retention and deletion requests

Backups hold personal data for up to 30 days after deletion from the live database. The privacy notice must say so, and a deletion request is complete when the last backup containing the data has expired.
