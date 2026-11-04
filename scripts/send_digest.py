"""Send the daily operations digest now (D-072), the same email the worker sends each morning.

    python -m scripts.send_digest                 # send to DIGEST_TO, or every admin
    python -m scripts.send_digest --to a@b.ch     # send to one address instead
    python -m scripts.send_digest --dry-run       # print the email, send nothing

On the server: docker compose -p civics-prod exec worker python -m scripts.send_digest
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.db import SessionLocal
from app.ops.digest import run_digest


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", action="append", help="recipient (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="print instead of sending")
    args = parser.parse_args(argv)
    async with SessionLocal() as db:
        _, emails = await run_digest(db, send=not args.dry_run, to=args.to)
    if not emails:
        print("No recipient: set DIGEST_TO or create an admin account.", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"Subject: {emails[0].subject}\n\n{emails[0].text}")
    else:
        print(f"Sent to {len(emails)} recipient(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
