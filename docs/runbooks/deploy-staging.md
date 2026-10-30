# Deploy staging (and production)

Staging shares the existing tutor VPS (decision D-004). The civics stack is its own Docker Compose project (`name: civics`) in `/opt/civics`, with its own `.env`, PostgreSQL, Redis, worker and backup. It binds no host ports. The tutor stack's Caddy, which owns ports 80 and 443, is the shared edge: it terminates TLS for the civics host names and proxies to the civics `web` container over a shared Docker network called `edge`.

Production gets its own server later, with its own domain and `.env`; the same procedure applies, except that the civics Caddy can then be the edge itself.

## 1. Prerequisites (Chris, once)

- Server: Infomaniak VPS Lite, Ubuntu 24.04, 2 vCPU, 4 GB RAM, `83.228.196.57`, SSH `ubuntu@83.228.196.57`. Docker is installed and the provider firewall allows TCP 22, 80, 443.
- The tutor stack is running in `/opt/sst-tutor`.
- DNS at the registrar, for both names: `A` record to `83.228.196.57` (and `AAAA` to `2001:1600:13:101::12dd`):
  - `civics-staging.swisssciencetutors.ch` (guide site, later)
  - `app.civics-staging.swisssciencetutors.ch` (the app)
- The shared network and the edge Caddy change (the exact site block is in `infra/edge-snippet.Caddyfile`):

```bash
docker network create edge
cd /opt/sst-tutor
# 1. In infra/docker-compose.yml add to the caddy service:  networks: [default, edge]
#    and at top level:                                       networks: { edge: { external: true } }
# 2. Append the site block from /opt/civics/infra/edge-snippet.Caddyfile to infra/Caddyfile
docker compose -f infra/docker-compose.yml --env-file .env up -d caddy          # recreates Caddy once, joins edge
docker compose -f infra/docker-compose.yml --env-file .env exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Sharing the server requires this change to the tutor stack; there is no alternative short of a separate server. Until the civics web container is running, the edge returns 502 for the civics names, which is expected. Caddy obtains the certificates automatically once the names resolve.

## 2. Memory budget

Two stacks share 4 GB. The civics services carry hard limits in `infra/docker-compose.yml`: PostgreSQL 512 MB, Redis 160 MB (`maxmemory 96mb`), API 512 MB, worker 512 MB, web 64 MB, backup 128 MB (about 1.9 GB in total). Give the tutor stack similar `deploy.resources.limits.memory` values so the two together stay under about 3.5 GB, and keep a swap file as a safety net. Check with `docker stats --no-stream`.

## 3. Get the code onto the server

```bash
sudo mkdir -p /opt/civics && sudo chown ubuntu:ubuntu /opt/civics
```

Until the code is on GitHub, upload the tree from the laptop (excluding `.venv`, `node_modules`, `web/dist`, `var`):

```bash
# on the laptop, in the repository root (Git Bash)
tar czf /tmp/civics.tgz --exclude=.venv --exclude=.git --exclude=web/node_modules --exclude=web/dist --exclude=var .
scp /tmp/civics.tgz ubuntu@83.228.196.57:/opt/civics/
ssh ubuntu@83.228.196.57 'cd /opt/civics && tar xzf civics.tgz && rm civics.tgz'
```

Once a GitHub repository exists: `git clone <repository-url> /opt/civics` and later `git pull --tags`.

## 4. Configure `.env`

```bash
cd /opt/civics && cp .env.example .env && nano .env
```

Staging values (the variables the stack needs):

```
APP_ENV=staging
SECRET_KEY=<64 random characters: openssl rand -hex 32>
APP_BASE_URL=https://app.civics-staging.swisssciencetutors.ch
POSTGRES_PASSWORD=<openssl rand -hex 24>
BACKUP_PASSPHRASE=<openssl rand -hex 24>   # keep a copy in the password manager
BACKUP_REMOTE=                             # rclone remote, see backups-and-restore.md
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...            # from step 6
EMAIL_BACKEND=smtp
SMTP_HOST=... SMTP_PORT=587 SMTP_USER=... SMTP_PASSWORD=...
ANTHROPIC_API_KEY=sk-ant-...               # leave out until the AI features are switched on
SENTRY_DSN=                                # optional
```

`DATABASE_URL` and `REDIS_URL` are set by Compose. `DOMAIN` and `ACME_EMAIL` are no longer used by this stack: certificates and host names belong to the edge Caddy. Leave any model-name variables out of the file, or set real model IDs; an empty value breaks AI calls.

## 5. First start

```bash
cd /opt/civics
docker compose -f infra/docker-compose.yml --env-file .env --profile ops build
docker compose -f infra/docker-compose.yml --env-file .env --profile ops run --rm migrate
docker compose -f infra/docker-compose.yml --env-file .env up -d
docker compose -f infra/docker-compose.yml --env-file .env ps
curl -I https://app.civics-staging.swisssciencetutors.ch/api/health   # expect 200 and a valid certificate
```

Create the first admin (asked to set up an authenticator app at first login):

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec \
  -e ADMIN_EMAIL=chris@swisssciencetutors.ch -e ADMIN_PASSWORD='<long password>' \
  api python -m scripts.seed
```

