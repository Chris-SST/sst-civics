from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import one_time
from app.auth.passwords import hash_password, password_is_acceptable
from app.auth.sessions import destroy_all_sessions
from app.db import get_db
from app.deps import require_roles
from app.email.messages import app_link
from app.jobs import send_email_job
from app.models import (
    PAYER_ROLES,
    ROLE_PARENT,
    ROLE_STUDENT,
    TOKEN_STUDENT_INVITE,
    Family,
    User,
)

router = APIRouter(prefix="/api/family", tags=["family"])
require_parent = require_roles(ROLE_PARENT)
require_payer = require_roles(*PAYER_ROLES)

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")

CURRICULA = (
    "ib_dp",
    "igcse",
    "a_level",
    "ib_myp",
    "swiss_matura",
    "french_bac",
    "university",
    "other",
)
COURSES = (
    "ib_maths_aa_sl",
    "ib_maths_aa_hl",
    "ib_maths_ai_sl",
    "ib_maths_ai_hl",
    "ib_physics_sl",
    "ib_physics_hl",
    "ib_chemistry_sl",
    "ib_chemistry_hl",
    "ib_biology_sl",
    "ib_biology_hl",
    "igcse_maths",
    "igcse_physics",
    "igcse_chemistry",
    "igcse_biology",
    "a_level_maths",
    "a_level_further_maths",
    "a_level_physics",
    "a_level_chemistry",
    "a_level_biology",
    "other",
)


class StudentIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    year_of_birth: int
    curriculum: str = "ib_dp"
    courses: list[str] = Field(default_factory=list, max_length=12)
    locale: Literal["en", "de", "fr"] = "en"
    username: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, max_length=200)
    invite_email: EmailStr | None = None


class StudentPatch(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    curriculum: str | None = None
    courses: list[str] | None = Field(default=None, max_length=12)
    locale: Literal["en", "de", "fr"] | None = None
    password: str | None = Field(default=None, max_length=200)


class FamilyPatch(BaseModel):
    locale: Literal["en", "de", "fr"]


class StudentOut(BaseModel):
    id: str
    first_name: str
    year_of_birth: int | None
    curriculum: str | None
    courses: list[str]
    locale: str
    username: str | None
    email: str | None
    invite_pending: bool
    last_login_at: str | None


def _student_out(u: User) -> StudentOut:
    return StudentOut(
        id=str(u.id),
        first_name=u.first_name,
        year_of_birth=u.year_of_birth,
        curriculum=u.curriculum,
        courses=list(u.courses or []),
        locale=u.locale,
        username=u.username,
        email=u.email,
        invite_pending=u.password_hash is None,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


def _validate_year(year: int) -> None:
    this_year = date.today().year
    if not (this_year - 25 <= year <= this_year - 5):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_year_of_birth")


def _validate_courses(curriculum: str | None, courses: list[str] | None) -> None:
    if curriculum is not None and curriculum not in CURRICULA:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_curriculum")
    if courses is not None and any(c not in COURSES for c in courses):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_course")


@router.get("/students", response_model=list[StudentOut])
async def list_students(
    user: User = Depends(require_payer), db: AsyncSession = Depends(get_db)
) -> list[StudentOut]:
    rows = (
        (
            await db.execute(
                select(User)
                .where(
                    User.family_id == user.family_id,
                    User.role == ROLE_STUDENT,
                    User.is_active.is_(True),
                )
                .order_by(User.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [_student_out(u) for u in rows]


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def add_student(
    body: StudentIn, user: User = Depends(require_parent), db: AsyncSession = Depends(get_db)
) -> StudentOut:
    _validate_year(body.year_of_birth)
    _validate_courses(body.curriculum, body.courses)
    student = User(
        family_id=user.family_id,
        role=ROLE_STUDENT,
        first_name=body.first_name.strip(),
        year_of_birth=body.year_of_birth,
        curriculum=body.curriculum,
        courses=body.courses,
        locale=body.locale,
    )
    if body.invite_email:
        email = body.invite_email.lower().strip()
        exists = await db.execute(select(User.id).where(User.email == email))
        if exists.first() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "email_in_use")
        student.email = email
    elif body.username and body.password:
        username = body.username.lower().strip()
        if not USERNAME_RE.match(username):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_username")
        if not password_is_acceptable(body.password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
        exists = await db.execute(select(User.id).where(User.username == username))
        if exists.first() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "username_in_use")
        student.username = username
        student.password_hash = hash_password(body.password)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "login_method_required")

    db.add(student)
    await db.flush()
    if student.email:
        token = await one_time.issue_token(db, student, TOKEN_STUDENT_INVITE)
        await send_email_job(
            "student_invite",
            student.locale,
            student.email,
            first_name=student.first_name,
            link=app_link(f"/accept-invite?token={token}"),
        )
    await db.commit()
    return _student_out(student)


async def _own_student(db: AsyncSession, user: User, student_id: str) -> User:
    try:
        sid = uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found") from None
    student = await db.get(User, sid)
    if (
        student is None
        or student.family_id != user.family_id
        or student.role != ROLE_STUDENT
        or not student.is_active
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return student


@router.patch("/students/{student_id}", response_model=StudentOut)
async def update_student(
    student_id: str,
    body: StudentPatch,
    user: User = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
) -> StudentOut:
    student = await _own_student(db, user, student_id)
    _validate_courses(body.curriculum, body.courses)
    if body.first_name is not None:
        student.first_name = body.first_name.strip()
    if body.curriculum is not None:
        student.curriculum = body.curriculum
    if body.courses is not None:
        student.courses = body.courses
    if body.locale is not None:
        student.locale = body.locale
    if body.password is not None:
        if not password_is_acceptable(body.password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
        student.password_hash = hash_password(body.password)
        await destroy_all_sessions(db, student.id)
    await db.commit()
    return _student_out(student)


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_student(
    student_id: str, user: User = Depends(require_parent), db: AsyncSession = Depends(get_db)
) -> None:
    student = await _own_student(db, user, student_id)
    await destroy_all_sessions(db, student.id)
    await db.delete(student)
    await db.commit()


@router.patch("/settings")
async def update_family(
    body: FamilyPatch, user: User = Depends(require_payer), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    family = await db.get(Family, user.family_id)
    if family is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_family")
    family.locale = body.locale
    user.locale = body.locale
    await db.commit()
    return {"status": "ok"}


@router.get("/options")
async def options() -> dict[str, list[str]]:
    return {"curricula": list(CURRICULA), "courses": list(COURSES)}
