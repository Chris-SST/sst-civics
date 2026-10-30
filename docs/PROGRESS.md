# Progress

Done and next, per phase checklist in PLAN.md. Updated 30 October 2026.

## Phase 0: Copy and strip (gate A: staging works end to end)

- [x] REUSE.md written and approved (D-002).
- [x] New repository from a copy of the SST app at tag `v0.1.0-citizen-base` (D-001); source docs moved to `docs/source-app/`.
- [ ] CI and tests pass after the removals (tests pass locally; CI needs the GitHub repository).
  - [x] 0.2 Remove family, parent/student/tutor roles, under-18 rules, safeguarding queue; collapse to Learner and Admin (D-018 to D-025). 61 tests.
  - [x] 0.3 Remove maths rendering and checks (KaTeX, figures, sympy, LaTeX prompts, mark-scheme marking); multiple choice is the only question kind; prompts bumped to v2. 64 tests.
  - [x] 0.4 New initial migration (D-005).
- [x] Learner and admin accounts with email sign-in links (0.5, 0.6; D-027 to D-032). Optional learner passwords, encrypted TOTP secrets, account self-deletion, data inventory in `docs/DATA_INVENTORY.md`. 89 tests.
- [x] Stripe one-off payments working in test mode, with entitlements per canton (0.7; D-033 to D-038). Civics Pass and extension by lookup key, one-off Checkout, webhook grants, refund rule and admin refund, `plans` table removed. 105 tests.
- [ ] Interface locales for the launch languages (0.8).
- [ ] Staging site live on the shared VPS with its own host names, TLS and nightly backups (0.9 code done, D-004; deploy waits on DNS, the edge Caddy change and a GitHub repository).
- [ ] Phase 0 review, README, `docs/DEMO_PHASE0.md`, demo walked (0.10).

## Next

Tasks 0.2 to 0.7 and 0.9 are done (30 October 2026). Next: 0.8 locales; the five new locale files also lack the 0.7 billing strings (`pricing.*`, `billingReturn.activeUntil`, new `errors.*` and `admin.refund*` keys). The five new locale files lack the strings added in 0.5 (they fall back to English; `npm run check:locales` lists them). The IB course modules under prompts/courses still hold maths examples; they go with the question model in Phase 1. Known leftovers: German learner screens use "du", old SST copy on the Landing page, main JS chunk over 500 kB.

## Waiting on Chris

- GitHub repository for this code (CI and deploys need it).
- DNS records for the staging host names (D-004) or a different naming.
- Confirm launch languages (D-014) and whether to write to the Zurich Gemeindeamt about licensing.
- Brand: confirm Civigo despite the Civi-Go conflict, or choose another (D-017, NAMING.md); attorney trade mark search.
- Edge Caddy change on the tutor server (`infra/edge-snippet.Caddyfile`).
