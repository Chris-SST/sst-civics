"""Password hashing with Argon2id through pwdlib. No hand-written cryptography."""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_hasher = PasswordHash((Argon2Hasher(),))

MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        # Run a hash anyway so timing does not reveal whether the account exists.
        _hasher.hash(password)
        return False
    return _hasher.verify(password, password_hash)


def password_is_acceptable(password: str) -> bool:
    return len(password) >= MIN_PASSWORD_LENGTH and not password.isspace()
