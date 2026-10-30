# Testing and quality

How to run every suite locally and what each one covers. CI runs the same commands (`.github/workflows/ci.yml`).

## At a glance

| Suite | Command | Covers |
| --- | --- | --- |
| Lint and format | `ruff check app worker tests scripts alembic` and `ruff format --check ...` | Python style and common bugs |
| Content check | `python scripts/validate_content.py` | question files, sources, topics, translations |
| Backend | `pytest -q` | API, access rules, billing, study modes, mock tests (SQLite; `CI_DATABASE_URL` for PostgreSQL) |
| Front end | `cd web && npm run build` and `npm run check:locales` | type-check, build, locale keys |
| End to end | `cd web && npm run e2e` | the learner journeys and accessibility, in Chromium |
| Guide site | `cd site && npm run build && npm run check:hreflang && npm run lighthouse` | hreflang and Lighthouse on a phone profile |

## End-to-end tests (Playwright)

One-off setup, from the repository root with the virtual environment active (the Playwright config also finds `.venv` by itself):

```bash
pip install -e ".[dev]"
cd web && npm ci && npx playwright install chromium     # on Linux: npx playwright install --with-deps chromium
npm run e2e
```

Playwright starts `tests/e2e/start_server.py` (the `webServer` option), which:

1. generates 60 example Zurich questions with `tests/e2e/make_fixture_content.py` into `var/e2e/content` (ids `e2e-q01` to `e2e-q60`, approved, English translations approved; the first 30 are the free sample set). It never writes into `content/` and refuses to;
2. creates a fresh SQLite database `var/e2e/e2e.db`, runs the migrations and `python -m scripts.import_content --root var/e2e/content`;
3. seeds an admin (`e2e-admin@example.ch`) with an authenticator secret the tests know (`web/e2e/helpers.ts` computes the codes);
4. builds `web/dist` if it is missing or older than `web/src`;
5. serves API and front end on `http://127.0.0.1:8100` (`E2E_PORT` changes it) with `APP_ENV=test`, `JOBS_INLINE=true`, `EMAIL_BACKEND=console` (emails in `var/e2e/outbox/`), `LLM_FAKE=true` and no Stripe key (only the webhook secret `whsec_e2e_test_secret`).

The tests run one after the other (one SQLite database) and use a fresh email address each. Locally a running server is reused; set `E2E_PYTHON` to use another interpreter. The settings in `.env` do not apply: the harness sets everything it needs.

| File in `web/e2e/` | What it proves |
| --- | --- |
| `free-questions.spec.ts` | sign-up with the age box, verification link from the outbox, Zurich topics shown, one sample question practised, a question beyond the sample set refused (403 `sample_only`) |
| `email-link.spec.ts` | requesting a sign-in link, reading it from the outbox, landing signed in |
| `mock-test.spec.ts` | an admin grants a pass through the admin area; the learner answers all 50 questions, hands in, sees a score, the "not yet confirmed by the canton" pass-mark label and the review of wrong answers, with no Explain this |
| `checkout.spec.ts` | with no Stripe key the pricing panel says payments are not switched on and has no Buy button; a wrongly signed webhook is refused; a correctly signed `checkout.session.completed` (built as in Stripe's scheme) opens access once, and a repeat is not applied twice |
| `expiry.spec.ts` | a pass that expired yesterday, granted through the admin endpoint, leaves the learner on the free tier and Explain this is refused |
| `account-deletion.spec.ts` | a learner signed in with a fresh email link deletes the account; the session and the admin list no longer show it |
| `accessibility.spec.ts` | axe (WCAG 2.0/2.1 A and AA) finds no serious or critical issue on landing, sign-up, learner home, practise (before and after an answer), mock intro, a running mock test, account and admin learners; sign-up and one practise answer work with the keyboard alone |

When a test fails, Playwright keeps a trace, a screenshot and the page snapshot in `web/test-results/`. Open a trace with `npx playwright show-trace web/test-results/<test>/trace.zip`. CI uploads these as the `playwright-traces` artefact.

Not covered by an automated test: a real Stripe Checkout page (needs a test key and the Stripe CLI, see `stripe-test-mode.md`), screen-reader speech (axe checks names, roles and labels; a manual pass with NVDA or VoiceOver is still needed before launch), and Safari or Firefox.

## Guide site

```bash
cd site
npm ci
npm run build
npm run check:hreflang    # every page: alternates exist, include the page itself and x-default, and are reciprocal
npm run lighthouse        # Lighthouse CI, mobile profile, needs Chrome; LHCI_RUNS=1 for a quick run
```

`npm run lighthouse` serves the built site with `astro preview`, audits the German home page, the knowledge-test page and the FAQ three times each, prints the median performance, accessibility, best-practices and SEO scores (`scripts/lighthouse-scores.mjs`) and fails if any is below 90 (`lighthouserc.cjs`). Reports are in `site/.lighthouseci/`, uploaded by CI as `lighthouse-reports`. The audited pages are German; when slugs change (`site/src/i18n/pages.mjs`), update the URLs in `lighthouserc.cjs`.

## CI jobs

- `e2e` (needs `backend` and `web`): installs Chromium and runs `npm run e2e`; uploads traces on failure.
- `guide-site-quality`: builds the site, runs the hreflang check and Lighthouse; uploads the reports.

Both run on every push and pull request.
