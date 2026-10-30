# Progress

Done and next, per phase checklist in PLAN.md. Updated 30 October 2026.

## Phase 0: Copy and strip (gate A: staging works end to end)

- [x] REUSE.md written and approved (D-002).
- [x] New repository from a copy of the SST app at tag `v0.1.0-citizen-base` (D-001); source docs moved to `docs/source-app/`.
- [x] CI and tests pass after the removals: lint, SQLite and PostgreSQL suites, web build, image build and scan all green on GitHub (30 October 2026).
  - [x] 0.2 Remove family, parent/student/tutor roles, under-18 rules, safeguarding queue; collapse to Learner and Admin (D-018 to D-025). 61 tests.
  - [x] 0.3 Remove maths rendering and checks (KaTeX, figures, sympy, LaTeX prompts, mark-scheme marking); multiple choice is the only question kind; prompts bumped to v2. 64 tests.
  - [x] 0.4 New initial migration (D-005).
- [x] Learner and admin accounts with email sign-in links (0.5, 0.6; D-027 to D-032). Optional learner passwords, encrypted TOTP secrets, account self-deletion, data inventory in `docs/DATA_INVENTORY.md`. 89 tests.
- [x] Stripe one-off payments working in test mode, with entitlements per canton (0.7; D-033 to D-038). Civics Pass and extension by lookup key, one-off Checkout, webhook grants, refund rule and admin refund, `plans` table removed. 105 tests.
- [ ] Interface locales for the launch languages (0.8).
- [ ] Staging site live on the shared VPS with its own host names, TLS and nightly backups (0.9 code done, D-004; deploy waits on DNS, the edge Caddy change and a GitHub repository).
- [x] Phase 0 code review (ten findings, nine fixed, one deferred to Phase 1), README rewritten, `docs/DEMO_PHASE0.md` written, old-product wording removed (0.10 code side, 30 October 2026).
- [x] DNS records and the shared edge Caddy on the tutor server done (30 October 2026); GitHub repository `Chris-SST/sst-civics` created and pushed (D-039).
- [x] Staging deployed on 30 October 2026: `https://app.civics-staging.swisssciencetutors.ch` (compose project `civics` in `/opt/civics`, console email, Stripe and AI keys empty), first admin created, deploy key installed.
- [x] Gate A signed off by Chris on 30 October 2026 after walking the admin, sign-up and access steps on staging. Stripe was not re-exercised on civics staging (no test key yet); the integration is the one proven in the tutor app. Release tagged `v0.1.0`.

## Phase 1: Zurich launch (gate B)

- [x] Question model, import from repository files, and the review queue in the admin area (1.1, 1.2; done 30 October 2026, D-044 to D-047). Content files under `content/` (schema in `content/README.md`), `scripts/validate_content.py` in CI, `scripts/import_content.py` in the compose migrate step, tables `topics`, `questions`, `question_translations`, `glossary_terms`; content API, practice and diagnostic on the canton's topics, review queue and translation status screen; course concept and generation pipeline removed. 151 tests. Admin review actions are not yet written back to the files (task 1.5). Before the next staging deploy: the API image must copy `content/` (`infra/Dockerfile.api`), and staging's database is recreated (migration 0001 rewritten).
- [x] Zurich topic list (1.4): 35 topics in `content/topics/zh.yaml`, targets 275/55/20, sources in `SOURCES-zh.md`. Unconfirmed: pass mark 30, 60-minute duration, per-section counts; to ask the Gemeindeamt together with the licensing question.
- [ ] Content pipeline scripts (1.5).
- [ ] About 350 Zurich questions approved, translated and reviewed (1.6).
- [x] Learn, Practise and Mock test with the four study modes (1.7 to 1.9; done 30 October 2026, D-048 to D-051). Package `app/study/`: study modes as a rendering contract, tables `question_progress` and `mock_runs` (replacing `topic_mastery` and `diagnostic_runs`), Leitner spaced repetition weighted towards weak topics, readiness estimate, free-tier sample set and one free mock test; pages `/learn`, `/practise`, `/mock` with the mode stepper and countdown; the diagnostic and `/api/practice` are gone. Migration 0001 rewritten again, so staging's database is recreated. Not yet checked in a browser on staging.
- [x] Explain this (1.10; done 30 October 2026, D-057). `POST /api/explain/start`, `prompts/explain/v1.md`, `prompts/gatekeeper/v2.md`, `ExplainPanel` on Learn and Practise cards (never in the mock test); the topic chat's entry points are removed from the learner home. Not yet checked with the live model or in a browser on staging; run the evals before go-live.
- [x] Glossary admin screen and learner glossary page (1.3 screen; done 30 October 2026, D-058). Official fr/it/en names from TERMDAT are still to be confirmed by a reviewer in the new Glossary tab.
- [x] Guide site scaffold (1.11): Astro in `site/`, eight-language routing with hreflang and sitemap, design-system components, residence calculator island, served by the civics Caddy from `site-releases`, CI build and tag-gated rsync deploy (D-043, D-056, D-059, D-060).
- [x] Guide content in German and English with official sources (1.12): overview, Zurich step by step, knowledge test, language certificates, fees, calculator, free practice, ten FAQs each. Overview, knowledge test, calculator, free practice and FAQ also in fr, it, pt, es, sq, tr as drafts for native review (56 pages). Umami analytics wired (D-062), awaiting the stats DNS record and one-time setup on the server.
- [x] Terms, privacy notice, independence notice drafted in English (1.13, `docs/legal/`); lawyer and accountant review open; other languages after approval.
- [x] Quality (1.14): Playwright end-to-end suite (free questions, email link, full mock, webhook fulfilment, expiry, deletion), axe accessibility on the main screens with fixes, Lighthouse 100/100/100/100 on three guide pages, hreflang check; CI jobs added. Weekly link check (1.15) exists in the worker.
- [ ] Test panel of 15 to 20 people (1.16): Chris recruits once the first questions are approved.

## Next

Tasks 0.2 to 0.7 and 0.9 are done (30 October 2026). Next: 0.8 locales; the five new locale files also lack the 0.7 billing strings (`pricing.*`, `billingReturn.activeUntil`, new `errors.*` and `admin.refund*` keys). The five new locale files lack the strings added in 0.5 (they fall back to English; `npm run check:locales` lists them). Known leftovers: German learner screens use "du", old SST copy on the Landing page, main JS chunk over 500 kB.

## Waiting on Chris

- Confirm launch languages (D-014) and whether to write to the Zurich Gemeindeamt about licensing.
- Brand: confirm Viapunt despite the Civi-Go conflict, or choose another (D-017, NAMING.md); attorney trade mark search.
- Edge Caddy change on the tutor server (`infra/edge-snippet.Caddyfile`).
