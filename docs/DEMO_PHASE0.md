# Phase 0 demo script (gate A)

Gate A: staging works end to end. Chris can sign up as a learner, pay in test mode, see access begin and end, and sign in as admin with an authenticator.

Takes about 40 minutes. Two ways to run it: on **staging** (`https://app.civics-staging.swisssciencetutors.ch`, host names are the defaults of D-004) or **locally** with the SQLite setup in [README.md](../README.md). The steps are the same; only where emails arrive differs.

You need: an authenticator app on your phone, a second email address you can read, and the Stripe test-mode Dashboard open in a tab.

## Before the demo

Each item is a one-off. Items marked "open" are not done yet (see [PROGRESS.md](PROGRESS.md)).

- Staging only. DNS `A` records (and `AAAA`) for `civics-staging.swisssciencetutors.ch` and `app.civics-staging.swisssciencetutors.ch` to `83.228.196.57` (open).
- Staging only. The edge Caddy change on the tutor stack: shared `edge` network and the block from `infra/edge-snippet.Caddyfile` (open). Until then the names return 502.
- Staging only. The code on the server in `/opt/civics`, by upload or `git clone`; the GitHub repository does not exist yet (open). Without it CI does not run and tag deploys are off.
- Staging only. `.env` set as in [runbooks/deploy-staging.md](runbooks/deploy-staging.md) section 4 with `EMAIL_BACKEND=smtp`, then first start (section 5).
- Admin: created with `scripts/seed.py` (`ADMIN_EMAIL`, `ADMIN_PASSWORD`; see README). Locally: `ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m scripts.seed`.
- Stripe: test keys in `.env`; `python -m scripts.stripe_bootstrap` run; cards and TWINT enabled in the Dashboard; webhook endpoint `/api/billing/webhook` with the four events and its `whsec_...` in `STRIPE_WEBHOOK_SECRET` (locally `stripe listen`). See [runbooks/stripe-test-mode.md](runbooks/stripe-test-mode.md).
- The chat needs the AI to be on: `ANTHROPIC_API_KEY` on staging, or `LLM_FAKE=true` locally (canned replies).
- The five newer interface languages are machine drafts and some billing strings still fall back to English (0.8 is open); expect that in step 6.
- Locally, emails are `.eml` files in `var/outbox/`; open one and copy the link. Staging sends real email.

## 1. Learner: sign up

1. Open the app and press **Sign up** (`/signup`). The page says accounts are for people aged 16 and over.
2. Fill in: email address, interface language, study language, canton (Zurich or Aargau are offered), and tick **I am 16 or older** and the terms. Leave **Also set a password (optional)** unticked.
3. Check the language lists: interface and study language each offer German, English, French, Italian, Portuguese, Spanish, Albanian and Turkish. No name, date of birth, nationality or address is asked.
4. Press **Create account**. You should see "Check your email", with "The link also signs you in."

## 2. Verification email as first sign-in

1. Open the email (in your inbox, or `var/outbox/`). It is in the interface language you chose, or English where no translation exists.
2. Follow the link (`/verify-email`). You should see "Your email address is confirmed and you are signed in" and be signed in without a password. The link is valid for 24 hours (D-028).
3. Open the same link again: it must be refused (single use).

## 3. Sign in by email link, optional password

1. Sign out. On `/login` enter the same address and press **Send me a sign-in link**. The reply is the same for known and unknown addresses (try a made-up one: no email arrives, no account is created).
2. Open the new email and follow the link (`/auth/link`). You land on your account signed in. The link lasts 15 minutes and works once.
3. On `/account`, under the password section, set a password (10 or more characters, entered twice). You should see the saved message.
4. Sign out and sign in with that password (**Sign in with a password instead**). Then back on `/account` enter the current password under the removal box and press **Remove password**. Sign out: only the link works now.

## 4. Language switcher

1. Use the language menu in the header. Switch through all eight in turn: English, Deutsch, Français, Italiano, Português, Español, Shqip, Türkçe.
2. In each, the header, learner page and pricing panel should change language. German should use "Sie". Italian, Portuguese, Spanish, Albanian and Turkish are machine drafts awaiting native review; missing strings show English.
3. On `/account` change the interface language and save; it should persist after a reload.

## 5. Pricing and the Civics Pass

1. Sign in and open the learner page (`/learner`). The **Civics Pass** panel shows "Civics Pass ZH", the period "for 6 months", and the price in CHF. The learner status is **Free practice**.
2. Compare the amount with the Stripe Dashboard, Product catalogue, product `civics_pass_zh` (test mode). They must match: the app reads the price from Stripe by lookup key (it takes up to 10 minutes to notice a changed price).
3. Only Zurich is on sale (`CANTONS_FOR_SALE=zh`). Aargau does not appear.
4. The line "Prices in CHF. Paid once, by card or TWINT, through Stripe." is shown. There is no subscription.

## 6. Test purchase by card

1. Press **Buy**. Stripe Checkout opens in test mode showing CHF and the pass.
2. Pay with `4242 4242 4242 4242`, any future date, any CVC, any name.
3. You return to `/billing/return`. You should see "Waiting for Stripe to confirm your payment", then "Thank you. Your Civics Pass for ZH is active until ..." (about six months ahead), within a few seconds. This comes from the webhook, not the redirect.
4. Press **Go to your dashboard**. The panel shows "Active until ..." and an **Extend by 3 months** button; **Buy** is gone for Zurich.
5. In the Stripe Dashboard, Developers, Webhooks, the endpoint should show `checkout.session.completed` delivered with a 200.

## 7. Test purchase with TWINT

