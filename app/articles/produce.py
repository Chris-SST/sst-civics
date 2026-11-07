"""Production of one article version: research, writing, deterministic checks, the
independent fact review with up to two fix rounds, and the translations with their own
independent review and one fix round each.

The caller (app/articles/workflow.py) has already claimed the article, so no two productions
of the same article run at once. Every AI call goes through app/llm/articles.py and is
written to the cost log; the article's `cost_chf` adds them up. A production run stops with
`needs_attention` when the fact review still fails after the fix rounds, when fewer than two
sources could be read, when an AI call fails, when the run costs more than
ARTICLES_COST_CAP_CHF, or when the monthly AI budget is used up. A translation that still
fails after its fix round is skipped (not published) and noted; it never blocks English."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles import glossary, research
from app.articles.constants import (
    GUIDE_KEYS,
    GUIDE_PAGE_TOPICS,
    LANGUAGE_NAMES,
    SEGMENTS,
    WORDS,
)
from app.articles.validate import validate_article, validate_translation
from app.config import get_settings
from app.llm import articles as ai
from app.llm.content import BudgetExceeded, check_budget
from app.llm.service import LANGUAGE_NAMES as PROMPT_LANGUAGE_NAMES
from app.models import (
    ART_CHANGES_REQUESTED,
    ART_DRAFTING,
    ART_PUBLISHED,
    ART_READY,
    ART_RESEARCHING,
    ART_REVIEWING,
    ART_TRANSLATING,
    Article,
)
from app.study.clock import ZURICH

log = logging.getLogger(__name__)

FACT_FIX_ROUNDS = 2
VALIDATION_FIX_ROUNDS = 2
BLOCKING = ("blocker", "major")


class ProductionStop(Exception):
    """The run cannot finish; the article goes to needs_attention with this reason."""

    def __init__(self, reason: str, findings: list[dict[str, Any]] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.findings = findings or []


def pending_feedback(article: Article) -> list[dict[str, Any]]:
    return [f for f in article.feedback or [] if not f.get("applied_revision")]


def blocking(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in findings if f.get("severity") in BLOCKING]


def normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Model output to an article version: stripped strings, a lower-case slug."""
    out = {
        "title": str(data.get("title", "")).strip(),
        "slug": str(data.get("slug", "")).strip().lower(),
        "description": str(data.get("description", "")).strip(),
        "summary": [str(s).strip() for s in data.get("summary") or []],
        "faq": [
            {"q": str(f.get("q", "")).strip(), "a": str(f.get("a", "")).strip()}
            for f in data.get("faq") or []
            if isinstance(f, dict)
        ],
        "sources": [
            {"title": str(s.get("title", "")).strip(), "url": str(s.get("url", "")).strip()}
            for s in data.get("sources") or []
            if isinstance(s, dict)
        ],
        "related": [str(k).strip() for k in data.get("related") or []],
        "body": str(data.get("body", "")).strip(),
    }
    return out


