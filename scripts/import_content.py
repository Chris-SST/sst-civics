"""Fill the database from the content files. Runs on every deploy after the migrations
(the compose `migrate` service) and after `alembic upgrade head` locally.

Usage:
  python -m scripts.import_content [--root content]

Validates first and writes nothing if the files have errors; exits 1 then, so a deploy
stops. Rules: app/content/importer.py and content/README.md."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a file: make the repository importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.files import content_root  # noqa: E402
from app.content.importer import import_content  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402


async def run(root: Path | None) -> int:
    root = root or content_root()
    if not root.is_dir():
        print(f"Content directory {root} not found; nothing imported.", file=sys.stderr)
        return 1
    async with SessionLocal() as db:
        result = await import_content(db, root)
    await engine.dispose()
    if not result.report.ok:
        for issue in result.report.errors:
            print(f"ERROR   {issue.path}: {issue.message} [{issue.kind}]", file=sys.stderr)
        print("Content has errors; nothing imported.", file=sys.stderr)
        return 1
    for line in result.summary_lines():
        print(line)
    if result.errors:
        print("Import rolled back; nothing changed.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import content files into the database")
    parser.add_argument("--root", type=Path, default=None, help="content directory")
    args = parser.parse_args(argv)
    return asyncio.run(run(args.root))


if __name__ == "__main__":
    sys.exit(main())
