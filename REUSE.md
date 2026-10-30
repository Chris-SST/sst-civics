# REUSE.md: inventory of the SST Virtual Tutor for the citizenship-test trainer

30 October 2026

The source app is the SST Virtual Tutor in `VSST`, a FastAPI and React web app that gives Swiss Science Tutors' students an AI maths and physics tutor, a question bank with diagnostics and mastery tracking, and Stripe subscriptions. The backend is Python 3.12 or newer with FastAPI (>=0.115), Uvicorn, SQLAlchemy 2 async (>=2.0.30) with asyncpg and aiosqlite, Alembic, Pydantic 2 and pydantic-settings, pwdlib (Argon2), pyotp, Stripe (>=12.0, API version 2026-05-27.dahlia), Redis and arq, httpx, sentry-sdk, the `anthropic` SDK (>=2.3), sympy (>=1.13) and antlr4-python3-runtime (>=4.11,<4.12), tested with pytest and linted with ruff. The front end is React 19, react-router-dom 7, i18next 25 with react-i18next 16, Vite 7 with vite-plugin-pwa 1, TypeScript 5, plus marked, DOMPurify, KaTeX and qrcode. Version numbers in `pyproject.toml` are minimum bounds, since there is no Python lock file; `web/package-lock.json` pins the front end (for example React 19.3.1, Vite 7.3.7, i18next 25.10.10, katex 0.19.1). Infrastructure is Docker Compose with Caddy, PostgreSQL 16, Redis 7, an arq worker and a backup container, deployed to an Infomaniak VPS by GitHub Actions.

The inspected commit is `199dd45031a326973c7599170e18c281c7ba5da9` ("Worker: health check through arq instead of the API image's HTTP probe"). The repository has no git tags (`git tag` returns nothing), so a tag must be created before copying, as plan instruction 3 requires. The working tree is also not clean: `alembic/versions/0004_question_bank.py` has uncommitted line-wrapping changes (formatting only, from `git diff`). Commit that first, then tag, so the tag matches what was read here.

What is actually built, from `docs/PROGRESS.md` (updated 29 October 2026, tests figure 30 October): Phase 0 is passed; Phase 1 has the chat tutor, gatekeeper, cost logging, question bank pipeline, diagnostic, mastery and practice. Not built: photo upload and screening (blocked on D-031; no table, route or component exists, only `s3_*` and `screening_api_key` settings and one docstring), TutorCruncher link, Ask a tutor, the evaluation suite (README only), data export and deletion (D-019), encrypted TOTP secrets (D-013). There are 59 passing backend tests (counted from `def test_` in `tests/`).

## 1. Summary

Counts are inventory rows, not files; lines are physical lines read from the files (SVG assets counted, fonts and lock files not). Lines under Keep are reusable as they stand; Adapt lines are the starting points that need edits.

| Area | Keep items | Keep lines | Adapt items | Adapt lines | Remove items | Remove lines |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Backend files and groups (section 3, excluding models.py) | 11 | 915 | 30 | 5996 | 3 | 1013 |
| Database tables in `app/models.py` (section 3) | 4 | 99 | 13 | 308 | 2 | 35 |
| Tests (section 3) | 1 | 25 | 8 | 1908 | 1 | 109 |
| Front end (section 4) | 4 | 172 | 28 | 7679 | 3 | 1477 |
| Prompts, evals, infra, CI, docs (section 5) | 3 | 100 | 13 | 1094 | 5 | 991 |
| **Total** | 23 | 1311 | 92 | 16985 | 14 | 3625 |

Overall the codebase is about 21,921 counted lines. Roughly 17% is removed outright, and most of the rest needs real edits because the parent, student and course concepts run through shared code. The bulk of straight reuse is the AI module, email backend, sessions, rate limiting, Stripe wrapper, observability and infra.

## 2. Plan versus code: differences

- The plan lists Infomaniak hosting as kept infrastructure. No code, compose file or CI step mentions Infomaniak; it appears only in `docs/DECISIONS.md` (D-002), `docs/PROGRESS.md` and two runbooks. The stack is provider-neutral Docker Compose, so this is a documentation change.
- The plan removes "homework photo upload and image screening". Neither exists in code. Only configuration (`S3_*`, `SCREENING_API_KEY` in `.env.example` and `app/config.py`), a docstring in `app/llm/service.py`, photo wording in `prompts/base/v1.md` and the `abuse_material` comment on `SafetyFlag.kind` remain.
- The plan says Stripe is adapted for TWINT. TWINT is not in code; payment methods are chosen in the Stripe Dashboard (D-009) and the string appears only in `scripts/stripe_bootstrap.py` output and docs. Checkout `mode: payment` already exists for the add-on products.
- The plan mentions "two-factor" only indirectly. TOTP exists and is mandatory for staff roles, enforced inside `current_auth`.
- The plan has no equivalent of the `tutor` role, but tutors review questions scoped by `tagged_courses`; this is the natural base for the Phase 1 Reviewer role.
- Admin "view as" (impersonation, D-024) is not in the plan's table; it touches 12 files, tests included.
- "Error tracking" is wired through the Sentry SDK but switched off on staging until a provider is chosen (D-005).
- Backups run nightly but stay on the server until `BACKUP_REMOTE` is set (D-002).
- The evaluation suite is only a README.