Create the Stripe test prices once: `... exec api python -m scripts.stripe_bootstrap`.

## 6. Stripe webhook endpoint

See `stripe-test-mode.md`. In the Stripe Dashboard (test mode) add the endpoint `https://app.civics-staging.swisssciencetutors.ch/api/billing/webhook`, copy the signing secret into `STRIPE_WEBHOOK_SECRET` and restart: `docker compose -f infra/docker-compose.yml --env-file .env up -d api worker`.

Production gets its own endpoint with the live secret, only after Chris approves go-live.

## 7. Redeploy

Manual:

```bash
cd /opt/civics && git pull --tags && git checkout <tag>
docker compose -f infra/docker-compose.yml --env-file .env --profile ops build
docker compose -f infra/docker-compose.yml --env-file .env --profile ops run --rm migrate
docker compose -f infra/docker-compose.yml --env-file .env up -d --remove-orphans
```

From CI: set repository secrets `STAGING_HOST` (`83.228.196.57`), `STAGING_USER` (`ubuntu`), `STAGING_SSH_KEY` and the variable `STAGING_DEPLOY_ENABLED=true`. Pushing a tag `v0.x.y` then runs the same commands over SSH in `/opt/civics`.

Why `--profile ops` on the build: the `migrate` service only exists in that profile, and a plain `build` skips it, so `run --rm migrate` would reuse an old image and silently apply no new migrations. Check with `docker compose -f infra/docker-compose.yml --env-file .env exec postgres psql -U civics -d civics -c "select * from alembic_version"` after every deploy.

## 8. Checks after every deploy

- `https://app.civics-staging.swisssciencetutors.ch/api/health` returns 200; the certificate is valid.
- The tutor site still works (the edge Caddy was reloaded).
- Log in as admin; the Overview shows recent Stripe events as "processed".
- Worker logs show no errors: `docker compose -f infra/docker-compose.yml --env-file .env logs --tail 50 worker`.
- `docker stats --no-stream` shows every container under its memory limit.
- The nightly backup file appears in the `civics_backups` volume the next morning.

## Logs

```bash
cd /opt/civics
docker compose -f infra/docker-compose.yml --env-file .env logs -f api worker web
docker logs -f <tutor caddy container>      # the edge: certificates and access for both stacks
```

Logs never contain message content or personal data beyond the email domain of a recipient.

## Switching the AI features on

Add `ANTHROPIC_API_KEY=sk-ant-...` to `/opt/civics/.env` and restart `api` and `worker`
(`docker compose -f infra/docker-compose.yml --env-file .env up -d api worker`). Check with:

```bash
docker compose -f infra/docker-compose.yml --env-file .env logs --since 10m api | grep "AI call"
```
