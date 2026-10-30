from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# Interface and study languages a learner can choose (app.models.LANGUAGES).
Locale = Literal["de", "en", "fr", "it", "pt", "es", "sq", "tr"]
# Pages a sign-in link may return to after signing in. A fixed list, so the link can never
# send anyone to an address outside the app.
LinkNext = Literal["/account"]


class SignupIn(BaseModel):
    """A learner signs up alone. Nothing beyond these fields is collected."""

    email: EmailStr
    # Optional: learners sign in with an email link unless they choose a password.
    password: str | None = Field(default=None, max_length=200)
    locale: Locale = "en"
    study_language: Locale = "en"
    canton: str = Field(default="zh", min_length=2, max_length=2)
    age_confirmed: bool = False  # self-declared "I am 16 or older"
    accept_terms: bool


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class LinkRequestIn(BaseModel):
    email: EmailStr
    locale: Locale = "en"  # language of the email; the interface language in use
    next: LinkNext | None = None


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class ProfileIn(BaseModel):
    locale: Locale | None = None
    study_language: Locale | None = None
    canton: str | None = Field(default=None, min_length=2, max_length=2)


class SetPasswordIn(BaseModel):
    current_password: str | None = Field(default=None, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class RemovePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)


class DeleteAccountIn(BaseModel):
    # Re-authentication: the password, or a sign-in link consumed in the last 10 minutes.
    password: str | None = Field(default=None, max_length=200)


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
    has_password: bool


class EntitlementOut(BaseModel):
    id: str
    canton: str
    starts_at: str
    expires_at: str
    source: str
    active: bool


class LatestPaymentOut(BaseModel):
    product: str
    canton: str
    paid_at: str
    refunded: bool
    # Lets the return page from Checkout see that its own session has been confirmed.
    checkout_session_id: str


class AccessOut(BaseModel):
    access: Literal["full", "none"]  # for the user's own canton
    canton: str
    entitlements: list[EntitlementOut]
    has_stripe_customer: bool
    # No active entitlement for the learner's canton: free practice only, no "Explain this".
    free_tier: bool = False
    # Per canton: an extension may be bought now (the pass is active or within the grace
    # period). The same rule the server enforces at checkout.
    can_extend: dict[str, bool] = {}


class SessionOut(BaseModel):
    mfa_pending: bool
    mfa_setup_required: bool
    # Seconds left in which this session counts as freshly re-authenticated by email link.
    reauth_seconds_left: int = 0
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
