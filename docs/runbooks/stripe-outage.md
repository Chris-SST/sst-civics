# Stripe outage or missing webhooks

## Symptoms

- Learners cannot start Checkout (the app shows "Prices are not available right now" or "Something went wrong").
- A learner paid but `/billing/return` says Stripe has not confirmed, and the pass does not appear.
- Admin → Overview shows no new Stripe events although payments were expected, or events with errors.
- https://status.stripe.com reports an incident.

## What keeps working

- Login, studying and admin for everyone whose access is already recorded: access is computed from our database, never live from Stripe.
- Free practice for everyone.
- Webhook delivery is retried by Stripe for up to three days, and our worker retries processing up to five times. Each Checkout Session is fulfilled once, so late or repeated deliveries do no harm.

## What to do

1. Check https://status.stripe.com. If Stripe is down, wait; nothing on our side needs changing.
2. If Stripe is up but no events arrive: Dashboard → Developers → Webhooks → the endpoint → check recent deliveries and the signing secret. A rotated secret must be copied into `STRIPE_WEBHOOK_SECRET` in `/opt/civics/.env` and the API restarted. The endpoint is `https://app.civics-staging.swisssciencetutors.ch/api/billing/webhook` and must be subscribed to `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed` and `charge.refunded`. If deliveries fail with 502, check that the edge Caddy (tutor stack) is up and the civics `web` container is on the `edge` network.
3. If events arrive but show errors in Admin → Overview: read the worker logs (`cd /opt/civics && docker compose -f infra/docker-compose.yml --env-file .env logs worker`). After fixing the cause, the worker's retries pick the event up again; once those are used up, resend the event (next step).
4. If a learner was charged but has no access: Dashboard → Developers → Events → find the `checkout.session.completed` (or `charge.refunded`) event → **Resend** to the endpoint. There is no subscription reconciliation any more; resending is the way to replay a missed event. If that is not possible, grant access by hand from Admin → Learners while investigating (6 months for a pass), and note the Checkout Session id in the incident notes. Do not do both: a later resend after a manual grant extends the pass a second time.

## Afterwards

Note the incident date, cause and fix in `docs/PROGRESS.md`.
