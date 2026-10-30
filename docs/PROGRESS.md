# Progress

Updated 29 October 2026.

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

### Gate A: passed on 29 October 2026

Chris reviewed staging and signed off "OK for a start" with three carry-overs, tracked below as Phase 1 items: phone layout, removal of the AI labels (D-025), positioning of the marketing copy and plan names (D-026). Items 4 to 7 above (backup storage, error tracking, brand files, GitHub repository) stay open and are not blocking.

## Phase 1: Closed beta (gate B)

Started 29 October 2026. Build order in D-028.

| Item | Status | Notes |
| --- | --- | --- |
| Gate A carry-over: phone layout clean-up on every page | Done 29 Oct 2026 | Header, forms, plan cards, admin tables (stack into cards on phones), 44px touch targets; checked at 390px and 360px |
| Gate A carry-over: remove "is an AI, not a person" wording everywhere | Done 29 Oct 2026 | Footer, student home and student invite email, all three languages (D-025) |
| Gate A carry-over: positioning proposal for copy and plan names | Proposal written 29 Oct 2026 | `docs/POSITIONING_PROPOSAL.md`; Chris to pick a naming scheme, then the display names change |
| Chat tutor for IB Maths AA, IB Maths AI and IB Physics, streaming, KaTeX | **Built 29 Oct 2026**, on staging; needs `ANTHROPIC_API_KEY` on the server to go live | `app/llm/` (provider wrapper, prompt loader, pricing, service), `prompts/base/v1.md`, three course modules with topic lists, `app/tutoring/` (topic-first sessions, SSE streaming, gatekeeper, three-strikes rule, running summary), student chat page with KaTeX, first-use notice. Course modules are drafts for SST tutor review. |
| Question bank pipeline (generate, solve, checks, review queue) | Backend built 29 Oct 2026 (D-037); review and generation screens built 29 Oct 2026 | Batch API or direct generation, independent solve, SymPy answer checks, duplicate check, rounding-consistent tolerances, spot checks (first 50 per course, then 10%), tutor review API scoped to tagged courses, student reports hide a question after two. Staging serves auto-verified questions (D-039); first generation run for IB Maths AA started on staging. Front end: `/tutor` has a "Question review" tab (queue filtered by module and status, review panel with checks, editable fields, approve / send back / retire, note and minutes); `/admin/questions` adds stats, the generation form, batches with "Check now", open reports and the same review queue. |
| Diagnostic, mastery scores, "work on this next" home page | Built 29 Oct 2026 (student pages checked at 390px) | Two questions per topic, Elo-style mastery (D-040), adaptive practice questions, AI-marked structured answers, spaced review dates. Front end: student home leads with the diagnostic call to action (D-041), then "Work on this next" with Practise and Ask-the-tutor buttons and a mastery bar per topic; `/student/diagnostic/:id` and `/student/practice` use the shared `QuestionCard` (mcq, numeric, short, structured; result, solution, report a problem). Practice reworked 30 Oct 2026 into rounds of five with a question count, varied feedback and a round summary (D-043) after Chris found repeats on staging. |
| Gap-led tutor sessions with check questions | Built 29 Oct 2026 | The tutor's context carries the student's mastery and recent wrong answers on the topic; check questions come from the bank with mode `check`. Front end: "Check what you learnt" in the chat header opens up to three question cards under the chat and shows the new mastery. |
| Figures by name, drawn in the browser | Prompt vocabulary written 29 Oct 2026 (`prompts/figures/v1.md`); renderer built 29 Oct 2026 (`web/src/components/Figure.tsx`, hand-written SVG, safe expression parser, no new dependency) | Eight figure types; the model never draws freehand |
| Photo upload with HEIC conversion, EXIF removal and abuse-material screening | Blocked on D-031 | Needs Chris's yes to storage and screening providers |
| Message limits, cost logging and cost alerts | Built 29 Oct 2026 | Per-plan daily and monthly caps (Swiss time), 80% notice, `llm_calls` log with tokens, USD/CHF cost, latency and prompt version; one alert email per student (CHF 8) and per monthly budget (CHF 300) per month; Admin → AI usage. |
| TutorCruncher link: automatic free access, email sign-in links | Not started | Needs `TUTORCRUNCHER_API_KEY` |
| Ask a tutor: queue, tutor dashboard, 24-hour timer, notifications | Not started | |
| Safeguarding screen, alerts to the lead, written procedure | Screen and alerts built 29 Oct 2026; **written procedure pending** | Fast-model screen on every message (self-harm, abuse, sexual, bullying, danger); wellbeing replies show 147; flag plus email to the safeguarding lead with no content; Admin → Safeguarding queue with audited transcript view. Harassment and override attempts are flagged too. |
| Evaluation suite, about 200 cases per launch course | Not started | |
| Terms, privacy notice and AI-safety page on the main site | Not started | Lawyer review before gate B |
| Four weeks of beta use by SST students | Not started | |

Also carried from Phase 0: encrypt TOTP secrets at rest (D-013), self-service data export and deletion (D-019), Playwright end-to-end tests (D-021), production read-only support view (D-024).

Verification on 30 October 2026: 59 backend tests pass, ruff clean, `npm run build` clean, migrations 0003 and 0004 apply and revert on SQLite.

Needed from Chris for Phase 1: `ANTHROPIC_API_KEY` in `/opt/sst-tutor/.env` on the server; the naming scheme from the positioning proposal; decisions in D-030 and D-031; TutorCruncher API key.

## Phase 2 and 3

Not started.
