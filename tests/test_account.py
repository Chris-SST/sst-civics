"""Account settings and self-deletion: optional passwords, profile choices, deletion and
what survives it (payments, AI cost records)."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select, update

from app.crypto import email_digest
from app.db import SessionLocal, utcnow
from app.email.backend import memory_outbox
from app.models import (
    Attempt,
    AuditLog,
    Conversation,
    Entitlement,
    LlmCall,
    Message,
    OneTimeToken,
    Payment,
    Question,
    QuestionReport,
    Session,
    StripeEvent,
    TopicMastery,
    User,
)
from tests.conftest import (
    LEARNER_PASSWORD,
    admin_logged_in,
    grant_access,
    learner_logged_in,
    link_sign_in,
    login,
    signup_body,
)

NEW_PASSWORD = "Another-pass-456"


async def _signup_without_password(api, email: str) -> None:
    r = await api.post("/api/auth/signup", json=signup_body(email, password=None))
    assert r.status_code == 201, r.text
    r = await link_sign_in(api, email)
    assert r.status_code == 200 and r.json()["status"] == "ok"


async def test_signup_without_password(api):
    await _signup_without_password(api, "nopw@example.ch")
    me = (await api.get("/api/auth/me")).json()
    assert me["user"]["has_password"] is False
    async with SessionLocal() as db:
        assert (await db.execute(select(User.password_hash))).scalar_one() is None
    # Password login fails like a wrong password; the link keeps working.
    r = await login(api, "nopw@example.ch", "anything-at-all")
    assert r.status_code == 401 and r.json()["detail"] == "invalid_credentials"


async def test_signup_rejects_a_short_password_when_one_is_given(api):
    r = await api.post("/api/auth/signup", json=signup_body("w@example.ch", password="short"))
    assert r.status_code == 400 and r.json()["detail"] == "weak_password"


async def test_signup_accepts_every_launch_language(api):
    for i, code in enumerate(("de", "en", "fr", "it", "pt", "es", "sq", "tr")):
        body = signup_body(f"l{i}@example.ch", locale=code, study_language=code)
        assert (await api.post("/api/auth/signup", json=body)).status_code == 201
    r = await api.post("/api/auth/signup", json=signup_body("x@example.ch", locale="ru"))
    assert r.status_code == 422


async def test_set_change_and_remove_password(api, api2):
    await _signup_without_password(api, "pw@example.ch")
    r = await api.post("/api/me/password", json={"new_password": "short"})
    assert r.status_code == 400 and r.json()["detail"] == "weak_password"
    r = await api.post("/api/me/password", json={"new_password": LEARNER_PASSWORD})
    assert r.status_code == 200
    assert (await api.get("/api/auth/me")).json()["user"]["has_password"] is True
    assert (await login(api2, "pw@example.ch", LEARNER_PASSWORD)).status_code == 200

    # Changing needs the current password and signs out other sessions.
    r = await api.post("/api/me/password", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 400 and r.json()["detail"] == "wrong_password"
    r = await api.post(
        "/api/me/password",
        json={"current_password": LEARNER_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 200
    assert (await api2.get("/api/auth/me")).status_code == 401
    assert (await api.get("/api/auth/me")).status_code == 200

    # Removing needs the current password; afterwards only the link signs in.
    r = await api.post("/api/me/password/remove", json={"current_password": "wrong-one-123"})
    assert r.status_code == 400 and r.json()["detail"] == "wrong_password"
    r = await api.post("/api/me/password/remove", json={"current_password": NEW_PASSWORD})
    assert r.status_code == 200
    assert (await login(api2, "pw@example.ch", NEW_PASSWORD)).status_code == 401
    r = await api.post("/api/me/password/remove", json={"current_password": NEW_PASSWORD})
    assert r.json()["detail"] == "no_password"


async def test_admin_cannot_remove_password_or_self_delete(api):
    await admin_logged_in(api)
    r = await api.post("/api/me/password/remove", json={"current_password": "Admin-pass-123"})
    assert r.status_code == 400 and r.json()["detail"] == "password_required_for_admins"
    r = await api.delete("/api/me", json={"password": "Admin-pass-123"})
    assert r.status_code == 403


async def test_update_profile(api):
    await learner_logged_in(api)
    r = await api.patch("/api/me", json={"locale": "tr", "study_language": "sq", "canton": "AG"})
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert (user["locale"], user["study_language"], user["canton"]) == ("tr", "sq", "ag")
    r = await api.patch("/api/me", json={"canton": "xx"})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_canton"
    r = await api.patch("/api/me", json={"study_language": "ru"})
    assert r.status_code == 422


async def _fill_learning_data(email: str) -> None:
    """Rows in every table that holds a learner's data."""
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.stripe_customer_id = "cus_test_1"
        q = Question(module_key="m", topic_code="t", question_text="Q?", answer="A")
        db.add(q)
        await db.flush()
        conv = Conversation(user_id=user.id, course_key="c", topic_code="t", topic_name="T")
        db.add(conv)
        await db.flush()
        db.add(Message(conversation_id=conv.id, user_id=user.id, seq=1, role="user", content="x"))
        db.add(Attempt(user_id=user.id, question_id=q.id, course_key="c", topic_code="t"))
        db.add(TopicMastery(user_id=user.id, course_key="c", topic_code="t"))
        db.add(QuestionReport(question_id=q.id, user_id=user.id, comment="typo"))
        q.report_count = 1
        db.add(
            Payment(user_id=user.id, stripe_invoice_id="in_1", amount_cents=2900, currency="chf")
        )
        db.add(
            LlmCall(user_id=user.id, purpose="tutor_reply", model="m", cost_chf=0.12, cost_usd=0.15)
        )
        db.add(
            StripeEvent(
                id="evt_1",
                type="invoice.paid",
                payload={
                    "id": "evt_1",
                    "type": "invoice.paid",
                    "data": {"object": {"customer": "cus_test_1", "customer_email": email}},
                },
            )
        )
        db.add(StripeEvent(id="evt_2", type="other", payload={"id": "evt_2", "type": "other"}))
        await db.commit()


