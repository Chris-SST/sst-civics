"""Public configuration for the front end. The learner's pages read from app/tutoring and
app/questions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["portal"])


@router.get("/config")
async def public_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "tutor_name": settings.tutor_name,
        "terms_version": settings.terms_version,
        "billing_enabled": bool(settings.stripe_secret_key),
        "env": settings.app_env,
    }
