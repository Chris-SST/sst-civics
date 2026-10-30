# civics

A trainer for the Swiss citizenship knowledge test, starting with the canton of Zurich. Learners sign up with an email address, practise sample questions free, and buy a one-off Civics Pass (CHF 29 for six months, paid by card or TWINT) for a canton. Each question is studied first in the learner's own language beside the German, then in German only, as in the real test. The working name in the code is `civics`; the provisional brand is Civigo (decision D-017). It is an independent service with no connection to any authority, and it gives general information, not legal advice.

The build plan is [PLAN.md](PLAN.md). Progress and decisions: [docs/PROGRESS.md](docs/PROGRESS.md) and [docs/DECISIONS.md](docs/DECISIONS.md). The repository began as a copy of the SST Virtual Tutor (D-001); what was kept, adapted and removed is in [REUSE.md](REUSE.md).

**Current state: Phase 0 (copy and strip) is complete, pending gate A.** Adult learner and admin accounts, sign-in by email link, one-off Stripe payments with per-canton entitlements, refunds, account deletion, an admin area and eight interface languages are built and tested. The staging deploy waits on DNS, the edge Caddy change and a GitHub repository. The question model, study modes, mock tests and guide site arrive in Phase 1; the chat is the earlier tutor chat, to be reshaped into "Explain this". The demo script for gate A is [docs/DEMO_PHASE0.md](docs/DEMO_PHASE0.md).

## Layout

```
app/        FastAPI API: auth, billing (Stripe), admin, email, llm, questions, tutoring
worker/     arq background worker: emails, Stripe events, nightly jobs
alembic/    database migrations (one initial migration, D-005)
web/        React + TypeScript + Vite PWA; locales in web/src/locales
infra/      Docker Compose, Caddy snippet for the shared edge, backup script
scripts/    seed (first admin), Stripe bootstrap, content check and import
content/    question bank as YAML: topics, questions, translations (content/README.md)
tests/      pytest suite (SQLite locally; SQLite and PostgreSQL in CI)
prompts/    versioned prompt files
evals/      evaluation suite
docs/       PROGRESS, DECISIONS, DATA_INVENTORY, DEMO_PHASE0, runbooks/, source-app/
```

## Run it locally in ten minutes

Requirements: Python 3.12 or newer, Node 22 or newer. No Docker needed.

```bash
python -m venv .venv
. .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` for a laptop (SQLite, jobs run in the API process, emails written to files, canned AI replies):

```
APP_ENV=dev
SECRET_KEY=<any long random string>
DATABASE_URL=sqlite+aiosqlite:///./var/dev.db
JOBS_INLINE=true
EMAIL_BACKEND=console
LLM_FAKE=true
APP_BASE_URL=http://localhost:8000
COOKIE_SECURE=false
```

```bash
mkdir -p var
alembic upgrade head
python -m scripts.import_content   # topics, questions and translations from content/
cd web && npm ci && npm run build && cd ..
uvicorn app.main:app --reload --port 8000
```

Run the import again after changing anything under `content/`; it validates the files first and changes nothing if they have errors. The file format and the rules are in [content/README.md](content/README.md).

Open http://localhost:8000. Every email (verification, sign-in link, deletion notice) is written as an `.eml` file in `var/outbox/`; open it in a text editor and follow the link. `LLM_FAKE=true` (dev and test only) gives canned chat replies without an API key.

For front-end work with hot reload, run `npm run dev` in `web/` (port 5173, proxies `/api` to 8000) and set `APP_BASE_URL=http://localhost:5173`.

### The first admin

`scripts/seed.py` reads two environment variables and creates one admin (verified, with a password; no name field):

```bash
ADMIN_EMAIL=you@example.ch ADMIN_PASSWORD='a-long-password-of-10-or-more' python -m scripts.seed
```

It does nothing if either is missing or the address exists. At first sign-in at `/login` the admin is sent to `/2fa/setup` to set up an authenticator app; admins always need it.

### Stripe in test mode

