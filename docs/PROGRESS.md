# Progress

Updated 28 October 2026.

## Phase 0: Foundations (gate A)

Gate A: Chris can sign up, subscribe in test mode and log in as each role on staging.

| Item | Status | Notes |
| --- | --- | --- |
| Repository, CI and Docker Compose set up; tests run on every push | Done | GitHub Actions: ruff, migrations on PostgreSQL, pytest (SQLite and PostgreSQL), web build, pip and npm audits, Trivy scans. Push to a GitHub repo to activate. |
| Staging server live with TLS, nightly backups and error tracking | **Live** since 28 Oct 2026 at https://staging.tutor.swisssciencetutors.ch | Infomaniak VPS `sst-tutor-staging` (83.228.196.57): Docker stack running (Caddy, API, worker, PostgreSQL, Redis, backup), migrations applied, plans and admin seeded. DNS `A` record added at Swizzonic (a stray `@.swisssciencetutors.ch` TXT record that blocked the editor was removed; its value duplicated a live record). Let's Encrypt certificate valid to 26 Jan 2027, auto-renewed. Backups run nightly but stay on the server until backup storage is ordered (`BACKUP_REMOTE`). Error tracking is wired (`SENTRY_DSN`) but off until Chris picks GlitchTip or Sentry EU. |
| Parent and student sign-up, login and password reset; 2FA for tutors and admin | Done | Email verification, Argon2id, server-side sessions, CSRF, rate limits, single-use 30-minute reset tokens, student username or invite-link login, TOTP mandatory for staff and optional for parents, admin 2FA reset. |
| Stripe test mode: Checkout, webhooks and Customer Portal end to end | Keys on staging since 29 Oct 2026, prices created; **Checkout walk-through by Chris pending** | Checkout (7-day trial, quantity = students), portal, signed webhooks stored and processed by the worker, nightly reconciliation, access rules, payment-failed grace period, add-on credits. Bootstrap script creates prices by lookup key. Tested with a mocked Stripe. |
| Brand applied; interface text in English, German and French | Done, **brand source files pending** | Palette and fonts taken from the live site (Lexend, Rethink Sans, green `#84b796`); fonts self-hosted; logos copied from the site. PWA icons are placeholders until Chris supplies the originals. |

Also delivered: admin area (overview, families, free-access grants, staff invites, plan limits, audit log, staging-only "View as" to open any parent, student or tutor view without logging out), tutor and student placeholder pages, installable PWA, README, runbooks and the demo script (`docs/DEMO_PHASE0.md`).

### Verification

- 32 backend tests pass (`pytest -q`); ruff clean; `npm run build` clean.
- Alembic migration applies and reverts on SQLite; CI does the same on PostgreSQL.
- Manual smoke test: migrate, seed admin, serve built front end from the API, sign up in French, confirmation email written to the outbox, security headers present.

### Waiting on Chris before gate A can be ticked

1. DNS: `A` record done. `AAAA` → `2001:1600:13:101::12dd` was filled in at Swizzonic and waits for Chris to confirm the save (optional; IPv4 is enough for the site to work).
2. Stripe: keys and prices done. Run demo section 3 (trial Checkout with the test card) and confirm the webhook arrives as "processed" in Admin → Overview.
3. Email: Google Workspace SMTP relay configured on 29 Oct 2026, staging switched to it and a real email delivered. DKIM (`google._domainkey`) and DMARC (`_dmarc`, `p=none`) records are live at Swizzonic. Remaining: press "Start authentication" in the Admin console (Gmail → Authenticate email), then tighten DMARC to `p=quarantine` after a few weeks of clean reports.
4. Order Infomaniak Swiss Backup (or another Swiss bucket) and set `BACKUP_REMOTE` so nightly backups leave the server.
5. Decide on error tracking: self-hosted GlitchTip on the staging host (no third party) or Sentry EU.
6. Brand source files (logo SVG, exact colour and font specification), if different from the live site.
7. Create the GitHub repository and push, so CI runs and deploys can go through tags instead of tar upload.

## Phase 1: Closed beta

Not started. See PLAN.md for the checklist. First Phase 1 items to tackle: `app/llm/` module with cost logging, `prompts/` base instructions and IB Maths AA module, streaming chat endpoint, gatekeeper and safeguarding screen.

## Phase 2 and 3

Not started.