class Run:
    """One production run of one article: shared context and the cost tally."""

    def __init__(self, db: AsyncSession, article: Article, now: datetime):
        self.db = db
        self.article = article
        self.now = now
        self.settings = get_settings()
        self.start_cost = float(article.cost_chf or 0.0)
        self.plan_keys: set[str] = set()
        self.live_keys: set[str] = set()
        self.plan_titles: dict[str, str] = {}
        self.draft: dict[str, Any] | None = None  # the latest version that passed the checks

    async def load_context(self) -> None:
        rows = (await self.db.execute(select(Article.key, Article.status, Article.plan))).all()
        self.plan_keys = {k for k, _, _ in rows}
        self.live_keys = {k for k, s, _ in rows if s == ART_PUBLISHED}
        self.plan_titles = {k: (p or {}).get("title", k) for k, _, p in rows}

    @property
    def run_cost(self) -> float:
        return float(self.article.cost_chf or 0.0) - self.start_cost

    async def spend(self, *results: ai.CallResult) -> None:
        for r in results:
            self.article.cost_chf = float(self.article.cost_chf or 0.0) + await ai.record(
                self.db, r
            )
        await self.db.commit()

    async def guard(self) -> None:
        """Before each AI step: the per-run cost cap and the monthly budget."""
        cap = self.settings.articles_cost_cap_chf
        if cap > 0 and self.run_cost >= cap:
            raise ProductionStop(
                f"cost cap reached: this run has cost CHF {self.run_cost:.2f} "
                f"(ARTICLES_COST_CAP_CHF {cap:.2f})"
            )
        try:
            await check_budget(self.db)
        except BudgetExceeded as exc:
            raise ProductionStop(f"monthly AI budget reached: {exc}") from exc

    async def set_status(self, status: str) -> None:
        self.article.status = status
        await self.db.commit()

    def note(self, entry: dict[str, Any]) -> None:
        entry = {"at": self.now.isoformat(), "revision": self.article.revision + 1, **entry}
        self.article.reviews = [*(self.article.reviews or []), entry]

    # --- payloads ---------------------------------------------------------------------

    def article_brief(self) -> dict[str, Any]:
        a, plan = self.article, self.article.plan
        low, high = WORDS[a.kind]
        nominal = (900, 1300) if a.kind == "article" else (1200, 1800)
        return {
            "key": a.key,
            "kind": a.kind,
            "category": a.category,
            "canton": a.canton,
            "planned_title": plan.get("title"),
            "brief": plan.get("brief"),
            "outline": plan.get("outline") or [],
            "must_cover": plan.get("must_cover") or [],
            "suggested_related": plan.get("related") or [],
            "word_range": list(nominal),
            "hard_word_limits": [low, high],
            "url_segment": SEGMENTS[a.kind]["en"],
        }

    def link_targets(self) -> dict[str, Any]:
        links_to = self.article.plan.get("links_to") or []
        return {
            "guide_pages": {
                k: GUIDE_PAGE_TOPICS.get(k, k) for k in GUIDE_KEYS if k in GUIDE_PAGE_TOPICS
            },
            "articles": [
                {"key": k, "title": self.plan_titles.get(k, k), "published": k in self.live_keys}
                for k in links_to
                if k in self.plan_keys and k != self.article.key
            ],
        }

    def sources(self) -> list[dict[str, str]]:
        return research.excerpts(self.article.sources_read, research.focus_of(self.article.plan))

    def today(self) -> str:
        return self.now.astimezone(ZURICH).date().isoformat()

    # --- English ------------------------------------------------------------------------

    def problems(self, content: dict[str, Any]) -> list[str]:
        return validate_article(
            content,
            kind=self.article.kind,
            lang="en",
            plan_keys=self.plan_keys,
            read_urls=research.read_urls(self.article.sources_read),
        )

    async def ask(
        self,
        purpose: str,
        prompt: str,
        model: str,
        payload: dict[str, Any],
        schema,
        effort: str,
        max_tokens: int = 16_000,
    ) -> dict[str, Any]:
        await self.guard()
        result = await ai.call(
            purpose=purpose,
            prompt_name=prompt,
            model=model,
            payload=payload,
            schema=schema,
            effort=effort,
            max_tokens=max_tokens,
        )
        await self.spend(result)
        if not result.ok:
            raise ProductionStop(f"{purpose} failed: {result.error}")
        return result.data or {}

    async def write(self) -> dict[str, Any]:
        s = self.settings
        payload = {
            "today": self.today(),
            "article": self.article_brief(),
            "links": self.link_targets(),
            "sources": self.sources(),
        }
        data = await self.ask(
            ai.PURPOSE_WRITE,
            ai.PROMPT_WRITE,
            s.articles_write_model,
            payload,
            ai.ARTICLE_SCHEMA,
            s.articles_effort,
        )
        return normalise(data)

    async def fix(
        self,
        content: dict[str, Any],
        *,
        findings: list[dict[str, Any]],
        owner_feedback: list[str] | None = None,
        kind: str,
    ) -> tuple[dict[str, Any], list[str]]:
        s = self.settings
        payload = {
            "today": self.today(),
            "reason": kind,
            "owner_feedback": owner_feedback or [],
            "findings": findings,
            "article": self.article_brief(),
            "links": self.link_targets(),
            "current_version": content,
            "sources": self.sources(),
        }
        data = await self.ask(
            ai.PURPOSE_FIX,
            ai.PROMPT_FIX,
            s.articles_write_model,
            payload,
            ai.FIX_SCHEMA,
            s.articles_effort,
        )
        changes = [str(c) for c in data.get("changes") or []]
        return normalise(data), changes

    async def ensure_valid(self, content: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(VALIDATION_FIX_ROUNDS + 1):
            problems = self.problems(content)
            if not problems:
                self.draft = content
                return content
            self.note({"kind": "validation", "lang": "en", "problems": problems})
            if attempt == VALIDATION_FIX_ROUNDS:
                break
            findings = [
                {"claim": "format", "problem": p, "severity": "blocker", "fix": "Correct it."}
                for p in problems
            ]
            content, _ = await self.fix(content, findings=findings, kind="format_check")
        raise ProductionStop(
            "the text still breaks the format rules after the fix rounds: " + "; ".join(problems)
        )

    async def review(self, content: dict[str, Any], owner_feedback: list[str]) -> list[dict]:
        s = self.settings
        payload = {
            "today": self.today(),
            "article": self.article_brief(),
            "owner_feedback": owner_feedback,
            "version": content,
            "sources": self.sources(),
        }
        data = await self.ask(
            ai.PURPOSE_REVIEW,
            ai.PROMPT_REVIEW,
            s.articles_review_model,
            payload,
            ai.REVIEW_SCHEMA,
            s.articles_effort,
            max_tokens=12_000,
        )
        findings = [f for f in data.get("findings") or [] if isinstance(f, dict)]
        self.note(
            {
                "kind": "fact_review",
                "verdict": data.get("verdict"),
                "findings": findings,
                "model": s.articles_review_model,
            }
        )
        return findings

    async def english(self, feedback: list[dict[str, Any]]) -> dict[str, Any]:
        owner = [f["text"] for f in feedback]
        await self.set_status(ART_DRAFTING)
        if owner and self.article.english:
            current = {k: v for k, v in self.article.english.items() if k != "checked"}
            content, changes = await self.fix(
                current, findings=[], owner_feedback=owner, kind="owner_feedback"
            )
            self.note({"kind": "fix", "reason": "owner_feedback", "changes": changes})
        else:
            content = await self.write()
        content = await self.ensure_valid(content)
        await self.set_status(ART_REVIEWING)
        for rnd in range(FACT_FIX_ROUNDS + 1):
            findings = await self.review(content, owner)
            if not blocking(findings):
                return {**content, "checked": self.today()}
            if rnd == FACT_FIX_ROUNDS:
                raise ProductionStop(
                    f"the fact review still finds problems after {FACT_FIX_ROUNDS} fix rounds",
                    blocking(findings),
                )
            content, changes = await self.fix(
                content, findings=findings, owner_feedback=owner, kind="fact_review"
            )
            self.note(
                {"kind": "fix", "reason": "fact_review", "round": rnd + 1, "changes": changes}
            )
            content = await self.ensure_valid(content)
        raise AssertionError("unreachable")

    # --- translations -------------------------------------------------------------------

    async def translate_one(
        self, lang: str, english: dict[str, Any]
    ) -> tuple[dict[str, Any], list[ai.CallResult]]:
        """Translate, check, review, and fix once. No database access (runs concurrently)."""
        s = self.settings
        calls: list[ai.CallResult] = []
        notes: list[dict[str, Any]] = []
        source = {
            "title": english["title"],
            "slug": english["slug"],
            "description": english["description"],
            "summary": english["summary"],
            "body": english["body"],
            "faq": english["faq"],
            "source_titles": [x["title"] for x in english["sources"]],
        }
        terms = glossary.glossary_for(lang)
        language = PROMPT_LANGUAGE_NAMES.get(lang, LANGUAGE_NAMES[lang])
        previous: dict[str, Any] | None = None
        findings: list[dict[str, Any]] = []
        for rnd in range(2):
            r = await ai.call(
                purpose=ai.PURPOSE_TRANSLATE,
                prompt_name=ai.PROMPT_TRANSLATE,
                model=s.articles_translate_model,
                payload={
                    "language": language,
                    "lang": lang,
                    "url_segment": SEGMENTS[self.article.kind][lang],
                    "english": source,
                    "glossary": terms,
                    "previous_translation": previous,
                    "findings": findings,
                },
                schema=ai.TRANSLATION_SCHEMA,
                effort=s.articles_translate_effort,
            )
            calls.append(r)
            if not r.ok:
                notes.append({"round": rnd + 1, "error": r.error})
                break
            content = self._translation(r.data or {}, english)
            problems = validate_translation(
                content, english, kind=self.article.kind, lang=lang, plan_keys=self.plan_keys
            )
            if problems:
                findings = [
                    {"claim": "format", "problem": p, "severity": "blocker", "fix": "Correct it."}
                    for p in problems
                ]
                notes.append({"round": rnd + 1, "kind": "validation", "problems": problems})
                previous = {k: content[k] for k in source if k in content}
                previous["source_titles"] = [x["title"] for x in content["sources"]]
                continue
            rv = await ai.call(
                purpose=ai.PURPOSE_TRANSLATION_REVIEW,
                prompt_name=ai.PROMPT_TRANSLATION_REVIEW,
                model=s.articles_translation_review_model,
                payload={
                    "language": language,
                    "lang": lang,
                    "english": source,
                    "translation": {
                        **{k: content[k] for k in ("title", "slug", "description", "summary")},
                        "body": content["body"],
                        "faq": content["faq"],
                        "source_titles": [x["title"] for x in content["sources"]],
                    },
                    "glossary": terms,
                },
                schema=ai.TRANSLATION_REVIEW_SCHEMA,
                effort=s.articles_translate_effort,
                max_tokens=12_000,
            )
            calls.append(rv)
            if not rv.ok:
                notes.append({"round": rnd + 1, "error": rv.error})
                break
            findings = [f for f in (rv.data or {}).get("findings") or [] if isinstance(f, dict)]
            notes.append(
                {
                    "round": rnd + 1,
                    "kind": "translation_review",
                    "verdict": (rv.data or {}).get("verdict"),
                    "findings": findings,
                }
            )
            if not blocking(findings):
                return {"status": "ok", "content": content, "notes": notes}, calls
            previous = {k: content[k] for k in source if k in content}
            previous["source_titles"] = [x["title"] for x in content["sources"]]
        return {"status": "failed", "content": None, "notes": notes}, calls

    @staticmethod
    def _translation(data: dict[str, Any], english: dict[str, Any]) -> dict[str, Any]:
        titles = [str(t).strip() for t in data.get("source_titles") or []]
        if len(titles) != len(english["sources"]):
            titles = [s["title"] for s in english["sources"]]
        content = normalise(
            {
                **data,
                "sources": [
                    {"title": t, "url": s["url"]}
                    for t, s in zip(titles, english["sources"], strict=True)
                ],
                "related": english.get("related") or [],
            }
        )
        return content

    async def translations(self, english: dict[str, Any]) -> dict[str, Any]:
        langs = self.settings.article_languages
        if not langs:
            return {}
        await self.set_status(ART_TRANSLATING)
        await self.guard()
        sem = asyncio.Semaphore(3)

        async def one(lang: str):
            async with sem:
                return lang, *await self.translate_one(lang, english)

        out: dict[str, Any] = {}
        for lang, result, calls in await asyncio.gather(*(one(lang) for lang in langs)):
            await self.spend(*calls)
            out[lang] = result
            for n in result["notes"]:
                self.note({"kind": "translation", "lang": lang, **n})
        return out


async def produce(db: AsyncSession, article: Article, now: datetime) -> str:
    """Run production for a claimed article. Returns the new status (ready,
    changes_requested when new suggestions arrived meanwhile, or needs_attention)."""
    from app.articles import workflow  # the needs_attention transition and its email

    run = Run(db, article, now)
    try:
        await run.load_context()
        feedback = pending_feedback(article)
        if not article.sources_read or not (feedback and article.english):
            await run.set_status(ART_RESEARCHING)
            article.sources_read = await research.fetch_sources(article.plan, now)
            await db.commit()
        n = len(research.readable(article.sources_read))
        if n < 2:
            raise ProductionStop(f"only {n} seed source(s) could be read; at least 2 are needed")
        english = await run.english(feedback)
        translations = await run.translations(english)
    except ProductionStop as stop:
        if run.draft is not None:
            # Keep the last version that passed the format checks, so Chris can read it on
            # the review page and suggest changes or publish it anyway. It is not
            # fact-checked, so it has no `checked` date and no translations.
            article.english = run.draft
            article.translations = {}
            article.revision += 1
            article.proposal_sent_at = None
            article.proposal_revision = None
        await workflow.mark_needs_attention(db, article, stop.reason, stop.findings, now)
        return article.status
    except Exception as exc:  # noqa: BLE001  any other failure stops the run the same way
        log.exception("Article %s: production failed", article.key)
        await db.rollback()
        article = await db.get(Article, article.id)
        await workflow.mark_needs_attention(
            db, article, f"unexpected error: {exc.__class__.__name__}", [], now
        )
        return article.status

    # Suggestions may have arrived while this run was working (the review page writes them
    # in its own session): read them fresh, mark the ones used, keep the rest for next time.
    await db.refresh(article, ["feedback"])
    used = {f["id"] for f in feedback}
    article.feedback = [
        {**f, "applied_revision": article.revision + 1} if f.get("id") in used else f
        for f in article.feedback or []
    ]
    article.english = english
    article.translations = translations
    article.revision += 1
    article.production_started_at = None
    article.proposal_sent_at = None
    article.proposal_revision = None
    article.last_error = None
    article.attempts = 0
    article.status = ART_CHANGES_REQUESTED if pending_feedback(article) else ART_READY
    await db.commit()
    log.info(
        "Article %s: revision %d %s (CHF %.2f this run, %s)",
        article.key,
        article.revision,
        article.status,
        run.run_cost,
        ", ".join(f"{k} {v['status']}" for k, v in translations.items()) or "no translations",
    )
    return article.status


def new_feedback(text: str, revision: int, now: datetime) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "at": now.isoformat(),
        "text": text,
        "revision": revision,
        "applied_revision": None,
    }
