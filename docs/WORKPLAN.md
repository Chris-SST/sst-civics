# Swiss citizenship test trainer – work plan

30 Oct 2026. How the build plan in `PLAN (1).md` will be executed, task by task, with the agent model and effort chosen for each task so that token use stays proportionate to the risk of the work.

## What was established today

- **Source app:** the SST Virtual Tutor at `..\VSST` (FastAPI 0.115, SQLAlchemy 2 async, Alembic, arq worker on Redis, PostgreSQL 16, React 19 + TypeScript + Vite PWA, i18next with en-GB/de-CH/fr-CH, Stripe, Anthropic SDK). About 7,800 backend and 7,700 front-end lines. It is at Phase 1 of its own plan: accounts, 2FA, Stripe subscriptions, admin, chat tutor, gatekeeper, cost log, question bank with batch API, diagnostic, mastery and practice are built.
- **Not the source:** `..\SST_man_app` is the payroll and admin tool; it is unrelated.
- **No git tag exists in VSST.** The plan requires the copy to be taken at a tagged commit. HEAD is `199dd45` ("Worker: health check through arq…"). A tag must be created before copying (see pre-flight).
- **First deliverable under way:** `REUSE.md`, the keep/adapt/remove inventory, drafted by a subagent and awaiting Chris's approval. No code is copied or changed before that approval.

## Working method and token policy

One orchestrator (this session) reads the plan, briefs subagents, reviews their output and keeps PLAN.md, PROGRESS.md and DECISIONS.md current. Subagents do the reading-heavy and mechanical work. Each brief names the files to touch, the tests that must pass, and the rules from the plan that apply (no AI attribution, no secrets, AI calls only through `app/llm/`, never copy cantonal catalogue text).

| Work type | Agent | Why |
| --- | --- | --- |
| Inventories, file sweeps, doc drafting, interface-string translation, test scaffolding, mechanical removals with a clear spec | Sonnet, default effort | Cheap; the task is well defined and the output is checked by tests or by the orchestrator |
| Design decisions with lasting cost: question data model and migrations, study-mode progression and spaced repetition, Stripe one-off entitlements, guide-site rendering choice, translation pipeline | Opus, high effort | Mistakes here are expensive to undo; one careful pass beats several cheap ones |
| Content pipeline runs (drafting questions, independent answering, back-translation) | Not a coding subagent: command-line scripts calling the batch API through `app/llm/`, as the plan requires | Batch API halves cost and keeps every call in the cost log |
| Review of a subagent's change before a gate | Orchestrator, or `/code-review medium` on the diff | Independent read, not anchored on the author |

Rules of thumb: one subagent per task, never two editing the same files at once; a subagent returns a summary and the tests' output, not file dumps; nothing runs in parallel that shares a migration file or `models.py`.

## Pre-flight: items Chris owns (before Phase 0 code)

1. **Approve REUSE.md** (or mark rows to change).
2. **Tag the VSST commit** to copy from, for example `git tag v0.1.0-citizen-base 199dd45` in `..\VSST`, or name a different commit. Recorded in DECISIONS.md.
3. **Repository name and location** for the new app (working name only; brand is an open decision). Default if silent: folder `..\Citizen\app` with a working name `civics` in code.
4. **Hosting account**: confirm the Infomaniak (or other Swiss) server and the staging domain. VSST's own runbooks describe one Swiss VPS with Docker Compose and Caddy; the plan wants a separate stack and domain for this product.
5. **Launch languages** (default: en, fr, it, pt, es, sq, tr; de master) and whether to write to the Zurich Gemeindeamt about licensing their questions now, since the answer changes Phase 1 content work.
6. **Stripe**: a separate Stripe account or the SST account with new products? Default: same account, new products in test mode, lookup keys from the plan.

## Phase 0: Copy and strip (gate A: staging works end to end)

Order matters: copy, then remove, then adapt, then deploy. Each step ends with `ruff check`, `ruff format --check`, `pytest -q` and `npm run build` passing.