1. Put the test key in `.env`: `STRIPE_SECRET_KEY=sk_test_...` (the bootstrap script refuses live keys).
2. Create the products and prices once: `python -m scripts.stripe_bootstrap` (lookup keys `civics_pass_zh`, `civics_pass_ag`, `civics_extension`; add `--amount KEY=RAPPEN` to change an amount). Prices are read from Stripe by key, never from code.
3. In the Stripe Dashboard (test mode), Settings, Payment methods: enable cards and TWINT.
4. Webhooks go to `/api/billing/webhook`, with exactly four events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `charge.refunded`. Locally: `stripe listen --forward-to localhost:8000/api/billing/webhook --events <the four, comma-separated>` and copy the printed `whsec_...` into `STRIPE_WEBHOOK_SECRET`.
5. Restart the API. Test card `4242 4242 4242 4242`, any future date, any CVC.

`CANTONS_FOR_SALE` (default `zh`) decides which passes are on sale. Details: [docs/runbooks/stripe-test-mode.md](docs/runbooks/stripe-test-mode.md).

### With PostgreSQL, Redis and a mail catcher

```bash
docker compose -f infra/docker-compose.dev.yml up -d
# .env: DATABASE_URL=postgresql+asyncpg://civics:civics@localhost:5432/civics
#       REDIS_URL=redis://localhost:6379/0  JOBS_INLINE=false
#       EMAIL_BACKEND=smtp  SMTP_HOST=localhost  SMTP_PORT=1025  SMTP_STARTTLS=false
alembic upgrade head && python -m scripts.import_content
uvicorn app.main:app --reload            # terminal 1
arq worker.main.WorkerSettings           # terminal 2
```

## Tests and checks

```bash
ruff check app worker tests scripts alembic && ruff format --check app worker tests scripts alembic
python scripts/validate_content.py       # content files: sources, options, topics, translations
pytest -q                                # SQLite; set CI_DATABASE_URL for PostgreSQL
cd web && npm run build                  # type-check and build
cd web && npm run check:locales          # every locale has the same keys and placeholders as en-GB
```

CI is in [.github/workflows/ci.yml](.github/workflows/ci.yml) and needs the GitHub repository (not yet created). Locale review status: [web/src/locales/README.md](web/src/locales/README.md).

## Staging and production

Staging shares the existing SST tutor VPS (D-004): the civics stack is its own Docker Compose project under `/opt/civics` (API, worker, PostgreSQL, Redis, nightly encrypted backup) and binds no host ports; the tutor stack's Caddy is the shared edge and proxies the civics host names. Production gets its own server before go-live.

- [docs/runbooks/deploy-staging.md](docs/runbooks/deploy-staging.md): prerequisites, first start, redeploy, checks
- [docs/runbooks/backups-and-restore.md](docs/runbooks/backups-and-restore.md)
- [docs/runbooks/stripe-test-mode.md](docs/runbooks/stripe-test-mode.md) and [stripe-outage.md](docs/runbooks/stripe-outage.md)
- [docs/runbooks/account-deletion.md](docs/runbooks/account-deletion.md)

## Environment variables

All are documented in [.env.example](.env.example). Never commit `.env`. Stripe stays in test mode, and the staging AI key is used, until Chris approves go-live.

## Conventions

- Interface text in British English; German is formal ("Sie"); French, Italian, Portuguese, Spanish, Albanian and Turkish follow the locale notes. Amounts in CHF with Swiss number formatting.
- Every AI call goes through `app/llm/`; no other module imports the provider's SDK. Prompts are versioned files in `prompts/`, never strings in code. Question content and guide pages are versioned files; the database is filled from them on deploy.
- No personal data to the AI provider: no names, emails or identifiers, and message content is never logged. Nationality, permit type, date of birth and address are never collected ([docs/DATA_INVENTORY.md](docs/DATA_INVENTORY.md)).
- No secrets in the repository.
- No Swiss or cantonal coats of arms and no "official" wording. The independence notice goes in every footer.
- Never copy text from cantonal question catalogues or test series; use them only to list topics.
- No AI attribution anywhere: code, docs, interface text or commit messages.
- Each feature ships with tests; lint, tests and the web build must pass.
