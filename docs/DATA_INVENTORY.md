# Data inventory

What the app stores about a person, why, for how long, and what happens on account deletion.
Result of the task 0.6 audit on 30 October 2026, read from `app/models.py`, the request schemas
(`app/auth/schemas.py`, `app/admin/routes.py`, `app/questions/routes_student.py`,
`app/billing/routes.py`) and the sign-up form (`web/src/pages/Signup.tsx`).

**Audit result.** Sign-up collects only email, interface language, study language, canton, the
"16 or older" confirmation and acceptance of the terms; the password is optional. No name,
nationality, permit type, date of birth, address or phone number is collected or stored. The one
place where further personal data could arrive was Stripe webhook payloads (customer email, name,
address); these are now stored without those details (`scrub_personal_fields` in
`app/billing/events.py`). No other personal field was found, so no column was deleted.

Backups hold everything below for up to 30 days after it leaves the live database
(`docs/runbooks/backups-and-restore.md`).

## Account (`users`)

| Field | Purpose | Retention | Deleted on account deletion |
| --- | --- | --- | --- |
| `email` | Sign-in links, account emails | Life of the account | Yes |
| `email_verified_at` | Proves the address was confirmed | Life of the account | Yes |
| `locale` (interface language) | Language of the interface and emails | Life of the account | Yes |
| `study_language` | Language the questions are shown in first | Life of the account | Yes |
| `canton` | Which canton's test is studied; access is per canton | Life of the account | Yes |
| `age_confirmed_at` | Self-declared "16 or older" (no date of birth) | Life of the account | Yes |
| `terms_version`, `terms_accepted_at` | Which terms were accepted, and when | Life of the account | Yes |
| `role`, `is_active` | Learner or admin; account switched off by an admin | Life of the account | Yes |
| `password_hash` (optional) | Argon2id hash, for password sign-in | Until removed by the learner or the account is deleted | Yes |
| `totp_secret`, `totp_enabled` | Two-factor authentication (admins); secret encrypted at rest | Until reset or the account is deleted | Yes |
| `stripe_customer_id` | Links the account to its Stripe customer (payment status) | Life of the account | Yes |
| `created_at`, `last_login_at` | Security and support | Life of the account | Yes |

## Security records

| Field | Purpose | Retention | Deleted on account deletion |
| --- | --- | --- | --- |
| `sessions` (token hash, expiry, last seen, `mfa_pending`, `email_link_at`) | Signed-in sessions | 14 days rolling for learners, 12 hours for admins; expired rows purged hourly | Yes |
| `one_time_tokens` (token hash, kind, expiry, used) | Sign-in links (15 min), email confirmation (24 h), password reset (30 min) | Purged one day after expiry | Yes |
| `audit_log` (actor id, action, target id) | Record of admin actions; no message content | Kept | Rows stay; the person's id is removed as actor; a `user.self_delete` row records the deletion by account id only |

## Progress data

| Field | Purpose | Retention | Deleted on account deletion |
| --- | --- | --- | --- |
| `attempts` (question, answer given, score) | Practice history | Life of the account | Yes |
| `topic_mastery` | Progress per topic, spaced repetition | Life of the account | Yes |
| `diagnostic_runs` | Placement test | Life of the account | Yes |
| `conversations`, `messages` (tutor chat text) | Tutor sessions; content is never logged or sent with identifiers | Life of the account | Yes |
| `question_reports` (optional comment) | Learner reports a faulty question | Until resolved, or the account is deleted | Yes (the question's open-report count is reduced) |
| `entitlements` | Access to a canton's content for a period (payment status) | Life of the account | Yes |

## Kept after deletion

| Field | Purpose | Retention | Deleted on account deletion |
| --- | --- | --- | --- |
| `payments` (product, canton, months, Checkout Session and payment intent ids, amount, currency, paid and refunded dates) | Accounting records | 10 years (Swiss Code of Obligations, art. 958f) | No: `user_id` set to null, keyed hash of the email stored in `email_hash` |
| `llm_calls` (tokens, cost, model, latency; no content) | AI cost accounting and budgets | Kept | No: `user_id` set to null |
| `stripe_events` (webhook payloads, without contact or address details) | Idempotency and audit of payment events | Kept | No: payloads naming the person's customer or account id are reduced to event id and type |
| `cost_alerts` (scope may be a user id) | One alert per threshold and month | Kept | No (holds an id only) |
