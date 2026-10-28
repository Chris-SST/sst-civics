# Deploy staging (and production)

One Swiss virtual server runs the whole stack with Docker Compose. Production is the same procedure with its own server, domain and `.env`.

## 1. Server and DNS (Chris, once)

Staging exists since 28 October 2026: Infomaniak VPS Lite `sst-tutor-staging`, Ubuntu 24.04, 2 vCPU, 4 GB RAM, 60 GB, Satigny. IPv4 `83.228.196.57`, IPv6 `2001:1600:13:101::12dd`, SSH `ubuntu@83.228.196.57` with the `sst-tutor` key. Provider firewall allows TCP 22, 80, 443 and ICMP.

Still to do at the registrar: `A` record `staging.tutor.swisssciencetutors.ch` → `83.228.196.57` and `AAAA` → `2001:1600:13:101::12dd`. Caddy obtains the certificate automatically once the name resolves. Production later gets `tutor.swisssciencetutors.ch` on its own server.

For a new server: Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, Swiss region; open 22, 80, 443 only.

## 2. Prepare the host

Done on staging on 28 October 2026 (user `ubuntu`, key-only SSH as provided by Infomaniak):

```bash
ssh ubuntu@83.228.196.57
sudo apt update && sudo apt install -y ca-certificates curl git ufw
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443 && sudo ufw --force enable
sudo mkdir -p /opt/sst-tutor && sudo chown ubuntu:ubuntu /opt/sst-tutor
```

## 3. Clone and configure

Until the code is on GitHub, the tree is uploaded from the laptop (excluding `.venv`, `node_modules`, `web/dist`, `var`):

```bash
# on the laptop, in the repository root (Git Bash)
tar czf /tmp/sst-tutor.tgz --exclude=.venv --exclude=.git --exclude=web/node_modules --exclude=web/dist --exclude=var .
scp /tmp/sst-tutor.tgz ubuntu@83.228.196.57:/opt/sst-tutor/
ssh ubuntu@83.228.196.57 'cd /opt/sst-tutor && tar xzf sst-tutor.tgz && rm sst-tutor.tgz'
```

Once a GitHub repository exists: `git clone <repository-url> /opt/sst-tutor` and later `git pull --tags`.

```bash
cd /opt/sst-tutor && cp .env.example .env && nano .env
```

Staging values:

```
APP_ENV=staging
SECRET_KEY=<64 random characters: openssl rand -hex 32>
APP_BASE_URL=https://staging.tutor.swisssciencetutors.ch
DOMAIN=staging.tutor.swisssciencetutors.ch
ACME_EMAIL=tutor@swisssciencetutors.ch
POSTGRES_PASSWORD=<openssl rand -hex 24>
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...        # from step 5
EMAIL_BACKEND=smtp
SMTP_HOST=... SMTP_PORT=587 SMTP_USER=... SMTP_PASSWORD=...
SENTRY_DSN=                            # optional, see DECISIONS D-005
BACKUP_PASSPHRASE=<openssl rand -hex 24>   # keep a copy in the password manager
BACKUP_REMOTE=                         # rclone remote, see backups-and-restore.md
```

`DATABASE_URL` and `REDIS_URL` are set by Compose; leave the example values.

## 4. First start

```bash
docker compose -f infra/docker-compose.yml --env-file .env build
docker compose -f infra/docker-compose.yml --env-file .env --profile ops run --rm migrate
docker compose -f infra/docker-compose.yml --env-file .env up -d
docker compose -f infra/docker-compose.yml --env-file .env ps
curl -I https://staging.tutor.swisssciencetutors.ch/api/health   # expect 200 and a valid certificate
```

Create the first admin (asked to set up an authenticator app at first login):

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec \
  -e ADMIN_EMAIL=chris@swisssciencetutors.ch -e ADMIN_PASSWORD='<long password>' -e ADMIN_NAME=Chris \
  api python -m scripts.seed
```

Create the Stripe test prices once: `... exec api python -m scripts.stripe_bootstrap`.

## 5. Stripe webhook endpoint

In the Stripe Dashboard (test mode) → Developers → Webhooks → Add endpoint:

- URL: `https://staging.tutor.swisssciencetutors.ch/api/billing/webhook`
- Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `customer.subscription.trial_will_end`, `invoice.paid`, `invoice.payment_failed`
- Copy the signing secret into `STRIPE_WEBHOOK_SECRET` and restart: `docker compose ... up -d api worker`.

Production gets its own endpoint with the live secret, only after Chris approves go-live.

## 6. Redeploy

Manual:

```bash
cd /opt/sst-tutor && git pull --tags && git checkout <tag>
docker compose -f infra/docker-compose.yml --env-file .env build
docker compose -f infra/docker-compose.yml --env-file .env --profile ops run --rm migrate
docker compose -f infra/docker-compose.yml --env-file .env up -d --remove-orphans
```

From CI: set repository secrets `STAGING_HOST` (`83.228.196.57`), `STAGING_USER` (`ubuntu`), `STAGING_SSH_KEY` and the variable `STAGING_DEPLOY_ENABLED=true`. Pushing a tag `v0.x.y` then runs the same commands over SSH.

## 7. Checks after every deploy

- `/api/health` returns 200; the certificate is valid.
- Log in as admin; the Overview shows recent Stripe events as "processed".
- Worker logs: `docker compose ... logs --tail 50 worker` show no errors.
- The nightly backup file appears in the `backups` volume the next morning.

## Logs

```bash
docker compose -f infra/docker-compose.yml --env-file .env logs -f api worker caddy
```

Logs never contain message content or personal data beyond the email domain of a recipient.
