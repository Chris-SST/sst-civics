"""Random tokens and their hashes for sessions, email links and CSRF."""

from __future__ import annotations

import hashlib
import secrets


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
