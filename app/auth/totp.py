"""Time-based one-time passwords for authenticator apps."""

from __future__ import annotations

import pyotp

from app.config import get_settings


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_label: str) -> str:
    issuer = get_settings().tutor_name
    return pyotp.TOTP(secret).provisioning_uri(name=account_label, issuer_name=issuer)


def verify_code(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
