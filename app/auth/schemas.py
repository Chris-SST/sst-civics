from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Locale = Literal["en", "de", "fr"]


class SignupIn(BaseModel):
    """A learner signs up alone. Nothing beyond these fields is collected."""

    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    locale: Locale = "en"
    study_language: Locale = "en"
    canton: str = Field(default="zh", min_length=2, max_length=2)
    age_confirmed: bool = False  # self-declared "I am 16 or older"
    accept_terms: bool


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class TotpCodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class UserOut(BaseModel):
    id: str
    role: str
    email: str | None
    locale: str
    study_language: str
    canton: str
    email_verified: bool
    totp_enabled: bool


class EntitlementOut(BaseModel):
    id: str
    canton: str
    starts_at: str
    expires_at: str
    source: str
    active: bool


class AccessOut(BaseModel):
    access: Literal["full", "none"]  # for the user's own canton
    canton: str
    entitlements: list[EntitlementOut]
    has_stripe_customer: bool


class SessionOut(BaseModel):
    mfa_pending: bool
    mfa_setup_required: bool
    impersonated_by: str | None = None


class MeOut(BaseModel):
    user: UserOut
    session: SessionOut
    access: AccessOut
    csrf_token: str


class LoginOut(BaseModel):
    status: Literal["ok", "mfa_required", "mfa_setup_required"]
    me: MeOut | None = None


class TotpSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