async def _assert_deleted(email: str) -> None:
    async with SessionLocal() as db:
        assert (await db.execute(select(User).where(User.email == email))).first() is None
        for model in (
            Conversation,
            Message,
            Attempt,
            TopicMastery,
            QuestionReport,
            Entitlement,
            OneTimeToken,
            Session,
        ):
            count = (await db.execute(select(func.count()).select_from(model))).scalar_one()
            assert count == 0, model.__name__
        payment = (await db.execute(select(Payment))).scalar_one()
        assert payment.user_id is None and payment.amount_cents == 2900
        assert payment.email_hash == email_digest(email) and email not in payment.email_hash
        call = (await db.execute(select(LlmCall))).scalar_one()
        assert call.user_id is None and call.cost_chf == 0.12
        evt1 = await db.get(StripeEvent, "evt_1")
        evt2 = await db.get(StripeEvent, "evt_2")
        assert email not in str(evt1.payload) and "cus_test_1" not in str(evt1.payload)
        assert evt1.payload["type"] == "invoice.paid"
        assert evt2.payload == {"id": "evt_2", "type": "other"}
        question = (await db.execute(select(Question))).scalar_one()
        assert question.report_count == 0
        actions = (await db.execute(select(AuditLog.action))).scalars().all()
        assert "user.self_delete" in actions


async def test_delete_account_with_password(api):
    await learner_logged_in(api, "del@example.ch")
    await grant_access("del@example.ch")
    await _fill_learning_data("del@example.ch")
    memory_outbox.clear()

    r = await api.delete("/api/me", json={})
    assert r.status_code == 403 and r.json()["detail"] == "reauth_required"
    r = await api.delete("/api/me", json={"password": "wrong-password-1"})
    assert r.status_code == 400 and r.json()["detail"] == "wrong_password"
    r = await api.delete("/api/me", json={"password": LEARNER_PASSWORD})
    assert r.status_code == 200 and r.json() == {"status": "deleted"}

    assert len(memory_outbox.messages) == 1
    assert memory_outbox.messages[0].to == "del@example.ch"
    assert memory_outbox.messages[0].subject == "Your account is being deleted"
    assert (await api.get("/api/auth/me")).status_code == 401
    await _assert_deleted("del@example.ch")


async def test_delete_account_without_password_needs_a_fresh_link(api):
    await _signup_without_password(api, "nopw-del@example.ch")
    await _fill_learning_data("nopw-del@example.ch")
    # A link consumed more than 10 minutes ago no longer counts.
    async with SessionLocal() as db:
        await db.execute(update(Session).values(email_link_at=utcnow() - timedelta(minutes=11)))
        await db.commit()
    assert (await api.get("/api/auth/me")).json()["session"]["reauth_seconds_left"] == 0
    r = await api.delete("/api/me", json={})
    assert r.status_code == 403 and r.json()["detail"] == "reauth_required"
    # A password given by someone without one does not help either.
    r = await api.delete("/api/me", json={"password": "Whatever-123"})
    assert r.status_code == 403

    r = await link_sign_in(api, "nopw-del@example.ch", next="/account")
    assert r.status_code == 200
    r = await api.delete("/api/me", json={})
    assert r.status_code == 200
    await _assert_deleted("nopw-del@example.ch")


async def test_password_login_does_not_count_as_fresh_link(api):
    await learner_logged_in(api, "pwlogin@example.ch")
    assert (await api.get("/api/auth/me")).json()["session"]["reauth_seconds_left"] == 0
    r = await api.delete("/api/me", json={})
    assert r.status_code == 403
