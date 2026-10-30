# Phase 0 demo script (gate A)

Gate A: Chris can sign up, subscribe in test mode and log in as each role on staging.

Takes about 25 minutes. Two ways to run it: on **staging** (`https://staging.tutor.swisssciencetutors.ch`) or **locally** on your laptop. The role walk-through (steps 2 to 7) is the same for both.

You need: an authenticator app on your phone (Google Authenticator, Microsoft Authenticator or 1Password), and for the Stripe step the test keys from the Stripe Dashboard.

## 1a. Staging

Prerequisites, each a one-off:

- DNS `A` record `staging.tutor` → `83.228.196.57` and `AAAA` → `2001:1600:13:101::12dd` on `swisssciencetutors.ch`. Caddy fetches the TLS certificate automatically within a few minutes of the record resolving.
- Stripe test keys in `/opt/sst-tutor/.env` on the server (`STRIPE_SECRET_KEY=sk_test_...`), the webhook endpoint created in the Stripe Dashboard pointing at `https://staging.tutor.swisssciencetutors.ch/api/billing/webhook`, and its `whsec_...` in `STRIPE_WEBHOOK_SECRET`. Then `docker compose -f infra/docker-compose.yml --env-file .env up -d api worker` and `docker compose ... exec api python -m scripts.stripe_bootstrap`.

Staging sends real email through Google Workspace (as tutor@swisssciencetutors.ch), so verification and invite links arrive in the inbox you used.

The admin account for the demo was created with the seed script; the email and the one-time password are in `/opt/sst-tutor/.env.admin` on the server (delete that file after the first login).

## 1b. Locally (no Docker)

Follow "Run it locally in 10 minutes" in [README.md](../README.md). Emails appear as `.eml` files in `var/outbox/`; open them in any mail client or text editor and copy the link. Open http://localhost:8000.

## Switching roles without logging out (staging only)

Once you are in as admin, Admin → Families → Open a family shows a **View as** button next to each parent and student, and Admin → Tutors and admins shows one next to each tutor. A blue banner marks the borrowed view; **Back to admin** returns you. Every switch is logged, and the server refuses the feature in production. You still need to create the parent account once through the real sign-up below, because that is what gate A tests.

## 2. Parent: sign up, verify, add students

1. Open the app. Switch the language menu (top right) to Deutsch, then Français, then back to English: all text changes, including the plan cards.
2. **Create account** → "a parent or legal guardian", an email you can read, a password of 10+ characters, tick both boxes. Submit.
3. Open the confirmation email and follow the link: "Your email address is confirmed".
4. Try logging in **before** confirming on a second account if you like: the app refuses with "Please confirm your email address first" and offers to resend.
5. **Log in** as the parent. You land on *Your family*. Status shows "No plan".
6. **Add a student**: first name only, year of birth, IB Diploma, tick IB Maths AA HL and IB Physics SL, login method "username and password". Save. The card shows the username.
7. Add a second student with the invitation method and another email address of yours. The card shows "Invitation sent".
8. Open the invitation email → set a password → "All set".

## 3. Parent: subscribe in Stripe test mode

Needs the Stripe test keys; without them the plan cards show "Payments are not connected".

1. Under *Choose a plan* press **Start free trial** on AI-only monthly. Stripe Checkout opens in test mode showing quantity 2 (two students), CHF 24.00 each, 7-day trial.
2. Pay with card `4242 4242 4242 4242`, any future expiry, any CVC, any name. (TWINT also appears if enabled in the dashboard; test mode simulates approval.)
3. You return to *Payment*: "Waiting for Stripe…" then "Your plan is active" within a few seconds. This came from the webhook, not from the redirect.
4. Back on *Your family*: status **Active**, plan AI-only monthly, "Free trial ends on …", 2 students.
5. **Manage billing** opens the Stripe Customer Portal (change plan, payment method, cancel, invoices). Cancel at period end there and return: the card says "Ends on …". Reactivate if you like.
6. Under *Add-ons* buy one **Ask a tutor** credit (CHF 19): after the return the card shows "1 Ask-a-tutor credit".
7. Optional, in the Stripe Dashboard: Developers → Events shows each webhook delivered with a 200 response.

## 4. Student

1. Log out. Log in with the first student's **username** and password.
2. The student home shows their name, courses, the "is an AI" notice, the status Active, and the note that the chat tutor opens in Phase 1.
3. Visit `/admin` or `/parent` directly: the app sends the student back to their own page.
4. Log out; log in as the second student with their **email**: same page.

## 5. Admin with mandatory 2FA

1. Log in with the seeded admin email and password. The app does not let you in yet: *Set up your authenticator app* with a QR code and key.
2. Scan with your phone, enter the 6-digit code, **Turn on**. You land on *Admin*.
3. **Overview**: counts of families and roles, subscription statuses, and the recent Stripe events with "processed".
4. **Families**: search your parent email, **Open**: Stripe IDs, members, payments. Grant free access until a date with reason "SST lesson family", save: Access becomes Active even without a subscription (this is how SST lesson families get it free until the TutorCruncher link exists).
5. **Tutors and admins**: invite a tutor with a third email address, tag `ib_physics_hl`.
6. **Plans and limits**: change the AI-only daily limit from 60 to 50, save. (Prices are in Stripe; limits are here.)
7. Log out, log in again as admin: now it asks only for the 6-digit code.

## 6. Tutor

1. Open the tutor invitation email → set a password.
2. Log in as the tutor: 2FA set-up is mandatory here too. Scan, enter code.
3. Tutor dashboard: tagged course IB Physics HL, availability, the empty Ask-a-tutor queue (Phase 1).
4. Visit `/admin`: refused, back to the tutor page.

## 7. Password reset and security

1. Log out. **Forgotten your password?** with the parent email → open the email → set a new password. Logging in with the old one fails; the new one works; any other open parent session is logged out.
2. Open the same reset link again: "This link is invalid or has expired" (single use, 30 minutes).
3. Ten wrong passwords in a row on one account: "Too many attempts".
4. In the Stripe Dashboard, under Customers, the parent is one customer with one subscription and quantity 2, as the TWINT mandate rule requires.

## 8. What the tests cover

```bash
pytest -q            # 32 tests: sign-up and verification, login and rate limits, reset flow, students,
                     # staff 2FA, Stripe checkout params, webhook signature and idempotency,
                     # subscription lifecycle and access rules, add-on credits, admin free access, CSRF
cd web && npm run build
```

## Gate A checklist

| Gate A item | Shown in step |
| --- | --- |
| Sign up | 2 |
| Subscribe in test mode | 3 |
| Log in as parent | 2 |
| Log in as student (username and email) | 4 |
| Log in as admin with 2FA | 5 |
| Log in as tutor with 2FA | 6 |
| Brand and three languages | 2.1 |
| Staging with TLS | 1a |
| Backups | nightly container, see `docs/runbooks/backups-and-restore.md` |
