# Analytics (Umami)

Cookie-free, self-hosted visitor statistics for the guide site (D-062). Umami runs as the `umami` service in `infra/docker-compose.yml`, in the existing PostgreSQL server, in its own database.

## How it is served

| What | Where | Why |
| --- | --- | --- |
| Tracker script and collect endpoint | `https://<guide host>/stats/script.js` and `/stats/api/send` (same origin; the guide Caddy block proxies only these two paths to `umami:3000`) | No extra CSP entry, no third-party request |
| Dashboard | `https://stats.civics-staging.swisssciencetutors.ch` (later `stats.<brand domain>`) | Umami cannot run its dashboard under a sub-path: `BASE_PATH` is applied when the image is built, and we use the official prebuilt image |

The dashboard host needs one DNS record (A/AAAA to the server, like the other names) and gets its certificate from the edge Caddy automatically.

## First-time setup (once, on the server)

1. Add DNS for `stats.civics-staging.swisssciencetutors.ch` (same address as the other civics names).
2. In `/opt/civics/.env` set `UMAMI_APP_SECRET` and `UMAMI_DB_PASSWORD`, each from `openssl rand -hex 32`.
3. Create the database and user in the running PostgreSQL (replace the password with the value of `UMAMI_DB_PASSWORD`):
   ```
   docker compose -f infra/docker-compose.yml --env-file .env exec postgres \
     psql -U civics -d civics -c "CREATE USER umami WITH PASSWORD '<UMAMI_DB_PASSWORD>';" \
                              -c "CREATE DATABASE umami OWNER umami;"
   ```
4. Add the `stats.` name to the host list in the edge Caddy block (`infra/edge-snippet.Caddyfile`) and reload the edge. Then rebuild the civics web service, because its Caddyfile is baked into the image, and start Umami:
   ```
   docker compose -f infra/docker-compose.yml --env-file .env up -d --build web umami
   ```
   The first start creates the tables (about a minute). Check with `docker compose ... ps` that `umami` is healthy.
5. Open the stats host and log in as `admin` with the default password `umami`. Change the password at once (Settings, Profile).
6. Settings, Websites, Add website: name "Guide", domain the guide host. Copy its Website ID.
7. Set `PUBLIC_UMAMI_WEBSITE_ID=<id>` in the environment of the guide build and redeploy the site (`scripts/deploy_site.sh`; see deploy-guide-site.md). The tracker appears in the page source only when this variable is set.
8. Visit the guide in a browser without Do Not Track and check that a visit shows in Realtime.

## Privacy

- Umami sets no cookies and stores nothing in the browser. It counts visits with a hash of IP address, user agent and website, salted per day (Umami's default), so a visitor cannot be followed across days; the IP address itself is not stored.
- No personal data is collected. The script respects the browser's Do Not Track setting (`data-do-not-track="true"`). Telemetry to Umami's makers is off (`DISABLE_TELEMETRY=1`). Data stays on our Swiss server.
- Because there are no cookies and no identifiers, no consent banner is shown.
- Chris to update `docs/legal/privacy-en.md` clause 6.4 (and the translations): remove the brackets and state, in plain words, that the guide site uses self-hosted, cookie-free visitor statistics that count page views and visit totals without identifying visitors; that IP addresses are not stored; and that no data goes to third parties. Check that clause 6.2 and the retention section (7) still match; the lawyer should confirm the wording. Only the guide site is measured, not the learning app.

## Memory on the shared server

The `umami` container is limited to 384 MB (about 400 MB idle is the figure quoted by third-party sources; watch `docker stats` in the first week and raise the limit only if it is killed). The database adds little to the existing PostgreSQL (limit 512 MB). Do not enable Umami on the production VPS until the memory budget there is checked.

## Backups

The `umami` database lives in the same PostgreSQL volume (`civics_pg_data`), but `infra/backup.sh` currently dumps only the `civics` database (`pg_dump ... -d civics`), so analytics are NOT yet in the nightly backup. To include them, add a second dump to `backup.sh` using the same credentials (the `civics` user is the cluster superuser, so it can read `umami`):

```
pg_dump -h postgres -U civics -d umami --no-owner --no-privileges | gzip -9 > "$OUT_DIR/umami-$STAMP.sql.gz"
```

and encrypt and copy it like the main dump (or switch to `pg_dumpall`, which includes users). The retention `find` pattern `civics-*` would also need to cover `umami-*`. Analytics history is low value, so losing it is acceptable until this is done.

## Switching analytics off

- Visitors: remove `PUBLIC_UMAMI_WEBSITE_ID` from the guide build environment and redeploy the site. The tracker tag disappears; nothing else changes.
- Server: `docker compose -f infra/docker-compose.yml --env-file .env stop umami`. The `/stats/` paths then return a 502, which the tracker ignores. To remove the data, `DROP DATABASE umami;` and `DROP USER umami;` in `psql`.
- Delete clause 6.4 in the privacy notice if analytics are removed for good.
