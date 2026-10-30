# Progress

Done and next, per phase checklist in PLAN.md. Updated 30 October 2026.

## Phase 0: Copy and strip (gate A: staging works end to end)

- [x] REUSE.md written and approved (D-002).
- [x] New repository from a copy of the SST app at tag `v0.1.0-citizen-base` (D-001); source docs moved to `docs/source-app/`.
- [ ] CI and tests pass after the removals.
  - [ ] 0.2 Remove family, parent/student/tutor roles, under-18 rules, parent summaries, safeguarding queue; collapse to Learner and Admin.
  - [ ] 0.3 Remove maths rendering and checks (KaTeX, figures, sympy, LaTeX prompts).
  - [ ] 0.4 New initial migration (D-005).
- [ ] Learner and admin accounts with email sign-in links (0.5, 0.6).
- [ ] Stripe one-off payments working in test mode, with entitlements per canton (0.7).
- [ ] Interface locales for the launch languages (0.8).
- [ ] Staging site live on the shared VPS with its own host names, TLS and nightly backups (0.9, D-004).
- [ ] Phase 0 review, README, `docs/DEMO_PHASE0.md`, demo walked (0.10).

## Next

Baseline of the untouched copy passed on 30 October 2026 (ruff clean, 59 tests, web build) on Python 3.14. Tasks 0.2 (roles and family removal with the new initial migration) and 0.9 (infrastructure) are in progress.

## Waiting on Chris

- GitHub repository for this code (CI and deploys need it).
- DNS records for the staging host names (D-004) or a different naming.
- Confirm launch languages (D-014) and whether to write to the Zurich Gemeindeamt about licensing.
