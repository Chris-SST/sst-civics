# Stripe outage or missing webhooks

## Symptoms

- Learners cannot start Checkout (the app shows "Prices are not available right now" or "Something went wrong").
- Admin → Overview shows no new Stripe events although payments were expected, or events with errors.
- https://status.stripe.com reports an incident.

## What keeps working

- Login, studying and admin for everyone whose access is already recorded: access is computed from our database, never live from Stripe.
- Webhook delivery is retried by Stripe for up to three days, and our worker retries processing up to five times.

## What to do

1. Check https://status.stripe.com. If Stripe is down, wait; nothing on our side needs changing.
2. If Stripe is up but no events arrive: Dashboard → Developers → Webhooks → the endpoint → check recent deliveries and the signing secret. A rotated secret must be copied into `STRIPE_WEBHOOK_SECRET` in `/opt/civics/.env` and the API restarted. The endpoint is `https://app.civics-staging.swisssciencetutors.ch/api/billing/webhook`; if deliveries fail with 502, check that the edge Caddy (tutor stack) is up and the civics `web` container is on the `edge` network.
3. If events arrive but show errors in Admin → Overview: read the worker logs (`cd /opt/civics && docker compose -f infra/docker-compose.yml --env-file .env logs worker`). After fixing the cause, the nightly reconciliation corrects purchase state; to run it now, see "Reconcile by hand" in `stripe-test-mode.md`.
4. If learners were charged but have no access: run the reconciliation, then check the user in Admin. As a last resort grant access by hand from the admin screen while investigating.

## Afterwards

Note the incident date, cause and fix in `docs/PROGRESS.md`.
