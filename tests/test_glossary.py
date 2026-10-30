"""Glossary review (task 1.3): the admin list and edit, the write-back to
content/glossary/<lang>.yaml, and the learner's own glossary page data."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.content.importer import import_content
from app.db import SessionLocal
from app.models import GlossaryTerm
from scripts.content import sync_reviews
from tests.conftest import CONTENT_TODAY, FIXTURE_CONTENT, Api, admin_logged_in, learner_logged_in

TODAY = CONTENT_TODAY.isoformat()


@pytest.fixture
def content(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    shutil.copytree(FIXTURE_CONTENT, root)
    return root


async def imported(content: Path) -> None:
    async with SessionLocal() as db:
        assert (await import_content(db, content, today=CONTENT_TODAY)).ok


async def term_id(api: Api, term: str, lang: str = "en") -> str:
    rows = (await api.get(f"/api/review/glossary?lang={lang}")).json()["terms"]
    return next(t["id"] for t in rows if t["term"] == term)


def glossary_file(content: Path, lang: str = "en") -> dict:
    return yaml.safe_load((content / "glossary" / f"{lang}.yaml").read_text(encoding="utf-8"))


async def test_admin_lists_terms_for_a_language(api, api2, content):
    await imported(content)
    r = await api.get("/api/review/glossary?lang=en")
    assert r.status_code == 401 or r.status_code == 403  # not signed in
    await admin_logged_in(api)
    r = await api.get("/api/review/glossary?lang=en")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["lang"] == "en" and "tr" in data["languages"] and "de" not in data["languages"]
    assert [t["term"] for t in data["terms"]] == ["Bund", "Ständerat"]
    bund = data["terms"][0]
    assert bund["translation"] == "Confederation" and bund["note"] == "The federal level."
    assert bund["status"] == "draft" and bund["file_sync_pending"] is False
    assert (await api.get("/api/review/glossary?lang=fr")).json()["terms"] == []
    assert (await api.get("/api/review/glossary?lang=de")).status_code == 400
    await learner_logged_in(api2, "lena@example.ch")
    assert (await api2.get("/api/review/glossary?lang=en")).status_code == 403


async def test_edit_marks_reviewed_and_pending(api, content):
    await imported(content)
    admin = await admin_logged_in(api)
    tid = await term_id(api, "Ständerat")
    r = await api.patch(
        f"/api/review/glossary/{tid}",
        json={
            "translation": "Council of States (upper chamber)",
            "note": " The cantons' chamber. ",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "reviewed" and out["file_sync_pending"] is True
    assert out["translation"] == "Council of States (upper chamber)"
    assert out["note"] == "The cantons' chamber." and out["reviewed_by"] == admin.email
    async with SessionLocal() as db:
        row = (
            await db.execute(select(GlossaryTerm).where(GlossaryTerm.term == "Ständerat"))
        ).scalar_one()
        assert row.pending_changes and row.pending_changes[0]["action"] == "review"
    stats = (await api.get("/api/review/stats")).json()
    assert stats["pending_file_updates"] == 1
    assert (
        await api.patch(f"/api/review/glossary/{tid}", json={"translation": ""})
    ).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    r = await api.patch(f"/api/review/glossary/{missing}", json={"translation": "x"})
    assert r.status_code == 404
    # An import keeps the edit while it waits for write-back.
    await imported(content)
    async with SessionLocal() as db:
        row = (
            await db.execute(select(GlossaryTerm).where(GlossaryTerm.term == "Ständerat"))
        ).scalar_one()
        assert row.translation == "Council of States (upper chamber)" and row.status == "reviewed"


async def test_sync_writes_the_glossary_file_and_the_import_agrees(api, content, capsys):
    await imported(content)
    await admin_logged_in(api)
    tid = await term_id(api, "Bund")
    r = await api.patch(
        f"/api/review/glossary/{tid}",
        json={"translation": "Swiss Confederation", "note": "The federal level of the state."},
    )
    assert r.status_code == 200, r.text

    assert await sync_reviews.run(["--root", str(content), "--dry-run"]) == 0
    assert glossary_file(content)["terms"][0]["translation"] == "Confederation"  # nothing written
    assert await sync_reviews.run(["--root", str(content), "--today", TODAY]) == 0
    assert "1 file(s) written, 0 skipped" in capsys.readouterr().out

    text = (content / "glossary" / "en.yaml").read_text(encoding="utf-8")
    assert text.startswith("# EXAMPLE GLOSSARY FOR TESTS ONLY.")  # the header comment stays
    terms = {t["term_de"]: t for t in glossary_file(content)["terms"]}
    assert terms["Bund"]["translation"] == "Swiss Confederation"
    assert terms["Bund"]["note"] == "The federal level of the state."
    assert terms["Bund"]["status"] == "reviewed" and terms["Bund"]["reviewed_by"]
    assert terms["Bund"]["reviewed_at"] is not None
    assert "status" not in terms["Ständerat"] and "note" not in terms["Ständerat"]

    async with SessionLocal() as db:
        rows = (await db.execute(select(GlossaryTerm))).scalars().all()
        assert not any(g.file_sync_pending or g.pending_changes for g in rows)
    await imported(content)  # the file now says what the database says
    async with SessionLocal() as db:
        bund = (
            await db.execute(select(GlossaryTerm).where(GlossaryTerm.term == "Bund"))
        ).scalar_one()
        assert bund.translation == "Swiss Confederation" and bund.status == "reviewed"
    assert await sync_reviews.run(["--root", str(content)]) == 0
    assert "No review actions waiting" in capsys.readouterr().out


async def test_sync_skips_a_term_removed_from_the_file(api, content, capsys):
    await imported(content)
    await admin_logged_in(api)
    tid = await term_id(api, "Bund")
    await api.patch(f"/api/review/glossary/{tid}", json={"translation": "Federation"})
    data = glossary_file(content)
    data["terms"] = [t for t in data["terms"] if t["term_de"] != "Bund"]
    (content / "glossary" / "en.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )
    assert await sync_reviews.run(["--root", str(content)]) == 1
    assert "Bund: not in the file; skipped" in capsys.readouterr().out


async def test_learner_sees_terms_in_the_study_language(api, content):
    await imported(content)
    await learner_logged_in(api, "lena@example.ch")  # study language English
    r = await api.get("/api/study/glossary")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["lang"] == "en"
    assert [t["term"] for t in data["terms"]] == ["Bund", "Ständerat"]
    assert data["terms"][0] == {
        "term": "Bund",
        "translation": "Confederation",
        "note": "The federal level.",
        "reviewed": False,
    }