| # | Task | Agent | Depends on |
| --- | --- | --- | --- |
| 0.1 | Copy VSST at the tag into the new repo; strip history or keep it (default: fresh `git init`, tag recorded); add PLAN.md, PROGRESS.md, DECISIONS.md, REUSE.md, CLAUDE.md adapted from VSST's | Orchestrator (shell) | Pre-flight 1–3 |
| 0.2 | Remove family, parent/student roles, under-18 rules, parent summaries, minors' safeguarding queue, impersonation if parent-specific, and their tests and locale strings; collapse roles to Learner and Admin | Sonnet, with the removal order from REUSE.md as the spec | 0.1 |
| 0.3 | Remove maths rendering and checks: KaTeX, `Figure.tsx`, `RichText` maths paths, sympy and antlr dependencies, `app/questions/checks.py` maths rules, figure prompts; keep plain Markdown rendering | Sonnet | 0.2 |
| 0.4 | Decide and write the migration strategy: new `0001_initial.py` for the stripped schema versus chaining drop migrations (default: new initial, since there is no production data) | Opus, high | 0.2, 0.3 |
| 0.5 | Sign-in: one-time email link as default (single use, 15 min), password optional, self-declared 16+ check at sign-up, no parental flow; keep admin 2FA; account self-deletion endpoint | Opus, high (auth is security-sensitive) | 0.4 |
| 0.6 | Collected data audit: schema and sign-up form hold only email, interface language, study language, canton, progress, payment status; delete any other field | Sonnet | 0.5 |
| 0.7 | Payments: Stripe Checkout in one-off mode, card and TWINT, products `civics_pass_zh`, `civics_pass_ag`, `civics_extension` by lookup key; entitlement per canton with expiry; webhook sets access; refund rule noted; update `scripts/stripe_bootstrap.py` and billing tests | Opus, high | 0.4 |
| 0.8 | i18n: add pt, es, sq, tr, it locale files for the remaining interface strings (machine first draft, marked for review); Swiss CHF formatting kept | Sonnet | 0.2 |
| 0.9 | Infra: separate compose stack, Caddy site, `.env.example`, backup script target, CI deploy target for the new staging domain; nightly encrypted backup | Sonnet (Opus only if the Caddy/compose split is unclear) | 0.1, pre-flight 4 |
| 0.10 | Phase 0 review: `/code-review medium`, update README, write `docs/DEMO_PHASE0.md`, deploy staging, walk the demo | Orchestrator | all above |

**Gate A checklist** (from the plan): REUSE.md approved; CI and tests pass after removals; learner and admin accounts with email links; Stripe one-off test payments with per-canton entitlements; staging live with its own domain, TLS and nightly backups.

## Phase 1: Zurich launch (gate B)

Content and code run in parallel streams because the content pipeline is the long pole: 350 questions, each through draft, independent answer, source check, human approval, translation into seven languages and back-translation.

**Stream A: question model and admin (code)**

| # | Task | Agent |
| --- | --- | --- |
| 1.1 | Question model: stable ID, version, scope (federal/canton/commune), category, German text with four options and one correct, explanation, sources with checked date, glossary terms, translations tied to a German version, status. Repository files (YAML or JSON per question) are the master; import on deploy; build-time validator (source present, checked date under a year, four options, one correct, translation per launch language or marked missing) | Opus, high |
| 1.2 | Admin review queue adapted from VSST tutor review: approve, edit, send back, retire; translation status screen; learner flags land here | Sonnet |
| 1.3 | Glossary model and admin screen; TERMDAT-sourced official names for fr/it/en | Sonnet |

**Stream B: content pipeline (scripts, batch API)**

| # | Task | Agent |
| --- | --- | --- |
| 1.4 | Topic list for Zurich from the official catalogue's subject headings and the federal and cantonal constitutions (headings only; no catalogue text copied) | Orchestrator with web research, saved as a versioned file |
| 1.5 | Scripts: `draft`, `answer_independently`, `source_check`, `translate`, `back_translate`; versioned prompts under `prompts/`; never overwrite an approved translation; run through `app/llm/` with cost logging | Opus, high for the pipeline design; Sonnet for prompt files and tests |
| 1.6 | Run the pipeline for about 350 Zurich questions in batches of 50; Chris or a reviewer approves in admin; then translation runs | Scripts, not an agent; orchestrator monitors cost |

