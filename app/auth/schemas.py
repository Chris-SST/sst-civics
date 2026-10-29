from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Locale = Literal["en", "de", "fr"]


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    locale: Locale = "en"
    account_type: Literal["parent", "adult"] = "parent"
    guardian_confirmed: bool = False
    accept_terms: bool


class LoginIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)  # email or student username
    password: str = Field(min_length=1, max_length=200)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class TotpCodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class UserOut(BaseModel):
    id: str
    role: str
    email: str | None
    username: str | None
    first_name: str
    locale: str
    email_verified: bool
    totp_enabled: bool


class FamilyOut(BaseModel):
    id: str
    locale: str
    plan_key: str | None
    subscription_status: str | None
    quantity: int
    current_period_end: str | None
    trial_end: str | None
    cancel_at_period_end: bool
    payment_warning: bool
    free_access_until: str | None
    tutor_credits: int
    access: str
    has_stripe_customer: bool
    student_count: int


class SessionOut(BaseModel):
    mfa_pending: bool
    mfa_setup_required: bool
    impersonated_by: str | None = None


class MeOut(BaseModel):
    user: UserOut
    session: SessionOut
    family: FamilyOut | None
    csrf_token: str


class LoginOut(BaseModel):
    status: Literal["ok", "mfa_required", "mfa_setup_required"]
    me: MeOut | None = None


class TotpSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
