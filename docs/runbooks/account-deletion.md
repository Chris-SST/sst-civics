# Account deletion

Learners delete their own account on the Account page (`/account`), which calls `DELETE /api/me`.
The code is `app/auth/deletion.py`; the full field list is in `docs/DATA_INVENTORY.md`.

## How it works

1. The learner re-authenticates: with their password, or by opening a fresh sign-in link
   (the page offers to send one, returning to `/account`). A link counts for 10 minutes after it
   was opened. A password login on its own does not count.
2. The app deletes the data, queues a confirmation email ("Your account is being deleted") to the
   address on file, then commits. If the email cannot be queued, nothing is deleted.
3. The session cookie is cleared. The address can be used for a new sign-up straight away.

Admin accounts cannot delete themselves (so the app is never left without an admin), and nobody
can delete an account while an admin is viewing the app as that learner.

## What is deleted

The user row (email, languages, canton, age confirmation, terms acceptance, password hash, TOTP
secret, Stripe customer id), sessions, one-time tokens, tutor conversations and messages,
attempts, topic mastery, diagnostic runs, question reports and entitlements.

## What is kept, and why

| Record | Kept as | Why |
| --- | --- | --- |
| `payments` | Amount, currency, date, Stripe invoice id; `user_id` null; `email_hash` set to an HMAC-SHA256 of the email keyed with `SECRET_KEY` | Accounting records must be kept for 10 years (Swiss Code of Obligations, art. 958f). The hash lets us find the records if the person later asks about a payment and gives their address, without storing the address. |
| `llm_calls` | Tokens, cost, model, latency; `user_id` null | AI cost accounting and the monthly budget. These rows never contain message content. |
| `stripe_events` | Payloads naming the person's Stripe customer or account id reduced to `{id, type, redacted_at}` | The event id must stay for idempotency (Stripe re-sends events). Payloads are already stored without contact and address details. |
| `audit_log` | Admin actions stay; the person's id is removed where they were the actor; one `user.self_delete` row with the old account id | Accountability for admin actions and a record that the deletion happened. |
| Stripe's own records | The Stripe customer, invoices and payment methods remain in Stripe | Stripe is the payment processor and keeps its records under its own legal duties. If the person also asks for the Stripe customer to go, delete the customer in the Stripe Dashboard (Customers → the customer → Delete); invoices stay for accounting. |
| Backups | Nightly backups still contain the data | They expire after 30 days (`backups-and-restore.md`); the deletion is complete when the last backup holding the data has expired. |

## Handling a deletion request by email

If a learner cannot sign in and asks by email: check that the request comes from the address on
the account (reply to that address and ask them to confirm), then send them a sign-in link from
the login page with their address so they can delete the account themselves. If that is not
possible, an admin with database access runs the same code:

```
cd /opt/civics
docker compose -f infra/docker-compose.yml --env-file .env exec api python -c "
import asyncio
from sqlalchemy import select
from app.auth.deletion import delete_account
from app.db import SessionLocal
from app.models import User

async def main(email):
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        await delete_account(db, user)
        await db.commit()

asyncio.run(main('person@example.ch'))
"
```

This path sends no confirmation email; reply to the person yourself, and say that billing
records and backups are kept as described above.