## 3. Backend inventory

### 3.1 Modules and file groups (excluding `app/models.py`)

| Module | Lines | Action | Reason and what changes |
| --- | ---: | --- | --- |
| `app/main.py` | 118 | Adapt | App factory, CSP, CSRF and security-header middleware stay. Remove the `family`, `portal` and student-chat router wiring; add routers for learn/mock test and reviewer queue. |
| `app/config.py` | 120 | Adapt | Keep the settings pattern. Drop `s3_*` (photo storage), `screening_api_key`, `tutorcruncher_*`, `stripe_trial_days`, `safeguarding_email`, `tutor_name`. Rename SST defaults (`main_site_url`, `email_from`, cookie names `sst_session`, `sst_csrf`). Add pass length, extension length and the Explain-this daily cap. |
| `app/db.py` | 48 | Keep | Async engine, portable `TZDateTime`, `Base`; nothing SST-specific. |
| `app/deps.py` | 72 | Adapt | Auth dependencies stay. `current_auth` forces TOTP for every `is_staff` user (tutor and admin) unless impersonating; role sets must become Learner/Admin/Reviewer. |
| `app/observability.py` | 24 | Keep | Sentry-compatible error tracking with `send_default_pii=False`. |
| `app/jobs.py` | 37 | Keep | Enqueue helper with in-process fallback (`JOBS_INLINE`) and the email job. |
| `app/portal.py` | 59 | Adapt | `/student/home` and `/tutor/dashboard` are stubs for the old roles; `/config` (public config for the front end) is worth keeping. |
| `app/auth/routes.py` | 327 | Adapt | Largest change. Signup takes `account_type` parent/adult and `guardian_confirmed`; login accepts email or student username; `accept-invite`, `forgot/reset-password` and `verify-email` assume passwords and invites. Needs request-link and consume-link endpoints, a self-declared 16+ check, account deletion. Keep csrf, logout, me, totp/*. |
| `app/auth/schemas.py` | 94 | Adapt | `SignupIn`, `FamilyOut`, `UserOut` carry parent and student fields. |
| `app/auth/me.py` | 81 | Adapt | Builds `/me` from user, family and `compute_access`, with impersonation fields. Becomes user plus entitlements per canton. |
| `app/auth/sessions.py` | 116 | Adapt | Server-side hashed sessions, cookies and CSRF reusable. TTL depends on staff status; `IMPERSONATION_TTL` is a staging-only extra. |
| `app/auth/one_time.py` | 68 | Adapt | Single-use hashed tokens are the sign-in-link mechanism. `TOKEN_LIFETIMES` needs `login_link` at 15 minutes and loses `student_invite`. |
| `app/auth/passwords.py` | 26 | Keep | Argon2id via pwdlib. Keep if optional passwords are wanted (plan: optional). |
| `app/auth/ratelimit.py` | 59 | Keep | Redis limiter with in-memory fallback; reuse for link requests. |
| `app/auth/tokens.py` | 14 | Keep | Random token and sha256 helpers. |
| `app/auth/totp.py` | 23 | Keep | Admin and reviewer 2FA via pyotp. Secrets are stored unencrypted today (D-013); fix before launch. |
| `app/billing/access.py` | 38 | Adapt | `compute_access(family)` is built on subscription status, trial and 7-day past-due grace. Replace with an entitlement lookup: pass for a canton valid until a date, plus admin free access. |
| `app/billing/events.py` | 198 | Adapt | Idempotent webhook handlers; all but `on_checkout_completed` are subscription handlers. Keep the dispatcher and checkout-completed; grant an entitlement from the line item's price lookup key. |
| `app/billing/plans.py` | 36 | Adapt | Hard-codes `ai_monthly`, `ai_annual`, `hybrid_monthly`, `ask_tutor_single`, `exam_sprint`. Replace with `civics_pass_zh`, `civics_pass_ag`, `civics_extension` and durations. |
| `app/billing/routes.py` | 274 | Adapt | Price lookup by key with a 10 minute cache matches the plan. Subscription Checkout (7-day trial, quantity = students) and the customer portal go. The add-on branch already uses `mode: payment` and is the starting point for one-off passes. |
| `app/billing/stripe_client.py` | 83 | Adapt | Thin wrapper (customer, prices by lookup key, checkout, portal, event verification) reusable. Drop `retrieve_subscription`; keep line-item retrieval. |
| `app/family/*` | 273 | Remove | Parent-managed students, usernames, year of birth, IB curricula and course lists. Whole module, router and `tests/test_students.py`. |
| `app/llm/client.py` | 435 | Keep | Provider protocol, `AnthropicProvider` with streaming and Batch API (`batch_create/status/results`), `DisabledProvider`, `FakeProvider`. Only the fake demo reply is maths text. |
| `app/llm/pricing.py` | 48 | Keep | Per-model price table and USD to CHF cost. |
| `app/llm/prompts.py` | 189 | Adapt | Versioned loader (highest `vN` wins, version label logged) stays. Course concepts (`course_module_key`, `course_level` SL/HL, `CourseInfo`, `topics.json` in en/de/fr) become canton/topic modules. |
| `app/llm/service.py` | 439 | Adapt | Cost logging, budget alerts, gatekeeper, streaming reply and summary stay. `build_system` always appends the `figures` prompt; `LANGUAGE_NAMES` is en/de/fr only; context is course/topic/mastery; docstring still lists photos as sent data; wellbeing labels target minors. |
| `app/questions/bank.py` | 372 | Adapt | Candidate pool, closest-difficulty selection, recent-attempt avoidance, attempt submission, mastery overview: the practice engine. Rework for the canton/category/four-option model and study modes. |
| `app/questions/checks.py` | 208 | Remove | SymPy and LaTeX answer equivalence, numeric tolerance, significant figures. Lift `tokens`, `similarity`, `is_near_duplicate` (about 25 lines) for the duplicate check. |
| `app/questions/mastery.py` | 89 | Adapt | Elo-style rating (start 1200, K 64 then 32), 0 to 100 score, review intervals. Reusable for Practise; the plan's understood/known rule is a new layer. |
| `app/questions/pipeline.py` | 629 | Adapt | Batch or direct generation, independent solve, checks, spot-check sampling, structured marking. Keep batch plumbing and answer agreement; replace maths checks with a source check; drop `mark_structured`; add translation and back-translation. Plan wants CLI scripts. |
| `app/questions/routes_admin.py` | 370 | Adapt | Review queue, edit/approve/retire, stats, generate, batch poll, reports, scoped by tutor `tagged_courses`. Becomes content review; `AVAILABLE_MODULES` is hard-coded to the IB modules. |
| `app/questions/routes_student.py` | 356 | Adapt | Overview, diagnostic, next, round, check, attempts, report. Becomes Learn/Practise/Mock; `require_learner` and `_own_course` checks on `user.courses` go. |
| `app/tutoring/routes.py` | 620 | Adapt | SSE chat, gatekeeper, three-strikes off-topic rule, summary refresh. Becomes Explain this attached to a question. Remove notice-seen and `_notify_safeguarding`. |
| `app/tutoring/admin_routes.py` | 226 | Adapt | `/ai-usage` (cost dashboard) kept. `/safety-flags` with audited transcript view is the minors' safeguarding queue: remove. |
| `app/tutoring/limits.py` | 85 | Adapt | Daily and monthly caps in Europe/Zurich time, read from the `plans` table. Keep the counting; flat 20 per day. |
| `app/admin/routes.py` | 430 | Adapt | 13 routes: overview, families, free access, staff, 2FA reset, plans, audit, impersonate. Keep overview, audit, 2FA reset, free access; rename family to learner; staff invite becomes reviewer invite; plan-limit editing goes. |
| `app/email/backend.py` | 83 | Keep | Console, SMTP and memory backends; provider-neutral. |
| `app/email/messages.py` | 195 | Adapt | en/de/fr templates: verify_email, reset_password, student_invite, staff_invite, trial_ending, cost_alert, safeguarding_alert, payment_failed. Add login_link, pass expiry, receipt; delete student invite, trial, safeguarding; SST signature; more languages. |
| `worker/main.py` | 41 | Adapt | arq settings with crons `reconcile_subscriptions`, `purge_sessions`, `poll_generation_batches`. Swap reconcile for expiry reminders. |
| `worker/tasks.py` | 134 | Adapt | Email, Stripe event processing, session purge, generation. Drop `reconcile_subscriptions` and `apply_subscription`. |
| `scripts/seed.py` | 74 | Adapt | Seeds plans and first admin; plans seeding changes. |
| `scripts/stripe_bootstrap.py` | 63 | Adapt | Creates prices by lookup key in rappen; replace the five SST prices with the three civics keys, all one-off. |
| `alembic/env.py, script.py.mako, alembic.ini` | 118 | Keep | Standard async setup. |
| `alembic/versions/0001 to 0004` | 532 | Remove | 0001 families, users, sessions, one_time_tokens, plans, stripe_events, payments, audit_log; 0002 adds `sessions.impersonator_user_id`; 0003 conversations, messages, llm_calls, safety_flags, cost_alerts; 0004 generation_batches, questions, question_reports, attempts, topic_mastery, diagnostic_runs. Write one new initial migration. |

### 3.2 `app/models.py` (489 lines, 19 tables)

Role constants (`ROLE_PARENT`, `ROLE_STUDENT`, `ROLE_ADULT`, `ROLE_TUTOR`, `ROLE_ADMIN`, `PAYER_ROLES`, `STAFF_ROLES`), `LOCALES = ("en", "de", "fr")` and the token and question status constants at the top are Adapt. Line counts below run from each class to the next.

| Table (class) | Lines | Action | Reason and what changes |
| --- | ---: | --- | --- |
| `families` (`Family`) | ~31 | Adapt | Paying household and Stripe customer. Remove `guardian_confirmed_at`, `quantity`, `trial_end`, `past_due_since`, `payment_warning`, `cancel_at_period_end`, `tutor_credits`, `exam_sprint_purchased_at`, subscription fields. Keep `stripe_customer_id`, terms version and time, `free_access_until` and reason. Merge into the user and add an entitlements table (canton, valid until, source payment). |
| `users` (`User`) | ~43 | Adapt | Remove `family_id`, `username`, `year_of_birth`, `curriculum`, `courses`, `tutor_notice_seen_at`. Keep email, verified time, locale, active, last login, TOTP. Add study language, canton, 16+ declaration. `tagged_courses` and `available` become reviewer scope. Role strings (parent, student, adult, tutor, admin) become learner, admin, reviewer. |
| `sessions` (`Session`) | ~21 | Adapt | Hashed token, expiry, `mfa_pending` kept; `impersonator_user_id` only if view-as is kept. |
| `one_time_tokens` (`OneTimeToken`) | ~16 | Adapt | Becomes the sign-in link store; add `login_link`, drop `student_invite`. |
| `plans` (`Plan`) | ~13 | Remove | Message limits per subscription plan. Prices already live in Stripe by lookup key; use a small products config for the three keys and durations. |
| `stripe_events` (`StripeEvent`) | ~13 | Keep | Webhook idempotency and audit. |
| `payments` (`Payment`) | ~13 | Adapt | Keyed on `stripe_invoice_id` and `family_id`; one-off Checkout has no invoice, so key on payment intent or session and link to user and canton. Billing records survive account deletion. |
| `audit_log` (`AuditLog`) | ~28 | Keep | Admin actions, no message content. |
| `conversations` (`Conversation`) | ~27 | Adapt | `course_key`, `topic_code`, `student_id`; becomes an Explain-this thread tied to a question id and version. |
| `messages` (`Message`) | ~22 | Adapt | Content, gate label, counted flag; rename `student_id`. Learner text, so deletion must cascade. |
| `llm_calls` (`LlmCall`) | ~24 | Keep | Tokens, USD and CHF cost, latency, prompt version, purpose; no content. Rename `student_id`; add translation purposes. |
| `safety_flags` (`SafetyFlag`) | ~22 | Remove | Safeguarding queue (wellbeing, override, abuse material) for minors. See question 2. |
| `cost_alerts` (`CostAlert`) | ~34 | Keep | One alert per kind, scope, month. |
| `generation_batches` (`GenerationBatch`) | ~24 | Adapt | Provider batch ids; `module_key`, `level`, `topic_codes`, `difficulties` become canton, category and pipeline stage. |
| `questions` (`Question`) | ~37 | Adapt | Rewrite. Maths fields (`level` SL/HL, `qtype`, `calculator_allowed`, `unit`, `tolerance`, `worked_solution`, `mark_scheme`, `marks`) go. Review fields (status, reviewer, note, report count, spot check, check results, prompt version) stay. Add stable id and version, scope, category, four options, explanation, sources with checked dates, glossary terms, and a translations child table tied to the German version. |
| `question_reports` (`QuestionReport`) | ~15 | Adapt | Learner flag with comment and resolved time; add report type (wrong, unclear, translation). |
| `attempts` (`Attempt`) | ~26 | Adapt | Drop `answer_text`, `score`, `feedback`, `ai_marked`, `course_key`; add study mode and language; modes diagnostic/practice/check become learn/practise/mock. |
| `topic_mastery` (`TopicMastery`) | ~19 | Adapt | Rating, attempts, next review per user and topic; reusable. The understood/known state is per question and mode, which this table does not hold. |
| `diagnostic_runs` (`DiagnosticRun`) | ~14 | Adapt | Fixed list of question ids with position and status; reuse as mock test runs (add start, deadline, score, pass mark). |

### 3.3 Tests

| Module | Lines | Action | Reason and what changes |
| --- | ---: | --- | --- |
| `tests/conftest.py` | 199 | Adapt | Schema fixture, CSRF-aware `Api` client and outbox helpers reusable; `signup_and_verify`, `parent_logged_in`, `create_staff` assume parent signup. |
| `tests/test_auth.py (8 tests)` | 136 | Adapt | Signup, verify, login, reset; rewrite for sign-in links. |
| `tests/test_access_and_csrf.py (3)` | 79 | Adapt | CSRF and role access; imports `parent_logged_in`. |
| `tests/test_staff_2fa.py (4)` | 92 | Adapt | Admin 2FA stays; uses tutor staff fixtures. |
| `tests/test_billing.py (8)` | 384 | Adapt | Mocked Stripe, webhook idempotency, access rules; rewrite for one-off passes. |
| `tests/test_stripe_client.py (1)` | 25 | Keep | Wrapper test. |
| `tests/test_impersonation.py (3)` | 74 | Adapt | Keep only if admin view-as is kept. |
| `tests/test_students.py (5)` | 109 | Remove | Parent-managed students and invites. |
| `tests/test_questions.py (12)` | 491 | Adapt | Pipeline, checks, review, mastery, practice; maths-check cases go. |
| `tests/test_tutor.py (15)` | 453 | Adapt | Gatekeeper, limits, streaming, summaries; safeguarding cases go. |

## 4. Front-end inventory

| Module | Lines | Action | Reason and what changes |
| --- | ---: | --- | --- |
| `web/src/App.tsx` | 106 | Adapt | Route table with `RequireRole`; `/parent/*`, `/student/*`, `/tutor/*`, `/accept-invite`, `/reset-password` change; lazy loading stays. |
| `web/src/api.ts` | 124 | Adapt | `ApiError` and CSRF-aware helpers reusable; types `UserOut.role`, `FamilyOut`, `StudentOut`, `PlanOut` rewritten. |
| `web/src/auth.tsx` | 87 | Adapt | `AuthProvider`, `RequireRole` kept; `homeFor` maps parent/adult to `/parent`. |
| `web/src/main.tsx, index.html, tsconfig.json` | 55 | Keep | Bootstrap and TS config; retitle index.html. |
| `web/src/i18n.ts` | 66 | Adapt | Three hard-coded languages, localStorage key `sst.lang`, browser guess for de/fr only. Make data-driven; no RTL handling exists (Arabic is later). |
| `web/src/locales/*.json (en-GB, de-CH, fr-CH)` | 1732 | Adapt | About 575 lines each, same keys. Delete parent, student, family, plans, safeguarding, impersonation and maths strings; translate the rest into the other launch languages. Question content stays out of these files. |
| `web/src/practice.ts` | 85 | Adapt | Types for the practice API (`QType` mcq/numeric/short/structured, `module_key`, `calculator_allowed`, mastery overview). |
| `web/src/styles.css` | 1537 | Adapt | One stylesheet in SST green, Lexend and Rethink Sans; rebrand, drop figure, chat-maths and parent classes. |
| `web/vite.config.ts` | 41 | Adapt | vite-plugin-pwa (autoUpdate, `/api/` excluded from navigate fallback) stays; manifest name, description, colours, icons are SST's. |
| `web/package.json (+ package-lock.json)` | 33 | Adapt | See section 6. |
| `web/public/ SVG assets (brand, icons)` | 5 | Adapt | SST logos and placeholder PWA icons, plus self-hosted woff2 fonts: replace with new brand, keep self-hosting. Line count is SVG only. |
| `components/ErrorText.tsx` | 18 | Keep | Maps API error codes to translated text. |
| `components/Layout.tsx` | 129 | Adapt | Header, language switch, footer, env banner, impersonation banner. Footer needs the independence notice. |
| `components/Figure.tsx` | 968 | Remove | Hand-written SVG renderer and expression parser for maths figures (D-042). |
| `components/RichText.tsx` | 90 | Adapt | marked, DOMPurify and KaTeX. Keep markdown and sanitising; drop KaTeX. |
| `components/QuestionCard.tsx` | 267 | Adapt | Answer entry for four question types, result, solution, report, `MasteryBar`. Reduce to four options; add the four study modes. |
| `components/QuestionReview.tsx` | 549 | Adapt | Review queue with filters, stats, edit/approve/retire, shared by tutors and admin. Add sources, version, translation status. |
| `pages/Landing.tsx` | 61 | Adapt | Marketing and plan cards from `/api/billing/plans`; the guide site replaces marketing. |
| `pages/Signup.tsx` | 128 | Adapt | Parent or adult account type plus guardian checkbox; becomes email, 16+ declaration, terms. |
| `pages/Login.tsx` | 96 | Adapt | Email or username with password; becomes email-link request. |
| `pages/VerifyEmail.tsx` | 50 | Adapt | Token landing page; reuse as sign-in link landing. |
| `pages/ForgotPassword.tsx, ResetPassword.tsx` | 127 | Adapt | Keep only if optional passwords are kept. |
| `pages/AcceptInvite.tsx` | 76 | Remove | Student and staff invite acceptance with password; reviewer invites can use the sign-in link. |
| `pages/TwoFactor.tsx` | 85 | Keep | TOTP setup with QR and verify. |
| `pages/ParentDashboard.tsx` | 433 | Remove | Student management, plan selection, Checkout, portal. A small Account page (pass status, buy or extend, delete account) replaces it. |
| `pages/BillingReturn.tsx` | 40 | Adapt | Post-Checkout return page. |
| `pages/StudentHome.tsx` | 360 | Adapt | Course picker, diagnostic call to action, work-on-next, mastery bars. Becomes the Learn/Practise/Mock hub. |
| `pages/StudentPractice.tsx` | 221 | Adapt | Rounds of five with mastery change; basis for Practise. |
| `pages/StudentDiagnostic.tsx` | 162 | Adapt | Fixed-list runner with skip; closest basis for Mock test (needs timer, no help, scoring). |
| `pages/StudentChat.tsx` | 353 | Adapt | SSE chat with streaming and check questions; becomes the Explain this panel. |
| `pages/TutorDashboard.tsx` | 74 | Adapt | Hosts `QuestionReview`; becomes the Reviewer screen. |
| `pages/AdminDashboard.tsx` | 543 | Adapt | Overview, Stripe events, families, free access, staff, plans, audit, impersonation. Rename and trim. |
| `pages/AdminQuestions.tsx` | 355 | Adapt | Generate, batches, reports. Generation moves to scripts. |
| `pages/AdminTutor.tsx` | 258 | Adapt | AI usage tab (keep) and safeguarding flags tab (remove). |
| `pages/NotFound.tsx` | 14 | Keep | Trivial. |

## 5. Prompts, evals, infrastructure, CI and documents

| Module | Lines | Action | Reason and what changes |
| --- | ---: | --- | --- |
| `prompts/README.md` | 18 | Adapt | Versioning convention kept; rewrite the table. |
| `prompts/base/v1.md` | 80 | Adapt | Persona for secondary-school maths and science; says the student is usually under 18, has KaTeX rules, photo reading, school AI rules. Rewrite for Explain this. |
| `prompts/courses/ (ib_maths_aa, ib_maths_ai, ib_physics)` | 520 | Remove | IB modules (v1.md, examples.md, topics.json each). Keep the three-file shape as template for canton/topic modules. |
| `prompts/figures/v1.md` | 65 | Remove | Figure vocabulary; loaded unconditionally by `llm/service.py`. |
| `prompts/gatekeeper/v1.md` | 47 | Adapt | Labels on_topic, borderline, off_topic, override, wellbeing for school students. Rescope to civics; add legal-advice-about-own-application. |
| `prompts/summary/v1.md` | 15 | Adapt | Running summary; probably unneeded for short chats. |
| `prompts/replies/v1.json` | 27 | Adapt | Fixed replies in en/de/fr; add launch languages. |
| `prompts/questions/generate/v1.md` | 33 | Adapt | Maths and school contexts to replace with source-grounded civics questions in German. |
| `prompts/questions/solve/v1.md` | 17 | Adapt | Independent answering pass (kept in plan); drop LaTeX and numeric formats. |
| `prompts/questions/mark/v1.md` | 16 | Remove | Structured-answer marking; target questions are multiple choice. |
| `evals/README.md` | 5 | Adapt | Only a README; the suite does not exist (PROGRESS: not started). |
| `infra/Dockerfile.api, Dockerfile.web` | 43 | Keep | Python 3.12-slim non-root image; web image builds the Vite bundle. |
| `infra/docker-compose.yml` | 122 | Adapt | caddy, api, worker, migrate, postgres 16, redis 7, backup. Rename images, volumes, domain; add the guide site. |
| `infra/docker-compose.dev.yml` | 28 | Keep | Postgres, Redis, Mailpit. |
| `infra/Caddyfile` | 37 | Adapt | Static files plus `/api` proxy; split main domain (guide) from `app.`. |
| `infra/backup.sh` | 29 | Keep | pg_dump, gzip, optional GPG, rclone to `BACKUP_REMOTE`, 30 day pruning. |
| `.github/workflows/ci.yml` | 127 | Adapt | Ruff, migrations up/down on PostgreSQL, pytest on SQLite and PostgreSQL, web build, pip-audit and npm audit (both `|| true`), Trivy, deploy on `v*` tags over SSH when `STAGING_DEPLOY_ENABLED`. Rename images; add content checks. |
| `docs/runbooks/ (5 files)` | 275 | Adapt | backups-and-restore, deploy-staging, stripe-test-mode, stripe-outage, README; rewrite hosts and Stripe sections. |
| `docs/PROGRESS.md, DECISIONS.md` | 126 | Remove | Start fresh in the new repo; mine D-002 to D-006, D-009, D-012, D-014, D-016, D-018 for rationale. |
| `docs/DEMO_PHASE0.md, DEMO_PHASE1.md, POSITIONING_PROPOSAL.md` | 264 | Remove | SST demo scripts and marketing positioning; use as a format for the new demo script. |
| `pyproject.toml, .env.example, README.md, CLAUDE.md` | 291 | Adapt | Metadata, env template, instructions; remove SST hosts and photo and TutorCruncher variables. |

## 6. Dependencies

Python to drop:

- `sympy` and `antlr4-python3-runtime`: used only by `app/questions/checks.py` (the antlr runtime is for `sympy.parsing.latex`).
- `pwdlib[argon2]`: drop only if passwords are not offered at all (plan says optional). Default: keep.
- `pyotp`: keep for admin and reviewer 2FA.
- `aiosqlite`: keep; tests and laptop development run on SQLite (D-012).

Python to add (each subject to the plan's rule on new third parties):

- A YAML and Markdown front-matter parser (for example PyYAML or python-frontmatter) for question and guide content files imported on deploy.
- A JSON-schema or Pydantic-based content validator for the build-time content check (no new library needed if Pydantic is used).
- Link checking for the weekly source check can use the existing `httpx`.

npm to drop: `katex` and `@types/katex`. Keep `marked` and `dompurify` (explanations), `qrcode` (admin TOTP setup), `i18next`, `react-i18next`, `react-router-dom`, `vite-plugin-pwa`.

npm and tooling to add: a static site generator or pre-render step for the guide (plan: propose in DECISIONS.md first; candidates are Astro or Eleventy, or pre-rendering in Vite); a browser language detector if automatic interface language selection should cover seven or more languages (currently a hand-written guess for de and fr); self-hosted cookie-less analytics (a separate service, not an npm package). Fonts need a check for Albanian and Turkish glyph coverage; the current self-hosted woff2 files are named `-latin` subsets. Arabic would need RTL CSS and an Arabic font later.

## 7. Removal order and risks

Suggested order. Run `ruff`, `pytest` and `npm run build` after each step.

1. Tag the source commit (after committing the 0004 formatting change), copy to a new repository, change names, cookie names, image tags and `.env.example` hosts first.
2. Remove front-end pages and routes before backend routes: `ParentDashboard`, `AcceptInvite`, `Figure`, then the KaTeX call in `RichText`.
3. Remove the `family` router from `app/main.py`, delete `app/family/` and `tests/test_students.py`.
4. Remove `figures` from `llm/service.py` (it is loaded unconditionally in `prompt_version` and `build_system`), then `prompts/figures`, `prompts/questions/mark` and `questions/checks.py` (keep the duplicate-similarity helpers), then drop `sympy` and `antlr4`.
5. Introduce the new account model: collapse `Family` into `User` plus entitlements, change roles, replace `compute_access`, rewrite billing events and checkout, then rewrite `tests/conftest.py`, `test_auth.py`, `test_billing.py`.
6. Replace the question model, then bank, mastery, routes and the Learn/Practise/Mock front end.
7. Rework the tutor module into Explain this; remove safety flags and the safeguarding email, or reduce them (question 2).

Migrations: write one new initial Alembic migration from the new models rather than chaining 0005 onto the four existing ones. The existing chain builds the parent and student tables and then needs destructive changes to most of them; the new repository has no production data, and CI already tests upgrade, downgrade, upgrade on PostgreSQL. The new `staging` database starts empty. Keep `alembic/env.py` as it is.

Coupling that makes removal awkward:

- Roles and family are everywhere. `ROLE_ADULT`/`ROLE_STUDENT` are imported in `auth/routes.py`, `billing/routes.py`, `portal.py`, `questions/routes_student.py` and `tutoring/routes.py` (each of the last two defines its own `require_learner`). `compute_access(family)` is called from `auth/me.py`, `portal.py`, billing, questions, tutoring and admin routes, and entitlement lives on `Family`. Also the learner columns in `conversations`, `messages`, `attempts`, `topic_mastery`, `llm_calls`, `safety_flags` and `question_reports` are named `student_id` (a rename touching models, services, routes and tests).
- The course concept (`module_key`, `course_key`, `topic_code`, SL/HL level) runs through `llm/prompts.py`, `llm/service.py`, `questions/bank.py`, `pipeline.py`, both question route files, `tutoring/routes.py`, `family/routes.py` (`CURRICULA`, `COURSES`), `practice.ts`, `QuestionCard`, `StudentHome`, `AdminQuestions`, and `AVAILABLE_MODULES`. The question model change is the biggest single piece of work.
- Maths in the prompt layer: `prompts/base/v1.md` and `questions/generate/v1.md` tell the model to write LaTeX, the front end renders it with KaTeX, and `FakeProvider` replies with a maths demo. Remove all three together or the tutor will output unrendered `\( \)` markup.
- 2FA and staff: `current_auth` demands TOTP for all `is_staff` roles, so Reviewers will also need an authenticator. Email-link sign-in must still produce an `mfa_pending` session for admin.
- Impersonation touches sessions, deps, me, auth routes, admin routes, config, models, `api.ts`, `Layout.tsx`, `AdminDashboard.tsx` and a test. It is refused in production by `impersonation_enabled`. Decide whether to keep it before step 5.
- Email templates are keyed by kind and locale with en/de/fr only; every sender uses `send_email_job(kind, locale, ...)`, so adding languages needs a fallback rule.
- Tests that will break at once: everything using `parent_logged_in`, `signup_and_verify` or `create_staff` in `conftest.py` (`test_access_and_csrf`, `test_auth`, `test_billing`, `test_staff_2fa`, `test_impersonation`, `test_students`), and every test that posts to `/api/practice` or `/api/tutor` with a student.
- Stripe: the webhook handlers, nightly reconcile cron, `Family.subscription_*` fields, `Payment.stripe_invoice_id` and the `PAST_DUE_GRACE` rule form one subscription model; replace them together.

## 8. Modules worth sharing later

The plan says copy now and share nothing yet. These are the candidates for a common library, so fixes can be carried across by hand until then:

- `app/llm/` (client, pricing, prompts loader, cost logging and alerts): most reusable, almost product-neutral.
- `app/auth/` session, token, rate limit and TOTP files, plus `app/deps.py`.
- `app/email/backend.py` and the template mechanism.
- `app/billing/stripe_client.py`, the webhook storage and idempotent dispatcher, and the price lookup cache.
- `app/jobs.py`, `worker/` skeleton, `app/db.py`, `app/observability.py`.
- `app/questions/mastery.py` and the batch generation plumbing in `pipeline.py`.
- `web/src/api.ts`, `ErrorText`, `QuestionReview` shell, the PWA config, and the infra folder with `backup.sh`, Dockerfiles and CI.

## 9. Questions for Chris

1. Passwords: keep optional passwords (Argon2, reset flow, two pages) or sign-in link only at launch? This decides whether `pwdlib` and the reset flow stay.
2. Wellbeing and safeguarding: the gatekeeper flags self-harm, abuse and similar to a safeguarding lead. The plan removes the minors' queue, but accounts open from 16. Keep a lighter flag and fixed reply for 16 and 17 year olds?
3. Admin "view as": keep for staging support, or remove with its tests?
4. Reviewer role: base it on the existing tutor role and `tagged_courses` (rename to languages and cantons), or build it later from scratch in Phase 1?
5. The mock test: reuse `DiagnosticRun` as a mock test run, or a new table? Reusing is quicker but its name and fields are diagnostic-specific.
6. SST branding in the copy (green, Lexend and Rethink Sans, SST logos, `swisssciencetutors.ch` hosts, Google Workspace SMTP sender): confirm none of it carries over, since the service is to be independent.
7. Staging: the plan asks for a separate Infomaniak stack and domain; should the new staging reuse the existing SST VPS (83.228.196.57) or a new server?
8. Admin 2FA secrets are still stored unencrypted (D-013, open since Phase 0): fix it in the copy, or in the source first so the fix can be carried across?
