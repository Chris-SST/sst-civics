"""Encryption at rest for small secrets, and keyed hashes for pseudonymous records.

TOTP secrets are encrypted with Fernet (AES-128-CBC with HMAC-SHA256, from the maintained
`cryptography` package). The Fernet key is derived with HKDF-SHA256 from
`TOTP_ENCRYPTION_KEY`, or from `SECRET_KEY` when that is empty. Stored values carry a version
prefix so the scheme can change later without guessing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

log = logging.getLogger(__name__)

PREFIX = "f1:"


@lru_cache(maxsize=4)
def _fernet(material: str) -> Fernet:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"civics-totp-secret",
        info=b"totp secret encryption v1",
    ).derive(material.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def _current() -> Fernet:
    settings = get_settings()
    return _fernet(settings.totp_encryption_key or settings.secret_key)


def encrypt_secret(plain: str) -> str:
    return PREFIX + _current().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(stored: str) -> str | None:
    """The plain secret, or None if it cannot be decrypted (for example after a key change;
    an admin then resets that person's two-factor set-up)."""
    if not stored.startswith(PREFIX):
        log.warning("Encrypted value without a known prefix")
        return None
    try:
        return _current().decrypt(stored[len(PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken:
        log.warning("Encrypted value could not be decrypted with the current key")
        return None


class EncryptedString(TypeDecorator):
    """A string column whose value is encrypted on write and decrypted on read."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt_secret(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt_secret(value)


def email_digest(email: str) -> str:
    """Keyed SHA-256 of a normalised email address, for records kept after deletion."""
    key = get_settings().secret_key.encode("utf-8")
    return hmac.new(key, email.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
