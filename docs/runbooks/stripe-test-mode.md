# Stripe in test mode

Everything stays in test mode until Chris approves go-live. The bootstrap script refuses live keys. Run server commands from `/opt/civics`.

## Products

One-off payments only (Checkout in `mode=payment`); there are no subscriptions, invoices or Customer Portal. Prices are looked up by `lookup_key`, never hard-coded in the app (D-015):

| Lookup key | What it buys | Test amount | Access |
| --- | --- | --- | --- |
| `civics_pass_zh` | Civics Pass, canton of Zurich | CHF 29 | 6 months from payment |
| `civics_pass_ag` | Civics Pass, canton of Aargau | CHF 29 | 6 months from payment |
| `civics_extension` | Three more months on a pass | CHF 9 | 3 months, from the pass's expiry if it is still active, else from payment |

All prices are in CHF with `tax_behavior=inclusive`. Each price carries the metadata `access_months` (6 or 3), which the app shows as the period and copies into the Checkout Session.

Create or update them: `STRIPE_SECRET_KEY=sk_test_... python -m scripts.stripe_bootstrap`. The script is safe to re-run: it creates missing products and prices, brings names and metadata up to date, and when an amount differs it creates a new price, moves the lookup key to it (`transfer_lookup_key`) and archives the old one. Another amount: `--amount civics_pass_zh=3400` (rappen). The app picks up a changed price within 10 minutes (price cache).

`CANTONS_FOR_SALE` (default `zh`) decides which passes `GET /api/billing/products` lists and Checkout accepts. Aargau stays hidden until its content exists; then set `CANTONS_FOR_SALE=zh,ag` and restart the API.

## Payment methods

Dashboard → Settings → Payment methods: enable **Cards** and **TWINT**. The app does not set `payment_method_types`, so Checkout offers whatever is enabled there. TWINT needs CHF, which every price uses.

## Rules the app enforces at Checkout

- A pass cannot be bought while an active pass for the same canton exists (`409 pass_active`); the learner is offered the extension instead.
- An extension needs a pass for that canton that is active or ended less than 90 days ago (`409 no_pass_to_extend`). Admin-granted access counts as a pass; a trial does not.
- The Stripe customer is created on the first Checkout with the email address only.

## Webhook events

Subscribe the endpoint to exactly these four events:

| Event | What the app does |
| --- | --- |
| `checkout.session.completed` | If `payment_status=paid`: grants the pass (new entitlement, `source=stripe`, 6 months) or extends the pass by 3 months, and records a `Payment`. If unpaid (a delayed method), waits for the next event. |
| `checkout.session.async_payment_succeeded` | Same as a paid `checkout.session.completed`. |
| `checkout.session.async_payment_failed` | Records nothing; logged only. |
| `charge.refunded` | On a full refund: the entitlement the payment started ends at the refund time (for an extension, the 3 months come off again) and the payment is marked refunded. A partial refund changes no access. |

Each Checkout Session is fulfilled once (the `Payment` row is unique on `stripe_checkout_session_id`), so repeated or out-of-order deliveries are harmless. Events are stored once by event id in `stripe_events`.

Staging endpoint: `https://app.civics-staging.swisssciencetutors.ch/api/billing/webhook`. Dashboard → Developers → Webhooks → the endpoint → select the four events above and remove any `customer.subscription.*` or `invoice.*` events left from the source app.

## Local webhooks

```bash
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook \
  --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,charge.refunded
# copy whsec_... into STRIPE_WEBHOOK_SECRET and restart the API
```

`stripe trigger checkout.session.completed` sends a synthetic session without our metadata; it is logged as "without a matching user" or "unknown product" and grants nothing. Use a real Checkout from the app to see the full flow.

## Test a purchase

1. Sign up as a learner (canton Zurich) and open the home page: the Civics Pass panel shows CHF 29 for 6 months and "Free practice".
2. Click **Buy**. On the Stripe page pay with a test card:
   - Success: `4242 4242 4242 4242`, any future date, any CVC
   - Requires authentication: `4000 0025 0000 3155`
   - Declined: `4000 0000 0000 9995`
3. Back on `/billing/return`, the page polls `/api/auth/me` every 2 seconds until this Checkout Session shows as the latest payment, then shows the expiry date. After 30 seconds it says Stripe is slow; access still appears once the webhook arrives.
4. The panel now shows "Active until …" and an **Extend** button; **Buy** is gone for that canton.

## Test TWINT

TWINT is offered only for CHF, and only when it is enabled in the Dashboard (test mode). On the Checkout page choose TWINT; Stripe shows a simulated TWINT page with **Authorise** and **Fail** buttons instead of the TWINT app. Authorise sends `checkout.session.completed` (paid) and the pass is granted; Fail leaves the session unpaid and grants nothing. TWINT confirms immediately, so the `async_payment_*` events are normally not seen with it; they cover delayed methods if any are enabled later.

## Refunds

The rule (plan, D-015): a refund within 14 days of purchase if fewer than 50 questions have been studied since the purchase (`REFUND_WINDOW_DAYS`, `REFUND_MAX_QUESTIONS_STUDIED`).

- The learner sees on the home page whether their latest payment is still refundable (`GET /api/billing/refund-eligibility`) and is asked to write to support. There is no self-service refund button.
- An admin opens Admin → Learners → the learner → Payments and clicks **Refund** (`POST /api/admin/payments/{id}/refund`). Outside the rule the button reads **Refund anyway** and sends `override: true`. The app calls Stripe's refund API for the payment intent with an idempotency key and writes a `payment.refund` audit entry.
- Access is not changed by the button. It changes when `charge.refunded` arrives, which in test mode is within seconds.
- A refund made directly in the Stripe Dashboard has the same effect on access, through the same webhook, but leaves no audit entry; prefer the admin screen.

## Where events go

- `POST /api/billing/webhook` verifies the signature and stores the event in `stripe_events` (without contact and address details).
- The worker processes it (`process_stripe_event`), with up to five retries; `processed_at` and `error` show in Admin → Overview.
- There is no reconcile cron: access only ever changes through the four events above or an admin grant. A missed event is recovered by resending it (see `stripe-outage.md`).
- Nightly at 03:15 UTC the worker logs how many entitlements expire in the next 7 days (`log_expiring_entitlements`). It changes nothing and sends no email; it is the basis for a later reminder.
