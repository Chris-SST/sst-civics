# Progress

Updated 28 October 2026.

## Phase 0: Foundations (gate A)

Gate A: Chris can sign up, subscribe in test mode and log in as each role on staging.

| Item | Status | Notes |
| --- | --- | --- |
| Repository, CI and Docker Compose set up; tests run on every push | Done | GitHub Actions: ruff, migrations on PostgreSQL, pytest (SQLite and PostgreSQL), web build, pip and npm audits, Trivy scans. Push to a GitHub repo to activate. |
| Staging server live with TLS, nightly backups and error tracking | **Blocked on Chris** | Needs a Swiss VPS account (Infomaniak or Exoscale), DNS for `staging.tutor.swisssciencetutors.ch` and a go-ahead on error tracking. Compose stack, Caddy TLS, backup container and Sentry-compatible hook are ready; runbook in `docs/runbooks/deploy-staging.md`. |
| Parent and student sign-up, login and password reset; 2FA for tutors and admin | Done | Email verification, Argon2id, server-side sessions, CSRF, rate limits, single-use 30-minute reset tokens, student username or invite-link login, TOTP mandatory for staff and optional for parents, admin 2FA reset. |
| Stripe test mode: Checkout, webhooks and Customer Portal end to end | Done in code, **needs Chris's test keys** to exercise against Stripe | Checkout (7-day trial, quantity = students), portal, signed webhooks stored and processed by the worker, nightly reconciliation, access rules, payment-failed grace period, add-on credits. Bootstrap script creates prices by lookup key. Tested with a mocked Stripe. |
| Brand applied; interface text in English, German and French | Done, **brand source files pending** | Palette and fonts taken from the live site (Lexend, Rethink Sans, green `#84b796`); fonts self-hosted; logos copied from the site. PWA icons are placeholders until Chris supplies the originals. |

Also delivered: admin area (overview, families, free-access grants, staff invites, plan limits, audit log), tutor and student placeholder pages, installable PWA, README, runbooks and the demo script (`docs/DEMO_PHASE0.md`).

### Verification

- 28 backend tests pass (`pytest -q`); ruff clean; `npm run build` clean.
- Alembic migration applies and reverts on SQLite; CI does the same on PostgreSQL.
- Manual smoke test: migrate, seed admin, serve built front end from the API, sign up in French, confirmation email written to the outbox, security headers present.

### Waiting on Chris before gate A can be ticked

1. Create the Swiss VPS and DNS record, or give the go-ahead and credentials for the agent to do it.
2. Stripe test-mode keys (`sk_test_...`) for `.env` on staging; enable TWINT and cards in the dashboard.
3. Choose the transactional email provider (Swiss or EU) and provide SMTP credentials, or approve Infomaniak SMTP.
4. Brand source files (logo SVG, exact colour and font specification), if different from the live site.
5. Decide on error tracking: self-hosted GlitchTip on the staging host (no third party) or Sentry EU.

## Phase 1: Closed beta

Not started. See PLAN.md for the checklist. First Phase 1 items to tackle: `app/llm/` module with cost logging, `prompts/` base instructions and IB Maths AA module, streaming chat endpoint, gatekeeper and safeguarding screen.

## Phase 2 and 3

Not started.
