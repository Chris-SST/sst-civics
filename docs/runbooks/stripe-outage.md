# Stripe outage or missing webhooks

## Symptoms

- Parents cannot start Checkout or open the billing portal (the app shows "Prices are not available right now" or "Something went wrong").
- Admin → Overview shows no new Stripe events although payments were expected, or events with errors.
- https://status.stripe.com reports an incident.

## What keeps working

- Login, students, admin, and the tutor (Phase 1) for everyone whose access is already recorded: access is computed from our database, never live from Stripe.
- Webhook delivery is retried by Stripe for up to three days, and our worker retries processing up to five times.

## What to do

1. Check https://status.stripe.com. If Stripe is down, wait; nothing on our side needs changing.
2. If Stripe is up but no events arrive: Dashboard → Developers → Webhooks → the endpoint → check recent deliveries and the signing secret. A rotated secret must be copied into `STRIPE_WEBHOOK_SECRET` and the API restarted.
3. If events arrive but show errors in Admin → Overview: read the worker logs (`docker compose ... logs worker`). After fixing the cause, the nightly reconciliation corrects subscription state; to run it now, see "Reconcile by hand" in `stripe-test-mode.md`.
4. If parents were charged but have no access: run the reconciliation, then check the family in Admin → Families. As a last resort grant free access for a few days from the family page while investigating.

## Afterwards

Note the incident date, cause and fix in `docs/PROGRESS.md`.