1. Use a second, fresh learner account in Zurich (repeat steps 1 and 2 with another address); an active pass blocks a second purchase for the same canton.
2. Press **Buy** and choose **TWINT** on the Checkout page. Stripe shows a simulated TWINT page.
3. Press **Authorise**. You return to `/billing/return` and the pass becomes active as in step 6. (The **Fail** button leaves the payment unpaid and grants nothing; try it once on a third account if you wish.)
4. If TWINT is missing on the Checkout page, it is not enabled in the Dashboard (Settings, Payment methods).

## 8. Chat (the "Explain this" precursor)

Today the chat is the earlier tutor chat on the learner page (**Ask the tutor**, per course and topic). It becomes "Explain this" on a question in Phase 1.

1. As the learner with the active pass, open `/learner`. **Ask the tutor** is enabled. Pick a topic, press it, and send a message on `/learner/chat/:id`. A reply arrives (canned if `LLM_FAKE=true`). The limit is 20 messages a day.
2. Sign in as a learner without a pass (a fresh account). The page says "You are on free practice. A Civics Pass for your canton opens all questions, mock tests and Explain this." and the chat buttons are disabled. The API itself answers 403 `no_access` to a conversation request.
3. If the page says the tutor is offline, no AI key or `LLM_FAKE` is set.

## 9. Refund eligibility text

1. As the learner who just paid, the pricing panel on `/learner` says the last payment can be refunded until a date if fewer than 50 questions have been studied since buying (with the count so far), and "Write to support to ask for a refund." There is no refund button for learners.
2. Optional: answer 50 or more practice questions and reload; the text changes to say the payment can no longer be refunded. (Rule: 14 days, fewer than 50 questions; D-036.)

## 10. Admin: sign-in with authenticator

1. Sign out and open `/login`. Sign in with the seeded admin email and password. You are sent to `/2fa/setup` (**set up an authenticator app**): scan the QR code, enter the six-digit code.
2. Sign out and in again: the password is followed by `/2fa`, where the code is required. Admins cannot sign in without it, and cannot remove their password.
3. You land in the admin area (`/admin`). The Overview shows recent Stripe events as processed and the number of active entitlements.

## 11. Admin: learners, search, manual grant

1. Open **Learners** (`/admin/learners`). The accounts you made are listed. Type part of an address in **Search by email**: the list narrows.
2. Open a learner without a pass. The detail shows age confirmation, terms version, payments and **Access by canton**.
3. Under **Grant access**, choose canton Zurich and an end date, press **Grant**. You should see "Access for ZH granted until ...". Sign in as that learner (or **View as**, staging and local only): status is active and the chat is available. This is how staging is tested without Stripe, and is recorded in the audit log.

## 12. Admin: refund and end of access

1. Open the learner who paid by card (step 6), under Payments. The payment shows with its refund text.
2. Press **Refund** (if outside the rule the button reads **Refund anyway** and asks for a second confirmation). Confirm.
3. The message says the refund was requested. Access does not change yet. Within seconds Stripe sends `charge.refunded`; reload: the payment shows "Refunded on ..." and the access entry ends.
4. Sign in as that learner: status is back to free practice, the chat is disabled, and **Buy** is available again.

## 13. Account deletion and what remains

1. As a learner, open `/account` and scroll to **Delete my account**. Read what is kept (billing records).
2. Try to delete straight away without re-authenticating: the app asks for it. Enter your password, or press the button to receive a sign-in link and open it (a link opened in the last 10 minutes counts; signing in with a password alone does not).
3. Tick "I understand that my account and learning data will be deleted for good." and press **Delete my account**. You land on `/account/deleted` ("Your account is deleted"), and a confirmation email is sent.
4. Sign-in with that address now fails. In the admin area the learner is gone from **Learners**.
5. What remains: the payment row, with no user id or email, only an HMAC of the address (`payments.email_hash`); AI call records and Stripe events without identifiers; one `user.self_delete` audit row. See [runbooks/account-deletion.md](runbooks/account-deletion.md) and [DATA_INVENTORY.md](DATA_INVENTORY.md). Optional check on the server: `docker compose -f infra/docker-compose.yml --env-file .env exec postgres psql -U civics -d civics -c "select id, user_id, email_hash from payments"`.

## 14. Server checks (staging)

1. Health: `curl -i https://app.civics-staging.swisssciencetutors.ch/api/health` returns 200 and `{"status":"ok","env":"staging"}`.
2. Certificate: the browser shows a valid padlock for both host names; `curl -vI` shows a certificate issued for the name and not expired.
3. Nightly backup: `docker compose -f infra/docker-compose.yml --env-file .env exec backup ls -la /backups` lists a `civics-<stamp>.sql.gz.gpg` file from last night (on the first day, run the backup once and check; see [runbooks/backups-and-restore.md](runbooks/backups-and-restore.md)).
4. Worker: `docker compose ... logs --tail 50 worker` shows no errors. The tutor site still loads (the edge Caddy was reloaded).
5. Locally, skip this step except for `/api/health` on http://localhost:8000.

## Gate A checklist

From PLAN.md, Phase 0. Tick when seen.

- [ ] REUSE.md written and approved.
- [ ] New repository from a copy of the SST app; CI and tests pass after the removals.
- [ ] Learner and admin accounts with email sign-in links.
- [ ] Stripe one-off payments working in test mode, with entitlements per canton.
- [ ] Staging site live on Infomaniak with its own domain, TLS and nightly backups.

Known gaps to accept or fix before signing: CI needs the GitHub repository; interface locales for the five newer languages are machine drafts and miss some billing strings (0.8); German learner screens partly use "du"; the Landing page still carries old SST copy; the main JavaScript chunk is over 500 kB.

Signed off by Chris: ______________________  Date: ______________
