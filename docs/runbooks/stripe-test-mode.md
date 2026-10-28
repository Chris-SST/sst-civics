# Stripe in test mode

Everything stays in test mode until Chris approves go-live. The bootstrap script refuses live keys.

## Prices

Prices are looked up by `lookup_key`, never hard-coded:

| Key | Product | Amount | Type |
| --- | --- | --- | --- |
| `ai_monthly` | AI-only | CHF 24 / month | subscription |
| `ai_annual` | AI-only | CHF 199 / year | subscription |
| `hybrid_monthly` | Hybrid | CHF 149 / month | subscription |
| `ask_tutor_single` | Ask a tutor | CHF 19 | one-off |
| `exam_sprint` | IB exam sprint | CHF 349 | one-off |

Create them: `python -m scripts.stripe_bootstrap` (with `STRIPE_SECRET_KEY=sk_test_...`). Changing a price: create a new price in the dashboard with the same lookup key and transfer the key (Stripe allows one active price per key). The app picks it up within 10 minutes.

## Payment methods

Dashboard → Settings → Payment methods: enable **Cards** and **TWINT**. TWINT for subscriptions needs API version `2026-05-27.dahlia` or later, which the app pins. One TWINT mandate per customer is allowed, which is why a family is one customer with one subscription and a second child raises the quantity.

## Local webhooks

```bash
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook
# copy whsec_... into STRIPE_WEBHOOK_SECRET and restart the API
stripe trigger checkout.session.completed      # sends a synthetic event
```

Synthetic events from `stripe trigger` will not match a family and are logged as ignored; use a real Checkout from the app to see the full flow.

## Test cards and TWINT

- Success: `4242 4242 4242 4242`
- Requires authentication: `4000 0025 0000 3155`
- Declined: `4000 0000 0000 9995`
- TWINT in test mode shows a simulated approval page.

## Test clocks (trial end, renewal, failed payment)

1. Dashboard → Customers → Test clocks → New. Create a customer under the clock.
2. In the app, that customer must be the family's `stripe_customer_id`. Easiest: create the family in the app first, then in the dashboard move the customer under a test clock (or create the subscription in the dashboard for the existing customer).
3. Advance the clock past the trial end: the app receives `customer.subscription.trial_will_end` (email to the parent) then `invoice.paid` and `customer.subscription.updated` (status active).
4. Attach a declining card and advance to the next renewal to see `invoice.payment_failed`, the warning email, and read-only access after 7 days.

## Where events go

- `POST /api/billing/webhook` verifies the signature and stores the event in `stripe_events`.
- The worker processes it (`process_stripe_event`), with retries on error; `processed_at` and `error` show in Admin → Overview.
- Every night at 03:15 the worker re-reads all subscriptions from Stripe, so a missed webhook heals itself.

## Reconcile by hand

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec worker \
  python -c "import asyncio; from worker.tasks import reconcile_subscriptions; print(asyncio.run(reconcile_subscriptions({})))"
```
