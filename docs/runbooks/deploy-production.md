# Production (viapunt.ch)

Production runs on the same VPS as staging (83.228.196.57) as a second, separate copy of the
stack: its own checkout, `.env`, database, Redis, backups and guide-site releases.

| | Staging | Production |
| --- | --- | --- |
| Checkout | `/opt/civics` | `/opt/civics-prod` |
| Compose project | `civics` | `civics-prod` (`-p civics-prod`) |
| Edge alias | `civics-web` | `civics-prod-web` (`EDGE_ALIAS` in `.env`) |
| Hosts | staging.viapunt.ch, app.staging.viapunt.ch | viapunt.ch, www.viapunt.ch (redirect), app.viapunt.ch |
| Questions served | approved and in review | approved only (`APP_ENV=production`) |
| Stripe | sandbox | live account Viapunt (acct_1UXIdDLuBRyRw400) |

All commands run in `/opt/civics-prod`:

```
C="docker compose -p civics-prod -f infra/docker-compose.yml --env-file .env"
```

## Update to the latest code and content

```
git fetch -q origin main && git merge -q --ff-only origin/main
$C --profile ops build api worker migrate web
$C --profile ops run --rm migrate        # migrations + content import
$C up -d --no-deps api worker web
```

## Guide site release

Build on the laptop with the production addresses and copy the build into
`/opt/civics-prod/site-releases/releases/<sha>/`, then switch the `current` symlink (same as
staging, see `deploy-guide-site.md`):

```
cd site && SITE_URL=https://viapunt.ch APP_URL=https://app.viapunt.ch npm run build
```

A production build carries no `noindex`; never deploy it to staging, nor a staging build here.

## Secrets in `/opt/civics-prod/.env`

Generated on the server at setup: `SECRET_KEY`, `TOTP_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`,
`BACKUP_PASSPHRASE`. Entered by Chris: `STRIPE_SECRET_KEY` (live, `sk_live_…`) and
`STRIPE_WEBHOOK_SECRET` (`whsec_…` of the live webhook `viapunt-production`). After changing
Stripe keys: `$C up -d --no-deps api worker`, then once `$C exec -T api python -m
scripts.stripe_bootstrap` to create the live products and prices.

## Edge Caddy

The tutor stack's `/opt/sst-tutor/infra/Caddyfile` has a block for the production hosts that
proxies to `civics-prod-web:80` and redirects `www.viapunt.ch`. The Caddyfile is baked into the
tutor Caddy image: after an edit, rebuild and restart that service (`docker compose -f
infra/docker-compose.yml build caddy && … up -d --no-deps caddy` in `/opt/sst-tutor`).
