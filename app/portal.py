"""Student and tutor home endpoints. Phase 0 placeholders; the tutor chat, practice and
Ask-a-tutor queue arrive in Phase 1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import compute_access
from app.config import get_settings
from app.db import get_db
from app.deps import require_roles, require_staff
from app.models import ROLE_ADULT, ROLE_STUDENT, Family, User

router = APIRouter(prefix="/api", tags=["portal"])


@router.get("/student/home")
async def student_home(
    user: User = Depends(require_roles(ROLE_STUDENT, ROLE_ADULT)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    family = await db.get(Family, user.family_id) if user.family_id else None
    settings = get_settings()
    return {
        "first_name": user.first_name,
        "courses": user.courses or [],
        "curriculum": user.curriculum,
        "access": compute_access(family),
        "plan_key": family.plan_key if family else None,
        "tutor_name": settings.tutor_name,
        "tutor_available": False,  # Phase 1
    }


@router.get("/tutor/dashboard")
async def tutor_dashboard(user: User = Depends(require_staff)) -> dict[str, Any]:
    return {
        "first_name": user.first_name,
        "tagged_courses": user.tagged_courses or [],
        "available": user.available,
        "queue": [],  # Phase 1
        "time_log_minutes_this_month": 0,
    }


@router.get("/config")
async def public_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "tutor_name": settings.tutor_name,
        "main_site_url": settings.main_site_url,
        "terms_version": settings.terms_version,
        "billing_enabled": bool(settings.stripe_secret_key),
        "env": settings.app_env,
    }