**Stream C: learning app (code)**

| # | Task | Agent |
| --- | --- | --- |
| 1.7 | Four study modes (own language, side by side, German with help, German only) as a rendering layer over `QuestionCard`; per-question, per-mode progress; "understood" and "known" rules from the plan | Opus, high |
| 1.8 | Learn (topic order of the catalogue), Practise (adapt VSST mastery and practice rounds: spaced repetition, weak-topic weighting, mode progression with step-back), readiness estimate labelled as a practice estimate | Opus, high for the progression logic; Sonnet for pages |
| 1.9 | Mock test: 50 questions in 60 minutes, proportions of the official test, countdown, no help, score against pass mark (30/50 flagged as unconfirmed), review of wrong answers in the learner's language | Sonnet, with tests for counts, proportions, timer and scoring |
| 1.10 | Explain this: adapt the VSST chat tutor and gatekeeper to one question's scope, learner's language, about 20 messages a day, no legal advice about the learner's own case, hidden in mock tests | Sonnet (the module exists; this is configuration and prompts) |

**Stream D: guide website and legal pages**

| # | Task | Agent |
| --- | --- | --- |
| 1.11 | Rendering choice proposed in DECISIONS.md: pre-render inside Vite (for example `vite-ssg` or a build step) versus a separate static generator served by Caddy at the apex domain with the app at `app.` | Opus, medium; Chris approves |
| 1.12 | Pages as Markdown per language: overview, Zurich step by step, the knowledge test, language certificates, fees, residence calculator (browser only), free practice, FAQ; hreflang, sitemap, FAQ markup, cookie-free analytics, footer independence notice, "last checked" dates | Sonnet for scaffolding and templates; orchestrator for the facts and sources; Lighthouse 90+ checked before gate B |
| 1.13 | Terms, privacy notice (AI provider outside Switzerland, deletion, billing records kept), independence notice | Sonnet drafts; Chris and a lawyer review |

**Stream E: quality**

| # | Task | Agent |
| --- | --- | --- |
| 1.14 | Tests: question import, study-mode progression, mock generation, entitlements; end-to-end for free questions, sign-up, mock test, checkout, access expiry; accessibility pass | Sonnet |
| 1.15 | Weekly source link check job in the worker; broken or changed page sends the question to review | Sonnet |
| 1.16 | Test panel of 15–20 people: Chris recruits; orchestrator prepares the feedback form and triage | Chris |

**Gate B checklist**: content approved and translated; panel done and findings fixed; terms and brand ready; nothing sold before this gate.

## Phases 2 and 3

Planned only at headline level until gate B: Aargau (330 questions, five categories, 45 in 40 minutes, pass mark 34, format to confirm from the official practice test), commune pages, more languages (Bosnian/Croatian/Serbian, Macedonian, Tamil, Ukrainian; Arabic needs right-to-left), German audio, then Vaud and Geneva in French and a fide speaking pilot.

## Open decisions with defaults the agent will record

Taken from the plan; each is written to DECISIONS.md with its date when first needed.

| Decision | Default | Needed by |
| --- | --- | --- |
| Brand and domain | Working name in code only | Phase 1 |
| Launch languages | en, fr, it, pt, es, sq, tr | Phase 1 |
| Official question licence | Original questions only | Phase 1 content |
| Price and period | CHF 29 for 6 months; CHF 9 for 3 more | 0.7 |
| Couple discount | None at launch | 0.7 |
| Google/Apple sign-in | Email link only | 0.5 |
| Zurich pass mark | 30 of 50, labelled unconfirmed | 1.9 |
| VAT and purpose clause | Chris's accountant and notary | Before gate B |
| App stores | Installable web app only | After launch |
| Source commit | Tag to be created on VSST HEAD `199dd45` | 0.1 |

## Next actions

1. Chris reads REUSE.md and this work plan and answers pre-flight items 1 to 6.
2. On approval: task 0.1 (copy at the tag) and 0.2 (removals) start the same day.
