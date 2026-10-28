# SST Virtual Tutor

Subscription web app that gives Swiss Science Tutors' students an AI tutor with a one-tap route to SST's human tutors. The build plan is [PLAN.md](PLAN.md); progress and decisions live in [docs/PROGRESS.md](docs/PROGRESS.md) and [docs/DECISIONS.md](docs/DECISIONS.md).

**Current state: Phase 0 (Foundations), awaiting gate A sign-off.** Accounts, login, 2FA, Stripe test mode, admin area, brand and three languages are built. The AI tutor itself arrives in Phase 1.

## Layout

```
app/      FastAPI API: auth, billing (Stripe), family, admin, portal, email, llm (Phase 1)
worker/   arq background worker: emails, Stripe events, nightly reconciliation
alembic/  database migrations
web/      React + TypeScript + Vite PWA (en-GB, de-CH, fr-CH)
infra/    Docker Compose, Caddy, backup script
scripts/  seed (plans, first admin), Stripe bootstrap
tests/    pytest suite (runs on SQLite locally, SQLite and PostgreSQL in CI)
docs/     PROGRESS.md, DECISIONS.md, runbooks/, DEMO_PHASE0.md
prompts/  versioned tutor prompts and course modules (Phase 1)
evals/    tutor evaluation suite (Phase 1)
```

## Run it locally in 10 minutes (no Docker needed)

Requirements: Python 3.12 or newer, Node 22 or newer.

```bash
# 1. Backend
python -m venv .venv
. .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` for a laptop setup (SQLite, in-process jobs, emails written to `var/outbox/`):

```
APP_ENV=dev
SECRET_KEY=<any long random string>
DATABASE_URL=sqlite+aiosqlite:///./var/dev.db
JOBS_INLINE=true
EMAIL_BACKEND=console
APP_BASE_URL=http://localhost:8000
COOKIE_SECURE=false
```

```bash
mkdir -p var
alembic upgrade head
ADMIN_EMAIL=you@example.ch ADMIN_PASSWORD='choose-a-long-one' python -m scripts.seed

# 2. Front end (built once, then served by the API at http://localhost:8000)
cd web && npm ci && npm run build && cd ..

# 3. Start
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. Sign up as a parent; the confirmation email appears as a `.eml` file in `var/outbox/` (open it and follow the link). The admin you seeded logs in at `/login` and is asked to set up an authenticator app.

For front-end development with hot reload, run `npm run dev` in `web/` (port 5173, proxies `/api` to 8000) and set `APP_BASE_URL=http://localhost:5173`.

### Stripe in test mode

1. Put the **test** keys in `.env`: `STRIPE_SECRET_KEY=sk_test_...`.
2. Create the products and prices once: `python -m scripts.stripe_bootstrap`.
3. Enable cards and TWINT under Settings → Payment methods in the Stripe Dashboard (test mode).
4. Forward webhooks locally: `stripe listen --forward-to localhost:8000/api/billing/webhook` and copy the printed `whsec_...` into `STRIPE_WEBHOOK_SECRET`.
5. Restart the API. Test card: `4242 4242 4242 4242`, any future date, any CVC.

Details and test clocks: [docs/runbooks/stripe-test-mode.md](docs/runbooks/stripe-test-mode.md).

### With PostgreSQL, Redis and a mail catcher

```bash
docker compose -f infra/docker-compose.dev.yml up -d     # Postgres 5432, Redis 6379, Mailpit http://localhost:8025
# .env: DATABASE_URL=postgresql+asyncpg://sst:sst@localhost:5432/sst  REDIS_URL=redis://localhost:6379/0
#       JOBS_INLINE=false  EMAIL_BACKEND=smtp  SMTP_HOST=localhost  SMTP_PORT=1025  SMTP_STARTTLS=false
alembic upgrade head && python -m scripts.seed
uvicorn app.main:app --reload            # terminal 1
arq worker.main.WorkerSettings           # terminal 2
```

## Tests and checks

```bash
ruff check app worker tests scripts alembic && ruff format --check app worker tests scripts alembic
pytest -q                                # 28 tests, SQLite
CI_DATABASE_URL=postgresql+asyncpg://sst:sst@localhost:5432/sst_test pytest -q   # against PostgreSQL
cd web && npm run build                  # type-check and build
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs lint, migrations up/down on PostgreSQL, both test runs, the web build, dependency audits and Trivy image scans on every push. Deploys to staging run only from `v*` tags.

## Staging and production

Everything runs on one Swiss virtual server with Docker Compose: Caddy (TLS, static front end, `/api` proxy), API, worker, PostgreSQL 16, Redis and a nightly encrypted backup to a second Swiss location. See [docs/runbooks/deploy-staging.md](docs/runbooks/deploy-staging.md).

## Environment variables

All variables are documented in [.env.example](.env.example). Secrets are never committed; Stripe stays in test mode until Chris approves go-live.

## Conventions

- Interface text in British English, German and French; amounts in CHF with Swiss formatting.
- Every AI call goes through `app/llm/` (Phase 1). Prompts live as versioned files in `prompts/`, never in code.
- Names, emails and other identifiers never leave the server; logs carry no message content.
- No AI attribution anywhere in code, docs, interface text or commit messages.
